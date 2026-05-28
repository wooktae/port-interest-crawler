# CHANGELOG

## Unreleased

### Added

- `docs/database.md`에 portfolio 단일 DB와 schema-per-domain 구조, interest 모듈 `search_path` 기준을 추가했다.
- `docs/source-file-catalog.md`에 주요 소스/문서 파일별 역할, 책임, 운영 주의사항을 추가했다.
- Python 스크립트 상단에 한글 module docstring을 추가해 파일별 실행 영향과 외부/DB 의존성을 설명했다.

### Changed

- DB name 기본값을 `portfolio`로 문서화하고 `INTEREST_DB_NAME`, `PORTFOLIO_DB_NAME` 설명을 같은 기본값 기준으로 정리했다.
- schema-per-domain 전환 후에도 기존 SQL이 `interest, reference, legacy, public` search_path 기반으로 동작한다는 설명을 추가했다.
- AWS Migration 준비 관점에서 단일 DB `portfolio` 안의 domain schema 구조를 사용한다고 명시했다.
- 민감정보는 환경변수 또는 로컬 설정으로 관리하고 실제 password/token/account/webhook 값은 문서에 기록하지 않는 기준을 보강했다.

### Docs

- README에 파일 카탈로그 위치와 주석 작성 기준을 추가했다.
- `docs/worklog/2026-05-28.md`에 파일 카탈로그/주석 정리 작업 기록을 추가했다.
- 기능 변경 없음.

## 2026-05-27

### Changed

- DB 접속정보를 `db_config.py`의 `get_db_config()`로 공통화하고 `INTEREST_DB_*` 환경변수 기반으로 외부화했다.
- Python 스크립트에 있던 DB password 하드코딩 후보를 제거했다.

### Docs

- README에 `INTEREST_DB_*` 환경변수 설명과 placeholder 기반 설정 예시를 추가했다.

### Notes

- 실제 DB 접속, 크롤링, 외부 API 호출, Selenium/Chrome 실행, 주문 실행은 수행하지 않았다.

## 2026-05-26

### Changed

- 1차 unused/legacy 정리 결과를 README 구조 설명에 반영했다.
- 삭제된 test/debug/dump/legacy 후보 파일 참조를 문서에서 제거했다.

### Added

- 초기 프로젝트 문서 초안을 추가했다.
  - `AGENTS.md`
  - `README.md`
  - `docs/worklog/2026-05-26.md`

### Notes

- 현재 로컬 파일 구조와 스크립트 import/entrypoint 확인 결과를 기준으로 작성했다.
- 실제 크롤링, 외부 API 호출, Selenium/Chrome/KRX/Naver/yfinance 요청, DB DDL/DML, 주문 실행은 수행하지 않았다.
- 민감정보 값은 문서에 기록하지 않았다.
