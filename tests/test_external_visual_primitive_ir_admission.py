from __future__ import annotations

import copy
import hashlib
import importlib
import io

import pytest
from PIL import Image, ImageDraw

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_fusion_proposal import compile_external_visual_object_proposal
from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support
from cad_agent.source_verified_geometry import materialize_verified_external_visual_lines
from primitive_ir_lib.geometry_alignment import AnchorPair
from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    Trace,
)


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


def _verified_target_case(
    lines: list[tuple[str, int]], calibration: Calibration | None = None
) -> dict[str, object]:
    if calibration is None:
        calibration = _calibration()
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    for _primitive_id, y in lines:
        draw.line((10, y, 30, y), fill=0, width=1)
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
        "view_role_proposal": "SIDE",
        "primitive_hypotheses": [
            {"id": primitive_id, "type": "LINE", "start_px": [10, y], "end_px": [30, y]}
            for primitive_id, y in lines
        ],
        "object_groups": [
            {
                "group_id": "opaque-group",
                "proposed_label": "UNKNOWN_BOUNDARY",
                "primitive_hypothesis_ids": [primitive_id for primitive_id, _y in lines],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
        expected_calibration_binding=calibration.to_dict(),
    )
    support = verify_external_visual_proposal_source_support(
        verification_request=request,
        source_render_bytes=render_bytes,
    )
    document = materialize_verified_external_visual_lines(
        verification_request=request,
        verification_result=support,
        source_render_bytes=render_bytes,
        calibration=calibration,
        source_file_name="synthetic-target.png",
        image_width_px=64,
        image_height_px=64,
    )
    return {
        "document": document,
        "request": request,
        "result": support,
        "render_bytes": render_bytes,
        "calibration": calibration,
    }


def _compose_line_delta(
    base_lines: list[dict[str, object]],
    target_case: dict[str, object],
    *,
    max_correspondence_residual: float = 10.0,
    keep_tolerance: float = 0.01,
    target_to_base_alignment_anchors: list[AnchorPair] | None = None,
):
    module = importlib.import_module("cad_agent.source_fusion_proposal")
    composer = getattr(module, "compose_verified_native_line_delta", None)
    if not callable(composer):
        return None
    if target_to_base_alignment_anchors is None:
        target_to_base_alignment_anchors = [
            AnchorPair("align-origin", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
            AnchorPair("align-x", (10.0, 0.0), (10.0, 0.0), "DATUM", 1.0),
        ]
    return composer(
        base_native_line_observations=base_lines,
        verified_target_document=target_case["document"],
        verification_request=target_case["request"],
        verification_result=target_case["result"],
        source_render_bytes=target_case["render_bytes"],
        calibration=target_case["calibration"],
        base_coordinate_unit=target_case["calibration"].unit,
        max_correspondence_residual=max_correspondence_residual,
        keep_tolerance=keep_tolerance,
        target_to_base_alignment_anchors=target_to_base_alignment_anchors,
        max_alignment_residual=0.001,
    )


def _delta_geometry(result: dict[str, object]) -> list[tuple[tuple[float, ...], ...]]:
    deltas = result["bounded_native_line_deltas"]
    assert isinstance(deltas, list)
    return sorted(
        (
            tuple(delta["before"]["start"]),
            tuple(delta["before"]["end"]),
            tuple(delta["after"]["start"]),
            tuple(delta["after"]["end"]),
        )
        for delta in deltas
    )


def test_existing_proposal_seam_derives_only_the_supported_bounded_line_delta() -> None:
    base = [
        {"observation_id": "base-opaque-a", "start": [20.0, 104.0], "end": [60.0, 104.0]},
        {"observation_id": "base-opaque-b", "start": [20.0, 68.0], "end": [60.0, 68.0]},
    ]
    target = _verified_target_case([("target-shifted", 10), ("target-kept", 30)])

    proposal = _compose_line_delta(base, target)

    # This is a behavioral oracle, not an API-presence test: it requires a unique
    # geometry-derived before/after proposal while remaining non-authoritative.
    assert proposal == {
        "status": "PROPOSAL_ONLY",
        "correspondence_status": "UNIQUE",
        "base_target_correspondence": [
            {
                "base_observation_id": "base-opaque-a",
                "target_primitive_id": "target-shifted",
                "disposition": "CHANGE",
                "residual": 4.0,
            },
            {
                "base_observation_id": "base-opaque-b",
                "target_primitive_id": "target-kept",
                "disposition": "KEEP",
                "residual": 0.0,
            },
        ],
        "geometry_tolerance": {
            "unit": "mm",
            "max_correspondence_residual": 10.0,
            "keep_tolerance": 0.01,
        },
        "target_to_base_alignment": {
            "status": "ALIGNED",
            "method": "VERIFIED_ANCHOR_SIMILARITY",
            "coordinate_unit": "mm",
            "anchor_pairs": [
                {
                    "anchor_id": "align-origin",
                    "base": [0.0, 0.0],
                    "target": [0.0, 0.0],
                    "authority": "DATUM",
                    "confidence": 1.0,
                },
                {
                    "anchor_id": "align-x",
                    "base": [10.0, 0.0],
                    "target": [10.0, 0.0],
                    "authority": "DATUM",
                    "confidence": 1.0,
                },
            ],
            "matrix": [[1.0, -0.0, 0.0], [0.0, 1.0, 0.0]],
            "uniform_scale": 1.0,
            "scale_tolerance": 1e-6,
            "residual_rms": 0.0,
            "max_residual": 0.001,
        },
        "bounded_native_line_deltas": [
            {
                "base_observation_id": "base-opaque-a",
                "target_primitive_id": "target-shifted",
                "before": {"start": [20.0, 104.0], "end": [60.0, 104.0]},
                "after": {"start": [20.0, 108.0], "end": [60.0, 108.0]},
            }
        ],
        "semantic_label_authority": "NONE",
        "cad_mutation": False,
    }

    permuted_base = [
        {"observation_id": "native-y", "start": [20.0, 68.0], "end": [60.0, 68.0]},
        {"observation_id": "native-x", "start": [20.0, 104.0], "end": [60.0, 104.0]},
    ]
    permuted_target = _verified_target_case([("visual-z", 30), ("visual-m", 10)])
    permuted = _compose_line_delta(permuted_base, permuted_target)
    assert isinstance(permuted, dict)
    assert permuted["correspondence_status"] == "UNIQUE"
    assert _delta_geometry(permuted) == _delta_geometry(proposal)

    ambiguous_target = _verified_target_case([("unresolved-target", 21)])
    ambiguous = _compose_line_delta(
        base, ambiguous_target, max_correspondence_residual=20.0
    )
    assert isinstance(ambiguous, dict)
    assert ambiguous["correspondence_status"] == "AMBIGUOUS"
    assert ambiguous["bounded_native_line_deltas"] == []


def test_sheet_translation_is_aligned_before_native_line_delta_matching() -> None:
    translated_calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=2.0,
        origin_px=(0.0, 66.0),
        method="manual_override",
        status="verified",
        source_sha256="1" * 64,
    )
    target = _verified_target_case(
        [("target-a", 10), ("target-b", 30)], translated_calibration
    )
    base = [
        {"observation_id": "base-a", "start": [20.0, 108.0], "end": [60.0, 108.0]},
        {"observation_id": "base-b", "start": [20.0, 68.0], "end": [60.0, 68.0]},
    ]
    alignment = [
        AnchorPair("datum-origin", (0.0, 0.0), (0.0, 4.0), "DATUM", 1.0),
        AnchorPair("datum-x", (10.0, 0.0), (10.0, 4.0), "DATUM", 1.0),
    ]

    result = _compose_line_delta(
        base,
        target,
        target_to_base_alignment_anchors=alignment,
    )

    assert isinstance(result, dict)
    assert result["correspondence_status"] == "UNIQUE"
    assert [item["disposition"] for item in result["base_target_correspondence"]] == [
        "KEEP",
        "KEEP",
    ]
    assert all(item["residual"] <= 0.01 for item in result["base_target_correspondence"])
    assert result["bounded_native_line_deltas"] == []
    assert result["target_to_base_alignment"]["method"] == "VERIFIED_ANCHOR_SIMILARITY"
    assert result["target_to_base_alignment"]["uniform_scale"] == 1.0
    assert result["target_to_base_alignment"]["scale_tolerance"] == 1e-6


def test_non_unit_similarity_cannot_hide_native_line_dimension_change() -> None:
    changed_scale_calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=2.4,
        origin_px=(0.0, 64.0),
        method="manual_override",
        reference_note="test exact source-bound calibration",
        status="verified",
        source_sha256="1" * 64,
    )
    target = _verified_target_case(
        [("dimension-changed-target", 10)], changed_scale_calibration
    )
    base = [
        {"observation_id": "base-line", "start": [20.0, 108.0], "end": [60.0, 108.0]}
    ]
    anchors = [
        AnchorPair("datum-origin", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("datum-x", (40.0, 0.0), (48.0, 0.0), "DATUM", 1.0),
    ]

    with pytest.raises(ValueError, match="TARGET_BASE_ALIGNMENT_SCALE_UNPROVEN"):
        _compose_line_delta(
            base,
            target,
            target_to_base_alignment_anchors=anchors,
        )


def test_line_delta_refuses_unproven_target_to_base_alignment() -> None:
    target = _verified_target_case([("target-line", 10)])

    with pytest.raises(ValueError, match="TARGET_BASE_ALIGNMENT_UNPROVEN"):
        _compose_line_delta(
            [{"observation_id": "base-line", "start": [20.0, 108.0], "end": [60.0, 108.0]}],
            target,
            target_to_base_alignment_anchors=[
                AnchorPair("only-one-datum", (10.0, 10.0), (10.0, 10.0), "DATUM", 1.0)
            ],
        )


def test_existing_proposal_seam_rejects_unverified_target_primitive() -> None:
    target = _verified_target_case([("target-line", 10)])
    target["document"].primitives[0].trace.extraction_tool = "unverified"

    with pytest.raises(ValueError, match="VERIFIED_TARGET_EVIDENCE_MISMATCH"):
        _compose_line_delta(
            [{"observation_id": "base-line", "start": [20.0, 104.0], "end": [60.0, 104.0]}],
            target,
        )


def test_far_target_line_has_no_supported_correspondence() -> None:
    target = _verified_target_case([("far-target", 10)])
    result = _compose_line_delta(
        [{"observation_id": "base-line", "start": [20.0, 1000.0], "end": [60.0, 1000.0]}],
        target,
        max_correspondence_residual=10.0,
    )

    assert isinstance(result, dict)
    assert result["correspondence_status"] == "NO_SUPPORTED_DELTA"
    assert result["base_target_correspondence"] == []
    assert result["bounded_native_line_deltas"] == []


def test_small_calibrated_residual_is_classified_as_keep() -> None:
    calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.0001,
        origin_px=(0.0, 64.0),
        method="manual_override",
        status="verified",
        source_sha256="1" * 64,
    )
    target = _verified_target_case([("slightly-shifted", 10)], calibration)
    result = _compose_line_delta(
        [
            {
                "observation_id": "base-line",
                "start": [0.001, 0.0053],
                "end": [0.003, 0.0053],
            }
        ],
        target,
        max_correspondence_residual=0.001,
        keep_tolerance=0.0002,
    )

    assert isinstance(result, dict)
    assert result["correspondence_status"] == "UNIQUE"
    assert result["base_target_correspondence"][0]["disposition"] == "KEEP"
    assert result["bounded_native_line_deltas"] == []


def test_manually_constructed_target_without_matching_support_evidence_is_rejected() -> None:
    target = _verified_target_case([("target-line", 10)])
    actual = target["document"]
    source_primitive = actual.primitives[0]
    forged_primitive = Primitive(
        id=source_primitive.id,
        type="line",
        source="geometry_external_ai",
        confidence=source_primitive.confidence,
        geometry=LineGeometry(
            start=Point2D(20.0, 88.0),
            end=Point2D(60.0, 88.0),
        ),
        trace=Trace(
            bbox_px=(10, 20, 30, 20),
            extraction_tool="external-ai-verified-source-support-v1",
            extracted_at=source_primitive.trace.extracted_at,
            verification_request_sha256="a" * 64,
            verification_result_sha256="b" * 64,
        ),
    )
    target["document"] = PrimitiveIRDocument(
        source_document=actual.source_document,
        calibration=actual.calibration,
        primitives=[forged_primitive],
    )

    with pytest.raises(ValueError, match="VERIFIED_TARGET_EVIDENCE_MISMATCH"):
        _compose_line_delta(
            [{"observation_id": "base-line", "start": [20.0, 88.0], "end": [60.0, 88.0]}],
            target,
        )
