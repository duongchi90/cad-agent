# R4 Candidate Revision Orchestrator Design

## Status and authority

- Planning Issue: `#133 — [Acceleration][Planning] R4 Candidate Revision Orchestrator executable design and runtime plan`
- Activation comment: `5227145372`
- Exact planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`
- Planning branch: `planning/issue-133-r4-candidate-revision-orchestrator`
- Planning date: `2026-08-09`
- Planning only. No runtime implementation, live AutoCAD operation, private/customer CAD access, acceptance, promotion, publication, or merge authority is granted here.

R4 runtime remains **BLOCKED** until R1, R2 runtime, and R3 runtime are accepted/merged and Master PO performs a fresh post-R3 rebaseline on exact current `main`.

PR #129 is planning-only and held DRAFT. Moving R3 Issue #128 is planning-only. Neither is treated as an accepted runtime contract. Any R2/R3 concept below is a semantic seam requirement whose exact accepted symbol/field must be resolved by the post-R3 rebaseline.

## 1. Decision summary

R4 is one thin **Candidate Revision Orchestrator** in `cad_agent`.

It owns deterministic immutable candidate-revision lineage and a separate non-authoritative selection-for-review binding. It does not own CAD generation/mutation, a component registry, visual or engineering approval, promotion, publication, or another manifest/revision database.

The selected lifecycle is:

```text
mutable disposable candidate workspace
    -> SEALED_CANDIDATE revision
    -> SELECTED_FOR_REVIEW binding
    -> accepted candidate (external authority)
    -> published/current production revision (R7 authority)
