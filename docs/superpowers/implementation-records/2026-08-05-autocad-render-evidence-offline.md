# S2A AutoCAD-Native Render Evidence Offline Contract

Status: Python contract complete; S2B live integration remains outside this
issue and is not implemented.

## Identity and bounded scope

- Issue: #49, S2A.
- Exact base SHA: `5d6074a2969894367df2e5d70b7a362c99e43c61`.
- Verified candidate SHA: `c5077322e61522339f40d7466aacb29e3c7cb48f`.
- Final head SHA: emitted by the final bounded commit and recorded in the PR
  provenance; a commit cannot contain its own object ID without becoming
  self-referential.
- Changed files: exactly the four allowlisted files below.
  - `mcp_integration_lib/autocad_render_evidence.py`
  - `mcp_integration_lib/tests/test_autocad_render_evidence.py`
  - `mcp_integration_lib/tests/fixtures/autocad-render-evidence.json`
  - `docs/superpowers/implementation-records/2026-08-05-autocad-render-evidence-offline.md`

The implementation is pure Python and offline. It validates closed request and
result objects, lowercase SHA-256 identities, safe relative artifact paths,
explicit UTC timestamps, layout and mutation identities, deterministic render
options, PNG dimensions, PDF page counts, `changed: false`, equal DBMOD values,
and warnings. Unknown fields, unsafe values, unsupported kinds/renderers, and
verdict/approval/repair/publication fields fail closed.

## Reuse Declaration

Existing capability inspected: `mcp_integration_lib.dotnet_ipc`, VS-T3 visual
evidence export, visual run manifest and dimension-register safeguards, existing
File IPC result conventions, and the approved read-only AutoCAD evidence rule.

Existing API reused: existing hash, path, timestamp, DBMOD, mutation, pytest,
Ruff, architecture-checker, and canonical-verifier conventions.

Adapter required: one adjacent pure-Python request/result validator; no new
transport, dispatcher, renderer, or verdict owner.

New capability genuinely missing: a closed contract binding native render/plot
artifact metadata to drawing, mutation, manifest, run, layout, and request
identities.

Files allowed to change: the exact four files listed in this record.

Files forbidden to duplicate: `mcp_integration_lib/dotnet_ipc.py`, C# plugin or
dispatcher code, AutoCAD transport, VS-T3 exporter, visual verdict, repair
executor, CAD writer, manifest/checkpoint/revision stores, publisher, CLI,
dependencies, and `requirements/windows-py311.lock`.

Compatibility behavior: existing operations are unchanged; this module makes
no AutoCAD process, HWND, File IPC request, plot command, model-space mutation,
visual verdict, approval, or publication claim.

Migration and rollback path: revert the one bounded S2A commit; no runtime
operation, schema, dependency, or lock state changes.

## Verification evidence

Focused command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_autocad_render_evidence.py -q -p no:cacheprovider
```

Observed result: exit `0`; `58 passed`.

Ruff command:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/autocad_render_evidence.py mcp_integration_lib/tests/test_autocad_render_evidence.py
```

Observed result: exit `0`; all checks passed.

Architecture command:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Observed result: exit `0`; `Architecture boundaries: PASS`.

Diff command:

```powershell
git diff --check
```

Observed result: exit `0`.

Canonical verifier command on the clean verified candidate:

```powershell
.\scripts\verify.ps1 -PythonExe C:\Users\dkv\Downloads\cad-agent-merge\.superpowers\worktrees\s2a-autocad-render-evidence-contract\.venv-py311\Scripts\python.exe -SkipAutoCADDotNet
```

Observed result: exit `0` on `c5077322e61522339f40d7466aacb29e3c7cb48f`.
Lock and environment contracts passed with 40 pinned/locked distributions;
dotnet IPC JUnit was `tests=38 failures=0 errors=0 skipped=0`; offline JUnit
was `tests=866 failures=0 errors=0 skipped=0`; the real-data unavailable-state
probe was `tests=2 skipped=2`; and the AutoCAD Mechanical unavailable-state
probe was `tests=9 skipped=9`. Ruff and diff checks passed. The AutoCAD .NET
gate was `NOT RUN` because `-SkipAutoCADDotNet` was explicit; the AutoCAD live
marker was `NOT RUN` because no qualifying File IPC session was configured.

The final record-only commit changes documentation evidence only. The focused
suite, Ruff, architecture checker, and `git diff --check` are rerun after it;
the full canonical verifier result remains bound to the verified candidate
above and is not relabeled as a run on the record-only head.

## Gate states

- Python offline contract: **COMPLETE** (`58 passed`).
- File IPC integration: **NOT RUN**.
- C# implementation: **NOT RUN**.
- AutoCAD Mechanical live gate: **NOT RUN**.
- Private real-drawing gate: **NOT RUN**.
- Visual verdict: **NOT IMPLEMENTED**.
- Repair and publication: **NOT IMPLEMENTED**.

Unavailable-state skips, if collected by the canonical verifier, are not
acceptance evidence and will not be reported as passes. S2B is not started by
this task.
