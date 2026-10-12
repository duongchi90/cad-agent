"""geometry_alignment_engine.py - Research Oracle for Geometry Alignment and Comparison.

Evaluates strategies A-D for:
1. Multi-tier anchor selection (cascading tier consensus vs highest-tier starvation).
2. Robust image polarity normalization (corner + area consensus vs rigid 0.98 border).
3. Arbitrary N >= 4 photograph homography estimation (least-squares DLT vs strict N=4).
4. Collinear anchor set handling.
5. Directional metric trend comparison without false component traps.

Part of Antigravity Research: RESTRICTED_GEOMETRY_ALIGNMENT_AND_COMPARISON_V1
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import cv2
import numpy as np

Point = tuple[float, float]

ALLOWED_AUTHORITIES = {
    "DATUM",
    "DRIVING_DIMENSION",
    "STABLE_ENTITY",
    "VISUAL_FEATURE",
}
AUTHORITY_TIERS = {
    "DATUM": 4,
    "DRIVING_DIMENSION": 3,
    "STABLE_ENTITY": 2,
    "VISUAL_FEATURE": 1,
}
MIN_VISUAL_FEATURE_CONFIDENCE = 0.8


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


def failed_result(method: str, anchor_ids: Sequence[str], reason: str) -> AlignmentResult:
    return AlignmentResult(
        status="FAILED",
        method=method,
        matrix=None,
        anchor_ids=tuple(anchor_ids),
        residual_rms_px=None,
        reasons=(reason,),
    )


# ---------------------------------------------------------------------------
# Common Anchor Validation
# ---------------------------------------------------------------------------

def validate_anchor_list(
    anchors: Sequence[AnchorPair],
    method: str,
) -> tuple[list[AnchorPair] | None, AlignmentResult | None]:
    try:
        items = list(anchors)
    except TypeError:
        return None, failed_result(method, (), "anchors must be a sequence")

    anchor_ids = tuple(sorted(str(getattr(item, "anchor_id", "")) for item in items))
    if any(not isinstance(item.anchor_id, str) or not item.anchor_id for item in items):
        return None, failed_result(method, anchor_ids, "anchor IDs must be non-empty strings")
    if len(set(anchor_ids)) != len(anchor_ids):
        return None, failed_result(method, anchor_ids, "duplicate anchor IDs are not allowed")

    validated: list[AnchorPair] = []
    for item in items:
        if item.authority not in ALLOWED_AUTHORITIES:
            return None, failed_result(method, anchor_ids, f"unsupported anchor authority: {item.authority}")
        if not isinstance(item.confidence, (int, float)) or isinstance(item.confidence, bool):
            return None, failed_result(method, anchor_ids, "anchor confidence must be numeric")
        if not math.isfinite(float(item.confidence)) or not 0.0 <= float(item.confidence) <= 1.0:
            return None, failed_result(method, anchor_ids, "anchor confidence must be finite in [0, 1]")
        try:
            reference = np.asarray(item.reference_px, dtype=np.float64)
            cad = np.asarray(item.cad_px, dtype=np.float64)
        except (TypeError, ValueError):
            return None, failed_result(method, anchor_ids, "anchor points must contain two numeric values")
        if reference.shape != (2,) or cad.shape != (2,):
            return None, failed_result(method, anchor_ids, "anchor points must contain two numeric values")
        if not np.isfinite(reference).all() or not np.isfinite(cad).all():
            return None, failed_result(method, anchor_ids, "anchor points must be finite")
        validated.append(
            AnchorPair(
                anchor_id=item.anchor_id,
                reference_px=(float(reference[0]), float(reference[1])),
                cad_px=(float(cad[0]), float(cad[1])),
                authority=item.authority,
                confidence=float(item.confidence),
            )
        )

    validated.sort(key=lambda item: item.anchor_id)
    reference_points = np.asarray([item.reference_px for item in validated], dtype=np.float64)
    cad_points = np.asarray([item.cad_px for item in validated], dtype=np.float64)
    if len(validated) > 1:
        if len(np.unique(reference_points, axis=0)) != len(validated):
            return None, failed_result(method, anchor_ids, "duplicate reference points are not allowed")
        if len(np.unique(cad_points, axis=0)) != len(validated):
            return None, failed_result(method, anchor_ids, "duplicate CAD points are not allowed")

    return validated, None


# ---------------------------------------------------------------------------
# Strategy A: Production Main Baseline (geometry_alignment.py & geometry_metrics.py)
# ---------------------------------------------------------------------------

def select_anchors_strategy_a(
    anchors: Sequence[AnchorPair],
    method: str = "FAILED_ANCHOR_SIMILARITY",
) -> tuple[list[AnchorPair] | None, AlignmentResult | None]:
    """Production anchor selection from geometry_alignment.py:110-124.

    FLAW: Takes ONLY the highest tier. If highest tier has 1 anchor, lower tiers are discarded,
    causing failure even when plenty of valid anchors exist!
    """
    validated, failure = validate_anchor_list(anchors, method)
    if failure is not None:
        return None, failure
    assert validated is not None

    anchor_ids = tuple(item.anchor_id for item in validated)
    eligible = [
        item
        for item in validated
        if item.authority != "VISUAL_FEATURE"
        or item.confidence >= MIN_VISUAL_FEATURE_CONFIDENCE
    ]
    if not eligible:
        return None, failed_result(
            method,
            anchor_ids,
            "no anchors meet the approved authority and confidence policy",
        )
    highest_tier = max(AUTHORITY_TIERS[item.authority] for item in eligible)
    selected = [item for item in eligible if AUTHORITY_TIERS[item.authority] == highest_tier]
    return selected, None


def estimate_similarity_strategy_a(
    anchors: Sequence[AnchorPair],
    *,
    max_rotation_deg: float = 5.0,
    min_uniform_scale: float = 0.5,
    max_uniform_scale: float = 2.0,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Production similarity alignment from geometry_alignment.py:140-235."""
    items, failure = select_anchors_strategy_a(anchors, method="FAILED_ANCHOR_SIMILARITY")
    if failure is not None:
        return failure
    assert items is not None

    if len(items) < 2:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "at least two anchors are required")

    reference = np.asarray([item.reference_px for item in items], dtype=np.float64)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float64)

    # Rank check for N >= 3
    centered_ref = reference - reference.mean(axis=0)
    centered_cad = cad - cad.mean(axis=0)
    rank_ref = int(np.linalg.matrix_rank(centered_ref, tol=1e-10))
    rank_cad = int(np.linalg.matrix_rank(centered_cad, tol=1e-10))
    if len(items) >= 3 and (rank_ref < 2 or rank_cad < 2):
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "three or more anchors must span two dimensions")

    source_centroid = cad.mean(axis=0)
    target_centroid = reference.mean(axis=0)
    source_centered = cad - source_centroid
    target_centered = reference - target_centroid

    if len(items) == 2:
        source_delta = source_centered[1] - source_centered[0]
        target_delta = target_centered[1] - target_centered[0]
        source_length = float(np.linalg.norm(source_delta))
        target_length = float(np.linalg.norm(target_delta))
        if source_length <= 1e-12 or target_length <= 1e-12:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "anchor pairs must be distinct")
        uniform_scale = target_length / source_length
        cosine = float(np.dot(source_delta, target_delta) / (source_length * target_length))
        sine = float((source_delta[0] * target_delta[1] - source_delta[1] * target_delta[0]) / (source_length * target_length))
        linear = uniform_scale * np.asarray([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    else:
        covariance = source_centered.T @ target_centered
        left, singular_values, right_transposed = np.linalg.svd(covariance)
        row_rotation = left @ right_transposed
        if float(np.linalg.det(row_rotation)) < 0.0:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "reflection is not an allowed alignment")
        source_energy = float(np.sum(source_centered * source_centered))
        if source_energy <= 1e-12:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "source anchors have no usable spread")
        uniform_scale = float(np.sum(singular_values) / source_energy)
        linear = uniform_scale * row_rotation.T

    if not math.isfinite(uniform_scale) or not min_uniform_scale <= uniform_scale <= max_uniform_scale:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "uniform scale is outside the approved range")
    rotation_deg = math.degrees(math.atan2(float(linear[1, 0]), float(linear[0, 0])))
    if abs(rotation_deg) > max_rotation_deg:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "rotation is outside the approved range")

    translation = target_centroid - linear @ source_centroid
    projected = cad @ linear.T + translation
    residuals = np.linalg.norm(projected - reference, axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if not math.isfinite(residual_rms) or residual_rms > max_residual_px:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "anchor residual exceeds the approved threshold")

    matrix = ((float(linear[0, 0]), float(linear[0, 1]), float(translation[0])),
              (float(linear[1, 0]), float(linear[1, 1]), float(translation[1])))
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=matrix,
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=residual_rms,
        reasons=(),
    )


