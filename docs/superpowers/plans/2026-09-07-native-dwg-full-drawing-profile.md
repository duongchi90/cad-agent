# Native DWG Full-Drawing Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a closed `NATIVE_DWG_FULL_DRAWING` provenance path for the immutable BVTL DWG source and its full-drawing DXF candidate, without fabricating generated or Base-CAD component provenance.

**Architecture:** Add one deterministic native-DWG packet/sealer and a thin composition adapter. Extend R3 with a dedicated native registry containing one drawing-level binding and empty component/view/link collections, then extend the existing R4 root path to bind that registry to DARA currentness and the existing read/query owners. Existing generated and Base-CAD paths remain unchanged.

**Tech Stack:** Python 3.11, pathlib/hashlib/json, existing `drawing_artifact_reference`, `component_view_registry`, `candidate_revision`, `drawing_query`, pytest, PowerShell `scripts/verify.ps1`.

**Spec:** `docs/superpowers/specs/2026-09-07-native-dwg-full-drawing-profile-design.md`

## Status and exact base

- Status: executing
- Base SHA: `a5fa94ee4dccf82087c95003be25e3abde0cc206`
- Completion Head SHA: pending
- Issue: #409
- Source artifact: workstation-only `BVTL.dwg`; never commit it
- Candidate artifact: disposable full-drawing DXF; never commit it

## Current verification checkpoint

- Focused native/R3/R4/DARA/query regression: `231 passed`.
- Ruff: changed-file checks passed.
- Authoritative `.\\scripts\\verify.ps1`: exit `0`; .NET `198 passed`; contract
  `68 passed + 50 subtests`; IPC `118 failures=0 errors=0 skipped=0`; offline
  `3186 passed, 18 deselected, 72 subtests`; causal-RED exactly one expected
  failure; real-data `2 skipped`; AutoCAD mechanical `14 skipped`.
- Live AutoCAD setup, persistence/reopen, visual, dimension, and calibration
  gates remain `NOT RUN`/`SKIP`; this checkpoint is not REAL P1 PASS.

## Global Constraints

- Native mode accepts only `source_format=DWG`, `candidate_format=DXF`, and `scope=FULL_DRAWING`.
- Source and candidate files are regular, non-symlink/non-reparse files and are re-snapshotted at sealing.
- Native, generated, and Base-CAD provenance modes are mutually exclusive.
- R3 native output contains exactly one `drawing_binding` and zero components, views, links, projection references, and entity-handle bindings.
- R4 native root requires `base_cad_handoff=None` and binds the exact DARA `R3_CANDIDATE` reference and current observation.
- Calibration is `NOT_APPLICABLE_NATIVE_CAD`; visual, dimension, persistence, reopen, repair, and publication are independent gates.
- Reuse existing DARA, R3, R4, drawing-query, AutoCAD readback, and verifier owners; add no transport, database, provider call, parser, or geometry engine.
- No source/customer/private/generated CAD artifact is committed.

### Task 1: Add failing native-DWG packet and composition tests

**Files:**
- Create: `tests/test_cad_agent_native_dwg_provenance.py`
- Reference: `cad_agent/native_dwg_provenance.py` (does not exist yet)
- Reference: `cad_agent/drawing_artifact_reference.py`

**Interfaces:**
- Produces the failing contract for `build_native_dwg_provenance`, `validate_native_dwg_provenance`, `build_native_dwg_r3_inputs`, and `compose_native_dwg_query_binding`.
- Uses only temporary synthetic `.dwg`/`.dxf` byte files and detached readback dictionaries; no BVTL file and no AutoCAD session.

- [x] **Step 1: Write the deterministic fixture helpers and first RED test**

Add a fixture with exact closed readback records. The helper must replace the
placeholder observation checksum with the canonical hash of all fields except
that checksum:

    def _readback(path: Path, data: bytes, *, count: int, signature: str) -> dict[str, object]:
        record = {
            "schema_version": "native-dwg-readback-1.0",
            "artifact_path": str(path),
            "artifact_sha256": hashlib.sha256(data).hexdigest(),
            "entity_count": count,
            "entity_signature_sha256": signature,
            "observation_sha256": "",
        }
        record["observation_sha256"] = canonical_json_sha256({
            key: record[key] for key in record if key != "observation_sha256"
        })
        return record

The first test calls `build_native_dwg_provenance(...)` with equal count and
signature and asserts schema `native-dwg-full-drawing-provenance-1.0`, mode
`NATIVE_DWG_FULL_DRAWING`, scope `FULL_DRAWING`, formats `DWG`/`DXF`, and
`calibration_mode == "NOT_APPLICABLE_NATIVE_CAD"`.

