"""Reference implementation of Strategies A-D for Source Support Curved Primitive Verification.

Addresses core limitations in cad_agent/source_support_verifier.py:
1. Hard rejection of CIRCLE and ARC primitives (type != 'LINE' fails with ValueError).
2. All-or-nothing crash on single unsupported primitive destroying batch validation.
3. Rigid 0.85 support requirement failing dashed and centerline strokes.
4. Fixed 220 threshold vulnerability on inverted/blueprint renders.
5. Lack of arc-length raster sampling for curved geometry.
"""

from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageFilter


# Default approved parameters matching production
_DEFAULT_ENDPOINT_TOLERANCE_PX = 2
_DEFAULT_MIN_SUPPORT_FRACTION = 0.85
_DEFAULT_DARKNESS_THRESHOLD = 220

_DASHED_MIN_SUPPORT_FRACTION = 0.45
_CENTERLINE_MIN_SUPPORT_FRACTION = 0.35


def _decode_render_image(render_bytes: bytes) -> np.ndarray:
    if not isinstance(render_bytes, bytes) or not render_bytes:
        raise ValueError("SOURCE_RENDER_BYTES_INVALID")
    try:
        with Image.open(io.BytesIO(render_bytes)) as img:
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.uint8, copy=True)
    except Exception:
        raise ValueError("SOURCE_RENDER_DECODE_FAILED")
    if arr.ndim != 2 or arr.size == 0:
        raise ValueError("SOURCE_RENDER_DECODE_FAILED")
    return arr


def _line_samples(start: List[int], end: List[int]) -> Tuple[np.ndarray, np.ndarray]:
    x0, y0 = start
    x1, y1 = end
    count = max(abs(x1 - x0), abs(y1 - y0)) + 1
    xs = np.rint(np.linspace(x0, x1, count)).astype(np.int32)
    ys = np.rint(np.linspace(y0, y1, count)).astype(np.int32)
    return xs, ys


def _circle_samples(center: List[int], radius: float) -> Tuple[np.ndarray, np.ndarray]:
    cx, cy = center
    circumference = 2.0 * math.pi * radius
    count = max(8, int(math.ceil(circumference)))
    angles = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    xs = np.rint(cx + radius * np.cos(angles)).astype(np.int32)
    ys = np.rint(cy + radius * np.sin(angles)).astype(np.int32)
    return xs, ys


def _arc_samples(
    center: List[int],
    radius: float,
    start_angle_deg: float,
    end_angle_deg: float,
) -> Tuple[np.ndarray, np.ndarray]:
    cx, cy = center
    sweep_deg = (end_angle_deg - start_angle_deg) % 360.0
    if sweep_deg == 0.0 and start_angle_deg != end_angle_deg:
        sweep_deg = 360.0
    elif sweep_deg == 0.0:
        sweep_deg = 360.0

    arc_len = radius * math.radians(sweep_deg)
    count = max(4, int(math.ceil(arc_len)))
    angles = np.linspace(
        math.radians(start_angle_deg),
        math.radians(start_angle_deg + sweep_deg),
        count,
        endpoint=True,
    )
    xs = np.rint(cx + radius * np.cos(angles)).astype(np.int32)
    ys = np.rint(cy + radius * np.sin(angles)).astype(np.int32)
    return xs, ys


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline
# (Direct reproduction of cad_agent/source_support_verifier.py)
# ---------------------------------------------------------------------------
def verify_source_support_strategy_a(
    roi_bbox: List[int],
    primitives: List[Dict[str, Any]],
    source_render_bytes: bytes,
    endpoint_tolerance_px: int = _DEFAULT_ENDPOINT_TOLERANCE_PX,
    min_support_fraction: float = _DEFAULT_MIN_SUPPORT_FRACTION,
    darkness_threshold: int = _DEFAULT_DARKNESS_THRESHOLD,
) -> Dict[str, Any]:
    image = _decode_render_image(source_render_bytes)
    height, width = image.shape
    x0, y0, x1, y1 = roi_bbox

    dark = np.zeros_like(image, dtype=np.uint8)
    roi_pixels = image[y0 : y1 + 1, x0 : x1 + 1]
    dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi_pixels <= darkness_threshold, 255, 0).astype(np.uint8)

    if endpoint_tolerance_px:
        size = endpoint_tolerance_px * 2 + 1
        supported_pixels = np.asarray(
            Image.fromarray(dark).filter(ImageFilter.MaxFilter(size=size)),
            dtype=np.uint8,
        )
    else:
        supported_pixels = dark

    results: List[Dict[str, Any]] = []
    for primitive in primitives:
        primitive_id = primitive.get("id")
        if not isinstance(primitive_id, str) or primitive.get("type") != "LINE":
            raise ValueError("VERIFICATION_REQUEST_INVALID")

        start = primitive.get("start_px")
        end = primitive.get("end_px")
        if not start or not end:
            raise ValueError("VERIFICATION_REQUEST_INVALID")

        xs, ys = _line_samples(start, end)
        if (
            np.any(xs < x0)
            or np.any(xs > x1)
            or np.any(ys < y0)
            or np.any(ys > y1)
            or np.any(xs < 0)
            or np.any(xs >= width)
            or np.any(ys < 0)
            or np.any(ys >= height)
        ):
            raise ValueError("PRIMITIVE_OUTSIDE_BOUND_SOURCE")

        support_fraction = float(np.mean(supported_pixels[ys, xs] > 0))
        if support_fraction < min_support_fraction:
            raise ValueError(f"PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:{primitive_id}")

        results.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "sample_count": int(xs.size),
                "support_fraction": round(support_fraction, 6),
                "supported": True,
            }
        )

    return {
        "status": "VERIFIED",
        "primitive_support": results,
    }


