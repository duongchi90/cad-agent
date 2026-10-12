"""Causal RED tests for Cutting Plane Line and Section View Correspondence.

These tests exercise CURRENT production code in:
- primitive_ir_lib/view_calibration.py
- semantic_ir_lib/models.py
- primitive_ir_lib/dimension_symbols.py

Demonstrating the exact production gaps:
1. parse_scale_label ignores section titles ("SECTION A-A", "MẶT CẮT A-A").
2. detect_view_candidates drops or unclassifies section views with zero semantic view typing.
3. semantic_ir_lib/models.py lacks cutting_plane and cross-view section correspondence models.
4. Production dimension/tick detectors fail to extract viewing vectors from cutting plane arrows.
5. Production has zero cross-view parent-to-section linking capability.
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

from primitive_ir_lib.view_calibration import parse_scale_label, detect_view_candidates
from semantic_ir_lib.models import SemanticPart, PartType
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText


def test_red_production_scale_label_blind_to_section_titles():
    """RED 1: parse_scale_label only parses scale ratios, completely blind to section titles."""
    # Production function only matches r"(?:TL|THI|TY\s*(?:LE|L[EB]|1[EB])|TILE)\s*[-:]?\s*1\s*:\s*(\d+)"
    # and r"\s*1\s*:\s*(\d+)\s*"
    assert parse_scale_label("SECTION A-A") is None
    assert parse_scale_label("SECTION B-B") is None
    assert parse_scale_label("MẶT CẮT A-A") is None
    assert parse_scale_label("CUT A-A") is None


def test_red_detect_view_candidates_lacks_section_view_classification():
    """RED 2: detect_view_candidates ignores section titles and outputs flat dicts without view_type."""
    # Create raw lines for parent view at (100, 100) to (200, 200)
    lines = [
        RawLine(id="l1", p1_px=(100.0, 100.0), p2_px=(200.0, 100.0), confidence=0.9, bbox_px=(100.0, 100.0, 200.0, 100.0)),
        RawLine(id="l2", p1_px=(200.0, 100.0), p2_px=(200.0, 200.0), confidence=0.9, bbox_px=(200.0, 100.0, 200.0, 200.0)),
        RawLine(id="l3", p1_px=(200.0, 200.0), p2_px=(100.0, 200.0), confidence=0.9, bbox_px=(100.0, 200.0, 200.0, 200.0)),
        RawLine(id="l4", p1_px=(100.0, 200.0), p2_px=(100.0, 100.0), confidence=0.9, bbox_px=(100.0, 100.0, 100.0, 200.0)),
        # Section view lines at (400, 100) to (500, 200)
        RawLine(id="s1", p1_px=(400.0, 100.0), p2_px=(500.0, 100.0), confidence=0.9, bbox_px=(400.0, 100.0, 500.0, 100.0)),
        RawLine(id="s2", p1_px=(500.0, 100.0), p2_px=(500.0, 200.0), confidence=0.9, bbox_px=(500.0, 100.0, 500.0, 200.0)),
        RawLine(id="s3", p1_px=(500.0, 200.0), p2_px=(400.0, 200.0), confidence=0.9, bbox_px=(400.0, 200.0, 500.0, 200.0)),
        RawLine(id="s4", p1_px=(400.0, 200.0), p2_px=(400.0, 100.0), confidence=0.9, bbox_px=(400.0, 100.0, 400.0, 200.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(400, 80, 480, 95), rotation_deg=0.0, confidence=0.9, source="text_tesseract"),
    ]

    candidates = detect_view_candidates(
        raw_texts=texts,
        raw_lines=lines,
        image_width=1000,
        image_height=1000,
        dpi=300,
    )

    # In production, because parse_scale_label("SECTION A-A") is None,
    # detect_view_candidates finds ZERO candidates for the section view!
    assert len(candidates) == 0, (
        f"Expected 0 candidates because production drops text without scale ratio, got {len(candidates)}"
    )


def test_red_production_has_no_cutting_plane_part_type():
    """RED 3: SemanticPart does not support cutting plane or section correspondence types."""
    import typing
    part_types = typing.get_args(PartType)
    assert "cutting_plane" not in part_types
    assert "section_callout" not in part_types
    assert "viewing_arrow" not in part_types
    assert "section_correspondence" not in part_types


def test_red_cutting_plane_arrows_unrecognized_as_viewing_vectors():
    """RED 4: Production dimension and tick detectors do not extract viewing vectors."""
    from primitive_ir_lib.dimension_symbols import _parse_core
    
    # Text labels 'A' and 'A' at cutting plane extremities
    parsed_a = _parse_core("A")
    # 'A' is not a dimension text, so it returns None
    assert parsed_a is None

    # There is no production function in primitive_ir_lib or semantic_ir_lib that calculates
    # viewing vector from arrow heads pointing at cutting plane ends
    with pytest.raises(ImportError):
        from primitive_ir_lib.view_calibration import extract_cutting_plane_viewing_vector  # type: ignore # noqa: F401


def test_red_zero_cross_view_section_correspondence():
    """RED 5: Production packages have zero functions for linking parent view cutting plane to section view."""
    with pytest.raises(ImportError):
        from semantic_ir_lib.view_detection import link_section_views  # type: ignore # noqa: F401
    with pytest.raises(ImportError):
        from primitive_ir_lib.view_calibration import resolve_section_view_correspondence  # type: ignore # noqa: F401