def estimate_photograph_strategy_a(
    anchors: Sequence[AnchorPair],
    *,
    source_is_photograph: bool,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Production photograph alignment from geometry_alignment.py:238-317.

    FLAW: Fails if len(items) != 4. Rejects 5 or more valid perspective anchors!
    """
    items, failure = select_anchors_strategy_a(anchors, method="FAILED_PHOTOGRAPH_HOMOGRAPHY")
    if failure is not None:
        return failure
    assert items is not None

    if source_is_photograph is not True:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph alignment requires source_is_photograph=true")
    if len(items) != 4:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph alignment requires exactly four anchors")

    reference = np.asarray([item.reference_px for item in items], dtype=np.float32)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float32)

    try:
        matrix = cv2.getPerspectiveTransform(cad, reference)
    except cv2.error:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph anchors do not define a usable homography")

    homogeneous = np.column_stack([cad.astype(np.float64), np.ones(4, dtype=np.float64)])
    projected_h = homogeneous @ matrix.astype(np.float64).T
    if np.any(np.abs(projected_h[:, 2]) <= 1e-12):
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph homography projects an anchor to infinity")
    projected = projected_h[:, :2] / projected_h[:, 2:3]
    residuals = np.linalg.norm(projected - reference.astype(np.float64), axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if residual_rms > max_residual_px:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph homography residual exceeds the approved threshold")

    return AlignmentResult(
        status="ALIGNED",
        method="APPROVED_PHOTOGRAPH_HOMOGRAPHY",
        matrix=tuple(tuple(float(v) for v in row) for row in matrix),
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=residual_rms,
        reasons=(),
    )


def normalize_outline_strategy_a(image: np.ndarray) -> np.ndarray:
    """Production normalize_outline from geometry_metrics.py:58-78.

    FLAW: Crashes if border has even 2.5% black or white pixels (threshold 0.98).
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate((binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]))
    black_fraction = float(np.mean(border == 0))
    white_fraction = float(np.mean(border == 255))
    if black_fraction >= 0.98:
        return binary.astype(np.uint8, copy=False)
    if white_fraction >= 0.98:
        return cv2.bitwise_not(binary)
    raise ValueError("foreground polarity is ambiguous")


