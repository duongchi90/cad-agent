"""Materialize exact, source-bound external visual geometry into PrimitiveIR.

The external proposal remains non-semantic.  This adapter only admits LINE
hypotheses after the existing deterministic source-support verifier recomputes
the supplied result from the exact render bytes.
"""

from __future__ import annotations

import io
import re
from collections.abc import Mapping

from PIL import Image

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import _normalize_calibration_binding
from cad_agent.source_support_verifier import (
    verify_external_visual_proposal_source_support,
)
from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
    now_iso,
)

__all__ = ["materialize_verified_external_visual_lines"]


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
        or any(isinstance(value, bool) or not isinstance(value, int) for value in roi)
    ):
        _fail("SOURCE_BINDING_INVALID")
    return binding


def _primitive_bbox(start: list[int], end: list[int]) -> tuple[int, int, int, int]:
    return (
        min(start[0], end[0]),
        min(start[1], end[1]),
        max(start[0], end[0]),
        max(start[1], end[1]),
    )


def materialize_verified_external_visual_lines(
    *,
    verification_request: object,
    verification_result: object,
    source_render_bytes: bytes,
    calibration: Calibration,
    source_file_name: str,
    image_width_px: int,
    image_height_px: int,
) -> PrimitiveIRDocument:
    """Create a truthful PrimitiveIR document from verified external LINEs.

    The result is accepted only when the current verifier reproduces it exactly;
    caller-supplied support scores or semantic/group labels are never trusted.
    """

    binding = _binding(verification_request)
    expected_result = verify_external_visual_proposal_source_support(
        verification_request=verification_request,
        source_render_bytes=source_render_bytes,
    )
    if not isinstance(verification_result, Mapping) or dict(verification_result) != expected_result:
        _fail("SOURCE_SUPPORT_RESULT_MISMATCH")

    if not isinstance(calibration, Calibration) or calibration.status != "verified":
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_UNVERIFIED")
    if calibration.source_sha256 != binding["source_sha256"]:
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH")
    calibration_binding = verification_request.get("exact_calibration_binding")
    if calibration_binding is None:
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_BINDING_MISSING")
    expected_calibration = _normalize_calibration_binding(
        calibration_binding,
        source_sha256=binding["source_sha256"],
        code="EXTERNAL_GEOMETRY_CALIBRATION_BINDING_INVALID",
    )
    actual_calibration = _normalize_calibration_binding(
        calibration.to_dict(),
        source_sha256=binding["source_sha256"],
        code="EXTERNAL_GEOMETRY_CALIBRATION_BINDING_INVALID",
    )
    if actual_calibration != expected_calibration:
        _fail("EXTERNAL_GEOMETRY_CALIBRATION_IDENTITY_MISMATCH")
    if not isinstance(source_file_name, str) or not source_file_name:
        _fail("SOURCE_FILE_NAME_INVALID")
    for value in (image_width_px, image_height_px):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            _fail("SOURCE_RENDER_DIMENSIONS_INVALID")
    if (image_width_px, image_height_px) != _render_dimensions(source_render_bytes):
        _fail("SOURCE_RENDER_DIMENSION_MISMATCH")

    hypotheses = verification_request.get("primitive_hypotheses")
    supports = expected_result.get("primitive_support")
    if not isinstance(hypotheses, list) or not isinstance(supports, list):
        _fail("VERIFICATION_RESULT_INVALID")
    support_by_id = {item["primitive_hypothesis_id"]: item for item in supports}

    request_sha256 = _sha256(
        verification_request.get("verification_request_sha256"),
        "VERIFICATION_REQUEST_INVALID",
    )
    result_sha256 = canonical_json_sha256(expected_result)
    primitives: list[Primitive] = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, Mapping) or hypothesis.get("type") != "LINE":
            _fail("VERIFICATION_REQUEST_INVALID")
        primitive_id = hypothesis.get("id")
        start_px = hypothesis.get("start_px")
        end_px = hypothesis.get("end_px")
        support = support_by_id.get(primitive_id)
        if (
            not isinstance(primitive_id, str)
            or not isinstance(start_px, list)
            or not isinstance(end_px, list)
            or len(start_px) != 2
            or len(end_px) != 2
            or not isinstance(support, Mapping)
        ):
            _fail("VERIFICATION_RESULT_INVALID")
        start = calibration.pixel_to_cad(*start_px)
        end = calibration.pixel_to_cad(*end_px)
        primitives.append(
            Primitive(
                id=primitive_id,
                type="line",
                source=_SOURCE_TYPE,
                confidence=float(support["support_fraction"]),
                geometry=LineGeometry(start=start, end=end),
                trace=Trace(
                    bbox_px=_primitive_bbox(start_px, end_px),
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
