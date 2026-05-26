import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import psycopg2

# ===== 설정 =====
TARGET_TICKER = "005930"
SEARCH_URL = (
    "https://finance.naver.com/news/news_search.naver"
    f"?q={TARGET_TICKER}&sm=title.basic&pd=2"
)

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

# ===== DB 연결 =====
def get_db_connection():
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )

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

# ===== 검색 결과 파싱 =====
def crawl_finance_search(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("[ERROR] 검색 페이지 요청 실패")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # dt.articleSubject 요소 리스트
    dts = soup.select("dl.newsList dt.articleSubject")
    dds = soup.select("dl.newsList dd.articleSummary")

    # dt & dd 리스트를 순서대로 zip 처리
    for dt, dd in zip(dts, dds):
        a_tag = dt.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        href = a_tag["href"]

        # 상대주소이면 절대주소로 변환
        link = "https://finance.naver.com" + href if href.startswith("/") else href

        # 언론사
        press_tag = dd.select_one("span.press")
        press = press_tag.get_text(strip=True) if press_tag else None

        # 등록일
        wdate_tag = dd.select_one("span.wdate")
        wdate = wdate_tag.get_text(strip=True) if wdate_tag else None
        published_at = None
        if wdate:
            try:
                published_at = datetime.strptime(wdate, "%Y.%m.%d %H:%M")
            except:
                published_at = None

        results.append({
            "title": title,
            "link": link,
            "press": press,
            "published_at": published_at
        })

    return results

# ===== 본문 크롤링 =====
def crawl_article_body(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except:
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    body_tag = soup.select_one("#news_read") or soup.select_one("div.articleCont")
    return body_tag.get_text("\n", strip=True) if body_tag else ""

# ===== MAIN =====
def main():
    print(f"[START] 네이버 금융 검색 뉴스: {TARGET_TICKER}")

    news_list = crawl_finance_search(SEARCH_URL)
    if not news_list:
        print("뉴스 검색 결과 없음")
        return

    # ticker_id 조회
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ticker WHERE ticker_code = %s", (TARGET_TICKER,))
            row = cur.fetchone()
            ticker_id = row[0] if row else None

    for n in news_list:
        print(f"[CRAWL] {n['title']}")

        body_text = crawl_article_body(n["link"])
        rec = {
            "ticker_id": ticker_id,
            "source": "naver_finance",
            "title": n["title"],
            "body": body_text,
            "published_at": n["published_at"],
            "html": ""  # 필요하면 r.text 저장
        }
        save_news_record(rec)
        time.sleep(0.5)

    print("[DONE] 완료!")

if __name__ == "__main__":
    main()