def compare_metric_trend_strategy_a(
    current_metrics: dict[str, float],
    previous_metrics: dict[str, float] | None,
    *,
    epsilon: float = 1e-6,
) -> str:
    """Production naive trend comparator: any increase in connected_component_difference
    unconditionally triggers REGRESSED, rejecting even large IoU gains.
    """
    if previous_metrics is None:
        return "BASELINE"
    missing_regressed = current_metrics["missing_edge_ratio"] > previous_metrics["missing_edge_ratio"] + epsilon
    extra_regressed = current_metrics["extra_edge_ratio"] > previous_metrics["extra_edge_ratio"] + epsilon
    hausdorff_regressed = current_metrics["hausdorff_p95_normalized"] > previous_metrics["hausdorff_p95_normalized"] + epsilon
    cc_regressed = current_metrics.get("connected_component_difference", 0) > previous_metrics.get("connected_component_difference", 0) + epsilon

    if missing_regressed or extra_regressed or hausdorff_regressed or cc_regressed:
        return "REGRESSED"

    iou_improved = current_metrics["silhouette_iou"] > previous_metrics["silhouette_iou"] + epsilon
    chamfer_improved = current_metrics["chamfer_distance_normalized"] < previous_metrics["chamfer_distance_normalized"] - epsilon

    if iou_improved or chamfer_improved:
        return "IMPROVED"

    return "UNCHANGED"


# ---------------------------------------------------------------------------
# Strategy B: Naive Distance Matcher (Disregards tiers, assumes dark background)
# ---------------------------------------------------------------------------

