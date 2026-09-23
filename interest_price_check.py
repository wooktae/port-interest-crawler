"""Check script that verifies whether watchlist price data is missing.

It reads the DB universe and price table and prints the uncollected tickers based on the recent business day.
It includes holiday determination and DB reads, and is for inspection only; it does not perform any save logic.
"""

import psycopg2
from db_config import get_db_config
from datetime import datetime, timedelta

from interest_get_holidays import is_holiday


DB_CONFIG = get_db_config()

START_DATE = datetime(2022, 1, 1).date()
PARTIAL_THRESHOLD = 60


# 🔥 KRX actual holiday correction (core)
KRX_EXTRA_HOLIDAYS = {
    # 2022
    datetime(2022, 3, 9).date(),
    datetime(2022, 5, 9).date(),
    datetime(2022, 6, 1).date(),
    datetime(2022, 10, 10).date(),

    # 2023
    datetime(2023, 5, 1).date(),
    datetime(2023, 5, 29).date(),
    datetime(2023, 10, 2).date(),

    # 2024
    datetime(2024, 4, 10).date(),
    datetime(2024, 5, 1).date(),
    datetime(2024, 10, 1).date(),

    # 2025
    datetime(2025, 1, 27).date(),
    datetime(2025, 3, 3).date(),
    datetime(2025, 5, 1).date(),
    datetime(2025, 5, 6).date(),
    datetime(2025, 6, 3).date(),

    # 2026
    datetime(2026, 3, 2).date(),
}


def is_krx_holiday(d):
    return is_holiday(d, "KR") or d in KRX_EXTRA_HOLIDAYS


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_universe(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code
        FROM stock_universe
    """)

    rows = [r[0] for r in cur.fetchall()]
    cur.close()

    return rows


def get_existing_map(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code, price_date
        FROM interest_price_raw
        WHERE price_date >= %s
    """, (START_DATE,))

    rows = cur.fetchall()
    cur.close()

    data = {}

    for code, d in rows:
        if d not in data:
            data[d] = set()
        data[d].add(code)

    return data


def run():

    conn = get_conn()

    universe = get_universe(conn)
    universe_set = set(universe)

    existing_map = get_existing_map(conn)

    today = datetime.now().date()

    d = START_DATE

    missing_date_count = 0
    missing_ticker_total = 0

    while d < today:

        # 🔥 fully remove holidays
        if is_krx_holiday(d):
            d += timedelta(days=1)
            continue

        exist_codes = existing_map.get(d, set())

        # None at all
        if not exist_codes:
            print(f"[MISSING DATE] {d} → 전체 없음 ({len(universe)} 종목)")
            missing_date_count += 1
            missing_ticker_total += len(universe)

        else:
            missing_codes = universe_set - exist_codes
            missing_cnt = len(missing_codes)

            if missing_cnt >= PARTIAL_THRESHOLD:
                print(f"[PARTIAL] {d} → {missing_cnt}개 누락")
                print(f"  sample: {list(missing_codes)[:5]}")
                missing_ticker_total += missing_cnt

        d += timedelta(days=1)

    conn.close()

    print("\n===== SUMMARY =====")
    print(f"missing date count: {missing_date_count}")
    print(f"missing ticker total: {missing_ticker_total}")


if __name__ == "__main__":
    run()
