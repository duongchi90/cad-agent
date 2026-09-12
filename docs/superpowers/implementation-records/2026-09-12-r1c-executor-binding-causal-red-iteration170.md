# R1C Executor Binding Causal RED — Iteration 170

Date: 2026-09-12 (Asia/Saigon)  
Issue: #409 real-PDF exact-provenance acceptance  
Reviewed base/main: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch before this slice: `codex/audit-text-style-compat-20260910`  
Pre-change HEAD: `b3460eb8eec273069740e0106bc04f683187efca`

## Authorization and bounded scope

SOL direct review `479f8840-7694-4347-8c26-345c6b8639c2` authorized exactly
one test-only causal RED at the current executor to existing R1C owner
boundary. The test uses only disposable synthetic configuration values. It
does not create a production key/provider/store, expose a bridge API, bypass
SourceCustody/HMAC checks, mutate source or CAD, or run AutoCAD/FileIPC.

## Test-first contract

`tests/test_cad_agent_r1c_executor_binding.py` constructs a complete
test-only R1C configuration containing an approved root, identity material,
policy limits, and a validated exact `source_bundle`. It then requires the
existing PDF executor `cad_agent.pdf.run_pdf_stages` to expose the narrow
`r1c_configuration` binding needed to invoke the existing
`inspect_source_bundle`/Source Fusion owners.

## RED evidence

Focused command:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q tests/test_cad_agent_r1c_executor_binding.py::test_pdf_executor_binds_complete_r1c_configuration_to_existing_owner
```

Result:

```text
1 failed in 0.17s
AssertionError: Issue #409 RED: current PDF executor lacks the binding to the existing R1C inspect_source_bundle/source-fusion owners
```

The fixture assertions passed first: the source bytes match the bundle item
hash and the bundle has a deterministic SHA-256. The only failure is the
missing `r1c_configuration` parameter on the existing PDF executor.

## Current classification

```text
STATE=CAUSAL_RED_CHARACTERIZED
BOUNDARY=R1C_OWNER_CONFIGURATION_NOT_EXPOSED_TO_CURRENT_EXECUTOR
MATERIAL_FINDING=R1C_EXECUTOR_BINDING_GAP
LIVE_ORACLE=NOT_RUN
HUMAN_GATE=NO
```

No implementation is authorized by this record. The next action is a fresh
SOL review of this exact RED before any minimal executor-owner binding is
implemented. No source, candidate, DXF, CAD, provider, M2, or live state was
mutated.

