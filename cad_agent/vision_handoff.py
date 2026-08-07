"""Closed, hash-bound vision handoff and immutable output-schema binding."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .visual_evidence import _path_contains_windows_reparse_point


HANDOFF_SCHEMA_VERSION = "vision-handoff-1.0"
DEFAULT_VALIDATOR_VERSION = "vision-handoff-validator-1.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "cad_truth",
        "cad_truth_authority",
        "codex_approval",
        "engineering_approval",
        "autocad_mutation",
        "file_ipc_mutation",
        "repair_application",
        "apply_repair",
        "scope_expansion",
        "publication",
        "publish",
        "verdict",
    }
)
_REQUIRED_TOP_LEVEL = frozenset(
    {
        "schema_version",
        "handoff_id",
        "program_id",
        "run_id",
        "request_id",
        "created_at",
        "expires_at",
        "single_use",
        "consumed",
        "source",
        "accepted_base",
        "scope",
        "owner_intent",
        "engineering_objective",
        "dimensions",
        "protected_constraints",
        "allowed_operations",
        "forbidden_mutations",
        "workspace",
        "required_verification_gates",
        "approval_reference",
        "approval_authority",
        "instruction_sources",
        "provider_policy",
        "output_schema_id",
        "output_schema_version",
        "output_schema_sha256",
        "output_validator_version",
        "handoff_sha256",
    }
)
_OPTIONAL_TOP_LEVEL = frozenset({"ir", "drawing", "evidence", "revision"})
_SCOPE_FIELDS = frozenset({"components", "views", "regions", "sheets", "entities"})
_DIMENSION_FIELDS = frozenset({"confirmed", "reference", "derived", "conflicting", "unresolved"})
_PROTECTED_FIELDS = frozenset(
    {"datums", "geometry", "dimensions", "constraints", "layers", "blocks", "handles"}
)


class VisionHandoffError(ValueError):
    """Raised when a vision handoff or schema snapshot cannot be trusted."""


def _fail(message: str) -> None:
    raise VisionHandoffError(message)


def _assert_finite_json(value: object, *, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        _fail(f"{path} must contain only finite numbers")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(f"{path} contains a non-string key")
            _assert_finite_json(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite_json(item, path=f"{path}[{index}]")


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    _assert_finite_json(value)
    try:
        return json.dumps(
            _canonical_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VisionHandoffError("value is not canonical JSON") from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _keys(value: object, *, required: set[str], optional: set[str] | None = None, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{path} must be an object")
    actual = set(value)
    allowed = required | (optional or set())
    missing = sorted(required - actual)
    unexpected = sorted(actual - allowed)
    if missing:
        _fail(f"{path} missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(f"{path} has Unexpected properties: {', '.join(unexpected)}")
    return dict(value)


def _string(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{path} must be a non-empty string")
    return value


def _identifier(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(f"{path} has an invalid identifier")
    return text


def _sha256(value: object, *, path: str) -> str:
    text = _string(value, path=path)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{path} must be a lowercase SHA-256")
    return text


def _bool(value: object, *, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{path} must be boolean")
    return value


def _string_list(value: object, *, path: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        _fail(f"{path} must be a list with at least {minimum} items")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_identifier(item, path=f"{path}[{index}]"))
    if len(set(result)) != len(result):
        _fail(f"{path} must not contain duplicate identities")
    return result


def _non_empty_string_list(value: object, *, path: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        _fail(f"{path} must be a list with at least {minimum} items")
    result = []
    for index, item in enumerate(value):
        result.append(_string(item, path=f"{path}[{index}]"))
    if len(set(result)) != len(result):
        _fail(f"{path} must not contain duplicate identities")
    return result


def _reject_forbidden_fields(value: object, *, path: str = "handoff") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _FORBIDDEN_AUTHORITY_FIELDS:
                _fail(f"{path}.{key} is a forbidden authority field")
            _reject_forbidden_fields(nested, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden_fields(nested, path=f"{path}[{index}]")


def _parse_time(value: object, *, path: str) -> datetime:
    text = _string(value, path=path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VisionHandoffError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        _fail(f"{path} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_file_identity(value: object, *, path: str) -> dict[str, Any]:
    item = _keys(
        value,
        required={"role", "identity", "sha256", "byte_length", "revision", "immutable"},
        optional={"path"},
        path=path,
    )
    _identifier(item["role"], path=f"{path}.role")
    _identifier(item["identity"], path=f"{path}.identity")
    _sha256(item["sha256"], path=f"{path}.sha256")
    if isinstance(item["byte_length"], bool) or not isinstance(item["byte_length"], int) or item["byte_length"] < 0:
        _fail(f"{path}.byte_length must be a non-negative integer")
    _identifier(item["revision"], path=f"{path}.revision")
    _bool(item["immutable"], path=f"{path}.immutable")
    if item["immutable"] is not True:
        _fail(f"{path}.immutable must be true")
    if "path" in item:
        _string(item["path"], path=f"{path}.path")
    return item


def _validate_identity_section(payload: Mapping[str, Any], *, key: str) -> None:
    _validate_file_identity(payload[key], path=key)


def _validate_list_object(value: object, *, fields: set[str], path: str) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not value:
        _fail(f"{path} must be a non-empty list")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        entry = _keys(item, required=fields, path=f"{path}[{index}]")
        result.append(entry)
    return result


def _validate_payload(payload: Mapping[str, Any], *, now: datetime, consumed_handoff_ids: frozenset[str]) -> bytes:
    _assert_finite_json(payload)
    _reject_forbidden_fields(payload)
    root = _keys(payload, required=set(_REQUIRED_TOP_LEVEL), optional=set(_OPTIONAL_TOP_LEVEL), path="handoff")
    if root["schema_version"] != HANDOFF_SCHEMA_VERSION:
        _fail(f"schema_version must be {HANDOFF_SCHEMA_VERSION!r}")
    for key in ("handoff_id", "program_id", "run_id", "request_id"):
        _identifier(root[key], path=key)
    if root["handoff_id"] in consumed_handoff_ids:
        _fail("handoff is reused")
    created_at = _parse_time(root["created_at"], path="created_at")
    expires_at = _parse_time(root["expires_at"], path="expires_at")
    if expires_at <= created_at:
        _fail("expires_at must be after created_at")
    if expires_at <= now:
        _fail("handoff is expired")
    if created_at > now:
        _fail("created_at is in the future")
    if _bool(root["single_use"], path="single_use") is not True:
        _fail("single_use must be true")
    if _bool(root["consumed"], path="consumed") is True:
        _fail("handoff is consumed")

    _validate_identity_section(root, key="source")
    _validate_identity_section(root, key="accepted_base")
    for optional in _OPTIONAL_TOP_LEVEL:
        if optional in root:
            _validate_identity_section(root, key=optional)

    scope = _keys(root["scope"], required=set(_SCOPE_FIELDS), path="scope")
    for key in _SCOPE_FIELDS:
        _string_list(scope[key], path=f"scope.{key}", minimum=1)
    _string(root["owner_intent"], path="owner_intent")
    _string(root["engineering_objective"], path="engineering_objective")

    dimensions = _keys(root["dimensions"], required=set(_DIMENSION_FIELDS), path="dimensions")
    for key in _DIMENSION_FIELDS:
        _string_list(dimensions[key], path=f"dimensions.{key}")
    protected = _keys(root["protected_constraints"], required=set(_PROTECTED_FIELDS), path="protected_constraints")
    for key in _PROTECTED_FIELDS:
        _string_list(protected[key], path=f"protected_constraints.{key}")

    _string_list(root["allowed_operations"], path="allowed_operations", minimum=1)
    _string_list(root["forbidden_mutations"], path="forbidden_mutations", minimum=1)
    workspace = _keys(root["workspace"], required={"roots", "write_policy"}, path="workspace")
    _non_empty_string_list(workspace["roots"], path="workspace.roots", minimum=1)
    if workspace["write_policy"] != "DISPOSABLE_ONLY":
        _fail("workspace.write_policy must be DISPOSABLE_ONLY")
    _string_list(root["required_verification_gates"], path="required_verification_gates", minimum=1)
    _identifier(root["approval_reference"], path="approval_reference")
    if root["approval_authority"] not in {"OWNER", "MASTER_PO"}:
        _fail("approval_authority must identify an owner-controlled authority")

    instruction_sources = _validate_list_object(
        root["instruction_sources"], fields={"source_id", "role", "sha256"}, path="instruction_sources"
    )
    for index, source in enumerate(instruction_sources):
        _identifier(source["source_id"], path=f"instruction_sources[{index}].source_id")
        _identifier(source["role"], path=f"instruction_sources[{index}].role")
        _sha256(source["sha256"], path=f"instruction_sources[{index}].sha256")
    if len({source["source_id"] for source in instruction_sources}) != len(instruction_sources):
        _fail("instruction_sources must not contain duplicate identities")

    policy = _keys(
        root["provider_policy"],
        required={"approval_mode", "experimental_api", "model_identity", "config_sha256"},
        path="provider_policy",
    )
    if policy["approval_mode"] != "deny_all":
        _fail("provider_policy.approval_mode must be deny_all")
    if _bool(policy["experimental_api"], path="provider_policy.experimental_api") is not False:
        _fail("provider_policy.experimental_api must be false")
    _identifier(policy["model_identity"], path="provider_policy.model_identity")
    _sha256(policy["config_sha256"], path="provider_policy.config_sha256")

    _identifier(root["output_schema_id"], path="output_schema_id")
    _identifier(root["output_schema_version"], path="output_schema_version")
    _sha256(root["output_schema_sha256"], path="output_schema_sha256")
    _identifier(root["output_validator_version"], path="output_validator_version")
    canonical_without_hash = _thaw(root)
    canonical_without_hash.pop("handoff_sha256")
    canonical_bytes = _canonical_bytes(canonical_without_hash)
    expected_hash = hashlib.sha256(canonical_bytes).hexdigest()
    if root["handoff_sha256"] != expected_hash:
        _fail("handoff_sha256 does not match canonical handoff bytes")
    return canonical_bytes


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    try:
        stat_result = path.stat()
    except OSError as exc:
        raise VisionHandoffError(f"cannot stat schema path: {path}") from exc
    return (stat_result.st_dev, stat_result.st_ino, stat_result.st_size, stat_result.st_mtime_ns)


def _read_schema(path: Path) -> tuple[bytes, object, bytes, tuple[int, int, int, int]]:
    candidate = Path(path)
    if _path_contains_windows_reparse_point(candidate) or candidate.is_symlink():
        _fail(f"schema path contains a reparse point or symlink: {candidate}")
    if not candidate.is_file():
        _fail(f"schema path is not a regular file: {candidate}")
    try:
        raw = candidate.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisionHandoffError(f"cannot read output schema: {candidate}") from exc
    if not isinstance(document, Mapping):
        _fail("output schema must be a JSON object")
    canonical = _canonical_bytes(document)
    return raw, document, canonical, _file_identity(candidate)


@dataclass(frozen=True)
class SchemaSnapshot:
    """Immutable bytes and filesystem identity captured for one run."""

    path: Path
    schema_id: str
    schema_version: str
    validator_version: str
    raw_bytes: bytes
    canonical_bytes: bytes
    sha256: str
    file_identity: tuple[int, int, int, int]

    def assert_unchanged(self) -> None:
        raw, _, canonical, identity = _read_schema(self.path)
        if identity != self.file_identity or raw != self.raw_bytes or canonical != self.canonical_bytes:
            _fail("output schema snapshot changed or was replaced (TOCTOU)")


def _snapshot_schema(path: Path, *, schema_id: str, schema_version: str, validator_version: str) -> SchemaSnapshot:
    raw, _, canonical, identity = _read_schema(path)
    return SchemaSnapshot(
        path=Path(path),
        schema_id=_identifier(schema_id, path="schema_id"),
        schema_version=_identifier(schema_version, path="schema_version"),
        validator_version=_identifier(validator_version, path="validator_version"),
        raw_bytes=raw,
        canonical_bytes=canonical,
        sha256=hashlib.sha256(canonical).hexdigest(),
        file_identity=identity,
    )


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


@dataclass(frozen=True)
class ServerOwnedAuthorityContext:
    """Complete immutable server-owned expectations for one handoff run."""

    handoff_id: str
    program_id: str
    run_id: str
    request_id: str
    created_at: str
    expires_at: str
    single_use: bool
    consumed: bool
    source: Mapping[str, object]
    accepted_base: Mapping[str, object]
    scope: Mapping[str, object]
    protected_constraints: Mapping[str, object]
    instruction_sources: Sequence[Mapping[str, object]]
    approval_reference: str
    approval_authority: str
    workspace: Mapping[str, object]
    allowed_operations: Sequence[str]
    forbidden_mutations: Sequence[str]
    required_verification_gates: Sequence[str]
    provider_policy: Mapping[str, object]
    consumed_handoff_ids: Sequence[str]

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _freeze(getattr(self, field_name)))


@dataclass(frozen=True)
class ValidatedVisionHandoff:
    """Fail-closed, immutable handoff and its run-scoped schema snapshot."""

    payload: Mapping[str, object]
    canonical_bytes: bytes
    handoff_sha256: str
    schema_snapshot: SchemaSnapshot

    def validate_output_schema_binding(
        self,
        *,
        schema_path: Path,
        schema_bytes: bytes,
        schema_id: str,
        schema_version: str,
        validator_version: str,
    ) -> None:
        validate_output_schema_binding(
            self,
            schema_path=schema_path,
            schema_bytes=schema_bytes,
            schema_id=schema_id,
            schema_version=schema_version,
            validator_version=validator_version,
        )


def _authority_context_payload(context: ServerOwnedAuthorityContext) -> dict[str, object]:
    return {
        "handoff_id": context.handoff_id,
        "program_id": context.program_id,
        "run_id": context.run_id,
        "request_id": context.request_id,
        "created_at": context.created_at,
        "expires_at": context.expires_at,
        "single_use": context.single_use,
        "consumed": context.consumed,
        "source": _thaw(context.source),
        "accepted_base": _thaw(context.accepted_base),
        "scope": _thaw(context.scope),
        "protected_constraints": _thaw(context.protected_constraints),
        "instruction_sources": _thaw(context.instruction_sources),
        "approval_reference": context.approval_reference,
        "approval_authority": context.approval_authority,
        "workspace": _thaw(context.workspace),
        "allowed_operations": _thaw(context.allowed_operations),
        "forbidden_mutations": _thaw(context.forbidden_mutations),
        "required_verification_gates": _thaw(context.required_verification_gates),
        "provider_policy": _thaw(context.provider_policy),
        "consumed_handoff_ids": _thaw(context.consumed_handoff_ids),
    }


def _validate_authority_context(
    payload: Mapping[str, Any], authority_context: object
) -> frozenset[str]:
    if not isinstance(authority_context, ServerOwnedAuthorityContext):
        _fail("authority context must be a complete ServerOwnedAuthorityContext")
    expected = _authority_context_payload(authority_context)
    for field in ("handoff_id", "program_id", "run_id", "request_id"):
        _identifier(expected[field], path=f"authority_context.{field}")
    created_at = _parse_time(expected["created_at"], path="authority_context.created_at")
    expires_at = _parse_time(expected["expires_at"], path="authority_context.expires_at")
    if expires_at <= created_at:
        _fail("authority_context.expires_at must be after created_at")
    if _bool(expected["single_use"], path="authority_context.single_use") is not True:
        _fail("authority_context.single_use must be true")
    if _bool(expected["consumed"], path="authority_context.consumed") is not False:
        _fail("authority_context.consumed must be false")
    consumed_handoff_ids = _string_list(
        expected["consumed_handoff_ids"],
        path="authority_context.consumed_handoff_ids",
    )
    for index, handoff_id in enumerate(consumed_handoff_ids):
        _identifier(handoff_id, path=f"authority_context.consumed_handoff_ids[{index}]")
    if len(consumed_handoff_ids) != len(set(consumed_handoff_ids)):
        _fail("authority_context.consumed_handoff_ids must not contain duplicates")
    _validate_file_identity(expected["source"], path="authority_context.source")
    _validate_file_identity(expected["accepted_base"], path="authority_context.accepted_base")
    scope = _keys(expected["scope"], required=set(_SCOPE_FIELDS), path="authority_context.scope")
    for field in _SCOPE_FIELDS:
        _string_list(scope[field], path=f"authority_context.scope.{field}", minimum=1)
    protected = _keys(
        expected["protected_constraints"],
        required=set(_PROTECTED_FIELDS),
        path="authority_context.protected_constraints",
    )
    for field in _PROTECTED_FIELDS:
        _string_list(protected[field], path=f"authority_context.protected_constraints.{field}")
    instruction_sources = _validate_list_object(
        expected["instruction_sources"],
        fields={"source_id", "role", "sha256"},
        path="authority_context.instruction_sources",
    )
    for index, source in enumerate(instruction_sources):
        _identifier(source["source_id"], path=f"authority_context.instruction_sources[{index}].source_id")
        _identifier(source["role"], path=f"authority_context.instruction_sources[{index}].role")
        _sha256(source["sha256"], path=f"authority_context.instruction_sources[{index}].sha256")
    _identifier(expected["approval_reference"], path="authority_context.approval_reference")
    if expected["approval_authority"] not in {"OWNER", "MASTER_PO"}:
        _fail("authority_context.approval_authority is not owner-controlled")
    workspace = _keys(expected["workspace"], required={"roots", "write_policy"}, path="authority_context.workspace")
    _non_empty_string_list(workspace["roots"], path="authority_context.workspace.roots", minimum=1)
    if workspace["write_policy"] != "DISPOSABLE_ONLY":
        _fail("authority_context.workspace.write_policy must be DISPOSABLE_ONLY")
    for field in ("allowed_operations", "forbidden_mutations", "required_verification_gates"):
        _string_list(expected[field], path=f"authority_context.{field}", minimum=1)
    policy = _keys(
        expected["provider_policy"],
        required={"approval_mode", "experimental_api", "model_identity", "config_sha256"},
        path="authority_context.provider_policy",
    )
    if policy["approval_mode"] != "deny_all":
        _fail("authority_context.provider_policy.approval_mode must be deny_all")
    if _bool(policy["experimental_api"], path="authority_context.provider_policy.experimental_api") is not False:
        _fail("authority_context.provider_policy.experimental_api must be false")
    _identifier(policy["model_identity"], path="authority_context.provider_policy.model_identity")
    _sha256(policy["config_sha256"], path="authority_context.provider_policy.config_sha256")

    for field in (
        "handoff_id",
        "program_id",
        "run_id",
        "request_id",
        "created_at",
        "expires_at",
        "single_use",
        "consumed",
        "source",
        "accepted_base",
        "scope",
        "protected_constraints",
        "instruction_sources",
        "approval_reference",
        "approval_authority",
        "workspace",
        "allowed_operations",
        "forbidden_mutations",
        "required_verification_gates",
        "provider_policy",
    ):
        if field not in payload:
            _fail(f"payload missing required authority field: {field}")

    identity = {field: payload[field] for field in ("handoff_id", "program_id", "run_id", "request_id")}
    expected_identity = {field: expected[field] for field in identity}
    groups = (
        ("identity", identity, expected_identity),
        (
            "lifecycle",
            {
                "created_at": payload["created_at"],
                "expires_at": payload["expires_at"],
                "single_use": payload["single_use"],
                "consumed": payload["consumed"],
            },
            {
                "created_at": expected["created_at"],
                "expires_at": expected["expires_at"],
                "single_use": expected["single_use"],
                "consumed": expected["consumed"],
            },
        ),
        ("source", payload["source"], expected["source"]),
        ("accepted_base", payload["accepted_base"], expected["accepted_base"]),
        ("scope", payload["scope"], expected["scope"]),
        ("protected_constraints", payload["protected_constraints"], expected["protected_constraints"]),
        ("instruction_sources", payload["instruction_sources"], expected["instruction_sources"]),
        (
            "approval",
            {"reference": payload["approval_reference"], "authority": payload["approval_authority"]},
            {"reference": expected["approval_reference"], "authority": expected["approval_authority"]},
        ),
        ("workspace", payload["workspace"], expected["workspace"]),
        ("allowed_operations", payload["allowed_operations"], expected["allowed_operations"]),
        ("forbidden_mutations", payload["forbidden_mutations"], expected["forbidden_mutations"]),
        (
            "required_verification_gates",
            payload["required_verification_gates"],
            expected["required_verification_gates"],
        ),
        ("provider", payload["provider_policy"], expected["provider_policy"]),
    )
    for group, actual, expected_value in groups:
        if _canonical_bytes(actual) != _canonical_bytes(expected_value):
            _fail(f"{group} authority context mismatch")
    return frozenset(consumed_handoff_ids)


def _normalize_now(now: datetime | None) -> datetime:
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        _fail("now must be timezone-aware")
    return current.astimezone(timezone.utc)


def bind_vision_handoff(
    payload: Mapping[str, object],
    *,
    schema_path: Path,
    schema_id: str,
    schema_version: str,
    validator_version: str = DEFAULT_VALIDATOR_VERSION,
    authority_context: ServerOwnedAuthorityContext,
    now: datetime | None = None,
) -> ValidatedVisionHandoff:
    """Bind server-owned schema/hash fields and validate one closed handoff."""

    if not isinstance(payload, Mapping):
        _fail("handoff must be an object")
    bound = copy.deepcopy(dict(payload))
    snapshot = _snapshot_schema(
        Path(schema_path), schema_id=schema_id, schema_version=schema_version, validator_version=validator_version
    )
    for key, expected in (
        ("output_schema_id", snapshot.schema_id),
        ("output_schema_version", snapshot.schema_version),
        ("output_schema_sha256", snapshot.sha256),
        ("output_validator_version", snapshot.validator_version),
    ):
        if key in bound and bound[key] != expected:
            _fail(f"server-owned {key} binding mismatch")
        bound[key] = expected
    supplied_handoff_hash = bound.pop("handoff_sha256", None)
    if supplied_handoff_hash is not None:
        _sha256(supplied_handoff_hash, path="handoff_sha256")
    canonical_without_hash = _canonical_bytes(bound)
    computed_handoff_hash = hashlib.sha256(canonical_without_hash).hexdigest()
    if supplied_handoff_hash is not None and supplied_handoff_hash != computed_handoff_hash:
        _fail("server-owned handoff_sha256 binding mismatch")
    bound["handoff_sha256"] = computed_handoff_hash
    current = _normalize_now(now)
    consumed_handoff_ids = _validate_authority_context(bound, authority_context)
    canonical_bytes = _validate_payload(
        bound,
        now=current,
        consumed_handoff_ids=consumed_handoff_ids,
    )
    return ValidatedVisionHandoff(
        payload=_freeze(bound),
        canonical_bytes=canonical_bytes,
        handoff_sha256=bound["handoff_sha256"],
        schema_snapshot=snapshot,
    )


def validate_vision_handoff(
    payload: Mapping[str, object],
    *,
    schema_path: Path,
    schema_id: str,
    schema_version: str,
    validator_version: str = DEFAULT_VALIDATOR_VERSION,
    authority_context: ServerOwnedAuthorityContext,
    now: datetime | None = None,
) -> ValidatedVisionHandoff:
    """Validate an already server-bound handoff without rebinding its identity."""

    current = _normalize_now(now)
    if not isinstance(payload, Mapping):
        _fail("handoff must be an object")
    consumed_handoff_ids = _validate_authority_context(payload, authority_context)
    snapshot = _snapshot_schema(
        Path(schema_path), schema_id=schema_id, schema_version=schema_version, validator_version=validator_version
    )
    canonical_bytes = _validate_payload(
        payload,
        now=current,
        consumed_handoff_ids=consumed_handoff_ids,
    )
    if payload["output_schema_id"] != snapshot.schema_id:
        _fail("output schema ID does not match the server-owned snapshot")
    if payload["output_schema_version"] != snapshot.schema_version:
        _fail("output schema version does not match the server-owned snapshot")
    if payload["output_schema_sha256"] != snapshot.sha256:
        _fail("output schema SHA-256 does not match the server-owned snapshot")
    if payload["output_validator_version"] != snapshot.validator_version:
        _fail("output validator version does not match the server-owned snapshot")
    return ValidatedVisionHandoff(
        payload=_freeze(_thaw(payload)),
        canonical_bytes=canonical_bytes,
        handoff_sha256=payload["handoff_sha256"],
        schema_snapshot=snapshot,
    )


def validate_output_schema_binding(
    handoff: ValidatedVisionHandoff,
    *,
    schema_path: Path,
    schema_bytes: bytes,
    schema_id: str,
    schema_version: str,
    validator_version: str,
) -> None:
    """Validate provider/local schema identity against one immutable snapshot."""

    if not isinstance(handoff, ValidatedVisionHandoff):
        _fail("handoff must be a ValidatedVisionHandoff")
    if Path(schema_path) != handoff.schema_snapshot.path:
        _fail("schema path does not match the immutable snapshot")
    handoff.schema_snapshot.assert_unchanged()
    if not isinstance(schema_bytes, bytes):
        _fail("provider schema bytes must be bytes")
    if schema_bytes != handoff.schema_snapshot.raw_bytes:
        _fail("provider schema bytes differ from the immutable snapshot")
    if _canonical_sha256(json.loads(schema_bytes.decode("utf-8"))) != handoff.schema_snapshot.sha256:
        _fail("provider schema canonical hash differs from the immutable snapshot")
    if schema_id != handoff.schema_snapshot.schema_id:
        _fail("provider schema ID differs from the immutable snapshot")
    if schema_version != handoff.schema_snapshot.schema_version:
        _fail("provider schema version differs from the immutable snapshot")
    if validator_version != handoff.schema_snapshot.validator_version:
        _fail("provider validator version differs from the immutable snapshot")
    if handoff.payload["output_schema_sha256"] != handoff.schema_snapshot.sha256:
        _fail("handoff schema hash is not bound to the immutable snapshot")


__all__ = [
    "DEFAULT_VALIDATOR_VERSION",
    "HANDOFF_SCHEMA_VERSION",
    "ServerOwnedAuthorityContext",
    "SchemaSnapshot",
    "ValidatedVisionHandoff",
    "VisionHandoffError",
    "bind_vision_handoff",
    "validate_output_schema_binding",
    "validate_vision_handoff",
]
