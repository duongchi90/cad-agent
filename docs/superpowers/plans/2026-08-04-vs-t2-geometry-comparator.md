# VS-T2 Geometry Comparator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Planning base SHA:** `2932febe5e95b042b202a767604d2143e6a6cc4f`

**Implementation base:** Create `task/vs-t2-geometry-comparator` from the fresh integrated `main` at the start of execution. Record the actual SHA in the PR body before changing code.

**Goal:** Build a deterministic offline comparator that aligns source and CAD region evidence through approved anchors, writes reproducible overlays and difference masks, computes the VS-T0 metric contract, and classifies candidate improvement or regression without issuing a visual verdict.

**Architecture:** Keep image algorithms in `primitive_ir_lib`; use `cad_agent` only for hash-bound file orchestration and contract validation. Use NumPy and OpenCV already present in the locked environment. Implement similarity alignment directly with deterministic NumPy linear algebra, and permit perspective correction only through exactly four approved photograph anchors. Free-form deformation, model calls, AutoCAD calls, and repair decisions are outside VS-T2.

**Tech Stack:** Windows, Python 3.11, OpenCV 5, NumPy 2, pytest, VS-T0 `geometry_comparison` contract.

## Global Constraints

- Comparator output is evidence, not a visual `PASS` or repair plan.
- Alignment priority is approved datums, confirmed driving-dimension anchors, stable CAD entity anchors, then high-confidence visual anchors.
- Translation, rotation, and uniform scale are allowed through a similarity transform.
- Perspective correction is allowed only for a source photograph and exactly four approved non-collinear correspondences.
- Affine shear, non-uniform scaling, thin-plate splines, optical-flow warping, and free-form deformation are prohibited.
- Alignment refusal is a valid output and must not fabricate zero-error metrics.
- Inputs and outputs are bound to source/reference hash, CAD render hash, mutation hash, region ID, and alignment configuration hash.
- Metrics must be finite and deterministic across repeated runs on the same bytes.
- No single average score determines acceptance.
- Source/CAD images and generated evidence remain outside Git; tests synthesize shapes in memory or under temporary directories.
- Every task starts with a failing focused test and ends with focused tests, `git diff --check`, diff inspection, and a bounded commit.
- `real_data`, OpenAI API, and AutoCAD Mechanical remain `NOT RUN` for this slice.

---

## File Structure

### New comparator files

- `primitive_ir_lib/geometry_alignment.py` — anchor validation, deterministic similarity transform, and four-point photograph homography.
- `primitive_ir_lib/geometry_metrics.py` — binary-outline normalization and deterministic metric functions.
- `primitive_ir_lib/geometry_comparator.py` — alignment application, overlays, difference masks, curve-profile comparison, and trend classification.

### New orchestration files

- `cad_agent/geometry_comparison_run.py` — immutable input snapshots, artifact hashing, atomic write, contract validation.
- `cad_agent/run_geometry_comparison.py` — CLI wrapper only.

### Tests

- `primitive_ir_lib/tests/test_geometry_alignment.py`
- `primitive_ir_lib/tests/test_geometry_metrics.py`
- `primitive_ir_lib/tests/test_geometry_comparator.py`
- `tests/test_geometry_comparison_run.py`
- `tests/test_geometry_comparator_policy.py`

## Stable Interfaces

