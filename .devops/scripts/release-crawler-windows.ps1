param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceSha,

    [Parameter(Mandatory = $false)]
    [string]$Region = "ap-northeast-2"
)

$ErrorActionPreference = "Stop"
$env:AWS_PAGER = ""

$ShortSha = $SourceSha.Substring(0, 12).ToLowerInvariant()

$ApplicationName = "portfolio-interest-crawler-windows"
$DeploymentGroup = "portfolio-interest-crawler-windows-ec2"
$InstanceId      = "i-0ff768ea639a91355"

$AccountId = "309011444323"
$Bucket = "portfolio-interest-crawler-artifacts-$AccountId"
$Key = "crawler/windows/$SourceSha/port-interest-crawler-windows-$ShortSha.zip"

$StartedByRelease = $false
$DeploymentId = ""
$FinalStatus = ""

function Invoke-AwsText {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Failure
    )

    $stderrPath = [System.IO.Path]::GetTempFileName()

    try {
        $oldPreference = $ErrorActionPreference

        try {
            $ErrorActionPreference = "Continue"

            $output = @(
                & aws @Arguments 2>$stderrPath
            )

            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldPreference
        }

        if ($exitCode -ne 0) {
            $detail = ""

            if (Test-Path -LiteralPath $stderrPath) {
                $detail = (
                    [System.IO.File]::ReadAllText($stderrPath)
                ).Trim()
            }

            if ([string]::IsNullOrWhiteSpace($detail)) {
                $detail = "AWS_CLI_EXIT_$exitCode"
            }

            throw "$Failure=$detail"
        }

        return ($output -join "`n").Trim()
    }
    finally {
        if (Test-Path -LiteralPath $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-AwsJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Failure
    )

    $text = Invoke-AwsText `
        -Arguments $Arguments `
        -Failure $Failure

    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "$Failure=EMPTY_JSON"
    }

    try {
        return $text | ConvertFrom-Json
    }
    catch {
        throw "$Failure=INVALID_JSON"
    }
}

function Get-InstanceState {

    $json = Invoke-AwsJson `
        -Arguments @(
            "ec2",
            "describe-instances",
            "--region", $Region,
            "--instance-ids", $InstanceId,
            "--output", "json"
        ) `
        -Failure "EC2_DESCRIBE_FAILED"

    $instance = @(
        $json.Reservations |
        ForEach-Object {
            @($_.Instances)
        }
    ) | Select-Object -First 1

    if (-not $instance) {
        throw "TARGET_INSTANCE_NOT_FOUND"
    }

    return [string]$instance.State.Name
}

function Wait-SsmOnline {

    for ($attempt = 1; $attempt -le 60; $attempt++) {

        $json = Invoke-AwsJson `
            -Arguments @(
                "ssm",
                "describe-instance-information",
                "--region", $Region,
                "--filters", "Key=InstanceIds,Values=$InstanceId",
                "--output", "json"
            ) `
            -Failure "SSM_READINESS_FAILED"

        $info = @(
            $json.InstanceInformationList
        ) | Select-Object -First 1

        if (
            $info -and
            [string]$info.PingStatus -eq "Online"
        ) {
            return
        }

        Start-Sleep -Seconds 5
    }

    throw "SSM_ONLINE_TIMEOUT"
}

