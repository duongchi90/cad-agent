from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.dimension_geometry import (
    _select_dimension_line,
    detect_dimension_geometry,
    detect_dimension_geometry_regions,
)
from primitive_ir_lib.tests.dimension_test_helpers import (
    synthetic_diagonal_non_leader,
    synthetic_horizontal_dimension,
    synthetic_leader_annotation,
)

_CASE01_IMAGE_ENV = "CAD_AGENT_CASE01_LINE_IMAGE"
_CASE01_RENDER_SHA256 = "5732b6014ec1c1d3b05e14c598b43ebec84a4d6198951264215a69fb7b0a0bc8"
_CASE01_UPPER_WITNESS = (153, 198, 168, 219)
_CASE01_LOWER_WITNESS = (153, 369, 168, 390)


def _source_supported_arrow_page(*, lower_x: int = 70, include_upper: bool = True) -> np.ndarray:
    page = np.full((140, 160, 3), 255, dtype=np.uint8)
    cv2.line(page, (70, 45), (70, 95), (0, 0, 0), 2)
    if include_upper:
        cv2.fillConvexPoly(
            page,
            np.array([[70, 32], [64, 42], [76, 42]], dtype=np.int32),
            (0, 0, 0),
        )
    cv2.fillConvexPoly(
        page,
        np.array([[lower_x, 108], [lower_x - 6, 98], [lower_x + 6, 98]], dtype=np.int32),
        (0, 0, 0),
    )
    return page


def test_dimension_selector_ranks_horizontal_and_vertical_candidates_together() -> None:
    shaft = ((18.0, 18.0), (18.0, 157.0))
    text_strokes = (
        ((2.0, 1.0), (35.0, 1.0)),
        ((2.0, 171.0), (35.0, 171.0)),
    )

    selected, kind = _select_dimension_line([*text_strokes, shaft])

    assert selected == shaft
    assert kind == "VERTICAL_DISTANCE"


def test_dimension_selector_preserves_longest_candidate_after_quarter_turn() -> None:
    # Clockwise quarter-turn of the same exact three-candidate crop.
    shaft = ((18.0, 18.0), (157.0, 18.0))
    text_strokes = (
        ((171.0, 2.0), (171.0, 35.0)),
        ((1.0, 2.0), (1.0, 35.0)),
    )

    selected, kind = _select_dimension_line([*text_strokes, shaft])

    assert selected == shaft
    assert kind == "HORIZONTAL_DISTANCE"


def test_dimension_region_discovers_two_source_supported_flanks() -> None:
    page = _source_supported_arrow_page()

    regions = detect_dimension_geometry_regions(page)

    assert any(left <= 70 <= right and top <= 32 and bottom >= 108
               for left, top, right, bottom in regions), regions


@pytest.mark.parametrize(
    "page",
    [
        _source_supported_arrow_page(include_upper=False),
        _source_supported_arrow_page(lower_x=82),
    ],
    ids=["missing-witness", "split-off-axis-witnesses"],
)
def test_dimension_region_rejects_incomplete_or_split_flank_pairs(page: np.ndarray) -> None:
    regions = detect_dimension_geometry_regions(page)

    assert regions == ()


def test_dimension_region_rejects_frame_corner_without_opposing_flanks() -> None:
    page = np.full((180, 180, 3), 255, dtype=np.uint8)
    cv2.line(page, (70, 25), (70, 155), (0, 0, 0), 2)
    cv2.line(page, (20, 25), (70, 25), (0, 0, 0), 2)

    assert detect_dimension_geometry_regions(page) == ()


@pytest.mark.real_data
def test_case01_detects_both_frozen_arrow_witnesses_without_fixture_guidance() -> None:
    image_value = os.environ.get(_CASE01_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_CASE01_IMAGE_ENV} to run the frozen CASE01 geometry regression")
    image_path = Path(image_value)
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == _CASE01_RENDER_SHA256
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None

    regions = detect_dimension_geometry_regions(image)

    observed = []
    for left, top, right, bottom in regions:
        geometry = detect_dimension_geometry(image[top:bottom, left:right])
        if geometry.dimension_line is None or len(geometry.arrow_points) != 2:
            continue
        page_points = [(x + left, y + top) for x, y in geometry.arrow_points]
        if any(
            _CASE01_UPPER_WITNESS[0] <= x < _CASE01_UPPER_WITNESS[2]
            and _CASE01_UPPER_WITNESS[1] <= y < _CASE01_UPPER_WITNESS[3]
            for x, y in page_points
        ) and any(
            _CASE01_LOWER_WITNESS[0] <= x < _CASE01_LOWER_WITNESS[2]
            and _CASE01_LOWER_WITNESS[1] <= y < _CASE01_LOWER_WITNESS[3]
            for x, y in page_points
        ):
            observed.append((left, top, right, bottom, page_points))
    assert observed, regions

    from primitive_ir_lib.dimension_observer import detect_dimension_clusters
    from primitive_ir_lib.text_extraction import detect_text_candidate_rois

    text_boxes = detect_text_candidate_rois(image)
    clusters = detect_dimension_clusters(image)
    roi_pairs = []
    for left, top, right, bottom, _ in observed:
        for text_left, text_top, text_right, text_bottom in text_boxes:
            overlaps = not (
                right < text_left or text_right < left or bottom < text_top or text_bottom < top
            )
            if not overlaps:
                continue
            roi_pairs.append((
                (left, top, right, bottom),
                (text_left, text_top, text_right, text_bottom),
            ))
    assert roi_pairs, "the detected source geometry must associate with an original text ROI"
    assert any(
        cluster.bbox_px[0] <= min(geometry_box[0], text_box[0])
        and cluster.bbox_px[1] <= min(geometry_box[1], text_box[1])
        and cluster.bbox_px[2] >= max(geometry_box[2], text_box[2])
        and cluster.bbox_px[3] >= max(geometry_box[3], text_box[3])
        for cluster in clusters
        for geometry_box, text_box in roi_pairs
    ), "observation ROI must retain the original text cluster and associated geometry"


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
