# port-interest-crawler

Naver, yfinance, KRX 등 외부 데이터 원천에서 가격, 뉴스, 리서치, 투자자 수급, 공매도, 프로그램 매매, 매크로, 원자재와 해외지수 데이터를 수집하는 Python 마이크로서비스다.

수집 결과는 PostgreSQL의 `interest` raw/history 영역에 적재하며, 후속 Preprocessor가 이를 소비한다.

이 저장소의 실행 경로는 외부 네트워크 요청, Selenium/Chrome, 파일 다운로드와 DB upsert로 이어질 수 있으므로 정적 분석과 문서 작업을 기본값으로 한다.

## 현재 상태

| 항목 | 값 |
| --- | --- |
| 운영 성격 | AWS Paper 데이터 수집 |
| 기본 구조 | 독립 실행형 Python script 중심 |
| Daily non-GUI | `interest_crawler_daily_nongui.py` |
| KRX GUI | Windows worker · Selenium · Chrome |
| History | 원천별 `*_history.py` backfill |
| Validation | 최신성 · row count · gap 점검 |
| Database | PostgreSQL `portfolio` |
| 기본 schema | `interest` |
| downstream | port-interest-preprocessor |
| 문서 기본 원칙 | 외부 호출과 DB 쓰기 없이 정적 확인 |

> validation 또는 check 이름이 붙은 파일도 DB 연결이나 외부 요청을 포함할 수 있다. 문서 검증 목적으로 실행하지 않는다.

## 기술 스택

| 항목 | 값 |
| --- | --- |
| Language | Python |
| HTTP | Requests |
| HTML Parsing | BeautifulSoup |
| Market Data | yfinance |
| Browser | Selenium · Chrome |
| Database Driver | psycopg · psycopg2 |
| Database | PostgreSQL |
| Data Source | Naver · KRX · yfinance |

## 책임 경계

### 담당 범위

| 영역 | 역할 |
| --- | --- |
| Price | 국내외 가격과 시계열 |
| News · Research | 뉴스와 리서치 자료 |
| Flow | 투자자 수급과 기관 데이터 |
| KRX | 프로그램 매매와 공매도 |
| Macro | 해외지수 · 매크로 · 원자재 |
| Ticker | 종목 기본 · 가치 · 재무 |
| Universe | stock universe와 sector mapping |
| Daily | 최신 거래일 수집 |
| History | 과거 기간 backfill |
| Validation | 최신성 · row count · gap 확인 |
| Persistence | raw/history DB 적재 |

### 직접 담당하지 않는 범위

| 항목 | 실제 책임 영역 |
| --- | --- |
| 배치 orchestration | Step Functions · Scheduler |
| KRX worker 기동 | Windows Scheduled Task |
| feature 생성 | port-interest-preprocessor |
| 전략 연구 | Strategy Research |
| 전략 판단 | Strategy Decision |
| 주문 계획 | Strategy Execution |
| 주문 제출 | port-marketconnector |
| 화면 | port-view |

Crawler 안에 전처리, 전략 판단과 주문 실행 로직을 복제하지 않는다.

## 실행 모델

Crawler는 GUI 의존 여부에 따라 두 실행 표면으로 분리한다.

### Non-GUI Daily

| 항목 | 값 |
| --- | --- |
| Entrypoint | `interest_crawler_daily_nongui.py` |
| 운영 실행 | ECS Fargate RunTask · non-GUI |
| 실행 계약 | Task Definition command `interest_crawler_daily_nongui.py` |
| 배포 identity | Git SHA image tag · immutable ECR digest |
| 주요 원천 | Naver · yfinance · 휴일 API |
| DB 처리 | PostgreSQL upsert |
| 제외 | KRX login · program · shortsell |
| 목적 | GUI 없는 Daily 수집 |

non-GUI entrypoint는 KRX GUI 의존 모듈을 import하지 않는다.

Dockerfile 기본 CMD가 아니라 ECS Task Definition의 explicit command가 운영 실행 계약이다.

운영 orchestration은 검증된 Task Definition revision을 참조한다.

### Windows KRX Worker

| 항목 | 값 |
| --- | --- |
| 환경 | Windows EC2 · GUI session |
| 운영 실행 | Scheduled Task |
| Browser | Selenium · Chrome |
| 수집 | KRX program · shortsell |
| 처리 | login · CSV download · parse · upsert |
| 배포 | versioned S3 ZIP · CodeDeploy IN_PLACE |
| 후속 | KRX raw validation |

Windows GUI 의존 흐름을 container의 기본 실행 경로로 합치지 않는다.

## 주요 파일

### Daily와 공통 수집

