$ErrorActionPreference = "Stop"

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$CandidateRoot = "C:\portfolio\codedeploy-candidate\port-interest-crawler"
$StateRoot = "C:\ProgramData\Portfolio\CrawlerCodeDeploy"
$BaselinePath = Join-Path $StateRoot "candidate-baseline.json"

$ProductionRoot = "C:\portfolio\port-interest-crawler"
$ProductionWrapper = "C:\portfolio\run_krx_worker_daily.ps1"
$TaskName = "Portfolio-KRX-Worker-Daily"

Write-Output "=== CRAWLER WINDOWS BEFORE INSTALL ==="

$RevisionRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ManifestPath = Join-Path $RevisionRoot "deployment-manifest.json"

if (-not (Test-Path $ManifestPath)) {
    Write-Output "REVISION_MANIFEST_NOT_FOUND"
    exit 10
}

$Manifest = Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($Manifest.artifact_type -ne "crawler-windows-versioned-zip") {
    Write-Output "ARTIFACT_TYPE_INVALID"
    exit 11
}

if ($Manifest.service -ne "port-interest-crawler") {
    Write-Output "SERVICE_INVALID"
    exit 12
}

if ($Manifest.runtime -ne "windows-krx-worker") {
    Write-Output "RUNTIME_INVALID"
    exit 13
}

if ([string]$Manifest.source_sha -notmatch '^[0-9a-f]{40}$') {
    Write-Output "SOURCE_SHA_INVALID"
    exit 14
}

Write-Output "SOURCE_SHA=$($Manifest.source_sha)"
Write-Output "REVISION_MANIFEST=SUCCESS"

if (-not (Test-Path $ProductionRoot)) {
    Write-Output "PRODUCTION_ROOT_NOT_FOUND"
    exit 20
}

if (-not (Test-Path $ProductionWrapper)) {
    Write-Output "PRODUCTION_WRAPPER_NOT_FOUND"
    exit 21
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

if ($Task.State -eq "Running") {
    Write-Output "SCHEDULED_TASK_RUNNING=BLOCK"
    exit 22
}

$Actions = @($Task.Actions)

if ($Actions.Count -ne 1) {
    Write-Output "TASK_ACTION_COUNT_INVALID=$($Actions.Count)"
    exit 23
}

$ExpectedExecute = "powershell.exe"
$ExpectedArguments = "-ExecutionPolicy Bypass -File C:\portfolio\run_krx_worker_daily.ps1"

if ([string]$Actions[0].Execute -ne $ExpectedExecute) {
    Write-Output "TASK_EXECUTE_INVALID=$($Actions[0].Execute)"
    exit 24
}

if ([string]$Actions[0].Arguments -ne $ExpectedArguments) {
    Write-Output "TASK_ARGUMENTS_INVALID=$($Actions[0].Arguments)"
    exit 25
}

$WrapperSha = (
    Get-FileHash $ProductionWrapper -Algorithm SHA256
).Hash.ToLowerInvariant()

$ProductionFiles = @()

foreach ($Record in @($Manifest.files)) {

    $Relative = [string]$Record.path

    if ($Relative -eq "appspec.yml" -or $Relative -like ".devops/*") {
        continue
    }

    $Target = Join-Path $ProductionRoot ($Relative.Replace("/", "\"))

    if (Test-Path $Target -PathType Leaf) {

        $Hash = (
            Get-FileHash $Target -Algorithm SHA256
        ).Hash.ToLowerInvariant()

        $ProductionFiles += @{
            path = $Relative
            sha256 = $Hash
        }
    }
}

$Baseline = @{
    source_sha = [string]$Manifest.source_sha
    production_wrapper_sha256 = $WrapperSha
    scheduled_task_name = $TaskName
    scheduled_task_execute = [string]$Actions[0].Execute
    scheduled_task_arguments = [string]$Actions[0].Arguments
    production_files = $ProductionFiles
}

New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null

[System.IO.File]::WriteAllText(
    $BaselinePath,
    ($Baseline | ConvertTo-Json -Depth 20),
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "OPERATING_BASELINE_CAPTURE=SUCCESS"

if (Test-Path $CandidateRoot) {
    Remove-Item $CandidateRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $CandidateRoot | Out-Null

Write-Output "CANDIDATE_STAGING_RESET=SUCCESS"
Write-Output "CRAWLER_WINDOWS_BEFORE_INSTALL=SUCCESS"