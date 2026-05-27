import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import json
import re
import time

from datetime import datetime, timedelta

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://news.naver.com/main/list.naver"

SOURCE_VERSION = "5.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_db_latest_date(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(as_of_date)
        FROM interest_news_raw
    """)

    row = cur.fetchone()
    cur.close()

    return row[0]


def get_dates_range(start_date, end_date):
    current = start_date

    while current <= end_date:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def collect_news_for_date(date):

    results = []
    page = 1

    while True:

        #print(f"{date} page={page} collecting...")

        params = {
            "mode": "LS2D",
            "mid": "sec",
            "sid1": "101",
            "sid2": "258",
            "listType": "title",
            "date": date,
            "page": page
        }

        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("ul.type02 li")

        if not items:
            break

        for li in items:
            a = li.select_one("a[href*='/article/']")
            if not a:
                continue

            url = a.get("href")
            title = a.get_text(strip=True)

            # 🔥 source
            source_tag = li.select_one("span.writing")
            source = source_tag.get_text(strip=True) if source_tag else None

            # 🔥 news_id 추출
            m = re.search(r"/article/(\d+)/(\d+)", url)
            if not m:
                continue

            office = m.group(1)
            article = m.group(2)

            mobile_url = f"https://n.news.naver.com/mnews/article/{office}/{article}"
            news_id = article

            # 🔥 published_at (완성형)
            date_tag = li.select_one("span.date")
            published_at = None

            if date_tag:
                raw_date = date_tag.get_text(strip=True)

                if raw_date:
                    try:
                        # 분전
                        if "분전" in raw_date:
                            minutes = int(re.search(r"(\d+)분전", raw_date).group(1))
                            published_at = datetime.now() - timedelta(minutes=minutes)

                        # 시간전
                        elif "시간전" in raw_date:
                            hours = int(re.search(r"(\d+)시간전", raw_date).group(1))
                            published_at = datetime.now() - timedelta(hours=hours)

                        # 🔥 일전 추가
                        elif "일전" in raw_date:
                            days = int(re.search(r"(\d+)일전", raw_date).group(1))
                            published_at = datetime.now() - timedelta(days=days)

                        # 절대시간
                        else:
                            raw_date = raw_date.replace("오전", "AM").replace("오후", "PM")
                            published_at = datetime.strptime(raw_date, "%Y.%m.%d. %p %I:%M")

                    except:
                        published_at = None

            # fallback (선택)
            if not published_at:
                pass

            as_of_ts = published_at if published_at else datetime.now()

            results.append({
                "news_id": news_id,
                "source": source,
                "title": title,
                "content": None,
                "published_at": published_at,
                "url": mobile_url,
                "raw_json": json.dumps({
                    "url": mobile_url,
                    "title": title,
                    "source": source,
                    "published_at": str(published_at)
                }, ensure_ascii=False),
                "collected_at": datetime.now(),
                "as_of_date": as_of_ts.date(),
                "as_of_ts": as_of_ts,
                "source_version": SOURCE_VERSION
            })

        # 🔥 다음 페이지 존재 여부로 종료
        next_page = soup.select_one(f"div.paging a[href*='page={page+1}']")
        if not next_page:
            break

        page += 1

    return results


def parse_article(url):
    resp = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")

    news_id = url.split("/")[-1]

    title_tag = soup.select_one("#title_area span")
    if not title_tag:
        title_tag = soup.select_one("#title_area")

    source_tag = soup.select_one("a.media_end_head_top_logo img")
    source = source_tag.get("alt") if source_tag else None

    date_tag = soup.select_one("span.media_end_head_info_datestamp_time")

    published_at = None
    if date_tag and date_tag.get("data-date-time"):
        published_at = datetime.strptime(
            date_tag.get("data-date-time"),
            "%Y-%m-%d %H:%M:%S"
        )

    title = title_tag.get_text(strip=True) if title_tag else None

    if not title or not title.strip():
        return None

    as_of_ts = published_at if published_at else datetime.now()

    return {
        "news_id": news_id,
        "source": source,
        "title": title.strip(),
        "content": None,   # 제목만 저장
        "published_at": published_at,
        "url": url,
        "raw_json": json.dumps({
            "url": url,
            "title": title.strip(),
            "source": source
        }, ensure_ascii=False),
        "collected_at": datetime.now(),
        "as_of_date": as_of_ts.date(),
        "as_of_ts": as_of_ts,
        "source_version": SOURCE_VERSION
    }


def save_to_db(conn, record):

    if not record:
        return False

    title = record.get("title")
    if title is None or not str(title).strip():
        return False

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO interest_news_raw (
            news_id,
            source,
            title,
            content,
            published_at,
            url,
            raw_json,
            collected_at,
            as_of_date,
            as_of_ts,
            source_version
        )
        VALUES (
            %(news_id)s,
            %(source)s,
            %(title)s,
            %(content)s,
            %(published_at)s,
            %(url)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_date)s,
            %(as_of_ts)s,
            %(source_version)s
        )
        ON CONFLICT (news_id)
        DO UPDATE SET
            source = EXCLUDED.source,
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            published_at = EXCLUDED.published_at,
            url = EXCLUDED.url,
            raw_json = EXCLUDED.raw_json,
            collected_at = EXCLUDED.collected_at,
            as_of_date = EXCLUDED.as_of_date,
            as_of_ts = EXCLUDED.as_of_ts,
            source_version = EXCLUDED.source_version,
            updated_at = now()
    """, record)

    cur.close()
    return True


def run():

    start_all = time.time()   # 🔥 추가

    conn = get_conn()

    latest_date = get_db_latest_date(conn)

    if latest_date:
        start_date = latest_date + timedelta(days=1)
    else:
        start_date = datetime.strptime("2007-01-01", "%Y-%m-%d").date()

    #start_date = datetime.strptime("2026-03-19", "%Y-%m-%d").date()
    end_date = datetime.now().date()

    collected_dates = []
    success_lines = []
    fail_lines = []

    for date in get_dates_range(start_date, end_date):

        start_day = time.time()   # 🔥 추가

        # 🔥 변경: 링크 → records
        records = collect_news_for_date(date)

        saved = 0

        for record in records:
            try:
                if not record:
                    continue

                inserted = save_to_db(conn, record)
                if inserted:
                    saved += 1

            except Exception as e:
                fail_lines.append(f"{date} / Reason: {str(e)}")

        conn.commit()

        if saved > 0:
            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            collected_dates.append(formatted_date)

            success_lines.append(
                f"{formatted_date} {saved} News Collected"
            )

            elapsed_day = time.time() - start_day   # 🔥 추가
            #print(f"[DONE] {formatted_date} | rows={saved} | {elapsed_day:.2f}s")   # 🔥 추가

    conn.close()

    elapsed_all = time.time() - start_all   # 🔥 추가
    #print(f"===== TOTAL DONE ({elapsed_all:.2f}s) =====")   # 🔥 추가

    # -----------------------------
    # 결과 생성
    # -----------------------------
    if not collected_dates:
        result = {
            "status": "NO_CHANGE",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log("interest_news", result)
        return result

    error_lines = []
    if fail_lines:
        error_lines = [
            f"{collected_dates[-1]} {len(fail_lines)} News Not Collected"
        ] + [
            f" {i+1}) {line}"
            for i, line in enumerate(fail_lines)
        ]

    result = {
        "status": "SUCCESS",
        "collected_dates": collected_dates,
        "success_lines": success_lines,
        "error_lines": error_lines,
        "failed_lines": [],
        "error_count": len(fail_lines)
    }

    print_step_log("interest_news", result)

    return result


if __name__ == "__main__":
    run()