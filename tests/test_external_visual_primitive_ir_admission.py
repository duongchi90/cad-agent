from __future__ import annotations

import copy
import hashlib
import io

import pytest
from PIL import Image, ImageDraw

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import compile_external_visual_object_proposal
from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support
from cad_agent.source_verified_geometry import materialize_verified_external_visual_lines
from primitive_ir_lib.models import Calibration, LineGeometry


def _verified_case() -> tuple[dict[str, object], dict[str, object], bytes]:
    image = Image.new("L", (64, 64), 255)
    ImageDraw.Draw(image).line((10, 10, 30, 10), fill=0, width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()
    binding = {
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
        "roi_bbox_px": [0, 0, 63, 63],
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "edge-1", "type": "LINE", "start_px": [10, 10], "end_px": [30, 10]}
        ],
        "object_groups": [
            {
                "group_id": "group-1",
                "proposed_label": "UNKNOWN_BOUNDARY",
                "primitive_hypothesis_ids": ["edge-1"],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
        expected_calibration_binding=_calibration().to_dict(),
    )
    result = verify_external_visual_proposal_source_support(
        verification_request=request,
        source_render_bytes=render_bytes,
    )
    return request, result, render_bytes


def _calibration(source_sha256: str = "1" * 64) -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=2.0,
        origin_px=(0.0, 64.0),
        method="manual_override",
        reference_note="test exact source-bound calibration",
        status="verified",
        source_sha256=source_sha256,
    )


def test_verified_external_line_materializes_truthful_source_bound_primitive_ir() -> None:
    request, result, render_bytes = _verified_case()

    doc = materialize_verified_external_visual_lines(
        verification_request=request,
        verification_result=result,
        source_render_bytes=render_bytes,
        calibration=_calibration(),
        source_file_name="source.png",
        image_width_px=64,
        image_height_px=64,
    )

    assert doc.source_document.sha256 == "1" * 64
    assert doc.calibration.source_sha256 == "1" * 64
    assert len(doc.primitives) == 1
    primitive = doc.primitives[0]
    assert primitive.id == "edge-1"
    assert primitive.source == "geometry_external_ai"
    assert isinstance(primitive.geometry, LineGeometry)
    assert primitive.geometry.start.x == 20.0
    assert primitive.geometry.start.y == 108.0
    assert primitive.geometry.end.x == 60.0
    assert primitive.geometry.end.y == 108.0
    assert primitive.trace.verification_request_sha256 == request["verification_request_sha256"]
    assert primitive.trace.verification_result_sha256 == canonical_json_sha256(result)


def test_admission_rejects_caller_tampered_verification_result() -> None:
    request, result, render_bytes = _verified_case()
    tampered = copy.deepcopy(result)
    support = tampered["primitive_support"]
    assert isinstance(support, list)
    assert isinstance(support[0], dict)
    support[0]["support_fraction"] = 0.1

    with pytest.raises(ValueError, match="SOURCE_SUPPORT_RESULT_MISMATCH"):
        materialize_verified_external_visual_lines(
            verification_request=request,
            verification_result=tampered,
            source_render_bytes=render_bytes,
            calibration=_calibration(),
            source_file_name="source.png",
            image_width_px=64,
            image_height_px=64,
        )


def test_admission_rejects_calibration_bound_to_different_source() -> None:
    request, result, render_bytes = _verified_case()

    with pytest.raises(ValueError, match="EXTERNAL_GEOMETRY_CALIBRATION_SOURCE_MISMATCH"):
        materialize_verified_external_visual_lines(
            verification_request=request,
            verification_result=result,
            source_render_bytes=render_bytes,
            calibration=_calibration("2" * 64),
            source_file_name="source.png",
            image_width_px=64,
            image_height_px=64,
        )


def test_admission_rejects_same_source_with_tampered_calibration_transform() -> None:
    request, result, render_bytes = _verified_case()
    tampered = Calibration(
        unit="mm",
        pixel_to_unit_scale=3.0,
        origin_px=(7.0, 59.0),
        method="manual_override",
        reference_note="same source, different transform",
        status="verified",
        source_sha256="1" * 64,
    )

    with pytest.raises(ValueError, match="EXTERNAL_GEOMETRY_CALIBRATION_IDENTITY_MISMATCH"):
        materialize_verified_external_visual_lines(
            verification_request=request,
            verification_result=result,
            source_render_bytes=render_bytes,
            calibration=tampered,
            source_file_name="source.png",
            image_width_px=64,
            image_height_px=64,
        )


def test_admission_rejects_request_without_calibration_binding() -> None:
    request, _bound_result, render_bytes = _verified_case()
    unbound_request = dict(request)
    unbound_request.pop("exact_calibration_binding")
    unbound_request.pop("verification_request_sha256")
    unbound_request["verification_request_sha256"] = canonical_json_sha256(unbound_request)
    result = verify_external_visual_proposal_source_support(
        verification_request=unbound_request,
        source_render_bytes=render_bytes,
    )

    with pytest.raises(ValueError, match="EXTERNAL_GEOMETRY_CALIBRATION_BINDING_MISSING"):
        materialize_verified_external_visual_lines(
            verification_request=unbound_request,
            verification_result=result,
            source_render_bytes=render_bytes,
            calibration=_calibration(),
            source_file_name="source.png",
            image_width_px=64,
            image_height_px=64,
        )
