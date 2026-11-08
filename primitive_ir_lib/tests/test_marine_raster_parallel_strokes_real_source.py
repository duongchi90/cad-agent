"""Source-grounded line-merging preservation check for the ALMA/HAER ROI.

The source image is kept outside Git. Set CAD_AGENT_ALMA_HAER_PROFILE_ROI to
the frozen crop whose identity is recorded in #491.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.run_image import run as run_image

pytestmark = pytest.mark.real_data

_IMAGE_ENV = "CAD_AGENT_ALMA_HAER_PROFILE_ROI"
_ROI_SHA256 = "041f43513bfad96a63dec1cf2e74261e0451d7c99e8a19ba431e4c702e12c27f"
_STATION_COLUMNS = ((510, 539), (1265, 1294))


def _line_segments_px(document: dict) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    height = document["source_document"]["image_height_px"]
    segments = []
    for primitive in document["primitives"]:
        if primitive.get("type") != "line":
            continue
        geometry = primitive["geometry"]
        start = geometry["start"]
        end = geometry["end"]
        segments.append((
            (float(start["x"]), height - float(start["y"])),
            (float(end["x"]), height - float(end["y"])),
        ))
    return segments


def _source_pixel_coverage(
    gray: np.ndarray,
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    y_start: int,
    y_end: int,
) -> tuple[int, int]:
    rows, columns = np.where(gray[y_start:y_end + 1] < 128)
    rows = rows + y_start
    keep = np.ones(columns.shape, dtype=bool)
    for left, right in _STATION_COLUMNS:
        keep &= ~((columns >= left) & (columns <= right))
    columns = columns[keep].astype(float)
    rows = rows[keep].astype(float)

    covered = np.zeros(columns.shape, dtype=bool)
    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            continue
        fraction = np.clip(
            ((columns - x1) * dx + (rows - y1) * dy) / length_squared,
            0.0,
            1.0,
        )
        distance = np.hypot(
            columns - x1 - fraction * dx,
            rows - y1 - fraction * dy,
        )
        covered |= distance <= 2.5
    return int(covered.sum()), int(columns.size)


def _run(image: Path, output: Path, *, merge_lines: bool) -> dict:
    run_image(
        str(image),
        str(output),
        scale_mm_per_px=1.0,
        calibration_status="needs_verification",
        preset="real_scan_tuned_v1",
        merge_lines=merge_lines,
        auto_ocr_roi=False,
        auto_calibrate=False,
    )
    assert output.is_file()
    return json.loads(output.read_text(encoding="utf-8"))


def test_merge_preserves_parallel_source_strokes_and_collinear_neighbor(tmp_path: Path):
    image_value = os.environ.get(_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_IMAGE_ENV} to run the approved ALMA/HAER ROI benchmark")
    image_path = Path(image_value)
    assert image_path.is_file(), f"{_IMAGE_ENV} does not point to a file"
    assert hashlib.sha256(image_path.read_bytes()).hexdigest() == _ROI_SHA256

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    assert image is not None and image.shape == (1317, 1816)

    baseline = _run(image_path, tmp_path / "baseline.json", merge_lines=False)
    candidate = _run(image_path, tmp_path / "merged.json", merge_lines=True)
    baseline_lines = _line_segments_px(baseline)
    candidate_lines = _line_segments_px(candidate)

    # The annotated horizontal profile/grid stroke at rows 226-228 survives
    # with at least 90% of the unmerged detector's source-pixel support.
    target_before = _source_pixel_coverage(image, baseline_lines, 226, 228)
    target_after = _source_pixel_coverage(image, candidate_lines, 226, 228)
    assert target_before[0] > 0 and target_after[1] == target_before[1]
    assert target_after[0] >= 0.90 * target_before[0], (target_before, target_after)

    # The adjacent source-supported collinear profile/grid stroke is retained.
    neighbor_before = _source_pixel_coverage(image, baseline_lines, 248, 253)
    neighbor_after = _source_pixel_coverage(image, candidate_lines, 248, 253)
    assert neighbor_before[0] > 0 and neighbor_after[1] == neighbor_before[1]
    assert neighbor_after[0] >= 0.90 * neighbor_before[0], (
        neighbor_before,
        neighbor_after,
    )
