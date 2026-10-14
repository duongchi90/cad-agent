from __future__ import annotations

import cv2
import numpy as np
import pytest

from primitive_ir_lib import geometry_extraction as geometry


CLOSED_RING = "closed_ring_identity_v1"


def _blank(height: int = 128, width: int = 160) -> np.ndarray:
    return np.full((height, width, 3), 255, dtype=np.uint8)


def _rings(
    centers: list[tuple[int, int]], radius: int = 10, thickness: int = 1,
    *, height: int = 128, width: int = 160,
) -> np.ndarray:
    image = _blank(height, width)
    for center in centers:
        cv2.circle(image, center, radius, (0, 0, 0), thickness=thickness, lineType=cv2.LINE_8)
    return image


def _assert_matches(circles, expected: list[tuple[int, int, float]]) -> None:
    assert len(circles) == len(expected)
    unmatched = list(circles)
    for x, y, radius in expected:
        match = next((c for c in unmatched if
                      abs(c.center_px[0] - x) <= 1.0
                      and abs(c.center_px[1] - y) <= 1.0
                      and abs(c.radius_px - radius) <= 1.5), None)
        assert match is not None, f"missing expected circle {(x, y, radius)} from {unmatched!r}"
        unmatched.remove(match)


def _forbid_hough(monkeypatch) -> None:
    def unexpected(*args, **kwargs):
        raise AssertionError("closed-ring strategy must not call Hough")

    monkeypatch.setattr(geometry.cv2, "HoughLinesP", lambda *a, **k: None)
    monkeypatch.setattr(geometry.cv2, "HoughCircles", unexpected)


def test_public_strategy_extracts_dense_rings_without_hough(monkeypatch):
    _forbid_hough(monkeypatch)
    centers = [(28, 28), (64, 28), (100, 28), (28, 68), (64, 68), (100, 68)]
    image = _rings(centers, radius=10, thickness=1, height=100, width=128)

    result = geometry.extract_raw_geometry(image, circle_strategy=CLOSED_RING)

    _assert_matches(result.circles, [(x, y, 10.0) for x, y in centers])
    assert all(c.confidence == 0.75 for c in result.circles)
    assert all(np.isfinite(c.radius_px) and c.radius_px > 0 for c in result.circles)
    assert all(all(np.isfinite(v) for v in c.bbox_px) for c in result.circles)


def test_invalid_strategy_rejects_before_any_acquisition(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid strategy reached image acquisition")

    monkeypatch.setattr(geometry, "extract_lines", unexpected)
    monkeypatch.setattr(geometry, "extract_circles", unexpected)
    with pytest.raises(ValueError):
        geometry.extract_raw_geometry(_blank(), circle_strategy=" Closed_Ring_Identity_V1 ")


def test_omitted_and_explicit_hough_keep_existing_preset_arguments(monkeypatch):
    line_calls = []
    circle_calls = []

    def record_lines(image, **kwargs):
        line_calls.append(dict(kwargs))
        return []

    def record_circles(image, **kwargs):
        circle_calls.append(dict(kwargs))
        return []

    monkeypatch.setattr(geometry, "extract_lines", record_lines)
    monkeypatch.setattr(geometry, "extract_circles", record_circles)
    image = _blank()
    geometry.extract_raw_geometry(image)
    geometry.extract_raw_geometry(image, circle_strategy="hough")
    geometry.extract_raw_geometry(image, preset="real_scan_tuned_v1", circle_strategy="hough")

    assert line_calls == [
        {"hough_threshold": 60, "min_line_length": 30, "max_line_gap": 10},
        {"hough_threshold": 60, "min_line_length": 30, "max_line_gap": 10},
        {"hough_threshold": 90, "min_line_length": 50, "max_line_gap": 5},
    ]
    assert circle_calls == [
        {"param2": 30, "max_radius": 200, "min_dist": 20},
        {"param2": 30, "max_radius": 200, "min_dist": 20},
        {"param2": 55, "max_radius": 80, "min_dist": 40},
    ]


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((12, 12), dtype=np.uint8),
        np.zeros((12, 12, 4), dtype=np.uint8),
        np.zeros((12, 12, 3), dtype=np.float32),
        np.zeros((0, 12, 3), dtype=np.uint8),
    ],
)
def test_contour_strategy_rejects_invalid_image_before_acquisition(monkeypatch, image):
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid BGR input reached acquisition")

    monkeypatch.setattr(geometry, "extract_lines", unexpected)
    monkeypatch.setattr(geometry, "extract_circles", unexpected)
    with pytest.raises(ValueError):
        geometry.extract_raw_geometry(image, circle_strategy=CLOSED_RING)


