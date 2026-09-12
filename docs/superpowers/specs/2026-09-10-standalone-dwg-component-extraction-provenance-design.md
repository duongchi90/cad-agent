# Proposed design: standalone-DWG component extraction with provenance

Status: proposed design for PO/architecture review; implementation is not authorized.

Date: 2026-09-10

Approval date: pending

Base: `codex/audit-text-style-compat-20260910` at `d79a9948aa5374daa47091d2c04edddb41dd61bd`

Supported scope: Windows, Python 3.11, AutoCAD Mechanical 2027, the existing
Python/File IPC/.NET boundary, and disposable candidate artifacts only.

Private source drawings, customer annotations, generated DXF files, and live
AutoCAD state remain workstation-only. This document records a proposed
contract and ownership boundary; it does not add a schema, transport, command,
CAD operation, or production authority.

## 1. Problem and decision

The page-1 reuse plan needs to reuse selected geometry from the standalone
`BVTL.dwg` page-2/base drawing. The established exact-base-Xref owner cannot be
used because the observed source has `XREF=0`. The native-DWG owner currently
seals whole-drawing custody/readback and intentionally exposes no component
lineage. The drawing-query owner only reads already-bound candidate handles.

The missing capability is therefore a narrow adapter for:

`STANDALONE_DWG_COMPONENT_EXTRACTION_WITH_PROVENANCE`

The adapter must reuse existing drawing custody/currentness, component/view
lineage, candidate-revision, provenance, and File IPC owners. It must never
reinterpret a standalone DWG as an Xref or weaken the exact-base-Xref
contract.

## 2. Goals

- Read a hash-bound standalone DWG without saving or changing its source state.
- Select only explicitly identified source entities/groups; never infer or
  estimate a handle from proximity, OCR, or a visual guess.
- Produce a disposable candidate by copying only the approved selection into a
  destination that cannot alias the source.
- Preserve source hash, source path identity, DBMOD, read-only state, selected
  handles, local transforms, candidate mappings, and failure/rollback evidence.
- Bind the result to existing DARA currentness, R3 component/view lineage, and
  R4 candidate revision/state owners.
- Keep page-1-only reconstruction separate from page-2 geometry reuse.

## 3. Non-goals

- No production DXF/DWG mutation, accepted-drawing mutation, source save, or
  publication/promotion.
- No second CAD transport, provider, database, geometry engine, parser, OCR
  path, or visual authority.
- No whole-drawing enumeration as a substitute for selected component identity.
- No global scale/warp or transformation of a similar drawing.
- No automatic inference of component membership, handles, dimensions, or
  page-1 deltas.
- No reuse of the exact-base-Xref inspection/extraction contract for a
  standalone source.

## 4. Proposed ownership boundary

### 4.1 Python orchestration adapter

Add a future thin `cad_agent` adapter only after this design is approved. It
would validate closed request/inspection/plan/result packets, snapshot the
source and candidate identities, call the existing File IPC client, and route
the evidence through existing DARA/R3/R4 owners.

It must not clone entities, parse DWG internals, or implement a second
candidate writer. The adapter may be named during implementation; this design
does not reserve a public module name.

### 4.2 Existing owners to reuse

- `cad_agent.native_dwg_provenance`: reference/regression owner for
  full-drawing native-DWG custody, currentness, and readback identity. The
  standalone component path must not call its full-drawing builders or its
  intentionally empty R3-input builder.
- `cad_agent.drawing_artifact_reference`: source baseline artifact reference and
  current observation before R3, followed by the disposable-candidate
  `R3_CANDIDATE` reference/current observation only after the standalone R3
  binding exists.
- `cad_agent.component_view_registry`: component/view lineage and impact
  binding; the implementation must preserve native full-drawing restrictions
  and add the required versioned standalone-component mode described below.
- `cad_agent.candidate_revision`: candidate revision/state and current-pointer
  binding; its registry normalization must add an explicit recognition/binding
  branch for the versioned standalone-component mode rather than falling
  through to the base-CAD handoff path.
- `cad_agent.drawing_query`: read-only inspection of the resulting bound
  candidate, not source extraction.
- Existing `mcp_integration_lib.dotnet_ipc` and the AutoCAD .NET dispatcher:
  the only live transport boundary.

### 4.2.1 Required R3/R4 standalone-lineage extension

Fresh source inspection shows that the current R3/R4 owners cannot carry this
capability as an adapter-only change: the component/view registry rejects
non-empty native-DWG component selections, while candidate-revision
normalization recognizes only the existing generated/native-DWG modes and
otherwise falls through to base-CAD handoff. The implementation plan must
therefore include one bounded, versioned R3/R4 extension as a single change:

- R3 adds `component-view-registry-standalone-dwg-1.0` with provenance mode
  `STANDALONE_DWG_COMPONENTS` and only the minimum exact source/candidate
  path/hash, selected-group, handle-binding, and provenance-checksum fields.
- R4 adds an explicit recognition/binding branch for that exact R3 schema and
  mode. It must bind the same source identity, candidate identity, selected
  handles, and registry checksum into the candidate revision; it must not
  broaden the generic base-CAD fallback or accept an unknown registry mode.
