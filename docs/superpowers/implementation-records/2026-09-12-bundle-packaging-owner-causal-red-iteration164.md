# AutoCAD Bundle Packaging Owner Causal RED — Iteration 164

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / AutoCAD bundle availability boundary  
Reviewed code HEAD: `f5d9a296884a7634e10565bfcdc69bc839ee4a74`

## Authority and boundary

Fresh SOL review of iteration 163 authorized exactly one owner-local
packaging-contract causal RED. The change is test-only. It does not add a
packaging script, alter the `.csproj`, commit a generated DLL, launch or load
AutoCAD, send LISP, invoke File IPC, touch the viewport, or mutate source,
customer/accepted CAD, candidate, DXF, or key state.

## Test-first contract

The existing bundle test file now declares one explicit future owner surface:
`scripts/package_autocad_bundle.ps1`. The new test supplies the real Release
DLL and repository `PackageContents.xml` and, once that owner exists, will
require it to create a disposable bundle with:

- `Contents/Windows/CadAgent.AutoCAD2027.dll` present;
- staged bytes and SHA-256 identical to the Release DLL; and
- the manifest `ModuleName` resolving to that staged file.

No implementation was written before observing RED.

## RED evidence

Focused test command:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q mcp_integration_lib/tests/test_autocad_application_bundle.py::test_autocad2027_bundle_packaging_owner_stages_release_dll
```

Result:

```text
1 failed in 0.12s
AssertionError: Issue #424 RED: deterministic AutoCAD bundle packaging owner is absent
```

The combined nearest-owner run kept the existing contract green and the new
contract red:

```text
1 failed, 1 passed in 0.69s
```

The failure is at the intended missing-owner assertion, after confirming the
repository manifest and real Release DLL exist; it is not a collection,
interpreter, or unrelated test error.

## Current classification

```text
STATE=CAUSAL_RED_CHARACTERIZED
MATERIAL_FINDING=BUNDLE_PACKAGING_OWNER_GAP
LIVE_ORACLE=NOT_RUN
HUMAN_GATE=NO
```

Fresh SOL review is required before any minimal packaging-owner implementation
or any live AutoCAD retry. The new test remains intentionally failing until
such an action is explicitly authorized.

