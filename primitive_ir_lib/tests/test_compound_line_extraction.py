from __future__ import annotations

import cv2
import numpy as np

from primitive_ir_lib import geometry_extraction
from primitive_ir_lib.geometry_extraction import RawLine


def _compound_component(*, dx: int = 0, dy: int = 0) -> np.ndarray:
    image = np.zeros((140, 180), dtype=np.uint8)
    segments = (
        ((20, 10), (20, 90)),
        ((27, 35), (57, 35)),
        ((57, 38), (57, 55)),
        ((27, 55), (57, 55)),
        ((27, 36), (27, 54)),
        ((20, 82), (13, 89)),
    )
    for start, end in segments:
        shifted_start = (start[0] + dx, start[1] + dy)
        shifted_end = (end[0] + dx, end[1] + dy)
        cv2.line(image, shifted_start, shifted_end, 255, 1)
    return image


def _normalised_segments(lines: list[RawLine]) -> list[tuple[float, ...]]:
    points = [point for line in lines for point in (line.p1_px, line.p2_px)]
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    segments = []
    for line in lines:
        endpoints = sorted((line.p1_px, line.p2_px))
        segments.append(
            tuple(
                round(value, 3)
                for point in endpoints
                for value in (point[0] - min_x, point[1] - min_y)
            )
        )
    return sorted(segments)


def _expected_normalised_segments() -> list[tuple[float, ...]]:
    return sorted(
        (
            (7.0, 0.0, 7.0, 80.0),
            (14.0, 25.0, 44.0, 25.0),
            (44.0, 28.0, 44.0, 45.0),
            (14.0, 45.0, 44.0, 45.0),
            (14.0, 26.0, 14.0, 44.0),
            (0.0, 79.0, 7.0, 72.0),
        )
    )


_LOCKED_CORNER_SEGMENT = (14.0, 26.0, 14.0, 44.0)
_CORNER_ENDPOINT_VARIANTS = {
    _LOCKED_CORNER_SEGMENT,
    (14.0, 25.0, 14.0, 45.0),
}


def _rotate_normalised_segment(segment: tuple[float, ...]) -> tuple[float, ...]:
    x1, y1, x2, y2 = segment
    endpoints = sorted(((80.0 - y1, x1), (80.0 - y2, x2)))
    return tuple(value for point in endpoints for value in point)


def _assert_observable_normalised_segments(
    lines: list[RawLine], *, rotated: bool = False
) -> None:
    expected = set(_expected_normalised_segments()) - {_LOCKED_CORNER_SEGMENT}
    variants = _CORNER_ENDPOINT_VARIANTS
    if rotated:
        expected = {_rotate_normalised_segment(segment) for segment in expected}
        variants = {_rotate_normalised_segment(segment) for segment in variants}

    actual = _normalised_segments(lines)
    assert len(actual) == 6
    assert len(set(actual)) == 6
    assert set(actual) - expected <= variants
    assert len(set(actual) & variants) == 1
    assert set(actual) == expected | (set(actual) & variants)


def _render_raw_lines(lines: list[RawLine], shape: tuple[int, int]) -> np.ndarray:
    rendered = np.zeros(shape, dtype=np.uint8)
    for line in lines:
        start = tuple(int(round(value)) for value in line.p1_px)
        end = tuple(int(round(value)) for value in line.p2_px)
        cv2.line(rendered, start, end, 255, 1)
    return rendered


def test_compound_line_emission_is_translation_invariant_and_uses_rawline_owner():
    """A normalized branch/rectangle/segment component must emit six RawLines.

    The translated fixture is the same topology at a different image location;
    its result must therefore have the same normalized geometry and no
    Page-1-specific coordinates may be part of the contract.
    """
    extractor = getattr(geometry_extraction, "extract_compound_raw_lines", None)
    assert callable(extractor), (
        "geometry_extraction owner must expose extract_compound_raw_lines "
        "before compound LINE reconstruction can be admitted"
    )

    origin = extractor(_compound_component())
    translated = extractor(_compound_component(dx=31, dy=19))

    assert len(origin) == 6
    assert len(translated) == 6
    assert all(isinstance(line, RawLine) for line in origin + translated)
    _assert_observable_normalised_segments(origin)
    assert _normalised_segments(origin) == _normalised_segments(translated)
    assert np.array_equal(
        _render_raw_lines(origin, _compound_component().shape),
        _compound_component(),
    )
    assert np.array_equal(
        _render_raw_lines(translated, _compound_component(dx=31, dy=19).shape),
        _compound_component(dx=31, dy=19),
    )


def test_compound_line_emission_is_rotation_invariant():
    """The same topology rotated in the image must rotate its RawLine output."""
    extractor = getattr(geometry_extraction, "extract_compound_raw_lines", None)
    assert callable(extractor)

    rotated_component = cv2.rotate(_compound_component(), cv2.ROTATE_90_CLOCKWISE)
    rotated = extractor(rotated_component)

    assert len(rotated) == 6
    assert all(isinstance(line, RawLine) for line in rotated)
    _assert_observable_normalised_segments(rotated, rotated=True)
    assert np.array_equal(
        _render_raw_lines(rotated, rotated_component.shape),
        rotated_component,
    )
