# port-interest-crawler Working Rules

This document defines the standards applied when modifying the Python collection code, history/backfill, validation, KRX worker, configuration, tests, and documentation of the `port-interest-crawler` microservice.

For `port-interest-crawler` work, reading this document alone should be enough to understand the work scope, external Source Data, execution risk, hybrid operational structure, DB loading responsibilities, and validation principles.

## 0. Highest-Priority Documentation Readability Rules

Apply this section before all other rules for documentation work.

### 0.0 Scope Limitation

The readability rules apply only to content newly written or directly modified in the current task.

Unless the user explicitly requests a full-document cleanup or comprehensive review, do not perform the following work.

| Item | Default Handling |
| --- | --- |
| Full scan of existing documentation | Do not perform |
| Complete README restructuring | Do not perform |
| Large-scale cleanup of historical CHANGELOG entries | Do not perform |
| Creation of a new scanner · audit tool | Do not perform |
| Creation of a sub-agent · orchestrator | Do not perform |

For adjacent content, review only the same table row, bullet group, or short paragraph.

Preserve existing out-of-scope violations and, when necessary, list them only as follow-up candidates.

### 0.1 Table Rules

New standalone summary tables use two columns by default.

The default headers are `Item / Value`.

More specific two-column headers may be used in the following situations.

| Situation | Preferred Headers |
| --- | --- |
| Changes by file | `File / Change` |
| entrypoint description | `File / Role` |
| Source Data | `Source / Handling` |
| Validation results | `Item / Result` |
| Configuration summary | `Setting / Value` |
| Risk summary | `Risk / Handling` |
| Test results | `Test / Result` |

When adding a row to an existing table, preserve its existing column structure.

Tables with three or more columns are allowed only in the following cases.

| Condition | Handling |
| --- | --- |
| Explicitly requested by the user | Use the requested structure |
| Preserving the existing table is safer | Keep the existing structure |
| Converting a comparison to two columns would lose meaning | Allow an exception |

### 0.2 Table Cell and Sentence Length

- Keep table cells to no more than two sentences.
- Separate multiple values in one cell with `<br>`.
- Do not place three or more facts in a long sentence within one cell.
- Move lengthy evidence outside the table or link to the relevant document.
- Do not create cells longer than 300 characters or lines longer than 500 characters.
- Do not paste raw logs, complete HTML, complete API responses, complete SQL, and AWS responses into documentation.

### 0.3 Documentation Density

Use the following priority when writing documentation.

1. Short summary
2. Short two-column table
3. Short bullets
4. Link to detailed documentation
5. Long-form text

Do not repeat the same facts at length across the README, CHANGELOG, worklog, and detailed documentation.

### 0.4 Status Indicators

Use only the following five status indicators.

| Indicator | Meaning |
| --- | --- |
| 🔴 | Prohibited · high risk · failure |
| 🟠 | Pending · observing · unconfirmed |
| 🟢 | Complete · successful · ENABLED |
| 🔵 | Reference · information · evidence |
| ⚫ | Not applicable |

Do not add HTML colors when a status indicator is sufficient.

### 0.5 Work Method Restrictions

Perform documentation work in the following order.

1. Confirm the requested scope
2. Read the target file directly
3. Modify only the necessary sections
4. Save as UTF-8 without BOM
5. Perform a short after-check
6. Report a change summary

Unless explicitly requested by the user, do not use the following methods.

- Full workspace scan
- Sub-agent
- Orchestrator
- New scanner
- Content hash matrix
- Temporary files outside the workspace
- Excessive automation scripts

## 1. Scope

### 1.1 Default Working Directory

`C:\Workspaces\port-interest-crawler`

### 1.2 Project Role

port-interest-crawler is a Python microservice that collects interest data from external Source Data providers and loads it into the PostgreSQL raw/history area.

