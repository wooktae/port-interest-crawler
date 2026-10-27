"""Selenium script that backfills program trading data from the KRX website over a past date range.

It downloads and parses per-date CSVs and then stores them in PostgreSQL.
Because it can trigger heavy downloads and DB writes, confirm the date range and local download path before running.
"""

import os
import glob
import time
import pandas as pd
import psycopg2
from db_config import get_db_config
from psycopg2.extras import execute_batch
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


DOWNLOAD_DIR = r"C:\Users\USER\Downloads"

START_DATE = "20240313"
END_DATE = "20260313"

SEARCH_WAIT = 1.5

SOURCE = "krx"
VERSION = "1.0.0"

DB_CONFIG = get_db_config()


# ---------------------------
# Chrome attach
# ---------------------------

def start_driver():

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    driver = webdriver.Chrome(options=options)

    print("attached tab:", driver.title)

    return driver


# ---------------------------
# DB
# ---------------------------

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


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

    rows = []

    for _, r in df.iterrows():

        rows.append(tuple(r))

    execute_batch(cur, sql, rows)

    conn.commit()
    conn.close()

    return len(rows)


# ---------------------------
# CSV parse
# ---------------------------

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


# ---------------------------
# CSV download
# ---------------------------

def download_csv(driver):

    wait = WebDriverWait(driver,20)

    download_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,"//button[@class='CI-MDI-UNIT-DOWNLOAD']")
        )
    )

    download_btn.click()

    # Handle the "no data" popup
    try:

        close_btn = WebDriverWait(driver,3).until(
            EC.element_to_be_clickable(
                (By.XPATH,"//button[text()='닫기']")
            )
        )

        print("no data popup -> close")

        close_btn.click()

        return None

    except:
        pass


    csv_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,"//div[@data-type='csv']//a")
        )
    )

    csv_btn.click()

    print("waiting csv file...")

    for _ in range(10):

        files = glob.glob(os.path.join(DOWNLOAD_DIR,"data_*.csv"))

        if files:

            return max(files,key=os.path.getctime)

        time.sleep(1)

    return None


# ---------------------------
# Generate dates
# ---------------------------

def generate_dates():

    start = datetime.strptime(START_DATE,"%Y%m%d")
    end = datetime.strptime(END_DATE,"%Y%m%d")

    dates = []

    while start <= end:

        dates.append(start.strftime("%Y%m%d"))

        start += timedelta(days=1)

    return dates


# ---------------------------
# MAIN
# ---------------------------

def run():

    print("===== PROGRAM TRADING COLLECTOR START =====")

    driver = start_driver()

    wait = WebDriverWait(driver,20)

    dates = generate_dates()

    for date in dates:

        print(f"[{date}] start")

        try:

            start_box = wait.until(
                EC.presence_of_element_located((By.ID,"strtDd"))
            )

            end_box = driver.find_element(By.ID,"endDd")

            driver.execute_script(
                "arguments[0].value=arguments[1]",
                start_box,
                date
            )

            driver.execute_script(
                "arguments[0].value=arguments[1]",
                end_box,
                date
            )

            search_btn = wait.until(
                EC.element_to_be_clickable((By.ID,"jsSearchButton"))
            )

            search_btn.click()

            print("search wait 1.5 sec")

            time.sleep(SEARCH_WAIT)

            csv_file = download_csv(driver)

            if csv_file is None:

                print(f"[{date}] no data")

                continue

            print("csv:",csv_file)

            df = parse_csv(csv_file,date)

            saved = insert_db(df)

            print(f"[{date}] saved rows:",saved)

            os.remove(csv_file)

        except Exception as e:

            print(f"[{date}] error:",e)

            continue

    print("===== DONE =====")


if __name__ == "__main__":
    run()
