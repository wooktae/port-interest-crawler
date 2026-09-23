# port-interest-crawler

A Python microservice that collects price, news, research, Investor Flow, Short Selling, program trading, macro, commodity, and foreign index data from external Source Data providers such as Naver, yfinance, and KRX.

Collection results are loaded into the `interest` raw/history area of PostgreSQL, and the downstream Preprocessor consumes them.

Because the execution paths in this repository can lead to external network requests, Selenium/Chrome, file downloads, and DB upserts, static analysis and documentation work are the default.

## Current State

| Item | Value |
| --- | --- |
| Operational nature | AWS Paper data collection |
| Base structure | Standalone Python script-centric |
| Daily non-GUI | `interest_crawler_daily_nongui.py` |
| KRX GUI | Windows worker · Selenium · Chrome |
| History | Per-source `*_history.py` backfill |
| Validation | Freshness · row count · gap check |
| Database | PostgreSQL `portfolio` |
| Default schema | `interest` |
| downstream | port-interest-preprocessor |
| Documentation principle | Static verification without external calls or DB writes |

> Files named validation or check may also include DB connections or external requests. Do not run them for documentation verification purposes.

## Technical Stack

| Item | Value |
| --- | --- |
| Language | Python |
| HTTP | Requests |
| HTML Parsing | BeautifulSoup |
| Market Data | yfinance |
| Browser | Selenium · Chrome |
| Database Driver | psycopg · psycopg2 |
| Database | PostgreSQL |
| Data Source | Naver · KRX · yfinance |

## Responsibility Boundary

### Owned Scope

| Area | Role |
| --- | --- |
| Price | Domestic and foreign prices and time series |
| News · Research | News and research materials |
| Flow | Investor Flow and institutional data |
| KRX | Program trading and Short Selling |
| Macro | Foreign index · macro · commodity |
| Ticker | Stock basic · value · financials |
| Universe | stock universe and sector mapping |
| Daily | Latest Trading Day collection |
| History | Past-period backfill |
| Validation | Freshness · row count · gap check |
| Persistence | raw/history DB loading |

### Excluded Scope

| Item | Actual Responsibility Area |
| --- | --- |
| Batch orchestration | Step Functions · Scheduler |
| KRX worker startup | Windows Scheduled Task |
| feature generation | port-interest-preprocessor |
| Strategy research | Strategy Research |
| Strategy decision | Strategy Decision |
| Order planning | Strategy Execution |
| Order submission | port-marketconnector |
| Views | port-view |

Do not duplicate preprocessing, strategy decision, or order execution logic inside the Crawler.

## Execution Model

The Crawler is split into two execution surfaces depending on GUI dependency.

### Non-GUI Daily

| Item | Value |
| --- | --- |
| Entrypoint | `interest_crawler_daily_nongui.py` |
| Operational execution | ECS Fargate RunTask · non-GUI |
| Execution contract | Task Definition command `interest_crawler_daily_nongui.py` |
| Deployment identity | Git SHA image tag · immutable ECR digest |
| Primary sources | Naver · yfinance · holiday API |
| DB handling | PostgreSQL upsert |
| Excluded | KRX login · program · shortsell |
| Purpose | Daily collection without GUI |

The non-GUI entrypoint does not import KRX GUI-dependent modules.

The explicit command in the ECS Task Definition, not the Dockerfile default CMD, is the operational execution contract.

Operational orchestration references a validated Task Definition revision.

### Windows KRX Worker

| Item | Value |
| --- | --- |
| Environment | Windows EC2 · GUI session |
| Operational execution | Scheduled Task |
| Browser | Selenium · Chrome |
| Collection | KRX program · shortsell |
| Handling | login · CSV download · parse · upsert |
| Deployment | versioned S3 ZIP · CodeDeploy IN_PLACE |
| Follow-up | KRX raw validation |

Do not merge the Windows GUI-dependent flow into the container's default execution path.

## Primary Files

### Daily and Common Collection

