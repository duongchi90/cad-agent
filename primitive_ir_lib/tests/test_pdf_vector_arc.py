"""Focused source-vector ARC admission tests for the existing PDF owner."""

from __future__ import annotations

import json
import hashlib
import copy
import math
import os
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import fitz
import cv2
import numpy as np
import pytest

import primitive_ir_lib.run_pdf as run_pdf_module
from primitive_ir_lib.run_pdf import _page_vector_arcs, _page_vector_line_witnesses, run_pdf
from primitive_ir_lib.geometry_extraction import RawArc, RawGeometry, RawLine
import primitive_ir_lib.run_image as run_image_module
from primitive_ir_lib.run_image import _line_is_explained_by_pdf_arc
from primitive_ir_lib.validator import validate_document
from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.reviewer import review_dxf
from semantic_ir_lib.io_utils import load_primitive_ir_document


def _write_quarter_arc_pdf(
    path: Path,
    *,
    radius: float = 45.0,
    ellipse_y_radius: float | None = None,
    close_path: bool = False,
    later_fill: bool = False,
    later_intersample_fill: bool = False,
    later_interior_fill: bool = False,
    later_image: bool = False,
    later_frame: bool = False,
    later_stroke: bool = False,
    later_curved_frame: bool = False,
    later_duplicate: bool = False,
    later_curved_stroke_intersample: bool = False,
    leading_tangent_line_length: float | None = None,
    occlude_leading_tangent_line: bool = False,
    occlude_leading_tangent_line_with_cubic_stroke: bool = False,
    occluding_cubic_line_cap: int = 0,
    arc_width: float = 1.5,
    disconnected: bool = False,
    start_deg: float = 0.0,
    sweep_deg: float = 90.0,
    page_rotation: int = 0,
    page_size_override: float | None = None,
    center_override: tuple[float, float] | None = None,
) -> None:
    document = fitz.open()
    y_radius = ellipse_y_radius or radius
    page_size = page_size_override or max(200.0, 2.0 * max(radius, y_radius) + 20.0)
    page = document.new_page(width=page_size, height=page_size)
    center = fitz.Point(*(center_override or (page_size / 2.0, page_size / 2.0)))
    start = math.radians(start_deg)
    end = math.radians(start_deg + sweep_deg)
    handle = (4.0 / 3.0) * math.tan(abs(end - start) / 4.0)
    direction = 1.0 if sweep_deg >= 0 else -1.0
    p0 = fitz.Point(center.x + radius * math.cos(start), center.y - y_radius * math.sin(start))
    p3 = fitz.Point(center.x + radius * math.cos(end), center.y - y_radius * math.sin(end))
    tangent_start = fitz.Point(-radius * math.sin(start) * direction, -y_radius * math.cos(start) * direction)
    tangent_end = fitz.Point(-radius * math.sin(end) * direction, -y_radius * math.cos(end) * direction)
    p1 = fitz.Point(p0.x + handle * tangent_start.x, p0.y + handle * tangent_start.y)
    p2 = fitz.Point(p3.x - handle * tangent_end.x, p3.y - handle * tangent_end.y)
    if leading_tangent_line_length is not None:
        midpoint = fitz.Point(
            0.125 * p0.x + 0.375 * p1.x + 0.375 * p2.x + 0.125 * p3.x,
            0.125 * p0.y + 0.375 * p1.y + 0.375 * p2.y + 0.125 * p3.y,
        )
        tangent = fitz.Point(
            0.75 * (p1.x - p0.x) + 1.5 * (p2.x - p1.x) + 0.75 * (p3.x - p2.x),
            0.75 * (p1.y - p0.y) + 1.5 * (p2.y - p1.y) + 0.75 * (p3.y - p2.y),
        )
        tangent /= math.hypot(tangent.x, tangent.y)
        half_length = leading_tangent_line_length / 2.0
        page.draw_line(
            midpoint - tangent * half_length,
            midpoint + tangent * half_length,
            color=(0, 0, 0),
            width=0.5,
            overlay=True,
        )
        if occlude_leading_tangent_line:
            cover_radius = half_length + 5.0
            page.draw_rect(
                fitz.Rect(
                    midpoint.x - cover_radius,
                    midpoint.y - cover_radius,
                    midpoint.x + cover_radius,
                    midpoint.y + cover_radius,
                ),
                color=None,
                fill=(1, 1, 1),
                overlay=True,
            )
        if occlude_leading_tangent_line_with_cubic_stroke:
            line_start = midpoint - tangent * half_length
            line_end = midpoint + tangent * half_length
            cover = page.new_shape()
            cover.draw_bezier(
                line_start,
                line_start + tangent * (leading_tangent_line_length / 3.0),
                line_end - tangent * (leading_tangent_line_length / 3.0),
                line_end,
            )
            cover.finish(
                color=(1, 1, 1),
                width=3.0,
                closePath=False,
                lineCap=occluding_cubic_line_cap,
            )
            cover.commit()
    shape = page.new_shape()
    shape.draw_bezier(p0, p1, p2, p3)
    if disconnected:
        gap_start = fitz.Point(center.x + radius * math.cos(math.radians(100)), center.y - radius * math.sin(math.radians(100)))
        gap_end = fitz.Point(center.x + radius * math.cos(math.radians(115)), center.y - radius * math.sin(math.radians(115)))
        shape.draw_bezier(gap_start, gap_start, gap_end, gap_end)
    shape.finish(color=(0, 0, 0), width=arc_width, closePath=close_path)
    shape.commit()
    if later_fill:
        page.draw_rect(fitz.Rect(139, 92, 151, 108), color=None, fill=(1, 1, 1), overlay=True)
    if later_intersample_fill:
        t = 16.5 / 32.0
        u = 1.0 - t
        hidden_point = fitz.Point(
            u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x,
            u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y,
        )
        page.draw_rect(
            fitz.Rect(
                hidden_point.x - 0.1,
                hidden_point.y - 0.1,
                hidden_point.x + 0.1,
                hidden_point.y + 0.1,
            ),
            color=None,
            fill=(1, 1, 1),
            overlay=True,
        )
    if later_interior_fill:
        page.draw_rect(fitz.Rect(109, 74, 111, 76), color=None, fill=(1, 1, 1), overlay=True)
    if later_image:
        image_path = path.with_suffix(".png")
        cv2.imwrite(str(image_path), np.full((8, 8, 3), 255, dtype=np.uint8))
        page.insert_image(fitz.Rect(141, 96, 149, 104), filename=str(image_path), overlay=True)
        image_path.unlink()
    if later_frame:
        # Its bounding box contains the candidate arc, while its actual stroke
        # remains well outside the arc's path.
        page.draw_rect(fitz.Rect(10, 10, 190, 190), color=(0, 0, 0), width=1.0, overlay=True)
    if later_stroke:
        # Cross the quarter-arc near its midpoint.
        page.draw_line(fitz.Point(132, 60), fitz.Point(132, 76), color=(0, 0, 0), width=1.0, overlay=True)
    if later_curved_frame:
        page.draw_bezier(
            fitz.Point(90, 80), fitz.Point(90, 120),
            fitz.Point(160, 120), fitz.Point(160, 80),
            color=(0, 0, 0), width=1.0, overlay=True,
        )
    if later_duplicate:
        duplicate = page.new_shape()
        duplicate.draw_bezier(p0, p1, p2, p3)
        duplicate.finish(color=(0, 0, 0), width=1.5)
        duplicate.commit()
    if later_curved_stroke_intersample:
        midpoint = fitz.Point(
            0.125 * p0.x + 0.375 * p1.x + 0.375 * p2.x + 0.125 * p3.x,
            0.125 * p0.y + 0.375 * p1.y + 0.375 * p2.y + 0.125 * p3.y,
        )
        tangent = fitz.Point(
            0.75 * (p1.x - p0.x) + 1.5 * (p2.x - p1.x) + 0.75 * (p3.x - p2.x),
            0.75 * (p1.y - p0.y) + 1.5 * (p2.y - p1.y) + 0.75 * (p3.y - p2.y),
        )
        tangent /= math.hypot(tangent.x, tangent.y)
        normal = fitz.Point(midpoint.x - center.x, midpoint.y - center.y)
        normal /= math.hypot(normal.x, normal.y)
        crossing_t = 0.53125

        def later_point(t: float) -> fitz.Point:
            offset = t - crossing_t
            return fitz.Point(
                midpoint.x + tangent.x * 40.0 * offset + normal.x * 1500.0 * offset**2,
                midpoint.y + tangent.y * 40.0 * offset + normal.y * 1500.0 * offset**2,
            )

        q0, q3 = later_point(0.0), later_point(1.0)
        derivative0 = fitz.Point(
            tangent.x * 40.0 - normal.x * 3000.0 * crossing_t,
            tangent.y * 40.0 - normal.y * 3000.0 * crossing_t,
        )
        derivative1 = fitz.Point(
            tangent.x * 40.0 + normal.x * 3000.0 * (1.0 - crossing_t),
            tangent.y * 40.0 + normal.y * 3000.0 * (1.0 - crossing_t),
        )
        q1 = q0 + derivative0 / 3.0
        q2 = q3 - derivative1 / 3.0
        page.draw_bezier(q0, q1, q2, q3, color=(1, 1, 1), width=1.0, overlay=True)
    if page_rotation:
        page.set_rotation(page_rotation)
    document.save(path)
    document.close()