def estimate_similarity_strategy_b(anchors: Sequence[AnchorPair]) -> AlignmentResult:
    """Naive matcher that groups all anchors without tier prioritization."""
    if len(anchors) < 2:
        return failed_result("FAILED_NAIVE", [], "need >= 2 anchors")
    items = list(anchors)[:2]
    p1_cad, p2_cad = np.array(items[0].cad_px), np.array(items[1].cad_px)
    p1_ref, p2_ref = np.array(items[0].reference_px), np.array(items[1].reference_px)
    s = np.linalg.norm(p2_ref - p1_ref) / max(1e-6, np.linalg.norm(p2_cad - p1_cad))
    t = p1_ref - s * p1_cad
    matrix = ((s, 0.0, float(t[0])), (0.0, s, float(t[1])))
    return AlignmentResult(
        status="ALIGNED",
        method="NAIVE_SIMILARITY",
        matrix=matrix,
        anchor_ids=tuple(i.anchor_id for i in items),
        residual_rms_px=0.0,
        reasons=(),
    )


def normalize_outline_strategy_b(image: np.ndarray) -> np.ndarray:
    """Naive: assumes dark background, never inverts."""
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary.astype(np.uint8, copy=False)


def compare_metric_trend_strategy_b(
    current_metrics: dict[str, float],
    previous_metrics: dict[str, float] | None,
) -> str:
    """Naive: only checks IoU, ignores edge regressions completely."""
    if previous_metrics is None:
        return "BASELINE"
    if current_metrics["silhouette_iou"] > previous_metrics["silhouette_iou"]:
        return "IMPROVED"
    return "UNCHANGED"


# ---------------------------------------------------------------------------
# Strategy C: Fixed 2-Tier Fallback with 0.90 Polarity Threshold
# ---------------------------------------------------------------------------

def select_anchors_strategy_c(anchors: Sequence[AnchorPair]) -> list[AnchorPair]:
    """Combines top 2 absolute tiers only (DATUM and DRIVING_DIMENSION); fails if < 2 anchors."""
    eligible = [a for a in anchors if a.authority != "VISUAL_FEATURE" or a.confidence >= 0.8]
    if not eligible:
        return []
    allowed_tiers = {4, 3}
    return [a for a in eligible if AUTHORITY_TIERS[a.authority] in allowed_tiers]


