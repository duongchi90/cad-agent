# S3B Exact-Base Xref Live Inspection and Gated Extraction

Status: the standalone inspection route and opt-in S3B live acceptance harness
are implemented. AutoCAD Mechanical live acceptance is **NOT RUN** on this
head because no qualifying session, File IPC trigger, approved fixture, and
server-owned S3B configuration were available. The implementation does not
claim S3B live acceptance.

## Identity and bounded scope

- Issue: #64, S3B implementation.
- Planning merge: `bea1020d186a51cca13daecf6d36482481fd9a03`.
- Exact implementation base: `1ba05ea6d768351fa7106109bcee244e60463527`.
- Implementation branch: `task/s3b-exact-base-xref`.
- Checkpoint PR: #65, kept as draft for final PO review.
- Fresh verification target head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
- Full implementation audit: the exact-base implementation diff contains
  exactly 27 paths, all allowlisted by Issue #64.
- Inspection follow-up audit: exactly these four paths:
  - `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
  - `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`
  - `mcp_integration_lib/tests/test_dotnet_ipc_live.py`
  - `docs/superpowers/implementation-records/2026-08-06-exact-base-xref-s3b.md`

The standalone inspection operation now calls the existing read-only drawing
gateway and serializes its fresh server-owned evidence. The live test calls
that inspection against the accepted DWG before opening the disposable
candidate, then calls the existing Task 5 extraction path. Extraction still
performs its own fresh preflight immediately before mutation. No second
transport, AutoCAD reader, source-fusion runtime, registry, revision store,
repair, verdict, or publication path is added.

## Reuse Declaration

Existing capability inspected: the existing `DotNetIPCClient` exact-base
inspection/extraction helpers, File IPC request/result store, Windows .NET
dispatch trigger, legacy AutoCAD File IPC trigger, S3A inspection/plan fixture
shape, disposable close guard, drawing hash helper, and read-only live-test
patterns.

Existing API reused: `exact_base_xref_inspection()`,
`exact_base_xref_extraction()`, their closed-contract and result validation,
`FileIPCLiveMCPClient`, `make_windows_dotnet_dispatch_trigger`,
`make_windows_dispatch_trigger`, `make_windows_lisp_trigger`, and the existing
`autocad_mechanical` marker.

Adapter required: one opt-in pytest/unittest harness that dispatches the
existing S3B inspection request against the accepted DWG, opens an operator-
provided disposable candidate, dispatches the existing S3B extraction request,
checks fresh live-preflight evidence and candidate provenance, closes the
candidate without saving, and removes only the uniquely named output after a
hash recheck.

New capability genuinely missing: an executable S3B live acceptance boundary
that proves the File IPC request reaches the Task 5 extraction route and that
success is candidate-only, source-read-only, hash-bound, and session-state
stable.

Full implementation allowlist: exactly the 27 paths authorized by Issue #64.
Inspection follow-up allowlist: exactly the four paths listed above.

Files forbidden to duplicate: IPC transport, Python production client,
schemas/examples, C#/.NET runtime, AutoCAD reader or dispatcher, accepted DWG,
source Xref, private drawings, SourceBundle/source fusion, component registry,
revision, repair, verdict, publication, dependencies, `STATUS.md`, and
`HANDOFF.md`.

Compatibility behavior: without all explicit S3B live prerequisites, the test
is collected under `autocad_mechanical` and reports `SKIP`. No offline test or
unavailable-state probe can promote this to live `PASS`. The test uses no
committed DWG, private source, API key, or live session identifier.

Migration and rollback path: revert the bounded S3B implementation commits as
one reviewed series. The existing offline contracts and Task 5 runtime remain
the safe fallback; no production behavior outside S3B is removed by rollback.

## Live prerequisites and safety boundary

The opt-in test requires all of the following process variables:

- `CAD_AGENT_FILE_IPC=1`;
- `CAD_AGENT_AUTOCAD_HWND` and `CAD_AGENT_AUTOCAD_LISP_PATH`;
- `CAD_AGENT_DOTNET_IPC_DIR`;
- `CAD_AGENT_S3B_FIXTURE_JSON`, pointing to an operator-approved JSON fixture
  containing an `inspection` and an `APPROVED` `plan`;
- `CAD_AGENT_S3B_CANDIDATE_DWG`, pointing to a disposable candidate under
  `CAD_AGENT_S3B_DISPOSABLE_ROOT`;
- server-owned `CAD_AGENT_S3B_DISPOSABLE_ROOT`, accepted-DWG path/hash, and
  exact-base source path/hash/revision variables.

The fixture inspection target hash must equal the accepted-DWG hash, the plan
target hash must equal the candidate hash, and both source bindings must equal
the configured source hash. The accepted DWG and candidate are opened through
the existing File IPC path. The test asserts fresh server-built inspection
evidence, `changed=false`, empty inspection handles, read-only inspected Xref
state, stable accepted-DWG DBMOD, fresh `live_preflight` eligibility, sorted
native candidate handles, complete source-handle mapping,
source/layer/block/provenance/revision/hash evidence, and unchanged source,
accepted DWG, candidate-input bytes, layout, view-port, UCS, and DBMOD state.

The output is a unique file below the server-owned disposable root. Cleanup
deletes it only after the returned output hash is rechecked. The active input
is closed with `save_changes=false`; the source Xref and accepted DWG are never
opened for mutation or saved.

## Verification evidence

Focused marker command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  mcp_integration_lib/tests/test_dotnet_ipc_live.py `
  -m autocad_mechanical -q -p no:cacheprovider
```

With the required live prerequisites absent, the observed result was **6
skipped, 6 deselected**, exit `0`. This is a truthful unavailable-state result
and not a live acceptance.

Focused .NET command:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln `
  --configuration Release --no-restore `
  --filter "FullyQualifiedName~OperationDispatcherTests|FullyQualifiedName~ExactBaseXrefReaderTests"
```

Observed result: **42 passed, 0 failed**, including the standalone inspection
gateway route and closed-failure tests.

Fresh full .NET solution result on exact head `9f5dc302`: **194 passed, 0
failed**. The hosted AutoCAD .NET gate remains **NOT RUN**.

Ruff command:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check `
  mcp_integration_lib/tests/test_dotnet_ipc_live.py
```

Observed result: exit `0`; all checks passed.

The canonical `scripts/verify.ps1` ran on exact head `9f5dc302` with a clean
tree and exit `0`: IPC JUnit **50 tests, 0 failure/error/skip**, offline JUnit
**1053 tests, 0 failure/error/skip**, private-data unavailable probe **2 SKIP**,
and AutoCAD unavailable probe **13 SKIP**. AutoCAD live remains **NOT RUN**;
this record-only finalization commit does not change runtime behavior.

## Gate states

- Task 6 live harness: **IMPLEMENTED**.
- AutoCAD Mechanical S3B live acceptance: **NOT RUN**; focused unavailable
  probe was **SKIP**.
- Private drawing/source-data acceptance: **NOT RUN**.
- S3B final PO acceptance and merge: **PENDING / LOCKED**.
- Task 7 full verification/evidence handoff: **COMPLETED** on exact head
  `9f5dc302` before this record-only finalization commit.
- S3C, R1C, registry, revision, repair, verdict, and publication: **LOCKED**.
