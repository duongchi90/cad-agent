# Generated Mechanical Pilot Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind a truthful generated shaft pilot through the existing DARA/R3/R4/query pipeline without a fabricated Base-CAD handoff.

**Architecture:** A new thin provenance owner validates exact pilot artifacts and emits a closed packet. R3 gains a discriminated generated mode while retaining its v1.0 Base-CAD path; R4 accepts `None` in the existing handoff slot only when a validated generated R3 registry proves the candidate identity. The adapter composes the existing owners and returns bounded-query inputs.

**Tech Stack:** Python 3.11, pytest, existing CAD Agent DARA/R3/R4 contracts, existing Mechanical pilot and DXF build evidence.

**Spec:** `docs/superpowers/specs/2026-09-03-generated-mechanical-pilot-provenance-design.md`

## Global Constraints

- Keep M3 real-provider acceptance frozen at `BLOCKED_BY_CREDIT_BALANCE_EXHAUSTED`.
- Do not call a provider, rerun M2, mutate or merge PR #340, or run live CAD in this implementation slice.
- Preserve the Base-CAD R3/R4 contract and all existing callers unchanged.
- Use no new transport, queue, daemon, persistence layer, geometry engine, or arbitrary execution surface.
- Follow strict RED → GREEN cycles; submission or mock-only evidence is not acceptance.

---

### Task 1: Closed generated-pilot provenance packet

**Files:**
- Create: `cad_agent/mechanical_pilot_provenance.py`
- Create: `tests/test_cad_agent_mechanical_pilot_provenance.py`

**Interfaces:**
- Consumes: `MechanicalPilotResult`, `sha256_file`, `load_build_evidence`, and `canonical_json_sha256`.
- Produces: `build_generated_pilot_provenance(result) -> dict[str, object]` and `validate_generated_pilot_provenance(payload) -> dict[str, object]`.

- [x] **Step 1: Write the failing packet tests**

  Build the checked-in shaft fixture in `tmp_path`. Assert the desired packet
  has exact source/candidate/evidence hashes, deterministic primitive and
  feature records, and a canonical checksum. Add table-driven mutations for
  candidate bytes, build evidence, a foreign handle, and an extra field.

- [x] **Step 2: Run the packet tests to verify RED**

  Run: `.venv-py311\Scripts\python.exe -m pytest -q tests/test_cad_agent_mechanical_pilot_provenance.py -k packet`

  Expected: collection fails because the new production module/API is absent.

- [x] **Step 3: Implement the minimum packet owner**

  Validate exact files and in-memory build mappings; derive literal closed
  primitive/feature records; sort by stable IDs; calculate the packet checksum;
  validate every internal reference and reject unknown fields.

- [x] **Step 4: Run the packet tests to verify GREEN**

  Run the Task 1 command and require all selected tests to pass.

### Task 2: R3 generated provenance mode

**Files:**
- Modify: `cad_agent/component_view_registry.py`
- Modify: `tests/test_cad_agent_mechanical_pilot_provenance.py`

**Interfaces:**
- Consumes: validated generated provenance packet and the existing `candidate` identity.
- Produces: generated `upstream_context`, `component-view-registry-1.1`, and unchanged R3 provenance evidence APIs.

- [x] **Step 1: Write the failing R3 tests**

  Assert that a generated context builds two `RECONSTRUCTED_NEW` components,
  binds every expected primitive handle, validates/replays deterministically,
  and rejects mixed Base-CAD fields, foreign handles, wrong build checksums,
  wrong source/semantic refs, and non-generated origin classes. Also assert the
  existing Base-CAD fixture still emits its exact v1.0 schema.

- [x] **Step 2: Run the R3 selection to verify RED**

  Run: `.venv-py311\Scripts\python.exe -m pytest -q tests/test_cad_agent_mechanical_pilot_provenance.py -k r3`

  Expected: generated context fails with `UPSTREAM_CONTEXT_INVALID`.

