# VS-T2 Geometry Comparator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Planning base SHA:** `2932febe5e95b042b202a767604d2143e6a6cc4f`

**Implementation base:** Create `task/vs-t2-geometry-comparator` from fresh integrated `main` and record that exact SHA before changing code.

**Goal:** Build a deterministic offline comparator that aligns source and CAD region evidence through approved anchors, writes reproducible overlays and difference masks, computes the ten VS-T0 metrics, and classifies improvement or regression without issuing a visual verdict.

**Architecture:** Image algorithms stay in `primitive_ir_lib`; `cad_agent` only snapshots files, binds hashes, validates contracts, and writes artifacts. Similarity alignment uses deterministic NumPy linear algebra. Perspective correction is limited to exactly four approved photograph anchors. Free-form deformation, model calls, AutoCAD calls, repair decisions, and publication are outside VS-T2.

**Tech Stack:** Windows, Python 3.11, OpenCV 5, NumPy 2, pytest, VS-T0 `geometry_comparison` contract.

## Global Constraints

- Comparator output is evidence, not visual `PASS`, repair, or publication authority.
- Anchor authority order is datum, confirmed driving-dimension anchor, stable CAD entity anchor, then high-confidence visual anchor.
- Similarity alignment permits translation, rotation, and uniform scale only.
- Perspective correction requires `source_is_photograph=true` and exactly four approved non-collinear pairs.
- Reject shear, nonuniform scale, reflections, thin-plate splines, optical flow, and free-form warping.
- Failed alignment is valid evidence: emit `alignment.status=FAILED`, `metrics={}`, `trend=BASELINE`, and no aligned image artifacts.
- Because the VS-T0 contract requires `alignment.transform_sha256`, a failed alignment uses the canonical SHA-256 of its closed failure record and input/config hashes; it must not claim that a transform exists.
- Bind outputs to reference package hash, exact reference image bytes, exact CAD render bytes, mutation hash, region ID, and alignment configuration.
- Metrics must be finite and deterministic for identical input bytes.
- Do not reduce acceptance to one average score.
- Source/CAD images and generated evidence stay outside Git; tests use generated images and temporary directories.
- Every task begins with a failing focused test and ends with focused tests, `git diff --check`, diff inspection, and a bounded commit.
- `real_data`, OpenAI API, and AutoCAD Mechanical remain `NOT RUN`.

---

## File Structure

### Comparator

- `primitive_ir_lib/geometry_alignment.py` — anchor validation, similarity fit, photograph-only homography, controlled warp.
- `primitive_ir_lib/geometry_metrics.py` — outline normalization and the ten VS-T0 metrics.
- `primitive_ir_lib/geometry_comparator.py` — overlays, masks, curve-profile evidence, and trend policy.

### Orchestration

- `cad_agent/geometry_comparison_run.py` — immutable snapshots, artifact hashes, atomic output, contract validation.
- `cad_agent/run_geometry_comparison.py` — CLI only.

### Tests

- `primitive_ir_lib/tests/geometry_test_helpers.py`
- `primitive_ir_lib/tests/test_geometry_alignment.py`
- `primitive_ir_lib/tests/test_geometry_metrics.py`
- `primitive_ir_lib/tests/test_geometry_comparator.py`
- `tests/test_geometry_comparison_run.py`
- `tests/test_geometry_comparator_policy.py`

## Stable Interfaces

```python
# primitive_ir_lib/geometry_alignment.py
from collections.abc import Sequence
from dataclasses import dataclass
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
    """Return a controlled similarity transform or FAILED."""


def estimate_photograph_alignment(
    anchors: Sequence[AnchorPair],
    *,
    source_is_photograph: bool,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Return a four-point photograph homography or FAILED."""


def warp_to_reference(
    cad_image: np.ndarray,
    alignment: AlignmentResult,
    *,
    output_size: tuple[int, int],
    is_mask: bool,
) -> np.ndarray:
    """Apply an ALIGNED transform with explicit interpolation/border policy."""
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
    """Return a uint8 foreground mask containing only 0 and 255."""


def compute_geometry_metrics(reference_mask: np.ndarray, cad_mask: np.ndarray) -> GeometryMetrics:
    """Compute the exact VS-T0 metrics or reject invalid masks."""
```

