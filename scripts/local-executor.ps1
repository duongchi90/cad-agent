param (
    [string]$ArtifactsDir = "artifacts",
    [Parameter(Mandatory = $true)]
    [string]$MissionEnvelopePath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedBranch,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedSha
)

$ErrorActionPreference = "Stop"

$repoPath = $PSScriptRoot | Split-Path -Parent
Set-Location $repoPath

if (!(Test-Path -LiteralPath $ArtifactsDir)) {
    New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null
}
$artifactsFull = [System.IO.Path]::GetFullPath($ArtifactsDir)

$missionSha = "UNVALIDATED"
$controlStateSha = "UNVALIDATED"
$capability = "OFFLINE_VERIFY"
$currentBranch = "UNVALIDATED"
$currentHead = "UNVALIDATED"
$bootstrapExit = 1
$verifyExit = 1
$bootstrapOutput = @()
$verifyOutput = @()
$result = "FAIL"
$failureMessage = $null

function Test-DescendantPath {
    param (
        [Parameter(Mandatory = $true)]
        [string]$ChildPath,
        [Parameter(Mandatory = $true)]
        [string]$ParentPath
    )

    $resolvedChild = (Resolve-Path -LiteralPath $ChildPath).ProviderPath
    $resolvedParent = (Resolve-Path -LiteralPath $ParentPath).ProviderPath
    $parentFull = [System.IO.Path]::GetFullPath($resolvedParent).TrimEnd('\')
    $cursor = [System.IO.FileInfo]::new(
        [System.IO.Path]::GetFullPath($resolvedChild)
    ).Directory

    while ($null -ne $cursor) {
        if ([string]::Equals(
            $cursor.FullName.TrimEnd('\'),
            $parentFull,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            return $true
        }
        $cursor = $cursor.Parent
    }
    return $false
}

function Write-FallbackTerminal {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $terminal = [ordered]@{
        schema_version = "cad-local-mission-terminal-1.0"
        mission_sha256 = $missionSha
        control_state_sha256 = $controlStateSha
        capability = "OFFLINE_VERIFY"
        local_branch = $currentBranch
        local_head_sha = $currentHead
        result = $result
        bootstrap_exit_code = $bootstrapExit
        verify_exit_code = $verifyExit
        live_result = "NOT_RUN"
        merge_authority = $false
        publication_authority = $false
    }
    $json = $terminal | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText(
        $Path,
        $json,
        [System.Text.UTF8Encoding]::new($false)
    )
}

try {
    if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        throw "RUNNER_TEMP_MISSING"
    }
    if ([string]::IsNullOrWhiteSpace($ExpectedBranch)) {
        throw "EXPECTED_BRANCH_MISSING"
    }
    if ($ExpectedSha -cnotmatch '^[0-9a-f]{40}$') {
        throw "EXPECTED_SHA_INVALID"
    }
    if (!(Test-Path -LiteralPath $MissionEnvelopePath -PathType Leaf)) {
        throw "MISSION_ENVELOPE_NOT_FOUND"
    }
    if (!(Test-DescendantPath -ChildPath $MissionEnvelopePath -ParentPath $env:RUNNER_TEMP)) {
        throw "MISSION_PATH_OUTSIDE_RUNNER_TEMP"
    }

    $currentBranch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_BRANCH_READ_FAILED"
    }
    $currentHead = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_HEAD_READ_FAILED"
    }

    if ($currentBranch -cne $ExpectedBranch.Trim()) {
        throw "BRANCH_MISMATCH"
    }
    if ($currentHead -cne $ExpectedSha.Trim()) {
        throw "HEAD_SHA_MISMATCH"
    }

    $status = & git status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_STATUS_READ_FAILED"
    }
    if ($status) {
        throw "DIRTY_WORKTREE"
    }

    $validationCode = @'