```

The governing rule is:

> R4 may seal immutable candidate lineage and bind an explicit candidate selection for downstream review. R4 may never make that candidate accepted, production-current, release-eligible, or published.

Durable R4 references, when added, live only under the existing `cad_agent.manifest` / PDF manifest lifecycle.

## 2. Why R4 is genuinely missing

The accepted reuse inventory classifies `candidate-revision-synchronization` as `NEW_MISSING_CAPABILITY`.

Already present:

- atomic run manifests/checkpoints/resume;
- exact artifact hashes;
- native DXF generation;
- Visual Supervisor freshness/mutation evidence;
- AutoCAD/File IPC execution boundaries;
- verified repair backup/rollback;
- R1 source/fusion identity;
- after R2 acceptance, frozen Base-CAD provenance;
- after R3 acceptance, linked logical component/view identity and impact projection.

Still missing is one deterministic orchestration boundary that proves:

```text
this candidate artifact
is an immutable child of this exact baseline/parent
under these exact accepted R1/R2/R3 identities
with this exact component/view impact/provenance scope
and these exact mutation/recovery evidence hashes
```

while preserving every predecessor and keeping selection, acceptance, current-production status, and publication separate.

That is the only new R4 capability.

## 3. Alternatives considered

### Option A — selected: stateless R4 core + existing manifest integration

Add one adjacent pure-Python core for revision identity/lineage/freshness/selection. Add optional durable references later through `cad_agent.manifest` and `cad_agent.pdf` only.

This avoids a second store and keeps R4 testable with synthetic data and no AutoCAD.

### Option B — rejected: R4 database/CAS/revision directory

A new SQLite, JSONL, CAS, or filesystem revision tree would duplicate the existing manifest/checkpoint truth owner.

Classification: `REJECT_DUPLICATE_OWNER`.

### Option C — rejected: revision state inside R3 registry

R3 owns logical component/view relationships. Candidate lineage/current/promotion state inside R3 would merge registry and revision authorities.

Classification: `REJECT_DUPLICATE_OWNER`.

### Option D — rejected: revision truth inside AutoCAD/File IPC

Runtime session state, drawings, or dispatcher payloads are not an acceptable revision store.

Classification: `REJECT_DUPLICATE_OWNER`.

## 4. Reuse-first ownership map

| Capability | Current/expected owner | Classification | R4 rule |
|---|---|---|---|
| Atomic manifest/checkpoint/resume | `cad_agent/manifest.py`, `cad_agent/pdf.py`, current run/resume | `EXTEND_WITH_ADAPTER` | Optional R4 refs/history live here only. |
| Canonical JSON SHA-256 | `cad_agent.drawing_contracts.canonical_json_sha256()` | `REUSE_AS_IS` | Sole canonical R4 identity/hash owner. |
| File SHA-256 | existing manifest/upstream hash owners | `REUSE_AS_IS` | Existing owner may verify files; R4 core consumes hashes and does not reopen CAD. |
| R1 source/fusion identity | final accepted R1 | `EXTEND_WITH_ADAPTER` after rebaseline | Bind accepted digest transitively/directly; do not re-fuse. |
| R2 frozen Base-CAD evidence | final accepted R2 | `EXTEND_WITH_ADAPTER` after rebaseline | Bind accepted handoff/source revision where reuse exists; do not re-extract. |
| R3 Component/View Registry | final accepted R3 | `REUSE_AS_IS` after rebaseline | Bind registry/impact/provenance identity; never become a registry. |
| Native CAD/DXF generation | `dxf_builder_lib` | `REUSE_AS_IS` | Candidate artifacts may originate here; no R4 geometry write. |
| AutoCAD/File IPC transport | `mcp_integration_lib` + plugin | `REJECT_DUPLICATE_OWNER` | No R4 transport/runtime-session authority. |
| Visual evidence freshness | `cad_agent.visual_evidence`, `visual_contracts` | `REUSE_AS_IS` | Bind evidence hash only; no visual PASS. |
| Repair backup/rollback | `cad_agent.live` + repair owners | `REUSE_AS_IS` | Bind verified evidence only; no copy/restore/repair. |
| Approval/proposal/apply | existing server/agent gates | `REJECT_DUPLICATE_OWNER` | R4 issues no approval. |
| Independent verdict | future R5 / existing evidence owners | `REJECT_DUPLICATE_OWNER` | R4 emits no verdict. |
| Repair execution | future R6 / existing executors | `REJECT_DUPLICATE_OWNER` | R4 executes no repair. |
| Promotion/publication | future R7 / existing promotion gate | `REJECT_DUPLICATE_OWNER` | R4 never changes current/published state. |
| Candidate revision synchronization | no complete owner | `NEW_MISSING_CAPABILITY` | Narrow R4 responsibility. |

## 5. Mandatory post-R3 rebaseline and non-invention rule

Before any R4 runtime branch exists, Master PO must map every semantic seam below to an exact accepted path/symbol/field/test on fresh `main`.

### 5.1 Final R1 seam

Resolve the final validator/hash and exact immutable source/fusion digest transitively bound by R3. R4 must not re-interpret source conflicts already closed by accepted R1/R3 validation.

### 5.2 Final R2 seam

When reused Base-CAD content exists, accepted R2/R3 must prove:

```text
R2 handoff identity/hash
base source ID
base source SHA-256
base source revision
reused logical component membership
candidate/source provenance binding
stale/re-extraction state
```

If accepted R3 already validates/carries R2 transitively, R4 reuses that proof rather than constructing a parallel validator.

No proposed API from PR #129 is assumed.

### 5.3 Final R3 seam

Accepted R3 must expose enough validated evidence to obtain without CAD parsing:

```text
registry snapshot identity/hash
candidate drawing/binding identity
stable logical component IDs
stable logical view IDs
component/view provenance references
linked component/view/layout impact closure
upstream R1/R2 binding
stale/foreign candidate refusal
```

R4 also requires an accepted deterministic mechanism for cross-snapshot logical correspondence: a per-record digest, stable logical ID plus validated snapshot identity, or the final R3 equivalent.

If R3 cannot prove this, R4 stops rather than inventing component/view correspondence.

### 5.4 Current-baseline seam

R4 requires one read-only server-owned baseline reference from the accepted manifest/promotion lifecycle containing at least:

```text
baseline revision identity/hash
baseline drawing SHA-256
run/project scope
```

R4 does not create the production-current pointer. Missing baseline ownership is a rebaseline failure, not permission for a new store.

### 5.5 Rebaseline failure

Any missing/materially inconsistent seam returns exactly:

```text
R4 REBASELINE REQUIRED
```

No R1/R2/R3/manifest/transport/publisher patch is implicitly authorized.

## 6. R4 responsibility boundary

R4 owns only:

1. accepted-context validation through Gate-0 mapped owner APIs;
2. deterministic candidate-revision identity;
3. immutable baseline/parent lineage;
4. binding candidate artifact hashes to exact R3 component/view impact/provenance identity;
5. freshness/staleness evaluation;
6. binding an explicit caller/server candidate choice into `SELECTED_FOR_REVIEW`;
7. supersession/logical-selection rollback that preserves all old evidence;
8. R4 record hashes through the existing canonical owner;
9. optional durable references under the existing manifest owner.

R4 does not own source fusion, Base-CAD extraction, the Component/View Registry, geometry solving, DXF writing, AutoCAD transport, CAD mutation, repair, backup copying, verdict, approval, acceptance, production-current promotion, publication, or a database/CAS/revision store.

## 7. State and authority model

### 7.1 Mutable candidate workspace

A workspace is a disposable target owned by an existing generator, synchronization, repair, or AutoCAD executor. It may mutate and is not durable revision truth.

### 7.2 Sealed candidate revision

After accepted owners provide complete immutable candidate artifact/evidence hashes and a fresh R3 registry binding, R4 may seal exactly:

```text
SEALED_CANDIDATE
```

A sealed revision is immutable. Any later CAD change requires a new workspace and child candidate revision.

### 7.3 Selected candidate

R4 may bind exactly:

```text
SELECTED_FOR_REVIEW
```

The exact candidate hash is explicitly supplied by caller/server authority. R4 validates/binds; it does not rank candidates or infer a winner from quality evidence.

### 7.4 Accepted state

Acceptance is external R5/engineer/approval authority. `ACCEPTED` is not an R4 state.

### 7.5 Published/current production state

R7/existing promotion gates own production-current/publication. R4 cannot set `published`, `production_current`, release eligibility, or equivalent state.

Current/baseline production identity is read-only R4 input.

## 8. Candidate revision record

The initial closed artifact is:

```text
candidate-revision-1.0
```

Exact root concepts:

```text
schema_version
revision_id
state = SEALED_CANDIDATE
run_id
baseline_revision
parent_candidate_revision_sha256
upstream_bindings
candidate_artifacts
change_scope
component_lineage
view_lineage
mutation_evidence
candidate_revision_sha256
```

### 8.1 Baseline revision

A minimal read-only reference supplied by the Gate-0 accepted baseline owner. It carries only exact identity/hash/scope needed to reject baseline drift.

### 8.2 Parent candidate

`parent_candidate_revision_sha256` is null for a first child of the baseline and otherwise binds one complete prior sealed R4 candidate SHA-256.

Self-parenting, cycles, foreign run/project, and baseline mismatch fail closed.

### 8.3 Upstream bindings

Closed accepted identity digests required by Gate 0, including the R3 registry hash and, where applicable, accepted R1/R2 digests. No paths/source bytes/session IDs/approval state.

### 8.4 Candidate artifacts

Closed sorted immutable artifact identity records. At minimum the candidate drawing hash and accepted R3 candidate/registry binding required by the post-R3 issue.

R4 core never opens/hashes CAD itself.

### 8.5 Change scope

Derived from accepted R3 impact evidence, never from R4 geometry inspection:

```text
changed component IDs
impacted component IDs
impacted view IDs
impacted layout bindings
impact-closure evidence SHA-256
```

A caller cannot omit an R3-linked impact.

### 8.6 Component/view lineage

References only, never a copied registry:

```text
logical ID
parent registry snapshot identity
current registry snapshot identity
R3-owned binding identity proving correspondence
change class
```

Closed change classes:

```text
UNCHANGED
CHANGED
NEW
REMOVED
```

R4 checks consistency with accepted R3 evidence. It never infers correspondence from CAD geometry, handles, filenames, or naming similarity.

### 8.7 Mutation evidence

Only hashes/identities already emitted by accepted owners, e.g. latest mutation evidence, build/review evidence, and verified backup/rollback evidence when applicable.

No mutation, backup, verdict, or approval is performed by R4.

## 9. Deterministic revision identity

R4 uses `cad_agent.drawing_contracts.canonical_json_sha256()` only.

`revision_id` is derived from normalized identity material containing:

```text
schema/version domain
run identity
baseline identity
parent candidate SHA-256
accepted upstream binding hashes
candidate artifact hashes
change-scope hash
component/view lineage identities
required mutation-evidence hashes
```

The first runtime may encode the complete digest as:

```text
candidate:<64-lowercase-hex-digest>
```

`candidate_revision_sha256` is the canonical hash of the complete normalized record excluding its own checksum field.

Identity must exclude wall-clock time, timestamped backup filenames, path traversal order, private paths, AutoCAD PID/HWND/session, random UUIDs, reviewer/approval identity, verdict, publication state, and caller list order.

A volatile CAD handle is never logical revision identity unless final accepted R3 explicitly includes it in a candidate snapshot binding digest; R4 never promotes a raw handle into logical component identity.

## 10. Immutable lineage invariants

Every candidate binds one exact:

```text
run/project scope
baseline revision
zero-or-one parent candidate
current R3 registry snapshot
candidate artifact set
change/impact scope
```

Rules:

- no revision rebind to another registry/baseline/R2 source revision/drawing/parent;
- parent remains intact;
- no cycles/self-parent;
- parent/child scope must match;
- artifact hash change creates a distinct revision;
- caller order changes do not;
- stale upstream creates a new candidate cycle after upstream refresh; old candidate is never rewritten;
- supersession never deletes predecessor evidence.

## 11. Freshness model

Closed first states:

```text
CURRENT
STALE_UPSTREAM
STALE_BASELINE
FOREIGN_SCOPE
```

R4 checks freshness on candidate creation/validation, selection, resume binding, and downstream handoff.

`STALE_UPSTREAM` means accepted R3 or transitively required R1/R2 identity changed. The old candidate remains historical evidence but cannot silently operate under the new context.

`STALE_BASELINE` means the server-owned baseline reference changed. The candidate is not automatically rebased.

`FOREIGN_SCOPE` means a run/project/baseline/candidate belongs elsewhere.

Only `CURRENT` may be selected for new downstream review.

## 12. Base-CAD revision changes

If accepted R2/R3 reports changed Base-CAD source SHA/revision:

1. preserve the old R4 candidate unchanged;
2. classify it stale against new upstream context;
3. do not overwrite reused components;
4. do not call extraction from R4;
5. require a new accepted R2 extraction/workspace;
6. require a new accepted R3 registry snapshot;
7. seal a new R4 candidate only after those owners complete.

## 13. Candidate selection record

Closed artifact:

```text
candidate-selection-1.0
```

Exact concepts:

```text
schema_version
selection_id
state = SELECTED_FOR_REVIEW
run_id
baseline_revision_sha256
candidate_revision_sha256
candidate_revision_id
eligible_candidate_revision_sha256s
selection_context_sha256
candidate_selection_sha256
```

Rules:

- selected candidate must be among explicitly supplied eligible sealed candidates;
- all candidates participating in one selection are exact-scope records;
- selected candidate must be `CURRENT`;
- candidate list order does not matter;
- R4 performs no quality ranking;
- no acceptance/PASS/publish/current-production field;
- selecting B never deletes A;
- a later selection may point back to A while preserving prior selection records.

## 14. Rollback and supersession

### 14.1 Workspace/CAD rollback

Existing execution owners retain CAD backup/recovery. `cad_agent.live.repair_live()` already verifies copies/hashes, second review, save conditions, and backup reopening. R4 only binds the resulting evidence digest.

### 14.2 Logical revision/selection rollback

Logical rollback means a **new selection record** points downstream review to a previously sealed candidate. It never edits/deletes candidate revisions or prior selection records.

A rejected/failed candidate remains historical evidence. A repair creates a new disposable workspace; after accepted owners finish, R4 seals a new child candidate.

## 15. Existing manifest/checkpoint integration

R4 core has no writer/store.

A separate bounded task may extend `cad_agent.manifest` with optional fields:

```text
candidate_revision_refs[]
candidate_selection_refs[]
selected_candidate_revision_sha256
```

Manifest owner rules:

- `cad_agent.manifest` owns validation/binding;
- `write_manifest()` remains the atomic writer;
- `read_manifest()` and, where applicable, `read_pdf_manifest()` validate the same manifest-owned reference semantics;
- absent R4 fields remain absent in legacy manifests;
- same reference rebind is idempotent;
- same ID/different hash fails closed;
- selection points only to a bound candidate;
- moving selection pointer preserves all candidate/selection references;
- no change to `release_profile`, `authoritative_release_eligible`, acceptance, production-current, or publication authority;
- malformed optional R4 fields block resume before stage work.

PDF does not get a second revision validator.

## 16. Candidate-only mutation boundary

Allowed flow:

```text
immutable current/baseline reference
    -> existing owner creates disposable candidate workspace
    -> existing authorized executor mutates only workspace
    -> accepted owner emits artifact/evidence hashes
    -> R3 emits fresh registry/candidate binding
    -> R4 seals immutable candidate revision
