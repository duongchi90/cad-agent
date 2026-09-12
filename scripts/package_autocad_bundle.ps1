[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [Parameter(Mandatory = $true)]
    [string]$SourceDll,
    [Parameter(Mandatory = $true)]
    [string]$OutputBundle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ExistingFile {
    param([string]$Path, [string]$Name)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "$Name must be a non-empty file path."
    }
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Name does not exist as a file: $resolved"
    }
    return (Resolve-Path -LiteralPath $resolved).Path
}

function Get-Sha256 {
    param([string]$Path)

    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $sha256.ComputeHash([IO.File]::ReadAllBytes($Path))
        )).Replace("-", "")
    } finally {
        $sha256.Dispose()
    }
}

$manifest = Resolve-ExistingFile -Path $ManifestPath -Name "ManifestPath"
$source = Resolve-ExistingFile -Path $SourceDll -Name "SourceDll"
if ([IO.Path]::GetExtension($source) -ine ".dll") {
    throw "SourceDll must have a .dll extension: $source"
}

if ([string]::IsNullOrWhiteSpace($OutputBundle)) {
    throw "OutputBundle must be a non-empty directory path."
}
$output = [IO.Path]::GetFullPath($OutputBundle)
if (Test-Path -LiteralPath $output) {
    throw "OutputBundle already exists; refusing to overwrite a conflicting path: $output"
}
$outputParent = Split-Path -Parent $output
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "OutputBundle parent must already exist: $outputParent"
}

$manifestRoot = [IO.Path]::GetFullPath((Split-Path -Parent $manifest))
$manifestBoundary = $manifestRoot
if (-not $manifestBoundary.EndsWith([IO.Path]::DirectorySeparatorChar)) {
    $manifestBoundary += [IO.Path]::DirectorySeparatorChar
}
if ($output.Equals($manifestRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $output.StartsWith($manifestBoundary, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputBundle must be disposable and outside the repository bundle source: $output"
}

[xml]$xml = Get-Content -LiteralPath $manifest -Raw
$entries = @($xml.ApplicationPackage.Components.ComponentEntry)
if ($entries.Count -ne 1) {
    throw "PackageContents.xml must contain exactly one ComponentEntry."
}
$moduleName = [string]$entries[0].ModuleName
if ([string]::IsNullOrWhiteSpace($moduleName) -or [IO.Path]::IsPathRooted($moduleName)) {
    throw "PackageContents.xml ModuleName must be a non-empty relative path."
}

$relativeModule = $moduleName.Replace('/', [IO.Path]::DirectorySeparatorChar)
$target = [IO.Path]::GetFullPath((Join-Path $output $relativeModule))
$outputBoundary = $output
if (-not $outputBoundary.EndsWith([IO.Path]::DirectorySeparatorChar)) {
    $outputBoundary += [IO.Path]::DirectorySeparatorChar
}
if (-not $target.StartsWith($outputBoundary, [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetExtension($target) -ine ".dll") {
    throw "PackageContents.xml ModuleName escapes OutputBundle or is not a DLL: $moduleName"
}

New-Item -ItemType Directory -Path $output | Out-Null
Copy-Item -LiteralPath $manifest -Destination (Join-Path $output "PackageContents.xml")
New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $target

$sourceHash = Get-Sha256 -Path $source
$targetHash = Get-Sha256 -Path $target
if ($sourceHash -ne $targetHash) {
    throw "Staged DLL hash does not match SourceDll."
}

Write-Output $output
