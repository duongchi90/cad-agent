from __future__ import annotations

import numpy as np

from primitive_ir_lib.dimension_geometry import detect_dimension_geometry
from primitive_ir_lib.tests.dimension_test_helpers import (
    synthetic_diagonal_non_leader,
    synthetic_horizontal_dimension,
    synthetic_leader_annotation,
)


def test_horizontal_dimension_geometry_is_deterministic() -> None:
    image = synthetic_horizontal_dimension()
    first = detect_dimension_geometry(image)
    second = detect_dimension_geometry(image.copy())
    assert first == second
    assert first.dimension_line is not None
    assert len(first.extension_lines) == 2
    assert len(first.arrow_points) == 2
    assert first.kind_hint == "HORIZONTAL_DISTANCE"


def test_blank_crop_has_no_false_dimension() -> None:
    image = np.full((80, 240, 3), 255, dtype=np.uint8)
    evidence = detect_dimension_geometry(image)
    assert evidence.dimension_line is None
    assert evidence.extension_lines == ()
    assert evidence.arrow_points == ()


def test_leader_line_with_arrow_marker_is_detected_deterministically() -> None:
    first = detect_dimension_geometry(synthetic_leader_annotation())
    second = detect_dimension_geometry(synthetic_leader_annotation())

    assert first == second
    assert len(first.leader_lines) == 1


def test_blank_and_unmarked_diagonal_have_no_leader_evidence() -> None:
    blank = np.full((80, 240, 3), 255, dtype=np.uint8)

    assert detect_dimension_geometry(blank).leader_lines == ()
    assert detect_dimension_geometry(synthetic_diagonal_non_leader()).leader_lines == ()
