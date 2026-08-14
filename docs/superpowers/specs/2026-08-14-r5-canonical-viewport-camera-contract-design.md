# R5 Canonical Viewport / Camera Evidence Contract — Design

Date: 2026-08-14
Issue: #247
Design base: `4f705a62965620c84f063d868b059a3f5b02e2a8`
Status: approved concept; design-only branch; no runtime implementation in this commit

## 1. Problem

R5 already owns server-side visual-review scope and freshness checks, while the native-render/evidence path already binds artifacts to exact drawing, mutation, layout, run and read-only state. What is still missing is a first-class contract for *how the drawing was framed when the visual evidence was captured*.

For CAD, the same geometry can look materially different under different zoom levels, viewport centers, crop windows, visual styles or UCS/view direction. A prompt such as `always zoom extents` is useful operator guidance, but it is not sufficient acceptance evidence because an agent can forget it, silently deviate, or compare before/after captures made under incompatible camera conditions.

The system therefore needs an explicit, server-owned capture plan and an observed capture receipt that can be validated before R5 may accept visual evidence.

## 2. Goals

1. Make every R5 visual cycle start from a canonical whole-drawing view.
2. Make every required R5 region receive a deterministic region view derived from CAD-space coordinates, not from ad-hoc mouse zooming.
3. Allow bounded detail captures only when the visual supervisor asks for more evidence.
4. Bind every capture to the exact current candidate, latest mutation, visual scope, view/layout and render/image artifact.
5. Make old captures stale after mutation.
6. Prevent before/after comparison from treating incompatible camera states as equivalent evidence.
7. Reuse existing R5, visual-evidence, native-render and File-IPC owners without creating a second supervisor, renderer, store, transport or publication authority.

## 3. Non-goals

This design does not:

- rewrite R1-R4, R6-R8;
- replace `visual_review_scope`;
- replace `autocad-native-render-evidence-1.0`;
- add a second image renderer;
- make screenshots authoritative over native render evidence;
- authorize production/private/customer CAD;
- authorize a live AutoCAD implementation in this design commit;
- define computer-vision scoring thresholds beyond the existing R5 owner;
- allow a provider/model to invent its own mandatory review scope.

## 4. Ownership

Existing owners remain authoritative:

- R3/R4 own component/view and current-candidate identity.
- R5 owns visual-review scope and final visual verdict.
- Existing visual-evidence code owns evidence freshness and read-only capture acceptance.
- Existing native-render code owns DWG/layout -> native render evidence.
- Existing File-IPC/AutoCAD seam owns execution of live CAD commands.

The new contracts are adjacent R5 evidence contracts only:

- `visual_capture_plan-1.0`: server-owned intent for required visual framing.
- `visual_capture_receipt-1.0`: observed evidence that the requested framing was actually used.

Neither contract may issue a verdict, mutate CAD, approve repair, publish artifacts or redefine review scope.

## 5. Canonical capture hierarchy

Every visual cycle uses three capture classes.

### 5.1 GLOBAL

Purpose: establish whole-drawing context before any local judgement.

Required semantics:

- `capture_class = GLOBAL`
- `zoom_mode = EXTENTS`
- deterministic margin policy
- canonical top/world view for 2D drawing review unless the server-owned scope explicitly references another accepted view
- canonical visual style
- canonical background/render policy inherited from the accepted native-render path where applicable

GLOBAL is mandatory for every R5 cycle. A missing GLOBAL receipt makes the visual cycle non-PASS.

### 5.2 REGION

Purpose: provide a normalized close view for each required server-owned review region.

Required semantics:

- `capture_class = REGION`
- `zoom_mode = WINDOW`
- window is derived from a server-owned WCS bounding box
- a deterministic margin is applied to the bounding box
- the region identity must already exist in the accepted `visual_review_scope`

The provider/model may not replace the WCS window with a self-chosen crop.

Every required review region must have one accepted REGION receipt. Missing required REGION evidence is non-PASS.

### 5.3 DETAIL

Purpose: inspect a smaller sub-region when GLOBAL + REGION are not sufficient.