# ---------------------------------------------------------------------------
# Strategy B: Exception-Free Structured Classifier
# (Never raises on unsupported primitives, but still LINE-only and fixed threshold)
# ---------------------------------------------------------------------------
def verify_source_support_strategy_b(
    roi_bbox: List[int],
    primitives: List[Dict[str, Any]],
    source_render_bytes: bytes,
    endpoint_tolerance_px: int = _DEFAULT_ENDPOINT_TOLERANCE_PX,
    min_support_fraction: float = _DEFAULT_MIN_SUPPORT_FRACTION,
    darkness_threshold: int = _DEFAULT_DARKNESS_THRESHOLD,
) -> Dict[str, Any]:
    image = _decode_render_image(source_render_bytes)
    height, width = image.shape
    x0, y0, x1, y1 = roi_bbox

    dark = np.zeros_like(image, dtype=np.uint8)
    roi_pixels = image[y0 : y1 + 1, x0 : x1 + 1]
    dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi_pixels <= darkness_threshold, 255, 0).astype(np.uint8)

    if endpoint_tolerance_px:
        size = endpoint_tolerance_px * 2 + 1
        supported_pixels = np.asarray(
            Image.fromarray(dark).filter(ImageFilter.MaxFilter(size=size)),
            dtype=np.uint8,
        )
    else:
        supported_pixels = dark

    results: List[Dict[str, Any]] = []
    for primitive in primitives:
        primitive_id = str(primitive.get("id", ""))
        p_type = primitive.get("type")
        if p_type != "LINE":
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "supported": False,
                    "reason": "UNSUPPORTED_PRIMITIVE_TYPE",
                    "support_fraction": 0.0,
                    "sample_count": 0,
                }
            )
            continue

        start = primitive.get("start_px")
        end = primitive.get("end_px")
        if not start or not end:
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "supported": False,
                    "reason": "INVALID_GEOMETRY",
                    "support_fraction": 0.0,
                    "sample_count": 0,
                }
            )
            continue

        xs, ys = _line_samples(start, end)
        if (
            np.any(xs < x0)
            or np.any(xs > x1)
            or np.any(ys < y0)
            or np.any(ys > y1)
            or np.any(xs < 0)
            or np.any(xs >= width)
            or np.any(ys < 0)
            or np.any(ys >= height)
        ):
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "supported": False,
                    "reason": "OUTSIDE_BOUNDS",
                    "support_fraction": 0.0,
                    "sample_count": int(xs.size),
                }
            )
            continue

        support_fraction = float(np.mean(supported_pixels[ys, xs] > 0))
        supported = support_fraction >= min_support_fraction
        results.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "supported": supported,
                "reason": "OK" if supported else "INSUFFICIENT_SUPPORT",
                "support_fraction": round(support_fraction, 6),
                "sample_count": int(xs.size),
            }
        )

    all_ok = all(r["supported"] for r in results) if results else False
    any_ok = any(r["supported"] for r in results) if results else False
    status = "ALL_VERIFIED" if all_ok else ("PARTIAL_VERIFIED" if any_ok else "REJECTED")

    return {
        "status": status,
        "primitive_support": results,
    }


