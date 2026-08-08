# R4 Candidate Revision Orchestrator Design

## Status and authority

- Planning Issue: `#133 — [Acceleration][Planning] R4 Candidate Revision Orchestrator executable design and runtime plan`
- Activation comment: `5227145372`
- Exact planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`
- Planning branch: `planning/issue-133-r4-candidate-revision-orchestrator`
- Planning date: `2026-08-09`
- This document is planning/design only. It authorizes no runtime implementation, AutoCAD operation, private/customer CAD access, acceptance, promotion, publication, or merge.

R4 runtime remains **BLOCKED** until all of the following are true:

1. R1 Source Bundle/Fusion is accepted and merged;
2. R2 Base CAD Adapter runtime is accepted and merged;
3. R3 Component/View Registry runtime is accepted and merged;
4. Master PO performs a fresh post-R3 rebaseline against exact current `main`;
5. Master PO explicitly issues bounded R4 runtime work with an exact base, branch, allowlist, and reviewer topology.

PR #129 is planning-only and held DRAFT. Moving R3 Issue #128 is also planning-only. Neither is an accepted runtime API for this design. Any R2/R3 concept named below is a **semantic seam requirement**, not a claim that a symbol or field currently exists.

## 1. Decision summary

R4 will be one thin **Candidate Revision Orchestrator** in `cad_agent` that creates deterministic immutable candidate-revision records from already validated upstream evidence and candidate artifact identities.

The selected architecture separates five concepts that must never be collapsed:

```text
mutable candidate workspace
    -> sealed candidate revision
    -> selected candidate for downstream review
    -> accepted candidate (external authority)
    -> published/current production revision (R7 authority)