```python
# primitive_ir_lib/geometry_alignment.py
from dataclasses import dataclass
from collections.abc import Sequence
import numpy as np

Point = tuple[float, float]

@dataclass(frozen=True)
class AnchorPair:
    anchor_id: str
    reference_px: Point
    cad_px: Point
    authority: str
    confidence: float

@dataclass(frozen=True)
class AlignmentResult:
    status: str
    method: str
    matrix: tuple[tuple[float, ...], ...] | None
    anchor_ids: tuple[str, ...]
    residual_rms_px: float | None
    reasons: tuple[str, ...]


def estimate_similarity_alignment(
    anchors: Sequence[AnchorPair],
    *,
    max_rotation_deg: float = 5.0,
    min_uniform_scale: float = 0.5,
    max_uniform_scale: float = 2.0,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Return deterministic translation/rotation/uniform-scale alignment or FAILED."""


def estimate_photograph_alignment(
    anchors: Sequence[AnchorPair],
    *,
    source_is_photograph: bool,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Allow a four-point homography only for an explicitly declared photograph."""


def warp_to_reference(
    cad_image: np.ndarray,
    alignment: AlignmentResult,
    *,
    output_size: tuple[int, int],
) -> np.ndarray:
    """Apply a verified controlled transform; reject FAILED alignment."""
```

```python
# primitive_ir_lib/geometry_metrics.py
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class GeometryMetrics:
    silhouette_iou: float
    chamfer_distance_normalized: float
    hausdorff_p95_normalized: float
    centroid_offset_x_ratio: float
    centroid_offset_y_ratio: float
    width_ratio_error: float
    height_ratio_error: float
    missing_edge_ratio: float
    extra_edge_ratio: float
    connected_component_difference: int


def normalize_outline(image: np.ndarray) -> np.ndarray:
    """Return a uint8 binary foreground mask with values 0 or 255."""


def compute_geometry_metrics(reference_mask: np.ndarray, cad_mask: np.ndarray) -> GeometryMetrics:
    """Compute the exact VS-T0 metric set; reject empty/shape-mismatched inputs."""
```

```python
# primitive_ir_lib/geometry_comparator.py
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import numpy as np

@dataclass(frozen=True)
class ComparisonArtifacts:
    aligned_cad: np.ndarray
    overlay: np.ndarray
    missing_mask: np.ndarray
    extra_mask: np.ndarray
    absolute_difference: np.ndarray


def create_comparison_artifacts(
    reference_image: np.ndarray,
    cad_image: np.ndarray,
    alignment: AlignmentResult,
) -> ComparisonArtifacts:
    """Create deterministic visual evidence after controlled alignment."""


def compare_metric_trend(
    current: GeometryMetrics,
    previous: GeometryMetrics | None,
    *,
    epsilon: float = 1e-6,
) -> str:
    """Return BASELINE, IMPROVED, REGRESSED, or UNCHANGED without a PASS verdict."""


def compare_curve_profile(reference_mask: np.ndarray, cad_mask: np.ndarray) -> dict[str, float]:
    """Return deterministic contour orientation/curvature evidence for review artifacts."""
```

```python
# cad_agent/geometry_comparison_run.py
from pathlib import Path


def run_geometry_comparison(
    *,
    run_id: str,
    region_id: str,
    reference_image: Path,
    cad_image: Path,
    reference_package_sha256: str,
    mutation_sha256: str,
    anchors_path: Path,
    output_dir: Path,
    previous_comparison_path: Path | None = None,
    source_is_photograph: bool = False,
) -> Path:
    """Write image evidence plus a validated geometry-comparison.json atomically."""
```

## Metric Definitions

Use these exact definitions so later tasks do not reinterpret scores:

```text
silhouette_iou = intersection(foreground) / union(foreground)
chamfer_distance_normalized = mean bidirectional edge distance / image diagonal
hausdorff_p95_normalized = max(p95(ref->cad), p95(cad->ref)) / image diagonal
centroid_offset_x_ratio = abs(cx_ref-cx_cad) / max(width_ref, 1)
centroid_offset_y_ratio = abs(cy_ref-cy_cad) / max(height_ref, 1)
width_ratio_error = abs(width_cad/width_ref - 1)
height_ratio_error = abs(height_cad/height_ref - 1)
missing_edge_ratio = ref_edge AND NOT dilated(cad_edge) / ref_edge_count
extra_edge_ratio = cad_edge AND NOT dilated(ref_edge) / cad_edge_count
connected_component_difference = abs(component_count_ref-component_count_cad)
```

