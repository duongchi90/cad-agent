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
_MISSING = object()


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


def _required_mapping(
    source: Mapping[str, object], key: str, display_name: str
) -> Mapping[str, object]:
    value = source.get(key)
    if not isinstance(value, Mapping):
        raise _fail(f"invalid {display_name}: {key} must be an object")
    return value


def _required_list(source: Mapping[str, object], key: str, display_name: str) -> list[object]:
    value = source.get(key)
    if not isinstance(value, list):
        raise _fail(f"invalid {display_name}: {key} must be a list")
    return value


def _add_blocker(
    blockers: list[dict[str, object]],
    code: str,
    path: str,
    expected: object,
    actual: object,
) -> None:
    if code not in SETUP_BLOCKERS:
        raise AssertionError(f"unsupported setup blocker code: {code}")
    blockers.append(
        {
            "code": code,
            "path": path,
            "expected": copy.deepcopy(None if expected is _MISSING else expected),
            "actual": copy.deepcopy(None if actual is _MISSING else actual),
            "severity": "error",
        }
    )


def _named_items(values: list[object]) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for value in values:
        if isinstance(value, Mapping) and isinstance(value.get("name"), str):
            result[value["name"]] = value
    return result


def evaluate_setup_plan(
    plan: Mapping[str, object],
    audit: Mapping[str, object],
    *,
    verified_by: str,
    approval_reference: str,
) -> dict[str, object]:
    """Compare one strict plan/audit pair and return deterministic gate evidence."""
    if not isinstance(plan, Mapping) or not isinstance(audit, Mapping):
        raise _fail("setup plan and audit must be objects")
    if not isinstance(verified_by, str) or not verified_by.strip():
        raise _fail("verified_by must be a non-empty string")
    if not isinstance(approval_reference, str) or not approval_reference.strip():
        raise _fail("approval_reference must be a non-empty string")

    expectations = _required_mapping(plan, "setup_expectations", "setup plan")
    profile_ref = _required_mapping(plan, "drawing_profile", "setup plan")
    template_ref = _required_mapping(plan, "template", "setup plan")
    expected_variables = _required_mapping(expectations, "variables", "setup expectations")
    expected_styles = _required_mapping(
        expectations, "required_styles", "setup expectations"
    )
    expected_layers = _required_list(
        expectations, "required_layers", "setup expectations"
    )
    expected_layouts = _required_list(expectations, "layouts", "setup expectations")
    blockers: list[dict[str, object]] = []

    if audit.get("changed") is not False:
        _add_blocker(blockers, "source_changed", "changed", False, audit.get("changed"))
    dbmod_before = audit.get("dbmod_before", _MISSING)
    dbmod_after = audit.get("dbmod_after", _MISSING)
    if (
        isinstance(dbmod_before, bool)
        or not isinstance(dbmod_before, int)
        or isinstance(dbmod_after, bool)
        or not isinstance(dbmod_after, int)
        or dbmod_before != dbmod_after
    ):
        _add_blocker(
            blockers,
            "source_changed",
            "dbmod_after",
            dbmod_before,
            dbmod_after,
        )

    drawing_path = audit.get("drawing_full_path")
    if (
        not isinstance(drawing_path, str)
        or not drawing_path.strip()
        or not Path(drawing_path).is_absolute()
        or Path(drawing_path).suffix.lower() not in {".dwg", ".dxf"}
    ):
        _add_blocker(
            blockers,
            "drawing_target_mismatch",
            "drawing_full_path",
            "absolute .dwg or .dxf path",
            drawing_path,
        )
    drawing_hash = audit.get("drawing_sha256")
    if not isinstance(drawing_hash, str) or _SHA256_RE.fullmatch(drawing_hash) is None:
        _add_blocker(
            blockers,
            "drawing_target_mismatch",
            "drawing_sha256",
            "64 lowercase hexadecimal characters",
            drawing_hash,
        )

    actual_variables = audit.get("variables")
    actual_variables = actual_variables if isinstance(actual_variables, Mapping) else {}
    for name in sorted(expected_variables):
        expected = expected_variables[name]
        actual = actual_variables.get(name, _MISSING)
        if actual != expected:
            _add_blocker(
                blockers,
                "setup_incomplete",
                f"variables.{name}",
                expected,
                actual,
            )

    expected_current_layer = expectations.get("current_layer", _MISSING)
    actual_current_layer = audit.get("current_layer", _MISSING)
    if actual_current_layer != expected_current_layer:
        _add_blocker(
            blockers,
            "setup_incomplete",
            "current_layer",
            expected_current_layer,
            actual_current_layer,
        )

    actual_layer_values = audit.get("layers")
    actual_layers = _named_items(actual_layer_values if isinstance(actual_layer_values, list) else [])
    for expected_layer_value in expected_layers:
        if not isinstance(expected_layer_value, Mapping) or not isinstance(
            expected_layer_value.get("name"), str
        ):
            raise _fail("invalid setup expectations: required layer")
        name = expected_layer_value["name"]
        actual_layer = actual_layers.get(name)
        if actual_layer is None:
            _add_blocker(
                blockers,
                "setup_incomplete",
                f"layers.{name}",
                dict(expected_layer_value),
                None,
            )
            continue
        for field in ("linetype", "plottable"):
            expected = expected_layer_value.get(field, _MISSING)
            actual = actual_layer.get(field, _MISSING)
            if actual != expected:
                _add_blocker(
                    blockers,
                    "setup_incomplete",
                    f"layers.{name}.{field}",
                    expected,
                    actual,
                )

    actual_styles = audit.get("styles")
    actual_styles = actual_styles if isinstance(actual_styles, Mapping) else {}
    for category in ("text", "dimension", "mleader", "table"):
        required_names = expected_styles.get(category)
        actual_names = actual_styles.get(category)
        if not isinstance(required_names, list):
            raise _fail(f"invalid setup expectations: styles.{category}")
        if not isinstance(actual_names, list):
            _add_blocker(
                blockers,
                "profile_missing",
                f"styles.{category}",
                required_names,
                actual_names,
            )
            continue
        for name in required_names:
            if name not in actual_names:
                _add_blocker(
                    blockers,
                    "profile_hash_mismatch",
                    f"styles.{category}.{name}",
                    True,
                    False,
                )

    actual_layout_values = audit.get("layouts")
    actual_layouts = _named_items(
        actual_layout_values if isinstance(actual_layout_values, list) else []
    )
    for expected_layout_value in expected_layouts:
        if not isinstance(expected_layout_value, Mapping) or not isinstance(
            expected_layout_value.get("name"), str
        ):
            raise _fail("invalid setup expectations: layout")
        name = expected_layout_value["name"]
        actual_layout = actual_layouts.get(name)
        if actual_layout is None:
            _add_blocker(
                blockers,
                "viewport_scale_mismatch",
                f"layouts.{name}",
                dict(expected_layout_value),
                None,
            )
            continue
        expected_scales = expected_layout_value.get("viewport_scales", _MISSING)
        actual_scales = actual_layout.get("viewport_scales", _MISSING)
        normalized_expected = (
            sorted(expected_scales) if isinstance(expected_scales, list) else expected_scales
        )
        normalized_actual = (
            sorted(actual_scales) if isinstance(actual_scales, list) else actual_scales
        )
        if normalized_actual != normalized_expected:
            _add_blocker(
                blockers,
                "viewport_scale_mismatch",
                f"layouts.{name}.viewport_scales",
                normalized_expected,
                normalized_actual,
            )
        expected_locked = expected_layout_value.get("locked", _MISSING)
        actual_locked = actual_layout.get("locked", _MISSING)
        if actual_locked != expected_locked:
            _add_blocker(
                blockers,
                "viewport_scale_mismatch",
                f"layouts.{name}.locked",
                expected_locked,
                actual_locked,
            )

    font_report = audit.get("font_report")
    font_report = font_report if isinstance(font_report, Mapping) else {}
    for field in ("missing", "substituted"):
        actual = font_report.get(field, _MISSING)
        if actual != []:
            _add_blocker(
                blockers,
                "font_substitution_risk",
                f"font_report.{field}",
                [],
                actual,
            )

    expected_settings_hash = template_ref.get("embedded_settings_sha256", _MISSING)
    actual_properties = audit.get("custom_properties")
    actual_properties = actual_properties if isinstance(actual_properties, Mapping) else {}
    actual_settings_hash = actual_properties.get("CAD_AGENT_SETTINGS_SHA256", _MISSING)
    if actual_settings_hash != expected_settings_hash:
        _add_blocker(
            blockers,
            "template_hash_mismatch",
            "custom_properties.CAD_AGENT_SETTINGS_SHA256",
            expected_settings_hash,
            actual_settings_hash,
        )
    calculated_settings_hash = canonical_json_sha256(expectations)
    if expected_settings_hash != calculated_settings_hash:
        _add_blocker(
            blockers,
            "profile_hash_mismatch",
            "template.embedded_settings_sha256",
            calculated_settings_hash,
            expected_settings_hash,
        )

    run_id = plan.get("run_id")
    profile_hash = profile_ref.get("sha256")
    template_hash = template_ref.get("file_sha256")
    if not isinstance(run_id, str) or _ID_RE.fullmatch(run_id) is None:
        raise _fail("invalid setup plan run_id")
    for name, value in (
        ("drawing_profile.sha256", profile_hash),
        ("template.file_sha256", template_hash),
    ):
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise _fail(f"invalid setup plan {name}")

    blockers.sort(key=lambda item: (str(item["code"]), str(item["path"])))
    return {
        "schema_version": "drawing-setup-evidence-1.0",
        "status": "SETUP_VERIFIED" if not blockers else "NEEDS_REVIEW",
        "run_id": run_id,
        "setup_plan_sha256": canonical_json_sha256(plan),
        "audit_sha256": canonical_json_sha256(audit),
        "drawing_profile_sha256": profile_hash,
        "template_file_sha256": template_hash,
        "blockers": blockers,
        "verified_by": verified_by,
        "approval_reference": approval_reference,
    }


