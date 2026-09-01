"""Deterministic Mechanical capability metadata and compile-only plans."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from cad_agent import cad_read_facade as _cad_read_facade
from cad_agent.drawing_contracts import canonical_json_sha256


MECHANICAL_SKILL_SCHEMA_VERSION = "mechanical-skill-1.0"
MECHANICAL_SKILL_CATALOG_SCHEMA_VERSION = "mechanical-skill-catalog-1.0"
SKILL_INVOCATION_PLAN_SCHEMA_VERSION = "skill-invocation-plan-1.0"
MAX_SEARCH_INTENT_LENGTH = 256
MAX_SEARCH_RESULTS = 25


class MechanicalSkillError(ValueError):
    """Categorical refusal at the deterministic Mechanical skill boundary."""


_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "skill_id",
        "skill_version",
        "category",
        "title",
        "description",
        "intent_tags",
        "required_context",
        "parameter_schema_id",
        "output_kind",
        "owner_route_id",
        "capability_refs",
        "evidence_requirements",
        "protected_constraint_policy",
        "max_operations",
        "compatibility_version",
        "support_state",
        "blocked_by",
        "catalog_record_sha256",
    }
)
_CATALOG_FIELDS = frozenset({"schema_version", "skills", "catalog_sha256"})
_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "skill_id",
        "skill_version",
        "catalog_sha256",
        "catalog_record_sha256",
        "support_state",
        "output_kind",
        "owner_route_id",
        "capability_refs",
        "drawing_binding",
        "operation_plan",
        "max_operations",
        "plan_sha256",
    }
)
_OPERATION_PLAN_FIELDS = frozenset({"operation", "parameters"})
_OBSERVATION_BINDING_FIELDS = frozenset(
    {
        "run_id",
        "project_id",
        "drawing_id",
        "drawing_reference_id",
        "drawing_reference_sha256",
        "artifact_sha256",
        "candidate_revision_id",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "current_observation_id",
        "current_observation_sha256",
    }
)
_SHA_FIELDS = frozenset(
    {
        "drawing_reference_sha256",
        "artifact_sha256",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "current_observation_sha256",
    }
)
_VALID_SUPPORT_STATES = frozenset({"READ_ONLY", "DEFERRED_UNSUPPORTED"})
_VALID_OUTPUT_KINDS = frozenset({"READ_REQUEST_PLAN"})
_VALID_POLICIES = frozenset({"READ_ONLY", "PRESERVE", "DOWNSTREAM_OWNER_REQUIRED"})
_TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)


def _fail(code: str) -> None:
    raise MechanicalSkillError(code)


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_string(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _require_string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or not value or any(type(item) is not str or not item for item in value):
        _fail(code)
    if len(set(value)) != len(value):
        _fail(code)
    return list(value)


def _record_hash_payload(record: Mapping[str, object]) -> dict[str, object]:
    return {
        key: deepcopy(value)
        for key, value in record.items()
        if key != "catalog_record_sha256"
    }


def _catalog_hash_payload(catalog: Mapping[str, object]) -> dict[str, object]:
    return {
        key: deepcopy(value) for key, value in catalog.items() if key != "catalog_sha256"
    }


def _plan_hash_payload(plan: Mapping[str, object]) -> dict[str, object]:
    return {key: deepcopy(value) for key, value in plan.items() if key != "plan_sha256"}


def _sealed_record(raw: Mapping[str, object]) -> dict[str, object]:
    record = deepcopy(dict(raw))
    record["catalog_record_sha256"] = canonical_json_sha256(record)
    return record


def _build_catalog() -> dict[str, object]:
    records = [
        _sealed_record(
            {
                "schema_version": MECHANICAL_SKILL_SCHEMA_VERSION,
                "skill_id": "inspect.mechanical_bom",
                "skill_version": "1.0",
                "category": "inspection",
                "title": "Inspect Mechanical BOM",
                "description": "Read the existing bounded Mechanical BOM capability.",
                "intent_tags": ["mechanical", "bom", "inspect", "read"],
                "required_context": ["DRAWING_CURRENT"],
                "parameter_schema_id": "NO_PARAMETERS",
                "output_kind": "READ_REQUEST_PLAN",
                "owner_route_id": "DOTNET_IPC_MECHANICAL_BOM_READ",
                "capability_refs": ["mechanical_bom"],
                "evidence_requirements": ["DRAWING_IDENTITY", "TERMINAL_RESULT"],
                "protected_constraint_policy": "READ_ONLY",
                "max_operations": 1,
                "compatibility_version": "cad-agent-main-1",
                "support_state": "READ_ONLY",
                "blocked_by": None,
            }
        ),
        _sealed_record(
            {
                "schema_version": MECHANICAL_SKILL_SCHEMA_VERSION,
                "skill_id": "geometry.hole_feature",
                "skill_version": "1.0",
                "category": "geometry",
                "title": "Hole Feature",
                "description": "Deferred until a reviewed Mechanical geometry owner exists.",
                "intent_tags": ["geometry", "hole", "feature"],
                "required_context": ["DRAWING_CURRENT", "CURRENT_CANDIDATE"],
                "parameter_schema_id": "DEFERRED",
                "output_kind": "READ_REQUEST_PLAN",
                "owner_route_id": "DEFERRED_UNSUPPORTED",
                "capability_refs": ["mechanical_hole_feature"],
                "evidence_requirements": ["DOWNSTREAM_OWNER_REQUIRED"],
                "protected_constraint_policy": "DOWNSTREAM_OWNER_REQUIRED",
                "max_operations": 0,
                "compatibility_version": "cad-agent-main-1",
                "support_state": "DEFERRED_UNSUPPORTED",
                "blocked_by": "MECH3_GEOMETRY_OWNER",
            }
        ),
        _sealed_record(
            {
                "schema_version": MECHANICAL_SKILL_SCHEMA_VERSION,
                "skill_id": "geometry.keyway",
                "skill_version": "1.0",
                "category": "geometry",
                "title": "Keyway",
                "description": "Deferred until a reviewed Mechanical geometry owner exists.",
                "intent_tags": ["geometry", "keyway", "shaft"],
                "required_context": ["DRAWING_CURRENT", "CURRENT_CANDIDATE"],
                "parameter_schema_id": "DEFERRED",
                "output_kind": "READ_REQUEST_PLAN",
                "owner_route_id": "DEFERRED_UNSUPPORTED",
                "capability_refs": ["mechanical_keyway"],
                "evidence_requirements": ["DOWNSTREAM_OWNER_REQUIRED"],
                "protected_constraint_policy": "DOWNSTREAM_OWNER_REQUIRED",
                "max_operations": 0,
                "compatibility_version": "cad-agent-main-1",
                "support_state": "DEFERRED_UNSUPPORTED",
                "blocked_by": "MECH3_GEOMETRY_OWNER",
            }
        ),
        _sealed_record(
            {
                "schema_version": MECHANICAL_SKILL_SCHEMA_VERSION,
                "skill_id": "geometry.shaft_step",
                "skill_version": "1.0",
                "category": "geometry",
                "title": "Stepped Shaft",
                "description": "Deferred until a reviewed Mechanical geometry owner exists.",
                "intent_tags": ["geometry", "shaft", "step"],
                "required_context": ["DRAWING_CURRENT", "CURRENT_CANDIDATE"],
                "parameter_schema_id": "DEFERRED",
                "output_kind": "READ_REQUEST_PLAN",
                "owner_route_id": "DEFERRED_UNSUPPORTED",
                "capability_refs": ["mechanical_shaft_step"],
                "evidence_requirements": ["DOWNSTREAM_OWNER_REQUIRED"],
                "protected_constraint_policy": "DOWNSTREAM_OWNER_REQUIRED",
                "max_operations": 0,
                "compatibility_version": "cad-agent-main-1",
                "support_state": "DEFERRED_UNSUPPORTED",
                "blocked_by": "MECH3_GEOMETRY_OWNER",
            }
        ),
    ]
    records.sort(key=lambda item: (item["skill_id"], item["skill_version"]))
    catalog: dict[str, object] = {
        "schema_version": MECHANICAL_SKILL_CATALOG_SCHEMA_VERSION,
        "skills": records,
    }
    catalog["catalog_sha256"] = canonical_json_sha256(catalog)
    return catalog


def _validate_record(record: object) -> dict[str, object]:
    if not isinstance(record, Mapping) or set(record) != _RECORD_FIELDS:
        _fail("RECORD_SCHEMA_INVALID")
    normalized = deepcopy(dict(record))
    if normalized["schema_version"] != MECHANICAL_SKILL_SCHEMA_VERSION:
        _fail("RECORD_SCHEMA_INVALID")
    for field in (
        "skill_id",
        "skill_version",
        "category",
        "title",
        "description",
        "parameter_schema_id",
        "output_kind",
        "owner_route_id",
        "compatibility_version",
        "support_state",
    ):
        _require_string(normalized[field], "RECORD_FIELD_INVALID")
    normalized["intent_tags"] = _require_string_list(normalized["intent_tags"], "RECORD_FIELD_INVALID")
    normalized["required_context"] = _require_string_list(
        normalized["required_context"], "RECORD_FIELD_INVALID"
    )
    normalized["capability_refs"] = _require_string_list(
        normalized["capability_refs"], "RECORD_FIELD_INVALID"
    )
    normalized["evidence_requirements"] = _require_string_list(
        normalized["evidence_requirements"], "RECORD_FIELD_INVALID"
    )
    if normalized["output_kind"] not in _VALID_OUTPUT_KINDS:
        _fail("RECORD_FIELD_INVALID")
    if normalized["support_state"] not in _VALID_SUPPORT_STATES:
        _fail("RECORD_FIELD_INVALID")
    if normalized["protected_constraint_policy"] not in _VALID_POLICIES:
        _fail("RECORD_FIELD_INVALID")
    if type(normalized["max_operations"]) is not int or normalized["max_operations"] < 0:
        _fail("RECORD_FIELD_INVALID")
    if normalized["blocked_by"] is not None:
        _require_string(normalized["blocked_by"], "RECORD_FIELD_INVALID")
    if not _is_sha256(normalized["catalog_record_sha256"]):
        _fail("RECORD_HASH_MISMATCH")
    try:
        expected = canonical_json_sha256(_record_hash_payload(normalized))
    except (TypeError, ValueError) as error:
        raise MechanicalSkillError("RECORD_HASH_MISMATCH") from error
    if normalized["catalog_record_sha256"] != expected:
        _fail("RECORD_HASH_MISMATCH")
    return normalized


def validate_mechanical_skill_catalog(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate a closed, hashed catalog and return a defensive copy."""

    if not isinstance(payload, Mapping) or set(payload) != _CATALOG_FIELDS:
        _fail("CATALOG_SCHEMA_INVALID")
    if payload.get("schema_version") != MECHANICAL_SKILL_CATALOG_SCHEMA_VERSION:
        _fail("CATALOG_SCHEMA_INVALID")
    skills = payload.get("skills")
    if not isinstance(skills, list) or not skills:
        _fail("CATALOG_SCHEMA_INVALID")
    normalized_skills = [_validate_record(record) for record in skills]
    identities = [(record["skill_id"], record["skill_version"]) for record in normalized_skills]
    if len(set(identities)) != len(identities):
        _fail("CATALOG_DUPLICATE_SKILL")
    if identities != sorted(identities):
        _fail("CATALOG_ORDER_INVALID")
    catalog_sha256 = payload.get("catalog_sha256")
    if not _is_sha256(catalog_sha256):
        _fail("CATALOG_HASH_MISMATCH")
    normalized = {
        "schema_version": payload["schema_version"],
        "skills": normalized_skills,
        "catalog_sha256": catalog_sha256,
    }
    try:
        expected = canonical_json_sha256(_catalog_hash_payload(normalized))
    except (TypeError, ValueError) as error:
        raise MechanicalSkillError("CATALOG_HASH_MISMATCH") from error
    if catalog_sha256 != expected:
        _fail("CATALOG_HASH_MISMATCH")
    return normalized


