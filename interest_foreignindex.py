import yfinance as yf
import psycopg2
import psycopg2.extras
import json
import contextlib
import sys
import os
from datetime import datetime, timedelta
import math

from interest_log_format import print_step_log


DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

INDEX_MAP = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOWJONES": "^DJI",
    "NIKKEI225": "^N225",
    "SHANGHAI": "000001.SS",
    "HANGSENG": "^HSI"
}

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.2.0"

DEFAULT_START_DATE = "2007-01-01"

NO_VOLUME_INDEXES = {"SHANGHAI", "HANGSENG"}


@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, "w") as fnull:
        old_stderr = sys.stderr
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

def is_invalid_number(value):
    if value is None:
        return True

    try:
        v = float(value)
        return math.isnan(v) or math.isinf(v)
    except Exception:
        return True


def to_safe_float(value):
    if is_invalid_number(value):
        return None
    return round(float(value), 4)


def to_json_safe(value):
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [to_json_safe(v) for v in value]

    return value

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_db_latest_date(conn, index_name):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(date)
        FROM interest_foreignindex_raw
        WHERE index_name = %s
    """, (index_name,))

    row = cur.fetchone()
    cur.close()

    return row[0]


def exists_in_db(conn, index_name, date):

    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM interest_foreignindex_raw
        WHERE index_name = %s
          AND date = %s
        LIMIT 1
    """, (index_name, date))

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


def fetch_index_rows(index_name, ticker, start_date, end_date):

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

        today = datetime.now().date()   # 🔥 추가

        for _, r in df.iterrows():

            trade_date = r["Date"].date()

            # 🔥 오늘 데이터 제거 (핵심)
            if trade_date >= today:
                continue

            open_price = to_safe_float(r["Open"])
            high_price = to_safe_float(r["High"])
            low_price = to_safe_float(r["Low"])
            close_price = to_safe_float(r["Close"])

            if close_price is None:
                print(f"[SKIP] {index_name} {trade_date} close_price is invalid")
                continue

            volume = None

            if index_name not in NO_VOLUME_INDEXES:
                try:
                    v = int(r["Volume"])
                    if v > 0:
                        volume = v
                except:
                    volume = None

            now_ts = datetime.now()

            raw_json = to_json_safe({
                "ticker": ticker,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume
            })
            
            rows.append({
                "index_name": index_name,
                "date": trade_date,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": close_price,
                "volume": volume,
                "raw_json": json.dumps(raw_json, ensure_ascii=False, allow_nan=False),
                "collected_at": now_ts,
                "as_of_ts": now_ts,
                "source": SOURCE_NAME,
                "source_version": SOURCE_VERSION
            })

        return rows

    except Exception as e:
        print(f"[ERROR] fetch_index_rows failed: {index_name} {ticker} / {e}")
        return []


def save_rows(conn, records):

    if not records:
        return 0

    sql = """
        INSERT INTO interest_foreignindex_raw (
            index_name,
            date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            raw_json,
            collected_at,
            as_of_ts,
            source,
            source_version
        )
        VALUES (
            %(index_name)s,
            %(date)s,
            %(open_price)s,
            %(high_price)s,
            %(low_price)s,
            %(close_price)s,
            %(volume)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_ts)s,
            %(source)s,
            %(source_version)s
        )
        ON CONFLICT (index_name, date)
        DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
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

        from interest_get_holidays import is_holiday

        for index_name, ticker in INDEX_MAP.items():

            latest_db_date = get_db_latest_date(conn, index_name)
            start_date, end_date = build_fetch_range(latest_db_date)

            if start_date >= end_date:
                continue

            rows = fetch_index_rows(index_name, ticker, start_date, end_date)

            if not rows:
                continue

            # 🔥 1. 휴일 제거
            rows = [
                r for r in rows
                if not is_holiday(r["date"], "US")
            ]

            if not rows:
                continue

            # 🔥 2. EXISTS 제거 (핵심)
            final_rows = [
                r for r in rows
                if not exists_in_db(conn, r["index_name"], r["date"])
            ]

            if not final_rows:
                continue

            saved = save_rows(conn, final_rows)
            conn.commit()

            total_saved += saved

            for r in final_rows:
                d = str(r["date"])

                collected_dates_set.add(d)
                success_map[d] = success_map.get(d, 0) + 1
                success_detail_map.setdefault(d, set()).add(index_name)

        collected_dates = sorted(list(collected_dates_set))
        total_index = len(INDEX_MAP)

        success_lines = [
            f"{d} {success_map[d]} Index Collected"
            for d in collected_dates
        ]

        error_lines = []

        for d in collected_dates:

            success_cnt = success_map.get(d, 0)

            if success_cnt < total_index:

                missing_indexes = set(INDEX_MAP.keys()) - success_detail_map.get(d, set())

                error_lines.append(f"{d} {len(missing_indexes)} Index Not Collected")

                for i, name in enumerate(sorted(missing_indexes), start=1):

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

        print_step_log("interest_foreignindex", result)
        return result

    except Exception as e:

        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [
                f"Failed to Collect Foreign Index Data / Reason: {str(e)}"
            ],
            "error_count": 0
        }

        print_step_log("interest_foreignindex", result)
        return result


if __name__ == "__main__":
    run()