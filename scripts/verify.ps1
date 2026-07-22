[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$candidateHead = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $candidateHead -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve an exact Git commit SHA for verification."
}
$initialStatus = @(& git -C $repoRoot -c core.quotepath=false `
    status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "git status failed while checking verification provenance."
}
if ($initialStatus.Count -ne 0) {
    throw "Verification requires a clean tree before test gates. Commit or stash these paths:`n$($initialStatus -join "`n")"
}
Write-Host "Commit SHA: $candidateHead"
Write-Host "Repository: clean at verification start."

if (-not $PythonExe) {
    $PythonExe = Join-Path $repoRoot ".venv-py311\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python environment not found: $PythonExe. Run scripts/bootstrap.ps1 first."
}

$pythonVersion = (& $PythonExe -c "import sys; print(sys.version.split()[0])" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch '^3\.11\.\d+$') {
    throw "Verification requires Python 3.11; found '$pythonVersion'."
}

$lockFile = Join-Path $repoRoot "requirements\windows-py311.lock"
& $PythonExe (Join-Path $repoRoot "scripts\lock_contract.py") check $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Dependency lock contract failed."
}
& $PythonExe (Join-Path $repoRoot "scripts\check_environment.py") $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installed environment does not match the dependency lock."
}

$dependencyProbe = "from importlib.metadata import version; names = ['numpy', 'opencv-python', 'pytesseract', 'Pillow', 'pypdf', 'PyMuPDF', 'ezdxf', 'anthropic', 'python-solvespace', 'pytest', 'ruff']; print('; '.join(f'{name}={version(name)}' for name in names))"
$dependencyVersions = (& $PythonExe -c $dependencyProbe | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Reading locked dependency versions failed."
}

