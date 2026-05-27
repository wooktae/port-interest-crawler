import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import re
import json
import time
from datetime import datetime, timezone

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

LIST_URL = "https://finance.naver.com/research/company_list.naver?page={}"
DETAIL_URL = "https://finance.naver.com/research/company_read.naver?nid={}"

SOURCE = "naver"
SOURCE_VERSION = "2.1.0"

PAGE_SLEEP_SEC = 0.10
DETAIL_SLEEP_SEC = 0.02


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


def safe_int(text):
    if not text:
        return None

    digits = re.sub(r"[^0-9]", "", text)

    if not digits:
        return None

    try:
        return int(digits)
    except:
        return None


def load_universe_cache(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code, company_name
        FROM stock_universe
        WHERE ticker_code IS NOT NULL
        AND company_name IS NOT NULL
    """)

    rows = cur.fetchall()
    cur.close()

    return {company_name.strip(): ticker_code for ticker_code, company_name in rows}


def get_nids_from_page(session, page):
    url = LIST_URL.format(page)
    resp = session.get(url, headers=HEADERS)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    links = soup.select("div.box_type_m a[href*='company_read.naver?nid=']")

    nids = []
    for a in links:
        href = a.get("href")
        m = re.search(r"nid=(\d+)", href)
        if m:
            nids.append(m.group(1))

    return list(dict.fromkeys(nids))


def parse_detail(session, nid, ticker_cache):
    url = DETAIL_URL.format(nid)

    resp = session.get(url, headers=HEADERS)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    company_tag = soup.select_one("th.view_sbj span em")
    company_name = company_tag.text.strip() if company_tag else None

    ticker_code = ticker_cache.get(company_name)

    agency_name = None
    publish_date = None

    source_tag = soup.select_one("p.source")
    if source_tag:
        text = source_tag.get_text(" ", strip=True)
        parts = [p.strip() for p in text.split("|")]

        if len(parts) >= 2:
            agency_name = parts[0]
            try:
                publish_date = datetime.strptime(parts[1], "%Y.%m.%d").date()
            except:
                publish_date = None

    title = None
    title_tag = soup.select_one("th.view_sbj")

    if title_tag:
        title_tag = BeautifulSoup(str(title_tag), "html.parser")
        remove_tag = title_tag.select_one("p.source")
        if remove_tag:
            remove_tag.extract()

        span_tag = title_tag.select_one("span")
        if span_tag:
            span_tag.extract()

        title = title_tag.get_text(" ", strip=True)

    target_tag = soup.select_one("em.money strong")
    target_price = safe_int(target_tag.get_text(strip=True) if target_tag else None)

    rec_tag = soup.select_one("em.coment")
    recommendation = rec_tag.get_text(strip=True) if rec_tag else None

    content_div = soup.select_one("td.view_cnt")
    content = content_div.get_text(" ", strip=True) if content_div else None

    now_utc = datetime.now(timezone.utc)

    return {
        "ticker_code": ticker_code,
        "company_name": company_name,
        "agency_name": agency_name,
        "title": title,
        "content": content,
        "recommendation": recommendation,
        "target_price": target_price,
        "publish_date": publish_date,
        "raw_json": json.dumps({
            "nid": nid,
            "title": title,
            "agency_name": agency_name,
            "company_name": company_name,
            "publish_date": str(publish_date) if publish_date else None,
            "target_price": target_price,
            "recommendation": recommendation
        }, ensure_ascii=False),
        "source": SOURCE,
        "source_version": SOURCE_VERSION,
        "as_of_date": publish_date,
        "as_of_ts": now_utc
    }


def save_record(cur, record):
    if not record["ticker_code"]:
        return False

    cur.execute("""
        INSERT INTO interest_agency_raw (
            ticker_code, company_name, agency_name, title, content,
            recommendation, target_price, publish_date,
            raw_json, collected_at, source, source_version,
            as_of_date, as_of_ts
        )
        VALUES (
            %(ticker_code)s, %(company_name)s, %(agency_name)s, %(title)s, %(content)s,
            %(recommendation)s, %(target_price)s, %(publish_date)s,
            %(raw_json)s, now(), %(source)s, %(source_version)s,
            %(as_of_date)s, %(as_of_ts)s
        )
        ON CONFLICT (ticker_code, agency_name, publish_date, title)
        DO UPDATE SET
            content = EXCLUDED.content,
            recommendation = EXCLUDED.recommendation,
            target_price = EXCLUDED.target_price,
            raw_json = EXCLUDED.raw_json,
            updated_at = now();
    """, record)   # 🔥 이거 반드시 있어야 함

    return True


def run():

    conn = get_conn()
    cur = conn.cursor()

    latest_db_date = get_db_latest_publish_date(conn)

    session = requests.Session()
    session.headers.update(HEADERS)

    ticker_cache = load_universe_cache(conn)

    collected_dates = []
    success_map = {}
    fail_lines = []

    page = 1
    stop = False   # 🔥 추가

    try:
        while True:
            nids = get_nids_from_page(session, page)

            if not nids:
                break

            for nid in nids:
                try:
                    record = parse_detail(session, nid, ticker_cache)

                    if latest_db_date and record["publish_date"]:
                        if record["publish_date"] < latest_db_date:
                            stop = True   # 🔥 핵심
                            break         # 🔥 for 탈출

                    saved = save_record(cur, record)

                    if saved and record["publish_date"]:
                        d = str(record["publish_date"])

                        if d not in collected_dates:
                            collected_dates.append(d)

                        success_map[d] = success_map.get(d, 0) + 1

                    time.sleep(DETAIL_SLEEP_SEC)

                except Exception as e:
                    fail_lines.append(f"{nid} / Reason: {str(e)}")

            conn.commit()

            if stop:
                break   # 🔥 while 탈출

            page += 1
            time.sleep(PAGE_SLEEP_SEC)

    except Exception as e:
        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [f"Failed to Collect Agency Data / Reason: {str(e)}"],
            "error_count": 0
        }

        print_step_log("interest_agency", result)
        return result

    conn.close()

    if not collected_dates:
        result = {
            "status": "NO_CHANGE",
            "collected_dates": None,
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
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
        "failed_lines": [],
        "error_count": len(fail_lines)
    }

    print_step_log("interest_agency", result)
    return result


if __name__ == "__main__":
    run()