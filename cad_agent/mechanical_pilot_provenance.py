"""Provenance composition for a generated Mechanical pilot candidate."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path
import re

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.live import load_build_evidence
from cad_agent.manifest import sha256_file
from cad_agent.mechanical_pilot import (
    MechanicalPilotResult,
    _documents,
    load_pilot_definition,
)
from cad_agent.visual_evidence import _path_contains_windows_reparse_point


GENERATED_PILOT_PROVENANCE_SCHEMA_VERSION = (
    "generated-mechanical-pilot-provenance-1.0"
)
_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "pilot_id",
        "candidate_id",
        "source_sha256",
        "candidate_sha256",
        "build_evidence_sha256",
        "pilot_evidence_sha256",
        "primitive_projections",
        "feature_projections",
        "provenance_sha256",
    }
)
_PRIMITIVE_FIELDS = frozenset(
    {
        "primitive_id",
        "projection_ref",
        "primitive_type",
        "source_sha256",
        "candidate_sha256",
        "geometry_sha256",
        "written_geometry_sha256",
        "entity_handle",
        "layer",
        "block_name",
        "legacy_uuid",
        "relative_path",
        "captured_at_utc",
    }
)
_FEATURE_FIELDS = frozenset(
    {"feature_id", "kind", "semantic_projection_ref", "primitive_ids"}
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FEATURE_KIND_TO_PART_TYPE = {
    "shaft_step": "mechanical_shaft_step",
    "hole_feature": "mechanical_hole_feature",
}


class GeneratedPilotProvenanceError(ValueError):
    """Categorical refusal for malformed or stale generated-pilot evidence."""


def _fail(code: str) -> None:
    raise GeneratedPilotProvenanceError(code)


def _closed(value: object, fields: frozenset[str], code: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(code)
    if any(type(key) is not str for key in value):
        _fail(code)
    return deepcopy(dict(value))


def _sha(value: object, code: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _identifier(value: object, code: str) -> str:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value or len(value) > 1024:
        _fail(code)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _fail(code)
    return value


def _regular_file(value: object, code: str) -> Path:
    try:
        path = Path(value)
    except (TypeError, ValueError):
        _fail(code)
    if (
        not path.is_file()
        or path.is_symlink()
        or _path_contains_windows_reparse_point(path)
    ):
        _fail(code)
    try:
        return path.resolve(strict=True)
    except OSError as error:
        raise GeneratedPilotProvenanceError(code) from error


def _candidate_id(pilot_id: str, candidate_sha256: str) -> str:
    return f"{pilot_id}:{candidate_sha256}"


def _primitive_geometry(value: object) -> object:
    if not isinstance(value, Mapping):
        _fail("PRIMITIVE_RECORD_INVALID")
    if "geometry" in value:
        return deepcopy(value["geometry"])
    if "text_data" in value:
        return deepcopy(value["text_data"])
    return None


def _primitive_projection(
    *,
    pilot_id: str,
    source_sha256: str,
    candidate_sha256: str,
    relative_path: str,
    primitive: object,
    written_geometry: object,
    handle: object,
    layer: object,
) -> dict[str, object]:
    if not hasattr(primitive, "to_dict"):
        _fail("PRIMITIVE_RECORD_INVALID")
    raw = primitive.to_dict()
    primitive_id = _identifier(raw.get("id"), "PRIMITIVE_RECORD_INVALID")
    primitive_type = _identifier(raw.get("type"), "PRIMITIVE_RECORD_INVALID")
    geometry = _primitive_geometry(raw)
    geometry_sha256 = canonical_json_sha256(
        {
            "identity_kind": "generated-pilot-source-geometry-v1",
            "pilot_id": pilot_id,
            "primitive_id": primitive_id,
            "primitive_type": primitive_type,
            "source_sha256": source_sha256,
            "geometry": geometry,
        }
    )
    written_geometry_sha256 = canonical_json_sha256(
        {
            "identity_kind": "generated-pilot-written-geometry-v1",
            "pilot_id": pilot_id,
            "primitive_id": primitive_id,
            "candidate_sha256": candidate_sha256,
            "written_geometry": deepcopy(written_geometry),
        }
    )
    projection_ref = canonical_json_sha256(
        {
            "identity_kind": "generated-pilot-source-projection-v1",
            "pilot_id": pilot_id,
            "primitive_id": primitive_id,
            "primitive_type": primitive_type,
            "source_sha256": source_sha256,
            "geometry_sha256": geometry_sha256,
            "written_geometry_sha256": written_geometry_sha256,
            "entity_handle": _identifier(handle, "PRIMITIVE_HANDLE_INVALID"),
            "layer": _text(layer, "PRIMITIVE_LAYER_INVALID"),
            "block_name": "MODELSPACE",
            "legacy_uuid": f"generated:{primitive_id}",
            "relative_path": relative_path,
            "captured_at_utc": "GENERATED_BUILD_EVIDENCE",
        }
    )
    return {
        "primitive_id": primitive_id,
        "projection_ref": projection_ref,
        "primitive_type": primitive_type,
        "source_sha256": source_sha256,
        "candidate_sha256": candidate_sha256,
        "geometry_sha256": geometry_sha256,
        "written_geometry_sha256": written_geometry_sha256,
        "entity_handle": _identifier(handle, "PRIMITIVE_HANDLE_INVALID"),
        "layer": _text(layer, "PRIMITIVE_LAYER_INVALID"),
        "block_name": "MODELSPACE",
        "legacy_uuid": f"generated:{primitive_id}",
        "relative_path": relative_path,
        "captured_at_utc": "GENERATED_BUILD_EVIDENCE",
    }


def _feature_projection(
    *,
    pilot_id: str,
    feature_id: object,
    value: object,
    primitive_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    feature_key = _identifier(feature_id, "FEATURE_RECORD_INVALID")
    if not isinstance(value, Mapping) or set(value) != {"kind", "primitive_ids"}:
        _fail("FEATURE_RECORD_INVALID")
    kind = value.get("kind")
    if kind not in _FEATURE_KIND_TO_PART_TYPE:
        _fail("FEATURE_KIND_INVALID")
    primitive_ids = value.get("primitive_ids")
    if (
        type(primitive_ids) is not list
        or not primitive_ids
        or any(type(item) is not str for item in primitive_ids)
        or len(set(primitive_ids)) != len(primitive_ids)
    ):
        _fail("FEATURE_PRIMITIVES_INVALID")
    normalized_ids = sorted(primitive_ids)
    if any(item not in primitive_by_id for item in normalized_ids):
        _fail("FEATURE_PRIMITIVE_FOREIGN")
    semantic_projection_ref = canonical_json_sha256(
        {
            "identity_kind": "generated-pilot-semantic-projection-v1",
            "pilot_id": pilot_id,
            "feature_id": feature_key,
            "feature_kind": kind,
            "primitive_projection_refs": [
                primitive_by_id[item]["projection_ref"] for item in normalized_ids
            ],
        }
    )
    return {
        "feature_id": feature_key,
        "kind": kind,
        "semantic_projection_ref": semantic_projection_ref,
        "primitive_ids": normalized_ids,
    }


def _validate_pilot_evidence(result: MechanicalPilotResult) -> tuple[str, str]:
    pilot_path = _regular_file(result.pilot_evidence_path, "PILOT_EVIDENCE_INVALID")
    try:
        payload = json.loads(pilot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GeneratedPilotProvenanceError("PILOT_EVIDENCE_INVALID") from error
    if not isinstance(payload, Mapping):
        _fail("PILOT_EVIDENCE_INVALID")
    expected = {
        "schema_version": "mechanical-shaft-pilot-1.0",
        "pilot_id": result.pilot_id,
        "source_path": str(result.source_path),
        "source_sha256": result.source_sha256,
        "candidate_path": str(result.candidate_path),
        "candidate_sha256": result.candidate_sha256,
        "build_evidence_path": str(result.build_evidence_path),
        "feature_bindings": result.feature_bindings,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            _fail("PILOT_EVIDENCE_MISMATCH")
    return str(result.pilot_id), sha256_file(pilot_path)


def _source_bound_primitive_document(result: MechanicalPilotResult) -> dict[str, object]:
    payload = result.primitive_doc.to_dict()
    for primitive in payload["primitives"]:
        primitive["handle"] = None
        primitive["layer"] = "UNCLASSIFIED"
    return payload


def _validate_build_evidence(result: MechanicalPilotResult) -> str:
    evidence_path = _regular_file(
        result.build_evidence_path, "BUILD_EVIDENCE_INVALID"
    )
    try:
        loaded = load_build_evidence(evidence_path, result.candidate_path)
    except Exception as error:
        raise GeneratedPilotProvenanceError("BUILD_EVIDENCE_INVALID") from error
    for field in (
        "handle_by_primitive_id",
        "layer_by_primitive_id",
        "written_geometry_by_primitive_id",
    ):
        if canonical_json_sha256(getattr(loaded, field)) != canonical_json_sha256(
            getattr(result.build, field)
        ):
            _fail("BUILD_EVIDENCE_MISMATCH")
    if loaded.entity_count != result.build.entity_count:
        _fail("BUILD_EVIDENCE_MISMATCH")
    return sha256_file(evidence_path)


def _validate_result_files(result: MechanicalPilotResult) -> tuple[str, str, str, str]:
    source_path = _regular_file(result.source_path, "SOURCE_ARTIFACT_INVALID")
    candidate_path = _regular_file(result.candidate_path, "CANDIDATE_ARTIFACT_INVALID")
    source_sha256 = sha256_file(source_path)
    candidate_sha256 = sha256_file(candidate_path)
    if source_sha256 != result.source_sha256:
        _fail("SOURCE_ARTIFACT_HASH_MISMATCH")
    if candidate_sha256 != result.candidate_sha256:
        _fail("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    if source_path != Path(result.source_path).resolve() or candidate_path != Path(
        result.candidate_path
    ).resolve():
        _fail("ARTIFACT_PATH_MISMATCH")
    build_sha256 = _validate_build_evidence(result)
    pilot_id, pilot_sha256 = _validate_pilot_evidence(result)
    if pilot_id != result.pilot_id:
        _fail("PILOT_ID_MISMATCH")
    try:
        definition = load_pilot_definition(source_path)
        expected_primitive, expected_semantic, expected_bindings = _documents(
            definition, source_sha256, source_path
        )
    except Exception as error:
        raise GeneratedPilotProvenanceError("PILOT_SOURCE_BINDING_INVALID") from error
    if (
        canonical_json_sha256(expected_primitive.to_dict())
        != canonical_json_sha256(_source_bound_primitive_document(result))
        or canonical_json_sha256(expected_semantic.to_dict())
        != canonical_json_sha256(result.semantic_doc.to_dict())
        or canonical_json_sha256(expected_bindings)
        != canonical_json_sha256(result.feature_bindings)
    ):
        _fail("PILOT_SOURCE_BINDING_MISMATCH")
    return source_sha256, candidate_sha256, build_sha256, pilot_sha256


def _packet_without_checksum(packet: Mapping[str, object]) -> dict[str, object]:
    return {
        key: deepcopy(packet[key])
        for key in _PACKET_FIELDS
        if key != "provenance_sha256"
    }


def _validate_primitive_projections(
    value: object,
    *,
    pilot_id: str,
    source_sha256: str,
    candidate_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    if type(value) is not list or not value:
        _fail("PRIMITIVE_PROJECTIONS_INVALID")
    normalized: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    handles: set[str] = set()
    for raw in value:
        item = _closed(raw, _PRIMITIVE_FIELDS, "PRIMITIVE_PROJECTION_INVALID")
        item["primitive_id"] = _identifier(
            item["primitive_id"], "PRIMITIVE_PROJECTION_INVALID"
        )
        item["primitive_type"] = _identifier(
            item["primitive_type"], "PRIMITIVE_PROJECTION_INVALID"
        )
        for field in (
            "source_sha256",
            "candidate_sha256",
            "geometry_sha256",
            "written_geometry_sha256",
            "projection_ref",
        ):
            item[field] = _sha(item[field], "PRIMITIVE_PROJECTION_INVALID")
        if item["source_sha256"] != source_sha256:
            _fail("PRIMITIVE_SOURCE_MISMATCH")
        if item["candidate_sha256"] != candidate_sha256:
            _fail("PRIMITIVE_CANDIDATE_MISMATCH")
        item["entity_handle"] = _identifier(
            item["entity_handle"], "PRIMITIVE_HANDLE_INVALID"
        )
        item["layer"] = _text(item["layer"], "PRIMITIVE_LAYER_INVALID")
        for field in ("block_name", "legacy_uuid", "relative_path", "captured_at_utc"):
            item[field] = _text(item[field], "PRIMITIVE_BINDING_INVALID")
        expected_projection = canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-source-projection-v1",
                "pilot_id": pilot_id,
                "primitive_id": item["primitive_id"],
                "primitive_type": item["primitive_type"],
                "source_sha256": source_sha256,
                "geometry_sha256": item["geometry_sha256"],
                "written_geometry_sha256": item["written_geometry_sha256"],
                "entity_handle": item["entity_handle"],
                "layer": item["layer"],
                "block_name": item["block_name"],
                "legacy_uuid": item["legacy_uuid"],
                "relative_path": item["relative_path"],
                "captured_at_utc": item["captured_at_utc"],
            }
        )
        if item["projection_ref"] != expected_projection:
            _fail("PRIMITIVE_PROJECTION_HASH_MISMATCH")
        if item["primitive_id"] in by_id:
            _fail("PRIMITIVE_DUPLICATE")
        folded_handle = str(item["entity_handle"]).casefold()
        if folded_handle in handles:
            _fail("PRIMITIVE_HANDLE_DUPLICATE")
        handles.add(folded_handle)
        by_id[str(item["primitive_id"])] = item
        normalized.append(item)
    normalized.sort(key=lambda item: str(item["primitive_id"]))
    return normalized, by_id


def _validate_feature_projections(
    value: object,
    *,
    pilot_id: str,
    primitive_by_id: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    if type(value) is not list or not value:
        _fail("FEATURE_PROJECTIONS_INVALID")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    used: set[str] = set()
    for raw in value:
        item = _closed(raw, _FEATURE_FIELDS, "FEATURE_PROJECTION_INVALID")
        feature_id = _identifier(item["feature_id"], "FEATURE_PROJECTION_INVALID")
        kind = item["kind"]
        if kind not in _FEATURE_KIND_TO_PART_TYPE:
            _fail("FEATURE_KIND_INVALID")
        primitive_ids = item["primitive_ids"]
        if (
            type(primitive_ids) is not list
            or not primitive_ids
            or any(type(pid) is not str for pid in primitive_ids)
            or len(set(primitive_ids)) != len(primitive_ids)
        ):
            _fail("FEATURE_PRIMITIVES_INVALID")
        primitive_ids = sorted(primitive_ids)
        if any(pid not in primitive_by_id for pid in primitive_ids):
            _fail("FEATURE_PRIMITIVE_FOREIGN")
        semantic_ref = _sha(
            item["semantic_projection_ref"], "FEATURE_PROJECTION_INVALID"
        )
        expected_ref = canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-semantic-projection-v1",
                "pilot_id": pilot_id,
                "feature_id": feature_id,
                "feature_kind": kind,
                "primitive_projection_refs": [
                    primitive_by_id[pid]["projection_ref"] for pid in primitive_ids
                ],
            }
        )
        if semantic_ref != expected_ref:
            _fail("FEATURE_PROJECTION_HASH_MISMATCH")
        if feature_id in seen:
            _fail("FEATURE_DUPLICATE")
        seen.add(feature_id)
        used.update(primitive_ids)
        normalized.append(
            {
                "feature_id": feature_id,
                "kind": kind,
                "semantic_projection_ref": semantic_ref,
                "primitive_ids": primitive_ids,
            }
        )
    if used != set(primitive_by_id):
        _fail("FEATURE_PRIMITIVE_COVERAGE_INVALID")
    normalized.sort(key=lambda item: str(item["feature_id"]))
    return normalized


def validate_generated_pilot_provenance(payload: object) -> dict[str, object]:
    """Validate and detach one generated-pilot provenance packet."""
    packet = _closed(payload, _PACKET_FIELDS, "PROVENANCE_SCHEMA_INVALID")
    if packet["schema_version"] != GENERATED_PILOT_PROVENANCE_SCHEMA_VERSION:
        _fail("PROVENANCE_SCHEMA_INVALID")
    pilot_id = _identifier(packet["pilot_id"], "PILOT_ID_INVALID")
    source_sha256 = _sha(packet["source_sha256"], "SOURCE_HASH_INVALID")
    candidate_sha256 = _sha(packet["candidate_sha256"], "CANDIDATE_HASH_INVALID")
    expected_candidate_id = _candidate_id(pilot_id, candidate_sha256)
    if packet["candidate_id"] != expected_candidate_id:
        _fail("CANDIDATE_ID_MISMATCH")
    _sha(packet["build_evidence_sha256"], "BUILD_EVIDENCE_HASH_INVALID")
    _sha(packet["pilot_evidence_sha256"], "PILOT_EVIDENCE_HASH_INVALID")
    primitives, primitive_by_id = _validate_primitive_projections(
        packet["primitive_projections"],
        pilot_id=pilot_id,
        source_sha256=source_sha256,
        candidate_sha256=candidate_sha256,
    )
    features = _validate_feature_projections(
        packet["feature_projections"],
        pilot_id=pilot_id,
        primitive_by_id=primitive_by_id,
    )
    normalized = {
        "schema_version": GENERATED_PILOT_PROVENANCE_SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "candidate_id": expected_candidate_id,
        "source_sha256": source_sha256,
        "candidate_sha256": candidate_sha256,
        "build_evidence_sha256": packet["build_evidence_sha256"],
        "pilot_evidence_sha256": packet["pilot_evidence_sha256"],
        "primitive_projections": primitives,
        "feature_projections": features,
        "provenance_sha256": "",
    }
    expected_sha256 = canonical_json_sha256(_packet_without_checksum(normalized))
    if packet["provenance_sha256"] != expected_sha256:
        _fail("PROVENANCE_HASH_MISMATCH")
    normalized["provenance_sha256"] = expected_sha256
    return normalized


def build_generated_pilot_provenance(
    result: MechanicalPilotResult,
) -> dict[str, object]:
    """Issue a checksummed packet from one exact pilot result and its files."""
    source_sha256, candidate_sha256, build_sha256, pilot_sha256 = (
        _validate_result_files(result)
    )
    candidate_relative_path = _regular_file(
        result.candidate_path, "CANDIDATE_ARTIFACT_INVALID"
    ).name
    pilot_id = _identifier(result.pilot_id, "PILOT_ID_INVALID")
    candidate_id = _candidate_id(pilot_id, candidate_sha256)
    primitive_ids = [primitive.id for primitive in result.primitive_doc.primitives]
    if len(primitive_ids) != len(set(primitive_ids)):
        _fail("PRIMITIVE_DUPLICATE")
    handles = result.build.handle_by_primitive_id
    layers = result.build.layer_by_primitive_id
    written = result.build.written_geometry_by_primitive_id
    if set(handles) != set(primitive_ids) or set(layers) != set(primitive_ids):
        _fail("BUILD_BINDING_COVERAGE_INVALID")
    if set(written) != set(primitive_ids):
        _fail("BUILD_GEOMETRY_COVERAGE_INVALID")
    primitives = [
        _primitive_projection(
            pilot_id=pilot_id,
            source_sha256=source_sha256,
            candidate_sha256=candidate_sha256,
            relative_path=candidate_relative_path,
            primitive=primitive,
            written_geometry=written[primitive.id],
            handle=handles[primitive.id],
            layer=layers[primitive.id],
        )
        for primitive in result.primitive_doc.primitives
    ]
    primitives.sort(key=lambda item: str(item["primitive_id"]))
    primitive_by_id = {item["primitive_id"]: item for item in primitives}
    features = [
        _feature_projection(
            pilot_id=pilot_id,
            feature_id=feature_id,
            value=value,
            primitive_by_id=primitive_by_id,
        )
        for feature_id, value in result.feature_bindings.items()
    ]
    features.sort(key=lambda item: str(item["feature_id"]))
    semantic_parts = {
        part.id: part for part in result.semantic_doc.parts
    }
    if set(semantic_parts) != {item["feature_id"] for item in features}:
        _fail("SEMANTIC_FEATURE_COVERAGE_INVALID")
    for feature in features:
        part = semantic_parts[feature["feature_id"]]
        if (
            part.part_type != _FEATURE_KIND_TO_PART_TYPE[feature["kind"]]
            or sorted(part.primitive_ids) != feature["primitive_ids"]
        ):
            _fail("SEMANTIC_FEATURE_MISMATCH")
    packet: dict[str, object] = {
        "schema_version": GENERATED_PILOT_PROVENANCE_SCHEMA_VERSION,
        "pilot_id": pilot_id,
        "candidate_id": candidate_id,
        "source_sha256": source_sha256,
        "candidate_sha256": candidate_sha256,
        "build_evidence_sha256": build_sha256,
        "pilot_evidence_sha256": pilot_sha256,
        "primitive_projections": primitives,
        "feature_projections": features,
        "provenance_sha256": "",
    }
    packet["provenance_sha256"] = canonical_json_sha256(
        _packet_without_checksum(packet)
    )
    return validate_generated_pilot_provenance(packet)


def build_generated_pilot_r3_inputs(
    result: MechanicalPilotResult,
) -> dict[str, object]:
    """Build the explicit generated context and typed R3 component inputs."""
    packet = build_generated_pilot_provenance(result)
    primitive_by_id = {
        str(item["primitive_id"]): item
        for item in packet["primitive_projections"]
    }
    components: list[dict[str, object]] = []
    for feature in packet["feature_projections"]:
        primitive_ids = list(feature["primitive_ids"])
        bindings = [
            {
                "target_namespace": "CANDIDATE",
                "candidate_id": packet["candidate_id"],
                "entity_handle": primitive_by_id[primitive_id]["entity_handle"],
                "block_name": primitive_by_id[primitive_id]["block_name"],
                "legacy_uuid": primitive_by_id[primitive_id]["legacy_uuid"],
                "relative_path": primitive_by_id[primitive_id]["relative_path"],
                "captured_at_utc": primitive_by_id[primitive_id]["captured_at_utc"],
            }
            for primitive_id in primitive_ids
        ]
        components.append(
            {
                "component_type": feature["kind"],
                "origin_class": "RECONSTRUCTED_NEW",
                "source_projection_refs": [
                    primitive_by_id[primitive_id]["projection_ref"]
                    for primitive_id in primitive_ids
                ],
                "semantic_projection_refs": [
                    feature["semantic_projection_ref"]
                ],
                "base_cad_provenance_ref": None,
                "candidate_entity_bindings": bindings,
            }
        )
    return {
        "upstream_context": {
            "provenance_mode": "GENERATED_MECHANICAL_PILOT",
            "candidate": {
                "candidate_id": packet["candidate_id"],
                "candidate_drawing_sha256": packet["candidate_sha256"],
            },
            "mechanical_pilot_provenance": packet,
        },
        "components": components,
    }


def compose_generated_pilot_query_binding(
    result: MechanicalPilotResult,
    *,
    run_id: str,
    project_id: str,
    drawing_id: str,
) -> dict[str, object]:
    """Compose one current, read-only DARA/R3/R4 binding for the pilot."""
    from cad_agent import component_view_registry as r3
    from cad_agent import drawing_artifact_reference as dara
    from cad_agent.candidate_revision import (
        CANDIDATE_REVISION_ROOT_KIND,
        CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        build_candidate_revision,
        build_candidate_revision_state,
    )

    packet = build_generated_pilot_provenance(result)
    r3_inputs = build_generated_pilot_r3_inputs(result)
    context = r3_inputs["upstream_context"]
    registry = r3.build_component_view_registry(**r3_inputs)
    registry_provenance = r3.component_view_registry_provenance_evidence(
        registry, upstream_context=context
    )
    artifact_path = _regular_file(result.candidate_path, "CANDIDATE_ARTIFACT_INVALID")
    artifact_bytes = artifact_path.read_bytes()
    if sha256_file(artifact_path) != packet["candidate_sha256"]:
        _fail("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    scope = {"run_id": run_id, "project_id": project_id, "drawing_id": drawing_id}
    baseline_evidence = {
        "evidence_kind": "BASELINE_CUSTODY",
        "evidence_id": "generated-pilot-baseline-" + packet["provenance_sha256"][:24],
        "evidence_sha256": canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-baseline-custody-v1",
                "scope": scope,
                "candidate_sha256": packet["candidate_sha256"],
                "provenance_sha256": packet["provenance_sha256"],
            }
        ),
    }
    baseline_reference = dara.issue_drawing_artifact_reference(
        **scope,
        artifact_role="BASELINE",
        artifact_bytes=artifact_bytes,
        upstream_evidence=baseline_evidence,
    )
    baseline_observation = dara.observe_drawing_artifact_currentness(
        reference=baseline_reference,
        artifact_bytes=artifact_bytes,
        observation_evidence_sha256=canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-baseline-observation-v1",
                "reference_sha256": baseline_reference["reference_sha256"],
            }
        ),
    )
    candidate_evidence = {
        "evidence_kind": "R3_CANDIDATE_CUSTODY",
        "evidence_id": "generated-pilot-candidate-" + packet["provenance_sha256"][:24],
        "evidence_sha256": canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-candidate-custody-v1",
                "scope": scope,
                "candidate_sha256": packet["candidate_sha256"],
                "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
            }
        ),
    }
    candidate_reference = dara.issue_drawing_artifact_reference(
        **scope,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=artifact_bytes,
        upstream_evidence=candidate_evidence,
        r3_provenance_binding={
            "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
            "provenance_sha256": registry_provenance["provenance_sha256"],
        },
    )
    candidate_observation = dara.observe_drawing_artifact_currentness(
        reference=candidate_reference,
        artifact_bytes=artifact_bytes,
        observation_evidence_sha256=canonical_json_sha256(
            {
                "identity_kind": "generated-pilot-candidate-observation-v1",
                "reference_sha256": candidate_reference["reference_sha256"],
            }
        ),
    )
    component_ids = [component["component_id"] for component in registry["components"]]
    impact = r3.project_linked_view_impacts(
        registry=registry,
        component_ids=component_ids,
        view_ids=[],
        upstream_context=context,
    )
    change_impact = {
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "impact": impact,
        "provenance_evidence": registry_provenance,
        "upstream_context": deepcopy(context),
        "root_candidate_reference": deepcopy(candidate_reference),
        "root_candidate_observation": deepcopy(candidate_observation),
        "root_candidate_artifact_bytes": artifact_bytes,
    }
    mutation_evidence = {
        "evidence_kind": "R4_ROOT_PRE_REPAIR",
        "evidence_id": "generated-pilot-root-" + packet["provenance_sha256"][:24],
        "r3_candidate_reference_id": candidate_reference["reference_id"],
        "r3_candidate_reference_sha256": candidate_reference["reference_sha256"],
        "candidate_artifact_sha256": candidate_reference["artifact_sha256"],
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
    }
    baseline_context = {
        "reference": baseline_reference,
        "observation": baseline_observation,
        "artifact_bytes": artifact_bytes,
    }
    revision = build_candidate_revision(
        registry=registry,
        base_cad_handoff=None,
        baseline_context=baseline_context,
        parent_candidate=None,
        change_impact=change_impact,
        mutation_evidence=mutation_evidence,
        lineage_context=(),
        schema_version=CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        candidate_kind=CANDIDATE_REVISION_ROOT_KIND,
    )
    candidate_state = build_candidate_revision_state(
        candidate_revisions=[revision],
        current_candidate_revision_sha256=revision["candidate_revision_sha256"],
    )
    return {
        "packet": packet,
        "reference": candidate_reference,
        "current_observation": candidate_observation,
        "artifact_bytes": artifact_bytes,
        "parent_reference": None,
        "accepted_transition_evidence_sha256": None,
        "registry": registry,
        "registry_upstream_context": context,
        "candidate_revision": revision,
        "candidate_state": candidate_state,
        "baseline_context": baseline_context,
        "change_impact": change_impact,
        "mutation_evidence": mutation_evidence,
    }


__all__ = [
    "GENERATED_PILOT_PROVENANCE_SCHEMA_VERSION",
    "GeneratedPilotProvenanceError",
    "build_generated_pilot_provenance",
    "build_generated_pilot_r3_inputs",
    "compose_generated_pilot_query_binding",
    "validate_generated_pilot_provenance",
]