```

The governing rule is:

> R4 may create immutable candidate lineage and bind an explicit selection-for-review. R4 may not make a candidate accepted, published, or production-current.

R4 does not parse CAD, generate DXF, mutate AutoCAD, execute repair, issue approval, produce a visual/engineering verdict, publish files, or own a second manifest/checkpoint/revision database.

The durable owner remains the existing `cad_agent.manifest` lifecycle. R4 core returns closed JSON-compatible records; a separately bounded integration task may bind immutable revision references and selection history through that existing manifest owner.

## 2. Why R4 is genuinely missing

The accepted repository reuse inventory classifies `candidate-revision-synchronization` as `NEW_MISSING_CAPABILITY`.

Current capabilities already provide:

- atomic staged run manifests and checkpoint/resume;
- source and artifact SHA-256 checks;
- native DXF generation;
- Visual Supervisor evidence freshness through mutation hashes;
- AutoCAD/File IPC mutation and review boundaries;
- verified repair backup and rollback mechanics;
- source/base-CAD provenance and, after R2/R3 acceptance, linked component/view evidence.

What is missing is one deterministic orchestration boundary that can say:

```text
this immutable candidate artifact
came from this immutable parent/baseline
using these exact upstream R1/R2/R3 identities
with this exact component/view impact closure
and this exact mutation/backup evidence
```

while preserving every prior candidate and keeping selection, acceptance, and publication as separate authority transitions.

R4 fills only that orchestration gap.

## 3. Alternatives considered

### Option A — selected: stateless R4 core + existing-manifest integration

Create an adjacent pure-Python R4 core that validates upstream context, seals candidate revision records, evaluates freshness, and builds non-authoritative selection records. Persist only references/history through `cad_agent.manifest` in a separately bounded task.

Benefits:

- no second revision store;
- no overlap with R3 registry ownership;
- no direct CAD/AutoCAD transport dependency;
- deterministic offline RED/GREEN tests with synthetic records;
- legacy manifests remain compatible when optional R4 fields are absent;
- promotion remains cleanly downstream.

This is the selected architecture.

### Option B — rejected: dedicated R4 revision database or filesystem tree

A new SQLite/JSONL/CAS/database directory containing candidate history would duplicate the existing manifest/checkpoint truth owner and violate the reuse-first roadmap.

Classification: `REJECT_DUPLICATE_OWNER`.

### Option C — rejected: put revision lifecycle inside R3 registry

R3 owns logical component/view relationships. If R3 also minted candidate lineage, selected revisions, or rollback state, component/view identity would become coupled to revision policy and R4 would disappear as a distinct authority boundary.

Classification: `REJECT_DUPLICATE_OWNER`.

### Option D — rejected: revision control inside AutoCAD/File IPC

File IPC and the .NET plugin own transport/live CAD behavior. Making them the source of candidate lineage or current/published state would make runtime session state a revision truth store and would bind offline orchestration to AutoCAD availability.

Classification: `REJECT_DUPLICATE_OWNER`.

## 4. Reuse-first ownership map

| Capability | Current/expected owner | R4 classification | R4 use |
|---|---|---|---|
| Atomic run manifest/checkpoint/resume | `cad_agent/manifest.py`, `cad_agent/pdf.py`, existing CLI run/resume | `EXTEND_WITH_ADAPTER` | Optional R4 references and selection history are bound through this owner only. No second store. |
| Canonical JSON SHA-256 | `cad_agent.drawing_contracts.canonical_json_sha256()` | `REUSE_AS_IS` | Sole canonical identity/hash owner for R4 records. |
| Source/artifact file SHA-256 | existing `cad_agent.manifest.sha256_file()` and accepted upstream owners | `REUSE_AS_IS` | Used only at the existing owner boundary where a file must be verified. R4 core consumes hashes and does not reopen CAD. |
| R1 Source Bundle/Fusion identity | final accepted R1 owner after merge | `EXTEND_WITH_ADAPTER` after rebaseline | R4 records accepted upstream identity transitively/directly as resolved after R3. It does not re-fuse sources. |
| R2 frozen Base-CAD reuse evidence | final accepted R2 owner after runtime acceptance | `EXTEND_WITH_ADAPTER` after rebaseline | When reused components exist, R4 binds the accepted R2 handoff identity/source revision without re-extraction. |
| R3 Component/View Registry | final accepted R3 owner after runtime acceptance | `REUSE_AS_IS` after rebaseline | Primary component/view impact/provenance seam. R4 never becomes a registry. |
| Native DXF/entity generation | `dxf_builder_lib` | `REUSE_AS_IS` | Candidate artifact may come from this owner; R4 never writes geometry. |
| AutoCAD/File IPC transport | `mcp_integration_lib` + AutoCAD .NET plugin | `REJECT_DUPLICATE_OWNER` | R4 core makes no transport call. Candidate mutation remains with accepted live owners. |
| Visual evidence freshness | `cad_agent.visual_evidence`, `cad_agent.visual_contracts` | `REUSE_AS_IS` | R4 may bind a mutation/evidence hash. It does not issue visual PASS. |
| Repair backup/rollback | `cad_agent.live.repair_live()` and existing repair owners | `REUSE_AS_IS` | R4 may bind verified backup/rollback evidence; it never copies/restores CAD itself. |
| Approval/proposal/apply | existing approved `agent_lib`/server-owned authority gates | `REJECT_DUPLICATE_OWNER` | R4 may consume an externally authorized selection input if required; it never issues approval. |
| Independent visual/engineering verdict | future R5 and existing evidence owners | `REJECT_DUPLICATE_OWNER` | R4 candidate state is never a PASS/verdict. |
| Verified promotion/publication | future R7 + existing promotion boundary | `REJECT_DUPLICATE_OWNER` | R4 cannot mark accepted/current/published. |
| Candidate revision synchronization | no complete owner | `NEW_MISSING_CAPABILITY` | This is the narrow capability R4 owns. |

## 5. Mandatory post-R3 rebaseline and non-invention rule

Before the first R4 runtime Issue, Master PO must map each semantic dependency below to an **exact accepted symbol and field** on fresh current `main`.

### 5.1 Required final R1 seam

R4 needs only the final immutable source/fusion identity required to prove that the R3/R2 context is still bound to the accepted reconstruction input.

R4 must not directly interpret R1 conflict internals when R3 already exposes a validated upstream binding.

The runtime rebaseline records:

- exact validator/hash symbol(s);
- exact accepted upstream digest(s) that R3 transitively binds;
- exact stale/unresolved state that blocks a candidate.

### 5.2 Required final R2 seam

When a candidate contains reused Base-CAD components, accepted R2 must expose enough validated evidence to bind:

```text
R2 handoff identity/hash
base source identity
base source SHA-256
base source revision
reused logical component membership
candidate/source provenance binding
stale/re-extraction state
```

If final R3 already validates and carries this R2 binding transitively, R4 reuses that proof rather than validating a duplicate parallel copy.

No R2 planning-time API from PR #129 is assumed.

### 5.3 Required final R3 seam

Accepted R3 must expose enough validated data to obtain, without geometry parsing:

```text
registry snapshot identity/hash
candidate drawing identity/hash or accepted candidate binding
stable logical component IDs
stable logical view IDs
component/view provenance references
linked-view/component impact closure for an intended change
accepted upstream R1/R2 bindings
stale/foreign candidate detection
```

R4 also requires a deterministic way to bind a component/view identity in one registry snapshot to the same logical identity in a parent snapshot. This may be an accepted per-record digest, stable logical ID plus validated snapshot hash, or another final R3-owned canonical mechanism.

R4 must not invent that mechanism if R3 does not provide it.

### 5.4 Required current-baseline seam

R4 needs one server-owned immutable **baseline revision reference** from the existing accepted manifest/promotion lifecycle containing at least:

```text
baseline revision identity/hash
baseline drawing SHA-256
run/project identity sufficient to prevent cross-run rebinding
```

R4 does not create the production-current pointer. If no accepted owner can provide this reference after R3 merges, runtime stops rather than creating a second current-revision store.

### 5.5 Rebaseline failure state

Any material gap above returns:

```text
R4 REBASELINE REQUIRED
```

The first R4 runtime Issue is not widened to patch R1, R2, R3, manifest, transport, verdict, or publisher ownership.

## 6. R4 responsibility boundary

R4 owns only:

1. validation of an already accepted R1/R2/R3/current-baseline context through accepted owner seams;
2. deterministic candidate-revision identity;
3. immutable parent/ancestor lineage;
4. binding of candidate artifact hashes to exact component/view impact/provenance identity;
5. freshness/staleness evaluation against current accepted upstream identities;
6. construction of a non-authoritative selected-candidate-for-review record from an explicit caller/server selection;
7. supersession/selection rollback semantics that preserve all old candidate evidence;
8. deterministic hashes for the R4 records through the existing canonical owner;
9. optional manifest integration through the existing manifest/checkpoint lifecycle.

R4 does **not** own:

- source fusion or source custody;
- Base-CAD eligibility/extraction;
- component/view registry construction;
- Primitive/Semantic geometry or solving;
- DXF/native CAD generation;
- AutoCAD/File IPC transport;
- candidate CAD mutation execution;
- repair execution or backup copying;
- visual/engineering verdict;
- approval issuance;
- candidate acceptance;
- production-current promotion;
- publication;
- a database, CAS, revision directory, or second manifest/checkpoint store.

## 7. State model: candidate is not current, accepted, or published

R4 uses explicit authority separation rather than one overloaded `status` field.

### 7.1 Mutable candidate workspace

A workspace is a disposable CAD target owned by an existing generator/repair/synchronization/AutoCAD executor.

It may change while work is in progress.

It is **not** a revision and is never durable revision truth.

### 7.2 Sealed candidate revision

A workspace becomes an R4 candidate revision only after the accepted owner supplies all required immutable artifact and evidence hashes.

The sealed R4 state is exactly:

```text
SEALED_CANDIDATE
```

A sealed candidate revision is immutable. Any later CAD mutation requires a new disposable workspace and a new sealed candidate revision.

### 7.3 Selected candidate for review

R4 may bind an explicit exact candidate hash into a separate selection record:

```text
SELECTED_FOR_REVIEW
```

This means only “this is the candidate downstream review should inspect.” It does not mean visually correct, engineer-approved, accepted, current, or published.

R4 must never choose a candidate by inventing a quality score or by converting evidence into approval.

### 7.4 Accepted candidate

Acceptance belongs to downstream visual/engineering/approval authority. R4 does not emit `ACCEPTED` state and rejects attempts to inject acceptance authority into an R4 candidate or selection record.

### 7.5 Published/current production revision

Promotion/publication belongs to R7 Verified Publisher and existing promotion gates. R4 cannot set production-current, published, release, or authoritative-eligible state.

The current production/baseline revision is read-only input to R4.

## 8. Candidate revision artifact

The initial closed R4 runtime artifact is conceptually:

```text
candidate-revision-1.0
```

The root contains these concepts:

```text
schema_version
revision_id
state = SEALED_CANDIDATE
run_id
baseline_revision
parent_candidate_revision
upstream_bindings
candidate_artifacts
change_scope
component_lineage
view_lineage
mutation_evidence
candidate_revision_sha256
```

### 8.1 Baseline revision reference

`baseline_revision` is a read-only reference supplied from the accepted current-baseline owner after rebaseline. It contains only the minimum exact identity required to reject cross-run/current drift.

R4 does not update it.

### 8.2 Parent candidate reference

`parent_candidate_revision` is null for the first candidate descended directly from the baseline. A later candidate may point to one prior sealed candidate revision.

The parent reference binds the full parent candidate revision SHA-256, not a mutable ordinal such as `v2` or a filename.

Cycles, missing parents, cross-run parents, and self-parenting fail closed.

### 8.3 Upstream bindings

`upstream_bindings` records only accepted identity hashes needed to prove the revision's reconstruction context, including final R3 registry snapshot identity and, where final accepted architecture requires, R1/R2 upstream digests.

Absolute paths, source bytes, timestamps, approval state, and transport/session identifiers are not revision identity.

### 8.4 Candidate artifacts

`candidate_artifacts` is a closed sorted set of immutable artifact references supplied by accepted owners. The first R4 slice requires at least the candidate drawing SHA-256 and the exact R3 registry/candidate binding identity needed to locate its logical content.

Additional evidence hashes may be present only when the post-R3 runtime Issue explicitly closes the field set.

R4 core does not open or hash the drawing path itself.

### 8.5 Change scope

`change_scope` is derived from accepted R3 graph/impact evidence, never from R4 geometry inspection.

It binds deterministic sorted identities for:

```text
changed component IDs
impacted component IDs
impacted view IDs
impacted layout bindings
impact-closure evidence hash
```

A caller may not silently omit a linked impacted view proven by R3.

### 8.6 Component/view lineage

R4 records references, not a second registry.

For each affected logical component/view, the lineage binds:

```text
logical ID
parent registry snapshot identity
current registry snapshot identity
accepted R3-owned binding identity sufficient to prove same/different logical object
change class
```

Initial closed change classes are:

```text
UNCHANGED
CHANGED
NEW
REMOVED
```

R4 does not infer these classes from CAD geometry. They must be consistent with accepted R3 identity/impact evidence.

If R3 cannot prove a logical cross-snapshot relationship, R4 fails closed rather than inventing correspondence.

### 8.7 Mutation evidence

R4 may bind exact hashes/identities of already produced evidence such as:

```text
latest mutation identity/hash
build/review evidence hash
verified backup/rollback evidence hash when applicable
```

The field is evidence only. R4 does not perform the mutation, review, backup, rollback, or approval.

## 9. Deterministic revision identity and checksum

R4 uses only `cad_agent.drawing_contracts.canonical_json_sha256()` for canonical JSON identities.

### 9.1 Revision ID

The deterministic revision ID is derived from identity material containing:

```text
schema/version domain
run identity
baseline revision identity
parent candidate revision SHA-256
accepted upstream binding hashes
candidate artifact hashes
change-scope hash
component/view lineage identities
mutation evidence hashes required by the closed contract
```

The runtime implementation may encode the full canonical digest as a prefixed identifier, for example:

```text
candidate:<64-lowercase-hex-digest>
```

No truncated hash is required by the first design.

### 9.2 Candidate revision SHA-256

`candidate_revision_sha256` is the canonical hash of the complete normalized revision record with the checksum field excluded from its own input.

### 9.3 Forbidden identity inputs

Revision identity must not depend on:

- wall-clock time;
- backup filenames;
- filesystem traversal order;
- absolute/private paths;
- AutoCAD HWND/PID/session IDs;
- random UUIDs;
- volatile entity handles unless the accepted R3 candidate binding explicitly makes a handle part of the snapshot artifact identity;
- approval/reviewer name;
- visual verdict;
- publication state;
- caller list order.

Timestamped backup filenames in the existing live repair owner are operational recovery artifacts, not R4 revision IDs.

## 10. Immutable lineage rules

Every sealed candidate revision satisfies:

```text
one exact run/project scope
one exact baseline revision
zero or one exact parent candidate revision
one exact current R3 registry snapshot
one exact candidate artifact set
one exact change/impact scope
```

Rules:

- a sealed revision cannot be rebound to a different registry, baseline, R2 source revision, candidate drawing hash, or parent;
- parent candidate artifacts remain intact;
- a revision cannot point to a descendant or itself;
- parent and child must use the same run/project scope;
- changing one candidate artifact hash creates a different revision identity;
- changing only list order must not change identity;
- a candidate derived from stale upstream evidence is blocked, not silently rebound;
- supersession never deletes a predecessor.

## 11. Stale upstream behavior

R4 evaluates freshness at every candidate creation, selection, resume, and downstream handoff boundary.

Closed initial freshness states:

```text
CURRENT
STALE_UPSTREAM
STALE_BASELINE
FOREIGN_SCOPE
```

### `CURRENT`

All accepted R1/R2/R3/current-baseline identities match the sealed revision context required for the operation.

### `STALE_UPSTREAM`

The final accepted R3 registry or transitively bound R1/R2 identity changed after this candidate was sealed.

The existing candidate remains valid historical evidence but cannot be silently selected as if it described the new upstream context.

### `STALE_BASELINE`

The server-owned current baseline reference changed. The candidate does not become the child of the new baseline automatically.

### `FOREIGN_SCOPE`

Run/project/baseline/candidate identity belongs to another scope.

All non-`CURRENT` states fail closed for new selection/promotion handoff. R4 never rewrites old revisions to fix freshness.

## 12. Base-CAD source revision changes

If reused components are present and accepted R2/R3 evidence reports that the exact Base-CAD source SHA/revision changed:

1. the old candidate revision remains immutable and historically correct for the source revision it used;
2. R4 marks it stale for the new upstream context;
3. R4 does not overwrite reused components;
4. R4 does not call extraction;
5. a new approved R2 extraction/workspace must be produced by the existing owner;
6. R3 must produce a fresh accepted registry snapshot;
7. only then may R4 seal a new candidate revision.

This preserves the frozen-copy rule from the accepted exact-base architecture.

## 13. Selection-for-review record

Selection is a separate closed artifact, conceptually:

```text
candidate-selection-1.0
```

It contains:

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

- the selected revision must be one of the explicitly supplied eligible sealed candidates;
- all candidate records must be `CURRENT` against the exact selection context;
- candidate and baseline scopes must match;
- caller order does not affect normalized eligible set;
- R4 does not rank candidates;
- no evidence score can be converted into acceptance;
- no approval, visual PASS, engineer PASS, publish, or production-current field is allowed;
- selecting candidate B does not delete candidate A;
- a later selection may supersede the selection pointer while preserving both selection records/history.

The caller/server chooses the exact candidate hash. R4 only validates and binds the choice.

## 14. Rollback and supersession semantics

R4 has two different rollback concepts and must not conflate them.

### 14.1 Candidate-workspace mutation rollback

This belongs to existing execution owners such as `cad_agent.live.repair_live()` and accepted AutoCAD/S3 mutation boundaries.

R4 may bind verified backup/rollback evidence after the fact.

R4 never copies, restores, opens, saves, closes, or reopens CAD files.

### 14.2 Revision/selection rollback

This is orchestration only.

A failed or rejected candidate remains as immutable evidence. To return downstream review to a prior candidate, the manifest selection pointer may be changed through the existing manifest owner while preserving:

- every candidate revision reference;
- every prior selection record/reference;
- prior hashes;
- parent lineage;
- failure/rejection evidence owned downstream.

No candidate revision artifact is edited or deleted.

A later candidate supersedes a predecessor by lineage/reference, not by overwriting its files or record.

## 15. Manifest/checkpoint integration without a second revision store

R4 core owns no persistence mechanism.

A separately bounded integration task may extend `cad_agent.manifest` with optional closed references using the same compatibility principles as the accepted SourceBundle binding:

```text
candidate_revision_refs[]
candidate_selection_refs[]
selected_candidate_revision_sha256
```

Exact field names are proposed R4-owned manifest integration names and may be finalized only by the runtime Issue after the post-R3 rebaseline.

Required behavior:

- `cad_agent.manifest` remains the sole validator/binder for durable references;
- `write_manifest()` remains the atomic writer;
- existing run/resume and PDF run/resume remain authoritative;
- absent R4 fields remain absent for legacy manifests;
- no migration rewrites old manifests;
- adding the same revision reference is idempotent;
- conflicting same-ID/different-hash binding fails closed;
- selection can reference only an already bound revision;
- moving a selected-candidate pointer does not remove historical candidate/selection refs;
- R4 integration may not change `release_profile`, `authoritative_release_eligible`, acceptance, or publication fields;
- a malformed optional R4 reference blocks resume before stage work rather than being ignored.

`cad_agent.pdf.read_pdf_manifest()` must use the same manifest-owned validators if PDF manifests can carry the optional R4 references after final rebaseline. R4 must not create a PDF-specific revision owner.

## 16. Existing backup and rollback capability reuse

`cad_agent.live` already provides verified repair backup semantics:

```text
hash original DXF/evidence
copy backup
re-hash source and backup
refuse mutation when verification fails
repair through existing executor
second review
save only on acceptable repair result
otherwise close modified original without save and reopen verified backup
```

R4 reuses this as execution evidence.

R4 must not duplicate:

- backup naming;
- `shutil.copy2` behavior;
- document open/close/save logic;
- AutoCAD recovery;
- repair execution;
- second review.

An R4 candidate can bind the resulting report/evidence hash, but not reinterpret it as candidate acceptance.

## 17. Candidate-only mutation boundary

A source, exact Base-CAD source, accepted drawing, or production-current drawing is never an R4 mutation target.

The allowed flow is:

```text
immutable current/baseline reference
    -> existing owner creates a new disposable candidate workspace
    -> existing authorized executor mutates only that workspace
    -> existing owner emits artifact/evidence hashes
    -> R3 emits a fresh registry/candidate binding
    -> R4 seals an immutable candidate revision
