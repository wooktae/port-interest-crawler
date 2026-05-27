import psycopg2
from db_config import get_db_config
import json
from datetime import datetime

DB_CONFIG = get_db_config()

SOURCE = "internal"
SOURCE_VERSION = "2.0.0"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def calculate_marketbreadth(conn):

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
        FROM price_history

    ),

    diff AS (

        SELECT
            price_date,
            CASE
                WHEN close_price > prev_close THEN 1
                ELSE 0
            END AS adv,
            CASE
                WHEN close_price < prev_close THEN 1
                ELSE 0
            END AS dec,
            CASE
                WHEN close_price = prev_close THEN 1
                ELSE 0
            END AS unc
        FROM base
        WHERE prev_close IS NOT NULL

    )

    SELECT
        price_date,
        SUM(adv),
        SUM(dec),
        SUM(unc)
    FROM diff
    GROUP BY price_date
    ORDER BY price_date;
    """

    cur.execute(sql)

    rows = cur.fetchall()

    records = []

    now = datetime.now()

    for r in rows:

        record = {

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
        }

        records.append(record)

    cur.close()

    return records


def save(records):

    conn = get_conn()
    cur = conn.cursor()

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

    cur.executemany(sql, records)

    conn.commit()

    cur.close()
    conn.close()


def run():

    print("===== MARKETBREADTH BUILD START =====")

    conn = get_conn()

    records = calculate_marketbreadth(conn)

    conn.close()

    save(records)

    print("rows saved:", len(records))

    print("===== DONE =====")


if __name__ == "__main__":
    run()