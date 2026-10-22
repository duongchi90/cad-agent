"""PDF-level controls for full-circle versus chord-closed partial-arc evidence."""

import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import fitz
import numpy as np
import pytest

from primitive_ir_lib.run_pdf import (
    _drawing_may_erase_circle,
    _fit_full_line_circle_path,
    _page_circle_witnesses,
    _single_line_record_paths,
    _suspect_geometry,
    run_pdf,
)
import primitive_ir_lib.geometry_extraction as geometry_extraction
import primitive_ir_lib.run_image as run_image_module
from primitive_ir_lib.geometry_extraction import RawCircle, RawGeometry
from primitive_ir_lib.run_image import (
    run as run_image,
)


def _draw_circular_beziers(
    page: fitz.Page, center: fitz.Point, radius: float, end_degrees: float
) -> None:
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


def _circle_primitives(page_ir: Path) -> list[dict]:
    payload = json.loads(page_ir.read_text(encoding="utf-8"))
    return [primitive for primitive in payload["primitives"] if primitive["type"] == "circle"]


def _has_circle_near(
    circles: list[dict],
    center: tuple[float, float],
    radius: float,
    *,
    center_tolerance: float = 8.0,
    radius_tolerance: float = 8.0,
) -> bool:
    return any(
        math.hypot(
            circle["geometry"]["center"]["x"] - center[0],
            circle["geometry"]["center"]["y"] - center[1],
        )
        <= center_tolerance
        and abs(circle["geometry"]["radius"] - radius) <= radius_tolerance
        for circle in circles
    )


def _rectangular_clip(rect: fitz.Rect, *, level: int = 0) -> dict:
    corners = [
        fitz.Point(rect.x0, rect.y0),
        fitz.Point(rect.x1, rect.y0),
        fitz.Point(rect.x1, rect.y1),
        fitz.Point(rect.x0, rect.y1),
    ]
    return {
        "type": "clip",
        "level": level,
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


def test_later_remote_stroke_only_quad_frame_preserves_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(10, 10),
            fitz.Point(590, 10),
            fitz.Point(10, 590),
            fitz.Point(590, 590),
        ),
        color=(0.05, 0.05, 0.05),
        width=2.0,
    )
    drawings = page.get_drawings(extended=True)
    drawings[-1]["items"].append(("l", fitz.Point(20, 20), fitz.Point(30, 30)))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert len(witnesses) == 1, "remote quad edges must not occlude a circle by their bbox alone"
    assert suspect_regions == []


def test_later_crossing_stroke_only_quad_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(100, 100),
            fitz.Point(500, 100),
            fitz.Point(100, 500),
            fitz.Point(500, 500),
        ),
        color=(0.05, 0.05, 0.05),
        width=2.0,
    )

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_malformed_nonfinite_quad_stays_fail_closed() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    invalid_point = SimpleNamespace(x=math.nan, y=10.0)
    valid_point = SimpleNamespace(x=20.0, y=20.0)
    invalid_quad = SimpleNamespace(
        ul=invalid_point,
        ur=valid_point,
        lr=SimpleNamespace(x=30.0, y=30.0),
        ll=SimpleNamespace(x=10.0, y=30.0),
    )
    drawings.append(
        {
            "type": "s",
            "items": [("qu", invalid_quad)],
            "rect": fitz.Rect(10, 10, 30, 30),
            "color": (0.05, 0.05, 0.05),
            "fill": None,
            "width": 2.0,
            "stroke_opacity": 1.0,
        }
    )

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_later_filled_quad_covering_circle_invalidates_full_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_quad(
        fitz.Quad(
            fitz.Point(20, 20),
            fitz.Point(580, 20),
            fitz.Point(20, 580),
            fitz.Point(580, 580),
        ),
        color=None,
        fill=(1.0, 1.0, 1.0),
    )

    _, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert witnesses == []
    assert suspect_regions


def test_filled_disconnected_subpath_closes_before_next_subpath() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = (300.0, 300.0)
    radius = 100.0

    # The first open fill subpath is implicitly closed by PDF fill semantics.
    # Its closing edge crosses the circle, while its two explicit edges stay
    # outside. A distant second subpath forces the item parser to flush it.
    shape = page.new_shape()
    shape.draw_polyline(
        [fitz.Point(200, 399.99), fitz.Point(300, 500), fitz.Point(400, 399.99)]
    )
    shape.draw_polyline(
        [fitz.Point(10, 10), fitz.Point(20, 10), fitz.Point(20, 20), fitz.Point(10, 20)]
    )
    shape.finish(color=None, fill=(0.75, 0.75, 0.75), closePath=False)
    shape.commit()

    drawing = next(d for d in page.get_drawings(extended=True) if d["type"] == "f")
    suspect = _suspect_geometry(drawing, 1.0, page.rotation_matrix)

    assert len(suspect["fill_polygons"]) == 2
    assert geometry_extraction._suspect_region_intersects_circle(
        suspect, center[0], center[1], radius, tolerance=2.0
    ), "every disconnected fill subpath must include its implicit closing edge"
    document.close()


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