| 파일 | 역할 |
| --- | --- |
| `interest_crawler_daily.py` | Daily 통합 수집 |
| `interest_crawler_daily_nongui.py` | non-GUI Daily 수집 |
| `interest_crawler_main.py` | 통합 실행 entrypoint |
| `interest_price.py` | 가격 수집 |
| `interest_marketbreadth.py` | 시장 breadth |
| `interest_foreignindex.py` | 해외지수 |
| `interest_macroeconomic.py` | 매크로 |
| `interest_commodity.py` | 원자재 |
| `interest_investorflow.py` | 투자자 수급 |
| `interest_agency.py` | 기관 데이터 |
| `interest_news.py` | 뉴스 |
| `interest_program.py` | KRX 프로그램 매매 |
| `interest_shortsell.py` | KRX 공매도 |
| `interest_ticker_main.py` | ticker 기본정보 |
| `interest_ticker_value.py` | ticker 가치정보 |
| `interest_ticker_finance.py` | ticker 재무정보 |

### History와 Backfill

| 파일 | 역할 |
| --- | --- |
| `interest_price_history.py` | 가격 history |
| `interest_marketbreadth_history.py` | breadth history |
| `interest_foreignindex_history.py` | 해외지수 history |
| `interest_macroeconomic_history.py` | 매크로 history |
| `interest_commodity_history.py` | 원자재 history |
| `interest_investorflow_history.py` | 투자자 수급 history |
| `interest_agency_history.py` | 기관 history |
| `interest_news_history.py` | 뉴스 history |
| `interest_program_history.py` | KRX 프로그램 history |
| `interest_shortsell_history.py` | KRX 공매도 history |

### Validation과 Check

| 파일 | 역할 |
| --- | --- |
| `interest_data_validate_daily.py` | Daily 데이터 검증 |
| `interest_data_validate_all.py` | 전체 범위 검증 |
| `interest_price_check.py` | 가격 점검 |
| `interest_krx_raw_validate_daily.py` | KRX raw 최신성 검증 |

### KRX와 Browser

| 파일 | 역할 |
| --- | --- |
| `interest_krx_chrome.py` | Chrome 관련 helper |
| `interest_krx_login_new.py` | KRX login |
| `interest_program.py` | 프로그램 매매 Daily |
| `interest_program_history.py` | 프로그램 매매 history |
| `interest_shortsell.py` | 공매도 Daily |
| `interest_shortsell_history.py` | 공매도 history |

### Universe와 Sector

| 파일 | 역할 |
| --- | --- |
| `build_stock_universe.py` | stock universe 구성 |
| `build_sector_mapping.py` | sector mapping |
| `build_universe_sector.py` | universe와 sector 결합 |

### 후보 파일

| 파일 | 분류 |
| --- | --- |
| `dump_public_schema_final.py` | legacy · DB dump 후보 |
| `block_watch_backtest_run.py` | 로컬 실험 후보 |
| `patch_research_decision_dependency.py` | 일회성 patch 후보 |

후보 파일은 정적 확인만으로 삭제하지 않는다.

상세 역할은 [소스 파일 카탈로그](docs/source-file-catalog.md)를 참고한다.

## 실행 위험

### Daily

Daily 스크립트는 외부 원천 요청과 DB 적재를 수행할 수 있다.

| 위험 | 내용 |
| --- | --- |
| Network | Naver · yfinance · 휴일 API |
| Browser | 일부 KRX 경로 |
| Database | insert · update · upsert |
| Filesystem | CSV · HTML · 임시 파일 |
| Exit | 부분 실패를 성공으로 오인 가능 |

현재 GUI Daily는 일부 child 실패를 최종 exit code로 집계하지 않을 수 있다. 완료 여부는 개별 단계 결과와 후속 validation을 함께 확인한다.

### History와 Backfill

history 스크립트는 장기간 요청과 대량 적재를 수행할 수 있다.

| 확인 | 내용 |
| --- | --- |
| 기간 | 시작일 · 종료일 |
| 거래일 | calendar gap과 trade gap 구분 |
| 제한 | 원천별 rate limit |
| 적재 | unique key · upsert |
| 재시작 | chunk · checkpoint |
| 실패 | 부분 적재와 재실행 기준 |

History를 Daily 기본 실행 경로로 사용하지 않는다.

### Validation

validation 스크립트도 DB 연결 또는 외부 요청을 포함할 수 있다.

이름만 보고 read-only라고 판단하지 않는다.

## 외부 데이터 원천

### Naver

| 항목 | 기준 |
| --- | --- |
| 대상 | 뉴스 · 리서치 · 수급 · ticker |
| HTTP | timeout · status 확인 |
| Parsing | HTML 구조와 encoding 확인 |
| 중복 | source · URL · 날짜 key 확인 |
| Credential | client id · secret 비노출 |

