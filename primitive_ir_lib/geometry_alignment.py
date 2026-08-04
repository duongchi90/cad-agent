"""Deterministic, restricted image alignment for geometry comparison."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math

import cv2
import numpy as np

Point = tuple[float, float]

_ALLOWED_AUTHORITIES = {
    "DATUM",
    "DRIVING_DIMENSION",
    "STABLE_ENTITY",
    "VISUAL_FEATURE",
}
_AUTHORITY_TIERS = {
    "DATUM": 4,
    "DRIVING_DIMENSION": 3,
    "STABLE_ENTITY": 2,
    "VISUAL_FEATURE": 1,
}
_MIN_VISUAL_FEATURE_CONFIDENCE = 0.8


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


def _failed(method: str, anchor_ids: Sequence[str], reason: str) -> AlignmentResult:
    return AlignmentResult(
        status="FAILED",
        method=method,
        matrix=None,
        anchor_ids=tuple(anchor_ids),
        residual_rms_px=None,
        reasons=(reason,),
    )


def _validated_anchors(
    anchors: Sequence[AnchorPair],
    *,
    method: str,
) -> tuple[list[AnchorPair] | None, AlignmentResult | None]:
    try:
        items = list(anchors)
    except TypeError:
        return None, _failed(method, (), "anchors must be a sequence")

    anchor_ids = tuple(sorted(str(getattr(item, "anchor_id", "")) for item in items))
    if any(not isinstance(item.anchor_id, str) or not item.anchor_id for item in items):
        return None, _failed(method, anchor_ids, "anchor IDs must be non-empty strings")
    if len(set(anchor_ids)) != len(anchor_ids):
        return None, _failed(method, anchor_ids, "duplicate anchor IDs are not allowed")

    validated: list[AnchorPair] = []
    for item in items:
        if item.authority not in _ALLOWED_AUTHORITIES:
            return None, _failed(method, anchor_ids, f"unsupported anchor authority: {item.authority}")
        if not isinstance(item.confidence, (int, float)) or isinstance(item.confidence, bool):
            return None, _failed(method, anchor_ids, "anchor confidence must be numeric")
        if not math.isfinite(float(item.confidence)) or not 0.0 <= float(item.confidence) <= 1.0:
            return None, _failed(method, anchor_ids, "anchor confidence must be finite in [0, 1]")
        try:
            reference = np.asarray(item.reference_px, dtype=np.float64)
            cad = np.asarray(item.cad_px, dtype=np.float64)
        except (TypeError, ValueError):
            return None, _failed(method, anchor_ids, "anchor points must contain two numeric values")
        if reference.shape != (2,) or cad.shape != (2,):
            return None, _failed(method, anchor_ids, "anchor points must contain two numeric values")
        if not np.isfinite(reference).all() or not np.isfinite(cad).all():
            return None, _failed(method, anchor_ids, "anchor points must be finite")
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
            return None, _failed(method, anchor_ids, "duplicate reference points are not allowed")
        if len(np.unique(cad_points, axis=0)) != len(validated):
            return None, _failed(method, anchor_ids, "duplicate CAD points are not allowed")
    eligible = [
        item
        for item in validated
        if item.authority != "VISUAL_FEATURE"
        or item.confidence >= _MIN_VISUAL_FEATURE_CONFIDENCE
    ]
    if not eligible:
        return None, _failed(
            method,
            anchor_ids,
            "no anchors meet the approved authority and confidence policy",
        )
    highest_tier = max(_AUTHORITY_TIERS[item.authority] for item in eligible)
    selected = [item for item in eligible if _AUTHORITY_TIERS[item.authority] == highest_tier]
    return selected, None


def _rank(points: np.ndarray) -> int:
    centered = points - points.mean(axis=0)
    return int(np.linalg.matrix_rank(centered, tol=1e-10))


def _similarity_failure(anchors: Sequence[AnchorPair], reason: str) -> AlignmentResult:
    return _failed(
        "FAILED_ANCHOR_SIMILARITY",
        tuple(item.anchor_id for item in anchors),
        reason,
    )


def estimate_similarity_alignment(
    anchors: Sequence[AnchorPair],
    *,
    max_rotation_deg: float = 5.0,
    min_uniform_scale: float = 0.5,
    max_uniform_scale: float = 2.0,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Fit a deterministic CAD-to-reference translation/rotation/scale transform."""

    items, failure = _validated_anchors(anchors, method="FAILED_ANCHOR_SIMILARITY")
    if failure is not None:
        return failure
    assert items is not None
    anchor_ids = tuple(item.anchor_id for item in items)
    if len(items) < 2:
        return _similarity_failure(items, "at least two anchors are required")
    for value, name in (
        (max_rotation_deg, "max_rotation_deg"),
        (min_uniform_scale, "min_uniform_scale"),
        (max_uniform_scale, "max_uniform_scale"),
        (max_residual_px, "max_residual_px"),
    ):
        if not math.isfinite(float(value)):
            return _similarity_failure(items, f"{name} must be finite")
    if min_uniform_scale <= 0.0 or max_uniform_scale < min_uniform_scale:
        return _similarity_failure(items, "uniform scale limits are invalid")
    if max_residual_px < 0.0 or max_rotation_deg < 0.0:
        return _similarity_failure(items, "alignment limits must be non-negative")

    reference = np.asarray([item.reference_px for item in items], dtype=np.float64)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float64)
    if len(items) >= 3 and (_rank(reference) < 2 or _rank(cad) < 2):
        return _similarity_failure(items, "three or more anchors must span two dimensions")

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
            return _similarity_failure(items, "anchor pairs must be distinct")
        uniform_scale = target_length / source_length
        cosine = float(np.dot(source_delta, target_delta) / (source_length * target_length))
        sine = float(
            (source_delta[0] * target_delta[1] - source_delta[1] * target_delta[0])
            / (source_length * target_length)
        )
        linear = uniform_scale * np.asarray(
            [[cosine, -sine], [sine, cosine]], dtype=np.float64
        )
    else:
        covariance = source_centered.T @ target_centered
        left, singular_values, right_transposed = np.linalg.svd(covariance)
        row_rotation = left @ right_transposed
        if float(np.linalg.det(row_rotation)) < 0.0:
            return _similarity_failure(items, "reflection is not an allowed alignment")
        source_energy = float(np.sum(source_centered * source_centered))
        if source_energy <= 1e-12:
            return _similarity_failure(items, "source anchors have no usable spread")
        uniform_scale = float(np.sum(singular_values) / source_energy)
        linear = uniform_scale * row_rotation.T

    if not math.isfinite(uniform_scale) or not min_uniform_scale <= uniform_scale <= max_uniform_scale:
        return _similarity_failure(items, "uniform scale is outside the approved range")
    rotation_deg = math.degrees(math.atan2(float(linear[1, 0]), float(linear[0, 0])))
    if abs(rotation_deg) > max_rotation_deg:
        return _similarity_failure(items, "rotation is outside the approved range")

    translation = target_centroid - linear @ source_centroid
    projected = cad @ linear.T + translation
    residuals = np.linalg.norm(projected - reference, axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if not math.isfinite(residual_rms) or residual_rms > max_residual_px:
        return _similarity_failure(items, "anchor residual exceeds the approved threshold")

    matrix = np.asarray(
        [
            [linear[0, 0], linear[0, 1], translation[0]],
            [linear[1, 0], linear[1, 1], translation[1]],
        ],
        dtype=np.float64,
    )
    return AlignmentResult(
        status="ALIGNED",
        method="VERIFIED_ANCHOR_SIMILARITY",
        matrix=tuple(tuple(float(value) for value in row) for row in matrix),
        anchor_ids=anchor_ids,
        residual_rms_px=residual_rms,
        reasons=(),
    )


def estimate_photograph_alignment(
    anchors: Sequence[AnchorPair],
    *,
    source_is_photograph: bool,
    max_residual_px: float = 3.0,
) -> AlignmentResult:
    """Fit a four-anchor homography only for an explicitly flagged photograph."""

    items, failure = _validated_anchors(anchors, method="FAILED_PHOTOGRAPH_HOMOGRAPHY")
    if failure is not None:
        return failure
    assert items is not None
    if source_is_photograph is not True:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph alignment requires source_is_photograph=true",
        )
    if len(items) != 4:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph alignment requires exactly four anchors",
        )
    if not math.isfinite(float(max_residual_px)) or max_residual_px < 0.0:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "max_residual_px must be a non-negative finite number",
        )

    reference = np.asarray([item.reference_px for item in items], dtype=np.float32)
    cad = np.asarray([item.cad_px for item in items], dtype=np.float32)
    if _rank(reference.astype(np.float64)) < 2 or _rank(cad.astype(np.float64)) < 2:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph anchors must be non-collinear",
        )
    try:
        matrix = cv2.getPerspectiveTransform(cad, reference)
    except cv2.error:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph anchors do not define a usable homography",
        )
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph homography is not finite",
        )

    homogeneous = np.column_stack([cad.astype(np.float64), np.ones(4, dtype=np.float64)])
    projected_h = homogeneous @ matrix.astype(np.float64).T
    if np.any(np.abs(projected_h[:, 2]) <= 1e-12):
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph homography projects an anchor to infinity",
        )
    projected = projected_h[:, :2] / projected_h[:, 2:3]
    residuals = np.linalg.norm(projected - reference.astype(np.float64), axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    if not math.isfinite(residual_rms) or residual_rms > max_residual_px:
        return _failed(
            "FAILED_PHOTOGRAPH_HOMOGRAPHY",
            tuple(item.anchor_id for item in items),
            "photograph homography residual exceeds the approved threshold",
        )

    return AlignmentResult(
        status="ALIGNED",
        method="APPROVED_PHOTOGRAPH_HOMOGRAPHY",
        matrix=tuple(tuple(float(value) for value in row) for row in matrix),
        anchor_ids=tuple(item.anchor_id for item in items),
        residual_rms_px=residual_rms,
        reasons=(),
    )


def warp_to_reference(
    cad_image: np.ndarray,
    alignment: AlignmentResult,
    *,
    output_size: tuple[int, int],
    is_mask: bool,
) -> np.ndarray:
    """Apply only an aligned similarity or approved photograph homography."""

    if alignment.status != "ALIGNED" or alignment.matrix is None:
        raise ValueError("warp_to_reference requires an ALIGNED result")
    if len(output_size) != 2 or any(int(value) <= 0 for value in output_size):
        raise ValueError("output_size must contain positive width and height")
    matrix = np.asarray(alignment.matrix, dtype=np.float64)
    if not np.isfinite(matrix).all():
        raise ValueError("alignment matrix must be finite")
    width, height = (int(output_size[0]), int(output_size[1]))
    interpolation = cv2.INTER_NEAREST if is_mask else cv2.INTER_LINEAR
    if is_mask:
        border_value: int | tuple[int, int, int] = 0
    elif cad_image.ndim == 3:
        border_value = (255, 255, 255)
    else:
        border_value = 255

    if alignment.method == "VERIFIED_ANCHOR_SIMILARITY" and matrix.shape == (2, 3):
        warped = cv2.warpAffine(
            cad_image,
            matrix,
            (width, height),
            flags=interpolation,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_value,
        )
    elif alignment.method == "APPROVED_PHOTOGRAPH_HOMOGRAPHY" and matrix.shape == (3, 3):
        warped = cv2.warpPerspective(
            cad_image,
            matrix,
            (width, height),
            flags=interpolation,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_value,
        )
    else:
        raise ValueError("alignment method or matrix shape is not controlled")
    if is_mask:
        return np.where(warped > 0, 255, 0).astype(np.uint8)
    return warped


__all__ = [
    "AnchorPair",
    "AlignmentResult",
    "Point",
    "estimate_photograph_alignment",
    "estimate_similarity_alignment",
    "warp_to_reference",
]
