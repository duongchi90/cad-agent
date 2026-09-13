# Semantic Multiplicity Contract Implementation Plan

For agentic workers: use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Make approved page-1 fidelity geometry deduplicate only within an explicitly mapped semantic line occurrence, while preserving ambiguous and distinct occurrences fail-closed.

Architecture: Extend the existing hash-bound region proposal data with optional source-pixel occurrence descriptors. cad_agent.fidelity maps raw Hough candidates to zero, one, or multiple descriptors and passes the resulting occurrence ids to its existing greedy filter; the filter deduplicates only same-occurrence candidates. Unmapped and ambiguous candidates remain present, so no new classifier or registry is needed.

Tech Stack: Python 3.11, pytest, OpenCV, existing cad_agent.fidelity and primitive_ir_lib.geometry_extraction owners.

Spec: docs/superpowers/specs/2026-09-13-semantic-multiplicity-contract-design.md

Status: planned

Base SHA: 0fc0f64289d0732f767fd4df486e1eeab3ace7b2

Completion Head SHA: Not recorded until the final implementation/evidence commit exists.

Verification command: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1

Verification result: Not recorded until execution completes.

Required private/live gates: real_data NOT RUN until implementation is verified; autocad_mechanical NOT RUN because this bounded review-only geometry change does not authorize live CAD mutation.

## Global Constraints

- Use the existing cad_agent.fidelity mapping/filter/selection owner.
- Preserve the existing Hough extraction owner and default behavior when no approved occurrence mapping is present.
- Treat the approved source render as truth; never feed native DWG data into reconstruction.
- Ambiguous or unmapped occurrence assignment is fail-closed and cannot remove a candidate.
- Do not tune Hough parameters, expand to page 2, mutate source/customer/accepted drawings, or reuse rejected candidate ancestry.
- Run a focused RED/GREEN cycle before the broader verification gate.

### Task 1: Add the approved occurrence descriptor contract to the region owner

Files:
- Modify: cad_agent/fidelity.py, function _normalized_regions
- Test: tests/test_semantic_multiplicity_contract.py

Interfaces:
- Consumes existing region records with id, bbox_px, and purpose.
- Produces optional normalized geometry_occurrences records with stable ids and page-pixel p1_px/p2_px segments, included in the existing proposal definition hash.

- [x] Step 1: Write the failing test.

  Add test_region_proposal_preserves_geometry_occurrences_and_hashes_them. Submit two valid occurrence records in one region, assert the proposal preserves them, then change one endpoint and assert the proposal definition digest changes.

- [x] Step 2: Run the focused test and verify it fails.

  Run pytest tests/test_cad_agent_fidelity.py -k geometry_occurrence_proposal -q.
  Expected: FAIL because _normalized_regions currently drops the occurrence field.

- [x] Step 3: Implement the smallest validation and normalization delta.

  Validate a non-empty unique occurrence id, two finite numeric points, a segment length of at least 12 pixels, and points inside the containing region. Copy only normalized occurrence fields into the existing region record. The existing definition hash then binds them without a second schema or registry.

- [x] Step 4: Run the focused test and verify it passes.

  Run pytest tests/test_cad_agent_fidelity.py -k geometry_occurrence_proposal -q and confirm PASS.

- [ ] Step 5: Commit the bounded contract change.

  Run git add cad_agent/fidelity.py tests/test_cad_agent_fidelity.py and git commit -m "feat: bind semantic geometry occurrences to regions".

### Task 2: Add the causal RED for occurrence-aware filtering

Files:
- Modify: tests/test_semantic_multiplicity_contract.py

Interfaces:
- Consumes RawGeometry, RawLine, and the existing private filter owner.
- Produces regression cases for distinct, same, and ambiguous occurrence assignments.

- [x] Step 1: Write the failing distinct-occurrence test.

  Add test_filter_preserves_distinct_semantic_occurrences_within_endpoint_tolerance with two six-pixel-separated horizontal RawLine values and occurrence_ids mapping each id to a different occurrence. Assert both ids remain.

- [x] Step 2: Run the RED.

  Run pytest tests/test_cad_agent_fidelity.py -k preserves_distinct_semantic_occurrences -q.
  Expected: FAIL because _filter_fidelity_geometry has no occurrence-aware input.

- [x] Step 3: Add the same-occurrence and ambiguous RED cases.

  Add test_filter_deduplicates_raw_fragments_within_one_semantic_occurrence with two endpoint-near raw lines sharing one occurrence and assert only the higher confidence/length line remains. Add test_filter_keeps_ambiguous_occurrence_candidates_fail_closed with None assignments and assert both candidates remain.