def test_later_wide_same_color_crossing_stroke_invalidates_circle_witness(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "wide-same-color-crossing-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    page.draw_circle(center, 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    page.draw_line(
        (0, 300),
        (600, 300),
        color=(0.05, 0.05, 0.05),
        width=100.0,
    )
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(circles, (600, 600), 425), (
        "a later same-color stroke that covers a material part of the circle perimeter "
        "must invalidate the full-circle witness"
    )


def test_run_pdf_uses_only_later_images_as_circle_occluders(tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-paint-order.pdf"
    output_dir = tmp_path / "out"
    background = np.full((600, 600, 3), 220, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", background)
    assert success
    document = fitz.open()

    image_before_circle = document.new_page(width=600, height=600)
    image_before_circle.insert_image(image_before_circle.rect, stream=encoded.tobytes())
    image_before_circle.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)

    image_after_circle = document.new_page(width=600, height=600)
    image_after_circle.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    image_after_circle.insert_image(image_after_circle.rect, stream=encoded.tobytes())

    document.save(pdf_path)
    document.close()
    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    before_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    after_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    assert _has_circle_near(before_circles, (600, 600), 425), (
        "a background image painted before a visible vector circle must not invalidate that witness"
    )
    assert not _has_circle_near(after_circles, (600, 600), 425), (
        "a later background image that erases the vector circle must invalidate its witness"
    )


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


def test_same_color_filled_wedge_invalidates_full_circle_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "same-color-filled-wedge.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    center = fitz.Point(300, 300)
    radius = 212.5
    dark = (0.05, 0.05, 0.05)
    page.draw_circle(center, radius, color=dark, width=1.5)

    start_angle = math.radians(-15.0)
    end_angle = math.radians(15.0)
    wedge = page.new_shape()
    wedge.draw_polyline(
        [
            center,
            fitz.Point(
                center.x + radius * math.cos(start_angle),
                center.y + radius * math.sin(start_angle),
            ),
            fitz.Point(
                center.x + radius * math.cos(end_angle),
                center.y + radius * math.sin(end_angle),
            ),
        ]
    )
    wedge.finish(color=None, fill=dark, closePath=True)
    wedge.commit()
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert not _has_circle_near(circles, (600, 600), 425), (
        "a same-color opaque fill that masks part of the circumference must invalidate the full-circle witness"
    )


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
    for drawing in drawings:
        drawing["level"] = 1
    drawings.insert(0, _rectangular_clip(fitz.Rect(0, 0, 400, 600), level=0))

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert witnesses == []
    assert suspect_regions


def test_expired_clip_and_group_levels_do_not_invalidate_later_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_circle((300, 300), 212.5, color=(0.05, 0.05, 0.05), width=1.5)
    drawings = page.get_drawings(extended=True)
    drawings.insert(0, _rectangular_clip(fitz.Rect(0, 0, 100, 600), level=0))
    drawings.insert(1, {"type": "group", "level": 0, "rect": fitz.Rect(0, 0, 100, 600)})

    with patch.object(fitz.Page, "get_drawings", return_value=drawings):
        require_all_witnesses, witnesses, suspect_regions = _page_circle_witnesses(page, 1.0)
    document.close()

    assert require_all_witnesses is False
    assert len(witnesses) == 1
    assert suspect_regions == []


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
    assert mixed_raster_count >= 1, (
        "an unrelated local vector curve must not suppress a raster circle"
    )


def test_run_pdf_refines_circle_geometry_from_unique_pdf_witness(tmp_path: Path) -> None:
    pdf_path = tmp_path / "circle-witness-precision.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    center = fitz.Point(161.55, 401.59)
    page_height = page.rect.height
    radii = (45.2725, 17.01095)
    for radius in radii:
        page.draw_circle(center, radius, color=(0.05, 0.05, 0.05), width=0.75)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert len(circles) == 2, "each uniquely visible PDF circle must have one raster candidate"
    for radius in radii:
        closest = min(
            circles,
            key=lambda circle: abs(circle["geometry"]["radius"] * 0.5 - radius),
        )
        output_radius_pt = closest["geometry"]["radius"] * 0.5
        output_center_pt = (
            closest["geometry"]["center"]["x"] * 0.5,
            closest["geometry"]["center"]["y"] * 0.5,
        )
        expected_center_pt = (center.x, page_height - center.y)
        assert abs(output_radius_pt - radius) <= 0.05
        assert math.dist(output_center_pt, expected_center_pt) <= 0.05


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

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")

    assert _has_circle_near(baseline_circles, (600, 600), 425), (
        "baseline must find the source raster circle"
    )
    assert _has_circle_near(gated_circles, (600, 600), 425), (
        "an unrelated curve bound must not suppress that same untouched raster circle"
    )


def test_run_pdf_preserves_raster_circle_inside_mixed_rectangle_curve_bounds(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "raster-circle-inside-mixed-vector-bounds.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((1200, 1200, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (600, 600), 425, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # PyMuPDF returns this as one drawing with items ['re', 'c', 'l'];
    # every actual vector path remains far from the raster circle perimeter.
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(40, 40, 560, 560))
    shape.draw_bezier((25, 30), (35, 5), (50, 55), (65, 30))
    shape.finish(color=(0.05, 0.05, 0.05), width=1.0)
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

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(baseline_circles, (600, 600), 425), (
        "baseline must find the source raster circle"
    )
    assert _has_circle_near(gated_circles, (600, 600), 425), (
        "an unrelated rectangle item must not replace supported path geometry with its full bounds"
    )


def test_run_pdf_keeps_local_raster_circle_on_rotated_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "rotated-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (150, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    _draw_circular_beziers(page, fitz.Point(450, 400), 40, 300.0)
    page.set_rotation(90)
    rendered_center = fitz.Point(150, 200) * page.rotation_matrix
    expected_center = (rendered_center.x, page.rect.height - rendered_center.y)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, expected_center, 70), (
        "a local unsupported page rotation must not suppress an independent raster circle"
    )


