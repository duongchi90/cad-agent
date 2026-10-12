"""Benchmark suite comparing Strategies A, B, C, and D across 8 engineering scenarios."""

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cutting_plane_engine import (
    Point2D,
    ViewRegion,
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)
from primitive_ir_lib.text_extraction import RawText


def test_scenario_1_standard_horizontal_section():
    """Scenario 1: Horizontal cutting plane A-A, arrows pointing North, Section View placed above."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="view_section_a", bbox_px=(100.0, 50.0, 300.0, 250.0)),  # Above front view
    ]
    texts = [
        RawText(id="t_title", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # Arrows at (100, 400) and (300, 400) pointing North: in image coords, smaller y is up. Let's make North = -y: tip=(100, 380), tail=(100, 400)
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    res_a = run_strategy_a(views, [], texts)
    res_b = run_strategy_b(views, [], texts)
    res_c = run_strategy_c(views, [], texts)
    res_d = run_strategy_d(views, [], texts, arrows)

    assert len(res_a) == 0  # Production baseline fails
    assert len(res_b) == 1
    assert res_b[0].viewing_vector == (0.0, 0.0)  # Strategy B lacks viewing vector
    assert res_b[0].status == "ambiguous"

    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.section_tag == "A"
    assert corr.parent_view_id == "view_front"
    assert corr.section_view_id == "view_section_a"
    assert corr.spatial_consistency is True
    assert corr.status == "verified"
    assert corr.confidence > 0.9


def test_scenario_2_vertical_section_pointing_east():
    """Scenario 2: Vertical cutting plane B-B, arrows pointing East (+x), Section View to the right."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 100.0, 300.0, 300.0)),
        ViewRegion(id="view_section_b", bbox_px=(450.0, 100.0, 650.0, 300.0)),  # To the right
    ]
    texts = [
        RawText(id="t_title", content="SECTION B-B", bbox_px=(450, 310, 550, 330), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="B", bbox_px=(210, 90, 225, 100), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="B", bbox_px=(210, 300, 225, 310), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (220.0, 100.0), "tail": (200.0, 100.0), "primitive_ids": ["arr1"]},  # Pointing East (+x)
        {"tip": (220.0, 300.0), "tail": (200.0, 300.0), "primitive_ids": ["arr2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.section_tag == "B"
    assert corr.viewing_vector[0] > 0.9  # Pointing East
    assert corr.spatial_consistency is True
    assert corr.status == "verified"


def test_scenario_3_scaled_section():
    """Scenario 3: Scaled Section C-C (1:2)."""
    views = [
        ViewRegion(id="view_main", bbox_px=(100.0, 300.0, 400.0, 600.0)),
        ViewRegion(id="view_sec_c", bbox_px=(100.0, 50.0, 250.0, 200.0)),
    ]
    texts = [
        RawText(id="t_title", content="SECTION C-C (1:2)", bbox_px=(100, 210, 220, 230), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="C", bbox_px=(90, 440, 98, 460), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="C", bbox_px=(402, 440, 410, 460), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 430.0), "tail": (100.0, 450.0), "primitive_ids": ["a1"]},
        {"tip": (400.0, 430.0), "tail": (400.0, 450.0), "primitive_ids": ["a2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.scale_ratio == 0.5  # 1:2 scale ratio extracted
    assert corr.status == "verified"


def test_scenario_4_stepped_section():
    """Scenario 4: Stepped / Offset Section D-D."""
    views = [
        ViewRegion(id="view_top", bbox_px=(100.0, 300.0, 400.0, 600.0)),
        ViewRegion(id="view_sec_d", bbox_px=(100.0, 50.0, 400.0, 250.0)),
    ]
    texts = [
        RawText(id="t_title", content="SECTION D-D", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="D", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="D", bbox_px=(402, 490, 410, 510), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # Stepped arrows: a1 at y=400, a2 at y=500
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (400.0, 480.0), "tail": (400.0, 500.0), "primitive_ids": ["a2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.section_tag == "D"
    assert corr.status == "verified"


def test_scenario_5_multilingual_vietnamese_callout():
    """Scenario 5: Vietnamese notation 'MẶT CẮT E-E (1:1)'."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="view_sec_e", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t_title", content="MẶT CẮT E-E (1:1)", bbox_px=(100, 260, 220, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="E", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="E", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    assert res_d[0].section_tag == "E"
    assert res_d[0].scale_ratio == 1.0
    assert res_d[0].status == "verified"


def test_scenario_6_bare_callout_with_scale():
    """Scenario 6: Bare callout 'F-F 1:5'."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="view_sec_f", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t_title", content="F-F 1:5", bbox_px=(100, 260, 160, 280), rotation_deg=0.0, confidence=0.85, source="text"),
        RawText(id="t_lbl1", content="F", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="F", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    assert res_d[0].section_tag == "F"
    assert res_d[0].scale_ratio == 0.2  # 1:5 scale
    assert res_d[0].status == "verified"


def test_scenario_7_inconsistent_viewing_direction():
    """Scenario 7: Inconsistent direction - arrows point North (-y), but section placed South (+y)."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 100.0, 300.0, 300.0)),
        ViewRegion(id="view_sec_g", bbox_px=(100.0, 400.0, 300.0, 600.0)),  # Placed SOUTH (larger y)
    ]
    texts = [
        RawText(id="t_title", content="SECTION G-G", bbox_px=(100, 380, 200, 400), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl1", content="G", bbox_px=(90, 190, 98, 210), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl2", content="G", bbox_px=(302, 190, 310, 210), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # Arrows point North (-y)
    arrows = [
        {"tip": (100.0, 180.0), "tail": (100.0, 200.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 180.0), "tail": (300.0, 200.0), "primitive_ids": ["a2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 1
    corr = res_d[0]
    assert corr.section_tag == "G"
    assert corr.spatial_consistency is False
    assert corr.status == "inconsistent_viewing_direction"


def test_scenario_8_multiple_sections_same_sheet():
    """Scenario 8: Multiple sections on same sheet (A-A horizontal, B-B vertical)."""
    views = [
        ViewRegion(id="view_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="view_sec_a", bbox_px=(100.0, 50.0, 300.0, 250.0)),   # North
        ViewRegion(id="view_sec_b", bbox_px=(450.0, 300.0, 650.0, 500.0)),  # East
    ]
    texts = [
        RawText(id="t_title_a", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl_a1", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl_a2", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_title_b", content="SECTION B-B", bbox_px=(450, 280, 550, 300), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl_b1", content="B", bbox_px=(190, 290, 205, 300), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t_lbl_b2", content="B", bbox_px=(190, 500, 205, 510), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        # A-A arrows pointing North (-y)
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
        # B-B arrows pointing East (+x)
        {"tip": (210.0, 300.0), "tail": (190.0, 300.0), "primitive_ids": ["b1"]},
        {"tip": (210.0, 500.0), "tail": (190.0, 500.0), "primitive_ids": ["b2"]},
    ]

    res_d = run_strategy_d(views, [], texts, arrows)
    assert len(res_d) == 2
    tags = {c.section_tag for c in res_d}
    assert tags == {"A", "B"}
    assert all(c.status == "verified" for c in res_d)
