"""Create an approved, hash-bound Drawing Setup plan.

M2-T3 deliberately stops at a validated ``SETUP_PENDING`` artifact.  It does
not open AutoCAD, change a drawing, or infer defaults for any configuration.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import drawing_contracts as _contracts
from .drawing_contracts import (
    DrawingContractError,
    canonical_json_sha256,
    read_contract,
)
from .manifest import sha256_file

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ContractInput = Mapping[str, object] | str | os.PathLike[str]


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


def _contract_from_mapping(source: Mapping[str, object], contract: str) -> dict[str, object]:
    payload = copy.deepcopy(dict(source))
    validator = getattr(_contracts, "_VALIDATORS", {}).get(contract.replace("-", "_"))
    if validator is None:
        raise _fail(f"unsupported contract kind: {contract}")
    try:
        validator(payload)
    except (DrawingContractError, KeyError, TypeError) as exc:
        raise _fail(f"invalid {contract} input: {exc}") from exc
    return payload


def _read_contract_input(source: ContractInput | None, contract: str) -> dict[str, object]:
    if source is None:
        raise _fail(f"missing {contract} input")
    if isinstance(source, Mapping):
        return _contract_from_mapping(source, contract)
    try:
        return read_contract(Path(source), contract=contract)
    except (DrawingContractError, OSError, TypeError, ValueError) as exc:
        raise _fail(f"invalid {contract} input: {exc}") from exc


def _take_alias(
    primary: object | None,
    alias: object | None,
    name: str,
) -> object | None:
    if primary is not None and alias is not None:
        raise _fail(f"inconsistent input contract: both {name}_path and {name} were supplied")
    return primary if primary is not None else alias


def _looks_like_run_id(value: object) -> bool:
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None and "." not in value


def _resolve_positional(
    args: tuple[object, ...],
    *,
    run_id: str | None,
    definition_path: ContractInput | None,
    profile_path: ContractInput | None,
    domain_pack_path: ContractInput | None,
    template_manifest_path: ContractInput | None,
    template_path: str | os.PathLike[str] | None,
) -> tuple[str | None, ContractInput | None, ContractInput | None, ContractInput | None, ContractInput | None, str | os.PathLike[str] | None]:
    if not args:
        return run_id, definition_path, profile_path, domain_pack_path, template_manifest_path, template_path
    if any(value is not None for value in (run_id, definition_path, profile_path, domain_pack_path, template_manifest_path, template_path)):
        raise _fail("inconsistent input contract: do not mix positional and keyword inputs")
    if len(args) != 6:
        raise _fail("create_setup_plan requires six positional inputs or named inputs")
    if _looks_like_run_id(args[0]):
        run_value, definition_value, profile_value, domain_value, manifest_value, template_value = args
    else:
        definition_value, profile_value, domain_value, manifest_value, template_value, run_value = args
    if not isinstance(run_value, str):
        raise _fail("invalid run ID: run_id must be a string")
    return (
        run_value,
        definition_value,  # type: ignore[return-value]
        profile_value,  # type: ignore[return-value]
        domain_value,  # type: ignore[return-value]
        manifest_value,  # type: ignore[return-value]
        template_value,  # type: ignore[return-value]
    )


def _validate_template_path(source: str | os.PathLike[str] | None) -> Path:
    if source is None:
        raise _fail("template path is missing")
    try:
        path = Path(source)
    except TypeError as exc:
        raise _fail("template path is invalid") from exc
    if path.is_symlink() or not path.is_file():
        raise _fail("template path is missing or not a regular file")
    if path.suffix.lower() != ".dwt":
        raise _fail("template path must name a .dwt file")
    return path


def _validate_generated_plan(plan: dict[str, object]) -> None:
    validator = getattr(_contracts, "_VALIDATORS", {}).get("drawing_setup_plan")
    if validator is None:
        raise _fail("generated drawing setup plan validator is unavailable")
    try:
        validator(plan)
    except (DrawingContractError, KeyError, TypeError) as exc:
        raise _fail(f"generated drawing setup plan is invalid: {exc}") from exc


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        raise _fail(f"cannot write setup plan artifact: {path}") from exc


def create_setup_plan(
    *args: object,
    run_id: str | None = None,
    definition_path: ContractInput | None = None,
    profile_path: ContractInput | None = None,
    domain_pack_path: ContractInput | None = None,
    template_manifest_path: ContractInput | None = None,
    template_path: str | os.PathLike[str] | None = None,
    definition: ContractInput | None = None,
    profile: ContractInput | None = None,
    domain_pack: ContractInput | None = None,
    template_manifest: ContractInput | None = None,
    output_path: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Bind approved Drawing Setup inputs into an immutable pending plan.

    Named inputs are preferred.  For compatibility with small callers, six
    positional inputs are accepted in either ``run_id, definition, profile,
    domain_pack, manifest, template`` or the reverse order.
    """
    (
        run_id,
        definition_path,
        profile_path,
        domain_pack_path,
        template_manifest_path,
        template_path,
    ) = _resolve_positional(
        args,
        run_id=run_id,
        definition_path=definition_path,
        profile_path=profile_path,
        domain_pack_path=domain_pack_path,
        template_manifest_path=template_manifest_path,
        template_path=template_path,
    )
    definition_path = _take_alias(definition_path, definition, "definition")  # type: ignore[assignment]
    profile_path = _take_alias(profile_path, profile, "profile")  # type: ignore[assignment]
    domain_pack_path = _take_alias(domain_pack_path, domain_pack, "domain_pack")  # type: ignore[assignment]
    template_manifest_path = _take_alias(template_manifest_path, template_manifest, "template_manifest")  # type: ignore[assignment]

    if not isinstance(run_id, str) or _ID_RE.fullmatch(run_id) is None:
        raise _fail("invalid run ID: expected a non-empty identifier without spaces")

    definition_payload = _read_contract_input(definition_path, "drawing_definition")
    profile_payload = _read_contract_input(profile_path, "drawing_profile")
    domain_payload = _read_contract_input(domain_pack_path, "domain_pack")
    manifest_payload = _read_contract_input(template_manifest_path, "template_manifest")
    template_file = _validate_template_path(template_path)

    definition_domain = definition_payload["domain"]
    definition_type = definition_payload["drawing_type"]
    if definition_domain not in profile_payload["supported_domains"]:
        raise _fail("definition domain is not supported by the approved drawing profile")
    if definition_type not in profile_payload["supported_drawing_types"]:
        raise _fail("definition drawing type is not supported by the approved drawing profile")
    if definition_domain not in domain_payload["domains"]:
        raise _fail("definition domain is not supported by the approved domain pack")
    if definition_type not in domain_payload["drawing_types"]:
        raise _fail("definition drawing type is not supported by the approved domain pack")

    profile_hash = canonical_json_sha256(profile_payload)
    if manifest_payload["drawing_profile_sha256"] != profile_hash:
        raise _fail("drawing profile SHA-256 does not match the approved template manifest")
    settings_hash = canonical_json_sha256(profile_payload["setup_expectations"])
    if manifest_payload["embedded_settings_sha256"] != settings_hash:
        raise _fail("embedded settings SHA-256 does not match the drawing profile")

    template_hash = sha256_file(template_file)
    if manifest_payload["file_sha256"] != template_hash:
        raise _fail("template SHA-256 does not match the approved template manifest")

    plan: dict[str, object] = {
        "schema_version": "drawing-setup-plan-1.0",
        "run_id": run_id,
        "state": "SETUP_PENDING",
        "definition": {
            "id": definition_payload["id"],
            "sha256": canonical_json_sha256(definition_payload),
        },
        "drawing_profile": {
            "id": profile_payload["id"],
            "revision": profile_payload["revision"],
            "sha256": profile_hash,
        },
        "domain_pack": {
            "id": domain_payload["id"],
            "revision": domain_payload["revision"],
            "sha256": canonical_json_sha256(domain_payload),
        },
        "template": {
            "id": manifest_payload["id"],
            "revision": manifest_payload["revision"],
            "file_sha256": template_hash,
            "embedded_settings_sha256": settings_hash,
        },
        "setup_expectations": copy.deepcopy(profile_payload["setup_expectations"]),
    }
    _validate_generated_plan(plan)
    frozen = _freeze(plan)
    assert isinstance(frozen, dict)
    if output_path is not None:
        _write_json(Path(output_path), frozen)
    return frozen


__all__ = ["DrawingSetupError", "create_setup_plan"]
