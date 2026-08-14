param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceSha,

    [string]$Region = "ap-northeast-2"
)

$ErrorActionPreference = "Stop"

chcp 65001 *> $null
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Family        = "portfolio-paper-interest-crawler"
$ContainerName = "interest-crawler"

$RepoRoot = (
    Resolve-Path (Join-Path $PSScriptRoot "..\..")
).Path

$ManifestPath = Join-Path `
    $RepoRoot `
    ".devops\config\crawler-ecs-activation-scope.json"

$ArtifactRoot = Join-Path `
    $RepoRoot `
    ".devops\artifacts\crawler-ecs-release"

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$Updated = [System.Collections.Generic.List[object]]::new()
$RollbackErrors = [System.Collections.Generic.List[string]]::new()

function Invoke-AwsJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Failure
    )

    $raw = & aws @Arguments

    if ($LASTEXITCODE -ne 0) {
        throw $Failure
    }

    if ([string]::IsNullOrWhiteSpace(($raw -join "`n"))) {
        throw "${Failure}_EMPTY_RESPONSE"
    }

    return (($raw -join "`n") | ConvertFrom-Json)
}

function Write-Utf8Json {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        $Value,

        [int]$Depth = 100
    )

    $json = $Value | ConvertTo-Json -Depth $Depth

    [System.IO.File]::WriteAllText(
        $Path,
        $json,
        $Utf8NoBom
    )
}

function Get-StateMachineDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Arn
    )

    $desc = Invoke-AwsJson `
        -Arguments @(
            "stepfunctions",
            "describe-state-machine",
            "--region", $Region,
            "--state-machine-arn", $Arn,
            "--output", "json"
        ) `
        -Failure "STATE_MACHINE_DESCRIBE_FAILED"

    return [PSCustomObject]@{
        Arn        = $Arn
        Definition = [string]$desc.definition
        RoleArn    = [string]$desc.roleArn
    }
}

function Get-CrawlerRevisionFromDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Definition,

        [Parameter(Mandatory = $true)]
        [string]$StateName
    )

    $obj = $Definition | ConvertFrom-Json

    $prop = $obj.States.PSObject.Properties |
        Where-Object { $_.Name -eq $StateName } |
        Select-Object -First 1

    if (-not $prop) {
        throw "ACTIVATION_STATE_NOT_FOUND=$StateName"
    }

    $state = $prop.Value

    $params = $state.Parameters
    if ($null -eq $params) {
        $params = $state.Arguments
    }

    if ($null -eq $params) {
        throw "ACTIVATION_STATE_PARAMETERS_NOT_FOUND=$StateName"
    }

    $td = [string]$params.TaskDefinition

    if ($td -notmatch 'portfolio-paper-interest-crawler:(\d+)$') {
        throw "UNEXPECTED_CRAWLER_TASK_DEFINITION=$td"
    }

    return [int]$Matches[1]
}

function Set-CrawlerRevisionInDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Definition,

        [Parameter(Mandatory = $true)]
        [string]$StateName,

        [Parameter(Mandatory = $true)]
        [int]$Revision
    )

    $obj = $Definition | ConvertFrom-Json

    $prop = $obj.States.PSObject.Properties |
        Where-Object { $_.Name -eq $StateName } |
        Select-Object -First 1

    if (-not $prop) {
        throw "ACTIVATION_STATE_NOT_FOUND=$StateName"
    }

    $state = $prop.Value
    $newTd = "${Family}:${Revision}"

    if ($null -ne $state.Parameters) {
        $state.Parameters.TaskDefinition = $newTd
    }
    elseif ($null -ne $state.Arguments) {
        $state.Arguments.TaskDefinition = $newTd
    }
    else {
        throw "ACTIVATION_STATE_PARAMETERS_NOT_FOUND=$StateName"
    }

    return ($obj | ConvertTo-Json -Depth 100 -Compress)
}

