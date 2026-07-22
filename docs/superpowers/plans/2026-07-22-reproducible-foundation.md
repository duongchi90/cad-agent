# Reproducible Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Windows/Python 3.11 project foundation with one dependency lock, one verification entry point, canonical guidance, explicit private/live test gates, and immutable least-privilege CI.

**Architecture:** Preserve all five implementation packages and their schemas. Add a tooling/documentation shell around them: hashed Python locks feed a PowerShell bootstrap, a shared PowerShell verifier drives local and CI checks, and concise canonical documents replace overlapping status prose without deleting historical evidence.

**Tech Stack:** Windows PowerShell 5.1+, CPython 3.11, pip-tools 7.6.0, pytest, Ruff, GitHub Actions, Tesseract 5.4.0.20240606, Markdown/TOML/YAML.

**Status:** Planned

**Base SHA:** `c6bfbc3a8c867cfe7ffc5d78cae28f61fb3efb45`

**Completion Head SHA:** Not recorded until the final evidence commit exists.

**Verification command:** `scripts/verify.ps1`

**Verification result:** Not recorded until execution completes.

**Specialized gate result:** Not recorded until execution completes. This
foundation-only slice must collect `real_data` and `autocad_lt`
unavailable-state probes as `SKIP`, never execute either live gate.

## Global Constraints

- Preserve the current implementation and improve it incrementally; do not rewrite the project from scratch.
- Support Windows and AutoCAD LT only. Python 3.11 is the only supported runtime for this milestone.
- Do not build a GUI, web service, VPS deployment, or cross-platform AutoCAD integration.
- Do not change package APIs, schemas, recognition results, calibration behavior, DXF behavior, or AutoCAD LT File IPC behavior.
- Missing real data or AutoCAD LT must be reported as `SKIP` or `NOT RUN`, never as a pass.
- No secret, API key, customer drawing, private annotation, or unapproved DXF artifact may be committed.
- One writer owns overlapping files. Parallel agents are reserved for read-heavy exploration, tests, and independent review.
- Automatic calibration's future production gate remains: at least two independent candidates and median relative error at most 3 percent. This plan records the rule but does not alter calibration code.

## Execution Preflight

Run these checks from the repository root before Task 1:

```powershell
py -3.11 --version
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
git ls-files --error-unmatch docs/superpowers/plans/2026-07-22-reproducible-foundation.md
git status --short --branch
```

Expected: Python reports `3.11.x`, Tesseract's first line is
`tesseract v5.4.0.20240606`, the branch is
`codex/reproducible-foundation`, this plan is already tracked by its dedicated
pre-implementation documentation commit, and the working tree contains no
unrelated changes.

If Python 3.11 is absent, obtain user approval for the system installation, then
run:

```powershell
winget install --exact --id Python.Python.3.11 --source winget
```

Open a fresh PowerShell session and repeat `py -3.11 --version` before editing
repository files.

## File Responsibility Map

- `pyproject.toml`: supported-environment metadata plus central pytest/Ruff configuration.
- `requirements/*.in`: direct dependencies grouped by runtime role.
- `requirements/windows-py311.lock`: generated, hash-locked complete offline environment.
- `scripts/lock_contract.py`: atomically resolve/stamp the lock from its direct
  inputs and reject stale, unpinned, or unhashed requirement blocks.
- `scripts/check_environment.py`: reject missing, mismatched, or unexpected
  installed distributions and run `pip check`.
- `scripts/bootstrap.ps1`: validate prerequisites, create/reuse `.venv-py311`, install the lock.
- `scripts/verify.ps1`: validate lock/environment integrity, run the zero-skip
  offline gate, collect two safe unavailable-state probes, run Ruff/Git/content
  checks, and write three JUnit artifacts.
- `tests/test_*_contract.py`: lock the foundation's configuration, scripts, workflow, guidance, and documentation contracts.
- `AGENTS.md`: concise repository working agreement and definition of done.
- `CLAUDE.md`: thin Claude adapter that points at canonical sources.
- `docs/PROJECT.md`: product goal, supported scope, non-goals, and modernization slices.
- `docs/ARCHITECTURE.md`: current five-package data flow and boundaries.
- `docs/STATUS.md`: sole canonical verified/partial/unverified status ledger.
- `docs/QUALITY.md`: test classes, severity, evidence, review, and release gates.
- `docs/templates/*.md`: bounded task/review/adjudication/release packet formats.
- `README.md`: short human quick start and links to canonical documents.
- `HANDOFF.md`, `CAD-Agent-Kien-Truc-v1_3.md`: retained historical records with a canonical-source banner.
- `.github/workflows/tests.yml`: immutable, least-privilege Windows/Python 3.11 CI using shared scripts.

---

### Task 1: Dependency roles, Windows lock, and bootstrap

**Files:**
- Create: `tests/test_bootstrap_contract.py`
- Create: `requirements/runtime.in`
- Create: `requirements/vision.in`
- Create: `requirements/solver.in`
- Create: `requirements/dev.in`
- Create: `requirements/windows-py311.lock` (generated)
- Create: `scripts/lock_contract.py`
- Create: `scripts/check_environment.py`
- Create: `scripts/bootstrap.ps1`
- Modify: `requirements.txt:1-11`
- Modify: `primitive_ir_lib/requirements.txt:1-9`
- Modify: `.gitignore:1-34`

**Interfaces:**
- Consumes: an explicitly selected CPython 3.11 executable and Tesseract `5.4.0.20240606`.
- Produces: `scripts/bootstrap.ps1 -PythonExe $python311` and
  `.venv-py311\Scripts\python.exe`; later tasks use this interpreter.

- [ ] **Step 1: Write the failing bootstrap/dependency contract test**

Create `tests/test_bootstrap_contract.py`:

```python
from __future__ import annotations

import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootstrapContractTests(unittest.TestCase):
    def test_dependency_roles_are_explicit(self) -> None:
        runtime = (ROOT / "requirements/runtime.in").read_text(encoding="utf-8")
        vision = (ROOT / "requirements/vision.in").read_text(encoding="utf-8")
        solver = (ROOT / "requirements/solver.in").read_text(encoding="utf-8")
        dev = (ROOT / "requirements/dev.in").read_text(encoding="utf-8")
        root_shim = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        phase1_shim = (ROOT / "primitive_ir_lib/requirements.txt").read_text(encoding="utf-8")

        self.assertNotIn("anthropic", runtime.lower())
        self.assertNotIn("solvespace", runtime.lower())
        self.assertNotIn("pytest", runtime.lower())
        self.assertEqual("anthropic>=0.117", vision.strip())
        self.assertEqual("python-solvespace", solver.strip())
        self.assertIn("-r runtime.in", dev)
        self.assertIn("-r vision.in", dev)
        self.assertIn("-r solver.in", dev)
        self.assertIn("pip-tools==7.6.0", dev)
        self.assertIn("-r requirements/runtime.in", root_shim)
        self.assertIn("-r ../requirements/runtime.in", phase1_shim)

    def test_lock_is_current_fully_pinned_and_hashed(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/lock_contract.py"),
                "check",
                str(ROOT / "requirements/windows-py311.lock"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_bootstrap_checks_the_installed_environment(self) -> None:
        bootstrap = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")
        lock_guard = (ROOT / "scripts/lock_contract.py").read_text(encoding="utf-8")
        self.assertIn("lock_contract.py", bootstrap)
        self.assertIn("check_environment.py", bootstrap)
        self.assertIn('choices=("compile", "check")', lock_guard)
        self.assertNotIn('choices=("stamp", "check")', lock_guard)
        self.assertIn("generated_path.replace(lock_path)", lock_guard)

    def test_lock_stamp_rejects_a_changed_direct_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_requirements = Path(tmp)
            for name in (
                "runtime.in",
                "vision.in",
                "solver.in",
                "dev.in",
                "windows-py311.lock",
            ):
                shutil.copy2(ROOT / "requirements" / name, temporary_requirements / name)
            with (temporary_requirements / "runtime.in").open("a", encoding="utf-8") as stream:
                stream.write("\n# changed after lock generation\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/lock_contract.py"),
                    "check",
                    str(temporary_requirements / "windows-py311.lock"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("input digest is missing or stale", completed.stdout + completed.stderr)

    def test_bootstrap_rejects_a_non_311_interpreter(self) -> None:
        bootstrap = ROOT / "scripts/bootstrap.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            fake_python = Path(tmp) / "fake-python.cmd"
            fake_python.write_text("@echo 3.10\n", encoding="ascii")
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-File",
                    str(bootstrap),
                    "-PythonExe",
                    str(fake_python),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        output = completed.stdout + completed.stderr
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Python 3.11 is required", output)

    def test_bootstrap_never_deletes_an_existing_environment(self) -> None:
        bootstrap = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")
        self.assertNotIn("Remove-Item", bootstrap)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test and confirm the missing foundation fails**

Run:

```powershell
py -3.11 tests\test_bootstrap_contract.py -v
```

Expected: FAIL or ERROR because `requirements/runtime.in` and
`scripts/bootstrap.ps1` do not exist.

- [ ] **Step 3: Create the direct dependency inputs and compatibility shims**

Create `requirements/runtime.in`:

```text
opencv-python>=4.8
numpy>=1.24
pytesseract>=0.3.10
pillow>=10.0
pypdf>=5.0
PyMuPDF>=1.24
ezdxf>=1.4
```

Create `requirements/vision.in`:

```text
anthropic>=0.117
```

Create `requirements/solver.in`:

```text
python-solvespace
```

Create `requirements/dev.in`:

```text
-r runtime.in
-r vision.in
-r solver.in

pip-tools==7.6.0
pytest>=8.4,<10
ruff>=0.12,<1
```

Replace `requirements.txt` with:

```text
# Compatibility entry point for the complete offline runtime.
# Development and CI use requirements/windows-py311.lock.
-r requirements/runtime.in
```

Replace `primitive_ir_lib/requirements.txt` with:

```text
# Compatibility entry point. The canonical direct runtime dependencies live at
# requirements/runtime.in in the repository root.
-r ../requirements/runtime.in
```

Append these ignored generated paths to `.gitignore`:

```gitignore
.lock-venv/
.artifacts/
```

- [ ] **Step 4: Implement lock, environment, and bootstrap guards**

Create `scripts/lock_contract.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path


INPUT_NAMES = ("runtime.in", "vision.in", "solver.in", "dev.in")
STAMP_PREFIX = "# input-sha256: "
PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+==[^\s;\\]+(?:\s*;.*)?$")
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}\b")


def compute_input_digest(lock_path: Path) -> str:
    digest = hashlib.sha256()
    for name in INPUT_NAMES:
        input_path = lock_path.parent / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        normalized = input_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        normalized = normalized.replace("\r", "\n")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def requirement_blocks(lock_text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in lock_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current:
                current.append(line)
            continue
        if line.startswith("--"):
            continue
        if current:
            blocks.append(current)
        current = [line]
    if current:
        blocks.append(current)
    return blocks


def validate_lock(lock_path: Path) -> None:
    text = lock_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    expected_stamp = STAMP_PREFIX + compute_input_digest(lock_path)
    errors: list[str] = []
    if not lines or lines[0] != expected_stamp:
        errors.append("input digest is missing or stale; regenerate and stamp the lock")

    blocks = requirement_blocks(text)
    if not blocks:
        errors.append("lock contains no requirement blocks")
    for block in blocks:
        pin = block[0].removesuffix("\\").rstrip()
        if not PIN_RE.fullmatch(pin):
            errors.append(f"requirement is not an exact == pin: {pin}")
        if not HASH_RE.search(" ".join(block)):
            errors.append(f"requirement has no sha256 hash: {pin}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Lock contract PASS: {len(blocks)} pinned, hashed distributions")


def stamp_lock(lock_path: Path) -> None:
    text = lock_path.read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.startswith(STAMP_PREFIX)
    )
    stamped = f"{STAMP_PREFIX}{compute_input_digest(lock_path)}\n{body.rstrip()}\n"
    lock_path.write_text(stamped, encoding="utf-8")


