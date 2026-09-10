"""Pure validation and detached provenance for standalone-DWG extraction.

This module owns only the Python packet boundary.  It does not open CAD,
issue File IPC requests, write a candidate, or create an R3/R4 lineage record.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
import ntpath
from pathlib import Path
import re

from cad_agent.drawing_contracts import canonical_json_sha256


STANDALONE_INSPECTION_SCHEMA_VERSION = (
    "standalone-dwg-component-inspection-1.0"
)
STANDALONE_INSPECTION_RESULT_SCHEMA_VERSION = (
    "standalone-dwg-component-inspection-result-1.0"
)
STANDALONE_EXTRACTION_SCHEMA_VERSION = (
    "standalone-dwg-component-extraction-1.0"
)
STANDALONE_EXTRACTION_RESULT_SCHEMA_VERSION = (
    "standalone-dwg-component-extraction-result-1.0"
)
STANDALONE_PRE_R3_PROVENANCE_SCHEMA_VERSION = (
    "standalone-dwg-pre-r3-provenance-1.0"
)
STANDALONE_PROVENANCE_MODE = "STANDALONE_DWG_COMPONENTS"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HANDLE_RE = re.compile(r"^[0-9A-Fa-f]{1,64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

_INSPECTION_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "run_id",
        "source_drawing_path",
        "source_drawing_sha256",
        "source_setup_audit_sha256",
        "selection_groups",
        "expected_dbmod",
        "approval",
    }
)
_SELECTION_GROUP_FIELDS = frozenset(
    {
        "group_id",
        "logical_component_id",
        "source_handles",
        "expected_entity_types",
        "source_layer_expectations",
    }
)
_INSPECTION_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "inspection_id",
        "request_id",
        "source_identity",
        "source_sha256_before",
        "source_sha256_after",
        "dbmod_before",
        "dbmod_after",
        "read_only",
        "groups",
        "warnings",
        "conflicts",
        "changed",
        "eligible",
        "inspection_sha256",
    }
)
_INSPECTION_GROUP_FIELDS = frozenset(
    {
        "group_id",
        "logical_component_id",
        "source_handles",
        "entity_types",
        "layers",
        "signature_sha256",
    }
)
_EXTRACTION_PLAN_FIELDS = frozenset(
    {
        "plan_id",
        "request_id",
        "run_id",
        "inspection_id",
        "inspection_sha256",
        "source_drawing_sha256",
        "candidate_output_path",
        "candidate_base_model",
        "components",
        "transform_policy",
        "approval",
    }
)
_COMPONENT_PLAN_FIELDS = frozenset(
    {"group_id", "logical_component_id", "source_handles", "transform"}
)
_TRANSFORM_FIELDS = frozenset(
    {"rotation_degrees", "translation", "uniform_scale"}
)
_POINT_FIELDS = frozenset({"x", "y", "z"})
_APPROVAL_FIELDS = frozenset({"reference", "status"})
_EXTRACTION_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "run_id",
        "source_drawing_sha256",
        "candidate_base_model",
        "candidate_output_sha256",
        "candidate_output_identity",
        "source_mutated",
        "source_dbmod_before",
        "source_dbmod_after",
        "save_performed",
        "components",
        "source_handle_to_candidate_handle",
        "result_sha256",
    }
)
_FAILURE_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "run_id",
        "failure_code",
        "candidate_output_path",
        "source_mutated",
        "save_performed",
    }
)
_CANDIDATE_IDENTITY_FIELDS = frozenset({"path", "file_id"})
_COMPONENT_RESULT_FIELDS = frozenset(
    {"group_id", "logical_component_id", "source_handles", "candidate_handles"}
)
_HANDLE_MAPPING_FIELDS = frozenset({"source_handle", "candidate_handle"})
_PROVENANCE_FIELDS = frozenset(
    {
        "schema_version",
        "provenance_mode",
        "source_reference",
        "source_current_observation",
        "candidate_output_identity",
        "candidate_output_sha256",
        "inspection_sha256",
        "extraction_result_sha256",
        "provenance_sha256",
    }
)


class StandaloneDwgExtractionError(ValueError):
    """Categorical refusal from the standalone-DWG packet boundary."""


def _fail(code: str) -> None:
    raise StandaloneDwgExtractionError(code)


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(code)
    return dict(value)


def _closed(value: object, fields: frozenset[str], code: str) -> dict[str, object]:
    item = _mapping(value, code)
    if set(item) != fields:
        _fail(code)
    return item


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value or _CONTROL_RE.search(value):
        _fail(code)
    return value


def _identifier(value: object, code: str) -> str:
    text = _text(value, code)
    if _IDENTIFIER_RE.fullmatch(text) is None:
        _fail(code)
    return text


def _sha256(value: object, code: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _integer(value: object, code: str) -> int:
    if type(value) is not int or value < 0:
        _fail(code)
    return value


def _finite_number(value: object, code: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code)
    if isinstance(value, float) and not math.isfinite(value):
        _fail(code)
    return value


def _absolute_path(value: object, code: str) -> str:
    text = _text(value, code)
    if _WINDOWS_ABSOLUTE_RE.match(text) is None:
        _fail(code)
    return ntpath.normpath(text.replace("/", "\\"))


def _path_key(value: str) -> str:
    return ntpath.normcase(ntpath.normpath(value.replace("/", "\\")))


def _path_exists(value: str) -> bool:
    try:
        return Path(value).exists()
    except (OSError, ValueError):
        return False


def _handles(value: object, *, empty_code: str = "EMPTY_GROUP") -> list[str]:
    if not isinstance(value, list) or not value:
        _fail(empty_code)
    normalized: list[str] = []
    for handle in value:
        if type(handle) is not str or _HANDLE_RE.fullmatch(handle) is None:
            _fail("HANDLE_INVALID")
        normalized.append(handle.upper())
    return normalized


def _strings(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail(code)
    return [_identifier(item, code) for item in value]


def _ensure_unique(values: list[str], code: str) -> None:
    if len(values) != len(set(values)):
        _fail(code)


def _validate_selection_group(value: object) -> dict[str, object]:
    group = _closed(value, _SELECTION_GROUP_FIELDS, "REQUEST_SCHEMA_INVALID")
    result = {
        "group_id": _identifier(group["group_id"], "REQUEST_SCHEMA_INVALID"),
        "logical_component_id": _identifier(
            group["logical_component_id"], "REQUEST_SCHEMA_INVALID"
        ),
        "source_handles": _handles(group["source_handles"]),
        "expected_entity_types": _strings(
            group["expected_entity_types"], "REQUEST_SCHEMA_INVALID"
        ),
        "source_layer_expectations": _strings(
            group["source_layer_expectations"], "REQUEST_SCHEMA_INVALID"
        ),
    }
    return result


def _normalize_groups(
    value: object,
    *,
    fields: frozenset[str],
    code: str,
) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        _fail("EMPTY_GROUP")
    groups: list[dict[str, object]] = []
    seen_group_ids: set[str] = set()
    seen_handles: set[str] = set()
    for raw in value:
        group = _closed(raw, fields, code)
        group_id = _identifier(group["group_id"], code)
        logical_id = _identifier(group["logical_component_id"], code)
        handles = _handles(group["source_handles"])
        for handle in handles:
            if handle in seen_handles:
                _fail("DUPLICATE_HANDLE")
            seen_handles.add(handle)
        if group_id in seen_group_ids:
            _fail("DUPLICATE_GROUP")
        seen_group_ids.add(group_id)
        if fields == _SELECTION_GROUP_FIELDS:
            groups.append(
                {
                    "group_id": group_id,
                    "logical_component_id": logical_id,
                    "source_handles": handles,
                    "expected_entity_types": _strings(
                        group["expected_entity_types"], code
                    ),
                    "source_layer_expectations": _strings(
                        group["source_layer_expectations"], code
                    ),
                }
            )
        else:
            entity_types = _strings(group["entity_types"], code)
            layers = _strings(group["layers"], code)
            groups.append(
                {
                    "group_id": group_id,
                    "logical_component_id": logical_id,
                    "source_handles": handles,
                    "entity_types": entity_types,
                    "layers": layers,
                    "signature_sha256": _sha256(
                        group["signature_sha256"], code
                    ),
                }
            )
    return groups


def validate_standalone_inspection_request(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate and detach a closed read-only standalone inspection request."""

    if not isinstance(payload, Mapping):
        _fail("REQUEST_SCHEMA_INVALID")
    if any(
        isinstance(key, str)
        and (key.startswith("candidate_input") or key == "candidate_input_path")
        for key in payload
    ):
        _fail("CANDIDATE_INPUT_FORBIDDEN")
    request = _closed(payload, _INSPECTION_REQUEST_FIELDS, "REQUEST_SCHEMA_INVALID")
    if request["schema_version"] != STANDALONE_INSPECTION_SCHEMA_VERSION:
        _fail("REQUEST_SCHEMA_INVALID")
    result: dict[str, object] = {
        "schema_version": request["schema_version"],
        "request_id": _identifier(request["request_id"], "REQUEST_SCHEMA_INVALID"),
        "run_id": _identifier(request["run_id"], "REQUEST_SCHEMA_INVALID"),
        "source_drawing_path": _absolute_path(
            request["source_drawing_path"], "REQUEST_SCHEMA_INVALID"
        ),
        "source_drawing_sha256": _sha256(
            request["source_drawing_sha256"], "HASH_INVALID"
        ),
        "source_setup_audit_sha256": _sha256(
            request["source_setup_audit_sha256"], "HASH_INVALID"
        ),
        "selection_groups": _normalize_groups(
            request["selection_groups"],
            fields=_SELECTION_GROUP_FIELDS,
            code="REQUEST_SCHEMA_INVALID",
        ),
        "expected_dbmod": _integer(request["expected_dbmod"], "REQUEST_SCHEMA_INVALID"),
        "approval": None,
    }
    if request["approval"] is not None:
        _fail("REQUEST_SCHEMA_INVALID")
    return result


