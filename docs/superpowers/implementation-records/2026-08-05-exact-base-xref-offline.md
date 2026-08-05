# S3A Exact-Base Xref Offline Contract

Status: Python contract complete; S3B/S3C live extraction and repair remain
locked and are not implemented.

## Identity and bounded scope

- Issue: #53, S3A.
- Exact implementation base SHA: `393f318317032096ec5e055ed1c928090f3b7e31`.
- Branch: `task/s3a-exact-base-xref-contract`.
- Completion head SHA: the exact single bounded commit is reported in the PR
  and final handoff; it cannot be embedded in the commit that creates this
  record without becoming self-referential.
- Changed files: exactly the four allowlisted files below.
  - `mcp_integration_lib/exact_base_xref.py`
  - `mcp_integration_lib/tests/test_exact_base_xref.py`
  - `mcp_integration_lib/tests/fixtures/exact-base-xref-inspection.json`
  - `docs/superpowers/implementation-records/2026-08-05-exact-base-xref-offline.md`

The implementation is pure Python and offline. It validates closed exact-base
inspection evidence and extraction plans with request/run identity, source
path/revision/hash, target drawing hash, vehicle/model observations, wheelbase,
track, chassis, cabin, and axle controls, Xref read-only state, component
handles/layers/blocks, `REUSED_FROM_BASE_CAD` provenance, eligibility, equal
DBMOD, and `changed: false`. Extraction plans bind the validated inspection,
select only inspected components, preserve source metadata, and allow only
local translation, rotation, and positive uniform scale. Approval is explicit:
plans are `PROPOSED` by default, while `APPROVED` requires a caller-supplied
reference. Unknown fields, unsafe paths, malformed hashes, mismatched
identity, ineligible inspections, duplicate/uninspected components,
non-uniform/global/reflected transforms, target handles, mutation, verdict,
repair, and publication authority fail closed.

## Reuse Declaration

Existing capability inspected: current source hashing/run identity,
manifest/checkpoint conventions, `mcp_integration_lib.dotnet_ipc`, Drawing
Setup safeguards, VS-T3 read-only evidence patterns, S2A closed contract
helpers, and the approved exact-base CAD policy.

Existing API reused: lowercase SHA-256, safe identifier/path/timestamp
conventions, closed dictionary validation, read-only `changed=false` and DBMOD
invariants, pytest, Ruff, architecture checker, and canonical verifier.

Adapter required: one pure-Python Xref inspection/extraction-plan contract
adjacent to the existing AutoCAD boundary; no new transport, dispatcher, CAD
database, or mutation executor.

New capability genuinely missing: a closed contract that proves exact-base
identity and eligibility, records inspected Xref components, and describes an
approved extraction plan with frozen source provenance before any AutoCAD
mutation is allowed.

Files allowed to change: the exact four files listed in this record and Issue
#53.

Files forbidden to duplicate: File IPC transport, C# dispatcher, AutoCAD Xref
implementation, CAD entity copier, DXF writer, manifest/checkpoint/revision
truth stores, component registry, repair executor, publisher, CLI,
dependencies, and `requirements/windows-py311.lock`.

Compatibility behavior: existing runtime, CLI, manifest, File IPC, C#, and
AutoCAD operations are unchanged. All paths are metadata only; actual Xref
attachment, extraction, candidate revision, private-data verification, and
AutoCAD live remain NOT RUN.

Migration and rollback path: revert the single bounded S3A commit; no runtime
or dependency state changes.

## Verification evidence

The focused TDD RED run failed at collection because the new module did not
exist. After implementation, the focused GREEN run was:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib/tests/test_exact_base_xref.py -q -p no:cacheprovider
```

Observed result: exit `0`; `49 passed`.

Ruff:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check mcp_integration_lib/exact_base_xref.py mcp_integration_lib/tests/test_exact_base_xref.py
```

Observed result: exit `0`; all checks passed.

Architecture checker:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Observed result: exit `0`; `Architecture boundaries: PASS`.

Diff check:

```powershell
git diff --check
```

Observed result: exit `0` before staging; the staged four-file check is run
again before the single bounded commit.

Canonical verifier:

```powershell
.\scripts\verify.ps1 -PythonExe C:\Users\dkv\Downloads\cad-agent-merge\.superpowers\worktrees\s3a-exact-base-xref-contract\.venv-py311\Scripts\python.exe -SkipAutoCADDotNet
```

The verifier requires a clean tree, so this command runs on the single bounded
commit. Its exact exit code and test counts are recorded in the final handoff.
The AutoCAD .NET/live portion is explicitly NOT RUN.

## Gate states

- Python offline exact-base contract: **COMPLETE** (`49 passed`).
- File IPC integration: **NOT RUN / LOCKED** to S3B/S3C.
- C# implementation: **NOT RUN / LOCKED** to S3B/S3C.
- AutoCAD Mechanical live Xref attach/extraction: **NOT RUN / LOCKED** to
  S3B/S3C.
- Private real-drawing data: **NOT RUN**.
- S3B live File IPC extraction: **NOT RUN / LOCKED**.
- S3C live repair/publication: **NOT RUN / LOCKED**.
- Verdict, repair, mutation, and publication: **PROHIBITED / NOT IMPLEMENTED**.

No AutoCAD process, File IPC request, Xref attachment, entity copy, DWG
mutation, C# module, dependency, lock, truth store, component registry, or
publisher was added or invoked by S3A.
