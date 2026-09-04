# Generated Mechanical Pilot Provenance Design

## Status

Approved by the Human Owner on 2026-09-03 as “Phương án A”.

## Measured gap

The Phase 3 shaft pilot produces a fresh candidate whose feature origin is
`RECONSTRUCTED_NEW`. The existing R3 component/view registry accepts that
origin label, but its upstream contract is exclusively a Base-CAD R2 reuse
handoff. R4 likewise requires that handoff before it can seal a root candidate.

On main `8cfbce22ba9f965164fbc9a4d67824475c15f150`, a truthful upstream context
containing only the generated candidate and mechanical-pilot evidence fails
closed with `UPSTREAM_CONTEXT_INVALID`. Creating a synthetic R2 handoff would
misstate generated geometry as `REUSED_FROM_BASE_CAD` and is forbidden.

## Goal

Represent one exact generated Mechanical pilot candidate through the existing
DARA, R3, R4, and bounded drawing-query owners without fabricating Base-CAD
reuse provenance.

## Architecture

### 1. Mechanical pilot provenance packet

Add `cad_agent.mechanical_pilot_provenance` as a thin deterministic owner. It
consumes an in-memory `MechanicalPilotResult` produced by the existing pilot
builder and verifies the source file, candidate file, build evidence, pilot
evidence, primitive bindings, feature bindings, and candidate handles before
issuing a closed checksummed packet.

The packet contains only bounded identity and binding evidence:

- exact pilot/source/candidate/build/pilot-evidence identities;
- one record per written primitive with a deterministic projection reference,
  written-geometry checksum, layer, and entity handle;
- one record per pilot feature with a deterministic semantic projection
  reference and exact primitive membership;
- a canonical packet checksum.

It is not a new store, transport, geometry engine, or authority service.

### Reuse-first declaration

The implementation reuses the existing `build_simple_shaft_pilot`,
`load_pilot_definition`, `_documents`, `load_build_evidence`, DARA reference and
currentness functions, R3 registry, R4 candidate-revision builders, and bounded
drawing-query owner. The new module is only a deterministic validator/sealer
and composition adapter around those owners; it does not duplicate geometry,
CAD transport, persistence, or query execution.

The existing Base-CAD `component-view-registry-1.0` and required R2 handoff
remain unchanged. Generated mode is an explicit second schema path with no
rollback, mutation, provider, or live-session side effects. Its only output is
checksummed evidence and arguments for the existing read-only owners.

### 2. Discriminated R3 upstream mode

Preserve the existing Base-CAD R3 context and `component-view-registry-1.0`
output byte-for-byte. Add a second exact context shape selected only by
`provenance_mode=GENERATED_MECHANICAL_PILOT` and issue
`component-view-registry-1.1` for that mode.

Generated components must be `RECONSTRUCTED_NEW`, must not carry a Base-CAD
reference, and may bind candidate handles only when the handle, primitive ID,
and build-evidence checksum are present in the validated pilot packet. Source
and semantic projection references are derived from and checked against that
same packet. Unknown, mixed, foreign, stale, or malformed context fails closed.

### 3. R4 root composition without a false R2 handoff

Keep `base_cad_handoff` mandatory and unchanged for the existing Base-CAD mode.
For a validated generated R3 registry, require `base_cad_handoff=None` and bind
the R4 root artifact directly to the candidate SHA in the generated R3
upstream bindings. Supplying an R2 handoff in generated mode, omitting it in
Base-CAD mode, or mismatching the candidate SHA fails closed.

The existing `candidate-revision-1.1` `ROOT_PRE_REPAIR` shape and candidate
state owner remain unchanged.

### 4. Thin composition adapter

The provenance module exposes one bounded composition function that:

1. validates and seals the generated pilot packet;
2. builds the generated R3 registry and provenance evidence;
3. issues current DARA `BASELINE` and `R3_CANDIDATE` references over the exact
   same pre-repair candidate bytes;
4. builds one R4 `ROOT_PRE_REPAIR` revision and current candidate state;
5. returns the exact arguments needed by `drawing_query.query_entities`.

No mutation, persistence, provider call, CAD session, or live request occurs in
this adapter.

## Fail-closed invariants

- Source, candidate, build evidence, and pilot evidence must still be regular
  files with the exact hashes represented by `MechanicalPilotResult`.
- Every feature primitive must exist, be written exactly once, and have one
  candidate handle.
- Every generated handle is owned by exactly one component.
- Base-CAD and generated provenance modes cannot be mixed.
- A foreign source/candidate/build hash, primitive, feature, or handle is
  rejected before query execution.
- Existing Base-CAD R3/R4 behavior and schema remain unchanged.
- Output ordering and checksums are deterministic.

## Acceptance

Using the checked-in simple shaft fixture and a fresh disposable output:

- the adapter produces a validated R3 generated registry containing the shaft
  and hole components with exact candidate handles;
- DARA currentness validates against the exact candidate bytes;
- R4 emits one current `ROOT_PRE_REPAIR` revision;
- an offline bounded component query resolves only the expected handles;
- candidate/source/build drift and foreign handle injection fail closed;
- all existing R3/R4/pilot/query regressions pass unchanged;
- the canonical verifier and hosted required checks pass before merge.

Live AutoCAD/FileIPC acceptance is a later #377 boundary and is not claimed by
these deterministic tests.

## Write set

- `cad_agent/mechanical_pilot_provenance.py`
- `cad_agent/component_view_registry.py`
- `cad_agent/candidate_revision.py`
- `tests/test_cad_agent_mechanical_pilot_provenance.py`
- this design and its implementation plan
- `docs/STATUS.md` only after objective evidence exists

## Explicit exclusions

No provider/API call, PR #340 mutation, M2 rerun, AutoCAD mutation, second CAD
transport, queue, daemon, shadow CAD database, arbitrary query language, or
source/customer/accepted drawing mutation.
