# R3 Component/View Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planning only. Runtime is not authorized by Issue #128.

**Planning date:** 2026-08-08

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Goal:** Add a deterministic Component/View Registry that binds accepted R1 source/projection evidence, accepted R2 base-CAD evidence, Semantic membership, and candidate-only CAD bindings without creating a second geometry, CAD, persistence, revision, approval, verdict, or publication authority.

**Architecture:** Implement R3 as a strict pure-Python orchestration adapter under `cad_agent`. Logical component/view/link IDs are canonical evidence identities independent of volatile CAD handles; candidate handles are snapshot bindings only. Upstream R1/R2 validation remains authoritative, and durable registry references may be added only through the existing `cad_agent.manifest` owner after a separate overlap/rebaseline gate.

**Tech Stack:** Python 3.11, existing `cad_agent.drawing_contracts.canonical_json_sha256()`, existing R1/S3/R2 accepted validators after rebaseline, existing Primitive/Semantic models and owners, pytest, Ruff, current architecture/reuse ratchets, `scripts/verify.ps1 -SkipAutoCADDotNet`, GitHub hosted `tests` and `reuse-declaration`. No new dependency.

## Global Constraints

- Authoritative design: `docs/superpowers/specs/2026-08-08-r3-component-view-registry-design.md`.
- Parent product design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Reuse inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- Preserve `primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib` ownership.
- `cad_agent` remains orchestration only; R3 must not absorb parser, OCR, solver, CAD-geometry, AutoCAD, repair, revision, verdict, or publisher behavior.
- Canonical registry hashing must reuse `cad_agent.drawing_contracts.canonical_json_sha256()`; do not add a second canonical serializer/hash owner.
- Numeric evidence is consumed only after accepted upstream canonicalization; R3 adds no numeric policy.
- No source/base/accepted CAD mutation. R3 core performs no CAD mutation at all.
- Candidate handles/block references are bindings, never logical component/view identity.
- No private/customer CAD and no live AutoCAD required for RED/GREEN.
- No dependency, lock, workflow, schema package, database, CAS, manifest replacement, or revision store.
- No approval, apply, visual verdict, promotion, repair, rollback, or publication authority.
- R3 runtime remains BLOCKED until final R1 and R2 are accepted and Master PO explicitly issues runtime work after a fresh post-R2 rebaseline.
- Do not invent a moving R2 API. Resolve exact accepted R2 symbols/fields in the runtime Issue before any R3 repository write.
- Every runtime task is RED-first and uses normal forward commits only.
- Missing AutoCAD/private-data prerequisites are `NOT RUN` or `SKIP`, never `PASS`.

---

## 0. Mandatory post-R2 issuance rebaseline — no repository write

This gate happens before Task 1 and is a Master-PO/runtime-issuance action, not a code task.

Record the following exact accepted symbols and paths in the future runtime Issue:

1. final R1 deterministic source/Primitive/Semantic projection validator/API symbol(s);
2. final R1 projection identity fields used to map stable source/semantic evidence;
3. final R2 Base CAD Adapter validator/API symbol(s);
4. final R2 evidence fields proving candidate drawing identity, base source ID/SHA/revision, reused component membership, source handle/layer/block, local transform provenance, and stale/revision status;
5. final R2 production/test paths and current open writer overlaps;
6. current `cad_agent.manifest` owner shape and whether an optional R3 artifact reference can be added compatibly.

The planning document intentionally does not name a not-yet-accepted R2 function.

**STOP immediately with `R3 UPSTREAM CONTRACT GAP` if:**

- R1 has no accepted deterministic projection identity suitable for registry membership;
- R2 cannot provide the required base/candidate/provenance facts without R3 calling AutoCAD or reimplementing exact-base extraction;
- accepted R2 requires a conflicting writer on a proposed R3 core path;
- a new store/schema/transport owner appears necessary.

No repository mutation occurs in this gate.

---

## File structure for R3 core

Preferred core runtime ownership:

```text
cad_agent/
  component_view_registry.py

tests/
  test_cad_agent_component_view_registry.py
```

The first three runtime tasks use only these two paths.

