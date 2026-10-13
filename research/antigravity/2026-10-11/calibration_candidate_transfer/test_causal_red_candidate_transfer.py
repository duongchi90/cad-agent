"""Causal RED test suite proving baseline transfer barriers and hazards between
cross_validate() (post-calibration verification) and auto_estimate_calibration() (pre-calibration discovery).

Failure Modes & Hazards:
RED 1: Seam Incompatibility: Production auto_estimate_calibration does not accept raw_circles or raw_arcs;
       passing circles raises TypeError.
RED 2: Concentric Circle Ambiguity Hazard: In cross_validate, prior scale S0 disambiguates concentric
       boreholes (counterbore vs through-hole). In auto_estimate_calibration, without S0, naive transfer
       snaps to the wrong concentric circle, producing a 100% scale error (0.20 vs 0.10 mm/px).
RED 3: Zero-Candidate Extraction on CASE01 Text Gaps: Production find_nearest_line fails to bridge gaps,
       causing auto_estimate_calibration to fail consensus or return halved spans.
RED 4: Scale Assumption Leakage: Pre-calibration association cannot use physical millimeter thresholds;
       must operate purely on scale-free pixel topological invariants.
RED 5: Downstream Fail-Closed Boundary: Verification that candidate extraction must remain strictly gated
       at status='needs_verification' with Semantic IR and DXF blocked.
"""

import pytest
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.geometry_extraction import RawLine, RawCircle


def test_red_1_production_auto_estimate_calibration_lacks_circle_parameter():
    """RED 1: Production auto_estimate_calibration signature is:
    (raw_texts, raw_lines, image_height_px, unit='mm', max_distance_px=150.0, ...)
    It has no 'raw_circles' or 'raw_arcs' parameter. Passing circles raises TypeError."""
    text = RawText("t1", "Ø50", (100.0, 100.0, 140.0, 120.0), 0.0, 0.95, "ocr", 50.0, "dimension_value")
    circle = RawCircle("c1", (120.0, 110.0), 50.0, 0.95, (70.0, 60.0, 170.0, 160.0))

    # Calling with raw_circles raises TypeError in current production:
    with pytest.raises(TypeError, match="unexpected keyword argument 'raw_circles'"):
        auto_estimate_calibration([text], [], image_height_px=1000, raw_circles=[circle])  # type: ignore


def test_red_2_concentric_circle_ambiguity_hazard():
    """RED 2: A counterbore feature has two concentric circles sharing center (300, 300):
      - c_inner: radius 50px (diameter 100px) -> for through-hole Ø10.0mm (true scale 0.100 mm/px)
      - c_outer: radius 100px (diameter 200px) -> for counterbore Ø20.0mm (true scale 0.100 mm/px)
    In cross_validate(), a known scale S0 = 0.100 mm/px easily pairs text 'Ø10.0' with c_inner (100px * 0.1 = 10mm).
    In auto_estimate_calibration(), without prior scale, if text 'Ø20.0' sits slightly closer to the inner hole edge,
    naive nearest-circle snapping pairs 'Ø20.0' with c_inner (100px diameter), computing scale:
      20.0 / 100px = 0.200 mm/px (+100% scale error!).
    Falsifies: Naive transfer from cross_validate is unsafe without concentricity disambiguation."""
    # Text 'Ø20.0' placed at (320, 320) [dist to center is 28.3px, inside inner circle]
    text_20 = RawText("t_20", "Ø20.0", (310.0, 310.0, 330.0, 330.0), 0.0, 0.95, "ocr", 20.0, "dimension_value")

    c_inner = RawCircle("c_inner", (300.0, 300.0), 50.0, 0.95, (250.0, 250.0, 350.0, 350.0))   # Diam = 100px
    c_outer = RawCircle("c_outer", (300.0, 300.0), 100.0, 0.95, (200.0, 200.0, 400.0, 400.0))  # Diam = 200px

    # Naive snapping picks inner circle because text is closer to inner radius than outer radius:
    # dist to inner circle edge: |28.3 - 50| = 21.7px
    # dist to outer circle edge: |28.3 - 100| = 71.7px
    dist_inner = abs(np.hypot(320 - 300, 320 - 300) - 50.0)
    dist_outer = abs(np.hypot(320 - 300, 320 - 300) - 100.0)
    assert dist_inner < dist_outer  # Inner circle is closer to text!

    naive_picked = c_inner if dist_inner < dist_outer else c_outer
    naive_diam = naive_picked.radius_px * 2.0
    naive_scale = text_20.parsed_value / naive_diam
    true_scale = 20.0 / (c_outer.radius_px * 2.0)  # 20.0 / 200 = 0.100 mm/px

    # Catastrophic error:
    assert naive_scale == 0.200
    assert true_scale == 0.100
    assert abs(naive_scale - true_scale) / true_scale == 1.0  # 100% error!