Required semantics:

- `capture_class = DETAIL`
- `zoom_mode = WINDOW`
- bounded by the parent REGION identity
- requested explicitly as next evidence by the visual supervisor or by an equivalent server-owned decision
- cannot replace mandatory GLOBAL or REGION evidence

DETAIL is optional. Absence is acceptable only when the current R5 cycle does not request it.

## 6. Contract: `visual_capture_plan-1.0`

The plan is closed and server-owned. Suggested normalized shape:

```json
{
  "schema_version": "visual-capture-plan-1.0",
  "plan_id": "capture-plan-...",
  "run_id": "...",
  "scope_id": "...",
  "registry_snapshot_sha256": "...",
  "candidate_revision_sha256": "...",
  "candidate_state_sha256": "...",
  "latest_mutation_sha256": "...",
  "captures": [
    {
      "capture_id": "global-1",
      "capture_class": "GLOBAL",
      "region_id": null,
      "view_id": "...",
      "sheet_id": "...",
      "layout_id": "...",
      "zoom_mode": "EXTENTS",
      "wcs_bbox": null,
      "margin_ratio": 0.05,
      "view_direction": "TOP",
      "ucs": "WORLD",
      "visual_style": "2D_WIREFRAME"
    },
    {
      "capture_id": "region-a",
      "capture_class": "REGION",
      "region_id": "region-a",
      "view_id": "...",
      "sheet_id": "...",
      "layout_id": "...",
      "zoom_mode": "WINDOW",
      "wcs_bbox": [0.0, 0.0, 100.0, 50.0],
      "margin_ratio": 0.10,
      "view_direction": "TOP",
      "ucs": "WORLD",
      "visual_style": "2D_WIREFRAME"
    }
  ]
}
```

The concrete implementation may use existing project identifier conventions, but the following invariants are mandatory:

- plan is bound to exact server-owned scope/current candidate/current mutation;
- exactly one GLOBAL capture exists per cycle;
- GLOBAL uses EXTENTS semantics and has no arbitrary WCS crop;
- every server-required region has exactly one REGION capture;
- REGION/DETAIL use finite, non-degenerate WCS bounding boxes;
- margins are finite and restricted to a bounded policy range;
- unknown properties fail closed;
- duplicate capture IDs or duplicate required REGION coverage fail closed;
- provider-supplied plan substitution is rejected.

The canonical SHA-256 of the normalized plan becomes `visual_capture_plan_sha256`.

## 7. Contract: `visual_capture_receipt-1.0`

The receipt records what was actually observed/executed. Suggested normalized shape:

```json
{
  "schema_version": "visual-capture-receipt-1.0",
  "receipt_id": "receipt-...",
  "capture_id": "region-a",
  "run_id": "...",
  "scope_id": "...",
  "region_id": "region-a",
  "view_id": "...",
  "sheet_id": "...",
  "layout_id": "...",
  "candidate_revision_sha256": "...",
  "candidate_state_sha256": "...",
  "latest_mutation_sha256": "...",
  "visual_capture_plan_sha256": "...",
  "capture_class": "REGION",
  "zoom_mode": "WINDOW",
  "requested_wcs_bbox": [0.0, 0.0, 100.0, 50.0],
  "observed_wcs_bbox": [0.0, 0.0, 100.0, 50.0],
  "view_center": [50.0, 25.0],
  "view_width": 110.0,
  "view_height": 55.0,
  "view_direction": "TOP",
  "ucs": "WORLD",
  "visual_style": "2D_WIREFRAME",
  "artifact_sha256": "...",
  "artifact_width": 1920,
  "artifact_height": 1080,
  "captured_at_utc": "...",
  "transient_state_restored": true
}
```

The implementation may omit derived fields that add no independent security value, but it must preserve enough observed camera state to prove conformance to the plan and enough artifact identity to bind the receipt to the exact image/native-render artifact reviewed by R5.

Mandatory receipt invariants:

