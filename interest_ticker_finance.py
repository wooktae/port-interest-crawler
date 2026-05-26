from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import psycopg2
import re
import json
from datetime import date

# =========================================
# 설정
# =========================================

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

TICKER_CODE = "005380"

CHROMEDRIVER_PATH = r"C:\UTIL\chromedriver-win64\chromedriver-win64\chromedriver.exe"

SOURCE = "naver"
SOURCE_VERSION = "1.0.0"


# =========================================
# DB 연결
# =========================================

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# =========================================
# 숫자 정리
# =========================================

def parse_number(text):
    text = text.strip()

    if text == "-" or text == "":
        return None

    text = text.replace(",", "")

    try:
        return float(text)
    except:
        return None


# =========================================
# 분기 문자열 → 날짜 변환
# =========================================

def convert_period_to_date(period_str):
    # "2025.06." → 2025-06-30
    year = int(period_str[:4])
    month = int(period_str[5:7])

    if month == 3:
        return date(year, 3, 31)
    elif month == 6:
        return date(year, 6, 30)
    elif month == 9:
        return date(year, 9, 30)
    elif month == 12:
        return date(year, 12, 31)


# =========================================
# 메인 실행
# =========================================

def run():
    print("===== NAVER FINANCE → DB INSERT START (OPTIMIZED) =====")

    # 1️⃣ Selenium 실행
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://m.stock.naver.com/domestic/stock/{TICKER_CODE}/finance/quarter"
    driver.get(url)

    wait = WebDriverWait(driver, 10)
    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'매출액')]")
        )
    )

    html = driver.execute_script("return document.documentElement.outerHTML;")
    driver.quit()

    # 2️⃣ BeautifulSoup 파싱
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    if len(tables) < 2:
        print("❌ 데이터 테이블 없음")
        return

    target_table = tables[1]

    # 3️⃣ 날짜 추출
    table_text = target_table.get_text()
    periods = re.findall(r"\d{4}\.\d{2}\.", table_text)
    periods = list(dict.fromkeys(periods))

    print("📅 기간:", periods)

    rows = target_table.find_all("tr")

    result = {period: {} for period in periods}

    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue

        name_tag = row.find("div")
        if not name_tag:
            continue

        item_name = name_tag.get_text(strip=True)
        values = [td.get_text(strip=True) for td in cols]

        for idx, period in enumerate(periods):
            if idx < len(values):
                result[period][item_name] = parse_number(values[idx])

    # 4️⃣ DB 저장 (UPSERT + source/version + collected_at)
    conn = get_conn()
    cur = conn.cursor()

    for period_str, data in result.items():
        period_date = convert_period_to_date(period_str)

        cur.execute("""
            INSERT INTO interest_ticker_finance_raw (
                ticker_code,
                period,
                freq_type,
                revenue,
                operating_income,
                net_income,
                controlling_net_income,
                non_controlling_net_income,
                operating_margin,
                net_margin,
                roe,
                debt_ratio,
                quick_ratio,
                retention_ratio,
                eps,
                per,
                bps,
                pbr,
                dps,
                raw_json,
                source,
                source_version,
                collected_at
            )
            VALUES (
                %s,%s,'Q',
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,
                %s,%s,
                now()
            )
            ON CONFLICT (ticker_code, period, freq_type)
            DO UPDATE SET
                revenue = EXCLUDED.revenue,
                operating_income = EXCLUDED.operating_income,
                net_income = EXCLUDED.net_income,
                controlling_net_income = EXCLUDED.controlling_net_income,
                non_controlling_net_income = EXCLUDED.non_controlling_net_income,
                operating_margin = EXCLUDED.operating_margin,
                net_margin = EXCLUDED.net_margin,
                roe = EXCLUDED.roe,
                debt_ratio = EXCLUDED.debt_ratio,
                quick_ratio = EXCLUDED.quick_ratio,
                retention_ratio = EXCLUDED.retention_ratio,
                eps = EXCLUDED.eps,
                per = EXCLUDED.per,
                bps = EXCLUDED.bps,
                pbr = EXCLUDED.pbr,
                dps = EXCLUDED.dps,
                raw_json = EXCLUDED.raw_json,
                source = EXCLUDED.source,
                source_version = EXCLUDED.source_version,
                updated_at = now();
        """, (
            TICKER_CODE,
            period_date,
            data.get("매출액"),
            data.get("영업이익"),
            data.get("당기순이익"),
            data.get("지배주주순이익"),
            data.get("비지배주주순이익"),
            data.get("영업이익률"),
            data.get("순이익률"),
            data.get("ROE"),
            data.get("부채비율"),
            data.get("당좌비율"),
            data.get("유보율"),
            data.get("EPS"),
            data.get("PER"),
            data.get("BPS"),
            data.get("PBR"),
            data.get("주당배당금"),
            json.dumps(data, ensure_ascii=False),
            SOURCE,
            SOURCE_VERSION
        ))

    conn.commit()
    cur.close()
    conn.close()

    print("✅ interest_ticker_finance_raw 저장 완료")


if __name__ == "__main__":
    run()