- [x] **Step 2: Add RED tamper tests before production code**

Cover these exact cases: deterministic replay; source or candidate hash drift;
count or signature mismatch; unknown fields or wrong formats; and readback
observation checksum drift. Each test builds the same fixture, mutates exactly
one field, and asserts the relevant NativeDwgProvenanceError code:
SOURCE_ARTIFACT_HASH_MISMATCH, CANDIDATE_ARTIFACT_HASH_MISMATCH,
ENTITY_COUNT_MISMATCH, ENTITY_SIGNATURE_MISMATCH, PROVENANCE_SCHEMA_INVALID,
or READBACK_HASH_MISMATCH.

Assert that changing bytes, paths, counts, signatures, setup audit hashes, or
packet fields cannot be repaired by recomputing only the outer packet checksum.

- [x] **Step 3: Add RED composition assertions**

Specify that `compose_native_dwg_query_binding(...)` returns a current DARA
`R3_CANDIDATE` reference, a revision with
`candidate_kind == "ROOT_PRE_REPAIR"`, a current candidate state, a native
R3 registry, and the expected active candidate path. Assert that the
composition contains no Base-CAD handoff and no generated-pilot fields.

- [x] **Step 4: Run the focused tests and record the expected RED result**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py -q

Expected: collection or import failure because the native module and its public
API do not exist. Do not claim production behavior from this run.

- [x] **Step 5: Commit the RED tests**

    git add tests/test_cad_agent_native_dwg_provenance.py
    git commit -m "test: add native DWG provenance red contract"

### Task 2: Implement the closed native-DWG packet/sealer

**Files:**
- Create: `cad_agent/native_dwg_provenance.py`
- Modify: `tests/test_cad_agent_native_dwg_provenance.py`

**Interfaces:**
- `NATIVE_DWG_PROVENANCE_SCHEMA_VERSION: str`
- `NATIVE_DWG_PROVENANCE_MODE: str`
- `NativeDwgProvenanceError(ValueError)`
- `build_native_dwg_provenance(*, source_path, candidate_path, source_readback, candidate_readback, source_setup_audit_sha256, candidate_setup_audit_sha256) -> dict[str, object]`
- `validate_native_dwg_provenance(payload: object) -> dict[str, object]`
- `build_native_dwg_r3_inputs(packet: Mapping[str, object]) -> dict[str, object]`
- `compose_native_dwg_query_binding(*, source_path: str | os.PathLike[str], candidate_path: str | os.PathLike[str], source_readback: Mapping[str, object], candidate_readback: Mapping[str, object], source_setup_audit_sha256: str, candidate_setup_audit_sha256: str, run_id: str, project_id: str, drawing_id: str) -> dict[str, object]`

- [x] **Step 1: Implement regular-file snapshot and path binding helpers**

Reuse canonical JSON hashing and the repository's reparse-point checks. The
snapshot helper resolves a regular file, reads from an open descriptor, compares
descriptor/device/inode/size/mtime to a second stat, and returns
`(resolved_path, bytes, sha256)`. The path binding hashes a profile-specific
identity plus the normalized case-folded resolved path; it never uses the
filename alone.

- [x] **Step 2: Implement closed readback normalization**

Accept exactly:

    {
        "schema_version": "native-dwg-readback-1.0",
        "artifact_path": str,
        "artifact_sha256": str,
        "entity_count": int,
        "entity_signature_sha256": str,
        "observation_sha256": str,
    }

Require a non-negative count, lowercase SHA-256 values, and a checksum over the
first five fields. The builder requires the readback path and artifact hash to
match the fresh file snapshot and requires equal source/candidate counts and
signatures.

- [x] **Step 3: Implement packet build/validate**

The packet has exactly:

    {
        "schema_version", "provenance_mode", "profile_id", "scope",
        "source_format", "candidate_format",
        "source_path_binding_sha256", "candidate_path_binding_sha256",
        "source_sha256", "candidate_sha256", "candidate_id",
        "source_readback", "candidate_readback",
        "source_setup_audit_sha256", "candidate_setup_audit_sha256",
        "calibration_mode", "provenance_sha256",
    }

Set `candidate_id` to
`native-dwg-full-drawing:<candidate_sha256>`. Set profile, scope, formats,
mode, and calibration exactly as specified. Compute the packet checksum only
after nested values are normalized, then call the validator before returning a
detached packet.

- [x] **Step 4: Make the RED packet tests GREEN**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py -k "packet" -q

Expected: all packet build, replay, drift, mismatch, and closed-field tests
pass. Run `git diff --check` and commit:

    git add cad_agent/native_dwg_provenance.py tests/test_cad_agent_native_dwg_provenance.py
    git commit -m "feat: seal native DWG full-drawing provenance"