- Standalone currentness/provenance is staged. Before R3 exists, the detached
  context may contain the DARA source `BASELINE` reference/current observation,
  raw hash-bound candidate output identity, and the standalone
  inspection/extraction result checksum. It must not issue or normalize a
  candidate `R3_CANDIDATE` DARA reference because that reference requires the
  exact `r3_provenance_binding`. After the standalone R3 registry/provenance
  evidence exists, issue and observe that candidate `R3_CANDIDATE` reference
  with the exact binding, then feed it into R4 and `drawing_query`. None of
  these standalone steps use the full-drawing native-DWG provenance packet.
- The extension is tested RED-first at both owners, including the current
  rejection codes, then GREEN with adversarial cross-lineage, stale-hash,
  duplicate-handle, mislabeled-full-drawing, and `REUSED_FROM_BASE_CAD`
  cases.

`NATIVE_DWG_FULL_DRAWING`, generated mode, base-CAD handoff, and all existing
exact-base-Xref behavior remain unchanged in intent and acceptance rules.

### 4.3 New AutoCAD-side capability to design, not implement here

The existing .NET drawing owner would gain one closed, read-only-source /
disposable-output operation family. The exact operation name is intentionally
deferred until the implementation plan. It must use the existing dispatcher,
request files, result files, leases, path normalization, and reparse-point
guards.

The source reader may open a standalone DWG read-only, inspect only the
requested handles/groups, and clone only approved source objects into a new
candidate database. It must not call the exact-base-Xref reader or require an
Xref record.

## 5. Closed data contracts (proposed)

The following shapes are design-level contracts. They are not active public
schemas until an approved implementation plan, failing tests, and independent
reviews exist.

### 5.1 Read-only source inspection request

Required closed fields:

```text
schema_version
request_id
run_id
source_drawing_path
source_drawing_sha256
source_setup_audit_sha256
selection_groups
expected_dbmod
approval
```

`approval` is null for inspection. `selection_groups` is a non-empty list of
closed records:

```text
group_id
logical_component_id
source_handles
expected_entity_types
source_layer_expectations
```

Handles are normalized hexadecimal identifiers and must be unique across the
request. Every handle must be supplied by an existing hash-bound observation
or explicit engineer evidence. The operation must reject guessed handles,
duplicate membership, an empty group, an unexpected entity type/layer, and a
source path that aliases a candidate destination.

### 5.2 Inspection result

Required closed fields:

```text
schema_version
inspection_id
request_id
source_identity
source_sha256_before
source_sha256_after
dbmod_before
dbmod_after
read_only
groups
warnings
conflicts
changed
eligible
inspection_sha256
```

Each group records the exact source handles, entity types/layers, geometric
extents/signature needed for identity, and the source revision/hash. Eligibility
requires: source hash unchanged, `dbmod_before == dbmod_after`, `read_only=true`,
`changed=false`, no conflicts, and all requested identities matching.

### 5.3 Candidate-base model (closed)

This capability always starts from an empty new disposable database. It does
not consume, copy, or merge into an existing candidate artifact. Therefore
there is no candidate input path, identity, or hash, and neither the plan nor
the result contains `candidate_input_sha256`. The only candidate artifact is
the newly created `candidate_output_path` under the allowed disposable root.

This choice is deliberate: it closes alias protection, provenance, rollback,
and deterministic-output semantics without inventing a candidate base. Any
future operation that starts from an existing disposable candidate is a
different capability and requires a separate approved design.

### 5.4 Proposed/approved extraction plan

The plan must bind exactly to one eligible inspection and contain:

```text
plan_id
request_id
run_id
inspection_id
inspection_sha256
source_drawing_sha256
candidate_output_path
candidate_base_model
components
transform_policy
approval
```

`candidate_base_model` is the literal value `EMPTY_NEW_DATABASE`. The output
path must be absent during planning and must not resolve to the source or any
prior candidate. No candidate input artifact is read or hashed.

`components` contains only inspection-backed groups. Each transform is local
translation/rotation/positive uniform scale, reusing the existing closed
transform policy; reflection and global deformation are rejected. The plan is
`PROPOSED` until a separate approval reference is supplied. The builder must
never fabricate approval.

### 5.5 Extraction result and provenance handoff

The disposable result must record:

```text
schema_version
request_id
run_id
source_drawing_sha256
candidate_base_model
candidate_output_sha256
candidate_output_identity
source_mutated
source_dbmod_before
source_dbmod_after
save_performed
components
source_handle_to_candidate_handle
result_sha256
```

Every component mapping must be one-to-one and reference an approved source
group. The provenance record must identify the standalone source explicitly;
it must not claim `REUSED_FROM_BASE_CAD` or an Xref inspection. Before R3
exists, the handoff contains the source `BASELINE` DARA currentness, raw
candidate output identity/hash, and the standalone inspection/extraction
result checksum. After the exact standalone R3 registry and
`r3_provenance_binding` exist, the adapter issues and observes the candidate
`R3_CANDIDATE` DARA reference with that binding. Only that staged candidate
reference is then adapted into the existing candidate-revision and
`drawing_query` evidence, with the source hash and extraction evidence as the
immutable provenance reference.