A fourth separately issued integration task may modify the existing manifest owner:

```text
cad_agent/manifest.py
tests/test_cad_agent_component_view_registry.py
```

Only issue that fourth task if the post-R2 overlap check is PASS. If R2 or another active writer owns `cad_agent/manifest.py`, defer the manifest task; do not rebase or widen R3 core.

---

### Task 1: Closed deterministic component registry core

**Purpose:** Establish the smallest R3 owner: component logical identity, origin classification, candidate binding separation, strict validation, and canonical registry SHA.

**Files:**
- Create: `cad_agent/component_view_registry.py`
- Create: `tests/test_cad_agent_component_view_registry.py`
- Modify: none

**Proposed R3 public surface after Task 1:**

```python
COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION = "component-view-registry-1.0"

class ComponentViewRegistryError(ValueError): ...

def build_component_view_registry(*, upstream_context: object, components: object) -> dict[str, object]: ...

def validate_component_view_registry(payload: object, *, upstream_context: object) -> dict[str, object]: ...

def component_view_registry_sha256(payload: object, *, upstream_context: object) -> str: ...
```

`upstream_context` is an R3 call parameter name, not an invented R2 contract. The runtime implementation must validate/decompose it only through the exact accepted R1/R2 symbols recorded by Gate 0. If Gate 0 cannot bind the required facts, STOP before writing this task.

**Component concepts locked by the design:**

```text
component_id
component_type
origin_class
source_projection_refs
semantic_projection_refs
base_cad_provenance_ref (optional)
view_ids (empty in Task 1)
candidate_entity_bindings
```

**Closed origin classes:**

```text
REUSED_UNCHANGED
RECONSTRUCTED_CHANGED
RECONSTRUCTED_NEW
MIXED_UNRESOLVED
```

**RED-first matrix:**

Add focused tests before production creation for all of the following:

1. importing `cad_agent.component_view_registry` / required public surface fails because the module is absent;
2. a stable component ID is unchanged when only candidate target handles change;
3. a stable component ID is unchanged when legacy Primitive/Semantic UUIDs or caller order change, provided accepted deterministic projection identity is unchanged;
4. source/projection membership change changes component ID;
5. exact-base source SHA or revision change changes a `REUSED_UNCHANGED` component ID or fails stale binding as required by accepted R2 evidence;
6. `REUSED_UNCHANGED` without accepted exact-base/R2 evidence fails closed;
7. `RECONSTRUCTED_CHANGED` requires a base/original correspondence reference but must not claim reused geometry;
8. `RECONSTRUCTED_NEW` cannot silently carry a reused exact-base binding;
9. ambiguous mixed reused/reconstructed evidence cannot be silently classified as wholly reused; it becomes `MIXED_UNRESOLVED` or fails if evidence is internally contradictory;
10. source/base/accepted/current drawing supplied as a mutable target candidate binding fails closed;
11. duplicate/incompatible target entity binding fails closed;
12. path/filename/timestamp/order/UUID changes do not become logical identity authority;
13. unknown root/component/binding fields fail closed;
14. NaN/Infinity or noncanonical numeric evidence is rejected by the accepted upstream owner before R3 identity work; R3 does not add its own rounding;
15. `component_view_registry_sha256()` delegates to the existing canonical hash owner and changes when candidate binding evidence changes;
16. public errors are categorical and contain no private path/source content;
17. static import scan shows no parser/OCR/model/provider/network/subprocess/ezdxf/AutoCAD/File IPC/database/revision/approval/verdict/publisher owner.

- [ ] **Step 1: Write the RED-only tests**

Modify only `tests/test_cad_agent_component_view_registry.py`. Use synthetic mapping fixtures and deterministic fake accepted upstream records shaped exactly according to the post-R2 Gate-0 mapping. Do not patch production or create a compatibility shim.