- [x] **Step 3: Implement the minimum discriminated R3 path**

  Detect only the two exact context shapes. For generated mode, validate the
  packet, derive projection indexes and allowed primitive/handle bindings, emit
  generated upstream bindings, use schema v1.1, and enforce generated component
  membership. Leave the existing Base-CAD branch and v1.0 output unchanged.

- [x] **Step 4: Run the R3 tests to verify GREEN**

  Run the Task 2 command, then run
  `.venv-py311\Scripts\python.exe -m pytest -q tests/test_cad_agent_component_view_registry.py`.

### Task 3: R4 root and bounded-query composition

**Files:**
- Modify: `cad_agent/candidate_revision.py`
- Modify: `cad_agent/mechanical_pilot_provenance.py`
- Modify: `tests/test_cad_agent_mechanical_pilot_provenance.py`

**Interfaces:**
- Consumes: generated R3 registry/context, exact candidate bytes, DARA, and existing R4 root/state builders.
- Produces: `compose_generated_pilot_query_binding(...) -> dict[str, object]` containing `reference`, `current_observation`, `artifact_bytes`, `parent_reference=None`, `accepted_transition_evidence_sha256=None`, `registry`, `registry_upstream_context`, and `candidate_state`.

- [x] **Step 1: Write the failing R4/query tests**

  Assert one current root revision is produced with the exact generated upstream
  bindings and no accepted transition. Use a real bounded fake CAD client to
  prove a shaft component query calls only its registry-bound handles. Assert
  generated mode rejects a supplied handoff, Base-CAD mode rejects a missing
  handoff, and stale candidate bytes fail before any client read.

- [x] **Step 2: Run the R4/query selection to verify RED**

  Run: `.venv-py311\Scripts\python.exe -m pytest -q tests/test_cad_agent_mechanical_pilot_provenance.py -k 'r4 or query or composition'`

  Expected: R4 rejects `base_cad_handoff=None` before recognizing the generated registry.

- [x] **Step 3: Implement the minimum R4 and adapter path**

  Validate R3 before selecting the provenance branch. Require a normal handoff
  for v1.0/Base-CAD, require `None` for generated v1.1, and compare the root
  reference SHA to the selected registry candidate SHA. Compose DARA references,
  R3 evidence, root impact/mutation evidence, R4 root, and current state without
  mutation or persistence.

- [x] **Step 4: Run the R4/query tests to verify GREEN**

  Run the Task 3 selection and require all selected tests to pass.

### Task 4: Regression, evidence, review, and integration

**Files:**
- Modify: `docs/STATUS.md` only with evidence that actually ran.

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: a reviewable bounded PR and exact hosted-gate evidence.

- [x] **Step 1: Run focused regression**

  Run all five relevant test modules: generated provenance, component registry,
  candidate revision, mechanical pilot, and drawing query.

- [x] **Step 2: Run static and repository checks**

  Run Ruff on changed Python files, `git diff --check`, and inspect the exact
  changed-path set for scope violations.

- [ ] **Step 3: Run the canonical verifier**

  Run: `.\scripts\verify.ps1`

  Require exit 0 and confirm verification did not dirty the worktree.

- [ ] **Step 4: Obtain independent reviews**

  Request architecture/requirements, correctness/tests, and security/operations
  review against the exact base/head diff. Resolve every P0/P1 finding and rerun
  affected verification.

- [ ] **Step 5: Record truthful status and commit**

  Update `docs/STATUS.md` with only deterministic acceptance, explicitly leaving
  Phase 1A live FileIPC query and provider-backed M3 acceptance unrun/blocked.
  Commit the bounded write set.

- [ ] **Step 6: Push, open the PR, and consume hosted gates**

  Push the branch, open a draft or ready PR linked to #377/#343, require the
  exact-head hosted required checks, consume current #301 advisories, and merge
  only if all gates and reviews are objectively satisfied.

- [ ] **Step 7: Fresh-read main and continue**

  After merge, fresh-read main and proceed to the one disposable #377 live
  query epoch. Do not claim live PASS from this offline slice.
