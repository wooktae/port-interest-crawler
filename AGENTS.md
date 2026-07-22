# port-interest-crawler 작업 규칙

이 문서는 `port-interest-crawler` 마이크로서비스의 Python 수집 코드, history/backfill, validation, KRX worker, 설정, 테스트와 문서를 수정할 때 적용하는 기준이다.

`port-interest-crawler` 관련 작업은 이 문서만 읽어도 작업 범위, 외부 데이터 원천, 실행 위험, hybrid 운영 구조, DB 적재 책임과 검증 원칙을 이해할 수 있어야 한다.

## 0. 최우선 문서 가독성 규칙

모든 문서 작업에서 본 섹션을 최우선으로 적용한다.

### 0.0 적용 범위 제한

가독성 규칙은 이번 작업에서 새로 작성하거나 직접 수정하는 부분에만 적용한다.

사용자가 문서 전체 정리나 전수 점검을 명시하지 않은 경우 아래 작업은 수행하지 않는다.

| 항목 | 기본 처리 |
| --- | --- |
| 기존 문서 전체 전수 스캔 | 수행하지 않음 |
| README 전체 재구성 | 수행하지 않음 |
| CHANGELOG 과거 이력 대량 정리 | 수행하지 않음 |
| 신규 scanner · audit 도구 작성 | 수행하지 않음 |
| sub-agent · orchestrator 생성 | 수행하지 않음 |

변경 인접부는 같은 표 행, 같은 bullet 묶음, 같은 짧은 문단까지만 본다.

범위 밖의 기존 위반은 원본을 유지하고 필요 시 후속 후보로만 남긴다.

### 0.1 표 작성 규칙

새로 만드는 독립 요약 표는 기본적으로 2컬럼으로 작성한다.

기본 헤더는 `항목 / 값`이다.

아래 상황에서는 더 구체적인 2컬럼 헤더를 사용할 수 있다.

| 상황 | 우선 헤더 |
| --- | --- |
| 파일별 변경 | `파일 / 변경` |
| entrypoint 설명 | `파일 / 역할` |
| 데이터 원천 | `원천 / 처리` |
| 검증 결과 | `항목 / 결과` |
| 설정 정리 | `설정 / 값` |
| 위험 정리 | `위험 / 처리` |
| 테스트 결과 | `테스트 / 결과` |

기존 표에 행을 추가하는 경우 기존 컬럼 구조를 유지한다.

3컬럼 이상 표는 다음 경우에만 허용한다.

| 조건 | 처리 |
| --- | --- |
| 사용자가 명시적으로 요청 | 요청 구조 사용 |
| 기존 표 보존이 더 안전 | 기존 구조 유지 |
| 비교 구조상 2컬럼 변환 시 의미 손실 | 예외 허용 |

### 0.2 표 셀과 문장 길이

- 표 셀은 2문장 이하로 유지한다.
- 한 셀에 여러 값이 있으면 `<br>`로 나눈다.
- 한 셀에 3개 이상의 사실을 장문으로 넣지 않는다.
- 긴 근거는 표 밖 설명이나 관련 문서 링크로 분리한다.
- 300자 초과 셀과 500자 초과 라인을 만들지 않는다.
- raw log, 전체 HTML, 전체 API 응답, 전체 SQL과 AWS 응답을 문서에 붙이지 않는다.

### 0.3 문서 밀도

문서 작성 우선순위는 아래를 따른다.

1. 짧은 Summary
2. 짧은 2컬럼 표
3. 짧은 bullet
4. 상세 문서 링크
5. 긴 본문

같은 사실을 README, CHANGELOG, worklog와 상세 문서에 장문으로 반복하지 않는다.

### 0.4 상태 표시

상태 배지는 아래 5종만 사용한다.

| 배지 | 의미 |
| --- | --- |
| 🔴 | 금지 · 고위험 · 실패 |
| 🟠 | 대기 · 관찰 · 미확정 |
| 🟢 | 완료 · 성공 · ENABLED |
| 🔵 | 참고 · 정보 · evidence |
| ⚫ | 해당 없음 |

상태 배지로 충분하면 HTML 색상을 추가하지 않는다.

### 0.5 작업 방식 제한

문서 작업은 아래 순서로 진행한다.

