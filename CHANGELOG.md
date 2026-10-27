# CHANGELOG

Records the primary change history of port-interest-crawler code and documentation.

## Writing Principles

| Item | Value |
| --- | --- |
| Recording scope | Crawler code · collection script · validation · configuration · tests · documentation |
| Excluded scope | Other MS internal implementation · full orchestration definition · one-time operational logs |
| Ordering | Add the latest date at the top |
| Classification | Added · Changed · Fixed · Removed · Security |
| Execution record | Record only validation actually performed |
| Sensitive information | No verbatim credential · host · ARN · command id |

## 2026-08-14 — Crawler Main Push Hybrid Automatic Deployment Completed

### Added

| Item | Value |
| --- | --- |
| Automatic Release | Crawler Hybrid automatic release based on main push |
| ECS release | `release-crawler-ecs.ps1` |
| Windows release | `release-crawler-windows.ps1` |
| ECS flow | Automatic Activation Scope Promotion after side-effect-free Candidate |
| Windows flow | Automatic CodeDeploy run based on versioned S3 artifact |

### Changed

| Item | Value |
| --- | --- |
| GitHub Actions | Performs ECS → Windows Release after Build/Publish |
| GitHub OIDC Role | Extended to a limited Release control-plane privilege |
| Responsibility separation | Clarified separation between Windows deployment and Scheduled Task business execution |

### Validation

| Item | Result |
| --- | --- |
| New commit main push E2E | Success |
| CodeBuild | Success |
| ECS Candidate Exit Code | 0 |
| Activation Scope Promotion | Success |
| Windows CodeDeploy | Success |
| EC2 running state preserved | Confirmed |
| Scheduled Task · KRX GUI automatic execution | None |

### Security

| Item | Result |
| --- | --- |
| SSM SendCommand use | None |
| DB write during Release | None |
| runtime secret included in artifact | None |
| Verbatim ARN · Account ID · Instance ID · credential record | None |

## 2026-08-07 — Crawler Hybrid DevOps Configuration

### Added

| Item | Value |
| --- | --- |
| CI | GitHub Actions OIDC → CodeBuild execution |
| Common gate | Python compile · Source SHA identity validation |
| Windows artifact | Git SHA versioned ZIP pipeline |
| Windows bundle | deterministic ZIP · manifest · file hash contract |
| Windows publish | versioned S3 artifact publish |
| Windows deploy | CodeDeploy IN_PLACE · Candidate staging · lifecycle validation |
| Container artifact | Docker build · Git SHA-based ECR image |
| Publish gate | Independent `PUSH_ARTIFACT` · `PUSH_IMAGE` gate |
| ECS Task Definition | immutable image digest-based configuration |
| ECS Candidate | standalone Fargate RunTask validation |
| ECS promotion | Reflect operational reference after Candidate success |
| ECS rollback | Restore previous revision reference and re-promotion |

### Changed

| Item | Value |
| --- | --- |
| non-GUI Daily | Confirmed the operational execution unit as ECS Fargate RunTask |
| Execution contract | Preserve Docker default CMD · run nongui via ECS Task Definition explicit command |
| Windows KRX Worker | Confirmed the Scheduled Task · CodeDeploy operational path |
| orchestration | Operational orchestration references only a validated Task Definition revision |
| Crawler CI | Expanded from a single Windows artifact to a Hybrid dual-runtime build |
| Build · Publish | Separated Build and Publish, established Windows·ECS deploy/rollback independence |
| `README.md` | Updated the execution model and AWS/Windows operations to the actual Hybrid structure |
| `AGENTS.md` | Reflected Hybrid DevOps standards and ECS/Windows promotion·rollback rules |
| `docs/source-file-catalog.md` | Reflected DevOps / Deployment file responsibilities |

### Validation

| Item | Result |
| --- | --- |
| Build-only quality gate | Success |
| Build-only S3 · ECR publish blocking | Verified |
| Container build · nongui compile contract | Success |
| ECR image publish and digest confirmation | Success |
| ECS Candidate Exit Code 0 | Confirmed |
| Candidate collection · DB write | None |
| Operational Task Definition promotion | Success |
| ECS revision rollback and re-promotion | Success |
| Windows Candidate · CodeDeploy | Success |
| Windows Scheduled Task execution | Success |
| KRX Login · Program · Shortsell | Success |
| KRX raw validation | Success |
| Windows rollback and re-promotion | Success |

### Security

| Item | Result |
| --- | --- |
| New verbatim credential record | None |
| runtime secret included in artifact | Excluded |
| Collection · DB write during Candidate validation | None |
| Windows EC2 artifact privileges | read-only minimal privileges |
| GitHub OIDC · CodeBuild role | No unnecessary Deploy privileges |

## 2026-07-22 — Crawler Documentation Standards Reorganization

### Changed