### Task 3: Extend R3 with a dedicated drawing-level native registry

**Files:**
- Modify: `cad_agent/component_view_registry.py`
- Modify: `tests/test_cad_agent_native_dwg_provenance.py`
- Preserve: `tests/test_cad_agent_component_view_registry.py`
- Preserve: `tests/test_cad_agent_mechanical_pilot_provenance.py`

**Interfaces:**
- Add `COMPONENT_VIEW_REGISTRY_NATIVE_DWG_SCHEMA_VERSION = "component-view-registry-native-dwg-1.0"`.
- Add native context fields `provenance_mode`, `candidate`, and `native_dwg_provenance`.
- Add native `drawing_binding` validation and provenance evidence while preserving the existing public builder signatures.

- [x] **Step 1: Add RED R3 tests**

Assert that `build_component_view_registry(**build_native_dwg_r3_inputs(packet))`
returns schema `component-view-registry-native-dwg-1.0`, native upstream
bindings, one `drawing_binding`, empty `components`, `views`, and
`links`, and a deterministic snapshot hash. Add failures for a non-empty
component/view/link collection, generated or Base-CAD fields, a foreign
candidate hash, and a tampered native packet.

- [x] **Step 2: Run the R3 RED tests**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py -k "r3 or registry" -q

Expected: RED because the native context and schema branch do not exist.

- [x] **Step 3: Add the native context branch without changing legacy branches**

In `_upstream_context`, detect only `NATIVE_DWG_FULL_DRAWING`, validate the
packet with the new module, require candidate ID/SHA equality, and return the
native schema, packet, upstream bindings, and no source-fusion/Base-CAD indexes.
Reject every extra context field.

In build/validate paths, branch on the native schema before component/view
normalization. Require empty `components` and `views`, derive empty
`links`, create the exact `drawing_binding` from the packet, and include it
in native snapshot material. Keep schemas 1.0 and 1.1 unchanged.

- [x] **Step 4: Add native provenance evidence and empty impact support**

For native schema, hash a closed material containing native schema, upstream
bindings, and drawing binding. `project_linked_view_impacts` accepts only
empty component/view selectors and returns the existing impact shape with empty
component IDs, view IDs, layout bindings, and link IDs. Non-empty selectors
fail closed.

- [x] **Step 5: Run focused R3 and legacy tests**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py tests/test_cad_agent_component_view_registry.py tests/test_cad_agent_mechanical_pilot_provenance.py -q

Expected: native tests pass and all existing R3/generated tests remain green.
Commit:

    git add cad_agent/component_view_registry.py tests/test_cad_agent_native_dwg_provenance.py
    git commit -m "feat: add native DWG drawing-level R3 registry"

### Task 4: Extend R4 root binding for native mode

**Files:**
- Modify: `cad_agent/candidate_revision.py`
- Modify: `tests/test_cad_agent_native_dwg_provenance.py`
- Preserve: `tests/test_cad_agent_candidate_revision.py`

**Interfaces:**
- Keep `build_candidate_revision`, `validate_candidate_revision`, and state APIs unchanged.
- Add native schema discrimination in `_normalize_registry` and `_normalize_root_inputs` only.

- [x] **Step 1: Add RED R4 tests**

Use the native R3 fixture to build a root revision. Test that a valid native
root is accepted, while a supplied Base-CAD handoff, generated packet, foreign
candidate artifact, stale DARA observation, non-empty native impact, or mixed
schema is rejected. Assert empty component/view lineage and native mode in
`upstream_bindings`.

- [x] **Step 2: Run the R4 RED tests**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py -k "r4 or revision" -q

Expected: RED because every non-generated registry currently requires a
Base-CAD handoff.

- [x] **Step 3: Implement native root discrimination**

In `_normalize_registry`, recognize the native R3 schema, require
`base_cad_handoff is None`, and validate native upstream bindings and packet
hash. Do not call the Base-CAD handoff validator for native input.

In `_normalize_root_inputs`, require the DARA root artifact SHA to equal the
native candidate SHA. Keep the existing R3-to-DARA pair
`registry_snapshot_sha256` and `provenance_sha256` as the only reference
binding. Native root impact is the empty R3 impact; generated and Base-CAD
checks remain unchanged.

- [x] **Step 4: Run R4 and full focused regression**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py tests/test_cad_agent_candidate_revision.py -q

Expected: native R4 tests and all existing candidate-revision tests pass.
Commit:

    git add cad_agent/candidate_revision.py tests/test_cad_agent_native_dwg_provenance.py
    git commit -m "feat: bind native DWG candidates through R4"

