[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Action,
    [string]$ResumeState
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Solution = Join-Path $RepoRoot 'autocad_plugin/CadAgent.AutoCAD2027.sln'
$DllPath = Join-Path $RepoRoot 'autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll'
$DispatcherPath = Join-Path $RepoRoot 'mcp_integration_lib/mcp_dispatch.lsp'
$ResumeTemplatePath = Join-Path $RepoRoot 'docs/templates/luna-resume-state.json'

function Stop-Fail {
    param([string]$Code, [string]$Detail)

    [Console]::Error.WriteLine(('ERROR={0}; {1}' -f $Code, $Detail))
    exit 2
}

function Invoke-GitText {
    param([string[]]$GitArguments)

    $output = & git -C $RepoRoot @GitArguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Stop-Fail 'GIT_COMMAND_FAILED' ('git {0}: {1}' -f ($GitArguments -join ' '), ($output -join ' '))
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Get-RepositorySnapshot {
    $branch = Invoke-GitText @('branch', '--show-current')
    $head = Invoke-GitText @('rev-parse', 'HEAD')
    $tree = Invoke-GitText @('rev-parse', 'HEAD^{tree}')
    $status = Invoke-GitText @('status', '--porcelain', '--untracked-files=all')
    return [pscustomobject]@{
        Branch = $branch
        Head = $head
        Tree = $tree
        IsDirty = -not [string]::IsNullOrWhiteSpace($status)
    }
}

function Get-FreshRemoteMain {
    $output = & git -C $RepoRoot ls-remote --exit-code origin refs/heads/main 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        return [pscustomobject]@{ Sha = ''; Error = (($output | ForEach-Object { [string]$_ }) -join ' ').Trim() }
    }

    $match = [regex]::Match((($output | ForEach-Object { [string]$_ }) -join "`n"), '(?m)^([0-9a-f]{40})\s+refs/heads/main\s*$')
    if (-not $match.Success) {
        return [pscustomobject]@{ Sha = ''; Error = 'origin did not return refs/heads/main' }
    }
    return [pscustomobject]@{ Sha = $match.Groups[1].Value; Error = '' }
}

function Write-StartReport {
    $snapshot = Get-RepositorySnapshot
    $remoteUrl = Invoke-GitText @('remote', 'get-url', 'origin')
    $remoteMain = Get-FreshRemoteMain

    Write-Output ('REPO_ROOT={0}' -f $RepoRoot)
    Write-Output ('REPOSITORY={0}' -f $remoteUrl)
    Write-Output ('BRANCH={0}' -f $snapshot.Branch)
    Write-Output ('LOCAL_HEAD={0}' -f $snapshot.Head)
    Write-Output ('LOCAL_TREE={0}' -f $snapshot.Tree)
    Write-Output ('WORKTREE={0}' -f $(if ($snapshot.IsDirty) { 'DIRTY' } else { 'CLEAN' }))
    Write-Output 'REMOTE_MAIN_SOURCE=git ls-remote origin refs/heads/main'
    if ($remoteMain.Sha) {
        Write-Output ('REMOTE_MAIN={0}' -f $remoteMain.Sha)
    }
    else {
        Write-Output ('REMOTE_MAIN=UNAVAILABLE; BLOCKER={0}' -f $remoteMain.Error)
    }
    Write-Output 'NEXT=Fresh-read the active GitHub issue, PR, CI, and required verdicts before a material boundary.'
}

function Test-ToolVersion {
    param(
        [string]$Name,
        [string[]]$VersionArguments,
        [string]$RequiredPattern,
        [string]$FallbackPath
    )

    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $executable = if ($command) {
        $command.Source
    }
    elseif ($FallbackPath -and (Test-Path -LiteralPath $FallbackPath -PathType Leaf)) {
        $FallbackPath
    }
    else {
        Write-Output ('BLOCKER={0} not found' -f $Name)
        return
    }

    $output = & $executable @VersionArguments 2>&1
    $exitCode = $LASTEXITCODE
    $version = (($output | ForEach-Object { [string]$_ }) -join ' ').Trim()
    if ($exitCode -ne 0 -or ($RequiredPattern -and $version -notmatch $RequiredPattern)) {
        Write-Output ('BLOCKER={0} version unavailable or unsupported: {1}' -f $Name, $version)
        return
    }
    Write-Output ('{0}={1}' -f $Name, $version)
}

function Write-DoctorReport {
    Write-Output ('POWERSHELL={0}' -f $PSVersionTable.PSVersion)
    Write-Output ('OS={0}' -f $env:OS)
    Test-ToolVersion 'py.exe' @('-3.11', '--version') '^Python 3\.11\.'
    Test-ToolVersion 'dotnet.exe' @('--version') '^10\.0\.'
    $programFiles = ${env:ProgramFiles}
    $tesseractPath = if ($programFiles) {
        Join-Path $programFiles 'Tesseract-OCR/tesseract.exe'
    }
    else {
        ''
    }
    Test-ToolVersion 'tesseract.exe' @('--version') '(?m)^tesseract v?5\.4\.0\.20240606' $tesseractPath

    $acadPath = if ($programFiles) {
        Join-Path $programFiles 'Autodesk/AutoCAD 2027/acad.exe'
    }
    else {
        ''
    }
    if ($acadPath -and (Test-Path -LiteralPath $acadPath -PathType Leaf)) {
        Write-Output 'AUTOCAD_MECHANICAL_2027=FOUND (not launched or inspected)'
    }
    else {
        Write-Output 'AUTOCAD_MECHANICAL_2027=NOT RUN; no installation path verified'
    }
    Write-Output 'AUTOCAD_ACTION=NOT RUN'
}

function Invoke-DotNet {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)

    $output = & $Executable @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $detail = (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
        Stop-Fail $FailureCode ('dotnet {0}; exit={1}; {2}' -f ($Arguments -join ' '), $exitCode, $detail)
    }
}

