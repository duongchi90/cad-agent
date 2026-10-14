# Semantic IR Millimetre Unit Admission Plan

Status: completed

Base SHA: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`

Completion Head SHA: `e30f17a143930bd917987b1122fa2a8cc571d69b`.

## Implementation sequence

- [x] Add a causal failing regression for non-mm and malformed unit labels,
  helper non-execution, unchanged source input, and the exact-mm control.
- [x] Add the minimum exact-mm admission guard at the semantic assembly entry.
- [x] Document the millimetre precondition and reuse boundary.
- [x] Run focused Semantic IR and staged caller contract tests, touched Ruff,
  and `git diff --check`.
- [x] Commit the scoped implementation after focused/static checks pass.
- [x] Run the canonical verifier once:
  `./scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`
- [x] After canonical PASS, close this plan with one plan-only commit and
  confirm only this plan changed while production/test blobs remained fixed.

## Verification and gates

- RED: `python -m pytest semantic_ir_lib/tests/test_semantic_unit_contract.py -q --tb=short`
  on unchanged production code — expected failure observed (6 rejection cases
  failed because no `ValueError` was raised; mm control passed), exit 1.
- GREEN: `python -m pytest semantic_ir_lib/tests -q --tb=short` — 74 passed,
  exit 0; `python -m pytest tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py
  tests/test_cad_agent_cli_staged_semantic_policy.py
  tests/test_cad_agent_cli_source_fact_composition.py
  tests/test_cad_agent_phase4_pilot_binding.py
  tests/test_cad_agent_r6_candidate_artifact_binding.py -q --tb=short` — 82
  passed, exit 0; `python -m pytest tests/test_cad_agent_mechanical_pilot.py
  -q --tb=short` — 23 passed, exit 0.
- Static: `python -m ruff check semantic_ir_lib/assemble.py
  semantic_ir_lib/tests/test_semantic_unit_contract.py` — exit 0;
  `git diff --check` — exit 0.
- Runtime: Windows; Python 3.11.9 at
  `C:\cad-agent\.venv-py311\Scripts\python.exe`.
- Canonical command:
  `./scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`
  — exit 0, 197.0 seconds, supervised child PID 23248. Offline JUnit: 3714
  tests, 0 failures/errors/skips; dotnet_ipc JUnit: 128 tests, 0
  failures/errors/skips. The canonical expected-RED gate: 1 expected failure,
  0 errors/skips. Private real-data probe: 2 skipped (no approved input);
  AutoCAD unavailable-state probe: 18 skipped; AutoCAD .NET, native CAD, and
  private drawing gates NOT RUN by package scope. Tesseract 5.4.0.20240606;
  OpenCV 5.0.0.93; locked dependencies passed.
- Durable verifier output:
  `D:\Cad agent temp\semantic-mm-unit-admission-e30f17a\verify.stdout.log`
  and `verify.stderr.log` (empty); canonical JUnit artifacts are under
  `.artifacts/test-results`.
- Private real-data benchmark: NOT RUN; this package is restricted to the
  synthetic unit discriminator and forbids private/reference drawings.
- AutoCAD Mechanical live gate: NOT RUN; no native or DXF behavior is changed.
- No branch push, PR, Security/Integration review, or CI action was authorized.
  A single #491 evidence receipt is authorized by the package.

## Completion record

Implementation commit: `e30f17a143930bd917987b1122fa2a8cc571d69b`.
Plan-only closure commit: performed after canonical PASS; see branch history.
Remaining limitation: non-mm units are refused; coordinate conversion is not
implemented. Real-data and native CAD gates remain NOT RUN.
