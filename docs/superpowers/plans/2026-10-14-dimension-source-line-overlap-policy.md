# Dimension source LINE overlap builder policy

Status: completed
Base SHA: 7da1ed42a2168b5c991fc389a4c8155b1e88a387
Approved design: `docs/superpowers/specs/2026-10-14-dimension-source-line-overlap-policy.md`
PO authority: #491 comment 6161127223; measured RED: #491 comment 6160919376.
Completion Head SHA: 6a8b7db46724b671f5437a275620e0998affd191

## Scope

Implement only the approved additive policy in `dxf_builder_lib/builder.py` and
the new focused module `dxf_builder_lib/tests/test_dimension_placement_policy.py`.
Legacy remains the default. CLI/pilot callers, reviewer contracts, schemas,
dependencies, PR #507 and native behavior remain unchanged.

## Execution record

1. Exact main/tree/owner/runtime admitted; authority comment read back. Clean
   worktree branch: `codex/dimension-source-line-overlap-v1`.
2. Render-isolation qualification: one frozen scratch harness at
   `D:\Cad agent temp\dimension-placement-owner-v1-20261014-01\render-isolation-qualification.py`,
   SHA256 `9AD23033E3544ED9203D260F7D6A40B30EEDEDC1A77D81F896AF307C7370958C`.
   One execution on Python 3.11.9/ezdxf 1.4.4 confirmed serialization clone
   retains DIMSTYLE Standard, faithful virtual LINE graphics, 40 mm native
   measurement, and unchanged original drawing entity/block inventory. The
   original-side candidate had 15 mm positive overlap on each dimension-line
   fragment; the opposed-side candidate had zero. One ordinary-context control
   rendered successfully. No disk DXF, build_dxf rerun or explode() was used.
   The control's comparison field referenced a neighbor absent from that
   control and is not evidence; qualification rests on render/resource
   success, paired-side results, and the unchanged original inventory.
3. TDD RED: `python -m pytest -q dxf_builder_lib/tests/test_dimension_placement_policy.py -k exposes_exact_opt_in_policy`
   failed as expected because `build_dxf` did not expose the approved policy.
   A second RED exposed that zero-length inferred dimensions were silently
   omitted under opt-in; the approved contract now rejects them while legacy
   retains its existing omission behavior.
4. Implemented the exact opt-in parameter and bounded cloned-render/LINE overlap
   selection in `dxf_builder_lib/builder.py`; no CLI/pilot/reviewer/schema or
   dependency changes.
5. Focused verification command:
   `python -m pytest -q dxf_builder_lib/tests/test_dimension_placement_policy.py dxf_builder_lib/tests/test_builder.py dxf_builder_lib/tests/test_reviewer.py tests/test_cad_agent_dimension_pilot.py tests/test_cad_agent_dimension_pilot_cli.py tests/test_dimension_pilot_contracts.py`
   Result: 141 passed. Ruff command `ruff check dxf_builder_lib/builder.py dxf_builder_lib/tests/test_dimension_placement_policy.py`
   passed; `git diff --check` passed. An earlier first focused pass exposed two
   test-fixture/oracle issues (touch point was inside the actual rendered LINE;
   exception regex did not match “classified”); the fixture was corrected and
   the final complete focused selection passed.
6. One implementation commit: `6a8b7db46724b671f5437a275620e0998affd191` (tree `77c5aecae9f517259cc4557804405375858e4e2c`).
7. Canonical verification ran exactly once in the supervised private child on `6a8b7db46724b671f5437a275620e0998affd191`:
   `scripts/verify.ps1 -PythonExe C:\cad-agent\.venv-py311\Scripts\python.exe -SkipAutoCADDotNet`
   Result: exit 0; “All checks passed”; Python 3.11.9; OpenCV 5.0.0.93; Tesseract 5.4.0.20240606. HEAD/tree/status were identical and clean before/after. AutoCAD .NET was explicitly skipped.
8. Real-data benchmark and AutoCAD/native gates: NOT RUN, consistent with PO authority. The implementation remains local/unpublished pending PO disposition.

## Stop boundaries

No CLI/pilot opt-in, PR/push/merge, reviewer or CI polling, real drawing,
AutoCAD/native action, dependency/schema/subsystem expansion, tolerance tuning,
or second render-isolation harness. Stop on identity/custody/runtime drift,
failed render isolation, unexplained trial residue, or unexpected focused or
canonical verification result.