def _wrap_page_in_triangle_clip(path: Path) -> None:
    """Apply a triangular PDF clip whose scissor contains the full quarter arc."""
    document = fitz.open(path)
    page = document[0]
    content_xref = page.get_contents()[0]
    original_stream = document.xref_stream(content_xref)
    # Page coordinates are converted to PDF's bottom-up coordinate system.
    # The diagonal cuts through the quarter arc, while its scissor rectangle
    # fully contains the arc path and its stroke width.
    clip_prefix = b"q 97 148 m 148 148 l 148 97 l h W n\n"
    document.update_stream(content_xref, clip_prefix + original_stream + b"\nQ")
    document.save(path.with_name(f"{path.stem}-triangle-clipped.pdf"))
    document.close()


def _wrap_page_in_rectangle_clip(path: Path) -> Path:
    """Apply a rectangular PDF clip that fully contains the quarter arc."""
    document = fitz.open(path)
    page = document[0]
    content_xref = page.get_contents()[0]
    original_stream = document.xref_stream(content_xref)
    # The clip rectangle surrounds the entire stroke with a small margin.
    clip_prefix = b"q 90 155 m 155 155 l 155 90 l 90 90 l h W n\n"
    document.update_stream(content_xref, clip_prefix + original_stream + b"\nQ")
    clipped_path = path.with_name(f"{path.stem}-rectangle-clipped.pdf")
    document.save(clipped_path)
    document.close()
    return clipped_path


def test_visible_open_pdf_vector_arc_reaches_primitive_ir(tmp_path: Path) -> None:
    source = tmp_path / "visible-quarter-arc.pdf"
    output = tmp_path / "result"
    _write_quarter_arc_pdf(source)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1
    assert arcs[0]["source"] == "geometry_pdfvector"
    assert len(arcs[0]["trace"]["source_pdf_sha256"]) == 64
    assert arcs[0]["trace"]["source_page_index"] == 0
    assert arcs[0]["trace"]["source_render_dpi"] == 72
    assert arcs[0]["trace"]["source_render_sha256"] == payload["source_document"]["sha256"]
    assert len(arcs[0]["trace"]["source_transform"]) == 6
    assert validate_document(payload) == []
    missing_source_identity = copy.deepcopy(payload)
    del missing_source_identity["primitives"][[p["type"] for p in missing_source_identity["primitives"]].index("arc")]["trace"]["source_pdf_sha256"]
    assert any("source_pdf_sha256" in error for error in validate_document(missing_source_identity))
    geometry = arcs[0]["geometry"]
    assert geometry["center"]["x"] == pytest.approx(100.0, abs=0.5)
    assert geometry["center"]["y"] == pytest.approx(100.0, abs=0.5)
    assert geometry["radius"] == pytest.approx(45.0, abs=0.5)
    sweep = (geometry["end_angle_deg"] - geometry["start_angle_deg"]) % 360.0
    assert sweep == pytest.approx(90.0, abs=1.0)

    primitive_doc = load_primitive_ir_document(str(output / "primitive_ir" / "page_01.json"))
    build = build_dxf(primitive_doc, str(tmp_path / "candidate.dxf"))
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed is True
    assert len(build.handle_by_primitive_id) == len(payload["primitives"])


def test_source_layer_witness_requires_full_rendered_pixel_support():
    visible = getattr(run_pdf_module, "_line_has_full_pixel_difference_support", None)
    assert callable(visible), "rendered-pixel witness check is missing"

    baseline = np.full((60, 100, 3), 255, dtype=np.uint8)
    layer_off = baseline.copy()
    baseline[30, 10:91] = 0
    assert visible(baseline, layer_off, (10, 30), (90, 30), 1.0)

    partially_occluded = baseline.copy()
    partially_occluded[30, 50:91] = 255
    assert not visible(partially_occluded, layer_off, (10, 30), (90, 30), 1.0)

    unrelated_nearby_paint = baseline.copy()
    unrelated_nearby_paint[30, 10:91] = 255
    unrelated_nearby_paint[32, 10:91] = 0
    assert not visible(unrelated_nearby_paint, layer_off, (10, 30), (90, 30), 1.0)

    fractional_competing_paint = baseline.copy()
    assert not visible(
        baseline,
        layer_off,
        (10, 30),
        (90, 30),
        1.0,
        competing_bounds_px=((10.0, 30.25, 90.0, 30.75),),
    )

    adjacent_ocg_paint = baseline.copy()
    adjacent_ocg_paint[30, 10:91] = 255
    adjacent_ocg_paint[31, 10:91] = 0
    assert not visible(adjacent_ocg_paint, layer_off, (10, 30), (90, 30), 1.0)


def _write_ocg_group_false_pixel_witness_pdf(path: Path) -> None:
    """Build a real PDF whose adjacent OCG raster ink can impersonate a hidden vector line."""
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    ocg = document.add_ocg("Oculto (ISO)")
    resources_xref = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    form_xref = document.get_new_xref()
    document.update_object(
        form_xref,
        f"<< /Type /XObject /Subtype /Form /FormType 1 /BBox [0 0 600 600] "
        f"/Resources << /Properties << /MC0 {ocg} 0 R >> >> "
        "/Group << /Type /Group /S /Transparency /CS /DeviceRGB /I true /K false >> >>",
    )
    document.update_stream(
        form_xref,
        b"/OC /MC0 BDC\n50 300 m 550 300 l 0 0 0 RG 1 w S\nEMC\n",
    )
    document.xref_set_key(resources_xref, "XObject/Fm1", f"{form_xref} 0 R")
    page_contents_xref = document.get_new_xref()
    document.update_object(page_contents_xref, "<<>>")
    document.update_stream(page_contents_xref, b"/Fm1 Do\n")
    document.xref_set_key(page.xref, "Contents", f"{page_contents_xref} 0 R")

    # This opaque later stroke fully covers the vector line. The independent
    # non-OCG raster line below is visually coincident with it in both renders.
    page.draw_line((50, 300), (550, 300), color=(1, 1, 1), width=4, overlay=True)

    def add_transparent_raster_line(y: int, *, layer: int | None = None) -> None:
        image = np.zeros((600, 600, 4), dtype=np.uint8)
        image[y, 50:551, :3] = 0
        image[y, 50:551, 3] = 255
        encoded_ok, encoded = cv2.imencode(".png", image)
        assert encoded_ok
        kwargs = {"oc": layer} if layer is not None else {}
        page.insert_image(
            fitz.Rect(0, 0, 600, 600), stream=encoded.tobytes(), overlay=True, **kwargs
        )

    # This OCG image changes only the immediately adjacent pixel row when the
    # layer is toggled. It is not a path in get_drawings() and has no peer bbox.
    add_transparent_raster_line(301, layer=ocg)
    add_transparent_raster_line(300)
    document.save(path)


def _write_ocg_direct_false_pixel_witness_pdf(path: Path) -> None:
    """Build a top-level OCG vector line hidden by paint plus an OCG raster decoy."""
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    ocg = document.add_ocg("Oculto (ISO)")
    page.draw_line(
        (50, 300), (550, 300), color=(0, 0, 0), width=1, oc=ocg, overlay=True
    )
    page.draw_line((50, 300), (550, 300), color=(1, 1, 1), width=4, overlay=True)
    image = np.zeros((600, 600, 4), dtype=np.uint8)
    image[301, 50:551, :3] = 0
    image[301, 50:551, 3] = 255
    encoded_ok, encoded = cv2.imencode(".png", image)
    assert encoded_ok
    page.insert_image(
        fitz.Rect(0, 0, 600, 600), stream=encoded.tobytes(), oc=ocg, overlay=True
    )
    document.save(path)


