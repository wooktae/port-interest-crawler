# port-interest-crawler

포트폴리오 관심 데이터 수집을 담당하는 Python 마이크로서비스 루트다. Naver, yfinance, KRX 등 외부 데이터 원천에서 가격, 뉴스, 리서치, 투자자 수급, 공매도, 프로그램 매매, 매크로/원자재/해외지수 데이터를 수집하고 PostgreSQL raw/history 계열 테이블에 적재하는 스크립트들이 모여 있다.

이 문서는 현재 로컬 파일 구조와 import/entrypoint 확인 결과를 기준으로 작성했다. 실제 크롤링, 외부 API 호출, Selenium/Chrome 실행, yfinance 요청, DB DDL/DML, 주문 실행은 수행하지 않았다.

## 현재 구조

현재 루트는 패키지 디렉터리보다 독립 실행형 Python 스크립트 중심이다.

- 운영/일일 수집 후보
  - `interest_crawler_daily.py`
  - `interest_crawler_daily_nongui.py`
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
  - `interest_krx_raw_validate_daily.py`
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
  - `patch_research_decision_dependency.py`

`test`, `debug`, HTML dump, 임시 파일처럼 보이는 로컬 산출물은 1차 정리에서 제거했다. 이후 새로 생성되는 임시 산출물은 운영 소스로 단정하지 않고 별도 후보로 취급한다.

전체 파일별 역할, 주요 책임, 운영 주의사항은 `docs/source-file-catalog.md`에 정리한다. AWS Migration 전 초기 정리에서는 unused/legacy 의심 파일도 삭제하지 않고 “정리 후보”로만 표시한다.

## 주요 기능

- Naver 금융/뉴스 기반 리서치, 뉴스, 투자자 수급, 티커 기초/가치/재무 데이터 수집
- yfinance 기반 국내외 가격, 해외지수, 매크로, 원자재 데이터 수집
- KRX 웹/Selenium 기반 공매도, 프로그램 매매 데이터 수집
- PostgreSQL raw/history 계열 테이블 적재
- non-GUI daily crawler와 Windows GUI KRX worker로 분리된 hybrid 실행 흐름 제공
- KRX raw 적재 완료 여부를 확인하는 KRX raw validation 스크립트 제공
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

## AWS 운영 구조

이 모듈은 portfolio system의 `aws-paper` 운영에서 데이터 수집 실행 단위로 사용된다. Daily 배치 오케스트레이션(Scheduler와 Step Functions 계열)이 데이터 수집 단계에 진입할 때 이 모듈이 호출 표면(invocation surface)이 된다. 오케스트레이션의 세부 상태머신, Scheduler 라인업, Lambda 내부 구현은 인접 시스템 소유이므로 이 저장소 문서에서는 다루지 않는다.

Crawler는 KRX GUI 의존 여부에 따라 두 개의 실행 표면(hybrid execution model)으로 분리된다.

- non-GUI daily crawler는 컨테이너/ECS Fargate RunTask 후보 실행 단위다. 진입점은 `interest_crawler_daily_nongui.py`이며 KRX GUI 의존 단계(`interest_krx_login_new`, `interest_program`, `interest_shortsell`)를 import하지 않는다. 실행 시 Naver, yfinance, 그리고 외부 휴일 API에 대한 outbound 요청과 PostgreSQL upsert가 발생한다.
- GUI KRX worker는 Selenium/Chrome/GUI 의존 흐름이다. Windows Scheduled Task 후보 실행 단위로 분리되어 있으며 KRX program과 KRX shortsell 수집을 담당한다. 실행 시 KRX data portal로 outbound 요청이 발생하고, CSV 다운로드와 파싱을 거쳐 PostgreSQL upsert로 이어진다.
- KRX worker 수집이 끝나면 `interest_krx_raw_validate_daily.py`가 `interest_program_raw`, `interest_shortsell_raw`의 최신 `trade_date`와 row_count를 확인해 raw 적재 여부를 판단한다. 실패 시 non-zero exit code로 종료해 후속 단계가 부적재 상태에서 이어지지 않도록 한다.

실제 AWS 클러스터/서비스 이름, task definition ARN, Windows instance id, 사설 IP, 로컬 절대 경로, SSM command id는 이 문서에 원문으로 기록하지 않는다. 필요한 경우 `<CRAWLER_ECS_TASK>`, `<WINDOWS_KRX_WORKER>`, `<SCHEDULED_TASK_NAME>`, `<DB_HOST>`, `<CHROME_DRIVER_PATH>`, `<COMMAND_ID>` 같은 구조적 플레이스홀더만 사용한다.

실행 책임 경계는 다음과 같다.

