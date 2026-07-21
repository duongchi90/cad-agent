"""Parse drawing-scale labels and convert them for a rendered page."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional


_SCALE_RE = re.compile(r"(?:TL|TY\s*LE|TILE)\s*[-:]?\s*1\s*:\s*(\d+)", re.IGNORECASE)


def parse_scale_label(content: str) -> Optional[int]:
    """Return the denominator from an OCR scale label, or ``None``."""
    normalized = unicodedata.normalize("NFD", content).encode("ascii", "ignore").decode()
    match = _SCALE_RE.search(normalized)
    return int(match.group(1)) if match else None


def mm_per_px_for_scale(denominator: int, dpi: int) -> float:
    """Convert a drawing scale denominator into millimetres per render pixel."""
    if denominator <= 0 or dpi <= 0:
        raise ValueError("denominator and dpi must be positive")
    return denominator * 25.4 / dpi


def _bbox_distance(a: tuple, b: tuple) -> float:
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _line_regions(lines: Iterable[object], gap_px: float) -> list[tuple]:
    """Cluster touching/nearby line bboxes into conservative drawing regions."""
    regions: list[list[float]] = []
    for line in lines:
        bbox = list(line.bbox_px)
        joined = [region for region in regions if _bbox_distance(bbox, region) <= gap_px]
        if not joined:
            regions.append(bbox)
            continue
        merged = [min([bbox[0]] + [region[0] for region in joined]),
                  min([bbox[1]] + [region[1] for region in joined]),
                  max([bbox[2]] + [region[2] for region in joined]),
                  max([bbox[3]] + [region[3] for region in joined])]
        regions = [region for region in regions if region not in joined]
        regions.append(merged)
    return [tuple(region) for region in regions]


def detect_view_candidates(raw_texts: Iterable[object], raw_lines: Iterable[object],
                           image_width: int, image_height: int, dpi: int,
                           max_label_distance_mm: float = 21.1666666667,
                           region_gap_mm: float = 5.2916666667) -> list[dict]:
    """Associate every scale label with one unambiguous nearby line region."""
    lines = list(raw_lines)
    texts = list(raw_texts)
    px_per_mm = dpi / 25.4
    regions = _line_regions(lines, gap_px=region_gap_mm * px_per_mm)
    max_label_distance_px = max_label_distance_mm * px_per_mm
    candidates = []
    for text in texts:
        denominator = parse_scale_label(text.content)
        if denominator is None:
            continue
        distances = sorted((_bbox_distance(text.bbox_px, region), region) for region in regions)
        if not distances or distances[0][0] > max_label_distance_px:
            continue
        if len(distances) > 1 and abs(distances[0][0] - distances[1][0]) < 1e-6:
            continue
        region = distances[0][1]
        candidate = {
            "source_text_id": text.id,
            "bbox_px": list(text.bbox_px),
            "region_bbox_px": list(region),
            "scale_denominator": denominator,
            "pixel_to_unit_scale": mm_per_px_for_scale(denominator, dpi),
            "status": "needs_verification",
        }
        region_area = max(0.0, (region[2] - region[0]) * (region[3] - region[1]))
        page_area = max(1.0, image_width * image_height)
        # A page-spanning cluster is usually a border/title-block bridge, not a
        # single view.  Its dimensions are not safe evidence for this label.
        if region_area / page_area >= 0.80:
            candidates.append(candidate)
            continue
        dimensions = [item for item in texts if item.semantic_role == "dimension_value"
                      and item.parsed_value is not None and item.parsed_value > 0
                      and item.bbox_px[0] >= region[0] and item.bbox_px[1] >= region[1]
                      and item.bbox_px[2] <= region[2] and item.bbox_px[3] <= region[3]]
        region_lines = [line for line in lines if _bbox_distance(line.bbox_px, region) == 0]
        evidence = []
        for dimension in dimensions:
            matching_line = min(region_lines,
                                key=lambda line: abs(dimension.parsed_value - line.length_px() * candidate["pixel_to_unit_scale"]),
                                default=None)
            if matching_line is not None:
                measured = matching_line.length_px() * candidate["pixel_to_unit_scale"]
                evidence.append((abs(dimension.parsed_value - measured) / dimension.parsed_value * 100.0,
                                 dimension, matching_line, measured))
        if evidence:
            delta, dimension, line, measured = min(evidence, key=lambda item: item[0])
            candidate["dimension_evidence"] = {
                "text_primitive_id": dimension.id,
                "geometry_primitive_id": line.id,
                "text_value": dimension.parsed_value,
                "geometry_measured_length": round(measured, 3),
                "delta_percent": round(delta, 4),
            }
        candidates.append(candidate)
    return candidates
