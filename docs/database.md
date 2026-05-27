# Database

## Overview

`port-interest-crawler`는 portfolio system의 interest data 수집 모듈이며, PostgreSQL 단일 DB `portfolio`를 기본 대상으로 사용한다.

AWS Migration 준비 관점에서도 DB를 domain별로 분리하지 않고, 하나의 PostgreSQL DB `portfolio` 안에서 schema-per-domain 구조를 사용한다.

## Database name

기본 DB name은 `portfolio`다.

- `INTEREST_DB_NAME`: 기본값 `portfolio`
- `PORTFOLIO_DB_NAME`: 기본값 `portfolio`

현재 모듈에서는 기존 호환성을 위해 `INTEREST_DB_*` 환경변수를 우선 사용한다. portfolio system 공통 설정을 사용하는 환경에서는 `PORTFOLIO_DB_NAME`도 같은 DB name인 `portfolio`로 맞춘다.

## Domain schemas

portfolio DB는 다음 domain schema를 사용한다.

- `reference`
- `interest`
- `preprocessor`
- `research`
- `decision`
- `execution`
- `connector`
- `ops`
- `legacy`
- `public`

기존 `public` schema의 테이블은 domain별 schema로 이동되었으며, 현재 `public`에 잔존 테이블은 없다.

## Search path

이 모듈의 DB connection `search_path`는 다음 순서로 사용한다.

```sql
interest, reference, legacy, public
```

schema-per-domain 전환 후에도 기존 SQL은 이 `search_path`를 기준으로 동작한다. 즉, schema qualifier가 없는 기존 SQL은 `interest`를 우선 조회하고, 공통 참조 데이터는 `reference`, 이전 호환 테이블은 `legacy`, 마지막 fallback은 `public` 순서로 해석된다.

## Secrets

DB password, API token, account number, webhook URL 같은 민감정보는 환경변수 또는 로컬 설정으로 관리한다.

문서, 코드 예시, 로그, 검증 결과에는 실제 password, token, account, webhook 값을 기록하지 않는다. 예시가 필요하면 `[REDACTED]`로 마스킹한다.