- Crawler는 데이터 수집 스크립트 실행과 raw/history 적재만 책임진다.
- 배치 오케스트레이션(Scheduler, Step Functions 계열)은 인접 시스템 책임이다.
- View 계열은 실행 상태 조회 또는 trigger UI 용도로만 이 모듈을 참조한다.
- Preprocessor MS는 이 모듈이 적재한 raw를 소비해 feature로 변환하는 후속 단계다.

### KRX 점검/리다이렉트 감지 운영 주의사항

KRX data portal은 점검 시간대, 리다이렉트, timeout이 발생할 수 있다. Selenium 기반 KRX 수집은 점검 페이지나 로그인 리다이렉트를 정상 응답으로 오해할 수 있으므로 다음 원칙을 따른다.

- KRX 점검/리다이렉트/timeout이 감지되면 strict-exit 또는 fail-fast로 종료해 부적재 raw가 downstream으로 이어지지 않게 한다.
- KRX worker 수집 완료 후 `interest_krx_raw_validate_daily.py`로 raw 최신 상태를 검증한다. row_count 0 또는 `max(trade_date)` 미달이면 실패로 처리한다.
- 특정 일자의 장애 로그, 실행 시간, 일회성 command id는 이 문서에 남기지 않는다.

## 설정 방법

현재 스크립트들은 DB 접속정보, KRX/Naver/yfinance 관련 설정, Chrome/ChromeDriver 경로, 환경변수 기반 credential을 사용할 수 있다.

민감정보는 코드, 문서, 로그, 예시 출력에 기록하지 않는다. 필요한 값은 환경변수 또는 local config로 분리하고 문서에는 `[REDACTED]`로 마스킹한다.

### DB 접속 환경변수

DB 접속정보는 `db_config.py`의 `get_db_config()`에서 `INTEREST_DB_*` 환경변수로 읽는다. 각 스크립트는 기존처럼 단독 실행할 수 있지만, 실행 전에 `INTEREST_DB_PASSWORD`는 반드시 설정해야 한다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `INTEREST_DB_HOST` | `localhost` | PostgreSQL host |
| `INTEREST_DB_PORT` | `5433` | PostgreSQL port |
| `INTEREST_DB_NAME` | `portfolio` | PostgreSQL database name |
| `PORTFOLIO_DB_NAME` | `portfolio` | portfolio system shared PostgreSQL database name. `INTEREST_DB_NAME`을 우선 사용하지 않는 환경에서도 같은 기본값을 사용한다. |
| `INTEREST_DB_USER` | `postgres` | PostgreSQL user |
| `INTEREST_DB_PASSWORD` | 없음 | PostgreSQL password. 비어 있으면 실행 시 `RuntimeError`가 발생한다. |

PowerShell 설정 예시:

```powershell
$env:INTEREST_DB_HOST="localhost"
$env:INTEREST_DB_PORT="5433"
$env:INTEREST_DB_NAME="portfolio"
$env:INTEREST_DB_USER="postgres"
$env:INTEREST_DB_PASSWORD="[REDACTED]"
```

### PostgreSQL schema

로컬 PostgreSQL 기본 DB name은 `portfolio`다. AWS Migration 준비 관점에서도 여러 DB로 분리하지 않고 단일 DB `portfolio` 안에서 domain별 schema를 나누는 구조를 사용한다.

현재 portfolio system schema는 `reference`, `interest`, `preprocessor`, `research`, `decision`, `execution`, `connector`, `ops`, `legacy`, `public`로 구분한다. 이 모듈은 interest 수집 모듈이므로 DB connection의 `search_path`를 다음 순서로 사용한다.

```sql
interest, reference, legacy, public
```

`public`에 있던 interest 관련 테이블은 domain schema로 이동되었지만, 이 모듈의 기존 SQL은 대부분 schema qualifier 없이 작성되어 있다. 따라서 connection `search_path`를 통해 기존 SQL이 `interest` schema를 우선 조회하고, 공통 참조 테이블은 `reference`, 이전 호환 대상은 `legacy` 순서로 해석되도록 유지한다.

자세한 DB 구조와 문서화 기준은 `docs/database.md`를 참고한다.

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

## 문서화 기준

- Python 파일에는 파일 상단 module docstring으로 역할, 진입점, DB/외부 API 의존성을 짧게 남긴다.
- 의미가 불명확하거나 운영상 중요한 함수에만 짧은 function docstring을 추가한다.
- HTML, CSS, SQL, YAML, properties 같은 설정/마크업 파일은 필요한 경우 상단 또는 큰 섹션 단위로만 주석을 남긴다.
- 주석에는 실제 password, token, API key, 계좌번호, webhook URL 같은 민감정보 값을 기록하지 않는다.

## 검증

문서만 수정한 경우에는 변경 범위만 확인한다.

```powershell
git status --short
git diff --stat
```

코드 수정 시에는 외부 요청, 크롤링, DB 쓰기, 주문 실행이 포함되지 않는 검증만 선택한다. 실행 위험이 있으면 완료 보고에 검증 한계를 남긴다.