```python
# primitive_ir_lib/geometry_comparator.py
from dataclasses import dataclass
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
    """Create deterministic evidence after controlled alignment."""


def compare_metric_trend(
    current: GeometryMetrics,
    previous: GeometryMetrics | None,
    *,
    epsilon: float = 1e-6,
) -> str:
    """Return BASELINE, IMPROVED, REGRESSED, or UNCHANGED."""


def compare_curve_profile(reference_mask: np.ndarray, cad_mask: np.ndarray) -> dict[str, float]:
    """Return deterministic contour orientation and curvature evidence."""
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
    """Write validated geometry-comparison.json and applicable evidence atomically."""
```

## Exact Metric Definitions

```text
silhouette_iou = intersection(foreground) / union(foreground)
chamfer_distance_normalized = mean bidirectional edge distance / image diagonal
hausdorff_p95_normalized = max(p95(reference-to-cad), p95(cad-to-reference)) / image diagonal
centroid_offset_x_ratio = abs(cx_reference-cx_cad) / max(width_reference, 1)
centroid_offset_y_ratio = abs(cy_reference-cy_cad) / max(height_reference, 1)
width_ratio_error = abs(width_cad/width_reference - 1)
height_ratio_error = abs(height_cad/height_reference - 1)
missing_edge_ratio = count(reference_edge AND NOT dilated(cad_edge)) / reference_edge_count
extra_edge_ratio = count(cad_edge AND NOT dilated(reference_edge)) / cad_edge_count
connected_component_difference = abs(foreground_component_count_reference-foreground_component_count_cad)
```

Use a one-pixel elliptical dilation kernel for missing/extra edge tolerance. Build edge maps with Canny. For each direction, compute distance to the other edge set using `cv2.distanceTransform(cv2.bitwise_not(other_edge))`. Empty silhouettes or empty edge sets are invalid metric inputs, not perfect matches. `connected_component_difference` counts disconnected foreground features; an internal hole affects edge metrics but does not by itself change foreground component count.

## Deterministic Trend Policy

1. IoU is higher-is-better; all other metrics are lower-is-better.
2. A change smaller than or equal to `epsilon` is unchanged.
3. Any regression in missing-edge ratio, extra-edge ratio, p95 Hausdorff, or connected-component difference returns `REGRESSED`.
4. Otherwise any regressing metric returns `REGRESSED`.
5. Return `IMPROVED` only when at least one metric improves and none regress.
6. Return `UNCHANGED` when all metrics remain within epsilon.
7. Return `BASELINE` when there is no previous comparison.
8. A previous comparison may be used only when its `region_id` and `reference_package_sha256` match the current run; otherwise refuse it.

## Synthetic Test Helpers

Create `primitive_ir_lib/tests/geometry_test_helpers.py`:

```python
from pathlib import Path
import cv2
import json
import numpy as np
from primitive_ir_lib.geometry_alignment import AnchorPair, AlignmentResult


def rectangle_mask(*, dx: int = 0, dy: int = 0) -> np.ndarray:
    image = np.zeros((160, 240), dtype=np.uint8)
    cv2.rectangle(image, (40 + dx, 45 + dy), (190 + dx, 120 + dy), 255, -1)
    return image


def two_component_mask() -> np.ndarray:
    image = rectangle_mask()
    cv2.circle(image, (215, 35), 12, 255, -1)
    return image


def single_component_mask() -> np.ndarray:
    return rectangle_mask()


def identity_anchor_pairs() -> list[AnchorPair]:
    return [
        AnchorPair("A", (40.0, 45.0), (40.0, 45.0), "DATUM", 1.0),
        AnchorPair("B", (190.0, 120.0), (190.0, 120.0), "DATUM", 1.0),
        AnchorPair("C", (40.0, 120.0), (40.0, 120.0), "DATUM", 1.0),
    ]


def identity_alignment() -> AlignmentResult:
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        anchor_ids=("A", "B", "C"),
        residual_rms_px=0.0,
        reasons=(),
    )


def write_mask(path: Path, mask: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), mask)
    return path


def write_anchor_file(path: Path, anchors: list[AnchorPair]) -> Path:
    payload = {
        "schema_version": "geometry-anchors-1.0",
        "anchors": [
            {
                "anchor_id": item.anchor_id,
                "reference_px": list(item.reference_px),
                "cad_px": list(item.cad_px),
                "authority": item.authority,
                "confidence": item.confidence,
            }
            for item in anchors
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path
```