def test_run_pdf_keeps_local_raster_circle_on_cropped_rotated_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "cropped-rotated-independent-raster-circle.pdf"
    output_dir = tmp_path / "out"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    _draw_circular_beziers(page, fitz.Point(400, 400), 40, 300.0)
    page.set_cropbox(fitz.Rect(100, 100, 500, 500))
    page.set_rotation(90)
    rendered_center = fitz.Point(100, 100) * page.rotation_matrix
    expected_center = (rendered_center.x, page.rect.height - rendered_center.y)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, expected_center, 70), (
        "crop and rotation must keep the suspect arc local to its transformed rendered position"
    )


def test_run_pdf_rejects_raster_circle_erased_by_wide_vector_arc(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-erased-by-wide-vector-arc.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    document = fitz.open()
    page = document.new_page(width=600, height=600)

    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success
    page.insert_image(page.rect, stream=encoded.tobytes())

    # At x=276 the centerline misses the detected circumference by about
    # 8 px, but the 18 px background-colored stroke erases part of the arc.
    shape = page.new_shape()
    shape.draw_bezier((276, 120), (276, 160), (276, 240), (276, 280))
    shape.finish(color=(220 / 255, 220 / 255, 220 / 255), width=18.0)
    shape.commit()

    page.get_pixmap(dpi=72, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    from primitive_ir_lib.run_image import run as run_image

    run_image(
        str(image_path),
        str(baseline_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(baseline_circles, (200, 400), 70), (
        "baseline must find the source raster circle"
    )
    assert not _has_circle_near(gated_circles, (200, 400), 70), (
        "a wide background-colored vector stroke must not leave the erased raster circle as a full circle"
    )


def test_run_pdf_rejects_circle_whose_perimeter_is_inside_a_filled_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raster-circle-erased-by-filled-path.pdf"
    image_path = tmp_path / "same-page-render.png"
    baseline_dir = tmp_path / "baseline"
    gated_dir = tmp_path / "gated"
    source_image = np.full((600, 600, 3), 220, dtype=np.uint8)
    center = (200.0, 200.0)
    cv2.circle(source_image, (200, 200), 70, (20, 20, 20), 4, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", source_image)
    assert success

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.insert_image(page.rect, stream=encoded.tobytes())
    page.draw_circle(center, 70, color=(0.05, 0.05, 0.05), width=1.0)
    sector_angles = [math.radians(degree) for degree in range(31)]
    points = [
        fitz.Point(center[0] + 80.0 * math.cos(angle), center[1] + 80.0 * math.sin(angle))
        for angle in sector_angles
    ]
    points.extend(
        fitz.Point(center[0] + 60.0 * math.cos(angle), center[1] + 60.0 * math.sin(angle))
        for angle in reversed(sector_angles)
    )
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(color=None, fill=(220 / 255, 220 / 255, 220 / 255), closePath=True)
    shape.commit()
    page.get_pixmap(dpi=72, alpha=False).save(image_path)
    document.save(pdf_path)
    document.close()

    from primitive_ir_lib.run_image import run as run_image

    run_image(
        str(image_path),
        str(baseline_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    run_pdf(pdf_path, gated_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    baseline_circles = _circle_primitives(baseline_dir / "primitive_ir.json")
    gated_circles = _circle_primitives(gated_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(baseline_circles, (200, 400), 70), (
        "baseline must find the source raster circle"
    )
    assert not _has_circle_near(gated_circles, (200, 400), 70), (
        "filled vector paint over the circle perimeter must not leave a full-circle candidate"
    )


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

    assert hidden_witness_count == 0, (
        "white-on-white vector geometry cannot witness a visible circle"
    )
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

    assert erased_witness_count == 0, (
        "later white paint must invalidate a dark circle witness on gray paper"
    )
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

    assert len(circles) == 1, (
        "keep the independent raster circle but reject the erased vector circle"
    )
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
        primitive for primitive in segmented_payload["primitives"] if primitive["type"] == "circle"
    ]
    straight_line_circles = [
        primitive for primitive in straight_payload["primitives"] if primitive["type"] == "circle"
    ]

    assert len(segmented_circles) == 1, (
        "reject the segmented vector arc but retain its independent raster circle"
    )
    segmented_center = segmented_circles[0]["geometry"]["center"]
    assert math.isclose(segmented_center["x"], 950, abs_tol=3)
    assert math.isclose(segmented_center["y"], 250, abs_tol=3)
    assert len(straight_line_circles) == 1, (
        "ordinary straight drafting linework must not suppress a raster circle"
    )


def test_run_pdf_rejects_split_path_partial_arc_and_chord(tmp_path: Path) -> None:
    pdf_path = tmp_path / "split-path-segmented-arc-and-controls.pdf"
    output_dir = tmp_path / "out"
    page_size = 400

    def add_partial_arc_and_chord(
        page: fitz.Page,
        center: fitz.Point,
        radius: float,
        *,
        fragment_count: int = 1,
    ) -> None:
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(degree)),
                center.y + radius * math.sin(math.radians(degree)),
            )
            for degree in range(356)
        ]
        segments = list(zip(points, points[1:]))
        for fragment_index in range(fragment_count):
            start_index = round(fragment_index * len(segments) / fragment_count)
            end_index = round((fragment_index + 1) * len(segments) / fragment_count)
            arc = page.new_shape()
            for start, end in segments[start_index:end_index]:
                arc.draw_line(start, end)
            arc.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
            arc.commit()
        chord = page.new_shape()
        chord.draw_line(points[-1], points[0])
        chord.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
        chord.commit()

    document = fitz.open()
    split_page = document.new_page(width=page_size, height=page_size)
    add_partial_arc_and_chord(split_page, fitz.Point(200, 200), 70)

    microfragment_page = document.new_page(width=page_size, height=page_size)
    add_partial_arc_and_chord(
        microfragment_page,
        fitz.Point(200, 200),
        70,
        fragment_count=30,
    )

    circle_page = document.new_page(width=page_size, height=page_size)
    circle_points = [
        fitz.Point(
            200 + 70 * math.cos(math.radians(360.0 * index / 64)),
            200 + 70 * math.sin(math.radians(360.0 * index / 64)),
        )
        for index in range(64)
    ]
    full_circle = circle_page.new_shape()
    for start, end in zip(circle_points, circle_points[1:] + circle_points[:1]):
        full_circle.draw_line(start, end)
    full_circle.finish(color=(0.05, 0.05, 0.05), width=1.5)
    full_circle.commit()

    raster_page = document.new_page(width=page_size, height=page_size)
    raster = np.full((page_size, page_size, 3), 220, dtype=np.uint8)
    raster_center = (80, 80)
    raster_radius = 25
    cv2.circle(raster, raster_center, raster_radius, (20, 20, 20), 2, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", raster)
    assert success
    raster_page.insert_image(raster_page.rect, stream=encoded.tobytes())
    add_partial_arc_and_chord(raster_page, fitz.Point(280, 280), 55)
    document.save(pdf_path)
    document.close()

    raster_document = fitz.open(pdf_path)
    split_render = tmp_path / "split-path.png"
    microfragment_render = tmp_path / "microfragment-path.png"
    raster_document[0].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False).save(
        split_render
    )
    raster_document[1].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False).save(
        microfragment_render
    )
    raster_document.close()
    pre_gate_ir = tmp_path / "pre-gate.json"
    run_image(str(split_render), str(pre_gate_ir), scale_mm_per_px=1.0)
    assert _has_circle_near(_circle_primitives(pre_gate_ir), (200, 200), 70), (
        "the red control must prove raster Hough actually proposes the unsupported circle"
    )
    microfragment_pre_gate_ir = tmp_path / "microfragment-pre-gate.json"
    run_image(str(microfragment_render), str(microfragment_pre_gate_ir), scale_mm_per_px=1.0)
    assert _has_circle_near(
        _circle_primitives(microfragment_pre_gate_ir), (200, 200), 70
    ), "the fragmented-path red control must prove Hough proposes the unsupported circle"

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    split_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    microfragment_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    full_circles = _circle_primitives(output_dir / "primitive_ir" / "page_03.json")
    raster_circles = _circle_primitives(output_dir / "primitive_ir" / "page_04.json")
    assert split_circles == [], (
        "separate vector paths for an arc and chord cannot witness a full circle"
    )
    assert microfragment_circles == [], (
        "many short open arc paths and a separate chord cannot bypass the full-circle witness gate"
    )
    assert _has_circle_near(full_circles, (200, 200), 70), "a complete source circle must survive"
    assert len(raster_circles) == 1, (
        "the independent raster circle must survive the uncertain vector paths"
    )
    raster_circle_center = raster_circles[0]["geometry"]["center"]
    assert math.isclose(raster_circle_center["x"], raster_center[0], abs_tol=3)
    assert math.isclose(raster_circle_center["y"], page_size - raster_center[1], abs_tol=3)


def test_run_pdf_keeps_source_supported_line_segmented_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "line-segmented-source-circle.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    shape = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        shape.draw_line(start, end)
    shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    shape.commit()
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert _has_circle_near(circles, (120, 120), 42.5), (
        "a complete, source-visible circle drawn as connected line segments must survive source gating"
    )


def test_run_pdf_keeps_consecutive_single_line_concentric_cycles_when_raster_aliases(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "separate-line-record-concentric-circles.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radii = (20.0, 20.25, 21.0)
    for radius in radii:
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(360.0 * index / 32)),
                center.y + radius * math.sin(math.radians(360.0 * index / 32)),
            )
            for index in range(32)
        ]
        for start, end in zip(points, points[1:] + points[:1]):
            page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.6)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    actual_radii = sorted(circle["geometry"]["radius"] for circle in circles)
    assert len(actual_radii) == 3, (
        "each distinct, closed source cycle must survive even when raster Hough candidates alias"
    )
    assert np.allclose(actual_radii, sorted(radius * 2.0 for radius in radii), atol=0.2), (
        f"source vector radii should remain distinct and exact; got {actual_radii}"
    )


def test_geometry_owner_materializes_source_cycles_when_raster_candidates_alias(
    monkeypatch,
) -> None:
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    cv2.circle(image, (100, 100), 21, (0, 0, 0), thickness=2)
    cv2.circle(image, (180, 180), 15, (0, 0, 0), thickness=2)
    aliased_raster_circle = RawCircle(
        id="aliased", center_px=(100.0, 100.0), radius_px=20.5,
        confidence=0.75, bbox_px=(79.5, 79.5, 120.5, 120.5),
    )
    independent_raster_circle = RawCircle(
        id="independent", center_px=(180.0, 180.0), radius_px=15.0,
        confidence=0.75, bbox_px=(165.0, 165.0, 195.0, 195.0),
    )
    monkeypatch.setattr(
        geometry_extraction,
        "extract_circles",
        lambda *_args, **_kwargs: [aliased_raster_circle, independent_raster_circle],
    )
    monkeypatch.setattr(geometry_extraction, "extract_lines", lambda *_args, **_kwargs: [])

    raw_geometry = geometry_extraction.extract_raw_geometry(
        image,
        preset="default",
        pdf_vector_circle_witnesses=[
            (100.0, 100.0, 20.0),
            (100.0, 100.0, 20.25),
            (100.0, 100.0, 21.0),
            (100.0, 100.0, 21.0),
            (100.0, 100.0, float("nan")),
        ],
    )

    assert sorted(circle.radius_px for circle in raw_geometry.circles) == [
        15.0, 20.0, 20.25, 21.0,
    ], "exact source cycles should survive raster aliasing, while duplicates collapse"
    assert raw_geometry.circles[0] is independent_raster_circle, (
        "an unrelated source-supported raster circle must remain intact"
    )


@pytest.mark.parametrize(
    ("witness", "max_radius", "rejection_reason"),
    [
        ((102.0, 100.0, 22.0), 20, "configured radius limit"),
        ((102.0, 100.0, 23.0), 200, "distributed source support"),
    ],
)
def test_rejected_vector_witness_does_not_suppress_supported_raster_circle(
    monkeypatch, witness, max_radius, rejection_reason,
) -> None:
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    cv2.circle(image, (100, 100), 20, (0, 0, 0), thickness=2)
    raster_circle = RawCircle(
        id="raster", center_px=(100.0, 100.0), radius_px=20.0,
        confidence=0.75, bbox_px=(80.0, 80.0, 120.0, 120.0),
    )
    monkeypatch.setattr(
        geometry_extraction, "extract_circles", lambda *_args, **_kwargs: [raster_circle]
    )
    monkeypatch.setattr(geometry_extraction, "extract_lines", lambda *_args, **_kwargs: [])

    raw_geometry = geometry_extraction.extract_raw_geometry(
        image,
        preset="default",
        max_radius=max_radius,
        pdf_vector_circle_witnesses=[witness],
    )

    assert raw_geometry.circles == [raster_circle], (
        f"a witness rejected by {rejection_reason} must not suppress an "
        "independently source-supported raster circle"
    )


def test_run_image_only_forwards_pdf_circle_evidence_without_mutating_geometry(
    tmp_path: Path, monkeypatch,
) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"test image bytes")
    image = np.full((30, 40, 3), 255, dtype=np.uint8)
    raster_circle = RawCircle(
        id="raster", center_px=(5.0, 5.0), radius_px=3.0,
        confidence=0.75, bbox_px=(2.0, 2.0, 8.0, 8.0),
    )
    raw_geometry = RawGeometry(circles=[raster_circle])
    captured: dict = {}

    monkeypatch.setattr(run_image_module.cv2, "imread", lambda _path: image)

    def extract(_image, **kwargs):
        captured["extract_kwargs"] = kwargs
        return raw_geometry

    def build_document(**kwargs):
        captured["raw_circles"] = kwargs["raw_circles"]
        return SimpleNamespace(cross_validations=[])

    monkeypatch.setattr(run_image_module, "extract_raw_geometry", extract)
    monkeypatch.setattr(run_image_module, "build_document", build_document)
    monkeypatch.setattr(run_image_module, "cross_validate", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(run_image_module, "save_document", lambda *_args, **_kwargs: None)

    witnesses = [(25.0, 20.0, 8.0)]
    suspect_regions = [(1.0, 2.0, 3.0, 4.0)]
    run_image(
        image_path=str(image_path),
        output_path=str(tmp_path / "out" / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        pdf_vector_circle_witnesses=witnesses,
        pdf_vector_circle_suspect_regions=suspect_regions,
        require_pdf_vector_circle_witness=True,
    )

    assert captured["extract_kwargs"] == {
        "preset": "real_scan_tuned_v1",
        "pdf_vector_circle_witnesses": witnesses,
        "pdf_vector_circle_suspect_regions": suspect_regions,
        "require_pdf_vector_circle_witness": True,
    }
    assert captured["raw_circles"] == [raster_circle]
    assert captured["raw_circles"][0] is raster_circle


def test_run_pdf_deduplicates_duplicate_single_line_circle_paint(tmp_path: Path) -> None:
    pdf_path = tmp_path / "duplicate-single-line-circle-paint.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for _ in range(2):
        for start, end in zip(points, points[1:] + points[:1]):
            page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.6)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert len(circles) == 1, "duplicate paint of one source cycle must not emit duplicate circles"
    assert math.isclose(circles[0]["geometry"]["radius"], radius * 2.0, abs_tol=0.2)


def test_run_pdf_does_not_promote_single_line_record_arc_plus_chord(tmp_path: Path) -> None:
    pdf_path = tmp_path / "single-line-record-arc-plus-chord.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 30.0
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(355.0 * index / 35)),
            center.y + radius * math.sin(math.radians(355.0 * index / 35)),
        )
        for index in range(36)
    ]
    for start, end in zip(points, points[1:]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line(points[-1], points[0], color=(0.05, 0.05, 0.05), width=0.8)
    document.save(pdf_path)
    document.close()

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    assert circles == [], "a separately recorded closing chord must not turn a partial arc into a circle"


def test_later_background_line_invalidates_single_record_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    center = fitz.Point(60, 60)
    radius = 30.0
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(points, points[1:] + points[:1]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line((30, 60), (90, 60), color=(0.75, 0.75, 0.75), width=2.0)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "later background-colored paint crossing the perimeter invalidates the cycle"
    assert suspects, "an occluded vector circle remains a bounded suspect region"


def test_same_color_later_stroke_requires_width_and_intersection_evidence() -> None:
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    center = fitz.Point(300, 300)
    radius = 212.5
    circle_width = 1.5
    circle_color = (0.05, 0.05, 0.05)
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 128)),
            center.y + radius * math.sin(math.radians(360.0 * index / 128)),
        )
        for index in range(128)
    ]
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()

    # Equal-width same-color drafting linework is the thin positive control.
    page.draw_line(
        (30, center.y), (570, center.y), color=circle_color, width=circle_width,
    )
    _, thin_witnesses, thin_suspects = _page_circle_witnesses(page, 1.0)
    assert len(thin_witnesses) == 1
    assert thin_suspects == []
    document.close()

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()
    # This width is 0.245 * radius: it fell below the old 0.25 * radius
    # exemption while still being far wider than the circle's source stroke.
    page.draw_line(
        (30, center.y), (570, center.y), color=circle_color, width=52.0625,
    )
    _, crossing_witnesses, crossing_suspects = _page_circle_witnesses(page, 1.0)
    document.close()

    assert crossing_witnesses == [], (
        "a wider same-color stroke crossing the source contour must not be "
        "skipped solely because it is below a radius-based threshold"
    )
    assert crossing_suspects, "a contour with uncertain occlusion remains a bounded suspect"

    document = fitz.open()
    page = document.new_page(width=600, height=600)
    page.draw_rect(page.rect, color=None, fill=(0.75, 0.75, 0.75))
    circle = page.new_shape()
    for start, end in zip(points, points[1:] + points[:1]):
        circle.draw_line(start, end)
    circle.finish(color=circle_color, width=circle_width)
    circle.commit()
    # Width alone cannot invalidate a witness when the line misses its perimeter.
    page.draw_line((30, 30), (570, 30), color=circle_color, width=52.0625)
    _, distant_witnesses, distant_suspects = _page_circle_witnesses(page, 1.0)
    document.close()

    assert len(distant_witnesses) == 1
    assert distant_suspects == []


