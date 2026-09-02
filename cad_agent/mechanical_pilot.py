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
)
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
    if not source_path.is_file() or source_path.is_symlink():
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


def _write_pilot_evidence(result: MechanicalPilotResult, path: Path) -> None:
    payload: dict[str, Any] = {
        "schema_version": PILOT_SCHEMA_VERSION,
        "pilot_id": result.pilot_id,
        "source_path": str(result.source_path),
        "source_sha256": result.source_sha256,
        "candidate_path": str(result.candidate_path),
        "candidate_sha256": result.candidate_sha256,
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def build_simple_shaft_pilot(source_path: Path, candidate_path: Path) -> MechanicalPilotResult:
    """Build one candidate for the selected two-feature synthetic pilot."""

    source_input = Path(source_path)
    if source_input.is_symlink():
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
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    build = build_dxf(primitive_doc, str(candidate_path), semantic_doc=semantic_doc)
    review = review_dxf(build)
    if not review.passed:
        raise ValueError("PILOT_HEADLESS_REVIEW_FAILED")
    build_evidence_path = candidate_path.with_name("build-evidence.json")
    write_build_evidence(build_evidence_path, build)
    pilot_evidence_path = candidate_path.with_name("pilot-evidence.json")
    result = MechanicalPilotResult(
        pilot_id=_string(definition["pilot_id"], "PILOT_ID"),
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
    )
    _write_pilot_evidence(result, pilot_evidence_path)
    return result


__all__ = [
    "MechanicalPilotResult",
    "PILOT_SCHEMA_VERSION",
    "build_simple_shaft_pilot",
    "load_pilot_definition",
]
