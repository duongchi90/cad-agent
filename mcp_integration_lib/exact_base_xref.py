"""Closed offline contracts for exact-base Xref inspection and extraction plans."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import PurePosixPath
import re


INSPECTION_SCHEMA_VERSION = "exact-base-xref-inspection-1.0"
EXTRACTION_PLAN_SCHEMA_VERSION = "exact-base-xref-extraction-plan-1.0"
REUSED_FROM_BASE_CAD = "REUSED_FROM_BASE_CAD"
TRANSFORM_POLICY = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY"

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:")

_INSPECTION_FIELDS = frozenset(
    {
        "base_source",
        "capture_timestamp",
        "changed",
        "components",
        "conflicts",
        "critical_dimensions",
        "dbmod_after",
        "dbmod_before",
        "eligible",
        "identity_observations",
        "inspection_id",
        "request_id",
        "run_id",
        "schema_version",
        "target_drawing_sha256",
        "warnings",
        "xref",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "approval",
        "base_source",
        "components",
        "impacted_views",
        "inspection_id",
        "plan_id",
        "provenance",
        "request_id",
        "run_id",
        "schema_version",
        "source_revision",
        "target_drawing_sha256",
        "transform_policy",
    }
)
_BASE_SOURCE_FIELDS = frozenset({"relative_path", "revision", "sha256", "source_id"})
_IDENTITY_FIELDS = frozenset({"field", "observed", "status", "target"})
_DIMENSION_FIELDS = frozenset(
    {"control", "observed", "status", "target", "tolerance", "unit"}
)
_XREF_FIELDS = frozenset({"name", "read_only", "status"})
_COMPONENT_FIELDS = frozenset(
    {
        "bounding",
        "component_type",
        "logical_component_id",
        "provenance",
        "source_block",
        "source_handle",
        "source_layer",
    }
)
_BOUNDING_FIELDS = frozenset({"max", "min"})
_POINT_FIELDS = frozenset({"x", "y", "z"})
_PLAN_COMPONENT_FIELDS = _COMPONENT_FIELDS | frozenset({"transform"})
_TRANSFORM_FIELDS = frozenset(
    {"rotation_degrees", "translation", "uniform_scale"}
)
_APPROVAL_FIELDS = frozenset({"reference", "status"})
_VIEW_FIELDS = frozenset({"identity", "name"})
_REQUIRED_IDENTITY_FIELDS = frozenset({"model", "vehicle"})
_REQUIRED_DIMENSION_CONTROLS = frozenset(
    {"axle", "cabin", "chassis", "track", "wheelbase"}
)
_FORBIDDEN_FIELDS = frozenset(
    {
        "approved",
        "autocad",
        "copied_entities",
        "copied_target_handle",
        "copied_target_handles",
        "deformation",
        "entity_handles",
        "global_transform",
        "matrix",
        "mutated",
        "mutation",
        "pass",
        "passed",
        "publish",
        "published",
        "publisher",
        "repair",
        "reflection",
        "save",
        "saved",
        "target_entity_handle",
        "target_entity_handles",
        "target_handle",
        "target_handles",
        "verdict",
    }
)


class ExactBaseXrefError(ValueError):
    """Raised when an exact-base Xref inspection or plan is not closed and safe."""


def _error(message: str) -> None:
    raise ExactBaseXrefError(message)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _error(f"{context} must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        _error(f"{context} keys must be strings")
    return dict(value)


def _closed_fields(
    value: object, expected: frozenset[str], context: str
) -> dict[str, object]:
    result = _mapping(value, context)
    unknown = set(result) - expected
    missing = expected - set(result)
    if unknown:
        _error(f"{context} contains unknown field(s): {sorted(unknown)}")
    if missing:
        _error(f"{context} is missing field(s): {sorted(missing)}")
    return result


def _reject_forbidden_fields(value: object, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                _error(f"{path} keys must be strings")
            if key.casefold() in _FORBIDDEN_FIELDS:
                _error(f"{path}.{key} is not allowed")
            _reject_forbidden_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_fields(nested, f"{path}[{index}]")


def _string(value: object, context: str, *, identifier: bool = False) -> str:
    if type(value) is not str or not value or len(value) > 512:
        _error(f"{context} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _error(f"{context} contains a control character")
    if identifier and not _ID_PATTERN.fullmatch(value):
        _error(f"{context} is not a safe identifier")
    return value


def _hash(value: object, context: str) -> str:
    if type(value) is not str or not _HASH_PATTERN.fullmatch(value):
        _error(f"{context} must be a lowercase 64-character SHA-256")
    return value


def _timestamp(value: object, context: str) -> str:
    if type(value) is not str or not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        _error(f"{context} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ExactBaseXrefError(f"{context} is not a valid timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        _error(f"{context} must be UTC")
    return value


def _number(value: object, context: str, *, minimum: float, maximum: float) -> float | int:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        _error(f"{context} must be a finite number")
    if not minimum <= float(value) <= maximum:
        _error(f"{context} is outside the allowed range")
    return value


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        _error(f"{context} must be a boolean")
    return value


def _list(value: object, context: str) -> list[object]:
    if type(value) is not list:
        _error(f"{context} must be a JSON list")
    return value


def _safe_relative_path(value: object, context: str) -> str:
    path = _string(value, context)
    if (
        path.startswith(("/", "\\"))
        or _DRIVE_PATH_PATTERN.match(path)
        or "\\" in path
        or "//" in path
        or ":" in path
        or "\x00" in path
    ):
        _error(f"{context} must use a safe relative POSIX path")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {".", ".."} for part in parts):
        _error(f"{context} must not contain traversal")
    return path


def _base_source(value: object, context: str = "base_source") -> dict[str, object]:
    result = _closed_fields(value, _BASE_SOURCE_FIELDS, context)
    _string(result["source_id"], f"{context}.source_id", identifier=True)
    _safe_relative_path(result["relative_path"], f"{context}.relative_path")
    _hash(result["sha256"], f"{context}.sha256")
    _string(result["revision"], f"{context}.revision", identifier=True)
    return result


def _point(value: object, context: str) -> dict[str, object]:
    result = _closed_fields(value, _POINT_FIELDS, context)
    for axis in ("x", "y", "z"):
        _number(result[axis], f"{context}.{axis}", minimum=-1_000_000_000, maximum=1_000_000_000)
    return result


def _bounding(value: object, context: str) -> dict[str, object]:
    result = _closed_fields(value, _BOUNDING_FIELDS, context)
    result["min"] = _point(result["min"], f"{context}.min")
    result["max"] = _point(result["max"], f"{context}.max")
    for axis in ("x", "y", "z"):
        if result["min"][axis] > result["max"][axis]:
            _error(f"{context}.{axis} min must not exceed max")
    return result


def _warnings_or_conflicts(value: object, context: str) -> list[object]:
    result = _list(value, context)
    for index, item in enumerate(result):
        _string(item, f"{context}[{index}]")
    return result


def _identity_observations(value: object) -> list[dict[str, object]]:
    observations = _list(value, "identity_observations")
    if len(observations) != len(_REQUIRED_IDENTITY_FIELDS):
        _error("identity_observations must contain vehicle and model exactly once")
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(observations):
        result = _closed_fields(item, _IDENTITY_FIELDS, f"identity_observations[{index}]")
        field = _string(result["field"], f"identity_observations[{index}].field", identifier=True)
        if field not in _REQUIRED_IDENTITY_FIELDS or field in seen:
            _error("identity_observations must contain vehicle and model exactly once")
        seen.add(field)
        observed = _string(result["observed"], f"identity_observations[{index}].observed")
        target = _string(result["target"], f"identity_observations[{index}].target")
        status = result["status"]
        if status not in {"FAIL", "PASS"}:
            _error(f"identity_observations[{index}].status must be PASS or FAIL")
        matches = observed == target
        if (status == "PASS") != matches:
            _error(f"identity_observations[{index}] status does not match observed identity")
        normalized.append(result)
    if seen != _REQUIRED_IDENTITY_FIELDS:
        _error("identity_observations must contain vehicle and model exactly once")
    return normalized


def _critical_dimensions(value: object) -> list[dict[str, object]]:
    dimensions = _list(value, "critical_dimensions")
    if len(dimensions) != len(_REQUIRED_DIMENSION_CONTROLS):
        _error("critical_dimensions must contain every required control exactly once")
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(dimensions):
        context = f"critical_dimensions[{index}]"
        result = _closed_fields(item, _DIMENSION_FIELDS, context)
        control = _string(result["control"], f"{context}.control", identifier=True)
        if control not in _REQUIRED_DIMENSION_CONTROLS or control in seen:
            _error("critical_dimensions must contain every required control exactly once")
        seen.add(control)
        observed = _number(result["observed"], f"{context}.observed", minimum=-1_000_000_000, maximum=1_000_000_000)
        target = _number(result["target"], f"{context}.target", minimum=-1_000_000_000, maximum=1_000_000_000)
        tolerance = _number(result["tolerance"], f"{context}.tolerance", minimum=0, maximum=1_000_000_000)
        if result["unit"] not in {"in", "mm"}:
            _error(f"{context}.unit must be in or mm")
        status = result["status"]
        if status not in {"FAIL", "PASS"}:
            _error(f"{context}.status must be PASS or FAIL")
        within_tolerance = abs(float(observed) - float(target)) <= float(tolerance)
        if (status == "PASS") != within_tolerance:
            _error(f"{context} status does not match its tolerance comparison")
        normalized.append(result)
    if seen != _REQUIRED_DIMENSION_CONTROLS:
        _error("critical_dimensions must contain every required control exactly once")
    return normalized


def _xref(value: object) -> dict[str, object]:
    result = _closed_fields(value, _XREF_FIELDS, "xref")
    _string(result["name"], "xref.name", identifier=True)
    if result["status"] != "INSPECTED":
        _error("xref.status must be INSPECTED")
    _boolean(result["read_only"], "xref.read_only")
    return result


def _component(value: object, context: str = "component") -> dict[str, object]:
    result = _closed_fields(value, _COMPONENT_FIELDS, context)
    _string(result["source_handle"], f"{context}.source_handle", identifier=True)
    _string(result["source_layer"], f"{context}.source_layer")
    _string(result["source_block"], f"{context}.source_block")
    _string(result["logical_component_id"], f"{context}.logical_component_id", identifier=True)
    _string(result["component_type"], f"{context}.component_type", identifier=True)
    result["bounding"] = _bounding(result["bounding"], f"{context}.bounding")
    if result["provenance"] != REUSED_FROM_BASE_CAD:
        _error(f"{context}.provenance must be {REUSED_FROM_BASE_CAD}")
    return result


def _unique_components(components: list[dict[str, object]], context: str) -> None:
    logical_ids = [component["logical_component_id"] for component in components]
    handles = [str(component["source_handle"]).casefold() for component in components]
    if len(set(logical_ids)) != len(logical_ids):
        _error(f"{context} contains duplicate logical component IDs")
    if len(set(handles)) != len(handles):
        _error(f"{context} contains duplicate source handles")


def _inspection_eligibility(
    identity: list[dict[str, object]],
    dimensions: list[dict[str, object]],
    xref: dict[str, object],
    changed: bool,
    dbmod_before: int,
    dbmod_after: int,
    conflicts: list[object],
) -> bool:
    return (
        all(item["status"] == "PASS" for item in identity)
        and all(item["status"] == "PASS" for item in dimensions)
        and xref["read_only"] is True
        and changed is False
        and dbmod_before == dbmod_after
        and not conflicts
    )


def validate_xref_inspection(payload: object) -> dict[str, object]:
    """Validate and copy exact-base, read-only Xref inspection evidence."""
    _reject_forbidden_fields(payload)
    result = _closed_fields(payload, _INSPECTION_FIELDS, "inspection")
    if result["schema_version"] != INSPECTION_SCHEMA_VERSION:
        _error("inspection.schema_version is unsupported")
    _string(result["inspection_id"], "inspection.inspection_id", identifier=True)
    _string(result["request_id"], "inspection.request_id", identifier=True)
    _string(result["run_id"], "inspection.run_id", identifier=True)
    _timestamp(result["capture_timestamp"], "inspection.capture_timestamp")
    result["base_source"] = _base_source(result["base_source"])
    _hash(result["target_drawing_sha256"], "inspection.target_drawing_sha256")
    identity = _identity_observations(result["identity_observations"])
    dimensions = _critical_dimensions(result["critical_dimensions"])
    result["xref"] = _xref(result["xref"])
    components = _list(result["components"], "components")
    if not components:
        _error("components must contain at least one inspected component")
    normalized_components = [
        _component(item, f"components[{index}]") for index, item in enumerate(components)
    ]
    _unique_components(normalized_components, "components")
    result["components"] = normalized_components
    result["warnings"] = _warnings_or_conflicts(result["warnings"], "warnings")
    result["conflicts"] = _warnings_or_conflicts(result["conflicts"], "conflicts")
    changed = _boolean(result["changed"], "inspection.changed")
    if changed:
        _error("inspection.changed must be false")
    for field in ("dbmod_before", "dbmod_after"):
        value = result[field]
        if type(value) is not int or value < 0:
            _error(f"inspection.{field} must be a non-negative integer")
    eligible = _boolean(result["eligible"], "inspection.eligible")
    expected = _inspection_eligibility(
        identity,
        dimensions,
        result["xref"],
        changed,
        result["dbmod_before"],
        result["dbmod_after"],
        result["conflicts"],
    )
    if eligible != expected:
        _error("inspection.eligible does not match identity, dimension, and read-only gates")
    result["identity_observations"] = identity
    result["critical_dimensions"] = dimensions
    return deepcopy(result)


def _transform(value: object, context: str = "transform") -> dict[str, object]:
    result = _closed_fields(value, _TRANSFORM_FIELDS, context)
    result["translation"] = _point(result["translation"], f"{context}.translation")
    _number(result["rotation_degrees"], f"{context}.rotation_degrees", minimum=-360, maximum=360)
    _number(result["uniform_scale"], f"{context}.uniform_scale", minimum=0.000001, maximum=100)
    return result


def _approval(value: object) -> dict[str, object]:
    result = _closed_fields(value, _APPROVAL_FIELDS, "approval")
    status = result["status"]
    if status not in {"APPROVED", "PROPOSED"}:
        _error("approval.status must be PROPOSED or APPROVED")
    reference = result["reference"]
    if status == "PROPOSED":
        if reference is not None:
            _error("PROPOSED approval must not fabricate an approval reference")
    else:
        _string(reference, "approval.reference", identifier=True)
    return result


def _view(value: object, context: str) -> dict[str, object]:
    result = _closed_fields(value, _VIEW_FIELDS, context)
    _string(result["identity"], f"{context}.identity", identifier=True)
    _string(result["name"], f"{context}.name")
    return result


def _plan_component(value: object, context: str) -> dict[str, object]:
    result = _closed_fields(value, _PLAN_COMPONENT_FIELDS, context)
    base = _component({key: result[key] for key in _COMPONENT_FIELDS}, context)
    base["transform"] = _transform(result["transform"], f"{context}.transform")
    return base


def _validate_plan_against_inspection(
    plan: dict[str, object], inspection: dict[str, object]
) -> None:
    if inspection["eligible"] is not True:
        _error("base CAD inspection is not eligible for extraction")
    for field in ("request_id", "run_id", "inspection_id", "target_drawing_sha256"):
        if plan[field] != inspection[field]:
            _error(f"plan.{field} does not match inspection")
    if plan["base_source"] != inspection["base_source"]:
        _error("plan.base_source does not match inspection")
    inspected = {
        component["logical_component_id"]: component for component in inspection["components"]
    }
    for index, component in enumerate(plan["components"]):
        logical_id = component["logical_component_id"]
        if logical_id not in inspected:
            _error(f"plan.components[{index}] was not present in inspection")
        source = inspected[logical_id]
        for field in _COMPONENT_FIELDS:
            if component[field] != source[field]:
                _error(f"plan.components[{index}].{field} does not match inspection")


def validate_extraction_plan(
    payload: object, inspection: object | None = None
) -> dict[str, object]:
    """Validate and copy a closed, non-mutating extraction plan."""
    _reject_forbidden_fields(payload)
    result = _closed_fields(payload, _PLAN_FIELDS, "extraction plan")
    if result["schema_version"] != EXTRACTION_PLAN_SCHEMA_VERSION:
        _error("extraction plan.schema_version is unsupported")
    _string(result["plan_id"], "extraction plan.plan_id", identifier=True)
    _string(result["request_id"], "extraction plan.request_id", identifier=True)
    _string(result["run_id"], "extraction plan.run_id", identifier=True)
    _string(result["inspection_id"], "extraction plan.inspection_id", identifier=True)
    result["base_source"] = _base_source(result["base_source"], "extraction plan.base_source")
    _hash(result["target_drawing_sha256"], "extraction plan.target_drawing_sha256")
    _string(result["source_revision"], "extraction plan.source_revision", identifier=True)
    if result["source_revision"] != result["base_source"]["revision"]:
        _error("extraction plan.source_revision must match base_source.revision")
    if result["provenance"] != REUSED_FROM_BASE_CAD:
        _error(f"extraction plan.provenance must be {REUSED_FROM_BASE_CAD}")
    if result["transform_policy"] != TRANSFORM_POLICY:
        _error("extraction plan.transform_policy is unsupported")
    result["approval"] = _approval(result["approval"])
    views = _list(result["impacted_views"], "impacted_views")
    result["impacted_views"] = [
        _view(item, f"impacted_views[{index}]") for index, item in enumerate(views)
    ]
    view_ids = [view["identity"] for view in result["impacted_views"]]
    if len(set(view_ids)) != len(view_ids):
        _error("impacted_views contains duplicate identities")
    components = _list(result["components"], "extraction plan.components")
    normalized_components = [
        _plan_component(item, f"extraction plan.components[{index}]")
        for index, item in enumerate(components)
    ]
    _unique_components(normalized_components, "extraction plan.components")
    result["components"] = normalized_components
    if inspection is not None:
        validated_inspection = validate_xref_inspection(inspection)
        _validate_plan_against_inspection(result, validated_inspection)
    return deepcopy(result)


def build_extraction_plan(
    *,
    plan_id: str,
    inspection: object,
    selections: object,
    impacted_views: object | None = None,
    approval_status: str = "PROPOSED",
    approval_reference: str | None = None,
) -> dict[str, object]:
    """Build a deterministic plan from eligible inspection metadata only."""
    validated_inspection = validate_xref_inspection(inspection)
    if validated_inspection["eligible"] is not True:
        _error("base CAD inspection is not eligible for extraction")
    _string(plan_id, "plan_id", identifier=True)
    raw_selections = _list(selections, "selections")
    selected_ids: set[str] = set()
    inspected = {
        component["logical_component_id"]: component
        for component in validated_inspection["components"]
    }
    plan_components: list[dict[str, object]] = []
    for index, selection in enumerate(raw_selections):
        item = _closed_fields(
            selection,
            frozenset({"logical_component_id", "transform"}),
            f"selections[{index}]",
        )
        logical_id = _string(
            item["logical_component_id"],
            f"selections[{index}].logical_component_id",
            identifier=True,
        )
        if logical_id in selected_ids:
            _error("selections contains duplicate logical component IDs")
        if logical_id not in inspected:
            _error(f"selections[{index}] was not present in inspection")
        selected_ids.add(logical_id)
        source = deepcopy(inspected[logical_id])
        source["transform"] = _transform(item["transform"], f"selections[{index}].transform")
        plan_components.append(source)
    if impacted_views is None:
        raw_views: object = []
    else:
        raw_views = impacted_views
    plan = {
        "schema_version": EXTRACTION_PLAN_SCHEMA_VERSION,
        "plan_id": plan_id,
        "request_id": validated_inspection["request_id"],
        "run_id": validated_inspection["run_id"],
        "inspection_id": validated_inspection["inspection_id"],
        "base_source": deepcopy(validated_inspection["base_source"]),
        "target_drawing_sha256": validated_inspection["target_drawing_sha256"],
        "source_revision": validated_inspection["base_source"]["revision"],
        "provenance": REUSED_FROM_BASE_CAD,
        "transform_policy": TRANSFORM_POLICY,
        "components": plan_components,
        "impacted_views": deepcopy(raw_views),
        "approval": {"status": approval_status, "reference": approval_reference},
    }
    return validate_extraction_plan(plan, inspection=validated_inspection)


__all__ = [
    "EXTRACTION_PLAN_SCHEMA_VERSION",
    "INSPECTION_SCHEMA_VERSION",
    "REUSED_FROM_BASE_CAD",
    "TRANSFORM_POLICY",
    "ExactBaseXrefError",
    "build_extraction_plan",
    "validate_extraction_plan",
    "validate_xref_inspection",
]
