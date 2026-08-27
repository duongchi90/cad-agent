# Phase 0 Closure + Phase 1 Thin CAD Query Slice — Implementation Plan

Date: 2026-08-27
Status: READY FOR EXECUTION AFTER PHASE-0 CLOSURE GATE
Master Roadmap: Issue #291
Approved design: `docs/superpowers/specs/2026-08-27-master-roadmap-design.md`
Design commit: `fde08fbc92b8bf1e8d86b60785c792f6704b60f6`
Planning branch: `governance/master-roadmap-design`
Authority effect: NONE

## Goal

Close the already-staged Phase 0 minimum workforce gate without inventing more governance slices, then implement one bounded Phase 1 read-only CAD query façade that proves exact drawing-currentness identity and bounded entity reads for the first real Mechanical vertical slice.

This plan deliberately does **not** implement Phase 2 skills, Phase 3 Mechanical geometry, Phase 4 image-to-CAD, new Local Executor capabilities, new transport, or new authority/state stores.

## Global constraints

- Fresh-read Issue #131, current `main`, PR #286, PR #289, Issue #290 and their exact current CI/reviewer state before any execution decision.
- Issue #131 remains sole mutable runtime/control authority.
- Phase 0 is considered a precondition, not a new implementation program. Do not open E2/E3/E4 merely because more process hardening is possible.
- Reuse the existing `mcp_integration_lib.MCPClient.entity_list()` and `entity_get()` surfaces. Do not modify transport/LISP/.NET/AutoCAD code for Phase 1 V1 unless a causal RED proves an actual missing owner seam and scope is separately amended.
- Reuse `cad_agent.drawing_artifact_reference.require_current_drawing_artifact_reference(...)` as the currentness gate. Do not invent a second drawing-state hash/store.
- New product code for this plan is additive and read-only.
- No arbitrary query expressions, joins, user predicates, callbacks, scripts, shell text, or unbounded result sets.
- Every successful result must carry the exact existing drawing/reference/currentness identity used for the read.
- TDD: commit meaningful RED before the production behavior that makes it GREEN.
- AutoCAD live is NOT RUN for this first slice unless a separately authorized acceptance gate later proves it necessary.
- Rollback is an ordinary forward revert. No persisted-data migration, DB migration, package/dependency migration, rebase, amend, squash, or force-push.

## Exact intended Phase 1 write-set

CREATE ONLY:

- `cad_agent/cad_query.py`
- `tests/test_cad_query.py`

No other production/test path is required by the initial plan. If a third code/test path becomes necessary, STOP and amend the delivery issue/write-set before writing it.

The approved design/plan files live on the planning branch and are not part of the Phase 1 production write-set.

---

## Task 0 — Close Phase 0 minimum gate using existing work only

### Purpose

Finish the existing A-D/E1 acceptance chain and then stop Phase 0 expansion.

### Read-only/finalization steps

1. Fresh-read canonical state:
   - newest valid numbered authority + terminal on Issue #131;
   - current `main` SHA/tree;
   - PR #286 base/head/state/CI/review;
   - PR #289 base/head/state/CI/review;
   - Issue #290 independent-review verdict.
2. Require PR #289's exact reviewed head to still match the independent review tuple. Head drift invalidates the review packet.
3. If #290 reports CHANGES REQUIRED, repair only under the existing E1 issue/write-set and causal finding. Do not create a successor governance capability merely to improve elegance.
4. If #290 reports PASS and predecessor evidence is still exact, perform the normal anti-race/acceptance reconciliation required by current governance.
5. Do not dispatch real self-hosted/local work while another numbered mission owns the single Local Executor lane.
6. Do not merge or move `main` unless current authority and Human/standing merge policy explicitly allow it.

### Phase 0 exit check

Record `ACCEPTED` only when the active accepted implementation path demonstrates:

- fresh-session currentness recovery;
- Web/local/Human routing;
- bounded mission + typed executor consumption without arbitrary shell execution;
- exact evidence reuse/first-gate selection;
- known-failure probe selection;
- required independent security/operations review;
- no duplicate truth/control/transport owner.

After this, Phase 0 moves to failure-driven maintenance. No planned E2/E3/E4 follows from this plan.

---

## Task 1 — RED: exact currentness must gate every CAD read

### Files

CREATE: `tests/test_cad_query.py`

### Tests to write first

Use `FakeMCPClient` or a tiny recording `MCPClient`-compatible double. Reuse valid DARA fixtures/builders from `tests/test_drawing_artifact_reference.py` rather than inventing a second reference contract.

Add focused tests proving:

