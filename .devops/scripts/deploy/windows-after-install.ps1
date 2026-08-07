$ErrorActionPreference = "Stop"

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$CandidateRoot = "C:\portfolio\codedeploy-candidate\port-interest-crawler"
$ManifestPath = Join-Path $CandidateRoot "deployment-manifest.json"
$Python = "C:\portfolio\venvs\interest-crawler\Scripts\python.exe"

Write-Output "=== CRAWLER WINDOWS AFTER INSTALL ==="

if (-not (Test-Path $CandidateRoot)) {
    Write-Output "CANDIDATE_ROOT_NOT_FOUND"
    exit 10
}

if (-not (Test-Path $ManifestPath)) {
    Write-Output "CANDIDATE_MANIFEST_NOT_FOUND"
    exit 11
}

if (-not (Test-Path $Python)) {
    Write-Output "CRAWLER_PYTHON_NOT_FOUND"
    exit 12
}

$Manifest = Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Output "SOURCE_SHA=$($Manifest.source_sha)"
Write-Output "MANIFEST_FILE_COUNT=$($Manifest.file_count)"

$ErrorCount = 0

foreach ($Record in @($Manifest.files)) {

    $Relative = [string]$Record.path
    $ExpectedHash = ([string]$Record.sha256).ToLowerInvariant()
    $Target = Join-Path $CandidateRoot ($Relative.Replace("/", "\"))

    if (-not (Test-Path $Target -PathType Leaf)) {
        Write-Output "MISSING_FILE=$Relative"
        $ErrorCount++
        continue
    }

    $ActualHash = (
        Get-FileHash $Target -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($ActualHash -ne $ExpectedHash) {
        Write-Output "HASH_MISMATCH=$Relative"
        $ErrorCount++
    }
}

Write-Output "MANIFEST_HASH_ERROR_COUNT=$ErrorCount"

if ($ErrorCount -ne 0) {
    exit 20
}

Write-Output "CANDIDATE_MANIFEST_HASH_VERIFY=SUCCESS"

$Forbidden = @(
    ".env",
    ".env.local",
    "load-crawler-db-env.ps1",
    "load-krx-env.ps1",
    "ALL_SCHEMA_TABLE_DUMP.txt"
)

foreach ($Relative in $Forbidden) {

    if (Test-Path (Join-Path $CandidateRoot $Relative)) {
        Write-Output "FORBIDDEN_RUNTIME_FILE=$Relative"
        exit 30
    }
}

Write-Output "CANDIDATE_FORBIDDEN_RUNTIME_FILE=SUCCESS"

$PythonFiles = @(
    $Manifest.files |
    Where-Object {
        ([string]$_.path).ToLowerInvariant().EndsWith(".py")
    }
)

Write-Output "CANDIDATE_PYTHON_FILE_COUNT=$($PythonFiles.Count)"

foreach ($Record in $PythonFiles) {

    $Relative = [string]$Record.path
    $Target = Join-Path $CandidateRoot ($Relative.Replace("/", "\"))

    $CompileCode = "import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec')"

    & $Python -c $CompileCode $Target

    if ($LASTEXITCODE -ne 0) {
        Write-Output "PYTHON_SYNTAX_FAILED=$Relative"
        exit 40
    }
}

Write-Output "CANDIDATE_PYTHON_COMPILE=SUCCESS"

$Wrapper = Join-Path $CandidateRoot "ops\run_krx_worker_daily.ps1"

if (-not (Test-Path $Wrapper)) {
    Write-Output "CANDIDATE_WRAPPER_NOT_FOUND"
    exit 50
}

Write-Output "CANDIDATE_WRAPPER_PRESENT=YES"

Write-Output "KRX_LOGIN_EXECUTION_COUNT=0"
Write-Output "PROGRAM_COLLECTION_EXECUTION_COUNT=0"
Write-Output "SHORTSELL_COLLECTION_EXECUTION_COUNT=0"
Write-Output "DB_CONNECTION_EXECUTION_COUNT=0"

Write-Output "CRAWLER_WINDOWS_AFTER_INSTALL=SUCCESS"