import requests
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from statistics import mean

# =========================================================
# CONFIG
# =========================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

SEOUL_TZ = ZoneInfo("Asia/Seoul")
HOLIDAY_API_BASE = "https://date.nager.at/api/v3/PublicHolidays"

ROWCOUNT_WARN_RATIO = 0.50
ROWCOUNT_ERROR_RATIO = 0.20
ROWCOUNT_LOOKBACK = 5
GAP_LOOKBACK_DAYS = 120
SOURCE_LIMIT = 5

PROGRAM_VOLUME_TOLERANCE = 1000
PROGRAM_AMOUNT_TOLERANCE = 1_000_000

# =========================================================
# TABLE META
# 첨부 파일 DDL 기준 + 컬럼 존재 여부 런타임 검증
# =========================================================
TABLE_SPECS = {
    "interest_news_raw": {
        "market": "KR",
        "date_col": "as_of_date",
        "required_cols": ["news_id", "source", "title", "published_at", "url", "as_of_date"],
        "dup_keys": ["news_id"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": [],
    },
    "interest_agency_raw": {
        "market": "KR",
        "date_col": "publish_date",
        "required_cols": ["ticker_code", "company_name", "agency_name", "title", "publish_date"],
        "dup_keys": ["ticker_code", "agency_name", "publish_date", "title"],
        "source_cols": ["source", "source_version"],
        "positive_cols": ["target_price"],
        "non_negative_cols": [],
    },
    "interest_foreignindex_raw": {
        "market": "US",
        "date_col": "date",
        "required_cols": ["index_name", "date", "close_price"],
        "dup_keys": ["index_name", "date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": ["open_price", "high_price", "low_price", "close_price"],
        "non_negative_cols": ["volume"],
    },
    "interest_commodity_raw": {
        "market": "US",
        "date_col": "date",
        "required_cols": ["commodity_code", "date", "price"],
        "dup_keys": ["commodity_code", "date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": ["price"],
        "non_negative_cols": [],
    },
    "interest_macroeconomic_raw": {
        "market": "US",
        "date_col": "period",
        "required_cols": ["country", "indicator_name", "period"],
        "dup_keys": ["country", "indicator_name", "period"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": [],
    },
    "interest_price_raw": {
        "market": "KR",
        "date_col": "price_date",
        "required_cols": ["ticker_code", "price_date", "close_price"],
        "dup_keys": ["ticker_code", "price_date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": ["open_price", "high_price", "low_price", "close_price"],
        "non_negative_cols": ["volume"],
    },
    "interest_investorflow_raw": {
        "market": "KR",
        "date_col": "trade_date",
        "required_cols": ["ticker_code", "trade_date"],
        "dup_keys": ["ticker_code", "trade_date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": [],
    },
    "interest_program_raw": {
        "market": "KR",
        "date_col": "trade_date",
        "required_cols": ["trade_date"],
        "dup_keys": ["trade_date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": [
            "arbitrage_sell_volume", "arbitrage_buy_volume",
            "nonarb_sell_volume", "nonarb_buy_volume",
            "total_sell_volume", "total_buy_volume"
        ],
    },
    "interest_shortsell_raw": {
        "market": "KR",
        "date_col": "trade_date",
        "required_cols": ["trade_date", "ticker_code"],
        "dup_keys": ["trade_date", "ticker_code"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": ["short_volume", "short_amount", "total_volume", "short_ratio"],
    },
    "interest_marketbreadth_raw": {
        "market": "KR",
        "date_col": "date",
        "required_cols": ["date"],
        "dup_keys": ["date"],
        "source_cols": ["source", "source_version"],
        "positive_cols": [],
        "non_negative_cols": ["advancers", "decliners"],
    },
}

# =========================================================
# RESULT COUNTER
# =========================================================
class ResultCounter:
    def __init__(self):
        self.ok = 0
        self.warn = 0
        self.error = 0
        self.info = 0

RESULT = ResultCounter()

# =========================================================
# LOG FORMAT
# =========================================================
def log_section(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)

def log_ok(name, msg):
    RESULT.ok += 1
    print(f"OK     | {name:<35} | {msg}")

def log_warn(name, msg):
    RESULT.warn += 1
    print(f"WARN   | {name:<35} | {msg}")

def log_error(name, msg):
    RESULT.error += 1
    print(f"ERROR  | {name:<35} | {msg}")

def log_info(name, msg):
    RESULT.info += 1
    print(f"INFO   | {name:<35} | {msg}")

def fmt_date(d):
    return d.strftime("%Y-%m-%d") if d else "None"

# =========================================================
# DB UTILS
# =========================================================
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn

def execute_query(cur, conn, query, params=None, fetch="all"):
    try:
        cur.execute(query, params)
        if fetch == "val":
            row = cur.fetchone()
            return row[0] if row else None
        elif fetch == "one":
            return cur.fetchone()
        else:
            return cur.fetchall()
    except Exception:
        conn.rollback()
        raise

def get_table_columns(cur, conn, table_name):
    q = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
    """
    rows = execute_query(cur, conn, q, (table_name,), fetch="all")
    return {r[0] for r in rows}

def has_cols(existing_cols, cols):
    return all(c in existing_cols for c in cols)

# =========================================================
# HOLIDAY / BUSINESS DAY
# =========================================================
def is_weekend(d: date):
    return d.weekday() >= 5

def fetch_holidays(year: int, country_code: str):
    url = f"{HOLIDAY_API_BASE}/{year}/{country_code}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    rows = resp.json()
    return set(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows)

def get_holiday_info(target_date: date, country_code: str, cache: dict):
    key = (country_code, target_date.year)
    if key not in cache:
        cache[key] = fetch_holidays(target_date.year, country_code)

    return {
        "is_non_business_day": is_weekend(target_date) or target_date in cache[key]
    }

def get_previous_business_day(base_date: date, holiday_func):
    d = base_date - timedelta(days=1)
    while holiday_func(d)["is_non_business_day"]:
        d -= timedelta(days=1)
    return d

# =========================================================
# BASIC METADATA
# =========================================================
def query_latest_date(cur, conn, table_name, date_col):
    q = sql.SQL("SELECT MAX({date_col}) FROM {table}").format(
        date_col=sql.Identifier(date_col),
        table=sql.Identifier(table_name)
    )
    return execute_query(cur, conn, q, fetch="val")

def query_total_count(cur, conn, table_name):
    q = sql.SQL("SELECT COUNT(*) FROM {table}").format(table=sql.Identifier(table_name))
    return execute_query(cur, conn, q, fetch="val")

# =========================================================
# 1. DATE VALIDATION
# =========================================================
def validate_date(cur, conn):
    log_section("DATE VALIDATION")

    now = datetime.now(SEOUL_TZ)
    today = now.date()
    cache = {}

    kr = lambda d: get_holiday_info(d, "KR", cache)
    us = lambda d: get_holiday_info(d, "US", cache)

    expected_kr = get_previous_business_day(today, kr)
    expected_us = get_previous_business_day(today, us)

    for table_name, spec in TABLE_SPECS.items():
        try:
            date_col = spec["date_col"]
            market = spec["market"]

            latest = query_latest_date(cur, conn, table_name, date_col)
            expected = expected_kr if market == "KR" else expected_us

            if latest is None:
                log_error(table_name, f"NO DATA | expected={expected}")
                continue

            # 뉴스 / 기관은 오늘 데이터까지 수집 가능하므로 today 허용
            if table_name in ["interest_news_raw", "interest_agency_raw"]:
                if latest >= expected:
                    log_ok(table_name, f"{latest} vs {expected} | today/latest allowed")
                else:
                    lag = (expected - latest).days
                    if lag <= 1:
                        log_warn(table_name, f"{latest} vs {expected} | lag_days={lag}")
                    else:
                        log_error(table_name, f"{latest} vs {expected} | lag_days={lag}")
                continue

            if latest == expected:
                log_ok(table_name, f"{latest} vs {expected}")
            elif latest < expected:
                lag = (expected - latest).days
                if lag <= 1:
                    log_warn(table_name, f"{latest} vs {expected} | lag_days={lag}")
                else:
                    log_error(table_name, f"{latest} vs {expected} | lag_days={lag}")
            else:
                log_warn(table_name, f"{latest} vs {expected} | future/latest unexpected")
        except Exception as e:
            log_error(table_name, f"오류: {e}")

# =========================================================
# 2. NULL CHECK
# =========================================================
def validate_null(cur, conn, schema_cache):
    log_section("NULL CHECK")

    for table_name, spec in TABLE_SPECS.items():
        try:
            existing_cols = schema_cache[table_name]
            target_cols = [c for c in spec["required_cols"] if c in existing_cols]

            if not target_cols:
                log_info(f"{table_name}_null", "SKIP | no matched required cols")
                continue

            where_clause = " OR ".join([f"{c} IS NULL" for c in target_cols])
            q = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
            cnt = execute_query(cur, conn, q, fetch="val")

            if cnt == 0:
                log_ok(f"{table_name}_null", f"null_count={cnt}")
            else:
                log_error(f"{table_name}_null", f"null_count={cnt}")
        except Exception as e:
            log_error(f"{table_name}_null", f"오류: {e}")

    try:
        table_name = "interest_macroeconomic_raw"
        existing_cols = schema_cache[table_name]
        candidate_cols = [c for c in ["released_value", "expected_value", "previous_value"] if c in existing_cols]
        if candidate_cols:
            where_clause = " AND ".join([f"{c} IS NULL" for c in candidate_cols])
            q = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("interest_macroeconomic_raw_valueset", f"all_null_count={cnt}")
            else:
                log_warn("interest_macroeconomic_raw_valueset", f"all_null_count={cnt}")
    except Exception as e:
        log_error("interest_macroeconomic_raw_valueset", f"오류: {e}")

# =========================================================
# 3. DUPLICATE CHECK
# =========================================================
def validate_duplicate(cur, conn, schema_cache):
    log_section("DUPLICATE CHECK")

    for table_name, spec in TABLE_SPECS.items():
        try:
            existing_cols = schema_cache[table_name]
            dup_keys = [c for c in spec["dup_keys"] if c in existing_cols]

            if len(dup_keys) != len(spec["dup_keys"]):
                log_info(f"{table_name}_dup", f"SKIP | missing dup keys: {spec['dup_keys']}")
                continue

            group_cols = ", ".join(dup_keys)
            q = f"""
                SELECT COUNT(*)
                FROM (
                    SELECT {group_cols}
                    FROM {table_name}
                    GROUP BY {group_cols}
                    HAVING COUNT(*) > 1
                ) t
            """
            cnt = execute_query(cur, conn, q, fetch="val")

            if cnt == 0:
                log_ok(f"{table_name}_dup", f"dup_count={cnt}")
            else:
                log_error(f"{table_name}_dup", f"dup_count={cnt}")
        except Exception as e:
            log_error(f"{table_name}_dup", f"오류: {e}")

# =========================================================
# 4. DOMAIN CHECK
# =========================================================
def validate_domain_generic(cur, conn, schema_cache):
    log_section("DOMAIN CHECK")

    for table_name, spec in TABLE_SPECS.items():
        existing_cols = schema_cache[table_name]

        for col in spec.get("positive_cols", []):
            if col not in existing_cols:
                continue
            try:
                # WTI 2020-04-20 음수 유가 케이스 허용
                if table_name == "interest_commodity_raw" and col == "price" and "commodity_code" in existing_cols:
                    q = f"""
                        SELECT COUNT(*)
                        FROM {table_name}
                        WHERE {col} IS NOT NULL
                          AND {col} <= 0
                          AND commodity_code <> 'WTI'
                    """
                else:
                    q = f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NOT NULL AND {col} <= 0"

                cnt = execute_query(cur, conn, q, fetch='val')
                if cnt == 0:
                    log_ok(f"{table_name}_{col}_positive", f"bad_count={cnt}")
                else:
                    log_warn(f"{table_name}_{col}_positive", f"bad_count={cnt}")
            except Exception as e:
                log_error(f"{table_name}_{col}_positive", f"오류: {e}")

        for col in spec.get("non_negative_cols", []):
            if col not in existing_cols:
                continue
            try:
                q = f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NOT NULL AND {col} < 0"
                cnt = execute_query(cur, conn, q, fetch='val')
                if cnt == 0:
                    log_ok(f"{table_name}_{col}_nonneg", f"bad_count={cnt}")
                else:
                    log_warn(f"{table_name}_{col}_nonneg", f"bad_count={cnt}")
            except Exception as e:
                log_error(f"{table_name}_{col}_nonneg", f"오류: {e}")

def validate_domain_specific(cur, conn, schema_cache):
    try:
        cols = schema_cache["interest_news_raw"]
        if has_cols(cols, ["published_at", "as_of_date"]):
            q = """
                SELECT COUNT(*)
                FROM interest_news_raw
                WHERE published_at IS NOT NULL
                  AND as_of_date IS NOT NULL
                  AND published_at::date <> as_of_date
            """
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("news_date_mismatch", f"bad_count={cnt}")
            else:
                log_warn("news_date_mismatch", f"bad_count={cnt}")
    except Exception as e:
        log_error("news_date_mismatch", f"오류: {e}")

    try:
        cols = schema_cache["interest_agency_raw"]
        if "score" in cols:
            q = "SELECT COUNT(*) FROM interest_agency_raw WHERE score IS NOT NULL AND score NOT BETWEEN 1 AND 5"
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("agency_score_range", f"bad_count={cnt}")
            else:
                log_warn("agency_score_range", f"bad_count={cnt}")
    except Exception as e:
        log_error("agency_score_range", f"오류: {e}")

    try:
        cols = schema_cache["interest_foreignindex_raw"]
        needed = ["open_price", "high_price", "low_price", "close_price"]
        if has_cols(cols, needed):
            q = """
                SELECT COUNT(*)
                FROM interest_foreignindex_raw
                WHERE (high_price IS NOT NULL AND low_price IS NOT NULL AND high_price < low_price)
                   OR (high_price IS NOT NULL AND open_price IS NOT NULL AND high_price < open_price)
                   OR (high_price IS NOT NULL AND close_price IS NOT NULL AND high_price < close_price)
                   OR (low_price IS NOT NULL AND open_price IS NOT NULL AND low_price > open_price)
                   OR (low_price IS NOT NULL AND close_price IS NOT NULL AND low_price > close_price)
            """
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("foreignindex_ohlc", f"bad_count={cnt}")
            else:
                log_error("foreignindex_ohlc", f"bad_count={cnt}")
    except Exception as e:
        log_error("foreignindex_ohlc", f"오류: {e}")

    try:
        cols = schema_cache["interest_price_raw"]
        needed = ["open_price", "high_price", "low_price", "close_price"]
        if has_cols(cols, needed):
            q = """
                SELECT COUNT(*)
                FROM interest_price_raw
                WHERE (high_price IS NOT NULL AND low_price IS NOT NULL AND high_price < low_price)
                   OR (high_price IS NOT NULL AND open_price IS NOT NULL AND high_price < open_price)
                   OR (high_price IS NOT NULL AND close_price IS NOT NULL AND high_price < close_price)
                   OR (low_price IS NOT NULL AND open_price IS NOT NULL AND low_price > open_price)
                   OR (low_price IS NOT NULL AND close_price IS NOT NULL AND low_price > close_price)
            """
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("price_ohlc", f"bad_count={cnt}")
            else:
                log_error("price_ohlc", f"bad_count={cnt}")
    except Exception as e:
        log_error("price_ohlc", f"오류: {e}")

    try:
        cols = schema_cache["interest_shortsell_raw"]
        if "short_ratio" in cols:
            q = """
                SELECT COUNT(*)
                FROM interest_shortsell_raw
                WHERE short_ratio IS NOT NULL
                  AND (short_ratio < 0 OR short_ratio > 100)
            """
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("shortsell_ratio_range", f"bad_count={cnt}")
            else:
                log_warn("shortsell_ratio_range", f"bad_count={cnt}")

        if has_cols(cols, ["short_volume", "total_volume"]):
            q = """
                SELECT COUNT(*)
                FROM interest_shortsell_raw
                WHERE short_volume IS NOT NULL
                  AND total_volume IS NOT NULL
                  AND short_volume > total_volume
            """
            cnt = execute_query(cur, conn, q, fetch="val")
            if cnt == 0:
                log_ok("shortsell_volume_consistency", f"bad_count={cnt}")
            else:
                log_warn("shortsell_volume_consistency", f"bad_count={cnt}")
    except Exception as e:
        log_error("shortsell_consistency", f"오류: {e}")

    try:
        cols = schema_cache["interest_program_raw"]

        formula_checks = [
            ("program_arbitrage_volume_formula", "arbitrage_buy_volume", "arbitrage_sell_volume", "arbitrage_net_volume", PROGRAM_VOLUME_TOLERANCE),
            ("program_arbitrage_amount_formula", "arbitrage_buy_amount", "arbitrage_sell_amount", "arbitrage_net_amount", PROGRAM_AMOUNT_TOLERANCE),
            ("program_nonarb_volume_formula", "nonarb_buy_volume", "nonarb_sell_volume", "nonarb_net_volume", PROGRAM_VOLUME_TOLERANCE),
            ("program_nonarb_amount_formula", "nonarb_buy_amount", "nonarb_sell_amount", "nonarb_net_amount", PROGRAM_AMOUNT_TOLERANCE),
            ("program_total_volume_formula", "total_buy_volume", "total_sell_volume", "total_net_volume", PROGRAM_VOLUME_TOLERANCE),
            ("program_total_amount_formula", "total_buy_amount", "total_sell_amount", "total_net_amount", PROGRAM_AMOUNT_TOLERANCE),
        ]

        for check_name, buy_col, sell_col, net_col, tolerance in formula_checks:
            if has_cols(cols, [buy_col, sell_col, net_col]):
                q = f"""
                    SELECT COUNT(*)
                    FROM interest_program_raw
                    WHERE {buy_col} IS NOT NULL
                      AND {sell_col} IS NOT NULL
                      AND {net_col} IS NOT NULL
                      AND ABS(({buy_col} - {sell_col}) - {net_col}) > {tolerance}
                """
                cnt = execute_query(cur, conn, q, fetch="val")
                if cnt == 0:
                    log_ok(check_name, f"bad_count={cnt}")
                elif cnt <= 10:
                    log_warn(check_name, f"bad_count={cnt} | tolerance={tolerance}")
                else:
                    log_info(check_name, f"bad_count={cnt} | tolerance={tolerance}")
    except Exception as e:
        log_error("program_formula", f"오류: {e}")

# =========================================================
# 5. ROW COUNT CHECK
# =========================================================
def get_date_counts(cur, conn, table_name, date_col, limit=ROWCOUNT_LOOKBACK + 2):
    q = f"""
        SELECT {date_col} AS dt, COUNT(*) AS cnt
        FROM {table_name}
        WHERE {date_col} IS NOT NULL
        GROUP BY {date_col}
        ORDER BY {date_col} DESC
        LIMIT {limit}
    """
    return execute_query(cur, conn, q, fetch="all")

def validate_row_count(cur, conn):
    log_section("ROW COUNT CHECK")

    for table_name, spec in TABLE_SPECS.items():
        try:
            date_col = spec["date_col"]
            rows = get_date_counts(cur, conn, table_name, date_col)

            if len(rows) < 2:
                log_warn(f"{table_name}_rowcount", "insufficient_history")
                continue

            latest_dt, latest_cnt = rows[0]
            prev_dt, prev_cnt = rows[1]

            if prev_cnt == 0:
                log_warn(f"{table_name}_rowcount", f"{latest_dt}:{latest_cnt} vs {prev_dt}:{prev_cnt} | prev=0")
                continue

            ratio_prev = latest_cnt / prev_cnt

            trailing = [r[1] for r in rows[1:ROWCOUNT_LOOKBACK + 1]]
            avg_cnt = mean(trailing) if trailing else None
            ratio_avg = (latest_cnt / avg_cnt) if avg_cnt else None

            msg = f"{latest_dt}:{latest_cnt} vs {prev_dt}:{prev_cnt} | prev_ratio={ratio_prev:.2f}"
            if ratio_avg is not None:
                msg += f" | avg{len(trailing)}={avg_cnt:.1f} | avg_ratio={ratio_avg:.2f}"

            if ratio_prev < ROWCOUNT_ERROR_RATIO:
                log_error(f"{table_name}_rowcount", msg)
            elif ratio_prev < ROWCOUNT_WARN_RATIO:
                log_warn(f"{table_name}_rowcount", msg)
            else:
                log_ok(f"{table_name}_rowcount", msg)

        except Exception as e:
            log_error(f"{table_name}_rowcount", f"오류: {e}")

# =========================================================
# 6. GAP CHECK
# =========================================================
def validate_gap(cur, conn):
    log_section("GAP CHECK")

    today = datetime.now(SEOUL_TZ).date()
    end_dt = today - timedelta(days=1)

    cache = {}
    kr = lambda d: get_holiday_info(d, "KR", cache)
    us = lambda d: get_holiday_info(d, "US", cache)

    # 🔥 KRX 강제 휴일 (핵심)
    KRX_FORCE_HOLIDAYS = {
        date(2025, 12, 31),
        date(2026, 3, 2),
    }

    GAP_RULES = {
        "interest_news_raw": "IGNORE",
        "interest_agency_raw": "IGNORE",

        "interest_foreignindex_raw": {"market": "US", "tolerance": 2},
        "interest_commodity_raw": {"market": "US", "tolerance": 2},
        "interest_macroeconomic_raw": {"market": "US", "tolerance": 3},

        "interest_price_raw": {"market": "KR", "tolerance": 5},
        "interest_investorflow_raw": {"market": "KR", "tolerance": 5},
        "interest_program_raw": {"market": "KR", "tolerance": 10},
        "interest_shortsell_raw": {"market": "KR", "tolerance": 5},
        "interest_marketbreadth_raw": {"market": "KR", "tolerance": 5},
    }

    for table_name, spec in TABLE_SPECS.items():
        try:
            rule = GAP_RULES.get(table_name)

            if rule == "IGNORE":
                log_info(f"{table_name}_gap", "SKIP (event-driven data)")
                continue

            date_col = spec["date_col"]
            market = rule["market"]
            tolerance = rule["tolerance"]

            start_dt = today - timedelta(days=GAP_LOOKBACK_DAYS)

            expected_dates = []
            d = start_dt

            while d <= end_dt:
                if market == "KR":
                    # 🔥 핵심 수정
                    if d in KRX_FORCE_HOLIDAYS:
                        d += timedelta(days=1)
                        continue

                    if not kr(d)["is_non_business_day"]:
                        expected_dates.append(d)
                else:
                    if not us(d)["is_non_business_day"]:
                        expected_dates.append(d)

                d += timedelta(days=1)

            # 실제 데이터
            q = f"""
                SELECT DISTINCT {date_col}
                FROM {table_name}
                WHERE {date_col} BETWEEN %s AND %s
            """
            actual_dates = execute_query(cur, conn, q, (start_dt, end_dt), fetch="all")
            actual_dates = {r[0] for r in actual_dates if r[0] is not None}

            # gap 계산
            missing = [d for d in expected_dates if d not in actual_dates]
            gap_count = len(missing)

            sample = ", ".join([str(d) for d in missing[:3]])

            msg = f"gap_count={gap_count} | tolerance={tolerance}"
            if sample:
                msg += f" | sample={sample}"

            if gap_count == 0:
                log_ok(f"{table_name}_gap", msg)
            elif gap_count <= tolerance:
                log_warn(f"{table_name}_gap", msg)
            else:
                log_error(f"{table_name}_gap", msg)

        except Exception as e:
            log_error(f"{table_name}_gap", f"오류: {e}")
            
# =========================================================
# 7. SOURCE / VERSION CHECK
# =========================================================
def validate_source_distribution(cur, conn, schema_cache):
    log_section("SOURCE / VERSION CHECK")

    for table_name, spec in TABLE_SPECS.items():
        try:
            cols = schema_cache[table_name]
            source_cols = spec.get("source_cols", [])
            if not has_cols(cols, source_cols):
                log_info(f"{table_name}_source", "SKIP | no source/version cols")
                continue

            source_col, version_col = source_cols
            q = f"""
                SELECT COALESCE({source_col}::text, 'NULL') AS source,
                       COALESCE({version_col}::text, 'NULL') AS version,
                       COUNT(*) AS cnt
                FROM {table_name}
                GROUP BY 1,2
                ORDER BY cnt DESC
                LIMIT {SOURCE_LIMIT}
            """
            rows = execute_query(cur, conn, q, fetch="all")

            if not rows:
                log_warn(f"{table_name}_source", "no rows")
                continue

            msg = " | ".join([f"{r[0]}/{r[1]}={r[2]}" for r in rows])
            log_ok(f"{table_name}_source", msg)

        except Exception as e:
            log_error(f"{table_name}_source", f"오류: {e}")

# =========================================================
# 8. PROFILE CHECK
# =========================================================
def validate_profile(cur, conn, schema_cache):
    log_section("PROFILE CHECK")

    targets = [
        ("interest_price_raw", "price_date", "close_price"),
        ("interest_foreignindex_raw", "date", "close_price"),
        ("interest_commodity_raw", "date", "price"),
    ]

    for table_name, date_col, value_col in targets:
        try:
            cols = schema_cache[table_name]
            if not has_cols(cols, [date_col, value_col]):
                log_info(f"{table_name}_profile", "SKIP | missing cols")
                continue

            latest_dt = query_latest_date(cur, conn, table_name, date_col)
            if latest_dt is None:
                log_warn(f"{table_name}_profile", "no latest date")
                continue

            q = f"""
                SELECT COUNT(*) AS cnt,
                       MIN({value_col}) AS min_val,
                       MAX({value_col}) AS max_val,
                       AVG({value_col}) AS avg_val
                FROM {table_name}
                WHERE {date_col} = %s
                  AND {value_col} IS NOT NULL
            """
            cnt, min_val, max_val, avg_val = execute_query(cur, conn, q, (latest_dt,), fetch="one")

            if cnt == 0:
                log_warn(f"{table_name}_profile", f"{latest_dt} | no values")
                continue

            log_ok(
                f"{table_name}_profile",
                f"{latest_dt} | cnt={cnt} | min={min_val} | max={max_val} | avg={round(float(avg_val), 4)}"
            )
        except Exception as e:
            log_error(f"{table_name}_profile", f"오류: {e}")

# =========================================================
# 9. TOTAL COUNT CHECK
# =========================================================
def validate_total_count(cur, conn):
    log_section("TOTAL COUNT CHECK")

    for table_name in TABLE_SPECS.keys():
        try:
            cnt = query_total_count(cur, conn, table_name)
            if cnt == 0:
                log_error(f"{table_name}_total", f"row_count={cnt}")
            else:
                log_ok(f"{table_name}_total", f"row_count={cnt}")
        except Exception as e:
            log_error(f"{table_name}_total", f"오류: {e}")

# =========================================================
# 10. SCHEMA CACHE
# =========================================================
def build_schema_cache(cur, conn):
    cache = {}
    log_section("SCHEMA CHECK")

    for table_name in TABLE_SPECS.keys():
        try:
            cols = get_table_columns(cur, conn, table_name)
            cache[table_name] = cols
            log_ok(table_name, f"column_count={len(cols)}")
        except Exception as e:
            cache[table_name] = set()
            log_error(table_name, f"오류: {e}")

    return cache

# =========================================================
# FINAL SUMMARY
# =========================================================
def print_summary():
    log_section("FINAL SUMMARY")
    print(f"OK     : {RESULT.ok}")
    print(f"WARN   : {RESULT.warn}")
    print(f"ERROR  : {RESULT.error}")
    print(f"INFO   : {RESULT.info}")
    print("DONE")

# =========================================================
# MAIN
# =========================================================
def run():
    print("\n" + "=" * 100)
    print("INTEREST DATA VALIDATION")
    print("=" * 100)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        schema_cache = build_schema_cache(cur, conn)

        validate_date(cur, conn)
        validate_null(cur, conn, schema_cache)
        validate_duplicate(cur, conn, schema_cache)
        validate_domain_generic(cur, conn, schema_cache)
        validate_domain_specific(cur, conn, schema_cache)
        validate_row_count(cur, conn)
        validate_gap(cur, conn)
        validate_source_distribution(cur, conn, schema_cache)
        validate_profile(cur, conn, schema_cache)
        validate_total_count(cur, conn)

    except Exception as e:
        log_section("FATAL ERROR")
        print(str(e))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    print_summary()

if __name__ == "__main__":
    run()