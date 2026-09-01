# Phase 2 Mechanical Skill Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, read-only Mechanical skill catalog that searches existing capability metadata and compiles one bounded plan without executing CAD or arbitrary code.

**Architecture:** The catalog is immutable in-code metadata, hashed with the existing canonical JSON helper, and exposed through defensive copies. Search is deterministic lexical/tag ranking. Invocation validates the exact current Phase 1 observation through `cad_read_facade.validate_observe_drawing_result`, validates catalog-owned parameters, and emits one closed plan; execution remains with the existing typed owner outside this module.

**Tech Stack:** Python 3.11, pytest, existing `cad_agent.cad_read_facade`, `cad_agent.drawing_contracts.canonical_json_sha256`, and current `mechanical_bom` route metadata.

**Spec:** GitHub Issue #352 and planning Issue #283, rebaselined from current main after PR #354.

## Global Constraints

- Current basis is `main=646b1b2dfda38f9513edcf41d83a995fc1e7302c`.
- Only create `cad_agent/mechanical_skills.py` and `tests/test_cad_agent_mechanical_skills.py`, plus this implementation plan record.
- Use no provider/API/key/billing, M2 evidence, PR #340/#337, AutoCAD live mutation, FileIPC transport changes, shell, subprocess, dynamic import, eval/exec, or runtime registry/database.
- Keep Phase 1 DARA/R3/R4 currentness and the existing `mechanical_bom` owner authoritative.
- Deferred skills are searchable metadata only and cannot be invoked.
- An invocation compiles data only; it never executes an owner, opens/saves/mutates a drawing, or self-certifies PASS.

---

### Task 1: Define causal RED tests for catalog, search, and compilation

**Files:**
- Create: `tests/test_cad_agent_mechanical_skills.py`

**Interfaces:**
- Consumes: existing Phase 1 test fixture output from `tests/test_cad_agent_cad_read_facade.py` and current `cad_read_facade.validate_observe_drawing_result`.
- Produces: tests for `get_mechanical_skill_catalog`, `validate_mechanical_skill_catalog`, `search_skills`, `invoke_skill`, and `validate_skill_invocation_plan`.

- [ ] **Step 1: Build a real owner observation fixture**

Load the existing Phase 1 test module with `importlib.util.spec_from_file_location`, call its `_bound_kwargs()` and `_client()`, and obtain a valid `observe_drawing` result through the current facade. Do not construct hash-only identity stand-ins.

- [ ] **Step 2: Add the missing public-contract tests**

The tests must assert the following behavior:

```python
catalog = skills.get_mechanical_skill_catalog()
assert catalog["schema_version"] == "mechanical-skill-catalog-1.0"
assert [item["skill_id"] for item in skills.search_skills("mechanical bom")] == [
    "inspect.mechanical_bom"
]
plan = skills.invoke_skill(
    "inspect.mechanical_bom", parameters={}, drawing_observation=observation
)
assert plan["owner_route_id"] == "DOTNET_IPC_MECHANICAL_BOM_READ"
assert plan["operation_plan"] == {
    "operation": "mechanical_bom",
    "parameters": {},
}
```

Cover deterministic catalog/hash replay, defensive catalog copies, unknown/extra fields, tampered catalog/record hashes, empty/oversized intent, limit/type confusion, deterministic ranking, deferred-hidden/default and include-deferred behavior, exact read-only plan binding, invalid parameters, invalid/tampered observation, and refusal of deferred skills.

- [ ] **Step 3: Add security/no-side-effect tests**

Assert invocation returns a plan without calling any client or execution owner. Add a source guard that rejects `eval`, `exec`, `importlib`, `subprocess`, `os.system`, raw AutoLISP/command strings, and mutation-owner imports in the production module. Assert plan root/nested keys are closed and caller cannot provide a route override.

- [ ] **Step 4: Run RED**

```powershell
& C:\temp\cad-agent-phase2-skill-facade\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_mechanical_skills.py -q
```

Expected: collection or contract failures state that `cad_agent.mechanical_skills` is absent; no implementation code exists yet.

- [ ] **Step 5: Commit RED**

```powershell
git add tests/test_cad_agent_mechanical_skills.py
git commit -m "test: define deterministic mechanical skill catalog"
```

### Task 2: Implement the smallest immutable catalog and compiler

**Files:**
- Create: `cad_agent/mechanical_skills.py`

