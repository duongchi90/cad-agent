# AutoCAD .NET close live follow-up

- Date: 2026-08-01
- Candidate commit: `4053c2a` (T20 one-shot `Application.Idle` close scheduler)
- Branch: `integration/autocad-dotnet-option-a`
- Host: AutoCAD Mechanical 2027 on Windows
- Scope: disposable DXF only; no production drawing mutation

## Result

The previous candidate was not approved for merge because its close
postcondition failed. T20 then added a one-shot managed `Application.Idle`
callback and passed an independent live smoke:

- health succeeded for the disposable DXF;
- read-only review succeeded for LINE handle `2F`;
- `close_disposable` returned `closed_without_saving=true`;
- after 8 seconds, AutoCAD Mechanical 2027 was back on `[Start]` and the
  target DXF was absent from the active document set;
- the DXF remained on disk, with no production drawing involved.

The smoke used a new isolated AutoCAD process and the repository's Win32
`CADAGENT_DISPATCH` trigger for all managed IPC operations. COM was used only by
the external harness to open the disposable DXF and inspect the postcondition;
the plugin contains no COM/ActiveX reference or call.

The T19 experiment marked `CADAGENT_DISPATCH` with `CommandFlags.Session`.
Its live run failed while waiting for AutoCAD to release the temporary DXF,
and the session remained on `dotnet_live.dxf`; the commit was reverted as
`debffd3`. T20 replaces that experiment with `Application.Idle` and is the
first candidate to pass the independent active-document postcondition.

## Automated marker

The repository's full opt-in AutoCAD marker was attempted with the legacy LISP
dispatcher and reported `8 failed, 5 passed, 423 deselected`. The legacy close
path reports `Automation Error. Drawing is busy`; this is recorded separately
from the focused .NET test and is not interpreted as a .NET close PASS.

## Verification

- C# Release x64 tests: `50 passed, 0 failed, 0 skipped`.
- T20 C# Release x64 tests: `51 passed, 0 failed, 0 skipped`.
- T20 Release x64 build: `0 errors`, 3 existing Autodesk reference-conflict
  warnings.
- Direct managed .NET live smoke: **PASS** (health, review, close, and
  independent active-document postcondition).
- Repository opt-in live module: the LISP bootstrap attempt timed out and is
  not used as evidence for the managed close result.
- Main branch: unchanged; no merge or GitHub push performed.