1. 요청 범위 확인
2. 대상 파일 직접 읽기
3. 필요한 부분만 수정
4. UTF-8 No BOM 저장
5. 짧은 after-check
6. 변경 요약 보고

사용자가 명시적으로 요청하지 않는 한 아래 방식은 사용하지 않는다.

- 전체 workspace 전수 스캔
- sub-agent
- orchestrator
- 신규 scanner
- content hash matrix
- workspace 밖 임시 파일
- 과도한 자동화 스크립트

## 1. Scope

### 1.1 기본 작업 디렉터리

`C:\Workspaces\port-interest-crawler`

### 1.2 프로젝트 역할

port-interest-crawler는 외부 데이터 원천에서 관심 데이터를 수집하고 PostgreSQL raw/history 영역에 적재하는 Python 마이크로서비스다.

| 영역 | 역할 |
| --- | --- |
| Price | 국내외 가격과 시계열 |
| News · Research | 뉴스와 리서치 자료 |
| Flow | 투자자 수급과 기관 데이터 |
| KRX | 공매도와 프로그램 매매 |
| Macro | 해외지수 · 매크로 · 원자재 |
| Ticker | 종목 기본 · 가치 · 재무 |
| Universe | 종목 universe와 sector mapping |
| Validation | 최신성 · row count · gap 확인 |
| History | 과거 기간 backfill |
| Persistence | `interest` raw/history 적재 |

### 1.3 기본 수정 대상

| 구분 | 대상 |
| --- | --- |
| Python | 루트 `*.py`와 package Python 파일 |
| Daily | 일일 수집 entrypoint |
| History | `*_history.py`와 backfill 관련 코드 |
| Validation | `*_validate*.py` · `*_check.py` |
| KRX | Selenium · Chrome · 로그인 · download 처리 |
| Script | shell · PowerShell · worker wrapper |
| 설정 | 환경변수 loader · local config 관련 코드 |
| 테스트 | `tests` · `test_*.py` |
| 문서 | `README.md` · `CHANGELOG.md` · `docs` |
| 의존성 | requirements · pyproject · lock 관련 파일 |

현재 요청에 포함되지 않은 파일은 수정하지 않는다.

### 1.4 다른 마이크로서비스

아래 프로젝트는 외부 의존 모듈이다.

- `port-view`
- `port-marketconnector`
- `port-interest-preprocessor`
- `port_strategy_common`
- `port_strategy_research`
- `port_strategy_decision`
- `port_strategy_execution`

현재 작업이 명시적으로 요구하지 않는 한 다른 MS의 코드와 문서는 수정하지 않는다.

`.kiro`의 cross-service spec도 port-interest-crawler 작업 범위에 자동 포함하지 않는다.

## 2. 실행 위험 등급

이 저장소의 스크립트는 import 또는 실행 시 외부 요청, 브라우저 기동, 파일 다운로드와 DB 쓰기로 이어질 수 있다.

모든 Python 파일을 일반적인 smoke test 대상으로 취급하지 않는다.

### 2.1 운영 · Daily 위험

| 파일 | 위험 |
| --- | --- |
| `interest_crawler_daily.py` | 다수 원천 호출과 DB 적재 가능 |
| `interest_crawler_daily_nongui.py` | non-GUI 외부 호출과 DB upsert |
| `interest_crawler_main.py` | 통합 수집 흐름 실행 가능 |
| `interest_price.py` | 가격 요청과 저장 |
| `interest_news.py` | 뉴스 요청과 저장 |
| `interest_investorflow.py` | 투자자 수급 수집과 저장 |
| `interest_program.py` | KRX GUI · 다운로드 · 저장 |
| `interest_shortsell.py` | KRX GUI · 다운로드 · 저장 |

운영 entrypoint는 사용자의 명시적 실행 요청 없이 실행하지 않는다.

### 2.2 History · Backfill 고위험

`*_history.py` 파일은 장기간 외부 요청과 대량 DB 적재를 수행할 수 있다.

| 위험 | 처리 |
| --- | --- |
| 긴 기간 요청 | 대상 기간 사전 확인 |
| API rate limit | 원천별 제한 확인 |
| 대량 upsert | unique key와 transaction 확인 |
| 중복 적재 | idempotency와 conflict 정책 확인 |
| 부분 실패 | 재시작 기준과 checkpoint 확인 |
| 소요 시간 | 일반 검증으로 실행 금지 |

