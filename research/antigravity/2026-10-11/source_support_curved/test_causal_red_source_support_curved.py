"""Public Causal RED for Source Support Curved Primitive Verification.

Reproduces 5 critical baseline failure modes on:
- cad_agent.source_support_verifier.verify_external_visual_proposal_source_support
"""

import sys
from pathlib import Path
import hashlib
import io
import pytest
import numpy as np
from PIL import Image, ImageDraw

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support
from source_support_curved_engine import verify_source_support_strategy_d


def _make_signed_request(
    primitives: list,
    render_bytes: bytes,
    roi_bbox: list = [0, 0, 63, 63],
) -> dict:
    render_sha256 = hashlib.sha256(render_bytes).hexdigest()
    binding = {
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": render_sha256,
        "roi_bbox_px": roi_bbox,
    }
    request = {
        "kind": "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST",
        "status": "PROPOSAL_ONLY",
        "proposal_source": "external_ai",
        "semantic_label_authority": "NONE",
        "primitive_ir_materialized": False,
        "cad_mutation": False,
        "checks_required": ["PER_PRIMITIVE_SOURCE_SUPPORT"],
        "exact_source_binding": binding,
        "primitive_hypotheses": primitives,
    }
    request["verification_request_sha256"] = canonical_json_sha256(request)
    return request


