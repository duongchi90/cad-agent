# Source-written TEXT drafting verification

Status: implementation/offline verification complete; material review pending.
Base SHA: b3f4f3f72de8188816edf511750a91fa7b64fce7.
Approval date:2026-10-11; Human autonomous existing-owner hardening scope.
SOLO_CODEX only; no subagents, new subsystem or Arc/Circle mutation epic.

## Existing owner and measured boundary

Builder already writes TEXT height and rotation_deg. Native reviewer2 already
compares both. Headless reviewer only compared content/WCS insertion, accepting
height3.5->20 and rotation0->45 despite the saved/reopened native DXF differing
from written source facts. Nominal passes both reviewers; native transport replay
rejects both corruptions. Audit/checkpoint:
https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6108569039.

Reuse the headless TEXT loop, existing finite scalar predicate, existing absolute
geometry/rotation tolerances, and DXF-owned fixtures. Check declared fields only;
legacy evidence without height/rotation does not gain inferred source values.
No global restyling, font optimizer, collision detector, schema or native mutation.
This verifies roundtrip/source-written drafting, not complete paper fidelity.

## Regression and verification

Baseline on exact-main tree:51 reviewer tests PASS.
Saved/reopened regression before production change:2 causal FAIL/2 valid controls
PASS. First test epoch also incorrectly read omitted zero rotation with dxf.get;
corrected to native default-aware attribute read, preserving the failed test log.
Tests now cover exact, wrong, within/outside tolerance, nonfinite and undeclared
legacy expectations, with candidate byte invariance. Nearest DXF/native-replay/
architecture selection148PASS; Ruff/whitespace checks passed. Counts and logs
retained in the evidence root post492-text-drafting-discriminator-20261011-01.

Canonical command:scripts/verify.ps1 -PythonExe
C:/cad-agent/.venv-py311/Scripts/python.exe. PASS at clean implementation
d7296bd0629ca29c8edd167087bf2be6404784aa:3539Python+77subtests,261.NET,
76IPC+52subtests; offline JUnit3616/IPC128 zero failures/errors/skips.
Known causal_red oracle fails as required; native18/real_data2 unavailable
probes remainSKIP. Only this plan changes after verified implementation.
Native/real-data gates are separate. This change calls no native command and
changes no live reviewer/transport; replay does not establish AutoCAD PASS.
All PR492 failed epochs/source/frozen/gold remain preserved. Material merge
requires fresh exact-head SECURITY_REDTEAM + INTEGRATION_CI and hosted checks.