def test_same_color_stroke_width_fails_closed_except_explicit_hairline() -> None:
    hairline = {"type": "s", "color": (0.05, 0.05, 0.05), "width": 0.0}
    assert not _drawing_may_erase_circle(hairline, hairline["color"], 0.0)

    for width in (None, "invalid", float("nan"), float("inf"), -1.0, 10**1000):
        drawing = {"type": "s", "color": (0.05, 0.05, 0.05), "width": width}
        assert _drawing_may_erase_circle(drawing, drawing["color"], 1.5)

    missing_width = {"type": "s", "color": (0.05, 0.05, 0.05)}
    assert _drawing_may_erase_circle(missing_width, missing_width["color"], 1.5)


def test_single_line_cycle_with_parser_gap_is_not_a_circle_witness() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(points, points[1:]):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
    page.draw_line(points[-1], fitz.Point(points[0].x + 0.05, points[0].y), color=(0.05, 0.05, 0.05), width=0.8)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "a path gap beyond parser endpoint precision is not a closed contour"
    assert suspects, "a nearly closed curved source path must not silently disappear"


def test_single_line_hairline_records_are_eligible_for_source_reconstruction() -> None:
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    records = [
        {
            "type": "s",
            "fill": None,
            "color": (0.05, 0.05, 0.05),
            "width": 0.0,
            "dashes": "[] 0",
            "stroke_opacity": 1.0,
            "items": [("l", start, end)],
            "seqno": index,
        }
        for index, (start, end) in enumerate(zip(points, points[1:] + points[:1]))
    ]

    paths = _single_line_record_paths(records)

    assert len(paths) == 1
    assert paths[0][3] is True
    assert math.isclose(paths[0][2]["rect"].width, radius * 2.0, abs_tol=0.2)
    fitted = _fit_full_line_circle_path(paths[0][2], np.ones(3, dtype=np.float64))
    assert fitted is not None, "zero-width PDF hairlines remain visible stroke geometry"
    assert math.isclose(fitted[2], radius, abs_tol=0.1)


