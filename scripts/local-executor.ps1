[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [ValidateSet("STATE_CHECK", "VERIFY", "SYNC_MAIN_STATE_CHECK")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$RepoPath,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBranch,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedSha,

    [string]$ArtifactsDir = "artifacts"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RepoPath -PathType Container)) {
    throw "LOCAL_REPO_NOT_FOUND"
}

$resolvedRepo = (Resolve-Path -LiteralPath $RepoPath).Path
Set-Location $resolvedRepo

$currentBranch = (& git branch --show-current | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($currentBranch)) {
    throw "LOCAL_BRANCH_UNRESOLVED"
}
if ($currentBranch -cne $ExpectedBranch) {
    throw "LOCAL_BRANCH_MISMATCH"
}

$currentSha = (& git rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $currentSha -notmatch '^[0-9a-f]{40}$') {
    throw "LOCAL_SHA_UNRESOLVED"
}
if ($Action -ne "SYNC_MAIN_STATE_CHECK" -and $currentSha -cne $ExpectedSha) {
    throw "LOCAL_SHA_MISMATCH"
}

if (-not (Test-Path -LiteralPath $ArtifactsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null
}
$resolvedArtifacts = (Resolve-Path -LiteralPath $ArtifactsDir).Path

$status = @(& git -c core.quotepath=false status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "LOCAL_GIT_STATUS_FAILED"
}

if ($Action -eq "SYNC_MAIN_STATE_CHECK") {
    if ($ExpectedBranch -cne "main") {
        throw "SYNC_MAIN_BRANCH_REQUIRED"
    }
    if ($status.Count -gt 0) {
        throw "LOCAL_WORKTREE_DIRTY"
    }

    $originUrl = (& git config --get remote.origin.url | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($originUrl)) {
        throw "ORIGIN_URL_UNRESOLVED"
    }
    if (
        $originUrl -cne "https://github.com/duongchi90/cad-agent" -and
        $originUrl -cne "https://github.com/duongchi90/cad-agent.git"
    ) {
        throw "ORIGIN_URL_MISMATCH"
    }

    $fetchOutput = @(& git fetch --no-tags origin main 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "FETCH_FAILED"
    }

    $remoteMainSha = (& git rev-parse refs/remotes/origin/main | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $remoteMainSha -cne $ExpectedSha) {
        throw "REMOTE_MAIN_SHA_MISMATCH"
    }

    & git merge-base --is-ancestor $currentSha $ExpectedSha 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "LOCAL_HEAD_NOT_ANCESTOR_OF_REMOTE_MAIN"
    }

    if ($currentSha -cne $ExpectedSha) {
        $mergeOutput = @(& git merge --ff-only origin/main 2>&1)
        if ($LASTEXITCODE -ne 0) {
            throw "FAST_FORWARD_FAILED"
        }
        $currentSha = (& git rev-parse HEAD | Out-String).Trim()
    }

    if ($currentSha -cne $ExpectedSha) {
        throw "FINAL_HEAD_MISMATCH"
    }

    $status = @(& git -c core.quotepath=false status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw "LOCAL_GIT_STATUS_FAILED"
    }
    if ($status.Count -gt 0) {
        throw "LOCAL_WORKTREE_DIRTY"
    }
}

$acadProcesses = @(Get-Process -Name acad -ErrorAction SilentlyContinue)
$stateLines = @(
    "LOCAL_EXECUTOR_STATE_V1",
    "ACTION=$Action",
    "REPO=$resolvedRepo",
    "BRANCH=$currentBranch",
    "HEAD=$currentSha",
    "DIRTY=$([bool]($status.Count -gt 0))",
    "AUTOCAD_PROCESS_COUNT=$($acadProcesses.Count)"
)
if ($acadProcesses.Count -gt 0) {
    $stateLines += "AUTOCAD_PIDS=$((@($acadProcesses | ForEach-Object { $_.Id }) -join ','))"
}
if ($status.Count -gt 0) {
    $stateLines += "GIT_STATUS_BEGIN"
    $stateLines += $status
    $stateLines += "GIT_STATUS_END"
}
$statePath = Join-Path $resolvedArtifacts "local-state.txt"
$stateLines | Out-File -LiteralPath $statePath -Encoding utf8
$stateLines | ForEach-Object { Write-Host $_ }

if ($Action -eq "STATE_CHECK" -or $Action -eq "SYNC_MAIN_STATE_CHECK") {
    Write-Host "LOCAL_EXECUTOR_RESULT=PASS"
    exit 0
}

$bootstrapOutput = @()
$verifyOutput = @()
$bootstrapExit = 1
$verifyExit = 1

try {
    $python311 = (& py -3.11 -c "import sys; print(sys.executable)" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($python311)) {
        throw "PYTHON_311_UNAVAILABLE"
    }

    Write-Host "Running: .\scripts\bootstrap.ps1 -PythonExe $python311"
    $bootstrapOutput = @(& .\scripts\bootstrap.ps1 -PythonExe $python311 2>&1)
    $bootstrapExit = $LASTEXITCODE
    if ($bootstrapExit -ne 0) {
        throw "BOOTSTRAP_FAILED"
    }

    Write-Host "Running: .\scripts\verify.ps1"
    $verifyOutput = @(& .\scripts\verify.ps1 2>&1)
    $verifyExit = $LASTEXITCODE
    if ($verifyExit -ne 0) {
        throw "VERIFY_FAILED"
    }
} catch {
    if ($verifyOutput.Count -eq 0) {
        $verifyOutput = @($_ | Out-String)
    } else {
        $verifyOutput += ($_ | Out-String)
    }
} finally {
    $bootstrapOutput | Out-File -LiteralPath (Join-Path $resolvedArtifacts "bootstrap-output.log") -Encoding utf8
    $verifyOutput | Out-File -LiteralPath (Join-Path $resolvedArtifacts "verify-output.log") -Encoding utf8
    (& git diff) | Out-File -LiteralPath (Join-Path $resolvedArtifacts "local-diff.patch") -Encoding utf8
    (& git -c core.quotepath=false status --porcelain=v1 --untracked-files=all) |
        Out-File -LiteralPath (Join-Path $resolvedArtifacts "git-status.txt") -Encoding utf8
}

if ($bootstrapExit -ne 0 -or $verifyExit -ne 0) {
    Write-Host "LOCAL_EXECUTOR_RESULT=FAIL"
    exit 1
}

Write-Host "LOCAL_EXECUTOR_RESULT=PASS"
exit 0