Tasks add deterministic helpers for transformed, reflected, nonuniform, perspective, and curve cases in this same file before importing them.

---

### Task 1: Deterministic Similarity Alignment

**Files:**
- Create: `primitive_ir_lib/geometry_alignment.py`
- Create: `primitive_ir_lib/tests/geometry_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_geometry_alignment.py`

- [ ] **Step 1: Write failing tests**

```python
def test_similarity_fit_recovers_controlled_transform() -> None:
    anchors = synthetic_similarity_anchor_pairs(
        translation=(12.0, -7.0), rotation_deg=2.0, scale=1.1
    )
    result = estimate_similarity_alignment(anchors)
    assert result.status == "ALIGNED"
    assert result.method == "VERIFIED_ANCHOR_SIMILARITY"
    assert result.residual_rms_px == pytest.approx(0.0, abs=1e-6)


def test_similarity_fit_refuses_one_anchor() -> None:
    result = estimate_similarity_alignment([identity_anchor_pairs()[0]])
    assert result.status == "FAILED"
    assert "two" in " ".join(result.reasons).lower()


def test_similarity_fit_refuses_reflection_and_three_point_nonuniform_mapping() -> None:
    assert estimate_similarity_alignment(reflected_anchor_pairs()).status == "FAILED"
    assert estimate_similarity_alignment(nonuniform_three_anchor_pairs()).status == "FAILED"


def test_similarity_fit_is_deterministic() -> None:
    source = identity_anchor_pairs()
    assert estimate_similarity_alignment(source) == estimate_similarity_alignment(source)
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic similarity fit**

Sort anchors by ID. Use NumPy SVD. Two distinct pairs are sufficient for a similarity fit; with three or more pairs reject rank-deficient source geometry. Reject duplicate IDs, duplicate point pairs, reflection, nonuniform residual pattern, non-finite values, scale/rotation limits, and RMS residual above threshold. Do not use RANSAC.

- [ ] **Step 4: Implement controlled warp**

Use `cv2.warpAffine`. Masks use `INTER_NEAREST` and zero border. Color images use `INTER_LINEAR` and white border.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_alignment.py primitive_ir_lib/tests/geometry_test_helpers.py primitive_ir_lib/tests/test_geometry_alignment.py
git commit -m "feat: add deterministic similarity alignment"
```

---

### Task 2: Photograph-Only Perspective Correction

**Files:**
- Modify: `primitive_ir_lib/geometry_alignment.py`
- Modify: `primitive_ir_lib/tests/geometry_test_helpers.py`
- Modify: `primitive_ir_lib/tests/test_geometry_alignment.py`

- [ ] **Step 1: Write failing tests**