def _write_ocg_inline_image_false_pixel_witness_pdf(path: Path) -> None:
    """Build a covered OCG vector line whose inline OCG image impersonates it."""
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    ocg = document.add_ocg("Oculto (ISO)")
    resources_xref = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    document.xref_set_key(resources_xref, "Properties", f"<< /MC0 {ocg} 0 R >>")
    content_xref = document.get_new_xref()
    document.update_object(content_xref, "<<>>")
    image_pixels = np.full((5, 500, 3), 255, dtype=np.uint8)
    image_pixels[1:4, :, :] = 0
    content = (
        b"/OC /MC0 BDC\n50 299 m 550 299 l 0 0 0 RG 1 w S\nEMC\n"
        b"1 1 1 RG 4 w 50 299 m 550 299 l S\n"
        b"/OC /MC0 BDC\nq\n500 0 0 5 50 297.5 cm\n"
        b"BI /W 500 /H 5 /CS /RGB /BPC 8 ID\n"
        + image_pixels.tobytes()
        + b"\nEI\nQ\nEMC\n"
    )
    document.update_stream(content_xref, content)
    document.xref_set_key(page.xref, "Contents", f"{content_xref} 0 R")
    document.save(path)
    document.close()


def _write_ocg_fractional_inline_image_false_pixel_witness_pdf(path: Path) -> None:
    """Place an inline OCG image in a fractional PDF box over one raster row."""
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    ocg = document.add_ocg("Oculto (ISO)")
    resources_xref = int(document.xref_get_key(page.xref, "Resources")[1].split()[0])
    document.xref_set_key(resources_xref, "Properties", f"<< /MC0 {ocg} 0 R >>")
    content_xref = document.get_new_xref()
    document.update_object(content_xref, "<<>>")
    image_pixels = np.zeros((1, 500, 3), dtype=np.uint8)
    content = (
        b"/OC /MC0 BDC\n50 300 m 550 300 l 0 0 0 RG 1 w S\nEMC\n"
        b"1 1 1 RG 4 w 50 300 m 550 300 l S\n"
        b"/OC /MC0 BDC\nq\n500 0 0 0.5 50 299.25 cm\n"
        b"BI /W 500 /H 1 /CS /RGB /BPC 8 ID\n"
        + image_pixels.tobytes()
        + b"\nEI\nQ\nEMC\n"
    )
    document.update_stream(content_xref, content)
    document.xref_set_key(page.xref, "Contents", f"{content_xref} 0 R")
    document.save(path)
    document.close()


def test_inline_ocg_image_cannot_witness_covered_source_layer_line(tmp_path: Path) -> None:
    source = tmp_path / "inline-ocg-image-false-line-witness.pdf"
    _write_ocg_inline_image_false_pixel_witness_pdf(source)

    with fitz.open(source) as document:
        page = document[0]
        candidate = next(
            drawing
            for drawing in page.get_drawings(extended=True)
            if drawing.get("layer") == "Oculto (ISO)"
        )
        assert candidate["items"] == [("l", fitz.Point(50, 301), fitz.Point(550, 301))]
        assert page.get_images(full=True) == []
        inline_images = page.get_image_info(xrefs=True)
        assert len(inline_images) == 1 and inline_images[0]["xref"] == 0
        initial_configs = [dict(config) for config in document.layer_ui_configs()]
        baseline = run_pdf_module._pixmap_rgb_array(
            page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        )
        assert baseline is not None
        document.set_layer_ui_config(0, fitz.PDF_OC_OFF)
        layer_off = run_pdf_module._pixmap_rgb_array(
            page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        )
        assert run_pdf_module._restore_pdf_optional_content_state(
            document, initial_configs
        )
        assert layer_off is not None
        candidate_samples_changed = np.any(baseline[:, :, :3] != layer_off[:, :, :3], axis=2)
        assert candidate_samples_changed[299, 50:550].all()
        assert run_pdf_module._page_pdf_source_layer_line_witnesses(
            page, page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False), 1.0, (0, 0)
        ) == []

    output = tmp_path / "pipeline"
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]
    assert lines, "the visible inline-image line should remain in raster geometry"
    assert not any(primitive.get("layer") == "HIDDEN" for primitive in lines)
    primitive_doc = load_primitive_ir_document(str(output / "primitive_ir" / "page_01.json"))
    build = build_dxf(primitive_doc, str(tmp_path / "inline-ocg-image.dxf"))
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed is True
    assert "HIDDEN" not in build.layer_by_primitive_id.values()


def test_fractional_inline_image_bbox_cannot_witness_pixel_row(tmp_path: Path) -> None:
    source = tmp_path / "fractional-inline-ocg-image-false-line-witness.pdf"
    _write_ocg_fractional_inline_image_false_pixel_witness_pdf(source)

    with fitz.open(source) as document:
        page = document[0]
        candidate = next(
            drawing
            for drawing in page.get_drawings(extended=True)
            if drawing.get("layer") == "Oculto (ISO)"
        )
        assert candidate["items"] == [
            ("l", fitz.Point(50, 300), fitz.Point(550, 300))
        ]
        assert page.get_images(full=True) == []
        inline_images = page.get_image_info(xrefs=True)
        assert len(inline_images) == 1 and inline_images[0]["xref"] == 0
        assert tuple(inline_images[0]["bbox"]) == pytest.approx(
            (50.0, 300.25, 550.0, 300.75)
        )

        initial_configs = [dict(config) for config in document.layer_ui_configs()]
        baseline = run_pdf_module._pixmap_rgb_array(
            page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        )
        assert baseline is not None
        document.set_layer_ui_config(0, fitz.PDF_OC_OFF)
        layer_off = run_pdf_module._pixmap_rgb_array(
            page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        )
        assert run_pdf_module._restore_pdf_optional_content_state(
            document, initial_configs
        )
        assert layer_off is not None
        changed = np.any(baseline[:, :, :3] != layer_off[:, :, :3], axis=2)
        assert changed[300, 50:550].all()
        assert not changed[299, 50:550].any()
        assert not changed[301, 50:550].any()
        assert run_pdf_module._page_pdf_source_layer_line_witnesses(
            page, page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False), 1.0, (0, 0)
        ) == []

    output = tmp_path / "fractional-pipeline"
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]
    assert lines, "visible raster image geometry should remain in Primitive IR"
    assert not any(primitive.get("layer") in {"HIDDEN", "CENTERLINE"} for primitive in lines)

    primitive_doc = load_primitive_ir_document(
        str(output / "primitive_ir" / "page_01.json")
    )
    build = build_dxf(primitive_doc, str(tmp_path / "fractional-inline-ocg-image.dxf"))
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed is True
    assert not any(
        layer in {"HIDDEN", "CENTERLINE"}
        for layer in build.layer_by_primitive_id.values()
    )


def test_real_pdf_group_ocg_neighbor_pixels_do_not_witness_hidden_source_line(
    tmp_path: Path,
):
    source = tmp_path / "group-ocg-adjacent-pixels.pdf"
    _write_ocg_group_false_pixel_witness_pdf(source)

    document = fitz.open(source)
    page = document[0]
    drawings = page.get_drawings(extended=True)
    candidate = next(drawing for drawing in drawings if drawing.get("layer") == "Oculto (ISO)")
    candidate_ancestors = [
        drawing
        for drawing in drawings
        if drawing.get("type") in {"group", "clip"}
        and drawing.get("level", candidate["level"]) < candidate["level"]
    ]
    assert {drawing["type"] for drawing in candidate_ancestors} == {"group", "clip"}
    assert candidate.get("scissor") is None
    candidate_index = drawings.index(candidate)
    assert not run_pdf_module._source_layer_line_has_safe_ancestry(
        drawings,
        candidate_index,
        run_pdf_module._full_page_transparency_group_index(page, drawings),
    )

    baseline_pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    baseline = run_pdf_module._pixmap_rgb_array(baseline_pixmap)
    assert baseline is not None
    document.set_layer_ui_config(0, fitz.PDF_OC_OFF)
    layer_off_pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    document.set_layer_ui_config(0, fitz.PDF_OC_ON)
    layer_off = run_pdf_module._pixmap_rgb_array(layer_off_pixmap)
    assert layer_off is not None
    changed = np.any(baseline != layer_off, axis=2)
    assert not changed[300, 50:551].any(), "the hidden vector stroke changed its own pixel row"
    assert changed[301, 50:551].all(), "the OCG neighbor-pixel control did not render"

    output = tmp_path / "pipeline"
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["layer"] == "HIDDEN" for primitive in payload["primitives"])


