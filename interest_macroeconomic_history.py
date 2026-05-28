"""yfinance 기반 매크로 지표 데이터를 과거 기간 기준으로 backfill하는 스크립트다.

정의된 매크로 ticker의 장기 이력을 조회해 PostgreSQL에 일괄 저장한다.
대량 외부 요청과 DB 쓰기가 발생할 수 있으므로 실행 전 대상 범위를 확인한다.
"""

import yfinance as yf
import psycopg2
from db_config import get_db_config
import json
from datetime import datetime

DB_CONFIG = get_db_config()

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
