# Source File Catalog

port-interest-crawler의 주요 파일과 디렉터리 역할을 빠르게 확인하기 위한 문서다.

모든 파일을 나열하는 inventory가 아니라, 구조 이해와 변경 영향 판단에 필요한 항목만 기록한다.

repository root 기준 상대 경로를 사용하며 cache, credential, download, HTML dump와 일회성 산출물은 제외한다.

## 사용 원칙

| 항목 | 값 |
| --- | --- |
| 기준 | 현재 Crawler 코드와 hybrid 운영 구조 |
| 포함 | 주요 entrypoint · 공통 helper · 운영 영향 파일 |
| 제외 | cache · credential · debug dump · 다운로드 산출물 |
| 갱신 | 파일 경로 · 책임 · 실행 위험이 바뀔 때 |
| 생략 | 내부 구현만 바뀌고 파일 책임이 동일한 경우 |
| 민감정보 | credential · host · ARN · command id 원문 금지 |

## Root와 공통 파일

| 파일 | 역할 |
| --- | --- |
| `AGENTS.md` | Crawler 코드와 문서 작업 규칙 |
| `README.md` | 현재 구조 · 실행 모델 · 운영 AS-IS |
| `CHANGELOG.md` | 주요 변경 이력 |
| `db_config.py` | PostgreSQL 환경변수 loader |
| `interest_get_holidays.py` | 시장 휴일 확인 |
| `interest_log_format.py` | 수집 로그와 summary 포맷 |

### 변경 시 확인

| 대상 | 확인 |
| --- | --- |
| `AGENTS.md` | 실행 제한 · strict-exit · 문서 갱신 규칙 |
| `README.md` | Daily · History · Validation · hybrid 구조 |
| `CHANGELOG.md` | 실제 Crawler 변경만 기록 |
| `db_config.py` | `INTEREST_DB_*` · password 기본값 · search path |
| 휴일 helper | KST · 공휴일 API 실패 · 거래일 판단 |
| 로그 helper | 실패를 SUCCESS 또는 DONE으로 출력하지 않는지 |

## Daily Orchestration

| 파일 | 역할 |
| --- | --- |
| `interest_crawler_daily.py` | GUI 포함 Daily 수집 orchestration |
| `interest_crawler_daily_nongui.py` | non-GUI Daily 수집 orchestration |
| `interest_crawler_main.py` | 수동 · 초기 통합 수집 |

### 실행 모델

| 항목 | 기준 |
| --- | --- |
| GUI Daily | KRX login · program · shortsell 포함 가능 |
| non-GUI Daily | Naver · yfinance · 휴일 API · DB |
| Container 후보 | `interest_crawler_daily_nongui.py` |
| Windows worker | KRX GUI 수집 분리 |
| 완료 확인 | child 단계 결과와 후속 validation을 함께 확인 |
| 금지 | 부분 실패 뒤 전체 SUCCESS |

현재 GUI Daily는 일부 child 실패를 최종 exit code로 집계하지 않을 수 있으므로 개별 단계 로그와 후속 validation을 함께 확인한다.

non-GUI entrypoint에 Selenium과 KRX GUI 모듈을 다시 결합하지 않는다.

## Daily Data Collectors

| 파일 | 역할 |
| --- | --- |
| `interest_price.py` | 국내 종목 가격 증분 수집 |
| `interest_marketbreadth.py` | 가격 기반 market breadth |
| `interest_foreignindex.py` | 해외지수 증분 수집 |
| `interest_macroeconomic.py` | 매크로 지표 증분 수집 |
| `interest_commodity.py` | 원자재 증분 수집 |
| `interest_investorflow.py` | Naver 투자자 수급 |
| `interest_agency.py` | Naver 증권사 리포트 |
| `interest_news.py` | Naver 뉴스 |
| `interest_program.py` | KRX 프로그램 매매 |
| `interest_shortsell.py` | KRX 공매도 |
| `interest_ticker_main.py` | 종목 기본정보 |
| `interest_ticker_value.py` | 종목 가치정보 |
| `interest_ticker_finance.py` | 종목 재무정보 |

### 원천별 구분