```

R4 itself performs no CAD mutation.

Source, exact Base-CAD source, accepted drawing, production-current drawing, and an already sealed candidate revision are never mutable R4 targets.

## 17. Authority separation

| Transition | Owner | R4 authority |
|---|---|---|
| Create/mutate disposable workspace | existing DXF/R2/repair/AutoCAD owner | none |
| Seal candidate revision | R4 | yes |
| Select exact candidate for downstream review | caller/server chooses; R4 validates/binds | binding only |
| Visual/engineering acceptance | R5/existing engineer authority | none |
| Repair execution | R6/existing executor | none |
| Promote/publish/current | R7/existing promotion gate | none |

## 18. Compatibility with visual evidence

Existing visual evidence already binds to `latest_mutation_sha256` and fails on stale drawing/session state.

R4 may bind its accepted mutation/evidence identity so R5 can verify evidence against an exact candidate revision SHA.

R4 does not call visual-verdict requirements to turn evidence into acceptance.

## 19. Privacy

R4 artifacts/errors exclude:

- absolute/private source paths;
- customer content/source bytes;
- AutoCAD PID/HWND/session;
- keys/secrets;
- raw parser/transport exception text;
- prompts/provider content;
- approval secrets.

Operational paths remain inside their existing owner. R4 records only opaque/hash identity required by revision lineage.

## 20. Proposed R4 public API

Preferred core paths:

```text
cad_agent/candidate_revision.py
tests/test_cad_agent_candidate_revision.py
```

Task-1 surface:

```python
CANDIDATE_REVISION_SCHEMA_VERSION = "candidate-revision-1.0"

