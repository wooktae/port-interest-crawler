import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import json
import re
import time

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://news.naver.com/main/list.naver"

SOURCE_NAME = "naver_stock_news"
SOURCE_VERSION = "3.0.0"

MAX_WORKERS = 8


# ----------------------------
# DB 연결
# ----------------------------
def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ----------------------------
# 최근 N일 날짜 생성
# ----------------------------
def get_dates(days=30):

    today = datetime.today()

    for i in range(days):
        d = today - timedelta(days=i)
        yield d.strftime("%Y%m%d")


# ----------------------------
# 뉴스 링크 수집
# ----------------------------
def collect_links_for_date(date):

    links = []

    page = 1

    while True:

        params = {
            "mode": "LS2D",
            "mid": "sec",
            "sid1": "101",
            "sid2": "258",
            "listType": "title",
            "date": date,
            "page": page
        }

        resp = requests.get(BASE_URL, headers=HEADERS, params=params)

        soup = BeautifulSoup(resp.text, "html.parser")

        page_links = []

        for a in soup.select("a[href*='/article/']"):

            href = a.get("href")

            if href and "/article/" in href:
                page_links.append(href)

        page_links = list(set(page_links))

        # 새로운 링크만 필터
        new_links = [l for l in page_links if l not in links]

        if not new_links:

            print(f"{date} last page = {page}")
            break

        links.extend(new_links)

        print(f"{date} page {page} new_links {len(new_links)}")

        page += 1

        time.sleep(0.1)

    return links


# ----------------------------
# 모바일 기사 URL 변환
# ----------------------------
def to_mobile_url(url):

    m = re.search(r"/article/(\d+)/(\d+)", url)

    if m:

        office = m.group(1)
        article = m.group(2)

        return f"https://n.news.naver.com/mnews/article/{office}/{article}"

    return None


# ----------------------------
# 기사 파싱
# ----------------------------
def parse_article(url):

    resp = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(resp.text, "html.parser")

    news_id = url.split("/")[-1]

    title_tag = soup.select_one("#title_area span")
    if not title_tag:
        title_tag = soup.select_one("#title_area")

    content_tag = soup.select_one("#dic_area")

    if not content_tag:
        content_tag = soup.select_one("#newsct_article")

    source_tag = soup.select_one("a.media_end_head_top_logo img")

    source = None

    if source_tag:
        source = source_tag.get("alt")

    date_tag = soup.select_one("span.media_end_head_info_datestamp_time")

    published_at = None

    if date_tag and date_tag.get("data-date-time"):

        published_at = datetime.strptime(
            date_tag.get("data-date-time"),
            "%Y-%m-%d %H:%M:%S"
        )

    as_of_ts = published_at if published_at else datetime.now()

    title = title_tag.get_text(strip=True) if title_tag else None

    content = content_tag.get_text(" ", strip=True) if content_tag else None

    return {

        "news_id": news_id,
        "source": source,
        "title": title,
        "content": content,
        "published_at": published_at,
        "url": url,

        "raw_json": json.dumps({
            "url": url,
            "title": title,
            "source": source
        }, ensure_ascii=False),

        "collected_at": datetime.now(),

        "as_of_date": as_of_ts.date(),
        "as_of_ts": as_of_ts,

        "source_version": SOURCE_VERSION
    }


# ----------------------------
# DB 저장
# ----------------------------
def save_to_db(record):

    conn = get_conn()

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

            title = EXCLUDED.title,
            content = EXCLUDED.content,
            published_at = EXCLUDED.published_at,
            raw_json = EXCLUDED.raw_json,
            updated_at = now();

    """, record)

    conn.commit()

    cur.close()

    conn.close()


# ----------------------------
# 기사 처리
# ----------------------------
def process_article(link):

    try:

        mobile = to_mobile_url(link)

        if not mobile:
            return

        record = parse_article(mobile)

        save_to_db(record)

        print("Saved:", record["news_id"], record["title"])

    except Exception as e:

        print("Error:", e)


# ----------------------------
# 실행
# ----------------------------
def run():

    print("===== NAVER STOCK NEWS CRAWLER =====")

    all_links = []

    for date in get_dates(30):

        links = collect_links_for_date(date)

        all_links.extend(links)

    all_links = list(set(all_links))

    print("TOTAL LINKS:", len(all_links))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = []

        for link in all_links:

            futures.append(executor.submit(process_article, link))

        for f in as_completed(futures):
            pass

    print("DONE")


if __name__ == "__main__":
    run()