# R3 Component/View Registry Design

Status: planning-only executable design for Issue #128. No runtime authorization.

Planning date: 2026-08-08

Exact planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

Authoritative parent design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`

Reuse inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`

## 1. Decision summary

R3 adds one thin orchestration capability: a deterministic **Component/View Registry artifact** that links logical components and logical 2D views to already-authoritative source/projection/base-CAD evidence and to candidate-only CAD bindings.

The registry is **not** a CAD database, geometry model, semantic solver, revision store, approval store, manifest store, or AutoCAD controller. It does not own source bytes and does not infer geometry. It records relationships between facts whose truth remains owned elsewhere.

The governing rule is:

> R3 may bind and index accepted evidence; it may not become the authority that created that evidence.

The registry has two distinct identity layers:

1. **logical identity** — stable component/view/link identity that excludes volatile CAD handles, timestamps, paths, caller order, UUIDs, and candidate-revision accidents;
2. **snapshot binding identity** — a deterministic checksum over the complete normalized registry snapshot, including candidate-only entity/block bindings, so a binding change is detectable without making the volatile handle the logical component identity.

R3 runtime remains blocked until R1 and R2 are accepted and Master PO performs a fresh post-R2 rebaseline.

## 2. Dependency status and non-invention rule

This design is written while upstream work is moving. The dependency contract is therefore semantic, not speculative.

| Dependency | State at planning base | R3 rule |
|---|---|---|
| R1 Source Bundle / Source Fusion | Active work continues after the accepted Task-4 `cad_agent.source_fusion` surface | R3 runtime must consume the **final accepted deterministic R1 projection/evidence boundary** after merge. Do not hard-code a moving R1 symbol from planning. |
| R2 Base CAD Adapter | Planning/runtime contract not yet accepted | R3 requires an accepted R2 record that proves candidate/base/source identity and reused-component provenance. The exact R2 API name and field shape are resolved only in the post-R2 rebaseline. |
| S3A exact-base Xref contracts | Accepted current owner exists in `mcp_integration_lib/exact_base_xref.py` | Reuse as existing evidence basis; do not clone inspection/extraction validation into R3. |
| S3B live exact-base execution | Existing File IPC/.NET authority | R3 never performs AutoCAD live work. It may consume accepted evidence handed through R2. |
| Primitive/Semantic IR | Existing owners in `primitive_ir_lib` and `semantic_ir_lib` | R3 references deterministic projection identity and semantic membership; it never copies or solves geometry. |
| Manifest/checkpoint/resume | Existing owner in `cad_agent.manifest` / current run orchestration | R3 does not create storage. Durable R3 references, when integrated, must extend this existing owner. |

### Mandatory post-R2 rebaseline

Before any R3 runtime Issue is issued, Master PO must record all of the following from accepted heads:

- exact final R1 projection validator/API symbol(s) and output identity fields;
- exact final R2 validator/API symbol(s), candidate identity evidence, and reused-component provenance fields;
- whether R2 already emits a stable logical component key or only source/extraction evidence;
- exact current manifest/checkpoint integration seam;
- exact current-main overlap against the proposed R3 runtime paths.

If any required fact is unavailable without inventing a new R1/R2 contract, stop with `R3 UPSTREAM CONTRACT GAP` rather than adding a second authority.

## 3. Existing ownership and reuse map

The current accepted architecture and reuse inventory remain authoritative.

