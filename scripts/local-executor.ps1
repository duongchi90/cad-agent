param (
    [string]$ArtifactsDir = "artifacts"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $ArtifactsDir)) {
    New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null
}

$repoPath = $PSScriptRoot | Split-Path -Parent
Set-Location $repoPath

Write-Host "LOCAL_MACHINE"
Write-Host "-----------------------"
Write-Host "Repo:       $repoPath"

# Git Info
$branch = git branch --show-current
Write-Host "Branch:     $branch"

$head = git rev-parse --short HEAD
Write-Host "HEAD:       $head"

$status = git status --porcelain
if ($status) {
    Write-Host "Dirty:      YES"
} else {
    Write-Host "Dirty:      NO"
}

Write-Host ""
Write-Host "Modified/Untracked:"
if ($status) {
    $status | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  (none)"
}

# AutoCAD Info
Write-Host ""
Write-Host "AutoCAD:"
$acadProcess = Get-Process -Name acad -ErrorAction SilentlyContinue
if ($acadProcess) {
    Write-Host "  Process:   RUNNING"
    Write-Host "  PID:       $($acadProcess.Id)"
} else {
    Write-Host "  Process:   STOPPED"
}

# Run tests and collect logs
Write-Host ""
Write-Host "Executing authoritative commands..."
Write-Host "Python: py -3.11"
$python311 = py -3.11 -c "import sys; print(sys.executable)"

Write-Host "Running: .\scripts\bootstrap.ps1 -PythonExe $python311"
$bootstrapOutput = & .\scripts\bootstrap.ps1 -PythonExe $python311 2>&1
$bootstrapExit = $LASTEXITCODE

Write-Host "Running: .\scripts\verify.ps1"
$verifyOutput = & .\scripts\verify.ps1 2>&1
$verifyExit = $LASTEXITCODE

Write-Host ""
Write-Host "Build/Verify Result:"
if ($bootstrapExit -eq 0 -and $verifyExit -eq 0) {
    Write-Host "  PASS"
} else {
    Write-Host "  FAIL"
}

# Save output to artifacts
$bootstrapOutput | Out-File -FilePath (Join-Path $ArtifactsDir "bootstrap-output.log")
$verifyOutput | Out-File -FilePath (Join-Path $ArtifactsDir "verify-output.log")
git diff > (Join-Path $ArtifactsDir "local-diff.patch")
git status > (Join-Path $ArtifactsDir "git-status.txt")

Write-Host ""
Write-Host "Artifacts generated in '$ArtifactsDir' folder."