def test_interleaved_single_line_branch_breaks_contour_reconstruction() -> None:
    document = fitz.open()
    page = document.new_page(width=120, height=120)
    center = fitz.Point(60, 60)
    radius = 21.25
    points = [
        fitz.Point(
            center.x + radius * math.cos(math.radians(360.0 * index / 32)),
            center.y + radius * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1])):
        page.draw_line(start, end, color=(0.05, 0.05, 0.05), width=0.8)
        if index == 15:
            page.draw_line(center, end, color=(0.05, 0.05, 0.05), width=0.8)

    _, witnesses, suspects = _page_circle_witnesses(page, 2.0)
    document.close()

    assert witnesses == [], "a branch inserted into the source record sequence is ambiguous"
    assert suspects, "the broken curved record sequence remains a bounded suspect"


def test_line_segmented_circle_witness_requires_known_contrast() -> None:
    document = fitz.open()
    document.new_page(width=120, height=120)
    document.new_page(width=120, height=120)
    white_page = document[0]
    gray_page = document[1]
    gray_page.draw_rect(gray_page.rect, color=None, fill=(0.75, 0.75, 0.75))
    for page, color in ((white_page, (1.0, 1.0, 1.0)), (gray_page, (0.05, 0.05, 0.05))):
        center = fitz.Point(60, 60)
        radius = 21.25
        points = [
            fitz.Point(
                center.x + radius * math.cos(math.radians(360.0 * index / 32)),
                center.y + radius * math.sin(math.radians(360.0 * index / 32)),
            )
            for index in range(32)
        ]
        shape = page.new_shape()
        for start, end in zip(points, points[1:] + points[:1]):
            shape.draw_line(start, end)
        shape.finish(color=color, width=1.5)
        shape.commit()

    _, white_witnesses, white_suspects = _page_circle_witnesses(white_page, 2.0)
    _, gray_witnesses, gray_suspects = _page_circle_witnesses(gray_page, 2.0)
    document.close()

    assert white_witnesses == [], (
        "a line path matching white paper must not witness a visible circle"
    )
    assert white_suspects, "an invisible line contour remains a suspect source region"
    assert len(gray_witnesses) == 1, (
        "a dark line circle may witness against a known gray paper background"
    )
    assert gray_suspects == []


