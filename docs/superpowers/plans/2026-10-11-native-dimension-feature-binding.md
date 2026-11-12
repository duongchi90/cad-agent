# Native linear DIM measured-feature guard

Status: completed (implementation/offline verification; native promotion remains blocked)
Base SHA: 133294b7f5ea8c4f768a08a9605b3897fab8a784
Completion Head SHA: 699351f09fe5688ee30dfe28d66bc03e83c4d104
Approval date: 2026-10-11; Human production-improvement instruction, existing
owners first, no routine microapproval, SUBAGENTS=0.

## Scope and reuse

Second bounded production improvement integrated into contour draft PR #492. The compact
[#491 audit](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6103952330)
identifies DIM/feature and drafting correctness gaps. A fresh packaged-consumer
discriminator proves class C: correct 80 mm measurement survives moving the DIM
extension origins to a different parallel feature/elevation. Both existing
reviewers accepted it; missing native definition readback also produced CLI exit0.

Reuse builder's existing `geometry_primitive_id`, headless/native reviewers,
FileIPC entity-get, evidence carriage and repair refusal. No new identifier,
schema/registry, renderer, transport, dependency or drawing-specific logic.
No new source case or private candidate mutation. Independent draft PRs remain
unmerged; current main is the exact base above. Both guards share existing
reviewers, so their conflicts are resolved in one SOLO-owned branch and their
combined behavior is verified before updating the existing draft PR.

For source-declared LINE dimensions, compare observed WCS definition points
13/14 to actual LINE endpoints, accepting either order with absolute 1e-6 mm
tolerance. Require readable finite points, LINE and DIM in direct ModelSpace,
and native linear/rotated/aligned dimension type. Other types or unavailable
readback cannot prove this obligation. Legacy evidence without a feature ID
retains its former measurement-only semantics. Source-bound reference DIMs also
require readable feature placement even without an exact approved numeric value.

Use Autodesk's native representation, not guessed screen coordinates:
[linear/rotated DXF definition points](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-F0004556-493C-48D5-8619-61D6ADF05C04.htm),
[aligned DXF definition points](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-7A123D5D-AC98-4A9A-A8CF-1A7EF5030418.htm).

Keep DIM feature verdicts out of primitive repair IDs. The existing live repair
owner refuses a failed feature obligation before backup or mutation; an ID
collision cannot turn a DIM verdict into a LINE erase/recreate request.

This proves static measured-feature placement only. It does not establish
DIMASSOC, driving constraints, arrow/text quality, or native coupled ARC editing.
Shared coordinates do not prove a unique semantic association to coincident
duplicate features. No full engineering/native acceptance claim is made.

## Verification plan and observed evidence

1. Before production change, nine consumer controls: seven causal failures,
   two valid controls PASS. Actual `mechanical-review` exit0 on all seven
   incorrect/unreadable cases; headless also falsely accepted wrong locations.
   Retained JUnit: D:/Cad agent temp/native-dimension-feature-production-evidence-20261011/causal-red.xml.
2. Initial focused/nearest checks:160 PASS, expanded dispatcher selection229 PASS;
   after integrating the contour guard247 PASS; final joint selection250 PASS.
   Twenty new offline controls
   include bound/reversed positives, translated/elevated/large-coordinate
   failures, missing fields, unsupported type, nonfinite points, unknown/different
   space, structural-only, legacy absence and repair-ID collision. Three of the
   twenty controls prove both obligations coexist on one native-entity candidate:
   both correct PASS, open contour/correct DIM FAIL, closed contour/wrong DIM FAIL.
3. First complete verifier at d5026e5a2b2bc107da2f773081bb7489750db5d9:
   .NET261 and IPC76+52 PASS, Python3437 PASS/one architecture-boundary failure.
   Test-only DXF mutation was incorrectly placed outside the DXF owner. Moved it
   to existing dxf_builder_lib/tests/dxf_test_support.py; boundary+new controls
   then23 PASS. No allowlist was expanded. Retain this failed epoch.
   Final scripts/verify.ps1 on committed combined Completion Head above:
   3454 Python +74 subtests PASS, offline JUnit3528/zero failures/errors/skips;
   .NET261 PASS; IPC76+52 subtests PASS, JUnit128/zero failures/errors/skips.
   Required causal-RED negative oracle1 expected failure, script gate PASS.
   Real-data2 and native18 unavailable probes SKIP; generic live/M2 NOT RUN.
   Lock/environment/lint/Autodesk DLL output/diff/clean-side-effect gates PASS.
   Python C:/cad-agent/.venv-py311/Scripts/python.exe; process-local installed
   SDK10.0.401 PATH, no install/global settings change. Log:
   D:/Cad agent temp/native-dimension-feature-production-evidence-20261011/full-verifier-combined.txt,
   SHA256670187c47e3801d865d29ed2b0590d0adddda90de7bd6fe0e85e3254d33fe50a.
4. Opt-in native gate is test_dimension_feature_binding_live.py. NOT RUN:
   current Computer Use inventory has no AutoCAD target window; process20172
   remains running with MainWindowHandle0. Prior PR #492 attempt stopped before
   drawing-open at WINDOW_RECEIVER_AMBIGUOUS. No unchanged transport retry,
   guard bypass, alternate COM adapter or additional CAD process was attempted.
5. Publish draft only, preserve exact code/tree identity, hosted CI and mandatory
   independent exact-head Security/Integration review. No merge/native promotion
   until applicable evidence is available. Private real-data gate NOT RUN;
   this does not change source recognition/calibration or add a benchmark case.
