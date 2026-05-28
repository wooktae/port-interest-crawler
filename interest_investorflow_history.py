"""Naver 금융의 종목별 투자자 수급 데이터를 과거 기간 기준으로 backfill하는 스크립트다.

종목별 전체 페이지를 순회해 투자자 수급 이력을 파싱하고 PostgreSQL에 저장한다.
대량 웹 요청과 DB 쓰기가 발생할 수 있으므로 실행 전 대상 universe와 제한을 확인한다.
"""

import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import re
import time
from datetime import datetime


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/"
}

SOURCE = "naver"
SOURCE_VERSION = "1.0.0"
START_YEAR = 2023


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_tickers():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT su.ticker_code, su.company_name
        FROM stock_universe su
        LEFT JOIN (
            SELECT ticker_code
            FROM interest_investor_flow_raw
            WHERE trade_date >= DATE '2023-01-01'
            GROUP BY ticker_code
        ) f
        ON su.ticker_code = f.ticker_code
        WHERE f.ticker_code IS NULL
        ORDER BY su.ticker_code
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def to_int(x):
    if not x:
        return None
    x = x.replace(",", "").replace("+", "").strip()
    try:
        return int(x)
    except:
        return None


def to_float(x):
    if not x:
        return None
    x = x.replace("%", "").replace(",", "").strip()
    try:
        return float(x)
    except:
        return None


def parse_row(cols):
    try:
        if not cols or len(cols) != 9:
            return None

        date_str = cols[0].strip()
        if not date_str or "." not in date_str:
            return None

        trade_date = datetime.strptime(date_str, "%Y.%m.%d").date()

        close_price = to_int(cols[1])

        diff_raw = cols[2]
        diff_num = to_int(re.sub(r"[^0-9]", "", diff_raw))
        if diff_num is None:
            return None

        if "하락" in diff_raw:
            price_diff = -diff_num
        else:
            price_diff = diff_num

        price_change_rate = to_float(cols[3])
        volume = to_int(cols[4])
        institution_net = to_int(cols[5])
        foreign_net = to_int(cols[6])
        foreign_hold_shares = to_int(cols[7])
        foreign_hold_ratio = to_float(cols[8])

        return {
            "trade_date": trade_date,
            "close_price": close_price,
            "price_diff": price_diff,
            "price_change_rate": price_change_rate,
            "volume": volume,
            "institution_net": institution_net,
            "foreign_net": foreign_net,
            "foreign_hold_shares": foreign_hold_shares,
            "foreign_hold_ratio": foreign_hold_ratio
        }
    except:
        return None


def request_html(session, url, retry=3):
    last_err = None

    for attempt in range(1, retry + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=(5, 10))
            resp.raise_for_status()
            return resp.content.decode("euc-kr", errors="ignore")
        except Exception as e:
            last_err = e
            time.sleep(1.0 * attempt)

    raise last_err


def get_last_page(session, ticker):
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page=1"

    try:
        html = request_html(session, url)
    except Exception as e:
        print(f"PAGE1 ERROR {ticker}: {e}")
        return 1

    soup = BeautifulSoup(html, "html.parser")

    pg_rr = soup.select_one("td.pgRR a")
    if pg_rr and pg_rr.get("href"):
        m = re.search(r"page=(\d+)", pg_rr["href"])
        if m:
            return int(m.group(1))

    # 마지막 페이지 링크가 없으면 1페이지뿐인 경우
    return 1


def fetch_page(session, ticker, page):
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"

    try:
        html = request_html(session, url)
    except Exception as e:
        print(f"REQUEST ERROR {ticker} page={page}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="type2")

    if len(tables) < 2:
        return []

    table = tables[1]
    rows = table.find_all("tr")
    data = []

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        record = parse_row(cols)

        if record is None:
            continue

        if record["trade_date"].year < START_YEAR:
            return None

        data.append(record)

    return data


def save_batch(cur, ticker, records):
    for r in records:
        cur.execute("""
            INSERT INTO interest_investor_flow_raw (
                ticker_code,
                trade_date,
                close_price,
                price_diff,
                price_change_rate,
                volume,
                institution_net,
                foreign_net,
                foreign_hold_shares,
                foreign_hold_ratio,
                source,
                source_version,
                collected_at
            )
            VALUES (
                %(ticker)s,
                %(trade_date)s,
                %(close_price)s,
                %(price_diff)s,
                %(price_change_rate)s,
                %(volume)s,
                %(institution_net)s,
                %(foreign_net)s,
                %(foreign_hold_shares)s,
                %(foreign_hold_ratio)s,
                %(source)s,
                %(source_version)s,
                now()
            )
            ON CONFLICT (ticker_code, trade_date)
            DO UPDATE SET
                close_price = EXCLUDED.close_price,
                price_diff = EXCLUDED.price_diff,
                price_change_rate = EXCLUDED.price_change_rate,
                volume = EXCLUDED.volume,
                institution_net = EXCLUDED.institution_net,
                foreign_net = EXCLUDED.foreign_net,
                foreign_hold_shares = EXCLUDED.foreign_hold_shares,
                foreign_hold_ratio = EXCLUDED.foreign_hold_ratio,
                updated_at = now();
        """, {
            "ticker": ticker,
            "source": SOURCE,
            "source_version": SOURCE_VERSION,
            **r
        })


def crawl_ticker(ticker, company):
    print(f"START {ticker} / {company}")
    start = time.time()

    conn = get_conn()
    cur = conn.cursor()
    session = requests.Session()

    total = 0

    try:
        last_page = get_last_page(session, ticker)
        print(f"PAGE_MAX {ticker} / {company} / {last_page}")

        for page in range(1, last_page + 1):
            print(f"FETCH {ticker} / {company} / page={page}/{last_page}")

            rows = fetch_page(session, ticker, page)

            if rows is None:
                break

            if not rows:
                continue

            save_batch(cur, ticker, rows)
            total += len(rows)

            # 네이버 서버 부하/차단 방지
            time.sleep(0.15)

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"ERROR {ticker} / {company}: {e}")

    finally:
        cur.close()
        conn.close()
        session.close()

    elapsed = round(time.time() - start, 2)
    print(f"{ticker} / {company} / rows={total} / time={elapsed}s")


def run():
    print("===== INVESTOR FLOW CRAWLER =====")
    tickers = get_tickers()
    print("TOTAL TICKERS:", len(tickers))

    for ticker, company in tickers:
        crawl_ticker(ticker, company)

    print("FINISHED")


if __name__ == "__main__":
    run()