Use a 1-pixel elliptical dilation kernel for missing/extra edge tolerance in synthetic tests. All distances are Euclidean distance-transform values. Empty masks are invalid comparator inputs, not perfect matches.

## Deterministic Trend Policy

The comparator does not collapse metrics to one weighted score. Trend uses a no-hidden-regression rule:

1. Define lower-is-better metrics as all except `silhouette_iou`; IoU is higher-is-better.
2. A metric improves when it changes by more than `epsilon` in the good direction.
3. A metric regresses when it changes by more than `epsilon` in the bad direction.
4. Return `REGRESSED` when any of these protected metrics regress: missing-edge ratio, extra-edge ratio, p95 Hausdorff, connected-component difference.
5. Otherwise return `IMPROVED` only when at least one metric improves and none regress.
6. Return `UNCHANGED` when all changes are within epsilon.
7. With no previous comparison return `BASELINE`.

This policy intentionally refuses to average away a newly missing feature.

---

### Task 1: Define deterministic alignment types and similarity transform

**Files:**
- Create: `primitive_ir_lib/geometry_alignment.py`
- Create: `primitive_ir_lib/tests/test_geometry_alignment.py`

**Interfaces:**
- Produces: `AnchorPair`, `AlignmentResult`, `estimate_similarity_alignment()`, `warp_to_reference()`.

- [ ] **Step 1: Write failing tests**

```python
def test_similarity_alignment_recovers_translation_rotation_and_uniform_scale() -> None:
    anchors = synthetic_similarity_anchor_pairs(
        translation=(12.0, -7.0), rotation_deg=2.0, scale=1.1
    )
    result = estimate_similarity_alignment(anchors)
    assert result.status == "ALIGNED"
    assert result.method == "VERIFIED_ANCHOR_SIMILARITY"
    assert result.residual_rms_px == pytest.approx(0.0, abs=1e-6)


def test_similarity_alignment_refuses_one_anchor() -> None:
    result = estimate_similarity_alignment([one_anchor()])
    assert result.status == "FAILED"
    assert "two" in " ".join(result.reasons).lower()


def test_similarity_alignment_refuses_nonuniform_scale() -> None:
    result = estimate_similarity_alignment(nonuniform_anchor_pairs())
    assert result.status == "FAILED"


def test_similarity_alignment_is_byte_for_byte_deterministic() -> None:
    assert estimate_similarity_alignment(anchors()) == estimate_similarity_alignment(anchors())
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic Umeyama similarity fit**

Use NumPy SVD with sorted input anchors. Reject duplicate IDs, duplicate point pairs, fewer than two unique pairs, collinear degeneracy when rotation/scale cannot be determined, reflection, scale outside range, rotation beyond limit, non-finite values, and residual above threshold. Do not use randomized RANSAC.

- [ ] **Step 4: Implement controlled warp and run GREEN**

Use `cv2.warpAffine` with `INTER_NEAREST` for masks and `INTER_LINEAR` for color images; border value is white for source-style images and zero for masks through an explicit parameter.

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_alignment.py primitive_ir_lib/tests/test_geometry_alignment.py
git commit -m "feat: add deterministic similarity alignment"
```

---

### Task 2: Add photograph-only four-point perspective correction

**Files:**
- Modify: `primitive_ir_lib/geometry_alignment.py`
- Modify: `primitive_ir_lib/tests/test_geometry_alignment.py`

- [ ] **Step 1: Add failing tests**

```python
def test_perspective_alignment_requires_photograph_flag_and_four_anchors() -> None:
    result = estimate_photograph_alignment(four_perspective_anchors(), source_is_photograph=False)
    assert result.status == "FAILED"


def test_perspective_alignment_accepts_exactly_four_non_collinear_anchors() -> None:
    result = estimate_photograph_alignment(four_perspective_anchors(), source_is_photograph=True)
    assert result.status == "ALIGNED"
    assert result.method == "APPROVED_PHOTOGRAPH_HOMOGRAPHY"


def test_perspective_alignment_refuses_five_anchors_and_collinear_points() -> None:
    assert estimate_photograph_alignment(five_anchors(), source_is_photograph=True).status == "FAILED"
    assert estimate_photograph_alignment(collinear_four(), source_is_photograph=True).status == "FAILED"
```

