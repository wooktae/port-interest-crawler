"""Script that incrementally collects per-ticker investor flow data from Naver Finance on a daily basis.

It reads the target universe from the DB, fetches investor-flow data from the
Naver Stock JSON API, and stores missing business-day records.

Because it involves external requests and DB upserts, run it only during the
production collection stage.
"""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
import requests

from db_config import get_db_config
from interest_get_holidays import is_holiday
from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
}

SOURCE = "naver"
SOURCE_VERSION = "3.1.0"
KST = ZoneInfo("Asia/Seoul")
MAX_PAGES_PER_TICKER = 100

API_URL = "https://m.stock.naver.com/front-api/stock/domestic/trend"


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
        start = datetime.now(KST).date() - timedelta(days=10)
    else:
        start = row[0] + timedelta(days=1)

    end = datetime.now(KST).date() - timedelta(days=1)

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
    """Normalize the Naver mobile KRX payload to the existing DB contract."""
    if not isinstance(item, dict):
        return None

    date_str = item.get("localTradedAt")
    krx = item.get("krx")
    if not date_str or not isinstance(krx, dict):
        return None

    try:
        trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

    close_price = to_int(krx.get("closingPrice"))
    price_diff = to_int(krx.get("changePrice"))
    volume = to_int(krx.get("tradingVolume"))
    institution_net = to_int(krx.get("organizationNetVolume"))
    foreign_net = to_int(krx.get("foreignNetVolume"))
    foreign_hold_shares = to_int(item.get("foreignHoldingStockQuantity"))
    foreign_hold_ratio = to_float(item.get("foreignHoldingRatio"))

    # Reject incomplete market records instead of silently saving NULL signals.
    required = (close_price, price_diff, volume, institution_net,
                foreign_net, foreign_hold_shares, foreign_hold_ratio)
    if any(value is None for value in required):
        raise ValueError(f"Incomplete KRX investor-flow fields for date={date_str}")

    return {
        "trade_date": trade_date,
        "close_price": close_price,
        "price_diff": price_diff,
        "price_change_rate": calculate_change_rate(close_price, price_diff),
        "volume": volume,
        "institution_net": institution_net,
        "foreign_net": foreign_net,
        "foreign_hold_shares": foreign_hold_shares,
        "foreign_hold_ratio": foreign_hold_ratio,
    }


def fetch_rows(session, ticker, needed_dates=None):
    """Read cursor pages until requested dates are found or history ends.

    Without needed_dates, return only the newest API page (read-only probe).
    With needed_dates, page backward only until the requested window is covered
    or has been passed. The cursor is opaque; never decode or compute it.
    """
    params = {"code": ticker}
    cursor = None
    seen_cursors = set()
    records_by_date = {}
    required_dates = set(needed_dates) if needed_dates is not None else None
    if required_dates is not None and not required_dates:
        return []

    for page in range(1, MAX_PAGES_PER_TICKER + 1):
        if cursor is not None:
            params["cursor"] = cursor

        response = session.get(
            API_URL, params=params, headers=HEADERS, timeout=(5, 10)
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise requests.HTTPError(
                f"Naver InvestorFlow HTTP error: ticker={ticker}, "
                f"page={page}, status={response.status_code}, "
                f"url={response.url}"
            ) from exc

        payload = response.json()
        if not isinstance(payload, dict) or payload.get("isSuccess") is not True:
            raise ValueError(
                f"Naver InvestorFlow API rejected ticker={ticker}, page={page}: "
                f"{str(payload)[:250]}"
            )

        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise ValueError(f"Invalid InvestorFlow response: ticker={ticker}, page={page}")

        items = result["items"]
        if not items:
            if result.get("hasNext"):
                raise ValueError(f"Empty InvestorFlow page with hasNext: ticker={ticker}")
            break

        for item in items:
            record = parse_item(item)
            if record is not None:
                records_by_date[record["trade_date"]] = record

        # A standalone read without a date window is intentionally bounded to
        # one page. Full historical collection must supply needed_dates.
        if required_dates is None:
            break

        if required_dates.issubset(records_by_date):
            break

        # All later pages should be older. Once the oldest known date is before
        # the earliest requested date, pagination cannot fill later missing rows.
        if required_dates and records_by_date:
            if min(records_by_date) < min(required_dates):
                break

        if result.get("hasNext") is not True:
            break

        next_cursor = result.get("cursor")
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            raise ValueError(f"Invalid/repeated InvestorFlow cursor: ticker={ticker}, page={page}")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        time.sleep(0.05)
    else:
        raise RuntimeError(
            f"InvestorFlow exceeded {MAX_PAGES_PER_TICKER} pages: ticker={ticker}"
        )

    # A newly listed/halted ticker may lack some historical dates. We return
    # available records, and the caller reports coverage rather than forging rows.
    return [records_by_date[d] for d in sorted(records_by_date)]


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
                source = EXCLUDED.source,
                source_version = EXCLUDED.source_version,
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
                ticker,
                needed_dates=needed_dates,
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
            "error_count": 1
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