`save_performed` has one closed meaning: it is `true` only after the newly
created disposable database has been serialized to `candidate_output_path`,
the write has completed, and the output can be re-opened/read back for the
hash-bound result. It does not mean that the source document or any other
AutoCAD document was saved. A successful extraction result must have
`save_performed=true`; a false value is never a usable candidate result.

## 6. Execution and safety invariants

### 6.1 Source safety

- Source file must be an existing regular non-reparse `.dwg`.
- Source path and source hash must match the sealed native-DWG custody record.
- Source document is opened read-only; no source save, close-with-save, or
  source-side transaction write is permitted.
- Source hash and DBMOD are checked before and after inspection/extraction.
- Any drift, write attempt, unexpected document, or missing handle is a
  categorical failure.

### 6.2 Disposable destination safety

- Candidate output must be an absent path in an allowed disposable root.
- Candidate creation starts from `EMPTY_NEW_DATABASE`; no candidate input
  artifact is opened, copied, hashed, or used as a provenance ancestor.
- Source and candidate must resolve to different identities and hashes.
- Serialization of the new candidate database to `candidate_output_path` is
  the sole permitted file write and the sole permitted document mutation in
  this capability.
- The result must be re-openable/readable and hash-bound before any later
  candidate review.
- Source saves, saves of any other document, production promotion,
  accepted-DXF mutation, and any AutoCAD session-state save are outside this
  operation and are forbidden.

### 6.3 Failure and rollback

- Preflight failures create no candidate output.
- A non-absent output path or any request to provide a candidate input artifact
  is rejected before destination creation.
- Any write target other than the exact planned `candidate_output_path`, or
  any result that claims `save_performed=false`, is rejected fail-closed.
- If candidate creation fails after a file is created, cleanup may delete only
  the exact output whose captured identity still matches the operation's
  creation identity.
- Cleanup failure is recorded as a material failure; source state remains
  untouched.
- No rollback may delete or restore a source/customer/accepted drawing.
- A partial mapping, stale source, changed DBMOD, or result-hash mismatch is
  never converted into a usable candidate.

## 7. Lineage and page-1 boundary

The plan must classify every selected group as `PAGE2_REUSED` or
`PAGE1_DELTA`. Only `PAGE2_REUSED` groups may enter this capability. Text,
dimensions, title-block content, changed cargo/rail/door geometry, and any
unresolved visual discrepancy remain in the existing page-1 fidelity/review
path. The extraction result cannot authorize those deltas.

The component/view registry must link reused groups to their exact source
handles and candidate handles. Standalone component lineage uses the required
versioned R3 mode and its explicit R4 recognition/binding extension described
in section 4.2.1. It must not be mislabeled as native full-drawing, routed
through base-CAD fallback, or accepted by bypassing validation.

## 8. Verification plan (future implementation only)

Before implementation is accepted, add failing tests first and reuse the
existing test owners:

1. Closed contract tests: unknown/missing fields, duplicate handles/groups,
   guessed/unbound handles, Xref-only fields, stale hashes, invalid transform,
   and fabricated approval all fail closed.
2. Standalone fixture tests: a temporary synthetic `.dwg`-named source with
   `XREF=0` is inspectable; the exact-base-Xref contract remains unchanged and
   rejects it for S3A.
3. Source invariants: read-only mode, source hash, DBMOD, path identity, and
   no source save are verified before/after both inspection and extraction;
   pre-R3 currentness uses the DARA source `BASELINE` reference/current
   observation plus the standalone result checksum, while the candidate
   `R3_CANDIDATE` reference/current observation is issued only after the exact
   R3 binding exists. No full-drawing native-DWG builder is used.
4. Candidate invariants: absent destination, non-aliasing path, candidate-only
   serialization, `save_performed=true` on success, re-openable output, exact
   source-to-candidate handle mapping, deterministic result hash, and
   identity-checked cleanup on failure. Attempts to write the source or any
   other document fail closed.
5. Reuse integration: DARA currentness, the required versioned standalone R3
   component/view provenance, explicit R4 candidate-revision recognition and
   binding, and drawing-query readback all bind to the same source and
   candidate identities; no native full-drawing restriction is weakened.
6. IPC/.NET contract tests: operation allowlisting, closed payloads, lease and
   path guards, no second transport, and no production/accepted target.
7. Live tests: run only with the approved AutoCAD Mechanical 2027/File IPC
   prerequisites. Missing private/live prerequisites are `SKIP` or `NOT RUN`,
   never pass.

The authoritative `scripts/verify.ps1` and `git diff --check` are required
before any implementation claim. This design itself has no runtime test or
live CAD evidence to report.

## 9. Approval gates and next record

This proposal does not authorize implementation. The next lifecycle step is a
bounded PO/architecture decision on whether to create the standalone owner.
If approved, a separate implementation plan must record the approved issue,
base SHA, exact files, failing tests, reviewer allocation, private/live gates,
and the disposable-only mutation boundary. Production use still requires the
existing human approval and independent visual/dimension/mechanical gates.