- exact plan SHA match;
- exact run/scope/candidate/mutation match;
- exact capture identity/class match;
- GLOBAL receipt proves EXTENTS/FIT-equivalent canonical framing;
- REGION/DETAIL receipt proves requested window framing within an explicit numeric tolerance owned by the validator;
- exact view/layout/UCS/view-direction/visual-style policy match;
- artifact SHA and dimensions are validated;
- transient AutoCAD state is restored after capture;
- unknown fields fail closed;
- replayed receipt against a different mutation/candidate/plan is rejected.

## 8. Bounding-box and margin semantics

Region windows are based on WCS geometry, not pixels.

For `bbox = [xmin, ymin, xmax, ymax]`:

- require `xmax > xmin` and `ymax > ymin`;
- reject NaN/Infinity;
- derive width/height in drawing units;
- apply the policy margin symmetrically around the center;
- if the region is degenerate or effectively point/line-only, use an explicit minimum-view-size policy rather than an unbounded zoom;
- all numeric normalization must follow existing deterministic numeric/canonical JSON policy where possible.

The first implementation should use a fixed default margin policy rather than expose free-form provider tuning. The recommended defaults are:

- GLOBAL margin: 5%;
- REGION margin: 10%;
- DETAIL margin: 5%.

These are server policy defaults, not provider preferences.

## 9. Before/after comparability

A visual comparison is camera-compatible only when both observations resolve to the same canonical policy identity for the compared scope.

At minimum, the comparator must require equality of:

- capture class;
- view/layout identity;
- zoom mode;
- normalized requested camera/window policy;
- view direction;
- UCS policy;
- visual style;
- render/background policy where relevant.

The image pixels do not need to be byte-identical because the CAD geometry may have changed. The camera *policy* must be equivalent.

For a mutation that changes region extents, a fresh REGION plan may legitimately produce a different WCS bbox. In that case the comparison is still valid only if both plans derive from the same deterministic region-bbox policy and the comparison layer records the two plan identities rather than pretending the raw windows were equal.

## 10. Freshness and mutation semantics

Existing R5 freshness rules remain authoritative.

A capture plan and every receipt are bound to `latest_mutation_sha256`. After R6 mutation:

- all prior capture plans/receipts are stale;
- no pre-repair visual PASS may be reused;
- fresh custody/currentness, fresh R3/R4 as required, and a new R5 cycle must generate a new capture plan and receipts.

A receipt with a valid image SHA but a stale mutation/candidate/scope identity is non-PASS.

## 11. R5 acceptance rule

R5 may produce a visual PASS only if:

1. server-owned `visual_review_scope` is current;
2. server-owned `visual_capture_plan` is current;
3. one valid GLOBAL receipt exists;
4. every required region has one valid REGION receipt;
5. every requested DETAIL capture has a valid receipt;
6. each receipt is fresh and bound to the exact artifact supplied to the visual provider;
7. no receipt is camera-incompatible with its plan;
8. no required evidence is `SKIP` or `NOT_RUN`;
9. existing geometry/visual/engineering gates continue to pass as required by current contracts.

Any missing, stale, foreign, ambiguous or camera-incompatible evidence yields FAIL/NEEDS_HUMAN/non-PASS according to the existing R5 contract; it must never be silently promoted to PASS.

## 12. Data flow

```text
R3/R4 current candidate
        |
        v
server-owned visual_review_scope
        |
        v
visual_capture_plan
        |
        +--> GLOBAL EXTENTS capture --------+
        |
        +--> REGION WINDOW capture(s) ------+--> receipts + exact artifacts
        |                                    |
        +--> optional DETAIL capture(s) -----+
                                             |
                                             v
                                      R5 visual provider
                                             |
                                             v
                              post-provider freshness validation
                                             |
                                      PASS / FAIL / NEEDS_HUMAN
```

The visual provider may request DETAIL evidence, but it may not alter mandatory GLOBAL/REGION membership or camera policy.

## 13. Integration strategy

### Slice A — contracts only

Preferred first implementation slice:

- extend `cad_agent/visual_contracts.py` with closed validators for plan/receipt;
- add focused tests in the existing visual-supervisor contract test owner;
- no AutoCAD execution;
- no visual-provider call;
- no transport change.