history와 backfill은 사용자 요청에 기간, 대상 원천과 DB 환경이 명확할 때만 실행한다.

### 2.3 Validation · Check 위험

validation 파일도 DB 연결이나 외부 요청을 포함할 수 있다.

이름에 `validate`, `check`가 있다는 이유만으로 read-only라고 판단하지 않는다.

실행 전 아래를 확인한다.

- DB 연결 여부
- SQL 종류
- 외부 원천 호출 여부
- 파일 생성 여부
- exit code 의미
- 실패 시 downstream 차단 여부

### 2.4 KRX · Browser 위험

| 영역 | 위험 |
| --- | --- |
| Selenium | Chrome 프로세스와 GUI 세션 |
| KRX login | credential · 세션 · redirect |
| Download | CSV와 임시 파일 생성 |
| Parsing | 점검 페이지를 데이터로 오인 |
| Timeout | 부분 적재 후 정상 종료 오인 |
| Worker | Windows Scheduled Task 실행 가능 |

문서 작업과 정적 분석 중에는 Chrome, ChromeDriver와 Selenium을 실행하지 않는다.

## 3. Hybrid 실행 모델

Crawler는 GUI 의존 여부에 따라 두 실행 표면으로 분리한다.

### 3.1 Non-GUI Daily

| 항목 | 기준 |
| --- | --- |
| Entrypoint | `interest_crawler_daily_nongui.py` |
| 실행 후보 | Container · ECS Fargate RunTask |
| 포함 | Naver · yfinance · 휴일 확인 · DB 적재 |
| 제외 | KRX GUI login · program · shortsell |
| 책임 | non-GUI 원천 수집과 raw 적재 |

non-GUI entrypoint에 Selenium, Chrome과 GUI KRX 수집을 다시 결합하지 않는다.

### 3.2 Windows KRX Worker

| 항목 | 기준 |
| --- | --- |
| 환경 | Windows GUI |
| 실행 후보 | Scheduled Task |
| 수집 | KRX program · shortsell |
| 처리 | 로그인 · CSV 다운로드 · parse · upsert |
| 후속 | KRX raw validation |

Windows worker의 GUI 의존 코드를 container 경로로 옮기지 않는다.

### 3.3 책임 경계

| 영역 | 책임 |
| --- | --- |
| Crawler | 외부 데이터 수집과 raw/history 적재 |
| Scheduler · Step Functions | 실행 시각과 orchestration |
| Windows worker | KRX GUI 수집 |
| Preprocessor | raw를 feature로 변환 |
| View | 실행 상태 조회와 trigger UI |

Crawler 안에 Preprocessor와 전략 판단 로직을 복제하지 않는다.

## 4. 외부 데이터 원천 기준

### 4.1 Naver

- request timeout과 user-agent를 명시한다.
- 응답 HTML 구조 변경을 빈 정상 데이터로 처리하지 않는다.
- 뉴스와 리서치 중복 key를 확인한다.
- Naver Open API credential을 출력하지 않는다.
- encoding과 날짜 파싱 실패를 명시적으로 처리한다.

### 4.2 yfinance

- ticker와 market suffix를 확인한다.
- timezone과 trade date 기준을 확인한다.
- 빈 DataFrame을 정상 적재 완료로 처리하지 않는다.
- 일부 ticker 실패와 전체 실패를 구분한다.
- 자동 retry와 sleep은 rate limit을 고려한다.

### 4.3 KRX

- 점검 페이지, redirect와 login 화면을 정상 CSV로 처리하지 않는다.
- 다운로드 파일명만으로 성공을 판정하지 않는다.
- expected date, row count와 필수 컬럼을 확인한다.
- Selenium timeout 뒤 부분 파일을 사용하지 않는다.
- strict-exit와 fail-fast 의미를 유지한다.

### 4.4 휴일과 거래일

- Asia/Seoul 기준 날짜를 사용한다.
- 주말, 공휴일과 실제 거래일을 구분한다.
- 휴일 API 실패를 무조건 시장 개장일로 해석하지 않는다.
- history/backfill은 실제 거래일 gap과 calendar gap을 구분한다.

