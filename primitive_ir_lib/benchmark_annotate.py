"""Interactive ground-truth line annotation for rendered benchmark pages.

Controls: left-click two endpoints to add a line; U undo; S save; A save and
mark annotated; Q quit without saving. Coordinates are rendered-image pixels.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import cv2


def add_lines(annotation: dict, lines: Iterable[tuple[tuple[int, int], tuple[int, int]]], mark_annotated: bool = False) -> dict:
    annotation.setdefault("expected_lines", [])
    for p1, p2 in lines:
        annotation["expected_lines"].append({"p1_px": [int(p1[0]), int(p1[1])], "p2_px": [int(p2[0]), int(p2[1])]})
    if mark_annotated:
        if not annotation["expected_lines"]:
            raise ValueError("At least one verified line is required before marking annotated")
        annotation["status"] = "annotated"
    return annotation


def save_annotation(annotation_path: Path, annotation: dict) -> None:
    annotation_path.write_text(json.dumps(annotation, indent=2) + "\n", encoding="utf-8")


def snap_point(point: tuple[int, int], candidate_points: Iterable[tuple[int, int]], snap_px: float) -> tuple[int, int]:
    """Snap a click to the nearest Hough endpoint within the configured radius."""
    if snap_px <= 0:
        return point
    nearest = min(candidate_points, key=lambda candidate: math.dist(point, candidate), default=None)
    return nearest if nearest is not None and math.dist(point, nearest) <= snap_px else point


def annotate_interactively(
    image_path: Path,
    annotation_path: Path,
    prediction_path: Path | None = None,
    min_length_px: float = 0.0,
    snap_px: float = 8.0,
) -> None:
    if min_length_px < 0 or snap_px < 0:
        raise ValueError("min_length_px and snap_px must be non-negative")
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(image_path)
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    prediction = json.loads(prediction_path.read_text(encoding="utf-8")) if prediction_path else {}
    candidates = []
    for line in prediction.get("lines", []):
        p1, p2 = tuple(line["p1_px"]), tuple(line["p2_px"])
        if math.dist(p1, p2) >= min_length_px:
            candidates.extend((p1, p2))
    pending: list[tuple[int, int]] = []
    lines = [(tuple(line["p1_px"]), tuple(line["p2_px"])) for line in annotation.get("expected_lines", [])]
    window = "CAD Agent benchmark annotation"

    def redraw() -> None:
        canvas = image.copy()
        for line in prediction.get("lines", []):
            p1, p2 = tuple(line["p1_px"]), tuple(line["p2_px"])
            if math.dist(p1, p2) >= min_length_px:
                cv2.line(canvas, p1, p2, (0, 0, 200), 1, cv2.LINE_AA)
        for p1, p2 in lines:
            cv2.line(canvas, p1, p2, (0, 190, 0), 2, cv2.LINE_AA)
        if pending:
            cv2.circle(canvas, pending[0], 4, (255, 0, 0), -1)
        label = "Click endpoints | U undo | S save | A annotate+save | Q quit"
        cv2.putText(canvas, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(window, canvas)

    def on_click(event, x, y, _flags, _param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        pending.append(snap_point((x, y), candidates, snap_px))
        if len(pending) == 2:
            lines.append((pending[0], pending[1]))
            pending.clear()
        redraw()

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_click)
    redraw()
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("u") and lines:
            lines.pop()
            pending.clear()
            redraw()
        if key in (ord("s"), ord("a")):
            annotation["expected_lines"] = []
            add_lines(annotation, lines, mark_annotated=(key == ord("a")))
            save_annotation(annotation_path, annotation)
            redraw()
    cv2.destroyWindow(window)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--prediction", type=Path, help="Optional raw geometry JSON to show in red")
    parser.add_argument("--min-length-px", type=float, default=0.0)
    parser.add_argument("--snap-px", type=float, default=8.0, help="Snap clicks to nearby prediction endpoints; 0 disables")
    args = parser.parse_args()
    annotate_interactively(args.image, args.annotation, args.prediction, args.min_length_px, args.snap_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())