# CASE02 ModelSpace Readback Implementation Plan

**Status:** executing
**Base SHA:** `abfb60ea7d9cf2012e0ea30b68b9fef8b5fb0512`
**Completion Head SHA:** pending
**Design:** `docs/superpowers/specs/2026-10-24-case02-modelspace-readback-design.md`

## Frozen boundary

Extend the existing `drawing_setup_audit` path to emit a complete, read-only ModelSpace inventory bound to the exact active drawing, disk SHA-256, `DBMOD=0`, AutoCAD process, and plugin build. Preserve legacy behavior unless the explicit opt-in is set. No AutoCAD opening/mutation during offline implementation.

## Tasks

1. Add failing C# and Python tests for opt-in shape, complete enumeration dispositions, path/hash/build/current-document custody, `DBMOD=0` before/after, and unchanged legacy request behavior.
2. Extend the existing AutoCAD drawing gateway and setup payload; enumerate all ModelSpace objects in the same read-only boundary and fail closed on custody or enumeration failure.
3. Add the fixed operation-scoped 16 MiB result policy to native serialization and Python result reading; keep request writes and other operations at their existing limit; overflow must yield a small failure without a partial inventory.
4. Extend the existing drawing setup contract/CLI opt-in and verify strict validation, hash binding, and compatibility.
5. Run focused C# and Python tests, affected contract checks, `git diff --check`, then the canonical verifier if resources permit. Record AutoCAD live readback separately; offline green is not native acceptance.
6. Re-read exact current main and branch head, inspect the final diff/write set, publish a Draft PR only after local verification, then request required exact-head Security and Integration reviews. Do not claim native acceptance until the separate CASE02 readback is executed and reconciled.

## Write set

- Existing `autocad_plugin/CadAgent.AutoCAD2027` request validation, dispatcher, drawing gateway, setup payload, result writer, and command dispatch.
- Their existing focused tests.
- Existing `mcp_integration_lib/dotnet_ipc.py` and its tests.
- Existing `cad_agent` drawing setup contract and CLI owners, their tests, and the existing drawing setup schema/example.
- This design and plan; `docs/STATUS.md` only when implementation evidence is closed.

No new subsystem, transport, database, external-source code, drawing mutation, or new test harness.

## Verification record

- `dotnet test autocad_plugin\CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --nologo`: PASS, 265 passed, 0 failed, 0 skipped.
- `mcp_integration_lib/tests/test_dotnet_ipc.py -m "not real_data and not autocad_mechanical"`: PASS, 77 passed and 52 subtests passed.
- Full offline pytest selection (`tests`, `primitive_ir_lib/tests`, `semantic_ir_lib/tests`, `dxf_builder_lib/tests`, `mcp_integration_lib/tests`, `agent_lib/tests`, excluding `real_data`, `autocad_mechanical`, `causal_red`): PASS, 3,737 passed, 24 deselected, 86 subtests passed.
- Drawing Setup schema/CLI/contract focused checks: PASS, 12 passed; parser baseline regenerated with `scripts/export_cli_contract.py` and its compatibility test passed.
- Oversized response test: PASS; 17 MiB opted-in response is replaced with a small failure and empty payload.
- `scripts/check_environment.py requirements/windows-py311.lock`: PASS (40 locked distributions); Tesseract 5.4.0.20240606 present.
- `git diff --check`: PASS.
- Canonical verifier: pending.
- Private/real-data gate: CASE02 candidate readback pending; no drawing opened during offline implementation.
- AutoCAD/.NET live gate: pending and distinct from offline tests.
