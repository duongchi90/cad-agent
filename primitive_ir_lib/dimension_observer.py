"""Offline dimension cluster detection and fail-closed observation policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re

import cv2
import numpy as np

from primitive_ir_lib.dimension_geometry import (
    DimensionGeometryEvidence,
    associate_arrow_tip_to_circles,
    detect_dimension_geometry,
    detect_dimension_geometry_regions,
)
from primitive_ir_lib.dimension_symbols import ParsedDimensionText, parse_dimension_text
from primitive_ir_lib.text_extraction import RawText, detect_text_candidate_rois

Bbox = tuple[int, int, int, int]
OcrReader = Callable[[np.ndarray], Sequence[RawText]]

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ROLES = {"DRIVING", "REFERENCE", "DERIVED"}
_OCR_ROTATIONS = (0.0, 90.0, -90.0, 180.0)


class DimensionObserverError(ValueError):
    """Raised when dimension observation or coverage accounting is unsafe."""


@dataclass(frozen=True)
class DimensionCluster:
    cluster_id: str
    bbox_px: Bbox
    member_boxes: tuple[Bbox, ...]


@dataclass(frozen=True)
class DimensionDisposition:
    cluster_id: str
    disposition: str
    observation: Mapping[str, object] | None
    reasons: tuple[str, ...]


def _validate_identifier(value: str, field: str) -> None:
    if _ID_RE.fullmatch(value) is None:
        raise DimensionObserverError(f"{field} has invalid identifier")


def _validate_hash(value: str, field: str) -> None:
    if _HASH_RE.fullmatch(value) is None:
        raise DimensionObserverError(f"{field} must be a lowercase SHA-256")


def _clip_bbox(bbox: Bbox, *, width: int, height: int) -> Bbox:
    x0, y0, x1, y1 = bbox
    clipped = (max(0, x0), max(0, y0), min(width, x1), min(height, y1))
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        raise DimensionObserverError("cluster bbox is outside the image")
    return clipped


def _merge_boxes(boxes: Sequence[Bbox]) -> list[Bbox]:
    merged: list[Bbox] = []
    for candidate in sorted(boxes, key=lambda box: (box[1], box[0], box[3], box[2])):
        x0, y0, x1, y1 = candidate
        for index, current in enumerate(merged):
            cx0, cy0, cx1, cy1 = current
            overlaps = not (x1 < cx0 - 8 or x0 > cx1 + 8 or y1 < cy0 - 8 or y0 > cy1 + 8)
            if overlaps:
                merged[index] = (min(x0, cx0), min(y0, cy0), max(x1, cx1), max(y1, cy1))
                break
        else:
            merged.append(candidate)
    return sorted(merged, key=lambda box: (box[1], box[0], box[3], box[2]))


def _rotate_crop(crop: np.ndarray, rotation_deg: float) -> np.ndarray:
    if rotation_deg == 0.0:
        return crop
    if rotation_deg == 90.0:
        return cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
    if rotation_deg == -90.0:
        return cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if rotation_deg == 180.0:
        return cv2.rotate(crop, cv2.ROTATE_180)
    raise DimensionObserverError("unsupported OCR rotation")


def _map_rotated_bbox(bbox: Bbox, *, width: int, height: int, rotation_deg: float) -> Bbox:
    x0, y0, x1, y1 = bbox
    corners = ((x0, y0), (x1, y0), (x0, y1), (x1, y1))
    if rotation_deg == 0.0:
        mapped = corners
    elif rotation_deg == 90.0:
        mapped = tuple((y, height - x) for x, y in corners)
    elif rotation_deg == -90.0:
        mapped = tuple((width - y, x) for x, y in corners)
    elif rotation_deg == 180.0:
        mapped = tuple((width - x, height - y) for x, y in corners)
    else:
        raise DimensionObserverError("unsupported OCR rotation")
    mapped_x = [point[0] for point in mapped]
    mapped_y = [point[1] for point in mapped]
    return (
        max(0, min(width, math.floor(min(mapped_x)))),
        max(0, min(height, math.floor(min(mapped_y)))),
        max(0, min(width, math.ceil(max(mapped_x)))),
        max(0, min(height, math.ceil(max(mapped_y)))),
    )


def _read_multi_angle_ocr(
    crop: np.ndarray,
    *,
    ocr_reader: OcrReader,
) -> tuple[list[RawText], list[dict[str, object]]]:
    height, width = crop.shape[:2]
    raw_texts: list[RawText] = []
    evidence: list[dict[str, object]] = []
    for rotation_deg in _OCR_ROTATIONS:
        rotated_texts = ocr_reader(_rotate_crop(crop, rotation_deg))
        for raw_text in rotated_texts:
            mapped_bbox = _map_rotated_bbox(
                raw_text.bbox_px,
                width=width,
                height=height,
                rotation_deg=rotation_deg,
            )
            normalized = RawText(
                id=raw_text.id,
                content=raw_text.content,
                bbox_px=mapped_bbox,
                rotation_deg=rotation_deg,
                confidence=raw_text.confidence,
                source=raw_text.source,
                parsed_value=raw_text.parsed_value,
                semantic_role=raw_text.semantic_role,
            )
            raw_texts.append(normalized)
            evidence.append({
                "id": f"{raw_text.id}-rot{int(rotation_deg)}",
                "content": raw_text.content,
                "bbox": [float(value) for value in mapped_bbox],
                "rotation_deg": rotation_deg,
                "confidence": float(raw_text.confidence),
                "source": raw_text.source,
            })
    return raw_texts, evidence


def detect_dimension_clusters(image_bgr: np.ndarray) -> list[DimensionCluster]:
    """Return stable reading-order candidate clusters without running OCR."""
    if not isinstance(image_bgr, np.ndarray) or image_bgr.ndim not in {2, 3}:
        raise DimensionObserverError("image_bgr must be a grayscale or BGR image")
    if image_bgr.size == 0:
        return []
    text_boxes = detect_text_candidate_rois(image_bgr)
    candidate_boxes = [*text_boxes, *detect_dimension_geometry_regions(image_bgr)]
    boxes = _merge_boxes(candidate_boxes)
    return [
        DimensionCluster(
            cluster_id=f"DIMCLUSTER-{index:03d}",
            bbox_px=box,
            member_boxes=(box,),
        )
        for index, box in enumerate(boxes, start=1)
    ]


def _crop_sha256(crop_bgr: np.ndarray) -> str:
    success, encoded = cv2.imencode(".png", crop_bgr)
    if not success:
        raise DimensionObserverError("cannot encode dimension crop")
    return hashlib.sha256(encoded.tobytes()).hexdigest()


def _raw_text_candidates(raw_texts: Sequence[RawText]) -> list[str]:
    candidates: list[str] = []
    for raw_text in raw_texts:
        content = raw_text.content.strip()
        if content and content not in candidates:
            candidates.append(content)
    return candidates


def _select_parsed_candidate(
    raw_texts: Sequence[RawText], *, default_unit: str | None
) -> tuple[ParsedDimensionText | None, list[ParsedDimensionText], tuple[str, ...]]:
    parsed_candidates: list[tuple[RawText, ParsedDimensionText]] = []
    reasons: list[str] = []
    for raw_text in raw_texts:
        if raw_text.rotation_deg not in {0.0, 90.0, -90.0, 180.0}:
            reasons.append("unsupported_ocr_rotation")
            continue
        parsed = parse_dimension_text(raw_text.content, default_unit=default_unit)
        parsed_candidates.append((raw_text, parsed))
    readable = [(raw, parsed) for raw, parsed in parsed_candidates if parsed.value is not None]
    if not readable:
        return None, [parsed for _, parsed in parsed_candidates], tuple(sorted(set(reasons)))

    ranked = sorted(readable, key=lambda item: (item[0].confidence, item[1].confidence), reverse=True)
    values = [parsed.value for _, parsed in readable]
    assert all(value is not None for value in values)
    spread = max(values) - min(values)
    if spread > max(1e-6, abs(ranked[0][1].value or 0.0) * 0.001):
        if len(ranked) > 1 and ranked[0][0].confidence - ranked[1][0].confidence < 0.15:
            reasons.append("conflicting_text_candidates")
            return None, [parsed for _, parsed in parsed_candidates], tuple(sorted(set(reasons)))
        reasons.append("lower_confidence_text_candidate_discarded")
    return ranked[0][1], [parsed for _, parsed in parsed_candidates], tuple(sorted(set(reasons)))


def _line_orientation(geometry: DimensionGeometryEvidence) -> tuple[float, float] | None:
    if geometry.dimension_line is None:
        return None
    first, second = geometry.dimension_line
    vector = (second[0] - first[0], second[1] - first[1])
    length = math.hypot(*vector)
    if length == 0:
        return None
    return vector[0] / length, vector[1] / length


def _outer_extension_points(
    geometry: DimensionGeometryEvidence,
) -> list[tuple[float, float]]:
    if geometry.dimension_line is None:
        return []
    line = geometry.dimension_line
    points: list[tuple[float, float]] = []
    for extension in geometry.extension_lines:
        candidate = max(extension, key=lambda point: math.hypot(point[0] - line[0][0], point[1] - line[0][1]))
        points.append(candidate)
    return points


def _attachment_candidates(
    geometry: DimensionGeometryEvidence,
    *,
    semantic_anchors: Sequence[Mapping[str, object]],
    view_id: str,
) -> list[dict[str, object]]:
    if len(geometry.extension_lines) < 2 or len(semantic_anchors) < 2:
        return []
    endpoints = _outer_extension_points(geometry)
    orientation = _line_orientation(geometry)
    if orientation is None or len(endpoints) < 2:
        return []
    valid_anchors: list[Mapping[str, object]] = []
    for anchor in semantic_anchors:
        point = anchor.get("point_px")
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        if not isinstance(anchor.get("id"), str) or not isinstance(anchor.get("type"), str):
            continue
        valid_anchors.append(anchor)

    candidates: list[dict[str, object]] = []
    for first_index, first in enumerate(valid_anchors):
        for second_index, second in enumerate(valid_anchors):
            if first_index == second_index:
                continue
            first_point = (float(first["point_px"][0]), float(first["point_px"][1]))
            second_point = (float(second["point_px"][0]), float(second["point_px"][1]))
            distances = [
                math.hypot(first_point[0] - endpoints[0][0], first_point[1] - endpoints[0][1]),
                math.hypot(second_point[0] - endpoints[1][0], second_point[1] - endpoints[1][1]),
            ]
            proximity = math.exp(-sum(distances) / 20.0)
            anchor_vector = (second_point[0] - first_point[0], second_point[1] - first_point[1])
            anchor_length = math.hypot(*anchor_vector)
            if anchor_length == 0:
                continue
            orientation_compatibility = abs(
                orientation[0] * anchor_vector[0] / anchor_length
                + orientation[1] * anchor_vector[1] / anchor_length
            )
            view_membership = float(first.get("view_id") == view_id and second.get("view_id") == view_id)
            confidence = (float(first.get("confidence", 0.0)) + float(second.get("confidence", 0.0))) / 2.0
            score = 0.45 * proximity + 0.25 * orientation_compatibility + 0.20 * view_membership + 0.10 * confidence
            candidates.append({
                "from_ref": {"type": first["type"], "id": first["id"]},
                "to_ref": {"type": second["type"], "id": second["id"]},
                "confidence": round(min(1.0, score), 3),
                "evidence": ["extension-line-0", "extension-line-1"],
            })
    return sorted(
        candidates,
        key=lambda candidate: (
            -float(candidate["confidence"]),
            str(candidate["from_ref"]["id"]),
            str(candidate["to_ref"]["id"]),
        ),
    )


def _geometry_payload(geometry: DimensionGeometryEvidence) -> dict[str, object]:
    def segment_payload(segment: tuple[tuple[float, float], tuple[float, float]]) -> list[list[float]]:
        return [[float(point[0]), float(point[1])] for point in segment]

    return {
        "dimension_line": segment_payload(geometry.dimension_line) if geometry.dimension_line else None,
        "extension_lines": [segment_payload(segment) for segment in geometry.extension_lines],
        "arrow_points": [[float(point[0]), float(point[1])] for point in geometry.arrow_points],
        "leader_lines": [segment_payload(segment) for segment in geometry.leader_lines],
    }


def _observation_sha256(observation: Mapping[str, object]) -> str:
    without_provenance = dict(observation)
    without_provenance.pop("provenance", None)
    encoded = json.dumps(without_provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


_SOURCE_DRAWING_REF_RE = re.compile(r"^page(?P<page>\d+)-drawing(?P<index>\d+)$")
# Tolerates only source-coordinate serialization noise (well below 0.001 pt).
_SOURCE_GEOMETRY_EPS_PT = 1e-4


def _finite_point2(value: object) -> tuple[float, float] | None:
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
        or not all(math.isfinite(item) for item in value)
    ):
        return None
    return float(value[0]), float(value[1])


def _finite_bounds4(
    value: object, *, allow_degenerate: bool = False
) -> tuple[float, float, float, float] | None:
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 4
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
        or not all(math.isfinite(item) for item in value)
    ):
        return None
    bounds = tuple(float(item) for item in value)
    if (
        bounds[0] > bounds[2]
        or bounds[1] > bounds[3]
        or (not allow_degenerate and (bounds[0] == bounds[2] or bounds[1] == bounds[3]))
    ):
        return None
    return bounds


def _source_drawing_index(
    inventory: Mapping[str, object], *, source_sha256: str, page_index: int
) -> dict[str, Mapping[str, object]] | None:
    if (
        not isinstance(inventory, Mapping)
        or inventory.get("source_sha256") != source_sha256
        or inventory.get("page_index") != page_index
        or isinstance(inventory.get("page_index"), bool)
        or inventory.get("complete") is not True
        or not isinstance(inventory.get("drawings"), (tuple, list))
        or not inventory.get("drawings")
    ):
        return None
    indexed: dict[str, Mapping[str, object]] = {}
    seen_indices: set[int] = set()
    for drawing in inventory["drawings"]:
        if not isinstance(drawing, Mapping):
            return None
        reference = drawing.get("ref")
        match = _SOURCE_DRAWING_REF_RE.fullmatch(reference) if isinstance(reference, str) else None
        if (
            match is None
            or int(match.group("page")) != page_index
            or reference != f"page{page_index}-drawing{int(match.group('index'))}"
            or int(match.group("index")) in seen_indices
            or reference in indexed
            or (
                drawing.get("bounds_pt") is not None
                and _finite_bounds4(drawing.get("bounds_pt"), allow_degenerate=True) is None
            )
            or not isinstance(drawing.get("items"), (tuple, list))
        ):
            return None
        indexed[reference] = drawing
        seen_indices.add(int(match.group("index")))
    return indexed


def _line_items(drawing: Mapping[str, object]) -> list[tuple[tuple[float, float], tuple[float, float]]] | None:
    items = drawing.get("items")
    if not isinstance(items, (tuple, list)) or not items:
        return None
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for item in items:
        if not isinstance(item, (tuple, list)) or len(item) != 3 or item[0] != "l":
            return None
        first, second = _finite_point2(item[1]), _finite_point2(item[2])
        if first is None or second is None or math.dist(first, second) <= _SOURCE_GEOMETRY_EPS_PT:
            return None
        segments.append((first, second))
    return segments


def _drawing_polyline(
    references: object, drawings: Mapping[str, Mapping[str, object]]
) -> list[tuple[float, float]] | None:
    if (
        not isinstance(references, (tuple, list))
        or not references
        or any(not isinstance(reference, str) for reference in references)
        or len(set(references)) != len(references)
    ):
        return None
    points: list[tuple[float, float]] = []
    for reference in references:
        drawing = drawings.get(reference)
        if drawing is None or drawing.get("type") != "s":
            return None
        segments = _line_items(drawing)
        if segments is None:
            return None
        for first, second in segments:
            if points and math.dist(points[-1], first) > _SOURCE_GEOMETRY_EPS_PT:
                return None
            if not points:
                points.append(first)
            points.append(second)
    return points


def _same_polyline(
    first: Sequence[tuple[float, float]], second: Sequence[tuple[float, float]]
) -> bool:
    if len(first) != len(second):
        return False
    same = all(math.dist(a, b) <= _SOURCE_GEOMETRY_EPS_PT for a, b in zip(first, second))
    reverse = all(math.dist(a, b) <= _SOURCE_GEOMETRY_EPS_PT for a, b in zip(first, reversed(second)))
    return same or reverse


def _triangle_tip_and_base(
    drawing: Mapping[str, object], *, leader_base_anchor: tuple[float, float]
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if drawing.get("type") not in {"f", "fs"} or drawing.get("fill") is None:
        return None
    segments = _line_items(drawing)
    if segments is None or len(segments) != 3:
        return None
    vertices: list[tuple[float, float]] = []
    edges: set[frozenset[tuple[float, float]]] = set()
    for first, second in segments:
        for point in (first, second):
            if not any(math.dist(point, existing) <= _SOURCE_GEOMETRY_EPS_PT for existing in vertices):
                vertices.append(point)
        edges.add(frozenset((first, second)))
    if len(vertices) != 3 or len(edges) != 3:
        return None
    area_twice = abs(
        (vertices[1][0] - vertices[0][0]) * (vertices[2][1] - vertices[0][1])
        - (vertices[1][1] - vertices[0][1]) * (vertices[2][0] - vertices[0][0])
    )
    if area_twice <= _SOURCE_GEOMETRY_EPS_PT:
        return None
    base_edges = [
        (first, second)
        for first, second in segments
        if math.dist(
            ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0),
            leader_base_anchor,
        ) <= _SOURCE_GEOMETRY_EPS_PT
    ]
    if len(base_edges) != 1:
        return None
    base_first, base_second = base_edges[0]
    tip_candidates = [
        point for point in vertices
        if math.dist(point, base_first) > _SOURCE_GEOMETRY_EPS_PT
        and math.dist(point, base_second) > _SOURCE_GEOMETRY_EPS_PT
    ]
    if len(tip_candidates) != 1:
        return None
    tip = tip_candidates[0]
    midpoint = ((base_first[0] + base_second[0]) / 2.0, (base_first[1] + base_second[1]) / 2.0)
    return tip, midpoint


def _closed_circle_contour_supports(
    references: object,
    drawings: Mapping[str, Mapping[str, object]],
    *,
    center: tuple[float, float],
    radius: float,
    fit_bound: float,
) -> bool:
    points = _drawing_polyline(references, drawings)
    if points is None or len(points) < 4 or math.dist(points[0], points[-1]) > _SOURCE_GEOMETRY_EPS_PT:
        return False
    for first, second in zip(points, points[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length_squared = dx * dx + dy * dy
        projection = ((center[0] - first[0]) * dx + (center[1] - first[1]) * dy) / length_squared
        projection = max(0.0, min(1.0, projection))
        nearest = (first[0] + projection * dx, first[1] + projection * dy)
        minimum_distance = math.dist(center, nearest)
        maximum_distance = max(math.dist(center, first), math.dist(center, second))
        if max(abs(minimum_distance - radius), abs(maximum_distance - radius)) > fit_bound:
            return False
    return True


def observe_radial_leader_attachment(
    *,
    source_sha256: str,
    page_index: int,
    extraction_complete: bool,
    source_drawing_inventory: Mapping[str, object],
    view: Mapping[str, object],
    text_spans: Sequence[Mapping[str, object]],
    leader_witnesses: Sequence[Mapping[str, object]],
    circle_candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return a fail-closed source association for one evidenced radial callout.

    All coordinates are in PDF points. The complete drawing inventory is a
    trusted hash-bound extraction input supplied by its existing owner; this
    observer checks its internal references but does not authenticate arbitrary
    caller-created inventory data against PDF bytes. This function records an
    association only and never changes geometry.
    """
    unresolved: dict[str, object] = {
        "kind": "RADIAL_LEADER",
        "status": "UNRESOLVED",
        "source_ref": {"pdf_sha256": source_sha256, "page_index": page_index},
        "target_ref": None,
        "geometry_consumed": False,
        "evidence_limits": ["source_drawing_inventory_is_trusted_extraction_input_not_authenticated_here"],
    }
    if (
        not isinstance(source_sha256, str)
        or _HASH_RE.fullmatch(source_sha256) is None
        or isinstance(page_index, bool)
        or not isinstance(page_index, int)
        or page_index < 0
        or extraction_complete is not True
        or not isinstance(source_drawing_inventory, Mapping)
        or not isinstance(view, Mapping)
        or view.get("source_sha256") != source_sha256
        or view.get("page_index") != page_index
        or not isinstance(view.get("view_id"), str)
        or not view.get("view_id")
        or not isinstance(view.get("derivation"), str)
        or not view.get("derivation", "").strip()
        or not isinstance(view.get("source_drawing_refs"), (tuple, list))
        or not view.get("source_drawing_refs")
    ):
        return unresolved

    source_drawings = _source_drawing_index(
        source_drawing_inventory, source_sha256=source_sha256, page_index=page_index
    )
    if source_drawings is None:
        return unresolved

    bounds = view.get("bounds_pt")
    if (
        not isinstance(bounds, (tuple, list))
        or len(bounds) != 4
        or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in bounds)
        or bounds[2] <= bounds[0]
        or bounds[3] <= bounds[1]
    ):
        return unresolved
    source_drawing_refs = view.get("source_drawing_refs")
    drawing_bounds = view.get("source_drawing_bounds_pt")
    if (
        not isinstance(source_drawing_refs, (tuple, list))
        or not source_drawing_refs
        or any(
            not isinstance(ref, str)
            or _SOURCE_DRAWING_REF_RE.fullmatch(ref) is None
            or ref not in source_drawings
            for ref in source_drawing_refs
        )
        or len(set(source_drawing_refs)) != len(source_drawing_refs)
        or not isinstance(drawing_bounds, Mapping)
        or set(drawing_bounds) != set(source_drawing_refs)
    ):
        return unresolved
    derived_boxes = list(drawing_bounds.values())
    if any(
        not isinstance(box, (tuple, list))
        or len(box) != 4
        or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in box)
        or box[2] <= box[0]
        or box[3] <= box[1]
        for box in derived_boxes
    ):
        return unresolved
    if any(
        _finite_bounds4(drawing_bounds[reference]) is None
        or _finite_bounds4(source_drawings[reference].get("bounds_pt")) is None
        or any(
            not math.isclose(actual, expected, rel_tol=0.0, abs_tol=_SOURCE_GEOMETRY_EPS_PT)
            for actual, expected in zip(
                _finite_bounds4(drawing_bounds[reference]) or (),
                _finite_bounds4(source_drawings[reference].get("bounds_pt")) or (),
            )
        )
        for reference in source_drawing_refs
    ):
        return unresolved
    derived_bounds = [
        min(float(box[0]) for box in derived_boxes),
        min(float(box[1]) for box in derived_boxes),
        max(float(box[2]) for box in derived_boxes),
        max(float(box[3]) for box in derived_boxes),
    ]
    if not all(
        math.isclose(float(supplied), derived, rel_tol=0.0, abs_tol=1e-6)
        for supplied, derived in zip(bounds, derived_bounds)
    ):
        return unresolved
    view_id = str(view["view_id"])

    def source_ref(value: object, kind: str) -> bool:
        if not isinstance(value, str):
            return False
        if kind == "text":
            return value.startswith(f"page{page_index}:")
        match = _SOURCE_DRAWING_REF_RE.fullmatch(value)
        return match is not None and int(match.group("page")) == page_index and value in source_drawings

    def valid_bbox(value: object) -> bool:
        return (
            isinstance(value, (tuple, list))
            and len(value) == 4
            and all(isinstance(item, (int, float)) and math.isfinite(item) for item in value)
            and value[0] < value[2]
            and value[1] < value[3]
        )

    def inside_bbox(value: object) -> bool:
        return (
            valid_bbox(value)
            and bounds[0] <= value[0] < value[2] <= bounds[2]
            and bounds[1] <= value[1] < value[3] <= bounds[3]
        )

    def inside_point(value: object) -> bool:
        return (
            isinstance(value, (tuple, list))
            and len(value) == 2
            and all(isinstance(item, (int, float)) and math.isfinite(item) for item in value)
            and bounds[0] <= value[0] <= bounds[2]
            and bounds[1] <= value[1] <= bounds[3]
        )

    matching_texts: list[Mapping[str, object]] = []
    for span in text_spans:
        if (
            not isinstance(span, Mapping)
            or span.get("source_sha256") != source_sha256
            or span.get("page_index") != page_index
            or not source_ref(span.get("id"), "text")
            or not valid_bbox(span.get("bbox_pt"))
        ):
            return unresolved
        parsed = parse_dimension_text(str(span.get("text", "")))
        if parsed.kind_hint in {"RADIUS", "DIAMETER"}:
            matching_texts.append(span)
    if len(matching_texts) != 1:
        return unresolved
    text_span = matching_texts[0]
    if parse_dimension_text(str(text_span.get("text", ""))).kind_hint != "RADIUS":
        return unresolved
    tx0, ty0, tx1, ty1 = (float(value) for value in text_span["bbox_pt"])

    def segment_intersects_text(first: Sequence[object], second: Sequence[object]) -> bool:
        if len(first) != 2 or len(second) != 2:
            return False
        x0, y0 = float(first[0]), float(first[1])
        dx, dy = float(second[0]) - x0, float(second[1]) - y0
        low, high = 0.0, 1.0
        for p, q in ((-dx, x0 - tx0), (dx, tx1 - x0), (-dy, y0 - ty0), (dy, ty1 - y0)):
            if p == 0:
                if q < 0:
                    return False
                continue
            t = q / p
            if p < 0:
                low = max(low, t)
            else:
                high = min(high, t)
            if low > high:
                return False
        return True

    matching_leaders: list[Mapping[str, object]] = []
    for witness in leader_witnesses:
        if (
            not isinstance(witness, Mapping)
            or witness.get("source_sha256") != source_sha256
            or witness.get("page_index") != page_index
            or witness.get("view_id") != view_id
            or not isinstance(witness.get("ordered_path_refs"), (tuple, list))
            or not witness.get("ordered_path_refs")
            or any(not source_ref(ref, "drawing") for ref in witness.get("ordered_path_refs", ()))
            or not isinstance(witness.get("points_pt"), (tuple, list))
            or len(witness.get("points_pt", ())) < 2
            or not source_ref(witness.get("arrowhead_ref"), "drawing")
            or not isinstance(witness.get("arrowhead_base_pt"), (tuple, list))
            or len(witness.get("arrowhead_base_pt", ())) != 2
        ):
            return unresolved
        points = witness["points_pt"]
        if any(
            not isinstance(point, (tuple, list))
            or len(point) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in point)
            for point in points
        ):
            return unresolved
        if any(segment_intersects_text(first, second) for first, second in zip(points, points[1:])):
            matching_leaders.append(witness)
    if len(matching_leaders) != 1:
        return unresolved
    witness = matching_leaders[0]

    source_leader_path = _drawing_polyline(witness["ordered_path_refs"], source_drawings)
    declared_leader_path = [_finite_point2(point) for point in witness["points_pt"]]
    if (
        source_leader_path is None
        or any(point is None for point in declared_leader_path)
        or not _same_polyline(source_leader_path, declared_leader_path)  # type: ignore[arg-type]
    ):
        return unresolved

    declared_tip = _finite_point2(witness.get("arrow_tip_pt"))
    declared_base = _finite_point2(witness.get("arrowhead_base_pt"))
    arrowhead = (
        _triangle_tip_and_base(
            source_drawings[witness["arrowhead_ref"]], leader_base_anchor=declared_base
        )
        if declared_base is not None
        and min(math.dist(declared_base, endpoint) for endpoint in (source_leader_path[0], source_leader_path[-1]))
        <= _SOURCE_GEOMETRY_EPS_PT
        else None
    )
    if (
        arrowhead is None
        or declared_tip is None
        or declared_base is None
        or math.dist(declared_tip, arrowhead[0]) > _SOURCE_GEOMETRY_EPS_PT
        or math.dist(declared_base, arrowhead[1]) > _SOURCE_GEOMETRY_EPS_PT
    ):
        return unresolved

    uncertainty = witness.get("uncertainty_pt")
    required_terms = ("arrow_tip", "target_contour", "transform", "fit")
    if (
        not isinstance(uncertainty, Mapping)
        or any(
            isinstance(uncertainty.get(key), bool)
            or not isinstance(uncertainty.get(key), (int, float))
            or not math.isfinite(uncertainty[key])
            or uncertainty[key] < 0
            for key in required_terms
        )
    ):
        return unresolved
    contact_bound = sum(float(uncertainty[key]) for key in required_terms if key != "fit")
    arrowhead_base = witness["arrowhead_base_pt"]
    if (
        not all(isinstance(value, (int, float)) and math.isfinite(value) for value in arrowhead_base)
        or not inside_point(arrowhead_base)
        or min(
            math.hypot(float(point[0]) - float(arrowhead_base[0]), float(point[1]) - float(arrowhead_base[1]))
            for point in (witness["points_pt"][0], witness["points_pt"][-1])
        ) > float(uncertainty["arrow_tip"])
    ):
        return unresolved
    arrow_tip = witness.get("arrow_tip_pt")
    if (
        not isinstance(arrow_tip, (tuple, list))
        or len(arrow_tip) != 2
        or _finite_point2(arrow_tip) is None
        or math.dist((float(arrow_tip[0]), float(arrow_tip[1])), arrowhead[0]) > _SOURCE_GEOMETRY_EPS_PT
    ):
        return unresolved

    geometry_candidates: list[dict[str, object]] = []
    refs_by_id: dict[str, Mapping[str, object]] = {}
    for circle in circle_candidates:
        if not isinstance(circle, Mapping):
            return unresolved
        if circle.get("source_sha256") != source_sha256 or circle.get("page_index") != page_index:
            return unresolved
        if circle.get("view_id") != view_id:
            continue
        if (
            not isinstance(circle.get("id"), str)
            or not circle.get("id")
            or not inside_bbox(circle.get("bounds_pt"))
            or not isinstance(circle.get("source_path_refs"), (tuple, list))
            or not circle.get("source_path_refs")
            or any(not source_ref(ref, "drawing") for ref in circle.get("source_path_refs", ()))
            or not isinstance(circle.get("center_pt"), (tuple, list))
            or len(circle["center_pt"]) != 2
            or not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in circle["center_pt"]
            )
            or isinstance(circle.get("radius_pt"), bool)
            or not isinstance(circle.get("radius_pt"), (int, float))
            or not math.isfinite(circle["radius_pt"])
            or circle["radius_pt"] <= 0
            or circle["center_pt"][0] - circle["radius_pt"] < circle["bounds_pt"][0]
            or circle["center_pt"][1] - circle["radius_pt"] < circle["bounds_pt"][1]
            or circle["center_pt"][0] + circle["radius_pt"] > circle["bounds_pt"][2]
            or circle["center_pt"][1] + circle["radius_pt"] > circle["bounds_pt"][3]
        ):
            return unresolved
        circle_center = _finite_point2(circle.get("center_pt"))
        if circle_center is None or not _closed_circle_contour_supports(
            circle.get("source_path_refs"),
            source_drawings,
            center=circle_center,
            radius=float(circle["radius_pt"]),
            fit_bound=float(uncertainty["fit"]),
        ):
            return unresolved
        identifier = str(circle["id"])
        if identifier in refs_by_id:
            # Association returns IDs; duplicate IDs could bind another circle's source ref.
            return unresolved
        refs_by_id[identifier] = circle
        geometry_candidates.append({
            "id": identifier,
            "center": circle["center_pt"],
            "radius": circle["radius_pt"],
        })
    association = associate_arrow_tip_to_circles(
        arrow_tip=(float(arrow_tip[0]), float(arrow_tip[1])),
        candidates=geometry_candidates,
        contact_bound=contact_bound,
    )
    unresolved.update({
        "view_ref": {
            "view_id": view_id,
            "bounds_pdf_pt": [float(value) for value in bounds],
            "derivation": view["derivation"],
        },
        "text_ref": {
            "span_id": text_span["id"],
            "raw_text": text_span["text"],
            "bbox_pdf_pt": [float(value) for value in text_span["bbox_pt"]],
        },
        "leader_ref": {
            "ordered_path_refs": list(witness["ordered_path_refs"]),
            "arrowhead_ref": witness["arrowhead_ref"],
            "arrow_tip_pdf_pt": [float(value) for value in arrow_tip],
        },
        "attachment_witness": {
            "method": "ARROW_TIP_ON_SOURCE_CONTOUR",
            "residual_pdf_pt": association["residual"],
            "uncertainty_pdf_pt": contact_bound,
        },
        "annotation_parse": {
            "designation": "RADIUS",
            "nominal": None,
            "unit": "UNRESOLVED",
            "semantic_role": "UNKNOWN",
        },
    })
    unresolved["status"] = association["status"]
    target_id = association["target_id"]
    if target_id is not None:
        target = refs_by_id[str(target_id)]
        unresolved["target_ref"] = {
            "primitive_id": target_id,
            "type": "CIRCLE",
            "geometry_fingerprint": hashlib.sha256(
                json.dumps(
                    [target["center_pt"], target["radius_pt"]],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "source_path_refs": list(target["source_path_refs"]),
        }
    return unresolved


def observe_dimension_cluster(
    image_bgr: np.ndarray,
    cluster: DimensionCluster,
    *,
    page_id: str,
    view_id: str,
    source_sha256: str,
    ocr_reader: OcrReader,
    semantic_anchors: Sequence[Mapping[str, object]] = (),
    explicit_role: str | None = None,
    default_unit: str | None = None,
    blocker_scope: Sequence[str] = (),
    critical: bool = False,
) -> DimensionDisposition:
    """Return exactly one auditable disposition for a supplied cluster."""
    _validate_identifier(page_id, "page_id")
    _validate_identifier(view_id, "view_id")
    _validate_hash(source_sha256, "source_sha256")
    if explicit_role is not None and explicit_role not in _ROLES:
        raise DimensionObserverError("explicit_role must be DRIVING, REFERENCE, or DERIVED")
    if not isinstance(critical, bool):
        raise DimensionObserverError("critical must be boolean")
    if not isinstance(cluster.cluster_id, str) or not cluster.cluster_id:
        raise DimensionObserverError("cluster_id must be non-empty")

    height, width = image_bgr.shape[:2]
    bbox = _clip_bbox(cluster.bbox_px, width=width, height=height)
    x0, y0, x1, y1 = bbox
    crop = image_bgr[y0:y1, x0:x1]
    raw_texts, ocr_evidence = _read_multi_angle_ocr(crop, ocr_reader=ocr_reader)
    parsed, parsed_candidates, parse_reasons = _select_parsed_candidate(
        raw_texts,
        default_unit=default_unit,
    )
    geometry = detect_dimension_geometry(crop)
    attachment_candidates = _attachment_candidates(
        geometry,
        semantic_anchors=semantic_anchors,
        view_id=view_id,
    )
    best_attachment = attachment_candidates[0] if attachment_candidates else None
    second_attachment = attachment_candidates[1] if len(attachment_candidates) > 1 else None
    attachment_resolved = (
        best_attachment is not None
        and float(best_attachment["confidence"]) >= 0.85
        and (
            second_attachment is None
            or float(best_attachment["confidence"]) - float(second_attachment["confidence"]) >= 0.10
        )
        and best_attachment["from_ref"] != best_attachment["to_ref"]
        and geometry.confidence >= 0.70
    )

    raw_candidates = _raw_text_candidates(raw_texts)
    if "conflicting_text_candidates" in parse_reasons:
        return DimensionDisposition(
            cluster_id=cluster.cluster_id,
            disposition="CONFLICT",
            observation=_make_observation(
                cluster=cluster,
                bbox=bbox,
                crop=crop,
                source_sha256=source_sha256,
                parsed=None,
                geometry=geometry,
                attachment_candidates=attachment_candidates,
                attachment_resolved=False,
                explicit_role=None,
                blocker_scope=blocker_scope,
                critical=critical,
                ocr_evidence=ocr_evidence,
                raw_texts=raw_texts,
                page_id=page_id,
                view_id=view_id,
                status_override="CONFLICT",
                role_override="CONFLICT",
            ),
            reasons=tuple(sorted(set(parse_reasons + ("conflicting_authoritative_readings",)))),
        )
    if parsed is None and not raw_candidates and geometry.dimension_line is None:
        return DimensionDisposition(
            cluster_id=cluster.cluster_id,
            disposition="UNRESOLVED",
            observation=_make_observation(
                cluster=cluster,
                bbox=bbox,
                crop=crop,
                source_sha256=source_sha256,
                parsed=None,
                geometry=geometry,
                attachment_candidates=attachment_candidates,
                attachment_resolved=False,
                explicit_role=explicit_role,
                blocker_scope=blocker_scope,
                critical=critical,
                ocr_evidence=ocr_evidence,
                raw_texts=raw_texts,
                page_id=page_id,
                view_id=view_id,
            ),
            reasons=tuple(sorted(set(parse_reasons + ("unreadable_observation",)))),
        )
    if parsed is None and raw_candidates and geometry.dimension_line is None and not geometry.leader_lines:
        return DimensionDisposition(
            cluster_id=cluster.cluster_id,
            disposition="NOT_A_DIMENSION",
            observation=None,
            reasons=tuple(sorted(set(parse_reasons + ("text_not_dimension_like",)))),
        )

    reasons = list(parse_reasons)
    if parsed is None:
        reasons.append("value_unresolved")
    if not attachment_resolved:
        reasons.append("attachment_unresolved")
    if explicit_role is None:
        reasons.append("role_unresolved")
    status = "CONFIRMED" if parsed is not None and attachment_resolved and explicit_role is not None else "UNRESOLVED"
    observation = _make_observation(
        cluster=cluster,
        bbox=bbox,
        crop=crop,
        source_sha256=source_sha256,
        parsed=parsed,
        geometry=geometry,
        attachment_candidates=attachment_candidates,
        attachment_resolved=attachment_resolved,
        explicit_role=explicit_role,
        blocker_scope=blocker_scope,
        critical=critical,
        ocr_evidence=ocr_evidence,
        raw_texts=raw_texts,
        page_id=page_id,
        view_id=view_id,
    )
    return DimensionDisposition(
        cluster_id=cluster.cluster_id,
        disposition=status,
        observation=observation,
        reasons=tuple(sorted(set(reasons))),
    )


def _make_observation(
    *,
    cluster: DimensionCluster,
    bbox: Bbox,
    crop: np.ndarray,
    source_sha256: str,
    parsed: ParsedDimensionText | None,
    geometry: DimensionGeometryEvidence,
    attachment_candidates: list[dict[str, object]],
    attachment_resolved: bool,
    explicit_role: str | None,
    blocker_scope: Sequence[str],
    critical: bool,
    ocr_evidence: Sequence[Mapping[str, object]],
    raw_texts: Sequence[RawText],
    page_id: str,
    view_id: str,
    status_override: str | None = None,
    role_override: str | None = None,
) -> dict[str, object]:
    raw_candidates = _raw_text_candidates(raw_texts)
    display_text = parsed.display_text if parsed is not None else (raw_candidates[0] if raw_candidates else "")
    value = parsed.value if parsed is not None else None
    unit = parsed.unit if parsed is not None else None
    status = status_override or ("CONFIRMED" if parsed is not None and attachment_resolved and explicit_role else "UNRESOLVED")
    role = role_override or (explicit_role if explicit_role is not None else "AMBIGUOUS")
    if status == "UNRESOLVED" and role not in _ROLES:
        role = "AMBIGUOUS"
    kind = (parsed.kind_hint if parsed and parsed.kind_hint else geometry.kind_hint) or "UNKNOWN"
    text_confidence = max((float(raw.confidence) for raw in raw_texts), default=0.0)
    if parsed is not None:
        text_confidence = max(text_confidence, parsed.confidence)
    attachment_confidence = float(attachment_candidates[0]["confidence"]) if attachment_candidates else 0.0
    observation: dict[str, object] = {
        "id": cluster.cluster_id,
        "display_text": display_text,
        "value": value,
        "unit": unit,
        "kind": kind,
        "role": role,
        "status": status,
        "critical": critical,
        "source_evidence": {
            "crop_id": cluster.cluster_id,
            "bbox": [float(value) for value in bbox],
            "crop_sha256": _crop_sha256(crop),
        },
        "text_confidence": min(1.0, max(0.0, text_confidence)),
        "attachment_confidence": min(1.0, max(0.0, attachment_confidence)),
        "blocker_scope": list(blocker_scope),
        "raw_text_candidates": raw_candidates,
        "ocr_evidence": [dict(item) for item in ocr_evidence],
        "symbol_text": parsed.symbol_text if parsed is not None else None,
        "tolerance": {
            "mode": parsed.tolerance_mode or "NONE" if parsed else "NONE",
            "upper": parsed.tolerance_upper if parsed else None,
            "lower": parsed.tolerance_lower if parsed else None,
            "unit": unit,
        },
        "extension_geometry": _geometry_payload(geometry),
        "attachment_candidates": attachment_candidates,
        "provenance": {
            "observer_version": "dimension-observer-1.0",
            "ocr_engine": (
                "tesseract-5.4.0.20240606"
                if any(raw.source == "text_tesseract" for raw in raw_texts)
                else "offline-ocr-reader"
            ),
            "ocr_rotations_deg": list(_OCR_ROTATIONS),
            "observation_sha256": "0" * 64,
        },
    }
    observation["provenance"]["observation_sha256"] = _observation_sha256(observation)
    del source_sha256, page_id, view_id
    return observation


def build_dimension_register(
    *,
    run_id: str,
    source_sha256: str,
    page_id: str,
    view_id: str,
    total_area_px: int,
    inspected_area_px: int,
    detected_cluster_ids: Sequence[str],
    dispositions: Sequence[DimensionDisposition],
) -> dict[str, object]:
    """Reject missing/duplicate dispositions and compute measured coverage."""
    _validate_identifier(run_id, "run_id")
    _validate_identifier(page_id, "page_id")
    _validate_identifier(view_id, "view_id")
    _validate_hash(source_sha256, "source_sha256")
    if total_area_px < 0 or inspected_area_px < 0 or inspected_area_px > total_area_px:
        raise DimensionObserverError("inspected area must be within total area")
    detected = list(detected_cluster_ids)
    if len(set(detected)) != len(detected):
        raise DimensionObserverError("detected cluster IDs must be unique")
    disposition_map: dict[str, DimensionDisposition] = {}
    for disposition in dispositions:
        if disposition.cluster_id in disposition_map:
            raise DimensionObserverError(f"duplicate disposition for {disposition.cluster_id}")
        if disposition.cluster_id not in detected:
            raise DimensionObserverError(f"disposition for unknown cluster {disposition.cluster_id}")
        if disposition.disposition not in {"CONFIRMED", "UNRESOLVED", "CONFLICT", "NOT_A_DIMENSION"}:
            raise DimensionObserverError(f"invalid disposition {disposition.disposition}")
        disposition_map[disposition.cluster_id] = disposition
    missing = [cluster_id for cluster_id in detected if cluster_id not in disposition_map]
    if missing:
        raise DimensionObserverError(f"missing disposition for {', '.join(missing)}")

    dimensions: list[Mapping[str, object]] = []
    summary = {"confirmed": 0, "unresolved": 0, "conflicts": 0}
    for cluster_id in detected:
        disposition = disposition_map[cluster_id]
        if disposition.disposition == "NOT_A_DIMENSION":
            continue
        if disposition.observation is None:
            raise DimensionObserverError(f"{cluster_id} disposition lacks observation")
        dimensions.append(disposition.observation)
        summary_key = {
            "CONFIRMED": "confirmed",
            "UNRESOLVED": "unresolved",
            "CONFLICT": "conflicts",
        }[disposition.disposition]
        summary[summary_key] += 1
    coverage_percent = 100.0 if total_area_px == 0 else inspected_area_px / total_area_px * 100.0
    return {
        "schema_version": "dimension-register-1.0",
        "run_id": run_id,
        "source_sha256": source_sha256,
        "page_id": page_id,
        "view_id": view_id,
        "coverage": {
            "clusters_detected": len(detected),
            "clusters_processed": len(dispositions),
            "page_coverage_percent": round(coverage_percent, 6),
        },
        "summary": summary,
        "dimensions": dimensions,
    }


__all__ = [
    "Bbox",
    "DimensionCluster",
    "DimensionDisposition",
    "DimensionObserverError",
    "OcrReader",
    "build_dimension_register",
    "detect_dimension_clusters",
    "observe_dimension_cluster",
]
