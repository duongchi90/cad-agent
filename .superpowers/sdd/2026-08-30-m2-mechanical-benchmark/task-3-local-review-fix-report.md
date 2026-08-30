# Task 3 Local Review Fix Report

Date: 2026-08-30

Scope: `mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py` and `tests/test_m2_benchmark.py`

Implemented

- `_current_main_sha()` now prefers `GITHUB_SHA` only when it is already a valid lowercase 64-character SHA-256. Otherwise it resolves `refs/heads/main^{commit}` via `git rev-parse`, validates the result, and raises on failure instead of returning an all-zero sentinel.
- Added a sidecar measurement artifact writer that uses the existing `write_live_report()` helper and writes outside the repository, derived from the record path.
- The live benchmark now persists request/result byte size totals and repeated entity-query count into that sidecar artifact.
- The live benchmark now verifies distinct hashes for the fixture input JSON and staged DXF, rather than reusing the staged DXF hash for both values.
- The live benchmark now requires empty `health.errors`, empty `mechanical_bom.errors`, and semantic BOM evidence for `COMP_FRAME` and `COMP_EMPTY` with the expected `PART_ID=FRAME-001` attribute.
- Added focused tests for the local-main SHA fallback, the sidecar measurement artifact, and the distinct-hash cleanup contract.

Verification

- `.\.venv-py311\Scripts\python.exe -m pytest tests/test_m2_benchmark.py mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py`
  - Result: `65 passed, 1 skipped`
  - Skip reason: live AutoCAD/MCP prerequisites were not present in this environment.
- `.\.venv-py311\Scripts\python.exe -m ruff check tests/test_m2_benchmark.py mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py`
  - Result: passed
- `git diff --check`
  - Result: no whitespace errors

Notes

- The closed M2 record schema was left intact.
- The added measurement artifact is a separate JSON sidecar and contains no secrets or customer paths.
