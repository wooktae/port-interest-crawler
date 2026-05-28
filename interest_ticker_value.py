"""Naver 기반 관심종목 valuation 데이터를 수집하는 스크립트다.

종목별 valuation 원천 데이터를 요청하고 필요한 값을 파싱해 PostgreSQL에 저장한다.
외부 웹 요청과 DB upsert가 포함되므로 운영 수집 단계에서만 실행한다.
"""

import requests
import psycopg2
from db_config import get_db_config
import json
import time
from datetime import datetime, date, timezone

DB_CONFIG = get_db_config()

TICKER_CODE = "005380"

SOURCE = "naver"
SOURCE_VERSION = "1.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def fetch_with_retry(url, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return {}


def extract_from_total_infos(data, target_code):
    total_infos = data.get("totalInfos", [])
    for item in total_infos:
        if item.get("code") == target_code:
            return item.get("value")
    return None


def parse_number(value):
    if not value:
        return None

    value = value.replace(",", "")
    value = value.replace("원", "")
    value = value.replace("%", "")
    value = value.replace("배", "").strip()

    try:
        return float(value)
    except:
        return None


def run():
    print("===== interest_ticker_value OPTIMIZED =====")

    integration_url = f"https://m.stock.naver.com/api/stock/{TICKER_CODE}/integration"
    data = fetch_with_retry(integration_url)

    # totalInfos 영역
    forward_eps = extract_from_total_infos(data, "cnsEps")
    forward_per = extract_from_total_infos(data, "cnsPer")
    dividend_yield = extract_from_total_infos(data, "dividendYieldRatio")
    dps = extract_from_total_infos(data, "dividend")

    # consensusInfo 영역
    consensus = data.get("consensusInfo", {})
    analyst_point = consensus.get("recommMean")
    target_price_avg = consensus.get("priceTargetMean")

    record = {
        "ticker_code": TICKER_CODE,
        "as_of_date": date.today(),
        "as_of_ts": datetime.now(timezone.utc),
        "forward_eps": parse_number(forward_eps),
        "forward_per": parse_number(forward_per),
        "dividend_yield": parse_number(dividend_yield),
        "dps": parse_number(dps),
        "analyst_point": parse_number(analyst_point),
        "target_price_avg": parse_number(target_price_avg),
        "raw_json": json.dumps(data, ensure_ascii=False),
        "source": SOURCE,
        "source_version": SOURCE_VERSION
    }

    print("📌 파싱 결과:")
    print({
        "forward_eps": record["forward_eps"],
        "forward_per": record["forward_per"],
        "dividend_yield": record["dividend_yield"],
        "dps": record["dps"],
        "analyst_point": record["analyst_point"],
        "target_price_avg": record["target_price_avg"]
    })

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO interest_ticker_value_raw (
            ticker_code,
            as_of_date,
            as_of_ts,
            forward_eps,
            forward_per,
            dividend_yield,
            dps,
            analyst_point,
            target_price_avg,
            raw_json,
            source,
            source_version,
            collected_at
        )
        VALUES (
            %(ticker_code)s,
            %(as_of_date)s,
            %(as_of_ts)s,
            %(forward_eps)s,
            %(forward_per)s,
            %(dividend_yield)s,
            %(dps)s,
            %(analyst_point)s,
            %(target_price_avg)s,
            %(raw_json)s,
            %(source)s,
            %(source_version)s,
            now()
        )
        ON CONFLICT (ticker_code, as_of_date)
        DO UPDATE SET
            forward_eps = EXCLUDED.forward_eps,
            forward_per = EXCLUDED.forward_per,
            dividend_yield = EXCLUDED.dividend_yield,
            dps = EXCLUDED.dps,
            analyst_point = EXCLUDED.analyst_point,
            target_price_avg = EXCLUDED.target_price_avg,
            raw_json = EXCLUDED.raw_json,
            as_of_ts = EXCLUDED.as_of_ts,
            source = EXCLUDED.source,
            source_version = EXCLUDED.source_version,
            updated_at = now();
    """, record)

    conn.commit()
    cur.close()
    conn.close()

    print("✅ interest_ticker_value_raw 저장 완료")


if __name__ == "__main__":
    run()