def compile_lock(lock_path: Path) -> None:
    repo_root = lock_path.parent.parent
    generated_path = lock_path.with_name(lock_path.name + ".generated")
    generated_relative = generated_path.relative_to(repo_root)
    input_relative = (lock_path.parent / "dev.in").relative_to(repo_root)
    command = [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--resolver=backtracking",
        "--generate-hashes",
        "--allow-unsafe",
        "--strip-extras",
        "--output-file",
        str(generated_relative),
        str(input_relative),
    ]
    try:
        completed = subprocess.run(command, cwd=repo_root, check=False)
        if completed.returncode != 0:
            raise SystemExit(f"pip-compile failed with exit code {completed.returncode}")
        stamp_lock(generated_path)
        validate_lock(generated_path)
        generated_path.replace(lock_path)
    finally:
        if generated_path.exists():
            generated_path.unlink()
    validate_lock(lock_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("compile", "check"))
    parser.add_argument("lock", type=Path)
    args = parser.parse_args()
    lock_path = args.lock.resolve()
    if args.command == "compile":
        compile_lock(lock_path)
    validate_lock(lock_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `scripts/check_environment.py`:

```python
from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from lock_contract import requirement_blocks, validate_lock


PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)")
BOOTSTRAP_ALLOWLIST = {"pip", "setuptools", "wheel"}


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_versions(lock_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in requirement_blocks(lock_path.read_text(encoding="utf-8")):
        match = PIN_RE.match(block[0])
        if match is None:
            raise SystemExit(f"cannot parse locked requirement: {block[0]}")
        result[canonical_name(match.group(1))] = match.group(2)
    return result


def installed_versions() -> dict[str, str]:
    return {
        canonical_name(dist.metadata["Name"]): dist.version
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_environment.py LOCK_FILE")
    lock_path = Path(sys.argv[1]).resolve()
    validate_lock(lock_path)
    locked = locked_versions(lock_path)
    installed = installed_versions()

    missing = sorted(set(locked) - set(installed))
    extra = sorted(set(installed) - set(locked) - BOOTSTRAP_ALLOWLIST)
    mismatched = sorted(
        f"{name}: locked={locked[name]} installed={installed[name]}"
        for name in set(locked) & set(installed)
        if locked[name] != installed[name]
    )
    if missing or extra or mismatched:
        raise SystemExit(
            f"missing={missing}\nextra={extra}\nversion_mismatch={mismatched}"
        )

    completed = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stdout + completed.stderr)
    print(
        f"Environment contract PASS: {len(locked)} locked distributions; "
        f"bootstrap allowlist present={sorted(set(installed) & BOOTSTRAP_ALLOWLIST)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `scripts/bootstrap.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$lockFile = Join-Path $repoRoot "requirements\windows-py311.lock"
$venvDir = Join-Path $repoRoot ".venv-py311"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

$selectedVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $selectedVersion -ne "3.11") {
    throw "Python 3.11 is required; selected interpreter reported '$selectedVersion'. Pass -PythonExe with the full path to python.exe."
}

if (-not (Test-Path -LiteralPath $lockFile -PathType Leaf)) {
    throw "Dependency lock not found: $lockFile"
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $PythonExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create $venvDir with Python 3.11."
    }
}

$venvVersion = (& $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $venvVersion -ne "3.11") {
    throw "$venvDir exists but is not a Python 3.11 environment. Move it aside and rerun bootstrap."
}

& $venvPython -m pip install --disable-pip-version-check --require-hashes -r $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installing requirements/windows-py311.lock failed."
}

& $venvPython (Join-Path $repoRoot "scripts\lock_contract.py") check $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Dependency lock contract failed."
}
& $venvPython (Join-Path $repoRoot "scripts\check_environment.py") $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installed environment does not match the dependency lock."
}

$tesseractPath = $env:CAD_AGENT_TESSERACT_CMD
if (-not $tesseractPath) {
    $tesseractCommand = Get-Command "tesseract.exe" -ErrorAction SilentlyContinue
    if ($tesseractCommand) {
        $tesseractPath = $tesseractCommand.Source
    } else {
        $tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    }
}

if (-not (Test-Path -LiteralPath $tesseractPath -PathType Leaf)) {
    throw "Tesseract 5.4.0.20240606 is required. Set CAD_AGENT_TESSERACT_CMD or install it at C:\Program Files\Tesseract-OCR\tesseract.exe."
}