## 5. Python 코드 작성 규칙

### 5.1 공통 원칙

- 기존 파일명, CLI option, source 값과 DB 의미를 우선 유지한다.
- module import만으로 외부 요청, browser 실행과 DB 쓰기가 발생하지 않게 한다.
- entrypoint는 `if __name__ == "__main__":` 경계를 유지한다.
- 수집, parse, transform과 persist 단계를 가능한 한 구분한다.
- 실패를 성공, `NO_CHANGE` 또는 빈 데이터 정상으로 바꾸지 않는다.
- 일회성 장애 우회를 영구 fallback으로 추가하지 않는다.

### 5.2 HTTP 요청

- timeout을 명시한다.
- status code와 응답 내용 형식을 함께 검증한다.
- retry 대상과 비대상을 구분한다.
- 4xx와 인증 실패를 무한 retry하지 않는다.
- 원천별 rate limit과 backoff를 확인한다.
- 요청 URL에 credential을 로그로 남기지 않는다.

### 5.3 Parse

- 필수 컬럼과 타입을 확인한다.
- 날짜, 숫자와 결측값 변환 실패를 숨기지 않는다.
- HTML error page와 CSV를 구분한다.
- 일부 row parse 실패를 전체 성공으로 보고하지 않는다.
- 원본 source 의미를 임의 변경하지 않는다.

### 5.4 Persist

- 기존 unique key와 conflict/upsert 정책을 유지한다.
- source, ticker, trade_date와 수집 시각 의미를 확인한다.
- transaction과 rollback 경계를 유지한다.
- 부분 적재 후 성공 marker를 출력하지 않는다.
- 대량 적재는 batch size와 commit 단위를 확인한다.
- validation 전 부적재 상태를 성공으로 확정하지 않는다.

### 5.5 Exit 결과 설계 기준

| 결과 | 기준 |
| --- | --- |
| SUCCESS | 기대 데이터 적재와 검증 통과 |
| NO_CHANGE | 정상적으로 신규 적재 대상 없음 |
| SKIP | 휴일 등 명시적 정상 제외 |
| FAILURE | 외부 요청 · parse · DB 실패 |
| BLOCKER | downstream 진행 금지 상태 |

현재 코드의 실제 status 문자열과 exit code를 우선하며, 위 분류는 신규 또는 수정 코드에서 결과 의미를 구분하기 위한 설계 기준으로 사용한다.

코드가 실제로 사용하는 `SUCCESS`, `FAILED`, `NO_CHANGE`는 현재 구현 사실로 인정하고, `SKIP`, `FAILURE`, `BLOCKER`를 현재 모든 코드가 출력한다고 설명하지 않는다.

`FAILED`와 `FAILURE`를 억지로 하나로 통일하지 않는다.

문서에서 성공과 `NO_CHANGE`를 임의로 합치지 않는다.

## 6. KRX strict-exit와 Raw Validation

### 6.1 Strict-exit

다음 상황은 정상 완료로 처리하지 않는다.

- KRX 점검 페이지
- login redirect
- session 만료
- download timeout
- 빈 CSV
- 필수 컬럼 누락
- expected date 미달
- row count 0
- downstream 단계에 필요한 raw 미적재

### 6.2 Daily Raw Validation

`interest_krx_raw_validate_daily.py`는 KRX raw 최신성을 확인하는 validation entrypoint다.

| 대상 | 확인 |
| --- | --- |
| `interest_program_raw` | 최신 `trade_date` · row count |
| `interest_shortsell_raw` | 최신 `trade_date` · row count |
| Expected date | 실행 기준 거래일 |
| 실패 | non-zero exit |
| 목적 | downstream 부적재 진행 차단 |

validation 결과를 맞추기 위해 expected date나 최소 row count를 근거 없이 낮추지 않는다.

### 6.3 데이터 공백과 Raw 불일치

수집 원천이 빈 결과를 반환했을 때 아래를 구분한다.

- 정상 휴일
- 원천 데이터 미공개
- KRX 점검
- redirect 또는 login 실패
- parse 실패
- 실제 데이터 0건
- 기존 최신 데이터 유지 상태

원인을 확인하지 않고 이전 데이터를 당일 성공 데이터로 재사용하지 않는다.

## 7. Daily와 History 분리

