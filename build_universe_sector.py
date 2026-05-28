"""stock universe의 sector/industry 정보를 yfinance 기준으로 보강하는 스크립트다.

DB에서 universe와 매핑 정보를 읽고 yfinance 외부 요청으로 업종 정보를 조회한다.
결과는 PostgreSQL reference/interest 계열 테이블에 갱신될 수 있으므로 실행 전 영향 범위를 확인한다.
"""

import time
import psycopg2
from db_config import get_db_config
import yfinance as yf
from datetime import datetime, timezone

DB_CONFIG = get_db_config()

SLEEP_SEC = 0.25  # 야후 과호출 방지 (필요하면 0.5~1.0로)
BATCH_COMMIT = 50


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_sector_mapping(conn):
    """
    sector_mapping(sector_en, sector_kr, sector_type) 기준으로 dict 구성
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
    sector_mapping에 없으면 일단 INSERT (KR은 NULL) 해둠
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
    stock_universe.market 값에 따라 yfinance 심볼 생성
    - KOSPI/KS -> .KS
    - KOSDAQ/KQ -> .KQ
    - 그 외는 기본 .KS (원하면 여기 로직 확장)
    """
    m = (market or "").upper().strip()

    if m in ("KOSDAQ", "KQ"):
        return f"{ticker_code}.KQ"
    # KOSPI / KS / 기타는 KS로
    return f"{ticker_code}.KS"


def translate_to_kr(sector_en, industry_en, sector_map, industry_map):
    """
    sector + industry를 한글 array로 변환.
    - 매핑에 없거나 kr이 NULL이면 제외(빈 배열 가능)
    """
    out = []

    if sector_en:
        kr = sector_map.get(sector_en)
        if kr:  # NULL/""이면 제외
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

    # 1) 매핑 로딩
    sector_map, industry_map = load_sector_mapping(conn)
    print(f"Loaded mapping: sector={len(sector_map)}, industry={len(industry_map)}")

    # 2) universe 종목 조회
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

        # 3) mapping에 없는 EN 값은 sector_mapping에 등록(kr=null)
        if sector_en and sector_en not in sector_map:
            ensure_mapping_row(conn, sector_en, "sector")
        if industry_en and industry_en not in industry_map:
            ensure_mapping_row(conn, industry_en, "industry")

        # 4) 한글 array 만들기
        sector_kr_arr = translate_to_kr(sector_en, industry_en, sector_map, industry_map)

        # (중요) 방금 INSERT한 새 매핑들은 dict에 반영 안 되므로,
        # 이번 런에서는 KR이 아직 없으면 []로 들어가는 게 정상.
        # 다음에 sector_mapping KR 채운 뒤 다시 돌리면 자동으로 채워짐.

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

        # 배치 커밋
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
