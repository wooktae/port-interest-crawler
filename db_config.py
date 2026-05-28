"""interest 수집 스크립트의 PostgreSQL 접속 설정을 공통으로 만든다.

DB 접속값은 환경변수에서 읽고, 실제 password 값은 코드나 문서에 남기지 않는다.
각 수집/검증 스크립트는 이 모듈을 통해 동일한 DB 기본값과 search_path를 사용한다.
"""

import os


def get_db_config():
    """환경변수 기반 DB 접속 설정과 interest 우선 search_path를 반환한다."""
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
