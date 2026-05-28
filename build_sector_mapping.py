"""yfinance sector/industry 영문 값을 한국어 매핑 테이블에 보강하는 스크립트다.

PostgreSQL에 접속해 universe 정보를 읽고, yfinance 외부 요청 결과를 mapping 테이블에 저장한다.
실행 시 외부 네트워크와 DB upsert가 발생하므로 문서화 작업 중에는 실행하지 않는다.
"""

import psycopg2
from db_config import get_db_config
import yfinance as yf
import time

DB_CONFIG = get_db_config()


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def run():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker_code, company_name
        FROM stock_universe
        ORDER BY ticker_code
    """)

    rows = cur.fetchall()

    print("TOTAL:", len(rows))

    sector_set = set()
    industry_set = set()

    for ticker, name in rows:

        try:

            yf_ticker = yf.Ticker(ticker + ".KS")
            info = yf_ticker.info

            sector = info.get("sector")
            industry = info.get("industry")

            print(
                ticker,
                name,
                "| sector:", sector,
                "| industry:", industry
            )

            if sector:
                sector_set.add(sector)

            if industry:
                industry_set.add(industry)

            time.sleep(0.2)

        except Exception as e:
            print("ERROR:", ticker, name, e)

    print("\n===== INSERT SECTOR =====")

    for sector in sector_set:

        cur.execute("""
        INSERT INTO sector_mapping (sector_en, sector_type)
        VALUES (%s, 'sector')
        ON CONFLICT (sector_en) DO NOTHING
        """, (sector,))

        print("INSERT:", sector)

    print("\n===== INSERT INDUSTRY =====")

    for industry in industry_set:

        cur.execute("""
        INSERT INTO sector_mapping (sector_en, sector_type)
        VALUES (%s, 'industry')
        ON CONFLICT (sector_en) DO NOTHING
        """, (industry,))

        print("INSERT:", industry)

    conn.commit()

    cur.close()
    conn.close()

    print("\nDONE")


if __name__ == "__main__":
    run()
