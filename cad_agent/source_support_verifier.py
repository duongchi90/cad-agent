"""Deterministic raster support checks for external visual line proposals.

This verifier consumes proposal-only requests and exact render bytes. It does
not infer semantics, run Hough/Canny extraction, materialize PrimitiveIR, or
mutate CAD/source artifacts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import cv2
import numpy as np


__all__ = ["verify_external_visual_proposal_source_support"]


def _fail(code: str) -> None:
    raise ValueError(code)


def _strict_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(code)
    return value


def _parameter_fraction(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("SOURCE_SUPPORT_PARAMETER_INVALID")
    result = float(value)
    if not 0.0 < result <= 1.0:
        _fail("SOURCE_SUPPORT_PARAMETER_INVALID")
    return result


def _decode_render(source_render_bytes: object) -> np.ndarray:
    if not isinstance(source_render_bytes, bytes) or not source_render_bytes:
        _fail("SOURCE_RENDER_BYTES_INVALID")
    encoded = np.frombuffer(source_render_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None or image.ndim != 2 or image.size == 0:
        _fail("SOURCE_RENDER_DECODE_FAILED")
    return image


def _request_parts(
    verification_request: object,
) -> tuple[Mapping[str, object], list[Mapping[str, object]], str]:
    if not isinstance(verification_request, Mapping):
        _fail("VERIFICATION_REQUEST_INVALID")
    if (
        verification_request.get("kind") != "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
        or verification_request.get("status") != "PROPOSAL_ONLY"
        or verification_request.get("proposal_source") != "external_ai"
        or verification_request.get("semantic_label_authority") != "NONE"
        or verification_request.get("primitive_ir_materialized") is not False
        or verification_request.get("cad_mutation") is not False
    ):
        _fail("VERIFICATION_REQUEST_INVALID")
    required_checks = verification_request.get("checks_required")
    if not isinstance(required_checks, list) or "PER_PRIMITIVE_SOURCE_SUPPORT" not in required_checks:
        _fail("VERIFICATION_REQUEST_INVALID")

    binding = verification_request.get("exact_source_binding")
    if not isinstance(binding, Mapping):
        _fail("SOURCE_BINDING_INVALID")
    expected_render_sha256 = binding.get("source_render_sha256")
    roi = binding.get("roi_bbox_px")
    if (
        not isinstance(expected_render_sha256, str)
        or len(expected_render_sha256) != 64
        or not isinstance(roi, list)
        or len(roi) != 4
    ):
        _fail("SOURCE_BINDING_INVALID")

    primitives_raw = verification_request.get("primitive_hypotheses")
    if not isinstance(primitives_raw, list) or not primitives_raw:
        _fail("VERIFICATION_REQUEST_INVALID")
    primitives: list[Mapping[str, object]] = []
    for primitive in primitives_raw:
        if not isinstance(primitive, Mapping):
            _fail("VERIFICATION_REQUEST_INVALID")
        primitives.append(primitive)
    return binding, primitives, expected_render_sha256


def _line_samples(start: list[int], end: list[int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0 = start
    x1, y1 = end
    count = max(abs(x1 - x0), abs(y1 - y0)) + 1
    xs = np.rint(np.linspace(x0, x1, count)).astype(np.int32)
    ys = np.rint(np.linspace(y0, y1, count)).astype(np.int32)
    return xs, ys


def verify_external_visual_proposal_source_support(
    *,
    verification_request: object,
    source_render_bytes: bytes,
    endpoint_tolerance_px: int = 2,
    min_support_fraction: float = 0.85,
    darkness_threshold: int = 220,
) -> dict[str, object]:
    """Verify that every proposed LINE is supported by exact bound raster ink.

    Support is measured by sampling the proposed segment at pixel cadence and
    asking whether each sample lies within ``endpoint_tolerance_px`` of a dark
    source pixel. This is evidence for observed raster support only; it does not
    prove semantic identity, physical connectivity, or CAD correctness.
    """

    binding, primitives, expected_render_sha256 = _request_parts(verification_request)

    tolerance = _strict_int(endpoint_tolerance_px, "SOURCE_SUPPORT_PARAMETER_INVALID")
    threshold = _strict_int(darkness_threshold, "SOURCE_SUPPORT_PARAMETER_INVALID")
    support_threshold = _parameter_fraction(min_support_fraction)
    if tolerance < 0 or tolerance > 16 or threshold < 0 or threshold > 255:
        _fail("SOURCE_SUPPORT_PARAMETER_INVALID")

    actual_render_sha256 = hashlib.sha256(source_render_bytes).hexdigest()
    if actual_render_sha256 != expected_render_sha256:
        _fail("SOURCE_RENDER_HASH_MISMATCH")
    image = _decode_render(source_render_bytes)
    height, width = image.shape

    roi = binding["roi_bbox_px"]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in roi):
        _fail("SOURCE_BINDING_INVALID")
    x0, y0, x1, y1 = roi
    if x0 < 0 or y0 < 0 or x0 >= x1 or y0 >= y1 or x1 >= width or y1 >= height:
        _fail("SOURCE_BINDING_OUTSIDE_RENDER")

    dark = (image <= threshold).astype(np.uint8)
    if tolerance:
        size = tolerance * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        supported_pixels = cv2.dilate(dark, kernel, iterations=1)
    else:
        supported_pixels = dark

    results: list[dict[str, object]] = []
    for primitive in primitives:
        primitive_id = primitive.get("id")
        if not isinstance(primitive_id, str) or primitive.get("type") != "LINE":
            _fail("VERIFICATION_REQUEST_INVALID")
        start = primitive.get("start_px")
        end = primitive.get("end_px")
        if (
            not isinstance(start, list)
            or not isinstance(end, list)
            or len(start) != 2
            or len(end) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in (*start, *end))
        ):
            _fail("VERIFICATION_REQUEST_INVALID")
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
            _fail("PRIMITIVE_OUTSIDE_BOUND_SOURCE")
        support_fraction = float(np.mean(supported_pixels[ys, xs] > 0))
        if support_fraction < support_threshold:
            _fail(f"PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:{primitive_id}")
        results.append(
            {
                "primitive_hypothesis_id": primitive_id,
                "sample_count": int(xs.size),
                "support_fraction": round(support_fraction, 6),
                "supported": True,
            }
        )

    return {
        "kind": "DETERMINISTIC_SOURCE_SUPPORT_RESULT",
        "status": "VERIFIED",
        "verification_request_sha256": verification_request.get("verification_request_sha256"),
        "source_render_sha256": actual_render_sha256,
        "parameters": {
            "endpoint_tolerance_px": tolerance,
            "min_support_fraction": support_threshold,
            "darkness_threshold": threshold,
        },
        "primitive_support": results,
        "semantic_label_authority": "NONE",
        "primitive_ir_materialized": False,
        "cad_mutation": False,
    }
