"""Create a hash-bound Drawing Setup plan and normalize read-only audit evidence."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .drawing_contracts import DrawingContractError, canonical_json_sha256
from .manifest import sha256_file


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_RELEASE_PROFILES = {"REVIEW", "AUTHORITATIVE"}
_AUDIT_PAYLOAD_FIELDS = (
    "changed",
    "dbmod_before",
    "dbmod_after",
    "variables",
    "current_layer",
    "custom_properties",
    "layers",
    "styles",
    "layouts",
    "font_report",
)


class DrawingSetupError(DrawingContractError):
    """Raised when approved Drawing Setup inputs cannot be bound safely."""


class _ImmutableDict(dict[str, Any]):
    """A JSON-serializable dict that cannot be changed after construction."""

    __slots__ = ()

    @staticmethod
    def _immutable(*_: object, **__: object) -> None:
        raise TypeError("Drawing Setup plan references are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class _ImmutableList(list[Any]):
    """A JSON-serializable list that cannot be changed after construction."""

    __slots__ = ()

    @staticmethod
    def _immutable(*_: object, **__: object) -> None:
        raise TypeError("Drawing Setup plan references are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return _ImmutableDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _ImmutableList([_freeze(item) for item in value])
    return copy.deepcopy(value)


def _fail(message: str) -> DrawingSetupError:
    return DrawingSetupError(message)


def _approved_mapping(source: Mapping[str, object], name: str) -> Mapping[str, object]:
    if not isinstance(source, Mapping):
        raise _fail(f"invalid {name} input")
    if source.get("status") != "APPROVED":
        raise _fail(f"{name} status must be APPROVED")
    return source


def _value(source: Mapping[str, object], key: str, name: str) -> object:
    try:
        return source[key]
    except (KeyError, TypeError) as exc:
        raise _fail(f"invalid {name} input: missing {key}") from exc


def _canonical_hash(source: Mapping[str, object], name: str) -> str:
    try:
        return canonical_json_sha256(source)
    except (TypeError, ValueError) as exc:
        raise _fail(f"invalid {name} input: cannot canonicalize") from exc


def _contains(values: object, value: object, name: str) -> bool:
    try:
        return value in values  # type: ignore[operator]
    except TypeError as exc:
        raise _fail(f"invalid {name} input") from exc


def _validate_template_file(template_file: Path) -> Path:
    try:
        path = Path(template_file)
    except TypeError as exc:
        raise _fail("template file is invalid") from exc
    if path.is_symlink() or not path.is_file():
        raise _fail("template file is missing or not a regular file")
    if path.suffix.lower() != ".dwt":
        raise _fail("template file must name a .dwt file")
    return path


def _template_hash(template_file: Path) -> str:
    try:
        return sha256_file(template_file)
    except OSError as exc:
        raise _fail("template file cannot be read") from exc


def create_setup_plan(
    *,
    run_id: str,
    definition: Mapping[str, object],
    profile: Mapping[str, object],
    domain_pack: Mapping[str, object],
    template_manifest: Mapping[str, object],
    template_file: Path,
) -> dict[str, object]:
    """Return a validated ``SETUP_PENDING`` plan bound to every input hash."""
    if not isinstance(run_id, str) or _ID_RE.fullmatch(run_id) is None:
        raise _fail("invalid run ID: expected a non-empty identifier without spaces")

    definition = _approved_mapping(definition, "definition")
    profile = _approved_mapping(profile, "drawing profile")
    domain_pack = _approved_mapping(domain_pack, "domain pack")
    template_manifest = _approved_mapping(template_manifest, "template manifest")

    definition_domain = _value(definition, "domain", "definition")
    definition_type = _value(definition, "drawing_type", "definition")
    release_profile = _value(definition, "release_profile", "definition")
    if not isinstance(release_profile, str) or release_profile not in _ACCEPTED_RELEASE_PROFILES:
        raise _fail("definition release profile is not accepted")
    if not _contains(_value(profile, "supported_domains", "drawing profile"), definition_domain, "drawing profile"):
        raise _fail("definition domain is not supported by the approved drawing profile")
    if not _contains(_value(profile, "supported_drawing_types", "drawing profile"), definition_type, "drawing profile"):
        raise _fail("definition drawing type is not supported by the approved drawing profile")
    if not _contains(_value(domain_pack, "domains", "domain pack"), definition_domain, "domain pack"):
        raise _fail("definition domain is not supported by the approved domain pack")
    if not _contains(_value(domain_pack, "drawing_types", "domain pack"), definition_type, "domain pack"):
        raise _fail("definition drawing type is not supported by the approved domain pack")

    profile_hash = _canonical_hash(profile, "drawing profile")
    settings = _value(profile, "setup_expectations", "drawing profile")
    if not isinstance(settings, Mapping):
        raise _fail("invalid drawing profile input: setup_expectations")
    settings_hash = _canonical_hash(settings, "drawing profile setup_expectations")
    if _value(template_manifest, "drawing_profile_sha256", "template manifest") != profile_hash:
        raise _fail("drawing profile SHA-256 does not match the approved template manifest")
    if _value(template_manifest, "embedded_settings_sha256", "template manifest") != settings_hash:
        raise _fail("embedded settings SHA-256 does not match the drawing profile")

    checked_template = _validate_template_file(template_file)
    template_hash = _template_hash(checked_template)
    if _value(template_manifest, "file_sha256", "template manifest") != template_hash:
        raise _fail("template SHA-256 does not match the approved template manifest")

    try:
        plan: dict[str, object] = {
            "schema_version": "drawing-setup-plan-1.0",
            "run_id": run_id,
            "state": "SETUP_PENDING",
            "definition": {
                "id": _value(definition, "id", "definition"),
                "sha256": _canonical_hash(definition, "definition"),
            },
            "drawing_profile": {
                "id": _value(profile, "id", "drawing profile"),
                "revision": _value(profile, "revision", "drawing profile"),
                "sha256": profile_hash,
            },
            "domain_pack": {
                "id": _value(domain_pack, "id", "domain pack"),
                "revision": _value(domain_pack, "revision", "domain pack"),
                "sha256": _canonical_hash(domain_pack, "domain pack"),
            },
            "template": {
                "id": _value(template_manifest, "id", "template manifest"),
                "revision": _value(template_manifest, "revision", "template manifest"),
                "file_sha256": template_hash,
                "embedded_settings_sha256": settings_hash,
            },
            "setup_expectations": copy.deepcopy(settings),
        }
        json.dumps(plan)
    except (TypeError, ValueError) as exc:
        raise _fail("invalid Drawing Setup plan input") from exc
    frozen = _freeze(plan)
    assert isinstance(frozen, dict)
    return frozen


def create_setup_audit(
    drawing: Path,
    drawing_sha256: str,
    ipc_result: Mapping[str, object],
) -> dict[str, object]:
    """Normalize one successful read-only IPC result into the strict audit contract."""
    drawing_path = Path(drawing).resolve()
    if not isinstance(drawing_sha256, str) or _SHA256_RE.fullmatch(drawing_sha256) is None:
        raise _fail("drawing SHA-256 must be 64 lowercase hexadecimal characters")
    if not isinstance(ipc_result, Mapping) or ipc_result.get("success") is not True:
        raise _fail("drawing setup audit requires a successful IPC result")
    if ipc_result.get("operation") != "drawing_setup_audit":
        raise _fail("IPC result operation must be drawing_setup_audit")

    result_path = ipc_result.get("drawing_full_path")
    if not isinstance(result_path, str) or Path(result_path).resolve() != drawing_path:
        raise _fail("IPC drawing_full_path does not match the audited drawing")
    if ipc_result.get("changed") is not False or ipc_result.get("entity_handles") != []:
        raise _fail("drawing setup audit IPC result must be read-only")

    payload = ipc_result.get("payload")
    if not isinstance(payload, Mapping):
        raise _fail("drawing setup audit IPC payload must be an object")
    missing = [field for field in _AUDIT_PAYLOAD_FIELDS if field not in payload]
    if missing:
        raise _fail(f"drawing setup audit IPC payload is missing {', '.join(missing)}")

    copied = {field: copy.deepcopy(payload[field]) for field in _AUDIT_PAYLOAD_FIELDS}
    if copied["changed"] is not False:
        raise _fail("drawing setup audit payload must be read-only")
    dbmod_before = copied["dbmod_before"]
    dbmod_after = copied["dbmod_after"]
    if (
        isinstance(dbmod_before, bool)
        or not isinstance(dbmod_before, int)
        or isinstance(dbmod_after, bool)
        or not isinstance(dbmod_after, int)
        or dbmod_before != dbmod_after
    ):
        raise _fail("drawing setup audit DBMOD values must be equal integers")

    audit: dict[str, object] = {
        "schema_version": "drawing-setup-audit-1.0",
        "drawing_full_path": str(drawing_path),
        "drawing_sha256": drawing_sha256,
        **copied,
    }
    try:
        json.dumps(audit, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _fail("drawing setup audit IPC payload is not strict JSON") from exc
    return audit


__all__ = ["DrawingSetupError", "create_setup_audit", "create_setup_plan"]
