"""yfinance 기반 원자재 가격 데이터를 일일 증분 수집하는 스크립트다.

원자재별 최신 적재일을 확인한 뒤 필요한 기간만 조회해 PostgreSQL에 저장한다.
yfinance 외부 요청과 DB upsert가 포함되므로 문서화/분석 중에는 실행하지 않는다.
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

COMMODITY_MAP = {
    "WTI": "CL=F",
    "BRENT": "BZ=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COPPER": "HG=F",
    "NATURAL_GAS": "NG=F"
}

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


def get_db_latest_date(conn, commodity_code):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(date)
        FROM interest_commodity_raw
        WHERE commodity_code = %s
    """, (commodity_code,))

    row = cur.fetchone()
    cur.close()

    return row[0]


def exists_in_db(conn, commodity_code, date):

    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM interest_commodity_raw
        WHERE commodity_code = %s
          AND date = %s
        LIMIT 1
    """, (commodity_code, date))

    exists = cur.fetchone() is not None
    cur.close()

    return exists


def build_fetch_range(latest_db_date):

    if latest_db_date:
        start_date = latest_db_date + timedelta(days=1)
    else:
        start_date = datetime.strptime(DEFAULT_START_DATE, "%Y-%m-%d").date()

    end_date = datetime.now().date()

    return start_date, end_date


def fetch_commodity_rows(commodity_code, ticker, start_date, end_date):

    try:
        with suppress_stderr():
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False
            )

        if df is None or df.empty:
            return []

        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        rows = []

        today = datetime.now().date()  # 🔥 추가

        for _, r in df.iterrows():

            trade_date = r["Date"].date()

            # 🔥 오늘 데이터 제거
            if trade_date >= today:
                continue

            if r["Close"] != r["Close"]:
                continue

            price = round(float(r["Close"]), 4)

            now_ts = datetime.now()

            rows.append({
                "commodity_code": commodity_code,
                "date": trade_date,
                "price": price,
                "raw_json": json.dumps({
                    "ticker": ticker,
                    "close": price
                }, ensure_ascii=False),
                "collected_at": now_ts,
                "as_of_ts": now_ts,
                "source": SOURCE_NAME,
                "source_version": SOURCE_VERSION
            })

        return rows

    except Exception:
        return []


def save_rows(conn, records):

    if not records:
        return 0

    sql = """
        INSERT INTO interest_commodity_raw (
            commodity_code,
            date,
            price,
            raw_json,
            collected_at,
            as_of_ts,
            source,
            source_version
        )
        VALUES (
            %(commodity_code)s,
            %(date)s,
            %(price)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_ts)s,
            %(source)s,
            %(source_version)s
        )
        ON CONFLICT (commodity_code, date)
        DO UPDATE SET
            price = EXCLUDED.price,
            raw_json = EXCLUDED.raw_json,
            collected_at = EXCLUDED.collected_at,
            as_of_ts = EXCLUDED.as_of_ts,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
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

        for commodity_code, ticker in COMMODITY_MAP.items():

            latest_db_date = get_db_latest_date(conn, commodity_code)
            start_date, end_date = build_fetch_range(latest_db_date)

            if start_date >= end_date:
                continue

            rows = fetch_commodity_rows(commodity_code, ticker, start_date, end_date)

            if not rows:
                continue

            # 🔥 1. 휴일 제거 (US 기준)
            rows = [
                r for r in rows
                if not is_holiday(r["date"], "US")
            ]

            if not rows:
                continue

            # 🔥 2. EXISTS 제거 (핵심)
            final_rows = [
                r for r in rows
                if not exists_in_db(conn, r["commodity_code"], r["date"])
            ]

            if not final_rows:
                continue

            saved = save_rows(conn, final_rows)
            conn.commit()

            total_saved += saved

            for r in final_rows:  # 🔥 rows → final_rows
                d = str(r["date"])

                collected_dates_set.add(d)
                success_map[d] = success_map.get(d, 0) + 1
                success_detail_map.setdefault(d, set()).add(commodity_code)

        collected_dates = sorted(list(collected_dates_set))
        total_cnt = len(COMMODITY_MAP)

        success_lines = [
            f"{d} {success_map[d]} Commodity Collected"
            for d in collected_dates
        ]

        error_lines = []

        for d in collected_dates:

            success_cnt = success_map.get(d, 0)

            if success_cnt < total_cnt:

                missing = set(COMMODITY_MAP.keys()) - success_detail_map.get(d, set())

                error_lines.append(f"{d} {len(missing)} Commodity Not Collected")

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

        print_step_log("interest_commodity", result)
        return result

    except Exception as e:

        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [
                f"Failed to Collect Commodity Data / Reason: {str(e)}"
            ],
            "error_count": 0
        }

        print_step_log("interest_commodity", result)
        return result


if __name__ == "__main__":
    run()