```

Any request to mutate an already sealed candidate revision must instead create a new workspace and child revision.

R4 itself performs no CAD mutation in the first runtime architecture.

## 18. Creation, selection, acceptance, and promotion authority

| Transition | Owner | R4 authority |
|---|---|---|
| Create disposable candidate workspace | existing DXF/R2/repair/AutoCAD execution owner | none |
| Seal candidate revision identity/lineage | R4 | yes |
| Select exact candidate for downstream review | caller/server chooses; R4 validates/binds | validation/binding only |
| Visual/engineering acceptance | R5/existing engineer approval authority | none |
| Repair execution | R6/existing repair executor | none |
| Promote to production-current / publish | R7 Verified Publisher + existing promotion gate | none |

R4 validators reject any field or operation that attempts to make R4 an approval, verdict, repair, or publication owner.

## 19. Compatibility with existing visual evidence

Existing visual evidence binds read-only evidence to `latest_mutation_sha256` and rejects stale render/session state.

R4 may include an accepted mutation/evidence identity in a candidate revision so downstream R5 can prove that evidence refers to the exact candidate.

R4 does not call `require_region_verified()`, convert a region status into candidate acceptance, or issue a visual verdict.

The downstream direction is:

```text
R4 sealed candidate revision
    -> R5 evidence/verdict bound to exact candidate revision SHA
    -> R6 repair may create another candidate workspace/revision
    -> R7 promotion only after accepted gates