| Capability | Current owner / concrete API | R3 classification | R3 behavior |
|---|---|---|---|
| Canonical JSON SHA-256 | `cad_agent.drawing_contracts.canonical_json_sha256()` | `REUSE_AS_IS` | Sole canonical registry hash owner. No direct alternate serializer/hash owner. |
| R1 locator/render provenance | `cad_agent.source_fusion.validate_page_locators()`, `validate_region_locators()`, `validate_render_provenance()` on planning base | `REUSE_AS_IS` pending final R1 rebaseline | R3 references final accepted deterministic evidence; no source parsing/rendering. |
| R1 source custody | `cad_agent.source_integrity` accepted custody/hash/numeric owners | `REUSE_AS_IS` | R3 cannot reopen, rehash, or recanonicalize source bytes independently. |
| Semantic parts/constraints | `semantic_ir_lib.models.SemanticIRDocument`, `SemanticPart`, `Constraint` and existing assembly/solver owners | `EXTEND_WITH_ADAPTER` | Registry records semantic/projection membership only; no second part/constraint geometry. |
| Exact-base inspection/extraction planning | `mcp_integration_lib.exact_base_xref.validate_xref_inspection()`, `validate_extraction_plan()`, `build_extraction_plan()` | `REUSE_AS_IS` behind accepted R2 | R3 does not duplicate eligibility, transform, or extraction validation. |
| Native DXF/entity generation | `dxf_builder_lib.builder.build_dxf()` | `REUSE_AS_IS` | Registry may bind generated candidate entities but never generates them. |
| AutoCAD transport/dispatcher | `mcp_integration_lib` + `autocad_plugin` | `REJECT_DUPLICATE_OWNER` | No AutoCAD calls from R3. |
| Run manifest/checkpoint/resume | `cad_agent.manifest` and existing run/PDF orchestration | `EXTEND_WITH_ADAPTER` only in a separately bounded integration task | Registry artifact reference may be bound there; no registry database/file-store owner. |
| Approval/apply | existing `agent_lib` proposal/apply and accepted approval gates | `REJECT_DUPLICATE_OWNER` | R3 carries no authority to approve or apply changes. |
| Candidate revision truth | future R4 Candidate Revision Orchestrator | `REJECT_DUPLICATE_OWNER` | R3 does not mint or promote revisions. |
| Visual verdict/publication | future R5/R7 owners | `REJECT_DUPLICATE_OWNER` | R3 emits no PASS/verdict/publish state. |
| Linked component/view graph | no complete accepted owner | `NEW_MISSING_CAPABILITY` | This is the narrow capability R3 owns. |

The current exact-base contract already contains `logical_component_id`, source handle/layer/block facts, bounded local transform policy, and `impacted_views`. R3 must reuse those facts through R2 rather than defining another extraction contract.

## 4. R3 responsibility boundary

R3 owns only these responsibilities:

1. normalize already-validated upstream references into one closed registry artifact;
2. derive stable logical component IDs independent of volatile CAD entity handles and legacy UUIDs;
3. derive stable logical view IDs and closed relationships between views/components;
4. record source/projection/base-CAD provenance references without copying source truth;
5. classify component reconstruction origin at the orchestration level;
6. bind candidate-only CAD entity/block references as non-authoritative snapshot evidence;
7. compute deterministic logical IDs and a deterministic registry snapshot SHA using the existing canonical hash owner;
8. project deterministic impact closure for linked components/views without applying changes.

R3 does **not** own:

- image/PDF parsing, OCR, Primitive extraction, Semantic assembly, constraint solving, or geometry inference;
- exact-base eligibility or extraction execution;
- DXF/entity generation;
- AutoCAD transport, dispatcher, open/save, render, repair, or mutation;
- source/base/accepted CAD mutation;
- candidate creation or revision numbering;
- approval, rejection, conflict resolution, promotion, rollback, visual verdict, or publication;
- a registry database, CAS, manifest, checkpoint, or revision history store.

## 5. Registry artifact model

The runtime artifact is a closed JSON-compatible mapping. Planning fixes the semantic model while allowing upstream field names to be resolved during the mandatory rebaseline.

### 5.1 Root record

The root concept contains:

```text
schema_version
upstream_bindings
components
views
links
registry_snapshot_sha256
```

`upstream_bindings` contains only validated identity references required to prove which accepted R1/R2/Semantic/candidate evidence the snapshot used. It must not contain absolute paths, raw source bytes, prompts, private content, or approval state.

`registry_snapshot_sha256` is generated through `canonical_json_sha256()` over the normalized root minus the checksum field itself.

### 5.2 Logical component record

A component record contains the concepts:

```text
component_id
component_type
origin_class
source_projection_refs
semantic_projection_refs
base_cad_provenance_ref     # optional
view_ids
candidate_entity_bindings
```

`component_id` is a logical deterministic identity. It must exclude:

- target/source CAD handles;
- block-reference handles;
- timestamps;
- UUIDs or SemanticPart legacy IDs;
- absolute or relative filenames/paths;
- list/filesystem order;
- run-local request IDs unless an accepted upstream identity contract explicitly makes one semantic;
- approval/reviewer status;
- revision number minted by future R4.

The ID is derived from stable accepted evidence such as deterministic source/projection identity, normalized semantic membership, component type, and exact-base source identity when applicable. The exact upstream fields are resolved from accepted R1/R2 during rebaseline; R3 must not synthesize replacements.

### 5.3 Candidate entity bindings

Candidate CAD bindings are evidence records, not component identity. They may record the accepted candidate drawing identity plus candidate-only native entity/block references needed to locate the logical component.

Rules:

- every binding must point to the current **candidate** identity supplied by accepted upstream authority;
- a source/base/accepted/current production drawing may never be a mutable target binding;
- source handles from exact-base provenance remain source evidence and must never be confused with target candidate handles;
- changing a candidate handle may change `registry_snapshot_sha256` but must not silently change the logical `component_id`;
- duplicate target-handle ownership across incompatible logical components fails closed unless the accepted CAD owner explicitly proves a shared immutable reference construct.

### 5.4 Logical view record

A view record contains the concepts:

```text
view_id
view_role
component_ids
source_projection_refs
semantic_projection_refs
candidate_entity_bindings
layout_bindings
```

`view_id` is deterministic and excludes display names, filenames, timestamps, UUIDs, and target handles. It is based on accepted stable projection/region evidence plus its logical role and component membership.

R3 is 2D and not 3D-first. It does not infer a geometric projection transform unless that transform is already authoritative upstream.

### 5.5 Link record

Links make relationships explicit rather than implied by naming or CAD layer conventions.

Closed initial relationship classes:

```text
COMPONENT_HAS_VIEW
VIEWS_SHARE_COMPONENT
VIEWS_SHARE_PARAMETER_EVIDENCE
VIEW_PRESENTED_ON_LAYOUT
```

The registry may later version this closed set through a separately reviewed R3 change. Runtime must reject unknown relation types; it must not accept caller-created relationship semantics silently.

Links are directional records with deterministic IDs derived from relation type plus stable endpoint IDs and accepted evidence reference identity.

## 6. Component origin classification

R3 adds an orchestration classification, not a new provenance truth system.

Closed initial classes:

```text
REUSED_UNCHANGED
RECONSTRUCTED_CHANGED
RECONSTRUCTED_NEW
MIXED_UNRESOLVED
```

Rules:

### `REUSED_UNCHANGED`

Allowed only when accepted R2/exact-base evidence proves the component was selected from an eligible exact base and its reused geometry is bound to the frozen source SHA/revision/local transform. R3 does not decide eligibility itself.

### `RECONSTRUCTED_CHANGED`

Used when accepted evidence identifies a corresponding original/base component but the target geometry is intentionally reconstructed rather than reused unchanged. The original/base link is provenance/context only.

### `RECONSTRUCTED_NEW`

Used when accepted source/projection/Semantic evidence supports a target component with no claimed reusable original component.

### `MIXED_UNRESOLVED`

Used when evidence spans reused and reconstructed material or origin cannot be proven without an external decision. This class blocks any downstream assumption that the component is wholly unchanged. R3 does not resolve the conflict or issue approval.

These classes coexist with accepted provenance classes such as `REUSED_FROM_BASE_CAD`, `OBSERVED`, `DERIVED`, and `AI_INFERRED`; R3 must not rewrite upstream provenance.

## 7. Exact-base integration seam

The accepted current exact-base Xref owner already validates:

- exact source ID/SHA/revision;
- logical component ID;
- source handle/layer/block;
- read-only Xref eligibility;
- local translation/rotation/positive-uniform-scale policy;
- extraction-plan component membership and impacted views.

R2 is expected to be the Base CAD Adapter around accepted S3/R1 owners, but its API is moving while this plan is written. Therefore R3 records only the facts it needs semantically:

```text
accepted R2 evidence identity
candidate drawing identity
base source identity (source ID + SHA + revision)
reused component membership
source handle/layer/block provenance
applied local transform provenance
stale/source-revision state
```

R3 does not prescribe the R2 field names or validator symbol.

At R3 issuance, the rebaseline must map each required fact to the exact accepted R2 symbol/field. If R2 does not expose one of these facts, R3 stops; it does not import AutoCAD transport or reimplement extraction to obtain it.

Stale base/Xref behavior is fail-closed: a registry cannot treat a stale/revision-mismatched reuse record as `REUSED_UNCHANGED`. R3 may surface a categorical stale-binding error but cannot re-extract or overwrite anything.

## 8. Primitive/Semantic compatibility

R3 preserves the existing engine:

```text
primitive_ir_lib -> semantic_ir_lib -> dxf_builder_lib
```

The existing Semantic model deliberately references Primitive IDs instead of copying geometry. R3 must preserve this same principle at the orchestration level.

Required compatibility rules:

