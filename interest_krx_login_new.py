import os
import subprocess
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DEBUG_PORT = "9222"
KRX_MAIN_URL = "https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd"

KRX_USER_ID = os.getenv("KRX_USER_ID", "yukiever")
KRX_USER_PASSWORD = os.getenv("KRX_USER_PASSWORD")

LINE = "=" * 100
DEBUG_LOG = False


def print_header(step_name: str):
    print(LINE)
    print(f"START :: {step_name}")
    print(LINE)
    print("Starting....\n")


def print_success(lines=None):
    print("[Success]")
    if lines:
        for line in lines:
            print(line)


def print_failed(lines=None):
    print("[Failed]")
    if lines:
        for line in lines:
            print(line)


def debug(message: str):
    if DEBUG_LOG:
        print(f"[DEBUG] {message}")


def pause(seconds):
    time.sleep(seconds)


# ---------------------------
# attach
# ---------------------------
def attach_driver():
    options = Options()
    options.add_experimental_option(
        "debuggerAddress", f"127.0.0.1:{DEBUG_PORT}"
    )
    return webdriver.Chrome(options=options)


# ---------------------------
# chrome 실행
# ---------------------------
def start_debug_chrome():
    subprocess.Popen(
        ["python", "interest_krx_chrome.py"],
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(6)


# ---------------------------
# driver 확보
# ---------------------------
def get_driver():
    try:
        return attach_driver()
    except Exception:
        start_debug_chrome()
        return attach_driver()


# ---------------------------
# 기본 대기
# ---------------------------
def wait_document_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


# ---------------------------
# 브라우저 창 활성화 보정
# ---------------------------
def activate_browser_window(driver):
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    try:
        driver.maximize_window()
    except Exception as e:
        debug(f"maximize_window failed: {e}")

    try:
        driver.execute_script("window.focus();")
    except Exception as e:
        debug(f"window.focus failed: {e}")

    pause(1)


# ---------------------------
# 로그인 상태 체크
# ---------------------------
def is_logged_in(driver):
    driver.switch_to.default_content()

    logout_candidates = [
        (By.ID, "jsLogoutBtn"),
        (By.XPATH, "//img[@title='로그아웃']"),
        (By.XPATH, "//a[.//img[@title='로그아웃']]"),
    ]

    for by, selector in logout_candidates:
        try:
            elems = driver.find_elements(by, selector)
            for elem in elems:
                if elem.is_displayed():
                    return True
        except Exception:
            pass

    login_candidates = [
        (By.XPATH, "//img[@title='로그인']"),
        (By.XPATH, "//a[.//img[@title='로그인']]"),
    ]

    for by, selector in login_candidates:
        try:
            elems = driver.find_elements(by, selector)
            for elem in elems:
                if elem.is_displayed():
                    return False
        except Exception:
            pass

    return False


# ---------------------------
# main window 정리
# ---------------------------
def keep_only_main_window(driver):
    main = None

    # 1) KRX 페이지 우선
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = driver.current_url

        if "data.krx.co.kr" in url:
            main = handle
            break

    # 2) new-tab 우선
    if main is None:
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            url = driver.current_url

            if "chrome://new-tab-page" in url:
                main = handle
                break

    # 3) http/https 페이지
    if main is None:
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            url = driver.current_url

            if url.startswith("http://") or url.startswith("https://"):
                main = handle
                break

    if main is None:
        raise Exception("No usable browser window found")

    for handle in driver.window_handles[:]:
        if handle == main:
            continue

        driver.switch_to.window(handle)
        url = driver.current_url

        if url.startswith("chrome://omnibox-popup"):
            continue

        try:
            driver.close()
        except Exception:
            pass

    driver.switch_to.window(main)


# ---------------------------
# 로그인 iframe 진입
# ---------------------------
def switch_to_login_iframe(driver, timeout=20):
    driver.switch_to.default_content()

    WebDriverWait(driver, timeout).until(
        EC.frame_to_be_available_and_switch_to_it(
            (By.ID, "COMS001_FRAME")
        )
    )


# ---------------------------
# KRX 알림 확인 버튼 처리
# ---------------------------
def close_alert_if_exists(driver):
    # 1) 브라우저 기본 alert
    try:
        alert = driver.switch_to.alert
        alert.accept()
        return True
    except Exception:
        pass

    # 2) 현재 context 안의 일반 확인 버튼
    try:
        buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(normalize-space(), '확인')]"
            " | //a[contains(normalize-space(), '확인')]"
            " | //span[contains(normalize-space(), '확인')]/ancestor::*[self::button or self::a][1]"
        )

        for btn in buttons:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].click();", btn)
                    return True
            except Exception:
                pass
    except Exception:
        pass

    return False


