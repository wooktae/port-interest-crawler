from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
import datetime

START_DATE = "20230101"
END_DATE = "20260314"

URL_SHORTSELL = "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT30501"

REQUEST_SLEEP_SEC = 1


def start_driver():

    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)

    return driver


def get_dates():

    start = datetime.datetime.strptime(START_DATE, "%Y%m%d")
    end = datetime.datetime.strptime(END_DATE, "%Y%m%d")

    days = []

    cur = start

    while cur <= end:

        if cur.weekday() < 5:
            days.append(cur.strftime("%Y%m%d"))

        cur += datetime.timedelta(days=1)

    return days


def crawl_day(driver, date):

    wait = WebDriverWait(driver, 10)

    driver.get(URL_SHORTSELL)

    # 날짜 입력
    date_input = wait.until(
        EC.presence_of_element_located((By.ID, "trdDd"))
    )

    date_input.clear()
    date_input.send_keys(date)

    # 조회 버튼
    search_btn = driver.find_element(By.ID, "btnSearch")
    search_btn.click()

    time.sleep(2)

    # CSV 다운로드
    csv_btn = driver.find_element(By.ID, "btnDownloadCsv")
    csv_btn.click()

    time.sleep(1)


def run():

    print("===== KRX SHORTSELL CRAWLER START =====")
    print(f"range: {START_DATE} ~ {END_DATE}")

    driver = start_driver()

    driver.get("https://data.krx.co.kr")

    input("KRX 로그인 후 ENTER 누르세요")

    dates = get_dates()

    total = len(dates)

    start_time = time.time()

    for i, d in enumerate(dates):

        crawl_day(driver, d)

        elapsed = time.time() - start_time
        progress = (i + 1) / total * 100

        avg = elapsed / (i + 1)
        remaining = avg * (total - i - 1)

        print(
            f"[{i+1}/{total}] {d} "
            f"progress={progress:5.1f}% "
            f"elapsed={int(elapsed)}s "
            f"remaining={int(remaining)}s"
        )

        time.sleep(REQUEST_SLEEP_SEC)

    driver.quit()

    print("===== FINISHED =====")


if __name__ == "__main__":
    run()