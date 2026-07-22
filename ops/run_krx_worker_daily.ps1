$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONLEGACYWINDOWSSTDIO = '0'
$ErrorActionPreference = "Stop"

$RootDir = "C:\portfolio"
$AppDir = "C:\portfolio\port-interest-crawler"
$VenvActivate = "C:\portfolio\venvs\interest-crawler\Scripts\Activate.ps1"
$LogDir = "C:\portfolio\logs"

$RunStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "krx_worker_daily_$RunStamp.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Step {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Run-Command {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Step "START :: $Name"

    try {
        & $Command 2>&1 | Tee-Object -FilePath $LogFile -Append
        if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
        Write-Step "SUCCESS :: $Name"
    }
    catch {
        Write-Step "FAILED :: $Name"
        Write-Step $_.Exception.Message
        throw
    }
}

Write-Step "===================================================================================================="
Write-Step "START :: KRX worker daily"
Write-Step "LogFile=$LogFile"

Set-Location $AppDir

Write-Step "Activate venv"
. $VenvActivate

Write-Step "Load crawler DB env"
. "$RootDir\load-crawler-db-env.ps1"

Write-Step "Load KRX env"
. "$RootDir\load-krx-env.ps1"

Write-Step "Check download junction"
$downloadItem = Get-Item "C:\Users\USER\Downloads" -Force -ErrorAction SilentlyContinue
if ($null -eq $downloadItem -or $downloadItem.LinkType -ne "Junction") {
    Write-Step "Recreate download junction"
    New-Item -ItemType Directory -Path "C:\Users\USER" -Force | Out-Null

    if (Test-Path "C:\Users\USER\Downloads") {
        Remove-Item "C:\Users\USER\Downloads" -Recurse -Force
    }

    cmd /c mklink /J "C:\Users\USER\Downloads" "C:\Users\Administrator\Downloads" | Tee-Object -FilePath $LogFile -Append
}
else {
    Write-Step "Download junction already exists"
}

Run-Command "KRX login" {
    python interest_krx_login_new.py
}

Write-Step "Clear old CSV before program"
Remove-Item "C:\Users\Administrator\Downloads\data_*.csv" -Force -ErrorAction SilentlyContinue

Run-Command "KRX program" {
    python interest_program.py
}

Write-Step "Clear old CSV before shortsell"
Remove-Item "C:\Users\Administrator\Downloads\data_*.csv" -Force -ErrorAction SilentlyContinue

Run-Command "KRX shortsell" {
    python interest_shortsell.py
}

Write-Step "Prepare crawler DB validator"

$ValidatorPath = Join-Path $AppDir "validate_krx_daily_db.py"

$ValidatorCode = @"
from datetime import datetime, timedelta
import sys

import psycopg2

from db_config import get_db_config
from interest_get_holidays import is_holiday


PROGRAM_MIN_COUNT = 1
SHORTSELL_MIN_COUNT = 300


def get_expected_trade_date():
    day = datetime.now().date() - timedelta(days=1)

    while is_holiday(day, "KR"):
        day -= timedelta(days=1)

    return day


def main():
    expected = get_expected_trade_date()
    config = get_db_config()

    conn = psycopg2.connect(**config)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(trade_date)
                FROM interest_program_raw
                """
            )
            program_latest_date = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM interest_program_raw
                WHERE trade_date = %s
                """,
                (expected,)
            )
            program_count = cur.fetchone()[0]

            cur.execute(
                """
                SELECT MAX(trade_date)
                FROM interest_shortsell_raw
                """
            )
            shortsell_latest_date = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM interest_shortsell_raw
                WHERE trade_date = %s
                """,
                (expected,)
            )
            shortsell_count = cur.fetchone()[0]

    finally:
        conn.close()

    print(f"EXPECTED_TRADE_DATE={expected}")
    print(f"PROGRAM_LATEST_DATE={program_latest_date}")
    print(f"PROGRAM_EXPECTED_COUNT={program_count}")
    print(f"SHORTSELL_LATEST_DATE={shortsell_latest_date}")
    print(f"SHORTSELL_EXPECTED_COUNT={shortsell_count}")

    errors = []

    if program_latest_date != expected:
        errors.append(
            "PROGRAM_LATEST_DATE_MISMATCH "
            f"expected={expected} actual={program_latest_date}"
        )

    if program_count != PROGRAM_MIN_COUNT:
        errors.append(
            "PROGRAM_COUNT_INVALID "
            f"expected={PROGRAM_MIN_COUNT} actual={program_count}"
        )

    if shortsell_latest_date != expected:
        errors.append(
            "SHORTSELL_LATEST_DATE_MISMATCH "
            f"expected={expected} actual={shortsell_latest_date}"
        )

    if shortsell_count < SHORTSELL_MIN_COUNT:
        errors.append(
            "SHORTSELL_COUNT_BELOW_MINIMUM "
            f"minimum={SHORTSELL_MIN_COUNT} actual={shortsell_count}"
        )

    if errors:
        for error in errors:
            print(f"VALIDATION_ERROR={error}")

        print(
            "CRAWLER_DB_VALIDATION=FAILED "
            f"error_count={len(errors)}"
        )
        return 1

    print(
        "CRAWLER_DB_VALIDATION=SUCCESS "
        f"expected_trade_date={expected} "
        f"program_count={program_count} "
        f"shortsell_count={shortsell_count}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
"@

[System.IO.File]::WriteAllText(
    $ValidatorPath,
    $ValidatorCode,
    [System.Text.UTF8Encoding]::new($false)
)

try {
    Run-Command "Validate crawler DB" {
        python $ValidatorPath
    }
}
finally {
    Remove-Item `
        -LiteralPath $ValidatorPath `
        -Force `
        -ErrorAction SilentlyContinue
}
Write-Step "DONE :: KRX worker daily"
Write-Step "===================================================================================================="