def test_run_pdf_rejects_line_segmented_polygon_and_ellipse_as_circle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "line-segmented-polygon-and-ellipse.pdf"
    output_dir = tmp_path / "out"
    document = fitz.open()

    polygon = document.new_page(width=120, height=120)
    polygon_center = fitz.Point(60, 60)
    polygon_radius = 21.25
    polygon_points = [
        fitz.Point(
            polygon_center.x + polygon_radius * math.cos(math.radians(360.0 * index / 16)),
            polygon_center.y + polygon_radius * math.sin(math.radians(360.0 * index / 16)),
        )
        for index in range(16)
    ]
    polygon_shape = polygon.new_shape()
    for start, end in zip(polygon_points, polygon_points[1:] + polygon_points[:1]):
        polygon_shape.draw_line(start, end)
    polygon_shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    polygon_shape.commit()

    ellipse = document.new_page(width=120, height=120)
    ellipse_center = fitz.Point(60, 60)
    ellipse_shape = ellipse.new_shape()
    ellipse_points = [
        fitz.Point(
            ellipse_center.x + 30 * math.cos(math.radians(360.0 * index / 32)),
            ellipse_center.y + 15 * math.sin(math.radians(360.0 * index / 32)),
        )
        for index in range(32)
    ]
    for start, end in zip(ellipse_points, ellipse_points[1:] + ellipse_points[:1]):
        ellipse_shape.draw_line(start, end)
    ellipse_shape.finish(color=(0.05, 0.05, 0.05), width=1.5)
    ellipse_shape.commit()

    document.save(pdf_path)
    document.close()
    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=144, preset="real_scan_tuned_v1")

    polygon_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    ellipse_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    assert not _has_circle_near(polygon_circles, (120, 120), 42.5), (
        "a closed polygon must not be promoted to a source circle"
    )
    assert not _has_circle_near(ellipse_circles, (120, 120), 45), (
        "a line-segmented ellipse must remain distinct from a source circle"
    )