- [ ] **Step 2: Run RED, implement minimal deterministic homography, run GREEN**

Use `cv2.getPerspectiveTransform` on anchors sorted by ID. Reproject all four points and enforce residual threshold. No `findHomography`, RANSAC, or free-form warp.

- [ ] **Step 3: Commit**

```powershell
git diff --check
git add primitive_ir_lib/geometry_alignment.py primitive_ir_lib/tests/test_geometry_alignment.py
git commit -m "feat: add controlled photograph alignment"
```

---

### Task 3: Implement exact mask normalization and core metric set

**Files:**
- Create: `primitive_ir_lib/geometry_metrics.py`
- Create: `primitive_ir_lib/tests/test_geometry_metrics.py`

**Interfaces:**
- Produces: `GeometryMetrics`, `normalize_outline()`, `compute_geometry_metrics()`.

- [ ] **Step 1: Write failing metrics tests**

```python
def test_identical_masks_have_exact_identity_metrics() -> None:
    mask = rectangle_mask()
    metrics = compute_geometry_metrics(mask, mask.copy())
    assert metrics.silhouette_iou == 1.0
    assert metrics.chamfer_distance_normalized == 0.0
    assert metrics.hausdorff_p95_normalized == 0.0
    assert metrics.missing_edge_ratio == 0.0
    assert metrics.extra_edge_ratio == 0.0
    assert metrics.connected_component_difference == 0


def test_shifted_rectangle_reports_offset_and_distance() -> None:
    metrics = compute_geometry_metrics(rectangle_mask(), shifted_rectangle_mask(dx=10))
    assert metrics.silhouette_iou < 1.0
    assert metrics.centroid_offset_x_ratio > 0.0
    assert metrics.hausdorff_p95_normalized > 0.0


def test_missing_hole_changes_components_and_missing_edges() -> None:
    metrics = compute_geometry_metrics(mask_with_hole(), mask_without_hole())
    assert metrics.missing_edge_ratio > 0.0
    assert metrics.connected_component_difference != 0


def test_empty_mask_is_rejected() -> None:
    with pytest.raises(GeometryMetricError, match="empty"):
        compute_geometry_metrics(np.zeros((64, 64), np.uint8), rectangle_mask())
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement metrics exactly as specified**

Normalize all input to single-channel uint8. Use `cv2.Canny`, `cv2.distanceTransform`, `np.percentile(..., 95)`, `cv2.moments`, `cv2.boundingRect`, and `cv2.connectedComponents`. Round only when serializing; keep full precision internally.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_metrics.py primitive_ir_lib/tests/test_geometry_metrics.py
git commit -m "feat: compute deterministic geometry metrics"
```

---

### Task 4: Create overlays, difference masks, and curve-profile evidence

**Files:**
- Create: `primitive_ir_lib/geometry_comparator.py`
- Create: `primitive_ir_lib/tests/test_geometry_comparator.py`

**Interfaces:**
- Consumes: `AlignmentResult`, `GeometryMetrics`.
- Produces: `ComparisonArtifacts`, `create_comparison_artifacts()`, `compare_curve_profile()`.

- [ ] **Step 1: Write failing artifact tests**