| 원천 | 관련 파일 |
| --- | --- |
| yfinance | price · foreignindex · macroeconomic · commodity |
| Naver | investorflow · agency · news · ticker |
| KRX | program · shortsell |
| PostgreSQL | marketbreadth · 모든 persist 경로 |

### 변경 시 확인

| 항목 | 값 |
| --- | --- |
| HTTP | timeout · status · rate limit |
| Parse | 필수 컬럼 · 날짜 · 숫자 · encoding |
| 빈 결과 | 정상 휴일과 원천 실패 구분 |
| Persist | unique key · upsert · transaction |
| Source | 기존 source 값과 ticker 의미 유지 |
| Exit | 일부 실패와 전체 실패 구분 |

## History와 Backfill

| 파일 | 역할 |
| --- | --- |
| `interest_price_history.py` | 가격 history |
| `interest_marketbreadth_history.py` | breadth history 재계산 |
| `interest_foreignindex_history.py` | 해외지수 history |
| `interest_macroeconomic_history.py` | 매크로 history |
| `interest_commodity_history.py` | 원자재 history |
| `interest_investorflow_history.py` | 투자자 수급 history |
| `interest_agency_history.py` | 증권사 리포트 history |
| `interest_news_history.py` | 뉴스 history |
| `interest_program_history.py` | KRX 프로그램 history |
| `interest_shortsell_history.py` | KRX 공매도 history |

### 변경 시 확인

| 항목 | 값 |
| --- | --- |
| 기간 | 시작일 · 종료일 |
| 거래일 | calendar gap과 trade gap |
| Chunk | 요청 · commit 단위 |
| Checkpoint | 실패 후 재개 기준 |
| Rate limit | 원천별 제한과 backoff |
| Idempotency | 중복과 conflict 정책 |
| 부분 실패 | 재수집 범위와 성공 marker |

History를 Daily 기본 실행 경로로 사용하지 않는다.

## Validation과 Check

| 파일 | 역할 |
| --- | --- |
| `interest_data_validate_daily.py` | Daily 최신성 · NULL · 중복 · 이상치 |
| `interest_data_validate_all.py` | 전체 데이터 품질 점검 |
| `interest_price_check.py` | 최근 거래일 가격 누락 확인 |
| `interest_krx_raw_validate_daily.py` | KRX raw 최신성 · row count 확인 |

### 실행 위험

| 파일 | 주의 |
| --- | --- |
| `interest_data_validate_daily.py` | DB와 휴일 API 의존 가능 |
| `interest_data_validate_all.py` | 대량 DB read와 휴일 API 가능 |
| `interest_price_check.py` | DB read와 거래일 판단 |
| `interest_krx_raw_validate_daily.py` | DB read · 실패 시 non-zero exit |

validation 또는 check라는 이름만으로 안전한 read-only script라고 판단하지 않는다.

### KRX Raw Validation

| 대상 | 확인 |
| --- | --- |
| `interest_program_raw` | 최신 `trade_date` · row count |
| `interest_shortsell_raw` | 최신 `trade_date` · row count |
| Expected date | 실행 기준 거래일 |
| 실패 | non-zero exit |
| 목적 | downstream 부적재 진행 차단 |

실제 exit code 숫자는 코드 계약을 우선한다.

문서에서 확인하지 않은 숫자를 임의로 고정하지 않는다.

## KRX와 Browser

| 파일 | 역할 |
| --- | --- |
| `interest_krx_chrome.py` | Chrome session과 GUI 준비 |
| `interest_krx_login_new.py` | KRX login · popup · iframe 처리 |
| `interest_program.py` | 프로그램 매매 Daily download |
| `interest_program_history.py` | 프로그램 매매 history download |
| `interest_shortsell.py` | 공매도 Daily download |
| `interest_shortsell_history.py` | 공매도 history download |

### Strict-exit 조건

| 조건 | 처리 |
| --- | --- |
| KRX 점검 페이지 | 실패 |
| Login redirect | 실패 |
| Session 만료 | 실패 |
| Download timeout | 실패 |
| 빈 CSV | 실패 |
| 필수 컬럼 누락 | 실패 |
| Expected date 미달 | 실패 |
| Row count 0 | 실패 |

