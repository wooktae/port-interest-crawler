"""Selenium script that incrementally collects short-selling data from the KRX website on a daily basis.

It downloads per-market CSVs, filters them to the universe tickers, and stores them in PostgreSQL.
Because it involves browser control, file downloads, and DB upserts, run it only in the production environment.
"""

import os
import sys
import glob
import time
import subprocess
from datetime import datetime, timedelta
from decimal import Decimal

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

UNIVERSE_LIMIT = 350

SEARCH_WAIT = 3
CSV_WAIT = 3

SOURCE = "krx"
VERSION = "2.0.0"

SHORTSELL_URL = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC02030201"

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


def get_universe_code_set(conn):
    cur = conn.cursor()

    cur.execute(f"""
        SELECT ticker_code
        FROM stock_universe
        LIMIT {UNIVERSE_LIMIT}
    """)

    rows = cur.fetchall()

    cur.close()

    return {str(r[0]).zfill(6) for r in rows}


def get_last_collected_date(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(trade_date)
        FROM interest_shortsell_raw
    """)

    row = cur.fetchone()

    cur.close()

    if row[0] is None:
        raise Exception("interest_shortsell_raw is empty")

    return (row[0] + timedelta(days=1)).strftime("%Y%m%d")


def insert_db(df):
    if df is None or df.empty:
        return 0

    conn = get_conn()
    cur = conn.cursor()

    sql = """
    INSERT INTO interest_shortsell_raw
    (trade_date, ticker_code, ticker_name,
     short_volume, short_amount, total_volume,
     short_ratio, source, source_version, collected_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
    ON CONFLICT (trade_date, ticker_code)
    DO UPDATE SET updated_at = now()
    """

    rows = []

    for _, r in df.iterrows():
        rows.append((
            r["trade_date"],
            r["ticker_code"],
            r.get("ticker_name"),
            r.get("short_volume"),
            r.get("short_amount"),
            r.get("total_volume"),
            r.get("short_ratio"),
            r.get("source"),
            r.get("source_version")
        ))

    execute_batch(cur, sql, rows)

    conn.commit()
    cur.close()
    conn.close()

    return len(rows)


def get_latest_business_day():
    d = datetime.now().date() - timedelta(days=1)

    while is_holiday(d, "KR"):
        d -= timedelta(days=1)

    return d


def generate_dates(conn):
    cur = conn.cursor()

    cur.execute("SELECT MAX(trade_date) FROM interest_shortsell_raw")
    row = cur.fetchone()

    cur.close()

    if row[0] is None:
        raise Exception("shortsell empty")

    start = row[0] + timedelta(days=1)
    end = get_latest_business_day()

    dates = []

    while start <= end:
        if not is_holiday(start, "KR"):
            dates.append(start.strftime("%Y%m%d"))

        start += timedelta(days=1)

    return dates


def snapshot_csv():
    return set(glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv")))


def wait_new_csv(before, timeout=20):
    start = time.time()

    while time.time() - start < timeout:
        now = set(glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv")))
        diff = now - before

        if diff:
            file_path = max(diff, key=os.path.getctime)

            size1 = os.path.getsize(file_path)
            time.sleep(1)
            size2 = os.path.getsize(file_path)

            if size1 == size2:
                return file_path

        time.sleep(1)

    return None


def clean_int(x):
    try:
        return int(str(x).replace(",", ""))
    except Exception:
        return None


def clean_decimal(x):
    try:
        return Decimal(str(x).replace(",", "").replace("%", ""))
    except Exception:
        return None


def parse_csv(file_path, trade_date, allowed_codes):
    try:
        df = pd.read_csv(file_path, encoding="cp949", dtype={"종목코드": str})
    except Exception:
        return None

    if df is None or df.empty:
        return None

    df = df.rename(columns={
        "종목코드": "ticker_code",
        "종목명": "ticker_name",
        "수량_공매도거래량_전체": "short_volume",
        "금액_공매도거래대금_전체": "short_amount",
        "수량_거래량": "total_volume",
        "수량_비중": "short_ratio"
    })

    if "ticker_code" not in df.columns:
        return None

    df["ticker_code"] = df["ticker_code"].astype(str).str.zfill(6)
    df = df[df["ticker_code"].isin(allowed_codes)]

    if df.empty:
        return None

    df["trade_date"] = datetime.strptime(trade_date, "%Y%m%d").date()

    df["short_volume"] = df["short_volume"].apply(clean_int)
    df["short_amount"] = df["short_amount"].apply(clean_decimal)
    df["total_volume"] = df["total_volume"].apply(clean_int)
    df["short_ratio"] = df["short_ratio"].apply(clean_decimal)

    df["source"] = SOURCE
    df["source_version"] = VERSION

    return df


def set_market(driver, market):
    if market == "KOSPI":
        input_id = "mktId_0_0"
    elif market == "KOSDAQ":
        input_id = "mktId_0_1"
    else:
        raise Exception("Invalid market")

    el = WebDriverWait(driver, 25).until(
        EC.element_to_be_clickable((By.ID, input_id))
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    driver.execute_script("arguments[0].click();", el)
    time.sleep(0.5)

    if not driver.find_element(By.ID, input_id).is_selected():
        raise Exception(f"{market} not selected")


def download_csv(driver, before):
    safe_click(
        driver,
        By.XPATH,
        "//button[@class='CI-MDI-UNIT-DOWNLOAD']",
        timeout=25
    )

    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='닫기']"))
        ).click()
        return None
    except Exception:
        pass

    safe_click(
        driver,
        By.XPATH,
        "//div[@data-type='csv']//a",
        timeout=15
    )

    time.sleep(CSV_WAIT)

    return wait_new_csv(before, timeout=20)


def set_trade_date(driver, date):
    box = WebDriverWait(driver, 25).until(
        EC.presence_of_element_located((By.ID, "trdDd"))
    )

    set_input_value(driver, box, date)


def search(driver):
    safe_click(driver, By.ID, "jsSearchButton", timeout=25)
    time.sleep(SEARCH_WAIT)


def collect_one_market(driver, date, market, allowed_codes):
    before = snapshot_csv()

    set_market(driver, market)
    set_trade_date(driver, date)
    search(driver)

    file = download_csv(driver, before)

    if not file:
        return None, f"{date} {market} CSV 실패"

    df = parse_csv(file, date, allowed_codes)

    try:
        os.remove(file)
    except Exception:
        pass

    if df is None or df.empty:
        return None, f"{date} {market} EMPTY"

    return df, None


def run():
    collected_dates = set()
    success_codes = set()
    fail_details = []
    date_count_map = {}
    driver = None

    try:
        conn = get_conn()
        allowed_codes = get_universe_code_set(conn)
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
            print_step_log("interest_shortsell", result)
            return result

        driver = start_driver()

        for date in dates:
            try:
                ensure_page_ready(driver, SHORTSELL_URL)

                date_total_count = 0

                for market in ["KOSPI", "KOSDAQ"]:
                    try:
                        activate_browser_window(driver)

                        df, error = collect_one_market(
                            driver,
                            date,
                            market,
                            allowed_codes
                        )

                        if error:
                            fail_details.append(error)
                            continue

                        count = insert_db(df)

                        date_total_count += count
                        success_codes.update(df["ticker_code"].tolist())

                    except Exception as e:
                        fail_details.append(f"{date} {market} / {str(e)}")

                        try:
                            ensure_page_ready(driver, SHORTSELL_URL)
                        except Exception:
                            pass

                if date_total_count > 0:
                    collected_dates.add(date)
                    date_count_map[date] = date_total_count

            except Exception as e:
                fail_details.append(f"{date} / {str(e)}")

        try:
            driver.quit()
        except Exception:
            pass

        if not collected_dates:
            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": fail_details,
                "failed_lines": [],
                "error_count": len(fail_details)
            }
            print_step_log("interest_shortsell", result)
            return result

        success_lines = [
            f"{datetime.strptime(d, '%Y%m%d').strftime('%Y-%m-%d')} {date_count_map[d]} Company Collected"
            for d in sorted(collected_dates)
        ]

        result = {
            "status": "SUCCESS",
            "collected_dates": [
                datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")
                for d in sorted(collected_dates)
            ],
            "success_lines": success_lines,
            "error_lines": fail_details,
            "failed_lines": [],
            "error_count": len(fail_details)
        }

        print_step_log("interest_shortsell", result)
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

        print_step_log("interest_shortsell", result)
        return result


def exit_code_from_result(result):
    if not isinstance(result, dict):
        return 1

    status = str(result.get("status") or "").upper()
    error_count = int(result.get("error_count") or 0)

    if status in {"SUCCESS", "NO_CHANGE"} and error_count == 0:
        return 0

    return 1


if __name__ == "__main__":
    result = run()
    exit_code = exit_code_from_result(result)

    print(
        "PROCESS_EXIT_DECISION "
        f"status={str(result.get('status') or '').upper()} "
        f"error_count={int(result.get('error_count') or 0)} "
        f"exit_code={exit_code}"
    )

    sys.exit(exit_code)