```python
def test_artifacts_have_fixed_shapes_and_binary_masks() -> None:
    artifacts = create_comparison_artifacts(reference_image(), cad_image(), identity_alignment())
    assert artifacts.aligned_cad.shape == reference_image().shape
    assert set(np.unique(artifacts.missing_mask)) <= {0, 255}
    assert set(np.unique(artifacts.extra_mask)) <= {0, 255}


def test_missing_and_extra_masks_are_directional() -> None:
    artifacts = create_comparison_artifacts(mask_with_two_features(), mask_with_one_different_feature(), identity_alignment())
    assert np.count_nonzero(artifacts.missing_mask) > 0
    assert np.count_nonzero(artifacts.extra_mask) > 0


def test_curve_profile_detects_arc_flattening() -> None:
    evidence = compare_curve_profile(circular_arc_mask(), flattened_arc_mask())
    assert evidence["orientation_histogram_l1"] > 0.0
    assert evidence["curvature_profile_p95"] > 0.0
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement evidence images**

Overlay uses reference in one channel and aligned CAD in another, with a neutral white background. Difference masks are direct logical operations on normalized foreground masks. Do not set global matplotlib or UI state.

- [ ] **Step 4: Implement curve evidence**

Extract external contours, resample each contour at fixed normalized arc-length positions, compute tangent-angle histogram and discrete curvature. Sort contours by area and centroid. Return evidence only; do not add curve metrics to the VS-T0 contract in this task.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_comparator.py primitive_ir_lib/tests/test_geometry_comparator.py
git commit -m "feat: create geometry comparison evidence"
```

---

### Task 5: Implement deterministic candidate trend classification

**Files:**
- Modify: `primitive_ir_lib/geometry_comparator.py`
- Modify: `primitive_ir_lib/tests/test_geometry_comparator.py`

- [ ] **Step 1: Write failing trend tests**

```python
def test_first_candidate_is_baseline() -> None:
    assert compare_metric_trend(identity_metrics(), None) == "BASELINE"


def test_missing_feature_regression_cannot_be_averaged_away() -> None:
    previous = good_metrics()
    current = replace(previous, silhouette_iou=0.99, missing_edge_ratio=0.2)
    assert compare_metric_trend(current, previous) == "REGRESSED"


def test_nonregressing_metric_improvement_is_improved() -> None:
    previous = shifted_metrics()
    current = replace(previous, silhouette_iou=0.95, centroid_offset_x_ratio=0.01)
    assert compare_metric_trend(current, previous) == "IMPROVED"


def test_changes_within_epsilon_are_unchanged() -> None:
    assert compare_metric_trend(good_metrics(), nearly_same_metrics(), epsilon=1e-5) == "UNCHANGED"
```

- [ ] **Step 2: Run RED, implement the exact policy above, run GREEN**

- [ ] **Step 3: Commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_comparator.py primitive_ir_lib/tests/test_geometry_comparator.py
git commit -m "feat: classify geometry comparison trend"
```

---

### Task 6: Add hash-bound runner, evidence manifest, and contract output

**Files:**
- Create: `cad_agent/geometry_comparison_run.py`
- Create: `cad_agent/run_geometry_comparison.py`
- Create: `tests/test_geometry_comparison_run.py`

**Interfaces:**
- Consumes: comparator functions, `validate_visual_contract(..., contract="geometry_comparison")`, `sha256_file()`.
- Produces: validated `geometry-comparison.json` and image evidence.

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_writes_hash_bound_validated_comparison(tmp_path: Path) -> None:
    reference, cad, anchors = write_synthetic_inputs(tmp_path)
    output = run_geometry_comparison(
        run_id="RUN-VS-T2-001",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "comparison",
    )
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["cad_render_sha256"] == sha256_file(cad)
    assert payload["alignment"]["status"] == "ALIGNED"


def test_runner_records_failed_alignment_without_fake_metrics(tmp_path: Path) -> None:
    ...
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["alignment"]["status"] == "FAILED"
    assert payload["metrics"] == {}
    assert payload["trend"] == "BASELINE"


def test_runner_rejects_changed_input_before_publish(tmp_path: Path, monkeypatch) -> None:
    ...
    with pytest.raises(GeometryComparisonRunError, match="changed"):
        run_geometry_comparison(...)
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_geometry_comparison_run.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable snapshots and atomic artifact writing**

Write:

```text
aligned-cad.png
overlay.png
missing-mask.png
extra-mask.png
absolute-difference.png
curve-profile.json
geometry-comparison.json
comparison-manifest.json
```

Every artifact entry contains relative path, SHA-256, byte size, region ID, source/reference identity, CAD render identity, mutation identity, alignment method, and creation timestamp. Timestamp is metadata only and must not affect metrics or comparison ID.

Comparison ID is derived from the canonical hashes and region ID, not random state.

- [ ] **Step 4: Add CLI**

```powershell
python -m cad_agent.run_geometry_comparison --run-id RUN-VS-T2-001 --region-id SIDE-CABIN --reference reference.png --cad-render cad.png --reference-package-sha256 <sha> --mutation-sha256 <sha> --anchors anchors.json --output D:\runs\RUN-VS-T2-001\iterations\SIDE-CABIN\001\comparison
```

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest tests/test_geometry_comparison_run.py primitive_ir_lib/tests/test_geometry_alignment.py primitive_ir_lib/tests/test_geometry_metrics.py primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
git diff --check
git add cad_agent/geometry_comparison_run.py cad_agent/run_geometry_comparison.py tests/test_geometry_comparison_run.py
git commit -m "feat: add offline geometry comparison runner"
```