def _source_identity(value: object) -> dict[str, object]:
    source = _mapping(value, "RESULT_SCHEMA_INVALID")
    allowed = {"path", "sha256", "dbmod", "xref_count"}
    if set(source) - allowed or not {"path", "sha256", "dbmod"}.issubset(source):
        _fail("RESULT_SCHEMA_INVALID")
    result: dict[str, object] = {
        "path": _absolute_path(source["path"], "RESULT_SCHEMA_INVALID"),
        "sha256": _sha256(source["sha256"], "RESULT_SCHEMA_INVALID"),
        "dbmod": _integer(source["dbmod"], "RESULT_SCHEMA_INVALID"),
    }
    if "xref_count" in source:
        result["xref_count"] = _integer(source["xref_count"], "RESULT_SCHEMA_INVALID")
        if result["xref_count"] != 0:
            _fail("XREF_UNSUPPORTED")
    return result


def standalone_inspection_result_sha256(payload: Mapping[str, object]) -> str:
    """Return the owner-derived checksum for an inspection result."""

    if not isinstance(payload, Mapping):
        _fail("RESULT_SCHEMA_INVALID")
    material = {key: deepcopy(value) for key, value in payload.items() if key != "inspection_sha256"}
    try:
        return canonical_json_sha256(material)
    except (TypeError, ValueError):
        _fail("RESULT_SCHEMA_INVALID")


