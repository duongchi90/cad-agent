"""Source Verified Curved Geometry Materializer Engine.

Research Reference Engine comparing Strategies A-D for Topic 28:
SOURCE_VERIFIED_CURVED_GEOMETRY_MATERIALIZER_V1.
"""

from __future__ import annotations

import copy
import io
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from PIL import Image

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import _normalize_calibration_binding
from cad_agent.source_verified_geometry import (
    materialize_verified_external_visual_lines as prod_materialize_lines,
)
from primitive_ir_lib.models import (
    ArcGeometry,
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
    now_iso,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_TYPE = "geometry_external_ai"
_TRACE_TOOL = "external-ai-verified-source-support-v1"


def _fail(code: str) -> None:
    raise ValueError(code)


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _render_dimensions(source_render_bytes: bytes) -> tuple[int, int]:
    if not isinstance(source_render_bytes, bytes) or not source_render_bytes:
        _fail("SOURCE_RENDER_BYTES_INVALID")
    try:
        with Image.open(io.BytesIO(source_render_bytes)) as image:
            image.load()
            return image.size
    except (OSError, ValueError):
        _fail("SOURCE_RENDER_DECODE_FAILED")


def _binding(verification_request: object) -> Mapping[str, object]:
    if not isinstance(verification_request, Mapping):
        _fail("VERIFICATION_REQUEST_INVALID")
    binding = verification_request.get("exact_source_binding")
    if not isinstance(binding, Mapping):
        _fail("SOURCE_BINDING_INVALID")
    _sha256(binding.get("source_sha256"), "SOURCE_BINDING_INVALID")
    if (
        isinstance(binding.get("page_index"), bool)
        or not isinstance(binding.get("page_index"), int)
        or binding["page_index"] < 0
    ):
        _fail("SOURCE_BINDING_INVALID")
    roi = binding.get("roi_bbox_px")
    if (
        not isinstance(roi, list)
        or len(roi) != 4
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in roi)
    ):
        _fail("SOURCE_BINDING_INVALID")
    return binding


# ==============================================================================
# Exact Bounding Box Calculations for Curved Primitives
# ==============================================================================

def compute_primitive_bbox_px(prim: Mapping[str, object]) -> Tuple[int, int, int, int]:
    """Compute accurate pixel bounding box for Line, Circle, or Arc."""
    ptype = prim.get("type")
    if ptype == "LINE":
        s = prim["start_px"]
        e = prim["end_px"]
        return (
            int(math.floor(min(s[0], e[0]))),
            int(math.floor(min(s[1], e[1]))),
            int(math.ceil(max(s[0], e[0]))),
            int(math.ceil(max(s[1], e[1]))),
        )
    elif ptype == "CIRCLE":
        c = prim["center_px"]
        r = float(prim["radius_px"])
        return (
            int(math.floor(c[0] - r)),
            int(math.floor(c[1] - r)),
            int(math.ceil(c[0] + r)),
            int(math.ceil(c[1] + r)),
        )
    elif ptype == "ARC":
        c = prim["center_px"]
        r = float(prim["radius_px"])
        t1 = math.radians(float(prim["start_angle_deg"]))
        t2 = math.radians(float(prim["end_angle_deg"]))
        pts = [
            (c[0] + r * math.cos(t1), c[1] + r * math.sin(t1)),
            (c[0] + r * math.cos(t2), c[1] + r * math.sin(t2)),
        ]
        # Include extrema points inside sweep
        # Normalized angles in [0, 360)
        a1 = float(prim["start_angle_deg"]) % 360.0
        a2 = float(prim["end_angle_deg"]) % 360.0
        for extremum_deg in [0.0, 90.0, 180.0, 270.0]:
            in_sweep = False
            if a1 <= a2:
                in_sweep = (a1 <= extremum_deg <= a2)
            else:
                in_sweep = (extremum_deg >= a1 or extremum_deg <= a2)
            if in_sweep:
                rad = math.radians(extremum_deg)
                pts.append((c[0] + r * math.cos(rad), c[1] + r * math.sin(rad)))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (
            int(math.floor(min(xs))),
            int(math.floor(min(ys))),
            int(math.ceil(max(xs))),
            int(math.ceil(max(ys))),
        )
    _fail("VERIFICATION_REQUEST_INVALID")


# ==============================================================================
# Pixel to CAD Coordinate and Angular Winding Conversion
# ==============================================================================

