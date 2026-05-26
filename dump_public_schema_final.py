import os
import subprocess
from pathlib import Path

import psycopg2
from psycopg2 import sql


DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "interest_crawler",
    "user": "postgres",
    "password": "doflwhsk3768!"
}

SCHEMA = "public"
LIMIT = 20

PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"

ORDER_PRIORITY = [
    "created_at",
    "updated_at",
    "date",
    "published_at",
    "period",
    "as_of_date",
    "id"
]


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (SCHEMA,))
        return [r[0] for r in cur.fetchall()]


def get_columns(conn, table):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
        """, (SCHEMA, table))
        return [r[0] for r in cur.fetchall()]


def build_order_clause(cols):
    for c in ORDER_PRIORITY:
        if c in cols:
            return f'ORDER BY "{c}" DESC'
    return ""


def get_row_count(conn, table):
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(SCHEMA),
            sql.Identifier(table)
        ))
        return cur.fetchone()[0]

def clean_pg_dump_ddl(text):
    """
    pg_dump schema-only 결과에서 반복 헤더/푸터와 SET 옵션을 제거하고,
    실제 CREATE/ALTER/INDEX/TRIGGER 중심 DDL만 남김.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    remove_prefixes = (
        "-- PostgreSQL database dump",
        "-- Dumped from database version",
        "-- Dumped by pg_dump version",
        "-- PostgreSQL database dump complete",
        "\\restrict",
        "\\unrestrict",
        "SET ",
        "SELECT pg_catalog.set_config",
    )

    kept = []
    for line in text.split("\n"):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith(remove_prefixes):
            continue
        
        if stripped.startswith("--"):
            continue
        
        kept.append(line.rstrip())

    return "\n".join(kept).strip()

def get_ddl(table):
    cmd = [
        PG_DUMP,
        "-h", DB_CONFIG["host"],
        "-p", str(DB_CONFIG["port"]),
        "-U", DB_CONFIG["user"],
        "-d", DB_CONFIG["dbname"],
        "-t", f"{SCHEMA}.{table}",
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--encoding=UTF8"
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = DB_CONFIG["password"]

    result = subprocess.run(cmd, capture_output=True, env=env)

    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    if result.returncode != 0:
        return compact_text(f"-- ERROR\n{stderr}\n{stdout}", max_blank_lines=0)

    return clean_pg_dump_ddl(stdout)


def get_sample(conn, table, order_clause):
    with conn.cursor() as cur:
        query = f'SELECT * FROM "{SCHEMA}"."{table}" {order_clause} LIMIT {LIMIT}'
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return cols, rows


def format_row(row):
    out = []
    for v in row:
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + "..."
        out.append(str(v))
    return " | ".join(out)

def compact_text(text, max_blank_lines=1):
    """
    연속된 공백줄을 max_blank_lines 개수만 남기고 줄임.
    기본값 1이면 빈 줄은 최대 1줄만 허용.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    compacted = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= max_blank_lines:
                compacted.append("")
        else:
            blank_count = 0
            compacted.append(line.rstrip())

    return "\n".join(compacted).strip()

def main():

    output_file = Path.cwd() / "ALL_TABLE_DUMP.txt"

    conn = get_conn()
    tables = get_tables(conn)

    print("TOTAL TABLES:", len(tables))

    with open(output_file, "w", encoding="utf-8", errors="replace") as f:

        for idx, table in enumerate(tables, 1):

            print(f"[{idx}/{len(tables)}] {table}")

            cols = get_columns(conn, table)
            order_clause = build_order_clause(cols)

            row_count = get_row_count(conn, table)

            ddl = get_ddl(table)

            try:
                sample_cols, sample_rows = get_sample(conn, table, order_clause)
            except Exception as e:
                sample_cols = []
                sample_rows = []
                sample_error = str(e)

            # ==========================
            # WRITE
            # ==========================
            f.write("=" * 100 + "\n")
            f.write(f"{idx}. TABLE: {table}\n")
            f.write("=" * 100 + "\n")

            # DDL
            f.write("[DDL]\n")
            f.write(ddl.strip() + "\n")

            # ROW COUNT
            f.write("[ROW COUNT]\n")
            f.write(str(row_count) + "\n")

            # SAMPLE
            f.write("[SAMPLE DATA - 20 ROWS]\n")

            if sample_rows:
                f.write(" | ".join(sample_cols) + "\n")
                f.write("-" * 80 + "\n")
                for r in sample_rows:
                    f.write(format_row(r) + "\n")
            else:
                f.write("(NO DATA OR ERROR)\n")

            f.write("\n")
    conn.close()

    print("\nDONE")
    print("OUTPUT FILE:", output_file)


if __name__ == "__main__":
    main()