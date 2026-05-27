import psycopg2
from db_config import get_db_config
import psycopg2.extras
import json
from datetime import datetime, timedelta

from interest_log_format import print_step_log


DB_CONFIG = get_db_config()

SOURCE = "internal"
SOURCE_VERSION = "2.1.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_latest_date(conn):

    cur = conn.cursor()

    cur.execute("""
        SELECT MAX(date)
        FROM interest_marketbreadth_raw
    """)

    row = cur.fetchone()
    cur.close()

    return row[0]


def calculate_marketbreadth(conn, start_date):

    cur = conn.cursor()

    sql = """
    WITH base AS (
        SELECT
            ticker_code,
            price_date,
            close_price,
            LAG(close_price) OVER (
                PARTITION BY ticker_code
                ORDER BY price_date
            ) AS prev_close
        FROM interest_price_raw
    ),
    diff AS (
        SELECT
            price_date,
            CASE WHEN close_price > prev_close THEN 1 ELSE 0 END AS adv,
            CASE WHEN close_price < prev_close THEN 1 ELSE 0 END AS dec,
            CASE WHEN close_price = prev_close THEN 1 ELSE 0 END AS unc
        FROM base
        WHERE prev_close IS NOT NULL
    )
    SELECT
        price_date,
        SUM(adv),
        SUM(dec),
        SUM(unc)
    FROM diff
    WHERE price_date >= %s
    GROUP BY price_date
    ORDER BY price_date;
    """

    cur.execute(sql, (start_date,))
    rows = cur.fetchall()

    now = datetime.now()

    records = []

    for r in rows:

        records.append({
            "date": r[0],
            "advancers_count": int(r[1]),
            "decliners_count": int(r[2]),
            "unchanged_count": int(r[3]),
            "total_market_volume": None,
            "raw_json": json.dumps({
                "advancers": int(r[1]),
                "decliners": int(r[2]),
                "unchanged": int(r[3])
            }),
            "collected_at": now,
            "as_of_ts": now,
            "as_of_date": r[0],
            "source": SOURCE,
            "source_version": SOURCE_VERSION
        })

    cur.close()

    return records


def save_rows(conn, records):

    if not records:
        return 0

    sql = """
    INSERT INTO interest_marketbreadth_raw (
        date,
        advancers_count,
        decliners_count,
        unchanged_count,
        total_market_volume,
        raw_json,
        collected_at,
        as_of_ts,
        as_of_date,
        source,
        source_version
    )
    VALUES (
        %(date)s,
        %(advancers_count)s,
        %(decliners_count)s,
        %(unchanged_count)s,
        %(total_market_volume)s,
        %(raw_json)s,
        %(collected_at)s,
        %(as_of_ts)s,
        %(as_of_date)s,
        %(source)s,
        %(source_version)s
    )
    ON CONFLICT (date)
    DO UPDATE SET
        advancers_count = EXCLUDED.advancers_count,
        decliners_count = EXCLUDED.decliners_count,
        unchanged_count = EXCLUDED.unchanged_count,
        raw_json = EXCLUDED.raw_json,
        as_of_ts = EXCLUDED.as_of_ts,
        updated_at = now();
    """

    cur = conn.cursor()
    psycopg2.extras.execute_batch(cur, sql, records, page_size=200)
    cur.close()

    return len(records)


# -----------------------------
# run (🔥 여기서 로그 직접 찍는다)
# -----------------------------
def run():

    conn = get_conn()

    try:

        latest = get_latest_date(conn)

        if latest is None:
            start_date = "2007-01-01"
        else:
            start_date = latest + timedelta(days=1)

        records = calculate_marketbreadth(conn, start_date)

        if not records:

            result = {
                "status": "NO_CHANGE",
                "collected_dates": [],
                "success_lines": [],
                "error_lines": [],
                "failed_lines": [],
                "error_count": 0
            }

            print_step_log("interest_marketbreadth", result)
            conn.close()
            return result

        saved = save_rows(conn, records)
        conn.commit()

        collected_dates = sorted(list(set(str(r["date"]) for r in records)))

        success_lines = [
            f"{d} Collected"
            for d in collected_dates
        ]

        result = {
            "status": "SUCCESS",
            "collected_dates": collected_dates,
            "success_lines": success_lines,
            "error_lines": [],
            "failed_lines": [],
            "error_count": 0
        }

        print_step_log("interest_marketbreadth", result)
        conn.close()
        return result

    except Exception as e:

        result = {
            "status": "FAILED",
            "collected_dates": [],
            "success_lines": [],
            "error_lines": [],
            "failed_lines": [str(e)],
            "error_count": 1
        }

        print_step_log("interest_marketbreadth", result)
        conn.close()
        return result


if __name__ == "__main__":
    run()