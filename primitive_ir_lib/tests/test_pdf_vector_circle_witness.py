"""PDF-level controls for full-circle versus chord-closed partial-arc evidence."""

import json
import math
from pathlib import Path
from unittest.mock import patch

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


def _rectangular_clip(rect: fitz.Rect) -> dict:
    corners = [
        fitz.Point(rect.x0, rect.y0),
        fitz.Point(rect.x1, rect.y0),
        fitz.Point(rect.x1, rect.y1),
        fitz.Point(rect.x0, rect.y1),
    ]
    return {
        "type": "clip",
        "rect": None,
        "scissor": rect,
        "items": [
            ("l", corners[index], corners[(index + 1) % len(corners)])
            for index in range(len(corners))
        ],
    }


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


def test_later_black_crossing_line_preserves_full_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "black-crossing-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    page.draw_circle(center, 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(0.05, 0.05, 0.05), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    assert circle_count >= 1, "a visible full circle must survive a later non-erasing black stroke"


def test_background_colored_crossing_line_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    background = (0.75, 0.75, 0.75)
    page.draw_rect(page.rect, color=None, fill=background)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=background, width=1.5)

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_later_clip_context_does_not_invalidate_prior_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    drawings.insert(0, _rectangular_clip(fitz.Rect(-100, -100, 700, 700)))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert len(witnesses) == 1
    assert suspect_regions == []


def test_prior_clip_cutting_circle_does_not_supply_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    drawings.insert(0, _rectangular_clip(fitz.Rect(0, 0, 400, 600)))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
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


