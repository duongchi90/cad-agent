# AutoCAD .NET close live follow-up

- Date: 2026-08-01
- Candidate commit: `7823543`
- Branch: `integration/autocad-dotnet-option-a`
- Host: AutoCAD Mechanical 2027 on Windows
- Scope: disposable DXF only; no production drawing mutation

## Result

The candidate is **not approved for merge**. The focused pytest returned
`1 passed, 3 deselected`, but that result only proves the IPC result was
returned. Independent verification after the request found:

- open documents still included
  `C:\temp\cadagent_dotnet_live_20260801\dotnet_live.dxf`;
- AutoCAD still showed the `dotnet_live.dxf` tab;
- the DXF file still existed on disk.

The same failure was reproduced across the deferred `SendStringToExecute`
variants and the managed `ExecuteInApplicationContext` callback. Direct
synchronous `CloseAndDiscard` previously raised `Drawing is busy`.

## Automated marker

The repository's full opt-in AutoCAD marker was attempted with the legacy LISP
dispatcher and reported `8 failed, 5 passed, 423 deselected`. The legacy close
path reports `Automation Error. Drawing is busy`; this is recorded separately
from the focused .NET test and is not interpreted as a .NET close PASS.

## Verification

- C# Release x64 tests: `50 passed, 0 failed, 0 skipped`.
- Release x64 build: `0 errors`, 3 existing Autodesk reference-conflict
  warnings.
- Focused .NET live test: `1 passed, 3 deselected`.
- Independent active-document postcondition: **FAIL**.
- Main branch: unchanged; no merge or GitHub push performed.
