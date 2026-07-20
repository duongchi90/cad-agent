"""Evaluate raw Hough geometry against manually verified pixel annotations.

Evaluate one page with --annotation/--prediction, or an entire benchmark tree
with --annotations-dir/--predictions-dir. Dataset evaluation skips templates
whose status is `
eeds_annotation`` and reports them explicitly.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _endpoint_error(expected: dict[str, Any], predicted: dict[str, Any]) -> float:
    e1, e2 = expected["p1_px"], expected["p2_px"]
    p1, p2 = predicted["p1_px"], predicted["p2_px"]
    direct = math.hypot(e1[0] - p1[0], e1[1] - p1[1]) + math.hypot(e2[0] - p2[0], e2[1] - p2[1])
    reverse = math.hypot(e1[0] - p2[0], e1[1] - p2[1]) + math.hypot(e2[0] - p1[0], e2[1] - p1[1])
    return min(direct, reverse) / 2.0


def _validate_line(line: dict[str, Any], location: str) -> None:
    for key in ("p1_px", "p2_px"):
        point = line.get(key)
        if not isinstance(point, list) or len(point) != 2 or not all(isinstance(value, (int, float)) for value in point):
            raise ValueError(f"{location}.{key} must be a two-number pixel coordinate")


def evaluate_lines(annotation: dict[str, Any], prediction: dict[str, Any], tolerance_px: float = 6.0) -> dict[str, Any]:
    if tolerance_px < 0:
        raise ValueError("tolerance_px must be non-negative")
    expected = annotation.get("expected_lines", [])
    if annotation.get("status") == "annotated" and not expected:
        raise ValueError("Annotated page must contain at least one verified expected line")
    predicted = prediction.get("lines", [])
    if not isinstance(expected, list) or not isinstance(predicted, list):
        raise ValueError("expected_lines and lines must be arrays")
    for index, line in enumerate(expected):
        _validate_line(line, f"expected_lines[{index}]")
    for index, line in enumerate(predicted):
        _validate_line(line, f"lines[{index}]")

    unmatched = set(range(len(predicted)))
    matches = []
    for expected_index, line in enumerate(expected):
        candidate = min(unmatched, key=lambda index: _endpoint_error(line, predicted[index]), default=None)
        if candidate is None:
            continue
        error = _endpoint_error(line, predicted[candidate])
        if error <= tolerance_px:
            unmatched.remove(candidate)
            matches.append({"expected_index": expected_index, "predicted_id": predicted[candidate].get("id", str(candidate)), "endpoint_error_px": round(error, 3)})
    true_positive = len(matches)
    precision = true_positive / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else 1.0
    return {"expected_lines": len(expected), "predicted_lines": len(predicted), "matched_lines": true_positive,
            "precision": round(precision, 4), "recall": round(recall, 4), "matches": matches}


def evaluate_dataset(annotations_dir: Path, predictions_dir: Path, tolerance_px: float = 6.0) -> dict[str, Any]:
    """Evaluate every reviewed annotation, preserving relative page paths."""
    pages: list[dict[str, Any]] = []
    skipped: list[str] = []
    missing_predictions: list[str] = []
    for annotation_path in sorted(annotations_dir.rglob("*.json")):
        relative_path = annotation_path.relative_to(annotations_dir)
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        if annotation.get("status") == "needs_annotation":
            skipped.append(relative_path.as_posix())
            continue
        prediction_path = predictions_dir / relative_path
        if not prediction_path.is_file():
            missing_predictions.append(relative_path.as_posix())
            continue
        prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
        result = evaluate_lines(annotation, prediction, tolerance_px)
        result["page"] = relative_path.as_posix()
        pages.append(result)

    expected = sum(page["expected_lines"] for page in pages)
    predicted = sum(page["predicted_lines"] for page in pages)
    matched = sum(page["matched_lines"] for page in pages)
    precision = matched / predicted if predicted else (1.0 if expected == 0 and pages else None)
    recall = matched / expected if expected else (1.0 if pages else None)
    return {
        "tolerance_px": tolerance_px,
        "reviewed_pages": len(pages),
        "skipped_unannotated_pages": skipped,
        "missing_prediction_pages": missing_predictions,
        "micro": {"expected_lines": expected, "predicted_lines": predicted, "matched_lines": matched,
                  "precision": round(precision, 4) if precision is not None else None, "recall": round(recall, 4) if recall is not None else None},
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--annotation", type=Path)
    source.add_argument("--annotations-dir", type=Path)
    parser.add_argument("--prediction", type=Path)
    parser.add_argument("--predictions-dir", type=Path)
    parser.add_argument("--tolerance-px", default=6.0, type=float)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    if args.annotation:
        if not args.prediction or args.predictions_dir:
            parser.error("--annotation requires --prediction only")
        annotation = json.loads(args.annotation.read_text(encoding="utf-8"))
        if annotation.get("status") == "needs_annotation":
            parser.error("Annotation chua co ground truth; dien expected_lines truoc khi evaluate")
        report = evaluate_lines(annotation, json.loads(args.prediction.read_text(encoding="utf-8")), args.tolerance_px)
    else:
        if not args.predictions_dir or args.prediction:
            parser.error("--annotations-dir requires --predictions-dir only")
        report = evaluate_dataset(args.annotations_dir, args.predictions_dir, args.tolerance_px)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())