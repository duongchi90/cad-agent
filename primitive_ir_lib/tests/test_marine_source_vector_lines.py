"""Bounded real-source regression for visible PDF vector LINE admission."""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import fitz
import pytest

import primitive_ir_lib.run_pdf as run_pdf_module
import primitive_ir_lib.run_image as run_image_module
from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.reviewer import review_dxf
from primitive_ir_lib.validator import validate_document
from semantic_ir_lib.io_utils import load_primitive_ir_document

pytestmark = pytest.mark.real_data
_SOURCE_ENV = "CAD_AGENT_GUNNERUS_MARINE_PDF"
_SOURCE_SHA256 = "c4ec405ff866bbec40cdc15a86a1165f255d583af4e0c592767d5f6d65cd7ae3"
_FROZEN_PATH_SEQNO = 1445  # Test selector only; tied to this frozen input hash.


def _segment_key(start: tuple[float, float], end: tuple[float, float]) -> tuple:
    rounded = tuple(tuple(round(value, 5) for value in point) for point in (start, end))
    return tuple(sorted(rounded))


def test_gunnerus_visible_source_path_reaches_primitive_ir_and_dxf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_value = os.environ.get(_SOURCE_ENV)
    if not source_value:
        pytest.skip(f"set {_SOURCE_ENV} to the privately held, approved PDF")
    source = Path(source_value)
    assert source.is_file(), f"{_SOURCE_ENV} must point to the approved PDF"
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    assert source_sha256 == _SOURCE_SHA256

    dpi = 144
    scale = dpi / 72.0
    with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
        page = pdf[0]
        assert page.rotation == 270
        drawings = page.get_drawings(extended=True)
        source_path = next(
            drawing for drawing in drawings
            if drawing.get("seqno") == _FROZEN_PATH_SEQNO
        )
        assert source_path.get("type") == "s"
        assert source_path.get("fill") is None
        assert source_path.get("layer") == "03_Lines_Waterlines"
        source_items = source_path["items"]
        assert len(source_items) == 796
        assert all(item[0] == "l" for item in source_items)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        expected: Counter[tuple] = Counter()
        rotation = page.rotation_matrix
        for item in source_items:
            first = fitz.Point(item[1]) * rotation
            second = fitz.Point(item[2]) * rotation
            first_px = (first.x * scale - pixmap.x, first.y * scale - pixmap.y)
            second_px = (second.x * scale - pixmap.x, second.y * scale - pixmap.y)
            expected[_segment_key(first_px, second_px)] += 1

        render_sha256 = hashlib.sha256(pixmap.tobytes("png")).hexdigest()
        result = run_pdf_module._page_pdf_source_layer_line_witnesses(
            page,
            pixmap,
            scale,
            (pixmap.x, pixmap.y),
            include_pdf_vector_lines=True,
            source_pdf_sha256=source_sha256,
            source_page_index=0,
            render_dpi=dpi,
            _candidate_seqnos={_FROZEN_PATH_SEQNO},
        )
        assert isinstance(result, tuple) and len(result) == 2
        _, source_lines = result
        render_origin = (pixmap.x, pixmap.y)
        render_bytes = pixmap.tobytes("png")

    assert len(source_lines) == 577
    assert any("-i183-layer-03_Lines_Waterlines" in line.id for line in source_lines)
    assert len({line.id for line in source_lines}) == len(source_lines)
    actual: Counter[tuple] = Counter()
    for line in source_lines:
        assert line.source_seqno == _FROZEN_PATH_SEQNO
        assert line.source_layer == "03_Lines_Waterlines"
        assert line.source_pdf_sha256 == source_sha256
        assert line.source_page_index == 0
        assert line.render_sha256 == render_sha256
        assert line.render_dpi == dpi
        assert line.render_origin_px == render_origin
        assert line.source_item_index is not None
        assert line.p1_px != line.p2_px
        actual[_segment_key(line.p1_px, line.p2_px)] += 1
    assert all(actual[key] <= expected[key] for key in actual)

    # Run the existing image owner with its actual raster geometry and
    # duplicate/ambiguity screen. The test-only scale checks conversion only;
    # it is not drawing-scale evidence or calibration acceptance.
    rendered_path = tmp_path / "page.png"
    rendered_path.write_bytes(render_bytes)
    ir_path = tmp_path / "primitive_ir.json"
    extracted_raster_lines = []
    extract_raw_geometry = run_image_module.extract_raw_geometry

    def capture_raster_lines(*args, **kwargs):
        geometry = extract_raw_geometry(*args, **kwargs)
        extracted_raster_lines.extend(geometry.lines)
        return geometry

    monkeypatch.setattr(
        run_image_module, "extract_raw_geometry", capture_raster_lines
    )
    run_image_module.run(
        image_path=str(rendered_path),
        output_path=str(ir_path),
        scale_mm_per_px=1.0,
        preset="real_scan_tuned_v1",
        source_page_index=0,
        image_bytes=render_bytes,
        pdf_vector_lines=source_lines,
    )
    payload = json.loads(ir_path.read_text(encoding="utf-8"))
    assert validate_document(payload) == []
    ir_lines = [p for p in payload["primitives"] if p["source"] == "geometry_pdfvector"]
    expected_ir_line_ids = [
        line.id for line in source_lines
        if not run_image_module._pdf_line_overlaps_raster(
            [line], extracted_raster_lines, []
        )
    ]
    # The full-segment overlap check conservatively rejects seven short
    # source items that approach the same rendered raster stroke within the
    # overlap interval. Keep those source/raster conflicts out of admitted
    # PDF vectors; do not preserve the earlier start-offset-only count.
    additional_overlap_items = {709, 710, 712, 715, 717, 718, 719}
    assert additional_overlap_items.isdisjoint({
        line.source_item_index for line in source_lines
        if line.id in expected_ir_line_ids
    })
    assert len(expected_ir_line_ids) == 566
    assert [line["id"] for line in ir_lines] == expected_ir_line_ids
    assert all(p["type"] == "line" for p in ir_lines)
    raster_ir_lines = [
        primitive for primitive in payload["primitives"]
        if primitive["source"] == "geometry_opencv" and primitive["type"] == "line"
    ]
    assert {line["id"] for line in raster_ir_lines} == {
        line.id for line in extracted_raster_lines
    }

    dxf_path = tmp_path / "gunnerus-source-lines.dxf"
    build_result = build_dxf(
        load_primitive_ir_document(str(ir_path)), str(dxf_path)
    )
    assert dxf_path.is_file()
    assert not build_result.skipped_primitive_ids
    ir_line_count = sum(
        primitive["type"] == "line" for primitive in payload["primitives"]
    )
    assert build_result.entity_count == len(payload["primitives"])
    retained_source_lines = [
        line for line in source_lines if line.id in build_result.handle_by_primitive_id
    ]
    assert len(retained_source_lines) == 566
    assert len(source_lines) - len(retained_source_lines) == 11
    assert all(
        build_result.written_geometry_by_primitive_id[line.id]["type"] == "line"
        for line in retained_source_lines
    )
    review = review_dxf(build_result, strict_primitive_inventory=True)
    assert review.passed is True
    assert review.checked_count == build_result.entity_count
    print(
        f"SOURCE_PATH_LINES={len(source_items)}; "
        f"WITNESSED_LINES={len(source_lines)}; "
        f"PRIMITIVE_IR_LINES={len(ir_lines)}; DXF_LINES={ir_line_count}"
    )
