# Source-declared native contour join guard

Status: completed (implementation/offline verification; native promotion remains blocked)
Base SHA: 133294b7f5ea8c4f768a08a9605b3897fab8a784
Completion Head SHA: 0b177d11484847437e546cc3ae9e7f41ea703501
Approval date: 2026-10-11; Human's explicit production-improvement instruction,
existing owners first, no routine design microapproval, SUBAGENTS=0.

## Bounded design and reuse

JXS radius-only edits left 0.1–0.3 mm gaps despite correct ARC/DIM values;
owner-mediated coupled endpoint edits closed them. Evidence and compact audit:
[issue 491](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6103952330).

Reuse `build_dxf`/`BuildResult`, the existing headless/native reviewers,
integrity-safe build evidence and `mechanical-review` caller. Reuse ezdxf native
WCS endpoints and `ConstructionArc`; no new geometry/constraint engine,
detector, transport, subsystem or public IPC operation.

Add optional source-declared endpoint pairs keyed by obligation ID:
`first`/`second` each contain `primitive_id` and `endpoint` (`start` or `end`).
No automatic adjacency inference. Empty obligations retain legacy roundtrip
behavior. Carry obligations through evidence save/load; compare actual endpoints
with absolute 1e-6 mm incidence tolerance. Open, invalid or unavailable joins
are nonPASS. Native joins require observed ModelSpace layout, never equal
coordinates in different drawing spaces. Native ARC readback must include observed extrusion; current
native snapshot support is XY-plane ARC, with elevation. Other planes are
unavailable rather than assumed XY. Headless DXF uses native WCS endpoints.

Keep contour verdicts separate from primitive mismatch IDs: recreating unchanged
per-entity geometry cannot repair an open plan. Existing repair refuses this
case before backup/mutation; caller must supply an explicit coupled plan.

Scope: detection part of P1, staged native LINE/ARC review. This does not add
in-place coupled ARC mutation, native constraints, tangency, arbitrary DIMASSOC
editing, source recognition, a CLI extraction flag or whole-DWG acceptance.
The .NET isolated-LINE mutation/reactor safety boundary remains unchanged.

## Implementation and regression

1. Packaged capability discriminator: current builder rejects contour argument.
2. Add evidence carriage, then observe open 0.1 mm contour headless false-green
   and actual packaged `mechanical-review` unavailable-ARC exit0.
3. Existing-reviewer guard and observed ARC extrusion readback. Nominal and
   coupled endpoints pass; radius-only and large-coordinate gap reject.
4. Invalid/unknown-plane/structural-only/unreadable obligations reject; legacy
   absence preserves behavior; topology ID collision cannot erase a primitive.
   A subsequent native-review discriminator reproduced ModelSpace/PaperSpace
   false-green despite equal coordinates; observed layout now closes that gap.
5. Focused checks, authoritative verifier and opt-in native gate; publish draft
   PR. Material merge awaits independent exact-head Security/Integration review.

## Verification

Focused command:
`python -X utf8 -m pytest dxf_builder_lib/tests mcp_integration_lib/tests/test_contour_join_guard.py mcp_integration_lib/tests/test_native_dimension_guard.py mcp_integration_lib/tests/test_phase4.py tests/test_cad_agent_live.py -q`

Observed: 154 PASS after fixture moved into the existing DXF test-support owner;
final focused/nearest selection including dispatcher and repair capability:
250 PASS, zero skips/failures. There are 13 new offline contour controls.
Ruff and `git diff --check`: PASS at that epoch.

Authoritative command: `scripts/verify.ps1 -PythonExe C:/cad-agent/.venv-py311/Scripts/python.exe`.
Result: PASS at initial implementation head28875fdf701e7122d5f49653e73922b6649729b0,
then final exact-head repeat PASS at Completion Head above after cross-space
guard refinement. Clean start/end and repository side-effect check passed.
Final offline JUnit: 3508 cases (3434 Python tests +74 subtests), zero failure,
error or skip. .NET IPC JUnit:128 cases (76 tests +52 subtests), zero failure,
error or skip. .NET tests:261 PASS. Lint, dependency/environment lock, Autodesk
DLL output check and expected causal-RED oracle passed their script gates.
Two real-data and17 native unavailable-state probes are SKIP, not capability
PASS; generic native live and M2 were NOT RUN by the full verifier.
First invocation selected runtime-only system dotnet and failed restore;
process-local PATH selected already-installed SDK10.0.401, without install or
global settings change. Final log lives at
`D:/Cad agent temp/native-arc-contour-production-evidence-20261011/full-verifier-final.txt`.

Specialized native command: explicit File IPC/HWND/dispatcher opt-in,
`pytest mcp_integration_lib/tests/test_contour_join_guard_live.py -q -m autocad_mechanical`.
Result: FAIL before drawing-open, `WINDOW_RECEIVER_AMBIGUOUS` from the existing
packaged Windows trigger (one attempt, PID20172 / requested HWND9569924).
No native ARC geometry was read; live incidence remains NOT PROVEN. JUnit:
`D:/Cad agent temp/native-arc-contour-production-evidence-20261011/native-gate.xml`.
No private COM substitution or receiver/currentness guard bypass. This existing
transport boundary is not repaired in the contour change. No repeat of the
unchanged blocker; independent live review is still required before promotion.

Private real-data benchmark: NOT RUN; no recognition/calibration behavior change
or new source case. Existing native JXS checkpoint is design evidence, not a
fresh packaged live PASS. No frozen candidate or gold access changes.