try {
    # ================================================================
    # 1. Verify exact immutable S3 artifact
    # ================================================================
    $versions = Invoke-AwsJson `
        -Arguments @(
            "s3api",
            "list-object-versions",
            "--bucket", $Bucket,
            "--prefix", $Key,
            "--output", "json"
        ) `
        -Failure "S3_VERSION_LIST_FAILED"

    $version = @(
        $versions.Versions |
        Where-Object {
            [string]$_.Key -eq $Key
        } |
        Sort-Object LastModified -Descending
    ) | Select-Object -First 1

    if (-not $version) {
        throw "WINDOWS_ARTIFACT_NOT_FOUND=$Key"
    }

    $VersionId = [string]$version.VersionId
    $ETag = ([string]$version.ETag).Trim('"')

    if ([string]::IsNullOrWhiteSpace($VersionId)) {
        throw "WINDOWS_ARTIFACT_VERSION_EMPTY"
    }

    # ================================================================
    # 2. Idempotency guard
    # ================================================================
    $list = Invoke-AwsJson `
        -Arguments @(
            "deploy",
            "list-deployments",
            "--region", $Region,
            "--application-name", $ApplicationName,
            "--deployment-group-name", $DeploymentGroup,
            "--output", "json"
        ) `
        -Failure "CODEDEPLOY_LIST_FAILED"

    foreach ($id in @($list.deployments | Select-Object -First 20)) {

        $existing = Invoke-AwsJson `
            -Arguments @(
                "deploy",
                "get-deployment",
                "--region", $Region,
                "--deployment-id", ([string]$id),
                "--output", "json"
            ) `
            -Failure "CODEDEPLOY_EXISTING_READ_FAILED"

        $info = $existing.deploymentInfo

        $existingKey = ""

        if (
            $info.revision -and
            $info.revision.s3Location
        ) {
            $existingKey = [string]$info.revision.s3Location.key
        }

        if (
            [string]$info.description -eq "crawler-windows-$ShortSha" -or
            $existingKey -eq $Key
        ) {
            if ([string]$info.status -eq "Succeeded") {

                Write-Host ""
                Write-Host "=== CRAWLER WINDOWS RELEASE RESULT ==="
                Write-Host "CRAWLER_WINDOWS_RELEASE=SUCCESS"
                Write-Host "SOURCE_SHA=$SourceSha"
                Write-Host "DEPLOYMENT_ID=$id"
                Write-Host "DEPLOYMENT_STATUS=Succeeded"
                Write-Host "RELEASE_ACTION=SKIPPED_ALREADY_DEPLOYED"
                Write-Host "SCHEDULED_TASK_EXECUTED=NO"
                Write-Host "KRX_GUI_EXECUTED=NO"
                Write-Host "=== CRAWLER WINDOWS RELEASE END ==="

                exit 0
            }

            throw "CURRENT_SHA_DEPLOYMENT_ALREADY_EXISTS=$id|status=$($info.status)"
        }
    }

    # ================================================================
    # 3. Preserve EC2 lifecycle state
    # ================================================================
    $InitialState = Get-InstanceState

    switch ($InitialState) {

        "running" {
            # Preserve running state.
        }

        "stopped" {
            Invoke-AwsText `
                -Arguments @(
                    "ec2",
                    "start-instances",
                    "--region", $Region,
                    "--instance-ids", $InstanceId,
                    "--output", "json"
                ) `
                -Failure "EC2_START_FAILED" |
                Out-Null

            $StartedByRelease = $true

            Invoke-AwsText `
                -Arguments @(
                    "ec2",
                    "wait",
                    "instance-running",
                    "--region", $Region,
                    "--instance-ids", $InstanceId
                ) `
                -Failure "EC2_RUNNING_WAIT_FAILED" |
                Out-Null

            Invoke-AwsText `
                -Arguments @(
                    "ec2",
                    "wait",
                    "instance-status-ok",
                    "--region", $Region,
                    "--instance-ids", $InstanceId
                ) `
                -Failure "EC2_STATUS_WAIT_FAILED" |
                Out-Null
        }

        default {
            throw "UNSUPPORTED_EC2_INITIAL_STATE=$InitialState"
        }
    }

    Wait-SsmOnline

    # ================================================================
    # 4. Exact S3 revision
    # ================================================================
    $revision = [ordered]@{
        revisionType = "S3"
        s3Location = [ordered]@{
            bucket     = $Bucket
            key        = $Key
            bundleType = "zip"
            version    = $VersionId
            eTag       = $ETag
        }
    }

    $revisionPath = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        "crawler-windows-revision-$ShortSha.json"

    $utf8 = New-Object System.Text.UTF8Encoding($false)

    [System.IO.File]::WriteAllText(
        $revisionPath,
        ($revision | ConvertTo-Json -Depth 10),
        $utf8
    )

    # ================================================================
    # 5. CodeDeploy
    # ================================================================
    $DeploymentId = Invoke-AwsText `
        -Arguments @(
            "deploy",
            "create-deployment",
            "--region", $Region,
            "--application-name", $ApplicationName,
            "--deployment-group-name", $DeploymentGroup,
            "--revision", "file://$revisionPath",
            "--description", "crawler-windows-$ShortSha",
            "--query", "deploymentId",
            "--output", "text"
        ) `
        -Failure "CODEDEPLOY_CREATE_FAILED"

    if ($DeploymentId -notmatch '^d-[A-Z0-9]+$') {
        throw "DEPLOYMENT_ID_INVALID=$DeploymentId"
    }

    for ($attempt = 1; $attempt -le 120; $attempt++) {

        $deployment = Invoke-AwsJson `
            -Arguments @(
                "deploy",
                "get-deployment",
                "--region", $Region,
                "--deployment-id", $DeploymentId,
                "--output", "json"
            ) `
            -Failure "CODEDEPLOY_GET_FAILED"

        $FinalStatus = [string]$deployment.deploymentInfo.status

        if (
            $FinalStatus -in @(
                "Succeeded",
                "Failed",
                "Stopped"
            )
        ) {
            break
        }

        Start-Sleep -Seconds 5
    }

    if ($FinalStatus -ne "Succeeded") {
        throw "CODEDEPLOY_NOT_SUCCESS=$DeploymentId|$FinalStatus"
    }

    # ================================================================
    # 6. Verify immutable deployed revision
    # ================================================================
    $verified = Invoke-AwsJson `
        -Arguments @(
            "deploy",
            "get-deployment",
            "--region", $Region,
            "--deployment-id", $DeploymentId,
            "--output", "json"
        ) `
        -Failure "CODEDEPLOY_VERIFY_FAILED"

    $deployedKey =
        [string]$verified.deploymentInfo.revision.s3Location.key

    $deployedVersion =
        [string]$verified.deploymentInfo.revision.s3Location.version

    if ($deployedKey -ne $Key) {
        throw "DEPLOYED_KEY_MISMATCH=$deployedKey"
    }

    if ($deployedVersion -ne $VersionId) {
        throw "DEPLOYED_VERSION_MISMATCH=$deployedVersion"
    }

    Write-Host ""
    Write-Host "=== CRAWLER WINDOWS RELEASE RESULT ==="
    Write-Host "CRAWLER_WINDOWS_RELEASE=SUCCESS"
    Write-Host "SOURCE_SHA=$SourceSha"
    Write-Host "S3_VERSION_ID=$VersionId"
    Write-Host "DEPLOYMENT_ID=$DeploymentId"
    Write-Host "DEPLOYMENT_STATUS=$FinalStatus"
    Write-Host "EC2_INITIAL_STATE=$InitialState"
    Write-Host "EC2_STARTED_BY_RELEASE=$StartedByRelease"
    Write-Host "SCHEDULED_TASK_EXECUTED=NO"
    Write-Host "KRX_GUI_EXECUTED=NO"
    Write-Host "SSM_SENDCOMMAND_EXECUTED=NO"
    Write-Host "=== CRAWLER WINDOWS RELEASE END ==="
}
finally {

    # Restore original stopped state.
    if ($StartedByRelease) {

        try {
            Invoke-AwsText `
                -Arguments @(
                    "ec2",
                    "stop-instances",
                    "--region", $Region,
                    "--instance-ids", $InstanceId,
                    "--output", "json"
                ) `
                -Failure "EC2_RESTORE_STOP_FAILED" |
                Out-Null

            Invoke-AwsText `
                -Arguments @(
                    "ec2",
                    "wait",
                    "instance-stopped",
                    "--region", $Region,
                    "--instance-ids", $InstanceId
                ) `
                -Failure "EC2_RESTORE_STOP_WAIT_FAILED" |
                Out-Null
        }
        catch {
            Write-Error "EC2_STATE_RESTORE_FAILED=$($_.Exception.Message)"
            throw
        }
    }
}