다운로드 파일 존재만으로 성공을 판정하지 않는다.

기존 파일과 신규 파일을 구분하고, 부분 파일을 parse하지 않는다.

## Windows KRX Worker

| 파일 | 역할 |
| --- | --- |
| `ops/run_krx_worker_daily.ps1` | Windows KRX worker daily wrapper |

### 실행 순서

| 단계 | 처리 |
| --- | --- |
| 준비 | venv · crawler DB env · KRX env 로드 |
| 수집 | KRX login → program → shortsell |
| 검증 | program · shortsell raw 최신성 DB 확인 |
| 로그 | 로컬 log 디렉터리에 실행 로그 기록 |

Scheduled Task용 GUI 수집 wrapper이며 non-GUI Daily 경로와 분리한다.

wrapper가 실행 중 생성하는 인라인 DB validator는 임시 산출물로 실행 후 제거한다.

## DevOps와 Deployment

| 파일 | 역할 |
| --- | --- |
| `Dockerfile` | Container image build |
| `.dockerignore` | Git · cache · `.devops/artifacts/` build context 제외 |
| `.github/workflows/crawler-codebuild.yml` | OIDC로 Crawler CodeBuild 시작 · publish gate 전달 |
| `.github/workflows/oidc-preflight.yml` | GitHub OIDC claim 확인용 preflight |
| `.devops/buildspec/buildspec.yml` | 공통 gate · Windows ZIP · Container build · 선택 publish |
| `.devops/bundle/windows-include.txt` | Windows Worker bundle 포함 범위 |
| `.devops/scripts/build/compile_check.py` | 안전한 Python compile gate |
| `.devops/scripts/package/build_windows_bundle.py` | Git SHA 기반 deterministic Windows ZIP 생성 |
| `.devops/scripts/test/verify_windows_bundle.py` | manifest · forbidden file · bundle contract 검증 |
| `.devops/scripts/deploy/windows-before-install.ps1` | CodeDeploy BeforeInstall lifecycle hook |
| `.devops/scripts/deploy/windows-after-install.ps1` | CodeDeploy AfterInstall lifecycle hook |
| `.devops/scripts/deploy/windows-validate.ps1` | CodeDeploy ValidateService lifecycle hook |

### 변경 시 확인

| 항목 | 값 |
| --- | --- |
| 실행 계약 | Docker 기본 CMD와 ECS Task Definition command 책임 구분 |
| Publish gate | `PUSH_ARTIFACT`와 `PUSH_IMAGE` 독립성 유지 |
| Build context | build output을 Container context에 넣지 않음 |
| Windows bundle | runtime secret · local env loader 제외 |
| Lifecycle hook | Candidate staging · runtime promotion · validation 책임 분리 |
| 민감정보 | credential · token 원문 문서 기록 금지 |

`.devops/artifacts/*.zip`, `__pycache__`, `*.pyc`와 임시 backup은 catalog에 포함하지 않는다.

## Universe와 Sector

| 파일 | 역할 |
| --- | --- |
| `build_stock_universe.py` | Naver 기반 stock universe |
| `build_sector_mapping.py` | sector · industry mapping |
| `build_universe_sector.py` | universe sector 보강 |

### 변경 시 확인

| 항목 | 값 |
| --- | --- |
| Universe | 시장 · ticker · 종목명 key |
| Mapping | 영문 · 한글 sector 의미 |
| yfinance | ticker suffix · 빈 응답 |
| Selenium | Naver scroll · page 구조 |
| DB | reference와 interest 책임 구분 |

reference 데이터 변경이 Crawler raw 적재 의미를 깨뜨리지 않게 한다.

## Database Contract

| 항목 | 값 |
| --- | --- |
| Database | `portfolio` |
| Config loader | `db_config.py` · `get_db_config()` |
| 환경변수 | `INTEREST_DB_*` |
| Password | 기본값 없음 |
| search path | `interest, reference, legacy, public` |

### Schema 책임

| Schema | 역할 |
| --- | --- |
| `interest` | raw · history · 수집 결과 |
| `reference` | ticker · market · calendar |
| `legacy` | 과거 호환 |
| `public` | fallback search path |

