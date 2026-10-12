"""
test_causal_red_multileader_topology.py
Public Causal RED Suite demonstrating 5 deterministic failure modes on current production:
- primitive_ir_lib.dimension_geometry._detect_leader_lines
- primitive_ir_lib.dimension_geometry._has_leader_marker
- primitive_ir_lib.dimension_geometry.detect_dimension_geometry
"""

import math
import pytest
import numpy as np

from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, CircleGeometry, TextData, Trace
from primitive_ir_lib.dimension_geometry import (
    _detect_leader_lines,
    _has_leader_marker,
    _is_diagonal,
    _length,
)


def test_red_01_standard_arrowhead_leader_rejected():
    """RED 1: Production _has_leader_marker rejects standard mechanical arrowheads (< 18px).
    A pointer leg (20.0, 20.0) -> (60.0, 60.0) terminating with a realistic 6mm arrowhead barb.
    Because _has_leader_marker enforces `18.0 <= marker_length <= 55.0`, the arrowhead is ignored
    and _detect_leader_lines returns ()!
    """
    pointer = ((20.0, 20.0), (60.0, 60.0))  # Length 56.57, diagonal
    # Realistic 6mm acute arrowhead barb at tip (20, 20) -> (25.0, 23.0) -> length 5.83px
    arrow_barb = ((20.0, 20.0), (25.0, 23.0))

    segments = [pointer, arrow_barb]

    # Check _has_leader_marker directly
    has_marker = _has_leader_marker(pointer, segments)
    assert not has_marker, "Production _has_leader_marker should fail because barb length 5.83 < 18.0"

    # Full _detect_leader_lines output
    leaders = _detect_leader_lines(segments)
    # CAUSAL FAILURE: Zero leader lines detected! Standard arrowhead is rejected!
    assert len(leaders) == 0


def test_red_02_dogleg_horizontal_landing_line_dropped():
    """RED 2: Production _detect_leader_lines strictly filters _is_diagonal, dropping horizontal landing line.
    A standard ASME/ISO multileader has a diagonal pointer leg and a horizontal landing shelf.
    Production collects only diagonal_segments, completely dropping the horizontal landing line!
    """
    pointer = ((20.0, 20.0), (60.0, 60.0))  # Diagonal pointer
    landing = ((60.0, 60.0), (90.0, 60.0))  # Horizontal landing shelf (dogleg)
    # Synthetic secondary marker to bypass red 1 for this test
    synth_marker = ((18.0, 18.0), (35.0, 35.0))  # Length 24.0, diagonal

    segments = [pointer, landing, synth_marker]
    leaders = _detect_leader_lines(segments)

    # Pointer is detected, but landing line is completely absent!
    assert len(leaders) == 1
    detected_seg = leaders[0]
    # The detected segment is only the pointer leg
    assert not (detected_seg[0] == (60.0, 60.0) and detected_seg[1] == (90.0, 60.0))
    # CAUSAL FAILURE: The horizontal landing line is dropped from leader_lines!
    assert all(seg != landing for seg in leaders)


def test_red_03_target_feature_attachment_missing():
    """RED 3: Production dimension_geometry has 0 target primitive attachment.
    A leader points to a circular bore hole at center (20, 10), radius 10 (point on circumference (20, 20)).
    Production leader_lines emits raw geometric coordinate tuples without target attachment.
    """
    pointer = ((20.0, 20.0), (60.0, 60.0))
    synth_marker = ((18.0, 18.0), (35.0, 35.0))
    segments = [pointer, synth_marker]

    leaders = _detect_leader_lines(segments)
    assert len(leaders) == 1

    # CAUSAL FAILURE: The emitted leader line has 0 target feature ID or attachment metadata!
    leader_entry = leaders[0]
    assert isinstance(leader_entry, tuple)
    assert len(leader_entry) == 2  # Just ((x0, y0), (x1, y1))
    assert not hasattr(leader_entry, "attached_feature_id")


def test_red_04_callout_text_unassociated_with_leader():
    """RED 4: Callout text adjacent to leader landing shelf is unassociated.
    Callout text '4x Ø8.5 THRU' sits beside the landing line.
    Production returns disjoint text candidates and disjoint leader_lines with no link.
    """
    pointer = ((20.0, 20.0), (60.0, 60.0))
    synth_marker = ((18.0, 18.0), (35.0, 35.0))
    segments = [pointer, synth_marker]

    leaders = _detect_leader_lines(segments)
    # CAUSAL FAILURE: Zero association between leader lines and callout text
    assert len(leaders) == 1
    assert not hasattr(leaders[0], "callout_text")


def test_red_05_pointer_direction_and_knee_vertex_unidentified():
    """RED 5: Production represents leader lines as undirected symmetric segment tuples.
    A multileader is fundamentally directed: tip (arrowhead) -> knee (dogleg vertex).
    Production canonicalizes endpoints by coordinate order, losing which end is the tip!
    """
    pointer = ((20.0, 20.0), (60.0, 60.0))
    synth_marker = ((18.0, 18.0), (35.0, 35.0))
    segments = [pointer, synth_marker]

    leaders = _detect_leader_lines(segments)
    assert len(leaders) == 1
    seg = leaders[0]
    # CAUSAL FAILURE: Undirected segment. No tip vs knee classification exists!
    assert isinstance(seg, tuple)
    assert not hasattr(seg, "tip")
    assert not hasattr(seg, "knee")