- [x] Step 4: Run all three RED tests.

  Run pytest tests/test_cad_agent_fidelity.py -k semantic_occurrence -q and confirm the failures are caused by the missing occurrence-aware interface, not malformed fixtures.

  In this workstation run, the equivalent custom unittest harness was used with
  native-library thread limits because pytest collection was blocked by the
  Windows commit/paging-file limit. It produced three TypeError failures for
  the missing occurrence_ids argument and one passing region-contract test.

### Task 3: Implement and wire the smallest existing-owner repair

Files:
- Modify: cad_agent/fidelity.py, _filter_fidelity_geometry, _select_fidelity_geometry, and run_fidelity_reconstruct
- Test: tests/test_semantic_multiplicity_contract.py

Interfaces:
- Consumes normalized region geometry_occurrences and extracted RawGeometry in crop coordinates.
- Produces an occurrence-id map for each raw candidate and the existing RawGeometry selection result; same-occurrence dedup only when the map is explicit and unique.

- [x] Step 1: Write and run the mapping RED.

  The test-only RED covers one compatible source segment, a multiple-match
  ambiguous segment, and an unmapped segment. The custom unittest harness
  fails all three with AttributeError because the mapper is not present.

- [ ] Step 2: Add the fixed source-segment mapper.

  Map a raw segment to an occurrence when both endpoints are collinear with the occurrence segment within a fixed one-pixel source-render tolerance and projected intervals overlap by at least 12 pixels. Return one id only for exactly one match; return None for zero or multiple matches.

- [ ] Step 3: Make the filter accept an optional occurrence-id map.

  Keep the current endpoint/confidence/length algorithm when the map is absent. When the map is present, compare a candidate only with retained lines carrying the same non-None occurrence id; never collapse or replace across different, missing, or ambiguous ids.

- [ ] Step 4: Pass region descriptors through reconstruction.

  Convert approved page-pixel occurrence points to crop-local points using the existing region origin, build the map after Hough extraction, and pass it into _select_fidelity_geometry. Add mapped and ambiguous counts to the existing quality report without changing its schema version.

- [ ] Step 5: Run the occurrence-aware tests GREEN.

  Run pytest tests/test_cad_agent_fidelity.py -k semantic_occurrence -q and confirm all three cases pass.

- [ ] Step 6: Run the owner regression suite.

  Run pytest tests/test_cad_agent_fidelity.py -q and confirm the existing no-mapping behavior and all fidelity tests remain green.

- [ ] Step 7: Commit the causal repair.

  Run git add cad_agent/fidelity.py tests/test_cad_agent_fidelity.py and git commit -m "fix: deduplicate fidelity lines by semantic occurrence".

### Task 4: Verify the product boundary and record evidence

Files:
- Modify docs/STATUS.md only after fresh verification evidence exists.
- Modify this plan only for lifecycle evidence.

Interfaces:
- Consumes the causal repair commit, current-main comparison, focused tests, authoritative verifier, and approved private page-1 input.
- Produces exact-head evidence for occurrence recall, duplicate population, unrelated entities, full page-1 visual behavior, and required gate states.

- [ ] Step 1: Fresh-read branch and source identity.

  Run git fetch --prune origin main, record git ls-remote origin refs/heads/main, git rev-parse HEAD, git diff origin/main...HEAD, and git status --short --branch. Stop if base or write-set is stale or contains rejected ancestry.

- [ ] Step 2: Run the authoritative verification.

  Run powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1. Record the exact result; a focused pass is not a product pass.

- [ ] Step 3: Run the approved private page-1 replay.

  Use the existing source-bound private packet and record source/render hashes, occurrence recall, missing-geometry population, same-occurrence duplicate population, unrelated LINE/entity deltas, selected profile, and full approved-region visual evidence. Record SKIP or NOT RUN for unavailable prerequisites.

- [ ] Step 4: Run git diff --check and confirm status stability.

  Run git diff --check and git status --short --branch; confirm verification did not modify repository status.

- [ ] Step 5: Route exactly one relevant SOL review.

  When the bounded GREEN and evidence packet are complete, send a delta-only REVIEW EVIDENCE request bound to the exact base and HEAD. Wait for the verdict before any next mutation or promotion.

- [ ] Step 6: Close the plan lifecycle only from evidence.

  After accepted review and all required gates, update this plan with Status: completed, the exact implementation/evidence Completion Head SHA, verification result, and private/live gate states. Update docs/STATUS.md only with evidence that actually ran.