def pixel_arc_to_cad_arc(
    center_px: List[float],
    radius_px: float,
    start_angle_px_deg: float,
    end_angle_px_deg: float,
    calibration: Calibration,
) -> ArcGeometry:
    """Transform pixel arc (CW, +y down) to CAD WCS ArcGeometry (CCW, +y up)."""
    center_cad = calibration.pixel_to_cad(center_px[0], center_px[1])
    radius_cad = radius_px * calibration.pixel_to_unit_scale

    # Compute start and end points in pixel frame
    r1 = math.radians(start_angle_px_deg)
    r2 = math.radians(end_angle_px_deg)
    p1_px = (center_px[0] + radius_px * math.cos(r1), center_px[1] + radius_px * math.sin(r1))
    p2_px = (center_px[0] + radius_px * math.cos(r2), center_px[1] + radius_px * math.sin(r2))

    # Transform points to CAD WCS
    p1_cad = calibration.pixel_to_cad(*p1_px)
    p2_cad = calibration.pixel_to_cad(*p2_px)

    # CAD angles are CCW from +x: atan2(dy, dx)
    cad_ang1 = math.degrees(math.atan2(p1_cad.y - center_cad.y, p1_cad.x - center_cad.x)) % 360.0
    cad_ang2 = math.degrees(math.atan2(p2_cad.y - center_cad.y, p2_cad.x - center_cad.x)) % 360.0

    # Inverting y reflects CW into CCW. So the arc in CAD goes CCW from p2 to p1!
    return ArcGeometry(
        center=center_cad,
        radius=radius_cad,
        start_angle_deg=round(cad_ang2, 3),
        end_angle_deg=round(cad_ang1, 3),
    )


# ==============================================================================
# Strategy Comparators
# ==============================================================================

class StrategyA_ProductionBaseline:
    """Current Production Baseline in cad_agent/source_verified_geometry.py."""

    @staticmethod
    def materialize(
        *,
        verification_request: object,
        verification_result: object,
        source_render_bytes: bytes,
        calibration: Calibration,
        source_file_name: str,
        image_width_px: int,
        image_height_px: int,
    ) -> PrimitiveIRDocument:
        return prod_materialize_lines(
            verification_request=verification_request,
            verification_result=verification_result,
            source_render_bytes=source_render_bytes,
            calibration=calibration,
            source_file_name=source_file_name,
            image_width_px=image_width_px,
            image_height_px=image_height_px,
        )


class StrategyB_NaiveTypeExpansion:
    """Adds Circle and Arc types, but copies pixel angles naively without CAD winding conversion."""

    @staticmethod
    def materialize(
        *,
        verification_request: Dict[str, Any],
        verification_result: Dict[str, Any],
        calibration: Calibration,
        source_file_name: str,
        image_width_px: int,
        image_height_px: int,
    ) -> PrimitiveIRDocument:
        binding = _binding(verification_request)
        prims: List[Primitive] = []
        for hyp in verification_request.get("primitive_hypotheses", []):
            ptype = hyp["type"]
            pid = hyp["id"]
            if ptype == "LINE":
                s = calibration.pixel_to_cad(*hyp["start_px"])
                e = calibration.pixel_to_cad(*hyp["end_px"])
                geom = LineGeometry(start=s, end=e)
                bbox = (0, 0, 10, 10)
            elif ptype == "CIRCLE":
                c = calibration.pixel_to_cad(*hyp["center_px"])
                r = hyp["radius_px"] * calibration.pixel_to_unit_scale
                geom = CircleGeometry(center=c, radius=r)
                bbox = (0, 0, 10, 10)
            elif ptype == "ARC":
                # Naive: does NOT invert winding!
                c = calibration.pixel_to_cad(*hyp["center_px"])
                r = hyp["radius_px"] * calibration.pixel_to_unit_scale
                geom = ArcGeometry(
                    center=c,
                    radius=r,
                    start_angle_deg=hyp["start_angle_deg"],
                    end_angle_deg=hyp["end_angle_deg"],
                )
                bbox = (0, 0, 10, 10)
            prims.append(
                Primitive(
                    id=pid,
                    type=ptype.lower(),
                    source=_SOURCE_TYPE,
                    confidence=0.9,
                    geometry=geom,
                    trace=Trace(bbox_px=bbox),
                )
            )
        return PrimitiveIRDocument(
            source_document=SourceDocument(source_file_name, binding["page_index"], image_width_px, image_height_px),
            calibration=calibration,
            primitives=prims,
        )


