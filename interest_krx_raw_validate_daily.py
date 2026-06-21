"""KRX GUI worker 수집 후 program / shortsell raw 적재 여부를 검증한다.

Step 2 INTEREST_CRAWLER guard 전용 스크립트다.
interest_program_raw / interest_shortsell_raw 의 expected trade_date row_count 와 max_date 를 확인한다.

사용 예:
    python interest_krx_raw_validate_daily.py --expected-date 2026-06-19
    python interest_krx_raw_validate_daily.py --run-date 2026-06-20

실패 시 exit code 30 을 반환한다.
"""

import argparse
import sys
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import psycopg2

from db_config import get_db_config


SEOUL_TZ = ZoneInfo("Asia/Seoul")

CHECKS = [
    {
        "label": "program",
        "table_name": "interest_program_raw",
        "date_column": "trade_date",
        "min_count": 1,
    },
    {
        "label": "shortsell",
        "table_name": "interest_shortsell_raw",
        "date_column": "trade_date",
        "min_count": 1,
    },
]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def previous_weekday(base_date: date) -> date:
    candidate = base_date - timedelta(days=1)

    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate


def resolve_expected_date(args) -> date:
    if args.expected_date:
        return parse_date(args.expected_date)

    if args.run_date:
        return previous_weekday(parse_date(args.run_date))

    today = datetime.now(SEOUL_TZ).date()
    return previous_weekday(today)


def get_conn():
    return psycopg2.connect(**get_db_config())


def validate_table(cur, check: dict, expected: date) -> bool:
    table_name = check["table_name"]
    date_column = check["date_column"]
    min_count = int(check["min_count"])

    sql = f"""
        SELECT
            MAX({date_column})::text AS max_date,
            COUNT(*) FILTER (WHERE {date_column} = %s::date) AS expected_count
        FROM {table_name}
    """

    cur.execute(sql, (expected.isoformat(),))
    max_date, expected_count = cur.fetchone()

    expected_count = int(expected_count or 0)

    ok = (
        max_date is not None
        and str(max_date) >= expected.isoformat()
        and expected_count >= min_count
    )

    status = "OK" if ok else "FAIL"

    print(
        f"{status:<6} | {table_name:<28} | "
        f"expected={expected.isoformat()} | "
        f"max_date={max_date} | "
        f"expected_count={expected_count} | "
        f"min_count={min_count}"
    )

    return ok


def run(args) -> int:
    expected = resolve_expected_date(args)

    print("=" * 100)
    print("KRX RAW VALIDATION START")
    print("=" * 100)
    print(f"expected_date={expected.isoformat()}")

    failed = False

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_schema, current_setting('search_path')")
            current_user, current_schema, search_path = cur.fetchone()

            print(
                f"session | user={current_user} | "
                f"schema={current_schema} | search_path={search_path}"
            )

            for check in CHECKS:
                if not validate_table(cur, check, expected):
                    failed = True

    print("=" * 100)
    print("KRX RAW VALIDATION SUMMARY")
    print("=" * 100)

    if failed:
        print("[FAILED] KRX program / shortsell raw validation failed")
        return 30

    print("[OK] KRX program / shortsell raw validation passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate KRX program / shortsell raw tables for expected trade_date."
    )

    parser.add_argument(
        "--expected-date",
        help="Expected KRX raw trade_date. Example: 2026-06-19",
    )

    parser.add_argument(
        "--run-date",
        help="Wrapper RunDate. Expected date is previous weekday of this date.",
    )

    return parser


if __name__ == "__main__":
    parser = build_parser()
    parsed_args = parser.parse_args()
    sys.exit(run(parsed_args))