def test_canonical_point_identity_ignores_order_and_duplicates_but_not_coordinates():
    canonicalize = getattr(geometry, "_canonical_point_set", None)
    assert callable(canonicalize), "owner must expose its exact point-set identity primitive"
    original = np.asarray([[1, 2], [3, 4], [5, 6]], dtype=np.int32)
    reordered_with_duplicates = np.asarray([[5, 6], [1, 2], [3, 4], [1, 2]], dtype=np.int32)
    moved = np.asarray([[1, 2], [3, 4], [5, 7]], dtype=np.int32)
    assert canonicalize(original) == canonicalize(reordered_with_duplicates)
    assert canonicalize(original) != canonicalize(moved)


def test_thick_closed_ring_is_admitted(monkeypatch):
    _forbid_hough(monkeypatch)
    center = (64, 64)
    result = geometry.extract_raw_geometry(_rings([center], radius=22, thickness=3), circle_strategy=CLOSED_RING)
    _assert_matches(result.circles, [(64, 64, 22.0)])


def _negative_images() -> dict[str, np.ndarray]:
    square = _blank()
    cv2.rectangle(square, (40, 40), (88, 88), (0, 0, 0), 2, cv2.LINE_8)

    ellipse = _blank()
    cv2.ellipse(ellipse, (64, 64), (28, 15), 0, 0, 360, (0, 0, 0), 2, cv2.LINE_8)

    arc = _blank()
    cv2.ellipse(arc, (64, 64), (24, 24), 0, 35, 310, (0, 0, 0), 2, cv2.LINE_8)

    disk = _blank()
    cv2.circle(disk, (64, 64), 22, (0, 0, 0), -1, cv2.LINE_8)

    tangent = _blank()
    cv2.circle(tangent, (52, 64), 14, (0, 0, 0), 2, cv2.LINE_8)
    cv2.circle(tangent, (80, 64), 14, (0, 0, 0), 2, cv2.LINE_8)

    clipped = _blank()
    cv2.circle(clipped, (8, 64), 20, (0, 0, 0), 2, cv2.LINE_8)

    return {"square": square, "ellipse": ellipse, "open_arc": arc, "disk": disk,
            "tangent_sibling_holes": tangent, "clipped": clipped}


@pytest.mark.parametrize("name", ["square", "ellipse", "open_arc", "disk", "tangent_sibling_holes", "clipped"])
def test_non_circle_and_ambiguous_boundaries_abstain(monkeypatch, name):
    _forbid_hough(monkeypatch)
    result = geometry.extract_raw_geometry(_negative_images()[name], circle_strategy=CLOSED_RING)
    assert result.circles == []


def test_mixed_scene_keeps_only_independent_valid_rings(monkeypatch):
    _forbid_hough(monkeypatch)
    image = _rings([(28, 34), (28, 92)], radius=9, thickness=1, height=128, width=192)
    cv2.rectangle(image, (78, 20), (126, 62), (0, 0, 0), 2, cv2.LINE_8)
    cv2.ellipse(image, (154, 42), (21, 11), 0, 0, 360, (0, 0, 0), 2, cv2.LINE_8)

    result = geometry.extract_raw_geometry(image, circle_strategy=CLOSED_RING)

    _assert_matches(result.circles, [(28, 34, 9.0), (28, 92, 9.0)])


def test_input_pixel_limit_fails_before_partial_results_or_hough(monkeypatch):
    _forbid_hough(monkeypatch)
    image = np.full((2001, 2000, 3), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        geometry.extract_raw_geometry(image, circle_strategy=CLOSED_RING)


def test_fit_count_limit_is_checked_before_any_fit(monkeypatch):
    _forbid_hough(monkeypatch)
    image = _blank(800, 800)
    for i in range(257):
        x = 12 + (i % 25) * 30
        y = 12 + (i // 25) * 30
        cv2.circle(image, (x, y), 3, (0, 0, 0), -1, cv2.LINE_8)
    fit_calls = 0
    real_fit = geometry.cv2.fitEllipse

    def counted_fit(points):
        nonlocal fit_calls
        fit_calls += 1
        return real_fit(points)

    monkeypatch.setattr(geometry.cv2, "fitEllipse", counted_fit)
    with pytest.raises(ValueError):
        geometry.extract_raw_geometry(image, circle_strategy=CLOSED_RING)
    assert fit_calls == 0