| Area | Role |
| --- | --- |
| Price | Domestic and foreign prices and time series |
| News · Research | News and research materials |
| Flow | Investor Flow and institutional data |
| KRX | Short Selling and program trading |
| Macro | Foreign index · macro · commodity |
| Ticker | Stock basic · value · financials |
| Universe | stock universe and sector mapping |
| Validation | Freshness · row count · gap check |
| History | Past-period backfill |
| Persistence | `interest` raw/history loading |

### 1.3 Default Modification Targets

| Category | Target |
| --- | --- |
| Python | Root `*.py` and package Python files |
| Daily | Daily collection entrypoint |
| History | `*_history.py` and backfill-related code |
| Validation | `*_validate*.py` · `*_check.py` |
| KRX | Selenium · Chrome · login · download handling |
| Script | shell · PowerShell · worker wrapper |
| Configuration | Environment-variable loader · local config-related code |
| Tests | `tests` · `test_*.py` |
| Documentation | `README.md` · `CHANGELOG.md` · `docs` |
| Dependencies | requirements · pyproject · lock-related files |

Do not modify files that are not included in the current request.

### 1.4 Other Microservices

The following projects are external dependencies.

- `port-view`
- `port-marketconnector`
- `port-interest-preprocessor`
- `port_strategy_common`
- `port_strategy_research`
- `port_strategy_decision`
- `port_strategy_execution`

Do not modify code or documentation in another microservice unless the current task explicitly requires it.

Cross-service specs under `.kiro` are not automatically included in the port-interest-crawler work scope.

## 2. Execution Risk Levels

Scripts in this repository can lead to external requests, browser startup, file downloads, and DB writes on import or execution.

Do not treat every Python file as an ordinary smoke test target.

### 2.1 Operational · Daily Risk

| File | Risk |
| --- | --- |
| `interest_crawler_daily.py` | Can call multiple sources and load to DB |
| `interest_crawler_daily_nongui.py` | non-GUI external calls and DB upsert |
| `interest_crawler_main.py` | Can run integrated collection flow |
| `interest_price.py` | Price request and save |
| `interest_news.py` | News request and save |
| `interest_investorflow.py` | Investor Flow collection and save |
| `interest_program.py` | KRX GUI · download · save |
| `interest_shortsell.py` | KRX GUI · download · save |

Do not run operational entrypoints without the user's explicit execution request.

### 2.2 History · Backfill High Risk

`*_history.py` files can perform long-running external requests and bulk DB loading.

| Risk | Handling |
| --- | --- |
| Long-period requests | Confirm target period in advance |
| API rate limit | Confirm per-source limits |
| Bulk upsert | Verify unique key and transaction |
| Duplicate loading | Verify idempotency and conflict policy |
| Partial failure | Verify restart criteria and checkpoint |
| Elapsed time | Prohibit running as general validation |

Run history and backfill only when the period, target source, and DB environment are clear in the user request.

### 2.3 Validation · Check Risk

Validation files may also include DB connections or external requests.

Do not judge them as read-only just because the name contains `validate` or `check`.

Verify the following before running.

- Whether a DB connection is made
- SQL type
- Whether external sources are called
- Whether files are created
- Meaning of the exit code
- Whether failure blocks downstream

### 2.4 KRX · Browser Risk

| Area | Risk |
| --- | --- |
| Selenium | Chrome process and GUI session |
| KRX login | credential · session · redirect |
| Download | CSV and temporary file creation |
| Parsing | Mistaking a maintenance page for data |
| Timeout | Mistaking partial loading for normal termination |
| Worker | Can run a Windows Scheduled Task |

Do not run Chrome, ChromeDriver, and Selenium during documentation and static analysis.

## 3. Hybrid Execution Model

The Crawler is split into two execution surfaces depending on GUI dependency.

### 3.1 Non-GUI Daily