def validate_standalone_inspection_result(
    payload: Mapping[str, object],
    request: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate a read-only inspection and normalize its owner checksum."""

    result = _closed(payload, _INSPECTION_RESULT_FIELDS, "RESULT_SCHEMA_INVALID")
    if result["schema_version"] != STANDALONE_INSPECTION_RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_INVALID")
    normalized: dict[str, object] = {
        "schema_version": result["schema_version"],
        "inspection_id": _identifier(result["inspection_id"], "RESULT_SCHEMA_INVALID"),
        "request_id": _identifier(result["request_id"], "RESULT_SCHEMA_INVALID"),
        "source_identity": _source_identity(result["source_identity"]),
        "source_sha256_before": _sha256(
            result["source_sha256_before"], "RESULT_SCHEMA_INVALID"
        ),
        "source_sha256_after": _sha256(
            result["source_sha256_after"], "RESULT_SCHEMA_INVALID"
        ),
        "dbmod_before": _integer(result["dbmod_before"], "RESULT_SCHEMA_INVALID"),
        "dbmod_after": _integer(result["dbmod_after"], "RESULT_SCHEMA_INVALID"),
        "read_only": result["read_only"],
        "groups": _normalize_groups(
            result["groups"], fields=_INSPECTION_GROUP_FIELDS, code="RESULT_SCHEMA_INVALID"
        ),
        "warnings": result["warnings"],
        "conflicts": result["conflicts"],
        "changed": result["changed"],
        "eligible": result["eligible"],
        "inspection_sha256": "",
    }
    if normalized["read_only"] is not True:
        _fail("READ_ONLY_REQUIRED")
    if normalized["source_sha256_before"] != normalized["source_sha256_after"]:
        _fail("SOURCE_HASH_DRIFT")
    if normalized["dbmod_before"] != normalized["dbmod_after"]:
        _fail("DBMOD_DRIFT")
    if normalized["source_identity"]["sha256"] != normalized["source_sha256_before"]:
        _fail("SOURCE_HASH_MISMATCH")
    if normalized["source_identity"]["dbmod"] != normalized["dbmod_before"]:
        _fail("DBMOD_MISMATCH")
    if normalized["changed"] is not False:
        _fail("SOURCE_CHANGED")
    if normalized["eligible"] is not True:
        _fail("INSPECTION_INELIGIBLE")
    if not isinstance(normalized["warnings"], list) or not all(
        type(item) is str for item in normalized["warnings"]
    ):
        _fail("RESULT_SCHEMA_INVALID")
    if not isinstance(normalized["conflicts"], list) or not all(
        type(item) is str for item in normalized["conflicts"]
    ):
        _fail("RESULT_SCHEMA_INVALID")
    if normalized["conflicts"]:
        _fail("CONFLICTS_PRESENT")
    if normalized["warnings"]:
        _fail("WARNINGS_PRESENT")
    if request is not None:
        expected = validate_standalone_inspection_request(request)
        if normalized["request_id"] != expected["request_id"]:
            _fail("REQUEST_ID_MISMATCH")
        if normalized["source_identity"]["path"] != expected["source_drawing_path"]:
            _fail("SOURCE_PATH_MISMATCH")
        if normalized["source_sha256_before"] != expected["source_drawing_sha256"]:
            _fail("SOURCE_HASH_MISMATCH")
        if normalized["dbmod_before"] != expected["expected_dbmod"]:
            _fail("DBMOD_MISMATCH")
        expected_groups = expected["selection_groups"]
        actual_groups = normalized["groups"]
        if [group["group_id"] for group in actual_groups] != [
            group["group_id"] for group in expected_groups
        ]:
            _fail("GROUP_COVERAGE_MISMATCH")
        for expected_group, actual_group in zip(expected_groups, actual_groups):
            if (
                actual_group["logical_component_id"] != expected_group["logical_component_id"]
                or actual_group["source_handles"] != expected_group["source_handles"]
                or not set(expected_group["expected_entity_types"]).issubset(
                    actual_group["entity_types"]
                )
                or not set(expected_group["source_layer_expectations"]).issubset(
                    actual_group["layers"]
                )
            ):
                _fail("GROUP_COVERAGE_MISMATCH")
    supplied_checksum = _sha256(
        result["inspection_sha256"], "CHECKSUM_INVALID"
    )
    expected_checksum = standalone_inspection_result_sha256(normalized)
    if supplied_checksum != expected_checksum:
        _fail("CHECKSUM_MISMATCH")
    normalized["inspection_sha256"] = supplied_checksum
    return deepcopy(normalized)


def _approval(value: object) -> dict[str, object]:
    approval = _closed(value, _APPROVAL_FIELDS, "APPROVAL_INVALID")
    if approval["status"] != "APPROVED":
        _fail("APPROVAL_INVALID")
    return {
        "reference": _identifier(approval["reference"], "APPROVAL_INVALID"),
        "status": "APPROVED",
    }


def _transform(value: object) -> dict[str, object]:
    transform = _closed(value, _TRANSFORM_FIELDS, "TRANSFORM_INVALID")
    translation = _closed(transform["translation"], _POINT_FIELDS, "TRANSFORM_INVALID")
    normalized_translation = {
        axis: _finite_number(translation[axis], "TRANSFORM_INVALID")
        for axis in ("x", "y", "z")
    }
    scale = _finite_number(transform["uniform_scale"], "TRANSFORM_INVALID")
    if scale <= 0:
        _fail("TRANSFORM_INVALID")
    return {
        "rotation_degrees": _finite_number(
            transform["rotation_degrees"], "TRANSFORM_INVALID"
        ),
        "translation": normalized_translation,
        "uniform_scale": scale,
    }


def build_standalone_extraction_plan(
    payload: Mapping[str, object],
    inspection_result: Mapping[str, object] | None = None,
    inspection_request: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate and detach an EMPTY_NEW_DATABASE extraction plan."""

    if not isinstance(payload, Mapping):
        _fail("PLAN_SCHEMA_INVALID")
    if any(
        isinstance(key, str)
        and (key.startswith("candidate_input") or key == "candidate_input_path")
        for key in payload
    ):
        _fail("CANDIDATE_INPUT_FORBIDDEN")
    plan = _closed(payload, _EXTRACTION_PLAN_FIELDS, "PLAN_SCHEMA_INVALID")
    normalized_path = _absolute_path(plan["candidate_output_path"], "PLAN_SCHEMA_INVALID")
    if _path_exists(normalized_path):
        _fail("CANDIDATE_OUTPUT_NOT_ABSENT")
    if plan["candidate_base_model"] != "EMPTY_NEW_DATABASE":
        _fail("CANDIDATE_BASE_INVALID")
    if plan["transform_policy"] != "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY":
        _fail("TRANSFORM_POLICY_INVALID")
    components_raw = plan["components"]
    if not isinstance(components_raw, list) or not components_raw:
        _fail("PLAN_SCHEMA_INVALID")
    components: list[dict[str, object]] = []
    seen_groups: set[str] = set()
    seen_handles: set[str] = set()
    for raw in components_raw:
        component = _closed(raw, _COMPONENT_PLAN_FIELDS, "PLAN_SCHEMA_INVALID")
        group_id = _identifier(component["group_id"], "PLAN_SCHEMA_INVALID")
        if group_id in seen_groups:
            _fail("DUPLICATE_GROUP")
        seen_groups.add(group_id)
        logical_id = _identifier(component["logical_component_id"], "PLAN_SCHEMA_INVALID")
        handles = _handles(component["source_handles"])
        for handle in handles:
            if handle in seen_handles:
                _fail("DUPLICATE_HANDLE")
            seen_handles.add(handle)
        components.append(
            {
                "group_id": group_id,
                "logical_component_id": logical_id,
                "source_handles": handles,
                "transform": _transform(component["transform"]),
            }
        )
    normalized = {
        "plan_id": _identifier(plan["plan_id"], "PLAN_SCHEMA_INVALID"),
        "request_id": _identifier(plan["request_id"], "PLAN_SCHEMA_INVALID"),
        "run_id": _identifier(plan["run_id"], "PLAN_SCHEMA_INVALID"),
        "inspection_id": _identifier(plan["inspection_id"], "PLAN_SCHEMA_INVALID"),
        "inspection_sha256": _sha256(plan["inspection_sha256"], "HASH_INVALID"),
        "source_drawing_sha256": _sha256(plan["source_drawing_sha256"], "HASH_INVALID"),
        "candidate_output_path": normalized_path,
        "candidate_base_model": "EMPTY_NEW_DATABASE",
        "components": components,
        "transform_policy": "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        "approval": _approval(plan["approval"]),
    }
    if inspection_request is not None:
        request = validate_standalone_inspection_request(inspection_request)
        if (
            normalized["request_id"] != request["request_id"]
            or normalized["run_id"] != request["run_id"]
            or normalized["source_drawing_sha256"] != request["source_drawing_sha256"]
        ):
            _fail("PLAN_INSPECTION_MISMATCH")
    if inspection_result is not None:
        inspection = validate_standalone_inspection_result(
            inspection_result, inspection_request
        )
        if (
            normalized["request_id"] != inspection["request_id"]
            or normalized["inspection_id"] != inspection["inspection_id"]
            or normalized["inspection_sha256"] != inspection["inspection_sha256"]
            or normalized["source_drawing_sha256"]
            != inspection["source_sha256_before"]
        ):
            _fail("PLAN_INSPECTION_MISMATCH")
        expected_groups = {
            group["group_id"]: set(group["source_handles"])
            for group in inspection["groups"]
        }
        for component in normalized["components"]:
            if component["group_id"] not in expected_groups or not set(
                component["source_handles"]
            ).issubset(expected_groups[component["group_id"]]):
                _fail("PLAN_INSPECTION_MISMATCH")
        if _path_key(normalized["candidate_output_path"]) == _path_key(
            inspection["source_identity"]["path"]
        ):
            _fail("OUTPUT_ALIASES_SOURCE")
    return deepcopy(normalized)


def _candidate_identity(value: object) -> dict[str, object]:
    identity = _closed(value, _CANDIDATE_IDENTITY_FIELDS, "RESULT_SCHEMA_INVALID")
    return {
        "path": _absolute_path(identity["path"], "RESULT_SCHEMA_INVALID"),
        "file_id": _identifier(identity["file_id"], "RESULT_SCHEMA_INVALID"),
    }


def _result_components(value: object) -> tuple[list[dict[str, object]], set[str], set[str]]:
    if not isinstance(value, list) or not value:
        _fail("RESULT_SCHEMA_INVALID")
    components: list[dict[str, object]] = []
    groups: set[str] = set()
    source_handles: set[str] = set()
    candidate_handles: set[str] = set()
    logical_ids: set[str] = set()
    for raw in value:
        component = _closed(raw, _COMPONENT_RESULT_FIELDS, "RESULT_SCHEMA_INVALID")
        group_id = _identifier(component["group_id"], "RESULT_SCHEMA_INVALID")
        logical_id = _identifier(component["logical_component_id"], "RESULT_SCHEMA_INVALID")
        if group_id in groups or logical_id in logical_ids:
            _fail("DUPLICATE_COMPONENT")
        groups.add(group_id)
        logical_ids.add(logical_id)
        sources = _handles(component["source_handles"])
        candidates = _handles(component["candidate_handles"])
        for source in sources:
            if source in source_handles:
                _fail("DUPLICATE_HANDLE")
            source_handles.add(source)
        for candidate in candidates:
            if candidate in candidate_handles:
                _fail("DUPLICATE_HANDLE")
            candidate_handles.add(candidate)
        components.append(
            {
                "group_id": group_id,
                "logical_component_id": logical_id,
                "source_handles": sources,
                "candidate_handles": candidates,
            }
        )
    return components, source_handles, candidate_handles


def standalone_extraction_result_sha256(payload: Mapping[str, object]) -> str:
    """Return the owner-derived checksum for an extraction result."""

    if not isinstance(payload, Mapping):
        _fail("RESULT_SCHEMA_INVALID")
    material = {key: deepcopy(value) for key, value in payload.items() if key != "result_sha256"}
    try:
        return canonical_json_sha256(material)
    except (TypeError, ValueError):
        _fail("RESULT_SCHEMA_INVALID")


def _validate_failure_result(payload: Mapping[str, object]) -> dict[str, object]:
    result = _closed(payload, _FAILURE_RESULT_FIELDS, "RESULT_SCHEMA_INVALID")
    if result["schema_version"] != STANDALONE_EXTRACTION_RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_INVALID")
    if result["failure_code"] not in {
        "CANDIDATE_OUTPUT_NOT_ABSENT",
        "FORBIDDEN_WRITE_TARGET",
        "SOURCE_MUTATED",
        "OUTPUT_NOT_REOPENABLE",
        "CLEANUP_FAILED",
    }:
        _fail("RESULT_SCHEMA_INVALID")
    if result["source_mutated"] is not False:
        _fail("SOURCE_MUTATED")
    if result["save_performed"] is not False:
        _fail("SAVE_NOT_PERFORMED")
    return {
        "schema_version": result["schema_version"],
        "request_id": _identifier(result["request_id"], "RESULT_SCHEMA_INVALID"),
        "run_id": _identifier(result["run_id"], "RESULT_SCHEMA_INVALID"),
        "failure_code": result["failure_code"],
        "candidate_output_path": _absolute_path(
            result["candidate_output_path"], "RESULT_SCHEMA_INVALID"
        ),
        "source_mutated": False,
        "save_performed": False,
    }


def validate_standalone_extraction_result(
    payload: Mapping[str, object],
    *,
    source_path: str | None = None,
    plan: Mapping[str, object] | None = None,
    inspection_result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate and detach a successful or fail-closed extraction result."""

    if not isinstance(payload, Mapping):
        _fail("RESULT_SCHEMA_INVALID")
    if "failure_code" in payload:
        return _validate_failure_result(payload)
    result = _closed(payload, _EXTRACTION_RESULT_FIELDS, "RESULT_SCHEMA_INVALID")
    if result["schema_version"] != STANDALONE_EXTRACTION_RESULT_SCHEMA_VERSION:
        _fail("RESULT_SCHEMA_INVALID")
    if result["candidate_base_model"] != "EMPTY_NEW_DATABASE":
        _fail("CANDIDATE_BASE_INVALID")
    if result["source_mutated"] is not False:
        _fail("SOURCE_MUTATED")
    if result["save_performed"] is not True:
        _fail("SAVE_NOT_PERFORMED")
    before = _integer(result["source_dbmod_before"], "RESULT_SCHEMA_INVALID")
    after = _integer(result["source_dbmod_after"], "RESULT_SCHEMA_INVALID")
    if before != after:
        _fail("DBMOD_DRIFT")
    identity = _candidate_identity(result["candidate_output_identity"])
    if source_path is not None and _path_key(identity["path"]) == _path_key(
        _absolute_path(source_path, "SOURCE_PATH_INVALID")
    ):
        _fail("OUTPUT_ALIASES_SOURCE")
    components, source_handles, candidate_handles = _result_components(
        result["components"]
    )
    mappings_raw = result["source_handle_to_candidate_handle"]
    if not isinstance(mappings_raw, list) or not mappings_raw:
        _fail("MAPPING_INVALID")
    mappings: list[dict[str, str]] = []
    mapped_sources: set[str] = set()
    mapped_candidates: set[str] = set()
    for raw in mappings_raw:
        mapping = _closed(raw, _HANDLE_MAPPING_FIELDS, "MAPPING_INVALID")
        source = _handles([mapping["source_handle"]])[0]
        candidate = _handles([mapping["candidate_handle"]])[0]
        if source in mapped_sources or candidate in mapped_candidates:
            _fail("MAPPING_NOT_ONE_TO_ONE")
        mapped_sources.add(source)
        mapped_candidates.add(candidate)
        mappings.append({"source_handle": source, "candidate_handle": candidate})
    if mapped_sources != source_handles or mapped_candidates != candidate_handles:
        _fail("MAPPING_COVERAGE_MISMATCH")
    normalized = {
        "schema_version": result["schema_version"],
        "request_id": _identifier(result["request_id"], "RESULT_SCHEMA_INVALID"),
        "run_id": _identifier(result["run_id"], "RESULT_SCHEMA_INVALID"),
        "source_drawing_sha256": _sha256(
            result["source_drawing_sha256"], "HASH_INVALID"
        ),
        "candidate_base_model": "EMPTY_NEW_DATABASE",
        "candidate_output_sha256": _sha256(
            result["candidate_output_sha256"], "HASH_INVALID"
        ),
        "candidate_output_identity": identity,
        "source_mutated": False,
        "source_dbmod_before": before,
        "source_dbmod_after": after,
        "save_performed": True,
        "components": components,
        "source_handle_to_candidate_handle": mappings,
        "result_sha256": "",
    }
    supplied_checksum = _sha256(result["result_sha256"], "CHECKSUM_INVALID")
    expected_checksum = standalone_extraction_result_sha256(normalized)
    if supplied_checksum != expected_checksum:
        _fail("CHECKSUM_MISMATCH")
    normalized["result_sha256"] = supplied_checksum
    if plan is not None:
        expected_plan = build_standalone_extraction_plan(plan)
        if (
            normalized["request_id"] != expected_plan["request_id"]
            or normalized["run_id"] != expected_plan["run_id"]
            or normalized["source_drawing_sha256"]
            != expected_plan["source_drawing_sha256"]
            or normalized["candidate_output_identity"]["path"]
            != expected_plan["candidate_output_path"]
        ):
            _fail("RESULT_PLAN_MISMATCH")
    if inspection_result is not None:
        inspection = validate_standalone_inspection_result(inspection_result)
        if normalized["source_drawing_sha256"] != inspection["source_sha256_before"]:
            _fail("SOURCE_HASH_MISMATCH")
        if _path_key(normalized["candidate_output_identity"]["path"]) == _path_key(
            inspection["source_identity"]["path"]
        ):
            _fail("OUTPUT_ALIASES_SOURCE")
    return deepcopy(normalized)


def standalone_provenance_context_sha256(payload: Mapping[str, object]) -> str:
    """Return the owner-derived checksum for a pre-R3 context."""

    if not isinstance(payload, Mapping):
        _fail("PROVENANCE_SCHEMA_INVALID")
    material = {key: deepcopy(value) for key, value in payload.items() if key != "provenance_sha256"}
    try:
        return canonical_json_sha256(material)
    except (TypeError, ValueError):
        _fail("PROVENANCE_SCHEMA_INVALID")


def _validate_source_dara(
    reference: Mapping[str, object],
    observation: Mapping[str, object],
    source_bytes: bytes | None,
) -> tuple[dict[str, object], dict[str, object]]:
    from cad_agent.drawing_artifact_reference import (
        validate_drawing_artifact_current_observation,
        validate_drawing_artifact_reference,
    )

    try:
        normalized_reference = validate_drawing_artifact_reference(
            reference, expected_artifact_role="BASELINE"
        )
        normalized_observation = validate_drawing_artifact_current_observation(
            observation
        )
    except Exception as error:
        _fail("SOURCE_BASELINE_INVALID")
    if normalized_observation["reference_id"] != normalized_reference["reference_id"]:
        _fail("SOURCE_BASELINE_MISMATCH")
    if normalized_observation["reference_sha256"] != normalized_reference["reference_sha256"]:
        _fail("SOURCE_BASELINE_MISMATCH")
    if normalized_observation["comparison"] != "CURRENT":
        _fail("SOURCE_BASELINE_STALE")
    if source_bytes is not None:
        from cad_agent.drawing_artifact_reference import (
            require_current_drawing_artifact_reference,
        )

        try:
            require_current_drawing_artifact_reference(
                reference=normalized_reference,
                observation=normalized_observation,
                artifact_bytes=source_bytes,
            )
        except Exception:
            _fail("SOURCE_BASELINE_STALE")
    return deepcopy(normalized_reference), deepcopy(normalized_observation)


def build_standalone_provenance_context(
    *,
    source_reference: Mapping[str, object] | None = None,
    source_current_observation: Mapping[str, object] | None = None,
    source_observation: Mapping[str, object] | None = None,
    source_artifact_bytes: bytes | None = None,
    run_id: str | None = None,
    project_id: str | None = None,
    drawing_id: str | None = None,
    source_upstream_evidence: Mapping[str, object] | None = None,
    observation_evidence_sha256: str | None = None,
    candidate_output_identity: Mapping[str, object] | None = None,
    candidate_output_sha256: str | None = None,
    inspection_result: Mapping[str, object] | None = None,
    extraction_result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build only the detached pre-R3 provenance context.

    The function accepts an existing validated source DARA pair, or issues a
    BASELINE pair when the caller supplies the source bytes and explicit DARA
    scope/evidence.  It deliberately has no candidate-reference output.
    """

    if source_current_observation is not None and source_observation is not None:
        _fail("SOURCE_BASELINE_INVALID")
    observation = source_current_observation or source_observation
    if extraction_result is None or inspection_result is None:
        _fail("PROVENANCE_INPUT_MISSING")
    inspection = validate_standalone_inspection_result(inspection_result)
    extraction = validate_standalone_extraction_result(extraction_result)
    if "failure_code" in extraction:
        _fail("EXTRACTION_NOT_SUCCESSFUL")
    if extraction["source_drawing_sha256"] != inspection["source_sha256_before"]:
        _fail("SOURCE_HASH_MISMATCH")
    candidate_identity = _candidate_identity(
        candidate_output_identity or extraction["candidate_output_identity"]
    )
    candidate_sha = _sha256(
        candidate_output_sha256 or extraction["candidate_output_sha256"],
        "HASH_INVALID",
    )
    if candidate_identity != extraction["candidate_output_identity"]:
        _fail("CANDIDATE_IDENTITY_MISMATCH")
    if candidate_sha != extraction["candidate_output_sha256"]:
        _fail("CANDIDATE_HASH_MISMATCH")
    if _path_key(candidate_identity["path"]) == _path_key(inspection["source_identity"]["path"]):
        _fail("OUTPUT_ALIASES_SOURCE")

    if source_reference is None:
        if source_artifact_bytes is None or not isinstance(source_artifact_bytes, bytes):
            _fail("SOURCE_BASELINE_INVALID")
        if not all(isinstance(value, str) and value for value in (run_id, project_id, drawing_id)):
            _fail("SOURCE_BASELINE_INVALID")
        if source_upstream_evidence is None:
            _fail("SOURCE_BASELINE_INVALID")
        if observation_evidence_sha256 is None:
            _fail("SOURCE_BASELINE_INVALID")
        from cad_agent.drawing_artifact_reference import (
            issue_drawing_artifact_reference,
            observe_drawing_artifact_currentness,
        )

        try:
            source_reference = issue_drawing_artifact_reference(
                run_id=run_id,
                project_id=project_id,
                drawing_id=drawing_id,
                artifact_role="BASELINE",
                artifact_bytes=source_artifact_bytes,
                upstream_evidence=source_upstream_evidence,
            )
            observation = observe_drawing_artifact_currentness(
                reference=source_reference,
                artifact_bytes=source_artifact_bytes,
                observation_evidence_sha256=observation_evidence_sha256,
            )
        except Exception:
            _fail("SOURCE_BASELINE_INVALID")
    if observation is None:
        _fail("SOURCE_BASELINE_INVALID")
    normalized_reference, normalized_observation = _validate_source_dara(
        source_reference, observation, source_artifact_bytes
    )
    if normalized_reference["artifact_sha256"] != extraction["source_drawing_sha256"]:
        _fail("SOURCE_HASH_MISMATCH")
    normalized = {
        "schema_version": STANDALONE_PRE_R3_PROVENANCE_SCHEMA_VERSION,
        "provenance_mode": STANDALONE_PROVENANCE_MODE,
        "source_reference": normalized_reference,
        "source_current_observation": normalized_observation,
        "candidate_output_identity": candidate_identity,
        "candidate_output_sha256": candidate_sha,
        "inspection_sha256": inspection["inspection_sha256"],
        "extraction_result_sha256": extraction["result_sha256"],
        "provenance_sha256": "",
    }
    normalized["provenance_sha256"] = standalone_provenance_context_sha256(normalized)
    return deepcopy(normalized)


__all__ = [
    "StandaloneDwgExtractionError",
    "STANDALONE_INSPECTION_SCHEMA_VERSION",
    "STANDALONE_INSPECTION_RESULT_SCHEMA_VERSION",
    "STANDALONE_EXTRACTION_SCHEMA_VERSION",
    "STANDALONE_EXTRACTION_RESULT_SCHEMA_VERSION",
    "STANDALONE_PRE_R3_PROVENANCE_SCHEMA_VERSION",
    "STANDALONE_PROVENANCE_MODE",
    "validate_standalone_inspection_request",
    "validate_standalone_inspection_result",
    "standalone_inspection_result_sha256",
    "build_standalone_extraction_plan",
    "validate_standalone_extraction_result",
    "standalone_extraction_result_sha256",
    "build_standalone_provenance_context",
    "standalone_provenance_context_sha256",
]
