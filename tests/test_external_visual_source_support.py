from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image, ImageDraw

from cad_agent.source_fusion_proposal import compile_external_visual_object_proposal
from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support


def _render_bytes() -> bytes:
    image = Image.new("L", (64, 64), 255)
    ImageDraw.Draw(image).rectangle((10, 10, 30, 30), outline=0, width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _circle_case(
    *, center: tuple[float, float] = (32.0, 32.0), proposal_radius: float = 10.0,
    rendered_radius: float = 10.0,
) -> tuple[dict[str, object], bytes]:
    image = Image.new("L", (64, 64), 255)
    ImageDraw.Draw(image).ellipse(
        (
            center[0] - rendered_radius,
            center[1] - rendered_radius,
            center[0] + rendered_radius,
            center[1] + rendered_radius,
        ),
        outline=0,
        width=1,
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()
    binding = {
        "source_sha256": "4" * 64,
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
            {
                "id": "hole-1",
                "type": "CIRCLE",
                "center_px": list(center),
                "radius_px": proposal_radius,
            }
        ],
        "object_groups": [
            {
                "group_id": "hole-group",
                "proposed_label": "UNKNOWN_HOLE",
                "primitive_hypothesis_ids": ["hole-1"],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
    )
    return request, render_bytes


def _request(*, include_unsupported_connector: bool) -> tuple[dict[str, object], bytes]:
    render_bytes = _render_bytes()
    render_sha256 = hashlib.sha256(render_bytes).hexdigest()
    binding = {
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": render_sha256,
        "roi_bbox_px": [0, 0, 63, 63],
    }
    primitives: list[dict[str, object]] = [
        {"id": "top", "type": "LINE", "start_px": [10, 10], "end_px": [30, 10]},
        {"id": "right", "type": "LINE", "start_px": [30, 10], "end_px": [30, 30]},
        {"id": "bottom", "type": "LINE", "start_px": [30, 30], "end_px": [10, 30]},
        {"id": "left", "type": "LINE", "start_px": [10, 30], "end_px": [10, 10]},
    ]
    if include_unsupported_connector:
        primitives.append(
            {
                "id": "invented_connector",
                "type": "LINE",
                "start_px": [30, 10],
                "end_px": [50, 30],
            }
        )
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": primitives,
        "object_groups": [
            {
                "group_id": "housing-001",
                "proposed_label": "MIRROR_HOUSING",
                "primitive_hypothesis_ids": ["top", "right", "bottom", "left"],
            }
        ],
        "excluded_memberships": (
            [
                {
                    "primitive_hypothesis_id": "invented_connector",
                    "excluded_group_id": "housing-001",
                }
            ]
            if include_unsupported_connector
            else []
        ),
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
    )
    return request, render_bytes


def test_source_support_accepts_real_strokes_and_rejects_invented_connector() -> None:
    supported_request, render_bytes = _request(include_unsupported_connector=False)
    supported = verify_external_visual_proposal_source_support(
        verification_request=supported_request,
        source_render_bytes=render_bytes,
    )
    assert supported["status"] == "VERIFIED"
    assert {item["primitive_hypothesis_id"] for item in supported["primitive_support"]} == {
        "top",
        "right",
        "bottom",
        "left",
    }

    contaminated_request, render_bytes = _request(include_unsupported_connector=True)
    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:invented_connector"):
        verify_external_visual_proposal_source_support(
            verification_request=contaminated_request,
            source_render_bytes=render_bytes,
        )


def test_source_support_rejects_tampered_verification_request_digest() -> None:
    request, render_bytes = _request(include_unsupported_connector=False)
    primitives = request["primitive_hypotheses"]
    assert isinstance(primitives, list)
    first = primitives[0]
    assert isinstance(first, dict)
    first["end_px"] = [29, 10]

    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_HASH_MISMATCH"):
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=render_bytes,
        )


def test_source_support_does_not_leak_across_exact_roi_boundary() -> None:
    image = Image.new("L", (32, 32), 255)
    ImageDraw.Draw(image).line((9, 10, 9, 20), fill=0, width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()
    binding = {
        "source_sha256": "2" * 64,
        "page_index": 0,
        "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
        "roi_bbox_px": [10, 10, 20, 20],
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "inside_line",
                "type": "LINE",
                "start_px": [10, 10],
                "end_px": [10, 20],
            }
        ],
        "object_groups": [
            {
                "group_id": "boundary-001",
                "proposed_label": "UNKNOWN_BOUNDARY",
                "primitive_hypothesis_ids": ["inside_line"],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
    )

    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:inside_line"):
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=render_bytes,
        )


@pytest.mark.parametrize(
    "profile_override",
    [
        {"darkness_threshold": 255},
        {"endpoint_tolerance_px": 16},
        {"min_support_fraction": 0.01},
    ],
)
def test_source_support_rejects_caller_controlled_verification_profile(
    profile_override: dict[str, int | float],
) -> None:
    image = Image.new("L", (32, 32), 255)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()
    binding = {
        "source_sha256": "3" * 64,
        "page_index": 0,
        "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
        "roi_bbox_px": [5, 5, 25, 25],
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "unsupported_white_line",
                "type": "LINE",
                "start_px": [8, 10],
                "end_px": [22, 10],
            }
        ],
        "object_groups": [
            {
                "group_id": "unknown-001",
                "proposed_label": "UNKNOWN_BOUNDARY",
                "primitive_hypothesis_ids": ["unsupported_white_line"],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
    )

    with pytest.raises(ValueError, match="SOURCE_SUPPORT_PROFILE_OVERRIDE_NOT_ALLOWED"):
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=render_bytes,
            **profile_override,
        )


def test_source_support_accepts_source_bound_circle_circumference() -> None:
    request, render_bytes = _circle_case()

    result = verify_external_visual_proposal_source_support(
        verification_request=request,
        source_render_bytes=render_bytes,
    )

    assert result["status"] == "VERIFIED"
    support = result["primitive_support"]
    assert isinstance(support, list)
    assert support[0]["primitive_hypothesis_id"] == "hole-1"
    assert support[0]["sample_count"] > 50
    assert support[0]["support_fraction"] >= 0.85


def test_source_support_rejects_circle_with_wrong_render_hash() -> None:
    request, render_bytes = _circle_case()

    with pytest.raises(ValueError, match="SOURCE_RENDER_HASH_MISMATCH"):
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=render_bytes + b"tampered",
        )


def test_source_support_rejects_circle_outside_roi() -> None:
    with pytest.raises(ValueError, match="PRIMITIVE_OUTSIDE_ROI"):
        _circle_case(center=(5.0, 5.0), proposal_radius=10.0)


def test_source_support_rejects_insufficient_circle_circumference_support() -> None:
    request, render_bytes = _circle_case(rendered_radius=5.0)

    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:hole-1"):
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=render_bytes,
        )
