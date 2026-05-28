"""KRX 웹에서 프로그램 매매 데이터를 일일 증분 수집하는 Selenium 스크립트다.

디버그 Chrome/Selenium으로 CSV를 내려받아 파싱하고 PostgreSQL에 저장한다.
브라우저 제어, 파일 다운로드, DB upsert가 포함되므로 운영 환경에서만 실행한다.
"""

import os
import glob
import time
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
from db_config import get_db_config
from psycopg2.extras import execute_batch

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from interest_log_format import print_step_log
from interest_get_holidays import is_holiday


DOWNLOAD_DIR = r"C:\Users\USER\Downloads"

START_DATE = "20240313"
END_DATE = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")

SEARCH_WAIT = 1.5

SOURCE = "krx"
VERSION = "1.0.0"

PROGRAM_URL = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020305"

DB_CONFIG = get_db_config()


def start_debug_chrome():
    subprocess.Popen(
        ["python", "interest_krx_chrome.py"],
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(7)


def start_driver():
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        return webdriver.Chrome(options=options)
    except Exception:
        start_debug_chrome()
        return webdriver.Chrome(options=options)


def get_conn():
    if not DB_CONFIG["password"]:
        raise Exception(
            "INTEREST_DB_PASSWORD 환경변수가 비어있어. "
            "PowerShell에서 $env:INTEREST_DB_PASSWORD=\"비밀번호\" 설정 후 실행해줘."
        )

    return psycopg2.connect(**DB_CONFIG)


def wait_document_ready(driver, timeout=30):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def activate_browser_window(driver):
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    try:
        driver.maximize_window()
    except Exception:
        pass

    try:
        driver.execute_script("window.focus();")
    except Exception:
        pass

    try:
        subprocess.Popen(
            ["python", "-c", "import interest_krx_chrome; interest_krx_chrome.force_foreground_chrome()"],
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    time.sleep(1)


def ensure_page_ready(driver, url):
    activate_browser_window(driver)

    driver.get(url)
    wait_document_ready(driver, timeout=30)

    activate_browser_window(driver)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "jsSearchButton"))
    )


def safe_click(driver, by, selector, timeout=20):
    elem = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    time.sleep(0.2)
    driver.execute_script("arguments[0].click();", elem)
    time.sleep(0.2)

    return elem


def set_input_value(driver, elem, value):
    driver.execute_script(
        """
        arguments[0].removeAttribute('readonly');
        arguments[0].focus();
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
        """,
        elem,
        value
    )


def get_latest_business_day():
    d = datetime.now().date() - timedelta(days=1)

    while is_holiday(d, "KR"):
        d -= timedelta(days=1)

    return d


