"""Local inspection script that consolidates the DDL and sample data of the schema-per-domain structure.

Using pg_dump and PostgreSQL queries, it consolidates the DDL, row count, and sample data
per schema/table into a single text file. This is not an operational collection source but a
local inspection/documentation candidate script prior to the AWS Migration.

Notes:
- Performs only DB reads and local file creation.
- The default targets are the schemas after the schema-per-domain transition of the portfolio DB.
- The pg_dump path can be overridden via the PG_DUMP_PATH environment variable.
"""

import os
import subprocess
from pathlib import Path

import psycopg2
from db_config import get_db_config
from psycopg2 import sql


DB_CONFIG = get_db_config()

# Based on the 2026-05 schema-per-domain layout.
# If needed, this can be overridden at run time via the DUMP_SCHEMAS="reference,interest,..." environment variable.
DEFAULT_SCHEMAS = [
    "reference",
    "interest",
    "preprocessor",
    "research",
    "decision",
    "execution",
    "connector",
    "ops",
    "legacy",
]

SCHEMAS = [
    s.strip()
    for s in os.getenv("DUMP_SCHEMAS", ",".join(DEFAULT_SCHEMAS)).split(",")
    if s.strip()
]

LIMIT = int(os.getenv("DUMP_SAMPLE_LIMIT", "20"))

PG_DUMP = os.getenv(
    "PG_DUMP_PATH",
    r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
)

OUTPUT_FILE = os.getenv("DUMP_OUTPUT_FILE", "ALL_SCHEMA_TABLE_DUMP.txt")

ORDER_PRIORITY = [
    "created_at",
    "updated_at",
    "date",
    "run_date",
    "data_date",
    "published_at",
    "period",
    "as_of_date",
    "id",
]


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def get_existing_schemas(conn):
    """Return only the schemas that actually exist in the DB among the requested schemas."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = ANY(%s)
            ORDER BY array_position(%s, schema_name)
            """,
            (SCHEMAS, SCHEMAS),
        )
        return [r[0] for r in cur.fetchall()]


def get_tables(conn, schemas):
    """Return the schema/table list based on the schema-per-domain layout."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = ANY(%s)
              AND table_type = 'BASE TABLE'
            ORDER BY array_position(%s, table_schema), table_name
            """,
            (schemas, schemas),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def get_columns(conn, schema_name, table_name):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_name),
        )
        return [r[0] for r in cur.fetchall()]


def build_order_clause(cols):
    for c in ORDER_PRIORITY:
        if c in cols:
            return sql.SQL(" ORDER BY {} DESC").format(sql.Identifier(c))
    return sql.SQL("")


def get_row_count(conn, schema_name, table_name):
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
            )
        )
        return cur.fetchone()[0]


def compact_text(text, max_blank_lines=1):
    """
    Reduce consecutive blank lines, keeping at most max_blank_lines of them.
    With the default of 1, at most one blank line is allowed.
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


def clean_pg_dump_ddl(text):
    """
    Remove the repeated headers/footers and SET options from the pg_dump schema-only output,
    keeping only the DDL centered on the actual CREATE/ALTER/INDEX/TRIGGER statements.
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


def get_ddl(schema_name, table_name):
    cmd = [
        PG_DUMP,
        "-h",
        DB_CONFIG["host"],
        "-p",
        str(DB_CONFIG["port"]),
        "-U",
        DB_CONFIG["user"],
        "-d",
        DB_CONFIG["dbname"],
        "-t",
        f'{schema_name}.{table_name}',
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--encoding=UTF8",
    ]

    env = os.environ.copy()
    password = DB_CONFIG.get("password")
    if password:
        env["PGPASSWORD"] = password

    result = subprocess.run(cmd, capture_output=True, env=env)

    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    if result.returncode != 0:
        return compact_text(f"-- ERROR\n{stderr}\n{stdout}", max_blank_lines=0)

    return clean_pg_dump_ddl(stdout)


def get_sample(conn, schema_name, table_name, order_clause):
    with conn.cursor() as cur:
        query = sql.SQL("SELECT * FROM {}.{}{}").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
            order_clause,
        ) + sql.SQL(" LIMIT %s")
        cur.execute(query, (LIMIT,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return cols, rows


def format_value(value):
    if value is None:
        return "NULL"

    text = str(value)
    if len(text) > 200:
        return text[:200] + "..."
    return text


def format_row(row):
    return " | ".join(format_value(v) for v in row)


def write_header(f, existing_schemas, tables):
    f.write("=" * 100 + "\n")
    f.write("SCHEMA-PER-DOMAIN TABLE DUMP\n")
    f.write("=" * 100 + "\n")
    f.write(f"DATABASE: {DB_CONFIG.get('dbname')}\n")
    f.write(f"SCHEMAS: {', '.join(existing_schemas)}\n")
    f.write(f"TOTAL TABLES: {len(tables)}\n")
    f.write(f"SAMPLE LIMIT: {LIMIT}\n")
    f.write("\n")


def main():
    output_file = Path.cwd() / OUTPUT_FILE

    conn = get_conn()
    try:
        existing_schemas = get_existing_schemas(conn)
        missing_schemas = [s for s in SCHEMAS if s not in existing_schemas]
        tables = get_tables(conn, existing_schemas)

        print("SCHEMAS:", ", ".join(existing_schemas))
        if missing_schemas:
            print("MISSING SCHEMAS:", ", ".join(missing_schemas))
        print("TOTAL TABLES:", len(tables))

        with open(output_file, "w", encoding="utf-8", errors="replace") as f:
            write_header(f, existing_schemas, tables)

            for idx, (schema_name, table_name) in enumerate(tables, 1):
                full_name = f"{schema_name}.{table_name}"
                print(f"[{idx}/{len(tables)}] {full_name}")

                cols = get_columns(conn, schema_name, table_name)
                order_clause = build_order_clause(cols)
                row_count = get_row_count(conn, schema_name, table_name)
                ddl = get_ddl(schema_name, table_name)

                try:
                    sample_cols, sample_rows = get_sample(
                        conn,
                        schema_name,
                        table_name,
                        order_clause,
                    )
                    sample_error = None
                except Exception as e:
                    conn.rollback()
                    sample_cols = []
                    sample_rows = []
                    sample_error = str(e)

                f.write("=" * 100 + "\n")
                f.write(f"{idx}. TABLE: {full_name}\n")
                f.write("=" * 100 + "\n")

                f.write("[DDL]\n")
                f.write(ddl.strip() + "\n")

                f.write("[ROW COUNT]\n")
                f.write(str(row_count) + "\n")

                f.write(f"[SAMPLE DATA - {LIMIT} ROWS]\n")
                if sample_rows:
                    f.write(" | ".join(sample_cols) + "\n")
                    f.write("-" * 80 + "\n")
                    for row in sample_rows:
                        f.write(format_row(row) + "\n")
                elif sample_error:
                    f.write(f"(ERROR: {sample_error})\n")
                else:
                    f.write("(NO DATA)\n")

                f.write("\n")
    finally:
        conn.close()

    print("\nDONE")
    print("OUTPUT FILE:", output_file)


if __name__ == "__main__":
    main()