| Item | Standard |
| --- | --- |
| Entrypoint | `interest_crawler_daily_nongui.py` |
| Operational execution | ECS Fargate RunTask · non-GUI |
| Execution contract | The explicit command in the ECS Task Definition |
| Included | Naver · yfinance · holiday check · DB loading |
| Excluded | KRX GUI login · program · shortsell |
| Responsibility | non-GUI source collection and raw loading |

Do not re-combine Selenium, Chrome, and GUI KRX collection into the non-GUI entrypoint.

The ECS Task Definition command, not the Dockerfile default CMD, is the operational execution contract.

### 3.2 Windows KRX Worker

| Item | Standard |
| --- | --- |
| Environment | Windows EC2 · GUI |
| Operational execution | Scheduled Task |
| Collection | KRX program · shortsell |
| Handling | login · CSV download · parse · upsert |
| Deployment | versioned S3 ZIP · CodeDeploy IN_PLACE |
| Follow-up | KRX raw validation |

Do not move the Windows worker's GUI-dependent code into the container path.

### 3.3 Responsibility Boundary

| Area | Responsibility |
| --- | --- |
| Crawler | External Source Data collection and raw/history loading |
| Scheduler · Step Functions | Execution timing and orchestration |
| Windows worker | KRX GUI collection |
| Preprocessor | Convert raw into feature |
| View | Execution-status query and trigger UI |

Do not duplicate Preprocessor and strategy decision logic inside the Crawler.

## 4. External Source Data Standards

### 4.1 Naver

- Specify request timeout and user-agent.
- Do not treat a change in response HTML structure as empty normal data.
- Verify duplicate keys for news and research.
- Do not print Naver Open API credentials.
- Handle encoding and date-parsing failures explicitly.

### 4.2 yfinance

- Verify ticker and market suffix.
- Verify timezone and trade date basis.
- Do not treat an empty DataFrame as completed normal loading.
- Distinguish partial-ticker failure from full failure.
- Automatic retry and sleep must account for rate limits.

### 4.3 KRX

- Do not treat maintenance pages, redirects, and login screens as a normal CSV.
- Do not judge success by the download file name alone.
- Verify expected date, row count, and required columns.
- Do not use a partial file after a Selenium timeout.
- Preserve the meaning of strict-exit and fail-fast.

### 4.4 Holidays and Trading Days

- Use Asia/Seoul-based dates.
- Distinguish weekends, Market Holidays, and actual Trading Days.
- Do not unconditionally interpret a holiday API failure as a market open day.
- For history/backfill, distinguish actual Trading Day gaps from calendar gaps.

## 5. Python Code Standards

### 5.1 Common Principles

- Prefer preserving existing file names, CLI options, source values, and DB semantics.
- Ensure that module import alone does not trigger external requests, browser execution, and DB writes.
- Preserve the `if __name__ == "__main__":` boundary for entrypoints.
- Distinguish the collection, parse, transform, and persist stages as much as possible.
- Do not convert a failure into a success, `NO_CHANGE`, or empty-data-as-normal.
- Do not add a one-time failure workaround as a permanent fallback.

### 5.2 HTTP Requests

- Specify a timeout.
- Verify both the status code and the response content format.
- Distinguish retry targets from non-targets.
- Do not retry 4xx and authentication failures indefinitely.
- Verify per-source rate limits and backoff.
- Do not log credentials in request URLs.

### 5.3 Parse

- Verify required columns and types.
- Do not hide conversion failures for dates, numbers, and missing values.
- Distinguish an HTML error page from a CSV.
- Do not report a partial row-parse failure as a full success.
- Do not arbitrarily change the meaning of the original source.

### 5.4 Persist

- Preserve the existing unique key and conflict/upsert policy.
- Verify the meaning of source, ticker, trade_date, and collection timestamp.
- Preserve transaction and rollback boundaries.
- Do not print a success marker after partial loading.
- For bulk loading, verify batch size and commit unit.
- Do not confirm an unloaded state as success before validation.

### 5.5 Exit Result Design Standard