```python
def test_homography_requires_photograph_flag() -> None:
    result = estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=False
    )
    assert result.status == "FAILED"


def test_homography_accepts_exactly_four_noncollinear_anchors() -> None:
    result = estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=True
    )
    assert result.status == "ALIGNED"
    assert result.method == "APPROVED_PHOTOGRAPH_HOMOGRAPHY"


def test_homography_refuses_wrong_count_and_collinearity() -> None:
    assert estimate_photograph_alignment(
        five_perspective_anchors(), source_is_photograph=True
    ).status == "FAILED"
    assert estimate_photograph_alignment(
        four_collinear_anchors(), source_is_photograph=True
    ).status == "FAILED"
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic four-point homography**

Use `cv2.getPerspectiveTransform` on anchors sorted by ID. Reproject all points and enforce residual threshold. Do not use `findHomography`, RANSAC, or free-form warping.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_alignment.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_alignment.py primitive_ir_lib/tests/geometry_test_helpers.py primitive_ir_lib/tests/test_geometry_alignment.py
git commit -m "feat: add controlled photograph alignment"
```

---

### Task 3: Normalize Masks and Compute the Ten Metrics

**Files:**
- Create: `primitive_ir_lib/geometry_metrics.py`
- Modify: `primitive_ir_lib/tests/geometry_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_geometry_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
def test_identical_masks_have_identity_metrics() -> None:
    mask = rectangle_mask()
    metrics = compute_geometry_metrics(mask, mask.copy())
    assert metrics.silhouette_iou == 1.0
    assert metrics.chamfer_distance_normalized == 0.0
    assert metrics.hausdorff_p95_normalized == 0.0
    assert metrics.missing_edge_ratio == 0.0
    assert metrics.extra_edge_ratio == 0.0
    assert metrics.connected_component_difference == 0


def test_shifted_rectangle_reports_distance_and_centroid_offset() -> None:
    metrics = compute_geometry_metrics(rectangle_mask(), rectangle_mask(dx=10))
    assert metrics.silhouette_iou < 1.0
    assert metrics.centroid_offset_x_ratio > 0.0
    assert metrics.hausdorff_p95_normalized > 0.0


def test_missing_disconnected_feature_changes_components_and_edges() -> None:
    metrics = compute_geometry_metrics(two_component_mask(), single_component_mask())
    assert metrics.missing_edge_ratio > 0.0
    assert metrics.connected_component_difference == 1


def test_empty_mask_is_rejected() -> None:
    empty = np.zeros((64, 64), dtype=np.uint8)
    with pytest.raises(GeometryMetricError, match="empty"):
        compute_geometry_metrics(empty, rectangle_mask())
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement exact metrics**

Normalize to single-channel uint8. Validate equal shapes. Extract Canny edges, invert the other edge map before `cv2.distanceTransform`, select distances only at source edge pixels, and use `np.percentile(distances, 95)`. Use `cv2.moments`, `cv2.boundingRect`, and `cv2.connectedComponents` on filled foreground masks. Keep full precision internally; round only during JSON serialization.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_metrics.py primitive_ir_lib/tests/geometry_test_helpers.py primitive_ir_lib/tests/test_geometry_metrics.py
git commit -m "feat: compute deterministic geometry metrics"
```

---

### Task 4: Build Overlays, Difference Masks, and Curve Evidence

**Files:**
- Create: `primitive_ir_lib/geometry_comparator.py`
- Modify: `primitive_ir_lib/tests/geometry_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_geometry_comparator.py`

- [ ] **Step 1: Write failing tests**

```python
def test_artifacts_have_fixed_shapes_and_binary_masks() -> None:
    reference = cv2.cvtColor(rectangle_mask(), cv2.COLOR_GRAY2BGR)
    cad = reference.copy()
    artifacts = create_comparison_artifacts(reference, cad, identity_alignment())
    assert artifacts.aligned_cad.shape == reference.shape
    assert set(np.unique(artifacts.missing_mask)) <= {0, 255}
    assert set(np.unique(artifacts.extra_mask)) <= {0, 255}


def test_missing_and_extra_masks_are_directional() -> None:
    reference = cv2.cvtColor(two_component_mask(), cv2.COLOR_GRAY2BGR)
    cad_mask = rectangle_mask(dx=5)
    cad = cv2.cvtColor(cad_mask, cv2.COLOR_GRAY2BGR)
    artifacts = create_comparison_artifacts(reference, cad, identity_alignment())
    assert np.count_nonzero(artifacts.missing_mask) > 0
    assert np.count_nonzero(artifacts.extra_mask) > 0


def test_curve_profile_detects_arc_flattening() -> None:
    evidence = compare_curve_profile(circular_arc_mask(), flattened_arc_mask())
    assert evidence["orientation_histogram_l1"] > 0.0
    assert evidence["curvature_profile_p95"] > 0.0
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement artifacts and curve evidence**

Overlay reference and aligned CAD in separate channels on a white background. Missing/extra masks are directional logical operations. For curves, sort contours by area/centroid, resample at fixed normalized arc-length positions, then compute tangent-angle histogram distance and discrete curvature p95.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py primitive_ir_lib/tests/test_geometry_metrics.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_comparator.py primitive_ir_lib/tests/geometry_test_helpers.py primitive_ir_lib/tests/test_geometry_comparator.py
git commit -m "feat: create geometry comparison evidence"
```