# ---------------------------
# iframe 상태에서 로그인 폼 값 확인
# ---------------------------
def read_login_form_state(driver):
    return driver.execute_script(
        """
        return {
            mbrId: document.querySelector('input[name="mbrId"]')?.value || '',
            mbrIdLen: document.querySelector('input[name="mbrId"]')?.value.length || 0,
            pwLen: document.querySelector('input[name="pw"]')?.value.length || 0,
            pwE2eLen: document.querySelector('input[name="pw__E2E__"]')?.value.length || 0,
            pwClass: document.querySelector('input[name="pw"]')?.className || '',
            activeName: document.activeElement?.name || '',
            activeId: document.activeElement?.id || ''
        };
        """
    )


# ---------------------------
# 중복 로그인 confirm 처리
# ---------------------------
def handle_duplicate_login_confirm_in_current_context(driver):
    try:
        texts = driver.find_elements(
            By.XPATH,
            "//*[contains(normalize-space(), '이미 로그인된 계정입니다')]"
        )

        visible_text_found = False

        for elem in texts:
            try:
                if elem.is_displayed():
                    visible_text_found = True
                    break
            except Exception:
                pass

        if not visible_text_found:
            return False

        confirm_button_candidates = [
            (By.XPATH, "//button[contains(normalize-space(), '확인')]"),
            (By.XPATH, "//a[contains(normalize-space(), '확인')]"),
            (By.XPATH, "//*[contains(@class, 'btn-confirm')]"),
            (By.XPATH, "//*[contains(@class, 'ui-button') and contains(normalize-space(), '확인')]"),
            (By.XPATH, "//span[contains(normalize-space(), '확인')]/ancestor::button[1]"),
        ]

        for by, selector in confirm_button_candidates:
            buttons = driver.find_elements(by, selector)

            for btn in buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        driver.execute_script("arguments[0].click();", btn)
                        return True
                except Exception:
                    pass

        return False

    except Exception:
        return False


def handle_duplicate_login_confirm(driver):
    # 1) 현재 context 우선
    if handle_duplicate_login_confirm_in_current_context(driver):
        pause(4)
        return True

    # 2) default content에서 확인
    try:
        driver.switch_to.default_content()

        if handle_duplicate_login_confirm_in_current_context(driver):
            pause(4)
            return True
    except Exception:
        pass

    # 3) 다시 iframe 들어가서 확인
    try:
        switch_to_login_iframe(driver, timeout=5)

        if handle_duplicate_login_confirm_in_current_context(driver):
            pause(4)
            return True
    except Exception:
        pass

    return False


# ---------------------------
# 로그인 후 결과 대기
# ---------------------------
def wait_after_login_submit(driver):
    pause(1)

    duplicate_handled = handle_duplicate_login_confirm(driver)

    if duplicate_handled:
        pause(4)
    else:
        pause(2)

    try:
        close_alert_if_exists(driver)
    except Exception:
        pass

    pause(2)


# ---------------------------
# 입력 보정
# ---------------------------
def set_input_value_with_events(driver, selector, value):
    driver.execute_script(
        """
        const el = document.querySelector(arguments[0]);
        if (!el) {
            return false;
        }

        el.scrollIntoView({ block: 'center' });
        el.focus();
        el.value = arguments[1];

        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));

        return true;
        """,
        selector,
        value
    )


