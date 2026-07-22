# CAD Agent Quality Gates

## Supported release environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

## Authoritative local commands

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

`scripts/verify.ps1` owns lock/environment validation, the zero-skip offline
pytest selection, safe unavailable-state probes for both specialized markers,
Ruff F401, Git whitespace checks, the content-hash side-effect check, and three
JUnit outputs. CI calls the same scripts rather than copying the commands.

## Test classes

### `offline`

Deterministic tests that require no customer data and no running AutoCAD LT.
They gate every commit and pull request.

### `contract`

Repository-foundation tests under `tests/`. They validate dependency roles,
supported-environment metadata, shared scripts, CI immutability, documentation
routing, and review guidance. Contract tests are deterministic members of the
`offline` gate; the separate name identifies what they protect rather than a
separate pytest marker.

### `real_data`

Private image/PDF benchmarks marked `real_data`. Inputs remain outside Git and
are identified by SHA-256 plus an approved annotation record. If the input is
absent, pytest reports an explicit skip. Changes to calibration, OCR, geometry,
line merging, pattern recognition, or constraints require the affected private
benchmark before release.

Run an approved real-image gate with:

```powershell
$env:CAD_AGENT_REAL_IMAGE = 'C:\approved-data\drawing.png'
$env:CAD_AGENT_TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
& '.\.venv-py311\Scripts\python.exe' -m pytest -m real_data -ra
```

### `autocad_lt`

Live tests marked `autocad_lt`. They require AutoCAD LT, File IPC, the approved
dispatcher, and explicit environment variables. Without them, pytest reports an
explicit skip. File IPC, handle, block/component, live review, live repair, or
release changes require this gate.

```powershell
$env:CAD_AGENT_FILE_IPC = '1'
$env:CAD_AGENT_AUTOCAD_HWND = '<active-window-handle>'
$env:CAD_AGENT_AUTOCAD_LISP_PATH = 'C:\approved-tools\mcp_dispatch.lsp'
& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_lt -ra
```

The two angle-bracket values are operator-supplied runtime inputs, not committed
project configuration.

## Result states

- `PASS`: the named command returned exit code 0 and its assertions ran.
- `FAIL`: an assertion, prerequisite, lint, or integrity check failed.
- `SKIP`: pytest collected the gate but a declared external prerequisite was
  unavailable.
- `NOT RUN`: the command was not executed.

Skipped and not-run gates are never counted as passed.

## Warning policy

Unexpected warnings are errors. The only initial allowlist is the intentional
ROI-policy warning exercised inside `test_vision_client.py`; the allowlist is
scoped to that test module and message prefix. New broad warning suppressions
are not accepted.

## Finding severity

- **P0:** data loss, unsafe production mutation, secret disclosure, or output
  that can cause immediate harmful use. Blocks all release activity.
- **P1:** incorrect CAD geometry/scale, broken primary workflow, security flaw,
  or unrecoverable compatibility regression. Blocks merge and release.
- **P2:** bounded correctness, maintainability, performance, or observability
  defect with a safe workaround. May be deferred only with owner and reason.
- **P3:** low-impact cleanup or clarity improvement. Does not block release.

## Required evidence

Every verification record contains:

- exact command and exit code;
- commit SHA;
- Windows, Python, Tesseract, and relevant dependency versions;
- passed, failed, skipped, warning, and not-run states;
- private input SHA-256 when a real-data gate runs;
- AutoCAD LT/session identifiers when a live gate runs;
- artifact paths and remaining risks.

## Independent review tiers

- Small change: Codex plus one bounded Claude review.
- Medium-risk change: requirements/architecture review and correctness/test
  review.
- Calibration, geometry, File IPC, AutoCAD LT, architecture, or release:
  requirements/architecture, correctness/test, and security/operations reviews.

First-pass reviews are blind to each other. Findings require concrete scope,
impact, evidence, and a proposed verification. Numeric scores are not used.

## Merge and release gate

Before merge: focused tests, `scripts/verify.ps1`, `git diff --check`, scope
review, and no unresolved P0/P1.

Before a production AutoCAD LT run: private-data evidence when affected, live
smoke when affected, backup/rollback path, human approval, and a second review
after any repair.