### 7.1 Daily

Daily 스크립트는 최신 거래일 적재와 당일 운영 안정성을 우선한다.

- 제한된 대상 기간
- 명확한 expected date
- 빠른 실패
- downstream validation
- 반복 실행 idempotency

### 7.2 History

History 스크립트는 과거 구간의 완전성과 재시작 가능성을 우선한다.

- 시작일과 종료일
- 거래일 목록
- chunk 단위
- checkpoint
- 원천별 rate limit
- gap 재수집
- 중복 방지

Daily entrypoint에 장기 backfill 기능을 숨겨 넣지 않는다.

History 스크립트를 Scheduler의 일일 기본 경로로 사용하지 않는다.

## 8. Database 기준

### 8.1 연결

| 항목 | 값 |
| --- | --- |
| Database | `portfolio` |
| Config loader | `db_config.py`의 `get_db_config()` |
| 환경변수 | `INTEREST_DB_*` |
| Password | 기본값 없음 |
| search path | `interest, reference, legacy, public` |

실제 운영 환경에서는 Crawler 전용 DB user를 사용한다.

`postgres` 기본값이 코드나 과거 문서에 있더라도 운영 권한 기준으로 해석하지 않는다.

### 8.2 Schema 책임

| Schema | 역할 |
| --- | --- |
| `interest` | raw · history · 수집 결과 |
| `reference` | ticker · market · calendar 기준정보 |
| `legacy` | 과거 호환 |
| `public` | fallback search path |

Crawler는 `preprocessor`, `research`, `decision`, `execution`의 비즈니스 결과를 직접 생성하지 않는다.

### 8.3 SQL과 Upsert

- 신규 SQL은 가능한 한 schema-qualified 이름을 사용한다.
- 기존 unqualified SQL은 connection `search_path`와 정합성을 확인한다.
- SQL 수정 전 실제 코드, migration 또는 `information_schema.columns`로 컬럼을 확인한다.
- unique key와 `ON CONFLICT` 의미를 확인한다.
- raw와 history 테이블의 보존 정책을 구분한다.
- delete 후 insert 패턴은 대상 범위를 확인한다.
- 실패한 DB 작업 뒤 SUCCESS를 출력하지 않는다.

## 9. 설정과 민감정보

### 9.1 민감정보

아래 값은 코드, 문서, 예시와 로그에 원문으로 기록하지 않는다.

- DB password와 전체 connection string
- Naver client id · client secret
- KRX credential과 사용자 ID
- token · cookie · session
- Chrome profile 경로
- 실제 DB host와 private IP
- AWS account-id
- 실제 ARN
- instance id
- SSM command id
- local absolute path
- Slack webhook URL

필요한 경우 아래 placeholder를 사용한다.

| Placeholder | 용도 |
| --- | --- |
| `[REDACTED]` | 일반 민감정보 |
| `[REDACTED_DB_HOST]` | DB host |
| `[REDACTED_USER_ID]` | 사용자 ID |
| `[REDACTED_SECRET]` | API secret |
| `[REDACTED_ARN]` | ARN |
| `[REDACTED_INSTANCE_ID]` | instance id |
| `[REDACTED_COMMAND_ID]` | command id |
| `<CHROME_DRIVER_PATH>` | ChromeDriver 경로 |
| `<WINDOWS_KRX_WORKER>` | Windows worker |
| `<CRAWLER_ECS_TASK>` | non-GUI task |

### 9.2 설정 변경

설정 key나 loader를 변경하면 아래를 함께 확인한다.

1. `db_config.py`
2. 해당 entrypoint
3. Daily와 History 호출부
4. Windows KRX worker
5. README
6. 실행 wrapper
7. 배포 환경변수

실제 local config와 credential 값을 읽어 문서에 옮기지 않는다.

## 10. AWS와 Windows 운영 기준

### 10.1 AWS

non-GUI Crawler는 container 또는 ECS Fargate RunTask 후보 실행 단위다.

실제 cluster, task definition ARN과 Scheduler 상태는 외부 운영 사실이다.

사용자가 명시적으로 요청하지 않는 한 AWS API를 호출하거나 리소스를 변경하지 않는다.

### 10.2 Windows Worker

Windows KRX worker는 GUI session과 Scheduled Task에 의존할 수 있다.

