import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DEBUG_PORT = "9222"


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
    print("[STEP] run interest_krx_chrome.py...")

    subprocess.Popen(
        ["python", "interest_krx_chrome.py"],
        shell=True
    )

    time.sleep(6)


# ---------------------------
# driver 확보
# ---------------------------
def get_driver():

    try:
        print("[STEP] try attach 9222...")
        driver = attach_driver()
        print("[OK] attach success")
        return driver

    except:
        print("[WARN] 9222 not found → start debug chrome")

        start_debug_chrome()

        print("[STEP] re-attach...")
        driver = attach_driver()
        print("[OK] attach success (after start)")
        return driver


# ---------------------------
# 로그인 상태 체크 (🔥 수정 핵심)
# ---------------------------
def is_logged_in(driver):

    try:
        logout_btn = driver.find_element(By.XPATH, "//img[@title='로그아웃']")
        return logout_btn.is_displayed()
    except:
        return False


# ---------------------------
# 로그인
# ---------------------------
def do_login(driver):

    print("[STEP] login start")

    wait = WebDriverWait(driver, 20)

    # 로그인 버튼
    login_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//a[.//img[@title='로그인']]")
        )
    )
    driver.execute_script("arguments[0].click();", login_btn)
    print("[OK] login button clicked")

    # iframe 진입
    wait.until(
        EC.frame_to_be_available_and_switch_to_it(
            (By.ID, "COMS001_FRAME")
        )
    )
    print("[OK] iframe entered")

    # 네이버 버튼
    naver_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//*[contains(text(),'네이버')]")
        )
    )

    # before handles
    before_handles = set(driver.window_handles)

    # 네이버 클릭
    naver_btn.click()
    print("[OK] naver clicked")

    time.sleep(2)

    # iframe 빠져나오기
    driver.switch_to.default_content()

    # after handles
    after_handles = set(driver.window_handles)
    new_handles = list(after_handles - before_handles)

    if new_handles:
        driver.switch_to.window(new_handles[0])
        print("[OK] switched new window")
    else:
        print("[OK] same window flow")

    # 안정화
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    time.sleep(3)

    # 로그인 버튼 클릭
    login_btn = wait.until(
        EC.element_to_be_clickable(
            (By.ID, "log.login")
        )
    )
    login_btn.click()
    print("[OK] naver login submitted")

    time.sleep(3)

    print("[SUCCESS] login done")


# ---------------------------
# 디버그
# ---------------------------
def debug_windows(driver):
    print("===== WINDOW DEBUG =====")

    for i, handle in enumerate(driver.window_handles):
        driver.switch_to.window(handle)
        print(f"[{i}]")
        print(f" handle : {handle}")
        print(f" url    : {driver.current_url}")
        print(f" title  : {driver.title}")
        print("-----------------------")


# ---------------------------
# main window 정리
# ---------------------------
def keep_only_main_window(driver):
    print("[STEP] keep only main window")

    main = None

    # 1️⃣ new-tab 우선
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = driver.current_url

        if "chrome://new-tab-page" in url:
            main = handle
            break

    # 2️⃣ http/https 페이지
    if main is None:
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            url = driver.current_url

            if url.startswith("http://") or url.startswith("https://"):
                main = handle
                break

    # 3️⃣ 없으면 에러
    if main is None:
        raise Exception("No usable browser window found")

    # 4️⃣ 나머지 정리
    for handle in driver.window_handles[:]:
        if handle == main:
            continue

        driver.switch_to.window(handle)
        url = driver.current_url

        if url.startswith("chrome://omnibox-popup"):
            print(f"[SKIP] omnibox popup: {url}")
            continue

        try:
            driver.close()
            print(f"[OK] closed: {url}")
        except Exception as e:
            print(f"[WARN] close failed: {url} / {e}")

    # 5️⃣ main 복귀
    driver.switch_to.window(main)
    print(f"[OK] switched to main: {driver.current_url}")


# ---------------------------
# MAIN
# ---------------------------
def run():

    print("======================================================")
    print("START :: interest_krx_login (attach only)")
    print("======================================================")

    try:

        driver = get_driver()

        debug_windows(driver)

        keep_only_main_window(driver)

        print("[STEP] go to KRX")
        driver.get("https://data.krx.co.kr")
        time.sleep(2)

        # 🔥 로그인 상태 체크
        if is_logged_in(driver):
            print("[SKIP] already logged in → exit")
            return

        # 로그인 수행
        do_login(driver)

        print("======================================================")
        print("[SUCCESS] KRX ready")
        print("======================================================")

        debug_windows(driver)

    except Exception as e:

        print("======================================================")
        print("[FAILED]")
        print(str(e))
        print("======================================================")


if __name__ == "__main__":
    run()