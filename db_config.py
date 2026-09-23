"""Provides shared PostgreSQL connection settings for the interest collection scripts.

DB connection values are read from environment variables, and the actual password value is never left in code or documentation.
Each collection/validation script uses the same DB defaults and search_path through this module.
"""

import os


def get_db_config():
    """Return the environment-variable-based DB connection settings and an interest-first search_path."""
    password = os.getenv("INTEREST_DB_PASSWORD", "")
    if not password:
        raise RuntimeError("INTEREST_DB_PASSWORD environment variable is required")

    return {
        "host": os.getenv("INTEREST_DB_HOST", "localhost"),
        "port": int(os.getenv("INTEREST_DB_PORT", "5433")),
        "dbname": os.getenv("INTEREST_DB_NAME", "portfolio"),
        "user": os.getenv("INTEREST_DB_USER", "postgres"),
        "password": password,
        "options": "-c search_path=interest,reference,legacy,public",
    }