class CandidateRevisionError(ValueError): ...

def build_candidate_revision(
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None,
    candidate_artifacts: object,
    change_impact: object,
    mutation_evidence: object,
) -> dict[str, object]: ...

def validate_candidate_revision(
    payload: object,
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> dict[str, object]: ...

def candidate_revision_sha256(
    payload: object,
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> str: ...

def evaluate_candidate_revision_freshness(
    *,
    revision: object,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...
```

Task-2 adds:

```python
CANDIDATE_SELECTION_SCHEMA_VERSION = "candidate-selection-1.0"

def build_candidate_selection(
    *,
    revisions: object,
    selected_revision_sha256: str,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...

def validate_candidate_selection(
    payload: object,
    *,
    revisions: object,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...
```

`registry`, `base_cad_handoff`, and `baseline_context` are R4 call-parameter names, not claims about planning-time R2/R3 API names. Private normalizers must call only the exact accepted symbols resolved by Gate 0.

The core remains pure orchestration: no filesystem/CAD/DXF/IPC/network/subprocess/model/approval/verdict/repair/publication/database behavior.

## 21. Proposed minimal runtime write-set

### Tasks 1–2 core

```text
cad_agent/candidate_revision.py
tests/test_cad_agent_candidate_revision.py
```

### Task 3 manifest integration

```text
MODIFY cad_agent/manifest.py
MODIFY cad_agent/pdf.py
MODIFY tests/test_cad_agent_candidate_revision.py
```

Task 3 does not modify the accepted R4 core unless Master PO issues a fresh write-set amendment.

No CLI or fourth production owner is presumed.

## 22. Runtime task decomposition

1. **Candidate revision core** — deterministic identity, immutable lineage, upstream/candidate binding, stale/fail-closed behavior.
2. **Selection and supersession** — explicit selection-for-review and logical rollback without deletion/overwrite.
3. **Existing-manifest integration** — durable revision/selection references and selected-candidate pointer under existing manifest/PDF readers.

No task implements approval, verdict, repair, publisher, or AutoCAD live work.

## 23. RED-first adversarial matrix

### Determinism

- same semantics/different caller order -> same revision ID/hash;
- changed candidate drawing hash/registry/baseline/parent/impact -> changed identity;
- non-authoritative path/timestamp/UUID/session change -> no identity change;
- invalid/noncanonical upstream values fail through accepted owner;
- unknown R4 fields fail closed.

### Lineage/staleness

- self/foreign/cross-run parent rejected;
- stale baseline rejected;
- stale R1/R2/R3 binding rejected;
- child cannot rewrite parent;
- predecessor survives supersession;
- old stale candidate remains historical only.

### R2/R3 provenance

- Base-CAD source SHA/revision mismatch -> stale/block;
- component/view correspondence not proven by R3 -> block;
- omitted linked impact -> block;
- target CAD handle/path cannot replace R3 logical identity.

### State/authority

- `SEALED_CANDIDATE` never accepted/current/published;
- injected approval/verdict/publish fields rejected;
- unknown/stale selection rejected;
- no automatic candidate ranking;
- logical selection rollback performs no CAD rollback.

### Manifest persistence

- legacy image/PDF manifests unchanged when R4 fields absent;
- optional refs validate through manifest owner;
- idempotent same reference;
- same ID/different hash conflict;
- selection must point to a bound candidate;
- pointer movement preserves history refs;
- malformed R4 ref blocks resume;
- no release/acceptance/publication field changes.

### Ownership/privacy

- no AutoCAD/File IPC;
- no CAD parser/DXF writer;
- no backup implementation duplication;
- no R3 registry creation;
- no approval/verdict/publisher owner;
- no path/private-source leakage;
- no new dependency/store/schema directory.

## 24. Verification model

Every runtime child task runs:

- exact focused RED/GREEN;
- Gate-0 accepted R1/R2/R3 focused tests where relevant;
- manifest/PDF run/resume regressions for Task 3;
- existing backup/rollback regression tests when evidence bindings are affected, without live mutation;
- Ruff on exact changed Python paths;
- architecture/reuse ratchet;
- `git diff --check`;
- exact changed-file audit from issuance base;
- `scripts/verify.ps1 -SkipAutoCADDotNet`;
- hosted `tests` and `reuse-declaration` on exact head/current-main synthetic;
- paired independent domain review;
- independent integration/CI review.

AutoCAD/private-data states remain literal `NOT RUN`/`SKIP` unless separately authorized and actually executed.

## 25. PASS / FAIL / SKIP / NOT RUN

| State | Meaning |
|---|---|
| `PASS` | Exact check executed against stated head/evidence and met every assertion. |
| `FAIL` | Exact check executed and contradicted an invariant; progression stops. |
| `SKIP` | Explicitly optional/gated probe skipped under declared prerequisite; not acceptance evidence. |
| `NOT RUN` | Required live/private/environment operation unavailable or unattempted; never promoted to PASS. |

## 26. Dependency and overlap matrix

| Lane/owner | Relationship | R4 rule |
|---|---|---|
| Active/final R1 | upstream runtime dependency | R4 waits for accepted merge; no R1 writes. |
| PR #129 R2 planning | planning input only/HOLD MERGE | no planning-time API assumption. |
| Final R2 runtime | upstream evidence where Base-CAD reuse exists | accepted evidence read-only; no R2 writes. |
| Moving #128 R3 planning | planning input only | no moving API assumption. |
| Final R3 runtime | immediate upstream | accepted registry/impact read-only; no R3 write. |
| manifest/PDF owner | Task 3 persistence | fresh overlap check before Task 3. |
| Luna/AutoCAD local lane | live operator | R4 core has no live AutoCAD/session control. |
| DXF builder | candidate artifact producer | read identity only. |
| `cad_agent.live`/repair | backup/rollback executor | evidence only; no duplicate execution. |
| Future R5 | consumer/verdict | R4 cannot pre-emit verdict. |
| Future R6 | may create repaired workspace | R4 seals resulting child; no repair execution. |
| Future R7 | promotion/publication | R4 never sets production-current/published. |

## 27. Migration and rollback

Planning PR: no migration; reverting the two docs removes planning only.

Core runtime: additive two-path module/test. Revert removes R4 core without changing existing owners.

Manifest integration: optional fields only; legacy manifests stay readable and are not rewritten on read. Revert removes bindings without deleting candidate artifacts.

CAD rollback remains existing live-owner responsibility. R4 logical rollback is a new selection reference to a prior sealed candidate while preserving all prior revision/selection evidence.

## 28. STOP conditions

Stop and report `R4 REBASELINE REQUIRED` if:

- final R1/R2/R3 semantics cannot supply the required immutable seam;
- R3 cannot prove cross-snapshot logical correspondence;
- no accepted baseline/current reference owner exists;
- R4 must parse CAD/DXF or infer geometry correspondence;
- R4 must call Base-CAD extraction;
- R4 must modify R3 production for convenience;
- R4 needs database/CAS/revision directory/second manifest;
- R4 needs AutoCAD/File IPC;
- R4 needs backup/restore or repair execution;
- R4 needs approval issuance;
- R4 needs visual/engineering PASS;
- R4 needs accepted/current/published/release-eligible authority;
- dependency/lock/workflow/schema-directory change appears necessary;
- private/customer CAD is required for first runtime tests;
- accepted upstream tests must be weakened/skipped;
- any child task needs a path outside its exact issued allowlist.

Do not solve a STOP by inventing an adapter that duplicates another owner.

## 29. Planning acceptance

This planning slice is complete only when:

- exactly the two Issue #133 planning docs are changed;
- candidate/current/accepted/published separation is explicit;
- immutable deterministic candidate lineage is defined;
- moving PR #129 / Issue #128 APIs remain non-authoritative;
- post-R3 Gate 0 is explicit;
- existing manifest/checkpoint remains sole durable owner;
- existing backup/rollback is reused;
- runtime write-sets and RED-first matrices are executable;
- no runtime/test/workflow/dependency/CAD/private-data write exists in this planning PR;
- hosted tests/reuse/docs checks are GREEN on exact final planning head/current-main synthetic;
- PR remains DRAFT;
- writer stops repository writes after hosted GREEN.