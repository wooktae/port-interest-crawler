"""yfinance 기반 해외지수 가격 데이터를 과거 기간 기준으로 backfill하는 스크립트다.

정의된 해외지수 ticker의 장기 이력을 조회해 PostgreSQL에 일괄 저장한다.
대량 외부 요청과 DB 쓰기가 발생할 수 있으므로 실행 전 대상 범위를 확인한다.
"""

import yfinance as yf
import psycopg2
from db_config import get_db_config
import json
from datetime import datetime

DB_CONFIG = get_db_config()

INDEX_MAP = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOWJONES": "^DJI",
    "NIKKEI225": "^N225",
    "SHANGHAI": "000001.SS",
    "HANGSENG": "^HSI",
    "VIX": "^VIX"
}

START_DATE = "2007-01-01"

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.1.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def fetch_history(index_name, ticker):

    print("Downloading:", index_name)

    df = yf.Ticker(ticker).history(start=START_DATE)

    if df.empty:
        return []

    rows = []

    for idx, r in df.iterrows():

        volume = None

        try:
            v = int(r["Volume"])
            if v > 0:
                volume = v
        except:
            volume = None

        rows.append({
            "index_name": index_name,
            "date": idx.date(),
            "open_price": round(float(r["Open"]),4),
            "high_price": round(float(r["High"]),4),
            "low_price": round(float(r["Low"]),4),
            "close_price": round(float(r["Close"]),4),
            "volume": volume,
            "raw_json": json.dumps({
                "ticker": ticker,
                "open": float(r["Open"]),
                "high": float(r["High"]),
                "low": float(r["Low"]),
                "close": float(r["Close"]),
                "volume": volume
            }, ensure_ascii=False),
            "collected_at": datetime.now(),
            "as_of_ts": datetime.now(),
            "source": SOURCE_NAME,
            "source_version": SOURCE_VERSION
        })

    return rows


def save_batch(conn, rows):

    cur = conn.cursor()

    sql = """
    INSERT INTO interest_foreignindex_raw
    (
        index_name,
        date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        raw_json,
        collected_at,
        as_of_ts,
        source,
        source_version
    )
    VALUES
    (
        %(index_name)s,
        %(date)s,
        %(open_price)s,
        %(high_price)s,
        %(low_price)s,
        %(close_price)s,
        %(volume)s,
        %(raw_json)s,
        %(collected_at)s,
        %(as_of_ts)s,
        %(source)s,
        %(source_version)s
    )
    ON CONFLICT (index_name, date)
    DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        volume = EXCLUDED.volume,
        raw_json = EXCLUDED.raw_json,
        as_of_ts = EXCLUDED.as_of_ts,
        updated_at = now();
    """

    cur.executemany(sql, rows)

    conn.commit()
    cur.close()


def run():

    print("===== FOREIGNINDEX HISTORY LOAD =====")

    conn = get_conn()

    for name, ticker in INDEX_MAP.items():

        rows = fetch_history(name, ticker)

        if not rows:
            print("Skip:", name)
            continue

        save_batch(conn, rows)

        print("Inserted:", name, len(rows))

    conn.close()

    print("===== DONE =====")


if __name__ == "__main__":
    run()