- [ ] **Step 2: Prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_component_view_registry.py -q -p no:cacheprovider
```

Expected: FAIL because the R3 module/public behavior is missing. Import/fixture/setup errors unrelated to R3 do not count as meaningful RED.

Commit the RED-only test file before production creation.

- [ ] **Step 3: Implement the minimal closed component registry**

Create only `cad_agent/component_view_registry.py`.

Implementation rules:

- use `collections.abc.Mapping`, `copy`, and existing accepted owner APIs only;
- import `canonical_json_sha256` from `cad_agent.drawing_contracts` rather than `hashlib`/alternate JSON canonicalization;
- keep all identity material as closed normalized mappings;
- sort canonical component/output collections by deterministic ID before hashing/returning;
- exclude handles, timestamps, filenames/paths, volatile UUIDs, caller order, approval, revision-owner state from logical `component_id` material;
- include candidate bindings in the registry snapshot material so stale binding changes are detectable;
- do not perform filesystem, network, subprocess, model, AutoCAD, DXF, parser, or store I/O.

- [ ] **Step 4: Prove Task-1 GREEN**

Run the focused test at least five times to catch order/nondeterminism:

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_component_view_registry.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

Then run exact changed-path Ruff:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/component_view_registry.py tests/test_cad_agent_component_view_registry.py
```

- [ ] **Step 5: Run focused upstream regressions**

Use the exact final R1/R2 test paths recorded by Gate 0, plus current accepted equivalents for source fusion, exact-base contracts, Semantic IR, and canonical hashing. No live AutoCAD.

Required semantic categories:

```text
R1 final projection tests: PASS
R2 final Base CAD adapter tests: PASS
mcp_integration_lib exact-base offline contract tests: PASS
semantic_ir_lib model/assembly tests: PASS
canonical drawing-contract hash tests: PASS
AutoCAD live: NOT RUN
private/customer data: NOT RUN
```

- [ ] **Step 6: Verify architecture/diff and commit**

Run:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py

git diff --check

git diff --cached --check