---

### Task 5: Classify Deterministic Candidate Trend

**Files:**
- Modify: `primitive_ir_lib/geometry_comparator.py`
- Modify: `primitive_ir_lib/tests/geometry_test_helpers.py`
- Modify: `primitive_ir_lib/tests/test_geometry_comparator.py`

- [ ] **Step 1: Write failing tests**

```python
def test_first_candidate_is_baseline() -> None:
    assert compare_metric_trend(identity_metrics(), None) == "BASELINE"


def test_missing_feature_regression_cannot_be_averaged_away() -> None:
    previous = good_metrics()
    current = replace(previous, silhouette_iou=0.99, missing_edge_ratio=0.2)
    assert compare_metric_trend(current, previous) == "REGRESSED"


def test_nonregressing_improvement_is_improved() -> None:
    previous = shifted_metrics()
    current = replace(previous, silhouette_iou=0.95, centroid_offset_x_ratio=0.01)
    assert compare_metric_trend(current, previous) == "IMPROVED"


def test_changes_within_epsilon_are_unchanged() -> None:
    assert compare_metric_trend(
        good_metrics(), nearly_same_metrics(), epsilon=1e-5
    ) == "UNCHANGED"
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement the exact trend policy**

Use field-by-field comparison with no weighted average. Protected missing/extra/topology regression wins over improvements elsewhere.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/geometry_comparator.py primitive_ir_lib/tests/geometry_test_helpers.py primitive_ir_lib/tests/test_geometry_comparator.py
git commit -m "feat: classify geometry comparison trend"
```

---

### Task 6: Add the Hash-Bound Runner and CLI

**Files:**
- Create: `cad_agent/geometry_comparison_run.py`
- Create: `cad_agent/run_geometry_comparison.py`
- Create: `tests/test_geometry_comparison_run.py`

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_writes_validated_hash_bound_comparison(tmp_path: Path) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", identity_anchor_pairs())
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
    assert (output.parent / "overlay.png").is_file()


def test_runner_records_failed_alignment_without_aligned_artifacts(tmp_path: Path) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", [identity_anchor_pairs()[0]])
    output = run_geometry_comparison(
        run_id="RUN-VS-T2-002",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "failed-comparison",
    )
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["alignment"]["status"] == "FAILED"
    assert payload["metrics"] == {}
    assert payload["trend"] == "BASELINE"
    assert not (output.parent / "overlay.png").exists()
    assert (output.parent / "alignment-failure.json").is_file()


def test_runner_rejects_source_changed_during_run(tmp_path: Path, monkeypatch) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", identity_anchor_pairs())
    monkeypatch.setattr(
        "cad_agent.geometry_comparison_run._verify_unchanged",
        lambda path, expected_sha256: False,
    )
    with pytest.raises(GeometryComparisonRunError, match="changed"):
        run_geometry_comparison(
            run_id="RUN-VS-T2-003",
            region_id="SIDE-CABIN",
            reference_image=reference,
            cad_image=cad,
            reference_package_sha256="5" * 64,
            mutation_sha256="3" * 64,
            anchors_path=anchors,
            output_dir=tmp_path / "changed-input",
        )
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest tests/test_geometry_comparison_run.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable snapshots and atomic output**

