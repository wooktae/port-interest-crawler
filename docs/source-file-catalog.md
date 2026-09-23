# Source File Catalog

A document for quickly checking the roles of the primary files and directories of port-interest-crawler.

It is not an inventory listing every file, but records only the items needed to understand the structure and judge change impact.

It uses paths relative to the repository root and excludes cache, credential, download, HTML dump, and one-time outputs.

## Usage Principles

| Item | Value |
| --- | --- |
| Basis | Current Crawler code and hybrid operational structure |
| Included | Primary entrypoints · common helpers · operationally impactful files |
| Excluded | cache · credential · debug dump · download outputs |
| Update | When file path · responsibility · execution risk changes |
| Omit | When only internal implementation changes and file responsibility is the same |
| Sensitive information | No verbatim credential · host · ARN · command id |

## Root and Common Files

| File | Role |
| --- | --- |
| `AGENTS.md` | Crawler code and documentation working rules |
| `README.md` | Current structure · execution model · operational AS-IS |
| `CHANGELOG.md` | Primary change history |
| `db_config.py` | PostgreSQL environment-variable loader |
| `interest_get_holidays.py` | Market Holiday check |
| `interest_log_format.py` | Collection log and summary format |

### Check When Changing

| Target | Check |
| --- | --- |
| `AGENTS.md` | Execution restrictions · strict-exit · documentation update rules |
| `README.md` | Daily · History · Validation · hybrid structure |
| `CHANGELOG.md` | Record only actual Crawler changes |
| `db_config.py` | `INTEREST_DB_*` · password default · search path |
| holiday helper | KST · holiday API failure · Trading Day determination |
| log helper | Whether failures are not printed as SUCCESS or DONE |

## Daily Orchestration

| File | Role |
| --- | --- |
| `interest_crawler_daily.py` | GUI-inclusive Daily collection orchestration |
| `interest_crawler_daily_nongui.py` | non-GUI Daily collection orchestration |
| `interest_crawler_main.py` | Manual · initial integrated collection |

### Execution Model

| Item | Standard |
| --- | --- |
| GUI Daily | Can include KRX login · program · shortsell |
| non-GUI Daily | Naver · yfinance · holiday API · DB |
| Container candidate | `interest_crawler_daily_nongui.py` |
| Windows worker | KRX GUI collection separated |
| Completion check | Confirm child step results together with follow-up validation |
| Prohibited | Full SUCCESS after partial failure |

The current GUI Daily may not aggregate some child failures into the final exit code, so confirm individual step logs together with follow-up validation.

Do not re-combine Selenium and KRX GUI modules into the non-GUI entrypoint.

## Daily Data Collectors

| File | Role |
| --- | --- |
| `interest_price.py` | Incremental collection of domestic stock prices |
| `interest_marketbreadth.py` | Price-based Market Breadth |
| `interest_foreignindex.py` | Incremental Foreign index collection |
| `interest_macroeconomic.py` | Incremental macro indicator collection |
| `interest_commodity.py` | Incremental Commodity collection |
| `interest_investorflow.py` | Naver Investor Flow |
| `interest_agency.py` | Naver brokerage reports |
| `interest_news.py` | Naver news |
| `interest_program.py` | KRX program trading |
| `interest_shortsell.py` | KRX Short Selling |
| `interest_ticker_main.py` | Stock basic info |
| `interest_ticker_value.py` | Stock value info |
| `interest_ticker_finance.py` | Stock financial info |

### Distinction by Source

| Source | Related Files |
| --- | --- |
| yfinance | price · foreignindex · macroeconomic · commodity |
| Naver | investorflow · agency · news · ticker |
| KRX | program · shortsell |
| PostgreSQL | marketbreadth · all persist paths |

### Check When Changing

| Item | Value |
| --- | --- |
| HTTP | timeout · status · rate limit |
| Parse | required columns · date · number · encoding |
| Empty result | Distinguish normal Market Holiday from source failure |
| Persist | unique key · upsert · transaction |
| Source | Preserve existing source values and ticker meaning |
| Exit | Distinguish partial failure from full failure |

## History and Backfill

| File | Role |
| --- | --- |
| `interest_price_history.py` | Price history |
| `interest_marketbreadth_history.py` | breadth history recomputation |
| `interest_foreignindex_history.py` | Foreign index history |
| `interest_macroeconomic_history.py` | Macro history |
| `interest_commodity_history.py` | Commodity history |
| `interest_investorflow_history.py` | Investor Flow history |
| `interest_agency_history.py` | Brokerage report history |
| `interest_news_history.py` | News history |
| `interest_program_history.py` | KRX program history |
| `interest_shortsell_history.py` | KRX Short Selling history |

### Check When Changing

| Item | Value |
| --- | --- |
| Period | Start date · end date |
| Trading Day | calendar gap and trade gap |
| Chunk | request · commit unit |
| Checkpoint | Resume criteria after failure |
| Rate limit | Per-source limit and backoff |
| Idempotency | Duplicate and conflict policy |
| Partial failure | Re-collection range and success marker |

