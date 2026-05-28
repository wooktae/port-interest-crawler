"""yfinance 기반 국내 관심종목 가격 데이터를 일일 증분 수집하는 스크립트다.

DB universe를 읽고 시장별 yfinance ticker로 변환한 뒤 최신 영업일 가격을 저장한다.
yfinance 외부 요청과 DB upsert가 포함되므로 운영 수집 단계에서만 실행한다.
"""

import yfinance as yf
import psycopg2
from db_config import get_db_config
import psycopg2.extras
import json
import pandas as pd
import contextlib
import sys
import os
from datetime import datetime, timedelta

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "2.0.0"
DEFAULT_START_DATE = "2007-01-01"


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


def get_latest_date(conn, code):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(price_date)
        FROM interest_price_raw
        WHERE ticker_code = %s
    """, (code,))

    row = cur.fetchone()
    cur.close()

    return row[0]


def build_range(latest):

    if latest:
        start = latest + timedelta(days=1)
    else:
        start = datetime.strptime(DEFAULT_START_DATE, "%Y-%m-%d").date()

    end = datetime.now().date()

    return start, end


def fetch_rows(code, market, start, end):

    ticker = convert_ticker(code, market)

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
            return []

        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        rows = []

        for _, r in df.iterrows():

            price_date = pd.to_datetime(r["Date"]).date()

            close = r.get("Close")
            if pd.isna(close):
                continue

            now = datetime.now()

            rows.append({
                "ticker_code": code,
                "price_date": price_date,
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
            })

        return rows

    except:
        return []


def save_rows(conn, rows):

    if not rows:
        return 0

    sql = """
        INSERT INTO interest_price_raw (
            ticker_code,
            price_date,
            open_price,
            high_price,
            low_price,
            close_price,
            adj_close_price,
            volume,
            raw_json,
            collected_at,
            as_of_ts,
            source,
            source_version
        )
        VALUES (
            %(ticker_code)s,
            %(price_date)s,
            %(open_price)s,
            %(high_price)s,
            %(low_price)s,
            %(close_price)s,
            %(adj_close_price)s,
            %(volume)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_ts)s,
            %(source)s,
            %(source_version)s
        )
        ON CONFLICT (ticker_code, price_date)
        DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            adj_close_price = EXCLUDED.adj_close_price,
            volume = EXCLUDED.volume,
            raw_json = EXCLUDED.raw_json,
            collected_at = EXCLUDED.collected_at,
            as_of_ts = EXCLUDED.as_of_ts,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
            updated_at = now();
    """

    cur = conn.cursor()
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    cur.close()

    return len(rows)

def exists_price(conn, ticker_code, date):

    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM interest_price_raw
        WHERE ticker_code = %s
          AND price_date = %s
        LIMIT 1
    """, (ticker_code, date))

    exists = cur.fetchone() is not None
    cur.close()

    return exists

from interest_get_holidays import is_holiday
from datetime import datetime, timedelta

def get_latest_business_day():

    d = datetime.now().date() - timedelta(days=1)

    while is_holiday(d, "KR"):
        d -= timedelta(days=1)

    return d

def count_rows_by_date(conn, target_date):

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM interest_price_raw
        WHERE price_date = %s
    """, (target_date,))

    cnt = cur.fetchone()[0]
    cur.close()

    return cnt

def get_existing_tickers_by_date(conn, target_date):

    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code
        FROM interest_price_raw
        WHERE price_date = %s
    """, (target_date,))

    rows = {r[0] for r in cur.fetchall()}
    cur.close()

    return rows

def run():

    conn = get_conn()
    universe = get_universe()

    total_saved = 0
    collected_dates = set()
    success_map = {}

    try:

        # 1️⃣ 최신 영업일
        latest_business_day = get_latest_business_day()

        for code, market in universe:

            latest = get_latest_date(conn, code)

            # 최신이면 PASS
            if latest == latest_business_day:
                continue

            # 🔥 range 복구
            if latest:
                start = latest + timedelta(days=1)
            else:
                start = latest_business_day

            end = latest_business_day + timedelta(days=1)

            if start >= end:
                continue

            rows = fetch_rows(code, market, start, end)

            if not rows:
                continue

            rows = [
                r for r in rows
                if not is_holiday(r["price_date"], "KR")
            ]

            if not rows:
                continue

            saved = save_rows(conn, rows)
            conn.commit()

            total_saved += saved

            for r in rows:
                d = str(r["price_date"])
                collected_dates.add(d)
                success_map[d] = success_map.get(d, 0) + 1

        conn.close()

        # -------------------
        # 결과 처리
        # -------------------

        if not collected_dates:
            status = "NO_CHANGE"
            success_lines = []
        else:
            status = "SUCCESS"
            success_lines = [
                f"{d} {success_map[d]} Price Collected"
                for d in sorted(collected_dates)
            ]

        result = {
            "status": status,
            "collected_dates": sorted(collected_dates),
            "success_lines": success_lines,
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log("interest_price", result)
        return result

    except Exception as e:

        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [str(e)],
            "error_count": 0
        }

        print_step_log("interest_price", result)
        return result


if __name__ == "__main__":
    run()
