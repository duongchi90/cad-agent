"""Degenerate cases, stress scenarios, and performance tests for Detail View correspondence."""

import math
import sys
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from detail_view_engine import (
    Point2D,
    DetailBubble,
    DetailViewRegion,
    run_strategy_d,
)
from primitive_ir_lib.text_extraction import RawText


def test_perf_dense_sheet_multiple_details_under_250ms():
    """Performance test: 20 detail views, 20 bubbles, 500 background texts in < 250ms."""
    parent_views = [
        DetailViewRegion(id=f"v_parent_{i}", bbox_px=(float(i * 300), 100.0, float(i * 300 + 200), 400.0))
        for i in range(5)
    ]
    detail_views: list[DetailViewRegion] = []
    bubbles: list[DetailBubble] = []
    texts: list[RawText] = []
    parent_features: dict[str, list[float]] = {}

    tags = [f"D{i}" for i in range(20)]
    for i, tag in enumerate(tags):
        p_idx = i % 5
        b_id = f"bub_{tag}"
        bubbles.append(DetailBubble(
            id=b_id,
            parent_view_id=f"v_parent_{p_idx}",
            center=Point2D(float(p_idx * 300 + 50), 200.0),
            radius=15.0,
            identifier_tag=tag,
        ))
        detail_views.append(DetailViewRegion(
            id=f"v_detail_{tag}",
            bbox_px=(float(i * 150), 600.0, float(i * 150 + 100), 800.0),
            feature_lengths=[30.0],  # 15mm * 2 = 30mm
        ))
        texts.append(RawText(
            id=f"t_{tag}",
            content=f"DETAIL {tag} 2:1",
            bbox_px=(float(i * 150), 810.0, float(i * 150 + 80), 830.0),
            rotation_deg=0.0,
            confidence=0.95,
            source="text",
        ))
        parent_features[b_id] = [15.0]

    # Add 480 background general notes
    for k in range(480):
        texts.append(RawText(
            id=f"noise_{k}",
            content=f"NOTE {k}: Standard tolerance",
            bbox_px=(float(k * 5), 900.0, float(k * 5 + 40), 915.0),
            rotation_deg=0.0,
            confidence=0.9,
            source="text",
        ))

    all_views = parent_views + detail_views

    t0 = time.perf_counter()
    res = run_strategy_d(all_views, texts, bubbles, parent_features)
    elapsed = time.perf_counter() - t0

    assert len(res) == 20
    assert all(c.status == "verified" for c in res)
    assert elapsed < 0.25, f"Expected runtime < 250ms, took {elapsed * 1000:.2f}ms"


def test_huge_macro_scale_coordinates():
    """Macro scale: coordinates in tens of thousands."""
    parent = DetailViewRegion(id="v_ship", bbox_px=(10000.0, 10000.0, 50000.0, 50000.0))
    detail = DetailViewRegion(id="v_det", bbox_px=(60000.0, 10000.0, 80000.0, 30000.0), feature_lengths=[400.0])
    bubble = DetailBubble(id="b_macro", parent_view_id="v_ship", center=Point2D(25000.0, 25000.0), radius=500.0, identifier_tag="M")
    texts = [
        RawText(id="t_m", content="DETAIL M 2:1", bbox_px=(60000, 30100, 70000, 30300), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"b_macro": [200.0]}

    res = run_strategy_d([parent, detail], texts, [bubble], parent_features)
    assert len(res) == 1
    assert res[0].status == "verified"


def test_micro_scale_coordinates():
    """Micro scale: dimensions in fractions of a millimeter."""
    parent = DetailViewRegion(id="v_chip", bbox_px=(0.10, 0.10, 0.50, 0.50))
    detail = DetailViewRegion(id="v_det", bbox_px=(0.60, 0.10, 0.80, 0.30), feature_lengths=[0.04])
    bubble = DetailBubble(id="b_micro", parent_view_id="v_chip", center=Point2D(0.25, 0.25), radius=0.05, identifier_tag="U")
    texts = [
        RawText(id="t_u", content="DETAIL U 4:1", bbox_px=(0.60, 0.31, 0.75, 0.33), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"b_micro": [0.01]}

    res = run_strategy_d([parent, detail], texts, [bubble], parent_features)
    assert len(res) == 1
    assert res[0].status == "verified"


def test_zero_radius_bubble_safety():
    """Degenerate case: zero radius bubble handled gracefully without exception."""
    parent = DetailViewRegion(id="v1", bbox_px=(100.0, 100.0, 300.0, 300.0))
    detail = DetailViewRegion(id="vd", bbox_px=(400.0, 100.0, 500.0, 200.0))
    bubble = DetailBubble(id="b0", parent_view_id="v1", center=Point2D(150.0, 150.0), radius=0.0, identifier_tag="Z")
    texts = [
        RawText(id="t_z", content="DETAIL Z 2:1", bbox_px=(400, 210, 480, 230), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    res = run_strategy_d([parent, detail], texts, [bubble])
    assert len(res) == 1
    assert res[0].detail_tag == "Z"


def test_large_magnification_100_to_1():
    """Extreme magnification: 100:1 ratio."""
    parent = DetailViewRegion(id="v1", bbox_px=(100.0, 100.0, 300.0, 300.0))
    detail = DetailViewRegion(id="vd", bbox_px=(400.0, 100.0, 500.0, 200.0), feature_lengths=[100.0])
    bubble = DetailBubble(id="b1", parent_view_id="v1", center=Point2D(150.0, 150.0), radius=5.0, identifier_tag="X")
    texts = [
        RawText(id="t_x", content="DETAIL X 100:1", bbox_px=(400, 210, 480, 230), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"b1": [1.0]}  # 1mm enlarged 100x -> 100mm

    res = run_strategy_d([parent, detail], texts, [bubble], parent_features)
    assert len(res) == 1
    assert res[0].nominal_magnification == 100.0
    assert res[0].status == "verified"


def test_mismatched_feature_length_counts():
    """Handling when one side has empty feature lists without failing."""
    parent = DetailViewRegion(id="v1", bbox_px=(100.0, 100.0, 300.0, 300.0))
    detail = DetailViewRegion(id="vd", bbox_px=(400.0, 100.0, 500.0, 200.0), feature_lengths=[])
    bubble = DetailBubble(id="b1", parent_view_id="v1", center=Point2D(150.0, 150.0), radius=5.0, identifier_tag="M")
    texts = [
        RawText(id="t_m", content="DETAIL M 2:1", bbox_px=(400, 210, 480, 230), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # No parent feature lengths provided
    res = run_strategy_d([parent, detail], texts, [bubble], parent_feature_lengths={})
    assert len(res) == 1
    assert res[0].status == "verified"
    assert res[0].nominal_magnification == 2.0


def test_stability_repeated_execution():
    """Verify deterministic repeatability across 50 iterations."""
    parent = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail = DetailViewRegion(id="v_det", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[30.0])
    bubble = DetailBubble(id="bub", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="B")
    texts = [
        RawText(id="t_b", content="DETAIL B 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub": [15.0]}

    for _ in range(50):
        res = run_strategy_d([parent, detail], texts, [bubble], parent_features)
        assert len(res) == 1
        assert res[0].status == "verified"
        assert res[0].confidence == 0.99