git diff --name-only <TASK_1_BASE>..HEAD
```

Changed-file audit must show exactly the two Task-1 paths. Commit normally; no amend/rebase/squash/force-push.

**Paired independent reviewer:** architecture/reuse + determinism reviewer. Reviewer must specifically attack volatile-handle/UUID/path/order identity leakage and second-owner imports.

**STOP conditions:** third core path, direct R2 contract invention, new serializer/numeric owner, geometry parsing, AutoCAD/File IPC, or persistence requirement.

---

### Task 2: Logical views, explicit links, and impact projection

**Purpose:** Add stable logical 2D views and an explicit linked-view graph without mutation or synchronization authority.

**Files:**
- Modify: `cad_agent/component_view_registry.py`
- Modify: `tests/test_cad_agent_component_view_registry.py`
- Create: none

**Public surface added:**

```python
def project_linked_view_impacts(
    *,
    registry: object,
    component_ids: object = (),
    view_ids: object = (),
    upstream_context: object,
) -> dict[str, object]: ...
```

No fifth R3 public API is permitted by the first runtime design without Master PO amendment.

**View concepts:**

```text
view_id
view_role
component_ids
source_projection_refs
semantic_projection_refs
candidate_entity_bindings
layout_bindings
```

**Closed link classes:**

```text
COMPONENT_HAS_VIEW
VIEWS_SHARE_COMPONENT
VIEWS_SHARE_PARAMETER_EVIDENCE
VIEW_PRESENTED_ON_LAYOUT
```

**RED-first matrix:**

1. view ID is stable across display-name, handle, timestamp, UUID, and input-order changes;
2. view role/stable component membership/source projection mutation changes view ID;
3. unknown relation class fails closed;
4. dangling component/view endpoint fails closed;
5. duplicate logical link fails closed;
6. self-link fails unless the relation type explicitly permits it; initial four classes do not need a self-link;
7. component `view_ids` and link graph are bidirectionally consistent;
8. view component membership and `COMPONENT_HAS_VIEW` agree exactly;
9. candidate handles cannot define view identity;
10. a view cannot bind candidate entities from a different candidate identity;
11. two caller permutations produce byte-equivalent normalized registry and equal SHA;
12. impact closure from a component returns all explicitly linked views/layout bindings and explanation link IDs;
13. impact closure from a view returns linked components/views deterministically;
14. unknown input IDs fail closed rather than returning an empty success;
15. impact projection performs no geometry edit, no source-view choice, no approval, and no revision mutation.

- [ ] **Step 1: Add Task-2 RED tests only**

Modify only the existing R3 test file. Commit RED-only after proving failures are caused by missing view/link/impact behavior.

- [ ] **Step 2: Implement the minimal view/link graph**

Modify only the R3 production owner. Preserve Task-1 component IDs. Add deterministic view/link normalization and the pure impact traversal.

- [ ] **Step 3: Run repeated focused determinism GREEN**

Run the R3 focused suite at least five times and include randomized/permuted synthetic input order from deterministic test fixtures.

- [ ] **Step 4: Run upstream regressions and static ownership gates**

Repeat Gate-0 R1/R2 focused suites, exact-base offline contracts, Semantic IR, canonical hash tests, architecture checker, Ruff on the exact two R3 paths, and `git diff --check`.

- [ ] **Step 5: Commit and STOP WRITE for paired review**

Cumulative Task-2 runtime branch diff must still be exactly the two R3 core paths.

**Paired independent reviewer:** graph-integrity + synchronization-authority reviewer. Reviewer must prove the graph cannot mutate CAD, select source view, mint approval, or omit linked impact through malformed/dangling records.

**STOP conditions:** need for CAD geometry transform calculation, solver behavior, revision application, approval logic, or third core path.

---

### Task 3: Exact-base provenance, candidate custody, and origin cross-binding hardening

**Purpose:** Bind the registry explicitly to accepted R2 base/candidate evidence and prove stale/foreign/source/accepted target cases fail closed.

**Files:**
- Modify: `cad_agent/component_view_registry.py`
- Modify: `tests/test_cad_agent_component_view_registry.py`
- Create: none

**Dependency:** exact accepted R2 symbols/fields from Gate 0. This task may not start from the planning-time assumptions of Issue #127 or any moving R2 branch.

**RED-first matrix:**

1. accepted R2 candidate identity mismatch vs registry candidate binding fails;
2. accepted R2 base source ID mismatch fails;
3. base SHA mismatch fails;
4. source revision mismatch/stale evidence fails `STALE_BASE_BINDING` or the exact runtime categorical code locked by the Issue;
5. reused logical component absent from accepted R2 reused-membership evidence fails;
6. source handle/layer/block provenance mismatch fails;
7. local transform provenance mismatch fails without R3 recomputing transforms;
8. R3 never accepts a global deformation/reflection/non-uniform scale by inventing policy; it delegates to the accepted R2/S3 validator;
9. accepted/source/base drawing identity cannot be used as mutable target candidate identity;
10. source handle and target candidate handle namespaces cannot be conflated;
11. a candidate handle copied from source provenance without accepted candidate binding fails;
12. stale R2 evidence cannot retain `REUSED_UNCHANGED` classification;
13. reconstructed changed/new components cannot falsely acquire `REUSED_FROM_BASE_CAD` through caller fields;
14. caller-minted hash equality is insufficient when accepted R2 evidence/validator rejects the record;
15. public failures sanitize raw AutoCAD/parser/path exception details;
16. no R3 AutoCAD/File IPC/.NET IPC import or execution.

- [ ] **Step 1: Add RED-only exact-base/candidate attacks**

Use synthetic accepted R2 fixtures built through the exact accepted R2 test helpers/constructors identified by Gate 0. Do not duplicate the R2 validator in test code.

- [ ] **Step 2: Prove meaningful RED and commit tests**

Focused R3 test must fail because cross-binding hardening is absent, not because the R2 fixture is invalid.

- [ ] **Step 3: Add minimal accepted-R2 cross-binding**

R3 production may import/call only the accepted R2 owner chosen by Gate 0. It must not import `mcp_integration_lib.dotnet_ipc`, `mcp_client`, AutoCAD plugin code, or duplicate exact-base transform/eligibility logic.

- [ ] **Step 4: Prove GREEN and no second owner**

Run R3 focused suite five times; exact R2 focused tests; S3A exact-base contract tests; architecture/reuse ratchet; exact two-file Ruff; diff checks.

- [ ] **Step 5: Canonical + hosted gate for R3 core**

Run:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Expected truthful states:

```text
Offline/core tests: PASS
R3 focused: PASS
R1/R2 selected regressions: PASS
Architecture/reuse: PASS
Ruff: PASS
AutoCAD .NET: NOT RUN
AutoCAD Mechanical live: NOT RUN
Private/customer CAD: NOT RUN
```

Push normally, open/retain a DRAFT PR, and require hosted `tests` + `reuse-declaration` on exact head/current-main synthetic before independent review.

**Paired independent reviewer:** exact-base provenance/security reviewer. Reviewer must attack stale source revisions, candidate/source handle confusion, forged R2 evidence, and accidental AutoCAD ownership.

**STOP conditions:** R2 accepted output is insufficient; any need to modify R2/S3 production just for R3; live AutoCAD required; third R3 core path required.

---

### Task 4: Bind registry artifact through the existing manifest/checkpoint owner

**Purpose:** Make an accepted R3 registry snapshot resumable without creating a registry store or revision history.

**Issue separately after Task 3 acceptance.** This task is optional until an actual pipeline consumer needs durable binding, but its design is complete so no discovery cycle is required.

**Precondition:** fresh overlap check proves no active R2/R4/other writer owns `cad_agent/manifest.py`. If overlap exists, defer this task; do not rebase or widen scope.

**Files:**
- Modify: `cad_agent/manifest.py`
- Modify: `tests/test_cad_agent_component_view_registry.py`
- Create: none
- Do not modify: `cad_agent/component_view_registry.py` unless a fresh write-set amendment is issued because Task-3 accepted API is insufficient.

**Manifest-owned proposed surface:**

```python
COMPONENT_VIEW_REGISTRY_REFERENCE_SCHEMA_VERSION = "component-view-registry-reference-1.0"

