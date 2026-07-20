"""Tests for the local HTML benchmark review index."""

import json
from pathlib import Path

from primitive_ir_lib.benchmark_report import build_report


def test_build_report_links_annotation_and_overlay(tmp_path: Path):
    (tmp_path / "annotations" / "doc").mkdir(parents=True)
    annotation = tmp_path / "annotations" / "doc" / "page_01.json"
    annotation.write_text(json.dumps({"status": "annotated", "expected_lines": [{"p1_px": [0, 0], "p2_px": [1, 1]}]}), encoding="utf-8")
    (tmp_path / "geometry_baseline.json").write_text(json.dumps({"documents": [{"id": "doc", "pages": [{
        "page": 1, "annotation_json": "annotations/doc/page_01.json", "raw_line_count": 7
    }]}]}), encoding="utf-8")

    output = tmp_path / "review.html"
    result = build_report(tmp_path, output)

    text = output.read_text(encoding="utf-8")
    assert result["pages"] == 1
    assert "overlays_filtered_100px/doc/page_01.png" in text
    assert "annotated" in text