1. `read_state(...)` succeeds only when `require_current_drawing_artifact_reference(...)` accepts the exact reference/observation/artifact bytes.
2. stale artifact bytes fail before any client read occurs.
3. stale/mismatched DARA observation fails before any client read occurs.
4. successful state output includes only closed identity fields derived from the existing DARA/currentness material, including at minimum:
   - `run_id`;
   - `project_id`;
   - `drawing_id`;
   - `artifact_sha256`;
   - `reference_id`;
   - `reference_sha256`;
   - `lookup_id`;
   - `lookup_sha256`.
5. no local timestamp/cache token/new revision id is invented by the façade.

### RED command

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
```

Expected: import/module failures because `cad_agent.cad_query` does not yet exist.

Commit the RED before production creation.

Suggested commit message:

```text
test: define currentness-bound cad query contract
```

---

## Task 2 — GREEN: minimal currentness-bound read façade

### Files

CREATE: `cad_agent/cad_query.py`

### Minimal implementation

Implement a small pure/read-only adapter with a dedicated `CadQueryError`.

Recommended first API shape:

```python
read_state(
    *,
    reference,
    observation,
    artifact_bytes: bytes,
    parent_reference=None,
    accepted_transition_evidence_sha256=None,
) -> dict[str, object]

query_entities(
    client,
    *,
    reference,
    observation,
    artifact_bytes: bytes,
    query: Mapping[str, object],
    parent_reference=None,
    accepted_transition_evidence_sha256=None,
) -> dict[str, object]
```

Rules:

1. Call `require_current_drawing_artifact_reference(...)` before any `client.entity_list()` or `client.entity_get()` call.
2. Build identity output only from validated existing reference/observation fields.
3. No filesystem/cache/network/process side effects inside the adapter.
4. Do not add a new schema package or persistent state object in V1.

### GREEN command

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
```

Expected: Task 1 tests PASS.

Suggested commit message:

```text
feat: add currentness-bound cad read facade
```

---

## Task 3 — RED: close the V1 query language and bound fan-out

### Files

MODIFY: `tests/test_cad_query.py`

### Closed query shape

Define one closed request mapping. Keep V1 deliberately small:

```text
types
layers
region
fields
mode
group_by
limit
```

Recommended semantics:

- `types`: unique list of supported entity type strings, empty = no type filter;
- `layers`: unique list of exact layer names, empty = no layer filter;
- `region`: `NONE` or a closed axis-aligned 2D bounding box `{xmin, ymin, xmax, ymax}`;
- `fields`: unique whitelist projection fields;
- `mode`: exactly `ENTITIES`, `COUNT`, or `GROUP`;
- `group_by`: `NONE`, `type`, or `layer`; only meaningful for `GROUP`;
- `limit`: positive bounded integer with a conservative fixed maximum.

### Projection whitelist

Start only with fields already returned by current `entity_list` / `entity_get` owners and needed by the pilot, for example:

```text
handle
type
layer
start
end
center
radius
start_angle_deg
end_angle_deg
insert
content
height
rotation_deg
```

Do not add a generic `properties` bag.

### RED tests

Add tests proving:

1. unknown query field fails closed;
2. unknown projection field fails closed;
3. arbitrary callable/predicate/expression-like values fail type validation;
4. `limit` above fixed maximum fails before entity reads;
5. duplicate filter/projection values fail or canonicalize deterministically per chosen contract;
6. invalid region bounds fail closed;
7. unsupported `mode/group_by` combinations fail closed;
8. successful output order is deterministic by handle;
9. `ENTITIES` does not silently truncate: if matches exceed `limit`, return a bounded-query error instructing the caller to narrow the query;
10. response shape is closed and includes exact state/reference identity beside `result`/summary fields.

Run:

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
```

Expected: new tests FAIL against the minimal Task 2 implementation.

Commit RED.

Suggested commit:

```text
test: close and bound cad entity queries
```

---

## Task 4 — GREEN: typed filters, field projection, count/group

### Files

MODIFY: `cad_agent/cad_query.py`

### Implementation rules

1. Call `client.entity_list(layer=...)` only through existing typed API.
2. When multiple layers are requested, either make one bounded call per unique layer or make one all-layer call and filter locally; choose the simpler path with deterministic bounded behavior and test it.
3. Use entity-list summaries to prefilter `handle/type/layer` before detail reads.
4. Call `entity_get(handle)` only when requested fields or region semantics require detail.
5. Cap detail fan-out with a fixed internal candidate maximum independent of caller `limit`.
6. `COUNT` should avoid detail reads when filters can be satisfied from summaries.
7. `GROUP` is limited to `type` or `layer` and should avoid detail reads where possible.
8. `ENTITIES` returns only requested whitelist fields plus mandatory identity fields needed to interpret each item (`handle/type/layer` as contractually chosen).
9. Treat malformed current owner output as `CadQueryError`; do not guess/fill geometry.
10. Sort results and group keys deterministically.

### Focused GREEN

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
```

Suggested commit:

```text
feat: add bounded typed cad entity queries
```

