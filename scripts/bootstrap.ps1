[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$lockFile = Join-Path $repoRoot "requirements\windows-py311.lock"
$venvDir = Join-Path $repoRoot ".venv-py311"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

$selectedVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $selectedVersion -ne "3.11") {
    throw "Python 3.11 is required; selected interpreter reported '$selectedVersion'. Pass -PythonExe with the full path to python.exe."
}

if (-not (Test-Path -LiteralPath $lockFile -PathType Leaf)) {
    throw "Dependency lock not found: $lockFile"
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $PythonExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create $venvDir with Python 3.11."
    }
}

$venvVersion = (& $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $venvVersion -ne "3.11") {
    throw "$venvDir exists but is not a Python 3.11 environment. Move it aside and rerun bootstrap."
}

& $venvPython (Join-Path $repoRoot "scripts\lock_contract.py") check $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Dependency lock contract failed."
}

& $venvPython -m pip install --disable-pip-version-check --require-hashes -r $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installing requirements/windows-py311.lock failed."
}

& $venvPython (Join-Path $repoRoot "scripts\check_environment.py") $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installed environment does not match the dependency lock."
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
    throw "Tesseract 5.4.0.20240606 is required. Set CAD_AGENT_TESSERACT_CMD or install it at C:\Program Files\Tesseract-OCR\tesseract.exe."
}

$tesseractVersion = (& $tesseractPath --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if ($tesseractVersion -ne "tesseract v5.4.0.20240606") {
    throw "Tesseract 5.4.0.20240606 is required; found '$tesseractVersion'."
}

Write-Host "Python: $venvPython ($venvVersion)"
Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"
Write-Host "Bootstrap complete."
