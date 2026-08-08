# R2 Base CAD Adapter Design

## Status and authority

- Planning Issue: `#127 — [R2 Planning] Base CAD Adapter executable design and runtime plan`
- Activation comment: `5227049025`
- Exact planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`
- Planning branch: `planning/issue-127-r2-base-cad-adapter`
- This document is planning/design only.
- R2 runtime remains **LOCKED** until the complete accepted R1 Source Bundle/Fusion Adapter is merged and a fresh runtime rebaseline passes all gates in this document.
- S3B implementation is accepted, but R2 runtime also requires accepted S3B live inspection/extraction evidence to be `PASS`; `SKIP` and `NOT RUN` are not substitutes.

This design adds no runtime code, dependency, lock file, workflow, schema-directory contract, AutoCAD operation, private/customer CAD, component registry, revision store, repair executor, visual verdict, approval issuer, or publisher.

## 1. Decision summary

R2 will be one **thin, stateless Base CAD Adapter** in `cad_agent` around already accepted R1, S3A, and S3B owners.

The selected runtime shape is an adjacent pure-Python orchestration module, provisionally:

```text
cad_agent/base_cad_adapter.py
```

with one focused test owner:

```text
tests/test_cad_agent_base_cad_adapter.py
```

R2 does not parse CAD, inspect Xrefs itself, copy entities itself, own AutoCAD transport, write DXF, issue approvals, persist components, select a current revision, or mutate accepted/current drawings.

Its responsibility is limited to:

1. bind one accepted R1 `READY` fusion input to the exact `EXACT_BASE_CAD/BASE_CAD` source identity;
2. bind that source to fresh S3A-compatible S3B live inspection evidence;
3. refuse ineligible, stale, mismatched, ambiguous, or globally deformed base-CAD reuse;
4. create deterministic **proposed** extraction selections by calling S3A rather than reimplementing extraction-plan rules;
5. consume an externally approved S3A extraction plan without issuing approval;
6. delegate live extraction exactly through the existing S3B `DotNetIPCClient.exact_base_xref_extraction()` boundary, which owns fresh preflight and candidate-only mutation;
7. normalize S3B success into a deterministic, privacy-safe frozen reuse handoff for future R3 consumption;
8. detect later source hash/revision drift and produce a re-extraction proposal without silently overwriting a frozen copy.

The governing ownership rule is:

> R1 owns source custody/fusion truth; S3A owns exact-base inspection/extraction-plan semantics; S3B owns live Xref inspection, fresh preflight, path policy, transport, and candidate mutation; R2 only binds those authorities into a deterministic reuse handoff; R3 later owns component/view registration.

## 2. Alternatives considered

### Option A — selected: adjacent stateless `cad_agent` adapter

Create one orchestration module and one focused test module. It consumes accepted R1/S3 records, reuses canonical hashes, calls S3A builders/validators, and delegates live execution to S3B. It emits immutable transfer records but no store.

Why selected:

- no overlap with active/future R1 `source_fusion` writers;
- no modification to S3B production owners merely for convenience;
- no second CAD parser, extraction engine, path authority, transport, registry, or revision owner;
- synthetic hosted tests can cover the adapter while live AutoCAD remains separately controlled;
- R3 can consume one closed handoff without making R2 a registry.

### Option B — rejected: extend S3B C# / File IPC contracts for R2 semantics

This would place R1 fusion binding, provenance freeze, and future-registry semantics inside `mcp_integration_lib/**`, `autocad_plugin/**`, or IPC schemas. S3B already owns live inspection/extraction and fresh preflight. Adding R2 there would mix orchestration with transport/mutation authority and create unnecessary overlap with the Luna local lane.

Classification: `REJECT_DUPLICATE_OWNER` unless a later exact defect proves an S3B contract is insufficient and Master PO explicitly rebaselines R2.

### Option C — rejected: make R2 a component/revision registry

Persisting candidate handles, component revisions, current-state pointers, or stale-source replacement decisions inside R2 would absorb R3/R4 responsibilities and create a second truth store.

Classification: `REJECT_DUPLICATE_OWNER`.

## 3. Internal reuse audit

| Capability | Current owner / concrete API | Classification | R2 decision |
|---|---|---|---|
| R1A declared source identity | `cad_agent/source_bundle.py`: `validate_source_bundle()`, `source_bundle_sha256()`; `EXACT_BASE_CAD` + `BASE_CAD` role | `REUSE_AS_IS` | Require exactly one selected exact-base source for the R2 binding. Do not use pathname as authority. |
| R1C byte custody | `cad_agent/source_integrity.py`: `validate_source_custody()`, `source_custody_sha256()` and accepted READY semantics | `REUSE_AS_IS` | R2 accepts only accepted `READY` custody and uses observed SHA/source identity; it never opens source bytes. |
| R1C final fusion packet | accepted plan seam in `cad_agent/source_fusion.py`: `build_source_fusion_packet()`, `validate_source_fusion_packet()`, `source_fusion_sha256()`, `require_source_fusion_match()` after final R1 merge | `EXTEND_WITH_ADAPTER` | R2 consumes and revalidates the final accepted seam. If the merged seam is materially different, runtime stops with `R2 REBASELINE REQUIRED`. |
| Canonical JSON identity | `cad_agent/drawing_contracts.py::canonical_json_sha256()` | `REUSE_AS_IS` | Sole canonical JSON hash owner for R2 records. No second serializer/hash convention. |
| S3A offline exact-base contract | `mcp_integration_lib/exact_base_xref.py`: `validate_xref_inspection()`, `build_extraction_plan()`, `validate_extraction_plan()`, `REUSED_FROM_BASE_CAD`, `TRANSFORM_POLICY` | `REUSE_AS_IS` | R2 does not recode identity/dimension eligibility, component membership, provenance, transform, or plan rules. |
| S3B Python live client | `mcp_integration_lib/dotnet_ipc.py::DotNetIPCClient.exact_base_xref_inspection()` and `exact_base_xref_extraction()` | `REUSE_AS_IS` | Sole Python live dispatch seam used by R2. No generic alternate operation builder. |
| S3B .NET live inspection/extraction | existing IPC contracts plus `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs`, `AutoCadExactBaseXrefReader.cs`, dispatcher/gateway | `REUSE_AS_IS` | Owns fresh live facts, read-only Xref inspection, canonical path policy, preflight and candidate mutation. R2 does not port this logic. |
| S3B result provenance | `contracts/autocad-ipc/examples/exact-base-xref-extraction.result.json`: source SHA/revision, source handle/layer/block, local transform, candidate handle, live-preflight hash, candidate input/output hashes, source immutability | `EXTEND_WITH_ADAPTER` | Normalize only these already-produced facts into the R2-to-R3 frozen handoff. |
| Manifest/checkpoint/resume | `cad_agent/manifest.py`: `read_manifest()`, `write_manifest()`, `completed_artifact()`, `bind_source_bundle()`, `require_source_bundle_match()`; `cad_agent/pdf.py`; current CLI staged-run owner | `REUSE_AS_IS` | R2 creates no store or current pointer. The first R2 slice remains stateless and hash-bound. Any future persisted small reference must be added only through the existing manifest owner in a separately approved task after R3/R4 needs are known. |
| Native editable DXF/entity generation | `dxf_builder_lib/builder.py::build_dxf()`, `NativeLinearDimensionSpec` | `REUSE_AS_IS` | R2 never generates replacement geometry. Changed/new components continue through existing Primitive/Semantic/DXF owners. |
| AutoCAD File IPC/.NET transport | `mcp_integration_lib.dotnet_ipc.DotNetIPCClient` and existing dispatcher | `REUSE_AS_IS` | R2 calls only the exact-base S3B methods. No transport/dispatcher is added. |
| Drawing Setup gate | `cad_agent/drawing_setup.py::require_setup_verified()` plus setup plan/audit/evidence contracts | `REUSE_AS_IS` | Target drawing setup is a downstream/candidate readiness gate where required. It is not reinterpreted as base-source identity. |
| Dimension-first evidence | `cad_agent/dimension_pilot.py::run_dimension_pilot()`, existing dimension contracts, Semantic solver and `dxf_builder_lib` | `REUSE_AS_IS` | R2 does not OCR/re-solve dimensions. S3A's required vehicle/model + wheelbase/track/chassis/cabin/axle checks remain the exact-base eligibility gate; accepted dimension evidence may supply those expectations upstream. |
| Frozen Base-CAD-to-R3 transfer record | no current owner provides one deterministic R1+S3 cross-boundary handoff without persistence | `NEW_MISSING_CAPABILITY` | This is the genuine R2 capability. It is a closed transfer record, not a component registry or revision store. |
| Component/view registry | future R3 | `REJECT_DUPLICATE_OWNER` | R2 may carry logical component IDs and candidate handles as evidence but never persists ownership/current status. |
| Candidate revision selection/history | future R4 | `REJECT_DUPLICATE_OWNER` | R2 may identify a disposable candidate hash but never marks a revision current/accepted or provides rollback history. |
| Approval issuer / visual verdict / publisher | existing/future dedicated owners | `REJECT_DUPLICATE_OWNER` | R2 consumes explicit approval only where S3B already requires it; it never issues approval, PASS, promotion, or publication. |

## 4. Existing exact-base authority that R2 must preserve

### 4.1 S3A inspection eligibility

`validate_xref_inspection()` already requires:

- exact closed inspection shape;
- vehicle and model observations exactly once;
- required critical controls `wheelbase`, `track`, `chassis`, `cabin`, `axle` exactly once;
- PASS status consistent with observed/target values and tolerance;
- read-only Xref evidence;
- `changed == false`;
- equal `dbmod_before` / `dbmod_after`;
- no conflicts for eligibility;
- inspected components with unique logical IDs and source handles;
- `REUSED_FROM_BASE_CAD` provenance.

R2 must call this validator. It must not implement a looser second eligibility calculation.

### 4.2 S3A extraction-plan semantics

`build_extraction_plan()` and `validate_extraction_plan()` already own:

- membership only from an eligible inspection;
- source ID/hash/revision binding;
- target drawing hash binding;
- source handle/layer/block/component metadata preservation;
- local translation, rotation, and positive uniform scale only;
- no global transform, reflection, arbitrary matrix, target-handle fabrication, verdict, repair, or publication fields;
- proposed versus externally approved plan reference semantics.

R2 proposal creation therefore calls `build_extraction_plan()` with its default `PROPOSED` approval. R2 never converts a proposal into approved authority itself.

### 4.3 S3B live authority

`DotNetIPCClient.exact_base_xref_inspection()` sends only inspection expectations and validates a fresh live result.

`DotNetIPCClient.exact_base_xref_extraction()` validates the offline S3A plan, requires approval equality, validates controlled paths, and delegates to the accepted .NET operation. The S3B server performs a complete fresh preflight immediately before mutation and only mutates a disposable candidate.

R2 does not expose a generic IPC `request()` escape hatch and does not reconstruct S3B request payloads itself.

## 5. R2 input contract after final R1 acceptance

The R2 adapter consumes four authority inputs and optional proposal inputs:

```text
source_bundle     -> R1A normalized SourceBundle
custody           -> accepted R1C READY source-custody record
fusion            -> accepted final R1 source-fusion packet
live_inspection   -> fresh S3B payload validated by S3A
```

plus later:

```text
selections                  -> logical component IDs + local transforms for a PROPOSED plan
approved_extraction_plan    -> externally approved S3A plan
approval                    -> the same explicit approval object consumed by S3B
S3B candidate/result facts  -> existing S3B output only
```

### 5.1 Final-R1 rebaseline checklist

Before the first R2 runtime Issue is issued, current `main` must prove that final R1 provides semantically equivalent accepted APIs for:

```python
validate_source_fusion_packet(payload)
source_fusion_sha256(payload)
require_source_fusion_match(*, source_bundle, custody, fusion)
```

and a fusion state that distinguishes reusable/ready input from blocking unresolved conflicts.

R2 must be able to bind the exact base source without reopening files by using:

- SourceBundle `source_id`, `kind=EXACT_BASE_CAD`, `role=BASE_CAD`, declared SHA;
- accepted custody item `source_id` and observed SHA;
- final fusion/custody/source-bundle match APIs.

If final R1 does not expose these facts safely, the first R2 runtime issue is not widened. It stops with:

```text
R2 REBASELINE REQUIRED
```

### 5.2 One exact-base source per binding

The initial R2 slice requires exactly one `EXACT_BASE_CAD/BASE_CAD` item in the bound SourceBundle. Zero or multiple eligible base sources fail closed. Multi-base arbitration is not introduced in R2.

### 5.3 Path strings are not authority

R1 SourceBundle and S3A may carry safe relative-path metadata for compatibility, but R2 never uses it to prove filesystem identity or containment. S3B server-owned canonical path/hash/revision policy remains authoritative for live access.

## 6. Deterministic R2 records

R2 introduces in-code closed record versions only; no schema-directory change is required for the proposed first runtime sequence.

### 6.1 `base-cad-binding-1.0`

Conceptual normalized fields:

```text
schema_version
run_id
source_bundle_sha256
source_custody_sha256
source_fusion_sha256
base_source:
  source_id
  sha256
  revision
inspection_id
inspection_sha256
target_drawing_sha256
eligible_component_ids
transform_policy
state = READY_FOR_SELECTION
```

`revision` comes from the S3B/S3A inspection `base_source.revision`; R1 remains the source byte/hash authority. R2 requires source ID and hash to match both boundaries.

The binding digest is computed only with `canonical_json_sha256(validated_binding)`.

### 6.2 Proposed extraction selection

R2 exposes a proposal helper that calls S3A `build_extraction_plan()` against the bound eligible inspection. The result remains an S3A extraction plan with:

```text
approval.status = PROPOSED
approval.reference = null
```

No R2 approval state is invented.

### 6.3 `base-cad-reuse-handoff-1.0`

After an externally approved plan succeeds through S3B, R2 normalizes a frozen transfer artifact for R3 with no absolute path or timestamp authority:

```text
schema_version
run_id
source_bundle_sha256
source_custody_sha256
source_fusion_sha256
base_cad_binding_sha256
inspection_sha256
extraction_plan_sha256
base_source:
  source_id
  sha256
  revision
candidate_input_sha256
candidate_output_sha256
live_preflight_evidence_sha256
components[]:
  logical_component_id
  source_handle
  source_layer
  source_block
  source_sha256
  source_revision
  candidate_handle
  transform
  provenance = REUSED_FROM_BASE_CAD
source_handle_to_candidate_handle[]
```

R2 validates that component/source facts agree with the approved S3A plan and S3B result before emitting the handoff. It does not infer missing handles or metadata.

The handoff is an immutable **transfer artifact**. It does not contain:

- component revision/current pointers;
- view/layout ownership;
- accepted/current revision state;
- approval status for R3;
- visual/engineering verdict;
- repair or publication permission.

Those omissions are the R3/R4 boundary, not missing R2 work.

## 7. Exact eligibility and no-global-deformation policy

R2 accepts base reuse only when all of the following are true:

1. final R1 source bundle/custody/fusion match and fusion is reusable/ready;
2. exactly one base source is selected by exact role/kind;
3. R1 declared/observed source SHA and S3A/S3B inspection source SHA agree;
4. S3 inspection run ID matches the R1 run;
5. S3A inspection validates and is `eligible == true`;
6. Xref is read-only and inspection reports no mutation/conflict;
7. S3A's vehicle/model and all five critical dimension controls pass;
8. proposal components are a subset of inspected components;
9. the extraction plan uses S3A `TRANSFORM_POLICY` only;
10. no adapter-level/global scale, warp, reflection, non-uniform transform, arbitrary matrix, or fit-to-image transform exists.

A positive local uniform scale allowed by S3A is component-local transformation metadata. It must never be lifted into a global deformation of the base vehicle drawing.

If a merely similar CAD requires global stretching/scaling/warping to match target evidence, R2 blocks base reuse. The changed/new geometry returns to the existing reconstruction pipeline instead of forcing the base to fit.

## 8. Approval and extraction boundary

R2 has no approval issuer.

The sequence is:

```text
R2 binding
  -> R2/S3A PROPOSED extraction plan
  -> external/operator approval under existing authority
  -> R2 receives already-APPROVED S3A plan + matching approval object
  -> R2 revalidates plan and current binding
  -> existing DotNetIPCClient.exact_base_xref_extraction()
  -> S3B fresh live preflight immediately before transaction
  -> disposable candidate mutation only
  -> S3B result validation
  -> R2 frozen reuse handoff
```

R2 must not:

- fabricate an approval reference;
- turn `PROPOSED` into `APPROVED`;
- treat a matching string as a generic approval issuer;
- bypass S3B's approval equality check;
- call S3B generic request operations to evade exact-base checks.

If no accepted upstream approval authority can supply the exact approved S3A plan and envelope approval required by S3B at runtime, extraction remains `NOT RUN`; R2 does not invent one.

## 9. Source and accepted-CAD immutability

The original exact-base source is always read-only authority. Accepted/current CAD is never an R2 mutation target.

R2 relies on S3B server-owned path policy and live result invariants, including:

- source hash/revision binding;
- canonical path/alias/root checks;
- source not saved and not mutated;
- source SHA before/after equal;
- accepted target not overwritten;
- mutation only in a new disposable candidate;
- fresh preflight immediately before extraction;
- cleanup/restoration on failure.

R2 checks the relevant returned invariants before producing a handoff but does not duplicate S3B's filesystem or AutoCAD implementation.

## 10. Stale source / Xref behavior

Frozen reuse is bound to the exact source `source_id + SHA-256 + revision` used for extraction.

When a later accepted source/Xref identity differs:

```text
same source_id + same sha + same revision -> CURRENT
anything else                            -> STALE_REEXTRACTION_REQUIRED
```

A stale result produces a deterministic re-extraction proposal containing only:

- prior handoff hash;
- affected logical component IDs;
- prior source ID/hash/revision;
- current source ID/hash/revision;
- reason codes.

It does **not**:

- overwrite existing candidate geometry;
- remap candidate handles;
- promote a new source revision;
- mark a component current;
- issue approval.

The engineer/future R3/R4 workflow may retain the frozen copy or request a new extraction revision. R2 only exposes the mismatch and proposed re-extraction scope.

## 11. R3 boundary

R3 Component/View Registry starts where R2 stops.

R2 may emit:

- logical component ID;
- source handle/layer/block;
- candidate handle;
- source hash/revision;
- local transform;
- provenance class;
- deterministic handoff hash.

R2 may not persist or own:

- component revision;
- component current/accepted state;
- view IDs as registry truth;
- entity-to-view/layout ownership;
- dimension registrations;
- conflict resolution state;
- revision lineage;
- current candidate pointer.

R3 must consume the R2 handoff explicitly and create its own separately authorized registry behavior. R2 cannot preempt R3 by adding a hidden in-memory/disk registry.

## 12. Manifest/checkpoint/resume decision

The existing `cad_agent` manifest/checkpoint lifecycle remains the sole run persistence authority.

The initial R2 runtime sequence does **not** add a new manifest field or stage because doing so before R3/R4 defines component/revision persistence would prematurely create “current base reuse” semantics.

R2 records are deterministic and revalidatable from existing authoritative hashes. A later bounded task may add only a small closed hash reference through `cad_agent.manifest` if R3/R4 proves it necessary. That task must preserve legacy readers and may never copy full R2 component arrays into the run manifest.

This is a deliberate reuse decision, not an omission.

## 13. Privacy and synthetic test policy

First R2 runtime tests use synthetic mappings and mocked/fake S3B call boundaries only.

Tests and ordinary errors must not include:

- private/customer CAD bytes;
- absolute customer paths;
- raw Windows file/volume IDs;
- AutoCAD handles beyond synthetic fixture values already present in public test contracts;
- source content;
- approval secrets/credentials;
- raw S3B exception text when it may expose local path details.

No live AutoCAD operation belongs in hosted R2 unit tests.

## 14. Dependency gates before R2 runtime issuance

All are mandatory:

### Gate A — final R1 acceptance

- complete R1 runtime accepted and merged;
- final current-main SHA supplied;
- final `source_fusion` API delta checked against Section 5;
- final fusion packet supports fail-closed reusable/blocked state and exact source/custody matching;
- no active R1 writer remains on R2 candidate paths.

Failure result: `R2 REBASELINE REQUIRED`.

### Gate B — S3B implementation identity

- accepted S3B `exact_base_xref.py`, `DotNetIPCClient.exact_base_xref_*`, IPC contracts, .NET policy/reader/dispatcher still exist with the invariants listed above;
- no accepted post-S3B change weakens fresh-preflight, approval equality, path policy, or candidate-only mutation.

Failure result: `R2 REBASELINE REQUIRED`.

### Gate C — S3B live acceptance

- operator-controlled S3B live inspection **PASS**;
- operator-controlled S3B live extraction **PASS** on approved disposable fixture;
- source/accepted immutability **PASS**;
- cleanup/restoration **PASS**;
- `SKIP` or `NOT RUN` is insufficient.

Failure result: R2 runtime remains `BLOCKED`; no code scope is widened to compensate.

### Gate D — one-writer overlap

- no active writer owns `cad_agent/base_cad_adapter.py` or `tests/test_cad_agent_base_cad_adapter.py`;
- Wave 1A, final R1, and Luna local paths are disjoint from the first R2 runtime write-set.

## 15. Migration and rollback

Migration: none for the first R2 runtime sequence. R1A/R1B/R1C, S3A, S3B, manifests, IPC schemas, CAD files, and R3/R4 stores are unchanged.

Rollback: revert/remove the R2 adapter and its focused tests. Existing S3A/S3B and R1 behavior remains authoritative. Any disposable candidate created during a separately authorized live run is cleaned through existing S3B/local-operator policy; source and accepted CAD require no rollback because R2 must never mutate them.

## 16. Acceptance invariants for the future R2 implementation

The runtime is acceptable only if all of these remain true:

- one adjacent R2 adapter owner;
- no changes to `cad_agent/source_fusion.py` for R2 convenience;
- no changes to `mcp_integration_lib/**` or `autocad_plugin/**` unless a new Master-PO amendment proves an accepted-owner gap;
- no CAD parser or DXF writer in R2;
- no global deformation;
- no approval issuer;
- no component/view registry or revision store;
- no visual/engineering PASS or publication authority;
- source/accepted CAD immutable;
- only disposable candidate mutation delegated to S3B;
- every reused component remains frozen to exact source hash/revision and original source metadata;
- stale source never silently overwrites a frozen component;
- canonical identities use existing project hash ownership;
- synthetic hosted tests are sufficient for code acceptance, while live AutoCAD evidence remains a separately truthful gate.