def test_run_pdf_rejects_open_line_ellipse_without_suppressing_crossed_raster_circle(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "open-line-ellipse-and-crossed-raster-circle.pdf"
    output_dir = tmp_path / "out"
    pre_gate_dir = tmp_path / "pre-gate"
    document = fitz.open()

    ellipse_page = document.new_page(width=400, height=400)
    ellipse_center = fitz.Point(200, 200)
    ellipse_points = [
        fitz.Point(
            ellipse_center.x + 70 * math.cos(math.radians(degree)),
            ellipse_center.y + 62 * math.sin(math.radians(degree)),
        )
        for degree in range(0, 356, 5)
    ]
    ellipse_shape = ellipse_page.new_shape()
    for start, end in zip(ellipse_points, ellipse_points[1:]):
        ellipse_shape.draw_line(start, end)
    ellipse_shape.finish(color=(0.05, 0.05, 0.05), width=1.5, closePath=False)
    ellipse_shape.commit()

    raster_page = document.new_page(width=400, height=400)
    raster = np.full((400, 400, 3), 220, dtype=np.uint8)
    cv2.circle(raster, (200, 200), 65, (20, 20, 20), 3, lineType=cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", raster)
    assert success
    raster_page.insert_image(raster_page.rect, stream=encoded.tobytes())
    raster_page.draw_line((130, 200), (270, 200), color=(0.05, 0.05, 0.05), width=1.5)

    document.save(pdf_path)
    document.close()

    rendered = fitz.open(pdf_path)
    ellipse_render = tmp_path / "open-ellipse.png"
    rendered[0].get_pixmap(dpi=72, alpha=False).save(ellipse_render)
    rendered.close()
    run_image(
        str(ellipse_render),
        str(pre_gate_dir / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
    )
    pre_gate_circles = _circle_primitives(pre_gate_dir / "primitive_ir.json")
    ellipse_candidates = [
        circle
        for circle in pre_gate_circles
        if _has_circle_near(
            [circle], (200, 200), 66, center_tolerance=16, radius_tolerance=14
        )
    ]
    assert ellipse_candidates, (
        "image-only extraction must prove Hough proposes the ellipse-induced circle candidate"
    )

    run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="real_scan_tuned_v1")

    ellipse_circles = _circle_primitives(output_dir / "primitive_ir" / "page_01.json")
    crossed_raster_circles = _circle_primitives(output_dir / "primitive_ir" / "page_02.json")
    for candidate in ellipse_candidates:
        candidate_center = candidate["geometry"]["center"]
        candidate_radius = candidate["geometry"]["radius"]
        assert not any(
            math.hypot(
                circle["geometry"]["center"]["x"] - candidate_center["x"],
                circle["geometry"]["center"]["y"] - candidate_center["y"],
            )
            <= 2.0
            and abs(circle["geometry"]["radius"] - candidate_radius) <= 2.0
            for circle in ellipse_circles
        ), "the same open-ellipse Hough candidate must be rejected by PDF source gating"
    assert _has_circle_near(crossed_raster_circles, (200, 200), 65), (
        "a straight drafting line crossing an independent raster circle must not suppress it"
    )
