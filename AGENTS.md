# AGENTS.md - port-interest-crawler

## 프로젝트
- 이 저장소는 포트폴리오 관심 데이터 수집을 담당하는 Python 마이크로서비스 루트다.
- 주요 역할은 Naver, yfinance, KRX 등 외부 데이터 원천에서 가격, 뉴스, 리서치, 투자자 수급, 공매도, 프로그램 매매, 매크로/원자재/해외지수 데이터를 수집해 PostgreSQL raw/history 계열 테이블에 적재하는 것이다.
- 현재 구조는 패키지보다 독립 실행형 Python 스크립트 중심이다.
- 운영 스크립트, history/backfill 스크립트, validation/check 스크립트, KRX/Selenium 보조 스크립트, 로컬 dump/test 산출물 후보를 구분해 다룬다.

## 작업 범위
- 현재 `port-interest-crawler` 루트 안에서만 작업한다.
- 현재 루트 밖 파일은 명시 요청 없이 수정하지 않는다.
- 참고용 sibling 프로젝트 문서는 읽기 전용으로만 사용한다.
- 변경은 작고 검증 가능한 단위로 진행한다.
- 코드 또는 문서 수정 전 현재 파일 구조와 실행 영향 범위를 먼저 확인한다.

## 허용 작업
- README / docs 작성 및 수정
- Python 스크립트 구조 분석
- 실행하지 않는 범위의 import, entrypoint, 외부 의존성, DB 접근 지점 확인
- 운영/history/validation/KRX/Naver/yfinance/로컬 산출물 후보 분류
- 안전 제약, 설정 항목, 실행 전제 문서화
- 명시 요청이 있는 경우에만 소스 코드 수정

## 금지 작업
- 실제 크롤링 실행 금지
- 외부 API 호출 금지
- Selenium/Chrome/KRX/Naver/yfinance 요청 실행 금지
- DB DDL/DML 직접 실행 금지
- 주문 제출 또는 주문 실행 금지
- 운영 배치, history backfill, validation job 실행 금지
- 민감정보 값 출력 또는 문서 기록 금지
- 실제 로컬 운영 설정 파일 수정 금지
- 명시 승인 없는 파일 삭제 금지
- 명시 요청 없는 commit 금지

## 유지해야 할 것
- 기존 DB 테이블명, 컬럼명, source 값, unique key, upsert 정책
- 기존 스크립트 파일명과 entrypoint
- 외부 데이터 원천별 접근 방식
- 운영 스크립트와 history/backfill 스크립트의 역할 구분
- validation/check 스크립트의 읽기/검증 의도
- 테스트, debug, html dump, 임시 파일은 운영 소스로 단정하지 않는다.

## 보안 규칙
- 비밀번호, 토큰, API key, 계좌번호, webhook URL, DB 접속정보, 실제 사용자 ID 등 민감정보 값은 출력하거나 문서에 기록하지 않는다.
- 민감정보가 필요하면 `[REDACTED]`로 마스킹한다.
- 로컬 파일에서 민감정보를 발견해도 값을 노출하지 않는다.
- secret은 source가 아니라 환경변수 또는 local config로 분리하는 방향을 우선한다.

## Git 규칙
- 작업 전후 `git status --short`로 변경 범위를 확인한다.
- 작업 후 `git diff --stat`으로 변경 파일 범위를 확인한다.
- 사용자 변경을 되돌리지 않는다.
- 명시 요청 없이 commit하지 않는다.

## 검증 명령
문서만 수정한 경우:

```powershell
git status --short
git diff --stat
```

코드 수정 시에는 실제 외부 요청, 크롤링, DB 쓰기, 주문 실행이 포함되지 않는 검증만 선택한다. 실행 위험이 있으면 완료 보고에 검증 한계를 명확히 적는다.

## 완료 보고
작업 완료 후 아래만 짧게 보고한다.

- 변경 파일
- 변경 요약
- 검증 결과
- 남은 위험 또는 후속 작업

## 문서화 규칙
- README.md는 프로젝트 이해, 실행 방법, 설정 방법, 주요 기능, 폴더 구조, 외부 의존성이 바뀐 경우에만 갱신한다.
- CHANGELOG.md에는 실제 변경된 주요 내용만 짧게 기록한다.
- docs/worklog/YYYY-MM-DD.md에는 작업 내용을 계획/완료 처리 형식으로 정리한다.
- worklog 작성 시 아래 들여쓰기 형식을 유지한다.
  - `1. 큰 작업 명`
  - ` 1) 세부 작업`
  - `   (1) 더 세부 작업`
  - `       - 추가 설명`
- 완료/예정/보류/실패/확인 상태를 작업 명 끝에 `: 완료`, `: 예정`, `: 보류`, `: 실패`, `: 확인`으로 명확히 표시한다.
- 상태값은 `작업 명: 완료`처럼 작업 명과 콜론 사이에 공백을 두지 않는다.