- never copy Primitive geometry into a registry-owned geometry model;
- never run Semantic assembly/pruning/solving in R3;
- never make legacy/random Primitive or Semantic UUIDs logical component identity;
- consume the final accepted R1 deterministic Primitive/Semantic projection identity after R1 merges;
- preserve multiplicity/ambiguity semantics established by accepted R1 projections;
- if a Semantic reference cannot be mapped unambiguously to accepted deterministic Primitive evidence, fail closed rather than selecting a legacy UUID.

## 9. Determinism and checksum rules

R3 uses `cad_agent.drawing_contracts.canonical_json_sha256()` as the sole canonical JSON SHA-256 owner.

### Logical IDs must be stable across

- caller/list permutation;
- regenerated legacy UUIDs;
- changed/removed volatile CAD handles where logical evidence is unchanged;
- changed timestamps;
- filename/path changes that do not alter accepted source identity;
- equivalent normalized upstream evidence already canonicalized by the accepted owner.

### Logical IDs must change when

- stable source/projection evidence changes;
- component type/origin changes;
- stable semantic membership changes;
- exact-base source SHA/revision changes for a reused component;
- a view's logical role or stable component membership changes.

### Snapshot SHA must change when

- any logical component/view/link changes;
- candidate entity/block binding changes;
- candidate identity changes;
- accepted upstream evidence binding changes.

R3 must not introduce a second numeric canonicalization policy. Any numeric evidence used in identity must already be normalized by the accepted upstream owner.

## 10. Linked-view synchronization boundary

R3 owns the **graph and impact projection**, not synchronization mutation.

Given an accepted registry and a set of changed logical component/view IDs, R3 may deterministically return:

```text
impacted component IDs
impacted view IDs
impacted layout bindings
relationship IDs explaining the closure
```

It may not:

- choose new geometry;
- edit another view;
- decide a source view;
- apply a shared parameter;
- create a candidate revision;
- approve a HIGH-impact change.

Those decisions belong to later proposal/revision orchestration. R3 supplies the explicit graph needed so later R4 cannot silently miss linked views.

## 11. Immutable source/base and candidate-only boundary

R3 is pure orchestration over supplied validated records.

Forbidden runtime operations inside R3 include:

- `open()` / `Path.read_*()` / source-byte hashing for CAD/source evidence;
- pypdf/Pillow/OCR/model/provider execution;
- `ezdxf` or other geometry parsing for registry truth;
- File IPC/.NET IPC/AutoCAD calls;
- subprocess/network access;
- source/base/accepted CAD writes;
- candidate CAD writes.

The registry may reference a candidate identity and candidate handles supplied by accepted owners, but it never mutates the candidate itself.

## 12. Persistence, manifest, and resume

The Component/View Registry must not create a registry database or second checkpoint store.

Initial R3 core runtime returns a deterministic in-memory/JSON-compatible artifact. A later bounded R3 integration task may bind an artifact filename/SHA/reference through the **existing** `cad_agent.manifest`/checkpoint lifecycle if the post-R2 rebaseline proves the existing owner can be extended compatibly.

That integration must preserve:

- existing run/resume and run-pdf/resume-pdf compatibility;
- atomic writes owned by existing manifest helpers;
- existing artifact SHA verification;
- safe legacy defaults;
- no revision-history semantics inside the registry reference.

If durable binding requires a new database, CAS, schema authority, or revision store, stop with `R3 PERSISTENCE OWNER GAP`.

## 13. Proposed R3 public surface

The R3-owned names are stable planning proposals. Upstream R1/R2 validator symbols called inside them are resolved only at the mandatory post-R2 rebaseline.

```text
COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION = "component-view-registry-1.0"
ComponentViewRegistryError
build_component_view_registry(...)
validate_component_view_registry(...)
component_view_registry_sha256(...)
project_linked_view_impacts(...)
```

### `build_component_view_registry(...)`

Consumes already-validated/validatable accepted R1 projection evidence, Semantic projection membership, optional accepted R2 base-CAD evidence, and candidate binding evidence. Produces a normalized registry; performs no I/O or mutation.

### `validate_component_view_registry(...)`

Fail-closed closed-record validation plus exact cross-binding against the accepted upstream context supplied by the caller. Caller-supplied hashes never mint upstream authority.

### `component_view_registry_sha256(...)`

Validates the registry then delegates canonical hashing to `canonical_json_sha256()`.

### `project_linked_view_impacts(...)`

Pure deterministic graph traversal over validated registry IDs. Produces impact evidence only.

No fifth public API is added in the first R3 runtime slice without Master PO amendment.

## 14. Failure model

Public failures are categorical and privacy-safe through `ComponentViewRegistryError`.

Required categories include concepts equivalent to:

```text
UPSTREAM_CONTEXT_INVALID
UPSTREAM_CONTEXT_MISMATCH
R2_BINDING_REQUIRED
STALE_BASE_BINDING
COMPONENT_ID_MISMATCH
COMPONENT_MEMBERSHIP_AMBIGUOUS
COMPONENT_ORIGIN_INVALID
VIEW_ID_MISMATCH
VIEW_MEMBERSHIP_INVALID
LINK_INVALID
CANDIDATE_BINDING_MISMATCH
SOURCE_OR_ACCEPTED_BINDING_FORBIDDEN
DUPLICATE_ENTITY_BINDING
REGISTRY_SNAPSHOT_SHA_MISMATCH
```

Exact string constants may be locked by the runtime Issue. Error text must not expose customer/source content, private paths, raw parser/AutoCAD exceptions, prompts, credentials, or source bytes.

## 15. Proposed runtime file ownership

Preferred R3 core ownership after the post-R2 rebaseline:

```text
CREATE cad_agent/component_view_registry.py
CREATE tests/test_cad_agent_component_view_registry.py
```

No schema file is required for the first slice; the module follows the existing strict pure-Python closed-validation pattern and avoids a third owner/path.

A separately issued persistence integration task may modify the existing manifest owner and its existing tests only if the fresh rebaseline proves this is necessary and non-overlapping. That later task must not create a new registry store.

## 16. Security and authority invariants

R3 must prove statically and dynamically that it does not import or own:

- OCR/image/PDF parsers;
- model/provider/network clients;
- AutoCAD/File IPC/.NET IPC transport;
- `ezdxf`/DXF writer logic;
- persistence/database/CAS packages;
- approval/verdict/publication logic;
- ambient clock/randomness for identity.

The registry must remain deterministic with synthetic records and accepted owner validators only.

## 17. Migration and rollback

R3 is additive.

Migration path:

1. keep existing Primitive/Semantic/DXF/AutoCAD/manifests unchanged;
2. add registry generation as an orchestration artifact after accepted R1/R2 evidence exists;
3. optionally bind its artifact reference through the existing manifest owner in a separately reviewed task;
4. later R4 consumes the registry read-only when building candidate revision proposals.

Rollback path:

- remove/disable the R3 adapter and registry artifact reference;
- existing Primitive/Semantic/DXF/AutoCAD flows remain authoritative and operational;
- no source/base/accepted CAD migration is required;
- no database/schema data migration exists.

## 18. Runtime issuance gates

Master PO may issue R3 runtime only after all are true:

1. final R1 deterministic projection work is accepted and merged;
2. R2 Base CAD Adapter is accepted and merged or explicitly accepted as sufficient for R3's required facts;
3. a fresh current-main rebaseline maps the semantic R1/R2 requirements in this design to exact accepted APIs;
4. exact proposed runtime write-set has no active writer overlap;
5. existing canonical hash/numeric/manifest owners remain sufficient;
6. synthetic RED can prove the missing registry behavior without AutoCAD/private data.

## 19. STOP conditions

Stop and return to Master PO if implementation would require any of the following:

- inventing or changing an unsettled R2 API merely to satisfy R3;
- a second Primitive/Semantic parser, solver, or geometry model;
- a second canonical serializer/hash/numeric owner;
- a second DXF/entity builder;
- AutoCAD/File IPC/.NET IPC calls from the registry module;
- a new manifest/checkpoint/revision/database/CAS truth store;
- source/base/accepted CAD mutation;
- approval, visual verdict, repair, promotion, rollback, or publication authority;
- private/customer CAD or live AutoCAD to prove core behavior;
- a third core R3 path before an explicit write-set amendment;
- inability to map final accepted R1/R2 evidence to stable logical component/view identity without legacy UUID or path authority.

## 20. Planning acceptance

This design is ready for runtime planning when it satisfies all of the following:

- R3 is a thin deterministic orchestration registry, not a second CAD/semantic/store owner;
- component logical identity is explicitly separated from volatile CAD/entity handles;
- linked-view relationships are explicit and deterministic;
- unchanged/reused vs changed/new classification is bounded by accepted evidence;
- exact-base integration reuses S3/R2 rather than duplicating extraction;
- Primitive/Semantic geometry ownership remains unchanged;
- source/base/accepted CAD is immutable and R3 performs no mutation;
- R3 has no revision/approval/verdict/publication authority;
- moving R1/R2 contracts are explicit rebaseline dependencies rather than invented APIs;
- the runtime plan can be issued task-by-task after the post-R2 gate.
