import yfinance as yf
import psycopg2
from db_config import get_db_config
import json
import pandas as pd
from datetime import datetime

DB_CONFIG = get_db_config()

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_universe():

    conn = get_conn()
    cur = conn.cursor()

    sql = """
        SELECT ticker_code, market
        FROM stock_universe
        ORDER BY ticker_code
    """

    cur.execute(sql)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def convert_yfinance_ticker(code, market):

    if market == "KOSPI":
        return f"{code}.KS"

    if market == "KOSDAQ":
        return f"{code}.KQ"

    return code


def safe_float(v):
    if pd.isna(v):
        return None
    return float(v)


def safe_int(v):
    if pd.isna(v):
        return None
    return int(v)


def fetch_history(code, market):

    ticker = convert_yfinance_ticker(code, market)

    print("Downloading:", ticker)

    df = yf.Ticker(ticker).history(start="2007-01-01")

    if df.empty:
        print("No data:", ticker)
        return []

    records = []

    for idx, row in df.iterrows():

        price_date = pd.to_datetime(idx).date()
        now_ts = datetime.now()

        record = {
            "ticker_code": code,
            "price_date": price_date,
            "open_price": safe_float(row["Open"]),
            "high_price": safe_float(row["High"]),
            "low_price": safe_float(row["Low"]),
            "close_price": safe_float(row["Close"]),
            "adj_close_price": safe_float(row["Close"]),
            "volume": safe_int(row["Volume"]),

            "raw_json": json.dumps({
                "ticker": ticker,
                "open": safe_float(row["Open"]),
                "high": safe_float(row["High"]),
                "low": safe_float(row["Low"]),
                "close": safe_float(row["Close"]),
                "volume": safe_int(row["Volume"])
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
        INSERT INTO price_history (
            ticker_code,
            price_date,
            open_price,
            high_price,
            low_price,
            close_price,
            adj_close_price,
            volume,
            raw_json,
            collected_at,
            as_of_ts,
            source,
            source_version
        )
        VALUES (
            %(ticker_code)s,
            %(price_date)s,
            %(open_price)s,
            %(high_price)s,
            %(low_price)s,
            %(close_price)s,
            %(adj_close_price)s,
            %(volume)s,
            %(raw_json)s,
            %(collected_at)s,
            %(as_of_ts)s,
            %(source)s,
            %(source_version)s
        )
        ON CONFLICT (ticker_code, price_date)
        DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            adj_close_price = EXCLUDED.adj_close_price,
            volume = EXCLUDED.volume,
            raw_json = EXCLUDED.raw_json,
            as_of_ts = EXCLUDED.as_of_ts,
            updated_at = now();
    """

    cur.executemany(sql, records)

    conn.commit()

    cur.close()
    conn.close()


def run():

    print("===== PRICE HISTORY BACKFILL START =====")

    universe = get_universe()

    total = 0

    for code, market in universe:

        records = fetch_history(code, market)

        if not records:
            continue

        save_batch(records)

        print(code, "saved rows:", len(records))

        total += len(records)

    print("TOTAL ROWS:", total)
    print("===== DONE =====")


if __name__ == "__main__":
    run()