### Slice B — evidence freshness binding

Bind validated plan/receipt identities into the existing visual-evidence acceptance path so stale/foreign/mismatched camera evidence is rejected.

Expected owners:

- `cad_agent/visual_evidence.py`;
- focused existing tests.

Do not create a new evidence store.

### Slice C — R5 finalization

Require accepted capture coverage before final R5 PASS.

Expected owner:

- `cad_agent/visual_supervisor_adapter.py`;
- focused existing tests.

### Slice D — live AutoCAD execution

Only after A-C are reviewed/merged, add the smallest accepted File-IPC/AutoCAD execution seam needed to:

- establish canonical EXTENTS framing;
- establish canonical WINDOW framing;
- observe the resulting camera state;
- capture/render the artifact;
- restore transient view state;
- return the receipt.

This live slice must reuse the existing File-IPC owner. It may not create an R8-specific zoom transport or a second renderer.

## 14. RED-first test matrix

Contract RED tests must include at least:

- missing GLOBAL;
- two GLOBAL captures;
- missing required REGION;
- duplicate REGION coverage;
- unknown capture class;
- GLOBAL with WINDOW bbox;
- REGION without WCS bbox;
- degenerate bbox;
- NaN/Infinity coordinates;
- negative or excessive margin;
- provider-supplied scope/camera substitution;
- plan SHA mismatch;
- candidate revision/state mismatch;
- mutation mismatch/stale receipt;
- view/layout mismatch;
- UCS/view-direction/visual-style mismatch;
- requested/observed window mismatch beyond tolerance;
- wrong artifact SHA/dimensions;
- transient state not restored;
- replay across run/scope/mutation;
- DETAIL not parented to an accepted REGION;
- DETAIL attempting to replace mandatory REGION;
- SKIP/NOT_RUN coverage treated as non-PASS;
- before/after camera-policy incompatibility.

GREEN must be the smallest implementation that satisfies these tests without widening unrelated schemas.

## 15. Runtime safety rules

The later live AutoCAD slice must remain read-only with respect to drawing content during capture:

- no CAD entity mutation;
- DBMOD before == after;
- drawing hash before == after;
- transient viewport/UCS/view state restored;
- no registry/printer/driver/default-printer/system mutation;
- ordinary PC3/PMP read/hash only;
- no private/customer or production-target requirement for acceptance development.

Failure to restore transient view state is non-PASS.

## 16. Compatibility and migration

Existing evidence without a capture plan/receipt remains valid only for legacy paths that do not claim the new canonical-camera R5 capability. Once a run declares `visual_capture_plan-1.0`, all required captures must provide matching receipts.

Do not silently reinterpret old visual evidence as camera-normalized evidence.

No existing R1-R7 owner should require data migration merely to land the contract validators.

## 17. Rollback

Each slice is independently revertible:

- Slice A: remove the adjacent validators/tests.
- Slice B: remove camera freshness binding while preserving existing visual freshness behavior.
- Slice C: remove the additional R5 camera-coverage gate.
- Slice D: remove the live camera executor while leaving contracts intact.

No slice should require rollback of the existing native-render, visual-review-scope, candidate, repair or publication owners.

## 18. Acceptance criteria

The feature is complete only when:

- closed plan/receipt contracts are merged with RED-first coverage;
- evidence freshness rejects stale/foreign camera receipts;
- R5 PASS requires canonical GLOBAL + all required REGION coverage;
- on-demand DETAIL works without replacing mandatory coverage;
- live AutoCAD can execute EXTENTS/WINDOW framing and return an observed receipt;
- capture is proven read-only and transient state is restored;
- before/after visual review cannot compare incompatible camera policy as if equivalent;
- independent integration/security review passes on exact head;
- no second owner/store/transport/renderer/R8 glue is introduced.

## 19. Implementation boundary

This design authorizes no code implementation by itself. After written-spec approval, the next step is a separate implementation plan followed by RED-first Slice A. Runtime AutoCAD work remains a later bounded gate.