### SQL 변경 시 확인

| 항목 | 값 |
| --- | --- |
| Table · column | 코드 · migration · DB 계약 확인 |
| 신규 SQL | 가능한 한 schema-qualified |
| 기존 SQL | connection `search_path` 확인 |
| Unique key | `ON CONFLICT` 의미 유지 |
| Delete | source · ticker · 기간 범위 확인 |
| Transaction | commit · rollback 경계 |
| 실패 | 부분 적재 뒤 SUCCESS 금지 |

Crawler는 `preprocessor`, `research`, `decision`, `execution` 결과를 직접 생성하지 않는다.

## External Dependencies

| 항목 | 역할 |
| --- | --- |
| Requests | HTTP 요청 |
| BeautifulSoup | HTML parsing |
| yfinance | 시장 데이터 |
| Selenium | Browser automation |
| Chrome · ChromeDriver | KRX GUI |
| psycopg · psycopg2 | PostgreSQL |
| Naver | Finance · News · Open API |
| KRX | Data portal |
| PostgreSQL | raw · history persistence |

실제 외부 원천과 DB를 문서 검증이나 unit test에서 사용하지 않는다.

## Tests

| 변경 | 검증 |
| --- | --- |
| Python 문법 | 안전한 compile check |
| HTTP parser | 저장된 fixture response |
| HTML parser | 로컬 fixture HTML |
| CSV parser | 로컬 fixture CSV |
| yfinance | DataFrame mock |
| Selenium | login · download mock |
| Daily orchestration | child call · exit code mock |
| History | chunk · checkpoint · idempotency |
| Validation | DB result · expected date mock |
| Repository | SQL · parameter · upsert |
| 문서 | 링크 · 사실 · 가독성 |

실행 위험 import가 있으면 파일 본문 정적 확인을 우선한다.

## Documents

| 문서 | 역할 |
| --- | --- |
| `AGENTS.md` | Crawler 작업 규칙 |
| `README.md` | 현재 구조와 운영 AS-IS |
| `CHANGELOG.md` | 주요 변경 이력 |
| `docs/source-file-catalog.md` | 주요 파일과 책임 |

날짜별 `docs/worklog/*.md`는 신규 생성하지 않는다.

과거 worklog를 유지하는 경우 역사 기록으로만 취급한다.

## 외부 의존 모듈

| 모듈 | 관계 |
| --- | --- |
| `port-interest-preprocessor` | Crawler raw 소비 |
| `port-view` | 실행 상태 조회 · trigger UI |
| `port-marketconnector` | 주문과 broker 연동 |
| `port_strategy_research` | 전략 연구 |
| `port_strategy_decision` | 전략 판단 |
| `port_strategy_execution` | 주문 계획 |
| Step Functions · Scheduler | orchestration |

다른 MS의 내부 코드와 문서는 Crawler 변경 범위에 자동 포함하지 않는다.

## 정리 후보

| 파일 | 판단 |
| --- | --- |
| `block_watch_backtest_run.py` | 운영 수집과 직접 관계 확인 필요 |
| `dump_public_schema_final.py` | DB dump · 로컬 파일 생성 후보 |
| `patch_research_decision_dependency.py` | Crawler 책임 밖 일회성 patch 후보 |

정리 후보는 실행하거나 삭제하지 않는다.

실제 참조, 호출 관계와 소유 MS를 확인한 뒤 별도 결정한다.

## 카탈로그 갱신 조건

| 변경 | 처리 |
| --- | --- |
| 주요 Python 파일 생성 · 삭제 · 이름 변경 | 갱신 |
| Daily · History · Validation 책임 변경 | 갱신 |
| non-GUI · KRX worker 구조 변경 | 갱신 |
| 데이터 원천 · parser 책임 변경 | 갱신 |
| 설정 · DB loader 역할 변경 | 갱신 |
| scripts · worker wrapper 변경 | 갱신 |
| 문서 생성 · 삭제 · 역할 변경 | 갱신 |
| 내부 구현만 변경 · 책임 동일 | 생략 가능 |

카탈로그 갱신 시 전체 repository inventory를 새로 만들지 않는다.

변경된 영역과 인접 항목만 확인한다.