_CATALOG = _build_catalog()


def get_mechanical_skill_catalog() -> dict[str, object]:
    """Return the current immutable-by-convention catalog as a defensive copy."""

    return deepcopy(_CATALOG)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_PATTERN.findall(value.casefold()))


def _normalize_intent(intent: object) -> tuple[str, ...]:
    if type(intent) is not str or not intent or len(intent) > MAX_SEARCH_INTENT_LENGTH:
        _fail("INTENT_INVALID")
    tokens = _tokens(intent)
    if not tokens:
        _fail("INTENT_INVALID")
    return tokens


def search_skills(
    intent: str,
    *,
    category: str | None = None,
    limit: int = 10,
    include_deferred: bool = False,
) -> list[dict[str, object]]:
    """Search safe catalog metadata using deterministic lexical ranking."""

    intent_tokens = _normalize_intent(intent)
    if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
        _fail("LIMIT_INVALID")
    if category is not None and (type(category) is not str or not category):
        _fail("CATEGORY_INVALID")
    if type(include_deferred) is not bool:
        _fail("INCLUDE_DEFERRED_INVALID")
    catalog = validate_mechanical_skill_catalog(_CATALOG)
    normalized_intent = " ".join(intent_tokens)
    candidates: list[tuple[tuple[object, ...], dict[str, object]]] = []
    for record in catalog["skills"]:
        if category is not None and record["category"] != category:
            continue
        if (
            record["support_state"] == "DEFERRED_UNSUPPORTED"
            and not include_deferred
        ):
            continue
        tag_tokens = {token.casefold() for tag in record["intent_tags"] for token in _tokens(tag)}
        metadata_tokens = set(_tokens(record["category"])) | set(_tokens(record["title"]))
        tag_hits = len(set(intent_tokens) & tag_tokens)
        metadata_hits = len(set(intent_tokens) & metadata_tokens)
        exact_id = int(normalized_intent == record["skill_id"].casefold())
        if not (exact_id or tag_hits or metadata_hits):
            continue
        score = (
            -exact_id,
            -tag_hits,
            -metadata_hits,
            record["skill_id"],
            record["skill_version"],
        )
        candidates.append((score, record))
    candidates.sort(key=lambda item: item[0])
    return [deepcopy(record) for _, record in candidates[:limit]]