def test_real_pdf_ocg_image_pixels_do_not_witness_group_scoped_hidden_source_line(
    tmp_path: Path,
):
    source = tmp_path / "direct-ocg-image-decoy.pdf"
    _write_ocg_direct_false_pixel_witness_pdf(source)
    document = fitz.open(source)
    page = document[0]
    candidate = next(
        drawing for drawing in page.get_drawings(extended=True)
        if drawing.get("layer") == "Oculto (ISO)"
    )
    drawings = page.get_drawings(extended=True)
    candidate_index = drawings.index(candidate)
    assert candidate.get("level", 0) > 0
    assert not run_pdf_module._source_layer_line_has_safe_ancestry(
        drawings,
        candidate_index,
        run_pdf_module._full_page_transparency_group_index(page, drawings),
    )
    baseline = run_pdf_module._pixmap_rgb_array(
        page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    )
    assert baseline is not None
    document.set_layer_ui_config(0, fitz.PDF_OC_OFF)
    layer_off = run_pdf_module._pixmap_rgb_array(
        page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    )
    document.set_layer_ui_config(0, fitz.PDF_OC_ON)
    assert layer_off is not None
    changed = np.any(baseline != layer_off, axis=2)
    assert not changed[300, 50:551].any()
    assert changed[301, 50:551].all()

    output = tmp_path / "pipeline"
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["layer"] == "HIDDEN" for primitive in payload["primitives"])


def test_source_layer_line_witness_does_not_borrow_adjacent_ocg_path_pixels():
    def pixmap(image: np.ndarray) -> fitz.Pixmap:
        return fitz.Pixmap(
            fitz.csRGB, image.shape[1], image.shape[0], image.tobytes(), False
        )

    candidate = {
        "layer": "Oculto (ISO)",
        "level": 1,
        "type": "s",
        "fill": None,
        "stroke_opacity": 1.0,
        "blendmode": None,
        "width": 1.0,
        "dashes": "[] 0",
        "items": [("l", (10.0, 30.0), (90.0, 30.0))],
        "seqno": 0,
    }
    adjacent_ocg_path = {
        "layer": "Oculto (ISO)",
        "level": 1,
        "type": "s",
        "fill": None,
        "stroke_opacity": 1.0,
        "blendmode": None,
        "width": 1.0,
        "dashes": "[] 0",
        "items": [("c", (10.0, 31.0), (30.0, 31.0), (60.0, 31.0), (90.0, 31.0))],
        "seqno": 1,
    }

    class Document:
        def layer_ui_configs(self):
            return [{"number": 0, "text": "Oculto (ISO)", "on": 1}]

        def get_ocgs(self):
            return {}

        def get_oc(self, xref):
            return None

        def set_layer_ui_config(self, number, action):
            assert number == 0
            assert action in {fitz.PDF_OC_ON, fitz.PDF_OC_OFF}

    class Page:
        rotation = 0
        rotation_matrix = fitz.Matrix(1, 1)
        parent = Document()

        def __init__(self, layer_off: np.ndarray):
            self.layer_off = layer_off

        def get_drawings(self, *, extended):
            assert extended is True
            return [candidate, adjacent_ocg_path]

        def get_bboxlog(self):
            return [
                ("stroke-path", fitz.Rect(10.0, 29.5, 90.0, 30.5)),
                ("stroke-path", fitz.Rect(10.0, 30.5, 90.0, 31.5)),
            ]

        def get_images(self, *, full):
            assert full is True
            return []

        def get_image_info(self, *, xrefs):
            assert xrefs is True
            return []

        def get_pixmap(self, *, matrix, alpha):
            assert matrix.a == pytest.approx(1.0)
            assert alpha is False
            return pixmap(self.layer_off)

    layer_off = np.full((60, 100, 3), 255, dtype=np.uint8)

    # The candidate is fully hidden, while a separate, non-simple path in
    # the same OCG changes the adjacent pixel row when the OCG is toggled.
    covered_baseline = layer_off.copy()
    covered_baseline[31, 10:91] = 0
    assert run_pdf_module._page_pdf_source_layer_line_witnesses(
        Page(layer_off), pixmap(covered_baseline), 1.0, (0, 0)
    ) == []

    # A true candidate contribution outside the adjacent path's pixel cells
    # remains admissible.
    visible_baseline = covered_baseline.copy()
    visible_baseline[29, 10:91] = 0
    witnesses = run_pdf_module._page_pdf_source_layer_line_witnesses(
        Page(layer_off), pixmap(visible_baseline), 1.0, (0, 0)
    )
    assert len(witnesses) == 1
    assert witnesses[0][1] == "HIDDEN"


def test_source_layer_witness_fails_closed_when_image_ocg_readback_fails():
    def pixmap(image: np.ndarray) -> fitz.Pixmap:
        return fitz.Pixmap(
            fitz.csRGB, image.shape[1], image.shape[0], image.tobytes(), False
        )

    candidate = {
        "layer": "Oculto (ISO)",
        "level": 0,
        "type": "s",
        "fill": None,
        "stroke_opacity": 1.0,
        "blendmode": None,
        "width": 1.0,
        "dashes": "[] 0",
        "items": [("l", (10.0, 30.0), (90.0, 30.0))],
        "seqno": 0,
    }

    class Document:
        def layer_ui_configs(self):
            return [{"number": 0, "text": "Oculto (ISO)", "on": 1}]

        def get_ocgs(self):
            return {1: {"name": "Oculto (ISO)"}}

        def get_oc(self, xref):
            assert xref == 2
            raise RuntimeError("image optional-content relation unreadable")

        def set_layer_ui_config(self, number, action):
            assert number == 0
            assert action in {fitz.PDF_OC_ON, fitz.PDF_OC_OFF}

    class Page:
        rotation = 0
        rotation_matrix = fitz.Matrix(1, 1)
        parent = Document()

        def get_drawings(self, *, extended):
            assert extended is True
            return [candidate]

        def get_bboxlog(self):
            return [("stroke-path", fitz.Rect(10.0, 29.5, 90.0, 30.5))]

        def get_images(self, *, full):
            assert full is True
            return [(2, 0, 0, 0, 0, 0, 0, 0)]

        def get_image_info(self, *, xrefs):
            assert xrefs is True
            return []

        def get_pixmap(self, *, matrix, alpha):
            assert matrix.a == pytest.approx(1.0)
            assert alpha is False
            return pixmap(layer_off)

    layer_off = np.full((60, 100, 3), 255, dtype=np.uint8)
    baseline = layer_off.copy()
    baseline[30, 10:91] = 0
    assert run_pdf_module._page_pdf_source_layer_line_witnesses(
        Page(), pixmap(baseline), 1.0, (0, 0)
    ) == []


def test_source_layer_mapping_rejects_unsupported_paint_properties():
    classify = getattr(run_pdf_module, "_pdf_source_layer_classification", None)
    assert callable(classify), "source-layer classifier is missing"

    base = {
        "layer": "Oculto (ISO)",
        "level": 1,
        "type": "s",
        "fill": None,
        "stroke_opacity": 1.0,
        "blendmode": None,
        "width": 1.0,
        "dashes": "[] 0",
        "items": [("l", (0.0, 0.0), (10.0, 0.0))],
    }
    assert classify(base) == "HIDDEN"
    assert classify({**base, "stroke_opacity": 0.5}) is None
    assert classify({**base, "blendmode": "Multiply"}) is None
    assert classify({**base, "scissor": fitz.Rect(0, 0, 5, 5)}) is None
    assert classify({**base, "layer": "Marca de centro (ISO)"}) is None
    assert classify({**base, "level": -1}) is None