| File | Role |
| --- | --- |
| `interest_crawler_daily.py` | Daily integrated collection |
| `interest_crawler_daily_nongui.py` | non-GUI Daily collection |
| `interest_crawler_main.py` | Integrated execution entrypoint |
| `interest_price.py` | Price collection |
| `interest_marketbreadth.py` | Market Breadth |
| `interest_foreignindex.py` | Foreign index |
| `interest_macroeconomic.py` | Macro |
| `interest_commodity.py` | Commodity |
| `interest_investorflow.py` | Investor Flow |
| `interest_agency.py` | Institutional data |
| `interest_news.py` | News |
| `interest_program.py` | KRX program trading |
| `interest_shortsell.py` | KRX Short Selling |
| `interest_ticker_main.py` | ticker basic info |
| `interest_ticker_value.py` | ticker value info |
| `interest_ticker_finance.py` | ticker financial info |

### History and Backfill

| File | Role |
| --- | --- |
| `interest_price_history.py` | Price history |
| `interest_marketbreadth_history.py` | breadth history |
| `interest_foreignindex_history.py` | Foreign index history |
| `interest_macroeconomic_history.py` | Macro history |
| `interest_commodity_history.py` | Commodity history |
| `interest_investorflow_history.py` | Investor Flow history |
| `interest_agency_history.py` | Institutional history |
| `interest_news_history.py` | News history |
| `interest_program_history.py` | KRX program history |
| `interest_shortsell_history.py` | KRX Short Selling history |

### Validation and Check

| File | Role |
| --- | --- |
| `interest_data_validate_daily.py` | Daily data validation |
| `interest_data_validate_all.py` | Full-range validation |
| `interest_price_check.py` | Price check |
| `interest_krx_raw_validate_daily.py` | KRX raw freshness validation |

### KRX and Browser

| File | Role |
| --- | --- |
| `interest_krx_chrome.py` | Chrome-related helper |
| `interest_krx_login_new.py` | KRX login |
| `interest_program.py` | Program trading Daily |
| `interest_program_history.py` | Program trading history |
| `interest_shortsell.py` | Short Selling Daily |
| `interest_shortsell_history.py` | Short Selling history |

### Universe and Sector

| File | Role |
| --- | --- |
| `build_stock_universe.py` | stock universe construction |
| `build_sector_mapping.py` | sector mapping |
| `build_universe_sector.py` | Combine universe and sector |

### Candidate Files

| File | Classification |
| --- | --- |
| `dump_public_schema_final.py` | legacy · DB dump candidate |
| `block_watch_backtest_run.py` | Local experiment candidate |
| `patch_research_decision_dependency.py` | One-time patch candidate |

Do not delete candidate files based on static verification alone.

For detailed roles, see the [Source File Catalog](docs/source-file-catalog.md).

## Execution Risk

### Daily

Daily scripts can perform external Source Data requests and DB loading.

| Risk | Content |
| --- | --- |
| Network | Naver · yfinance · holiday API |
| Browser | Some KRX paths |
| Database | insert · update · upsert |
| Filesystem | CSV · HTML · temporary files |
| Exit | Partial failures may be mistaken for success |

The current GUI Daily may not aggregate some child failures into the final exit code. Confirm completion by reviewing individual step results together with follow-up validation.

### History and Backfill

History scripts can perform long-running requests and bulk loading.

| Check | Content |
| --- | --- |
| Period | Start date · end date |
| Trading Day | Distinguish calendar gap from trade gap |
| Limits | Per-source rate limit |
| Loading | unique key · upsert |
| Restart | chunk · checkpoint |
| Failure | Partial loading and re-run criteria |

Do not use History as the default Daily execution path.

### Validation

Validation scripts may also include DB connections or external requests.

Do not judge them as read-only based on the name alone.

## External Source Data

### Naver

| Item | Standard |
| --- | --- |
| Target | News · research · flow · ticker |
| HTTP | timeout · status check |
| Parsing | Verify HTML structure and encoding |
| Duplicates | Check source · URL · date key |
| Credential | Do not expose client id · secret |

Do not treat empty HTML or structural changes as a normal zero-record result.

### yfinance

| Item | Standard |
| --- | --- |
| Target | Price · Foreign index · Macro · Commodity |
| Ticker | Verify suffix and market |
| Date | Verify timezone · trade date |
| Empty result | Do not treat as normal success |
| Failure | Distinguish partial-ticker and full failure |

### KRX

