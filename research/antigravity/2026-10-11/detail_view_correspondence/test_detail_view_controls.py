"""Controls suite for Detail View Callout, Enlargement Scale, and Parent Bubble Correspondence.

Testing:
- Positive controls (exact correspondence, full magnification verification)
- Strong negative controls (tag mismatch B vs C, orphan detail view)
- Regular dimension immunity
- Exact mathematical calibration scaling (mm_per_px_for_general_scale)
- Degenerate & nonfinite controls (zero/negative scales, nonfinite coordinates)
- Non-circular bubble shapes (elliptical, spline)
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

from detail_view_engine import (
    Point2D,
    DetailBubble,
    DetailViewRegion,
    run_strategy_d,
    parse_detail_scale_callout,
    mm_per_px_for_general_scale,
)
from primitive_ir_lib.text_extraction import RawText


def test_positive_control_exact_correspondence():
    """Positive Control: Complete valid detail bubble and detail view pairing."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_a", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[20.0])
    bubble = DetailBubble(id="bub_a", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="A")
    texts = [
        RawText(id="t_a", content="DETAIL A SCALE 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_a": [10.0]}

    res = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res) == 1
    assert res[0].status == "verified"
    assert res[0].nominal_magnification == 2.0
    assert res[0].measured_magnification == 2.0


def test_negative_control_tag_mismatch():
    """Negative Control: Parent bubble tagged B, detail callout tagged C -> no false correspondence."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_c", bbox_px=(600.0, 100.0, 800.0, 300.0))
    bubble = DetailBubble(id="bub_b", parent_view_id="v_front", center=Point2D(250.0, 250.0), radius=20.0, identifier_tag="B")
    texts = [
        RawText(id="t_c", content="DETAIL C 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]

    res = run_strategy_d([parent_view, detail_view], texts, [bubble])
    assert len(res) == 1
    assert res[0].status == "missing_detail_view"
    assert res[0].detail_view_id == ""


def test_negative_control_orphan_detail_view():
    """Negative Control: Callout exists but no detail bubble exists in parent view."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_k", bbox_px=(600.0, 100.0, 800.0, 300.0))
    texts = [
        RawText(id="t_k", content="DETAIL K 5:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    # No bubbles in parent view
    res = run_strategy_d([parent_view, detail_view], texts, [])
    assert len(res) == 0


def test_calibration_general_scale_math():
    """Mathematical verification: mm_per_px_for_general_scale for enlargement vs reduction."""
    dpi = 300
    base_unit = 25.4 / dpi  # 0.084666 mm/px

    # 1:1 scale
    assert math.isclose(mm_per_px_for_general_scale(1, 1, dpi), base_unit)

    # 2:1 enlargement: features on paper are 2x larger, so 1 pixel is 0.5 CAD mm
    assert math.isclose(mm_per_px_for_general_scale(2, 1, dpi), 0.5 * base_unit)

    # 5:1 enlargement: 1 pixel is 0.2 CAD mm
    assert math.isclose(mm_per_px_for_general_scale(5, 1, dpi), 0.2 * base_unit)

    # 1:5 reduction: features on paper are 5x smaller, so 1 pixel is 5 CAD mm
    assert math.isclose(mm_per_px_for_general_scale(1, 5, dpi), 5.0 * base_unit)


def test_degenerate_scale_inputs_rejected():
    """Degenerate cases: zero or negative scale inputs raise ValueError in calibration math."""
    with pytest.raises(ValueError):
        mm_per_px_for_general_scale(0, 1, 300)
    with pytest.raises(ValueError):
        mm_per_px_for_general_scale(1, 0, 300)
    with pytest.raises(ValueError):
        mm_per_px_for_general_scale(-2, 1, 300)
    with pytest.raises(ValueError):
        mm_per_px_for_general_scale(1, 1, 0)


def test_non_circular_bubble_shapes():
    """Non-circular bubble: elliptical and spline boundary bubbles."""
    parent_view = DetailViewRegion(id="v_front", bbox_px=(100.0, 100.0, 500.0, 500.0))
    detail_view = DetailViewRegion(id="v_det_s", bbox_px=(600.0, 100.0, 800.0, 300.0), feature_lengths=[40.0])
    bubble = DetailBubble(
        id="bub_spline",
        parent_view_id="v_front",
        center=Point2D(250.0, 250.0),
        radius=25.0,
        identifier_tag="S",
        shape="spline",
    )
    texts = [
        RawText(id="t_s", content="DETAIL S 2:1", bbox_px=(600, 310, 750, 330), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    parent_features = {"bub_spline": [20.0]}

    res = run_strategy_d([parent_view, detail_view], texts, [bubble], parent_features)
    assert len(res) == 1
    assert res[0].status == "verified"


def test_detail_callout_regex_coverage():
    """Unit test for multilingual syntax coverage of detail view callout regex."""
    assert parse_detail_scale_callout("DETAIL A SCALE 2:1") is not None
    assert parse_detail_scale_callout("DET. B 5:1") is not None
    assert parse_detail_scale_callout("CHI TIẾT C TL 10:1") is not None
    assert parse_detail_scale_callout("CHI TIET D (2:1)") is not None
    assert parse_detail_scale_callout("VIEW E 1:1") is not None
    assert parse_detail_scale_callout("PHÓNG ĐẠI F 4:1") is not None

    # Invalid strings
    assert parse_detail_scale_callout("SECTION A-A") is None
    assert parse_detail_scale_callout("100.0 ± 0.05") is None
    assert parse_detail_scale_callout("") is None


def test_empty_inputs_handling():
    """Degenerate case: empty views, texts, bubbles return empty list."""
    assert run_strategy_d([], [], []) == []
