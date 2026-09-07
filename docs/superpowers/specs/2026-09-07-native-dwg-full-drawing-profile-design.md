# Native DWG Full-Drawing Profile Design

## Status

Proposed after the Human Owner confirmed the full-drawing BVTL candidate
direction on 2026-09-07. This document does not authorize production CAD
mutation, visual approval, calibration, or publication. It is the design gate
for Issue #409 against base `1765ac150d5d59be022033aef9175aa86c9be458`.

## Measured gap

The real BVTL source is an immutable native `DWG`, and the disposable editable
candidate is a full-drawing AutoCAD export. Existing provenance owners can
truthfully represent either a generated mechanical pilot or a Base-CAD R2
reuse handoff. They cannot currently represent this full-drawing native-DWG
lineage without either mislabeling the candidate as generated or fabricating a
`REUSED_FROM_BASE_CAD` component handoff.

The existing live evidence proves only a bounded candidate readback and
deterministic entity signature. It does not yet prove the complete native-DWG
profile, source/candidate equivalence, persistence/reopen, profile
calibration, or visual/dimension verdicts. Those remain separate acceptance
gates.

## Goal

Add one closed, deterministic provenance mode for a full native-DWG source and
its editable full-drawing candidate, routing the resulting binding through the
existing DARA, R3, R4, drawing-query, AutoCAD readback, and review owners.

The mode must make the following claims and only these claims:

- source format is native `DWG` and source bytes are hash-bound;
- candidate scope is the complete drawing, with candidate bytes and
  AutoCAD-readback identity hash-bound;
- source/candidate equivalence is based on measured entity counts and the
  canonical entity signature, not on filename or visual similarity;
- no image/PDF calibration, OCR, generated-geometry, or provider evidence is
  implied;
- visual fidelity, dimension correctness, calibration approval, persistence,
  reopen, and publication remain independent gates.

## Design

### 1. Closed native-DWG provenance packet

Add `cad_agent.native_dwg_provenance` as a thin validator/sealer. It consumes
already-produced source/candidate files and read-only AutoCAD observations; it
does not open AutoCAD, write CAD, repair entities, or create a second store.

The packet is `native-dwg-full-drawing-provenance-1.0` and contains exactly:

- `profile_id = native-dwg-full-drawing`;
- `scope = FULL_DRAWING`;
- source path binding, source SHA-256, and `source_format = DWG`;
- candidate path binding, candidate SHA-256, and `candidate_format = DXF` for
  this lane;
- source and candidate entity counts;
- source and candidate canonical entity-signature SHA-256 values;
- the source and candidate readback observation SHA-256 values;
- setup/profile audit SHA-256 values for each side;
- `calibration_mode = NOT_APPLICABLE_NATIVE_CAD`;
- a deterministic candidate ID and packet SHA-256.

The validator re-snapshots every regular file at the sealing boundary and
refuses replacement, symlink/reparse-point input, path/hash drift, malformed
closed records, mismatched counts/signatures, unknown profile values, or
additional packet fields.

### 2. Explicit R3 native mode

Extend the existing R3 context discriminator with
`provenance_mode = NATIVE_DWG_FULL_DRAWING` and a new schema version rather
than overloading the generated-pilot or Base-CAD-reuse modes.

The native registry uses a dedicated `drawing_binding` at the drawing level;
it does not manufacture a component, primitive projection, semantic part, or
entity-handle list. The binding is anchored to the candidate artifact, exact
readback signature, and native-DWG packet hash. Its `components`, `views`, and
`links` collections are empty by contract. It carries no
`mechanical_pilot_provenance`, no `source_fusion`, no synthetic R2 reuse
handoff, and no `base_cad_provenance_ref`.

The native registry schema is
`component-view-registry-native-dwg-1.0`. Its closed `drawing_binding`
contains the candidate ID, source/candidate SHA-256 values, source/candidate
entity counts, the equal canonical entity-signature SHA-256, the native packet
SHA-256, and the DARA candidate-reference SHA-256. R3 provenance evidence
hashes this binding directly; it does not project the full drawing into
components.

The existing `component-view-registry-1.0` Base-CAD path and
`component-view-registry-1.1` generated path remain byte-for-byte compatible.
Generated and native contexts cannot be mixed with one another or with
Base-CAD context fields.

### 3. R4 root binding

R4 accepts a native R3 registry as a third closed upstream mode. It binds the
`ROOT_PRE_REPAIR` candidate revision directly to the native `drawing_binding`
and exact candidate artifact reference. `base_cad_handoff` is absent in this
mode; supplying one fails closed. The existing Base-CAD requirement remains
unchanged, and generated mode continues to forbid a Base-CAD handoff.

