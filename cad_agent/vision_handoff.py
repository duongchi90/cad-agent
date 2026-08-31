"""Closed, hash-bound vision handoff and immutable output-schema binding."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
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
SERVER_OWNED_ADAPTER_VERSION = "adapter-1.0"
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
_PROVIDER_EFFECTIVE_ATTESTATION_FIELDS = frozenset(
    {
        "thread_id",
        "instruction_sources",
        "approval_mode",
        "experimental_api",
        "model_identity",
        "config_sha256",
        "adapter_version",
        "sandbox_write_policy",
        "cwd",
        "writable_roots",
        "full_access",
        "auto_review",
        "approval_escalation",
        "transport",
        "alternate_transports",
    }
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
class ServerOwnedWorkerBindingContext:
    """Immutable server-owned local runtime and effective sandbox identity."""

    adapter_version: str
    observed_thread_id: str
    sandbox_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _freeze(getattr(self, field_name)))


@dataclass(frozen=True)
class ServerOwnedWorkerStartContext:
    """Server-owned expectations used before a provider thread exists."""

    adapter_version: str
    sandbox_policy: Mapping[str, object]
    instruction_source_paths: Sequence[Mapping[str, object]]

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _freeze(getattr(self, field_name)))


@dataclass(frozen=True)
class ProviderStartObservation:
    """Typed, provider-returned facts from one official thread/start call."""

    thread_id: str
    model: str
    model_provider: str
    cwd: str
    approval_policy: str
    approvals_reviewer: str
    sandbox: Mapping[str, object]
    instruction_sources: Sequence[Mapping[str, object]]

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


@dataclass(frozen=True)
class BoundWorkerThread:
    """Immutable local binding between one provider thread and one handoff."""

    handoff_id: str
    handoff_hash: str
    run_id: str
    thread_id: str
    adapter_version: str
    model_config_identity: Mapping[str, object]
    instruction_source_identity: Sequence[Mapping[str, object]]
    sandbox_policy: Mapping[str, object]
    output_schema_sha256: str
    output_validator_version: str
    approval_reference: str
    approval_authority: str
    handoff_expires_at: str
    policy_identity: str
    authority_context_identity: str

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _freeze(getattr(self, field_name)))


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


def _worker_policy_identity(
    authority_context: ServerOwnedAuthorityContext,
    sandbox_policy: Mapping[str, object],
) -> str:
    expected = _authority_context_payload(authority_context)
    policy_payload = {
        "scope": expected["scope"],
        "protected_constraints": expected["protected_constraints"],
        "workspace": expected["workspace"],
        "sandbox_policy": _thaw(sandbox_policy),
        "allowed_operations": expected["allowed_operations"],
        "forbidden_mutations": expected["forbidden_mutations"],
        "required_verification_gates": expected["required_verification_gates"],
        "provider_policy": expected["provider_policy"],
        "instruction_sources": expected["instruction_sources"],
    }
    return _canonical_sha256(policy_payload)


def _worker_authority_context_identity(
    authority_context: ServerOwnedAuthorityContext,
    policy_identity: str,
) -> str:
    expected = _authority_context_payload(authority_context)
    authority_payload = {
        "handoff_id": expected["handoff_id"],
        "program_id": expected["program_id"],
        "run_id": expected["run_id"],
        "request_id": expected["request_id"],
        "created_at": expected["created_at"],
        "expires_at": expected["expires_at"],
        "single_use": expected["single_use"],
        "consumed": expected["consumed"],
        "source": expected["source"],
        "accepted_base": expected["accepted_base"],
        "approval_reference": expected["approval_reference"],
        "approval_authority": expected["approval_authority"],
        "policy_identity": policy_identity,
    }
    return _canonical_sha256(authority_payload)


def validate_provider_effective_attestation(
    value: object,
    *,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
) -> None:
    """Match provider-observed effective policy to existing server-owned authority."""

    if not isinstance(value, Mapping) or set(value) != _PROVIDER_EFFECTIVE_ATTESTATION_FIELDS:
        _fail("provider effective attestation shape mismatch")
    if not isinstance(binding, BoundWorkerThread):
        _fail("provider effective attestation authority mismatch")
    if not isinstance(authority_context, ServerOwnedAuthorityContext):
        _fail("provider effective attestation authority mismatch")
    if not isinstance(worker_context, ServerOwnedWorkerBindingContext):
        _fail("provider effective attestation authority mismatch")

    instruction_sources = _validate_list_object(
        value["instruction_sources"],
        fields={"source_id", "role", "sha256"},
        path="provider_effective_attestation.instruction_sources",
    )
    for index, source in enumerate(instruction_sources):
        _identifier(
            source["source_id"],
            path=f"provider_effective_attestation.instruction_sources[{index}].source_id",
        )
        _identifier(
            source["role"],
            path=f"provider_effective_attestation.instruction_sources[{index}].role",
        )
        _sha256(
            source["sha256"],
            path=f"provider_effective_attestation.instruction_sources[{index}].sha256",
        )
    if len({source["source_id"] for source in instruction_sources}) != len(instruction_sources):
        _fail("provider effective attestation instruction source mismatch")
    if (
        _canonical_bytes(instruction_sources)
        != _canonical_bytes(binding.instruction_source_identity)
        or _canonical_bytes(instruction_sources)
        != _canonical_bytes(authority_context.instruction_sources)
    ):
        _fail("provider effective attestation instruction source mismatch")

    provider_policy = authority_context.provider_policy
    if not isinstance(provider_policy, Mapping) or set(provider_policy) != {
        "approval_mode",
        "experimental_api",
        "model_identity",
        "config_sha256",
    }:
        _fail("provider effective attestation authority mismatch")
    model_config = binding.model_config_identity
    if not isinstance(model_config, Mapping) or set(model_config) != {
        "model_identity",
        "config_sha256",
    }:
        _fail("provider effective attestation authority mismatch")
    sandbox = binding.sandbox_policy
    worker_sandbox = worker_context.sandbox_policy
    if (
        not isinstance(sandbox, Mapping)
        or set(sandbox) != {"roots", "write_policy", "cwd"}
        or not isinstance(worker_sandbox, Mapping)
        or set(worker_sandbox) != {"roots", "write_policy", "cwd"}
        or _canonical_bytes(sandbox) != _canonical_bytes(worker_sandbox)
    ):
        _fail("provider effective attestation authority mismatch")
    writable_roots = _non_empty_string_list(
        value["writable_roots"],
        path="provider_effective_attestation.writable_roots",
        minimum=1,
    )

    expected_policy_identity = _worker_policy_identity(authority_context, sandbox)
    expected_authority_identity = _worker_authority_context_identity(
        authority_context, expected_policy_identity
    )
    if (
        binding.policy_identity != expected_policy_identity
        or binding.authority_context_identity != expected_authority_identity
        or binding.adapter_version != worker_context.adapter_version
        or binding.adapter_version != SERVER_OWNED_ADAPTER_VERSION
        or binding.thread_id != worker_context.observed_thread_id
        or provider_policy["approval_mode"] != "deny_all"
        or provider_policy["experimental_api"] is not False
        or provider_policy["model_identity"] != model_config["model_identity"]
        or provider_policy["config_sha256"] != model_config["config_sha256"]
        or sandbox["write_policy"] != "DISPOSABLE_ONLY"
        or sandbox["cwd"] != sandbox["roots"][0]
    ):
        _fail("provider effective attestation authority mismatch")

    if (
        value["thread_id"] != binding.thread_id
        or value["approval_mode"] != "deny_all"
        or value["approval_mode"] != provider_policy["approval_mode"]
        or value["experimental_api"] is not False
        or value["experimental_api"] != provider_policy["experimental_api"]
        or value["model_identity"] != model_config["model_identity"]
        or value["config_sha256"] != model_config["config_sha256"]
        or value["adapter_version"] != binding.adapter_version
        or value["sandbox_write_policy"] != sandbox["write_policy"]
        or value["cwd"] != sandbox["cwd"]
        or _canonical_bytes(writable_roots) != _canonical_bytes(sandbox["roots"])
        or value["full_access"] is not False
        or value["auto_review"] is not False
        or value["approval_escalation"] is not False
        or value["transport"] != "official_sdk"
        or not isinstance(value["alternate_transports"], (list, tuple))
        or len(value["alternate_transports"]) != 0
    ):
        _fail("provider effective attestation policy mismatch")


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


def _worker_handoff_payload(
    handoff: ValidatedVisionHandoff,
    *,
    authority_context: ServerOwnedAuthorityContext,
    now: datetime | None,
) -> tuple[Mapping[str, object], datetime]:
    if not isinstance(handoff, ValidatedVisionHandoff):
        _fail("worker thread binding requires a ValidatedVisionHandoff")
    current = _normalize_now(now)
    handoff.schema_snapshot.assert_unchanged()
    payload = handoff.payload
    if not isinstance(payload, Mapping):
        _fail("worker thread binding handoff payload must be immutable mapping")
    canonical_without_hash = _thaw(payload)
    supplied_hash = canonical_without_hash.pop("handoff_sha256", None)
    if not isinstance(supplied_hash, str):
        _fail("worker thread handoff hash is missing")
    _sha256(supplied_hash, path="handoff_sha256")
    canonical_bytes = _canonical_bytes(canonical_without_hash)
    expected_hash = hashlib.sha256(canonical_bytes).hexdigest()
    if supplied_hash != expected_hash or handoff.handoff_sha256 != supplied_hash:
        _fail("worker thread handoff binding is invalid")
    if handoff.canonical_bytes != canonical_bytes:
        _fail("worker thread canonical handoff bytes do not match")

    consumed_handoff_ids = _validate_authority_context(payload, authority_context)
    validated_bytes = _validate_payload(
        payload,
        now=current,
        consumed_handoff_ids=consumed_handoff_ids,
    )
    if validated_bytes != canonical_bytes or validated_bytes != handoff.canonical_bytes:
        _fail("worker thread handoff validation changed canonical bytes")
    return payload, current


def _worker_model_config_identity(
    payload: Mapping[str, object]
) -> dict[str, object]:
    policy = _keys(
        payload["provider_policy"],
        required={"model_identity", "config_sha256"},
        optional={"approval_mode", "experimental_api"},
        path="provider_policy",
    )
    _identifier(policy["model_identity"], path="provider_policy.model_identity")
    _sha256(policy["config_sha256"], path="provider_policy.config_sha256")
    return {
        "model_identity": policy["model_identity"],
        "config_sha256": policy["config_sha256"],
    }


def _worker_instruction_source_identity(
    payload: Mapping[str, object]
) -> list[dict[str, Any]]:
    observed = _validate_list_object(
        payload["instruction_sources"],
        fields={"source_id", "role", "sha256"},
        path="worker_thread.instruction_source_identity",
    )
    for index, source in enumerate(observed):
        _identifier(source["source_id"], path=f"worker_thread.instruction_source_identity[{index}].source_id")
        _identifier(source["role"], path=f"worker_thread.instruction_source_identity[{index}].role")
        _sha256(source["sha256"], path=f"worker_thread.instruction_source_identity[{index}].sha256")
    if _canonical_bytes(observed) != _canonical_bytes(payload["instruction_sources"]):
        _fail("worker thread instruction source identity mismatch")
    return observed


def _worker_sandbox_policy(payload: Mapping[str, object], value: object) -> dict[str, Any]:
    if not isinstance(value, ServerOwnedWorkerBindingContext):
        _fail("worker thread requires a server-owned worker binding context")
    if value.adapter_version != SERVER_OWNED_ADAPTER_VERSION:
        _fail("worker thread adapter version is not server-owned")
    observed = _keys(
        value.sandbox_policy,
        required={"roots", "write_policy", "cwd"},
        path="worker_thread.sandbox_policy",
    )
    observed_roots = _non_empty_string_list(
        observed["roots"], path="worker_thread.sandbox_policy.roots", minimum=1
    )
    _string(observed["cwd"], path="worker_thread.sandbox_policy.cwd")
    if observed["write_policy"] != "DISPOSABLE_ONLY":
        _fail("worker thread sandbox write policy must be DISPOSABLE_ONLY")
    workspace = _keys(payload["workspace"], required={"roots", "write_policy"}, path="workspace")
    expected_roots = _non_empty_string_list(workspace["roots"], path="workspace.roots", minimum=1)
    expected = {
        "roots": expected_roots,
        "write_policy": workspace["write_policy"],
        "cwd": expected_roots[0],
    }
    normalized = {
        "roots": observed_roots,
        "write_policy": observed["write_policy"],
        "cwd": observed["cwd"],
    }
    if _canonical_bytes(normalized) != _canonical_bytes(expected):
        _fail("worker thread sandbox policy or controlled cwd mismatch")
    return normalized


def _server_observed_thread_id(value: object) -> str:
    if not isinstance(value, ServerOwnedWorkerBindingContext):
        _fail("worker thread requires a server-owned worker binding context")
    return _identifier(
        value.observed_thread_id,
        path="worker_thread.server_observed_thread_id",
    )


def _validate_worker_context(
    value: ServerOwnedWorkerBindingContext, *, thread_id: str
) -> None:
    observed_thread_id = _server_observed_thread_id(value)
    if observed_thread_id != thread_id:
        _fail(
            "worker_thread.thread_id does not match the server-observed provider thread identity"
        )


def _make_bound_worker_thread(
    handoff: ValidatedVisionHandoff,
    *,
    thread_id: str,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    now: datetime | None,
) -> BoundWorkerThread:
    payload, _ = _worker_handoff_payload(
        handoff,
        authority_context=authority_context,
        now=now,
    )
    _identifier(thread_id, path="worker_thread.thread_id")
    _validate_worker_context(worker_context, thread_id=thread_id)
    model_config = _worker_model_config_identity(payload)
    instruction_sources = _worker_instruction_source_identity(payload)
    sandbox = _worker_sandbox_policy(payload, worker_context)
    policy_identity = _worker_policy_identity(authority_context, sandbox)
    authority_context_identity = _worker_authority_context_identity(
        authority_context,
        policy_identity,
    )
    return BoundWorkerThread(
        handoff_id=payload["handoff_id"],
        handoff_hash=handoff.handoff_sha256,
        run_id=payload["run_id"],
        thread_id=thread_id,
        adapter_version=worker_context.adapter_version,
        model_config_identity=model_config,
        instruction_source_identity=instruction_sources,
        sandbox_policy=sandbox,
        output_schema_sha256=payload["output_schema_sha256"],
        output_validator_version=payload["output_validator_version"],
        approval_reference=payload["approval_reference"],
        approval_authority=payload["approval_authority"],
        handoff_expires_at=payload["expires_at"],
        policy_identity=policy_identity,
        authority_context_identity=authority_context_identity,
    )


def _validate_bound_worker_thread(binding: object, *, now: datetime | None) -> BoundWorkerThread:
    if not isinstance(binding, BoundWorkerThread):
        _fail("resume/fork requires a complete BoundWorkerThread")
    _identifier(binding.handoff_id, path="bound_worker_thread.handoff_id")
    _sha256(binding.handoff_hash, path="bound_worker_thread.handoff_hash")
    _identifier(binding.run_id, path="bound_worker_thread.run_id")
    _identifier(binding.thread_id, path="bound_worker_thread.thread_id")
    _identifier(binding.adapter_version, path="bound_worker_thread.adapter_version")
    _identifier(binding.output_validator_version, path="bound_worker_thread.output_validator_version")
    _sha256(binding.output_schema_sha256, path="bound_worker_thread.output_schema_sha256")
    _identifier(binding.approval_reference, path="bound_worker_thread.approval_reference")
    _sha256(binding.policy_identity, path="bound_worker_thread.policy_identity")
    _sha256(
        binding.authority_context_identity,
        path="bound_worker_thread.authority_context_identity",
    )
    if binding.approval_authority not in {"OWNER", "MASTER_PO"}:
        _fail("bound worker thread approval authority is invalid")
    if _parse_time(binding.handoff_expires_at, path="bound_worker_thread.handoff_expires_at") <= _normalize_now(now):
        _fail("bound worker thread history is stale or expired")
    return binding


def bind_worker_thread(
    handoff: ValidatedVisionHandoff,
    *,
    thread_id: str,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    now: datetime | None = None,
) -> BoundWorkerThread:
    """Bind one observed provider thread to a validated handoff only."""

    return _make_bound_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority_context,
        worker_context=worker_context,
        now=now,
    )


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _canonical_runtime_file(value: object, *, path: str) -> tuple[Path, str]:
    candidate_text = _string(value, path=path)
    candidate = Path(candidate_text)
    if not candidate.is_absolute():
        _fail(f"{path} must be an absolute path")
    if _path_contains_windows_reparse_point(candidate) or candidate.is_symlink():
        _fail(f"{path} contains a reparse point or symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise VisionHandoffError(f"{path} cannot be resolved") from exc
    if _path_contains_windows_reparse_point(resolved) or resolved.is_symlink():
        _fail(f"{path} contains a reparse point or symlink")
    if _path_key(candidate) != _path_key(resolved):
        _fail(f"{path} is not canonical")
    if not resolved.is_file():
        _fail(f"{path} must be a regular file")
    try:
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError as exc:
        raise VisionHandoffError(f"{path} cannot be read") from exc
    return resolved, digest


def _canonical_runtime_path(value: object, *, path: str) -> Path:
    candidate_text = _string(value, path=path)
    candidate = Path(candidate_text)
    if not candidate.is_absolute():
        _fail(f"{path} must be an absolute path")
    if _path_contains_windows_reparse_point(candidate) or candidate.is_symlink():
        _fail(f"{path} contains a reparse point or symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise VisionHandoffError(f"{path} cannot be resolved") from exc
    if _path_contains_windows_reparse_point(resolved) or resolved.is_symlink():
        _fail(f"{path} contains a reparse point or symlink")
    if _path_key(candidate) != _path_key(resolved):
        _fail(f"{path} is not canonical")
    return resolved


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _start_sandbox_policy(
    payload: Mapping[str, object],
    start_context: ServerOwnedWorkerStartContext,
) -> tuple[Path, Path, tuple[str, ...], dict[str, object]]:
    if not isinstance(start_context, ServerOwnedWorkerStartContext):
        _fail("worker start requires a server-owned start context")
    if start_context.adapter_version != SERVER_OWNED_ADAPTER_VERSION:
        _fail("worker start adapter version is not server-owned")
    observed = _keys(
        start_context.sandbox_policy,
        required={"roots", "write_policy", "cwd"},
        path="worker_start.sandbox_policy",
    )
    observed_roots = _non_empty_string_list(
        observed["roots"], path="worker_start.sandbox_policy.roots", minimum=1
    )
    if len(observed_roots) != 1 or observed["write_policy"] != "DISPOSABLE_ONLY":
        _fail("worker start sandbox policy must be DISPOSABLE_ONLY with one root")
    if observed["cwd"] != observed_roots[0]:
        _fail("worker start cwd must equal the disposable root")
    workspace = _keys(payload["workspace"], required={"roots", "write_policy"}, path="workspace")
    expected_roots = _non_empty_string_list(workspace["roots"], path="workspace.roots", minimum=1)
    if (
        workspace["write_policy"] != "DISPOSABLE_ONLY"
        or _canonical_bytes(observed_roots) != _canonical_bytes(expected_roots)
        or observed["cwd"] != expected_roots[0]
    ):
        _fail("worker start sandbox policy or cwd mismatch")
    root = _canonical_runtime_path(observed_roots[0], path="worker_start.sandbox_policy.roots[0]")
    cwd = _canonical_runtime_path(observed["cwd"], path="worker_start.sandbox_policy.cwd")
    if root != cwd:
        _fail("worker start cwd must equal the disposable root")
    return root, cwd, (str(root),), {
        "roots": [str(root)],
        "write_policy": "DISPOSABLE_ONLY",
        "cwd": str(cwd),
    }


def validate_worker_start_context(
    handoff: ValidatedVisionHandoff,
    *,
    authority_context: ServerOwnedAuthorityContext,
    start_context: ServerOwnedWorkerStartContext,
    now: datetime | None = None,
) -> tuple[Path, Path, tuple[str, ...]]:
    """Validate server custody before any provider thread/start call."""

    payload, _ = _worker_handoff_payload(
        handoff,
        authority_context=authority_context,
        now=now,
    )
    root, cwd, roots, _ = _start_sandbox_policy(payload, start_context)
    return root, cwd, roots


def _expected_start_instruction_sources(
    authority_context: ServerOwnedAuthorityContext,
    start_context: ServerOwnedWorkerStartContext,
) -> tuple[dict[str, object], ...]:
    authority_sources = _validate_list_object(
        authority_context.instruction_sources,
        fields={"source_id", "role", "sha256"},
        path="authority_context.instruction_sources",
    )
    expected_paths = _validate_list_object(
        start_context.instruction_source_paths,
        fields={"source_id", "path"},
        path="worker_start.instruction_source_paths",
    )
    authority_ids = [source["source_id"] for source in authority_sources]
    if len(set(authority_ids)) != len(authority_ids):
        _fail("authority instruction source identity is ambiguous")
    expected_hashes = [source["sha256"] for source in authority_sources]
    if len(set(expected_hashes)) != len(expected_hashes):
        _fail("authority instruction source hash identity is ambiguous")
    if len(expected_paths) != len(authority_sources):
        _fail("worker start instruction source mapping is incomplete")
    path_by_id: dict[str, tuple[Path, str]] = {}
    for index, entry in enumerate(expected_paths):
        source_id = _identifier(
            entry["source_id"],
            path=f"worker_start.instruction_source_paths[{index}].source_id",
        )
        if source_id in path_by_id:
            _fail("worker start instruction source mapping is ambiguous")
        resolved, digest = _canonical_runtime_file(
            entry["path"], path=f"worker_start.instruction_source_paths[{index}].path"
        )
        path_by_id[source_id] = (resolved, digest)
    if set(path_by_id) != set(authority_ids):
        _fail("worker start instruction source mapping does not match authority")
    result: list[dict[str, object]] = []
    for source in authority_sources:
        source_id = source["source_id"]
        resolved, digest = path_by_id[source_id]
        if digest != source["sha256"]:
            _fail("worker start instruction source hash drift")
        result.append({"source_id": source_id, "path": resolved, "sha256": digest})
    return tuple(result)


def _provider_start_observation(value: object) -> ProviderStartObservation:
    fields = {
        "thread_id",
        "model",
        "model_provider",
        "cwd",
        "approval_policy",
        "approvals_reviewer",
        "sandbox",
        "instruction_sources",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("provider start observation shape mismatch")
    for key in (
        "thread_id",
        "model",
        "model_provider",
        "cwd",
        "approval_policy",
        "approvals_reviewer",
    ):
        _string(value[key], path=f"provider_start_observation.{key}")
    sandbox = _keys(
        value["sandbox"],
        required={"type", "network_access", "writable_roots"},
        path="provider_start_observation.sandbox",
    )
    _string(sandbox["type"], path="provider_start_observation.sandbox.type")
    _bool(sandbox["network_access"], path="provider_start_observation.sandbox.network_access")
    writable_roots = sandbox["writable_roots"]
    if not isinstance(writable_roots, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in writable_roots
    ):
        _fail("provider_start_observation.sandbox.writable_roots is invalid")
    sources = _validate_list_object(
        value["instruction_sources"],
        fields={"path", "sha256"},
        path="provider_start_observation.instruction_sources",
    )
    for index, source in enumerate(sources):
        _string(source["path"], path=f"provider_start_observation.instruction_sources[{index}].path")
        _sha256(source["sha256"], path=f"provider_start_observation.instruction_sources[{index}].sha256")
    return ProviderStartObservation(
        thread_id=_identifier(value["thread_id"], path="provider_start_observation.thread_id"),
        model=value["model"],
        model_provider=value["model_provider"],
        cwd=value["cwd"],
        approval_policy=value["approval_policy"],
        approvals_reviewer=value["approvals_reviewer"],
        sandbox={
            "type": sandbox["type"],
            "network_access": sandbox["network_access"],
            "writable_roots": tuple(writable_roots),
        },
        instruction_sources=tuple(
            {"path": source["path"], "sha256": source["sha256"]} for source in sources
        ),
    )


def _validate_provider_start_observation(
    observation: ProviderStartObservation,
    *,
    payload: Mapping[str, object],
    authority_context: ServerOwnedAuthorityContext,
    start_context: ServerOwnedWorkerStartContext,
    expected_paths: tuple[dict[str, object], ...],
) -> None:
    policy = _keys(
        authority_context.provider_policy,
        required={"approval_mode", "experimental_api", "model_identity", "config_sha256"},
        path="authority_context.provider_policy",
    )
    if (
        observation.approval_policy != "never"
        or observation.approvals_reviewer != "user"
        or observation.model != policy["model_identity"]
        or observation.model_provider != "openai"
        or observation.cwd != start_context.sandbox_policy["cwd"]
    ):
        _fail("provider start observation policy mismatch")
    sandbox = observation.sandbox
    if sandbox["network_access"] is not False:
        _fail("provider start observation network policy widened")
    server_root = _canonical_runtime_path(
        start_context.sandbox_policy["roots"][0],
        path="worker_start.sandbox_policy.roots[0]",
    )
    sandbox_type = sandbox["type"]
    if sandbox_type == "readOnly":
        if tuple(sandbox["writable_roots"]) != ():
            _fail("provider readOnly sandbox cannot expose writable roots")
    elif sandbox_type == "workspaceWrite":
        writable = tuple(
            _canonical_runtime_path(item, path="provider_start_observation.sandbox.writable_roots")
            for item in sandbox["writable_roots"]
        )
        if not writable or any(not _path_within(item, server_root) for item in writable):
            _fail("provider start observation sandbox widened beyond disposable root")
    else:
        _fail("provider start observation sandbox type is not allowed")

    observed_sources = tuple(observation.instruction_sources)
    if len(observed_sources) != len(expected_paths):
        _fail("provider start instruction source set mismatch")
    observed_paths: set[str] = set()
    observed_hashes: set[str] = set()
    expected_by_path = {_path_key(item["path"]): item for item in expected_paths}
    for index, source in enumerate(observed_sources):
        resolved, digest = _canonical_runtime_file(
            source["path"], path=f"provider_start_observation.instruction_sources[{index}].path"
        )
        path_key = _path_key(resolved)
        if path_key in observed_paths or source["sha256"] in observed_hashes:
            _fail("provider start instruction source observation is ambiguous")
        expected = expected_by_path.get(path_key)
        if expected is None or expected["sha256"] != source["sha256"] or digest != source["sha256"]:
            _fail("provider start instruction source observation mismatch")
        observed_paths.add(path_key)
        observed_hashes.add(source["sha256"])
    if observed_paths != set(expected_by_path):
        _fail("provider start instruction source observation is incomplete")


def bind_provider_started_worker_thread(
    handoff: ValidatedVisionHandoff,
    *,
    provider_observation: object,
    authority_context: ServerOwnedAuthorityContext,
    start_context: ServerOwnedWorkerStartContext,
    now: datetime | None = None,
) -> tuple[ProviderStartObservation, BoundWorkerThread, ServerOwnedWorkerBindingContext]:
    """Create the immutable worker binding only after official provider start."""

    payload, _ = _worker_handoff_payload(
        handoff,
        authority_context=authority_context,
        now=now,
    )
    _start_sandbox_policy(payload, start_context)
    expected_paths = _expected_start_instruction_sources(authority_context, start_context)
    observation = _provider_start_observation(provider_observation)
    _validate_provider_start_observation(
        observation,
        payload=payload,
        authority_context=authority_context,
        start_context=start_context,
        expected_paths=expected_paths,
    )
    worker_context = ServerOwnedWorkerBindingContext(
        adapter_version=start_context.adapter_version,
        observed_thread_id=observation.thread_id,
        sandbox_policy={
            "roots": [str(_canonical_runtime_path(start_context.sandbox_policy["roots"][0], path="worker_start.sandbox_policy.roots[0]"))],
            "write_policy": "DISPOSABLE_ONLY",
            "cwd": str(_canonical_runtime_path(start_context.sandbox_policy["cwd"], path="worker_start.sandbox_policy.cwd")),
        },
    )
    binding = _make_bound_worker_thread(
        handoff,
        thread_id=observation.thread_id,
        authority_context=authority_context,
        worker_context=worker_context,
        now=now,
    )
    return observation, binding, worker_context


def validate_provider_start_observation(
    provider_observation: object,
    *,
    handoff: ValidatedVisionHandoff,
    binding: BoundWorkerThread,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    start_context: ServerOwnedWorkerStartContext,
    now: datetime | None = None,
) -> ProviderStartObservation:
    """Revalidate the same typed provider facts on later operations."""

    if not isinstance(binding, BoundWorkerThread):
        _fail("provider start observation binding mismatch")
    if not isinstance(worker_context, ServerOwnedWorkerBindingContext):
        _fail("provider start observation worker context mismatch")
    payload, _ = _worker_handoff_payload(
        handoff,
        authority_context=authority_context,
        now=now,
    )
    _start_sandbox_policy(payload, start_context)
    expected_paths = _expected_start_instruction_sources(authority_context, start_context)
    observation = _provider_start_observation(provider_observation)
    _validate_provider_start_observation(
        observation,
        payload=payload,
        authority_context=authority_context,
        start_context=start_context,
        expected_paths=expected_paths,
    )
    if (
        observation.thread_id != binding.thread_id
        or worker_context.observed_thread_id != binding.thread_id
        or binding.adapter_version != start_context.adapter_version
    ):
        _fail("provider start observation thread binding mismatch")
    return observation


def resume_worker_thread(
    binding: BoundWorkerThread,
    handoff: ValidatedVisionHandoff,
    *,
    thread_id: str,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    now: datetime | None = None,
) -> BoundWorkerThread:
    """Revalidate a complete prior binding without accepting a bare thread ID."""

    _validate_bound_worker_thread(binding, now=now)
    candidate = _make_bound_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority_context,
        worker_context=worker_context,
        now=now,
    )
    if candidate != binding:
        _fail("worker thread resume binding mismatch")
    return binding


def fork_worker_thread(
    source_binding: BoundWorkerThread,
    handoff: ValidatedVisionHandoff,
    *,
    source_handoff: ValidatedVisionHandoff,
    source_authority_context: ServerOwnedAuthorityContext,
    source_worker_context: ServerOwnedWorkerBindingContext,
    authority_context: ServerOwnedAuthorityContext,
    worker_context: ServerOwnedWorkerBindingContext,
    thread_id: str,
    now: datetime | None = None,
) -> BoundWorkerThread:
    """Bind a fork only to a fresh handoff and fresh approval identity."""

    source = _validate_bound_worker_thread(source_binding, now=now)
    source_candidate = _make_bound_worker_thread(
        source_handoff,
        thread_id=_server_observed_thread_id(source_worker_context),
        authority_context=source_authority_context,
        worker_context=source_worker_context,
        now=now,
    )
    if source_candidate != source:
        _fail("worker thread fork source binding is not server-proven")
    target = _make_bound_worker_thread(
        handoff,
        thread_id=thread_id,
        authority_context=authority_context,
        worker_context=worker_context,
        now=now,
    )
    if target.thread_id == source.thread_id:
        _fail("worker thread fork requires a fresh provider thread ID")
    if target.handoff_id == source.handoff_id or target.handoff_hash == source.handoff_hash:
        _fail("worker thread fork requires a fresh handoff")
    if target.approval_reference == source.approval_reference:
        _fail("worker thread fork requires a fresh approval")
    if target.policy_identity != source.policy_identity:
        _fail("worker thread fork policy identity cannot widen")
    return target


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
    "BoundWorkerThread",
    "DEFAULT_VALIDATOR_VERSION",
    "HANDOFF_SCHEMA_VERSION",
    "ProviderStartObservation",
    "ServerOwnedAuthorityContext",
    "ServerOwnedWorkerBindingContext",
    "ServerOwnedWorkerStartContext",
    "SERVER_OWNED_ADAPTER_VERSION",
    "SchemaSnapshot",
    "ValidatedVisionHandoff",
    "VisionHandoffError",
    "bind_worker_thread",
    "bind_vision_handoff",
    "fork_worker_thread",
    "resume_worker_thread",
    "validate_output_schema_binding",
    "validate_provider_effective_attestation",
    "validate_provider_start_observation",
    "validate_worker_start_context",
    "validate_vision_handoff",
]