Do not use History as the default Daily execution path.

## Validation and Check

| File | Role |
| --- | --- |
| `interest_data_validate_daily.py` | Daily freshness · NULL · duplicate · outlier |
| `interest_data_validate_all.py` | Full data quality check |
| `interest_price_check.py` | Check for missing prices on recent Trading Days |
| `interest_krx_raw_validate_daily.py` | KRX raw freshness · row count check |

### Execution Risk

| File | Caution |
| --- | --- |
| `interest_data_validate_daily.py` | May depend on DB and holiday API |
| `interest_data_validate_all.py` | Possible bulk DB read and holiday API |
| `interest_price_check.py` | DB read and Trading Day determination |
| `interest_krx_raw_validate_daily.py` | DB read · non-zero exit on failure |

Do not judge a script as a safe read-only script based on the name validation or check alone.

### KRX Raw Validation

| Target | Check |
| --- | --- |
| `interest_program_raw` | Latest `trade_date` · row count |
| `interest_shortsell_raw` | Latest `trade_date` · row count |
| Expected date | Execution-basis Trading Day |
| Failure | non-zero exit |
| Purpose | Block downstream progression on unloaded data |

The actual exit code numbers defer to the code contract.

Do not arbitrarily fix numbers that are not confirmed in the documentation.

## KRX and Browser

| File | Role |
| --- | --- |
| `interest_krx_chrome.py` | Chrome session and GUI preparation |
| `interest_krx_login_new.py` | KRX login · popup · iframe handling |
| `interest_program.py` | Program trading Daily download |
| `interest_program_history.py` | Program trading history download |
| `interest_shortsell.py` | Short Selling Daily download |
| `interest_shortsell_history.py` | Short Selling history download |

### Strict-exit Conditions

| Condition | Handling |
| --- | --- |
| KRX maintenance page | Failure |
| Login redirect | Failure |
| Session expiration | Failure |
| Download timeout | Failure |
| Empty CSV | Failure |
| Missing required columns | Failure |
| Expected date not met | Failure |
| Row count 0 | Failure |

Do not judge success by the existence of a download file alone.

Distinguish existing files from new files, and do not parse partial files.

## Windows KRX Worker

| File | Role |
| --- | --- |
| `ops/run_krx_worker_daily.ps1` | Windows KRX worker daily wrapper |

### Execution Order

| Stage | Handling |
| --- | --- |
| Preparation | Load venv · crawler DB env · KRX env |
| Collection | KRX login → program → shortsell |
| Validation | DB check of program · shortsell raw freshness |
| Log | Record execution logs to the local log directory |

It is a GUI collection wrapper for the Scheduled Task and is separated from the non-GUI Daily path.

The inline DB validator that the wrapper creates during execution is a temporary output and is removed after execution.

## DevOps and Deployment

| File | Role |
| --- | --- |
| `Dockerfile` | Container image build |
| `.dockerignore` | Exclude Git · cache · `.devops/artifacts/` from build context |
| `.github/workflows/crawler-codebuild.yml` | Orchestrate ECS and Windows Release after CodeBuild/Publish on main push |
| `.github/workflows/oidc-preflight.yml` | Preflight for checking GitHub OIDC claims |
| `.devops/buildspec/buildspec.yml` | Common gate · Windows ZIP · Container build · optional publish |
| `.devops/scripts/release-crawler-ecs.ps1` | immutable ECR image Candidate · Task Definition registration · Activation Scope Promotion · stale guard · rollback |
| `.devops/scripts/release-crawler-windows.ps1` | versioned S3 ZIP-based CodeDeploy · EC2 lifecycle state preservation · Scheduled Task/KRX GUI non-execution |
| `.devops/config/crawler-ecs-activation-scope.json` | Definition of the ECS promotion-target Activation Scope |
| `.devops/bundle/windows-include.txt` | Windows Worker bundle inclusion range |
| `.devops/scripts/build/compile_check.py` | Safe Python compile gate |
| `.devops/scripts/package/build_windows_bundle.py` | Generate a Git SHA-based deterministic Windows ZIP |
| `.devops/scripts/test/verify_windows_bundle.py` | Validate manifest · forbidden file · bundle contract |
| `.devops/scripts/deploy/windows-before-install.ps1` | CodeDeploy BeforeInstall lifecycle hook |
| `.devops/scripts/deploy/windows-after-install.ps1` | CodeDeploy AfterInstall lifecycle hook |
| `.devops/scripts/deploy/windows-validate.ps1` | CodeDeploy ValidateService lifecycle hook |

### Check When Changing

