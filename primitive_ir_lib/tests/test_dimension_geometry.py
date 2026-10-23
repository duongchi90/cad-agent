from __future__ import annotations

import numpy as np

from primitive_ir_lib.dimension_geometry import detect_dimension_geometry
from primitive_ir_lib.dimension_geometry import associate_arrow_tip_to_circles
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


def test_radial_arrow_contact_returns_only_the_unique_source_supported_circle() -> None:
    result = associate_arrow_tip_to_circles(
        arrow_tip=(0.0, 0.0),
        candidates=(
            {"id": "circle-a", "center": (10.0, 0.0), "radius": 10.0},
            {"id": "circle-b", "center": (30.0, 0.0), "radius": 10.0},
        ),
        contact_bound=0.2,
    )

    assert result == {
        "status": "UNIQUE_CANDIDATE",
        "target_id": "circle-a",
        "residual": 0.0,
        "contact_bound": 0.2,
    }


def test_radial_arrow_contact_fails_closed_for_ambiguity_or_missing_bound() -> None:
    candidates = (
        {"id": "circle-a", "center": (10.0, 0.0), "radius": 10.0},
        {"id": "circle-b", "center": (-10.0, 0.0), "radius": 10.0},
    )
    ambiguous = associate_arrow_tip_to_circles(
        arrow_tip=(0.0, 0.0), candidates=candidates, contact_bound=0.2,
    )
    unresolved = associate_arrow_tip_to_circles(
        arrow_tip=(0.0, 0.0), candidates=candidates, contact_bound=None,
    )

    assert ambiguous["status"] == "AMBIGUOUS"
    assert ambiguous["target_id"] is None
    assert unresolved["status"] == "UNRESOLVED"
    assert unresolved["target_id"] is None
