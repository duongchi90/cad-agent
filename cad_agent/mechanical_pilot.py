"""Thin deterministic owner for the selected Phase 3 shaft pilot.

The pilot binds two typed Mechanical features to existing Primitive IR
geometry and routes candidate generation/read-back through the existing DXF
builder and headless reviewer. It is intentionally a fixture owner, not a
general Mechanical geometry engine or an execution transport.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cad_agent.live import write_build_evidence
from cad_agent.manifest import sha256_file
from cad_agent.visual_evidence import _path_contains_windows_reparse_point
from dxf_builder_lib.builder import BuildResult, build_dxf
from dxf_builder_lib.reviewer import ReviewResult, review_dxf
from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
    Validation,
)
from primitive_ir_lib.validator import validate_document as validate_primitive_document
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart
from semantic_ir_lib.validator import validate_document


PILOT_SCHEMA_VERSION = "mechanical-shaft-pilot-1.0"
_ROOT_FIELDS = frozenset(
    {"schema_version", "pilot_id", "source_document", "calibration", "features"}
)
_SOURCE_FIELDS = frozenset(
    {"file_name", "page_index", "image_width_px", "image_height_px"}
)
_CALIBRATION_FIELDS = frozenset(
    {"unit", "pixel_to_unit_scale", "origin_px", "method", "reference_note", "status"}
)
_SHAFT_FIELDS = frozenset({"id", "kind", "segments"})
_HOLE_FIELDS = frozenset({"id", "kind", "center", "diameter_mm"})
_SEGMENT_FIELDS = frozenset({"id", "start", "end"})
_EXPECTED_FEATURE_KINDS = ("shaft_step", "hole_feature")
_PHASE4_PILOT_ID = "synthetic-simple-stepped-shaft-v1"
_PHASE4_ENDPOINT_TOLERANCE_PX = 8.0
_PHASE4_AXIS_TOLERANCE_PX = 8.0


@dataclass(frozen=True)
class MechanicalPilotResult:
    pilot_id: str
    source_path: Path
    candidate_path: Path
    build_evidence_path: Path
    pilot_evidence_path: Path
    source_sha256: str
    candidate_sha256: str
    feature_bindings: dict[str, dict[str, object]]
    primitive_doc: PrimitiveIRDocument
    semantic_doc: SemanticIRDocument
    build: BuildResult
    review: ReviewResult
    source_pdf_name: str | None = None
    source_pdf_sha256: str | None = None
    pdf_manifest_path: Path | None = None


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PILOT_{name}_INVALID")
    return value


def _exact_fields(value: Mapping[str, object], fields: frozenset[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"PILOT_{name}_SCHEMA_INVALID")


def _string(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"PILOT_{name}_INVALID")
    return value


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"PILOT_{name}_INVALID")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"PILOT_{name}_INVALID")
    return number


def _point(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"PILOT_{name}_INVALID")
    return (_number(value[0], name), _number(value[1], name))


def _validate_definition(payload: object) -> dict[str, object]:
    root = _mapping(payload, "ROOT")
    _exact_fields(root, _ROOT_FIELDS, "ROOT")
    if root.get("schema_version") != PILOT_SCHEMA_VERSION:
        raise ValueError("PILOT_SCHEMA_VERSION_INVALID")
    _string(root.get("pilot_id"), "PILOT_ID")

    source = _mapping(root.get("source_document"), "SOURCE_DOCUMENT")
    _exact_fields(source, _SOURCE_FIELDS, "SOURCE_DOCUMENT")
    _string(source.get("file_name"), "SOURCE_FILE_NAME")
    for field in ("page_index", "image_width_px", "image_height_px"):
        value = source.get(field)
        if type(value) is not int or value < 0:
            raise ValueError("PILOT_SOURCE_DOCUMENT_INVALID")

    calibration = _mapping(root.get("calibration"), "CALIBRATION")
    _exact_fields(calibration, _CALIBRATION_FIELDS, "CALIBRATION")
    if calibration.get("unit") != "mm" or calibration.get("method") != "manual_override":
        raise ValueError("PILOT_CALIBRATION_INVALID")
    if calibration.get("status") != "verified":
        raise ValueError("PILOT_CALIBRATION_UNVERIFIED")
    _number(calibration.get("pixel_to_unit_scale"), "CALIBRATION_SCALE", positive=True)
    _point(calibration.get("origin_px"), "CALIBRATION_ORIGIN")
    _string(calibration.get("reference_note"), "CALIBRATION_REFERENCE")

    features = root.get("features")
    if not isinstance(features, list) or len(features) != len(_EXPECTED_FEATURE_KINDS):
        raise ValueError("PILOT_FEATURE_CLUSTER_INVALID")
    feature_ids: set[str] = set()
    kinds: list[str] = []
    for feature in features:
        record = _mapping(feature, "FEATURE")
        kind = _string(record.get("kind"), "FEATURE_KIND")
        feature_id = _string(record.get("id"), "FEATURE_ID")
        if feature_id in feature_ids:
            raise ValueError("PILOT_FEATURE_ID_DUPLICATE")
        feature_ids.add(feature_id)
        kinds.append(kind)
        if kind == "shaft_step":
            _exact_fields(record, _SHAFT_FIELDS, "SHAFT_FEATURE")
            segments = record.get("segments")
            if not isinstance(segments, list) or not segments:
                raise ValueError("PILOT_SHAFT_SEGMENTS_INVALID")
            segment_ids: set[str] = set()
            for segment in segments:
                segment_record = _mapping(segment, "SEGMENT")
                _exact_fields(segment_record, _SEGMENT_FIELDS, "SEGMENT")
                segment_id = _string(segment_record.get("id"), "SEGMENT_ID")
                if segment_id in segment_ids:
                    raise ValueError("PILOT_SEGMENT_ID_DUPLICATE")
                segment_ids.add(segment_id)
                start = _point(segment_record.get("start"), "SEGMENT_POINT")
                end = _point(segment_record.get("end"), "SEGMENT_POINT")
                if start == end:
                    raise ValueError("PILOT_ZERO_LENGTH_SEGMENT")
        elif kind == "hole_feature":
            _exact_fields(record, _HOLE_FIELDS, "HOLE_FEATURE")
            _point(record.get("center"), "HOLE_CENTER")
            _number(record.get("diameter_mm"), "HOLE_DIAMETER", positive=True)
        else:
            raise ValueError("PILOT_FEATURE_KIND_UNSUPPORTED")
    if tuple(kinds) != _EXPECTED_FEATURE_KINDS:
        raise ValueError("PILOT_FEATURE_CLUSTER_INVALID")
    return dict(root)


def _read_pilot_definition(source_path: Path) -> tuple[dict[str, object], str]:
    if (
        not source_path.is_file()
        or source_path.is_symlink()
        or _path_contains_windows_reparse_point(source_path)
    ):
        raise ValueError("PILOT_SOURCE_NOT_REGULAR_FILE")
    try:
        source_bytes = source_path.read_bytes()
        payload = json.loads(source_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("PILOT_SOURCE_READ_INVALID") from error
    return _validate_definition(payload), hashlib.sha256(source_bytes).hexdigest()


def load_pilot_definition(source_path: Path) -> dict[str, object]:
    """Load and validate one exact synthetic pilot definition."""

    return _read_pilot_definition(source_path)[0]


def _trace_for_points(points: list[tuple[float, float]]) -> Trace:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return Trace(
        bbox_px=(min(xs), min(ys), max(xs), max(ys)),
        extraction_tool="phase3_synthetic_fixture",
    )


def _documents(
    definition: Mapping[str, object], source_sha256: str, source_path: Path
) -> tuple[PrimitiveIRDocument, SemanticIRDocument, dict[str, dict[str, object]]]:
    source = _mapping(definition["source_document"], "SOURCE_DOCUMENT")
    calibration = _mapping(definition["calibration"], "CALIBRATION")
    primitives: list[Primitive] = []
    parts: list[SemanticPart] = []
    bindings: dict[str, dict[str, object]] = {}
    for feature in definition["features"]:
        record = _mapping(feature, "FEATURE")
        feature_id = _string(record["id"], "FEATURE_ID")
        kind = _string(record["kind"], "FEATURE_KIND")
        primitive_ids: list[str] = []
        if kind == "shaft_step":
            for segment in record["segments"]:
                segment_record = _mapping(segment, "SEGMENT")
                segment_id = _string(segment_record["id"], "SEGMENT_ID")
                primitive_id = f"{feature_id}:{segment_id}"
                start = _point(segment_record["start"], "SEGMENT_POINT")
                end = _point(segment_record["end"], "SEGMENT_POINT")
                primitives.append(
                    Primitive(
                        id=primitive_id,
                        type="line",
                        source="geometry_opencv",
                        confidence=1.0,
                        trace=_trace_for_points([start, end]),
                        geometry=LineGeometry(
                            start=Point2D(*start), end=Point2D(*end)
                        ),
                    )
                )
                primitive_ids.append(primitive_id)
            part_type = "mechanical_shaft_step"
        else:
            center = _point(record["center"], "HOLE_CENTER")
            primitive_id = feature_id
            primitives.append(
                Primitive(
                    id=primitive_id,
                    type="circle",
                    source="geometry_opencv",
                    confidence=1.0,
                    trace=_trace_for_points([center]),
                    geometry=CircleGeometry(
                        center=Point2D(*center),
                        radius=_number(record["diameter_mm"], "HOLE_DIAMETER", positive=True) / 2.0,
                    ),
                )
            )
            primitive_ids.append(primitive_id)
            part_type = "mechanical_hole_feature"
        parts.append(
            SemanticPart(
                id=feature_id,
                part_type=part_type,
                primitive_ids=primitive_ids,
                confidence=1.0,
            )
        )
        bindings[feature_id] = {"kind": kind, "primitive_ids": primitive_ids}

    primitive_doc = PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name=_string(source["file_name"], "SOURCE_FILE_NAME"),
            page_index=source["page_index"],
            image_width_px=source["image_width_px"],
            image_height_px=source["image_height_px"],
            sha256=source_sha256,
        ),
        calibration=Calibration(
            unit=calibration["unit"],
            pixel_to_unit_scale=calibration["pixel_to_unit_scale"],
            origin_px=tuple(calibration["origin_px"]),
            method=calibration["method"],
            reference_note=calibration["reference_note"],
            status=calibration["status"],
        ),
        primitives=primitives,
    )
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(
            file_name=source_path.name,
            primitive_count=len(primitives),
            sha256=source_sha256,
        ),
        parts=parts,
    )
    errors = validate_document(
        semantic_doc.to_dict(),
        known_primitive_ids={primitive.id for primitive in primitives},
    )
    if errors:
        raise ValueError(f"PILOT_SEMANTIC_DOCUMENT_INVALID:{errors[0]}")
    return primitive_doc, semantic_doc, bindings


def _hash(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"PILOT_{name}_INVALID")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"PILOT_{name}_INVALID") from error
    return value


def _integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"PILOT_{name}_INVALID")
    return value


def _primitive_point(value: object, name: str) -> Point2D:
    point = _mapping(value, name)
    _exact_fields(point, frozenset({"x", "y"}), name)
    return Point2D(
        _number(point["x"], f"{name}_X"),
        _number(point["y"], f"{name}_Y"),
    )


def _load_primitive_document(source_input: Path) -> tuple[PrimitiveIRDocument, str]:
    """Load one strict Primitive IR artifact produced by the existing PDF owner."""

    if (
        not source_input.is_file()
        or source_input.is_symlink()
        or _path_contains_windows_reparse_point(source_input)
    ):
        raise ValueError("PILOT_PRIMITIVE_NOT_REGULAR_FILE")
    try:
        raw = source_input.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("PILOT_PRIMITIVE_SCHEMA_INVALID")
        errors = validate_primitive_document(dict(payload))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError) as error:
        raise ValueError("PILOT_PRIMITIVE_SCHEMA_INVALID") from error
    if errors or payload.get("schema_version") != "1.0.0":
        raise ValueError("PILOT_PRIMITIVE_SCHEMA_INVALID")

    source = _mapping(payload.get("source_document"), "PRIMITIVE_SOURCE_DOCUMENT")
    for field in ("file_name", "page_index", "image_width_px", "image_height_px"):
        if field not in source:
            raise ValueError("PILOT_PRIMITIVE_SOURCE_DOCUMENT_INVALID")
    source_sha256 = source.get("sha256")
    if source_sha256 is not None:
        source_sha256 = _hash(source_sha256, "PRIMITIVE_SOURCE_DOCUMENT_SHA256")
    source_document = SourceDocument(
        file_name=_string(source["file_name"], "PRIMITIVE_SOURCE_FILE_NAME"),
        page_index=_integer(source["page_index"], "PRIMITIVE_SOURCE_PAGE_INDEX"),
        image_width_px=_integer(source["image_width_px"], "PRIMITIVE_SOURCE_WIDTH"),
        image_height_px=_integer(source["image_height_px"], "PRIMITIVE_SOURCE_HEIGHT"),
        sha256=source_sha256,
    )

    calibration = _mapping(payload.get("calibration"), "PRIMITIVE_CALIBRATION")
    for field in ("unit", "pixel_to_unit_scale", "origin_px", "method"):
        if field not in calibration:
            raise ValueError("PILOT_PRIMITIVE_CALIBRATION_INVALID")
    if calibration.get("unit") != "mm" or calibration.get("method") != "manual_override":
        raise ValueError("PILOT_PRIMITIVE_CALIBRATION_INVALID")
    if calibration.get("status") != "verified":
        raise ValueError("PILOT_PRIMITIVE_CALIBRATION_UNVERIFIED")
    origin = calibration.get("origin_px")
    if not isinstance(origin, list) or len(origin) != 2:
        raise ValueError("PILOT_PRIMITIVE_CALIBRATION_INVALID")
    calibration_source_sha256 = calibration.get("source_sha256")
    if calibration_source_sha256 is not None:
        calibration_source_sha256 = _hash(
            calibration_source_sha256, "PRIMITIVE_CALIBRATION_SOURCE_SHA256"
        )
    calibration_document = Calibration(
        unit="mm",
        pixel_to_unit_scale=_number(
            calibration["pixel_to_unit_scale"], "PRIMITIVE_CALIBRATION_SCALE", positive=True
        ),
        origin_px=(
            _number(origin[0], "PRIMITIVE_CALIBRATION_ORIGIN"),
            _number(origin[1], "PRIMITIVE_CALIBRATION_ORIGIN"),
        ),
        method="manual_override",
        reference_note=(
            calibration.get("reference_note")
            if calibration.get("reference_note") is None
            else _string(calibration.get("reference_note"), "PRIMITIVE_CALIBRATION_REFERENCE")
        ),
        status="verified",
        source_sha256=calibration_source_sha256,
    )

    raw_primitives = payload.get("primitives")
    if not isinstance(raw_primitives, list):
        raise ValueError("PILOT_PRIMITIVE_SCHEMA_INVALID")
    primitives: list[Primitive] = []
    for raw_primitive in raw_primitives:
        primitive = _mapping(raw_primitive, "PRIMITIVE")
        primitive_type = primitive.get("type")
        if primitive_type not in ("line", "circle"):
            raise ValueError("PILOT_PRIMITIVE_KIND_UNSUPPORTED")
        if primitive.get("source") != "geometry_opencv":
            raise ValueError("PILOT_PRIMITIVE_SOURCE_UNSUPPORTED")
        trace = _mapping(primitive.get("trace"), "PRIMITIVE_TRACE")
        bbox = trace.get("bbox_px")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("PILOT_PRIMITIVE_TRACE_INVALID")
        trace_value = Trace(
            bbox_px=tuple(_number(item, "PRIMITIVE_TRACE_BBOX") for item in bbox),
            extraction_tool=(
                trace.get("extraction_tool")
                if trace.get("extraction_tool") is None
                else _string(trace.get("extraction_tool"), "PRIMITIVE_TRACE_TOOL")
            ),
            extracted_at=(
                trace.get("extracted_at")
                if trace.get("extracted_at") is None
                else _string(trace.get("extracted_at"), "PRIMITIVE_TRACE_TIME")
            ),
        )
        validation = _mapping(primitive.get("validation"), "PRIMITIVE_VALIDATION")
        validation_status = validation.get("status")
        if validation_status not in {
            "unreviewed", "reviewer1_pass", "reviewer1_fail",
            "reviewer2_pass", "reviewer2_fail", "repaired",
        }:
            raise ValueError("PILOT_PRIMITIVE_VALIDATION_INVALID")
        primitive_geometry = _mapping(primitive.get("geometry"), "PRIMITIVE_GEOMETRY")
        if primitive_type == "line":
            geometry: object = LineGeometry(
                start=_primitive_point(primitive_geometry.get("start"), "PRIMITIVE_LINE_START"),
                end=_primitive_point(primitive_geometry.get("end"), "PRIMITIVE_LINE_END"),
            )
        else:
            geometry = CircleGeometry(
                center=_primitive_point(
                    primitive_geometry.get("center"), "PRIMITIVE_CIRCLE_CENTER"
                ),
                radius=_number(primitive_geometry.get("radius"), "PRIMITIVE_CIRCLE_RADIUS", positive=True),
            )
        handle = primitive.get("handle")
        if handle is not None:
            handle = _string(handle, "PRIMITIVE_HANDLE")
        primitives.append(
            Primitive(
                id=_string(primitive.get("id"), "PRIMITIVE_ID"),
                type=primitive_type,
                source="geometry_opencv",
                confidence=_number(primitive.get("confidence"), "PRIMITIVE_CONFIDENCE"),
                layer=_string(primitive.get("layer"), "PRIMITIVE_LAYER"),
                handle=handle,
                trace=trace_value,
                geometry=geometry,
                validation=Validation(
                    status=validation_status,
                    notes=(
                        validation.get("notes")
                        if validation.get("notes") is None
                        else _string(validation.get("notes"), "PRIMITIVE_VALIDATION_NOTES")
                    ),
                ),
            )
        )
    return (
        PrimitiveIRDocument(
            source_document=source_document,
            calibration=calibration_document,
            primitives=primitives,
        ),
        hashlib.sha256(raw).hexdigest(),
    )


def _cluster_endpoints(
    endpoints: list[tuple[float, float]], tolerance: float
) -> tuple[list[tuple[float, float]], list[int]]:
    parent = list(range(len(endpoints)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, point in enumerate(endpoints):
        for right in range(left):
            if math.hypot(point[0] - endpoints[right][0], point[1] - endpoints[right][1]) <= tolerance:
                union(left, right)

    groups: dict[int, list[int]] = {}
    for index in range(len(endpoints)):
        groups.setdefault(find(index), []).append(index)
    roots = sorted(groups, key=lambda root: min(groups[root]))
    root_to_cluster = {root: index for index, root in enumerate(roots)}
    centers = [
        (
            sum(endpoints[index][0] for index in groups[root]) / len(groups[root]),
            sum(endpoints[index][1] for index in groups[root]) / len(groups[root]),
        )
        for root in roots
    ]
    labels = [root_to_cluster[find(index)] for index in range(len(endpoints))]
    return centers, labels


def _phase4_profile_bindings(
    primitive_doc: PrimitiveIRDocument,
) -> tuple[list[str], str]:
    lines = [primitive for primitive in primitive_doc.primitives if primitive.type == "line"]
    circles = [primitive for primitive in primitive_doc.primitives if primitive.type == "circle"]
    if len(lines) != 8 or len(circles) != 1:
        raise ValueError("PILOT_SHAFT_PROFILE_INVALID")

    endpoints: list[tuple[float, float]] = []
    for primitive in lines:
        assert isinstance(primitive.geometry, LineGeometry)
        start = (primitive.geometry.start.x, primitive.geometry.start.y)
        end = (primitive.geometry.end.x, primitive.geometry.end.y)
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 2 * _PHASE4_ENDPOINT_TOLERANCE_PX:
            raise ValueError("PILOT_SHAFT_PROFILE_INVALID")
        dx, dy = abs(end[0] - start[0]), abs(end[1] - start[1])
        if not (
            (dx > _PHASE4_AXIS_TOLERANCE_PX and dy <= _PHASE4_AXIS_TOLERANCE_PX)
            or (dy > _PHASE4_AXIS_TOLERANCE_PX and dx <= _PHASE4_AXIS_TOLERANCE_PX)
        ):
            raise ValueError("PILOT_SHAFT_PROFILE_INVALID")
        endpoints.extend((start, end))

    centers, labels = _cluster_endpoints(endpoints, _PHASE4_ENDPOINT_TOLERANCE_PX)
    if len(centers) != 8:
        raise ValueError("PILOT_SHAFT_PROFILE_INVALID")
    edge_clusters: list[tuple[int, int]] = []
    adjacency: dict[int, list[tuple[int, int]]] = {index: [] for index in range(8)}
    for edge_index in range(8):
        left, right = labels[edge_index * 2 : edge_index * 2 + 2]
        if left == right:
            raise ValueError("PILOT_SHAFT_PROFILE_INVALID")
        edge_clusters.append((left, right))
        adjacency[left].append((right, edge_index))
        adjacency[right].append((left, edge_index))
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise ValueError("PILOT_SHAFT_PROFILE_INVALID")

    matches: list[tuple[list[int], list[int]]] = []
    for start in range(8):
        for first_neighbor, first_edge in adjacency[start]:
            vertices = [start]
            edge_ids = [first_edge]
            previous, current = start, first_neighbor
            while current != start:
                if len(edge_ids) > 8:
                    break
                vertices.append(current)
                options = [item for item in adjacency[current] if item[0] != previous]
                if len(options) != 1:
                    break
                next_vertex, next_edge = options[0]
                edge_ids.append(next_edge)
                previous, current = current, next_vertex
            if current != start or len(vertices) != 8 or len(edge_ids) != 8:
                continue
            points = [centers[index] for index in vertices]
            x0 = sum(points[index][0] for index in (0, 7)) / 2
            x1 = sum(points[index][0] for index in (1, 2, 5, 6)) / 4
            x2 = sum(points[index][0] for index in (3, 4)) / 2
            y0 = sum(points[index][1] for index in (0, 1)) / 2
            y1 = sum(points[index][1] for index in (2, 3)) / 2
            y2 = sum(points[index][1] for index in (4, 5)) / 2
            y3 = sum(points[index][1] for index in (6, 7)) / 2
            expected_x = [x0, x1, x1, x2, x2, x1, x1, x0]
            expected_y = [y0, y0, y1, y1, y2, y2, y3, y3]
            if not (
                x0 + 2 * _PHASE4_ENDPOINT_TOLERANCE_PX < x1 < x2 - 2 * _PHASE4_ENDPOINT_TOLERANCE_PX
                and y0 + 2 * _PHASE4_ENDPOINT_TOLERANCE_PX < y1 < y2 - 2 * _PHASE4_ENDPOINT_TOLERANCE_PX
                and y2 + 2 * _PHASE4_ENDPOINT_TOLERANCE_PX < y3
                and all(
                    abs(point[0] - expected_x[index]) <= _PHASE4_ENDPOINT_TOLERANCE_PX
                    and abs(point[1] - expected_y[index]) <= _PHASE4_ENDPOINT_TOLERANCE_PX
                    for index, point in enumerate(points)
                )
            ):
                continue
            matches.append((vertices, edge_ids))

    if len(matches) != 1:
        raise ValueError("PILOT_SHAFT_PROFILE_AMBIGUOUS")
    vertices, edge_ids = matches[0]
    points = [centers[index] for index in vertices]
    circle = circles[0]
    assert isinstance(circle.geometry, CircleGeometry)
    center = circle.geometry.center
    x_min = min(point[0] for point in points)
    x_max = max(point[0] for point in points)
    y_min = min(point[1] for point in points)
    y_max = max(point[1] for point in points)
    if not (
        x_min + _PHASE4_ENDPOINT_TOLERANCE_PX < center.x < x_max - _PHASE4_ENDPOINT_TOLERANCE_PX
        and y_min + _PHASE4_ENDPOINT_TOLERANCE_PX < center.y < y_max - _PHASE4_ENDPOINT_TOLERANCE_PX
    ):
        raise ValueError("PILOT_HOLE_POSITION_INVALID")
    return [lines[index].id for index in edge_ids], circle.id


def _semantic_from_primitive(
    primitive_doc: PrimitiveIRDocument,
    source_path: Path,
    source_sha256: str,
) -> tuple[SemanticIRDocument, dict[str, dict[str, object]]]:
    shaft_ids, hole_id = _phase4_profile_bindings(primitive_doc)
    semantic_doc = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(
            file_name=source_path.name,
            primitive_count=len(primitive_doc.primitives),
            sha256=source_sha256,
        ),
        parts=[
            SemanticPart(
                id="shaft-profile-001",
                part_type="mechanical_shaft_step",
                primitive_ids=shaft_ids,
                confidence=1.0,
            ),
            SemanticPart(
                id="hole-axial-001",
                part_type="mechanical_hole_feature",
                primitive_ids=[hole_id],
                confidence=1.0,
            ),
        ],
    )
    errors = validate_document(
        semantic_doc.to_dict(),
        known_primitive_ids={primitive.id for primitive in primitive_doc.primitives},
    )
    if errors:
        raise ValueError(f"PILOT_SEMANTIC_DOCUMENT_INVALID:{errors[0]}")
    return semantic_doc, {
        "shaft-profile-001": {"kind": "shaft_step", "primitive_ids": shaft_ids},
        "hole-axial-001": {"kind": "hole_feature", "primitive_ids": [hole_id]},
    }


def _build_candidate_result(
    *,
    pilot_id: str,
    source_path: Path,
    candidate_path: Path,
    source_sha256: str,
    primitive_doc: PrimitiveIRDocument,
    semantic_doc: SemanticIRDocument,
    bindings: dict[str, dict[str, object]],
    source_pdf_name: str | None = None,
    source_pdf_sha256: str | None = None,
    pdf_manifest_path: Path | None = None,
) -> MechanicalPilotResult:
    candidate_path = Path(candidate_path).resolve()
    if source_path == candidate_path:
        raise ValueError("PILOT_CANDIDATE_MUST_DIFFER")
    if candidate_path.exists():
        raise ValueError("PILOT_CANDIDATE_ALREADY_EXISTS")
    if _path_contains_windows_reparse_point(candidate_path.parent):
        raise ValueError("PILOT_CANDIDATE_ROOT_REPARSE")
    if candidate_path.parent.exists() and any(candidate_path.parent.iterdir()):
        raise ValueError("PILOT_CANDIDATE_ROOT_NOT_EMPTY")
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    build = build_dxf(primitive_doc, str(candidate_path), semantic_doc=semantic_doc)
    review = review_dxf(build)
    if not review.passed:
        raise ValueError("PILOT_HEADLESS_REVIEW_FAILED")
    build_evidence_path = candidate_path.with_name("build-evidence.json")
    write_build_evidence(build_evidence_path, build)
    pilot_evidence_path = candidate_path.with_name("pilot-evidence.json")
    result = MechanicalPilotResult(
        pilot_id=pilot_id,
        source_path=source_path,
        candidate_path=candidate_path,
        build_evidence_path=build_evidence_path,
        pilot_evidence_path=pilot_evidence_path,
        source_sha256=source_sha256,
        candidate_sha256=sha256_file(candidate_path),
        feature_bindings=bindings,
        primitive_doc=primitive_doc,
        semantic_doc=semantic_doc,
        build=build,
        review=review,
        source_pdf_name=source_pdf_name,
        source_pdf_sha256=source_pdf_sha256,
        pdf_manifest_path=pdf_manifest_path,
    )
    _write_pilot_evidence(result, pilot_evidence_path)
    return result


def _write_pilot_evidence(result: MechanicalPilotResult, path: Path) -> None:
    payload: dict[str, Any] = {
        "schema_version": PILOT_SCHEMA_VERSION,
        "pilot_id": result.pilot_id,
        "source_path": str(result.source_path),
        "source_sha256": result.source_sha256,
        "candidate_path": str(result.candidate_path),
        "candidate_sha256": result.candidate_sha256,
        "primitive_source_document": result.primitive_doc.source_document.to_dict(),
        "primitive_calibration": result.primitive_doc.calibration.to_dict(),
        "build_evidence_path": str(result.build_evidence_path),
        "feature_bindings": result.feature_bindings,
        "semantic_part_types": [part.part_type for part in result.semantic_doc.parts],
        "build": {
            "entity_count": result.build.entity_count,
            "skipped_primitive_ids": result.build.skipped_primitive_ids,
        },
        "review": {
            "passed": result.review.passed,
            "checked_count": result.review.checked_count,
            "mismatch_count": len(result.review.mismatches),
        },
    }
    if result.source_pdf_name is not None and result.source_pdf_sha256 is not None:
        payload["source_pdf"] = {
            "name": result.source_pdf_name,
            "sha256": result.source_pdf_sha256,
            "manifest_path": str(result.pdf_manifest_path)
            if result.pdf_manifest_path is not None
            else None,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def build_simple_shaft_pilot(source_path: Path, candidate_path: Path) -> MechanicalPilotResult:
    """Build one candidate for the selected two-feature synthetic pilot."""

    source_input = Path(source_path)
    if source_input.is_symlink() or _path_contains_windows_reparse_point(source_input):
        raise ValueError("PILOT_SOURCE_NOT_REGULAR_FILE")
    source_path = source_input.resolve(strict=True)
    candidate_path = Path(candidate_path).resolve()
    if source_path == candidate_path:
        raise ValueError("PILOT_CANDIDATE_MUST_DIFFER")
    if candidate_path.exists():
        raise ValueError("PILOT_CANDIDATE_ALREADY_EXISTS")
    if candidate_path.parent.exists() and any(candidate_path.parent.iterdir()):
        raise ValueError("PILOT_CANDIDATE_ROOT_NOT_EMPTY")
    definition, source_sha256 = _read_pilot_definition(source_path)
    primitive_doc, semantic_doc, bindings = _documents(
        definition, source_sha256, source_path
    )
    return _build_candidate_result(
        pilot_id=_string(definition["pilot_id"], "PILOT_ID"),
        source_path=source_path,
        candidate_path=candidate_path,
        source_sha256=source_sha256,
        primitive_doc=primitive_doc,
        semantic_doc=semantic_doc,
        bindings=bindings,
    )


def bind_simple_shaft_pilot_from_primitive(
    primitive_path: Path,
    candidate_path: Path,
    *,
    pdf_manifest_path: Path | None = None,
    pdf_source_path: Path | None = None,
) -> MechanicalPilotResult:
    """Bind one exact PDF-produced Primitive IR shape to the selected pilot."""

    source_input = Path(primitive_path)
    if source_input.is_symlink() or _path_contains_windows_reparse_point(source_input):
        raise ValueError("PILOT_PRIMITIVE_NOT_REGULAR_FILE")
    source_path = source_input.resolve(strict=True)
    primitive_doc, source_sha256 = _load_primitive_document(source_path)
    semantic_doc, bindings = _semantic_from_primitive(
        primitive_doc, source_path, source_sha256
    )
    source_pdf_name: str | None = None
    source_pdf_sha256: str | None = None
    bound_manifest_path: Path | None = None
    if pdf_manifest_path is not None:
        manifest_input = Path(pdf_manifest_path)
        if (
            not manifest_input.is_file()
            or manifest_input.is_symlink()
            or _path_contains_windows_reparse_point(manifest_input)
        ):
            raise ValueError("PILOT_PDF_MANIFEST_INVALID")
        bound_manifest_path = manifest_input.resolve(strict=True)
        try:
            from cad_agent.pdf import read_pdf_manifest

            manifest = read_pdf_manifest(bound_manifest_path)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError("PILOT_PDF_MANIFEST_INVALID") from error
        source = _mapping(manifest.get("source"), "PDF_SOURCE")
        source_pdf_name = _string(source.get("name"), "PDF_SOURCE_NAME")
        source_pdf_sha256 = _hash(source.get("sha256"), "PDF_SOURCE_SHA256")
        if pdf_source_path is None:
            raise ValueError("PILOT_PDF_SOURCE_REQUIRED")
        pdf_source_input = Path(pdf_source_path)
        if (
            not pdf_source_input.is_file()
            or pdf_source_input.is_symlink()
            or _path_contains_windows_reparse_point(pdf_source_input)
        ):
            raise ValueError("PILOT_PDF_SOURCE_HASH_MISMATCH")
        verified_pdf_path = pdf_source_input.resolve(strict=True)
        if (
            not verified_pdf_path.is_file()
            or _path_contains_windows_reparse_point(verified_pdf_path)
            or verified_pdf_path.name != source_pdf_name
            or sha256_file(verified_pdf_path) != source_pdf_sha256
        ):
            raise ValueError("PILOT_PDF_SOURCE_HASH_MISMATCH")
        matches: list[Mapping[str, object]] = []
        for page in manifest.get("pages", []):
            if not isinstance(page, Mapping):
                continue
            stages = page.get("stages")
            if not isinstance(stages, Mapping):
                continue
            stage = stages.get("primitive_ir")
            if not isinstance(stage, Mapping) or stage.get("state") != "completed":
                continue
            artifact = stage.get("artifact")
            if not isinstance(artifact, str):
                continue
            try:
                artifact_path = (bound_manifest_path.parent / artifact).resolve(strict=True)
            except OSError:
                continue
            if artifact_path != source_path:
                continue
            if stage.get("sha256") != source_sha256:
                raise ValueError("PILOT_PDF_PRIMITIVE_HASH_MISMATCH")
            matches.append(page)
        if len(matches) != 1:
            raise ValueError("PILOT_PDF_PRIMITIVE_BINDING_INVALID")
    return _build_candidate_result(
        pilot_id=_PHASE4_PILOT_ID,
        source_path=source_path,
        candidate_path=candidate_path,
        source_sha256=source_sha256,
        primitive_doc=primitive_doc,
        semantic_doc=semantic_doc,
        bindings=bindings,
        source_pdf_name=source_pdf_name,
        source_pdf_sha256=source_pdf_sha256,
        pdf_manifest_path=bound_manifest_path,
    )


__all__ = [
    "MechanicalPilotResult",
    "PILOT_SCHEMA_VERSION",
    "bind_simple_shaft_pilot_from_primitive",
    "build_simple_shaft_pilot",
    "load_pilot_definition",
]