| Result | Standard |
| --- | --- |
| SUCCESS | Expected data loaded and validation passed |
| NO_CHANGE | No new loading target, normally |
| SKIP | Explicit normal exclusion such as a holiday |
| FAILURE | External request · parse · DB failure |
| BLOCKER | State that prohibits downstream progression |

The actual status strings and exit codes in the current code take precedence; the classification above is used as a design standard to distinguish result meanings in new or modified code.

Recognize the `SUCCESS`, `FAILED`, and `NO_CHANGE` that the code actually uses as current implementation facts, and do not describe `SKIP`, `FAILURE`, and `BLOCKER` as being emitted by all current code.

Do not forcibly unify `FAILED` and `FAILURE` into one.

Do not arbitrarily merge success and `NO_CHANGE` in documentation.

## 6. KRX strict-exit and Raw Validation

### 6.1 Strict-exit

Do not treat the following situations as normal completion.

- KRX maintenance page
- login redirect
- session expiration
- download timeout
- empty CSV
- missing required columns
- expected date not met
- row count 0
- raw not loaded that a downstream stage requires

### 6.2 Daily Raw Validation

`interest_krx_raw_validate_daily.py` is a validation entrypoint that verifies KRX raw freshness.

| Target | Check |
| --- | --- |
| `interest_program_raw` | Latest `trade_date` · row count |
| `interest_shortsell_raw` | Latest `trade_date` · row count |
| Expected date | Execution-basis Trading Day |
| Failure | non-zero exit |
| Purpose | Block downstream progression on unloaded data |

Do not lower the expected date or minimum row count without basis in order to match the validation result.

### 6.3 Data Gaps and Raw Mismatches

When a collection source returns an empty result, distinguish the following.

- Normal Market Holiday
- Source data not yet published
- KRX maintenance
- redirect or login failure
- parse failure
- Actual zero records
- State that retains the existing latest data

Do not reuse previous data as same-day success data without confirming the cause.

## 7. Separation of Daily and History

### 7.1 Daily

Daily scripts prioritize latest Trading Day loading and same-day operational stability.

- Limited target period
- Clear expected date
- Fast failure
- downstream validation
- Repeat-run idempotency

### 7.2 History

History scripts prioritize completeness of past ranges and restartability.

- Start date and end date
- Trading Day list
- chunk unit
- checkpoint
- Per-source rate limit
- gap re-collection
- Duplicate prevention

Do not hide long-running backfill functionality inside the Daily entrypoint.

Do not use History scripts as the Scheduler's default daily path.

## 8. Database Standards

### 8.1 Connection

| Item | Value |
| --- | --- |
| Database | `portfolio` |
| Config loader | `get_db_config()` in `db_config.py` |
| Environment variables | `INTEREST_DB_*` |
| Password | No default |
| search path | `interest, reference, legacy, public` |

In the real operational environment, a dedicated Crawler DB user is used.

Even if a `postgres` default exists in the code or older documentation, do not interpret it as an operational-privilege baseline.

### 8.2 Schema Responsibilities

| Schema | Role |
| --- | --- |
| `interest` | raw · history · collection results |
| `reference` | ticker · market · calendar reference data |
| `legacy` | Backward compatibility |
| `public` | fallback search path |

The Crawler does not directly produce the business results of `preprocessor`, `research`, `decision`, or `execution`.

### 8.3 SQL and Upsert

- New SQL uses schema-qualified names whenever possible.
- Verify that existing unqualified SQL is consistent with the connection `search_path`.
- Before modifying SQL, verify columns through the actual code, migrations, or `information_schema.columns`.
- Verify the meaning of unique keys and `ON CONFLICT`.
- Distinguish the retention policies of raw and history tables.
- For a delete-then-insert pattern, verify the target range.
- Do not print SUCCESS after a failed DB operation.

## 9. Configuration and Sensitive Information

### 9.1 Sensitive Information