def _validate_plan_binding(binding: object) -> dict[str, object]:
    if not isinstance(binding, Mapping) or set(binding) != _OBSERVATION_BINDING_FIELDS:
        _fail("PLAN_BINDING_INVALID")
    normalized = deepcopy(dict(binding))
    for field, value in normalized.items():
        if type(value) is not str or not value:
            _fail("PLAN_BINDING_INVALID")
        if field in _SHA_FIELDS and not _is_sha256(value):
            _fail("PLAN_BINDING_INVALID")
    return normalized


def _record_for_plan(catalog: Mapping[str, object], skill_id: object, version: object) -> dict[str, object]:
    if type(skill_id) is not str or type(version) is not str:
        _fail("PLAN_SKILL_INVALID")
    for record in catalog["skills"]:
        if record["skill_id"] == skill_id and record["skill_version"] == version:
            return record
    _fail("PLAN_SKILL_INVALID")


def validate_skill_invocation_plan(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate a closed plan against the current in-code catalog."""

    if not isinstance(payload, Mapping) or set(payload) != _PLAN_FIELDS:
        _fail("PLAN_SCHEMA_INVALID")
    plan_sha256 = payload.get("plan_sha256")
    if not _is_sha256(plan_sha256):
        _fail("PLAN_HASH_MISMATCH")
    try:
        expected_plan_sha256 = canonical_json_sha256(_plan_hash_payload(payload))
    except (TypeError, ValueError) as error:
        raise MechanicalSkillError("PLAN_HASH_MISMATCH") from error
    if plan_sha256 != expected_plan_sha256:
        _fail("PLAN_HASH_MISMATCH")
    if payload.get("schema_version") != SKILL_INVOCATION_PLAN_SCHEMA_VERSION:
        _fail("PLAN_SCHEMA_INVALID")
    catalog = validate_mechanical_skill_catalog(_CATALOG)
    if payload.get("catalog_sha256") != catalog["catalog_sha256"]:
        _fail("PLAN_CATALOG_MISMATCH")
    record = _record_for_plan(catalog, payload.get("skill_id"), payload.get("skill_version"))
    if payload.get("catalog_record_sha256") != record["catalog_record_sha256"]:
        _fail("PLAN_CATALOG_MISMATCH")
    if payload.get("support_state") != record["support_state"]:
        _fail("PLAN_SKILL_INVALID")
    if payload.get("output_kind") != record["output_kind"]:
        _fail("PLAN_SKILL_INVALID")
    if payload.get("owner_route_id") != record["owner_route_id"]:
        _fail("PLAN_ROUTE_INVALID")
    if payload.get("capability_refs") != record["capability_refs"]:
        _fail("PLAN_ROUTE_INVALID")
    if type(payload.get("max_operations")) is not int or payload["max_operations"] != record["max_operations"]:
        _fail("PLAN_OPERATION_INVALID")
    _validate_plan_binding(payload.get("drawing_binding"))
    operation_plan = payload.get("operation_plan")
    if not isinstance(operation_plan, Mapping) or set(operation_plan) != _OPERATION_PLAN_FIELDS:
        _fail("PLAN_OPERATION_INVALID")
    if operation_plan.get("operation") != "mechanical_bom":
        _fail("PLAN_OPERATION_INVALID")
    if operation_plan.get("parameters") != {}:
        _fail("PLAN_OPERATION_INVALID")
    if record["support_state"] != "READ_ONLY":
        _fail("SKILL_NOT_INVOCABLE")
    return deepcopy(dict(payload))


def invoke_skill(
    skill_id: str,
    *,
    parameters: Mapping[str, object],
    drawing_observation: Mapping[str, object],
) -> dict[str, object]:
    """Compile exactly one existing read-only capability plan."""

    if type(skill_id) is not str or not skill_id:
        _fail("SKILL_NOT_FOUND")
    if not isinstance(parameters, Mapping) or dict(parameters) != {}:
        _fail("PARAMETERS_INVALID")
    catalog = validate_mechanical_skill_catalog(_CATALOG)
    record = next(
        (item for item in catalog["skills"] if item["skill_id"] == skill_id),
        None,
    )
    if record is None:
        _fail("SKILL_NOT_FOUND")
    if record["support_state"] != "READ_ONLY":
        _fail("SKILL_NOT_INVOCABLE")
    try:
        observation = _cad_read_facade.validate_observe_drawing_result(drawing_observation)
    except Exception as error:
        raise MechanicalSkillError("DRAWING_OBSERVATION_INVALID") from error
    binding = _validate_plan_binding(
        {key: value for key, value in observation["binding"].items() if key != "drawing_path"}
    )
    operation_plan = {"operation": "mechanical_bom", "parameters": {}}
    plan: dict[str, object] = {
        "schema_version": SKILL_INVOCATION_PLAN_SCHEMA_VERSION,
        "skill_id": record["skill_id"],
        "skill_version": record["skill_version"],
        "catalog_sha256": catalog["catalog_sha256"],
        "catalog_record_sha256": record["catalog_record_sha256"],
        "support_state": record["support_state"],
        "output_kind": record["output_kind"],
        "owner_route_id": record["owner_route_id"],
        "capability_refs": deepcopy(record["capability_refs"]),
        "drawing_binding": binding,
        "operation_plan": operation_plan,
        "max_operations": record["max_operations"],
    }
    plan["plan_sha256"] = canonical_json_sha256(plan)
    return validate_skill_invocation_plan(plan)


__all__ = [
    "MAX_SEARCH_INTENT_LENGTH",
    "MAX_SEARCH_RESULTS",
    "MECHANICAL_SKILL_CATALOG_SCHEMA_VERSION",
    "MECHANICAL_SKILL_SCHEMA_VERSION",
    "MechanicalSkillError",
    "SKILL_INVOCATION_PLAN_SCHEMA_VERSION",
    "get_mechanical_skill_catalog",
    "invoke_skill",
    "search_skills",
    "validate_mechanical_skill_catalog",
    "validate_skill_invocation_plan",
]
