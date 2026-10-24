"""Focused source-vector ARC admission tests for the existing PDF owner."""

from __future__ import annotations

import json
import hashlib
import copy
import math
import os
from pathlib import Path
from types import SimpleNamespace

import fitz
import cv2
import numpy as np
import pytest

from primitive_ir_lib.run_pdf import _page_vector_arcs, run_pdf
from primitive_ir_lib.geometry_extraction import RawArc, RawLine
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
    later_duplicate: bool = False,
    disconnected: bool = False,
    start_deg: float = 0.0,
    sweep_deg: float = 90.0,
    page_rotation: int = 0,
) -> None:
    document = fitz.open()
    y_radius = ellipse_y_radius or radius
    page_size = max(200.0, 2.0 * max(radius, y_radius) + 20.0)
    page = document.new_page(width=page_size, height=page_size)
    center = fitz.Point(page_size / 2.0, page_size / 2.0)
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
    shape = page.new_shape()
    shape.draw_bezier(p0, p1, p2, p3)
    if disconnected:
        gap_start = fitz.Point(center.x + radius * math.cos(math.radians(100)), center.y - radius * math.sin(math.radians(100)))
        gap_end = fitz.Point(center.x + radius * math.cos(math.radians(115)), center.y - radius * math.sin(math.radians(115)))
        shape.draw_bezier(gap_start, gap_start, gap_end, gap_end)
    shape.finish(color=(0, 0, 0), width=1.5, closePath=close_path)
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
    if later_duplicate:
        duplicate = page.new_shape()
        duplicate.draw_bezier(p0, p1, p2, p3)
        duplicate.finish(color=(0, 0, 0), width=1.5)
        duplicate.commit()
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
        rendered,
        1.0,
        (pixmap.x, pixmap.y),
        72,
        hashlib.sha256(source.read_bytes()).hexdigest(),
        0,
    )
    document.close()
    assert arcs == []


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
