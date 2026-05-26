import yfinance as yf
import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

MACRO_TICKERS = {
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "US2Y": "^IRX",
    "DXY": "DX-Y.NYB",
    "USDKRW": "KRW=X",
    "USDJPY": "JPY=X",
    "USDCNY": "CNY=X"
}

SOURCE_NAME = "yfinance"
SOURCE_VERSION = "1.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def safe_value(x):
    try:
        if hasattr(x, "item"):
            return float(x.item())
        return float(x)
    except:
        return None


def fetch_macro_history():

    records = []

    for name, ticker in MACRO_TICKERS.items():

        print("Downloading:", name)

        df = yf.download(
            ticker,
            period="max",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            print("No data:", name)
            continue

        for idx, row in df.iterrows():

            close_price = safe_value(row["Close"])

            if close_price is None:
                continue

            open_price = safe_value(row["Open"])
            high_price = safe_value(row["High"])
            low_price = safe_value(row["Low"])
            volume = safe_value(row["Volume"])

            date_value = idx.date()

            now_ts = datetime.now()

            record = (
                "Global",
                name,
                date_value,
                round(close_price, 6),
                None,
                None,
                None,
                json.dumps({
                    "ticker": ticker,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume
                }, ensure_ascii=False),
                now_ts,
                now_ts,
                SOURCE_NAME,
                SOURCE_VERSION
            )

            records.append(record)

        print(name, "rows:", len(df))

    return records


def save_batch(records):

    conn = get_conn()
    cur = conn.cursor()

    sql = """
        INSERT INTO interest_macroeconomic_raw (
            country,
            indicator_name,
            period,
            released_value,
            expected_value,
            previous_value,
            impact_level,
            raw_json,
            released_at,
            collected_at,
            source,
            source_version
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (country, indicator_name, period)
        DO UPDATE SET
            released_value = EXCLUDED.released_value,
            raw_json = EXCLUDED.raw_json,
            collected_at = now(),
            updated_at = now();
    """

    cur.executemany(sql, records)

    conn.commit()
    cur.close()
    conn.close()


def run():

    print("===== MACRO HISTORY BACKFILL START =====")

    records = fetch_macro_history()

    print("TOTAL ROWS:", len(records))

    save_batch(records)

    print("===== DONE =====")


if __name__ == "__main__":
    run()