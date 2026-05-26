import requests
from bs4 import BeautifulSoup
import psycopg
import time
import re

# === DB 연결 ===
conn = psycopg.connect(
    host="localhost",
    port=5433,
    dbname="interest_crawler",
    user="postgres",
    password="doflwhsk3768!"
)
cur = conn.cursor()

HEADERS = {"User-Agent":"Mozilla/5.0"}

# 리서치 리포트 리스트 페이지(종목/일반 보고서)
BASE_LIST_URL = "https://finance.naver.com/research/company_list.naver"

def crawl_naver_research(page=1):
    params = {"&page": page}
    resp = requests.get(BASE_LIST_URL, headers=HEADERS, params=params)
    soup = BeautifulSoup(resp.text, "html.parser")

    # box_type_m 아래 a 태그 제목/링크
    box = soup.find("div", class_="box_type_m")
    if not box:
        return []

    report_info_list = []
    linkList = box.find_all("a")
    dateList = soup.find_all("td", class_="date")

    # 날짜 반복 인덱스
    idx_date = 0
    i = -1
    for a in linkList:
        i += 1
        # class 속성이 있으면 제목 링크임
        if a.get("class"):
            # 제목 다음 <a> 태그가 실제 리포트 링크
            try:
                title = a.get_text(strip=True)
                link  = "https://finance.naver.com" + a["href"]
                date  = dateList[idx_date].get_text(strip=True)
            except:
                continue

            report_info_list.append({
                "title": title,
                "link": link,
                "date": date
            })
            idx_date += 1

    return report_info_list

# 🕸️ 여러 페이지 순회
for p in range(1, 3):  # 일단 2페이지만 예시
    reports = crawl_naver_research(p)
    print(f"[Page {p}] got {len(reports)} reports")

    for r in reports:
        title = r["title"]
        link  = r["link"]
        date  = r["date"]

        # 옵션: 종목 코드가 URL에 있으면 추출
        ticker_code = None
        m = re.search(r"code=(\d+)", link)
        if m:
            ticker_code = m.group(1)

        ticker_id = None
        if ticker_code:
            cur.execute("SELECT id FROM ticker WHERE ticker_code=%s", (ticker_code,))
            row = cur.fetchone()
            if row:
                ticker_id = row[0]
            else:
                # ticker 이름은 제목으로 우선 채워둠
                cur.execute(
                    "INSERT INTO ticker (ticker_code, name, market) VALUES (%s,%s,%s) RETURNING id",
                    (ticker_code, title, "KOSPI")
                )
                ticker_id = cur.fetchone()[0]

        # agency_recommendation 저장
        cur.execute("""
            INSERT INTO agency_recommendation
            (ticker_id, source, recommendation, report_title, summary_text)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            ticker_id,
            "NaverRes",                # 네이버 리서치 출처 표시
            None,                      # 투자의견 별도 없음
            title,
            link                       # 링크를 저장
        ))
        print(f"🔹 saved: {title}")

    conn.commit()
    time.sleep(1)  # 과도한 호출 방지

cur.close()
conn.close()
print("Done Naver Research crawler!")