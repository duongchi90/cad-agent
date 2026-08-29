# Task 3 Final Fix Report

Date: 2026-08-30

Scope: `mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py` and `tests/test_m2_benchmark.py`

Implemented

- Split `_cleanup_epoch_artifacts()` so it verifies the fixture input JSON hash and the staged disposable DXF hash separately.
- Updated the live benchmark call site to pass `fixture.input_path` and `fixture.input_sha256` for the source-side cleanup check, while preserving the staged DXF hash check for the disposable drawing.
- Added regressions that prove cleanup does not report true when either the input JSON or staged DXF hash is mismatched or the input file is mutated.
- Tightened `_current_main_sha()` so `GITHUB_SHA` is accepted only when it already matches the exact lowercase 64-character SHA-256 form; otherwise the helper falls back to the local `refs/heads/main^{commit}` lookup and still fails closed on resolution errors.
- Added regression coverage for invalid `GITHUB_SHA` fallback behavior and preserved the existing local-main success and failure tests.
- Kept the measurement sidecar on the existing `write_live_report()` atomic write path, outside the repository via the record-path sibling, with non-sensitive summary data only.
- Added a regression that exercises the sidecar writer and verifies the payload stays compact and repo-external.

Verification

- `.\.venv-py311\Scripts\python.exe -m pytest tests/test_m2_benchmark.py mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py -q`
  - Result: `70 passed, 1 skipped`
  - Skip reason: live AutoCAD/MCP prerequisites were not present in this environment.
- `.\.venv-py311\Scripts\python.exe -m ruff check tests/test_m2_benchmark.py mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py`
  - Result: passed
- `git diff --check`
  - Result: clean, with only line-ending warnings from Git on the edited files

Notes

- No closed schema or production module changes were made.
- No launch, NETLOAD, repair, save, mutation, or BVTL behavior was added.
