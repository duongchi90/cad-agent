import pytest

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.view_calibration import (
    detect_view_candidates,
    extract_scale_label_candidates,
    mm_per_px_for_scale,
    parse_scale_label,
)


def test_parse_scale_label_accepts_common_title_variants():
    assert parse_scale_label("TL 1:40") == 40
    assert parse_scale_label("Tỷ lệ 1:8") == 8
    assert parse_scale_label("Tile 1:20") == 20
    assert parse_scale_label("4:40") is None


def test_mm_per_px_for_scale_uses_render_dpi():
    assert mm_per_px_for_scale(40, 144) == pytest.approx(7.0555555556)


def test_extract_scale_label_candidates_retains_ocr_provenance():
    primitives = [
        {"id": "scale", "type": "text", "trace": {"bbox_px": [10, 20, 60, 40]},
         "text_data": {"content": "Tile 1:20"}},
        {"id": "note", "type": "text", "trace": {"bbox_px": [1, 1, 2, 2]},
         "text_data": {"content": "GHI CHU"}},
    ]
    assert extract_scale_label_candidates(primitives, 144) == [{
        "source_text_id": "scale", "bbox_px": [10, 20, 60, 40],
        "scale_denominator": 20, "pixel_to_unit_scale": pytest.approx(3.5277777778),
        "status": "needs_verification",
    }]


def _text(content, bbox, id_="text"):
    return RawText(id_, content, bbox, 0.0, 0.9, "text_tesseract")


def _line(x0, y0, x1, y1, id_="line"):
    return RawLine(id_, (x0, y0), (x1, y1), 0.9, (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))


def test_detect_view_candidate_assigns_label_anywhere_to_one_nearby_region():
    label = _text("TL-1:5", (490, 150, 620, 180), "scale")
    lines = [_line(400, 100, 700, 100), _line(400, 100, 400, 350), _line(700, 100, 700, 350)]

    candidates = detect_view_candidates([label], lines, 1400, 900, 144)

    assert candidates == [{
        "source_text_id": "scale", "bbox_px": [490, 150, 620, 180],
        "region_bbox_px": [400.0, 100.0, 700.0, 350.0],
        "scale_denominator": 5, "pixel_to_unit_scale": pytest.approx(0.8819444444),
        "status": "needs_verification",
    }]


def test_detect_view_candidate_rejects_ambiguous_nearby_regions():
    label = _text("TL 1:5", (590, 150, 630, 180), "scale")
    lines = [_line(400, 100, 550, 100), _line(400, 100, 400, 350),
             _line(670, 100, 820, 100), _line(820, 100, 820, 350)]

    assert detect_view_candidates([label], lines, 1400, 900, 144) == []


def test_detect_view_candidate_records_dimension_evidence_inside_region():
    label = _text("TL 1:10", (450, 130, 520, 150), "scale")
    dimension = RawText("dimension", "500", (460, 180, 500, 200), 0.0, 0.9,
                        "text_tesseract", parsed_value=500.0, semantic_role="dimension_value")
    lines = [_line(400, 100, 900, 100), _line(400, 100, 400, 300), _line(900, 100, 900, 300)]

    candidate = detect_view_candidates([label, dimension], lines, 1200, 800, 254)[0]

    assert candidate["dimension_evidence"]["text_primitive_id"] == "dimension"
    assert candidate["dimension_evidence"]["delta_percent"] == pytest.approx(0.0)