# ---------------------------------------------------------------------------
# Strategy C: Style-Aware Line Verifier
# (Supports dashed/centerline line styles, but still LINE-only)
# ---------------------------------------------------------------------------
def verify_source_support_strategy_c(
    roi_bbox: List[int],
    primitives: List[Dict[str, Any]],
    source_render_bytes: bytes,
    endpoint_tolerance_px: int = _DEFAULT_ENDPOINT_TOLERANCE_PX,
    darkness_threshold: int = _DEFAULT_DARKNESS_THRESHOLD,
) -> Dict[str, Any]:
    image = _decode_render_image(source_render_bytes)
    height, width = image.shape
    x0, y0, x1, y1 = roi_bbox

    dark = np.zeros_like(image, dtype=np.uint8)
    roi_pixels = image[y0 : y1 + 1, x0 : x1 + 1]
    dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi_pixels <= darkness_threshold, 255, 0).astype(np.uint8)

    if endpoint_tolerance_px:
        size = endpoint_tolerance_px * 2 + 1
        supported_pixels = np.asarray(
            Image.fromarray(dark).filter(ImageFilter.MaxFilter(size=size)),
            dtype=np.uint8,
        )
    else:
        supported_pixels = dark

    results: List[Dict[str, Any]] = []
    for primitive in primitives:
        primitive_id = str(primitive.get("id", ""))
        p_type = primitive.get("type")
        if p_type != "LINE":
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "supported": False,
                    "reason": "UNSUPPORTED_PRIMITIVE_TYPE",
                    "support_fraction": 0.0,
                    "sample_count": 0,
                }
            )
            continue

        start = primitive.get("start_px")
        end = primitive.get("end_px")
        style = primitive.get("style", "solid")

        req_fraction = _DEFAULT_MIN_SUPPORT_FRACTION
        if style == "dashed":
            req_fraction = _DASHED_MIN_SUPPORT_FRACTION
        elif style == "centerline":
            req_fraction = _CENTERLINE_MIN_SUPPORT_FRACTION

        xs, ys = _line_samples(start, end)
        if (
            np.any(xs < x0)
            or np.any(xs > x1)
            or np.any(ys < y0)
            or np.any(ys > y1)
            or np.any(xs < 0)
            or np.any(xs >= width)
            or np.any(ys < 0)
            or np.any(ys >= height)
        ):
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "supported": False,
                    "reason": "OUTSIDE_BOUNDS",
                    "support_fraction": 0.0,
                    "sample_count": int(xs.size),
                }
            )
            continue

        support_fraction = float(np.mean(supported_pixels[ys, xs] > 0))
        supported = support_fraction >= req_fraction
        results.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "supported": supported,
                "reason": "OK" if supported else "INSUFFICIENT_SUPPORT",
                "support_fraction": round(support_fraction, 6),
                "sample_count": int(xs.size),
            }
        )

    all_ok = all(r["supported"] for r in results) if results else False
    any_ok = any(r["supported"] for r in results) if results else False
    status = "ALL_VERIFIED" if all_ok else ("PARTIAL_VERIFIED" if any_ok else "REJECTED")

    return {
        "status": status,
        "primitive_support": results,
    }


# ---------------------------------------------------------------------------
# Strategy D: Multimodal Adaptive Curved & Structured Verifier Oracle
# 1. Multi-primitive support: LINE, CIRCLE, ARC.
# 2. Equidistant arc-length sampling for circles & arcs.
# 3. Adaptive background polarity detection (supports blueprint / dark background).
# 4. Style-aware support thresholds (solid, dashed, centerline).
# 5. Non-crashing structured per-primitive verdicts.
# 6. Degenerate & non-finite guards.
# ---------------------------------------------------------------------------
def _detect_and_normalize_ink_mask(
    image: np.ndarray,
    roi_bbox: List[int],
    fixed_darkness_threshold: int = _DEFAULT_DARKNESS_THRESHOLD,
) -> np.ndarray:
    """Extracts dark ink on light background mask, adapting to blueprint/inverted modes."""
    x0, y0, x1, y1 = roi_bbox
    roi = image[y0 : y1 + 1, x0 : x1 + 1]

    # Sample ROI perimeter to estimate background polarity
    perimeter_pixels = np.concatenate([
        roi[0, :],
        roi[-1, :],
        roi[:, 0],
        roi[:, -1],
    ])
    bg_median = float(np.median(perimeter_pixels))

    dark = np.zeros_like(image, dtype=np.uint8)
    if bg_median < 80.0:
        # Inverted / blueprint render (light ink on dark background)
        dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi >= 128, 255, 0).astype(np.uint8)
    else:
        # Ink is darker than background.
        # Safe adaptive bound: ink must be <= min(fixed_darkness_threshold, bg_median - 25.0)
        threshold = min(float(fixed_darkness_threshold), bg_median - 25.0)
        dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi <= threshold, 255, 0).astype(np.uint8)

    return dark