| Item | Standard |
| --- | --- |
| Target | Program trading · Short Selling |
| Access | Selenium · Chrome · login |
| Output | CSV download |
| Validation | expected date · row count · required columns |
| Failure | maintenance · redirect · timeout · empty CSV |

Do not treat maintenance pages or login redirects as a normal CSV.

## KRX strict-exit

Do not treat the following situations as normal completion.

- KRX maintenance page
- login redirect
- session expiration
- download timeout
- empty CSV
- missing required columns
- expected date not met
- row count 0

Do not convert a failed KRX collection into SUCCESS or `NO_CHANGE`.

## KRX Raw Validation

`interest_krx_raw_validate_daily.py` verifies the raw loading state after the Windows KRX worker.

| Target | Check |
| --- | --- |
| `interest_program_raw` | Latest `trade_date` · row count |
| `interest_shortsell_raw` | Latest `trade_date` · row count |
| Expected date | Execution-basis Trading Day |
| Failure | non-zero exit |
| Purpose | Block downstream progression |

Treat it as a failure when the row count is 0 or the latest Trading Day is earlier than the expected date.

Do not lower the expected date or minimum row count without basis in order to pass validation.

## Daily and History

### Daily Standard

| Item | Standard |
| --- | --- |
| Target | Latest Trading Day |
| Period | Short and clear range |
| Failure | fail-fast |
| Re-run | idempotent |
| Follow-up | validation |

### History Standard

| Item | Standard |
| --- | --- |
| Target | Past period |
| Period | Start date · end date |
| Execution | chunk |
| Resume | checkpoint |
| Limits | rate limit |
| Quality | gap re-collection |

Do not hide long-running backfill functionality inside Daily code.

## Database

### Connection Standard

| Item | Value |
| --- | --- |
| Database | `portfolio` |
| Config loader | `db_config.py` · `get_db_config()` |
| Environment variables | `INTEREST_DB_*` |
| Password | No default |
| search path | `interest, reference, legacy, public` |

In the operational environment, a dedicated Crawler DB user is used.

Do not interpret the `postgres` default in the documentation as an operational-privilege baseline.

### Schema Responsibilities

| Schema | Role |
| --- | --- |
| `interest` | raw · history · collection results |
| `reference` | ticker · market · calendar |
| `legacy` | Backward compatibility |
| `public` | fallback search path |

The Crawler does not directly produce `preprocessor`, `research`, `decision`, or `execution` results.

### SQL Standard

- New SQL uses schema-qualified names whenever possible.
- Existing unqualified SQL operates based on the connection `search_path`.
- Preserve the meaning of unique keys and `ON CONFLICT`.
- Distinguish raw and history retention policies.
- For delete-then-insert, verify the target period and source.
- Do not print SUCCESS after partial loading.

## Configuration

### DB Environment Variables

| Environment variable | Default · Role |
| --- | --- |
| `INTEREST_DB_HOST` | `localhost` |
| `INTEREST_DB_PORT` | `5433` |
| `INTEREST_DB_NAME` | `portfolio` |
| `PORTFOLIO_DB_NAME` | `portfolio` |
| `INTEREST_DB_USER` | Per-environment Crawler DB user |
| `INTEREST_DB_PASSWORD` | No default |

PowerShell example:

```powershell
$env:INTEREST_DB_HOST="localhost"
$env:INTEREST_DB_PORT="5433"
$env:INTEREST_DB_NAME="portfolio"
$env:INTEREST_DB_USER="[REDACTED]"
$env:INTEREST_DB_PASSWORD="[REDACTED]"
```

### Other Configuration

| Category | Example |
| --- | --- |
| Browser | Chrome · ChromeDriver path |
| KRX | login credential · download directory |
| Naver | client id · client secret |
| HTTP | URL · user-agent · timeout |
| Collection | ticker · market · date range |
| Worker | timezone · Scheduled Task |

Do not record actual local config and credential values in the documentation.

## AWS and Windows Operations

### Hybrid DevOps Summary

