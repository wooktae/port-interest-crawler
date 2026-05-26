import time
import requests
from urllib.parse import quote
from datetime import datetime
import psycopg2
import psycopg2.extras

# === 네이버 API 설정 ===
NAVER_CLIENT_ID     = "t7GCfTofVAFbJEbNDpEC"
NAVER_CLIENT_SECRET = "n2tZSJIu0z"
BASE_SEARCH_URL     = "https://openapi.naver.com/v1/search/news.json"

# === DB 설정 ===
DB_CONFIG = {
    "host":"localhost",
    "port":5433,
    "dbname":"interest_crawler",
    "user":"postgres",
    "password":"doflwhsk3768!"
}

# === DB 헬퍼 ===
def get_db_connection():
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )

def fetch_tickers():
    sql = "SELECT id, name FROM ticker;"
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

def save_news_record(record):
    sql = """
    INSERT INTO news_raw
       (ticker_id, source, news_title, news_body, published_at, raw_html)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                record["ticker_id"],
                record["source"],
                record["title"],
                record["body"],
                record["published_at"],
                record["html"]
            ))
            conn.commit()

# === 네이버 검색 API 호출 ===
def fetch_naver_news(query, display=5, start=1, sort="date"):
    # 1) query URL 인코딩
    encoded_q = quote(query, safe="")

    # 2) 요청 URL
    url = f"{BASE_SEARCH_URL}?query={encoded_q}&display={display}&start={start}&sort={sort}"

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }

    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"[ERROR] API 요청 실패({resp.status_code}): {resp.text}")
        return []

    data = resp.json()
    return data.get("items", [])

# === 메인 ===
def main():
    print("[START] 뉴스 수집 시작 (네이버 API)")

    tickers = fetch_tickers()
    if not tickers:
        print("ticker 테이블 없음 또는 불러오기 실패")
        return

    for t in tickers:
        ticker_id   = t["id"]
        ticker_name = t["name"]

        # 검색어: 종목명 + " 증시"
        keyword = f"{ticker_name} 증시"
        print(f"[SEARCH] {keyword}")

        # 1) 1페이지 display=5
        items = fetch_naver_news(keyword, display=5, start=1, sort="date")
        if not items:
            print(f"  → 결과 없음: {keyword}")
            continue

        # 2) 수집된 뉴스 저장
        for item in items:
            pub_date = None
            try:
                pub_date = datetime.strptime(
                    item.get("pubDate",""), "%a, %d %b %Y %H:%M:%S +0900"
                )
            except:
                pub_date = None

            news_rec = {
                "ticker_id": ticker_id,
                "source": "naver_api",
                "title": item.get("title",""),
                "body": item.get("description",""),
                "published_at": pub_date,
                "html": ""
            }
            save_news_record(news_rec)
            print(f"  [SAVED] {news_rec['title']}")

            # API rate 부담 줄이기
            time.sleep(0.2)

    print("[DONE] 뉴스 수집 완료!")

if __name__ == "__main__":
    main()
