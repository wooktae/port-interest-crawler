"""Script that incrementally collects Naver Stock research / brokerage opinion data on a daily basis.

It requests Naver Stock's JSON research API and upserts company research reports
into PostgreSQL.

Because it involves external requests and DB writes, run it only during the
production collection stage.
"""

import json
import re
import time
from datetime import datetime, timezone

import psycopg2
import requests
from bs4 import BeautifulSoup

from db_config import get_db_config
from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://stock.naver.com/research/company",
}

API_URL = (
    "https://stock.naver.com/api/stockSecurity/researches/v2/company"
    "?index={index}&size={size}"
)

SOURCE = "naver"
SOURCE_VERSION = "3.0.0"

PAGE_SIZE = 15
PAGE_SLEEP_SEC = 0.10
REQUEST_TIMEOUT_SEC = 15


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_db_latest_publish_date(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(publish_date)
        FROM interest_agency_raw
    """)

    row = cur.fetchone()
    cur.close()

    return row[0]


def safe_int(value):
    """Convert Naver API price values to int safely."""
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()

    if not text:
        return None

    digits = re.sub(r"[^0-9]", "", text)

    if not digits:
        return None

    try:
        return int(digits)
    except (TypeError, ValueError):
        return None


def clean_html_content(html):
    """Convert the HTML-formatted research summary to plain text."""
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def parse_publish_date(value):
    if not value:
        return None

    value = str(value).strip()

    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def fetch_page(session, index):
    """Fetch one page from the Naver Stock research API."""
    url = API_URL.format(
        index=index,
        size=PAGE_SIZE,
    )

    resp = session.get(
        url,
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()

    data = resp.json()

    if not isinstance(data, dict):
        raise ValueError(
            f"Unexpected API response type: {type(data).__name__}"
        )

    items = data.get("items")

    if items is None:
        raise ValueError(
            f"'items' field missing from API response: index={index}"
        )

    if not isinstance(items, list):
        raise ValueError(
            f"Unexpected 'items' type: {type(items).__name__}"
        )

    return data


def parse_item(item):
    """Convert one Naver API research item into the DB record structure."""

    publish_date = parse_publish_date(item.get("writeDate"))
    now_utc = datetime.now(timezone.utc)

    ticker_code = item.get("itemCode")
    company_name = item.get("itemName")
    agency_name = item.get("brokerName")
    title = item.get("title")

    content = clean_html_content(item.get("content"))

    recommendation = item.get("opinionText")
    target_price = safe_int(item.get("goalPrice"))

    if ticker_code:
        ticker_code = str(ticker_code).strip()

    if company_name:
        company_name = str(company_name).strip()

    if agency_name:
        agency_name = str(agency_name).strip()

    if title:
        title = str(title).strip()

    if recommendation:
        recommendation = str(recommendation).strip()

    raw_json = json.dumps(
        {
            "nid": item.get("nid"),
            "title": item.get("title"),
            "content": item.get("content"),
            "brokerName": item.get("brokerName"),
            "brokerCode": item.get("brokerCode"),
            "writeDate": item.get("writeDate"),
            "readCount": item.get("readCount"),
            "itemCode": item.get("itemCode"),
            "itemName": item.get("itemName"),
            "goalPrice": item.get("goalPrice"),
            "opinionText": item.get("opinionText"),
            "opinionType": item.get("opinionType"),
        },
        ensure_ascii=False,
    )

    return {
        "ticker_code": ticker_code,
        "company_name": company_name,
        "agency_name": agency_name,
        "title": title,
        "content": content,
        "recommendation": recommendation,
        "target_price": target_price,
        "publish_date": publish_date,
        "raw_json": raw_json,
        "source": SOURCE,
        "source_version": SOURCE_VERSION,
        "as_of_date": publish_date,
        "as_of_ts": now_utc,
    }


def save_record(cur, record):
    if not record["ticker_code"]:
        return False

    if not record["agency_name"]:
        return False

    if not record["publish_date"]:
        return False

    if not record["title"]:
        return False

    cur.execute("""
        INSERT INTO interest_agency_raw (
            ticker_code,
            company_name,
            agency_name,
            title,
            content,
            recommendation,
            target_price,
            publish_date,
            raw_json,
            collected_at,
            source,
            source_version,
            as_of_date,
            as_of_ts
        )
        VALUES (
            %(ticker_code)s,
            %(company_name)s,
            %(agency_name)s,
            %(title)s,
            %(content)s,
            %(recommendation)s,
            %(target_price)s,
            %(publish_date)s,
            %(raw_json)s,
            now(),
            %(source)s,
            %(source_version)s,
            %(as_of_date)s,
            %(as_of_ts)s
        )
        ON CONFLICT (
            ticker_code,
            agency_name,
            publish_date,
            title
        )
        DO UPDATE SET
            company_name = EXCLUDED.company_name,
            content = EXCLUDED.content,
            recommendation = EXCLUDED.recommendation,
            target_price = EXCLUDED.target_price,
            raw_json = EXCLUDED.raw_json,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
            as_of_date = EXCLUDED.as_of_date,
            as_of_ts = EXCLUDED.as_of_ts,
            updated_at = now();
    """, record)

    return True


def run():
    conn = None

    collected_dates = []
    success_map = {}
    fail_lines = []

    try:
        conn = get_conn()
        cur = conn.cursor()

        latest_db_date = get_db_latest_publish_date(conn)

        session = requests.Session()
        session.headers.update(HEADERS)

        index = 0
        stop = False

        while True:
            data = fetch_page(session, index)

            items = data.get("items", [])
            has_next = bool(data.get("hasNext"))

            if not items:
                break

            for item in items:
                nid = item.get("nid", "UNKNOWN")

                try:
                    record = parse_item(item)

                    publish_date = record["publish_date"]

                    # Naver API is returned newest first.
                    # Once an older date than the latest DB date appears,
                    # no additional pages need to be collected.
                    if (
                        latest_db_date
                        and publish_date
                        and publish_date < latest_db_date
                    ):
                        stop = True
                        break

                    saved = save_record(cur, record)

                    if saved and publish_date:
                        d = str(publish_date)

                        if d not in collected_dates:
                            collected_dates.append(d)

                        success_map[d] = success_map.get(d, 0) + 1

                except Exception as e:
                    fail_lines.append(
                        f"{nid} / Reason: {str(e)}"
                    )

            conn.commit()

            if stop:
                break

            if not has_next:
                break

            index += 1
            time.sleep(PAGE_SLEEP_SEC)

        cur.close()

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [
                f"Failed to Collect Agency Data / Reason: {str(e)}"
            ],
            "error_count": 0,
        }

        print_step_log("interest_agency", result)
        return result

    finally:
        if conn:
            conn.close()

    if not collected_dates:
        result = {
            "status": "NO_CHANGE",
            "collected_dates": None,
            "success_lines": [],
            "error_lines": [],
            "failed_lines": fail_lines,
            "error_count": len(fail_lines),
        }

        print_step_log("interest_agency", result)
        return result

    collected_dates = sorted(collected_dates)

    success_lines = [
        f"{d} {success_map[d]} Agency Reports Collected"
        for d in collected_dates
    ]

    result = {
        "status": "SUCCESS",
        "collected_dates": collected_dates,
        "success_lines": success_lines,
        "error_lines": [],
        "failed_lines": fail_lines,
        "error_count": len(fail_lines),
    }

    print_step_log("interest_agency", result)
    return result


if __name__ == "__main__":
    run()