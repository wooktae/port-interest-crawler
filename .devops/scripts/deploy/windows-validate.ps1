$ErrorActionPreference = "Stop"

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$CandidateRoot = "C:\portfolio\codedeploy-candidate\port-interest-crawler"
$ManifestPath = Join-Path $CandidateRoot "deployment-manifest.json"

$BaselinePath = "C:\ProgramData\Portfolio\CrawlerCodeDeploy\candidate-baseline.json"

$ProductionRoot = "C:\portfolio\port-interest-crawler"
$ProductionWrapper = "C:\portfolio\run_krx_worker_daily.ps1"

Write-Output "=== CRAWLER WINDOWS VALIDATE SERVICE ==="

if (-not (Test-Path $ManifestPath)) {
    Write-Output "CANDIDATE_MANIFEST_NOT_FOUND"
    exit 10
}

if (-not (Test-Path $BaselinePath)) {
    Write-Output "BASELINE_NOT_FOUND"
    exit 11
}

$Manifest = Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Baseline = Get-Content $BaselinePath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Output "CANDIDATE_SOURCE_SHA=$($Manifest.source_sha)"

if ([string]$Manifest.source_sha -ne [string]$Baseline.source_sha) {
    Write-Output "SOURCE_SHA_BASELINE_MISMATCH"
    exit 12
}

$WrapperSha = (
    Get-FileHash $ProductionWrapper -Algorithm SHA256
).Hash.ToLowerInvariant()

Write-Output "BASELINE_WRAPPER_SHA256=$($Baseline.production_wrapper_sha256)"
Write-Output "CURRENT_WRAPPER_SHA256=$WrapperSha"

if (
    $WrapperSha -ne
    ([string]$Baseline.production_wrapper_sha256).ToLowerInvariant()
) {
    Write-Output "PRODUCTION_WRAPPER_CHANGED"
    exit 20
}

Write-Output "PRODUCTION_WRAPPER_UNCHANGED=SUCCESS"

$ChangedCount = 0

foreach ($Record in @($Baseline.production_files)) {

    $Relative = [string]$Record.path
    $Target = Join-Path $ProductionRoot ($Relative.Replace("/", "\"))

    if (-not (Test-Path $Target -PathType Leaf)) {
        Write-Output "PRODUCTION_FILE_MISSING=$Relative"
        $ChangedCount++
        continue
    }

    $CurrentHash = (
        Get-FileHash $Target -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if (
        $CurrentHash -ne
        ([string]$Record.sha256).ToLowerInvariant()
    ) {
        Write-Output "PRODUCTION_FILE_CHANGED=$Relative"
        $ChangedCount++
    }
}

Write-Output "PRODUCTION_SOURCE_CHANGED_COUNT=$ChangedCount"

if ($ChangedCount -ne 0) {
    exit 30
}

Write-Output "PRODUCTION_SOURCE_UNCHANGED=SUCCESS"

$Task = Get-ScheduledTask `
    -TaskName $Baseline.scheduled_task_name `
    -ErrorAction Stop

$Actions = @($Task.Actions)

Write-Output "TASK_STATE=$($Task.State)"
Write-Output "TASK_ACTION_COUNT=$($Actions.Count)"

if ($Actions.Count -ne 1) {
    Write-Output "TASK_ACTION_COUNT_CHANGED"
    exit 40
}

if (
    [string]$Actions[0].Execute -ne
    [string]$Baseline.scheduled_task_execute
) {
    Write-Output "TASK_EXECUTE_CHANGED"
    exit 41
}

if (
    [string]$Actions[0].Arguments -ne
    [string]$Baseline.scheduled_task_arguments
) {
    Write-Output "TASK_ARGUMENTS_CHANGED"
    exit 42
}

if ($Task.State -eq "Running") {
    Write-Output "SCHEDULED_TASK_RUNNING_DURING_VALIDATION"
    exit 43
}

Write-Output "SCHEDULED_TASK_UNCHANGED=SUCCESS"

Write-Output "KRX_LOGIN_EXECUTION_COUNT=0"
Write-Output "PROGRAM_COLLECTION_EXECUTION_COUNT=0"
Write-Output "SHORTSELL_COLLECTION_EXECUTION_COUNT=0"
Write-Output "DB_WRITE_EXECUTION_COUNT=0"

Write-Output "CRAWLER_WINDOWS_CANDIDATE_STAGING=SUCCESS"
Write-Output "CRAWLER_WINDOWS_VALIDATE_SERVICE=SUCCESS"