def require_setup_verified(
    evidence: Mapping[str, object],
    *,
    setup_plan_sha256: str,
    drawing_profile_sha256: str,
    template_file_sha256: str,
) -> None:
    """Refuse any non-verified, blocked, or stale Drawing Setup evidence."""
    if not isinstance(evidence, Mapping):
        raise _fail("Drawing Setup evidence must be an object")
    if evidence.get("status") != "SETUP_VERIFIED":
        raise _fail("Drawing Setup evidence is not SETUP_VERIFIED")
    if evidence.get("blockers") != []:
        raise _fail("SETUP_VERIFIED evidence must contain no blockers")

    expected_hashes = {
        "setup_plan_sha256": setup_plan_sha256,
        "drawing_profile_sha256": drawing_profile_sha256,
        "template_file_sha256": template_file_sha256,
    }
    for name, expected in expected_hashes.items():
        if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
            raise _fail(f"invalid expected {name}")
        if evidence.get(name) != expected:
            raise _fail(f"stale Drawing Setup evidence: {name} mismatch")
    audit_hash = evidence.get("audit_sha256")
    if not isinstance(audit_hash, str) or _SHA256_RE.fullmatch(audit_hash) is None:
        raise _fail("Drawing Setup evidence audit_sha256 is invalid")


__all__ = [
    "DrawingSetupError",
    "SETUP_BLOCKERS",
    "create_setup_audit",
    "create_setup_plan",
    "evaluate_setup_plan",
    "require_setup_verified",
]