def test_run_pdf_keeps_raster_circle_enclosed_by_unrelated_curve_bounds(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-enclosed-by-vector-bounds.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((1200, 1200, 3), 210, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (30, 30, 30), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # The four cubic sides enclose the raster circle, but remain well outside
    # its circumference. Their PDF drawing rectangle alone overlaps it.
    shape = page.new_shape()
    corners = [fitz.Point(40, 40), fitz.Point(560, 40), fitz.Point(560, 560), fitz.Point(40, 560)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        delta = end - start
        shape.draw_bezier(start, start + delta / 3, start + delta * (2 / 3), end)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.0, closePath=True)
    shape.commit()

    page.get_pixmap(dpi=144, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    from primitive_ir_lib.run_image import run as run_image

    run_image(
        str(image_path),
        str(baseline_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    baseline_count = _circle_primitive_count(baseline_dir / "primitive_ir.json")
    gated_count = _circle_primitive_count(gated_dir / "primitive_ir" / "page_01.json")

    assert baseline_count >= 1, "the same rendered raster circle must be found without PDF source gating"
    assert gated_count >= 1, "an enclosing curve bound must not suppress an untouched raster circumference"


def test_run_pdf_rejects_white_on_white_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invisible-circle-witness.pdf"
    output_dir = tmp_path / "out"
    center = fitz.Point(300, 300)
    radius = 212.5
    black = (0.05, 0.05, 0.05)
    document = fitz.open()

    hidden_witness = document.new_page(width=600, height=600)
    hidden_witness.draw_circle(center, radius, color=(1.0, 1.0, 1.0), width=1.5)
    _draw_circular_beziers(hidden_witness, center, radius, 355.0)

    visible_circle = document.new_page(width=600, height=600)
    visible_circle.draw_circle(center, radius, color=black, width=1.5)

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    hidden_witness_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    visible_circle_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")

    assert hidden_witness_count == 0, "white-on-white vector geometry cannot witness a visible circle"
    assert visible_circle_count >= 1, "a visible source circle must remain recognized"


def test_run_pdf_rejects_circle_erased_by_white_paint_on_gray_paper(tmp_path: Path) -> None:
    pdf_path = tmp_path / "gray-paper-circle-erasure.pdf"
    output_dir = tmp_path / "out"
    center = fitz.Point(300, 300)
    radius = 212.5
    black = (0.05, 0.05, 0.05)
    gray = (0.75, 0.75, 0.75)
    document = fitz.open()

    erased_witness = document.new_page(width=600, height=600)
    erased_witness.draw_rect(erased_witness.rect, color=None, fill=gray)
    erased_witness.draw_circle(center, radius, color=black, width=1.5)
    erased_witness.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)

    gray_positive_control = document.new_page(width=600, height=600)
    gray_positive_control.draw_rect(gray_positive_control.rect, color=None, fill=gray)
    gray_positive_control.draw_circle(center, radius, color=black, width=1.5)

    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    erased_witness_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_01.json")
    gray_positive_count = _circle_primitive_count(output_dir / "primitive_ir" / "page_02.json")

    assert erased_witness_count == 0, "later white paint must invalidate a dark circle witness on gray paper"
    assert gray_positive_count >= 1, "a visible dark circle on gray paper must remain recognized"


def test_run_pdf_keeps_raster_circle_outside_uncertain_vector_bounds(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed-raster-and-erased-vector-circle.pdf"
    output_dir = tmp_path / "out"
    page_size = 1200
    raster_center = (950, 950)
    raster_radius = 130
    image = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    cv2.circle(image, raster_center, raster_radius, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", image)
    assert success

    document = fitz.open()
    page = document.new_page(width=page_size, height=page_size)
    page.insert_image(page.rect, stream=encoded.tobytes())
    page.draw_circle((300, 300), 150, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line((0, 300), (600, 300), color=(1.0, 1.0, 1.0), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    payload = json.loads((output_dir / "primitive_ir" / "page_01.json").read_text(encoding="utf-8"))
    circles = [primitive for primitive in payload["primitives"] if primitive["type"] == "circle"]

    assert len(circles) == 1, "keep the independent raster circle but reject the erased vector circle"
    center = circles[0]["geometry"]["center"]
    assert math.isclose(center["x"], 950, abs_tol=3)
    assert math.isclose(center["y"], 250, abs_tol=3)


def test_run_pdf_rejects_segmented_partial_arc_but_keeps_raster_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "segmented-vector-arc-and-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    page_size = 1200
    raster_center = (950, 950)
    raster_radius = 130
    image = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    cv2.circle(image, raster_center, raster_radius, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", image)
    assert success

    document = fitz.open()
    segmented_arc = document.new_page(width=page_size, height=page_size)
    segmented_arc.insert_image(segmented_arc.rect, stream=encoded.tobytes())
    shape = segmented_arc.new_shape()
    center = fitz.Point(300, 300)
    radius = 150
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(degree)),
            center.y + radius * math.sin(math.radians(degree)),
        )
        for degree in range(356)
    ]
    for start, end in zip(points, points[1:]):
        shape.draw_line(start, end)
    shape.draw_line(points[-1], points[0])
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    shape.commit()

    straight_line_control = document.new_page(width=page_size, height=page_size)
    straight_line_control.insert_image(straight_line_control.rect, stream=encoded.tobytes())
    straight_line_control.draw_line((40, 40), (700, 40), color=(0.05, 0.05, 0.05), width=1.5)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    segmented_payload = json.loads(
        (output_dir / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    straight_payload = json.loads(
        (output_dir / "primitive_ir" / "page_02.json").read_text(encoding="utf-8")
    )
    segmented_circles = [
        primitive for primitive in segmented_payload["primitives"]
        if primitive["type"] == "circle"
    ]
    straight_line_circles = [
        primitive for primitive in straight_payload["primitives"]
        if primitive["type"] == "circle"
    ]

    assert len(segmented_circles) == 1, "reject the segmented vector arc but retain its independent raster circle"
    segmented_center = segmented_circles[0]["geometry"]["center"]
    assert math.isclose(segmented_center["x"], 950, abs_tol=3)
    assert math.isclose(segmented_center["y"], 250, abs_tol=3)
    assert len(straight_line_circles) == 1, "ordinary straight drafting linework must not suppress a raster circle"