**Interfaces:**
- Consumes: `cad_agent.cad_read_facade.validate_observe_drawing_result` and `cad_agent.drawing_contracts.canonical_json_sha256`.
- Produces: `get_mechanical_skill_catalog()`, `validate_mechanical_skill_catalog(payload)`, `search_skills(intent, *, category=None, limit=10, include_deferred=False)`, `invoke_skill(skill_id, *, parameters, drawing_observation)`, and `validate_skill_invocation_plan(payload)`.

- [ ] **Step 1: Define closed schemas and categorical errors**

Use exact versions `mechanical-skill-1.0`, `mechanical-skill-catalog-1.0`, and `skill-invocation-plan-1.0`. Use `MechanicalSkillError(ValueError)` with stable codes only. Define exact root, record, operation-plan, and invocation-plan field sets; reject booleans where integer limits are required.

- [ ] **Step 2: Build immutable metadata**

Create one enabled read-only record:

```python
{
    "skill_id": "inspect.mechanical_bom",
    "skill_version": "1.0",
    "category": "inspection",
    "title": "Inspect Mechanical BOM",
    "description": "Read the existing bounded Mechanical BOM capability.",
    "intent_tags": ["mechanical", "bom", "inspect", "read"],
    "required_context": ["DRAWING_CURRENT"],
    "parameter_schema_id": "NO_PARAMETERS",
    "output_kind": "READ_REQUEST_PLAN",
    "owner_route_id": "DOTNET_IPC_MECHANICAL_BOM_READ",
    "capability_refs": ["mechanical_bom"],
    "evidence_requirements": ["DRAWING_IDENTITY", "TERMINAL_RESULT"],
    "protected_constraint_policy": "READ_ONLY",
    "max_operations": 1,
    "compatibility_version": "cad-agent-main-1",
    "support_state": "READ_ONLY",
    "blocked_by": None,
}
```

Add only the deferred roadmap metadata needed for the first Mechanical pilot (`geometry.shaft_step`, `geometry.keyway`, `geometry.hole_feature`) with support state `DEFERRED_UNSUPPORTED`; no raw primitive alias becomes a Mechanical skill. Add record and catalog hashes from existing canonical JSON.

- [ ] **Step 3: Implement deterministic search**

Normalize bounded non-empty intent into Unicode alphanumeric/underscore/hyphen tokens. Rank exact skill ID, exact tag matches, then category/title token matches, with stable `(skill_id, skill_version)` tie-break. Default to `READ_ONLY`/`ENABLED`; `include_deferred=True` returns deferred metadata but never changes invocability. Return defensive copies.

- [ ] **Step 4: Implement validation and plan compilation**

Validate the current internal catalog and exact skill. Accept only read-only supported records, require exactly `{}` for `NO_PARAMETERS`, validate the observation with the Phase 1 owner seam before copying its binding, and compile exactly one closed `mechanical_bom` operation descriptor. Include catalog/record hashes, risk/evidence metadata, exact observation binding, `max_operations=1`, and a deterministic `plan_sha256`. Do not include paths, request IDs, HWNDs, IPC roots, shell commands, callables, credentials, or approval claims.

- [ ] **Step 5: Run GREEN and lint**

```powershell
& C:\temp\cad-agent-phase2-skill-facade\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_mechanical_skills.py -q
& C:\temp\cad-agent-phase2-skill-facade\.venv-py311\Scripts\ruff.exe check cad_agent/mechanical_skills.py tests/test_cad_agent_mechanical_skills.py
git diff --check
```

Expected: all new tests pass with no warnings.

- [ ] **Step 6: Commit GREEN**

```powershell
git add cad_agent/mechanical_skills.py tests/test_cad_agent_mechanical_skills.py
git commit -m "feat: add deterministic mechanical skill compiler"
```

### Task 3: Verify, record, and stop at the next genuine frontier

**Files:**
- Read-only verification of the two implementation paths and current main contracts.

**Interfaces:**
- Consumes: the committed Phase 2 module/tests.
- Produces: exact test evidence and the next Phase 3 boundary; no live execution.

- [ ] **Step 1: Run relevant regression and authoritative verification**

Run the new focused suite, Phase 1 facade/validator tests, architecture/reuse checks, then `scripts/verify.ps1` with the locked Python 3.11 environment. Record all skipped/unavailable live markers explicitly.

- [ ] **Step 2: Verify write-set and no side effects**

Confirm only the plan plus the two Phase 2 paths differ from current main, no drawing/source/customer/accepted artifact changed, no provider/M2/CAD action occurred, and the module contains no forbidden execution surface.

- [ ] **Step 3: Record GitHub evidence**

Post the exact base/head, focused and authoritative results, catalog route, refusal cases, and no-side-effect evidence to Issue #352. Do not claim Phase 3 capability or provider/live acceptance from this compile-only slice.
