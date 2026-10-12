"""Boundary controls and false-positive elimination for Source Support Curved Verifier.

Covers 8 positive and negative boundary controls:
1. Control 1: Positive solid circles across radii (8px, 15px, 30px).
2. Control 2: Positive arc sweeps (45°, 90°, 180°, 270°).
3. Control 3: Negative invented circle in blank space (0% support).
4. Control 4: Negative circle radius mismatch (concentric offset 10px).
5. Control 5: Negative invented arc in blank space.
6. Control 6: Negative dashed line with insufficient ink (10% support).
7. Control 7: Tolerance boundary (2px offset passes vs 4px offset fails).
8. Control 8: Outside ROI boundary rejection.
"""

import sys
from pathlib import Path
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

from source_support_curved_engine import verify_source_support_strategy_d


def _render_image(draw_fn, size=(100, 100), bg=255) -> bytes:
    img = Image.new("L", size, bg)
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ctrl_1_positive_solid_circles_radii():
    """Control 1: Solid circles with radii 8px, 15px, 30px."""
    def _draw(d):
        d.ellipse([20 - 8, 20 - 8, 20 + 8, 20 + 8], outline=0, width=1)
        d.ellipse([60 - 15, 30 - 15, 60 + 15, 30 + 15], outline=0, width=1)
        d.ellipse([50 - 25, 70 - 25, 50 + 25, 70 + 25], outline=0, width=1)

    render_bytes = _render_image(_draw)
    prims = [
        {"id": "c8", "type": "CIRCLE", "center_px": [20, 20], "radius_px": 8.0},
        {"id": "c15", "type": "CIRCLE", "center_px": [60, 30], "radius_px": 15.0},
        {"id": "c25", "type": "CIRCLE", "center_px": [50, 70], "radius_px": 25.0},
    ]
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res["status"] == "ALL_VERIFIED"
    for item in res["primitive_support"]:
        assert item["supported"] is True
        assert item["support_fraction"] >= 0.85


def test_ctrl_2_positive_arc_sweeps():
    """Control 2: Arc sweeps from 45° to 270°."""
    def _draw(d):
        d.arc([10, 10, 50, 50], start=0, end=45, fill=0, width=1)
        d.arc([55, 10, 95, 50], start=0, end=180, fill=0, width=1)
        d.arc([30, 55, 70, 95], start=0, end=270, fill=0, width=1)

    render_bytes = _render_image(_draw)
    prims = [
        {"id": "a45", "type": "ARC", "center_px": [30, 30], "radius_px": 20.0, "start_angle_deg": 0.0, "end_angle_deg": 45.0},
        {"id": "a180", "type": "ARC", "center_px": [75, 30], "radius_px": 20.0, "start_angle_deg": 0.0, "end_angle_deg": 180.0},
        {"id": "a270", "type": "ARC", "center_px": [50, 75], "radius_px": 20.0, "start_angle_deg": 0.0, "end_angle_deg": 270.0},
    ]
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res["status"] == "ALL_VERIFIED"
    for item in res["primitive_support"]:
        assert item["supported"] is True


def test_ctrl_3_negative_invented_circle_in_blank_space():
    """Control 3: Circle proposed in completely blank space."""
    render_bytes = _render_image(lambda d: None)  # Blank white image
    prim = {"id": "c_phantom", "type": "CIRCLE", "center_px": [50, 50], "radius_px": 20.0}
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False
    assert res["primitive_support"][0]["support_fraction"] == 0.0


def test_ctrl_4_negative_circle_radius_mismatch():
    """Control 4: Real circle has radius 15px. Proposed circle has radius 25px (concentric offset 10px)."""
    render_bytes = _render_image(lambda d: d.ellipse([35, 35, 65, 65], outline=0, width=1))  # r=15 at (50, 50)
    prim = {"id": "c_wrong_r", "type": "CIRCLE", "center_px": [50, 50], "radius_px": 25.0}  # r=25
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False
    assert res["primitive_support"][0]["support_fraction"] < 0.10


def test_ctrl_5_negative_invented_arc_in_blank_space():
    """Control 5: Arc proposed in empty space."""
    render_bytes = _render_image(lambda d: None)
    prim = {"id": "a_phantom", "type": "ARC", "center_px": [50, 50], "radius_px": 20.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0}
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False


def test_ctrl_6_negative_dashed_line_insufficient_ink():
    """Control 6: Very sparse dashes (2px dash, 18px gap -> ~10% support)."""
    def _draw(d):
        for x in range(10, 90, 20):
            d.line([(x, 50), (x + 1, 50)], fill=0, width=1)

    render_bytes = _render_image(_draw)
    prim = {"id": "sparse_dash", "type": "LINE", "start_px": [10, 50], "end_px": [90, 50], "style": "dashed"}
    bbox = [0, 0, 99, 99]

    res = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False


def test_ctrl_7_tolerance_boundary():
    """Control 7: Line offset by 2px (within tolerance) vs 4px (beyond tolerance)."""
    # Real line at y=50
    render_bytes = _render_image(lambda d: d.line([(10, 50), (90, 50)], fill=0, width=1))

    # Line 1: at y=52 (offset 2px -> within endpoint_tolerance_px=2)
    p_pass = {"id": "p_pass", "type": "LINE", "start_px": [10, 52], "end_px": [90, 52]}
    # Line 2: at y=54 (offset 4px -> outside endpoint_tolerance_px=2)
    p_fail = {"id": "p_fail", "type": "LINE", "start_px": [10, 54], "end_px": [90, 54]}

    bbox = [0, 0, 99, 99]
    res = verify_source_support_strategy_d(bbox, [p_pass, p_fail], render_bytes, endpoint_tolerance_px=2)
    assert res["status"] == "PARTIAL_VERIFIED"
    assert res["primitive_support"][0]["supported"] is True
    assert res["primitive_support"][1]["supported"] is False


def test_ctrl_8_outside_roi_boundary_rejection():
    """Control 8: Circle centered inside ROI but circumference crossing outside ROI boundary."""
    render_bytes = _render_image(lambda d: d.ellipse([5, 5, 45, 45], outline=0, width=1), size=(60, 60))
    # ROI is [10, 10, 50, 50], circle has center (25, 25) radius 20 -> x reaches 5 and 45 (outside 10..50)
    prim = {"id": "c_overflow", "type": "CIRCLE", "center_px": [25, 25], "radius_px": 20.0}
    bbox = [10, 10, 50, 50]

    res = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False
    assert res["primitive_support"][0]["reason"] == "OUTSIDE_BOUNDS"