def get_last_collected_date():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(trade_date)
        FROM interest_program_raw
    """)

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row[0] is None:
        return START_DATE

    next_day = row[0] + timedelta(days=1)
    return next_day.strftime("%Y%m%d")


def generate_dates(conn):
    cur = conn.cursor()

    cur.execute("SELECT MAX(trade_date) FROM interest_program_raw")
    row = cur.fetchone()

    cur.close()

    if row[0] is None:
        start = datetime.strptime(START_DATE, "%Y%m%d").date()
    else:
        start = row[0] + timedelta(days=1)

    end = get_latest_business_day()

    dates = []

    while start <= end:
        if not is_holiday(start, "KR"):
            dates.append(start.strftime("%Y%m%d"))

        start += timedelta(days=1)

    return dates


def insert_db(df):
    conn = get_conn()
    cur = conn.cursor()

    sql = """
    INSERT INTO interest_program_raw
    (
        trade_date,

        arbitrage_sell_volume,
        arbitrage_buy_volume,
        arbitrage_net_volume,
        arbitrage_sell_amount,
        arbitrage_buy_amount,
        arbitrage_net_amount,

        nonarb_sell_volume,
        nonarb_buy_volume,
        nonarb_net_volume,
        nonarb_sell_amount,
        nonarb_buy_amount,
        nonarb_net_amount,

        total_sell_volume,
        total_buy_volume,
        total_net_volume,
        total_sell_amount,
        total_buy_amount,
        total_net_amount,

        source,
        source_version,
        collected_at
    )
    VALUES
    (%s,%s,%s,%s,%s,%s,%s,
     %s,%s,%s,%s,%s,%s,
     %s,%s,%s,%s,%s,%s,
     %s,%s,now())
    ON CONFLICT (trade_date)
    DO UPDATE SET updated_at = now()
    """

    rows = [tuple(r) for _, r in df.iterrows()]

    execute_batch(cur, sql, rows)

    conn.commit()
    cur.close()
    conn.close()

    return len(rows)


def parse_csv(file_path, date):
    df = pd.read_csv(file_path, encoding="cp949")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "구분": "type",
        "거래량_매도": "sell_volume",
        "거래량_매수": "buy_volume",
        "거래량_순매수": "net_volume",
        "거래대금_매도": "sell_amount",
        "거래대금_매수": "buy_amount",
        "거래대금_순매수": "net_amount"
    })

    row = {
        "trade_date": pd.to_datetime(date).date(),

        "arbitrage_sell_volume": None,
        "arbitrage_buy_volume": None,
        "arbitrage_net_volume": None,
        "arbitrage_sell_amount": None,
        "arbitrage_buy_amount": None,
        "arbitrage_net_amount": None,

        "nonarb_sell_volume": None,
        "nonarb_buy_volume": None,
        "nonarb_net_volume": None,
        "nonarb_sell_amount": None,
        "nonarb_buy_amount": None,
        "nonarb_net_amount": None,

        "total_sell_volume": None,
        "total_buy_volume": None,
        "total_net_volume": None,
        "total_sell_amount": None,
        "total_buy_amount": None,
        "total_net_amount": None,

        "source": SOURCE,
        "source_version": VERSION
    }

    for _, r in df.iterrows():
        if r["type"] == "차익":
            row["arbitrage_sell_volume"] = r["sell_volume"]
            row["arbitrage_buy_volume"] = r["buy_volume"]
            row["arbitrage_net_volume"] = r["net_volume"]
            row["arbitrage_sell_amount"] = r["sell_amount"]
            row["arbitrage_buy_amount"] = r["buy_amount"]
            row["arbitrage_net_amount"] = r["net_amount"]

        elif r["type"] == "비차익":
            row["nonarb_sell_volume"] = r["sell_volume"]
            row["nonarb_buy_volume"] = r["buy_volume"]
            row["nonarb_net_volume"] = r["net_volume"]
            row["nonarb_sell_amount"] = r["sell_amount"]
            row["nonarb_buy_amount"] = r["buy_amount"]
            row["nonarb_net_amount"] = r["net_amount"]

        elif r["type"] == "전체":
            row["total_sell_volume"] = r["sell_volume"]
            row["total_buy_volume"] = r["buy_volume"]
            row["total_net_volume"] = r["net_volume"]
            row["total_sell_amount"] = r["sell_amount"]
            row["total_buy_amount"] = r["buy_amount"]
            row["total_net_amount"] = r["net_amount"]

    return pd.DataFrame([row])


def clear_old_csv():
    files = glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv"))

    for f in files:
        try:
            os.remove(f)
        except Exception:
            pass


def wait_downloaded_csv(timeout=20):
    start = time.time()

    while time.time() - start < timeout:
        files = glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv"))

        if files:
            file_path = max(files, key=os.path.getctime)

            size1 = os.path.getsize(file_path)
            time.sleep(1)
            size2 = os.path.getsize(file_path)

            if size1 == size2:
                return file_path

        time.sleep(1)

    return None


def download_csv(driver):
    wait = WebDriverWait(driver, 25)

    safe_click(driver, By.XPATH, "//button[@class='CI-MDI-UNIT-DOWNLOAD']", timeout=25)

    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='닫기']"))
        ).click()
        return None
    except Exception:
        pass

    wait.until(
        EC.element_to_be_clickable((By.XPATH, "//div[@data-type='csv']//a"))
    )

    safe_click(driver, By.XPATH, "//div[@data-type='csv']//a", timeout=10)

    return wait_downloaded_csv(timeout=20)


def collect_one_date(driver, wait, date):
    clear_old_csv()

    start_box = wait.until(
        EC.presence_of_element_located((By.ID, "strtDd"))
    )
    end_box = driver.find_element(By.ID, "endDd")

    set_input_value(driver, start_box, date)
    set_input_value(driver, end_box, date)

    safe_click(driver, By.ID, "jsSearchButton", timeout=25)

    time.sleep(SEARCH_WAIT)

    csv_file = download_csv(driver)

    if csv_file is None:
        return None, f"{date} Program Not Collected"

    df = parse_csv(csv_file, date)

    try:
        os.remove(csv_file)
    except Exception:
        pass

    if df is None or df.empty:
        return None, f"{date} Empty Data"

    return df, None


def run():
    collected_dates = []
    error_lines = []
    driver = None

    try:
        conn = get_conn()
        dates = generate_dates(conn)
        conn.close()

        if not dates:
            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": [],
                "failed_lines": [],
                "error_count": 0
            }
            print_step_log("interest_program", result)
            return result

        driver = start_driver()
        ensure_page_ready(driver, PROGRAM_URL)

        wait = WebDriverWait(driver, 25)

        for date in dates:
            try:
                activate_browser_window(driver)

                df, error = collect_one_date(driver, wait, date)

                if error:
                    error_lines.append(error)
                    continue

                insert_db(df)
                collected_dates.append(date)

            except Exception as e:
                error_lines.append(f"{date} / {str(e)}")

                try:
                    ensure_page_ready(driver, PROGRAM_URL)
                except Exception:
                    pass

        try:
            driver.quit()
        except Exception:
            pass

        if not collected_dates:
            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": error_lines,
                "failed_lines": [],
                "error_count": len(error_lines)
            }
            print_step_log("interest_program", result)
            return result

        success_lines = [
            f"{datetime.strptime(d, '%Y%m%d').strftime('%Y-%m-%d')} Collected"
            for d in collected_dates
        ]

        result = {
            "status": "SUCCESS",
            "collected_dates": [
                datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")
                for d in collected_dates
            ],
            "success_lines": success_lines,
            "error_lines": error_lines,
            "failed_lines": [],
            "error_count": len(error_lines)
        }

        print_step_log("interest_program", result)
        return result

    except Exception as e:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [str(e)],
            "error_count": 1
        }

        print_step_log("interest_program", result)
        return result


if __name__ == "__main__":
    run()
