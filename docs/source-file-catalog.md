# Source File Catalog

이 문서는 `port-interest-crawler` 루트의 주요 소스/문서 파일을 AWS Migration 전 초기 정리 관점에서 정리한 목록이다. 실제 크롤링, 외부 API 호출, Selenium/Chrome 실행, DB DDL/DML, 주문 실행은 수행하지 않고 정적 파일 확인 기준으로 작성했다.

## 운영/일일 수집 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `interest_crawler_daily.py` | 일일 수집 오케스트레이션 | KRX 로그인 이후 뉴스, 리서치, 가격, 수급, 프로그램 매매, 공매도, market breadth를 순서대로 호출한다. | 운영 일일 수집 단계를 묶는 최상위 실행 후보 | 실행 시 외부 요청, Selenium/Chrome, DB 쓰기가 연쇄 발생한다. 단계 순서를 임의 변경하지 않는다. |
| `interest_crawler_daily_nongui.py` | non-GUI 일일 수집 오케스트레이션 | KRX GUI 의존 단계를 제외하고 뉴스, 리서치, 해외지수, 원자재, 매크로, 가격, 투자자 수급, market breadth를 순차 호출한다. | 컨테이너/ECS Fargate RunTask 후보로 사용될 수 있는 진입점 | 실행 시 Naver, yfinance, 휴일 API 호출과 DB upsert가 발생한다. KRX GUI 흐름은 별도 Windows worker로 분리된 상태로 유지한다. |
| `interest_crawler_main.py` | 주요 수집 수동 실행기 | ticker, 뉴스, 리서치, 해외지수, 원자재, 매크로, market breadth 수집을 순차 호출한다. | 수동 또는 초기 수집용 오케스트레이션 후보 | 각 하위 모듈의 외부 연동과 DB upsert가 실행된다. |
| `interest_price.py` | 국내 종목 가격 증분 수집 | DB universe를 읽고 yfinance ticker로 변환해 최근 가격을 저장한다. | 관심종목 일일 가격 raw/history 적재 | yfinance 요청, 휴일 판단, DB upsert가 포함된다. |
| `interest_marketbreadth.py` | 시장 폭 지표 증분 계산 | DB 가격 데이터를 기반으로 상승/하락, 이동평균 관련 breadth 지표를 계산한다. | 가격 테이블 기반 파생 지표 산출 | 외부 API보다는 DB 읽기/쓰기가 핵심이다. 가격 테이블 전제와 계산 의미를 유지한다. |
| `interest_foreignindex.py` | 해외지수 증분 수집 | yfinance로 해외지수 가격 구간을 조회하고 JSON-safe 값으로 정리해 저장한다. | 해외지수 일일 데이터 적재 | yfinance 요청과 DB upsert가 포함된다. |
| `interest_macroeconomic.py` | 매크로 지표 증분 수집 | 국가/지표별 yfinance ticker 데이터를 최신 기간 이후로 조회해 저장한다. | 매크로 지표 일일 데이터 적재 | indicator 이름, country 값, 기간 산출 기준을 변경하지 않는다. |
| `interest_commodity.py` | 원자재 증분 수집 | 원자재 ticker별 최신 적재일 이후 가격을 yfinance에서 가져와 저장한다. | 원자재 일일 데이터 적재 | yfinance 요청과 DB upsert가 포함된다. |
| `interest_investorflow.py` | 투자자 수급 증분 수집 | Naver 금융 종목별 투자자 수급 테이블을 파싱해 최근 영업일 데이터를 저장한다. | 종목별 투자자 수급 적재 | Naver HTML 구조와 휴일 판정에 의존한다. |
| `interest_agency.py` | 증권사 리포트 증분 수집 | Naver 증권 리서치 목록/상세를 파싱해 리포트 데이터를 저장한다. | 리서치/증권사 의견 적재 | Naver 요청과 DB upsert가 포함된다. |
| `interest_news.py` | 뉴스 증분 수집 | 날짜별 Naver 뉴스 링크와 기사 본문을 수집해 저장한다. | 관심 뉴스 raw 데이터 적재 | 웹 요청량과 파싱 실패 처리에 주의한다. |
| `interest_program.py` | 프로그램 매매 증분 수집 | KRX 웹에서 CSV를 다운로드하고 프로그램 매매 데이터를 DB에 저장한다. | KRX 프로그램 매매 일일 적재 | Selenium/Chrome, 다운로드 폴더, DB upsert에 의존한다. |
| `interest_shortsell.py` | 공매도 증분 수집 | KRX 웹에서 시장별 CSV를 다운로드하고 universe 종목으로 필터링해 저장한다. | KRX 공매도 일일 적재 | Selenium/Chrome, CSV 파일, universe 필터, DB upsert를 확인한다. |
| `interest_ticker_main.py` | 종목 기본 정보 수집 | Naver/yfinance 기반 기본 속성을 조회해 관심종목 정보를 저장한다. | ticker master성 정보 보강 | 외부 요청과 DB 쓰기가 포함된다. |
| `interest_ticker_value.py` | 종목 valuation 수집 | Naver 기반 valuation 값을 파싱해 DB에 저장한다. | 종목 가치지표 보강 | 원천 JSON/HTML 구조 변경에 취약할 수 있다. |
| `interest_ticker_finance.py` | 종목 재무제표 수집 | Selenium과 BeautifulSoup으로 Naver 재무 표 데이터를 파싱해 저장한다. | 종목 재무 데이터 보강 | Chrome/ChromeDriver와 Naver 페이지 구조에 의존한다. |

