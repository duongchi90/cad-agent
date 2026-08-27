# Sealed Local Mission Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing self-hosted ChatGPT Local Executor into a sealed `OFFLINE_VERIFY` mission consumer with no arbitrary command surface and machine-readable non-authoritative terminal evidence.

**Architecture:** Reuse the existing workflow and PowerShell executor. Add one pure Python execution-envelope validator that reuses the A-D mission/currentness contracts, then make the workflow materialize the envelope only under `$RUNNER_TEMP` and make PowerShell validate exact branch/head/envelope before invoking the fixed bootstrap/verify path.

**Tech Stack:** Python 3.11, pytest, PowerShell, GitHub Actions workflow YAML, existing `cad_agent.mission_contract`, `cad_agent.control_snapshot`, and `cad_agent.drawing_contracts.canonical_json_sha256`.

**Spec:** `docs/superpowers/specs/2026-08-27-local-mission-adapter-design.md`

## Global Constraints

- Issue: `#288`.
- Stacked base is exact #286 head `729f005b5c1cad6f88245bb134b524be644c4855`.
- Branch: `governance/local-mission-adapter`.
- Future PR base: `governance/operating-model-enforcement`.
- No AutoCAD/COM/ROT/UI/NETLOAD/File-IPC live action.
- No merge/publication/CONTROL_SEQ authority.
- No new runner, service, transport, database, daemon, dependency, package owner, or persistent truth store.
- Only `OFFLINE_VERIFY` is executable in E1.
- No production/workflow/script change before a corresponding failing regression exists.
- Exact #288 seven-path write-set only.

---

### Task 1: Causal RED for the arbitrary-command bypass

**Files:**
- Create: `tests/test_chatgpt_local_executor_contract.py`
- Read: `.github/workflows/chatgpt-local-executor.yml`
- Read: `scripts/local-executor.ps1`

**Interfaces:**
- Consumes: repository text files at their exact paths.
- Produces: static security regression that fails while `command` / `Invoke-Expression` remains reachable.

- [ ] **Step 1: Write the failing workflow regression**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatgpt-local-executor.yml"
EXECUTOR = ROOT / "scripts" / "local-executor.ps1"


def test_local_executor_has_no_arbitrary_command_surface() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    executor = EXECUTOR.read_text(encoding="utf-8")

    assert "      command:" not in workflow
    assert "Invoke-Expression" not in workflow
    assert "Invoke-Expression" not in executor
    assert "iex " not in workflow.lower()
    assert "iex " not in executor.lower()
```

- [ ] **Step 2: Run the focused RED**

Run:

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
& $python311 -m pytest tests/test_chatgpt_local_executor_contract.py::test_local_executor_has_no_arbitrary_command_surface -q
```

Expected: FAIL because current workflow contains `command` and `Invoke-Expression`.

- [ ] **Step 3: Commit the tests-only RED**

Commit message:

```text
test: expose local executor command bypass
```

No workflow, script, or production module changes in this commit.

---

### Task 2: Define the sealed execution envelope with TDD

**Files:**
- Create: `tests/test_local_execution_envelope.py`
- Create: `cad_agent/local_execution_envelope.py`

**Interfaces:**
- Consumes: `validate_local_mission(mission, control_snapshot=...)` and `canonical_json_sha256`.
- Produces: `validate_local_execution_envelope(envelope: Mapping[str, object]) -> dict[str, object]`, `build_local_mission_terminal(...) -> dict[str, object]`, `LocalExecutionEnvelopeError`.

- [ ] **Step 1: Add reusable valid mission/snapshot fixture code inside the test module**

Build a valid control snapshot through `build_control_snapshot(...)`, route through `classify_work(...)` or a closed `LOCAL_REPO_REQUIRED` routing fixture accepted by `compile_local_mission(...)`, and compile a mission with these exact request invariants:

```python
{
    "repo_mutation": False,
    "write_set": [],
    "live_budget": 0,
    "merge_authority": False,
    "publication_authority": False,
    "human_relay_required": False,
}
```

All other required mission request fields must use concrete non-empty values and finite budgets accepted by `compile_local_mission`.

- [ ] **Step 2: Write failing envelope tests**

Tests must include these exact behaviors:

```python
def test_rejects_unknown_capability(): ...
def test_rejects_mission_sha_mismatch(): ...
def test_rejects_mission_control_snapshot_mismatch(): ...
def test_rejects_offline_verify_with_nonzero_live_budget(): ...
def test_rejects_unexpected_envelope_field(): ...
def test_accepts_canonical_offline_verify_envelope(): ...
```

For each rejection test, assert `LocalExecutionEnvelopeError` with a stable causal phrase such as `capability`, `expected_mission_sha256`, `control snapshot`, `live_budget`, or `unexpected fields` so a generic rejection cannot satisfy the regression.