def validate_component_view_registry_reference(value: object) -> dict[str, object]: ...

def bind_component_view_registry_reference(
    manifest: Mapping[str, object],
    *,
    registry_artifact_name: str,
    registry_sha256: str,
) -> dict[str, object]: ...

def require_component_view_registry_reference_match(
    manifest: Mapping[str, object],
    *,
    registry_artifact_name: str,
    registry_sha256: str,
) -> None: ...
```

This is an extension of the existing manifest owner, analogous in authority shape to current source-bundle binding. It is not a new manifest/store owner.

**Reference concept fields:**

```text
schema_version
artifact_name
registry_sha256
```

The reference deliberately does **not** store revision authority, approval, verdict, raw registry contents, absolute path, or target CAD handles.

**RED-first matrix:**

1. valid registry filename + accepted `registry_sha256` binds once;
2. rebinding same exact reference is idempotent;
3. different SHA or artifact name conflicts fail closed;
4. unknown fields fail closed;
5. absolute path, traversal, drive path, control characters fail closed;
6. malformed/non-lowercase SHA fails closed;
7. legacy manifests without registry reference retain existing safe behavior;
8. `read_manifest()` preserves/validates optional registry reference;
9. source-bundle behavior remains unchanged;
10. existing stage completion/hash logic remains unchanged;
11. resume mismatch fails before downstream R4 may consume stale registry;
12. no database/CAS/revision history appears;
13. no registry component data is copied into the manifest.

- [ ] **Step 1: Add manifest RED tests in the existing R3 test owner**

Modify only `tests/test_cad_agent_component_view_registry.py`; production manifest unchanged. Prove meaningful RED.

- [ ] **Step 2: Add minimal optional registry-reference binding to `cad_agent.manifest`**

Follow the existing closed source-bundle reference pattern. Do not add a stage, new manifest file, database, or schema file.

- [ ] **Step 3: Run focused + legacy manifest/CLI regressions**

At minimum:

```text
R3 focused registry/manifest tests: PASS
existing tests exercising cad_agent.manifest: PASS
run/resume tests: PASS
run-pdf/resume-pdf tests: PASS
source-bundle manifest binding tests: PASS
```

Use exact repository test paths confirmed on current main at issuance.

- [ ] **Step 4: Ruff, architecture, diff, canonical verifier**

Ruff exactly the two Task-4 changed Python paths, architecture/reuse ratchet, diff checks, then canonical verifier with AutoCAD .NET skipped.

- [ ] **Step 5: Hosted exact-head/current-main synthetic and STOP WRITE**

DRAFT PR only. Hosted `tests` and `reuse-declaration` must be GREEN. Independent manifest/resume reviewer required before Master PO acceptance.

**Paired independent reviewer:** persistence/resume compatibility reviewer. Reviewer must prove R3 did not create revision/store authority and that legacy resume remains safe.

**STOP conditions:** manifest schema/version migration becomes necessary; a third path is needed; active writer overlap; durable registry requires database/CAS; legacy readers would become unsafe.

---

## Task dependency graph

```text
Final accepted R1 + final accepted R2
            |
            v
