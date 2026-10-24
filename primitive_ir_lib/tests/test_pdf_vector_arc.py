"""Focused source-vector ARC admission tests for the existing PDF owner."""

from __future__ import annotations

import json
import hashlib
import copy
import math
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
    later_image: bool = False,
    disconnected: bool = False,
    start_deg: float = 0.0,
    sweep_deg: float = 90.0,
    page_rotation: int = 0,
) -> None:
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    center = fitz.Point(100, 100)
    y_radius = ellipse_y_radius or radius
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
    if later_image:
        image_path = path.with_suffix(".png")
        cv2.imwrite(str(image_path), np.full((8, 8, 3), 255, dtype=np.uint8))
        page.insert_image(fitz.Rect(141, 96, 149, 104), filename=str(image_path), overlay=True)
        image_path.unlink()
    if page_rotation:
        page.set_rotation(page_rotation)
    document.save(path)
    document.close()


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
