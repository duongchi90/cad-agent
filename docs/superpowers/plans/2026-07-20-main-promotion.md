# Main Integration Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the fully tested integration branch to `main` and make `main` the canonical GitHub branch.

**Architecture:** Commit only handoff, ignore, and documentation on `integration/main-master`; then fast-forward `main`, which is already its ancestor. Preserve `master` and feature branches for separate cleanup.

**Tech Stack:** Git, GitHub, Python 3.11 virtual environment, pytest.

## Global Constraints

- Use `.venv-py311`; preserve system Python 3.12.
- Prefix PATH with `C:\Program Files\Tesseract-OCR` only for the test command.
- Require 220 passing tests; accept only the three documented OCR ROI warnings.
- Do not delete or force-push any branch.

---

### Task 1: Record reproducible integration evidence

**Files:** `.gitignore`, `HANDOFF.md`, and the design/plan documents.

- [ ] Add `.venv-py311/` to `.gitignore`.
- [ ] Add a dated HANDOFF entry for commit `1e960bb`, the `gia_do` fix, Python 3.11, the Tesseract PATH prefix, and `220 passed, 3 warnings`.
- [ ] Run:

```powershell
$env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
.\.venv-py311\Scripts\python.exe -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q
```

Expected: exit code 0, 220 passed, three OCR ROI warnings.

- [ ] Stage only `.gitignore`, `HANDOFF.md`, and these two documentation files; verify `.venv-py311/` is absent; commit with `docs: record main integration verification`.

### Task 2: Promote the integration branch

- [ ] Push `integration/main-master`.
- [ ] Run `git switch main`, `git pull --ff-only origin main`, `git merge --ff-only integration/main-master`, and `git push origin main`.
- [ ] Change the GitHub default branch to `main`.
- [ ] Run `git fetch origin --prune`, inspect `origin/main`, and retain every existing branch.

## Self-review

The plan records reproducible test evidence before a fast-forward-only promotion and leaves branch deletion out of scope.