- [ ] **Step 3: Write failing terminal-authority tests**

```python
def test_terminal_is_evidence_only():
    terminal = build_local_mission_terminal(
        mission_sha256="a" * 64,
        control_state_sha256="b" * 64,
        capability="OFFLINE_VERIFY",
        local_branch="governance/local-mission-adapter",
        local_head_sha="c" * 40,
        result="PASS",
        bootstrap_exit_code=0,
        verify_exit_code=0,
    )
    assert set(terminal) == {
        "schema_version",
        "mission_sha256",
        "control_state_sha256",
        "capability",
        "local_branch",
        "local_head_sha",
        "result",
        "bootstrap_exit_code",
        "verify_exit_code",
        "live_result",
        "merge_authority",
        "publication_authority",
    }
    assert "control_seq" not in terminal
    assert terminal["live_result"] == "NOT_RUN"
    assert terminal["merge_authority"] is False
    assert terminal["publication_authority"] is False
```

- [ ] **Step 4: Run the envelope RED**

Run:

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
& $python311 -m pytest tests/test_local_execution_envelope.py -q
```

Expected: FAIL because `cad_agent.local_execution_envelope` does not exist / cannot satisfy the closed contract.

- [ ] **Step 5: Implement the minimal envelope module**

The module must expose exactly these public constants/functions/classes:

```python
LOCAL_EXECUTION_ENVELOPE_SCHEMA_VERSION = "cad-local-execution-envelope-1.0"
LOCAL_MISSION_TERMINAL_SCHEMA_VERSION = "cad-local-mission-terminal-1.0"
ALLOWED_CAPABILITIES = frozenset({"OFFLINE_VERIFY"})

class LocalExecutionEnvelopeError(ValueError): ...

def validate_local_execution_envelope(
    envelope: Mapping[str, object],
) -> dict[str, object]: ...

def build_local_mission_terminal(
    *,
    mission_sha256: str,
    control_state_sha256: str,
    capability: str,
    local_branch: str,
    local_head_sha: str,
    result: str,
    bootstrap_exit_code: int,
    verify_exit_code: int,
) -> dict[str, object]: ...
```

`validate_local_execution_envelope` must use exact closed fields:

```python
{
    "schema_version",
    "capability",
    "expected_mission_sha256",
    "mission",
    "control_snapshot",
}
```

Canonical mission identity is:

```python
mission_sha256 = canonical_json_sha256(mission)
```

Then call:

```python
validated_mission = validate_local_mission(
    mission,
    control_snapshot=control_snapshot,
)
```

Fail unless:

```python
capability == "OFFLINE_VERIFY"
validated_mission["routing_classification"] == "LOCAL_REPO_REQUIRED"
validated_mission["live_budget"] == 0
validated_mission["merge_authority"] is False
validated_mission["publication_authority"] is False
```

Return canonical data containing the normalized envelope plus derived `mission_sha256` and exact `control_state_sha256`.

`build_local_mission_terminal` must validate lowercase SHA lengths, exact capability, `result in {"PASS", "FAIL"}`, integer exit codes, and always fix:

```python
"live_result": "NOT_RUN",
"merge_authority": False,
"publication_authority": False,
```

- [ ] **Step 6: Run envelope GREEN**

Run:

```powershell
& $python311 -m pytest tests/test_local_execution_envelope.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Commit message:

```text
feat: validate sealed local mission envelope
```

---

### Task 3: Harden the workflow and PowerShell owner

**Files:**
- Modify: `.github/workflows/chatgpt-local-executor.yml`
- Modify: `scripts/local-executor.ps1`
- Modify: `tests/test_chatgpt_local_executor_contract.py`

**Interfaces:**
- Consumes: one raw JSON execution envelope from workflow dispatch and exact expected branch/SHA.
- Produces: fixed `OFFLINE_VERIFY` execution plus `mission-terminal.json` evidence.

- [ ] **Step 1: Extend the static contract tests before modifying workflow/script**

Add assertions requiring:

```python
assert "mission_envelope_json:" in workflow
assert "required: true" in workflow
assert "$env:RUNNER_TEMP" in workflow
assert "CAD_AGENT_MISSION_ENVELOPE_JSON" in workflow
assert "-MissionEnvelopePath" in workflow
assert "-ExpectedBranch" in workflow
assert "-ExpectedSha" in workflow
assert "mission-terminal.json" in executor
assert "validate_local_execution_envelope" in executor
assert "bootstrap.ps1" in executor
assert "verify.ps1" in executor
```

Also assert workflow does not interpolate `${{ github.event.inputs.mission_envelope_json }}` directly inside a `run:` PowerShell command body; it must be passed through `env:` first.

- [ ] **Step 2: Run focused RED**

Run:

