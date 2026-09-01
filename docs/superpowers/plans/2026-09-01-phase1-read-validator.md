# Phase 1 Read Result Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a pure owner-owned validator for the existing `observe_drawing` result so Phase 2 can bind a plan without duplicating CAD currentness logic.

**Architecture:** Extend `cad_agent.cad_read_facade` with one validation seam for its already-closed result shape. The validator checks schema, closed keys, bounded summary data, binding identity fields, and the existing canonical result hash, then returns a defensive copy. It performs no AutoCAD/FileIPC call and does not become a second drawing-currentness authority.

**Tech Stack:** Python 3.11, pytest, existing `cad_agent.drawing_contracts.canonical_json_sha256`, existing Phase 1 facade fixtures.

**Spec:** GitHub Issue #353, `[Phase 1] Expose validated read-result seam for Phase 2 binding`.

## Global Constraints

- Current basis is `main=84689546d120566e297cb24c6a95995ca645b1a2`.
- Keep the exact owner boundary in `cad_agent/cad_read_facade.py`; do not modify DARA, R3, R4, FileIPC, AutoCAD, provider, M2, or PR #340.
- Reject unknown fields, tampered hashes, malformed identities, and oversized payloads with categorical `CadReadFacadeError` codes.
- Do not claim that the validator independently proves a live drawing is current; live currentness remains owned by `observe_drawing` and its existing inputs.
- Preserve all existing Phase 1 behavior and tests.

---

### Task 1: Add the causal validator contract tests

**Files:**
- Modify: `tests/test_cad_agent_cad_read_facade.py`

**Interfaces:**
- Consumes: existing `_facade()`, `_bound()`, and `_client()` test fixtures and `observe_drawing`.
- Produces: assertions for `validate_observe_drawing_result(payload) -> dict[str, object]`.

- [ ] **Step 1: Write the failing tests**

Add tests that first build a real `observe_drawing` payload through the existing owner, then assert:

```python
validated = _facade().validate_observe_drawing_result(payload)
assert validated == payload
assert validated is not payload

tampered = deepcopy(payload)
tampered["binding"]["artifact_sha256"] = "0" * 64
with pytest.raises(_facade().CadReadFacadeError, match="RESULT_HASH_MISMATCH"):
    _facade().validate_observe_drawing_result(tampered)

extra = deepcopy(payload)
extra["unexpected"] = True
with pytest.raises(_facade().CadReadFacadeError, match="RESULT_SCHEMA_INVALID"):
    _facade().validate_observe_drawing_result(extra)
```

Also cover a wrong `operation`, a mismatched `query_id`, a malformed binding SHA, and an oversized summary sample. The tests must call no live owner beyond the existing fixture client used to produce the valid payload.

- [ ] **Step 2: Run the focused tests to verify the expected RED**

Run:

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_cad_read_facade.py -q
```

Expected: the new tests fail because `cad_read_facade.validate_observe_drawing_result` is not yet exported; existing Phase 1 tests remain otherwise green.

- [ ] **Step 3: Commit the causal RED**

```powershell
git add tests/test_cad_agent_cad_read_facade.py
git commit -m "test: define phase1 read result validation seam"
```

### Task 2: Implement the minimal owner validator

**Files:**
- Modify: `cad_agent/cad_read_facade.py`

**Interfaces:**
- Consumes: an `observe_drawing` result returned by this module.
- Produces: `validate_observe_drawing_result(payload) -> dict[str, object]`, exported in `__all__`.

- [ ] **Step 1: Implement closed-shape validation**

Implement the function with these exact checks:

1. Require a `Mapping` and exact root keys `schema_version`, `operation`, `binding`, `summary`, `query_id`, and `result_sha256`.
2. Require `schema_version == CAD_READ_FACADE_SCHEMA_VERSION` and `operation == "observe_drawing"`.
3. Require the exact twelve binding keys emitted by `_validated_binding`; every identity field is a non-empty string and every `*_sha256` binding field is a lowercase 64-character SHA-256.
4. Require summary keys `entity_count`, `by_type`, `by_layer`, and `sample_entities`; counts are non-negative integers, maps have string keys and non-negative integer values, and the sample has at most `MAX_SUMMARY_SAMPLE_COUNT` entries of the exact `handle`/`type`/`layer` shape.
5. Rebuild the hash input from the four owner payload fields (`schema_version`, `operation`, `binding`, `summary`) and verify `result_sha256 == canonical_json_sha256(hash_input)` and `query_id == "cad-query-" + result_sha256`.
6. Serialize the full result with the same bounded JSON settings used by `_finish_result` and reject values over `MAX_QUERY_RESULT_BYTES`.
7. Return `deepcopy(dict(payload))`; never call client, AutoCAD, FileIPC, mutation, or provider code.

Use categorical existing exception `CadReadFacadeError`; add only the narrow error codes named by the tests.

- [ ] **Step 2: Run the focused tests to verify GREEN**

```powershell
& .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_cad_read_facade.py -q
```

Expected: all Phase 1 facade tests pass, including the new validator cases.

- [ ] **Step 3: Run lint and diff checks**

```powershell
& .\.venv-py311\Scripts\ruff.exe check cad_agent/cad_read_facade.py tests/test_cad_agent_cad_read_facade.py
git diff --check
```

Expected: exit code 0 with no warnings.

- [ ] **Step 4: Commit the minimal GREEN**

```powershell
git add cad_agent/cad_read_facade.py tests/test_cad_agent_cad_read_facade.py
git commit -m "feat: expose validated phase1 read result"
```

### Task 3: Verify the owner seam and hand off to Phase 2

**Files:**
- Read-only: `cad_agent/cad_read_facade.py`, `tests/test_cad_agent_cad_read_facade.py`

**Interfaces:**
- Consumes: the committed validator and existing Phase 1 test suite.
- Produces: privacy-safe Issue #353 evidence and a current Phase 2 rebaseline for Issue #352.

- [ ] **Step 1: Run the authoritative verification**

```powershell
& .\scripts\verify.ps1
```

Record the exit code and test totals; do not reinterpret `SKIP` or `NOT RUN` as PASS.

- [ ] **Step 2: Confirm repository scope and runtime safety**

Verify `git diff --name-only origin/main...HEAD` contains only the plan plus the two owner/test paths, no CAD drawing changed, and no provider/M2 process or credential was used.

- [ ] **Step 3: Record the bounded evidence**

Post only schema/error/oracle/test evidence to Issue #353. Do not claim Phase 2 accepted until its own rebaseline and tests pass. The next Phase 2 write-set remains `cad_agent/mechanical_skills.py` and `tests/test_cad_agent_mechanical_skills.py`, subject to this validator contract.
