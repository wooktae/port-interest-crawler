import yfinance as yf
import psycopg2
import psycopg2.extras
import json
import pandas as pd
import contextlib
import sys
import os
import time
from datetime import datetime, timedelta

from interest_get_holidays import is_holiday


DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "2.0.0"


# --------------------------
# suppress stderr
# --------------------------
@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, "w") as fnull:
        old_stderr = sys.stderr
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_universe():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code, market
        FROM stock_universe
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


def convert_ticker(code, market):
    if market == "KOSPI":
        return f"{code}.KS"
    if market == "KOSDAQ":
        return f"{code}.KQ"
    return code


# --------------------------
# fetch (🔥 핵심)
# --------------------------
def fetch_rows(code, market, target_date):

    ticker = convert_ticker(code, market)

    # 🔥 range 조회 (중요)
    start = target_date - timedelta(days=5)
    end = target_date + timedelta(days=1)

    try:
        with suppress_stderr():
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False,
                threads=False
            )

        if df is None or df.empty:
            return None

        # 🔥 멀티컬럼 처리 (핵심)
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        # 🔥 target_date만 필터
        df = df[df["Date"].dt.date == target_date]

        if df.empty:
            return None

        r = df.iloc[0]

        close = r.get("Close")
        if pd.isna(close):
            return None

        now = datetime.now()

        return {
            "ticker_code": code,
            "price_date": target_date,
            "open_price": float(r["Open"]),
            "high_price": float(r["High"]),
            "low_price": float(r["Low"]),
            "close_price": float(close),
            "adj_close_price": float(close),
            "volume": int(r["Volume"]) if not pd.isna(r["Volume"]) else None,
            "raw_json": json.dumps({"ticker": ticker}),
            "collected_at": now,
            "as_of_ts": now,
            "source": SOURCE_NAME,
            "source_version": SOURCE_VERSION
        }

    except:
        return None


# --------------------------
# save
# --------------------------
def save(conn, row):

    if not row:
        return 0

    sql = """
    INSERT INTO interest_price_raw (
        ticker_code, price_date,
        open_price, high_price, low_price,
        close_price, adj_close_price, volume,
        raw_json, collected_at, as_of_ts,
        source, source_version
    )
    VALUES (
        %(ticker_code)s, %(price_date)s,
        %(open_price)s, %(high_price)s, %(low_price)s,
        %(close_price)s, %(adj_close_price)s, %(volume)s,
        %(raw_json)s, %(collected_at)s, %(as_of_ts)s,
        %(source)s, %(source_version)s
    )
    ON CONFLICT (ticker_code, price_date)
    DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        adj_close_price = EXCLUDED.adj_close_price,
        volume = EXCLUDED.volume,
        updated_at = now();
    """

    cur = conn.cursor()
    cur.execute(sql, row)
    cur.close()

    return 1


# --------------------------
# MAIN
# --------------------------
def run():

    TARGET_DATE = "2022-05-02"   # 🔥 여기만 바꾸면 됨
    target_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()

    # 휴일 skip
    if is_holiday(target_date, "KR"):
        print(f"{TARGET_DATE} is holiday → skip")
        return

    conn = get_conn()
    universe = get_universe()

    # 기존 ticker skip
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker_code
        FROM interest_price_raw
        WHERE price_date = %s
    """, (target_date,))
    existing_codes = {r[0] for r in cur.fetchall()}
    cur.close()

    total = 0
    skip_count = 0
    fail_count = 0
    failed_sample = None   # 🔥 추가

    print(f"processing {target_date}")

    for code, market in universe:

        if code in existing_codes:
            skip_count += 1
            continue

        row = fetch_rows(code, market, target_date)

        if not row:
            fail_count += 1

            # 🔥 실패 샘플 1개만 저장
            if failed_sample is None:
                failed_sample = code

            continue

        total += save(conn, row)

        time.sleep(0.01)

    conn.commit()
    conn.close()

    print(f"{TARGET_DATE} TOTAL SAVED: {total}")
    print(f"{TARGET_DATE} SKIPPED: {skip_count}")
    print(f"{TARGET_DATE} FAILED: {fail_count}")

    # 🔥 샘플 출력
    if failed_sample:
        print(f"{TARGET_DATE} FAILED SAMPLE: {failed_sample}")


if __name__ == "__main__":
    run()