| Item | Value |
| --- | --- |
| `AGENTS.md` | Fully rewritten as Crawler-specific working rules |
| Highest-priority rules | New standalone tables two columns · local edits · no long cells |
| Execution risk | Strengthened standards for external sources · Selenium · DB upsert |
| Execution model | Separated non-GUI Daily and Windows KRX worker |
| Daily · History | Distinguished latest-collection and backfill responsibilities |
| KRX safety | Organized maintenance · redirect · timeout strict-exit standards |
| Validation | Organized expected date · row count · downstream blocking standards |
| DB standards | Organized `interest` schema · upsert · transaction cautions |
| Test standards | Prefer HTTP · yfinance · Selenium · DB mock |
| `README.md` | Fully restructured around current state · responsibility boundary · execution model |
| Documentation system | Organized around README · CHANGELOG · source catalog |
| `docs/source-file-catalog.md` | Restructured the 5-column long-form list into a 2-column structure centered on responsibility · risk · change impact |
| `docs/source-file-catalog.md` | Reflected the Windows KRX worker wrapper `ops/run_krx_worker_daily.ps1` |
| Worklog policy | Stopped creating date-specific worklogs and consolidated into the CHANGELOG |

### Fixed

| Item | Value |
| --- | --- |
| `AGENTS.md` | Corrected the KRX strict-exit `OPEN stage` expression to `downstream stage` based on the actual code |
| `README.md` · `docs/source-file-catalog.md` | Removed the reference to the nonexistent `docs/database.md` |
| `README.md` | Condensed the validation file-creation wording to include DB connection or external requests |

### Security

| Item | Result |
| --- | --- |
| Python code changes | None |
| Crawler · History · Validation execution | 0 |
| Naver · yfinance · KRX calls | 0 |
| Selenium · Chrome execution | 0 |
| DB · AWS · Windows Task execution | 0 |
| Git write commands | 0 |
| New verbatim sensitive information record | 0 |

## 2026-07-01 — Hybrid Execution and KRX Raw Validation Documentation

### Added

| Item | Value |
| --- | --- |
| AWS operational structure | AWS Paper data collection execution unit |
| non-GUI Daily | `interest_crawler_daily_nongui.py` |
| Windows KRX worker | GUI · Selenium · Chrome execution surface |
| KRX strict-exit | maintenance · redirect · timeout failure criteria |
| KRX validation | `interest_krx_raw_validate_daily.py` |
| Experiment candidate | `patch_research_decision_dependency.py` |
| Source catalog | Reflected new entrypoint and candidate files |
| Worklog | `docs/worklog/2026-07-01.md` |

### Changed

| Item | Value |
| --- | --- |
| README primary features | Reflected the Hybrid execution model |
| KRX operations | Specified raw validation after program · shortsell collection |
| Responsibility boundary | Separated Crawler from orchestration · Preprocessor |

### Security

| Item | Result |
| --- | --- |
| Functional changes | None |
| External API · Selenium execution | 0 |
| DB · AWS · Slack execution | 0 |
| New verbatim sensitive information record | 0 |

## 2026-05-28 — Database and Source Catalog Documentation

### Added

| Item | Value |
| --- | --- |
| `docs/database.md` | Single DB and schema-per-domain structure |
| `docs/source-file-catalog.md` | Primary source and documentation responsibilities |
| Module docstring | Per-file execution impact and external · DB dependencies |
| Worklog | `docs/worklog/2026-05-28.md` |

### Changed

| Item | Value |
| --- | --- |
| Database | Default `portfolio` |
| Environment variables | Unified around `INTEREST_DB_NAME` · `PORTFOLIO_DB_NAME` |
| search path | `interest, reference, legacy, public` |
| SQL compatibility | Documented the search path premise of existing unqualified SQL |
| Security | Separated credentials into environment variables or local config |
| README | Reflected source catalog and comment-writing standards |

### Security

| Item | Result |
| --- | --- |
| Functional changes | None |
| Crawler · DB execution | 0 |
| New verbatim sensitive information record | 0 |

## 2026-05-27 — DB Configuration Externalization

### Changed

| Item | Value |
| --- | --- |
| DB loader | `get_db_config()` in `db_config.py` |
| Environment variables | `INTEREST_DB_*` |
| Password | Removed hardcoding candidates in Python scripts |
| README | Placeholder-based DB configuration examples |

### Security

| Item | Result |
| --- | --- |
| Actual DB connection | 0 |
| External API · Selenium execution | 0 |
| New verbatim sensitive information record | 0 |

## 2026-05-26 — Initial Documentation and First-Pass File Cleanup

### Added

| Item | Value |
| --- | --- |
| `AGENTS.md` | Initial Crawler working rules |
| `README.md` | Project structure draft |
| Worklog | `docs/worklog/2026-05-26.md` |

### Changed

| Item | Value |
| --- | --- |
| README structure | Reflected the first-pass unused · legacy cleanup results |
| Documentation standards | Used current-file and import · entrypoint confirmation results |

### Removed

| Item | Value |
| --- | --- |
| Documentation references | References to deleted test · debug · dump · legacy candidates |

### Security

| Item | Result |
| --- | --- |
| Crawler · external API execution | 0 |
| Selenium · KRX · DB execution | 0 |
| New verbatim sensitive information record | 0 |
