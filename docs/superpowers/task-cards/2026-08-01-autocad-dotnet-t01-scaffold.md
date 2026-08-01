# Task Card T01 — C# Solution and SDK Boundary

**Role:** Coder  
**Model:** Luna Extra High (`gpt-5.6-luna`, reasoning `xhigh`)  
**Base:** `14fa9fe` (`docs: plan parallel AutoCAD plugin tasks`)  
**Branch:** `codex/autocad-dotnet-t01-scaffold`  
**Worktree:** `D:\cad-agent-master\cad-agent\.worktrees\autocad-dotnet-t01-scaffold`

## Objective

Create the compilable .NET 10 x64 solution boundary without implementing AutoCAD behavior.

## Allowed files

- `autocad_plugin/CadAgent.AutoCAD2027.sln`
- `autocad_plugin/CadAgent.AutoCAD2027/CadAgent.AutoCAD2027.csproj`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj`
- `autocad_plugin/Directory.Build.props.example`
- `.gitignore`

## Forbidden files

All existing Python, C#, schema, test, script, status, and architecture files outside the allowed list. Do not add Autodesk DLLs, ObjectARX files, Mechanical SDK files, VSIX files, or generated `bin/obj` output.

## Requirements

- Set `TargetFramework=net10.0-windows`, `Platforms=x64`, `PlatformTarget=x64`, `OutputType=Library`, nullable and implicit usings.
- Add only to `CadAgent.AutoCAD2027.Tests.csproj`: `Microsoft.NET.Test.Sdk` `18.6.0`, `xunit.v3` `3.2.2`, and the official VSTest adapter `xunit.runner.visualstudio` `3.1.5`, with test-runner assets private to the test project.
- Use local `AcadDir` and `ArxSdkDir` properties; prefer `$(ArxSdkDir)\inc` and fall back to `$(AcadDir)`.
- Reference only `AcCoreMgd`, `AcDbMgd`, and `AcMgd`, each with `<Private>false</Private>`.
- Commit only `Directory.Build.props.example`; make local `Directory.Build.props` ignored.

## Required verification

```powershell
dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64
```

Inspect the output directory and prove the three Autodesk DLLs are not copied. Review the diff and commit with a scoped message.

## Completion report

Return commit SHA, changed files, restore/build output, output-DLL check, and any local SDK prerequisite that remained unavailable. Do not merge.