def test_pdf_layer_visibility_probe_fails_closed_when_layer_state_cannot_be_restored():
    class Document:
        def layer_ui_configs(self):
            return [{"number": 0, "text": "Oculto (ISO)", "on": 1}]

        def get_ocgs(self):
            return {}

        def get_oc(self, xref):
            return None

        def set_layer_ui_config(self, number, action):
            if action == fitz.PDF_OC_ON:
                raise RuntimeError("restore failed")

    class Page:
        rotation = 0
        rotation_matrix = fitz.Matrix(1, 1)
        parent = Document()

        def get_drawings(self, *, extended):
            return [{
                "layer": "Oculto (ISO)", "level": 1, "type": "s", "fill": None,
                "stroke_opacity": 1.0, "blendmode": None, "dashes": "[] 0",
                "width": 1.0, "items": [("l", (2.0, 5.0), (18.0, 5.0))],
                "seqno": 0,
            }]

        def get_bboxlog(self):
            return [("stroke-path", fitz.Rect(2.0, 4.0, 18.0, 6.0))]

        def get_images(self, *, full):
            assert full is True
            return []

        def get_image_info(self, *, xrefs):
            assert xrefs is True
            return []

        def get_pixmap(self, **kwargs):
            return fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 10), False)

    baseline = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 10), False)
    with pytest.raises(RuntimeError, match="restore PDF optional-content layer state"):
        run_pdf_module._page_pdf_source_layer_line_witnesses(
            Page(), baseline, 1.0, (0, 0)
        )


def test_pdf_layer_visibility_probe_detects_silent_related_layer_state_change():
    class Document:
        def __init__(self):
            self.configs = [
                {"number": 0, "text": "Oculto (ISO)", "depth": 0, "type": "checkbox", "on": 1, "locked": 0},
                {"number": 1, "text": "Other", "depth": 0, "type": "checkbox", "on": 0, "locked": 0},
            ]

        def layer_ui_configs(self):
            return [dict(config) for config in self.configs]

        def get_ocgs(self):
            return {}

        def get_oc(self, xref):
            return None

        def set_layer_ui_config(self, number, action):
            if number == 0:
                self.configs[0]["on"] = int(action == fitz.PDF_OC_ON)
                if action == fitz.PDF_OC_ON:
                    # Simulate a successful API return with a linked OCG silently
                    # changed; attempting to restore that OCG also lies.
                    self.configs[1]["on"] = 1
            elif number == 1 and action == fitz.PDF_OC_ON:
                self.configs[1]["on"] = 1

    class Page:
        rotation = 0
        rotation_matrix = fitz.Matrix(1, 1)

        def __init__(self):
            self.parent = Document()

        def get_drawings(self, *, extended):
            assert extended is True
            return [{
                "layer": "Oculto (ISO)", "level": 0, "type": "s", "fill": None,
                "stroke_opacity": 1.0, "blendmode": None, "dashes": "[] 0",
                "width": 1.0, "items": [("l", (2.0, 5.0), (18.0, 5.0))],
                "seqno": 0,
            }]

        def get_bboxlog(self):
            return [("stroke-path", fitz.Rect(2.0, 4.5, 18.0, 5.5))]

        def get_images(self, *, full):
            assert full is True
            return []

        def get_image_info(self, *, xrefs):
            assert xrefs is True
            return []

        def get_pixmap(self, **kwargs):
            return fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 10), False)

    baseline = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 10), False)
    with pytest.raises(RuntimeError, match="restore PDF optional-content layer state"):
        run_pdf_module._page_pdf_source_layer_line_witnesses(
            Page(), baseline, 1.0, (0, 0)
        )


@pytest.mark.real_data
def test_b041_classifies_only_visible_source_layer_lines(tmp_path: Path) -> None:
    pdf_value = os.environ.get("CAD_AGENT_B041_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_B041_CIRCLE_PDF to the approved private B041 PDF")
    source = Path(pdf_value)
    assert source.is_file(), "CAD_AGENT_B041_CIRCLE_PDF must point to the approved PDF"
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_sha256 == "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"

    output = tmp_path / "b041-source-layers"
    result = run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    primitives = payload["primitives"]
    layers = Counter(primitive["layer"] for primitive in primitives)

    assert result["pages"][0]["primitive_count"] == 242
    assert Counter(primitive["type"] for primitive in primitives) == {
        "line": 236, "circle": 3, "arc": 3,
    }
    # The short source CENTERLINE dash at x=162, y=313..319 meets an earlier
    # visible contour at its first endpoint. That endpoint pixel is unchanged
    # when the CENTERLINE OCG is hidden, so the full-span witness must leave
    # this one candidate unclassified while preserving the detected geometry.
    assert layers == {"UNCLASSIFIED": 229, "CENTERLINE": 7, "HIDDEN": 6}
    unresolved_joined_dash = [
        primitive
        for primitive in primitives
        if primitive["type"] == "line"
        and primitive["layer"] == "UNCLASSIFIED"
        and primitive["geometry"]["start"]["x"] == pytest.approx(162.0, abs=0.5)
        and primitive["geometry"]["start"]["y"] == pytest.approx(313.0, abs=0.5)
        and primitive["geometry"]["end"]["x"] == pytest.approx(162.0, abs=0.5)
        and primitive["geometry"]["end"]["y"] == pytest.approx(319.0, abs=0.5)
    ]
    assert len(unresolved_joined_dash) == 1
    assert all(
        primitive["type"] == "line"
        for primitive in primitives
        if primitive["layer"] in {"CENTERLINE", "HIDDEN"}
    )

    primitive_doc = load_primitive_ir_document(
        str(output / "primitive_ir" / "page_01.json")
    )
    dxf_path = tmp_path / "b041-source-layers.dxf"
    build = build_dxf(primitive_doc, str(dxf_path))
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed is True
    assert build.entity_count == 242
    assert Counter(build.layer_by_primitive_id.values()) == layers

    ezdxf = pytest.importorskip("ezdxf")
    reopened = ezdxf.readfile(str(dxf_path))
    entities = list(reopened.modelspace())
    assert len(entities) == 242
    assert Counter(entity.dxf.layer for entity in entities) == layers
    assert reopened.layers.get("HIDDEN").dxf.linetype.casefold() == "continuous"
    assert reopened.layers.get("CENTERLINE").dxf.linetype.casefold() == "continuous"


