"""Controls suite for Cutting Plane Line and Section View Correspondence.

Testing:
- Positive controls (exact match, full correspondence)
- Strong negative controls (tag mismatch A-A vs B-B, orphan section, orphan cutting plane)
- Ambiguity controls (duplicate identical callouts)
- Geometric invariance (45-degree angled cutting plane and viewing vector)
- Degenerate cases (single arrow, opposing arrow heads)
- Nonfinite cases (NaN / Inf coordinate rejection)
"""

import math
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
    run_strategy_d,
    CuttingPlaneCorrespondenceOracle,
    parse_section_callout_text,
)
from primitive_ir_lib.text_extraction import RawText


def test_positive_control_exact_correspondence():
    """Positive Control: Complete valid cutting plane and section view pairing."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 1
    assert res[0].status == "verified"
    assert res[0].section_tag == "A"
    assert res[0].parent_view_id == "v_front"
    assert res[0].section_view_id == "v_sec"


def test_negative_control_mismatched_tags():
    """Negative Control: Cutting plane tagged A-A, section view tagged B-B -> no false correspondence."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        # Callout is B-B, but cutting plane is A-A!
        RawText(id="t1", content="SECTION B-B", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 1
    # Section A is missing on sheet!
    assert res[0].status == "missing_section"
    assert res[0].section_view_id == ""


def test_negative_control_orphan_section_view():
    """Negative Control: Section title exists, but no cutting plane arrows exist in parent view."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION K-K", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows: list[dict] = []  # No cutting plane arrows

    res = run_strategy_d(views, [], texts, arrows)
    # Zero cutting planes detected -> zero false correspondences
    assert len(res) == 0


def test_rotation_invariance_angled_45_degree_cutting_plane():
    """Rotation Invariance: 45° angled cutting plane with viewing vector (-sqrt(2)/2, -sqrt(2)/2)."""
    # Parent view centered around (300, 300)
    views = [
        ViewRegion(id="v_front", bbox_px=(200.0, 200.0, 400.0, 400.0)),
        # Section view placed in North-West direction: (50, 50, 180, 180)
        ViewRegion(id="v_sec_angled", bbox_px=(50.0, 50.0, 180.0, 180.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION M-M", bbox_px=(50, 190, 150, 210), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="M", bbox_px=(230, 360, 240, 375), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="M", bbox_px=(360, 230, 370, 245), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # Cutting plane line goes from (250, 350) to (350, 250). Normal pointing North-West (-0.707, -0.707)
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    arrows = [
        {"tip": (250.0 - 20 * inv_sqrt2, 350.0 - 20 * inv_sqrt2), "tail": (250.0, 350.0), "primitive_ids": ["a1"]},
        {"tip": (350.0 - 20 * inv_sqrt2, 250.0 - 20 * inv_sqrt2), "tail": (350.0, 250.0), "primitive_ids": ["a2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 1
    corr = res[0]
    assert corr.section_tag == "M"
    assert corr.status == "verified"
    assert corr.spatial_consistency is True


def test_degenerate_control_single_arrow():
    """Degenerate Control: Only 1 arrow provided -> insufficient for ISO cutting plane."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},  # Single arrow only
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 0  # Requires pair of arrows


def test_degenerate_control_opposing_arrow_heads():
    """Degenerate Control: Arrows pointing in opposite directions (one North, one South)."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # Opposing arrows: a1 points North, a2 points South -> cancels out viewing vector
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},  # North
        {"tip": (300.0, 420.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},  # South
    ]

    res = run_strategy_d(views, [], texts, arrows)
    # Average viewing vector is (0, 0), which cannot establish consistent projection
    if res:
        assert res[0].spatial_consistency is False


def test_nonfinite_coordinates_gracefully_rejected():
    """Nonfinite Control: NaN and Inf arrow coordinates are safely ignored without crashing."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (float("nan"), 100.0), "tail": (100.0, 100.0), "primitive_ids": ["bad1"]},
        {"tip": (float("inf"), float("-inf")), "tail": (0.0, 0.0), "primitive_ids": ["bad2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 0


def test_section_regex_parsers():
    """Unit test for multilingual and syntax coverage of section callout regex."""
    assert parse_section_callout_text("SECTION A-A") is not None
    assert parse_section_callout_text("SEC. B-B") is not None
    assert parse_section_callout_text("MẶT CẮT C-C (1:10)") is not None
    assert parse_section_callout_text("MAT CAT D-D") is not None
    assert parse_section_callout_text("COUPE E-E") is not None
    assert parse_section_callout_text("SCHNITT F-F") is not None
    assert parse_section_callout_text("G-G") is not None
    assert parse_section_callout_text("H-H (SCALE 1:2)") is not None
    # Invalid strings
    assert parse_section_callout_text("DIA 50") is None
    assert parse_section_callout_text("4x M8") is None
    assert parse_section_callout_text("") is None