| Item | Value |
| --- | --- |
| Execution contract | Distinguish the responsibilities of Docker default CMD and ECS Task Definition command |
| Publish gate | Preserve `PUSH_ARTIFACT` and `PUSH_IMAGE` independence |
| Build context | Do not put build output into the Container context |
| Windows bundle | Exclude runtime secret · local env loader |
| Lifecycle hook | Separate Candidate staging · runtime promotion · validation responsibilities |
| Sensitive information | Prohibit verbatim credential · token record in documentation |

Do not include `.devops/artifacts/*.zip`, `__pycache__`, `*.pyc`, and temporary backups in the catalog.

## Universe and Sector

| File | Role |
| --- | --- |
| `build_stock_universe.py` | Naver-based stock universe |
| `build_sector_mapping.py` | sector · industry mapping |
| `build_universe_sector.py` | universe sector enrichment |

### Check When Changing

| Item | Value |
| --- | --- |
| Universe | market · ticker · stock name key |
| Mapping | English · Korean sector meaning |
| yfinance | ticker suffix · empty response |
| Selenium | Naver scroll · page structure |
| DB | Distinguish reference and interest responsibilities |

Ensure reference data changes do not break the meaning of Crawler raw loading.

## Database Contract

| Item | Value |
| --- | --- |
| Database | `portfolio` |
| Config loader | `db_config.py` · `get_db_config()` |
| Environment variables | `INTEREST_DB_*` |
| Password | No default |
| search path | `interest, reference, legacy, public` |

### Schema Responsibilities

| Schema | Role |
| --- | --- |
| `interest` | raw · history · collection results |
| `reference` | ticker · market · calendar |
| `legacy` | Backward compatibility |
| `public` | fallback search path |

### Check When Changing SQL

| Item | Value |
| --- | --- |
| Table · column | Verify via code · migration · DB contract |
| New SQL | schema-qualified whenever possible |
| Existing SQL | Verify connection `search_path` |
| Unique key | Preserve `ON CONFLICT` meaning |
| Delete | Verify source · ticker · period range |
| Transaction | commit · rollback boundary |
| Failure | No SUCCESS after partial loading |

The Crawler does not directly produce `preprocessor`, `research`, `decision`, or `execution` results.

## External Dependencies

| Item | Role |
| --- | --- |
| Requests | HTTP requests |
| BeautifulSoup | HTML parsing |
| yfinance | Market Data |
| Selenium | Browser automation |
| Chrome · ChromeDriver | KRX GUI |
| psycopg · psycopg2 | PostgreSQL |
| Naver | Finance · News · Open API |
| KRX | Data portal |
| PostgreSQL | raw · history persistence |

Do not use actual external sources and DB in documentation verification or unit tests.

## Tests

| Change | Validation |
| --- | --- |
| Python syntax | Safe compile check |
| HTTP parser | Stored fixture response |
| HTML parser | Local fixture HTML |
| CSV parser | Local fixture CSV |
| yfinance | DataFrame mock |
| Selenium | login · download mock |
| Daily orchestration | child call · exit code mock |
| History | chunk · checkpoint · idempotency |
| Validation | DB result · expected date mock |
| Repository | SQL · parameter · upsert |
| Documentation | Links · facts · readability |

When execution-risk imports exist, prioritize static verification of the file body.

## Documents

| Document | Role |
| --- | --- |
| `AGENTS.md` | Crawler working rules |
| `README.md` | Current structure and operational AS-IS |
| `CHANGELOG.md` | Primary change history |
| `docs/source-file-catalog.md` | Primary files and responsibilities |

Do not create date-specific `docs/worklog/*.md` files.

When keeping past worklogs, treat them only as historical records.

## External Dependency Modules

| Module | Relationship |
| --- | --- |
| `port-interest-preprocessor` | Consumes Crawler raw |
| `port-view` | Execution-status query · trigger UI |
| `port-marketconnector` | Order and broker integration |
| `port_strategy_research` | Strategy research |
| `port_strategy_decision` | Strategy decision |
| `port_strategy_execution` | Order planning |
| Step Functions · Scheduler | orchestration |

Other MS internal code and documentation are not automatically included in the Crawler change scope.

## Cleanup Candidates

| File | Judgment |
| --- | --- |
| `block_watch_backtest_run.py` | Direct relationship to operational collection needs confirmation |
| `dump_public_schema_final.py` | DB dump · local file creation candidate |
| `patch_research_decision_dependency.py` | One-time patch candidate outside Crawler responsibility |

Do not run or delete cleanup candidates.

Decide separately after confirming actual references, call relationships, and the owning MS.

## Catalog Update Conditions

| Change | Handling |
| --- | --- |
| Create · delete · rename a primary Python file | Update |
| Change Daily · History · Validation responsibility | Update |
| Change non-GUI · KRX worker structure | Update |
| Change Source Data · parser responsibility | Update |
| Change config · DB loader roles | Update |
| Change scripts · worker wrapper | Update |
| Create · delete a document or change its role | Update |
| Change only internal implementation · same responsibility | May be omitted |

Do not create a new full repository inventory when updating the catalog.

Check only the changed area and adjacent items.