No native mode is eligible for repair, promotion, or publication merely because
the packet validates. Those actions still require the existing approval,
backup/rollback, live review, and independent verdict contracts.

### 4. Acceptance oracle and live boundary

The native packet is necessary but not sufficient for Phase 4 acceptance. The
acceptance oracle consumes these independent records:

1. source setup audit and candidate setup audit, each with exact profile and
   readback identity;
2. candidate persistence and reopen evidence from the existing AutoCAD owner;
3. deterministic source/candidate entity count and signature equality;
4. independent visual verdict;
5. dimension verdict;
6. calibration verdict, which is `NOT_APPLICABLE_NATIVE_CAD` for this profile;
7. unchanged source and candidate hashes after every read-only operation.

Missing live, visual, dimension, persistence, or reopen evidence is `NOT RUN`
or `SKIP`, never `PASS`. The current UltraViewer foreground contention remains
an operational blocker for the live setup audit and is not hidden by this
profile.

## Reuse declaration

| Capability | Existing owner | Decision |
| --- | --- | --- |
| File hashing, canonical JSON, regular-file and reparse checks | `drawing_contracts`, existing provenance helpers | `REUSE_AS_IS` |
| Drawing artifact references and currentness | `cad_agent.drawing_artifact_reference` | `REUSE_AS_IS` |
| R3 registry normalization and evidence | `cad_agent.component_view_registry` | `EXTEND_WITH_ADAPTER` |
| R4 candidate revision/state | `cad_agent.candidate_revision` | `EXTEND_WITH_ADAPTER` |
| AutoCAD readback/setup evidence | existing Drawing Setup/File IPC/.NET owners | `REUSE_AS_IS` |
| Entity count/signature observation | existing live readback and verifier evidence | `REUSE_AS_IS` |
| Visual/dimension review | existing independent verdict contracts | `REUSE_AS_IS` |
| New transport, database, geometry engine, provider call, or CAD parser | none | `REJECT` |

The adapter must not duplicate the AutoCAD transport, DXF writer, source
fusion, Base-CAD S3A handoff, visual comparator, or repair executor.

## Fail-closed invariants

- Native mode accepts only `source_format = DWG` and `scope = FULL_DRAWING`.
- Source and candidate are immutable during each observation and sealing step.
- Candidate path/hash, readback path/hash, entity count, and entity signature
  must agree with the packet.
- Native, generated, and Base-CAD provenance modes are mutually exclusive.
- Native R3 contains exactly one `drawing_binding` and zero components, views,
  links, projection references, and entity-handle bindings.
- Filename, layer names, viewport appearance, and user claims are never
  substitutes for source/candidate identity.
- Calibration is never inferred from native-DWG evidence.
- A valid provenance packet cannot produce a visual, dimension, persistence,
  reopen, repair, or publication PASS by itself.
- Existing generated and Base-CAD tests must pass unchanged.

## Tests and evidence

The RED/GREEN implementation plan must add focused tests before production
code. Required RED cases include foreign source/candidate hash, source or
candidate signature mismatch, stale AutoCAD observation, path replacement,
extra packet field, generated/native field mixing, Base-CAD handoff injection,
and a missing visual/dimension verdict. GREEN must prove deterministic packet
hashes, DARA currentness, native R3 binding, native R4 root binding, and
read-only query composition.

Required verification after implementation:

- focused native provenance, R3, R4, DARA, and drawing-query tests;
- `./scripts/verify.ps1` with disposable temp roots;
- `git diff --check` and clean-tree verification;
- Issue #409 evidence containing exact commit, test output, artifact hashes,
  and every live/private gate as `PASS`, `SKIP`, or `NOT RUN`;
- independent requirements/architecture, correctness/test, and
  security/operations review under #392 before any release claim.

## Write set

- `cad_agent/native_dwg_provenance.py`;
- `cad_agent/component_view_registry.py`;
- `cad_agent/candidate_revision.py`;
- focused native-DWG provenance/R3/R4 tests;
- this design and its implementation plan;
- `docs/STATUS.md` only after fresh objective evidence exists.

No source/customer drawing, generated candidate, AutoCAD state, or private
artifact is committed.

## Explicit exclusions

No source mutation, redraw, geometry inference, OCR, image/PDF calibration,
provider/API call, PR #340 mutation, M2/provider rerun, new CAD transport,
shadow CAD database, automatic visual approval, automatic dimension approval,
repair, promotion, or publication is included.

## Rollback

The runtime change is one bounded adapter/schema extension. Reverting its
implementation commit restores the existing generated and Base-CAD paths;
native artifacts remain disposable and outside the repository. The design and
plan remain as evidence of the rejected or accepted boundary.
