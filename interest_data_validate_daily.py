"""일일 수집 후 핵심 테이블의 데이터 품질을 빠르게 점검하는 스크립트다.

PostgreSQL 최신일, NULL, row count, 이상치, 중복 여부를 확인한다.
휴일 판정 과정에서 외부 요청이 포함될 수 있으므로 운영 점검 목적일 때만 실행한다.
"""

import requests
import psycopg2
from db_config import get_db_config
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

# =========================================================
# CONFIG
# =========================================================
DB_CONFIG = get_db_config()

SEOUL_TZ = ZoneInfo("Asia/Seoul")
HOLIDAY_API_BASE = "https://date.nager.at/api/v3/PublicHolidays"

TABLES = [
    {"table_name": "interest_news_raw",          "latest_expr": "MAX(as_of_date)",   "market": "KR"},
    {"table_name": "interest_agency_raw",        "latest_expr": "MAX(publish_date)", "market": "KR"},
    {"table_name": "interest_foreignindex_raw",  "latest_expr": "MAX(date)",         "market": "US"},
    {"table_name": "interest_commodity_raw",     "latest_expr": "MAX(date)",         "market": "US"},
    {"table_name": "interest_macroeconomic_raw", "latest_expr": "MAX(period)",       "market": "US"},
    {"table_name": "interest_price_raw",         "latest_expr": "MAX(price_date)",   "market": "KR"},
    {"table_name": "interest_investorflow_raw",  "latest_expr": "MAX(trade_date)",   "market": "KR"},
    {"table_name": "interest_program_raw",       "latest_expr": "MAX(trade_date)",   "market": "KR"},
    {"table_name": "interest_shortsell_raw",     "latest_expr": "MAX(trade_date)",   "market": "KR"},
    {"table_name": "interest_marketbreadth_raw", "latest_expr": "MAX(date)",         "market": "KR"},
]

# =========================================================
# UTILS
# =========================================================
def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fmt_date(d):
    return d.strftime("%Y-%m-%d") if d else "None"

def is_weekend(d: date):
    return d.weekday() >= 5

def fetch_holidays(year: int, country_code: str):
    url = f"{HOLIDAY_API_BASE}/{year}/{country_code}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    rows = resp.json()
    return set(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows)

def get_holiday_info(target_date: date, country_code: str, cache: dict):
    key = (country_code, target_date.year)
    if key not in cache:
        cache[key] = fetch_holidays(target_date.year, country_code)

    return {
        "is_non_business_day": is_weekend(target_date) or target_date in cache[key]
    }

def get_previous_business_day(base_date: date, holiday_func):
    d = base_date - timedelta(days=1)
    while holiday_func(d)["is_non_business_day"]:
        d -= timedelta(days=1)
    return d

def query_latest_dates():
    sql = "\nUNION ALL\n".join([
        f"SELECT '{t['table_name']}', {t['latest_expr']} FROM {t['table_name']}"
        for t in TABLES
    ])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    return {t: d for t, d in rows}

# =========================================================
# LOG FORMAT
# =========================================================
def log_section(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)

# =========================================================
# QC CHECKS
# =========================================================
def check_nulls(conn):
    log_section("NULL CHECK")

    queries = {
        "news": "SELECT COUNT(*) FROM interest_news_raw WHERE news_id IS NULL OR title IS NULL OR published_at IS NULL",
        "agency": "SELECT COUNT(*) FROM interest_agency_raw WHERE ticker_code IS NULL OR publish_date IS NULL",
        "price": "SELECT COUNT(*) FROM interest_price_raw WHERE price_date IS NULL",
        "foreignindex": "SELECT COUNT(*) FROM interest_foreignindex_raw WHERE close_price IS NULL",
    }

    with conn.cursor() as cur:
        for k, q in queries.items():
            cur.execute(q)
            cnt = cur.fetchone()[0]
            print(f"{'OK' if cnt==0 else 'WARN':<6} | {k:<15} | null_count={cnt}")

def check_row_counts(conn):
    log_section("ROW COUNT CHECK")

    rules = [
        ("price", "interest_price_raw", "price_date", 300),
        ("investorflow", "interest_investorflow_raw", "trade_date", 300),
        ("shortsell", "interest_shortsell_raw", "trade_date", 150),
        ("foreignindex", "interest_foreignindex_raw", "date", 5),
        ("commodity", "interest_commodity_raw", "date", 5),
        ("macro", "interest_macroeconomic_raw", "period", 5),
    ]

    with conn.cursor() as cur:
        for name, table, col, min_cnt in rules:
            cur.execute(f"""
                SELECT {col}, COUNT(*)
                FROM {table}
                GROUP BY {col}
                ORDER BY {col} DESC
                LIMIT 2
            """)
            for d, cnt in cur.fetchall():
                print(f"{'OK' if cnt>=min_cnt else 'WARN':<6} | {name:<15} | {d} | count={cnt}")

def check_anomalies(conn):
    log_section("ANOMALY CHECK")

    with conn.cursor() as cur:

        cur.execute("SELECT COUNT(*) FROM interest_agency_raw WHERE target_price <= 0")
        print(f"{'OK' if cur.fetchone()[0]==0 else 'WARN':<6} | target_price")

        cur.execute("SELECT COUNT(*) FROM interest_news_raw WHERE published_at::date != as_of_date")
        print(f"{'OK' if cur.fetchone()[0]==0 else 'WARN':<6} | news_date")

def check_duplicates(conn):
    log_section("DUPLICATE CHECK")

    with conn.cursor() as cur:

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT news_id FROM interest_news_raw
                GROUP BY news_id HAVING COUNT(*) > 1
            ) t
        """)
        print(f"{'OK' if cur.fetchone()[0]==0 else 'WARN':<6} | news_duplicate")

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT ticker_code, agency_name, publish_date, title
                FROM interest_agency_raw
                GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
            ) t
        """)
        print(f"{'OK' if cur.fetchone()[0]==0 else 'WARN':<6} | agency_duplicate")

# =========================================================
# MAIN
# =========================================================
def run():
    """일일 validation 항목을 순서대로 실행하고 결과를 출력한다."""
    now = datetime.now(SEOUL_TZ)
    today = now.date()
    yesterday = today - timedelta(days=1)

    cache = {}

    kr = lambda d: get_holiday_info(d, "KR", cache)
    us = lambda d: get_holiday_info(d, "US", cache)

    expected_kr = yesterday if not kr(yesterday)["is_non_business_day"] else get_previous_business_day(today, kr)
    expected_us = yesterday if not us(yesterday)["is_non_business_day"] else get_previous_business_day(today, us)

    latest = query_latest_dates()

    log_section("DATE VALIDATION")

    for t in TABLES:
        name = t["table_name"]
        exp = expected_kr if t["market"]=="KR" else expected_us
        act = latest.get(name)

        if act is None:
            status = "FAIL"
        elif act < exp:
            status = "WARN"
        else:
            status = "OK"

        print(f"{status:<6} | {name:<30} | {fmt_date(act)} vs {exp}")

    with get_conn() as conn:
        check_nulls(conn)
        check_row_counts(conn)
        check_anomalies(conn)
        check_duplicates(conn)

    log_section("FINAL SUMMARY")
    print("QC FINISHED")

if __name__ == "__main__":
    run()
