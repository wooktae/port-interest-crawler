"""Script that incrementally collects per-ticker investor flow data from Naver Finance on a daily basis.

It reads the target universe from the DB, fetches investor-flow data from the
Naver Stock JSON API, and stores missing business-day records.

Because it involves external requests and DB upserts, run it only during the
production collection stage.
"""

import time
from datetime import datetime, timedelta

import psycopg2
import requests

from db_config import get_db_config
from interest_get_holidays import is_holiday
from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
}

SOURCE = "naver"
SOURCE_VERSION = "3.0.0"

API_URL = (
    "https://stock.naver.com/api/domestic/detail/"
    "{ticker}/trend"
    "?tradeType=KRX&startIdx=0&pageSize=50"
)


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_tickers():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            su.ticker_code,
            su.company_name,
            MAX(f.trade_date) AS last_date
        FROM stock_universe su
        LEFT JOIN interest_investorflow_raw f
            ON su.ticker_code = f.ticker_code
        GROUP BY
            su.ticker_code,
            su.company_name
        ORDER BY
            su.ticker_code
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def generate_dates(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(trade_date)
        FROM interest_investorflow_raw
    """)

    row = cur.fetchone()
    cur.close()

    if row[0] is None:
        start = datetime.now().date() - timedelta(days=10)
    else:
        start = row[0] + timedelta(days=1)

    end = datetime.now().date() - timedelta(days=1)

    dates = []

    while start <= end:
        if not is_holiday(start, "KR"):
            dates.append(start)

        start += timedelta(days=1)

    return dates


def to_int(value):
    if value is None or value == "":
        return None

    try:
        return int(str(value).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def to_float(value):
    if value is None or value == "":
        return None

    try:
        return float(
            str(value)
            .replace("%", "")
            .replace(",", "")
            .strip()
        )
    except (TypeError, ValueError):
        return None


def calculate_change_rate(close_price, price_diff):
    if close_price is None or price_diff is None:
        return None

    previous_close = close_price - price_diff

    if previous_close == 0:
        return None

    return round(
        (price_diff / previous_close) * 100,
        2
    )


def parse_item(item):
    bizdate = item.get("bizdate")

    if not bizdate:
        return None

    try:
        trade_date = datetime.strptime(
            bizdate,
            "%Y%m%d"
        ).date()
    except (TypeError, ValueError):
        return None

    close_price = to_int(item.get("closePrice"))
    price_diff = to_int(item.get("prevChangePrice"))

    return {
        "trade_date": trade_date,
        "close_price": close_price,
        "price_diff": price_diff,
        "price_change_rate": calculate_change_rate(
            close_price,
            price_diff
        ),
        "volume": to_int(
            item.get("tradeVolume")
        ),
        "institution_net": to_int(
            item.get("organPureBuyQuant")
        ),
        "foreign_net": to_int(
            item.get("foreignerPureBuyQuant")
        ),
        "foreign_hold_shares": to_int(
            item.get("frgnStock")
        ),
        "foreign_hold_ratio": to_float(
            item.get("frgnHoldRatio")
        ),
    }


def fetch_rows(session, ticker):
    url = API_URL.format(ticker=ticker)

    response = session.get(
        url,
        headers=HEADERS,
        timeout=(5, 10)
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list):
        raise ValueError(
            f"Unexpected Naver investor flow response "
            f"for ticker={ticker}: "
            f"type={type(payload).__name__}"
        )

    records = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        record = parse_item(item)

        if record:
            records.append(record)

    return records


def save_batch(cur, ticker, records):
    for r in records:
        cur.execute("""
            INSERT INTO interest_investorflow_raw (
                ticker_code,
                trade_date,
                close_price,
                price_diff,
                price_change_rate,
                volume,
                institution_net,
                foreign_net,
                foreign_hold_shares,
                foreign_hold_ratio,
                source,
                source_version,
                collected_at
            )
            VALUES (
                %(ticker)s,
                %(trade_date)s,
                %(close_price)s,
                %(price_diff)s,
                %(price_change_rate)s,
                %(volume)s,
                %(institution_net)s,
                %(foreign_net)s,
                %(foreign_hold_shares)s,
                %(foreign_hold_ratio)s,
                %(source)s,
                %(source_version)s,
                now()
            )
            ON CONFLICT (ticker_code, trade_date)
            DO UPDATE SET
                close_price = EXCLUDED.close_price,
                price_diff = EXCLUDED.price_diff,
                price_change_rate = EXCLUDED.price_change_rate,
                volume = EXCLUDED.volume,
                institution_net = EXCLUDED.institution_net,
                foreign_net = EXCLUDED.foreign_net,
                foreign_hold_shares = EXCLUDED.foreign_hold_shares,
                foreign_hold_ratio = EXCLUDED.foreign_hold_ratio,
                updated_at = now()
        """, {
            "ticker": ticker,
            "source": SOURCE,
            "source_version": SOURCE_VERSION,
            **r
        })


def get_existing_tickers_by_date(conn, target_date):
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code
        FROM interest_investorflow_raw
        WHERE trade_date = %s
    """, (target_date,))

    rows = {
        r[0]
        for r in cur.fetchall()
    }

    cur.close()

    return rows


def run():
    conn = get_conn()
    tickers = get_tickers()

    collected_dates = set()
    success_map = {}

    session = None
    cur = None

    try:
        session = requests.Session()
        cur = conn.cursor()

        target_dates = generate_dates(conn)

        if not target_dates:
            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": [],
                "failed_lines": [],
                "error_count": 0
            }

            print_step_log(
                "interest_investorflow",
                result
            )

            return result

        target_date_set = set(target_dates)

        existing_map = {
            target_date: get_existing_tickers_by_date(
                conn,
                target_date
            )
            for target_date in target_dates
        }

        for ticker, company, last_date in tickers:
            needed_dates = {
                target_date
                for target_date in target_dates
                if ticker not in existing_map[target_date]
            }

            if not needed_dates:
                continue

            rows = fetch_rows(
                session,
                ticker
            )

            target_rows = [
                row
                for row in rows
                if row["trade_date"] in target_date_set
                and row["trade_date"] in needed_dates
            ]

            if not target_rows:
                continue

            save_batch(
                cur,
                ticker,
                target_rows
            )

            for r in target_rows:
                d = str(r["trade_date"])

                collected_dates.add(d)

                success_map[d] = (
                    success_map.get(d, 0) + 1
                )

            time.sleep(0.05)

        conn.commit()

        if not collected_dates:
            status = "NO_CHANGE"
            success_lines = []
        else:
            status = "SUCCESS"

            success_lines = [
                f"{d} {success_map[d]} Investor Collected"
                for d in sorted(collected_dates)
            ]

        result = {
            "status": status,
            "collected_dates": sorted(
                collected_dates
            ),
            "success_lines": success_lines,
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log(
            "interest_investorflow",
            result
        )

        return result

    except Exception as e:
        conn.rollback()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [str(e)],
            "error_count": 0
        }

        print_step_log(
            "interest_investorflow",
            result
        )

        return result

    finally:
        if cur is not None:
            cur.close()

        if session is not None:
            session.close()

        conn.close()


if __name__ == "__main__":
    run()