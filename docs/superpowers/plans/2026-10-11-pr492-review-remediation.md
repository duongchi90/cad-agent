# PR #492 independent review remediation

Status: completed (implementation/offline verification; re-review/native promotion pending)
Base SHA: 133294b7f5ea8c4f768a08a9605b3897fab8a784
Completion Head SHA: f57269bd96a8b2b503306bb2897ef254084e213c
Reviewed Head SHA: eddcc44b80e5e5e29c06c5230cd49ff7c1f7d03e
Approval date: 2026-10-11; Human supplied both independent reviews and authorized
the existing SOLO production loop. No subagents or new subsystem.

## Findings, existing owners and bounded repair

- F1 / Integration finding 1: actual `repair_live` accepted a review containing
  both contour and primitive failures. Make the existing contour refusal
  unconditional before backup or mutation; preserve dimension refusal/recovery.
- F2: saved reversed/tilted ARC extrusion with incident WCS LINE endpoints passed
  headless review but failed live review. Reuse `contour_endpoints` in both paths
  with observed native fields. Unsupported/nonfinite geometry is unavailable,
  never discharged with written expectations. No new geometry engine.
- F3 is a coverage/native-evidence concern, not an established production defect.
  Add narrow native type-bit controls at the existing live reviewer consumer.
  This remains replay/offline evidence; actual AutoCAD semantics are not proven.

## Regression and verification

Before production changes, five targeted controls produced three causal failures:
mixed contour/primitive repair DID NOT RAISE; reversed and tilted ARC headless
review falsely passed. Contour-only and default-plane positive controls passed.
Retained evidence: native-dimension-feature-production-evidence-20261011/
review-remediation-red.xml (outside Git).

After the minimal fixes: contour controls 17 PASS; expanded contour/DIM and owner
boundary selection 56 PASS, including nonfinite ARC center/radius and native DIM
type bits 0/1, 32/33, unsupported 34-38, negative and boolean values.
Command: `python -m pytest mcp_integration_lib/tests/test_contour_join_guard.py
mcp_integration_lib/tests/test_dimension_feature_binding.py
tests/test_reuse_architecture_boundaries.py -q`.
Nearest-owner selection (DXF owner, both relationship guards, native DIM consumer,
Phase4, live CLI/repair and architecture boundaries): 199 PASS.

Canonical `scripts/verify.ps1 -PythonExe C:/cad-agent/.venv-py311/Scripts/python.exe`
completed with exit 0 on the clean committed Completion Head above: 3471 Python
plus 74 subtests PASS, JUnit3545 with zero failures/errors/skips; 261 .NET PASS;
76 IPC plus 52 subtests PASS, JUnit128 with zero failures/errors/skips.
The required causal-RED negative oracle produced its expected failure and the
script gate passed. Lock/environment/lint/Autodesk DLL/diff/side-effect gates
passed. Existing MSB3277 and nullable .NET warnings remain; no .NET source changed.
Real-data unavailable probes2 SKIP; native unavailable probes18 SKIP; AutoCAD/M2
NOT RUN. Full local log: D:/Cad agent temp/
native-dimension-feature-production-evidence-20261011/full-verifier-review-remediation.txt.
Use already-installed SDK10.0.401 through process-local PATH; no installation.
No retry of the unchanged
WINDOW_RECEIVER_AMBIGUOUS condition, no new CAD source case, no frozen/revealed
candidate edit or gold access. Publishing a draft does not close independent
exact-head re-review or native promotion.