- GUI 사용 가능 session인지 확인한다.
- Chrome과 ChromeDriver 호환성을 확인한다.
- download directory를 명시한다.
- 기존 CSV와 신규 CSV를 구분한다.
- Scheduled Task exit code를 확인한다.
- KST timezone을 명시한다.

실제 Scheduled Task 실행은 사용자 요청 없이 수행하지 않는다.

### 10.3 운영 명령 작성

- 동적 식별자는 `list/describe → 변수 추출 → 후속 확인` 흐름을 사용한다.
- 실제 instance id, ARN, command id와 private IP를 문서에 남기지 않는다.
- Windows와 Linux shell 문법을 혼합하지 않는다.
- 한글 포함 파일은 UTF-8 No BOM으로 저장한다.
- native command는 exit code를 확인한다.
- 실패 뒤 SUCCESS 또는 DONE marker를 출력하지 않는다.

## 11. 실행 제한

사용자가 명시적으로 요청하지 않는 한 아래 작업을 수행하지 않는다.

| 구분 | 금지 작업 |
| --- | --- |
| Crawler | Daily · Main · 개별 수집 실행 |
| History | backfill · gap fill 실행 |
| Validation | DB 연결 validation 실행 |
| Network | Naver · yfinance · KRX · 휴일 API 호출 |
| Browser | Selenium · Chrome · ChromeDriver 실행 |
| KRX | login · CSV download |
| DB | DDL · DML · migration · psql |
| AWS | ECS · SSM · Scheduler 실행 또는 변경 |
| Windows | Scheduled Task 실행 또는 변경 |
| Slack | webhook 또는 notifier 호출 |
| Git | add · commit · push · reset · restore |

읽기 전용 검증도 사용자의 요청 범위에서만 수행한다.

## 12. 테스트와 검증

### 12.1 기본 원칙

- 실제 외부 원천과 DB 없이 가능한 unit test를 우선한다.
- HTTP, yfinance, Selenium, filesystem과 DB connection을 mock 또는 stub으로 격리한다.
- 실제 credential과 운영 환경변수를 테스트에 사용하지 않는다.
- 테스트가 Chrome과 network를 자동 실행하지 않게 한다.
- history 테스트는 짧은 fixture 기간만 사용한다.

### 12.2 변경별 최소 검증

| 변경 대상 | 최소 검증 |
| --- | --- |
| Python 문법 | 안전한 compile check |
| HTTP parser | 저장된 fixture response |
| HTML parser | 로컬 fixture HTML |
| CSV parser | 로컬 fixture CSV |
| yfinance 처리 | DataFrame mock |
| KRX login · download | Selenium mock |
| Daily orchestration | child call mock · exit code |
| History | chunk · checkpoint · idempotency |
| Validation | DB result mock · expected date |
| Repository | SQL · parameter · upsert test |
| 문서 | 링크 · 사실 · 가독성 |
| Script | syntax · 인자 전달 정적 확인 |

실행 위험 import가 있는 파일은 compile 과정에서도 side effect 여부를 먼저 확인한다.

실행하지 못한 검증은 완료로 기록하지 않고 사유를 남긴다.

## 13. 문서 관리 규칙

### 13.1 README.md

README는 port-interest-crawler의 현재 구조와 운영 AS-IS를 설명한다.

README에 포함할 내용:

- 프로젝트 역할
- 주요 데이터 원천
- Daily · History · Validation 구분
- non-GUI와 Windows KRX worker
- strict-exit와 raw validation
- DB와 schema
- 설정과 외부 의존성
- AWS · Windows 운영 경계
- 보안과 실행 제한
- 상세 문서 링크

다른 MS와 Step Functions 전체 정의를 장문으로 복사하지 않는다.

### 13.2 CHANGELOG.md

CHANGELOG는 port-interest-crawler 코드와 문서의 주요 변경만 기록한다.

- 최신 날짜를 상단에 추가한다.
- `Added`, `Changed`, `Fixed`, `Removed`, `Security`를 필요에 따라 사용한다.
- 실제 Crawler 변경만 기록한다.
- 일회성 실행 시각, command id와 raw log를 기록하지 않는다.
- 신규 섹션부터 2컬럼 표 중심으로 작성한다.
- 과거 이력은 별도 요청이 없으면 원본을 유지한다.

