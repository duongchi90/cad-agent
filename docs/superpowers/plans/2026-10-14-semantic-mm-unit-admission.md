# Semantic IR Millimetre Unit Admission Plan

Status: executing

Base SHA: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`

Completion Head SHA: pending.

## Implementation sequence

- [x] Add a causal failing regression for non-mm and malformed unit labels,
  helper non-execution, unchanged source input, and the exact-mm control.
- [x] Add the minimum exact-mm admission guard at the semantic assembly entry.
- [x] Document the millimetre precondition and reuse boundary.
- [x] Run focused Semantic IR and staged caller contract tests, touched Ruff,
  and `git diff --check`.
- [ ] Commit the scoped implementation after focused/static checks pass.
- [ ] Run the canonical verifier once:
  `./scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`
- [ ] After canonical PASS, close this plan with at most one plan-only commit.

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
- Canonical command: pending. Exact command:
  `./scripts/verify.ps1 -PythonExe 'C:\cad-agent\.venv-py311\Scripts\python.exe' -SkipAutoCADDotNet`.
- Private real-data benchmark: NOT RUN; this package is restricted to the
  synthetic unit discriminator and forbids private/reference drawings.
- AutoCAD Mechanical live gate: NOT RUN; no native or DXF behavior is changed.
- Exact-head Security/Integration review: NOT requested; no PR/publication is
  authorized by this package.

## Completion record

Implementation commit, final evidence, and any remaining limitations: pending.
