"""Create an approved, hash-bound Drawing Setup plan."""

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
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_RELEASE_PROFILES = {"REVIEW", "AUTHORITATIVE"}
SETUP_BLOCKERS = frozenset(
    {
        "source_changed",
        "setup_incomplete",
        "profile_missing",
        "profile_hash_mismatch",
        "template_hash_mismatch",
        "font_substitution_risk",
        "viewport_scale_mismatch",
        "drawing_target_mismatch",
    }
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


def _add_setup_blocker(
    blockers: list[dict[str, object]],
    code: str,
    path: str,
    expected: object,
    actual: object,
) -> None:
    if code not in SETUP_BLOCKERS:
        raise AssertionError(f"unknown Drawing Setup blocker code: {code}")
    blockers.append(
        {
            "code": code,
            "path": path,
            "expected": copy.deepcopy(expected),
            "actual": copy.deepcopy(actual),
            "severity": "BLOCKER",
        }
    )


def _named_entries(value: object, name_key: str) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, list):
        return {}
    result: dict[str, Mapping[str, object]] = {}
    for item in value:
        if isinstance(item, Mapping) and isinstance(item.get(name_key), str):
            result[item[name_key]] = item
    return result


def evaluate_setup_plan(
    plan: Mapping[str, object],
    audit: Mapping[str, object],
    *,
    verified_by: str,
    approval_reference: str,
) -> dict[str, object]:
    """Compare a read-only audit with an approved plan and emit evidence."""
    if not isinstance(plan, Mapping) or not isinstance(audit, Mapping):
        raise DrawingSetupError("Drawing Setup plan and audit must be objects")
    if not isinstance(verified_by, str) or not verified_by.strip():
        raise DrawingSetupError("verified_by must be a non-empty string")
    if not isinstance(approval_reference, str) or not approval_reference.strip():
        raise DrawingSetupError("approval_reference must be a non-empty string")

    blockers: list[dict[str, object]] = []
    expectations = plan.get("setup_expectations")
    template = plan.get("template")
    if not isinstance(expectations, Mapping):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations", "object", expectations)
        expectations = {}
    if not isinstance(template, Mapping):
        _add_setup_blocker(blockers, "template_hash_mismatch", "template", "object", template)
        template = {}

    drawing_path = audit.get("drawing_full_path")
    if not isinstance(drawing_path, str) or not drawing_path.strip():
        _add_setup_blocker(blockers, "drawing_target_mismatch", "drawing_full_path", "non-empty path", drawing_path)
    expected_drawing_path = plan.get("drawing_full_path")
    if isinstance(expected_drawing_path, str) and drawing_path != expected_drawing_path:
        _add_setup_blocker(blockers, "drawing_target_mismatch", "drawing_full_path", expected_drawing_path, drawing_path)

    drawing_sha256 = audit.get("drawing_sha256")
    if not isinstance(drawing_sha256, str) or _HASH_RE.fullmatch(drawing_sha256) is None:
        _add_setup_blocker(blockers, "drawing_target_mismatch", "drawing_sha256", "64 lowercase hex characters", drawing_sha256)

    dbmod_before = audit.get("dbmod_before")
    dbmod_after = audit.get("dbmod_after")
    if audit.get("changed") is not False or dbmod_before != dbmod_after:
        _add_setup_blocker(blockers, "source_changed", "changed", False, audit.get("changed"))
        if dbmod_before != dbmod_after:
            _add_setup_blocker(blockers, "source_changed", "dbmod_after", dbmod_before, dbmod_after)

    expected_variables = expectations.get("variables")
    actual_variables = audit.get("variables")
    if not isinstance(expected_variables, Mapping):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations.variables", "object", expected_variables)
        expected_variables = {}
    if not isinstance(actual_variables, Mapping):
        _add_setup_blocker(blockers, "setup_incomplete", "variables", "object", actual_variables)
        actual_variables = {}
    for key, expected in expected_variables.items():
        actual = actual_variables.get(key)
        if key not in actual_variables or actual != expected:
            _add_setup_blocker(blockers, "setup_incomplete", f"variables.{key}", expected, actual)

    expected_current_layer = expectations.get("current_layer")
    actual_current_layer = audit.get("current_layer")
    if not isinstance(expected_current_layer, str):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations.current_layer", "string", expected_current_layer)
    elif actual_current_layer != expected_current_layer:
        _add_setup_blocker(blockers, "setup_incomplete", "current_layer", expected_current_layer, actual_current_layer)

    expected_layer_list = expectations.get("required_layers")
    actual_layer_list = audit.get("layers")
    if not isinstance(expected_layer_list, list):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations.required_layers", "array", expected_layer_list)
        expected_layer_list = []
    actual_layers = _named_entries(actual_layer_list, "name")
    if not isinstance(actual_layer_list, list):
        _add_setup_blocker(blockers, "setup_incomplete", "layers", "array", actual_layer_list)
    for expected_layer in expected_layer_list:
        if not isinstance(expected_layer, Mapping) or not isinstance(expected_layer.get("name"), str):
            _add_setup_blocker(blockers, "profile_missing", "setup_expectations.required_layers", "named layer", expected_layer)
            continue
        name = expected_layer["name"]
        actual_layer = actual_layers.get(name)
        if actual_layer is None:
            _add_setup_blocker(blockers, "setup_incomplete", f"layers[{name}]", expected_layer, None)
            continue
        for key in ("linetype", "plottable"):
            if actual_layer.get(key) != expected_layer.get(key):
                _add_setup_blocker(blockers, "setup_incomplete", f"layers[{name}].{key}", expected_layer.get(key), actual_layer.get(key))

    expected_styles = expectations.get("required_styles")
    actual_styles = audit.get("styles")
    if not isinstance(expected_styles, Mapping):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations.required_styles", "object", expected_styles)
        expected_styles = {}
    if not isinstance(actual_styles, Mapping):
        _add_setup_blocker(blockers, "setup_incomplete", "styles", "object", actual_styles)
        actual_styles = {}
    if set(actual_styles) != set(expected_styles):
        _add_setup_blocker(blockers, "profile_hash_mismatch", "styles", dict(expected_styles), dict(actual_styles))
    for key, expected in expected_styles.items():
        actual = actual_styles.get(key)
        if not isinstance(expected, list) or not isinstance(actual, list):
            _add_setup_blocker(blockers, "setup_incomplete", f"styles.{key}", expected, actual)
        elif sorted(actual) != sorted(expected):
            _add_setup_blocker(blockers, "profile_hash_mismatch", f"styles.{key}", expected, actual)

    expected_layouts = expectations.get("layouts")
    actual_layouts = audit.get("layouts")
    if not isinstance(expected_layouts, list):
        _add_setup_blocker(blockers, "profile_missing", "setup_expectations.layouts", "array", expected_layouts)
        expected_layouts = []
    actual_layouts_by_name = _named_entries(actual_layouts, "name")
    if not isinstance(actual_layouts, list):
        _add_setup_blocker(blockers, "setup_incomplete", "layouts", "array", actual_layouts)
    for expected_layout in expected_layouts:
        if not isinstance(expected_layout, Mapping) or not isinstance(expected_layout.get("name"), str):
            _add_setup_blocker(blockers, "profile_missing", "setup_expectations.layouts", "named layout", expected_layout)
            continue
        name = expected_layout["name"]
        actual_layout = actual_layouts_by_name.get(name)
        if actual_layout is None:
            _add_setup_blocker(blockers, "viewport_scale_mismatch", f"layouts[{name}]", expected_layout, None)
            continue
        for key in ("viewport_scales", "locked"):
            expected = expected_layout.get(key)
            actual = actual_layout.get(key)
            if key == "viewport_scales" and isinstance(expected, list) and isinstance(actual, list):
                matches = sorted(actual) == sorted(expected)
            else:
                matches = actual == expected
            if not matches:
                _add_setup_blocker(blockers, "viewport_scale_mismatch", f"layouts[{name}].{key}", expected, actual)

    expected_template_hash = template.get("embedded_settings_sha256")
    actual_properties = audit.get("custom_properties")
    actual_template_hash = actual_properties.get("CAD_AGENT_SETTINGS_SHA256") if isinstance(actual_properties, Mapping) else None
    if actual_template_hash != expected_template_hash:
        _add_setup_blocker(blockers, "template_hash_mismatch", "custom_properties.CAD_AGENT_SETTINGS_SHA256", expected_template_hash, actual_template_hash)

    font_report = audit.get("font_report", {"missing": [], "substituted": []})
    substituted = font_report.get("substituted", []) if isinstance(font_report, Mapping) else font_report
    missing = font_report.get("missing", []) if isinstance(font_report, Mapping) else font_report
    if substituted or missing:
        _add_setup_blocker(blockers, "font_substitution_risk", "font_report", [], font_report)

    try:
        setup_plan_sha256 = canonical_json_sha256(plan)
        audit_sha256 = canonical_json_sha256(audit)
    except (TypeError, ValueError) as exc:
        raise DrawingSetupError("Drawing Setup plan or audit cannot be canonically hashed") from exc

    return {
        "schema_version": "drawing-setup-evidence-1.0",
        "status": "SETUP_VERIFIED" if not blockers else "NEEDS_REVIEW",
        "run_id": plan.get("run_id"),
        "setup_plan_sha256": setup_plan_sha256,
        "audit_sha256": audit_sha256,
        "drawing_profile_sha256": plan.get("drawing_profile", {}).get("sha256") if isinstance(plan.get("drawing_profile"), Mapping) else None,
        "template_file_sha256": template.get("file_sha256"),
        "blockers": blockers,
        "verified_by": verified_by.strip(),
        "approval_reference": approval_reference.strip(),
    }


def require_setup_verified(
    evidence: Mapping[str, object],
    *,
    setup_plan_sha256: str,
    drawing_profile_sha256: str,
    template_file_sha256: str,
) -> None:
    """Fail closed unless evidence is verified and bound to the expected inputs."""
    if not isinstance(evidence, Mapping):
        raise DrawingSetupError("Drawing Setup evidence must be an object")
    if evidence.get("status") != "SETUP_VERIFIED":
        raise DrawingSetupError("Drawing Setup evidence is not SETUP_VERIFIED")
    if evidence.get("blockers") != []:
        raise DrawingSetupError("Drawing Setup evidence contains blockers")
    expected_hashes = {
        "setup_plan_sha256": setup_plan_sha256,
        "drawing_profile_sha256": drawing_profile_sha256,
        "template_file_sha256": template_file_sha256,
    }
    for key, expected in expected_hashes.items():
        if evidence.get(key) != expected:
            raise DrawingSetupError(f"Drawing Setup evidence {key} does not match")


__all__ = [
    "DrawingSetupError",
    "SETUP_BLOCKERS",
    "create_setup_plan",
    "evaluate_setup_plan",
    "require_setup_verified",
]
