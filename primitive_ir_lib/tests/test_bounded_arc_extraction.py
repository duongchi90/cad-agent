"""Bounded real-source ARC extraction contract for Page-1 issue #409.

The approved source crop is private and intentionally not committed.  Set
``CAD_AGENT_PAGE1_CROP`` to run this focused causal test locally.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import pytest

from primitive_ir_lib.geometry_extraction import extract_raw_geometry


_CROP_ENV = "CAD_AGENT_PAGE1_CROP"
_EXPECTED_CROP_SHA256 = "e04056a6606f2351f53756050311aefca4bb8248e25db4928e533633f4b195b7"
_TOLERANCE_PX = 3
_POSITIVE_BOXES = {
    "720": (378, 465, 483, 536),
    "501": (366, 408, 519, 471),
}
_NEGATIVE_BOX = (359, 362, 487, 394)

pytestmark = pytest.mark.real_data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bbox_overlap(left: tuple[float, float, float, float], right: tuple[int, int, int, int]) -> int:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    return max(0, int(x1 - x0)) * max(0, int(y1 - y0))


def _target_overlap_fraction(
    left: tuple[float, float, float, float], right: tuple[int, int, int, int]
) -> float:
    target_area = max(1, (right[2] - right[0]) * (right[3] - right[1]))
    return _bbox_overlap(left, right) / target_area


def test_page1_arc_extraction_red_green_contract():
    crop_value = os.environ.get(_CROP_ENV)
    if not crop_value:
        pytest.skip(f"set {_CROP_ENV} to run the approved Page-1 source-bound test")
    crop = Path(crop_value)
    if not crop.is_file():
        raise AssertionError(f"{_CROP_ENV} does not point to a file: {crop}")
    assert _sha256(crop) == _EXPECTED_CROP_SHA256

    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    assert image is not None and tuple(image.shape[:2]) == (1608, 2261)
    geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")

    assert len(geometry.lines) == 520
    assert len(geometry.circles) == 19

    for label, box in _POSITIVE_BOXES.items():
        candidates = [
            arc for arc in geometry.arcs if _target_overlap_fraction(arc.bbox_px, box) >= 0.1
        ]
        assert candidates, f"missing ARC witness for positive component {label}"
        assert max(arc.confidence for arc in candidates) >= 0.5, label

    negative_candidates = [
        arc
        for arc in geometry.arcs
        if _target_overlap_fraction(arc.bbox_px, _NEGATIVE_BOX) >= 0.1
    ]
    assert all(arc.confidence < 0.5 for arc in negative_candidates)
