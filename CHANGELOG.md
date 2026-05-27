# CHANGELOG

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
