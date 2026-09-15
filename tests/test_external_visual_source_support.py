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
        endpoint_tolerance_px=1,
        min_support_fraction=0.90,
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
            endpoint_tolerance_px=1,
            min_support_fraction=0.90,
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
            endpoint_tolerance_px=1,
            min_support_fraction=0.90,
        )