```

## 20. Privacy and evidence minimization

R4 artifacts and public errors must not contain:

- absolute/private source paths;
- raw customer content;
- AutoCAD process/HWND/session identity;
- HMAC/key material;
- raw parser/transport exception text;
- source bytes;
- provider/model prompts;
- approval secrets.

Where an accepted owner uses an absolute path operationally, R4 records only the accepted opaque/hash identity required by the revision contract.

Synthetic first-runtime tests use generated mappings and disposable files only.

## 21. Proposed R4 public API

The first R4 core runtime is proposed as one adjacent module:

```text
cad_agent/candidate_revision.py
```

with a focused test owner:

```text
tests/test_cad_agent_candidate_revision.py
```

Proposed public surface:

```python
CANDIDATE_REVISION_SCHEMA_VERSION = "candidate-revision-1.0"
CANDIDATE_SELECTION_SCHEMA_VERSION = "candidate-selection-1.0"

class CandidateRevisionError(ValueError): ...

def build_candidate_revision(
    *,
    upstream_context: object,
    baseline_context: object,
    parent_candidate: object | None,
    candidate_artifacts: object,
    change_scope: object,
    mutation_evidence: object,
) -> dict[str, object]: ...

def validate_candidate_revision(
    payload: object,
    *,
    upstream_context: object,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> dict[str, object]: ...

def candidate_revision_sha256(
    payload: object,
    *,
    upstream_context: object,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> str: ...

def evaluate_candidate_revision_freshness(
    *,
    revision: object,
    upstream_context: object,
    baseline_context: object,
) -> dict[str, object]: ...

def build_candidate_selection(
    *,
    revisions: object,
    selected_revision_sha256: str,
    upstream_context: object,
    baseline_context: object,
) -> dict[str, object]: ...

def validate_candidate_selection(
    payload: object,
    *,
    revisions: object,
    upstream_context: object,
    baseline_context: object,
) -> dict[str, object]: ...
```

`upstream_context` and `baseline_context` are R4 call-parameter names, not invented R1/R2/R3/current-store contracts. The future runtime Issue must map them to exact accepted validators/fields during Gate 0 before any code is written.

The core module must remain pure orchestration: no filesystem, CAD parser, DXF builder, IPC, network, subprocess, model, approval, verdict, repair, publication, or database behavior.

## 22. Proposed minimal runtime write-set

### R4 core Tasks 1–2

Create/modify only:

```text
cad_agent/candidate_revision.py
tests/test_cad_agent_candidate_revision.py
```

### R4 manifest integration Task 3

Only after core acceptance and a fresh overlap check:

```text
MODIFY cad_agent/manifest.py
MODIFY cad_agent/pdf.py
MODIFY tests/test_cad_agent_candidate_revision.py
```

No R4 production module modification is required merely to persist already validated references unless final current-main behavior proves otherwise.

If a third production owner beyond `manifest.py`/`pdf.py` appears necessary for persistence, stop and rebaseline rather than adding a store or CLI workflow by convenience.

## 23. Runtime task decomposition

The detailed implementation plan will split R4 into:

1. **Candidate revision core** — deterministic identity, immutable lineage, accepted upstream/candidate binding, stale/fail-closed behavior;
2. **Selection and supersession** — explicit selection-for-review, parent/child lineage, stale selection refusal, logical rollback without deleting prior evidence;
3. **Existing-manifest integration** — optional durable revision/selection references and selected-candidate pointer under the existing manifest/PDF readers only.

No task implements approval, verdict, repair execution, publisher behavior, or AutoCAD live work.

## 24. RED-first adversarial requirements

The runtime plan must prove meaningful RED before production edits for at least:

### Identity/determinism

- same semantic input in different caller order -> same revision ID/hash;
- changed candidate drawing hash -> different revision;
- changed registry snapshot -> different revision;
- changed baseline/parent -> different revision;
- changed impact closure -> different revision;
- timestamp/path/UUID/session changes that are non-authoritative -> no identity change;
- NaN/noncanonical upstream data rejected by accepted upstream owner;
- unknown R4 fields fail closed.

### Lineage

- self-parent rejected;
- missing/foreign parent rejected;
- cross-run parent rejected;
- stale baseline rejected;
- stale R1/R2/R3 binding rejected;
- child cannot rewrite parent;
- prior candidate survives supersession.

### R2/R3 provenance

- reused Base-CAD source SHA/revision mismatch -> stale/block;
- component/view logical mismatch -> block;
- omitted R3-linked impacted view -> block;
- caller-forged component correspondence -> block;
- candidate handle/path cannot replace R3 logical identity.

### State/authority

- `SEALED_CANDIDATE` is never accepted/published/current;
- attempt to inject approval/verdict/publish fields -> reject;
- selection of unknown candidate -> reject;
- selection of stale candidate -> reject;
- R4 cannot rank candidates automatically;
- moving selection preserves all candidate evidence;
- rollback selection does not mutate CAD.

### Persistence

- legacy manifests without R4 fields remain byte/behavior compatible when not rewritten;
- optional references validate through manifest owner;
- duplicate same reference is idempotent;
- same revision ID/different hash conflicts;
- selection pointer must target a bound candidate;
- changing pointer preserves reference/history arrays;
- malformed optional R4 field blocks resume;
- PDF reader uses same manifest-owned validator;
- no authoritative release/publish field changes.

### Ownership/privacy

- no AutoCAD/File IPC call;
- no parser/DXF writer import;
- no backup implementation duplication;
- no component registry creation;
- no approval/verdict/publisher owner;
- no private path/raw source leakage;
- no new dependency/store/schema directory.

## 25. Verification model

Every future R4 runtime task must run:

- its exact focused RED/GREEN suite;
- accepted final R1 tests named by Gate 0 where relevant;
- accepted final R2 tests named by Gate 0 where relevant;
- accepted final R3 tests named by Gate 0;
- manifest/PDF run/resume regressions when Task 3 is involved;
- existing backup/rollback tests when evidence bindings are involved, without live mutation;
- Ruff on exact changed Python paths;
- architecture/reuse ratchet;
- `git diff --check`;
- exact changed-file audit;
- canonical `scripts/verify.ps1 -SkipAutoCADDotNet`;
- hosted `tests` and `reuse-declaration` on exact head/current-main synthetic;
- independent authority/determinism reviewer;
- independent integration/CI/write-set reviewer.

AutoCAD live/private-data gates remain `NOT RUN` unless a separately authorized local evidence Issue explicitly runs them. They are never promoted from `SKIP`/`NOT RUN` to `PASS`.

## 26. PASS / FAIL / SKIP / NOT RUN semantics

| State | R4 meaning |
|---|---|
| `PASS` | The named check actually executed against the exact stated revision/head/evidence and satisfied all assertions. |
| `FAIL` | The check executed and contradicted a required invariant. Progression is blocked. |
| `SKIP` | An explicitly optional/gated probe was intentionally skipped under a declared prerequisite. It is not acceptance evidence. |
| `NOT RUN` | A required live/private/environment operation was unavailable or not attempted. It is never treated as PASS. |

## 27. Dependency and overlap matrix

| Lane / owner | Relationship to R4 | R4 rule |
|---|---|---|
| Active R1 Source Fusion | Upstream runtime dependency | R4 runtime cannot start until final R1 accepted/merged. No R1 path changes. |
| PR #129 R2 planning | Planning input only; HOLD MERGE | Do not assume its proposed API. Final accepted R2 runtime seam is resolved post-R3. |
| Issue #128 R3 planning | Moving planning input only | Do not assume its proposed API or paths are accepted. R4 records semantic seam requirements only. |
| Final R2 runtime | Upstream evidence dependency where Base-CAD reuse exists | Consume accepted frozen provenance; no extraction/AutoCAD logic. |
| Final R3 runtime | Immediate upstream dependency | Consume validated registry/impact identity read-only. No registry write. |
| `cad_agent.manifest` / PDF lifecycle | Existing durable owner | Task 3 only after exact overlap check; no second store. |
| Luna / AutoCAD local lane | Live operator authority | R4 core requires no live AutoCAD. No simultaneous session control. |
| `dxf_builder_lib` | Candidate geometry producer | Read accepted artifact identity only; no write. |
| `cad_agent.live` / repair owners | Backup/rollback executor | Bind evidence only; no duplicated repair/backup code. |
| Future R5 | Consumer of exact sealed candidate revision | R5 verdict must bind R4 revision SHA; R4 cannot pre-emit verdict. |
| Future R6 | May create a repaired candidate workspace | Repair produces evidence/workspace; R4 seals the resulting child revision. |
| Future R7 | Promotion/publication owner | R7 may consume accepted candidate revision; R4 never sets current/published. |

## 28. Migration and rollback

### Planning PR

No runtime migration exists. Reverting the two planning docs removes only planning guidance.

### Future R4 core

Migration is additive: add the adjacent R4 core/test without changing existing artifacts or stores.

Rollback: remove/revert the R4 core. Existing R1/R2/R3, manifests, DXF, repair, Visual Supervisor, and AutoCAD workflows remain unchanged.

### Future manifest integration

Migration is optional fields only. Legacy manifests without R4 references remain valid and unchanged.

Rollback removes the optional binding behavior. Existing manifests/checkpoints remain authoritative and candidate artifact files are not deleted by rollback.

No destructive data migration is allowed in the first R4 sequence.

## 29. STOP conditions

Stop and report `R4 REBASELINE REQUIRED` rather than widening scope if any of these are true:

- final accepted R1/R2/R3 symbols or identity semantics materially differ from the required seams;
- R3 cannot provide deterministic logical component/view correspondence without R4 rebuilding a registry;
- R2/Base-CAD provenance must be reopened or re-extracted by R4;
- no accepted owner can provide the current/baseline revision identity required to reject drift;
- candidate lineage would require a new database/CAS/revision directory;
- manifest/checkpoint behavior cannot be extended compatibly;
- an R4 task would need to modify R3 production merely for convenience;
- AutoCAD/File IPC transport must be added to R4;
- CAD parsing/DXF generation is required in R4;
- R4 would need to execute repair or implement backup/restore;
- a visual/engineering verdict is needed to build an R4 record;
- R4 would need to issue approval;
- R4 would need to set accepted, production-current, release-eligible, or published state;
- private/customer CAD is required for first runtime tests;
- dependency/lock/workflow/schema-directory changes are required;
- any accepted upstream test must be weakened/skipped to obtain GREEN;
- any runtime task needs a path outside its exact issued allowlist.

## 30. Acceptance for this planning slice

This planning task is acceptable only when:

- exactly the two Issue #133 planning documents are created;
- the design references current accepted architecture/reuse owners instead of duplicating them;
- PR #129 and moving R3 #128 remain explicitly non-authoritative planning inputs;
- candidate/current/accepted/published states are separated;
- candidate revision identity and lineage are deterministic and immutable;
- manifest/checkpoint remains the sole durable owner;
- backup/rollback is reused rather than reimplemented;
- R2/R3 semantic seams and post-R3 rebaseline conditions are explicit;
- the runtime plan is RED-first with bounded candidate write-sets;
- no runtime/test/workflow/dependency/CAD/private-data change exists in this planning PR;
- hosted tests/reuse/docs checks are GREEN on the exact final planning head/current-main synthetic;
- the PR remains DRAFT;
- writer stops repository writes after final hosted GREEN.