$tesseractPath = $env:CAD_AGENT_TESSERACT_CMD
if (-not $tesseractPath) {
    $tesseractCommand = Get-Command "tesseract.exe" -ErrorAction SilentlyContinue
    if ($tesseractCommand) {
        $tesseractPath = $tesseractCommand.Source
    } else {
        $tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    }
}
if (-not (Test-Path -LiteralPath $tesseractPath -PathType Leaf)) {
    throw "Tesseract executable not found: $tesseractPath"
}
$tesseractVersion = (& $tesseractPath --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if ($tesseractVersion -ne "tesseract v5.4.0.20240606") {
    throw "Verification requires Tesseract 5.4.0.20240606; found '$tesseractVersion'."
}

function Get-RepositorySnapshot {
    $paths = @(& git -C $repoRoot -c core.quotepath=false `
        ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed while building the side-effect snapshot."
    }
    $entries = foreach ($relativePath in $paths) {
        $fullPath = Join-Path $repoRoot $relativePath
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $hash = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
            "$relativePath=$hash"
        }
    }
    return @($entries | Sort-Object)
}

function Get-JUnitTotals {
    param([string]$Path)
    [xml]$junit = Get-Content -LiteralPath $Path -Raw
    $suites = @($junit.testsuites.testsuite)
    return [pscustomobject]@{
        Tests = ($suites | ForEach-Object { [int]$_.tests } | Measure-Object -Sum).Sum
        Failures = ($suites | ForEach-Object { [int]$_.failures } | Measure-Object -Sum).Sum
        Errors = ($suites | ForEach-Object { [int]$_.errors } | Measure-Object -Sum).Sum
        Skipped = ($suites | ForEach-Object { [int]$_.skipped } | Measure-Object -Sum).Sum
    }
}

function Invoke-PytestGate {
    param(
        [string]$Name,
        [string]$MarkerExpression,
        [string]$JUnitPath,
        [ValidateSet("offline", "all-skipped")]
        [string]$ExpectedState
    )
    & $PythonExe -m pytest @testTargets -q -m $MarkerExpression -p no:cacheprovider `
        "--junitxml=$JUnitPath"
    if ($LASTEXITCODE -ne 0) {
        throw "$Name pytest gate failed with exit code $LASTEXITCODE."
    }
    $totals = Get-JUnitTotals -Path $JUnitPath
    if ($totals.Tests -le 0 -or $totals.Failures -ne 0 -or $totals.Errors -ne 0) {
        throw "$Name produced invalid JUnit totals: $($totals | Out-String)"
    }
    if ($ExpectedState -eq "offline" -and $totals.Skipped -ne 0) {
        throw "Offline gate contains $($totals.Skipped) unexpected skips."
    }
    if ($ExpectedState -eq "all-skipped" -and $totals.Skipped -ne $totals.Tests) {
        throw "$Name must report every collected test as skipped when prerequisites are absent."
    }
    Write-Host "$Name JUnit: tests=$($totals.Tests) failures=$($totals.Failures) errors=$($totals.Errors) skipped=$($totals.Skipped)"
}

$snapshotBefore = Get-RepositorySnapshot
$artifactDir = Join-Path $repoRoot ".artifacts\test-results"
$junitPath = Join-Path $artifactDir "junit.xml"
$realDataJunitPath = Join-Path $artifactDir "real-data-unavailable.xml"
$autocadJunitPath = Join-Path $artifactDir "autocad-lt-unavailable.xml"
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

$tesseractDir = Split-Path -Parent $tesseractPath
$originalPath = $env:PATH
$env:PATH = "$tesseractDir;$env:PATH"
$testTargets = @(
    "tests",
    "primitive_ir_lib/tests",
    "semantic_ir_lib/tests",
    "dxf_builder_lib/tests",
    "mcp_integration_lib/tests",
    "agent_lib/tests"
)

Push-Location $repoRoot
try {
    Invoke-PytestGate `
        -Name "offline" `
        -MarkerExpression "not real_data and not autocad_mechanical" `
        -JUnitPath $junitPath `
        -ExpectedState "offline"

    $specializedVariables = @(
        "CAD_AGENT_REAL_IMAGE",
        "CAD_AGENT_FILE_IPC",
        "CAD_AGENT_AUTOCAD_HWND",
        "CAD_AGENT_AUTOCAD_LISP_PATH"
    )
    $savedEnvironment = @{}
    foreach ($name in $specializedVariables) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($null -ne $value) {
            $savedEnvironment[$name] = $value
        }
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
    try {
        Invoke-PytestGate `
            -Name "real_data unavailable-state probe" `
            -MarkerExpression "real_data" `
            -JUnitPath $realDataJunitPath `
            -ExpectedState "all-skipped"
        Invoke-PytestGate `
            -Name "autocad_mechanical unavailable-state probe" `
            -MarkerExpression "autocad_mechanical" `
            -JUnitPath $autocadJunitPath `
            -ExpectedState "all-skipped"
    } finally {
        foreach ($name in $specializedVariables) {
            $value = if ($savedEnvironment.ContainsKey($name)) {
                $savedEnvironment[$name]
            } else {
                $null
            }
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }

    $lintTargets = @(
        "primitive_ir_lib",
        "semantic_ir_lib",
        "dxf_builder_lib",
        "mcp_integration_lib",
        "agent_lib",
        "tests",
        "scripts"
    )
    & $PythonExe -m ruff check @lintTargets
    if ($LASTEXITCODE -ne 0) {
        throw "Ruff failed with exit code $LASTEXITCODE."
    }

    & git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --check failed."
    }
    & git diff --cached --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --cached --check failed."
    }
} finally {
    Pop-Location
    $env:PATH = $originalPath
}

$snapshotAfter = Get-RepositorySnapshot
if (($snapshotBefore -join "`n") -ne ($snapshotAfter -join "`n")) {
    throw "Verification changed a tracked or non-ignored file. Inspect git status and content hashes."
}

Write-Host "Python: $pythonVersion"
Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"
Write-Host "Dependencies: $dependencyVersions"
Write-Host "Offline JUnit: $junitPath"
Write-Host "Unavailable-state JUnit: $realDataJunitPath; $autocadJunitPath"
Write-Host "Verification complete."