## History/Backfill 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `interest_price_history.py` | 국내 가격 이력 backfill | universe 전체의 장기 가격 이력을 yfinance에서 조회해 저장한다. | 가격 history 대량 적재 | 대량 외부 요청과 DB 쓰기가 발생한다. |
| `interest_marketbreadth_history.py` | 시장 폭 지표 이력 재계산 | 가격 이력을 기반으로 전체 기간 market breadth를 재계산한다. | 파생 지표 history 재생성 | 대량 DB 읽기/쓰기가 발생하며 계산 의미를 유지해야 한다. |
| `interest_foreignindex_history.py` | 해외지수 이력 backfill | 해외지수별 장기 가격 이력을 yfinance에서 조회해 저장한다. | 해외지수 history 적재 | 대상 ticker와 기간을 확인한다. |
| `interest_macroeconomic_history.py` | 매크로 이력 backfill | 정의된 매크로 ticker의 장기 이력을 수집해 저장한다. | 매크로 history 적재 | yfinance 요청량과 DB upsert 정책을 확인한다. |
| `interest_commodity_history.py` | 원자재 이력 backfill | 원자재 ticker별 장기 가격 이력을 수집해 저장한다. | 원자재 history 적재 | 대상 원자재 목록과 기간을 확인한다. |
| `interest_investorflow_history.py` | 투자자 수급 이력 backfill | 종목별 Naver 수급 페이지 전체를 순회해 저장한다. | 수급 history 적재 | 대량 웹 요청과 페이지 제한에 주의한다. |
| `interest_agency_history.py` | 증권사 리포트 이력 backfill | Naver 리서치 과거 페이지를 순회해 상세 데이터를 저장한다. | 리서치 history 적재 | 페이지 범위, 중복 정책, 요청 간격을 확인한다. |
| `interest_news_history.py` | 뉴스 이력 backfill | 날짜별 뉴스 링크 수집과 기사 파싱을 병렬 처리한다. | 뉴스 history 적재 | 대량 요청과 병렬 처리 부하에 주의한다. |
| `interest_program_history.py` | 프로그램 매매 이력 backfill | KRX CSV를 기간별로 다운로드하고 저장한다. | 프로그램 매매 history 적재 | Selenium, 다운로드 경로, 기간 범위를 확인한다. |
| `interest_shortsell_history.py` | 공매도 이력 backfill | KRX 공매도 CSV를 종목별로 다운로드하고 저장한다. | 공매도 history 적재 | Selenium, universe, 다운로드 파일 처리에 의존한다. |

## Validation/Check 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `interest_data_validate_daily.py` | 일일 데이터 검증 | 최신일, NULL, row count, 이상치, 중복을 빠르게 확인한다. | 일일 수집 후 품질 점검 | DB 읽기와 휴일 API 요청 가능성이 있다. |
| `interest_data_validate_all.py` | 전체 데이터 검증 | 테이블별 최신일, NULL, 중복, domain, gap, profile 등을 종합 점검한다. | AWS Migration 전 품질 확인 후보 | 읽기 중심이나 DB와 외부 휴일 API 의존성이 있다. |
| `interest_price_check.py` | 가격 누락 점검 | 최근 영업일 기준 가격 미수집 종목을 계산해 출력한다. | price 적재 누락 확인 | DB 읽기와 휴일 판정에 의존하며 저장 로직은 없다. |
| `interest_krx_raw_validate_daily.py` | KRX raw 적재 검증 | `interest_program_raw`와 `interest_shortsell_raw`의 최신 `trade_date`와 row_count를 확인해 KRX worker 수집 결과를 검증한다. | KRX GUI worker 수집 후 raw 적재 여부 판단 | 검증 실패 시 exit code 30으로 종료해 후속 단계가 부적재 상태에서 이어지지 않게 한다. DB 읽기 전용이며 외부 요청은 없다. |

## KRX/Selenium/Chrome 보조 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `interest_krx_chrome.py` | KRX Chrome 세션 준비 | 디버그 Chrome 실행, 포트 확인, 창 포커스 제어를 수행한다. | KRX 수집 전 브라우저 환경 준비 | Windows GUI와 로컬 Chrome 상태에 영향을 준다. |
| `interest_krx_login_new.py` | KRX 로그인 보조 | Selenium으로 KRX 로그인 상태와 팝업/iframe을 처리한다. | KRX 수집 전 인증 상태 준비 | 계정/브라우저 상태에 의존하며 민감정보는 환경변수/로컬 설정으로만 다룬다. |