@pytest.mark.parametrize(
    "options",
    [
        {"ellipse_y_radius": 28.0},
        {"close_path": True},
        {"later_fill": True},
        {"later_image": True},
        {"disconnected": True},
    ],
    ids=["ellipse", "chord-closed", "later-paint-occlusion", "later-image-occlusion", "disconnected-path"],
)
def test_unsupported_or_ambiguous_vector_paths_do_not_emit_arc(tmp_path: Path, options: dict) -> None:
    source = tmp_path / "negative.pdf"
    output = tmp_path / "negative-result"
    _write_quarter_arc_pdf(source, **options)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_later_stroke_bbox_without_path_overlap_does_not_hide_arc(tmp_path: Path) -> None:
    source = tmp_path / "later-frame.pdf"
    output = tmp_path / "later-frame-result"
    _write_quarter_arc_pdf(source, later_frame=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1


def test_later_curved_stroke_bbox_without_path_overlap_preserves_arc(tmp_path: Path) -> None:
    source = tmp_path / "later-curved-frame.pdf"
    output = tmp_path / "later-curved-frame-result"
    _write_quarter_arc_pdf(source, later_curved_frame=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1


def test_later_opaque_fill_between_arc_samples_blocks_admission(tmp_path: Path) -> None:
    source = tmp_path / "intersample-occlusion.pdf"
    output = tmp_path / "intersample-occlusion-result"
    _write_quarter_arc_pdf(source, radius=200.0, later_intersample_fill=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_later_fill_inside_arc_bounds_but_away_from_path_preserves_arc(tmp_path: Path) -> None:
    source = tmp_path / "interior-fill.pdf"
    output = tmp_path / "interior-fill-result"
    _write_quarter_arc_pdf(source, later_interior_fill=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1


def test_later_stroke_crossing_arc_still_blocks_admission(tmp_path: Path) -> None:
    source = tmp_path / "later-crossing-stroke.pdf"
    output = tmp_path / "later-crossing-stroke-result"
    _write_quarter_arc_pdf(source, later_stroke=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_later_stroke_retracing_arc_still_blocks_admission(tmp_path: Path) -> None:
    source = tmp_path / "later-duplicate.pdf"
    output = tmp_path / "later-duplicate-result"
    _write_quarter_arc_pdf(source, later_duplicate=True)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_later_curved_stroke_between_samples_blocks_arc_admission(tmp_path: Path) -> None:
    source = tmp_path / "later-curved-crossing-stroke.pdf"
    output = tmp_path / "later-curved-crossing-stroke-result"
    _write_quarter_arc_pdf(
        source,
        later_curved_stroke_intersample=True,
        arc_width=1.0,
        page_size_override=520.0,
        center_override=(100.0, 100.0),
    )

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_open_arc_crossing_zero_degrees_keeps_the_minor_sweep(tmp_path: Path) -> None:
    source = tmp_path / "wraparound.pdf"
    output = tmp_path / "wraparound-result"
    _write_quarter_arc_pdf(source, start_deg=315.0, sweep_deg=90.0)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1
    geometry = arcs[0]["geometry"]
    assert (geometry["end_angle_deg"] - geometry["start_angle_deg"]) % 360.0 == pytest.approx(90.0, abs=1.0)


def test_page_rotation_transform_preserves_arc_radius_and_sweep(tmp_path: Path) -> None:
    source = tmp_path / "rotated.pdf"
    output = tmp_path / "rotated-result"
    _write_quarter_arc_pdf(source, page_rotation=90)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    assert len(arcs) == 1
    assert arcs[0]["geometry"]["radius"] == pytest.approx(45.0, abs=0.5)
    assert (arcs[0]["geometry"]["end_angle_deg"] - arcs[0]["geometry"]["start_angle_deg"]) % 360.0 == pytest.approx(90.0, abs=1.0)


def test_clipped_pdf_vector_arc_is_not_admitted(tmp_path: Path) -> None:
    source = tmp_path / "clipped.pdf"
    _write_quarter_arc_pdf(source)
    document = fitz.open(source)
    page = document[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    rendered = tmp_path / "render.png"
    pixmap.save(rendered)
    drawings = [dict(drawing) for drawing in page.get_drawings(extended=True)]
    drawings[0]["level"] = 1  # PyMuPDF's nested/clip drawing context marker.
    clipped_page = SimpleNamespace(
        rotation=page.rotation,
        rotation_matrix=page.rotation_matrix,
        get_drawings=lambda **kwargs: drawings,
        get_bboxlog=page.get_bboxlog,
    )

    arcs = _page_vector_arcs(
        clipped_page,
        rendered.read_bytes(),
        1.0,
        (pixmap.x, pixmap.y),
        72,
        hashlib.sha256(source.read_bytes()).hexdigest(),
        0,
    )
    document.close()
    assert arcs == []


def test_pdf_arc_support_uses_frozen_render_bytes_during_shared_png_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "render-custody-arc.pdf"
    output = tmp_path / "render-custody-arc-result"
    _write_quarter_arc_pdf(source)
    rendered_path = output / "rendered" / "page_01.png"
    original_arc_reader = run_pdf_module._page_vector_arcs
    substituted = False

    def swap_shared_png_during_arc_read(page, rendered_png_bytes, *args, **kwargs):
        nonlocal substituted
        source_bytes = rendered_path.read_bytes()
        source_image = cv2.imdecode(
            np.frombuffer(source_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        assert source_image is not None
        encoded_ok, blank_image = cv2.imencode(
            ".png", np.full_like(source_image, 255)
        )
        assert encoded_ok
        rendered_path.write_bytes(blank_image.tobytes())
        substituted = True
        try:
            return original_arc_reader(page, rendered_png_bytes, *args, **kwargs)
        finally:
            rendered_path.write_bytes(source_bytes)

    monkeypatch.setattr(run_pdf_module, "_page_vector_arcs", swap_shared_png_during_arc_read)
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)

    assert substituted
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert sum(primitive["type"] == "arc" for primitive in payload["primitives"]) == 1


def test_nonrectangular_clip_cannot_hide_arc_behind_its_scissor_bbox(tmp_path: Path) -> None:
    source = tmp_path / "triangle-clipped.pdf"
    _write_quarter_arc_pdf(source)
    _wrap_page_in_triangle_clip(source)
    clipped_source = source.with_name("triangle-clipped-triangle-clipped.pdf")
    output = tmp_path / "triangle-clipped-result"

    run_pdf(clipped_source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert not any(primitive["type"] == "arc" for primitive in payload["primitives"])


def test_rectangular_clip_containing_arc_preserves_vector_arc(tmp_path: Path) -> None:
    source = tmp_path / "rectangle-clipped.pdf"
    _write_quarter_arc_pdf(source)
    clipped_source = _wrap_page_in_rectangle_clip(source)
    output = tmp_path / "rectangle-clipped-result"

    run_pdf(clipped_source, output, scale_mm_per_px=1.0, dpi=72)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    assert sum(primitive["type"] == "arc" for primitive in payload["primitives"]) == 1


def test_only_short_line_fragments_on_the_arc_locus_are_suppressed() -> None:
    arc = RawArc(
        id="arc",
        center_px=(0.0, 0.0),
        radius_px=10.0,
        start_px=(10.0, 0.0),
        end_px=(0.0, 10.0),
        signed_sweep_deg=90.0,
        confidence=1.0,
        bbox_px=(0.0, 0.0, 10.0, 10.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
    )
    duplicate_fragment = RawLine("fragment", (10.0, 0.0), (9.848, 1.736), 1.0, (9, 0, 10, 2))
    crossing_line = RawLine("crossing", (9.0, -5.0), (9.0, 5.0), 1.0, (9, -5, 9, 5))

    assert _line_is_explained_by_pdf_arc(duplicate_fragment, arc)
    assert not _line_is_explained_by_pdf_arc(crossing_line, arc)


def test_independent_pdf_tangent_line_survives_arc_duplicate_suppression(tmp_path: Path) -> None:
    source = tmp_path / "independent-tangent-line.pdf"
    output = tmp_path / "independent-tangent-line-result"
    render_scale = 216.0 / 72.0
    expected_line_length_px = 60.0
    radius_px = 850.0
    center_px = (350.0 * render_scale, 350.0 * render_scale)
    _write_quarter_arc_pdf(
        source,
        radius=850.0 / render_scale,
        arc_width=0.5,
        page_size_override=700.0,
        center_override=(350.0, 350.0),
        leading_tangent_line_length=expected_line_length_px / render_scale,
    )

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=216)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]
    assert len(arcs) == 1
    midpoint = (
        center_px[0] + radius_px / math.sqrt(2.0),
        center_px[1] - radius_px / math.sqrt(2.0),
    )
    tangent = (-1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0))
    image_height_px = payload["source_document"]["image_height_px"]

    def overlaps_independent_tangent(line: dict) -> bool:
        geometry = line["geometry"]
        endpoints = [
            (geometry["start"]["x"], image_height_px - geometry["start"]["y"]),
            (geometry["end"]["x"], image_height_px - geometry["end"]["y"]),
        ]
        perpendicular = [
            abs(
                (point[0] - midpoint[0]) * tangent[1]
                - (point[1] - midpoint[1]) * tangent[0]
            )
            for point in endpoints
        ]
        projected = [
            (point[0] - midpoint[0]) * tangent[0]
            + (point[1] - midpoint[1]) * tangent[1]
            for point in endpoints
        ]
        return (
            max(perpendicular) <= 4.0
            and min(projected) <= expected_line_length_px / 2.0
            and max(projected) >= -expected_line_length_px / 2.0
        )

    assert any(overlaps_independent_tangent(line) for line in lines), (
        "the independent PDF tangent stroke was removed as an ARC duplicate"
    )


def test_short_pdf_tangent_witness_does_not_extend_arc_hough_line(tmp_path: Path) -> None:
    source = tmp_path / "short-tangent-witness.pdf"
    output = tmp_path / "short-tangent-witness-result"
    render_scale = 144.0 / 72.0
    witness_length_px = 10.0
    _write_quarter_arc_pdf(
        source,
        radius=850.0 / render_scale,
        arc_width=0.5,
        page_size_override=1000.0,
        center_override=(500.0, 500.0),
        leading_tangent_line_length=witness_length_px / render_scale,
    )

    # The independent oracle is the short LINE record in the generated PDF,
    # not the raster detector's line extent.
    with fitz.open(source) as pdf:
        source_lines = [
            drawing["items"][0]
            for drawing in pdf[0].get_drawings(extended=True)
            if len(drawing.get("items", [])) == 1
            and drawing["items"][0][0] == "l"
        ]
        assert len(source_lines) == 1
        source_start = fitz.Point(source_lines[0][1]) * render_scale
        source_end = fitz.Point(source_lines[0][2]) * render_scale
        source_length = math.dist(
            (source_start.x, source_start.y), (source_end.x, source_end.y)
        )
        assert source_length == pytest.approx(witness_length_px, abs=0.1)

    run_pdf(source, output, scale_mm_per_px=1.0, dpi=144)

    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
    lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]
    assert len(arcs) == 1
    image_height = payload["source_document"]["image_height_px"]
    witness_start = (source_start.x, image_height - source_start.y)
    witness_end = (source_end.x, image_height - source_end.y)
    witness_dx = witness_end[0] - witness_start[0]
    witness_dy = witness_end[1] - witness_start[1]
    witness_norm = math.hypot(witness_dx, witness_dy)
    witness_direction = (witness_dx / witness_norm, witness_dy / witness_norm)

    witness_matched_lengths = []
    for primitive in lines:
        geometry = primitive["geometry"]
        endpoints = [
            (geometry["start"]["x"], geometry["start"]["y"]),
            (geometry["end"]["x"], geometry["end"]["y"]),
        ]
        dx = endpoints[1][0] - endpoints[0][0]
        dy = endpoints[1][1] - endpoints[0][1]
        line_length = math.hypot(dx, dy)
        if line_length <= 1e-9 or abs(
            (dx * witness_direction[0] + dy * witness_direction[1]) / line_length
        ) < 0.98:
            continue
        perpendicular = [
            abs(
                (point[0] - witness_start[0]) * witness_direction[1]
                - (point[1] - witness_start[1]) * witness_direction[0]
            )
            for point in endpoints
        ]
        projections = [
            (point[0] - witness_start[0]) * witness_direction[0]
            + (point[1] - witness_start[1]) * witness_direction[1]
            for point in endpoints
        ]
        overlap = max(
            0.0,
            min(witness_norm, max(projections)) - max(0.0, min(projections)),
        )
        if max(perpendicular) <= 2.5 and overlap > 0:
            witness_matched_lengths.append(line_length)

    assert witness_matched_lengths, "the visible source LINE witness was lost"
    assert all(
        0.75 * witness_length_px <= length <= witness_length_px + 2.0
        for length in witness_matched_lengths
    ), (
        "the emitted ARC-adjacent LINE must stay within the source-supported extent; "
        f"source extent={witness_length_px:.1f}px, emitted extents={witness_matched_lengths}"
    )


def test_merge_lines_does_not_extend_pdf_witness_clipped_line(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "merge-witness-input.png"
    image_path.write_bytes(b"synthetic image")
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    arc = RawArc(
        id="arc",
        center_px=(0.0, 0.0),
        radius_px=100.0,
        start_px=(100.0 * math.cos(math.radians(-10.0)), 100.0 * math.sin(math.radians(-10.0))),
        end_px=(100.0 * math.cos(math.radians(10.0)), 100.0 * math.sin(math.radians(10.0))),
        signed_sweep_deg=20.0,
        confidence=1.0,
        bbox_px=(98.0, -18.0, 101.0, 18.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
    )
    # The first Hough segment is clipped to the short PDF LINE witness.
    # The separate same-direction segment has no PDF witness or pixel support.
    detected_lines = [
        RawLine("arc-tangent", (100.0, -6.0), (100.0, 6.0), 0.8, (100, -6, 100, 6)),
        RawLine("unsupported-fragment", (100.0, 12.0), (100.0, 25.0), 0.7, (100, 12, 100, 25)),
    ]
    witness = RawLine("pdf-witness", (100.0, -4.0), (100.0, 4.0), 1.0, (100, -4, 100, 4))
    captured: dict = {}

    monkeypatch.setattr(run_image_module.cv2, "imread", lambda _path: image)
    monkeypatch.setattr(
        run_image_module, "extract_raw_geometry", lambda *_args, **_kwargs: RawGeometry(lines=detected_lines)
    )

    def build_document(**kwargs):
        captured["raw_lines"] = kwargs["raw_lines"]
        return SimpleNamespace(cross_validations=[])

    monkeypatch.setattr(run_image_module, "build_document", build_document)
    monkeypatch.setattr(run_image_module, "cross_validate", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(run_image_module, "save_document", lambda *_args, **_kwargs: None)

    run_image_module.run(
        image_path=str(image_path),
        output_path=str(tmp_path / "out" / "primitive_ir.json"),
        scale_mm_per_px=1.0,
        merge_lines=True,
        pdf_vector_arcs=[arc],
        pdf_vector_line_witnesses=[witness],
    )

    lines = captured["raw_lines"]
    assert len(lines) == 2, f"witness-bounded and independent lines must remain distinct: {lines}"
    assert any(line.id == "arc-tangent" and line.length_px() == pytest.approx(8.0) for line in lines)
    assert any(
        line.id == "unsupported-fragment" and line.length_px() == pytest.approx(13.0)
        for line in lines
    )


def test_duplicate_hough_candidates_for_one_pdf_witness_emit_one_line(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "duplicate-witness-input.png"
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)

    arc = RawArc(
        id="arc",
        center_px=(0.0, 0.0),
        radius_px=100.0,
        start_px=(100.0 * math.cos(math.radians(-10.0)), 100.0 * math.sin(math.radians(-10.0))),
        end_px=(100.0 * math.cos(math.radians(10.0)), 100.0 * math.sin(math.radians(10.0))),
        signed_sweep_deg=20.0,
        confidence=1.0,
        bbox_px=(98.0, -18.0, 101.0, 18.0),
        source_pdf_sha256="a" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="b" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
    )
    separate_arc = RawArc(
        id="separate-arc",
        center_px=(0.0, 0.0),
        radius_px=110.0,
        start_px=(110.0 * math.cos(math.radians(-10.0)), 110.0 * math.sin(math.radians(-10.0))),
        end_px=(110.0 * math.cos(math.radians(10.0)), 110.0 * math.sin(math.radians(10.0))),
        signed_sweep_deg=20.0,
        confidence=1.0,
        bbox_px=(108.0, -18.0, 111.0, 18.0),
        source_pdf_sha256="c" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="d" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
    )
    witness = RawLine("pdf-witness", (100.0, -4.0), (100.0, 4.0), 1.0, (100, -4, 100, 4))
    separate_witness = RawLine(
        "separate-pdf-witness", (110.0, -4.0), (110.0, 4.0), 1.0, (110, -4, 110, 4)
    )
    duplicate_hough_candidates = [
        RawLine("arc-tangent-1", (100.0, -6.0), (100.0, 6.0), 0.8, (100, -6, 100, 6)),
        RawLine("arc-tangent-2", (100.0, -6.0), (100.0, 6.0), 0.8, (100, -6, 100, 6)),
        RawLine("separate-witness-line", (110.0, -6.0), (110.0, 6.0), 0.8, (110, -6, 110, 6)),
        RawLine("independent-line", (20.0, 20.0), (50.0, 20.0), 0.9, (20, 20, 50, 20)),
    ]
    monkeypatch.setattr(
        run_image_module,
        "extract_raw_geometry",
        lambda *_args, **_kwargs: RawGeometry(lines=duplicate_hough_candidates),
    )

    output_path = tmp_path / "duplicate-witness-output.json"
    run_image_module.run(
        image_path=str(image_path),
        output_path=str(output_path),
        scale_mm_per_px=1.0,
        merge_lines=True,
        pdf_vector_arcs=[arc, separate_arc],
        pdf_vector_line_witnesses=[witness, separate_witness],
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    emitted_lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]

    assert len(emitted_lines) == 3, (
        "repeated Hough detections must collapse only within their shared PDF "
        f"witness interval while preserving the independent line: {emitted_lines}"
    )
    assert {primitive["id"] for primitive in emitted_lines} == {
        "arc-tangent-1",
        "separate-witness-line",
        "independent-line",
    }


def test_overlapping_hough_intervals_for_one_pdf_witness_emit_one_bounded_line(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "overlapping-witness-input.png"
    image = np.full((150, 5200, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)

    radius = 5000.0
    end_angle = math.radians(2.0)
    arc = RawArc(
        id="long-arc",
        center_px=(0.0, 0.0),
        radius_px=radius,
        start_px=(radius, 0.0),
        end_px=(radius * math.cos(end_angle), radius * math.sin(end_angle)),
        signed_sweep_deg=2.0,
        confidence=1.0,
        bbox_px=(4998.0, -2.0, 5001.0, 175.0),
        source_pdf_sha256="e" * 64,
        source_page_index=0,
        source_transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        render_sha256="f" * 64,
        render_dpi=72,
        render_origin_px=(0, 0),
    )
    witness = RawLine("long-pdf-witness", (5000.0, 0.0), (5000.0, 100.0), 1.0, (5000, 0, 5000, 100))
    proposals = [
        RawLine("interval-a", (5000.0, 0.0), (5000.0, 75.0), 0.8, (5000, 0, 5000, 75)),
        RawLine("interval-b", (5000.0, 25.0), (5000.0, 100.0), 0.9, (5000, 25, 5000, 100)),
    ]
    monkeypatch.setattr(
        run_image_module,
        "extract_raw_geometry",
        lambda *_args, **_kwargs: RawGeometry(lines=proposals),
    )

    output_path = tmp_path / "overlapping-witness-output.json"
    run_image_module.run(
        image_path=str(image_path),
        output_path=str(output_path),
        scale_mm_per_px=1.0,
        merge_lines=True,
        pdf_vector_arcs=[arc],
        pdf_vector_line_witnesses=[witness],
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    emitted_lines = [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]

    assert len(emitted_lines) == 1, (
        "overlapping proposals for one source witness must not emit duplicate "
        f"Primitive IR LINE claims: {emitted_lines}"
    )
    geometry = emitted_lines[0]["geometry"]
    assert geometry["start"]["x"] == pytest.approx(5000.0)
    assert geometry["end"]["x"] == pytest.approx(5000.0)
    assert abs(geometry["end"]["y"] - geometry["start"]["y"]) == pytest.approx(100.0)


@pytest.mark.parametrize("bboxlog_corruption", ["truncated", "kind_mismatch"])
def test_inconsistent_bboxlog_fails_closed_for_hidden_line_witness(
    tmp_path: Path, bboxlog_corruption: str
) -> None:
    source = tmp_path / "hidden-line-bboxlog.pdf"
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    page.draw_line(
        fitz.Point(20, 100), fitz.Point(80, 100), color=(0, 0, 0), width=0.5
    )
    page.draw_rect(
        fitz.Rect(18, 96, 82, 104), color=None, fill=(1, 1, 1), overlay=True
    )
    document.save(source)
    document.close()

    with fitz.open(source) as pdf:
        page = pdf[0]
        drawings = page.get_drawings(extended=True)
        bboxlog = page.get_bboxlog()
        assert [record[0] for record in bboxlog] == ["stroke-path", "fill-path"]
        assert _page_vector_line_witnesses(page, 1.0, (0, 0)) == []

        if bboxlog_corruption == "truncated":
            corrupted_bboxlog = bboxlog[:-1]
        else:
            corrupted_bboxlog = list(bboxlog)
            corrupted_bboxlog[1] = ("stroke-path", corrupted_bboxlog[1][1])

        inconsistent_page = SimpleNamespace(
            rotation=page.rotation,
            rotation_matrix=page.rotation_matrix,
            get_drawings=lambda **_: drawings,
            get_bboxlog=lambda: corrupted_bboxlog,
        )
        assert _page_vector_line_witnesses(inconsistent_page, 1.0, (0, 0)) == []


@pytest.mark.parametrize(
    ("occluder", "cover_line_cap"),
    [("fill", 0), ("cubic_stroke", 0), ("cubic_stroke", 1)],
)
def test_hidden_pdf_tangent_line_does_not_resurrect_arc_fragment(
    tmp_path: Path, occluder: str, cover_line_cap: int
) -> None:
    source_without_line = tmp_path / "arc-without-line.pdf"
    output_without_line = tmp_path / "arc-without-line-result"
    source_with_hidden_line = tmp_path / "arc-with-hidden-line.pdf"
    output_with_hidden_line = tmp_path / "arc-with-hidden-line-result"
    render_scale = 216.0 / 72.0
    expected_line_length_px = 60.0
    radius_px = 850.0
    center_px = (350.0 * render_scale, 350.0 * render_scale)

    _write_quarter_arc_pdf(
        source_without_line,
        radius=850.0 / render_scale,
        arc_width=0.5,
        page_size_override=700.0,
        center_override=(350.0, 350.0),
    )
    _write_quarter_arc_pdf(
        source_with_hidden_line,
        radius=850.0 / render_scale,
        arc_width=0.5,
        page_size_override=700.0,
        center_override=(350.0, 350.0),
        leading_tangent_line_length=expected_line_length_px / render_scale,
        occlude_leading_tangent_line=occluder == "fill",
        occlude_leading_tangent_line_with_cubic_stroke=occluder == "cubic_stroke",
        occluding_cubic_line_cap=cover_line_cap,
    )

    with fitz.open(source_without_line) as control_doc, fitz.open(
        source_with_hidden_line
    ) as covered_doc:
        control_pixels = control_doc[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        covered_pixels = covered_doc[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        if cover_line_cap == 1:
            assert control_pixels.samples == covered_pixels.samples

    run_pdf(source_without_line, output_without_line, scale_mm_per_px=1.0, dpi=216)
    run_pdf(source_with_hidden_line, output_with_hidden_line, scale_mm_per_px=1.0, dpi=216)

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (
            output_without_line / "primitive_ir" / "page_01.json",
            output_with_hidden_line / "primitive_ir" / "page_01.json",
        )
    ]
    arcs_by_case = [
        [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]
        for payload in payloads
    ]
    lines_by_case = [
        [primitive for primitive in payload["primitives"] if primitive["type"] == "line"]
        for payload in payloads
    ]
    assert [len(arcs) for arcs in arcs_by_case] == [1, 1]

    midpoint = (
        center_px[0] + radius_px / math.sqrt(2.0),
        center_px[1] - radius_px / math.sqrt(2.0),
    )
    tangent = (-1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0))
    image_height_px = payloads[1]["source_document"]["image_height_px"]

    def overlaps_hidden_tangent(line: dict) -> bool:
        geometry = line["geometry"]
        endpoints = [
            (geometry["start"]["x"], image_height_px - geometry["start"]["y"]),
            (geometry["end"]["x"], image_height_px - geometry["end"]["y"]),
        ]
        perpendicular = [
            abs(
                (point[0] - midpoint[0]) * tangent[1]
                - (point[1] - midpoint[1]) * tangent[0]
            )
            for point in endpoints
        ]
        projected = [
            (point[0] - midpoint[0]) * tangent[0]
            + (point[1] - midpoint[1]) * tangent[1]
            for point in endpoints
        ]
        return (
            max(perpendicular) <= 4.0
            and min(projected) <= expected_line_length_px / 2.0
            and max(projected) >= -expected_line_length_px / 2.0
        )

    assert not any(overlaps_hidden_tangent(line) for line in lines_by_case[0])
    assert not any(overlaps_hidden_tangent(line) for line in lines_by_case[1]), (
        "an occluded PDF line witness preserved a raster fragment of the ARC as a LINE"
    )


@pytest.mark.real_data
def test_b041_preserves_three_source_supported_corner_arcs(tmp_path: Path) -> None:
    pdf_value = os.environ.get("CAD_AGENT_B041_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_B041_CIRCLE_PDF to the approved private B041 PDF")
    source = Path(pdf_value)
    assert source.is_file(), "CAD_AGENT_B041_CIRCLE_PDF must point to the approved PDF"
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_sha256 == "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"

    output = tmp_path / "b041-vector-arc-result"
    run_pdf(source, output, scale_mm_per_px=1.0, dpi=72)
    payload = json.loads(
        (output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8")
    )
    arcs = [primitive for primitive in payload["primitives"] if primitive["type"] == "arc"]

    assert len(arcs) == 3
    assert all(arc["source"] == "geometry_pdfvector" for arc in arcs)
    assert all(arc["trace"]["source_pdf_sha256"] == source_sha256 for arc in arcs)
    assert all(arc["trace"]["source_page_index"] == 0 for arc in arcs)
    assert all(arc["geometry"]["radius"] == pytest.approx(2.79, abs=0.02) for arc in arcs)
    assert all(
        (arc["geometry"]["end_angle_deg"] - arc["geometry"]["start_angle_deg"]) % 360.0
        == pytest.approx(90.0, abs=0.02)
        for arc in arcs
    )
    assert validate_document(payload) == []

    primitive_doc = load_primitive_ir_document(
        str(output / "primitive_ir" / "page_01.json")
    )
    build = build_dxf(primitive_doc, str(tmp_path / "b041-vector-arcs.dxf"))
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed is True
    assert len(build.handle_by_primitive_id) == len(payload["primitives"])
