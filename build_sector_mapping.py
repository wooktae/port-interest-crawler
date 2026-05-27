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