---

## Task 5 — RED/GREEN: bounded region semantics only for proven geometry

### Files

MODIFY: `tests/test_cad_query.py`
MODIFY: `cad_agent/cad_query.py`

### Scope

Do not build a general spatial engine. Support only the exact entity geometry needed by the first pilot and already exposed by `entity_get()`.

Start with a narrow set such as:

- `LINE` via `start/end`;
- `CIRCLE` via `center/radius`;
- `ARC` via `center/radius` using a conservative circle-envelope test for V1 if exact arc intersection is not needed by the pilot;
- `TEXT` via insertion point only if the pilot requires text filtering.

If the pilot does not require a type, do not add its region semantics.

### RED tests

Prove:

- stale currentness still blocks before any region detail reads;
- unsupported entity type under region query fails closed or is excluded only under an explicit tested contract — never guessed;
- candidate detail fan-out cap is enforced;
- boundary-touching geometry follows one documented inclusive rule;
- region queries remain deterministic and bounded.

Commit RED first.

Suggested RED commit:

```text
test: define bounded cad region semantics
```

### GREEN

Implement the smallest tested geometry overlap checks only.

Suggested GREEN commit:

```text
feat: support bounded pilot region queries
```

Focused command after each step:

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
```

---

## Task 6 — Reuse/integration regression proof

### Files

No new production path expected.

### Focused regressions

Run:

```powershell
py -3.11 -m pytest tests/test_cad_query.py -q
py -3.11 -m pytest tests/test_drawing_artifact_reference.py -q
py -3.11 -m pytest mcp_integration_lib/tests/test_entity_get_type_shadow.py -q
```

Add the nearest existing MCP entity-list/get tests if their filenames are identified during execution. Do not broaden to unrelated AutoCAD live gates.

### Reuse assertions to record in the delivery PR

- Existing capability inspected: DARA currentness, `MCPClient.entity_list`, `MCPClient.entity_get`, `FakeMCPClient`, current File-IPC/AutoCAD read owner.
- Existing API reused: exact methods above.
- Adapter required: only a thin read-only façade enforcing currentness, closed filtering/projection and bounded summaries.
- New capability genuinely missing: one provenance-bound bounded query façade for LLM consumption; not a new transport/entity store/query DB.
- Forbidden duplicates: transport/LISP/.NET owner, drawing mirror, cache truth store, generic query engine, SQL/expression evaluator.

### Diff checks

Require exact implementation write-set:

```text
cad_agent/cad_query.py
tests/test_cad_query.py
```

Any third production/test path => STOP and reconcile scope.

Run:

```powershell
git diff --check
```

---

## Task 7 — Authoritative hosted verification on exact head

### Preconditions

- focused tests GREEN;
- exact intended two-path production/test diff;
- clean repository at verification start;
- no unresolved P0/P1 security/currentness finding;
- exact head SHA recorded.

### Verification

Use the repository's existing authoritative hosted verification path on Windows/Python 3.11. Do not introduce a new workflow.

Required evidence:

- exact head SHA/tree;
- focused test counts;
- DARA regression result;
- MCP entity read regression result;
- full offline verifier result;
- reuse-declaration gate result if applicable;
- AutoCAD/live explicitly `NOT_RUN` unless separately authorized;
- artifact IDs/hashes where the existing workflow provides them.

If full verification exposes an unrelated pre-existing failure, classify it from evidence; do not mutate product scope to make CI green.

---

## Task 8 — Independent review and pilot handoff

### Review focus

For the exact final head, independently verify:

1. currentness check executes before any CAD read;
2. query shape is closed and cannot express arbitrary code/predicates;
3. result/detail fan-out is bounded;
4. every successful response binds to exact existing DARA identity/currentness;
5. no shadow drawing state, cache truth, transport or query subsystem was introduced;
6. malformed/stale owner output fails closed;
7. implementation remains read-only;
8. exact write-set is only the approved two code/test paths.

### Phase 1 disposition

If review/CI passes, record Phase 1 as `VERTICAL_SLICE_PASS` only when the selected real Phase 4 pilot actually consumes the façade successfully. Offline contract completion alone is `FOUNDATION_EXISTS`, not product acceptance.

Then open the smallest Phase 2 skill-façade issue driven by the exact pilot capability need. Do not pre-plan a broad skill catalog or Mechanical library.

---

## Acceptance summary

This plan is complete when:

- Phase 0 existing work reaches its already-required minimum acceptance boundary without a speculative successor governance program;
- Phase 1 adds exactly one thin read-only façade over existing MCP + DARA owners;
- stale drawing identity blocks before any read;
- queries are typed, closed and bounded;
- no second transport/state/query engine is created;
- hosted verification and independent review pass on the exact head;
- the real pilot can use the façade, after which evidence — not catalog ambition — determines the next capability.