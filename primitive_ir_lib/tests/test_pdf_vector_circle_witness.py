"""PDF-level controls for full-circle versus chord-closed partial-arc evidence."""

import json
import math
from pathlib import Path

import cv2
import fitz
import numpy as np

from primitive_ir_lib.run_pdf import _page_circle_witnesses, run_pdf


def _draw_circular_beziers(page: fitz.Page, center: fitz.Point, radius: float, end_degrees: float) -> None:
    shape = page.new_shape()
    boundaries = [0.0, 71.0, 142.0, 213.0, 284.0, end_degrees]
    for start_degrees, stop_degrees in zip(boundaries, boundaries[1:]):
        a0 = math.radians(start_degrees)
        a1 = math.radians(stop_degrees)
        delta = a1 - a0
        handle = (4.0 / 3.0) * math.tan(delta / 4.0) * radius
        p0 = fitz.Point(center.x + radius * math.cos(a0), center.y + radius * math.sin(a0))
        p3 = fitz.Point(center.x + radius * math.cos(a1), center.y + radius * math.sin(a1))
        tangent0 = fitz.Point(-math.sin(a0), math.cos(a0))
        tangent1 = fitz.Point(-math.sin(a1), math.cos(a1))
        p1 = fitz.Point(p0.x + handle * tangent0.x, p0.y + handle * tangent0.y)
        p2 = fitz.Point(p3.x - handle * tangent1.x, p3.y - handle * tangent1.y)
        shape.draw_bezier(p0, p1, p2, p3)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=True)
    shape.commit()


def _circle_primitive_count(page_ir: Path) -> int:
    payload = json.loads(page_ir.read_text(encoding="utf-8"))
    return sum(primitive["type"] == "circle" for primitive in payload["primitives"])


def test_later_crossing_line_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    radius = 212.5
    page.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)

    require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert witnesses == []
    assert suspect_regions


def test_run_pdf_does_not_promote_chord_closed_partial_arc_to_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "circle-controls.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    center = fitz.Point(300, 300)
    radius = 212.5

    full_circle = document.new_page(width=600, height=600)
    full_circle.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=1.5)
    full_circle.draw_circle(center, 170.0, color=(0.05, 0.05, 0.05), width=1.5)

    partial = document.new_page(width=600, height=600)
    _draw_circular_beziers(partial, center, radius, 355.0)

    ellipse = document.new_page(width=600, height=600)
    ellipse.draw_oval(fitz.Rect(100, 115, 500, 485), color=(0.05, 0.05, 0.05), width=1.5)

    mixed_raster = document.new_page(width=600, height=600)
    source_image = np.full((1200, 1200, 3), 210, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (30, 30, 30), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    mixed_raster.insert_image(mixed_raster.rect, stream=encoded.tobytes())
    curve = mixed_raster.new_shape()
    curve.draw_bezier((25, 30), (35, 5), (50, 55), (65, 30))
    curve.finish(color=(0.05, 0.05, 0.05), width=1.0)
    curve.commit()

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    full_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    chord_closed_arc_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")
    ellipse_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_03.json")
    mixed_raster_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_04.json")

    assert full_circle_count >= 2, "both complete concentric source circles must remain recognized"
    assert chord_closed_arc_count == 0, "a chord-closed 355-degree arc is not a full source circle"
    assert ellipse_circle_count == 0, "an ellipse must not be used as a full-circle witness"
    assert mixed_raster_count >= 1, "an unrelated local vector curve must not suppress a raster circle"
