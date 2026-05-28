"""yfinance 기반 매크로 지표 데이터를 일일 증분 수집하는 스크립트다.

국가/지표별 최신 적재 기간 이후 데이터를 조회하고 PostgreSQL에 저장한다.
yfinance 외부 요청과 DB upsert가 포함되므로 운영 수집 단계에서만 실행한다.
"""

import yfinance as yf
import psycopg2
from db_config import get_db_config
import psycopg2.extras
import json
import contextlib
import sys
import os
from datetime import datetime, timedelta

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

MACRO_TICKERS = {
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "US2Y": "^IRX",
    "DXY": "DX-Y.NYB",
    "USDKRW": "KRW=X",
    "USDJPY": "JPY=X",
    "USDCNY": "CNY=X"
}

COUNTRY_NAME = "Global"
SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.1.0"
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


def get_db_latest_period(conn, country, indicator_name):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(period)
        FROM interest_macroeconomic_raw
        WHERE country = %s
          AND indicator_name = %s
    """, (country, indicator_name))

    row = cur.fetchone()
    cur.close()

    return row[0]


def exists_in_db(conn, indicator_name, date):

    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM interest_macroeconomic_raw
        WHERE country = %s
          AND indicator_name = %s
          AND period = %s
        LIMIT 1
    """, (COUNTRY_NAME, indicator_name, date))

    exists = cur.fetchone() is not None
    cur.close()

    return exists


def build_fetch_range(latest_db_period):

    if latest_db_period:
        start_date = latest_db_period + timedelta(days=1)
    else:
        start_date = datetime.strptime(DEFAULT_START_DATE, "%Y-%m-%d").date()

    end_date = datetime.now().date()

    return start_date, end_date


def safe_float(x):
    try:
        return float(x) if x is not None else None
    except:
        return None


def fetch_rows(indicator_name, ticker, start_date, end_date):

    try:
        with suppress_stderr():
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
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

            period = r["Date"].date()
            close_price = safe_float(r.get("Close"))

            if close_price is None:
                continue

            now_ts = datetime.now()

            rows.append({
                "country": COUNTRY_NAME,
                "indicator_name": indicator_name,
                "period": period,
                "released_value": round(close_price, 6),
                "expected_value": None,
                "previous_value": None,
                "impact_level": None,
                "raw_json": json.dumps({
                    "ticker": ticker,
                    "close": close_price
                }, ensure_ascii=False),
                "released_at": now_ts,
                "collected_at": now_ts,
                "source": SOURCE_NAME,
                "source_version": SOURCE_VERSION
            })

        return rows

    except:
        return []


def save_rows(conn, records):

    if not records:
        return 0

    sql = """
        INSERT INTO interest_macroeconomic_raw (
            country, indicator_name, period,
            released_value, expected_value, previous_value, impact_level,
            raw_json, released_at, collected_at,
            source, source_version
        )
        VALUES (
            %(country)s, %(indicator_name)s, %(period)s,
            %(released_value)s, %(expected_value)s, %(previous_value)s, %(impact_level)s,
            %(raw_json)s, %(released_at)s, %(collected_at)s,
            %(source)s, %(source_version)s
        )
        ON CONFLICT (country, indicator_name, period)
        DO UPDATE SET
            released_value = EXCLUDED.released_value,
            raw_json = EXCLUDED.raw_json,
            collected_at = EXCLUDED.collected_at,
            updated_at = now();
    """

    cur = conn.cursor()
    psycopg2.extras.execute_batch(cur, sql, records, page_size=200)
    cur.close()

    return len(records)

def run():

    conn = get_conn()

    total_saved = 0

    collected_dates_set = set()
    success_map = {}
    success_detail_map = {}

    try:

        from interest_get_holidays import is_holiday  # 🔥 추가

        for indicator_name, ticker in MACRO_TICKERS.items():

            latest = get_db_latest_period(conn, COUNTRY_NAME, indicator_name)
            start_date, end_date = build_fetch_range(latest)

            if start_date >= end_date:
                continue

            rows = fetch_rows(indicator_name, ticker, start_date, end_date)

            if not rows:
                continue

            # 🔥 1. 휴일 제거 (US 기준)
            rows = [
                r for r in rows
                if not is_holiday(r["period"], "US")
            ]

            if not rows:
                continue
            
            # 🔥 여기 추가
            today = datetime.now().date()
            rows = [
                r for r in rows
                if r["period"] < today
]

            # 🔥 2. EXISTS 제거 (핵심)
            final_rows = [
                r for r in rows
                if not exists_in_db(conn, r["indicator_name"], r["period"])
            ]

            if not final_rows:
                continue

            saved = save_rows(conn, final_rows)
            conn.commit()

            total_saved += saved

            for r in final_rows:   # 🔥 rows → final_rows
                d = str(r["period"])

                collected_dates_set.add(d)
                success_map[d] = success_map.get(d, 0) + 1
                success_detail_map.setdefault(d, set()).add(indicator_name)

        collected_dates = sorted(list(collected_dates_set))
        total_cnt = len(MACRO_TICKERS)

        success_lines = [
            f"{d} {success_map[d]} Macro Collected"
            for d in collected_dates
        ]

        error_lines = []

        for d in collected_dates:

            success_cnt = success_map.get(d, 0)

            if success_cnt < total_cnt:

                missing = set(MACRO_TICKERS.keys()) - success_detail_map.get(d, set())

                error_lines.append(f"{d} {len(missing)} Macro Not Collected")

                for i, name in enumerate(sorted(missing), start=1):

                    if exists_in_db(conn, name, d):
                        reason = "Data Exists"
                    else:
                        reason = "NULL Data"

                    error_lines.append(f" {i}) {name} / Reason: {reason}")

                error_lines.append("")

        conn.close()

        status = "SUCCESS"

        if total_saved == 0 and not collected_dates:
            status = "NO_CHANGE"

        result = {
            "status": status,
            "collected_dates": collected_dates,
            "success_lines": success_lines,
            "error_lines": error_lines,
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log("interest_macroeconomic", result)
        return result

    except Exception as e:

        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [f"Macro Failed / {str(e)}"],
            "error_count": 0
        }

        print_step_log("interest_macroeconomic", result)
        return result


if __name__ == "__main__":
    run()
