import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import re
import json
import time
from datetime import datetime, timezone

DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

LIST_URL = "https://finance.naver.com/research/company_list.naver?page={}"
DETAIL_URL = "https://finance.naver.com/research/company_read.naver?nid={}"

SOURCE = "naver"
SOURCE_VERSION = "2.0.0"

PAGE_SLEEP_SEC = 0.10
DETAIL_SLEEP_SEC = 0.02
COMMIT_EVERY_PAGE = True


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def map_score(rec: str | None):
    if not rec:
        return None

    r = rec.strip().lower()

    if "strong" in r or "강력매수" in r or "강매수" in r:
        return 5
    if "buy" in r or "매수" in r:
        return 4
    if "hold" in r or "중립" in r or "보유" in r:
        return 3
    if "sell" in r or "매도" in r:
        return 2

    return None


def safe_int(text: str | None):
    if not text:
        return None

    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None

    try:
        return int(digits)
    except Exception:
        return None


def format_seconds(sec: float):
    if sec is None or sec < 0:
        return "N/A"

    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def load_universe_cache(conn):
    """
    stock_universe 기준으로만 종목 매핑
    company_name -> ticker_code
    """
    cur = conn.cursor()

    # stock_universe에 company_name 컬럼이 있다고 가정
    cur.execute("""
        SELECT ticker_code, company_name
        FROM stock_universe
        WHERE ticker_code IS NOT NULL
          AND company_name IS NOT NULL
    """)

    rows = cur.fetchall()
    cur.close()

    cache = {}
    dup_count = 0

    for ticker_code, company_name in rows:
        name = company_name.strip()
        if name in cache and cache[name] != ticker_code:
            dup_count += 1
        cache[name] = ticker_code

    print(f"[INIT] STOCK_UNIVERSE CACHE LOADED: {len(cache)} companies")
    if dup_count > 0:
        print(f"[WARN] duplicate company_name mapping count: {dup_count}")

    return cache


def get_total_page_estimate(session: requests.Session):
    """
    첫 페이지의 pageN 영역에서 마지막 페이지 숫자 추정
    없으면 None
    """
    try:
        resp = session.get(LIST_URL.format(1), headers=HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        page_links = soup.select("td.pgRR a, td.pgR a, table.Nnavi a")

        nums = []
        for a in page_links:
            href = a.get("href", "")
            m = re.search(r"page=(\d+)", href)
            if m:
                nums.append(int(m.group(1)))

        return max(nums) if nums else None
    except Exception:
        return None


def get_nids_from_page(session: requests.Session, page: int):
    url = LIST_URL.format(page)

    resp = session.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    links = soup.select("div.box_type_m a[href*='company_read.naver?nid=']")

    nids = []
    for a in links:
        href = a.get("href", "")
        m = re.search(r"nid=(\d+)", href)
        if m:
            nids.append(m.group(1))

    # 중복 제거 + 순서 유지
    nids = list(dict.fromkeys(nids))
    return nids


def parse_detail(session: requests.Session, nid: str, ticker_cache: dict):
    url = DETAIL_URL.format(nid)

    resp = session.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    company_tag = soup.select_one("th.view_sbj span em")
    company_name = company_tag.text.strip() if company_tag else None
    ticker_code = ticker_cache.get(company_name) if company_name else None

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
            except Exception:
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

        cleaned = title_tag.get_text(" ", strip=True)
        title = cleaned if cleaned else None

    target_tag = soup.select_one("em.money strong")
    target_price = safe_int(target_tag.get_text(strip=True) if target_tag else None)

    rec_tag = soup.select_one("em.coment")
    recommendation = rec_tag.get_text(strip=True) if rec_tag else None
    score = map_score(recommendation)

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
        "score": score,
        "target_price": target_price,
        "publish_date": publish_date,
        "as_of_date": publish_date,
        "as_of_ts": now_utc,
        "raw_json": json.dumps(
            {
                "nid": nid,
                "company_name": company_name,
                "agency_name": agency_name,
                "title": title,
                "recommendation": recommendation,
                "target_price": target_price,
                "publish_date": str(publish_date) if publish_date else None
            },
            ensure_ascii=False
        ),
        "source": SOURCE,
        "source_version": SOURCE_VERSION
    }


def save_record(cur, record):
    """
    stock_universe에 있는 종목만 저장
    """
    if not record["ticker_code"]:
        return False

    cur.execute("""
        INSERT INTO interest_agency_raw (
            ticker_code,
            company_name,
            agency_name,
            title,
            content,
            recommendation,
            score,
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
            %(score)s,
            %(target_price)s,
            %(publish_date)s,
            %(raw_json)s,
            now(),
            %(source)s,
            %(source_version)s,
            %(as_of_date)s,
            %(as_of_ts)s
        )
        ON CONFLICT (ticker_code, agency_name, publish_date, title)
        DO UPDATE SET
            company_name    = EXCLUDED.company_name,
            content         = EXCLUDED.content,
            recommendation  = EXCLUDED.recommendation,
            score           = EXCLUDED.score,
            target_price    = EXCLUDED.target_price,
            raw_json        = EXCLUDED.raw_json,
            source          = EXCLUDED.source,
            source_version  = EXCLUDED.source_version,
            as_of_date      = EXCLUDED.as_of_date,
            as_of_ts        = EXCLUDED.as_of_ts,
            updated_at      = now();
    """, record)

    return True