Gate 0 post-R2 rebaseline (no write)
            |
            v
Task 1 component registry core
            |
            v
Task 2 views + explicit link graph
            |
            v
Task 3 R2 exact-base/candidate hardening
            |
            +----------------------+
            |                      |
            v                      v
      R3 core acceptance      Task 4 manifest binding
            |                      |
            +-----------+----------+
                        v
                R4 may consume R3
```

Task 4 must not block acceptance of the pure R3 core if no durable consumer exists yet. It must complete before any resume/pipeline behavior relies on a persisted registry reference.

---

## Exact overlap matrix

| Lane / owner | Potential overlap | R3 action |
|---|---|---|
| Active/final R1 `cad_agent/source_fusion.py` + tests | None with R3 core; semantic dependency only | Read/import accepted APIs only after merge. Never edit R1 paths. |
| R2 Base CAD Adapter planning/runtime | Unknown until accepted plan/runtime write-set | Gate 0 must compare exact paths. R3 core prefers new adjacent paths. Any overlap => STOP/reissue, no rebase. |
| Wave 1A worker-control lanes (`agent_lib/**`, `cad_agent/vision_handoff.py`) | None | Do not touch. |
| S3A/S3B exact-base owners (`mcp_integration_lib/**`, AutoCAD plugin) | None | Consume accepted evidence only. No write/import of transport for execution. |
| Luna local AutoCAD lane | No repository writer authority | R3 core requires no AutoCAD/local operation. |
| Future R4 Candidate Revision Orchestrator | Semantic dependency after R3 | R3 must not pre-implement revision creation/promotion. R4 consumes registry read-only. |
| Existing manifest/checkpoint owner | Task 4 only | Fresh overlap check required immediately before Task 4 issuance. |

---

## Adversarial acceptance matrix across R3

A final R3 core head must demonstrate all of the following.

### Identity and determinism

- component/view/link IDs ignore volatile handles, UUIDs, timestamps, filenames/paths, caller order;
- logical identity changes on stable evidence membership/type/base-source changes;
- registry snapshot SHA changes on candidate binding/candidate identity changes;
- repeated/permuted runs produce exact normalized equality;
- no ambient clock/random/locale/timezone identity.

### Referential closure

- every component/view/link endpoint exists exactly once;
- bidirectional component↔view membership is closed;
- unknown relation types fail closed;
- duplicate IDs/bindings fail closed;
- ambiguous semantic duplicate-class membership follows accepted R1 ambiguity behavior, not legacy UUID selection.

### Provenance

- source/projection refs are accepted R1 identities;
- reused components are bound to accepted R2/base source SHA/revision/provenance;
- stale R2/base evidence blocks reused-unchanged claims;
- reconstructed components cannot spoof reused provenance;
- source handles remain evidence, not target identity.

### CAD safety

- candidate binding must be candidate-only;
- no source/base/accepted target mutation reference;
- no AutoCAD/File IPC/.NET IPC call;
- no `ezdxf`/DXF generation;
- R3 never edits candidate geometry.

### Authority

- no approval/apply state transitions;
- no revision numbering/current-revision owner;
- no repair executor;
- no visual PASS/verdict;
- no promotion/publication;
- no second manifest/checkpoint/database/CAS owner.

### Privacy

- public errors contain only categorical IDs/codes;
- no source bytes, private paths, raw parser/AutoCAD exceptions, prompts, credentials, or customer content.

---

## Verification policy for every runtime task

Run the narrowest focused tests first, then relevant upstream regressions, then repository gates.

Required order:

1. focused R3 RED/GREEN;
2. accepted R1 projection tests named by Gate 0;
3. accepted R2 Base CAD tests named by Gate 0;
4. exact-base offline contract regressions when Task 3 is involved;
5. Semantic/Primitive compatibility regressions affected by references only;
6. manifest/run/resume regressions when Task 4 is involved;
7. Ruff on exactly changed Python paths;
8. `scripts/check_architecture_boundaries.py`;
9. repository reuse declaration/ratchet;
10. `git diff --check` and `git diff --cached --check`;
11. cumulative exact write-set audit;
12. canonical `scripts/verify.ps1 -SkipAutoCADDotNet`;
13. hosted `tests` + `reuse-declaration` on exact final head/current-main synthetic merge.

### Literal result semantics

- `PASS`: gate executed and satisfied its exact contract.
- `FAIL`: gate executed and contradicted the contract.
- `SKIP`: an explicitly optional test/probe was selected but skipped by its declared prerequisite.
- `NOT RUN`: gate was not executed, including AutoCAD Mechanical live/private-data gates absent from R3.

Do not promote `SKIP`/`NOT RUN` to `PASS`.

Expected R3 core completion states:

```text
Focused synthetic R3: PASS
Relevant offline R1/R2/S3/Semantic regressions: PASS
Ruff: PASS
Architecture/reuse: PASS
Diff/write-set: PASS
Canonical offline verifier: PASS
Hosted tests: PASS
Hosted reuse-declaration: PASS
AutoCAD .NET: NOT RUN (explicit -SkipAutoCADDotNet)
AutoCAD Mechanical live: NOT RUN
Private/customer CAD: NOT RUN
Real model/provider/OCR execution for R3: NOT RUN
```

---

## Reuse Declaration template for R3 runtime PRs

Every future R3 runtime PR must include the exact repository-required labels:

```text
Existing capability inspected:
Existing API reused:
Adapter required:
New capability genuinely missing:
Files allowed to change:
Files forbidden to duplicate:
Compatibility behavior:
Migration and rollback path:
```

For core R3, `New capability genuinely missing` must name only the deterministic linked Component/View Registry and explain that the accepted inventory identifies no complete owner for the linked component/view graph.

---

## Program-level STOP conditions

Stop R3 and request Master PO disposition when any task discovers:

- accepted R1/R2 facts are insufficient and would need contract invention;
- a third core R3 path is necessary;
- R3 must parse source/CAD bytes or calculate geometry to determine identity;
- R3 needs AutoCAD/File IPC/.NET IPC execution;
- a second canonical serializer/hash/numeric owner is proposed;
- a new manifest/checkpoint/revision/database/CAS store is proposed;
- source/base/accepted CAD could be mutated;
- candidate revision creation/promotion becomes necessary;
- approval/verdict/repair/publication logic is needed;
- private/customer data or live AutoCAD is required to make core tests pass;
- current main or an active writer introduces semantic/path overlap with the issued write-set.

No rebase/main-sync is a substitute for reissuance after semantic overlap.

---

## Planning completion criteria

Issue #128 planning is complete when:

- exactly the two planning docs exist and no runtime/test/workflow/dependency file changed;
- the design identifies concrete current owners and the genuine R3 gap;
- moving R2 API names are not invented;
- the R3 core can be issued as bounded two-path RED-first tasks after post-R2 rebaseline;
- component identity is separate from volatile CAD handles;
- linked views have an explicit deterministic graph and impact-only projection;
- exact-base provenance is consumed through R2/S3 rather than reimplemented;
- Primitive/Semantic geometry ownership remains unchanged;
- manifest persistence reuses the existing owner in a separately gated task;
- R3 has no revision/approval/verdict/publication authority;
- hosted documentation/reuse checks are GREEN;
- PR remains DRAFT and writer stops for Master PO review.
