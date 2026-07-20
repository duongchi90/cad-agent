"""Render detector and reviewed-line overlays for benchmark inspection."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Optional

import cv2


def render_overlay(
    image_path: Path,
    prediction_path: Path,
    output_path: Path,
    annotation_path: Optional[Path] = None,
    min_length_px: float = 0.0,
) -> dict:
    if min_length_px < 0:
        raise ValueError("min_length_px must be non-negative")
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    annotation = json.loads(annotation_path.read_text(encoding="utf-8")) if annotation_path else {}
    visible_predictions = []
    for line in prediction.get("lines", []):
        p1, p2 = tuple(map(int, line["p1_px"])), tuple(map(int, line["p2_px"]))
        if math.dist(p1, p2) < min_length_px:
            continue
        visible_predictions.append(line)
        cv2.line(image, p1, p2, (0, 0, 255), 1, cv2.LINE_AA)
    for line in annotation.get("expected_lines", []):
        p1, p2 = tuple(map(int, line["p1_px"])), tuple(map(int, line["p2_px"]))
        cv2.line(image, p1, p2, (0, 190, 0), 2, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise RuntimeError(f"Cannot write overlay: {output_path}")
    return {"predicted_lines": len(visible_predictions), "expected_lines": len(annotation.get("expected_lines", [])), "output": str(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--annotation", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-length-px", type=float, default=0.0, help="Hide predicted segments shorter than this")
    args = parser.parse_args()
    result = render_overlay(args.image, args.prediction, args.output, args.annotation, args.min_length_px)
    print(f"Overlay saved: {result['output']} (predicted={result['predicted_lines']}, expected={result['expected_lines']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())