class StrategyC_ForwardCoordinateTransform:
    """Forward-maps centers and lines, but fails on wrap-around arc angular intervals."""

    @staticmethod
    def materialize(
        *,
        verification_request: Dict[str, Any],
        verification_result: Dict[str, Any],
        calibration: Calibration,
        source_file_name: str,
        image_width_px: int,
        image_height_px: int,
    ) -> PrimitiveIRDocument:
        binding = _binding(verification_request)
        prims: List[Primitive] = []
        for hyp in verification_request.get("primitive_hypotheses", []):
            ptype = hyp["type"]
            pid = hyp["id"]
            if ptype == "LINE":
                s = calibration.pixel_to_cad(*hyp["start_px"])
                e = calibration.pixel_to_cad(*hyp["end_px"])
                geom = LineGeometry(start=s, end=e)
            elif ptype == "CIRCLE":
                c = calibration.pixel_to_cad(*hyp["center_px"])
                r = hyp["radius_px"] * calibration.pixel_to_unit_scale
                geom = CircleGeometry(center=c, radius=r)
            elif ptype == "ARC":
                # Negates angle without modulo 360 or winding inversion
                c = calibration.pixel_to_cad(*hyp["center_px"])
                r = hyp["radius_px"] * calibration.pixel_to_unit_scale
                geom = ArcGeometry(
                    center=c,
                    radius=r,
                    start_angle_deg=-hyp["start_angle_deg"],
                    end_angle_deg=-hyp["end_angle_deg"],
                )
            bbox = compute_primitive_bbox_px(hyp)
            prims.append(
                Primitive(
                    id=pid,
                    type=ptype.lower(),
                    source=_SOURCE_TYPE,
                    confidence=0.9,
                    geometry=geom,
                    trace=Trace(bbox_px=bbox),
                )
            )
        return PrimitiveIRDocument(
            source_document=SourceDocument(source_file_name, binding["page_index"], image_width_px, image_height_px),
            calibration=calibration,
            primitives=prims,
        )


class StrategyD_LosslessCurvedMaterializerOracle:
    """Selected Oracle: Polymorphic materializer for LINE, CIRCLE, ARC with exact WCS mapping."""

    @staticmethod
    def materialize(
        *,
        verification_request: Dict[str, Any],
        verification_result: Dict[str, Any],
        source_render_bytes: bytes,
        calibration: Calibration,
        source_file_name: str,
        image_width_px: int,
        image_height_px: int,
        filter_failed_verdicts: bool = True,
    ) -> PrimitiveIRDocument:
        binding = _binding(verification_request)
        if not isinstance(calibration, Calibration) or calibration.status != "verified":
            _fail("EXTERNAL_GEOMETRY_CALIBRATION_UNVERIFIED")
        if calibration.source_sha256 != binding["source_sha256"]:
            _fail("EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH")

        # Dimensions check
        for dim in (image_width_px, image_height_px):
            if not isinstance(dim, int) or dim <= 0:
                _fail("SOURCE_RENDER_DIMENSIONS_INVALID")
        if (image_width_px, image_height_px) != _render_dimensions(source_render_bytes):
            _fail("SOURCE_RENDER_DIMENSION_MISMATCH")

        hypotheses = verification_request.get("primitive_hypotheses", [])
        supports = verification_result.get("primitive_support", [])
        support_by_id = {item["primitive_hypothesis_id"]: item for item in supports}

        request_sha256 = _sha256(
            verification_request.get("verification_request_sha256"),
            "VERIFICATION_REQUEST_INVALID",
        )
        result_sha256 = canonical_json_sha256(verification_result)

        primitives: List[Primitive] = []
        for hyp in hypotheses:
            pid = hyp.get("id")
            ptype = hyp.get("type")
            support = support_by_id.get(pid)
            if not isinstance(support, Mapping):
                _fail("VERIFICATION_RESULT_INVALID")

            # Filter failed hypotheses
            if filter_failed_verdicts:
                verdict = support.get("verdict", "PASS")
                if verdict != "PASS" or float(support.get("support_fraction", 0.0)) < 0.20:
                    continue

            confidence = float(support.get("support_fraction", 0.9))
            bbox = compute_primitive_bbox_px(hyp)

            geom: Any = None
            if ptype == "LINE":
                s = calibration.pixel_to_cad(*hyp["start_px"])
                e = calibration.pixel_to_cad(*hyp["end_px"])
                geom = LineGeometry(start=s, end=e)
            elif ptype == "CIRCLE":
                c = calibration.pixel_to_cad(*hyp["center_px"])
                r = float(hyp["radius_px"]) * calibration.pixel_to_unit_scale
                geom = CircleGeometry(center=c, radius=r)
            elif ptype == "ARC":
                geom = pixel_arc_to_cad_arc(
                    center_px=hyp["center_px"],
                    radius_px=float(hyp["radius_px"]),
                    start_angle_px_deg=float(hyp["start_angle_deg"]),
                    end_angle_px_deg=float(hyp["end_angle_deg"]),
                    calibration=calibration,
                )
            else:
                _fail("VERIFICATION_REQUEST_INVALID")

            primitives.append(
                Primitive(
                    id=pid,
                    type=ptype.lower(),
                    source=_SOURCE_TYPE,
                    confidence=round(confidence, 3),
                    geometry=geom,
                    trace=Trace(
                        bbox_px=bbox,
                        extraction_tool=_TRACE_TOOL,
                        extracted_at=now_iso(),
                        verification_request_sha256=request_sha256,
                        verification_result_sha256=result_sha256,
                    ),
                )
            )

        return PrimitiveIRDocument(
            source_document=SourceDocument(
                file_name=source_file_name,
                page_index=binding["page_index"],
                image_width_px=image_width_px,
                image_height_px=image_height_px,
                sha256=binding["source_sha256"],
            ),
            calibration=calibration,
            primitives=primitives,
        )