```powershell
& $python311 -m pytest tests/test_chatgpt_local_executor_contract.py -q
```

Expected: FAIL because the existing workflow/script do not implement sealed envelope materialization/validation/terminal output.

- [ ] **Step 3: Replace workflow inputs and execution step**

Required dispatch inputs:

```yaml
expected_branch:
  required: true
expected_sha:
  required: true
mission_envelope_json:
  required: true
```

Remove `command` completely.

The execution step must use environment variables:

```yaml
env:
  CAD_AGENT_EXPECTED_BRANCH: ${{ inputs.expected_branch }}
  CAD_AGENT_EXPECTED_SHA: ${{ inputs.expected_sha }}
  CAD_AGENT_MISSION_ENVELOPE_JSON: ${{ inputs.mission_envelope_json }}
```

PowerShell writes UTF-8 without BOM to:

```powershell
$missionPath = Join-Path $env:RUNNER_TEMP "cad-agent-mission-envelope.json"
[System.IO.File]::WriteAllText(
    $missionPath,
    $env:CAD_AGENT_MISSION_ENVELOPE_JSON,
    [System.Text.UTF8Encoding]::new($false)
)
```

Then invoke only `scripts/local-executor.ps1` with exact path/branch/SHA parameters.

- [ ] **Step 4: Harden `scripts/local-executor.ps1` guards**

Add mandatory parameters:

```powershell
[string]$MissionEnvelopePath,
[string]$ExpectedBranch,
[string]$ExpectedSha
```

Before bootstrap/verify:

```powershell
$currentBranch = (git branch --show-current).Trim()
$currentHead = (git rev-parse HEAD).Trim()
if ($currentBranch -ne $ExpectedBranch.Trim()) { throw "BRANCH_MISMATCH" }
if ($currentHead -ne $ExpectedSha.Trim()) { throw "HEAD_SHA_MISMATCH" }
```

Resolve `$MissionEnvelopePath` and `$env:RUNNER_TEMP` to absolute paths and fail unless the mission file is a descendant of the runner temp root.

Use Python 3.11 to read JSON and call `validate_local_execution_envelope`. Do not interpolate mission values as source code or executable arguments. The Python boundary should return JSON only, which PowerShell parses with `ConvertFrom-Json`.

Require validated mission `active_pr_head_sha` to equal `$currentHead` when `active_pr` is not `NONE`.

Only after all guards pass run the existing authoritative bootstrap and verify commands.

- [ ] **Step 5: Emit terminal evidence in `finally`**

Call `build_local_mission_terminal` or construct from values validated by that function, then write compact JSON to:

```powershell
Join-Path $ArtifactsDir "mission-terminal.json"
```

On pre-validation failure use `UNVALIDATED` for mission/control identities and `FAIL` result. Never add `control_seq`, live PASS, merge authority, or publication authority.

- [ ] **Step 6: Run focused GREEN**

Run:

```powershell
& $python311 -m pytest tests/test_chatgpt_local_executor_contract.py tests/test_local_execution_envelope.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Commit message:

```text
feat: seal local executor mission boundary
```

---

### Task 4: Exact-head verification and review

**Files:**
- No new write-set paths.

**Interfaces:**
- Consumes: final E1 exact head.
- Produces: hosted evidence and security/operations disposition only.

- [ ] **Step 1: Verify cumulative diff**

Compare exact #286 base `729f005b5c1cad6f88245bb134b524be644c4855` to E1 head and require exactly the seven #288 paths.

- [ ] **Step 2: Run authoritative hosted verification**

Run through repository CI / hosted verifier. Acceptance requires focused E1 tests plus the existing authoritative `scripts/verify.ps1` contract to pass. AutoCAD/live must remain `NOT_RUN`.

- [ ] **Step 3: Run reuse declaration / architecture checks**

Verify no new dependency, workflow owner, runner, service, transport, database, daemon, package boundary, AutoCAD owner, or File-IPC owner was introduced.

- [ ] **Step 4: Independent security/operations review on exact head**

Reviewer must specifically check:

```text
arbitrary command injection
GitHub expression -> PowerShell injection
mission JSON materialization path containment
exact vs prefix SHA binding
branch/head/currentness binding
mission/control-snapshot mismatch
capability fail-closed behavior
terminal authority escalation
runner-temp-only payload handling
no live capability
```

- [ ] **Step 5: Open/update DRAFT stacked PR**

Base: `governance/operating-model-enforcement`.

Body must state exact base/head, changed paths, RED/GREEN evidence, hosted verification, security verdict, `AutoCAD/live=NOT_RUN`, and `NO_MERGE` until explicit SOL acceptance.

- [ ] **Step 6: Final anti-race**

Fresh-read Issue #131, current `main`, #286, #284/#285, #288, and E1 PR. Stop if a newer authority conflicts with E1 scope.
