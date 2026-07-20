# Main Integration Promotion Design

## Goal

Promote the verified `integration/main-master` work to `main`, record its
test evidence, and make `main` the repository's canonical branch.

## Current State

`main` is an ancestor of `integration/main-master`; the only additional commit
is `1e960bb` (`feat: integrate master benchmark pipeline and fix gia_do`). The
complete test suite passes in `.venv-py311` with Tesseract available on PATH:
220 passed, with three expected OCR ROI warnings.

## Design

1. Add `.venv-py311/` to `.gitignore` so the local Python 3.11 environment is
   never committed.
2. Update `HANDOFF.md` with the integration commit, `gia_do` regression fix,
   full test command/result, Python 3.11 requirement for optional SolveSpace
   tests, and Tesseract PATH requirement for OCR tests.
3. Commit those documentation/configuration changes on
   `integration/main-master` and push them.
4. Fast-forward `main` to the integration branch and push `main`.
5. Change GitHub's default branch from `master` to `main`.

## Branch Retention

Do not delete `master`, feature, or fix branches in this change. Retain them
until `main` has been used successfully, then remove only branches that are
confirmed obsolete in a separate cleanup action.

## Validation

Before promotion, rerun the complete suite using:

```powershell
$env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
.\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q
```

Expected result: 220 passed; three OCR ROI warnings are acceptable.
