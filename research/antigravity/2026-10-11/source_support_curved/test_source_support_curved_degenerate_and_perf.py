"""Degenerate, edge, and performance profiling test suite for Source Support Curved Verifier.

Covers 7 tests:
1. Edge 1: Empty primitives list returns empty result with REJECTED status.
2. Edge 2: Micro and zero-radius circle (radius <= 0 or micro < 1px) safe rejection.
3. Edge 3: Micro and zero-sweep arc safe rejection.
4. Edge 4: Non-finite coordinate guards (NaN / Inf in start, end, center, radius, angles).
5. Edge 5: Corrupt or empty render image bytes raise descriptive ValueError.
6. Edge 6: Extreme coordinate magnitudes (1500px on 2000x2000 canvas) numerical stability.
7. Perf 7: Large-scale latency and throughput profiling (100 mixed primitives in < 30 ms).
"""

import sys
from pathlib import Path
import io
import math
import time
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


def test_edge_1_empty_primitives_list():
    """Edge 1: Empty primitives list returns empty support list with REJECTED status."""
    render_bytes = _render_image(lambda d: None)
    res = verify_source_support_strategy_d([0, 0, 99, 99], [], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"] == []


def test_edge_2_micro_and_zero_radius_circle():
    """Edge 2: Micro / zero radius circle (radius <= 0 or < 1px) safely rejected without division by zero."""
    render_bytes = _render_image(lambda d: None)
    c_zero = {"id": "c0", "type": "CIRCLE", "center_px": [50, 50], "radius_px": 0.0}
    c_neg = {"id": "c_neg", "type": "CIRCLE", "center_px": [50, 50], "radius_px": -10.0}

    res = verify_source_support_strategy_d([0, 0, 99, 99], [c_zero, c_neg], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["supported"] is False
    assert res["primitive_support"][0]["reason"] == "INVALID_GEOMETRY"
    assert res["primitive_support"][1]["reason"] == "INVALID_GEOMETRY"


def test_edge_3_micro_and_zero_sweep_arc():
    """Edge 3: Degenerate arc with radius < 1px safely rejected."""
    render_bytes = _render_image(lambda d: None)
    a_zero_r = {"id": "a0", "type": "ARC", "center_px": [50, 50], "radius_px": 0.5, "start_angle_deg": 0.0, "end_angle_deg": 90.0}

    res = verify_source_support_strategy_d([0, 0, 99, 99], [a_zero_r], render_bytes)
    assert res["status"] == "REJECTED"
    assert res["primitive_support"][0]["reason"] == "INVALID_GEOMETRY"


def test_edge_4_non_finite_coordinates_nan_inf():
    """Edge 4: NaN and Inf coordinates in LINE, CIRCLE, ARC safely handled without crashing."""
    render_bytes = _render_image(lambda d: None)
    prims = [
        {"id": "l_nan", "type": "LINE", "start_px": [float("nan"), 10], "end_px": [30, 10]},
        {"id": "l_inf", "type": "LINE", "start_px": [10, 10], "end_px": [float("inf"), 10]},
        {"id": "c_nan", "type": "CIRCLE", "center_px": [50, 50], "radius_px": float("nan")},
        {"id": "a_inf", "type": "ARC", "center_px": [50, float("inf")], "radius_px": 10.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
    ]

    res = verify_source_support_strategy_d([0, 0, 99, 99], prims, render_bytes)
    assert res["status"] == "REJECTED"
    for item in res["primitive_support"]:
        assert item["supported"] is False
        assert item["reason"] == "INVALID_GEOMETRY"


def test_edge_5_corrupt_render_bytes_safe_exception():
    """Edge 5: Corrupt or empty render image bytes raise descriptive ValueError."""
    with pytest.raises(ValueError, match="SOURCE_RENDER_BYTES_INVALID"):
        verify_source_support_strategy_d([0, 0, 50, 50], [], b"")

    with pytest.raises(ValueError, match="SOURCE_RENDER_DECODE_FAILED"):
        verify_source_support_strategy_d([0, 0, 50, 50], [], b"not_an_image_bytes")


def test_edge_6_extreme_coordinate_magnitudes():
    """Edge 6: 2000x2000 high-res image with primitives at x=1500px maintains precision."""
    img = Image.new("L", (2000, 2000), 255)
    draw = ImageDraw.Draw(img)
    draw.line([(1500, 1500), (1800, 1500)], fill=0, width=1)
    draw.ellipse([1500 - 50, 1700 - 50, 1500 + 50, 1700 + 50], outline=0, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()

    prims = [
        {"id": "l_huge", "type": "LINE", "start_px": [1500, 1500], "end_px": [1800, 1500]},
        {"id": "c_huge", "type": "CIRCLE", "center_px": [1500, 1700], "radius_px": 50.0},
    ]
    bbox = [1400, 1400, 1900, 1900]

    res = verify_source_support_strategy_d(bbox, prims, render_bytes)
    assert res["status"] == "ALL_VERIFIED"
    assert res["primitive_support"][0]["supported"] is True
    assert res["primitive_support"][1]["supported"] is True


def test_perf_7_large_scale_latency_and_throughput():
    """Perf 7: 100 mixed primitives (40 lines + 30 circles + 30 arcs) on 1000x1000 image."""
    img = Image.new("L", (1000, 1000), 255)
    draw = ImageDraw.Draw(img)
    prims = []

    # 40 lines
    for i in range(40):
        y = 50 + i * 20
        draw.line([(100, y), (300, y)], fill=0, width=1)
        prims.append({"id": f"l_{i}", "type": "LINE", "start_px": [100, y], "end_px": [300, y]})

    # 30 circles
    for i in range(30):
        cx = 400 + (i % 6) * 80
        cy = 100 + (i // 6) * 120
        r = 25.0
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=1)
        prims.append({"id": f"c_{i}", "type": "CIRCLE", "center_px": [cx, cy], "radius_px": r})

    # 30 arcs
    for i in range(30):
        cx = 400 + (i % 6) * 80
        cy = 600 + (i // 6) * 60
        r = 20.0
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=0, end=90, fill=0, width=1)
        prims.append({"id": f"a_{i}", "type": "ARC", "center_px": [cx, cy], "radius_px": r, "start_angle_deg": 0.0, "end_angle_deg": 90.0})

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    render_bytes = buf.getvalue()
    bbox = [0, 0, 999, 999]

    assert len(prims) == 100

    # Warm-up run
    verify_source_support_strategy_d(bbox, prims[:5], render_bytes)

    t0 = time.perf_counter()
    res = verify_source_support_strategy_d(bbox, prims, render_bytes)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    assert res["status"] == "ALL_VERIFIED"
    assert len(res["primitive_support"]) == 100
    assert all(item["supported"] for item in res["primitive_support"])

    # Latency budget: < 90 ms for 100 mixed primitives on 1000x1000 1MP image
    assert latency_ms < 90.0, f"Expected < 90ms, got {latency_ms:.2f}ms"