def run():
    print("===== NAVER RESEARCH FULL CRAWLER (STOCK_UNIVERSE ONLY) =====")

    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor()

    session = requests.Session()
    session.headers.update(HEADERS)

    ticker_cache = load_universe_cache(conn)
    estimated_total_pages = get_total_page_estimate(session)

    if estimated_total_pages:
        print(f"[INIT] estimated total pages: {estimated_total_pages}")
    else:
        print("[INIT] estimated total pages: unknown")

    start_time = time.time()

    page = 1
    total_seen = 0
    total_saved = 0
    total_skipped_no_ticker = 0
    total_errors = 0

    while True:
        try:
            nids = get_nids_from_page(session, page)
        except Exception as e:
            total_errors += 1
            print(f"[ERROR] page={page} list fetch failed: {e}")
            break

        if not nids:
            print(f"[END] no more nids at page={page}")
            break

        page_seen = 0
        page_saved = 0
        page_skipped = 0
        page_errors = 0

        for idx, nid in enumerate(nids, start=1):
            try:
                record = parse_detail(session, nid, ticker_cache)
                total_seen += 1
                page_seen += 1

                if record["ticker_code"] is None:
                    total_skipped_no_ticker += 1
                    page_skipped += 1
                else:
                    saved = save_record(cur, record)
                    if saved:
                        total_saved += 1
                        page_saved += 1

                elapsed = time.time() - start_time
                speed = total_seen / elapsed if elapsed > 0 else 0

                eta_text = "N/A"
                progress_text = "N/A"

                if estimated_total_pages and page > 0:
                    avg_items_per_page = total_seen / page
                    estimated_total_items = int(estimated_total_pages * avg_items_per_page)
                    remaining_items = max(estimated_total_items - total_seen, 0)
                    eta_sec = remaining_items / speed if speed > 0 else None
                    eta_text = format_seconds(eta_sec)
                    progress_text = f"{total_seen}/{estimated_total_items}"
                else:
                    progress_text = str(total_seen)

                print(
                    f"[PAGE {page:04d}] "
                    f"{idx:02d}/{len(nids):02d} | "
                    f"TOTAL={progress_text} | "
                    f"SAVED={total_saved} | "
                    f"SKIP={total_skipped_no_ticker} | "
                    f"ERR={total_errors} | "
                    f"SPEED={speed:.2f}/s | "
                    f"ETA={eta_text} | "
                    f"{record['company_name']} / {record['ticker_code']}"
                )

                if DETAIL_SLEEP_SEC > 0:
                    time.sleep(DETAIL_SLEEP_SEC)

            except Exception as e:
                total_errors += 1
                page_errors += 1
                print(f"[ERROR] page={page}, nid={nid}, err={e}")
                continue

        if COMMIT_EVERY_PAGE:
            conn.commit()

        elapsed = time.time() - start_time
        speed = total_seen / elapsed if elapsed > 0 else 0

        if estimated_total_pages:
            avg_items_per_page = total_seen / page
            estimated_total_items = int(estimated_total_pages * avg_items_per_page)
            remaining_items = max(estimated_total_items - total_seen, 0)
            eta_sec = remaining_items / speed if speed > 0 else None
            eta_text = format_seconds(eta_sec)
        else:
            eta_text = "N/A"

        print(
            f"[PAGE SUMMARY] "
            f"page={page} | page_seen={page_seen} | page_saved={page_saved} | "
            f"page_skip={page_skipped} | page_err={page_errors} | "
            f"total_seen={total_seen} | total_saved={total_saved} | "
            f"total_skip={total_skipped_no_ticker} | total_err={total_errors} | "
            f"elapsed={format_seconds(elapsed)} | eta={eta_text}"
        )

        page += 1

        if PAGE_SLEEP_SEC > 0:
            time.sleep(PAGE_SLEEP_SEC)

    conn.commit()
    cur.close()
    conn.close()
    session.close()

    total_elapsed = time.time() - start_time

    print("===== CRAWL COMPLETE =====")
    print(f"TOTAL SEEN     : {total_seen}")
    print(f"TOTAL SAVED    : {total_saved}")
    print(f"TOTAL SKIPPED  : {total_skipped_no_ticker}")
    print(f"TOTAL ERRORS   : {total_errors}")
    print(f"TOTAL ELAPSED  : {format_seconds(total_elapsed)}")


if __name__ == "__main__":
    run()