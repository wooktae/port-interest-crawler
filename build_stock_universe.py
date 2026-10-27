"""Selenium script that collects per-market stock universe candidates from Naver Finance screens.

It requires Chrome/ChromeDriver and a PostgreSQL connection, and stores results in the DB after scroll-based web collection.
Because running it triggers external web requests and DB writes, run it intentionally only in the production environment.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import psycopg2
from db_config import get_db_config
import time
import re
from datetime import datetime

# ----------------------------
# DB settings
# ----------------------------
DB_CONFIG = get_db_config()

# ----------------------------
# URL
# ----------------------------
URL_KOSPI200 = "https://m.stock.naver.com/domestic/index/KPI200/enrollstocks"
URL_KOSDAQ = "https://m.stock.naver.com/domestic/index/KOSDAQ/enrollstocks"

CHROMEDRIVER_PATH = r"C:\UTIL\chromedriver-win64\chromedriver-win64\chromedriver.exe"

CODE_RE = re.compile(r"\b\d{6}\b")


# ----------------------------
# DB connection
# ----------------------------
def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ----------------------------
# Create driver
# ----------------------------
def create_driver():

    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,3000")
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(CHROMEDRIVER_PATH)

    return webdriver.Chrome(service=service, options=options)


# ----------------------------
# Scroll
# ----------------------------
def initial_scroll(driver):

    for _ in range(8):

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(1)


# ----------------------------
# Extract current stocks
# ----------------------------
def extract_stocks(driver):

    body = driver.find_element(By.TAG_NAME, "body").text

    lines = body.split("\n")

    stocks = []

    for i, line in enumerate(lines):

        code_match = CODE_RE.fullmatch(line.strip())

        if code_match:

            ticker = line.strip()

            name = None
            if i > 0:
                name = lines[i - 1].strip()

            stocks.append((ticker, name))

    return list(dict.fromkeys(stocks))


# ----------------------------
# Load more
# ----------------------------
def load_until(driver, target_count):

    while True:

        stocks = extract_stocks(driver)

        if len(stocks) >= target_count:
            break

        try:

            btn = driver.find_element(By.CSS_SELECTOR, "a.VMore_link__Tsoh9")

            driver.execute_script("arguments[0].click();", btn)

            time.sleep(1)

        except:
            break


# ----------------------------
# index crawler
# ----------------------------
def crawl_index(driver, url, target_count):

    driver.get(url)

    time.sleep(3)

    initial_scroll(driver)

    load_until(driver, target_count)

    stocks = extract_stocks(driver)

    return stocks[:target_count]


# ----------------------------
# Save to DB
# ----------------------------
def save_to_db(ticker, name, market, universe):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO stock_universe (
            ticker_code,
            company_name,
            market,
            universe,
            sector,
            created_at,
            updated_at
        )
        VALUES (%s,%s,%s,%s,NULL,NOW(),NOW())
        ON CONFLICT (ticker_code)
        DO UPDATE SET
            company_name = EXCLUDED.company_name,
            market = EXCLUDED.market,
            universe = EXCLUDED.universe,
            updated_at = NOW()
    """, (ticker, name, market, universe))

    conn.commit()

    cur.close()
    conn.close()


# ----------------------------
# Run
# ----------------------------
def run():

    print("===== BUILD STOCK UNIVERSE =====")

    driver = create_driver()

    # ----------------------------
    # KOSPI200
    # ----------------------------

    kospi = crawl_index(driver, URL_KOSPI200, 200)

    for ticker, name in kospi:

        save_to_db(
            ticker,
            name,
            "KOSPI",
            "KOSPI200"
        )

        print("Saved:", ticker, name)

    print("KOSPI200 DONE:", len(kospi))


    # ----------------------------
    # KOSDAQ150
    # ----------------------------

    kosdaq = crawl_index(driver, URL_KOSDAQ, 150)

    for ticker, name in kosdaq:

        save_to_db(
            ticker,
            name,
            "KOSDAQ",
            "KOSDAQ150"
        )

        print("Saved:", ticker, name)

    print("KOSDAQ150 DONE:", len(kosdaq))

    driver.quit()

    print("TOTAL:", len(kospi) + len(kosdaq))


# ----------------------------
# main
# ----------------------------
if __name__ == "__main__":
    run()
