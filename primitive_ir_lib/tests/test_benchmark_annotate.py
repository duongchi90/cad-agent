"""Tests for benchmark annotation serialization without opening a GUI."""

import json
from pathlib import Path

from primitive_ir_lib.benchmark_annotate import add_lines, save_annotation, snap_point


def test_add_lines_preserves_schema_and_can_mark_annotated(tmp_path: Path):
    annotation = {"status": "needs_annotation", "expected_lines": []}
    add_lines(annotation, [((1, 2), (30, 2)), ((4, 5), (4, 20))], mark_annotated=True)
    path = tmp_path / "annotation.json"
    save_annotation(path, annotation)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "annotated"
    assert saved["expected_lines"] == [
        {"p1_px": [1, 2], "p2_px": [30, 2]},
        {"p1_px": [4, 5], "p2_px": [4, 20]},
    ]

def test_snap_point_uses_nearby_hough_endpoint_only():
    candidates = [(10, 10), (100, 100)]
    assert snap_point((13, 14), candidates, 6) == (10, 10)
    assert snap_point((30, 30), candidates, 6) == (30, 30)
    assert snap_point((13, 14), candidates, 0) == (13, 14)