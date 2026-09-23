"""Script that enriches the sector/industry information of the stock universe based on yfinance.

It reads the universe and mapping information from the DB and queries sector information via yfinance external requests.
Because the results may update PostgreSQL reference/interest-family tables, confirm the impact scope before running.
"""

import time
import psycopg2
from db_config import get_db_config
import yfinance as yf
from datetime import datetime, timezone

DB_CONFIG = get_db_config()

SLEEP_SEC = 0.25  # Avoid over-calling Yahoo (increase to 0.5~1.0 if needed)
BATCH_COMMIT = 50


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_sector_mapping(conn):
    """
    Builds dicts based on sector_mapping(sector_en, sector_kr, sector_type).
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sector_en, sector_kr, sector_type
        FROM sector_mapping
    """)
    rows = cur.fetchall()
    cur.close()

    sector_map = {}    # (type='sector') EN -> KR
    industry_map = {}  # (type='industry') EN -> KR

    for en, kr, tp in rows:
        if not en:
            continue
        if tp == "sector":
            sector_map[en] = kr
        elif tp == "industry":
            industry_map[en] = kr

    return sector_map, industry_map


def ensure_mapping_row(conn, en_value: str, sector_type: str):
    """
    If it is not in sector_mapping, INSERT it first (with KR as NULL).
    """
    if not en_value:
        return
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sector_mapping (sector_en, sector_kr, sector_type, created_at, updated_at)
        VALUES (%s, NULL, %s, now(), now())
        ON CONFLICT (sector_en, sector_type) DO NOTHING
    """, (en_value, sector_type))
    cur.close()


def to_yf_symbol(ticker_code: str, market: str | None):
    """
    Generates the yfinance symbol based on the stock_universe.market value.
    - KOSPI/KS -> .KS
    - KOSDAQ/KQ -> .KQ
    - Everything else defaults to .KS (extend the logic here if desired)
    """
    m = (market or "").upper().strip()

    if m in ("KOSDAQ", "KQ"):
        return f"{ticker_code}.KQ"
    # KOSPI / KS / others map to KS
    return f"{ticker_code}.KS"


def translate_to_kr(sector_en, industry_en, sector_map, industry_map):
    """
    Converts sector + industry into a Korean array.
    - Excluded if not in the mapping or if kr is NULL (an empty array is possible)
    """
    out = []

    if sector_en:
        kr = sector_map.get(sector_en)
        if kr:  # excluded if NULL/""
            out.append(kr)

    if industry_en:
        kr = industry_map.get(industry_en)
        if kr and kr not in out:
            out.append(kr)

    return out


def run():
    print("===== build_universe_sector.py START =====")

    conn = get_conn()
    conn.autocommit = False

    # 1) Load the mapping
    sector_map, industry_map = load_sector_mapping(conn)
    print(f"Loaded mapping: sector={len(sector_map)}, industry={len(industry_map)}")

    # 2) Query the universe tickers
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker_code, company_name, market
        FROM stock_universe
        ORDER BY ticker_code
    """)
    stocks = cur.fetchall()
    cur.close()

    total = len(stocks)
    print(f"TOTAL: {total}")

    updated = 0
    committed = 0

    for idx, (ticker_code, company_name, market) in enumerate(stocks, start=1):
        yf_symbol = to_yf_symbol(ticker_code, market)

        sector_en = None
        industry_en = None

        try:
            info = yf.Ticker(yf_symbol).info or {}
            sector_en = info.get("sector")
            industry_en = info.get("industry")
        except Exception as e:
            print(f"[{idx}/{total}] {ticker_code} {company_name} | yfinance error: {e}")
            time.sleep(SLEEP_SEC)
            continue

        # 3) EN values not in the mapping are registered in sector_mapping (kr=null)
        if sector_en and sector_en not in sector_map:
            ensure_mapping_row(conn, sector_en, "sector")
        if industry_en and industry_en not in industry_map:
            ensure_mapping_row(conn, industry_en, "industry")

        # 4) Build the Korean array
        sector_kr_arr = translate_to_kr(sector_en, industry_en, sector_map, industry_map)

        # (Important) The newly INSERTed mappings are not reflected in the dict,
        # so during this run it is normal for entries with no KR yet to become [].
        # Once the sector_mapping KR values are filled in and it is run again, they fill automatically.

        try:
            cur2 = conn.cursor()
            cur2.execute("""
                UPDATE stock_universe
                SET sector = %s,
                    updated_at = now()
                WHERE ticker_code = %s
            """, (sector_kr_arr, ticker_code))
            cur2.close()

            updated += 1
            print(f"[{idx}/{total}] {ticker_code} {company_name} | EN: {sector_en} / {industry_en} | KR: {sector_kr_arr}")

        except Exception as e:
            print(f"[{idx}/{total}] {ticker_code} {company_name} | DB update error: {e}")
            conn.rollback()
            time.sleep(SLEEP_SEC)
            continue

        # Batch commit
        if updated % BATCH_COMMIT == 0:
            conn.commit()
            committed += 1
            print(f"--- COMMIT #{committed} (updated={updated}) ---")

        time.sleep(SLEEP_SEC)

    conn.commit()
    conn.close()

    print(f"✅ DONE. updated={updated}, total={total}")


if __name__ == "__main__":
    run()
