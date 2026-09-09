# Drawing Setup Expectation Policy Contract Change Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, hash-bound `expectation_policy` to the existing Drawing Setup plan/evaluator so observations never become conformance PASS and a policy plan cannot return vacuous `SETUP_VERIFIED`.

**Architecture:** Extend the existing pure-Python contract validator and evaluator in place. Legacy plans without `expectation_policy` retain the current all-gating behavior and output; policy plans classify each approved comparison path as `GATING` or `OBSERVATION_ONLY`, emit scoped evidence, and require a non-empty evaluated gating scope before verification.

**Tech Stack:** Python 3.11, pytest, existing `cad_agent.drawing_contracts`, existing `cad_agent.drawing_setup`, JSON canonical SHA-256 manifests, PowerShell `scripts/verify.ps1`.

**Spec:** `docs/superpowers/specs/2026-09-09-drawing-setup-expectation-policy-contract-change-v2.md`

**Plan revision:** `20260909.02` — revised only for SOL finding [issue comment 5601415396](https://github.com/duongchi90/cad-agent/issues/412#issuecomment-5601415396): `default_mode` is exactly `GATING`, and the positive unresolved-value fixture marks `current_layer` as `OBSERVATION_ONLY`.

## Global Constraints

- Exact approved proposal body SHA-256: `17ee02ea89d6fadce5148b730a8f62d302b032a29431cba6a3a33847b4e0da6d`.
- Exact approval evidence: https://github.com/duongchi90/cad-agent/issues/412#issuecomment-5601313049.
- Base SHA: `2d320361e2146d0602aac6f226f5bffed5f931a5`; fresh pre-implementation worktree is clean on the implementation branch.
- Modify only `cad_agent/drawing_contracts.py`, `cad_agent/drawing_setup.py`, and `tests/test_cad_agent_drawing_setup.py` unless a focused test proves a CLI change is required.
- No AutoCAD plugin, FileIPC, transport, dispatcher, source drawing, DWT, accepted drawing, or second `drawing_setup_verify` action.
- No fabricated expected values, DWT lineage, embedded-settings measurement, scale, UCS, fonts, layouts, layers, or styles.
- Existing no-policy plans and existing blocker vocabulary remain compatible.
- Every implementation task ends with its focused test command before the next task.
- The plan remains `planned` until implementation and all required verification are complete; no completion SHA is claimed now.

---

### Task 1: Capture the approved baseline and test fixture contract

**Files:**
- Modify: `tests/test_cad_agent_drawing_setup.py:1-110`
- Read: `cad_agent/drawing_contracts.py:45-80`
- Read: `cad_agent/drawing_setup.py:332-628`

**Interfaces:**
- Consumes: existing `approved_setup_plan()`, `matching_setup_audit()`, `evaluate_setup_plan()`, and `require_setup_verified()` fixtures/helpers.
- Produces: a test-local policy-plan builder that preserves the current fixture hashes and can select concrete, `UNRESOLVED`, empty, and mixed policy shapes without changing repository fixtures.

- [ ] **Step 1: Add a failing policy fixture helper test.** Add a helper beside `_create_plan` that deep-copies `approved_setup_plan()`, adds a root `expectation_policy`, and returns a mutable `dict[str, object]`; add a test asserting its policy hash input is present and the current no-policy fixture remains unchanged.

```python
def _policy_plan(
    *, field_modes: dict[str, str], unresolved: frozenset[str] = frozenset()
) -> dict[str, object]:
    plan = copy.deepcopy(approved_setup_plan())
    plan["expectation_policy"] = {
        "schema_version": "drawing-setup-expectation-policy-1.0",
        "default_mode": "GATING",
        "field_modes": dict(field_modes),
    }
    expectations = plan["setup_expectations"]
    for path in unresolved:
        if path.startswith("variables."):
            expectations["variables"][path.removeprefix("variables.")] = "UNRESOLVED"
        else:
            expectations[path] = "UNRESOLVED"
    return plan
```

- [ ] **Step 2: Run the focused fixture test to verify it fails for the current contract.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "policy_plan" -q`

Expected: FAIL because the current `drawing_setup_plan` validator rejects the new root property or the unresolved marker before the policy behavior exists.

- [ ] **Step 3: Do not change production code in this task.** Keep this task’s helper/test red so the implementation tasks have an explicit regression baseline. If the helper’s default argument is rejected by the project’s style/lint rules, use `unresolved: frozenset[str] = frozenset()` and keep the same observable behavior.

- [ ] **Step 4: Re-run the focused command and record the exact failure in the implementation record.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "policy_plan" -q`

Expected: the same contract rejection, with no repository files other than the intended test file changed.

- [ ] **Step 5: Commit the red test only.**

```powershell
git add tests/test_cad_agent_drawing_setup.py
git commit -m "test: pin drawing setup policy regressions"
```

### Task 2: Add strict validation for the optional expectation policy

**Files:**
- Modify: `cad_agent/drawing_contracts.py:14-25,164-201,262-273,348-368`
- Test: `tests/test_cad_agent_drawing_setup.py:policy fixture tests`

**Interfaces:**
- Consumes: root-level `expectation_policy` and existing `setup_expectations`.
- Produces: `_validate_expectation_policy(value, contract)`, policy-aware `_validate_expectations(value, contract, policy=None)`, and optional `expectation_policy` acceptance in `drawing_setup_plan-1.0` while keeping profiles legacy-strict.

- [ ] **Step 1: Write failing validator tests for the exact policy shape.** Add tests for `default_mode=GATING` with field modes `GATING`/`OBSERVATION_ONLY`, unknown path, unknown mode, missing policy fields, `UNRESOLVED` under `GATING`, scalar `UNRESOLVED` under observation-only, empty `layouts` under observation-only, and a legacy profile that still rejects unresolved setup expectations.

```python
def test_policy_plan_accepts_observation_only_unresolved_and_empty_layouts(tmp_path: Path) -> None:
    plan = _policy_plan(
        field_modes={
            "variables.MSLTSCALE": "OBSERVATION_ONLY",
            "layouts": "OBSERVATION_ONLY",
            "current_layer": "OBSERVATION_ONLY",
        },
        unresolved={"variables.MSLTSCALE", "current_layer"},
    )
    plan["setup_expectations"]["layouts"] = []
    path = tmp_path / "policy-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert read_contract(path, contract="drawing_setup_plan") == plan
```

Use the repository’s existing `read_contract` temporary-file pattern rather than adding a second validator entry point. The test must assert the exact `DrawingContractError` message for each rejected shape.

- [ ] **Step 2: Run the new validator tests to confirm they fail before implementation.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "policy or unresolved or empty_layouts" -q`

Expected: FAIL because `_validate_setup_plan` has no optional policy and `_validate_expectations` requires concrete values.

- [ ] **Step 3: Implement the minimal policy validator.** Define the allowed paths and modes once, validate the exact object shape, and pass the policy mode into `_validate_expectations` only for `drawing_setup_plan`. Keep `_validate_profile` calling `_validate_expectations` without a policy so approved profiles remain strict. For each observation-only path, accept only the approved `UNRESOLVED` marker or the explicitly empty collection/object shape; retain the existing concrete checks for every gating path.

```python
def _validate_expectation_policy(value: object, *, contract: str) -> dict[str, Any]:
    policy = _object(value, contract=contract, path="expectation_policy")
    _keys(policy, contract=contract, required={"schema_version", "default_mode", "field_modes"})
    if policy["schema_version"] != "drawing-setup-expectation-policy-1.0":
        _fail(contract, "expectation_policy.schema_version is invalid")
    if policy["default_mode"] != "GATING":
        _fail(contract, "expectation_policy.default_mode must be GATING")
    modes = _object(policy["field_modes"], contract=contract, path="expectation_policy.field_modes")
    for path, mode in modes.items():
        if path not in _EXPECTATION_POLICY_PATHS or mode not in {"GATING", "OBSERVATION_ONLY"}:
            _fail(contract, f"expectation_policy.field_modes.{path} is invalid")
    return policy
```

The implementation must not add a policy to `drawing_profile-1.0`; policy is a plan-level opt-in and is hash-bound by the plan/evidence hashes.

- [ ] **Step 4: Run the focused validator tests and the legacy contract tests.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py tests/test_drawing_setup_contracts.py -q`

Expected: PASS, including all existing profile strictness tests and the new policy shape tests.

- [ ] **Step 5: Commit the validator change.**

```powershell
git add cad_agent/drawing_contracts.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: validate drawing setup expectation policies"
```

### Task 3: Factor policy path classification without changing legacy evaluation

**Files:**
- Modify: `cad_agent/drawing_setup.py:332-581`
- Test: `tests/test_cad_agent_drawing_setup.py:matching and policy evaluator tests`

**Interfaces:**
- Consumes: validated plan policy, existing audit mapping, existing `_add_blocker` and `_named_items` helpers.
- Produces: private policy helpers that return `(mode, path)` classification and scoped evidence data; `evaluate_setup_plan()` continues to accept the existing keyword-only `verified_by` and `approval_reference` parameters.

- [ ] **Step 1: Write failing tests for classification and legacy identity.** Add a test that evaluates a no-policy plan and asserts the current evidence keys/status remain unchanged. Add policy tests that assert the policy hash is canonical, every observation-only path is recorded, and no observation-only path appears in `gating_paths`.

```python
def test_no_policy_evaluation_preserves_legacy_evidence_shape() -> None:
    plan = approved_setup_plan()
    evidence = evaluate_setup_plan(
        plan, matching_setup_audit(plan), verified_by="OWNER", approval_reference="LEAN-SETUP-001"
    )
    assert evidence["status"] == "SETUP_VERIFIED"
    assert evidence["blockers"] == []
    assert "verification_scope" not in evidence
```

- [ ] **Step 2: Run the evaluator tests to confirm policy fields are absent and the new assertions fail.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "legacy_evidence or observation_paths" -q`

Expected: the legacy assertion passes and the policy-scoping assertions fail because the evaluator currently compares all fields as gating and emits no scoped evidence.

- [ ] **Step 3: Implement classification helpers using the policy’s default.** Use a pure helper such as `_policy_mode(plan, path)` that returns `GATING` when no policy exists or when a path is not listed, and returns the explicit field mode otherwise. Build sorted path lists from actual comparison units. Do not use observed audit values as expected values and do not mutate `plan` or `audit`.

- [ ] **Step 4: Run focused evaluator tests and verify the no-policy path is unchanged.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "matching_audit or legacy_evidence or observation_paths" -q`

Expected: PASS for existing matching/mismatch tests and for policy path inventory tests; status for the no-policy matching plan remains `SETUP_VERIFIED`.

- [ ] **Step 5: Commit the classification change.**

```powershell
git add cad_agent/drawing_setup.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: classify drawing setup comparison scope"
```

### Task 4: Implement gating-only comparison and observation-only evidence

**Files:**
- Modify: `cad_agent/drawing_setup.py:332-581`
- Test: `tests/test_cad_agent_drawing_setup.py:policy evaluator tests`

**Interfaces:**
- Consumes: Task 3 policy classification and current audit comparison code.
- Produces: policy-aware `evaluate_setup_plan()` evidence with `comparison=NOT_EVALUATED`, `conformance=NOT_ASSERTED`, sorted scope lists, and existing blocker codes only for gating comparisons.

- [ ] **Step 1: Add failing tests for mixed policy behavior.** Cover a passing gating scalar plus an observation-only mismatch; assert no observation blocker and exact observation record. Cover a gating mismatch plus an observation-only mismatch; assert `NEEDS_REVIEW` and only the gating mismatch’s existing blocker code.

```python
def test_mixed_policy_observation_mismatch_never_blocks() -> None:
    plan = _policy_plan(field_modes={"current_layer": "OBSERVATION_ONLY"})
    audit = matching_setup_audit(approved_setup_plan())
    audit["current_layer"] = "OBSERVED-DIFFERENT"
    evidence = evaluate_setup_plan(
        plan, audit, verified_by="OWNER", approval_reference="POLICY-001"
    )
    assert evidence["status"] == "SETUP_VERIFIED"
    assert all(item["path"] != "current_layer" for item in evidence["blockers"])
    assert evidence["observation_records"][0]["comparison"] == "NOT_EVALUATED"
    assert evidence["observation_records"][0]["conformance"] == "NOT_ASSERTED"
```

The test must include at least one concrete gating path in its final mixed-policy fixture; the empty-scope assertion above is an intermediate red regression and must be split into the dedicated empty-scope test in Task 5 so the final mixed test proves `SETUP_VERIFIED` is possible only from a passing non-empty gating subset.

- [ ] **Step 2: Run the mixed-policy tests before implementation.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "mixed_policy or observation_mismatch" -q`

Expected: FAIL because current comparisons add a `setup_incomplete` blocker for the observation-only current-layer mismatch and no observation records exist.

- [ ] **Step 3: Refactor each existing comparison unit behind its mode.** Keep the existing comparisons and `_add_blocker` calls for gating paths. For observation-only paths, validate only the legal marker/shape from Task 2, copy the matching audit value, and append an observation record with the exact keys `path`, `observed_value`, `comparison`, and `conformance`. Treat `layouts=[]`, missing fonts, and unmeasured embedded settings as observations when policy marks them non-gating; do not compare the template custom property in that mode.

- [ ] **Step 4: Emit policy evidence deterministically.** Add the canonical policy hash, sorted `gating_paths`, sorted `evaluated_gating_paths`, sorted `observation_only_paths`, sorted `unresolved_paths`, `verification_scope`, and `conformance_assertion`. Use `verification_scope=GATING_ONLY` only after the non-vacuous guard in Task 5; use `NO_CONFORMANCE_ASSERTION` for empty scope.

- [ ] **Step 5: Run focused policy and legacy tests.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "policy or matching_audit or setup_mismatch or comparison_covers" -q`

Expected: PASS for observation-only non-blocking behavior, mixed gating behavior, all current blocker categories, and unchanged no-policy behavior.

- [ ] **Step 6: Commit scoped evaluation.**

```powershell
git add cad_agent/drawing_setup.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: emit scoped drawing setup observations"
```

### Task 5: Enforce the non-vacuous verification status rule

**Files:**
- Modify: `cad_agent/drawing_setup.py:581-628`
- Modify: `cad_agent/drawing_contracts.py:348-368`
- Test: `tests/test_cad_agent_drawing_setup.py:policy status and require tests`

**Interfaces:**
- Consumes: scoped policy evidence from Task 4.
- Produces: `NEEDS_REVIEW` with `EMPTY_GATING_SCOPE` for empty/all-observation-only policy plans; `SETUP_VERIFIED` only for a non-empty, actually evaluated, fully passing gating scope; `require_setup_verified()` rejects vacuous policy evidence.

- [ ] **Step 1: Write the required red regressions.** Add these exact test cases:

```python
def test_all_observation_only_never_returns_setup_verified() -> None:
    plan = _policy_plan(
        field_modes={
            "variables.INSUNITS": "OBSERVATION_ONLY",
            "variables.MSLTSCALE": "OBSERVATION_ONLY",
            "current_layer": "OBSERVATION_ONLY",
            "required_layers": "OBSERVATION_ONLY",
            "required_styles": "OBSERVATION_ONLY",
            "layouts": "OBSERVATION_ONLY",
            "font_policy": "OBSERVATION_ONLY",
            "embedded_settings": "OBSERVATION_ONLY",
        },
        unresolved={"variables.INSUNITS", "variables.MSLTSCALE", "current_layer", "font_policy"},
    )
    plan["setup_expectations"]["required_layers"] = []
    plan["setup_expectations"]["required_styles"] = {
        "text": [], "dimension": [], "mleader": [], "table": []
    }
    plan["setup_expectations"]["layouts"] = []
    evidence = evaluate_setup_plan(
        plan, matching_setup_audit(approved_setup_plan()),
        verified_by="OWNER", approval_reference="POLICY-EMPTY-001"
    )
    assert evidence["status"] == "NEEDS_REVIEW"
    assert evidence["blockers"] == []
    assert evidence["verification_reason"] == "EMPTY_GATING_SCOPE"
    assert evidence["verification_scope"] == "NO_CONFORMANCE_ASSERTION"
    assert evidence["conformance_assertion"] is False
```

Also add `test_empty_gating_scope_emits_needs_review_reason`,
`test_mixed_gating_and_observation_only_only_gating_mismatch_blocks`, and
`test_require_setup_verified_rejects_vacuous_policy_evidence`. The mixed test
must assert that a passing non-empty gating subset can verify, that an
observation-only mismatch does not block, and that a gating mismatch returns
`NEEDS_REVIEW`.

- [ ] **Step 2: Run the red regressions.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "all_observation_only or empty_gating_scope or mixed_gating_and_observation or vacuous_policy" -q`

Expected: FAIL because the current status expression is `SETUP_VERIFIED if not blockers else NEEDS_REVIEW` and `require_setup_verified()` checks neither policy scope nor conformance assertion.

- [ ] **Step 3: Implement the status guard after blockers are sorted.** For a policy plan, calculate `gating_paths` and `evaluated_gating_paths` from actual comparisons. Return `NEEDS_REVIEW` plus `verification_reason=EMPTY_GATING_SCOPE`, `verification_scope=NO_CONFORMANCE_ASSERTION`, and `conformance_assertion=false` whenever the evaluated gating scope is empty or the M2 mandatory-dimension guard is unresolved/non-gating. Otherwise return `SETUP_VERIFIED` only when all declared gating paths passed and no blockers exist.

- [ ] **Step 4: Extend contract evidence validation without widening legacy status values.** Keep status limited to `SETUP_VERIFIED` and `NEEDS_REVIEW`; validate optional policy evidence fields only when present, require the empty-scope reason/scope combination for `NEEDS_REVIEW` policy evidence, and reject `SETUP_VERIFIED` evidence that declares an empty or unaudited gating scope.

- [ ] **Step 5: Harden `require_setup_verified()`.** Preserve all existing stale-hash and blocker checks, then reject policy evidence unless `verification_scope == "GATING_ONLY"`, `conformance_assertion is True`, and both `gating_paths` and `evaluated_gating_paths` are non-empty with every declared gating path evaluated. Reject `NO_CONFORMANCE_ASSERTION`, `EMPTY_GATING_SCOPE`, and all-observation-only evidence with `DrawingSetupError`.

- [ ] **Step 6: Run status, contract, and downstream tests.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py tests/test_drawing_setup_contracts.py -q`

Expected: PASS, including all new non-vacuous regressions and all existing legacy matching, mismatch, stale-hash, CLI, and contract tests.

- [ ] **Step 7: Commit the non-vacuous gate.**

```powershell
git add cad_agent/drawing_contracts.py cad_agent/drawing_setup.py tests/test_cad_agent_drawing_setup.py
git commit -m "fix: reject vacuous drawing setup verification"
```

### Task 6: Prove CLI compatibility and inspect whether a CLI change is required

**Files:**
- Read: `cad_agent/cli.py:240-322,825-850,1000-1030`
- Test: `tests/test_cad_agent_drawing_setup.py:238-290,721-745`
- Modify: `cad_agent/cli.py` only if the focused tests below prove the existing parser/command cannot consume a validated policy plan.

**Interfaces:**
- Consumes: policy-aware `read_contract()`, `evaluate_setup_plan()`, and evidence validator.
- Produces: unchanged `drawing-setup-plan` and `drawing-setup-verify` command signatures unless a narrowly evidenced parser change is necessary.

- [ ] **Step 1: Add a focused CLI policy-plan verification test without changing the parser.** Write a policy plan and audit JSON to `tmp_path`, invoke `main(["drawing-setup-verify", ...])`, and assert the command writes valid scoped evidence and returns `2` for empty gating scope. Also assert the existing no-policy verified CLI test still returns `0`.

- [ ] **Step 2: Run only the CLI tests.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py -k "drawing_setup_verify_cli or policy_cli" -q`

Expected: PASS with no `cad_agent/cli.py` modification if the command already delegates to `read_contract()` and `evaluate_setup_plan()`.

- [ ] **Step 3: If and only if the focused test fails because the parser cannot express the already-approved policy field, make the smallest existing-command change.** Keep the `drawing-setup-plan` positional/keyword interface backward-compatible, add no new command or transport, and add a parser contract test. If the focused test passes, record `cad_agent/cli.py` as unchanged.

- [ ] **Step 4: Run the complete focused Drawing Setup suite.**

Run: `py -3.11 -m pytest tests/test_cad_agent_drawing_setup.py tests/test_drawing_setup_contracts.py -q`

Expected: PASS and a clean `git diff --check`.

- [ ] **Step 5: Commit only a proven CLI compatibility change, if one exists.**

```powershell
git add cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "test: preserve drawing setup CLI policy compatibility"
```

### Task 7: Run release verification and record bounded gate results

**Files:**
- Modify: `docs/STATUS.md` only after fresh evidence is available
- Read: `scripts/verify.ps1`, `docs/QUALITY.md`, `docs/STATUS.md`

**Interfaces:**
- Consumes: all implementation commits and focused test evidence.
- Produces: full verification output, clean diff evidence, and truthful status documentation; no claim for a live AutoCAD gate that was not run.

- [ ] **Step 1: Run the authoritative repository verification.**

Run: `.\scripts\verify.ps1`

Expected: exit code `0`; record the exact output and any explicitly reported skips.

- [ ] **Step 2: Run the final diff and worktree checks.**

Run: `git diff --check; git status --short; git rev-parse HEAD`

Expected: no whitespace errors, only intended plan/spec/status changes, and a recorded final implementation HEAD SHA.

- [ ] **Step 3: Run the specialized live gate only if the changed owner is exercised.**

Run the affected `autocad_mechanical` smoke test exactly as defined by the current `scripts/verify.ps1`/quality contract. Do not issue a second `drawing_setup_verify` request and do not mutate the disposable DWG. If the prerequisite is absent, record `NOT RUN` or `SKIP`, never `PASS`.

- [ ] **Step 4: Update `docs/STATUS.md` with only fresh evidence.** Record the approved contract change, focused tests, full verification result, live-gate status, and any deferred item with owner/reason. Do not claim `SETUP_VERIFIED` for the prior failed live projection.

- [ ] **Step 5: Mark this plan completed only after evidence is recorded.** Set the plan status to `completed`, add the completion Head SHA immediately before the lifecycle-closing commit, and record the exact verification command/result and required private/live gate outcomes. Do not check boxes based on historical commits.

- [ ] **Step 6: Commit the status/evidence record.**

```powershell
git add docs/STATUS.md docs/superpowers/specs/2026-09-09-drawing-setup-expectation-policy-contract-change-v2.md docs/superpowers/plans/2026-09-09-drawing-setup-expectation-policy-contract-change.md
git commit -m "docs: record drawing setup policy verification"
```

## Plan self-review

- Spec coverage: policy validation is Task 2; legacy preservation and path classification are Task 3; scoped observation semantics are Task 4; non-vacuous status and downstream rejection are Task 5; CLI compatibility is Task 6; verification and truthful status are Task 7.
- Placeholder scan: the plan contains no `TBD`, `TODO`, or unspecified implementation step; the only conditional file change is the explicitly approved CLI compatibility guard.
- Type consistency: `_validate_expectation_policy` returns `dict[str, Any]`; `_policy_mode` consumes a `Mapping[str, object]` plan and returns a mode string; `evaluate_setup_plan()` and `require_setup_verified()` retain their current public parameters.
- Scope check: all work stays inside the existing Drawing Setup contract/evaluator and its tests; no independent subsystem or new transport is introduced.

## Record status

- Status: planned
- Base SHA: `2d320361e2146d0602aac6f226f5bffed5f931a5`
- Completion Head SHA: not yet completed
- Exact verification command/result: not run; plan creation only
- Required private/live gates: AutoCAD/FileIPC smoke not run; no live owner invocation authorized by this plan stage
