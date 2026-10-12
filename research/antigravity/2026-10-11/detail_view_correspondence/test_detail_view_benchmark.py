"""Benchmark suite comparing Strategies A, B, C, and D across 8 detail view scenarios."""

import sys
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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)
from primitive_ir_lib.text_extraction import RawText


def test_scenario_1_standard_2_to_1_detail():
    """Scenario 1: Detail B with 2:1 enlargement scale."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(
        id="v_det_b",
        bbox_px=(600.0, 100.0, 800.0, 300.0),
        feature_lengths=[40.0],  # 20mm feature enlarged 2x -> 40mm
    )
    bubble = DetailBubble(
        id="bub_b",
        parent_view_id="v_front",
        center=Point2D(250.0, 250.0),
        radius=25.0,
        identifier_tag="B",
    )
    texts = [
        RawText(id="t_b", content="DETAIL B SCALE 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_b": [20.0]}

    res_a = run_strategy_a([parent_view, detail_view], texts, [bubble])
    res_b = run_strategy_b([parent_view, detail_view], texts, [bubble])
    res_c = run_strategy_c([parent_view, detail_view], texts, [bubble])
    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)

    assert len(res_a) == 0  # Production baseline fails

    assert len(res_b) == 1
    assert res_b[0].nominal_magnification == 1.0  # Strategy B blind to scale

    assert len(res_c) == 1
    assert res_c[0].nominal_magnification == 2.0

    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.detail_tag == "B"
    assert corr.parent_view_id == "v_front"
    assert corr.detail_view_id == "v_det_b"
    assert corr.nominal_magnification == 2.0
    assert corr.measured_magnification == 2.0
    assert corr.magnification_error_percent == 0.0
    assert corr.status == "verified"
    assert corr.confidence > 0.95


def test_scenario_2_high_magnification_5_to_1():
    """Scenario 2: Detail C with 5:1 scale."""
    parent_view = DetailViewRegion(id="v_main", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_c", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[50.0])
    bubble = DetailBubble(id="bub_c", parent_view_id="v_main", center=Point2D(200.0, 200.0), radius=15.0, identifier_tag="C")
    texts = [
        RawText(id="t_c", content="DETAIL C (5:1)", bbox_px=(600, 310, 720, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_c": [10.0]}  # 10mm enlarged 5x -> 50mm

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    assert res_d[0].detail_tag == "C"
    assert res_d[0].nominal_magnification == 5.0
    assert res_d[0].measured_magnification == 5.0
    assert res_d[0].status == "verified"


def test_scenario_3_super_magnification_10_to_1():
    """Scenario 3: Micro detail D with 10:1 scale."""
    parent_view = DetailViewRegion(id="v_main", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_d", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[100.0])
    bubble = DetailBubble(id="bub_d", parent_view_id="v_main", center=Point2D(300.0, 300.0), radius=10.0, identifier_tag="D")
    texts = [
        RawText(id="t_d", content="DETAIL D 10:1", bbox_px=(600, 310, 720, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_d": [10.0]}

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    assert res_d[0].nominal_magnification == 10.0
    assert res_d[0].status == "verified"


def test_scenario_4_multilingual_vietnamese_callout():
    """Scenario 4: Vietnamese notation 'CHI TIẾT E TL 2:1'."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_e", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[30.0])
    bubble = DetailBubble(id="bub_e", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="E")
    texts = [
        RawText(id="t_e", content="CHI TIẾT E TL 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_e": [15.0]}

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    assert res_d[0].detail_tag == "E"
    assert res_d[0].nominal_magnification == 2.0
    assert res_d[0].status == "verified"


def test_scenario_5_reduction_scale_detail():
    """Scenario 5: Reduction scale detail view 1:2."""
    parent_view = DetailViewRegion(id="v_giant", bbox_px=(100.0, 100.0, 1000.0, 1000.0))
    detail_view = DetailViewRegion(id="v_det_f", bbox_px=(1100.0, 100.0, 1300.0, 300.0), feature_lengths=[50.0])
    bubble = DetailBubble(id="bub_f", parent_view_id="v_giant", center=Point2D(500.0, 500.0), radius=150.0, identifier_tag="F")
    texts = [
        RawText(id="t_f", content="DETAIL F (1:2)", bbox_px=(1100, 310, 1220, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_f": [100.0]}  # 100mm scaled down to 50mm

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    assert res_d[0].nominal_magnification == 0.5
    assert res_d[0].measured_magnification == 0.5
    assert res_d[0].status == "verified"


def test_scenario_6_magnification_mismatch_detected():
    """Scenario 6: Callout claims 5:1 but geometry is drawn at 2:1 -> mismatch flagged."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(
        id="v_det_g",
        bbox_px=(600.0, 100.0, 800.0, 300.0),
        feature_lengths=[20.0],  # Measured magnification is 20/10 = 2.0
    )
    bubble = DetailBubble(id="bub_g", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="G")
    texts = [
        RawText(id="t_g", content="DETAIL G 5:1", bbox_px=(600, 310, 720, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_g": [10.0]}

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.nominal_magnification == 5.0
    assert corr.measured_magnification == 2.0
    assert corr.status == "magnification_mismatch"
    assert corr.magnification_error_percent == 60.0


def test_scenario_7_multiple_details_same_sheet():
    """Scenario 7: Multiple details on single sheet (Detail A 2:1, Detail B 4:1)."""
    parent_view = DetailViewRegion(id="v_main", bbox_px=(100.0, 100.0, 500.0, 500.0))
    v_a = DetailViewRegion(id="v_det_a", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[20.0])
    v_b = DetailViewRegion(id="v_det_b", bbox_px=(600.0, 400.0, 800.0, 600.0), feature_lengths=[40.0])
    bub_a = DetailBubble(id="b_a", parent_view_id="v_main", center=Point2D(200.0, 200.0), radius=15.0, identifier_tag="A")
    bub_b = DetailBubble(id="b_b", parent_view_id="v_main", center=Point2D(400.0, 400.0), radius=15.0, identifier_tag="B")
    texts = [
        RawText(id="t_a", content="DETAIL A 2:1", bbox_px=(600, 310, 700, 330), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_b", content="DETAIL B 4:1", bbox_px=(600, 610, 700, 630), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"b_a": [10.0], "b_b": [10.0]}

    res_d = run_strategy_d([parent_view, v_a, v_b], texts, [bub_a, bub_b], parent_features)
    assert len(res_d) == 2
    tags = {c.detail_tag for c in res_d}
    assert tags == {"A", "B"}
    assert all(c.status == "verified" for c in res_d)


def test_scenario_8_abbreviated_callout():
    """Scenario 8: Abbreviated callout 'DET. H (SCALE 2:1)'."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_h", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[30.0])
    bubble = DetailBubble(id="bub_h", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="H")
    texts = [
        RawText(id="t_h", content="DET. H (SCALE 2:1)", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_h": [15.0]}

    res_d = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res_d) == 1
    assert res_d[0].detail_tag == "H"
    assert res_d[0].nominal_magnification == 2.0
    assert res_d[0].status == "verified"