# ---------------------------
# KRX 자체 로그인
# ---------------------------
def do_krx_login(driver):
    activate_browser_window(driver)

    if not KRX_USER_PASSWORD:
        raise Exception(
            "KRX_USER_PASSWORD 환경변수가 비어있어. "
            "PowerShell에서는 $env:KRX_USER_PASSWORD=\"비밀번호\" "
            "CMD에서는 set KRX_USER_PASSWORD=비밀번호 설정 후 다시 실행 필요."
        )

    wait = WebDriverWait(driver, 20)

    # 1) 우측 상단 로그인 클릭
    login_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//a[.//img[@title='로그인']]")
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_btn)
    pause(0.3)
    driver.execute_script("arguments[0].click();", login_btn)

    pause(2)

    # 2) 로그인 iframe 진입
    switch_to_login_iframe(driver, timeout=20)

    pause(2)

    # 3) 아이디 입력
    id_input = wait.until(
        EC.visibility_of_element_located(
            (By.ID, "mbrId")
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", id_input)
    pause(0.3)

    id_input.click()
    pause(0.2)
    id_input.clear()
    pause(0.2)
    id_input.send_keys(KRX_USER_ID)
    pause(0.5)

    set_input_value_with_events(driver, 'input[name="mbrId"]', KRX_USER_ID)
    pause(0.5)

    form_state = read_login_form_state(driver)
    debug(f"after id input = {form_state}")

    # 4) 비밀번호 입력
    pw_input = wait.until(
        EC.visibility_of_element_located(
            (By.NAME, "pw")
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pw_input)
    pause(0.3)

    pw_input.click()
    pause(0.5)

    pw_input.clear()
    pause(0.3)

    pw_input.send_keys(KRX_USER_PASSWORD)
    pause(0.7)

    form_state = read_login_form_state(driver)
    debug(f"after password send_keys = {form_state}")

    # KRX 키보드보안 필드에서 Selenium send_keys 값이 실제 value에 안 잡히는 경우 보정
    if form_state.get("pwLen", 0) == 0:
        set_input_value_with_events(driver, 'input[name="pw"]', KRX_USER_PASSWORD)

        pause(0.7)

        form_state = read_login_form_state(driver)
        debug(f"after password fallback = {form_state}")

    # 키보드보안 focusout 유도
    try:
        driver.execute_script(
            """
            const pw = document.querySelector('input[name="pw"]');

            if (pw) {
                pw.blur();
                pw.dispatchEvent(new Event('blur', { bubbles: true }));
                pw.dispatchEvent(new Event('focusout', { bubbles: true }));
            }

            if (window.bh && typeof window.bh.doFocusOut === 'function') {
                window.bh.doFocusOut();
            }
            """
        )
        pause(0.7)
    except Exception as e:
        debug(f"focusout script failed: {e}")

    form_state = read_login_form_state(driver)
    debug(f"before submit = {form_state}")

    if form_state.get("mbrIdLen", 0) == 0:
        raise Exception("아이디 값이 브라우저 폼에 들어가지 않았어.")

    if form_state.get("pwLen", 0) == 0:
        raise Exception("비밀번호 값이 브라우저 폼에 들어가지 않았어.")

    # 5) 로그인 버튼 클릭
    submit_btn = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a.jsLoginBtn")
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
    pause(0.3)
    driver.execute_script("arguments[0].click();", submit_btn)

    # 6) 로그인 결과/중복 로그인 팝업 처리
    wait_after_login_submit(driver)

    # 7) 기본 페이지 복귀 후 최종 확인
    driver.switch_to.default_content()

    return is_logged_in(driver)


# ---------------------------
# result 생성
# ---------------------------
def build_result(status, success_lines=None, error_lines=None, failed_lines=None):
    return {
        "status": status,
        "collected_dates": [datetime.now().strftime("%Y-%m-%d")],
        "success_lines": success_lines or [],
        "error_lines": error_lines or [],
        "failed_lines": failed_lines or [],
        "error_count": 0 if status == "SUCCESS" else 1
    }


# ---------------------------
# MAIN
# ---------------------------
def run():
    start = datetime.now()

    print_header("krx_login")

    try:
        driver = get_driver()

        keep_only_main_window(driver)

        driver.get(KRX_MAIN_URL)
        wait_document_ready(driver, timeout=30)

        activate_browser_window(driver)

        pause(2)

        # 분기 1: 이미 로그인된 상태
        if is_logged_in(driver):
            elapsed = (datetime.now() - start).total_seconds()

            success_lines = [
                "KRX already logged in",
                f"KRX Login Ready / elapsed={elapsed:.2f}s"
            ]

            print_success(success_lines)

            return build_result(
                status="SUCCESS",
                success_lines=success_lines
            )

        # 분기 2: 로그인 안 된 상태
        login_confirmed = do_krx_login(driver)

        elapsed = (datetime.now() - start).total_seconds()

        if not login_confirmed:
            failed_lines = [
                "KRX login submitted but login marker was not confirmed",
                f"elapsed={elapsed:.2f}s"
            ]

            print_failed(failed_lines)

            return build_result(
                status="FAILED",
                failed_lines=failed_lines,
                error_lines=failed_lines
            )

        success_lines = [
            "KRX ID/PW Login Success",
            f"KRX Login Ready / elapsed={elapsed:.2f}s"
        ]

        print_success(success_lines)

        return build_result(
            status="SUCCESS",
            success_lines=success_lines
        )

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()
        message = str(e)

        failed_lines = [
            message,
            f"elapsed={elapsed:.2f}s"
        ]

        print_failed(failed_lines)

        return build_result(
            status="FAILED",
            failed_lines=failed_lines,
            error_lines=[message]
        )


if __name__ == "__main__":
    run()