### 13.3 docs

새 문서를 만들기 전에 README, CHANGELOG와 기존 docs에 흡수 가능한지 먼저 확인한다.

날짜별 `docs/worklog/*.md`는 신규 생성하지 않는다.

코드와 문서 변경 이력은 `CHANGELOG.md`에 기록한다.

### 13.4 source-file-catalog.md 자동 갱신

`docs/source-file-catalog.md`가 존재하는 경우 아래 변경이 발생하면 같은 작업에서 갱신 여부를 반드시 확인한다.

| 변경 | 처리 |
| --- | --- |
| 주요 Python 파일 생성 · 삭제 · 이름 변경 | 카탈로그 갱신 |
| Daily · History · Validation 책임 변경 | 역할과 위험 갱신 |
| non-GUI · KRX worker 구조 변경 | 실행 모델 갱신 |
| 데이터 원천 · parser 책임 변경 | 원천과 주의사항 갱신 |
| 설정 · DB loader 역할 변경 | 설정 항목 갱신 |
| scripts · worker wrapper 변경 | 운영 항목 갱신 |
| 문서 생성 · 삭제 · 역할 변경 | Documents 항목 갱신 |
| 내부 구현만 변경 · 책임 동일 | 생략 가능 |

카탈로그는 전체 파일 inventory가 아니다.

운영과 유지보수에 의미 있는 entrypoint, 묶음 경로와 책임만 기록한다.

## 14. Git 규칙

기본적으로 읽기 전용 상태 확인만 허용한다.

| 허용 | 금지 |
| --- | --- |
| `git status --short`<br>`git diff --stat`<br>`git diff --check` | `git add`<br>`git commit`<br>`git push`<br>`git reset`<br>`git restore`<br>`git checkout`<br>`git stash` |

사용자가 명시적으로 요청하지 않는 한 commit을 생성하지 않는다.

## 15. 완료 보고

작업 완료 시 아래만 짧게 보고한다.

| 항목 | 내용 |
| --- | --- |
| 변경 파일 | 실제 수정한 파일 |
| 핵심 변경 | 기능 또는 문서 변경 요약 |
| 실행 위험 | 실행하지 않은 원천 · KRX · DB 경로 |
| 검증 | 수행한 정적 검사와 test |
| 미수행 | 실행하지 못한 검증 |
| 보안 | 민감정보 원문 기록 여부 |
| 후속 | 실제로 남은 항목만 기록 |

운영자가 수행한 작업과 Kiro가 수행한 작업을 구분한다.

## 16. 완료 체크리스트

- [ ] 요청된 port-interest-crawler 파일만 수정했는가?
- [ ] 다른 MS와 `.kiro` 파일을 불필요하게 수정하지 않았는가?
- [ ] 최우선 문서 가독성 규칙을 적용했는가?
- [ ] 신규 독립 표를 기본 2컬럼으로 작성했는가?
- [ ] 긴 셀과 긴 라인을 만들지 않았는가?
- [ ] Daily · History · Validation 역할을 구분했는가?
- [ ] non-GUI와 Windows KRX worker를 혼동하지 않았는가?
- [ ] 외부 원천별 실패와 빈 데이터를 구분했는가?
- [ ] KRX 점검 · redirect · timeout을 성공 처리하지 않았는가?
- [ ] raw validation과 downstream 차단 의미를 유지했는가?
- [ ] history 대량 적재 범위와 idempotency를 확인했는가?
- [ ] DB unique key · upsert · transaction 정합을 확인했는가?
- [ ] 휴일과 거래일 기준을 확인했는가?
- [ ] 민감정보 원문을 기록하지 않았는가?
- [ ] 실패를 SUCCESS · NO_CHANGE로 기록하지 않았는가?
- [ ] 변경 범위에 맞는 안전한 검증을 수행했는가?
- [ ] 파일 구조나 책임이 바뀌면 `docs/source-file-catalog.md`를 확인했는가?
- [ ] 날짜별 `docs/worklog/*.md`를 새로 만들지 않았는가?
- [ ] UTF-8 No BOM으로 저장했는가?
- [ ] 실제 수정 내용만 README와 CHANGELOG에 반영했는가?
