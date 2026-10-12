"""Causal RED tests for Detail View Callout, Enlargement Scale, and Parent Bubble Correspondence.

These tests exercise CURRENT production code in:
- primitive_ir_lib/view_calibration.py
- semantic_ir_lib/pattern_recognition.py
- semantic_ir_lib/models.py

Demonstrating the exact production gaps:
1. parse_scale_label is 100% blind to enlargement scales (2:1, 5:1, 10:1, SCALE 2:1, CHI TIẾT B TL 2:1) returning None.
2. mm_per_px_for_scale only takes integer reduction denominators (1:N), erroneously computing 1:N reduction instead of N:1 enlargement.
3. Detail bubble circles in parent views are misclassified as bolt holes (lo_bat_vit) or outer boundaries.
4. semantic_ir_lib/models.py PartType omits detail_bubble and detail_correspondence types.
5. Production has zero cross-view parent-to-detail correspondence and magnification verification.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.view_calibration import parse_scale_label, mm_per_px_for_scale
from semantic_ir_lib.pattern_recognition import build_parts_from_primitives
from semantic_ir_lib.models import SemanticPart, PartType
from primitive_ir_lib.models import Primitive, CircleGeometry, Point2D, Trace


def test_red_parse_scale_label_blind_to_enlargement_scales():
    r"""RED 1: parse_scale_label hardcodes 1:(\d+) and completely fails on enlargement scales."""
    # Production regex: r"(?:TL|THI|TY\s*(?:LE|L[EB]|1[EB])|TILE)\s*[-:]?\s*1\s*:\s*(\d+)"
    # and r"\s*1\s*:\s*(\d+)\s*"
    assert parse_scale_label("SCALE 2:1") is None
    assert parse_scale_label("DETAIL A (5:1)") is None
    assert parse_scale_label("CHI TIẾT B TL 2:1") is None
    assert parse_scale_label("10:1") is None
    assert parse_scale_label("2:1") is None


def test_red_mm_per_px_for_scale_cannot_represent_enlargement():
    """RED 2: mm_per_px_for_scale assumes reduction 1:N, scaling in the opposite direction."""
    dpi = 300
    base_unit_scale = 25.4 / dpi  # 1:1 scale (0.084666 mm/px)

    # For an enlargement 2:1, CAD features are 2x larger on paper, so 1 pixel represents HALF the CAD mm:
    # expected enlargement mm_per_px = (1 / 2.0) * (25.4 / dpi) = 0.5 * base_unit_scale
    expected_enlargement_scale = 0.5 * base_unit_scale

    # But production mm_per_px_for_scale(2, dpi) computes 2 * 25.4 / dpi (1:2 reduction, 2x LARGER mm/px):
    computed_prod = mm_per_px_for_scale(2, dpi)
    assert computed_prod == 2.0 * base_unit_scale
    # The production formula results in a 4x relative error for a 2:1 enlargement!
    assert computed_prod != expected_enlargement_scale
    assert computed_prod / expected_enlargement_scale == 4.0


def test_red_detail_bubble_misclassified_as_bolt_hole():
    """RED 3: A detail bubble circle in parent view is misclassified as bolt hole (lo_bat_vit)."""
    # A detail circle with radius 12mm around a small feature
    circle_prim = Primitive(
        id="c_bubble",
        type="circle",
        source="hough_circle",
        confidence=0.9,
        trace=Trace(bbox_px=(88, 88, 112, 112)),
        geometry=CircleGeometry(center=Point2D(100.0, 100.0), radius=12.0),
    )
    parts = build_parts_from_primitives([circle_prim])
    assert len(parts) == 1
    # Misclassified as lo_bat_vit because radius <= 15.0 mm!
    assert parts[0].part_type == "lo_bat_vit"


def test_red_production_has_no_detail_view_models():
    """RED 4: semantic_ir_lib/models.py PartType omits detail view types."""
    import typing
    part_types = typing.get_args(PartType)
    assert "detail_bubble" not in part_types
    assert "detail_callout" not in part_types
    assert "detail_correspondence" not in part_types


def test_red_zero_parent_to_detail_view_linking():
    """RED 5: Production packages have zero functions for linking parent bubble to detail view."""
    with pytest.raises(ImportError):
        from primitive_ir_lib.view_calibration import resolve_detail_view_correspondence  # type: ignore # noqa: F401
    with pytest.raises(ImportError):
        from semantic_ir_lib.view_detection import link_detail_views  # type: ignore # noqa: F401