---

### Task 7: Add policy tests and canonical status

**Files:**
- Create: `tests/test_geometry_comparator_policy.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add failing policy tests**

Prove all of these:

- insufficient anchors produce `FAILED`, not a guessed transform;
- a reflection is rejected;
- a nonuniform scale is rejected;
- perspective is rejected unless `source_is_photograph=true` and exactly four approved anchors exist;
- no function or schema in VS-T2 contains `verdict`, `PASS`, repair operation, or publication authority;
- protected missing-feature metrics force `REGRESSED` even when IoU improves;
- repeated runs from identical bytes produce identical JSON excluding timestamp and identical image hashes.

- [ ] **Step 2: Run RED, implement minimal policy fixes, run GREEN**

```powershell
python -m pytest tests/test_geometry_comparator_policy.py tests/test_geometry_comparison_run.py primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
```

- [ ] **Step 3: Update docs truthfully**

Record:

```text
VS-T2 state: Partially verified — deterministic synthetic/offline comparator only.
real_data: NOT RUN.
OpenAI API: NOT RUN.
AutoCAD Mechanical: NOT RUN.
Comparator does not issue visual verdicts or repair instructions.
```

- [ ] **Step 4: Run the authoritative verifier**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Expected: exit `0`; record exact counts and final head SHA. Do not promote private/live gates.

- [ ] **Step 5: Final inspection and commit**

```powershell
git diff --check
git status --short
git diff --stat
git add docs/ARCHITECTURE.md docs/STATUS.md tests/test_documentation_contract.py tests/test_geometry_comparator_policy.py
git commit -m "docs: record VS-T2 geometry comparator gate"
```

## Acceptance Checklist

- [ ] Similarity alignment is deterministic and controlled.
- [ ] Perspective correction is photograph-only and four-anchor-only.
- [ ] Free-form deformation is absent.
- [ ] Failed alignment never emits fake zero-error metrics.
- [ ] All ten VS-T0 metrics are finite and reproducible.
- [ ] Missing/extra features, displacement, proportion, contour, and curve-profile changes are detected in synthetic tests.
- [ ] Candidate trend cannot average away a protected regression.
- [ ] Output validates through the integrated `geometry_comparison` contract.
- [ ] Comparator never produces visual verdict, repair, or publication authority.
- [ ] Focused tests and `scripts/verify.ps1` pass on the final head.
- [ ] Private, OpenAI API, and AutoCAD gates remain honestly `NOT RUN`.

## Execution Mode

Implement VS-T2 on its own branch/worktree. It may run in parallel with VS-T1 because primary write sets are disjoint except canonical documentation; each worker must defer `docs/ARCHITECTURE.md` and `docs/STATUS.md` updates to its own final commit, and the integration owner resolves those documentation changes without altering runtime evidence.