빈 HTML이나 구조 변경을 정상 데이터 0건으로 처리하지 않는다.

### yfinance

| 항목 | 기준 |
| --- | --- |
| 대상 | 가격 · 해외지수 · 매크로 · 원자재 |
| Ticker | suffix와 market 확인 |
| 날짜 | timezone · trade date 확인 |
| 빈 결과 | 정상 성공으로 처리하지 않음 |
| 실패 | 일부 ticker와 전체 실패 구분 |

### KRX

| 항목 | 기준 |
| --- | --- |
| 대상 | 프로그램 매매 · 공매도 |
| 접근 | Selenium · Chrome · login |
| 산출물 | CSV download |
| 검증 | expected date · row count · 필수 컬럼 |
| 실패 | 점검 · redirect · timeout · 빈 CSV |

점검 페이지와 login redirect를 정상 CSV로 처리하지 않는다.

## KRX strict-exit

다음 상황은 정상 완료로 처리하지 않는다.

- KRX 점검 페이지
- login redirect
- session 만료
- download timeout
- 빈 CSV
- 필수 컬럼 누락
- expected date 미달
- row count 0

실패한 KRX 수집을 SUCCESS 또는 `NO_CHANGE`로 바꾸지 않는다.

## KRX Raw Validation

`interest_krx_raw_validate_daily.py`는 Windows KRX worker 이후 raw 적재 상태를 확인한다.

| 대상 | 확인 |
| --- | --- |
| `interest_program_raw` | 최신 `trade_date` · row count |
| `interest_shortsell_raw` | 최신 `trade_date` · row count |
| Expected date | 실행 기준 거래일 |
| 실패 | non-zero exit |
| 목적 | downstream 진행 차단 |

row count가 0이거나 최신 거래일이 기대일보다 이전이면 실패로 처리한다.

검증을 통과시키기 위해 expected date나 최소 row count를 근거 없이 낮추지 않는다.

## Daily와 History

### Daily 기준

| 항목 | 기준 |
| --- | --- |
| 대상 | 최신 거래일 |
| 기간 | 짧고 명확한 범위 |
| 실패 | fail-fast |
| 재실행 | idempotent |
| 후속 | validation |

### History 기준

| 항목 | 기준 |
| --- | --- |
| 대상 | 과거 기간 |
| 기간 | 시작일 · 종료일 |
| 실행 | chunk |
| 재개 | checkpoint |
| 제한 | rate limit |
| 품질 | gap 재수집 |

Daily 코드에 장기 backfill 기능을 숨겨 넣지 않는다.

## Database

### 연결 기준

| 항목 | 값 |
| --- | --- |
| Database | `portfolio` |
| Config loader | `db_config.py` · `get_db_config()` |
| 환경변수 | `INTEREST_DB_*` |
| Password | 기본값 없음 |
| search path | `interest, reference, legacy, public` |

운영 환경에서는 Crawler 전용 DB user를 사용한다.

문서의 `postgres` 기본값을 운영 권한 기준으로 해석하지 않는다.

### Schema 책임

| Schema | 역할 |
| --- | --- |
| `interest` | raw · history · 수집 결과 |
| `reference` | ticker · market · calendar |
| `legacy` | 과거 호환 |
| `public` | fallback search path |

Crawler는 `preprocessor`, `research`, `decision`, `execution` 결과를 직접 생성하지 않는다.

### SQL 기준

- 신규 SQL은 가능한 한 schema-qualified 이름을 사용한다.
- 기존 unqualified SQL은 connection `search_path` 기준으로 동작한다.
- unique key와 `ON CONFLICT` 의미를 유지한다.
- raw와 history 보존 정책을 구분한다.
- delete 후 insert는 대상 기간과 source를 확인한다.
- 부분 적재 뒤 SUCCESS를 출력하지 않는다.

## 설정

### DB 환경변수

| 환경변수 | 기본값 · 역할 |
| --- | --- |
| `INTEREST_DB_HOST` | `localhost` |
| `INTEREST_DB_PORT` | `5433` |
| `INTEREST_DB_NAME` | `portfolio` |
| `PORTFOLIO_DB_NAME` | `portfolio` |
| `INTEREST_DB_USER` | 환경별 Crawler DB user |
| `INTEREST_DB_PASSWORD` | 기본값 없음 |

PowerShell 예시:

```powershell
$env:INTEREST_DB_HOST="localhost"
$env:INTEREST_DB_PORT="5433"
$env:INTEREST_DB_NAME="portfolio"
$env:INTEREST_DB_USER="[REDACTED]"
$env:INTEREST_DB_PASSWORD="[REDACTED]"
```

### 기타 설정

