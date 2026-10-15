"""Real-source regression for the motor-mount-top main-view circle."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import RawCircle, extract_raw_geometry
from primitive_ir_lib.run_image import run
from primitive_ir_lib.text_extraction import RawText


_IMAGE_ENV = "CAD_AGENT_CASE05_MOTOR_MOUNT_TOP_IMAGE"
_IMAGE_SHA256 = "0e55e38823e4037aab03323c7988d33784ed1e345a5bc83827aeea2eec6394bf"
_EXPECTED_CENTER_PX = (498.791, 820.279)
_EXPECTED_RADIUS_PX = 312.548
_MATCH_TOLERANCE_PX = 5.0


@pytest.mark.real_data
def test_public_image_caller_promotes_engineering_circle_not_title_glyphs(tmp_path: Path) -> None:
    image_value = os.environ.get(_IMAGE_ENV)
    if not image_value:
        pytest.skip(f"set {_IMAGE_ENV} to run the frozen CASE05 real-data regression")

    image_path = Path(image_value)
    assert image_path.is_file(), f"{_IMAGE_ENV} does not point to a file: {image_path}"
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == _IMAGE_SHA256

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape == (1263, 1787, 3)

    raw_geometry = extract_raw_geometry(image, preset="real_scan_tuned_v1")
    matching_raw_circles = [
        circle
        for circle in raw_geometry.circles
        if np.hypot(
            circle.center_px[0] - _EXPECTED_CENTER_PX[0],
            circle.center_px[1] - _EXPECTED_CENTER_PX[1],
        ) <= _MATCH_TOLERANCE_PX
        and abs(circle.radius_px - _EXPECTED_RADIUS_PX) <= _MATCH_TOLERANCE_PX
    ]

    assert matching_raw_circles, (
        "the source-supported engineering circle must remain available as raw evidence "
        f"(center={_EXPECTED_CENTER_PX}, radius={_EXPECTED_RADIUS_PX}px); "
        f"detected {len(raw_geometry.circles)} circles"
    )
    assert len(raw_geometry.circles) == 4

    output_path = tmp_path / "primitive-ir.json"
    run(
        image_path=str(image_path),
        output_path=str(output_path),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
        auto_ocr_roi=True,
        ocr_lang="eng",
    )
    payload = __import__("json").loads(output_path.read_text(encoding="utf-8"))
    circles = [item for item in payload["primitives"] if item["type"] == "circle"]
    assert len(circles) == 1, (
        "the source page has one engineering circle; confirmed round text glyphs "
        f"must not be promoted (Primitive IR contains {len(circles)} circles)"
    )


def test_circle_promotion_distinguishes_engineering_glyph_and_unresolved_roles() -> None:
    from primitive_ir_lib.run_image import _circles_for_assembly

    engineering = RawCircle("engineering", (100.0, 100.0), 25.0, 0.9, (75.0, 75.0, 125.0, 125.0))
    glyph = RawCircle("glyph", (20.0, 20.0), 5.0, 0.9, (15.0, 15.0, 25.0, 25.0))
    unresolved_candidate = RawCircle("unresolved", (45.0, 20.0), 5.0, 0.9, (40.0, 15.0, 50.0, 25.0))
    text = RawText(
        id="recognized-word", content="motor", bbox_px=(10, 10, 60, 30),
        rotation_deg=0.0, confidence=0.95, source="text_tesseract",
    )

    promoted, confirmed_glyphs, unresolved_circles = _circles_for_assembly(
        [engineering, glyph, unresolved_candidate],
        [text],
        {"recognized-word": [("o", (15, 15, 25, 25))]},
    )

    assert [item.id for item in promoted] == ["engineering"]
    assert [item.id for item in confirmed_glyphs] == ["glyph"]
    assert [item.id for item in unresolved_circles] == ["unresolved"]
