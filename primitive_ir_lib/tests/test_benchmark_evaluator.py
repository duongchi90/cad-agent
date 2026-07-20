"""Tests for benchmark line matching metrics."""

import json
from pathlib import Path

import pytest

from primitive_ir_lib.benchmark_evaluator import evaluate_dataset, evaluate_lines


def test_evaluator_matches_reversed_endpoints_and_counts_false_positive():
    annotation = {
        "status": "annotated",
        "expected_lines": [
            {"p1_px": [10, 10], "p2_px": [100, 10]},
            {"p1_px": [10, 30], "p2_px": [100, 30]},
        ],
    }
    prediction = {
        "lines": [
            {"id": "a", "p1_px": [100, 10], "p2_px": [10, 10]},
            {"id": "b", "p1_px": [12, 31], "p2_px": [102, 31]},
            {"id": "noise", "p1_px": [1, 80], "p2_px": [20, 80]},
        ],
    }

    result = evaluate_lines(annotation, prediction, tolerance_px=3)

    assert result["matched_lines"] == 2
    assert result["precision"] == 0.6667
    assert result["recall"] == 1.0


def test_dataset_evaluator_skips_templates_and_aggregates_reviewed_pages(tmp_path: Path):
    annotations = tmp_path / "annotations"
    predictions = tmp_path / "predictions"
    (annotations / "doc").mkdir(parents=True)
    (predictions / "doc").mkdir(parents=True)
    (annotations / "doc" / "page_01.json").write_text(json.dumps({
        "status": "annotated", "expected_lines": [{"p1_px": [0, 0], "p2_px": [10, 0]}]
    }), encoding="utf-8")
    (predictions / "doc" / "page_01.json").write_text(json.dumps({
        "lines": [{"id": "good", "p1_px": [0, 0], "p2_px": [10, 0]}, {"id": "extra", "p1_px": [0, 4], "p2_px": [4, 4]}]
    }), encoding="utf-8")
    (annotations / "doc" / "page_02.json").write_text(json.dumps({
        "status": "needs_annotation", "expected_lines": []
    }), encoding="utf-8")

    report = evaluate_dataset(annotations, predictions, tolerance_px=1)

    assert report["reviewed_pages"] == 1
    assert report["skipped_unannotated_pages"] == ["doc/page_02.json"]
    assert report["micro"]["matched_lines"] == 1
    assert report["micro"]["precision"] == 0.5
    assert report["micro"]["recall"] == 1.0


def test_dataset_without_reviewed_pages_has_no_metrics(tmp_path: Path):
    annotations = tmp_path / "annotations"
    predictions = tmp_path / "predictions"
    annotations.mkdir()
    predictions.mkdir()
    (annotations / "page_01.json").write_text(json.dumps({"status": "needs_annotation"}), encoding="utf-8")

    report = evaluate_dataset(annotations, predictions)

    assert report["reviewed_pages"] == 0
    assert report["micro"]["precision"] is None
    assert report["micro"]["recall"] is None

if __name__ == "__main__":
    test_evaluator_matches_reversed_endpoints_and_counts_false_positive()
    print("1/1 test PASS")

def test_annotated_page_without_verified_lines_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        evaluate_lines({"status": "annotated", "expected_lines": []}, {"lines": []})