| 범주 | 예시 |
| --- | --- |
| Browser | Chrome · ChromeDriver 경로 |
| KRX | login credential · download directory |
| Naver | client id · client secret |
| HTTP | URL · user-agent · timeout |
| 수집 | ticker · market · date range |
| Worker | timezone · Scheduled Task |

실제 local config와 credential 값을 문서에 기록하지 않는다.

## AWS와 Windows 운영

### Hybrid DevOps 요약

| 항목 | 값 |
| --- | --- |
| Source | GitHub main |
| CI | GitHub Actions OIDC → CodeBuild |
| ECS Artifact | Git SHA image tag · immutable ECR digest |
| ECS Runtime | Fargate RunTask · non-GUI |
| Windows Artifact | Git SHA versioned ZIP · S3 object version |
| Windows Runtime | Windows EC2 · Scheduled Task |
| Windows Deploy | CodeDeploy IN_PLACE |
| Promotion | Candidate 검증 후 운영 reference 반영 |
| Rollback | ECS revision rollback · Windows runtime restore |

Windows artifact publish와 Container image publish의 gate는 서로 독립적이다.

Build와 Publish를 구분하며, Build-only에서는 외부 artifact publish가 일어나지 않는다.

### AWS

non-GUI Crawler는 ECS Fargate RunTask로 운영한다.

Scheduler와 Step Functions는 실행 시각과 orchestration을 담당하며, 운영 orchestration은 검증된 Task Definition revision을 참조한다.

Crawler 문서에서는 state machine 전체 정의와 외부 리소스 상태를 다루지 않는다.

### Windows

KRX worker는 GUI session과 Scheduled Task에 의존할 수 있다.

| 확인 | 내용 |
| --- | --- |
| Session | GUI 사용 가능 상태 |
| Browser | Chrome · ChromeDriver 호환 |
| Download | 신규 CSV와 기존 파일 구분 |
| Timezone | Asia/Seoul |
| Exit | Scheduled Task exit code |
| Validation | KRX raw validation 후속 실행 |

실제 AWS resource와 Windows task 실행은 사용자 요청 없이 수행하지 않는다.

## 실행

각 Python 파일은 독립 entrypoint일 수 있다.

아래 명령은 실행 위험 예시다.

```powershell
python interest_crawler_daily.py
```

실행 시 외부 요청, browser, 파일 다운로드와 DB 적재가 발생할 수 있다.

## 실행 금지 목록

문서 작업과 정적 분석 중에는 아래 작업을 수행하지 않는다.

- Daily · Main · 개별 수집 실행
- History · backfill 실행
- Validation · check 실행
- Naver · yfinance · KRX · 휴일 API 호출
- Selenium · Chrome · ChromeDriver 실행
- KRX login · CSV download
- DB DDL · DML · psql
- ECS · SSM · Scheduler 실행
- Windows Scheduled Task 실행
- Slack 호출

## 보안

다음 값은 코드, 문서와 로그에 원문으로 기록하지 않는다.

- DB password와 connection string
- Naver client id · client secret
- KRX 사용자 ID · password
- token · cookie · session
- 실제 DB host · private IP
- AWS account-id
- 실제 ARN
- instance id
- SSM command id
- local absolute path
- Slack webhook URL

Placeholder:

| 값 | Placeholder |
| --- | --- |
| 일반 민감정보 | `[REDACTED]` |
| DB host | `[REDACTED_DB_HOST]` |
| 사용자 ID | `[REDACTED_USER_ID]` |
| Secret | `[REDACTED_SECRET]` |
| ARN | `[REDACTED_ARN]` |
| instance id | `[REDACTED_INSTANCE_ID]` |
| command id | `[REDACTED_COMMAND_ID]` |
| ChromeDriver | `<CHROME_DRIVER_PATH>` |
| Windows worker | `<WINDOWS_KRX_WORKER>` |
| ECS task | `<CRAWLER_ECS_TASK>` |

## 외부 의존성

| 항목 | 값 |
| --- | --- |
| Python | Runtime |
| Requests | HTTP |
| BeautifulSoup | HTML parsing |
| yfinance | Market data |
| Selenium | Browser automation |
| psycopg · psycopg2 | PostgreSQL |
| Chrome · ChromeDriver | KRX GUI |
| Naver | Finance · News · Open API |
| KRX | Data portal |
| PostgreSQL | Raw · history persistence |

## 문서

| 문서 | 역할 |
| --- | --- |
| `AGENTS.md` | port-interest-crawler 작업 규칙 |
| `README.md` | 현재 구조와 운영 AS-IS |
| `CHANGELOG.md` | 주요 변경 이력 |
| `docs/source-file-catalog.md` | 주요 파일과 책임 |

날짜별 `docs/worklog/*.md`는 신규 생성하지 않는다.

코드와 문서 변경 이력은 `CHANGELOG.md`에 기록한다.