### Task 5: Complete the thin DARA/R3/R4/query composition adapter

**Files:**
- Modify: `cad_agent/native_dwg_provenance.py`
- Modify: `tests/test_cad_agent_native_dwg_provenance.py`
- Preserve: `cad_agent/drawing_query.py`

**Interfaces:**
- `compose_native_dwg_query_binding` returns the generated composition shape: packet, reference, current observation, artifact bytes, registry, registry context, candidate revision/state, baseline context, impact, mutation evidence, and expected active document path.
- The adapter calls existing DARA/R3/R4 owners and does not add a query language or enumerate the full drawing.

- [x] **Step 1: Implement candidate snapshot and DARA custody**

Snapshot the candidate for composition, issue a `BASELINE` reference and
current observation, then issue an `R3_CANDIDATE` reference using the native
R3 provenance pair. Use scope `{run_id, project_id, drawing_id}` and evidence
IDs prefixed `native-dwg-baseline-` and `native-dwg-candidate-`. Refuse
candidate drift between the packet and DARA reference.

- [x] **Step 2: Implement native R4 root composition**

Build empty native impact, `R4_ROOT_PRE_REPAIR` mutation evidence, and
`candidate-revision-1.1` root with `base_cad_handoff=None`. Build and
validate candidate state with the existing state owner. Return detached values
and the resolved candidate path.

- [x] **Step 3: Verify existing drawing-query reuse**

Call `drawing_query.observe_drawing(client=None, ...)` with the composed
binding and assert a valid result bound to DARA/R3/R4 identities, with zero
component/view/link counts and
`whole_drawing_entity_count_status == "NOT_ENUMERATED"`. Do not claim this
is full entity acceptance; counts/signatures come from the native packet.

- [x] **Step 4: Run composition and query tests**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py -k "composition or query" -q

Expected: all composition/query tests pass. Commit:

    git add cad_agent/native_dwg_provenance.py tests/test_cad_agent_native_dwg_provenance.py
    git commit -m "feat: compose native DWG DARA R3 R4 binding"

### Task 6: Run repository verification and publish implementation evidence

**Files:**
- Modify: `docs/superpowers/plans/2026-09-07-native-dwg-full-drawing-profile.md`
- Modify: `docs/STATUS.md` only if fresh evidence satisfies current entry rules
- External evidence: GitHub Issue #409 and required #392 review

- [x] **Step 1: Run focused quality checks**

    .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_native_dwg_provenance.py tests/test_cad_agent_component_view_registry.py tests/test_cad_agent_candidate_revision.py tests/test_cad_agent_drawing_query.py -q
    git diff --check

Expected: exit 0, no repository diff caused by tests, and no private/live gate
misreported as passed.

- [x] **Step 2: Run the authoritative verifier with a disposable temp root**

Set disposable `TEMP` and `TMP` directories before invoking the exact
repository command:

    $env:TEMP = 'C:\temp\cad-agent-pytest-native-dwg-20260907-01'
    $env:TMP = $env:TEMP
    .\scripts\verify.ps1

Record exact exit code and every .NET, contract, IPC, offline, real-data,
AutoCAD, causal-RED, and provider state. `SKIP` and `NOT RUN` remain
explicit.

- [ ] **Step 3: Run required independent reviews**

Publish the compact implementation packet to #392 for requirements/
architecture, correctness/test, and security/operations review. Each accepted
finding must name scope, impact, evidence, and verification. Do not claim a
release or P1 pass until the required reviews are independently complete.

- [ ] **Step 4: Update plan and status only from evidence**

Fill `Completion Head SHA` with the final implementation/evidence commit
before a lifecycle-closing commit. Update `docs/STATUS.md` only with exact
fresh results. Record live native-DWG setup, persistence/reopen, visual,
dimension, and calibration gates as `PASS`, `SKIP`, or `NOT RUN`; never
infer a P1 pass from offline tests.

- [ ] **Step 5: Publish the exact GitHub handoff**

Push the branch and comment on #409 with exact base/head SHAs, changed files,
focused and authoritative test results, packet/candidate/source hashes, review
links, and the next unsatisfied boundary. Keep all DWG/DXF/private artifacts
workstation-only.

## Self-review checklist

- No task adds a second transport, store, geometry owner, provider, or visual authority.
- The R3-to-DARA hash is acyclic: R3 packet/binding seals first, DARA reference binds the R3 provenance pair, then R4 binds both.
- Existing generated and Base-CAD schemas have dedicated regression coverage.
- Native full-drawing scope never claims component-level identity or full entity query coverage.
- The plan does not promote offline provenance to visual/dimension/live PASS.