import json
import sys
from pathlib import Path
from cad_agent.local_execution_envelope import validate_local_execution_envelope

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
validated = validate_local_execution_envelope(payload)
print(json.dumps(validated, sort_keys=True, separators=(",", ":")))
'@

    $validationOutput = & py -3.11 -c $validationCode $MissionEnvelopePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "MISSION_VALIDATION_FAILED: $($validationOutput -join ' ')"
    }
    $validated = ($validationOutput -join "`n") | ConvertFrom-Json

    $missionSha = [string]$validated.mission_sha256
    $controlStateSha = [string]$validated.control_state_sha256
    $capability = [string]$validated.capability

    if ($capability -cne "OFFLINE_VERIFY") {
        throw "CAPABILITY_MISMATCH"
    }
    if (
        $validated.mission.active_pr -ne "NONE" -and
        [string]$validated.mission.active_pr_head_sha -cne $currentHead
    ) {
        throw "MISSION_HEAD_SHA_MISMATCH"
    }

    Write-Host "LOCAL_MACHINE"
    Write-Host "-----------------------"
    Write-Host "Repo:       $repoPath"
    Write-Host "Branch:     $currentBranch"
    Write-Host "HEAD:       $currentHead"
    Write-Host "Mission:    $missionSha"
    Write-Host "Capability: $capability"
    Write-Host ""
    Write-Host "Executing authoritative OFFLINE_VERIFY commands..."

    $python311 = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($python311)) {
        throw "PYTHON311_RESOLUTION_FAILED"
    }

    Write-Host "Running: .\scripts\bootstrap.ps1 -PythonExe $python311"
    $bootstrapOutput = & .\scripts\bootstrap.ps1 -PythonExe $python311 2>&1
    $bootstrapExit = 0

    Write-Host "Running: .\scripts\verify.ps1"
    $verifyOutput = & .\scripts\verify.ps1 2>&1
    $verifyExit = 0
    $result = "PASS"
} catch {
    $failureMessage = $_.Exception.Message
    if ($bootstrapExit -ne 0) {
        $bootstrapOutput += $_
    } else {
        $verifyOutput += $_
    }
    Write-Host "Local mission failed closed: $failureMessage"
} finally {
    try {
        $bootstrapOutput | Out-File -FilePath (
            Join-Path $artifactsFull "bootstrap-output.log"
        )
        $verifyOutput | Out-File -FilePath (
            Join-Path $artifactsFull "verify-output.log"
        )
        git diff > (Join-Path $artifactsFull "local-diff.patch")
        git status > (Join-Path $artifactsFull "git-status.txt")
        if ($failureMessage) {
            $failureMessage | Out-File -FilePath (
                Join-Path $artifactsFull "failure.txt"
            )
        }

        $terminalPath = Join-Path $artifactsFull "mission-terminal.json"
        $terminalCode = @'
import json
import sys
from cad_agent.local_execution_envelope import build_local_mission_terminal

terminal = build_local_mission_terminal(
    mission_sha256=sys.argv[1],
    control_state_sha256=sys.argv[2],
    capability=sys.argv[3],
    local_branch=sys.argv[4],
    local_head_sha=sys.argv[5],
    result=sys.argv[6],
    bootstrap_exit_code=int(sys.argv[7]),
    verify_exit_code=int(sys.argv[8]),
)
print(json.dumps(terminal, sort_keys=True, separators=(",", ":")))
'@
        $terminalOutput = & py -3.11 -c $terminalCode `
            $missionSha `
            $controlStateSha `
            $capability `
            $currentBranch `
            $currentHead `
            $result `
            $bootstrapExit `
            $verifyExit 2>&1

        if ($LASTEXITCODE -eq 0) {
            [System.IO.File]::WriteAllText(
                $terminalPath,
                ($terminalOutput -join "`n"),
                [System.Text.UTF8Encoding]::new($false)
            )
        } else {
            Write-FallbackTerminal -Path $terminalPath
        }
        Write-Host "Artifacts generated in '$artifactsFull'."
    } catch {
        $emissionFailure = $_.Exception.Message
        Write-Host "Artifact/terminal emission failed: $emissionFailure"
        $failureMessage = "ARTIFACT_TERMINAL_EMISSION_FAILED: $emissionFailure"
        $result = "FAIL"
    }
}

if ($result -ne "PASS") {
    exit 1
}