$tesseractVersion = (& $tesseractPath --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if ($tesseractVersion -ne "tesseract v5.4.0.20240606") {
    throw "Tesseract 5.4.0.20240606 is required; found '$tesseractVersion'."
}

Write-Host "Python: $venvPython ($venvVersion)"
Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"
Write-Host "Bootstrap complete."
```

- [ ] **Step 5: Generate the hash-locked Windows/Python 3.11 environment**

Run:

```powershell
py -3.11 -m venv .lock-venv
& '.\.lock-venv\Scripts\python.exe' -m pip install 'pip-tools==7.6.0'
& '.\.lock-venv\Scripts\python.exe' scripts\lock_contract.py `
  compile requirements\windows-py311.lock
```

Expected: `requirements/windows-py311.lock` is generated with a
current input SHA-256 stamp, a `pip-compile` header, exact `==` pins, and
`sha256` hashes; the only supported stamp path performs a fresh resolve before
atomically replacing the lock; the lock contract prints `PASS`.

- [ ] **Step 6: Bootstrap the target environment and run the contract test**

Run:

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
& '.\.venv-py311\Scripts\python.exe' tests\test_bootstrap_contract.py -v
Remove-Item Env:CAD_AGENT_REAL_IMAGE -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_FILE_IPC -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_HWND -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_LISP_PATH -ErrorAction SilentlyContinue
& '.\.venv-py311\Scripts\python.exe' -m pytest `
  primitive_ir_lib\tests semantic_ir_lib\tests dxf_builder_lib\tests `
  mcp_integration_lib\tests agent_lib\tests -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check `
  scripts\lock_contract.py scripts\check_environment.py `
  tests\test_bootstrap_contract.py --select F401
```

Expected: bootstrap prints Python `3.11` and Tesseract
`5.4.0.20240606`; all six bootstrap contracts and focused Ruff gate pass; the
existing full suite has zero failures/errors and no dependency-driven import error. The known
real-image print-and-return behavior is still fixed explicitly in Task 2.

- [ ] **Step 7: Commit Task 1**

```powershell
git add .gitignore requirements.txt primitive_ir_lib/requirements.txt requirements scripts/bootstrap.ps1 scripts/lock_contract.py scripts/check_environment.py tests/test_bootstrap_contract.py
git commit -m "build: lock Windows Python 3.11 environment"
```

### Task 2: Central pytest/Ruff policy and explicit specialized test states

**Files:**
- Create: `tests/test_project_configuration.py`
- Create: `pyproject.toml`
- Modify: `primitive_ir_lib/tests/test_real_image_benchmark.py:1-66`
- Modify: `primitive_ir_lib/tests/test_vision_client.py:1-20`
- Modify: `mcp_integration_lib/tests/test_file_ipc_e2e.py:1-31`
- Modify: `mcp_integration_lib/tests/test_file_ipc_live.py:1-11`

**Interfaces:**
- Consumes: `.venv-py311\Scripts\python.exe` from Task 1.
- Produces: registered `real_data` and `autocad_lt` pytest markers, warning-as-error policy, and central Ruff F401 scope used by `scripts/verify.ps1`.

- [ ] **Step 1: Write the failing project configuration test**

Create `tests/test_project_configuration.py`:

```python
from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "pyproject.toml").open("rb") as stream:
            cls.config = tomllib.load(stream)

    def test_supported_environment_is_exact(self) -> None:
        self.assertEqual(">=3.11,<3.12", self.config["project"]["requires-python"])
        environment = self.config["tool"]["cad_agent"]
        self.assertEqual("windows", environment["supported_os"])
        self.assertEqual("3.11", environment["supported_python"])
        self.assertEqual("AutoCAD LT", environment["supported_autocad"])
        self.assertEqual("5.4.0.20240606", environment["tesseract_version"])

    def test_pytest_registers_specialized_gates_and_errors_on_warnings(self) -> None:
        pytest_config = self.config["tool"]["pytest"]["ini_options"]
        marker_names = {entry.split(":", 1)[0] for entry in pytest_config["markers"]}
        self.assertEqual({"real_data", "autocad_lt"}, marker_names)
        self.assertIn("--strict-markers", pytest_config["addopts"])
        self.assertEqual(["error"], pytest_config["filterwarnings"])

    def test_ruff_scope_remains_the_existing_f401_gate(self) -> None:
        self.assertEqual("py311", self.config["tool"]["ruff"]["target-version"])
        self.assertEqual(["F401"], self.config["tool"]["ruff"]["lint"]["select"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm `pyproject.toml` is missing**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' tests\test_project_configuration.py -v
```

Expected: ERROR opening `pyproject.toml`.

- [ ] **Step 3: Add the central TOML configuration**

Create `pyproject.toml`:

```toml
[project]
name = "cad-agent"
version = "0.0.0"
requires-python = ">=3.11,<3.12"

[tool.cad_agent]
supported_os = "windows"
supported_python = "3.11"
supported_autocad = "AutoCAD LT"
tesseract_version = "5.4.0.20240606"

[tool.pytest.ini_options]
minversion = "8.4"
testpaths = [
  "tests",
  "primitive_ir_lib/tests",
  "semantic_ir_lib/tests",
  "dxf_builder_lib/tests",
  "mcp_integration_lib/tests",
  "agent_lib/tests",
]
addopts = ["--strict-markers", "-ra"]
markers = [
  "real_data: requires an approved private CAD image or PDF outside Git",
  "autocad_lt: requires a running local AutoCAD LT File IPC session",
]
filterwarnings = ["error"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["F401"]
```

- [ ] **Step 4: Mark specialized tests and make missing real data a true skip**

In `primitive_ir_lib/tests/test_real_image_benchmark.py`, add `import pytest`,
set the module marker, and replace the print-and-return branch:

```python
import pytest

pytestmark = pytest.mark.real_data


def test_real_scan_2760_1525_boundary_survives_full_merge():
    image_path = os.environ.get(_IMAGE_ENV)
    if not image_path:
        pytest.skip(f"set {_IMAGE_ENV} to run the real-image benchmark")
```

Keep the remainder of the existing test unchanged.

In both `mcp_integration_lib/tests/test_file_ipc_e2e.py` and
`mcp_integration_lib/tests/test_file_ipc_live.py`, add:

```python
import pytest

pytestmark = pytest.mark.autocad_lt
```

Keep the existing `unittest.skipUnless` guards; the marker classifies the gate,
while the guard produces an explicit skip when AutoCAD LT is unavailable.

- [ ] **Step 5: Allow only the three intentional ROI-policy warnings in their owning test module**

In `primitive_ir_lib/tests/test_vision_client.py`, add:

```python
import pytest

pytestmark = pytest.mark.filterwarnings(
    "ignore:extract_text_tesseract:UserWarning"
)
```

This prefix matches only the intentional `extract_text_tesseract()` ROI warning
exercised by this module; every other warning remains an error.

- [ ] **Step 6: Run focused configuration and state tests**

Run:

```powershell
Remove-Item Env:CAD_AGENT_REAL_IMAGE -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_FILE_IPC -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_HWND -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_LISP_PATH -ErrorAction SilentlyContinue
& '.\.venv-py311\Scripts\python.exe' -m pytest `
  tests\test_project_configuration.py `
  primitive_ir_lib\tests\test_real_image_benchmark.py `
  primitive_ir_lib\tests\test_vision_client.py `
  mcp_integration_lib\tests\test_file_ipc_live.py `
  -q
```

Expected: exit 0; the real-data test and unavailable AutoCAD LT test are listed
as skipped; no warning summary appears.

- [ ] **Step 7: Run the complete configured suite**

Run:

```powershell
$env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
Remove-Item Env:CAD_AGENT_REAL_IMAGE -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_FILE_IPC -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_HWND -ErrorAction SilentlyContinue
Remove-Item Env:CAD_AGENT_AUTOCAD_LISP_PATH -ErrorAction SilentlyContinue
& '.\.venv-py311\Scripts\python.exe' -m pytest `
  -m "not real_data and not autocad_lt" -q
& '.\.venv-py311\Scripts\python.exe' -m pytest -m real_data -q
& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_lt -q
```

Expected: all three commands exit 0; the offline command has zero
failures/errors/skips and zero unexpected warnings; each specialized command
collects its tests and reports every one as skipped.

- [ ] **Step 8: Commit Task 2**

```powershell
git add pyproject.toml tests/test_project_configuration.py primitive_ir_lib/tests/test_real_image_benchmark.py primitive_ir_lib/tests/test_vision_client.py mcp_integration_lib/tests/test_file_ipc_e2e.py mcp_integration_lib/tests/test_file_ipc_live.py
git commit -m "test: classify private and AutoCAD LT gates"
```

### Task 3: One verification command and immutable least-privilege CI

**Files:**
- Create: `tests/test_verification_contract.py`
- Create: `scripts/verify.ps1`
- Modify: `.github/workflows/tests.yml:1-27`

**Interfaces:**
- Consumes: `.venv-py311`, `pyproject.toml`, registered test markers, and the dependency lock from Tasks 1-2.
- Produces: `scripts/verify.ps1 -PythonExe $python311`, an offline JUnit plus
  two specialized unavailable-state JUnits under `.artifacts/test-results/`,
  and the only CI invocation path.

- [ ] **Step 1: Write the failing verification/workflow contract test**

Create `tests/test_verification_contract.py`:

```python
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
UPLOAD_ARTIFACT_SHA = "b7c566a772e6b6bfb58ed0dc250532a479d7789f"


class VerificationContractTests(unittest.TestCase):
    def test_verify_script_owns_all_checks(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        for test_root in (
            "tests",
            "primitive_ir_lib/tests",
            "semantic_ir_lib/tests",
            "dxf_builder_lib/tests",
            "mcp_integration_lib/tests",
            "agent_lib/tests",
        ):
            self.assertIn(test_root, script)
        self.assertIn("-m pytest", script)
        self.assertIn("-m ruff check", script)
        self.assertIn("git diff --check", script)
        self.assertIn("git diff --cached --check", script)
        self.assertIn("--junitxml", script)
        self.assertIn("importlib.metadata", script)
        self.assertIn("not real_data and not autocad_lt", script)
        self.assertIn("real-data-unavailable.xml", script)
        self.assertIn("autocad-lt-unavailable.xml", script)
        self.assertIn("check_environment.py", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("ls-files", script)
        self.assertIn('Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"', script)

    def test_workflow_is_pinned_and_least_privilege(self) -> None:
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", workflow)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_SHA}", workflow)
        self.assertIn(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", workflow)
        action_refs = re.findall(
            r"^\s*uses:\s*actions/[^@\s]+@([^\s#]+)", workflow, re.MULTILINE
        )
        self.assertEqual(3, len(action_refs))
        for ref in action_refs:
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(".\\scripts\\bootstrap.ps1 -PythonExe python", workflow)
        self.assertIn(".\\scripts\\verify.ps1", workflow)
        self.assertIn("path: .artifacts/test-results/", workflow)
        self.assertNotIn("python -m pytest primitive_ir_lib", workflow)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and confirm the shared verifier is missing**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_verification_contract.py -q
```

Expected: FAIL because `scripts/verify.ps1` does not exist and the workflow
still uses mutable action tags.

- [ ] **Step 3: Implement the shared verifier**

Create `scripts/verify.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $PythonExe) {
    $PythonExe = Join-Path $repoRoot ".venv-py311\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python environment not found: $PythonExe. Run scripts/bootstrap.ps1 first."
}

$pythonVersion = (& $PythonExe -c "import sys; print(sys.version.split()[0])" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch '^3\.11\.\d+$') {
    throw "Verification requires Python 3.11; found '$pythonVersion'."
}

$lockFile = Join-Path $repoRoot "requirements\windows-py311.lock"
& $PythonExe (Join-Path $repoRoot "scripts\lock_contract.py") check $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Dependency lock contract failed."
}
& $PythonExe (Join-Path $repoRoot "scripts\check_environment.py") $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Installed environment does not match the dependency lock."
}

$dependencyProbe = "from importlib.metadata import version; names = ['numpy', 'opencv-python', 'pytesseract', 'Pillow', 'pypdf', 'PyMuPDF', 'ezdxf', 'anthropic', 'python-solvespace', 'pytest', 'ruff']; print('; '.join(f'{name}={version(name)}' for name in names))"
$dependencyVersions = (& $PythonExe -c $dependencyProbe | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Reading locked dependency versions failed."
}

$tesseractPath = $env:CAD_AGENT_TESSERACT_CMD
if (-not $tesseractPath) {
    $tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
}
if (-not (Test-Path -LiteralPath $tesseractPath -PathType Leaf)) {
    throw "Tesseract executable not found: $tesseractPath"
}
$tesseractVersion = (& $tesseractPath --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if ($tesseractVersion -ne "tesseract v5.4.0.20240606") {
    throw "Verification requires Tesseract 5.4.0.20240606; found '$tesseractVersion'."
}

function Get-RepositorySnapshot {
    $paths = @(& git -C $repoRoot -c core.quotepath=false `
        ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed while building the side-effect snapshot."
    }
    $entries = foreach ($relativePath in $paths) {
        $fullPath = Join-Path $repoRoot $relativePath
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $hash = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
            "$relativePath=$hash"
        }
    }
    return @($entries | Sort-Object)
}

function Get-JUnitTotals {
    param([string]$Path)
    [xml]$junit = Get-Content -LiteralPath $Path -Raw
    $suites = @($junit.testsuites.testsuite)
    return [pscustomobject]@{
        Tests = ($suites | ForEach-Object { [int]$_.tests } | Measure-Object -Sum).Sum
        Failures = ($suites | ForEach-Object { [int]$_.failures } | Measure-Object -Sum).Sum
        Errors = ($suites | ForEach-Object { [int]$_.errors } | Measure-Object -Sum).Sum
        Skipped = ($suites | ForEach-Object { [int]$_.skipped } | Measure-Object -Sum).Sum
    }
}

function Invoke-PytestGate {
    param(
        [string]$Name,
        [string]$MarkerExpression,
        [string]$JUnitPath,
        [ValidateSet("offline", "all-skipped")]
        [string]$ExpectedState
    )
    & $PythonExe -m pytest @testTargets -q -m $MarkerExpression `
        "--junitxml=$JUnitPath"
    if ($LASTEXITCODE -ne 0) {
        throw "$Name pytest gate failed with exit code $LASTEXITCODE."
    }
    $totals = Get-JUnitTotals -Path $JUnitPath
    if ($totals.Tests -le 0 -or $totals.Failures -ne 0 -or $totals.Errors -ne 0) {
        throw "$Name produced invalid JUnit totals: $($totals | Out-String)"
    }
    if ($ExpectedState -eq "offline" -and $totals.Skipped -ne 0) {
        throw "Offline gate contains $($totals.Skipped) unexpected skips."
    }
    if ($ExpectedState -eq "all-skipped" -and $totals.Skipped -ne $totals.Tests) {
        throw "$Name must report every collected test as skipped when prerequisites are absent."
    }
    Write-Host "$Name JUnit: tests=$($totals.Tests) failures=$($totals.Failures) errors=$($totals.Errors) skipped=$($totals.Skipped)"
}

$snapshotBefore = Get-RepositorySnapshot
$artifactDir = Join-Path $repoRoot ".artifacts\test-results"
$junitPath = Join-Path $artifactDir "junit.xml"
$realDataJunitPath = Join-Path $artifactDir "real-data-unavailable.xml"
$autocadJunitPath = Join-Path $artifactDir "autocad-lt-unavailable.xml"
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

$tesseractDir = Split-Path -Parent $tesseractPath
$originalPath = $env:PATH
$env:PATH = "$tesseractDir;$env:PATH"
$testTargets = @(
    "tests",
    "primitive_ir_lib/tests",
    "semantic_ir_lib/tests",
    "dxf_builder_lib/tests",
    "mcp_integration_lib/tests",
    "agent_lib/tests"
)

Push-Location $repoRoot
try {
    Invoke-PytestGate `
        -Name "offline" `
        -MarkerExpression "not real_data and not autocad_lt" `
        -JUnitPath $junitPath `
        -ExpectedState "offline"

    $specializedVariables = @(
        "CAD_AGENT_REAL_IMAGE",
        "CAD_AGENT_FILE_IPC",
        "CAD_AGENT_AUTOCAD_HWND",
        "CAD_AGENT_AUTOCAD_LISP_PATH"
    )
    $savedEnvironment = @{}
    foreach ($name in $specializedVariables) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($null -ne $value) {
            $savedEnvironment[$name] = $value
        }
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
    try {
        Invoke-PytestGate `
            -Name "real_data unavailable-state probe" `
            -MarkerExpression "real_data" `
            -JUnitPath $realDataJunitPath `
            -ExpectedState "all-skipped"
        Invoke-PytestGate `
            -Name "autocad_lt unavailable-state probe" `
            -MarkerExpression "autocad_lt" `
            -JUnitPath $autocadJunitPath `
            -ExpectedState "all-skipped"
    } finally {
        foreach ($name in $specializedVariables) {
            $value = if ($savedEnvironment.ContainsKey($name)) {
                $savedEnvironment[$name]
            } else {
                $null
            }
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }

    $lintTargets = @(
        "primitive_ir_lib",
        "semantic_ir_lib",
        "dxf_builder_lib",
        "mcp_integration_lib",
        "agent_lib",
        "tests",
        "scripts"
    )
    & $PythonExe -m ruff check @lintTargets
    if ($LASTEXITCODE -ne 0) {
        throw "Ruff failed with exit code $LASTEXITCODE."
    }

    & git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --check failed."
    }
    & git diff --cached --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --cached --check failed."
    }
} finally {
    Pop-Location
    $env:PATH = $originalPath
}

$snapshotAfter = Get-RepositorySnapshot
if (($snapshotBefore -join "`n") -ne ($snapshotAfter -join "`n")) {
    throw "Verification changed a tracked or non-ignored file. Inspect git status and content hashes."
}

Write-Host "Python: $pythonVersion"
Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"
Write-Host "Dependencies: $dependencyVersions"
Write-Host "Offline JUnit: $junitPath"
Write-Host "Unavailable-state JUnit: $realDataJunitPath; $autocadJunitPath"
Write-Host "Verification complete."
```

- [ ] **Step 4: Replace the workflow with the shared-script CI**

Replace `.github/workflows/tests.yml` with:

```yaml
name: tests

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  offline-tests:
    runs-on: windows-latest
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0
        with:
          persist-credentials: false

      - name: Set up Python 3.11
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: requirements/windows-py311.lock

      - name: Install Tesseract 5.4.0
        run: choco install tesseract --version=5.4.0.20240606 --no-progress -y

      - name: Bootstrap locked environment
        run: .\scripts\bootstrap.ps1 -PythonExe python

      - name: Run authoritative verification
        run: .\scripts\verify.ps1

      - name: Upload test evidence
        if: always()
        uses: actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f # v6.0.0
        with:
          name: windows-py311-test-results
          path: .artifacts/test-results/
          if-no-files-found: error
```

- [ ] **Step 5: Run the workflow contract**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_verification_contract.py -q
```

Expected: both contract tests pass.

- [ ] **Step 6: Run the authoritative verifier locally**

Run:

```powershell
.\scripts\verify.ps1
Test-Path -LiteralPath '.artifacts\test-results\junit.xml'
Test-Path -LiteralPath '.artifacts\test-results\real-data-unavailable.xml'
Test-Path -LiteralPath '.artifacts\test-results\autocad-lt-unavailable.xml'
```

Expected: the offline JUnit has zero failures/errors/skips; the `real_data` and
`autocad_lt` probe JUnits contain only explicit skips; Ruff, both Git diff
checks, the lock/environment checks, and the content-hash side-effect check
pass; `Verification complete.` is printed; all three `Test-Path` calls return
`True`.

- [ ] **Step 7: Commit Task 3**

```powershell
git add .github/workflows/tests.yml scripts/verify.ps1 tests/test_verification_contract.py
git commit -m "ci: share locked Windows verification"
```

### Task 4: Canonical product and architecture documents

**Files:**
- Create: `tests/test_documentation_contract.py`
- Create: `docs/PROJECT.md`
- Create: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: the approved design spec and actual five-package repository structure.
- Produces: stable product/scope and architecture links used by status, quality, README, AGENTS, and Claude guidance.

- [ ] **Step 1: Write the failing product/architecture documentation contract**

Create `tests/test_documentation_contract.py`:

```python
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_project_document_records_the_approved_scope(self) -> None:
        project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("Windows", project)
        self.assertIn("Python 3.11", project)
        self.assertIn("AutoCAD LT", project)
        self.assertIn("No GUI, web service, or VPS", project)
        self.assertIn("Incremental hardening", project)

    def test_architecture_names_every_package_and_schema(self) -> None:
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        for package in (
            "primitive_ir_lib",
            "semantic_ir_lib",
            "agent_lib",
            "dxf_builder_lib",
            "mcp_integration_lib",
        ):
            self.assertIn(package, architecture)
        for schema in (
            "primitive_ir.schema.json",
            "semantic_ir.schema.json",
            "agent_ir.schema.json",
        ):
            self.assertIn(schema, architecture)
        self.assertIn("cad_agent", architecture)
        self.assertIn("not implemented in this slice", architecture)
        self.assertIn("detected constraints only", architecture)
        self.assertIn("PruneResult", architecture)
        self.assertIn("SolveResult", architecture)
        self.assertIn("agent_lib.run", architecture)
        self.assertIn("automatically calls `apply_agent_report()`", architecture)
        self.assertIn("not an approved production mutation path", architecture)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and confirm both canonical files are missing**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py -q
```

Expected: both tests fail opening `docs/PROJECT.md` and
`docs/ARCHITECTURE.md`.

- [ ] **Step 3: Create the canonical project document**

Create `docs/PROJECT.md`:

```markdown
# CAD Agent Project

## Goal

Convert an approved real CAD image or PDF into a reviewable DXF, validate it
headlessly, open it in AutoCAD LT, and produce reproducible evidence for every
stage.

## Supported environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

Other operating systems, Python versions, and full AutoCAD may work in parts,
but they are not release evidence for this project.

## Product principles

- Incremental hardening: preserve verified code and refactor only against a
  failing test, benchmark, or measured integration problem.
- Deterministic rules first; AI supports ambiguous recognition and review.
- Human approval is mandatory for unverified calibration, ambiguous decisions,
  and production DXF mutation.
- Private drawings and annotations remain outside Git.
- A missing private/live gate is reported as skipped or not run, never passed.

## First product milestone

One approved real image or PDF runs through Primitive IR, Semantic IR, optional
agent advice, DXF build/headless review, and AutoCAD LT live review/repair. The
run records input hash, configuration, artifacts, approvals, and test evidence.

## Modernization slices

1. Reproducible foundation: canonical guidance, locked environment, shared
   verification, explicit gates, and immutable CI.
2. Thin vertical-slice CLI: `doctor`, `run`, and `resume`, with manifests,
   checkpoints, approval gates, and no duplicated domain algorithms.
3. Private real-data benchmark normalization and evidence-driven algorithm
   hardening.
4. Windows/AutoCAD LT production review-repair loop, backup policy, live smoke,
   and release checklist.

Each slice receives its own approved design, implementation plan, tests, and
review gate.

## Non-goals

- No GUI, web service, or VPS.
- No Linux or macOS production support.
- No full AutoCAD support commitment.
- No rewrite of the five existing implementation packages.
- No automatic production mutation without human approval.

## Canonical reference

- Current architecture: `docs/ARCHITECTURE.md`
```

- [ ] **Step 4: Create the canonical architecture document**

Create `docs/ARCHITECTURE.md`:

````markdown
# CAD Agent Architecture

## Current data flow

```text
Image/PDF
  -> primitive_ir_lib       (geometry, text, tables, calibration -> Primitive IR)
  -> semantic_ir_lib        (parts, compounds, constraints, pruning, solving)
  -> agent_lib              (optional audited advice for ambiguous cases)
  -> dxf_builder_lib        (DXF build -> headless review -> headless repair)
  -> mcp_integration_lib    (AutoCAD LT live review/repair through File IPC)
```

The phase number is not the call order in every entry point. In particular,
`agent_lib` may advise between semantic analysis and DXF generation.

## Package boundaries

### `primitive_ir_lib`

Consumes images or rendered PDF pages. Produces `PrimitiveIRDocument` with
geometry, text, source trace, confidence, and calibration. `run_image.py` and
`run_pdf.py` are file-oriented entry points. Calibration that has not been
human-verified must not be reused as verified production scale.

### `semantic_ir_lib`

Consumes Primitive IR. Produces `SemanticIRDocument` containing
single-primitive parts, compound parts, and detected constraints only.
`prune_constraints()` returns a separate `PruneResult`; `solve_constraints()`
returns a separate `SolveResult` with `solved_primitives`. Neither result is
automatically written back into `SemanticIRDocument`.

### `agent_lib`

Consumes ambiguous Primitive/Semantic IR plus optional image evidence.
`run_agent()` produces an `AgentReport` without mutating the IR, and
`apply_agent_report()` is the separate mutation API. The existing
`agent_lib.run` and demo entry points automatically call `apply_agent_report()`
for all returned actions without a human approval prompt; they are not an
approved production mutation path. This foundation records that boundary and
does not change the behavior.

### `dxf_builder_lib`

Consumes Primitive IR, optional solved coordinates, and Semantic IR. Builds DXF
with handles and semantic layers/components. Reviewer #1 checks translation from
intended IR/build output to DXF; Repair #1 fixes confirmed translation defects
and is followed by another review.

### `mcp_integration_lib`

Connects the built DXF to AutoCAD LT through a live client or File IPC. Reviewer
#2 and Repair #2 operate on AutoCAD-side entities by handle. Live tests require
an explicit local AutoCAD LT session and never run silently in ordinary CI.

## Contracts

- `primitive_ir.schema.json`: primitive geometry/text/calibration contract.
- `semantic_ir.schema.json`: semantic parts and constraints contract.
- `agent_ir.schema.json`: proposed actions and audit-trail contract.
- DXF entity handles connect build evidence to headless and AutoCAD LT review.

Each phase writes or accepts a stable artifact so a later phase can be rerun
without reprocessing the original image.

## Safety boundaries

- Unverified calibration or ambiguous recognition stops at a human approval
  boundary.
- Headless review/repair completes before AutoCAD LT mutation.
- Production DXF repair requires a backup and explicit user approval.
- Real drawings, private annotations, credentials, and API keys stay outside
  Git.

## Planned orchestrator boundary

A thin `cad_agent` package will eventually own environment checks, run
manifests, checkpoints, approvals, resumability, and evidence reports. It will
call the package APIs above and contain no recognition or CAD algorithms. It is
not implemented in this slice.

## Historical reference

`CAD-Agent-Kien-Truc-v1_3.md` and `HANDOFF.md` preserve detailed implementation
history. They are evidence, not the current status ledger.
````

- [ ] **Step 5: Run documentation and authoritative verification**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py -q
.\scripts\verify.ps1
```

Expected: the two documentation tests pass and authoritative verification exits
0 without changing repository status.

- [ ] **Step 6: Commit Task 4**

```powershell
git add docs/PROJECT.md docs/ARCHITECTURE.md tests/test_documentation_contract.py
git commit -m "docs: define canonical project architecture"
```

### Task 5: Canonical status/quality ledger and concise quick start

**Files:**
- Create: `docs/STATUS.md`
- Create: `docs/QUALITY.md`
- Create: `docs/superpowers/README.md`
- Modify: `docs/PROJECT.md`
- Modify: `tests/test_documentation_contract.py`
- Replace: `README.md:1-end`
- Modify: `HANDOFF.md:1-6`
- Modify: `CAD-Agent-Kien-Truc-v1_3.md:1-6`

**Interfaces:**
- Consumes: `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, the pre-foundation baseline, and `scripts/bootstrap.ps1`/`scripts/verify.ps1`.
- Produces: the only current status ledger, quality-gate definitions, a short quick start, and explicit historical-document routing.

- [ ] **Step 1: Extend the documentation contract with failing status/quality checks**

Add `import re` beside the existing standard-library imports, then add these
methods to `DocumentationContractTests` in
`tests/test_documentation_contract.py`:

```python
    def test_status_is_evidence_based(self) -> None:
        status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        self.assertIn("908d016", status)
        self.assertIn("255 passed, 11 skipped, 3 warnings", status)
        self.assertIn("Verified", status)
        self.assertIn("Partially verified", status)
        self.assertIn("Unverified", status)
        self.assertIn("NOT RUN", status)

    def test_quality_defines_every_required_gate(self) -> None:
        quality = (ROOT / "docs/QUALITY.md").read_text(encoding="utf-8")
        for term in (
            "offline",
            "contract",
            "real_data",
            "autocad_lt",
            "P0",
            "P1",
            "P2",
            "P3",
            "scripts/verify.ps1",
            "human approval",
        ):
            self.assertIn(term, quality)

    def test_readme_is_a_short_router_without_evergreen_test_counts(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(readme.splitlines()), 120)
        self.assertIn("docs/PROJECT.md", readme)
        self.assertIn("docs/ARCHITECTURE.md", readme)
        self.assertIn("docs/STATUS.md", readme)
        self.assertIn("docs/QUALITY.md", readme)
        self.assertNotIn("57/57", readme)
        self.assertNotIn("220 passed", readme)

    def test_current_documents_agree_on_environment_command_and_gate_states(self) -> None:
        documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/STATUS.md", "docs/QUALITY.md")
        }
        for path, content in documents.items():
            for term in (
                "Supported release environment",
                "Windows",
                "Python 3.11",
                "AutoCAD LT",
                "Tesseract 5.4.0.20240606",
                r".\scripts\verify.ps1",
                "`real_data`",
                "`autocad_lt`",
                "SKIP",
                "NOT RUN",
            ):
                self.assertIn(term, content, f"{term!r} missing from {path}")

    def test_plan_checkboxes_are_not_treated_as_current_status(self) -> None:
        planning = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
        self.assertIn("Unchecked boxes are not status evidence", planning)
        self.assertIn("Base SHA", planning)
        self.assertIn("Completion Head SHA", planning)
        self.assertIn("docs/STATUS.md", planning)

    def test_project_routes_to_current_status_and_quality(self) -> None:
        project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("docs/STATUS.md", project)
        self.assertIn("docs/QUALITY.md", project)
        self.assertIn("docs/superpowers/README.md", project)

    def test_historical_documents_route_to_canonical_sources(self) -> None:
        for relative_path in ("HANDOFF.md", "CAD-Agent-Kien-Truc-v1_3.md"):
            opening = "\n".join(
                (ROOT / relative_path).read_text(encoding="utf-8").splitlines()[:8]
            )
            self.assertIn("Historical record", opening)
            self.assertIn("docs/STATUS.md", opening)
            self.assertIn("docs/ARCHITECTURE.md", opening)

    def test_foundation_certificate_is_well_formed_when_present(self) -> None:
        status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        if "## Foundation certificate" not in status:
            self.assertIn("| Reproducible foundation | Unverified |", status)
            return

        certificate = status.split("## Foundation certificate", 1)[1]
        review_path = ROOT / "docs/reviews/2026-07-22-reproducible-foundation.md"
        review = review_path.read_text(encoding="utf-8")
        for term in (
            "State: **Verified**",
            "Exit code: `0`",
            "Python: `3.11.",
            "Tesseract executable:",
            "Dependencies:",
            "Offline JUnit:",
            "`real_data`: `SKIP`",
            "`autocad_lt`: `SKIP`",
            "Unexpected warnings: `0`",
            "Remaining risks:",
            "docs/reviews/2026-07-22-reproducible-foundation.md",
        ):
            self.assertIn(term, certificate)
        certificate_head = certificate.split(
            "Reviewed implementation Head SHA: `", 1
        )[1].split("`", 1)[0]
        review_head = review.split("Candidate Head SHA: `", 1)[1].split("`", 1)[0]
        self.assertRegex(certificate_head, r"^[0-9a-f]{40}$")
        self.assertEqual(certificate_head, review_head)
        self.assertRegex(
            certificate,
            r"Offline JUnit: `tests=\d+; failures=0; errors=0; skipped=0`",
        )
        for marker in ("real_data", "autocad_lt"):
            totals = re.search(
                rf"`{marker}`: `SKIP`.*`tests=(\d+); skipped=(\d+)`",
                certificate,
            )
            self.assertIsNotNone(totals)
            self.assertGreater(int(totals.group(1)), 0)
            self.assertEqual(totals.group(1), totals.group(2))
        self.assertGreaterEqual(len(re.findall(r"\b[0-9a-f]{64}\b", review.lower())), 7)
        self.assertIn("Unresolved P0/P1: `0`", review)

    def test_plan_lifecycle_metadata_is_well_formed(self) -> None:
        plan = (
            ROOT
            / "docs/superpowers/plans/2026-07-22-reproducible-foundation.md"
        ).read_text(encoding="utf-8")
        status_match = re.search(r"\*\*Status:\*\* (Planned|Completed)", plan)
        self.assertIsNotNone(status_match)
        self.assertIn("**Verification command:** `scripts/verify.ps1`", plan)
        if status_match.group(1) == "Completed":
            self.assertRegex(
                plan,
                r"\*\*Completion Head SHA:\*\* `[0-9a-f]{40}`",
            )
            self.assertIn("**Verification result:** `PASS`", plan)
            self.assertIn("`real_data`: `SKIP` probe, live gate `NOT RUN`", plan)
            self.assertIn("`autocad_lt`: `SKIP` probe, live gate `NOT RUN`", plan)
        else:
            self.assertIn(
                "Completion Head SHA:** Not recorded until the final evidence commit exists.",
                plan,
            )
            self.assertIn(
                "**Verification result:** Not recorded until execution completes.",
                plan,
            )
```

- [ ] **Step 2: Run the extended contract and confirm canonical files/routing are absent**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py -q
```

Expected: the existing project/architecture tests pass; the new status, quality,
plan-metadata, project-routing, README-length, and historical-routing tests fail.

- [ ] **Step 3: Create the evidence-based status ledger**

Create `docs/STATUS.md`:

```markdown
# CAD Agent Status

## Status vocabulary

- **Verified:** the named command ran successfully on the named commit and
  environment.
- **Partially verified:** deterministic coverage passed, but a required private
  data or AutoCAD LT gate has not run on the same candidate.
- **Unverified:** no current reproducible evidence supports the claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

## Authoritative verification

After bootstrap, run `.\scripts\verify.ps1`. It runs the offline gate and
collects unavailable-state probes for `real_data` and `autocad_lt` as explicit
`SKIP` results with prerequisites removed. A real private-data or live AutoCAD
LT gate that was not separately executed remains `NOT RUN`.

## Pre-foundation baseline

| State | Date | Commit | Environment | Command | Result |
|---|---|---|---|---|---|
| Verified | 2026-07-22 | `908d016` | Windows, bundled Python 3.12.13, Tesseract 5.4.0.20240606 | `python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q -p no:cacheprovider` | `255 passed, 11 skipped, 3 warnings` |

This baseline demonstrates that the existing core is worth preserving. It is
not the Python 3.11 foundation certificate because seven solver tests were among
the skips and the run used Python 3.12.

## Current module status

| Area | State | Evidence and limit |
|---|---|---|
| Primitive IR | Partially verified | Offline tests passed in the pre-foundation baseline. The approved private real-image gate was NOT RUN. |
| Semantic IR | Partially verified | Offline logic passed; solver-dependent coverage was skipped in the pre-foundation environment. |
| DXF build/review/repair | Verified | `ezdxf`-backed offline tests passed in the pre-foundation baseline. |
| MCP/File IPC | Partially verified | Fake/offline MCP tests passed. AutoCAD LT live smoke was NOT RUN on the current candidate. |
| Agent advice/audit | Partially verified | Offline agent tests passed; `run_agent()` is non-mutating, but current run/demo entry points auto-apply reports without a human approval prompt and are not approved production mutation paths. |
| Reproducible foundation | Unverified | Certification requires `scripts/verify.ps1` on the completed foundation head using Windows/Python 3.11. |

## Known production gates

- Calibration may be auto-accepted only with at least two independent
  candidates and median relative error at most 3 percent. Current production
  callers must opt into consensus and retain human approval for unverified
  scale.
- Private drawing benchmarks remain outside Git and are addressed by SHA-256.
- AutoCAD LT mutation requires backup, human approval, live review, repair, and
  a second review.

## Next slice

After the foundation is certified, design and implement the thin `cad_agent`
vertical-slice CLI with manifests, checkpoints, approval gates, and resumability.
```

- [ ] **Step 4: Create the canonical quality and release gates**

Create `docs/QUALITY.md`:

````markdown
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
````

- [ ] **Step 5: Define how plans record execution evidence**

Create `docs/superpowers/README.md`:

```markdown
# Design and Implementation Records

Files under `specs/` and `plans/` record approved intent at a point in time.
They do not replace the current ledger in `docs/STATUS.md`.

## Historical plans

Plans created before this foundation may contain unchecked boxes even when Git
history shows that some or all work shipped. Unchecked boxes are not status
evidence. Do not infer completion and do not bulk-check historical boxes without
fresh command and commit evidence.

## New record requirements

Every new design records approval date and supported scope. Every new
implementation plan records:

- Status: planned, executing, completed, or superseded
- Base SHA
- Completion Head SHA when completed
- Exact verification command and result
- Required private/live gates and whether each passed, skipped, or was not run

`Completion Head SHA` means the final implementation/evidence commit immediately
before a plan-only lifecycle-closing commit. This avoids asking a commit to
contain its own SHA.

When implementation completes, add the evidence to `docs/STATUS.md`; retain the
plan as the execution record.
```

- [ ] **Step 6: Link the project document to the newly created ledgers**

Replace the final `Canonical reference` section in `docs/PROJECT.md` with:

```markdown
## Canonical references

- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Quality and release gates: `docs/QUALITY.md`
- Design/plan record policy: `docs/superpowers/README.md`
```

- [ ] **Step 7: Replace README with the supported quick start**

Replace `README.md` with:

````markdown
# CAD Agent

CAD Agent converts CAD images/PDFs into structured IR and DXF, then validates
the result headlessly and through AutoCAD LT.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

## Quick start

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

The bootstrap creates/reuses `.venv-py311` and installs the hash-locked
`requirements/windows-py311.lock`. Verification rejects a stale/polluted
environment, runs the offline suite with zero skips, safely probes both
specialized markers as unavailable, runs Ruff/Git/content checks, and writes
three JUnit artifacts under `.artifacts/`.

## Packages

- `primitive_ir_lib/`: image/PDF to Primitive IR.
- `semantic_ir_lib/`: parts, compounds, constraints, pruning, and solving.
- `agent_lib/`: audited advice for ambiguous cases.
- `dxf_builder_lib/`: DXF build, headless review, and headless repair.
- `mcp_integration_lib/`: AutoCAD LT live review/repair through File IPC.

## Safety

Private drawings and annotations stay outside Git. Missing private/live tests are
reported as `SKIP` or `NOT RUN`. The specialized markers are `real_data` and
`autocad_lt`; `.\scripts\verify.ps1` probes their unavailable state but never
executes either live gate. Unverified calibration, ambiguous recognition, and
production DXF mutation require human approval.

## Canonical documentation

- Product and scope: `docs/PROJECT.md`
- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Test and release gates: `docs/QUALITY.md`

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are retained as historical
records; they are not current status sources.
````

- [ ] **Step 8: Add canonical-source banners to both historical records**

Insert this block at line 1 of both `HANDOFF.md` and
`CAD-Agent-Kien-Truc-v1_3.md`, leaving all historical content below it intact:

```markdown
> [!IMPORTANT]
> **Historical record.** Current architecture is maintained in
> `docs/ARCHITECTURE.md`; current verified status and operating gates are in
> `docs/STATUS.md` and `docs/QUALITY.md`. Preserve the material below as dated
> implementation evidence, not as the source of current project truth.

```

- [ ] **Step 9: Run documentation and full verification**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py -q
.\scripts\verify.ps1
```

Expected: every documentation contract passes; full verification exits 0 and
creates no repository-status delta.

- [ ] **Step 10: Commit Task 5**

```powershell
git add README.md HANDOFF.md CAD-Agent-Kien-Truc-v1_3.md docs/PROJECT.md docs/STATUS.md docs/QUALITY.md docs/superpowers/README.md tests/test_documentation_contract.py
git commit -m "docs: establish canonical status and quality gates"
```

### Task 6: Durable agent contract and bounded review packets

**Files:**
- Create: `tests/test_guidance_contract.py`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `docs/templates/TASK_BRIEF.md`
- Create: `docs/templates/REVIEW_PACKET.md`
- Create: `docs/templates/REVIEW_FINDING.md`
- Create: `docs/templates/ADJUDICATION.md`
- Create: `docs/templates/RELEASE_CHECKLIST.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all four canonical documents and shared scripts from Tasks 1-5.
- Produces: automatically loaded repository guidance plus compact manual packets for the user's three Claude Free reviewer sessions.

- [ ] **Step 1: Write the failing guidance contract test**

Create `tests/test_guidance_contract.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GuidanceContractTests(unittest.TestCase):
    def test_agents_is_concise_and_routes_to_canonical_sources(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(agents.splitlines()), 160)
        for reference in (
            "docs/PROJECT.md",
            "docs/ARCHITECTURE.md",
            "docs/STATUS.md",
            "docs/QUALITY.md",
            "scripts/bootstrap.ps1",
            "scripts/verify.ps1",
        ):
            self.assertIn(reference, agents)
        self.assertIn("one writer", agents.lower())
        self.assertIn("human approval", agents.lower())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Agent working agreement: `AGENTS.md`", readme)

    def test_claude_adapter_is_thin_and_forbids_status_invention(self) -> None:
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(claude.splitlines()), 40)
        self.assertIn("AGENTS.md", claude)
        self.assertIn("docs/STATUS.md", claude)
        self.assertIn("Do not infer", claude)
        self.assertIn("review packet", claude.lower())

    def test_every_review_template_has_its_required_contract(self) -> None:
        requirements = {
            "TASK_BRIEF.md": ("Task ID", "Acceptance criteria", "Risk tier", "Base SHA"),
            "REVIEW_PACKET.md": (
                "Base SHA",
                "Head SHA",
                "Test evidence",
                "Diff scope",
                "self-contained",
                "SHA-256",
            ),
            "REVIEW_FINDING.md": ("Finding ID", "Severity", "Evidence", "Reproduction"),
            "ADJUDICATION.md": ("Decision", "Reason", "Owner", "Verification"),
            "RELEASE_CHECKLIST.md": ("Rollback", "Human approval", "P0/P1", "Head SHA"),
        }
        for file_name, required_terms in requirements.items():
            content = (ROOT / "docs/templates" / file_name).read_text(encoding="utf-8")
            for term in required_terms:
                self.assertIn(term, content, f"{term!r} missing from {file_name}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and confirm guidance/templates are missing**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_guidance_contract.py -q
```

Expected: tests fail opening `AGENTS.md`, `CLAUDE.md`, and the template files.

- [ ] **Step 3: Create the repository working agreement**

Create `AGENTS.md`:

````markdown
# CAD Agent Working Agreement

## Canonical sources

Read these before planning or changing behavior:

- Product and scope: `docs/PROJECT.md`
- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Quality and release gates: `docs/QUALITY.md`
- Design/plan record policy: `docs/superpowers/README.md`

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are historical evidence. Do not
use a historical status claim when it conflicts with `docs/STATUS.md` or fresh
command output.

## Supported environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

Do not expand platform, deployment, or AutoCAD scope without an approved design.

## Authoritative commands

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

Do not copy the pytest selection into another script or workflow. Add a test
root or lint target to `scripts/verify.ps1` and its contract test.

## Change workflow

1. Inspect current status, relevant contracts, and recent commits.
2. For new behavior, obtain design approval before implementation.
3. Use a failing regression test or benchmark before changing production logic.
4. Keep one writer for a branch or overlapping file set. Use parallel agents for
   read-heavy exploration, test execution, and independent review.
5. Keep commits scoped and run focused checks after each task.
6. Run `scripts/verify.ps1` before claiming completion or committing a release
   candidate.

## Specialized gates

- Calibration, OCR, geometry, line merging, pattern recognition, or constraints:
  run the affected `real_data` benchmark using the approved private input.
- File IPC, handles, components, live review, or live repair: run the affected
  `autocad_lt` smoke test.
- If a prerequisite is absent, report `SKIP` or `NOT RUN`; never report a pass.
- Automatic calibration's production gate is at least two independent
  candidates with median relative error at most 3 percent.

## Safety

- Never commit API keys, `.env`, customer drawings, private annotations, or
  unapproved generated DXF files.
- Human approval is required for unverified calibration, ambiguous recognition,
  and production DXF mutation.
- Preserve the original DXF and establish rollback before AutoCAD LT repair.
- Avoid destructive Git/filesystem operations. Resolve and verify exact targets
  before any approved deletion or recursive move.
- Do not alter architecture, public schemas, or package boundaries outside the
  approved task.

## Review allocation

- Small: Codex plus one bounded independent review.
- Medium: requirements/architecture plus correctness/test reviews.
- Calibration, geometry, File IPC, AutoCAD LT, architecture, or release:
  requirements/architecture, correctness/test, and security/operations reviews.

Give Claude Free reviewers a compact packet from `docs/templates/`, not the full
repository. Keep first-pass reports independent. Accept findings only when they
name scope, impact, evidence, and verification; do not use numeric quality
scores. Upload or inline every referenced artifact; a workstation-local path is
not review evidence for an external session.

## Definition of done

- Acceptance criteria are satisfied with fresh evidence.
- Focused tests and `scripts/verify.ps1` pass.
- Required private/live gates ran, or their missing state is explicitly recorded.
- `git diff --check` is clean and verification did not change repository status.
- No unresolved P0/P1 finding remains; deferred P2 has a reason and owner.
- `docs/STATUS.md` reflects only evidence that actually ran.
````

- [ ] **Step 4: Create the thin Claude adapter**

Create `CLAUDE.md`:

```markdown
# Claude Review Adapter

Read `AGENTS.md` first, then only the canonical document relevant to the assigned
review:

- scope: `docs/PROJECT.md`
- architecture: `docs/ARCHITECTURE.md`
- evidence: `docs/STATUS.md`
- gates/severity: `docs/QUALITY.md`

Work only inside the supplied review packet and diff scope. Do not infer current
status from `HANDOFF.md`, old plans, unchecked boxes, or model-generated claims.
Do not edit the repository from a Claude Free review session.

Use only content in the self-contained packet and its uploaded attachments.
Report an attachment as missing if the packet gives only a local filesystem
path or if its SHA-256 does not match the manifest.

Return findings using `docs/templates/REVIEW_FINDING.md`. Every finding must name
the file/line or artifact, impact, evidence, reproduction, and verification. If
no actionable issue exists in scope, state the files and evidence reviewed and
return "No findings".

Do not read another reviewer's first-pass report until all independent reports
have been submitted.
```

- [ ] **Step 5: Link the quick start to the now-existing working agreement**

Append this bullet to the `Canonical documentation` list in `README.md`:

```markdown
- Agent working agreement: `AGENTS.md`
```

- [ ] **Step 6: Create the bounded task and review templates**

Create `docs/templates/TASK_BRIEF.md`:

```markdown
# Task Brief

- **Task ID:** required stable identifier
- **Goal:** required single outcome
- **Base SHA:** required 40-character commit
- **Risk tier:** small, medium, or high
- **Allowed files:** required explicit paths
- **Non-goals:** required exclusions

## Acceptance criteria

List observable pass/fail outcomes with exact commands or artifacts.

## Required gates

Name `offline`, `real_data`, and/or `autocad_lt`; record external prerequisites.

## Safety and rollback

State protected data/artifacts, approval points, and recovery path.
```

Create `docs/templates/REVIEW_PACKET.md`:

```markdown
# Review Packet

- **Task ID:** required identifier
- **Reviewer role:** requirements/architecture, correctness/test, or security/operations
- **Base SHA:** required 40-character commit
- **Head SHA:** required 40-character commit
- **Diff scope:** required paths or attached patch
- **Canonical context:** required inline excerpts or uploaded files
- **Evidence delivery:** self-contained packet plus uploaded attachments; local-only paths are invalid

## Acceptance criteria

Copy the approved criteria without rewriting them.

## Test evidence

Provide exact command, exit code, environment, pass/fail/skip/warning counts,
and inline output or an uploaded artifact.

## Attachment manifest

For every uploaded file, record its file name, purpose, byte count, and SHA-256.
If no attachment is required, state `None` and inline all evidence.

## Known not-run gates

List each gate and why it did not run. An empty list must say `None`.

## Requested output

Use one repeatable `REVIEW_FINDING.md` block per finding inside a single reviewer
report; do not provide a numeric score.
```

Create `docs/templates/REVIEW_FINDING.md`:

```markdown
# Review Finding

- **Finding ID:** role plus stable sequence
- **Severity:** P0, P1, P2, or P3
- **Confidence:** high, medium, or low
- **Scope:** file and line, command, or artifact
- **Impact:** concrete user/system consequence
- **Evidence:** observed code/output/contract
- **Reproduction:** exact steps or `Not reproducible from supplied packet`
- **Verification:** exact test or inspection that proves resolution

## Finding

State one actionable issue. Repeat the complete block for each additional
finding in the same reviewer report.
```

Create `docs/templates/ADJUDICATION.md`:

```markdown
# Review Adjudication

- **Task ID:** required identifier
- **Base SHA:** required 40-character commit
- **Head SHA:** required 40-character commit

| Finding ID | Decision | Reason | Owner | Verification |
|---|---|---|---|---|
| required ID | accepted, rejected, or deferred | evidence-based reason | named owner | exact command/artifact |

No P0/P1 may remain deferred. Every deferred P2 requires an owner and reason.
```

Create `docs/templates/RELEASE_CHECKLIST.md`:

```markdown
# Release Checklist

- **Candidate Head SHA:** required 40-character commit
- **Target:** Windows, Python 3.11, AutoCAD LT
- **Human approval:** approver identity and timestamp

## Evidence

- [ ] `scripts/verify.ps1` passed on the candidate Head SHA.
- [ ] Required `real_data` gate passed, or is explicitly not affected.
- [ ] Required `autocad_lt` gate passed, or is explicitly not affected.
- [ ] JUnit, private input hash, and live-session evidence are recorded.
- [ ] Independent findings are adjudicated; unresolved P0/P1 count is zero.

## Safety

- [ ] Secrets and private drawings are absent from Git.
- [ ] Original DXF backup is verified.
- [ ] Rollback steps and operator are named.
- [ ] Post-repair review and health check are defined.
```

- [ ] **Step 7: Run guidance and full verification**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_guidance_contract.py -q
.\scripts\verify.ps1
```

Expected: all guidance contracts pass and full verification exits 0 without a
repository-status delta.

- [ ] **Step 8: Commit Task 6**

```powershell
git add AGENTS.md CLAUDE.md README.md docs/templates tests/test_guidance_contract.py
git commit -m "docs: add durable agent review contract"
```

### Task 7: Frozen-candidate review, durable evidence, and final verification

**Files:**
- Modify: `docs/STATUS.md`
- Create: `docs/reviews/2026-07-22-reproducible-foundation.md`
- Modify: `docs/superpowers/plans/2026-07-22-reproducible-foundation.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/requirements-architecture/REVIEW_PACKET.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/requirements-architecture/candidate.patch`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/requirements-architecture/MANIFEST.sha256`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/correctness-test/REVIEW_PACKET.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/correctness-test/candidate.patch`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/correctness-test/MANIFEST.sha256`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/security-operations/REVIEW_PACKET.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/security-operations/candidate.patch`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/security-operations/MANIFEST.sha256`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/reports/requirements-architecture.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/reports/correctness-test.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/reports/security-operations.md`
- Create outside Git: `.artifacts/reviews/foundation/cycle-1/adjudication.md`

If an accepted fix changes the candidate, repeat those same exact relative file
names under `cycle-2`, then `cycle-3`, incrementing only the cycle directory.

**Interfaces:**
- Consumes: the clean Task 6 head, the three verifier JUnits, a verification transcript, and three blind first-pass Claude Free reports that all name the same final candidate SHA.
- Produces: a sanitized committed review record, a complete Python 3.11 foundation certificate, zero unresolved P0/P1, explicit remaining risks, and a plan-only lifecycle-closing commit.

- [ ] **Step 1: Verify and freeze a clean implementation candidate**

Run from a clean Task 6 head:

```powershell
$reviewRoot = '.artifacts\reviews\foundation'
$statePath = Join-Path $reviewRoot 'current-cycle.json'
$base = '908d016403b744c067aae53b8d5507ef34939e19'
New-Item -ItemType Directory -Force $reviewRoot | Out-Null
$candidateHeadBefore = (git rev-parse HEAD).Trim()
$cycleNumber = 1
if (Test-Path -LiteralPath $statePath -PathType Leaf) {
  $previousState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
  if ($previousState.CandidateHead -eq $candidateHeadBefore) {
    $cycleNumber = [int]($previousState.CycleName -replace '^cycle-', '')
  } else {
    $cycleNumber = 1 + [int]($previousState.CycleName -replace '^cycle-', '')
  }
}
$cycleName = "cycle-$cycleNumber"
$cycleRoot = Join-Path $reviewRoot $cycleName
$transcript = Join-Path $cycleRoot 'foundation-verification.txt'
New-Item -ItemType Directory -Force $cycleRoot | Out-Null
try {
  .\scripts\verify.ps1 *>&1 | Tee-Object -LiteralPath $transcript
} catch {
  $_ | Out-String | Add-Content -LiteralPath $transcript
  throw
}
$candidateHead = (git rev-parse HEAD).Trim()
if ($candidateHead -notmatch '^[0-9a-f]{40}$') {
  throw "Candidate Head is not a full commit SHA: $candidateHead"
}
if ($candidateHead -ne $candidateHeadBefore) {
  throw 'HEAD changed while verification was running.'
}
$status = @(git status --porcelain=v1 --untracked-files=all)
if ($status) {
  $status
  throw 'Review candidate must be a clean commit.'
}
[ordered]@{
  Base = $base
  CandidateHead = $candidateHead
  CycleName = $cycleName
  CycleRoot = $cycleRoot
  Transcript = $transcript
} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
Get-FileHash -Algorithm SHA256 `
  $transcript, `
  '.artifacts\test-results\junit.xml', `
  '.artifacts\test-results\real-data-unavailable.xml', `
  '.artifacts\test-results\autocad-lt-unavailable.xml'
```

Expected: verification exits 0; the transcript records the exact Python patch
version, Tesseract executable/version, dependency versions, offline zero-skip
totals, two all-skipped unavailable-state probes, Ruff, Git diff checks, and the
content-hash side-effect check. Git is clean and `$candidateHead` is frozen for
this review cycle.

- [ ] **Step 2: Prove production implementation and public schemas are unchanged**

Run:

```powershell
$statePath = '.artifacts\reviews\foundation\current-cycle.json'
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$base = [string]$state.Base
$candidateHead = [string]$state.CandidateHead
if ((git rev-parse HEAD).Trim() -ne $candidateHead) {
  throw 'Current HEAD does not match the persisted review candidate.'
}
$packageChanges = @(git diff --name-only $base $candidateHead -- `
  primitive_ir_lib semantic_ir_lib dxf_builder_lib mcp_integration_lib agent_lib)
$unexpectedPackageChanges = @($packageChanges | Where-Object {
  $_ -notmatch '(^|/)tests/' -and $_ -ne 'primitive_ir_lib/requirements.txt'
})
if ($unexpectedPackageChanges) {
  $unexpectedPackageChanges
  throw 'Foundation changed a production package file outside the approved requirements shim.'
}

& git diff --exit-code $base $candidateHead -- `
  primitive_ir.schema.json semantic_ir.schema.json agent_ir.schema.json
if ($LASTEXITCODE -ne 0) {
  throw 'A public JSON schema changed in the foundation slice.'
}
& git diff --check "$base..$candidateHead"
if ($LASTEXITCODE -ne 0) {
  throw 'Candidate diff has whitespace errors.'
}
```

Expected: the only non-test file under an implementation package is the
approved `primitive_ir_lib/requirements.txt` compatibility shim; all three
schemas are byte-for-byte unchanged from the baseline; diff check exits 0.

- [ ] **Step 3: Build redacted, externally accessible role bundles**

Create a new cycle directory and role-scoped patches:

```powershell
$statePath = '.artifacts\reviews\foundation\current-cycle.json'
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$base = [string]$state.Base
$candidateHead = [string]$state.CandidateHead
$cycleName = [string]$state.CycleName
$cycleRoot = [string]$state.CycleRoot
$transcript = [string]$state.Transcript
if ((git rev-parse HEAD).Trim() -ne $candidateHead) {
  throw 'Current HEAD does not match the persisted review candidate.'
}
$roles = @(
  'requirements-architecture',
  'correctness-test',
  'security-operations'
)
$roleScopes = @{
  'requirements-architecture' = @(
    'README.md', 'AGENTS.md', 'CLAUDE.md', 'docs/PROJECT.md',
    'docs/ARCHITECTURE.md', 'docs/STATUS.md', 'docs/QUALITY.md',
    'docs/superpowers/README.md', 'docs/templates',
    'tests/test_documentation_contract.py', 'tests/test_guidance_contract.py'
  )
  'correctness-test' = @(
    '.github/workflows/tests.yml', '.gitignore', 'pyproject.toml',
    'requirements.txt', 'primitive_ir_lib/requirements.txt', 'requirements/*.in',
    'scripts', 'tests', 'primitive_ir_lib/tests/test_real_image_benchmark.py',
    'primitive_ir_lib/tests/test_vision_client.py',
    'mcp_integration_lib/tests/test_file_ipc_e2e.py',
    'mcp_integration_lib/tests/test_file_ipc_live.py'
  )
  'security-operations' = @(
    '.github/workflows/tests.yml', '.gitignore', 'AGENTS.md', 'CLAUDE.md',
    'requirements/*.in', 'scripts', 'docs/QUALITY.md', 'docs/templates'
  )
}

foreach ($role in $roles) {
  $roleDir = Join-Path $cycleRoot $role
  New-Item -ItemType Directory -Force $roleDir | Out-Null
  $scope = $roleScopes[$role]
  & git diff --binary $base $candidateHead -- $scope |
    Set-Content -LiteralPath (Join-Path $roleDir 'candidate.patch') -Encoding UTF8
  Copy-Item -LiteralPath `
    'docs\superpowers\specs\2026-07-22-reproducible-foundation-design.md' `
    -Destination (Join-Path $roleDir 'approved-design.md')
  Copy-Item -LiteralPath $transcript -Destination $roleDir
  Copy-Item -LiteralPath '.artifacts\test-results\junit.xml' -Destination $roleDir
  Copy-Item -LiteralPath '.artifacts\test-results\real-data-unavailable.xml' -Destination $roleDir
  Copy-Item -LiteralPath '.artifacts\test-results\autocad-lt-unavailable.xml' -Destination $roleDir
  Copy-Item -LiteralPath 'docs\templates\REVIEW_PACKET.md' `
    -Destination (Join-Path $roleDir 'REVIEW_PACKET.md')
  if ($role -ne 'requirements-architecture') {
    Copy-Item -LiteralPath 'requirements\windows-py311.lock' -Destination $roleDir
  }
}
```

Use `apply_patch` to complete each copied `REVIEW_PACKET.md`. Every packet must
contain these observed values and attachment names, not workstation-local links:

```text
Task ID: reproducible-foundation
Reviewer role: the role matching its directory
Base SHA: 908d016403b744c067aae53b8d5507ef34939e19
Head SHA: the exact CandidateHead value in current-cycle.json
Acceptance criteria: copy all nine criteria from approved-design.md verbatim
Diff scope: candidate.patch
Canonical context: approved-design.md plus the new canonical files present in candidate.patch
Test evidence: foundation-verification.txt and the three named JUnit files
Known gate state: real_data SKIP probe; autocad_lt SKIP probe; neither live gate executed
Requested output: one repeatable REVIEW_FINDING block per finding, or No findings
```

Run the redaction and manifest checks after completing each packet:

```powershell
$state = Get-Content -LiteralPath `
  '.artifacts\reviews\foundation\current-cycle.json' -Raw | ConvertFrom-Json
$cycleRoot = [string]$state.CycleRoot
$roles = @(
  'requirements-architecture',
  'correctness-test',
  'security-operations'
)
foreach ($role in $roles) {
  $roleDir = Join-Path $cycleRoot $role
  $forbiddenFiles = @(Get-ChildItem -LiteralPath $roleDir -Recurse -File | Where-Object {
    $_.Extension -match '^\.(png|jpe?g|pdf|dwg|dxf|env|pem|key)$'
  })
  if ($forbiddenFiles) {
    $forbiddenFiles.FullName
    throw "Private/binary production material entered the $role review bundle."
  }
  $secretHits = @(Get-ChildItem -LiteralPath $roleDir -Recurse -File |
    Select-String -Pattern '(?i)(sk-ant-[A-Za-z0-9_-]{10,}|api[_-]?key\s*[:=]\s*["'']?[A-Za-z0-9_-]{12,})')
  if ($secretHits) {
    $secretHits
    throw "Possible secret found in the $role review bundle."
  }
  $manifestPath = Join-Path $roleDir 'MANIFEST.sha256'
  $manifest = Get-ChildItem -LiteralPath $roleDir -File |
    Where-Object { $_.Name -ne 'MANIFEST.sha256' } |
    Sort-Object Name |
    ForEach-Object {
      $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
      "$hash  $($_.Name)"
    }
  Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding ASCII
}
```

Manually inspect the manifest and packet once. For each Claude Free session,
upload every file in that role directory and ask the reviewer to confirm the
Head SHA and manifest before reviewing. A local path alone is never evidence.
Do not upload another reviewer's response.

- [ ] **Step 4: Collect three blind reports for the frozen Head**

Create `.artifacts/reviews/foundation/cycle-1/reports/`. Save each Claude answer
as one role-named Markdown report; repeat the complete finding block inside that
file for multiple findings. Each report must state the exact candidate Head SHA,
the manifest it checked, its reviewed scope, and either evidence-backed findings
or `No findings`.

Run:

```powershell
$state = Get-Content -LiteralPath `
  '.artifacts\reviews\foundation\current-cycle.json' -Raw | ConvertFrom-Json
$candidateHead = [string]$state.CandidateHead
$cycleRoot = [string]$state.CycleRoot
$roles = @(
  'requirements-architecture',
  'correctness-test',
  'security-operations'
)
if ((git rev-parse HEAD).Trim() -ne $candidateHead) {
  throw 'Current HEAD does not match the persisted review candidate.'
}
$reportsDir = Join-Path $cycleRoot 'reports'
New-Item -ItemType Directory -Force $reportsDir | Out-Null
foreach ($role in $roles) {
  $report = Join-Path $reportsDir "$role.md"
  if (-not (Test-Path -LiteralPath $report -PathType Leaf)) {
    throw "Missing reviewer report: $report"
  }
  $content = Get-Content -LiteralPath $report -Raw
  if ($content -notmatch [regex]::Escape($candidateHead)) {
    throw "$role report does not name the frozen candidate Head."
  }
  if ($content -match '(?i)(score|rating)\s*[:=]\s*\d|\d+\s*/\s*100') {
    throw "$role report uses a prohibited numeric quality score."
  }
  Get-FileHash -LiteralPath $report -Algorithm SHA256
}
```

Expected: all three reports address the same frozen Head and remain independent.

- [ ] **Step 5: Adjudicate findings and repeat the cycle after any fix**

Reload the final-cycle path and create the adjudication file:

```powershell
$state = Get-Content -LiteralPath `
  '.artifacts\reviews\foundation\current-cycle.json' -Raw | ConvertFrom-Json
$cycleRoot = [string]$state.CycleRoot
Copy-Item -LiteralPath 'docs\templates\ADJUDICATION.md' `
  -Destination (Join-Path $cycleRoot 'adjudication.md')
```

For every
finding, record accepted/rejected/deferred, repository evidence, owner, and exact
verification. No P0/P1 may be rejected solely because it is inconvenient, and
no P0/P1 may remain deferred.

For every accepted finding that changes the repository:

1. Add or strengthen a failing focused contract/regression test and run it to
   observe the documented failure.
2. Apply the smallest in-scope fix; foundation review must not expand into a
   production algorithm or AutoCAD LT mutation.
3. Run the focused test, then `scripts/verify.ps1`.
4. Commit the fix with an evidence-based message.
5. Increment `cycle-N`, return to Step 1, freeze the new clean Head, rebuild all
   three bundles, and obtain three reports that explicitly acknowledge that new
   final Head. Do not reuse approval tied to the older SHA.

Repeat until the final cycle has zero unresolved P0/P1 and every deferred P2 has
a reason and owner. Re-running Step 1 after each fix atomically increments and
persists `.artifacts/reviews/foundation/current-cycle.json`; every later command
reloads that file, so no PowerShell session state is assumed across the external
review pause.

- [ ] **Step 6: Prove the certificate transition is initially red**

The conditional certificate contract was committed in Task 5 and currently
accepts only the explicit `Unverified` state. Run this stricter transition probe:

```powershell
& '.\.venv-py311\Scripts\python.exe' -c `
  "from pathlib import Path; text=Path('docs/STATUS.md').read_text(encoding='utf-8'); assert '## Foundation certificate' in text"
```

Expected: FAIL with `AssertionError`, proving the final certificate does not yet
exist. Do not modify the contract test in this task; keeping its test cardinality
stable prevents stale JUnit totals.

- [ ] **Step 7: Create the durable normalized review record and certificate**

First compute observed hashes from the final cycle:

```powershell
$state = Get-Content -LiteralPath `
  '.artifacts\reviews\foundation\current-cycle.json' -Raw | ConvertFrom-Json
$candidateHead = [string]$state.CandidateHead
$cycleRoot = [string]$state.CycleRoot
$transcript = [string]$state.Transcript
$roles = @(
  'requirements-architecture',
  'correctness-test',
  'security-operations'
)
if ((git rev-parse HEAD).Trim() -ne $candidateHead) {
  throw 'Current HEAD does not match the persisted review candidate.'
}
$evidenceDir = Join-Path $cycleRoot 'requirements-architecture'
$transcriptHash = (Get-FileHash -LiteralPath $transcript -Algorithm SHA256).Hash.ToLowerInvariant()
$offlineHash = (Get-FileHash (Join-Path $evidenceDir 'junit.xml') -Algorithm SHA256).Hash.ToLowerInvariant()
$realDataHash = (Get-FileHash (Join-Path $evidenceDir 'real-data-unavailable.xml') -Algorithm SHA256).Hash.ToLowerInvariant()
$autocadHash = (Get-FileHash (Join-Path $evidenceDir 'autocad-lt-unavailable.xml') -Algorithm SHA256).Hash.ToLowerInvariant()
$reviewRows = foreach ($role in $roles) {
  $packet = Join-Path (Join-Path $cycleRoot $role) 'REVIEW_PACKET.md'
  $manifest = Join-Path (Join-Path $cycleRoot $role) 'MANIFEST.sha256'
  $report = Join-Path (Join-Path $cycleRoot 'reports') "$role.md"
  $packetHash = (Get-FileHash $packet -Algorithm SHA256).Hash.ToLowerInvariant()
  $manifestHash = (Get-FileHash $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
  $reportHash = (Get-FileHash $report -Algorithm SHA256).Hash.ToLowerInvariant()
  "| $role | ``$packetHash`` | ``$manifestHash`` | ``$reportHash`` | acknowledged ``$candidateHead`` |"
}
$adjudicationText = Get-Content -LiteralPath (Join-Path $cycleRoot 'adjudication.md') -Raw
$reviewRecord = @"
# Reproducible Foundation Review Record

- Candidate Head SHA: ``$candidateHead``
- Review cycle: ``$([IO.Path]::GetFileName($cycleRoot))``
- Verification transcript SHA-256: ``$transcriptHash``
- Offline JUnit SHA-256: ``$offlineHash``
- real_data unavailable-state JUnit SHA-256: ``$realDataHash``
- autocad_lt unavailable-state JUnit SHA-256: ``$autocadHash``
- Unresolved P0/P1: ``0``

| Role | Packet SHA-256 | Manifest SHA-256 | Raw report SHA-256 | Final-head acknowledgement |
|---|---|---|---|---|
$($reviewRows -join "`n")

## Normalized adjudication

$adjudicationText

## Retention and privacy

Raw packets/reports remain outside Git in the operator evidence archive for at
least the lifetime of this foundation release. This committed record contains
only normalized findings and integrity hashes; it contains no credential,
customer drawing, private annotation, or generated production DXF.
"@
$reviewRecord
```

Use `apply_patch` to create
`docs/reviews/2026-07-22-reproducible-foundation.md` from the printed text
verbatim. Preserve every full lowercase SHA-256 and the normalized adjudication;
do not commit raw model prose.

Then read the exact environment lines and JUnit totals:

```powershell
$state = Get-Content -LiteralPath `
  '.artifacts\reviews\foundation\current-cycle.json' -Raw | ConvertFrom-Json
$candidateHead = [string]$state.CandidateHead
$cycleRoot = [string]$state.CycleRoot
$transcript = [string]$state.Transcript
$evidenceDir = Join-Path $cycleRoot 'requirements-architecture'
$transcriptHash = (Get-FileHash -LiteralPath $transcript -Algorithm SHA256).Hash.ToLowerInvariant()
$offlinePath = Join-Path $evidenceDir 'junit.xml'
$realDataPath = Join-Path $evidenceDir 'real-data-unavailable.xml'
$autocadPath = Join-Path $evidenceDir 'autocad-lt-unavailable.xml'
$offlineHash = (Get-FileHash $offlinePath -Algorithm SHA256).Hash.ToLowerInvariant()
$realDataHash = (Get-FileHash $realDataPath -Algorithm SHA256).Hash.ToLowerInvariant()
$autocadHash = (Get-FileHash $autocadPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ((git rev-parse HEAD).Trim() -ne $candidateHead) {
  throw 'Current HEAD does not match the persisted review candidate.'
}
function Read-Totals([string]$path) {
  [xml]$xml = Get-Content -LiteralPath $path -Raw
  $suites = @($xml.testsuites.testsuite)
  [pscustomobject]@{
    Tests = ($suites | ForEach-Object { [int]$_.tests } | Measure-Object -Sum).Sum
    Failures = ($suites | ForEach-Object { [int]$_.failures } | Measure-Object -Sum).Sum
    Errors = ($suites | ForEach-Object { [int]$_.errors } | Measure-Object -Sum).Sum
    Skipped = ($suites | ForEach-Object { [int]$_.skipped } | Measure-Object -Sum).Sum
  }
}
$offline = Read-Totals $offlinePath
$realData = Read-Totals $realDataPath
$autocad = Read-Totals $autocadPath
$python = (Select-String -LiteralPath $transcript -Pattern '^Python: ' | Select-Object -Last 1).Line.Replace('Python: ', '')
$tesseract = (Select-String -LiteralPath $transcript -Pattern '^Tesseract: ' | Select-Object -Last 1).Line.Replace('Tesseract: ', '')
$dependencies = (Select-String -LiteralPath $transcript -Pattern '^Dependencies: ' | Select-Object -Last 1).Line.Replace('Dependencies: ', '')
$date = Get-Date -Format 'yyyy-MM-dd'
$certificate = @"
## Foundation certificate

- State: **Verified**
- Date: ``$date``
- Reviewed implementation Head SHA: ``$candidateHead``
- Command: ``.\scripts\verify.ps1``
- Exit code: ``0``
- Python: ``$python``
- Tesseract executable: ``$tesseract``
- Dependencies: ``$dependencies``
- Offline JUnit: ``tests=$($offline.Tests); failures=$($offline.Failures); errors=$($offline.Errors); skipped=$($offline.Skipped)``; SHA-256 ``$offlineHash``
- ``real_data``: ``SKIP`` unavailable-state probe; ``tests=$($realData.Tests); skipped=$($realData.Skipped)``; SHA-256 ``$realDataHash``
- ``autocad_lt``: ``SKIP`` unavailable-state probe; ``tests=$($autocad.Tests); skipped=$($autocad.Skipped)``; SHA-256 ``$autocadHash``
- Unexpected warnings: ``0``; scoped intentional ROI warning policy remains documented in ``docs/QUALITY.md``
- Ruff: ``PASS``
- Lock/environment, Git whitespace, and repository content-hash side-effect checks: ``PASS``
- Verification transcript SHA-256: ``$transcriptHash``
- Independent review: ``docs/reviews/2026-07-22-reproducible-foundation.md``; three final-head reports; unresolved P0/P1 ``0``
- Remaining risks: the approved private ``real_data`` gate and live ``autocad_lt`` gate were NOT RUN; current ``agent_lib.run``/demo auto-apply behavior is not an approved production mutation path.
"@
$certificate
```

Use `apply_patch` to append the printed certificate to `docs/STATUS.md` and
replace the entire `Current module status` table with these evidence states:

```markdown
| Area | State | Evidence and limit |
|---|---|---|
| Primitive IR | Partially verified | Final Python 3.11 offline gate passed with zero skips; approved private `real_data` execution was NOT RUN and its unavailable-state probe was SKIP. |
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD LT mutation is outside this state. |
| MCP/File IPC | Partially verified | Offline/fake IPC tests passed; live `autocad_lt` execution was NOT RUN and its unavailable-state probe was SKIP. |
| Agent advice/audit | Partially verified | Offline tests passed; `run_agent()` is non-mutating, but the current run/demo entry points auto-apply reports and are not approved production mutation paths. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |
```

Use the exact observed `$candidateHead` in both committed documents. Do not
copy any value from this plan when an artifact provides the observed value.

- [ ] **Step 8: Verify, stabilize counts, and commit durable evidence**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest `
  tests\test_documentation_contract.py::DocumentationContractTests::test_foundation_certificate_is_well_formed_when_present `
  -q
.\scripts\verify.ps1
git diff --check
git status --short --branch
```

Expected: the strict certificate branch passes; authoritative verification exits
0; offline test cardinality matches the certificate because the conditional
contract already existed in Task 5; only `docs/STATUS.md` and the normalized
review record are modified. If a count differs, update only the observed count
from the new JUnit and rerun `scripts/verify.ps1` once before committing.

Commit:

```powershell
git add docs/STATUS.md docs/reviews/2026-07-22-reproducible-foundation.md
git commit -m "docs: certify reproducible foundation"
.\scripts\verify.ps1
```

- [ ] **Step 9: Close the plan lifecycle without a self-referential SHA**

Capture the certificate commit:

```powershell
$completionHead = (git rev-parse HEAD).Trim()
```

Use `apply_patch` on this plan to replace `**Status:** Planned` with
`**Status:** Completed`. Replace the current completion sentence with the label
`**Completion Head SHA:**`, a space, and the exact value printed in
`$completionHead` enclosed in Markdown backticks. Replace the pending
verification/gate result lines with these observed result lines:

```markdown
**Verification result:** `PASS` on the Completion Head SHA; see the Foundation certificate in `docs/STATUS.md`.

**Specialized gate result:** `real_data`: `SKIP` probe, live gate `NOT RUN`; `autocad_lt`: `SKIP` probe, live gate `NOT RUN`.
```
Do not bulk-edit task checkboxes: `docs/superpowers/README.md` defines lifecycle
metadata and Git evidence as status, and explicitly states that unchecked boxes
are not status evidence.

Run and commit:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest `
  tests\test_documentation_contract.py::DocumentationContractTests::test_plan_lifecycle_metadata_is_well_formed `
  -q
.\scripts\verify.ps1
git add docs/superpowers/plans/2026-07-22-reproducible-foundation.md
git commit -m "docs: close reproducible foundation plan"
```

- [ ] **Step 10: Verify the committed branch before handoff**

Use `superpowers:verification-before-completion`, then run fresh:

```powershell
.\scripts\verify.ps1
git diff --check 908d016..HEAD
git log --oneline --decorate -10
git status --short --branch
```

Expected: verification exits 0 with offline zero skips and both specialized
probes all-skipped; the task commits, review/certificate commit, and plan-only
closure commit appear on `codex/reproducible-foundation`; the worktree is clean.
Do not push or merge without explicit user authorization.
