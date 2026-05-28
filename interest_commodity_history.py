"""yfinance 기반 원자재 가격 데이터를 과거 기간 기준으로 backfill하는 스크립트다.

정의된 원자재 ticker의 장기 가격 이력을 조회해 PostgreSQL history/raw 계열 테이블에 저장한다.
대량 yfinance 요청과 DB 쓰기가 발생할 수 있으므로 실행 전 대상 범위를 확인한다.
"""

import yfinance as yf
import psycopg2
from db_config import get_db_config
import json
from datetime import datetime

DB_CONFIG = get_db_config()

COMMODITY_MAP = {
    "WTI": "CL=F",
    "BRENT": "BZ=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COPPER": "HG=F",
    "NATURAL_GAS": "NG=F"
}

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def fetch_history(name, ticker):

    print("Downloading:", name)

    df = yf.Ticker(ticker).history(start="2007-01-01")

    if df.empty:
        print("No data:", name)
        return []

    records = []

    for idx, row in df.iterrows():

        price = round(float(row["Close"]), 4)
        price_date = idx.date()
        now_ts = datetime.now()

        record = {
            "commodity_code": name,
            "date": price_date,
            "price": price,
            "raw_json": json.dumps({
                "ticker": ticker,
                "close": price
            }, ensure_ascii=False),
            "collected_at": now_ts,
            "as_of_ts": now_ts,
            "source": SOURCE_NAME,
            "source_version": SOURCE_VERSION
        }

        records.append(record)

    return records


def save_batch(records):

    conn = get_conn()
    cur = conn.cursor()

    sql = """
        INSERT INTO interest_commodity_raw (
            commodity_code,
            date,
            price,
            raw_json,
            collected_at,
            as_of_ts,
            source,
            source_version
        )
        VALUES (
            %(commodity_code)s,
            %(date)s,
            %(price)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_ts)s,
            %(source)s,
            %(source_version)s
        )
        ON CONFLICT (commodity_code, date)
        DO UPDATE SET
            price = EXCLUDED.price,
            raw_json = EXCLUDED.raw_json,
            as_of_ts = EXCLUDED.as_of_ts,
            updated_at = now();
    """

    cur.executemany(sql, records)

    conn.commit()
    cur.close()
    conn.close()


def run():

    print("===== COMMODITY BACKFILL START =====")

    total = 0

    for name, ticker in COMMODITY_MAP.items():

        records = fetch_history(name, ticker)

        if not records:
            continue

        save_batch(records)

        print(name, "saved rows:", len(records))

        total += len(records)

    print("TOTAL ROWS:", total)
    print("===== DONE =====")


if __name__ == "__main__":
    run()