function Invoke-PluginBuild {
    param([switch]$PrintPacket)

    $before = Get-RepositorySnapshot
    if ($before.IsDirty) {
        Stop-Fail 'WORKTREE_DIRTY' 'Build refused before dotnet; commit or discard no files automatically.'
    }
    if (-not (Test-Path -LiteralPath $Solution -PathType Leaf)) {
        Stop-Fail 'SOLUTION_MISSING' $Solution
    }
    if (-not (Test-Path -LiteralPath $DispatcherPath -PathType Leaf)) {
        Stop-Fail 'DISPATCHER_MISSING' $DispatcherPath
    }

    $dotnet = Get-Command 'dotnet' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $dotnet) {
        Stop-Fail 'DOTNET_MISSING' 'Install the supported .NET SDK; AutoCAD was not launched.'
    }

    $cleanArguments = @('clean', $Solution, '-c', 'Release', '-p:Platform=x64')
    Invoke-DotNet $dotnet.Source $cleanArguments 'CLEAN_FAILED'
    if (Test-Path -LiteralPath $DllPath -PathType Leaf) {
        Stop-Fail 'CLEAN_OUTPUT_REMAINS' 'dotnet clean left the old DLL in place; refusing to trust or delete it.'
    }

    $buildArguments = @('build', $Solution, '-c', 'Release', '-p:Platform=x64')
    Invoke-DotNet $dotnet.Source $buildArguments 'BUILD_FAILED'
    if (-not (Test-Path -LiteralPath $DllPath -PathType Leaf)) {
        Stop-Fail 'BUILD_OUTPUT_MISSING' $DllPath
    }

    $after = Get-RepositorySnapshot
    if ($after.IsDirty) {
        Stop-Fail 'WORKTREE_DIRTY' 'The source tree changed during build; no load packet was produced.'
    }
    if ($after.Head -ne $before.Head -or $after.Tree -ne $before.Tree) {
        Stop-Fail 'SOURCE_HEAD_CHANGED' 'HEAD or tree changed during build; no load packet was produced.'
    }

    $hash = (Get-FileHash -LiteralPath $DllPath -Algorithm SHA256).Hash
    Write-Output ('SOURCE_HEAD={0}' -f $before.Head)
    Write-Output ('SOURCE_TREE={0}' -f $before.Tree)
    Write-Output ('DLL_PATH={0}' -f $DllPath)
    Write-Output ('DLL_SHA256={0}' -f $hash)
    if ($PrintPacket) {
        Write-Output 'MANUAL LOAD PACKET (operator-run only; these commands were not executed)'
        Write-Output ('NETLOAD {0}' -f $DllPath)
        Write-Output ('APPLOAD {0}' -f $DispatcherPath)
        Write-Output 'Load Once'
        Write-Output 'CADAGENT_HEALTH'
    }
}

function Test-ResumeState {
    if ([string]::IsNullOrWhiteSpace($ResumeState)) {
        Stop-Fail 'RESUME_INVALID' 'Supply -ResumeState with a local JSON file.'
    }
    if (-not (Test-Path -LiteralPath $ResumeTemplatePath -PathType Leaf)) {
        Stop-Fail 'RESUME_SCHEMA_MISSING' $ResumeTemplatePath
    }
    if (-not (Test-Path -LiteralPath $ResumeState -PathType Leaf)) {
        Stop-Fail 'RESUME_INVALID' 'Resume JSON file not found.'
    }

    try {
        $template = Get-Content -LiteralPath $ResumeTemplatePath -Raw | ConvertFrom-Json
        $state = Get-Content -LiteralPath $ResumeState -Raw | ConvertFrom-Json
    }
    catch {
        Stop-Fail 'RESUME_INVALID' ('Malformed JSON: {0}' -f $_.Exception.Message)
    }
    if ($null -eq $template -or $template -isnot [pscustomobject] -or $null -eq $state -or $state -isnot [pscustomobject]) {
        Stop-Fail 'RESUME_INVALID' 'Both template and resume state must be JSON objects.'
    }

    $requiredFields = @($template.PSObject.Properties | ForEach-Object { $_.Name })
    if ($requiredFields.Count -ne 12) {
        Stop-Fail 'RESUME_SCHEMA_UNRECONCILED' 'The tracked #305 template no longer contains the reviewed 12-field minimum.'
    }
    foreach ($field in $requiredFields) {
        $property = $state.PSObject.Properties[$field]
        if ($null -eq $property -or $property.Value -isnot [string]) {
            Stop-Fail 'RESUME_INVALID' ('Missing or non-text canonical field: {0}' -f $field)
        }
        $value = $property.Value.Trim()
        if ([string]::IsNullOrWhiteSpace($value) -or $value -match '^(?i:TODO|TBD|PLACEHOLDER|UNKNOWN|N/?A|REPLACE[-_ ]?ME|\.\.\.|<[^>]+>|\{\{.*\}\}|\?+)$') {
            Stop-Fail 'RESUME_INVALID' ('Blank or placeholder canonical field: {0}' -f $field)
        }
    }
    Write-Output ('RESUME_VALID=YES; CANONICAL_FIELDS={0}' -f $requiredFields.Count)
}

switch ($Action) {
    'Start' { Write-StartReport; break }
    'Doctor' { Write-DoctorReport; break }
    'BuildPlugin' { Invoke-PluginBuild; break }
    'Packet' { Invoke-PluginBuild -PrintPacket; break }
    'ValidateResume' { Test-ResumeState; break }
    default { Stop-Fail 'UNKNOWN_ACTION' $Action }
}