| Item | Value |
| --- | --- |
| Source | GitHub main |
| Release trigger | main push automatic · manual run |
| CI | GitHub Actions OIDC → CodeBuild |
| ECS Artifact | Git SHA image tag · immutable ECR digest |
| ECS Runtime | Fargate RunTask · non-GUI |
| Windows Artifact | Git SHA versioned ZIP · S3 object version |
| Windows Runtime | Windows EC2 · Scheduled Task |
| Windows Deploy | CodeDeploy IN_PLACE |
| Promotion | Reflect Activation Scope reference after Candidate validation |
| Rollback | ECS revision rollback · Windows runtime restore |

The automatic Release flow after a main push follows the order below.

GitHub main push → CodeBuild/Test → ECR Image + Windows ZIP Publish → ECS side-effect-free Candidate → ECS Activation Scope Promotion → Windows CodeDeploy

The gates for Windows artifact publish and Container image publish are independent of each other.

Build and Publish are distinguished, and no external artifact publish occurs in Build-only.

The GitHub OIDC Role has CodeBuild orchestration and a limited Crawler Release control-plane privilege, and does not have Runtime business privileges such as DB DML or KRX business execution.

Detailed IAM, actual resource names, ARNs, revision numbers, and Deployment IDs are not recorded in this document and are managed in port-devops.

### AWS

The non-GUI Crawler runs as an ECS Fargate RunTask.

The ECS Release first performs a side-effect-free Candidate without actual collection or DB writes, and after success promotes only the Task Definition reference within the designated Activation Scope.

Scheduler and Step Functions handle execution timing and orchestration, and operational orchestration references a validated Task Definition revision.

The Crawler documentation does not cover the full state machine definition or external resource state.

### Windows

The KRX worker may depend on a GUI session and Scheduled Task.

| Check | Content |
| --- | --- |
| Session | GUI-available state |
| Browser | Chrome · ChromeDriver compatibility |
| Download | Distinguish new CSV from existing files |
| Timezone | Asia/Seoul |
| Exit | Scheduled Task exit code |
| Validation | Follow-up KRX raw validation |

The Windows Release deploys only the runtime via CodeDeploy IN_PLACE, and does not automatically run the Scheduled Task or KRX GUI business execution, which are separate responsibilities. If the EC2 is running, its state is preserved; if stopped, it is started only during deployment and restored to its original state afterward.

Do not perform actual AWS resource and Windows task execution without a user request.

## Execution

Each Python file may be an independent entrypoint.

The command below is an example of an execution risk.

```powershell
python interest_crawler_daily.py
```

Running it may trigger external requests, a browser, file downloads, and DB loading.

## Prohibited Execution List

Do not perform the following work during documentation and static analysis.

- Daily · Main · individual collection execution
- History · backfill execution
- Validation · check execution
- Naver · yfinance · KRX · holiday API calls
- Selenium · Chrome · ChromeDriver execution
- KRX login · CSV download
- DB DDL · DML · psql
- ECS · SSM · Scheduler execution
- Windows Scheduled Task execution
- Slack calls

## Security

Do not record the following values verbatim in code, documentation, or logs.

- DB password and connection string
- Naver client id · client secret
- KRX user ID · password
- token · cookie · session
- actual DB host · private IP
- AWS account-id
- actual ARN
- instance id
- SSM command id
- local absolute path
- Slack webhook URL

Placeholders:

| Value | Placeholder |
| --- | --- |
| General sensitive information | `[REDACTED]` |
| DB host | `[REDACTED_DB_HOST]` |
| User ID | `[REDACTED_USER_ID]` |
| Secret | `[REDACTED_SECRET]` |
| ARN | `[REDACTED_ARN]` |
| instance id | `[REDACTED_INSTANCE_ID]` |
| command id | `[REDACTED_COMMAND_ID]` |
| ChromeDriver | `<CHROME_DRIVER_PATH>` |
| Windows worker | `<WINDOWS_KRX_WORKER>` |
| ECS task | `<CRAWLER_ECS_TASK>` |

## External Dependencies

| Item | Value |
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

## Documentation

| Document | Role |
| --- | --- |
| `AGENTS.md` | port-interest-crawler working rules |
| `README.md` | Current structure and operational AS-IS |
| `CHANGELOG.md` | Primary change history |
| `docs/source-file-catalog.md` | Primary files and responsibilities |

Do not create date-specific `docs/worklog/*.md` files.

Record code and documentation change history in `CHANGELOG.md`.