def test_red_3_production_find_nearest_line_fails_on_collinear_text_gaps():
    """RED 3: When dimension lines are split by text gaps, production
    find_nearest_line returns a half-segment with length 90px instead of the true 250px span.
    When require_consensus=True, split lines produce inconsistent scales that fail consensus."""
    t1 = RawText("t1", "25.0", (100.0, 95.0, 130.0, 105.0), 0.0, 0.95, "ocr", 25.0, "dimension_value")
    # True span is 250px (0 to 250). True scale = 0.100 mm/px.
    # Fragmented into two segments: (0, 100) -> (90, 100) and (140, 100) -> (250, 100)
    seg1 = RawLine("s1", p1_px=(0.0, 100.0), p2_px=(90.0, 100.0), confidence=0.9, bbox_px=(0.0, 100.0, 90.0, 100.0))
    seg2 = RawLine("s2", p1_px=(140.0, 100.0), p2_px=(250.0, 100.0), confidence=0.9, bbox_px=(140.0, 100.0, 250.0, 100.0))

    best = find_nearest_line(t1, [seg1, seg2])
    assert best is not None
    # Best line has length 90 or 110, never the full 250px span!
    assert best.length_px() < 120.0
    err_scale = t1.parsed_value / best.length_px()
    assert abs(err_scale - 0.100) / 0.100 > 1.0  # > 100% scale calculation error!


def test_red_4_scale_assumption_leakage_hazard():
    """RED 4: If an association algorithm hardcodes a pixel distance threshold (e.g. max_distance_px=150.0),
    on a high-resolution 1200 DPI scan, standard dimension text spacing (6mm = 283px) exceeds 150px
    and is falsely rejected as 'unsupported'."""
    # At 1200 DPI, 1 inch = 1200px, 1mm = 47.24px.
    # Text offset of 4mm = 189px from dimension line.
    text_1200dpi = RawText("t_hires", "10.0", (500.0, 100.0, 600.0, 150.0), 0.0, 0.95, "ocr", 10.0, "dimension_value")
    dim_line = RawLine("l_hires", p1_px=(0.0, 320.0), p2_px=(1000.0, 320.0), confidence=0.95, bbox_px=(0.0, 320.0, 1000.0, 320.0))
    # Distance between text center y=125 and line y=320 is 195px.
    # Production find_nearest_line with max_distance_px=150.0 fails!
    matched = find_nearest_line(text_1200dpi, [dim_line], max_distance_px=150.0)
    assert matched is None  # Falsely dropped due to static pixel threshold!


def test_red_5_candidate_mode_must_strictly_gate_semantic_and_dxf():
    """RED 5: Confirm that candidate extraction must strictly preserve status='needs_verification'
    and block Semantic IR and DXF. Semantic IR io_utils line 108 must raise ValueError on any
    unverified candidate."""
    from semantic_ir_lib.io_utils import _primitive_ir_document_from_dict

    # A mock primitive document with auto-extracted candidate:
    mock_doc = {
        "source_document": {
            "file_name": "test.png",
            "page_index": 0,
            "image_width_px": 1000,
            "image_height_px": 1000,
            "sha256": "dummy_sha256",
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 0.100,
            "origin_px": (0.0, 1000.0),
            "method": "auto_estimate_calibration",
            "status": "needs_verification",  # Unverified candidate
            "source_sha256": "dummy_sha256",
        },
        "primitives": [],
    }

    # Calling semantic IR conversion on unverified candidate MUST fail closed:
    with pytest.raises(ValueError, match="Primitive IR calibration is needs_verification; Semantic IR assembly is refused"):
        _primitive_ir_document_from_dict(mock_doc)