## Universe/Sector 구성 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `build_stock_universe.py` | stock universe 수집 | Naver 증권 화면을 스크롤 수집해 시장별 종목 universe를 저장한다. | reference/universe 구성 | Selenium, Naver 페이지 구조, DB 쓰기에 의존한다. |
| `build_sector_mapping.py` | sector mapping 보강 | yfinance sector/industry 영문 값을 한국어 매핑 테이블에 보강한다. | sector/industry 매핑 후보 생성 | yfinance 요청과 DB upsert가 포함된다. |
| `build_universe_sector.py` | universe sector 보강 | universe 종목의 sector/industry를 yfinance로 조회하고 매핑한다. | universe 업종 정보 보강 | DB mapping 전제와 yfinance 응답 품질에 의존한다. |

## 공통/설정/보조 파일

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `db_config.py` | DB 설정 공통 모듈 | `INTEREST_DB_*` 환경변수와 search_path 기준으로 PostgreSQL 접속 설정을 만든다. | DB 접속 설정 중복 제거 | 실제 password 값은 코드/문서에 기록하지 않는다. |
| `interest_get_holidays.py` | 휴일 조회 보조 | 국가별 공휴일 API를 호출해 시장 휴일 여부를 판단한다. | 수집/검증 영업일 판단 | 외부 API 요청이 포함된다. |
| `interest_log_format.py` | 로그 출력 보조 | 수집 단계별 결과와 일일 summary 출력 형식을 통일한다. | 콘솔 로그 포맷 공통화 | 외부 요청/DB 접근은 없다. |

## 문서 파일

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | 작업 지침 | 프로젝트 범위, 금지 작업, 보안/Git/문서화 규칙을 정의한다. | 협업 및 자동화 작업 안전 기준 | 민감정보와 실제 실행 금지 규칙을 우선 적용한다. |
| `README.md` | 프로젝트 개요 | 구조, 실행 방법, 설정 방법, 외부 의존성, 안전 제약을 설명한다. | 사용자 관점 프로젝트 안내 | 구조/실행/설정 변경이 있을 때만 갱신한다. |
| `CHANGELOG.md` | 변경 이력 | 날짜별 주요 변경, 문서화, 기능 변경 여부를 기록한다. | 릴리스/작업 변경 요약 | 실제 변경 내용만 짧게 기록한다. |
| `docs/database.md` | DB 구조 문서 | portfolio 단일 DB, domain schema, search_path, secrets 기준을 정리한다. | AWS Migration 전 DB 구조 이해 | 실제 접속정보나 secret 값은 기록하지 않는다. |
| `docs/source-file-catalog.md` | 전체 파일 카탈로그 | 주요 파일별 역할, 내용, 운영 주의사항을 표로 정리한다. | Migration 전 파일 단위 인벤토리 | unused/legacy 후보는 삭제하지 않고 후보로만 표시한다. |
| `docs/worklog/2026-05-26.md` | 2026-05-26 작업 일지 | 초기 문서화와 1차 정리 내용을 기록한다. | 날짜별 작업 추적 | 기존 들여쓰기 형식을 유지한다. |
| `docs/worklog/2026-05-27.md` | 2026-05-27 작업 일지 | DB 환경변수 공통화와 schema-per-domain 문서화를 기록한다. | 날짜별 작업 추적 | 민감정보 값은 기록하지 않는다. |
| `docs/worklog/2026-05-28.md` | 2026-05-28 작업 일지 | 파일 카탈로그 작성과 파일별 설명 주석 추가 작업을 기록한다. | 날짜별 작업 추적 | 완료/예정/보류 상태 표기 형식을 유지한다. |

## 정리 후보

| 파일 경로 | 한글 제목 | 파일 내용 | 주요 역할 | 수정/운영 시 주의사항 |
| --- | --- | --- | --- | --- |
| `block_watch_backtest_run.py` | 로컬 백테스트 실행 후보 | 블록 감시 백테스트 실행용으로 보이는 로컬 실험 파일이다. | 운영 수집과 직접 연결 여부 확인 대상 | 삭제하지 않고 정리 후보로만 표시한다. |
| `dump_public_schema_final.py` | public schema 덤프 후보 | pg_dump와 DB 조회로 public schema DDL/샘플을 정리한다. | Migration 참고용 로컬 점검 후보 | 실행 시 DB 읽기와 로컬 파일 생성이 발생할 수 있다. |
| `patch_research_decision_dependency.py` | research/decision 의존성 패치 후보 | Crawler 소유가 아닌 인접 도메인 의존성을 다루는 것으로 보이는 일회성 스크립트 후보다. | 운영 수집과 직접 연결 여부 확인 대상 | Crawler 책임 범위 밖으로 보이므로 삭제하지 않고 정리 후보로만 표시한다. 실행 여부는 별도 확인이 필요하다. |