try {
    # ------------------------------------------------------------
    # 1. Preconditions
    # ------------------------------------------------------------
    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "ACTIVATION_SCOPE_MANIFEST_NOT_FOUND"
    }

    $manifest = (
        [System.IO.File]::ReadAllText($ManifestPath)
    ) | ConvertFrom-Json

    $scope = @($manifest.activation_scope)

    if ($scope.Count -ne 7) {
        throw "ACTIVATION_SCOPE_COUNT_EXPECTED_7_ACTUAL_$($scope.Count)"
    }

    if ([string]$manifest.task_definition_family -ne $Family) {
        throw "ACTIVATION_SCOPE_FAMILY_MISMATCH"
    }

    $ShortSha = $SourceSha.Substring(0, 12).ToLowerInvariant()

    New-Item `
        -ItemType Directory `
        -Path $ArtifactRoot `
        -Force |
        Out-Null

    # ------------------------------------------------------------
    # 2. Resolve all approved State Machine ARNs
    # ------------------------------------------------------------
    $smList = Invoke-AwsJson `
        -Arguments @(
            "stepfunctions",
            "list-state-machines",
            "--region", $Region,
            "--output", "json"
        ) `
        -Failure "STATE_MACHINE_LIST_FAILED"

    $ResolvedScope = @()

    foreach ($item in $scope) {
        $name      = [string]$item.state_machine
        $stateName = [string]$item.state_name

        $sm = @($smList.stateMachines) |
            Where-Object { $_.name -eq $name } |
            Select-Object -First 1

        if (-not $sm) {
            throw "STATE_MACHINE_NOT_FOUND=$name"
        }

        $ResolvedScope += [PSCustomObject]@{
            Name      = $name
            Arn       = [string]$sm.stateMachineArn
            StateName = $stateName
        }
    }

    if ($ResolvedScope.Count -ne 7) {
        throw "RESOLVED_SCOPE_COUNT_INVALID"
    }

    # ------------------------------------------------------------
    # 3. Capture baseline definitions
    #    All 7 must currently use one common Crawler revision.
    # ------------------------------------------------------------
    $Baselines = @()
    $BaselineRevisions = @()

    foreach ($target in $ResolvedScope) {
        $current = Get-StateMachineDefinition -Arn $target.Arn

        $revision = Get-CrawlerRevisionFromDefinition `
            -Definition $current.Definition `
            -StateName $target.StateName

        $Baselines += [PSCustomObject]@{
            Name       = $target.Name
            Arn        = $target.Arn
            StateName  = $target.StateName
            Definition = $current.Definition
            Revision   = $revision
        }

        $BaselineRevisions += $revision
    }

    $BaselineRevisionSet = @(
        $BaselineRevisions |
        Sort-Object -Unique
    )

    if ($BaselineRevisionSet.Count -ne 1) {
        throw "BASELINE_REVISION_SET_NOT_UNIFORM=$($BaselineRevisionSet -join ',')"
    }

    $BaselineRevision = [int]$BaselineRevisionSet[0]

    # ------------------------------------------------------------
    # 4. Read operating TD baseline
    # ------------------------------------------------------------
    $tdResponse = Invoke-AwsJson `
        -Arguments @(
            "ecs",
            "describe-task-definition",
            "--region", $Region,
            "--task-definition", "${Family}:${BaselineRevision}",
            "--output", "json"
        ) `
        -Failure "BASELINE_TASK_DEFINITION_DESCRIBE_FAILED"

    $td = $tdResponse.taskDefinition

    if ([string]$td.status -ne "ACTIVE") {
        throw "BASELINE_TASK_DEFINITION_NOT_ACTIVE"
    }

    $container = @($td.containerDefinitions) |
        Where-Object { $_.name -eq $ContainerName } |
        Select-Object -First 1

    if (-not $container) {
        throw "CRAWLER_CONTAINER_NOT_FOUND"
    }

    $currentImage = [string]$container.image

    if (
        $currentImage -notmatch
        '^[0-9]+\.dkr\.ecr\.[^.]+\.amazonaws\.com/([^@:]+)'
    ) {
        throw "ECR_REPOSITORY_PARSE_FAILED"
    }

    $EcrRepository = $Matches[1]

    # ------------------------------------------------------------
    # 5. Resolve exact candidate image Digest
    #    Accept full SHA tag or 12-char SHA tag.
    # ------------------------------------------------------------
    $Digest = $null
    $ResolvedImageTag = $null

    foreach ($tag in @($SourceSha.ToLowerInvariant(), $ShortSha)) {
        $imageResultRaw = & aws ecr describe-images `
            --region $Region `
            --repository-name $EcrRepository `
            --image-ids "imageTag=$tag" `
            --output json 2>$null

        if ($LASTEXITCODE -eq 0 -and $imageResultRaw) {
            $imageResult = ($imageResultRaw -join "`n") | ConvertFrom-Json

            $candidateDigest = [string](
                @($imageResult.imageDetails) |
                Select-Object -First 1
            ).imageDigest

            if (-not [string]::IsNullOrWhiteSpace($candidateDigest)) {
                $Digest = $candidateDigest
                $ResolvedImageTag = $tag
                break
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($Digest)) {
        throw "CANDIDATE_ECR_DIGEST_NOT_FOUND_FOR_SOURCE_SHA"
    }

    if ($Digest -notmatch '^sha256:[0-9a-fA-F]{64}$') {
        throw "CANDIDATE_ECR_DIGEST_INVALID"
    }

    $RepositoryUri = $currentImage -replace '@sha256:[0-9a-fA-F]{64}$', ''

    if ($RepositoryUri -eq $currentImage) {
        $RepositoryUri = $currentImage -replace ':[^/:]+$', ''
    }

    $CandidateImage = "${RepositoryUri}@${Digest}"

    # ------------------------------------------------------------
    # 6. Build candidate Task Definition from current operating TD
    # ------------------------------------------------------------
    $candidateContainers = @(
        $td.containerDefinitions |
        ConvertTo-Json -Depth 100 |
        ConvertFrom-Json
    )

    $candidateContainer = $candidateContainers |
        Where-Object { $_.name -eq $ContainerName } |
        Select-Object -First 1

    if (-not $candidateContainer) {
        throw "CANDIDATE_CONTAINER_NOT_FOUND"
    }

    $candidateContainer.image = $CandidateImage

    # Operating business command remains unchanged in registered TD.
    $OperatingCommand = @($candidateContainer.command) -join " "

    if ($OperatingCommand -ne "python interest_crawler_daily_nongui.py") {
        throw "OPERATING_COMMAND_CONTRACT_CHANGED=$OperatingCommand"
    }

    $registerPayload = [ordered]@{
        family               = [string]$td.family
        taskRoleArn          = [string]$td.taskRoleArn
        executionRoleArn     = [string]$td.executionRoleArn
        networkMode          = [string]$td.networkMode
        containerDefinitions = $candidateContainers
        volumes              = @($td.volumes)
        placementConstraints = @($td.placementConstraints)
        requiresCompatibilities = @($td.requiresCompatibilities)
        cpu                   = [string]$td.cpu
        memory                = [string]$td.memory
    }

    foreach ($optional in @(
        "pidMode",
        "ipcMode",
        "proxyConfiguration",
        "inferenceAccelerators",
        "ephemeralStorage",
        "runtimePlatform",
        "enableFaultInjection"
    )) {
        if (
            $td.PSObject.Properties.Name -contains $optional -and
            $null -ne $td.$optional
        ) {
            $registerPayload[$optional] = $td.$optional
        }
    }

    $registerPath = Join-Path `
        $ArtifactRoot `
        "register-task-definition-${ShortSha}.json"

    Write-Utf8Json `
        -Path $registerPath `
        -Value $registerPayload

    $null = (
        [System.IO.File]::ReadAllText($registerPath)
    ) | ConvertFrom-Json

    # ------------------------------------------------------------
    # 7. Register candidate revision
    # ------------------------------------------------------------
    $registered = Invoke-AwsJson `
        -Arguments @(
            "ecs",
            "register-task-definition",
            "--region", $Region,
            "--cli-input-json", "file://$registerPath",
            "--output", "json"
        ) `
        -Failure "CANDIDATE_TASK_DEFINITION_REGISTER_FAILED"

    $CandidateTd = $registered.taskDefinition
    $CandidateRevision = [int]$CandidateTd.revision
    $CandidateTdArn = [string]$CandidateTd.taskDefinitionArn

    if ($CandidateRevision -le $BaselineRevision) {
        throw "CANDIDATE_REVISION_NOT_NEW"
    }

    if ([string]$CandidateTd.status -ne "ACTIVE") {
        throw "CANDIDATE_TASK_DEFINITION_NOT_ACTIVE"
    }

    # ------------------------------------------------------------
    # 8. Resolve operating network contract
    # ------------------------------------------------------------
    $main = $Baselines |
        Where-Object {
            $_.Name -eq "portfolio-paper-daily-step1-17-approval"
        } |
        Select-Object -First 1

    if (-not $main) {
        throw "MAIN_STATE_MACHINE_BASELINE_NOT_FOUND"
    }

    $mainDef = $main.Definition | ConvertFrom-Json
    $mainState = $mainDef.States.$($main.StateName)

    $mainParams = $mainState.Parameters
    if ($null -eq $mainParams) {
        $mainParams = $mainState.Arguments
    }

    $Cluster = [string]$mainParams.Cluster
    $AwsVpc  = $mainParams.NetworkConfiguration.AwsvpcConfiguration

    if ([string]::IsNullOrWhiteSpace($Cluster)) {
        throw "CANDIDATE_CLUSTER_NOT_FOUND"
    }

    $Subnets = @($AwsVpc.Subnets)
    $SecurityGroups = @($AwsVpc.SecurityGroups)
    $AssignPublicIp = [string]$AwsVpc.AssignPublicIp

    if ($Subnets.Count -eq 0) {
        throw "CANDIDATE_SUBNETS_NOT_FOUND"
    }

    if ($SecurityGroups.Count -eq 0) {
        throw "CANDIDATE_SECURITY_GROUPS_NOT_FOUND"
    }

    # ------------------------------------------------------------
    # 9. Candidate-safe Fargate execution
    # ------------------------------------------------------------
    $networkPayload = [ordered]@{
        awsvpcConfiguration = [ordered]@{
            subnets        = $Subnets
            securityGroups = $SecurityGroups
            assignPublicIp = $AssignPublicIp
        }
    }

    $candidateCommand = @(
        "python",
        "-m",
        "py_compile",
        "/app/interest_crawler_daily_nongui.py"
    )

    $overridePayload = [ordered]@{
        containerOverrides = @(
            [ordered]@{
                name    = $ContainerName
                command = $candidateCommand
            }
        )
    }

    $networkPath = Join-Path $ArtifactRoot "candidate-network.json"
    $overridePath = Join-Path $ArtifactRoot "candidate-override.json"

    Write-Utf8Json -Path $networkPath -Value $networkPayload
    Write-Utf8Json -Path $overridePath -Value $overridePayload

    $run = Invoke-AwsJson `
        -Arguments @(
            "ecs",
            "run-task",
            "--region", $Region,
            "--cluster", $Cluster,
            "--launch-type", "FARGATE",
            "--task-definition", $CandidateTdArn,
            "--network-configuration", "file://$networkPath",
            "--overrides", "file://$overridePath",
            "--started-by", "crawler-candidate-$ShortSha",
            "--count", "1",
            "--output", "json"
        ) `
        -Failure "CANDIDATE_RUNTASK_API_FAILED"

    if (@($run.failures).Count -gt 0) {
        $reason = (
            @($run.failures) |
            ForEach-Object { $_.reason }
        ) -join ";"

        throw "CANDIDATE_RUNTASK_REJECTED=$reason"
    }

    $tasks = @($run.tasks)

    if ($tasks.Count -ne 1) {
        throw "CANDIDATE_TASK_COUNT_INVALID=$($tasks.Count)"
    }

    $CandidateTaskArn = [string]$tasks[0].taskArn

    if ([string]::IsNullOrWhiteSpace($CandidateTaskArn)) {
        throw "CANDIDATE_TASK_ARN_EMPTY"
    }

    & aws ecs wait tasks-stopped `
        --region $Region `
        --cluster $Cluster `
        --tasks $CandidateTaskArn

    if ($LASTEXITCODE -ne 0) {
        throw "CANDIDATE_WAIT_FAILED"
    }

    $finalTask = Invoke-AwsJson `
        -Arguments @(
            "ecs",
            "describe-tasks",
            "--region", $Region,
            "--cluster", $Cluster,
            "--tasks", $CandidateTaskArn,
            "--output", "json"
        ) `
        -Failure "CANDIDATE_DESCRIBE_FAILED"

    $task = @($finalTask.tasks) | Select-Object -First 1

    if (-not $task) {
        throw "CANDIDATE_FINAL_TASK_NOT_FOUND"
    }

    $finalContainer = @($task.containers) |
        Where-Object { $_.name -eq $ContainerName } |
        Select-Object -First 1

    if (-not $finalContainer) {
        throw "CANDIDATE_FINAL_CONTAINER_NOT_FOUND"
    }

    if ([string]$task.lastStatus -ne "STOPPED") {
        throw "CANDIDATE_FINAL_STATUS_NOT_STOPPED"
    }

    if ($null -eq $finalContainer.exitCode) {
        throw "CANDIDATE_EXIT_CODE_EMPTY"
    }

    if ([int]$finalContainer.exitCode -ne 0) {
        throw "CANDIDATE_EXIT_CODE_$($finalContainer.exitCode)"
    }

    # ------------------------------------------------------------
    # 10. STALE PROMOTION GUARD
    #
    # Nothing in the 7-state Activation Scope may have changed
    # since the release started.
    # ------------------------------------------------------------
    foreach ($baseline in $Baselines) {
        $current = Get-StateMachineDefinition -Arn $baseline.Arn

        $revision = Get-CrawlerRevisionFromDefinition `
            -Definition $current.Definition `
            -StateName $baseline.StateName

        if ($revision -ne $BaselineRevision) {
            throw "STALE_PROMOTION_GUARD_REVISION_CHANGED=$($baseline.Name)|expected=$BaselineRevision|actual=$revision"
        }

        if ($current.Definition -ne $baseline.Definition) {
            throw "STALE_PROMOTION_GUARD_DEFINITION_CHANGED=$($baseline.Name)"
        }
    }

    # ------------------------------------------------------------
    # 11. Promote exact approved 7-state Activation Scope
    # ------------------------------------------------------------
    foreach ($baseline in $Baselines) {
        $newDefinition = Set-CrawlerRevisionInDefinition `
            -Definition $baseline.Definition `
            -StateName $baseline.StateName `
            -Revision $CandidateRevision

        $safeName = $baseline.Name -replace '[^A-Za-z0-9._-]', '_'

        $definitionPath = Join-Path `
            $ArtifactRoot `
            "${safeName}-promotion.json"

        [System.IO.File]::WriteAllText(
            $definitionPath,
            $newDefinition,
            $Utf8NoBom
        )

        & aws stepfunctions update-state-machine `
            --region $Region `
            --state-machine-arn $baseline.Arn `
            --definition "file://$definitionPath" `
            *> $null

        if ($LASTEXITCODE -ne 0) {
            throw "STATE_MACHINE_PROMOTION_FAILED=$($baseline.Name)"
        }

        $Updated.Add($baseline)
    }

    # ------------------------------------------------------------
    # 12. Verify all 7 now reference exactly Candidate revision
    # ------------------------------------------------------------
    foreach ($baseline in $Baselines) {
        $verified = $false

        for ($attempt = 1; $attempt -le 5; $attempt++) {
            $current = Get-StateMachineDefinition -Arn $baseline.Arn

            $revision = Get-CrawlerRevisionFromDefinition `
                -Definition $current.Definition `
                -StateName $baseline.StateName

            if ($revision -eq $CandidateRevision) {
                $verified = $true
                break
            }

            Start-Sleep -Seconds 2
        }

        if (-not $verified) {
            throw "PROMOTION_VERIFY_FAILED=$($baseline.Name)"
        }
    }

    # ------------------------------------------------------------
    # 13. Final uniform revision check
    # ------------------------------------------------------------
    $FinalRevisionSet = @()

    foreach ($baseline in $Baselines) {
        $current = Get-StateMachineDefinition -Arn $baseline.Arn

        $FinalRevisionSet += Get-CrawlerRevisionFromDefinition `
            -Definition $current.Definition `
            -StateName $baseline.StateName
    }

    $FinalRevisionSet = @(
        $FinalRevisionSet |
        Sort-Object -Unique
    )

    if (
        $FinalRevisionSet.Count -ne 1 -or
        [int]$FinalRevisionSet[0] -ne $CandidateRevision
    ) {
        throw "FINAL_ACTIVATION_REVISION_SET_INVALID=$($FinalRevisionSet -join ',')"
    }

    Write-Host ""
    Write-Host "=== COPY RESULT ==="
    Write-Host "CRAWLER_ECS_RELEASE=SUCCESS"
    Write-Host "SOURCE_SHA=$SourceSha"
    Write-Host "IMAGE_TAG=$ResolvedImageTag"
    Write-Host "IMAGE_DIGEST=$Digest"
    Write-Host "BASELINE_REVISION=$BaselineRevision"
    Write-Host "CANDIDATE_REVISION=$CandidateRevision"
    Write-Host "CANDIDATE_EXIT_CODE=$($finalContainer.exitCode)"
    Write-Host "CANDIDATE_BUSINESS_EXECUTION=NO"
    Write-Host "STALE_PROMOTION_GUARD=PASS"
    Write-Host "ACTIVATION_SCOPE_COUNT=$($Baselines.Count)"
    Write-Host "PROMOTED_COUNT=$($Updated.Count)"
    Write-Host "FINAL_REVISION_SET=$($FinalRevisionSet -join ',')"
    Write-Host "ROLLBACK_REQUIRED=NO"
    Write-Host "=== COPY END ==="

    exit 0
}
catch {
    $PrimaryError = $_.Exception.Message

    # ------------------------------------------------------------
    # Roll back only State Machines actually updated by this run.
    # Candidate TD registration itself is not an operating activation.
    # ------------------------------------------------------------
    if ($Updated.Count -gt 0) {
        foreach ($baseline in @($Updated) | Select-Object -Reverse) {
            try {
                $rollbackPath = Join-Path `
                    $ArtifactRoot `
                    "$(($baseline.Name -replace '[^A-Za-z0-9._-]', '_'))-rollback.json"

                [System.IO.File]::WriteAllText(
                    $rollbackPath,
                    $baseline.Definition,
                    $Utf8NoBom
                )

                & aws stepfunctions update-state-machine `
                    --region $Region `
                    --state-machine-arn $baseline.Arn `
                    --definition "file://$rollbackPath" `
                    *> $null

                if ($LASTEXITCODE -ne 0) {
                    throw "UPDATE_FAILED"
                }

                $check = Get-StateMachineDefinition -Arn $baseline.Arn

                $revision = Get-CrawlerRevisionFromDefinition `
                    -Definition $check.Definition `
                    -StateName $baseline.StateName

                if ($revision -ne $baseline.Revision) {
                    throw "REVISION_VERIFY_FAILED"
                }
            }
            catch {
                $RollbackErrors.Add(
                    "$($baseline.Name):$($_.Exception.Message)"
                )
            }
        }
    }

    Write-Host ""
    Write-Host "=== COPY RESULT ==="
    Write-Host "CRAWLER_ECS_RELEASE=FAILED"
    Write-Host "ERROR=$PrimaryError"
    Write-Host "UPDATED_BEFORE_FAILURE=$($Updated.Count)"

    if ($RollbackErrors.Count -eq 0) {
        Write-Host "ROLLBACK_STATUS=SUCCESS_OR_NOT_REQUIRED"
    }
    else {
        Write-Host "ROLLBACK_STATUS=FAILED"
        Write-Host "ROLLBACK_ERROR_COUNT=$($RollbackErrors.Count)"

        foreach ($rollbackError in $RollbackErrors) {
            Write-Host "ROLLBACK_ERROR=$rollbackError"
        }
    }

    Write-Host "=== COPY END ==="

    exit 1
}