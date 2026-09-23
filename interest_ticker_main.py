"""Script that collects basic information for target tickers based on Naver/yfinance.

Using the DB universe, it queries Naver API-style data and yfinance information and stores the basic attributes.
Because it involves external requests and DB upserts, run it only during the production collection stage.
"""

import requests
import yfinance as yf
import psycopg2
from db_config import get_db_config
import json
import time
from datetime import datetime, timezone

DB_CONFIG = get_db_config()

TICKER_CODE = "005380"
YF_TICKER = "005380.KS"

SOURCE = "naver"
SOURCE_VERSION = "1.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# -----------------------------
# Parse Naver totalInfos
# -----------------------------
def extract_from_total_infos(data, target_code):
    total_infos = data.get("totalInfos", [])
    for item in total_infos:
        if item.get("code") == target_code:
            return item.get("value")
    return None


# -----------------------------
# Clean up numeric strings
# -----------------------------
def parse_number(value):
    if not value:
        return None

    value = value.replace(",", "")
    value = value.replace("원", "")
    value = value.replace("%", "")
    value = value.replace("배", "").strip()

    # Handle market cap such as "104조 2,217억"
    if "조" in value:
        trillion_part = value.split("조")[0]
        remainder = value.split("조")[1]

        trillion = float(trillion_part)

        billion = 0
        if "억" in remainder:
            billion_part = remainder.replace("억", "").strip()
            if billion_part:
                billion = float(billion_part)

        return int(trillion * 1_0000_0000_0000 + billion * 1_0000_0000)

    if "억" in value:
        return int(float(value.replace("억", "")) * 1_0000_0000)

    try:
        return float(value)
    except:
        return None


def safe_int(v):
    try:
        if v is None:
            return None
        return int(float(v))
    except:
        return None


def fetch_with_retry(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return {}


# -----------------------------
# Main execution
# -----------------------------
def run():
    print("===== interest_ticker_main OPTIMIZED =====")

    naver_integration_url = f"https://m.stock.naver.com/api/stock/{TICKER_CODE}/integration"
    naver_basic_url = f"https://m.stock.naver.com/api/stock/{TICKER_CODE}/basic"

    naver_int = fetch_with_retry(naver_integration_url)
    naver_basic = fetch_with_retry(naver_basic_url)

    yf_ticker = yf.Ticker(YF_TICKER)
    info = yf_ticker.info

    # Extract based on Naver totalInfos
    last_price = extract_from_total_infos(naver_int, "lastClosePrice")
    market_value = extract_from_total_infos(naver_int, "marketValue")
    foreign_rate = extract_from_total_infos(naver_int, "foreignRate")
    high_52w = extract_from_total_infos(naver_int, "highPriceOf52Weeks")
    low_52w = extract_from_total_infos(naver_int, "lowPriceOf52Weeks")

    record = {
        "ticker_code": TICKER_CODE,
        "company_name": naver_int.get("stockName"),
        "market": naver_basic.get("stockExchangeType", {}).get("code"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "current_price": parse_number(last_price),
        "market_cap": parse_number(market_value),
        "float_shares": safe_int(info.get("floatShares")),
        "avg_volume": safe_int(info.get("averageVolume")),
        "foreign_ownership_rate": parse_number(foreign_rate),
        "high_52w": parse_number(high_52w),
        "low_52w": parse_number(low_52w),
        "raw_json": json.dumps({
            "naver_integration": naver_int,
            "naver_basic": naver_basic,
            "yfinance_info": info
        }, ensure_ascii=False),

        # optimization applied
        "as_of_ts": datetime.now(timezone.utc),
        "source": SOURCE,
        "source_version": SOURCE_VERSION,
    }

    print("📌 파싱 결과:")
    print({
        "company_name": record["company_name"],
        "current_price": record["current_price"],
        "market_cap": record["market_cap"],
        "foreign_rate": record["foreign_ownership_rate"],
        "high_52w": record["high_52w"],
        "low_52w": record["low_52w"]
    })

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO interest_ticker_main_raw (
            ticker_code, company_name, market,
            sector, industry,
            current_price, market_cap,
            float_shares, avg_volume,
            foreign_ownership_rate,
            high_52w, low_52w,
            raw_json,
            as_of_ts,
            source, source_version,
            collected_at
        )
        VALUES (
            %(ticker_code)s, %(company_name)s, %(market)s,
            %(sector)s, %(industry)s,
            %(current_price)s, %(market_cap)s,
            %(float_shares)s, %(avg_volume)s,
            %(foreign_ownership_rate)s,
            %(high_52w)s, %(low_52w)s,
            %(raw_json)s,
            %(as_of_ts)s,
            %(source)s, %(source_version)s,
            now()
        )
        ON CONFLICT (ticker_code)
        DO UPDATE SET
            company_name = EXCLUDED.company_name,
            market = EXCLUDED.market,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            current_price = EXCLUDED.current_price,
            market_cap = EXCLUDED.market_cap,
            float_shares = EXCLUDED.float_shares,
            avg_volume = EXCLUDED.avg_volume,
            foreign_ownership_rate = EXCLUDED.foreign_ownership_rate,
            high_52w = EXCLUDED.high_52w,
            low_52w = EXCLUDED.low_52w,
            raw_json = EXCLUDED.raw_json,
            as_of_ts = EXCLUDED.as_of_ts,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
            updated_at = now();
    """, record)

    conn.commit()
    cur.close()
    conn.close()

    print("✅ interest_ticker_main_raw 저장 완료")


if __name__ == "__main__":
    run()