Do not record the following values verbatim in code, documentation, examples, or logs.

- DB password and full connection string
- Naver client id · client secret
- KRX credential and user ID
- token · cookie · session
- Chrome profile path
- actual DB host and private IP
- AWS account-id
- actual ARN
- instance id
- SSM command id
- local absolute path
- Slack webhook URL

Use the following placeholders when needed.

| Placeholder | Purpose |
| --- | --- |
| `[REDACTED]` | General sensitive information |
| `[REDACTED_DB_HOST]` | DB host |
| `[REDACTED_USER_ID]` | User ID |
| `[REDACTED_SECRET]` | API secret |
| `[REDACTED_ARN]` | ARN |
| `[REDACTED_INSTANCE_ID]` | instance id |
| `[REDACTED_COMMAND_ID]` | command id |
| `<CHROME_DRIVER_PATH>` | ChromeDriver path |
| `<WINDOWS_KRX_WORKER>` | Windows worker |
| `<CRAWLER_ECS_TASK>` | non-GUI task |

### 9.2 Configuration Changes

When changing a configuration key or loader, also verify the following.

1. `db_config.py`
2. The relevant entrypoint
3. Daily and History callers
4. Windows KRX worker
5. README
6. Execution wrapper
7. Deployment environment variables

Do not read actual local config and credential values and move them into the documentation.

## 10. AWS and Windows Operational Standards

### 10.0 Hybrid DevOps Standards

- Crawler CI starts CodeBuild via GitHub Actions OIDC.
- A main push automatically runs `crawler-codebuild.yml` to orchestrate the Hybrid Release.
- The GitHub OIDC Role has CodeBuild orchestration and a limited Crawler Release control-plane privilege.
- Do not state that the OIDC Role has no Deploy privileges at all.
- Do not expand the OIDC Role to Runtime business privileges such as DB DML or KRX business execution.
- ECR·S3 artifact write preserves the CodeBuild role and the existing Publish boundary.
- Detailed IAM Action·Resource, ARNs, and Policy JSON are not recorded in this document and remain the responsibility of port-devops.
- The Windows artifact and Container image can be built together from the same Source.
- The gates for Windows artifact publish and Container image publish are independent.
- Distinguish Build and Publish, and ensure no external artifact publish occurs in Build-only.
- The Container image is tracked by Git SHA tag, and immutable digest use is preferred at deployment.
- Do not put build output such as `.devops/artifacts` into the Container build context.
- Do not include runtime secrets and local env loader in the Windows bundle.

The main push Hybrid Release flow follows the order below by default.

| Stage | Content |
| --- | --- |
| Trigger | main push or manual run |
| Build | CodeBuild · Test |
| Publish | ECR Image · Windows ZIP |
| ECS | side-effect-free Candidate then Activation Scope Promotion |
| Windows | versioned S3 ZIP-based CodeDeploy |

The Release control-plane is the artifact·runtime deployment boundary and is not actual Crawler collection or order business execution.

### 10.1 AWS

The non-GUI Crawler runs as an ECS Fargate RunTask.

- The explicit command in the ECS Task Definition is the operational entrypoint contract.
- Do not put KRX GUI dependencies into the Container path.
- The ECS Candidate validates the artifact·runtime contract without actual collection and DB writes.
- The Candidate command is a compile-only runtime-contract validation of the nongui entrypoint.
- Register a new Task Definition revision after Candidate Exit Code 0.
- Promote only the Task Definition reference within the designated operational Activation Scope.
- Apply a stale promotion guard during promotion.
- Maintain a structure that can roll back to the previous definition on partial promotion failure.
- Do not run actual Crawler collection or DB writes during the Release process.
- Perform operational promotion only after Candidate success.
- ECS rollback defaults to restoring the previous Task Definition revision reference.
- After rollback, it must be possible to re-promote the validated Candidate.
- Do not promote a failed Candidate to operations.