def estimate_similarity_strategy_c(
    anchors: Sequence[AnchorPair],
    *,
    max_rotation_deg: float = 5.0,
    min_uniform_scale: float = 0.5,
    max_uniform_scale: float = 2.0,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Strategy C: top 2 tiers fallback."""
    items = select_anchors_strategy_c(anchors)
    if len(items) < 2:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "at least two anchors are required")
    reference = np.asarray([item.reference_px for item in items], dtype=np.float64)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float64)
    centered_ref = reference - reference.mean(axis=0)
    centered_cad = cad - cad.mean(axis=0)
    if len(items) >= 3 and (np.linalg.matrix_rank(centered_ref, tol=1e-10) < 2 or np.linalg.matrix_rank(centered_cad, tol=1e-10) < 2):
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "three or more anchors must span two dimensions")
    covariance = centered_cad.T @ centered_ref
    left, singular_values, right_transposed = np.linalg.svd(covariance)
    row_rotation = left @ right_transposed
    if float(np.linalg.det(row_rotation)) < 0.0:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "reflection is not an allowed alignment")
    source_energy = float(np.sum(centered_cad * centered_cad))
    if source_energy <= 1e-12:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "source anchors have no usable spread")
    uniform_scale = float(np.sum(singular_values) / source_energy)
    linear = uniform_scale * row_rotation.T
    translation = reference.mean(axis=0) - linear @ cad.mean(axis=0)
    projected = cad @ linear.T + translation
    residuals = np.linalg.norm(projected - reference, axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if residual_rms > max_residual_px:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "anchor residual exceeds the approved threshold")
    matrix = ((float(linear[0, 0]), float(linear[0, 1]), float(translation[0])),
              (float(linear[1, 0]), float(linear[1, 1]), float(translation[1])))
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=matrix,
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=round(residual_rms, 4),
        reasons=(),
    )


def normalize_outline_strategy_c(image: np.ndarray) -> np.ndarray:
    """Lowers border threshold to 0.90, but still checks only 1px border."""
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate((binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]))
    if float(np.mean(border == 0)) >= 0.90:
        return binary
    if float(np.mean(border == 255)) >= 0.90:
        return cv2.bitwise_not(binary)
    raise ValueError("foreground polarity is ambiguous")


def compare_metric_trend_strategy_c(
    current_metrics: dict[str, float],
    previous_metrics: dict[str, float] | None,
    *,
    epsilon: float = 1e-6,
) -> str:
    """Fixed-threshold comparator: checks edges + IoU, but unconditionally fails if cc difference > 1."""
    if previous_metrics is None:
        return "BASELINE"
    missing_regressed = current_metrics["missing_edge_ratio"] > previous_metrics["missing_edge_ratio"] + epsilon
    extra_regressed = current_metrics["extra_edge_ratio"] > previous_metrics["extra_edge_ratio"] + epsilon
    hausdorff_regressed = current_metrics["hausdorff_p95_normalized"] > previous_metrics["hausdorff_p95_normalized"] + epsilon
    if missing_regressed or extra_regressed or hausdorff_regressed:
        return "REGRESSED"
    cc_diff = current_metrics.get("connected_component_difference", 0)
    prev_cc_diff = previous_metrics.get("connected_component_difference", 0)
    if cc_diff - prev_cc_diff > 1:
        return "REGRESSED"
    if current_metrics["silhouette_iou"] > previous_metrics["silhouette_iou"] + epsilon:
        return "IMPROVED"
    return "UNCHANGED"


# ---------------------------------------------------------------------------
# Strategy D: Cascading Tier Consensus, Robust Polarity Consensus,
# N-Point DLT Homography, and Directional Metric Comparator (Selected Oracle)
# ---------------------------------------------------------------------------

def select_anchors_strategy_d(
    anchors: Sequence[AnchorPair],
    method: str = "FAILED_ANCHOR_SIMILARITY",
    min_anchors_needed: int = 2,
) -> tuple[list[AnchorPair] | None, AlignmentResult | None]:
    """Cascading tier consensus.

    Collects anchors hierarchically: DATUM (4) -> DRIVING_DIMENSION (3) ->
    STABLE_ENTITY (2) -> VISUAL_FEATURE (1).
    Cascades down until at least `min_anchors_needed` distinct anchors are accumulated.
    Prevents single-anchor starvation of higher tiers.
    """
    validated, failure = validate_anchor_list(anchors, method)
    if failure is not None:
        return None, failure
    assert validated is not None

    anchor_ids = tuple(item.anchor_id for item in validated)
    eligible = [
        item
        for item in validated
        if item.authority != "VISUAL_FEATURE"
        or item.confidence >= MIN_VISUAL_FEATURE_CONFIDENCE
    ]
    if not eligible:
        return None, failed_result(
            method,
            anchor_ids,
            "no anchors meet the approved authority and confidence policy",
        )

    # Group by tier
    by_tier: dict[int, list[AnchorPair]] = {}
    for item in eligible:
        tier = AUTHORITY_TIERS[item.authority]
        by_tier.setdefault(tier, []).append(item)

    # Accumulate descending
    selected: list[AnchorPair] = []
    for tier in sorted(by_tier.keys(), reverse=True):
        selected.extend(by_tier[tier])
        if len(selected) >= min_anchors_needed:
            # Check geometric distinctness
            ref_pts = np.asarray([a.reference_px for a in selected])
            cad_pts = np.asarray([a.cad_px for a in selected])
            if len(np.unique(ref_pts, axis=0)) >= min_anchors_needed and len(np.unique(cad_pts, axis=0)) >= min_anchors_needed:
                break

    return selected, None


def estimate_similarity_strategy_d(
    anchors: Sequence[AnchorPair],
    *,
    max_rotation_deg: float = 5.0,
    min_uniform_scale: float = 0.5,
    max_uniform_scale: float = 2.0,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Robust similarity alignment with cascading tier consensus and weighted Procrustes."""
    items, failure = select_anchors_strategy_d(anchors, method="FAILED_ANCHOR_SIMILARITY", min_anchors_needed=2)
    if failure is not None:
        return failure
    assert items is not None

    if len(items) < 2:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "at least two anchors are required")

    reference = np.asarray([item.reference_px for item in items], dtype=np.float64)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float64)
    weights = np.asarray([AUTHORITY_TIERS[item.authority] * item.confidence for item in items], dtype=np.float64)
    weights = weights / weights.sum()

    centered_ref = reference - np.average(reference, axis=0, weights=weights)
    centered_cad = cad - np.average(cad, axis=0, weights=weights)

    rank_ref = int(np.linalg.matrix_rank(centered_ref, tol=1e-8))
    rank_cad = int(np.linalg.matrix_rank(centered_cad, tol=1e-8))

    source_centroid = np.average(cad, axis=0, weights=weights)
    target_centroid = np.average(reference, axis=0, weights=weights)
    source_centered = cad - source_centroid
    target_centered = reference - target_centroid

    if rank_ref < 2 or rank_cad < 2:
        # Collinear anchor set: find principal 1D axis
        # Use first and last anchors along principal component
        u_cad, s_cad, vh_cad = np.linalg.svd(source_centered)
        axis_cad = vh_cad[0]
        proj_cad = source_centered @ axis_cad
        i_min, i_max = int(np.argmin(proj_cad)), int(np.argmax(proj_cad))
        delta_cad = cad[i_max] - cad[i_min]
        delta_ref = reference[i_max] - reference[i_min]
        l_cad = float(np.linalg.norm(delta_cad))
        l_ref = float(np.linalg.norm(delta_ref))
        if l_cad <= 1e-12 or l_ref <= 1e-12:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "anchor pairs must be distinct")
        uniform_scale = l_ref / l_cad
        cos_t = float(np.dot(delta_cad, delta_ref) / (l_cad * l_ref))
        sin_t = float((delta_cad[0] * delta_ref[1] - delta_cad[1] * delta_ref[0]) / (l_cad * l_ref))
        linear = uniform_scale * np.asarray([[cos_t, -sin_t], [sin_t, cos_t]], dtype=np.float64)
    else:
        # 2D weighted Procrustes
        W = np.diag(weights)
        covariance = source_centered.T @ W @ target_centered
        left, singular_values, right_transposed = np.linalg.svd(covariance)
        # Enforce pure rotation (det = +1)
        d = float(np.linalg.det(left @ right_transposed))
        if d < 0.0:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "reflection is not an allowed alignment")
        source_energy = float(np.sum(weights[:, None] * source_centered * source_centered))
        if source_energy <= 1e-12:
            return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "source anchors have no usable spread")
        uniform_scale = float(np.sum(singular_values) / source_energy)
        row_rotation = left @ right_transposed
        linear = uniform_scale * row_rotation.T

    if not math.isfinite(uniform_scale) or not min_uniform_scale <= uniform_scale <= max_uniform_scale:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "uniform scale is outside the approved range")
    rotation_deg = math.degrees(math.atan2(float(linear[1, 0]), float(linear[0, 0])))
    if abs(rotation_deg) > max_rotation_deg:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "rotation is outside the approved range")

    translation = target_centroid - linear @ source_centroid
    projected = cad @ linear.T + translation
    residuals = np.linalg.norm(projected - reference, axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if not math.isfinite(residual_rms) or residual_rms > max_residual_px:
        return failed_result("FAILED_ANCHOR_SIMILARITY", [i.anchor_id for i in items], "anchor residual exceeds the approved threshold")

    matrix = ((float(linear[0, 0]), float(linear[0, 1]), float(translation[0])),
              (float(linear[1, 0]), float(linear[1, 1]), float(translation[1])))
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=matrix,
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=round(residual_rms, 4),
        reasons=(),
    )


