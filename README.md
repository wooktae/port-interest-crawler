# port-interest-crawler

포트폴리오 관심 데이터 수집을 담당하는 Python 마이크로서비스 루트다. Naver, yfinance, KRX 등 외부 데이터 원천에서 가격, 뉴스, 리서치, 투자자 수급, 공매도, 프로그램 매매, 매크로/원자재/해외지수 데이터를 수집하고 PostgreSQL raw/history 계열 테이블에 적재하는 스크립트들이 모여 있다.

이 문서는 현재 로컬 파일 구조와 import/entrypoint 확인 결과를 기준으로 작성했다. 실제 크롤링, 외부 API 호출, Selenium/Chrome 실행, yfinance 요청, DB DDL/DML, 주문 실행은 수행하지 않았다.

## 현재 구조

현재 루트는 패키지 디렉터리보다 독립 실행형 Python 스크립트 중심이다.

- 운영/일일 수집 후보
  - `interest_crawler_daily.py`
  - `interest_crawler_main.py`
  - `interest_price.py`
  - `interest_marketbreadth.py`
  - `interest_foreignindex.py`
  - `interest_macroeconomic.py`
  - `interest_commodity.py`
  - `interest_investorflow.py`
  - `interest_agency.py`
  - `interest_news.py`
  - `interest_program.py`
  - `interest_shortsell.py`
  - `interest_ticker_main.py`
  - `interest_ticker_value.py`
  - `interest_ticker_finance.py`
- history/backfill 후보
  - `interest_price_history.py`
  - `interest_marketbreadth_history.py`
  - `interest_foreignindex_history.py`
  - `interest_macroeconomic_history.py`
  - `interest_commodity_history.py`
  - `interest_investorflow_history.py`
  - `interest_agency_history.py`
  - `interest_news_history.py`
  - `interest_program_history.py`
  - `interest_shortsell_history.py`
- validation/check 후보
  - `interest_data_validate_daily.py`
  - `interest_data_validate_all.py`
  - `interest_price_check.py`
- KRX/Selenium/Chrome 관련 후보
  - `interest_krx_chrome.py`
  - `interest_krx_login_new.py`
  - `interest_program.py`
  - `interest_program_history.py`
  - `interest_shortsell.py`
  - `interest_shortsell_history.py`
- universe/sector 구성 후보
  - `build_stock_universe.py`
  - `build_sector_mapping.py`
  - `build_universe_sector.py`
- legacy 또는 로컬 실험 후보
  - `dump_public_schema_final.py`
  - `block_watch_backtest_run.py`

`test`, `debug`, HTML dump, 임시 파일처럼 보이는 로컬 산출물은 1차 정리에서 제거했다. 이후 새로 생성되는 임시 산출물은 운영 소스로 단정하지 않고 별도 후보로 취급한다.

## 주요 기능

- Naver 금융/뉴스 기반 리서치, 뉴스, 투자자 수급, 티커 기초/가치/재무 데이터 수집
- yfinance 기반 국내외 가격, 해외지수, 매크로, 원자재 데이터 수집
- KRX 웹/Selenium 기반 공매도, 프로그램 매매 데이터 수집
- PostgreSQL raw/history 계열 테이블 적재
- 일일 수집 orchestration 후보와 history/backfill 스크립트 분리
- 데이터 품질 검증 및 gap/check 스크립트 제공
- stock universe와 sector mapping 구성 후보 제공

## 실행 방법

각 스크립트는 독립 실행형 entrypoint를 가진 파일이 많다. 다만 실행 시 외부 네트워크, Selenium/Chrome, KRX 로그인, yfinance 요청, DB 연결 및 upsert가 발생할 수 있으므로 운영 환경에서만 의도적으로 실행해야 한다.

예시 형식:

```powershell
python interest_crawler_daily.py
```

history/backfill 스크립트는 장기간 데이터를 요청하고 DB에 대량 적재할 수 있다. 실행 전 대상 기간, DB 연결, unique key/upsert 정책, 외부 원천 제한을 확인해야 한다.

validation/check 스크립트도 DB 연결 또는 외부 요청이 포함될 수 있으므로 문서화/분석 작업 중에는 실행하지 않는다.

## 설정 방법

현재 스크립트들은 DB 접속정보, KRX/Naver/yfinance 관련 설정, Chrome/ChromeDriver 경로, 환경변수 기반 credential을 사용할 수 있다.

민감정보는 코드, 문서, 로그, 예시 출력에 기록하지 않는다. 필요한 값은 환경변수 또는 local config로 분리하고 문서에는 `[REDACTED]`로 마스킹한다.

### DB 접속 환경변수

DB 접속정보는 `db_config.py`의 `get_db_config()`에서 `INTEREST_DB_*` 환경변수로 읽는다. 각 스크립트는 기존처럼 단독 실행할 수 있지만, 실행 전에 `INTEREST_DB_PASSWORD`는 반드시 설정해야 한다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `INTEREST_DB_HOST` | `localhost` | PostgreSQL host |
| `INTEREST_DB_PORT` | `5433` | PostgreSQL port |
| `INTEREST_DB_NAME` | `interest_crawler` | PostgreSQL database name |
| `INTEREST_DB_USER` | `postgres` | PostgreSQL user |
| `INTEREST_DB_PASSWORD` | 없음 | PostgreSQL password. 비어 있으면 실행 시 `RuntimeError`가 발생한다. |

PowerShell 설정 예시:

```powershell
$env:INTEREST_DB_HOST="localhost"
$env:INTEREST_DB_PORT="5433"
$env:INTEREST_DB_NAME="interest_crawler"
$env:INTEREST_DB_USER="postgres"
$env:INTEREST_DB_PASSWORD="[REDACTED]"
```

주요 설정 유형:

- PostgreSQL host, port, database, user, password
- Chrome 또는 ChromeDriver 경로
- KRX 로그인 관련 환경변수
- Naver API client id/secret
- 외부 데이터 원천별 URL, user-agent, timeout
- 수집 대상 ticker, market, date range

## 외부 의존성

현재 파일에서 확인되는 주요 의존성 후보는 다음과 같다.

- Python
- `requests`
- `beautifulsoup4`
- `psycopg` 또는 `psycopg2`
- `yfinance`
- `selenium`
- PostgreSQL
- Chrome 또는 ChromeDriver
- Naver Finance / Naver News / Naver Open API
- KRX data portal

외부 API, 웹 크롤링, yfinance, Selenium/Chrome 호출은 운영 영향이 있으므로 분석 또는 문서 작업 중에는 실행하지 않는다.

## 안전 제약

- 실제 크롤링 실행 금지
- 외부 API 호출 금지
- Selenium/Chrome/KRX/Naver/yfinance 요청 실행 금지
- DB DDL/DML 직접 실행 금지
- 주문 제출 또는 주문 실행 금지
- 민감정보 값 출력 또는 문서 기록 금지
- 민감정보가 필요하면 `[REDACTED]`로 마스킹

## 검증

문서만 수정한 경우에는 변경 범위만 확인한다.

```powershell
git status --short
git diff --stat
```

코드 수정 시에는 외부 요청, 크롤링, DB 쓰기, 주문 실행이 포함되지 않는 검증만 선택한다. 실행 위험이 있으면 완료 보고에 검증 한계를 남긴다.
