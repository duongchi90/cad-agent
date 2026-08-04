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

from primitive_ir_lib.dimension_geometry import DimensionGeometryEvidence, detect_dimension_geometry
from primitive_ir_lib.dimension_symbols import ParsedDimensionText, parse_dimension_text
from primitive_ir_lib.text_extraction import RawText, detect_text_candidate_rois

Bbox = tuple[int, int, int, int]
OcrReader = Callable[[np.ndarray], Sequence[RawText]]

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ROLES = {"DRIVING", "REFERENCE", "DERIVED"}


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


def _geometry_bbox(geometry: DimensionGeometryEvidence, *, width: int, height: int) -> Bbox | None:
    points: list[tuple[float, float]] = []
    for segment in (geometry.dimension_line, *geometry.extension_lines, *geometry.leader_lines):
        if segment is not None:
            points.extend(segment)
    points.extend(geometry.arrow_points)
    if not points:
        return None
    padding = 14
    x0 = max(0, math.floor(min(point[0] for point in points)) - padding)
    y0 = max(0, math.floor(min(point[1] for point in points)) - padding)
    x1 = min(width, math.ceil(max(point[0] for point in points)) + padding)
    y1 = min(height, math.ceil(max(point[1] for point in points)) + padding)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def detect_dimension_clusters(image_bgr: np.ndarray) -> list[DimensionCluster]:
    """Return stable reading-order candidate clusters without running OCR."""
    if not isinstance(image_bgr, np.ndarray) or image_bgr.ndim not in {2, 3}:
        raise DimensionObserverError("image_bgr must be a grayscale or BGR image")
    if image_bgr.size == 0:
        return []
    height, width = image_bgr.shape[:2]
    text_boxes = detect_text_candidate_rois(image_bgr)
    geometry = detect_dimension_geometry(image_bgr)
    geometry_box = _geometry_bbox(geometry, width=width, height=height)
    candidate_boxes = [*text_boxes]
    if geometry_box is not None:
        candidate_boxes.append(geometry_box)
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
        if raw_text.rotation_deg not in {0.0, 90.0, -90.0}:
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
    }


def _observation_sha256(observation: Mapping[str, object]) -> str:
    without_provenance = dict(observation)
    without_provenance.pop("provenance", None)
    encoded = json.dumps(without_provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    raw_texts = list(ocr_reader(crop))
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
                raw_texts=raw_texts,
                page_id=page_id,
                view_id=view_id,
            ),
            reasons=tuple(sorted(set(parse_reasons + ("unreadable_observation",)))),
        )
    if parsed is None and raw_candidates and geometry.dimension_line is None:
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
        summary_key = disposition.disposition.casefold()
        if summary_key in summary:
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
