# CHANGELOG

port-interest-crawler 코드와 문서의 주요 변경 이력을 기록한다.

## 작성 원칙

| 항목 | 값 |
| --- | --- |
| 기록 범위 | Crawler 코드 · 수집 script · validation · 설정 · 테스트 · 문서 |
| 제외 범위 | 다른 MS 내부 구현 · orchestration 전체 정의 · 일회성 운영 로그 |
| 정렬 | 최신 날짜를 상단에 추가 |
| 분류 | Added · Changed · Fixed · Removed · Security |
| 실행 기록 | 실제 수행한 검증만 기록 |
| 민감정보 | credential · host · ARN · command id 원문 금지 |

## 2026-07-22 — Crawler 문서 기준 재정비

### Changed

| 항목 | 값 |
| --- | --- |
| `AGENTS.md` | Crawler 전용 작업 규칙으로 전면 재작성 |
| 최우선 규칙 | 신규 독립 표 2컬럼 · 국소 수정 · 긴 셀 금지 |
| 실행 위험 | 외부 원천 · Selenium · DB upsert 기준 강화 |
| 실행 모델 | non-GUI Daily와 Windows KRX worker 분리 |
| Daily · History | 최신 수집과 backfill 책임 구분 |
| KRX 안전 | 점검 · redirect · timeout strict-exit 기준 정리 |
| Validation | expected date · row count · downstream 차단 기준 정리 |
| DB 기준 | `interest` schema · upsert · transaction 주의사항 정리 |
| 테스트 기준 | HTTP · yfinance · Selenium · DB mock 우선 |
| `README.md` | 현재 상태 · 책임 경계 · 실행 모델 중심으로 전면 재구성 |
| 문서 체계 | README · CHANGELOG · source catalog 중심으로 정리 |
| `docs/source-file-catalog.md` | 5열 장문 목록을 책임 · 위험 · 변경 영향 중심의 2열 구조로 재구성 |
| `docs/source-file-catalog.md` | Windows KRX worker wrapper `ops/run_krx_worker_daily.ps1` 반영 |
| Worklog 정책 | 날짜별 worklog 신규 생성을 중단하고 CHANGELOG로 통합 |

### Fixed

| 항목 | 값 |
| --- | --- |
| `AGENTS.md` | KRX strict-exit의 `OPEN 단계` 표현을 실제 코드 기준 `downstream 단계`로 수정 |
| `README.md` · `docs/source-file-catalog.md` | 미존재 `docs/database.md` 참조 제거 |
| `README.md` | validation 파일 생성 표현을 DB 연결 또는 외부 요청 포함으로 축약 |

### Security

| 항목 | 결과 |
| --- | --- |
| Python 코드 변경 | 없음 |
| Crawler · History · Validation 실행 | 0건 |
| Naver · yfinance · KRX 호출 | 0건 |
| Selenium · Chrome 실행 | 0건 |
| DB · AWS · Windows Task 실행 | 0건 |
| Git write 명령 | 0건 |
| 민감정보 원문 신규 기록 | 0건 |

## 2026-07-01 — Hybrid 실행과 KRX Raw Validation 문서화

### Added

| 항목 | 값 |
| --- | --- |
| AWS 운영 구조 | AWS Paper 데이터 수집 실행 단위 |
| non-GUI Daily | `interest_crawler_daily_nongui.py` |
| Windows KRX worker | GUI · Selenium · Chrome 실행 표면 |
| KRX strict-exit | 점검 · redirect · timeout 실패 기준 |
| KRX validation | `interest_krx_raw_validate_daily.py` |
| 실험 후보 | `patch_research_decision_dependency.py` |
| Source catalog | 신규 entrypoint와 후보 파일 반영 |
| Worklog | `docs/worklog/2026-07-01.md` |

### Changed

| 항목 | 값 |
| --- | --- |
| README 주요 기능 | Hybrid 실행 모델 반영 |
| KRX 운영 | program · shortsell 수집 후 raw validation 명시 |
| 책임 경계 | Crawler와 orchestration · Preprocessor 분리 |

### Security

| 항목 | 결과 |
| --- | --- |
| 기능 변경 | 없음 |
| 외부 API · Selenium 실행 | 0건 |
| DB · AWS · Slack 실행 | 0건 |
| 민감정보 원문 신규 기록 | 0건 |

## 2026-05-28 — Database와 Source Catalog 문서화

### Added

| 항목 | 값 |
| --- | --- |
| `docs/database.md` | 단일 DB와 schema-per-domain 구조 |
| `docs/source-file-catalog.md` | 주요 소스와 문서 책임 |
| Module docstring | 파일별 실행 영향과 외부 · DB 의존성 |
| Worklog | `docs/worklog/2026-05-28.md` |

### Changed

| 항목 | 값 |
| --- | --- |
| Database | 기본값 `portfolio` |
| 환경변수 | `INTEREST_DB_NAME` · `PORTFOLIO_DB_NAME` 기준 통일 |
| search path | `interest, reference, legacy, public` |
| SQL 호환 | 기존 unqualified SQL의 search path 전제 문서화 |
| 보안 | credential은 환경변수 또는 local config로 분리 |
| README | source catalog와 주석 작성 기준 반영 |

### Security

| 항목 | 결과 |
| --- | --- |
| 기능 변경 | 없음 |
| Crawler · DB 실행 | 0건 |
| 민감정보 원문 신규 기록 | 0건 |

## 2026-05-27 — DB 설정 외부화

### Changed

| 항목 | 값 |
| --- | --- |
| DB loader | `db_config.py`의 `get_db_config()` |
| 환경변수 | `INTEREST_DB_*` |
| Password | Python script 하드코딩 후보 제거 |
| README | placeholder 기반 DB 설정 예시 |

### Security

| 항목 | 결과 |
| --- | --- |
| 실제 DB 접속 | 0건 |
| 외부 API · Selenium 실행 | 0건 |
| 민감정보 원문 신규 기록 | 0건 |

## 2026-05-26 — 초기 문서와 1차 파일 정리

### Added

| 항목 | 값 |
| --- | --- |
| `AGENTS.md` | 초기 Crawler 작업 규칙 |
| `README.md` | 프로젝트 구조 초안 |
| Worklog | `docs/worklog/2026-05-26.md` |

### Changed

| 항목 | 값 |
| --- | --- |
| README 구조 | 1차 unused · legacy 정리 결과 반영 |
| 문서 기준 | 현재 파일과 import · entrypoint 확인 결과 사용 |

### Removed

| 항목 | 값 |
| --- | --- |
| 문서 참조 | 삭제된 test · debug · dump · legacy 후보 참조 |

### Security

| 항목 | 결과 |
| --- | --- |
| Crawler · 외부 API 실행 | 0건 |
| Selenium · KRX · DB 실행 | 0건 |
| 민감정보 원문 신규 기록 | 0건 |
