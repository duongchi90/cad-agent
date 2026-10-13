from __future__ import annotations

import numpy as np

from primitive_ir_lib.dimension_geometry import detect_dimension_geometry
from primitive_ir_lib.tests.dimension_test_helpers import (
    frozen_dimension_witness_image,
    pr503_frozen_track_image,
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


def test_frozen_complete_witness_remains_full_span() -> None:
    evidence = detect_dimension_geometry(frozen_dimension_witness_image("complete"))

    assert evidence.dimension_line is not None
    assert abs(evidence.dimension_line[0][1] - evidence.dimension_line[1][1]) <= 2.0
    assert abs(min(point[0] for point in evidence.dimension_line) - 40.0) <= 2.0
    assert abs(max(point[0] for point in evidence.dimension_line) - 180.0) <= 2.0
    assert len(evidence.extension_lines) == 2


def test_interrupted_witness_uses_both_outer_extension_bounds() -> None:
    evidence = detect_dimension_geometry(frozen_dimension_witness_image("interrupted"))

    assert evidence.dimension_line is not None
    assert abs(evidence.dimension_line[0][1] - evidence.dimension_line[1][1]) <= 2.0
    assert abs(min(point[0] for point in evidence.dimension_line) - 40.0) <= 2.0
    assert abs(max(point[0] for point in evidence.dimension_line) - 180.0) <= 2.0
    assert len(evidence.extension_lines) == 2


def test_one_extension_is_insufficient_for_full_dimension_witness() -> None:
    evidence = detect_dimension_geometry(
        frozen_dimension_witness_image("insufficient_association")
    )

    assert len(evidence.extension_lines) < 2


def test_unrelated_collinear_fragment_does_not_extend_witness_past_outer_bounds() -> None:
    evidence = detect_dimension_geometry(
        frozen_dimension_witness_image("unrelated_collinear_fragment")
    )

    assert evidence.dimension_line is not None
    assert abs(min(point[0] for point in evidence.dimension_line) - 40.0) <= 2.0
    assert abs(max(point[0] for point in evidence.dimension_line) - 180.0) <= 2.0
    assert len(evidence.extension_lines) == 2


def test_competing_same_anchor_witnesses_are_not_collapsed_to_one() -> None:
    evidence = detect_dimension_geometry(frozen_dimension_witness_image("competing_witness"))

    selected_full_span = (
        evidence.dimension_line is not None
        and abs(min(point[0] for point in evidence.dimension_line) - 40.0) <= 2.0
        and abs(max(point[0] for point in evidence.dimension_line) - 180.0) <= 2.0
        and len(evidence.extension_lines) >= 2
    )
    assert not selected_full_span


def test_one_track_near_both_dimension_endpoints_is_not_two_witnesses() -> None:
    evidence = detect_dimension_geometry(pr503_frozen_track_image("one_track_both_endpoints"))

    assert len(evidence.extension_lines) < 2 or evidence.extension_lines[0] != evidence.extension_lines[1]
    assert evidence.dimension_line is None or abs(
        evidence.dimension_line[0][0] - evidence.dimension_line[1][0]
    ) + abs(evidence.dimension_line[0][1] - evidence.dimension_line[1][1]) >= 28.0


def test_disconnected_nearby_tracks_do_not_form_distinct_outer_witnesses() -> None:
    evidence = detect_dimension_geometry(pr503_frozen_track_image("disconnected_inner_tracks"))

    assert len(evidence.extension_lines) < 2


def test_distinct_outer_tracks_remain_a_complete_dimension_witness() -> None:
    evidence = detect_dimension_geometry(pr503_frozen_track_image("distinct_outer_tracks"))

    assert evidence.dimension_line is not None
    assert len(evidence.extension_lines) == 2
    assert abs(
        evidence.extension_lines[1][0][0] - evidence.extension_lines[0][0][0]
    ) >= 28.0


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