For `ALIGNED`, write:

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

For `FAILED`, write only:

```text
alignment-failure.json
geometry-comparison.json
comparison-manifest.json
```

Manifest entries contain relative path, SHA-256, byte size, region, reference image/package identity, CAD render identity, mutation identity, alignment method/status, and timestamp. Timestamp must not affect comparison ID or metrics. Derive comparison ID from canonical hashes plus region ID. Derive `transform_sha256` from the matrix when aligned, or the closed failure record when failed.

When `previous_comparison_path` is supplied, validate it through the VS-T0 contract and require matching region/reference package before calculating trend.

- [ ] **Step 4: Add CLI**

```powershell
python -m cad_agent.run_geometry_comparison --run-id RUN-VS-T2-001 --region-id SIDE-CABIN --reference reference.png --cad-render cad.png --reference-package-sha256 5555555555555555555555555555555555555555555555555555555555555555 --mutation-sha256 3333333333333333333333333333333333333333333333333333333333333333 --anchors anchors.json --output D:\runs\RUN-VS-T2-001\iterations\SIDE-CABIN\001\comparison
```

- [ ] **Step 5: Verify GREEN and commit**

```powershell
python -m pytest tests/test_geometry_comparison_run.py primitive_ir_lib/tests/test_geometry_alignment.py primitive_ir_lib/tests/test_geometry_metrics.py primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
git diff --check
git add cad_agent/geometry_comparison_run.py cad_agent/run_geometry_comparison.py tests/test_geometry_comparison_run.py
git commit -m "feat: add offline geometry comparison runner"
```

---

### Task 7: Enforce Policy and Record Status

**Files:**
- Create: `tests/test_geometry_comparator_policy.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add policy tests**

Prove:

- insufficient anchors produce `FAILED`;
- reflection and three-anchor nonuniform mappings are rejected;
- perspective requires photograph flag and exactly four approved anchors;
- failed alignment emits no fake metrics or aligned image artifacts;
- VS-T2 exposes no verdict, repair operation, or publication authority;
- protected missing-feature regression forces `REGRESSED` even when IoU improves;
- mismatched previous region/reference identity is rejected;
- identical input bytes produce identical JSON excluding timestamp and identical evidence hashes.

- [ ] **Step 2: Run focused verification**

```powershell
python -m pytest tests/test_geometry_comparator_policy.py tests/test_geometry_comparison_run.py primitive_ir_lib/tests/test_geometry_comparator.py -q -p no:cacheprovider
```

- [ ] **Step 3: Update canonical documentation**

Record exactly:

```text
VS-T2: Partially verified — deterministic synthetic/offline comparator only.
real_data: NOT RUN.
OpenAI API: NOT RUN.
AutoCAD Mechanical: NOT RUN.
Comparator does not issue visual verdicts or repair instructions.
```

- [ ] **Step 4: Run the authoritative verifier**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Record final head SHA and exact counts. Do not promote unavailable gates.

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
- [ ] Failed alignment emits no fake metrics or aligned images.
- [ ] All ten VS-T0 metrics are finite and reproducible.
- [ ] Synthetic tests detect missing/extra features, displacement, proportion, contour, and curve-profile changes.
- [ ] Component tests use disconnected features rather than holes.
- [ ] Candidate trend cannot average away a protected regression.
- [ ] Output validates through the integrated `geometry_comparison` contract.
- [ ] Comparator never produces verdict, repair, or publication authority.
- [ ] Focused tests and `scripts/verify.ps1` pass on final head.
- [ ] Private, OpenAI API, and AutoCAD gates remain `NOT RUN`.

## Execution Mode

Run VS-T2 in an isolated branch/worktree. It may run in parallel with VS-T1 because runtime write sets are disjoint. The integration owner resolves final documentation changes and one reviewer evaluates both before VS-T6 consumes them.
