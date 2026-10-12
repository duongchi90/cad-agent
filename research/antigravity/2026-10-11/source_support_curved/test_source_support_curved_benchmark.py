"""Benchmark suite comparing Strategies A, B, C, D for Source Support Verification.

Evaluates 8 scenarios:
1. Scenario 1: Solid rectangle (4 lines on white background).
2. Scenario 2: Solid circle hole (radius 20px).
3. Scenario 3: Fillet arc corner (90° arc, radius 15px).
4. Scenario 4: Dashed hidden line (8px dash, 12px gap).
5. Scenario 5: Centerline dot-dash (period 22px).
6. Scenario 6: Mixed batch (4 lines + 1 circle + 1 arc + 1 invented line).
7. Scenario 7: Inverted blueprint (white lines on black background).
8. Scenario 8: Low-contrast scan (background 200, pencil lines 150).
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

from source_support_curved_engine import (
    verify_source_support_strategy_a,
    verify_source_support_strategy_b,
    verify_source_support_strategy_c,
    verify_source_support_strategy_d,
)


def _render_image(draw_fn, size=(64, 64), bg=255) -> bytes:
    img = Image.new("L", size, bg)
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_scenario_1_solid_rectangle():
    """Scenario 1: Clean solid rectangle lines."""
    render_bytes = _render_image(lambda d: d.rectangle([10, 10, 40, 40], outline=0, width=1))
    prims = [
        {"id": "t", "type": "LINE", "start_px": [10, 10], "end_px": [40, 10]},
        {"id": "r", "type": "LINE", "start_px": [40, 10], "end_px": [40, 40]},
        {"id": "b", "type": "LINE", "start_px": [40, 40], "end_px": [10, 40]},
        {"id": "l", "type": "LINE", "start_px": [10, 40], "end_px": [10, 10]},
    ]
    bbox = [0, 0, 63, 63]

    res_a = verify_source_support_strategy_a(bbox, prims, render_bytes)
    res_b = verify_source_support_strategy_b(bbox, prims, render_bytes)
    res_c = verify_source_support_strategy_c(bbox, prims, render_bytes)
    res_d = verify_source_support_strategy_d(bbox, prims, render_bytes)

    assert res_a["status"] == "VERIFIED"
    assert res_b["status"] == "ALL_VERIFIED"
    assert res_c["status"] == "ALL_VERIFIED"
    assert res_d["status"] == "ALL_VERIFIED"


def test_scenario_2_solid_circle_hole():
    """Scenario 2: Single solid circle hole."""
    render_bytes = _render_image(lambda d: d.ellipse([15, 15, 45, 45], outline=0, width=1))
    prim = {"id": "c1", "type": "CIRCLE", "center_px": [30, 30], "radius_px": 15.0}
    bbox = [0, 0, 63, 63]

    # Strategy A crashes
    with pytest.raises(ValueError):
        verify_source_support_strategy_a(bbox, [prim], render_bytes)

    # Strategy B and C report unsupported type
    res_b = verify_source_support_strategy_b(bbox, [prim], render_bytes)
    assert res_b["status"] == "REJECTED"
    assert res_b["primitive_support"][0]["reason"] == "UNSUPPORTED_PRIMITIVE_TYPE"

    res_c = verify_source_support_strategy_c(bbox, [prim], render_bytes)
    assert res_c["status"] == "REJECTED"

    # Strategy D verifies circle
    res_d = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True


def test_scenario_3_fillet_arc_corner():
    """Scenario 3: Fillet arc corner (90° sweep)."""
    render_bytes = _render_image(lambda d: d.arc([15, 15, 45, 45], start=0, end=90, fill=0, width=1))
    prim = {"id": "a1", "type": "ARC", "center_px": [30, 30], "radius_px": 15.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0}
    bbox = [0, 0, 63, 63]

    with pytest.raises(ValueError):
        verify_source_support_strategy_a(bbox, [prim], render_bytes)

    res_b = verify_source_support_strategy_b(bbox, [prim], render_bytes)
    assert res_b["status"] == "REJECTED"

    res_d = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True


def test_scenario_4_dashed_hidden_line():
    """Scenario 4: Dashed hidden line with 8px dash, 12px gap."""
    def _draw_dash(d):
        for x in range(10, 90, 20):
            d.line([(x, 25), (x + 7, 25)], fill=0, width=1)

    render_bytes = _render_image(_draw_dash, size=(100, 64))
    prim = {"id": "dash_1", "type": "LINE", "start_px": [10, 25], "end_px": [90, 25], "style": "dashed"}
    bbox = [0, 0, 99, 63]

    # Strategy A crashes (0.57 < 0.85)
    with pytest.raises(ValueError):
        verify_source_support_strategy_a(bbox, [prim], render_bytes)

    # Strategy B fails support check
    res_b = verify_source_support_strategy_b(bbox, [prim], render_bytes)
    assert res_b["status"] == "REJECTED"

    # Strategy C and D pass via style="dashed"
    res_c = verify_source_support_strategy_c(bbox, [prim], render_bytes)
    assert res_c["status"] == "ALL_VERIFIED"
    assert res_c["primitive_support"][0]["supported"] is True

    res_d = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res_d["status"] == "ALL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True


def test_scenario_5_centerline_dot_dash():
    """Scenario 5: Centerline dot-dash (dash 15, gap 8, dot 2, gap 8 = period 33)."""
    def _draw_cl(d):
        for x in range(10, 90, 33):
            d.line([(x, 25), (x + 14, 25)], fill=0, width=1)
            d.line([(x + 23, 25), (x + 24, 25)], fill=0, width=1)

    render_bytes = _render_image(_draw_cl, size=(100, 64))
    prim = {"id": "cl_1", "type": "LINE", "start_px": [10, 25], "end_px": [90, 25], "style": "centerline"}
    bbox = [0, 0, 99, 63]

    with pytest.raises(ValueError):
        verify_source_support_strategy_a(bbox, [prim], render_bytes)

    res_b = verify_source_support_strategy_b(bbox, [prim], render_bytes)
    assert res_b["status"] == "REJECTED"

    res_c = verify_source_support_strategy_c(bbox, [prim], render_bytes)
    assert res_c["status"] == "ALL_VERIFIED"

    res_d = verify_source_support_strategy_d(bbox, [prim], render_bytes)
    assert res_d["status"] == "ALL_VERIFIED"


def test_scenario_6_mixed_batch_with_one_hallucination():
    """Scenario 6: Mixed batch (4 lines + 1 circle + 1 arc + 1 hallucination)."""
    def _draw(d):
        d.rectangle([10, 10, 40, 40], outline=0, width=1)
        d.ellipse([50, 10, 70, 30], outline=0, width=1)
        d.arc([50, 40, 70, 60], start=0, end=90, fill=0, width=1)

    render_bytes = _render_image(_draw, size=(100, 80))
    prims = [
        {"id": "t", "type": "LINE", "start_px": [10, 10], "end_px": [40, 10]},
        {"id": "r", "type": "LINE", "start_px": [40, 10], "end_px": [40, 40]},
        {"id": "b", "type": "LINE", "start_px": [40, 40], "end_px": [10, 40]},
        {"id": "l", "type": "LINE", "start_px": [10, 40], "end_px": [10, 10]},
        {"id": "c", "type": "CIRCLE", "center_px": [60, 20], "radius_px": 10.0},
        {"id": "a", "type": "ARC", "center_px": [60, 50], "radius_px": 10.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
        {"id": "phantom", "type": "LINE", "start_px": [80, 10], "end_px": [95, 30]},
    ]
    bbox = [0, 0, 99, 79]

    # Strategy A crashes
    with pytest.raises(ValueError):
        verify_source_support_strategy_a(bbox, prims, render_bytes)

    # Strategy B and C only support 4 lines out of 7 (drop circle, arc, phantom)
    res_b = verify_source_support_strategy_b(bbox, prims, render_bytes)
    res_c = verify_source_support_strategy_c(bbox, prims, render_bytes)
    assert sum(1 for r in res_b["primitive_support"] if r["supported"]) == 4
    assert sum(1 for r in res_c["primitive_support"] if r["supported"]) == 4

    # Strategy D verifies 6 out of 7 primitives!
    res_d = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res_d["status"] == "PARTIAL_VERIFIED"
    assert sum(1 for r in res_d["primitive_support"] if r["supported"]) == 6
    supported_ids = {r["primitive_hypothesis_id"] for r in res_d["primitive_support"] if r["supported"]}
    assert supported_ids == {"t", "r", "b", "l", "c", "a"}


def test_scenario_7_inverted_blueprint():
    """Scenario 7: White lines on black background (blueprint)."""
    # Black background, white rectangle
    def _draw(d):
        d.rectangle([10, 10, 40, 40], outline=255, width=1)

    render_bytes = _render_image(_draw, size=(64, 64), bg=0)
    prims = [
        {"id": "t", "type": "LINE", "start_px": [10, 10], "end_px": [40, 10]},
        {"id": "phantom", "type": "LINE", "start_px": [15, 15], "end_px": [35, 35]},
    ]
    bbox = [0, 0, 63, 63]

    # Strategies A, B, C treat black background as dark ink, falsely verifying phantom line!
    res_a = verify_source_support_strategy_a(bbox, prims, render_bytes)
    assert res_a["primitive_support"][1]["support_fraction"] == 1.0  # False pass

    res_b = verify_source_support_strategy_b(bbox, prims, render_bytes)
    assert res_b["primitive_support"][1]["supported"] is True  # False pass

    # Strategy D detects inverted polarity: t is verified, phantom is rejected!
    res_d = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res_d["status"] == "PARTIAL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True
    assert res_d["primitive_support"][1]["supported"] is False


def test_scenario_8_low_contrast_pencil_scan():
    """Scenario 8: Gray paper (200) with faint pencil lines (140)."""
    def _draw(d):
        d.line([(10, 20), (50, 20)], fill=140, width=1)

    render_bytes = _render_image(_draw, size=(64, 64), bg=200)
    prims = [
        {"id": "real", "type": "LINE", "start_px": [10, 20], "end_px": [50, 20]},
        {"id": "phantom", "type": "LINE", "start_px": [10, 45], "end_px": [50, 45]},
    ]
    bbox = [0, 0, 63, 63]

    # Fixed 220 threshold treats entire 200 paper as ink!
    res_b = verify_source_support_strategy_b(bbox, prims, render_bytes)
    assert res_b["primitive_support"][1]["supported"] is True  # False pass

    # Strategy D adaptive percentile splits pencil lines from background
    res_d = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res_d["status"] == "PARTIAL_VERIFIED"
    assert res_d["primitive_support"][0]["supported"] is True
    assert res_d["primitive_support"][1]["supported"] is False
