import requests
from bs4 import BeautifulSoup
import psycopg2
from db_config import get_db_config
import re
import time
from datetime import datetime, timedelta

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/"
}

SOURCE = "naver"
SOURCE_VERSION = "2.1.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_tickers():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            su.ticker_code,
            su.company_name,
            MAX(f.trade_date) AS last_date
        FROM stock_universe su
        LEFT JOIN interest_investorflow_raw f
        ON su.ticker_code = f.ticker_code
        GROUP BY su.ticker_code, su.company_name
        ORDER BY su.ticker_code
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

def generate_dates(conn):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(trade_date)
        FROM interest_investorflow_raw
    """)

    row = cur.fetchone()
    cur.close()

    if row[0] is None:
        start = datetime.now().date() - timedelta(days=10)
    else:
        start = row[0] + timedelta(days=1)

    end = datetime.now().date() - timedelta(days=1)

    dates = []

    while start <= end:
        if not is_holiday(start, "KR"):
            dates.append(start)
        start += timedelta(days=1)

    return dates


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


def request_html(session, url):

    resp = session.get(url, headers=HEADERS, timeout=(5, 10))
    resp.raise_for_status()

    return resp.content.decode("euc-kr", errors="ignore")


def parse_row(cols):

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

    price_diff = -diff_num if "하락" in diff_raw else diff_num

    return {
        "trade_date": trade_date,
        "close_price": close_price,
        "price_diff": price_diff,
        "price_change_rate": to_float(cols[3]),
        "volume": to_int(cols[4]),
        "institution_net": to_int(cols[5]),
        "foreign_net": to_int(cols[6]),
        "foreign_hold_shares": to_int(cols[7]),
        "foreign_hold_ratio": to_float(cols[8])
    }


def fetch_page(session, ticker, page):

    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"

    html = request_html(session, url)
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

        if record:
            data.append(record)

    return data


def save_batch(cur, ticker, records):

    for r in records:

        cur.execute("""
        INSERT INTO interest_investorflow_raw (
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
            updated_at = now()
        """, {
            "ticker": ticker,
            "source": SOURCE,
            "source_version": SOURCE_VERSION,
            **r
        })


from interest_get_holidays import is_holiday


def get_recent_business_days(n=3):

    days = []
    d = datetime.now().date() - timedelta(days=1)

    while len(days) < n:
        if not is_holiday(d, "KR"):
            days.append(d)
        d -= timedelta(days=1)

    return days


def fetch_target_date_rows(session, ticker, target_date):

    page = 1
    results = []

    while True:

        rows = fetch_page(session, ticker, page)

        if not rows:
            break

        stop = False

        for r in rows:

            if r["trade_date"] < target_date:
                stop = True
                break

            if r["trade_date"] == target_date:
                results.append(r)

        if stop:
            break

        page += 1
        time.sleep(0.1)

    return results

def get_existing_tickers_by_date(conn, target_date):
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code
        FROM interest_investorflow_raw
        WHERE trade_date = %s
    """, (target_date,))

    rows = {r[0] for r in cur.fetchall()}
    cur.close()

    return rows

def run():

    conn = get_conn()
    tickers = get_tickers()

    collected_dates = set()
    success_map = {}

    try:

        session = requests.Session()
        cur = conn.cursor()

        # 🔥 변경 핵심
        target_dates = generate_dates(conn)

        if not target_dates:
            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": [],
                "failed_lines": [],
                "error_count": 0
            }
            print_step_log("interest_investorflow", result)
            return result

        for ticker, company, last_date in tickers:

            for target_date in target_dates:

                existing = get_existing_tickers_by_date(conn, target_date)

                if ticker in existing:
                    continue

                rows = fetch_target_date_rows(session, ticker, target_date)

                if not rows:
                    continue

                save_batch(cur, ticker, rows)

                for r in rows:
                    d = str(r["trade_date"])
                    collected_dates.add(d)
                    success_map[d] = success_map.get(d, 0) + 1

        conn.commit()

        cur.close()
        conn.close()
        session.close()

        if not collected_dates:
            status = "NO_CHANGE"
            success_lines = []
        else:
            status = "SUCCESS"
            success_lines = [
                f"{d} {success_map[d]} Investor Collected"
                for d in sorted(collected_dates)
            ]

        result = {
            "status": status,
            "collected_dates": sorted(collected_dates),
            "success_lines": success_lines,
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log("interest_investorflow", result)
        return result

    except Exception as e:

        conn.close()

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [str(e)],
            "error_count": 0
        }

        print_step_log("interest_investorflow", result)
        return result


if __name__ == "__main__":
    run()