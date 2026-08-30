# Task 3 Fix Report

Date: 2026-08-30
Base under repair: `9a64f6e`

## Scope

Implemented the requested Task 3 fix round within the bounded benchmark write-set:

- `mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py`
- `tests/test_m2_benchmark.py`

No production architecture, Task 1/2 APIs, planning docs, or `docs/STATUS.md` were changed.

## Findings Closed

1. Schema-valid record persistence now goes through the repository-owned M2 contract.
   - The live harness now loads an existing record with same-main refusal preserved.
   - New runs create records through `new_m2_record(...)`.
   - New epochs append through `append_m2_epoch(...)`.
   - Final payloads are revalidated with `validate_m2_record(...)`.
   - `write_live_report(...)` now atomically writes the schema-valid record itself, not an ad hoc wrapper.

2. Comparable/success state is no longer fabricated before evidence.
   - Epochs start non-comparable and unsuccessful.
   - Headless data is copied from real fixture metrics via `headless_metrics(...)`.
   - Live data is copied from observed `review_dxf_live(...)` counts plus observed BOM component counts.
   - Any `MCPTimeoutError`, `MCPToolError`, or `DotNetIPCResultError` after human capture clears `accepted_comparable` and `success` before persistence.

3. Negative probes are now derived from observed refusals.
   - Stale-evidence rejection uses copied build evidence plus a changed disposable DXF and derives capture/count from the actual `load_build_evidence(...)` refusal.
   - Wrong-target rejection opens a second disposable drawing, sends the bound request against the wrong active target, and derives capture/count from the actual refusal.
   - No hard-coded stale/wrong-target success counters remain.

4. M2 opt-in unavailable states are explicit.
   - Missing core AutoCAD/FileIPC prerequisites still produce an explicit module skip.
   - Missing M2 record path produces an explicit opt-in skip.
   - Missing M2 session or human-event inputs no longer false-green; they produce a non-comparable epoch path and fail after persistence when the live test runs.

5. Cleanup reporting is based on observed results.
   - The harness verifies real before/after SHA state for the disposable drawing.
   - It uses exact `close_disposable(disposable=True, save_changes=False)`.
   - It checks request/result cleanup, including the close request id.
   - It reuses the existing release and directory cleanup helpers.
   - Cleanup fields are reported from observed postconditions rather than optimistic defaults.

6. Live-only safety remained intact.
   - No AutoCAD launch, NETLOAD automation, repair, save, save-as, entity mutation, or BVTL access was added.
   - The live module remains safe to skip when prerequisites are absent.

## Offline Coverage Added

Focused offline harness-shape tests now cover:

- schema-valid record append/write behavior
- failure after human capture clearing false-green state
- real stale-evidence refusal capture
- wrong-target refusal capture with a second drawing
- explicit missing opt-in reporting
- explicit missing record-path skip behavior
- truthful cleanup reporting and exact-directory removal
- transport counter derivation
- request/result artifact cleanup checks
- live-review metric copying without invented counts

These tests use fakes/monkeypatch and do not require AutoCAD.

## Verification

Focused pytest:

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py -q -p no:cacheprovider
```

Result: `60 passed, 1 skipped`

Skip detail:

- `mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py` skipped because `CAD_AGENT_FILE_IPC`, `CAD_AGENT_FILE_IPC_DIR`, `CAD_AGENT_DOTNET_IPC_DIR`, `CAD_AGENT_AUTOCAD_HWND`, and `CAD_AGENT_AUTOCAD_LISP_PATH` were not all present. This is an explicit unavailable-state skip, not a live pass.

Focused Ruff:

```powershell
& .\.venv-py311\Scripts\python.exe -m ruff check tests\test_m2_benchmark.py mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py
```

Result: `All checks passed!`

Whitespace check:

```powershell
git diff --check
```

Result: exit `0`; Git reported only LF-to-CRLF warnings for the two edited benchmark files.

## Remaining Limits

- No live AutoCAD Mechanical benchmark epoch was executed in this fix round because the required live prerequisites were unavailable in this workspace.
- Request/result byte sizes and repeated-query counts are observed inside the live harness path for runtime decision-making, but no Task 1/2 schema change was made in this bounded round.
