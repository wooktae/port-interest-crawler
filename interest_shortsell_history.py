import os
import glob
import time
import pandas as pd
import psycopg2
from db_config import get_db_config
from psycopg2.extras import execute_batch

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DOWNLOAD_DIR = r"C:\Users\USER\Downloads"

START_DATE = "20240313"
END_DATE = "20260313"

UNIVERSE_LIMIT = 350

SEARCH_WAIT = 8
CSV_WAIT = 7

SOURCE = "krx"
VERSION = "2.0.0"

DB_CONFIG = get_db_config()


# ---------------------------
# DRIVER
# ---------------------------

def start_driver():

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    driver = webdriver.Chrome(options=options)

    return driver


# ---------------------------
# DB
# ---------------------------

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------
# UNIVERSE
# ---------------------------

def get_universe(conn):

    cur = conn.cursor()

    cur.execute(f"""
        SELECT ticker_code, company_name
        FROM stock_universe
        ORDER BY ticker_code
        LIMIT {UNIVERSE_LIMIT}
    """)

    rows = cur.fetchall()

    cur.close()

    return [(r[0].zfill(6), r[1]) for r in rows]


# ---------------------------
# 이미 받은 종목
# ---------------------------

def get_collected_tickers(conn):

    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT ticker_code
        FROM interest_shortsell_raw
    """)

    rows = cur.fetchall()

    cur.close()

    return {r[0].zfill(6) for r in rows}


# ---------------------------
# CSV snapshot
# ---------------------------

def snapshot_csv():

    return set(glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv")))


def wait_new_csv(before):

    for _ in range(30):

        now = set(glob.glob(os.path.join(DOWNLOAD_DIR, "data_*.csv")))

        diff = now - before

        if diff:

            latest = max(diff, key=os.path.getctime)

            return latest

        time.sleep(1)

    raise Exception("CSV not found")


# ---------------------------
# CSV parse
# ---------------------------

def parse_csv(file_path, ticker, name):

    df = pd.read_csv(file_path, encoding="cp949")

    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "일자": "trade_date",
        "공매도 수량_거래량_전체": "short_volume",
        "공매도 금액_거래대금_전체": "short_amount"
    })

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    df["short_volume"] = (
        df["short_volume"].astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df["short_amount"] = (
        df["short_amount"].astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df["ticker_code"] = ticker
    df["ticker_name"] = name

    df["total_volume"] = None
    df["short_ratio"] = None

    return df


# ---------------------------
# DB insert
# ---------------------------

def insert_db(df):

    conn = get_conn()
    cur = conn.cursor()

    sql = """
    INSERT INTO interest_shortsell_raw
    (
        trade_date,
        ticker_code,
        ticker_name,
        short_volume,
        short_amount,
        total_volume,
        short_ratio,
        source,
        source_version,
        collected_at
    )
    VALUES
    (%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
    ON CONFLICT (trade_date, ticker_code)
    DO UPDATE SET
        short_volume = EXCLUDED.short_volume,
        short_amount = EXCLUDED.short_amount,
        updated_at = now()
    """

    rows = []

    for _, r in df.iterrows():

        rows.append((
            r["trade_date"],
            r["ticker_code"],
            r["ticker_name"],
            r["short_volume"],
            r["short_amount"],
            r["total_volume"],
            r["short_ratio"],
            SOURCE,
            VERSION
        ))

    execute_batch(cur, sql, rows)

    conn.commit()
    conn.close()

    return len(rows)


# ---------------------------
# CSV 클릭 (팝업)
# ---------------------------

def click_csv_popup(driver, wait):

    csv_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//a[.//span[contains(@class,'ico_filedown')] and contains(.,'CSV')]"
        ))
    )

    driver.execute_script("arguments[0].click();", csv_btn)


# ---------------------------
# MAIN
# ---------------------------

def run():

    print("===== SHORTSELL COLLECTOR START =====")

    driver = start_driver()

    wait = WebDriverWait(driver, 20)

    conn = get_conn()

    universe = get_universe(conn)
    collected = get_collected_tickers(conn)

    conn.close()

    print("universe:", len(universe))
    print("already collected:", len(collected))

    targets = [(c, n) for c, n in universe if c not in collected]

    print("to collect:", len(targets))


    for i, (code, name) in enumerate(targets, start=1):

        print(f"[{i}/{len(targets)}] {code} {name}")

        try:

            box = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[title='공매도 종목 검색']")
                )
            )

            driver.execute_script("""
                arguments[0].value='';
                arguments[0].value=arguments[1];
                arguments[0].dispatchEvent(new Event('keyup'));
            """, box, name)

            driver.execute_script(
                "document.querySelector('#strdDd').value=arguments[0];",
                START_DATE
            )

            driver.execute_script(
                "document.querySelector('#endDd').value=arguments[0];",
                END_DATE
            )

            before = snapshot_csv()

            # 검색
            search_btn = wait.until(
                EC.element_to_be_clickable((By.ID, "jsSearchButton"))
            )

            search_btn.click()

            print("search wait 7 sec")
            time.sleep(SEARCH_WAIT)

            # 다운로드 버튼
            download_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "img[title*='다운로드']")
                )
            )

            download_btn.click()

            # CSV 클릭
            click_csv_popup(driver, wait)

            print("csv wait 7 sec")
            time.sleep(CSV_WAIT)

            file_path = wait_new_csv(before)

            print("csv:", file_path)

            df = parse_csv(file_path, code, name)

            saved = insert_db(df)

            print("saved rows:", saved)

            os.remove(file_path)

        except Exception as e:

            print(f"ERROR [{code} {name}] -> {e}")

            continue


    print("===== DONE =====")


if __name__ == "__main__":
    run()