def verify_source_support_strategy_d(
    roi_bbox: List[int],
    primitives: List[Dict[str, Any]],
    source_render_bytes: bytes,
    endpoint_tolerance_px: int = _DEFAULT_ENDPOINT_TOLERANCE_PX,
    solid_min_fraction: float = _DEFAULT_MIN_SUPPORT_FRACTION,
    dashed_min_fraction: float = _DASHED_MIN_SUPPORT_FRACTION,
    centerline_min_fraction: float = _CENTERLINE_MIN_SUPPORT_FRACTION,
    darkness_threshold: int = _DEFAULT_DARKNESS_THRESHOLD,
) -> Dict[str, Any]:
    image = _decode_render_image(source_render_bytes)
    height, width = image.shape
    x0, y0, x1, y1 = roi_bbox

    dark = _detect_and_normalize_ink_mask(image, roi_bbox, darkness_threshold)

    if endpoint_tolerance_px:
        size = endpoint_tolerance_px * 2 + 1
        supported_pixels = np.asarray(
            Image.fromarray(dark).filter(ImageFilter.MaxFilter(size=size)),
            dtype=np.uint8,
        )
    else:
        supported_pixels = dark

    results: List[Dict[str, Any]] = []
    for primitive in primitives:
        primitive_id = str(primitive.get("id", ""))
        p_type = primitive.get("type")
        style = primitive.get("style", "solid")

        # Determine required support fraction by stroke style
        if style == "dashed":
            req_fraction = dashed_min_fraction
        elif style == "centerline":
            req_fraction = centerline_min_fraction
        else:
            req_fraction = solid_min_fraction

        # Sample coordinates based on primitive type
        if p_type == "LINE":
            start = primitive.get("start_px")
            end = primitive.get("end_px")
            if (
                not start
                or not end
                or len(start) != 2
                or len(end) != 2
                or not all(isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v)) for v in (*start, *end))
            ):
                results.append(
                    {
                        "primitive_hypothesis_id": primitive_id,
                        "primitive_type": p_type,
                        "supported": False,
                        "reason": "INVALID_GEOMETRY",
                        "support_fraction": 0.0,
                        "sample_count": 0,
                    }
                )
                continue
            xs, ys = _line_samples(start, end)

        elif p_type == "CIRCLE":
            center = primitive.get("center_px")
            radius = primitive.get("radius_px")
            if (
                not center
                or radius is None
                or len(center) != 2
                or not all(isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v)) for v in center)
                or not (isinstance(radius, (int, float)) and not (math.isnan(radius) or math.isinf(radius)))
                or radius < 1.0
            ):
                results.append(
                    {
                        "primitive_hypothesis_id": primitive_id,
                        "primitive_type": p_type,
                        "supported": False,
                        "reason": "INVALID_GEOMETRY",
                        "support_fraction": 0.0,
                        "sample_count": 0,
                    }
                )
                continue
            xs, ys = _circle_samples(center, float(radius))

        elif p_type == "ARC":
            center = primitive.get("center_px")
            radius = primitive.get("radius_px")
            start_ang = primitive.get("start_angle_deg")
            end_ang = primitive.get("end_angle_deg")
            if (
                not center
                or radius is None
                or start_ang is None
                or end_ang is None
                or len(center) != 2
                or not all(isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v)) for v in center)
                or not all(isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v)) for v in (radius, start_ang, end_ang))
                or radius < 1.0
            ):
                results.append(
                    {
                        "primitive_hypothesis_id": primitive_id,
                        "primitive_type": p_type,
                        "supported": False,
                        "reason": "INVALID_GEOMETRY",
                        "support_fraction": 0.0,
                        "sample_count": 0,
                    }
                )
                continue
            xs, ys = _arc_samples(center, float(radius), float(start_ang), float(end_ang))

        else:
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "primitive_type": p_type,
                    "supported": False,
                    "reason": "UNSUPPORTED_PRIMITIVE_TYPE",
                    "support_fraction": 0.0,
                    "sample_count": 0,
                }
            )
            continue

        # Check boundary containment
        if (
            np.any(xs < x0)
            or np.any(xs > x1)
            or np.any(ys < y0)
            or np.any(ys > y1)
            or np.any(xs < 0)
            or np.any(xs >= width)
            or np.any(ys < 0)
            or np.any(ys >= height)
        ):
            results.append(
                {
                    "primitive_hypothesis_id": primitive_id,
                    "primitive_type": p_type,
                    "supported": False,
                    "reason": "OUTSIDE_BOUNDS",
                    "support_fraction": 0.0,
                    "sample_count": int(xs.size),
                }
            )
            continue

        support_fraction = float(np.mean(supported_pixels[ys, xs] > 0))
        supported = support_fraction >= req_fraction
        results.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "primitive_type": p_type,
                "supported": supported,
                "reason": "OK" if supported else "INSUFFICIENT_SUPPORT",
                "support_fraction": round(support_fraction, 6),
                "sample_count": int(xs.size),
            }
        )

    all_ok = all(r["supported"] for r in results) if results else False
    any_ok = any(r["supported"] for r in results) if results else False
    status = "ALL_VERIFIED" if all_ok else ("PARTIAL_VERIFIED" if any_ok else "REJECTED")

    return {
        "status": status,
        "primitive_support": results,
    }