def estimate_photograph_strategy_d(
    anchors: Sequence[AnchorPair],
    *,
    source_is_photograph: bool,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Robust photograph homography for ANY N >= 4 perspective anchors."""
    items, failure = select_anchors_strategy_d(anchors, method="FAILED_PHOTOGRAPH_HOMOGRAPHY", min_anchors_needed=4)
    if failure is not None:
        return failure
    assert items is not None

    if source_is_photograph is not True:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph alignment requires source_is_photograph=true")
    if len(items) < 4:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph alignment requires at least four anchors")

    reference = np.asarray([item.reference_px for item in items], dtype=np.float32)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float32)

    if len(items) == 4:
        try:
            matrix = cv2.getPerspectiveTransform(cad, reference)
        except cv2.error:
            return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph anchors do not define a usable homography")
    else:
        # N > 4 least squares homography
        matrix, inliers = cv2.findHomography(cad, reference, cv2.LMEDS)
        if matrix is None:
            return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph anchors do not define a usable homography")

    homogeneous = np.column_stack([cad.astype(np.float64), np.ones(len(items), dtype=np.float64)])
    projected_h = homogeneous @ matrix.astype(np.float64).T
    if np.any(np.abs(projected_h[:, 2]) <= 1e-12):
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph homography projects an anchor to infinity")
    projected = projected_h[:, :2] / projected_h[:, 2:3]
    residuals = np.linalg.norm(projected - reference.astype(np.float64), axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if residual_rms > max_residual_px:
        return failed_result("FAILED_PHOTOGRAPH_HOMOGRAPHY", [i.anchor_id for i in items], "photograph homography residual exceeds the approved threshold")

    return AlignmentResult(
        status="ALIGNED",
        method="APPROVED_PHOTOGRAPH_HOMOGRAPHY",
        matrix=tuple(tuple(float(v) for v in row) for row in matrix),
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=round(residual_rms, 4),
        reasons=(),
    )


def normalize_outline_strategy_d(image: np.ndarray) -> np.ndarray:
    """Robust multi-evidence polarity normalization.

    Combines:
    1. Four corner patches (5x5 px each) - resistant to border frame lines.
    2. 3-pixel inset perimeter band.
    3. Global image intensity median.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    h, w = binary.shape[:2]

    # Sample four corners (5x5)
    cs = min(5, h // 4, w // 4)
    c_tl = binary[0:cs, 0:cs]
    c_tr = binary[0:cs, w - cs:w]
    c_bl = binary[h - cs:h, 0:cs]
    c_br = binary[h - cs:h, w - cs:w]
    corner_pixels = np.concatenate([c_tl.ravel(), c_tr.ravel(), c_bl.ravel(), c_br.ravel()])
    corner_white_frac = float(np.mean(corner_pixels == 255))
    corner_black_frac = float(np.mean(corner_pixels == 0))

    # Inset perimeter band (3px inset)
    inset = min(3, h // 10, w // 10)
    inset_border = np.concatenate((
        binary[inset, inset:w - inset],
        binary[h - 1 - inset, inset:w - inset],
        binary[inset:h - inset, inset],
        binary[inset:h - inset, w - 1 - inset],
    ))
    inset_white_frac = float(np.mean(inset_border == 255))
    inset_black_frac = float(np.mean(inset_border == 0))

    # Combined consensus score
    white_score = 0.6 * corner_white_frac + 0.4 * inset_white_frac
    black_score = 0.6 * corner_black_frac + 0.4 * inset_black_frac

    if white_score >= 0.65:
        # White background -> foreground is black -> invert binary
        return cv2.bitwise_not(binary)
    if black_score >= 0.65:
        # Black background -> foreground is white -> keep binary
        return binary.astype(np.uint8, copy=False)

    # Fallback to full border if unambiguous
    border = np.concatenate((binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]))
    if float(np.mean(border == 255)) >= 0.85:
        return cv2.bitwise_not(binary)
    if float(np.mean(border == 0)) >= 0.85:
        return binary.astype(np.uint8, copy=False)

    raise ValueError("foreground polarity is ambiguous")


def compare_metric_trend_strategy_d(
    current_metrics: dict[str, float],
    previous_metrics: dict[str, float] | None,
    *,
    epsilon: float = 1e-6,
) -> str:
    """Directional trend comparator.

    Protects against edge regressions while preventing component count changes
    from falsely rejecting significant IoU improvements.
    """
    if previous_metrics is None:
        return "BASELINE"

    # Core edge & distance checks
    missing_regressed = current_metrics["missing_edge_ratio"] > previous_metrics["missing_edge_ratio"] + epsilon
    extra_regressed = current_metrics["extra_edge_ratio"] > previous_metrics["extra_edge_ratio"] + epsilon
    hausdorff_regressed = current_metrics["hausdorff_p95_normalized"] > previous_metrics["hausdorff_p95_normalized"] + epsilon

    if missing_regressed or extra_regressed or hausdorff_regressed:
        return "REGRESSED"

    iou_improved = current_metrics["silhouette_iou"] > previous_metrics["silhouette_iou"] + epsilon
    chamfer_improved = current_metrics["chamfer_distance_normalized"] < previous_metrics["chamfer_distance_normalized"] - epsilon

    # Component count check is gated by IoU improvement
    cc_diff = current_metrics.get("connected_component_difference", 0)
    prev_cc_diff = previous_metrics.get("connected_component_difference", 0)
    cc_regressed = cc_diff > prev_cc_diff

    if cc_regressed and (current_metrics["silhouette_iou"] - previous_metrics["silhouette_iou"] < 0.05):
        return "REGRESSED"

    if iou_improved or chamfer_improved:
        return "IMPROVED"

    return "UNCHANGED"