Actual cluster, task definition ARN, and Scheduler state are external operational facts.

Do not call AWS APIs or change resources unless explicitly requested by the user.

### 10.2 Windows Worker

The Windows KRX worker may depend on a GUI session and Scheduled Task.

- Verify whether the session is GUI-available.
- Verify Chrome and ChromeDriver compatibility.
- Specify the download directory.
- Distinguish existing CSV from new CSV.
- Verify the Scheduled Task exit code.
- Specify the KST timezone.

Windows deployment is based on a versioned S3 artifact and the CodeDeploy IN_PLACE lifecycle.

- Candidate validation must not change the operational Runtime and Scheduler.
- Promote only a validated Candidate Runtime to the operational Runtime.
- Windows rollback defaults to restoring the pre-deployment runtime backup.
- After rollback, it must be possible to re-promote the validated Candidate.
- Grant the Windows EC2 only artifact-read minimal S3 privileges.

The Windows Release control-plane maintains the following execution boundary.

- The Release itself does not automatically run the Scheduled Task.
- The Release itself does not run KRX GUI and Selenium collection.
- The Release does not use SSM SendCommand.
- If the EC2 is running, keep the running state.
- If the EC2 is stopped, start it for deployment and restore it to the original stopped state after completion.
- Actual KRX business execution responsibility remains with the existing Windows Scheduled Task.

Do not perform actual Scheduled Task execution without a user request.

### 10.3 Writing Operational Commands

- Use the `list/describe → extract variable → subsequent verification` flow for dynamic identifiers.
- Do not record actual instance ids, ARNs, command ids, and private IPs in the documentation.
- Do not mix Windows and Linux shell syntax.
- Save files containing Korean as UTF-8 without BOM.
- Verify the exit code of native commands.
- Do not print a SUCCESS or DONE marker after a failure.

## 11. Execution Restrictions

Do not perform the following work unless explicitly requested by the user.

| Category | Prohibited Work |
| --- | --- |
| Crawler | Daily · Main · individual collection execution |
| History | backfill · gap fill execution |
| Validation | DB-connected validation execution |
| Network | Naver · yfinance · KRX · holiday API calls |
| Browser | Selenium · Chrome · ChromeDriver execution |
| KRX | login · CSV download |
| DB | DDL · DML · migration · psql |
| AWS | ECS · SSM · Scheduler execution or change |
| Windows | Scheduled Task execution or change |
| Slack | webhook or notifier calls |
| Git | add · commit · push · reset · restore |

Run read-only validation only within the user-requested scope.

## 12. Tests and Validation

### 12.1 Basic Principles

- Prefer unit tests that are possible without real external sources and DB.
- Isolate HTTP, yfinance, Selenium, filesystem, and DB connections with mocks or stubs.
- Do not use real credentials and operational environment variables in tests.
- Ensure tests do not automatically run Chrome and network.
- History tests use only short fixture periods.

### 12.2 Minimum Validation by Change

| Change Target | Minimum Validation |
| --- | --- |
| Python syntax | Safe compile check |
| HTTP parser | Stored fixture response |
| HTML parser | Local fixture HTML |
| CSV parser | Local fixture CSV |
| yfinance handling | DataFrame mock |
| KRX login · download | Selenium mock |
| Daily orchestration | child call mock · exit code |
| History | chunk · checkpoint · idempotency |
| Validation | DB result mock · expected date |
| Repository | SQL · parameter · upsert test |
| Documentation | Links · facts · readability |
| Script | syntax · argument-passing static check |

For files with execution-risk imports, first check for side effects even during compile.

Do not record validation that could not be run as complete; record the reason it was not run.

## 13. Documentation Management Rules

### 13.1 README.md

The README describes the current structure and operational AS-IS of port-interest-crawler.

Content to include in the README:

- Project role
- Primary Source Data
- Daily · History · Validation distinction
- non-GUI and Windows KRX worker
- strict-exit and raw validation
- DB and schema
- Configuration and external dependencies
- AWS · Windows operational boundary
- Security and execution restrictions
- Links to detailed documentation

Do not copy other microservices and the full Step Functions definition at length.

### 13.2 CHANGELOG.md

The CHANGELOG records only the primary changes to port-interest-crawler code and documentation.

- Add the latest date at the top.
- Use `Added`, `Changed`, `Fixed`, `Removed`, `Security` as needed.
- Record only actual Crawler changes.
- Do not record one-time execution timestamps, command ids, and raw logs.
- Use primarily two-column tables in new sections.
- Preserve historical entries unless separately requested otherwise.

### 13.3 docs

Before creating a new document, first determine whether it can be incorporated into the README, CHANGELOG, and existing docs.

Do not create date-specific `docs/worklog/*.md` files.

Record code and documentation change history in `CHANGELOG.md`.

### 13.4 Automatic source-file-catalog.md Updates

When `docs/source-file-catalog.md` exists and one of the following changes occurs, determine within the same task whether it must be updated.

| Change | Handling |
| --- | --- |
| Create · delete · rename a primary Python file | Update the catalog |
| Change Daily · History · Validation responsibility | Update roles and risks |
| Change non-GUI · KRX worker structure | Update the execution model |
| Change Source Data · parser responsibility | Update sources and cautions |
| Change config · DB loader roles | Update the configuration section |
| Change scripts · worker wrapper | Update the operations section |
| Create · delete a document or change its role | Update the Documents section |
| Change only internal implementation · same responsibility | May be omitted |

The catalog is not an inventory of every file.

Record only entrypoints, grouped paths, and responsibilities meaningful to operations and maintenance.

## 14. Git Rules

Only read-only status inspection is allowed by default.

| Allowed | Prohibited |
| --- | --- |
| `git status --short`<br>`git diff --stat`<br>`git diff --check` | `git add`<br>`git commit`<br>`git push`<br>`git reset`<br>`git restore`<br>`git checkout`<br>`git stash` |

Do not create a commit unless explicitly requested by the user.

## 15. Completion Report

At completion, report only the following and keep it concise.

| Item | Content |
| --- | --- |
| Changed files | Files actually modified |
| Key changes | Summary of functional or documentation changes |
| Execution risk | Source · KRX · DB paths not executed |
| Validation | Static checks and tests performed |
| Not performed | Validation that could not be run |
| Security | Whether sensitive values were recorded verbatim |
| Follow-up | Only items that actually remain |

Distinguish work performed by the operator from work performed by Kiro.

## 16. Completion Checklist

- [ ] Were only the requested port-interest-crawler files modified?
- [ ] Were other microservices and `.kiro` files left unchanged unless needed?
- [ ] Were the highest-priority documentation readability rules applied?
- [ ] Do new standalone tables use two columns by default?
- [ ] Were long cells and lines avoided?
- [ ] Were the Daily · History · Validation roles distinguished?
- [ ] Were non-GUI and the Windows KRX worker not confused?
- [ ] Were per-source failures and empty data distinguished?
- [ ] Were KRX maintenance · redirect · timeout not treated as success?
- [ ] Were the meanings of raw validation and downstream blocking preserved?
- [ ] Were the history bulk-loading range and idempotency verified?
- [ ] Was DB unique key · upsert · transaction consistency verified?
- [ ] Were the Market Holiday and Trading Day criteria verified?
- [ ] Were sensitive values kept out of the documentation verbatim?
- [ ] Were failures not recorded as SUCCESS · NO_CHANGE?
- [ ] Was validation appropriate to the change scope performed?
- [ ] If file structure or responsibility changed, was `docs/source-file-catalog.md` checked?
- [ ] Were no date-specific `docs/worklog/*.md` files created?
- [ ] Were files saved as UTF-8 without BOM?
- [ ] Were only actual changes reflected in the README and CHANGELOG?