def test_red_1_circle_primitive_causes_unhandled_crash():
    """RED 1: Proposing a CIRCLE primitive hard-crashes with VERIFICATION_REQUEST_INVALID."""
    # Render a real circle (hole) at (32, 32) with radius 15
    img = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(img)
    draw.ellipse([32 - 15, 32 - 15, 32 + 15, 32 + 15], outline=0, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    circle_prim = {
        "id": "hole_1",
        "type": "CIRCLE",
        "center_px": [32, 32],
        "radius_px": 15.0,
    }
    req = _make_signed_request([circle_prim], render_bytes)

    # Production verifier FAILS with unhandled exception on type != "LINE"
    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_INVALID"):
        verify_external_visual_proposal_source_support(
            verification_request=req,
            source_render_bytes=render_bytes,
        )

    # Strategy D verifies the circle via arc-length sampling
    res_d = verify_source_support_strategy_d(
        roi_bbox=[0, 0, 63, 63],
        primitives=[circle_prim],
        source_render_bytes=render_bytes,
    )
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True
    assert res_d["primitive_support"][0]["support_fraction"] > 0.90


def test_red_2_arc_primitive_causes_unhandled_crash():
    """RED 2: Proposing an ARC primitive hard-crashes with VERIFICATION_REQUEST_INVALID."""
    # Render a real 90° arc at (30, 30) with radius 15
    img = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(img)
    draw.arc([30 - 15, 30 - 15, 30 + 15, 30 + 15], start=0, end=90, fill=0, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    arc_prim = {
        "id": "fillet_1",
        "type": "ARC",
        "center_px": [30, 30],
        "radius_px": 15.0,
        "start_angle_deg": 0.0,
        "end_angle_deg": 90.0,
    }
    req = _make_signed_request([arc_prim], render_bytes)

    # Production verifier FAILS with unhandled exception
    with pytest.raises(ValueError, match="VERIFICATION_REQUEST_INVALID"):
        verify_external_visual_proposal_source_support(
            verification_request=req,
            source_render_bytes=render_bytes,
        )

    # Strategy D verifies the arc
    res_d = verify_source_support_strategy_d(
        roi_bbox=[0, 0, 63, 63],
        primitives=[arc_prim],
        source_render_bytes=render_bytes,
    )
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True
    assert res_d["primitive_support"][0]["support_fraction"] > 0.85


def test_red_3_all_or_nothing_crash_destroys_batch_validation():
    """RED 3: Single unsupported connector line destroys verification of 4 valid lines."""
    img = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 30, 30], outline=0, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    primitives = [
        {"id": "top", "type": "LINE", "start_px": [10, 10], "end_px": [30, 10]},
        {"id": "right", "type": "LINE", "start_px": [30, 10], "end_px": [30, 30]},
        {"id": "bottom", "type": "LINE", "start_px": [30, 30], "end_px": [10, 30]},
        {"id": "left", "type": "LINE", "start_px": [10, 30], "end_px": [10, 10]},
        # Invented unsupported connector
        {"id": "invented", "type": "LINE", "start_px": [30, 10], "end_px": [50, 30]},
    ]
    req = _make_signed_request(primitives, render_bytes)

    # Production verifier crashes entirely, discarding the 4 valid lines
    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:invented"):
        verify_external_visual_proposal_source_support(
            verification_request=req,
            source_render_bytes=render_bytes,
        )

    # Strategy D returns structured result without raising
    res_d = verify_source_support_strategy_d(
        roi_bbox=[0, 0, 63, 63],
        primitives=primitives,
        source_render_bytes=render_bytes,
    )
    assert res_d["status"] == "PARTIAL_VERIFIED"
    support_map = {item["primitive_hypothesis_id"]: item["supported"] for item in res_d["primitive_support"]}
    assert support_map["top"] is True
    assert support_map["right"] is True
    assert support_map["bottom"] is True
    assert support_map["left"] is True
    assert support_map["invented"] is False


def test_red_4_dashed_line_proposal_fails_support_threshold():
    """RED 4: Standard dashed hidden line proposal rejected under rigid 0.85 requirement."""
    img = Image.new("L", (100, 64), 255)
    draw = ImageDraw.Draw(img)
    # Draw dashed line from (10, 20) to (90, 20): 8px dash, 12px gap (~57% dilated ink support)
    for x in range(10, 90, 20):
        draw.line([(x, 20), (x + 7, 20)], fill=0, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    dashed_prim = {
        "id": "hidden_1",
        "type": "LINE",
        "start_px": [10, 20],
        "end_px": [90, 20],
        "style": "dashed",
    }
    req = _make_signed_request([dashed_prim], render_bytes, roi_bbox=[0, 0, 99, 63])

    # Production verifier crashes because support fraction ~ 0.57 < 0.85
    with pytest.raises(ValueError, match="PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:hidden_1"):
        verify_external_visual_proposal_source_support(
            verification_request=req,
            source_render_bytes=render_bytes,
        )

    # Strategy D accepts dashed lines via style-aware threshold (>= 0.45)
    res_d = verify_source_support_strategy_d(
        roi_bbox=[0, 0, 99, 63],
        primitives=[dashed_prim],
        source_render_bytes=render_bytes,
    )
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True


def test_red_5_inverted_background_blueprint_false_support_pass():
    """RED 5: Fixed 220 threshold treats dark blueprint background as 100% ink, passing hallucinated lines."""
    # Inverted blueprint: black background (0)
    img = Image.new("L", (64, 64), 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    # Completely invented line through empty space
    phantom_prim = {
        "id": "phantom_line",
        "type": "LINE",
        "start_px": [10, 10],
        "end_px": [50, 50],
    }
    req = _make_signed_request([phantom_prim], render_bytes)

    # Production verifier FAILS BY PASSING:
    # Because pixel <= 220 (0 <= 220 is True everywhere!), it reports 100% support for the phantom line!
    prod_res = verify_external_visual_proposal_source_support(
        verification_request=req,
        source_render_bytes=render_bytes,
    )
    assert prod_res["status"] == "VERIFIED"
    assert prod_res["primitive_support"][0]["support_fraction"] == 1.0  # False positive!

    # Strategy D detects dark background polarity, expects bright strokes, and correctly rejects
    res_d = verify_source_support_strategy_d(
        roi_bbox=[0, 0, 63, 63],
        primitives=[phantom_prim],
        source_render_bytes=render_bytes,
    )
    assert res_d["status"] == "REJECTED"
    assert res_d["primitive_support"][0]["supported"] is False
    assert res_d["primitive_support"][0]["support_fraction"] == 0.0
