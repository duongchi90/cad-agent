"""Strict Drawing Setup contracts and canonical hashing.

This module is intentionally pure Python.  It validates the boundary consumed by
the later setup-plan, AutoCAD, and release-gate tasks without adding jsonschema
or any other runtime dependency.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_VARIABLES = {
    "INSUNITS", "MEASUREMENT", "LTSCALE", "CELTSCALE",
    "PSLTSCALE", "MSLTSCALE", "DIMASSOC", "ANNOALLVISIBLE",
}
_EXPECTATION_KEYS = {
    "variables", "current_layer", "required_layers",
    "required_styles", "layouts", "font_policy",
}
_EXPECTATION_POLICY_PATHS = {
    "variables.INSUNITS",
    "variables.MEASUREMENT",
    "variables.LTSCALE",
    "variables.CELTSCALE",
    "variables.PSLTSCALE",
    "variables.MSLTSCALE",
    "variables.DIMASSOC",
    "variables.ANNOALLVISIBLE",
    "current_layer",
    "required_layers",
    "required_styles",
    "layouts",
    "font_policy",
    "embedded_settings",
}
_EXPECTATION_POLICY_MODES = {"GATING", "OBSERVATION_ONLY"}
_EVIDENCE_POLICY_KEYS = {
    "expectation_policy_sha256",
    "verification_scope",
    "verification_reason",
    "gating_paths",
    "evaluated_gating_paths",
    "observation_only_paths",
    "unresolved_paths",
    "observation_records",
    "conformance_assertion",
}
_REQUIRED_EVIDENCE_POLICY_KEYS = _EVIDENCE_POLICY_KEYS - {"verification_reason"}


class DrawingContractError(ValueError):
    """Raised when a Drawing Setup contract is absent, malformed, or unapproved."""


def _assert_finite_json(value: object, *, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DrawingContractError(f"{path} must contain only finite numbers")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_finite_json(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite_json(item, path=f"{path}[{index}]")


def canonical_json_sha256(payload: Mapping[str, object]) -> str:
    """Return SHA-256 for the canonical UTF-8 JSON representation of a mapping."""
    if not isinstance(payload, Mapping):
        raise TypeError("canonical JSON hashing requires a mapping")
    _assert_finite_json(payload)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(contract: str, message: str) -> None:
    raise DrawingContractError(f"{contract}: {message}")


def _keys(payload: Mapping[str, Any], *, contract: str, required: set[str], optional: set[str] | None = None) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(payload))
    unexpected = sorted(set(payload) - allowed)
    if missing:
        _fail(contract, f"missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(contract, f"Unexpected properties: {', '.join(unexpected)}")


def _object(value: object, *, contract: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(contract, f"{path} must be an object")
    return value


def _string(value: object, *, contract: str, path: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(contract, f"{path} must be a non-empty string")
    if pattern is not None and not pattern.fullmatch(value):
        _fail(contract, f"{path} has invalid format")
    return value


def _bool(value: object, *, contract: str, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(contract, f"{path} must be boolean")
    return value


def _number(value: object, *, contract: str, path: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(contract, f"{path} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(contract, f"{path} must be finite")
    return value


def _sha(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if not _HASH_RE.fullmatch(text):
        _fail(contract, f"{path} must be a lowercase SHA-256")
    return text


def _id(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if not _ID_RE.fullmatch(text):
        _fail(contract, f"{path} has invalid identifier format")
    return text


def _approval(value: object, *, contract: str, path: str = "approval") -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required={"reference", "approved_by"})
    _string(item["reference"], contract=contract, path=f"{path}.reference")
    _string(item["approved_by"], contract=contract, path=f"{path}.approved_by")


def _common(
    payload: dict[str, Any],
    *,
    contract: str,
    version: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    if "schema_version" not in payload:
        _fail(contract, "missing required properties: schema_version")
    if required != {"schema_version"}:
        _keys(payload, contract=contract, required=required, optional=optional)
    if payload.get("schema_version") != version:
        _fail(contract, f"schema_version must be {version!r}")
    _id(payload.get("id", ""), contract=contract, path="id") if "id" in required else None
    if "revision" in required:
        _string(payload["revision"], contract=contract, path="revision")
    if "status" in required and payload.get("status") != "APPROVED":
        _fail(contract, "status must be APPROVED")
    if "approval" in required:
        _approval(payload["approval"], contract=contract)


def _strings(value: object, *, contract: str, path: str, min_items: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(contract, f"{path} must be a non-empty list")
    for index, item in enumerate(value):
        _string(item, contract=contract, path=f"{path}[{index}]")
    return value


def _audit_style_names(value: object, *, contract: str, path: str, min_items: int = 1) -> list[str]:
    """Validate observed audit style names, including AutoCAD's empty text name."""
    if not isinstance(value, list) or len(value) < min_items:
        _fail(contract, f"{path} must be a non-empty list")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            _fail(contract, f"{path}[{index}] must be a string")
    return value


def _validate_definition(payload: dict[str, Any]) -> None:
    contract = "drawing_definition"
    required = {"schema_version","id","domain","drawing_type","purpose","source_mode","revision","release_profile","status","approval"}
    _common(payload, contract=contract, version="drawing-definition-1.0", required=required)
    for key in ("domain", "drawing_type", "purpose", "source_mode"):
        _string(payload[key], contract=contract, path=key)
    if payload["release_profile"] not in {"REVIEW", "AUTHORITATIVE"}:
        _fail(contract, "release_profile must be REVIEW or AUTHORITATIVE")


def _validate_layer(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required={"name","linetype","plottable"})
    _string(item["name"], contract=contract, path=f"{path}.name")
    _string(item["linetype"], contract=contract, path=f"{path}.linetype")
    _bool(item["plottable"], contract=contract, path=f"{path}.plottable")


def _validate_expectation_policy(value: object, *, contract: str) -> dict[str, Any]:
    policy = _object(value, contract=contract, path="expectation_policy")
    _keys(
        policy,
        contract=contract,
        required={"schema_version", "default_mode", "field_modes"},
    )
    if policy["schema_version"] != "drawing-setup-expectation-policy-1.0":
        _fail(contract, "expectation_policy.schema_version is invalid")
    if policy["default_mode"] != "GATING":
        _fail(contract, "expectation_policy.default_mode must be GATING")
    field_modes = _object(
        policy["field_modes"],
        contract=contract,
        path="expectation_policy.field_modes",
    )
    for path, mode in field_modes.items():
        _string(path, contract=contract, path="expectation_policy.field_modes key")
        if path not in _EXPECTATION_POLICY_PATHS:
            _fail(contract, f"expectation_policy.field_modes.{path} is invalid")
        _string(mode, contract=contract, path=f"expectation_policy.field_modes.{path}")
        if mode not in _EXPECTATION_POLICY_MODES:
            _fail(contract, f"expectation_policy.field_modes.{path} is invalid")
    return policy


def _expectation_mode(policy: Mapping[str, Any] | None, path: str) -> str:
    if policy is None:
        return "GATING"
    field_modes = policy["field_modes"]
    assert isinstance(field_modes, Mapping)
    mode = field_modes.get(path, policy["default_mode"])
    assert isinstance(mode, str)
    return mode


def _observation_unresolved(policy: Mapping[str, Any] | None, path: str, value: object) -> bool:
    return _expectation_mode(policy, path) == "OBSERVATION_ONLY" and value == "UNRESOLVED"


def _validate_expectations(
    value: object,
    *,
    contract: str,
    policy: Mapping[str, Any] | None = None,
) -> None:
    item = _object(value, contract=contract, path="setup_expectations")
    _keys(item, contract=contract, required=_EXPECTATION_KEYS)
    variables = _object(item["variables"], contract=contract, path="setup_expectations.variables")
    _keys(variables, contract=contract, required=_VARIABLES)
    for key in _VARIABLES:
        path = f"variables.{key}"
        if not _observation_unresolved(policy, path, variables[key]):
            _number(variables[key], contract=contract, path=f"setup_expectations.{path}")
    if not _observation_unresolved(policy, "current_layer", item["current_layer"]):
        _string(item["current_layer"], contract=contract, path="setup_expectations.current_layer")
    layers = item["required_layers"]
    if not (
        _observation_unresolved(policy, "required_layers", layers)
        or (_expectation_mode(policy, "required_layers") == "OBSERVATION_ONLY" and layers == [])
    ):
        if not isinstance(layers, list) or not layers:
            _fail(contract, "setup_expectations.required_layers must be non-empty")
        for index, layer in enumerate(layers):
            _validate_layer(layer, contract=contract, path=f"setup_expectations.required_layers[{index}]")
    styles_value = item["required_styles"]
    if not _observation_unresolved(policy, "required_styles", styles_value):
        styles = _object(styles_value, contract=contract, path="setup_expectations.required_styles")
        _keys(styles, contract=contract, required={"text","dimension","mleader","table"})
        min_items = 0 if _expectation_mode(policy, "required_styles") == "OBSERVATION_ONLY" else 1
        for key in ("text","dimension","mleader","table"):
            _strings(
                styles[key],
                contract=contract,
                path=f"setup_expectations.required_styles.{key}",
                min_items=min_items,
            )
    layouts = item["layouts"]
    if not (
        _observation_unresolved(policy, "layouts", layouts)
        or (_expectation_mode(policy, "layouts") == "OBSERVATION_ONLY" and layouts == [])
    ):
        if not isinstance(layouts, list) or not layouts:
            _fail(contract, "setup_expectations.layouts must be non-empty")
        for index, layout in enumerate(layouts):
            layout_item = _object(layout, contract=contract, path=f"setup_expectations.layouts[{index}]")
            _keys(layout_item, contract=contract, required={"name","viewport_scales","locked"})
            _string(layout_item["name"], contract=contract, path=f"setup_expectations.layouts[{index}].name")
            scales = layout_item["viewport_scales"]
            if not isinstance(scales, list) or not scales:
                _fail(contract, f"setup_expectations.layouts[{index}].viewport_scales must be a non-empty list")
            for scale in scales:
                number = _number(
                    scale,
                    contract=contract,
                    path=f"setup_expectations.layouts[{index}].viewport_scales",
                )
                if number <= 0:
                    _fail(contract, "viewport scales must be positive")
            _bool(layout_item["locked"], contract=contract, path=f"setup_expectations.layouts[{index}].locked")
    font_value = item["font_policy"]
    if not _observation_unresolved(policy, "font_policy", font_value):
        font = _object(font_value, contract=contract, path="setup_expectations.font_policy")
        _keys(font, contract=contract, required={"selected_mode","new_drawing","legacy_compatibility"})
        if font["selected_mode"] not in {"NEW_DRAWING","LEGACY_COMPATIBILITY"}:
            _fail(contract, "font_policy.selected_mode is invalid")
        new = _object(font["new_drawing"], contract=contract, path="font_policy.new_drawing")
        _keys(new, contract=contract, required={"approved_fonts","substitution_allowed"})
        _strings(new["approved_fonts"], contract=contract, path="font_policy.new_drawing.approved_fonts")
        if _bool(new["substitution_allowed"], contract=contract, path="font_policy.new_drawing.substitution_allowed"):
            _fail(contract, "new_drawing font substitution must be false")
        legacy = _object(font["legacy_compatibility"], contract=contract, path="font_policy.legacy_compatibility")
        _keys(legacy, contract=contract, required={"preserve_source_styles","mapping_report_required"})
        if not _bool(legacy["preserve_source_styles"], contract=contract, path="font_policy.legacy_compatibility.preserve_source_styles"):
            _fail(contract, "legacy compatibility must preserve source styles")
        if not _bool(legacy["mapping_report_required"], contract=contract, path="font_policy.legacy_compatibility.mapping_report_required"):
            _fail(contract, "legacy compatibility requires a mapping report")


def _validate_profile(payload: dict[str, Any]) -> None:
    contract = "drawing_profile"
    required = {"schema_version","id","revision","status","supported_domains","supported_drawing_types","model","setup_expectations","approval"}
    _common(payload, contract=contract, version="drawing-profile-1.0", required=required)
    _strings(payload["supported_domains"], contract=contract, path="supported_domains")
    _strings(payload["supported_drawing_types"], contract=contract, path="supported_drawing_types")
    model = _object(payload["model"], contract=contract, path="model")
    _keys(model, contract=contract, required={"unit","scale","ucs"})
    if model != {"unit":"mm","scale":"1:1","ucs":"WORLD"}:
        _fail(contract, "model must use mm, 1:1, WORLD")
    _validate_expectations(payload["setup_expectations"], contract=contract)


def _validate_domain_pack(payload: dict[str, Any]) -> None:
    contract = "domain_pack"
    required = {"schema_version","id","revision","status","domains","drawing_types","vocabulary","approval"}
    _common(payload, contract=contract, version="domain-pack-1.0", required=required)
    _strings(payload["domains"], contract=contract, path="domains")
    _strings(payload["drawing_types"], contract=contract, path="drawing_types")
    _strings(payload["vocabulary"], contract=contract, path="vocabulary")


def _validate_template_manifest(payload: dict[str, Any]) -> None:
    contract = "template_manifest"
    required = {"schema_version","id","revision","file_name","file_sha256","drawing_profile_sha256","embedded_settings_sha256","status","approval"}
    _common(payload, contract=contract, version="template-manifest-1.0", required=required)
    file_name = _string(payload["file_name"], contract=contract, path="file_name")
    if not file_name.lower().endswith(".dwt") or "/" in file_name or "\\" in file_name:
        _fail(contract, "file_name must be a filename ending in .dwt")
    for key in ("file_sha256","drawing_profile_sha256","embedded_settings_sha256"):
        _sha(payload[key], contract=contract, path=key)


def _validate_ref(value: object, *, contract: str, path: str, fields: set[str]) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required=fields)
    for key in fields:
        if key.endswith("sha256") or key == "file_sha256":
            _sha(item[key], contract=contract, path=f"{path}.{key}")
        elif key == "id":
            _id(item[key], contract=contract, path=f"{path}.{key}")
        elif key == "revision":
            _string(item[key], contract=contract, path=f"{path}.{key}")


def _validate_setup_plan(payload: dict[str, Any]) -> None:
    contract = "drawing_setup_plan"
    required = {"schema_version","run_id","state","definition","drawing_profile","domain_pack","template","setup_expectations"}
    _common(
        payload,
        contract=contract,
        version="drawing-setup-plan-1.0",
        required=required,
        optional={"expectation_policy"},
    )
    _id(payload["run_id"], contract=contract, path="run_id")
    if payload["state"] != "SETUP_PENDING":
        _fail(contract, "state must be SETUP_PENDING")
    _validate_ref(payload["definition"], contract=contract, path="definition", fields={"id","sha256"})
    _validate_ref(payload["drawing_profile"], contract=contract, path="drawing_profile", fields={"id","revision","sha256"})
    _validate_ref(payload["domain_pack"], contract=contract, path="domain_pack", fields={"id","revision","sha256"})
    _validate_ref(payload["template"], contract=contract, path="template", fields={"id","revision","file_sha256","embedded_settings_sha256"})
    policy = (
        _validate_expectation_policy(payload["expectation_policy"], contract=contract)
        if "expectation_policy" in payload
        else None
    )
    _validate_expectations(payload["setup_expectations"], contract=contract, policy=policy)


def _validate_audit_entry(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required={"name","linetype","plottable"})
    _string(item["name"], contract=contract, path=f"{path}.name")
    _string(item["linetype"], contract=contract, path=f"{path}.linetype")
    _bool(item["plottable"], contract=contract, path=f"{path}.plottable")


def _validate_audit(payload: dict[str, Any]) -> None:
    contract = "drawing_setup_audit"
    required = {"schema_version","drawing_full_path","drawing_sha256","changed","dbmod_before","dbmod_after","variables","current_layer","custom_properties","layers","styles","layouts","font_report"}
    _common(payload, contract=contract, version="drawing-setup-audit-1.0", required={"schema_version"})
    _keys(payload, contract=contract, required=required)
    _string(payload["drawing_full_path"], contract=contract, path="drawing_full_path")
    _sha(payload["drawing_sha256"], contract=contract, path="drawing_sha256")
    _bool(payload["changed"], contract=contract, path="changed")
    for key in ("dbmod_before","dbmod_after"):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(contract, f"{key} must be integer")
    variables = _object(payload["variables"], contract=contract, path="variables")
    for key, value in variables.items():
        _string(key, contract=contract, path=f"variables.{key}")
        _number(value, contract=contract, path=f"variables.{key}")
    _string(payload["current_layer"], contract=contract, path="current_layer")
    properties = _object(payload["custom_properties"], contract=contract, path="custom_properties")
    for key, value in properties.items():
        _string(key, contract=contract, path=f"custom_properties.{key}")
        _string(value, contract=contract, path=f"custom_properties.{key}")
    layers = payload["layers"]
    if not isinstance(layers, list):
        _fail(contract, "layers must be a list")
    for index, layer in enumerate(layers):
        _validate_audit_entry(layer, contract=contract, path=f"layers[{index}]")
    styles = _object(payload["styles"], contract=contract, path="styles")
    _keys(styles, contract=contract, required={"text","dimension","mleader","table"})
    _audit_style_names(styles["text"], contract=contract, path="styles.text")
    for key in ("dimension", "mleader", "table"):
        _strings(styles[key], contract=contract, path=f"styles.{key}")
    layouts = payload["layouts"]
    if not isinstance(layouts, list):
        _fail(contract, "layouts must be a list")
    for index, layout in enumerate(layouts):
        item = _object(layout, contract=contract, path=f"layouts[{index}]")
        _keys(item, contract=contract, required={"name","viewport_scales","locked"})
        _string(item["name"], contract=contract, path=f"layouts[{index}].name")
        scales = item["viewport_scales"]
        if not isinstance(scales, list):
            _fail(contract, f"layouts[{index}].viewport_scales must be a list")
        for scale in scales:
            if _number(scale, contract=contract, path=f"layouts[{index}].viewport_scales") <= 0:
                _fail(contract, "viewport scales must be positive")
        _bool(item["locked"], contract=contract, path=f"layouts[{index}].locked")
    font = _object(payload["font_report"], contract=contract, path="font_report")
    _keys(font, contract=contract, required={"missing","substituted"})
    _strings(font["missing"], contract=contract, path="font_report.missing", min_items=0)
    _strings(font["substituted"], contract=contract, path="font_report.substituted", min_items=0)


def _validate_blocker(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required={"code","path","expected","actual","severity"})
    _string(item["code"], contract=contract, path=f"{path}.code")
    _string(item["path"], contract=contract, path=f"{path}.path")
    _string(item["severity"], contract=contract, path=f"{path}.severity")
    if not isinstance(item["expected"], (str, int, float, bool, type(None), list, dict)):
        _fail(contract, f"{path}.expected must be JSON-compatible")
    if not isinstance(item["actual"], (str, int, float, bool, type(None), list, dict)):
        _fail(contract, f"{path}.actual must be JSON-compatible")
    _assert_finite_json(item["expected"], path=f"{path}.expected")
    _assert_finite_json(item["actual"], path=f"{path}.actual")


def _validate_observation_record(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(item, contract=contract, required={"path", "observed_value", "comparison", "conformance"})
    _string(item["path"], contract=contract, path=f"{path}.path")
    if not isinstance(item["observed_value"], (str, int, float, bool, type(None), list, dict)):
        _fail(contract, f"{path}.observed_value must be JSON-compatible")
    _assert_finite_json(item["observed_value"], path=f"{path}.observed_value")
    if item["comparison"] != "NOT_EVALUATED":
        _fail(contract, f"{path}.comparison must be NOT_EVALUATED")
    if item["conformance"] != "NOT_ASSERTED":
        _fail(contract, f"{path}.conformance must be NOT_ASSERTED")


def _validate_policy_evidence(payload: dict[str, Any], *, contract: str) -> None:
    present = _EVIDENCE_POLICY_KEYS & set(payload)
    if not present:
        return
    if not _REQUIRED_EVIDENCE_POLICY_KEYS <= present:
        _fail(contract, "policy evidence must include every scoped field")

    _sha(payload["expectation_policy_sha256"], contract=contract, path="expectation_policy_sha256")
    scope = payload["verification_scope"]
    if scope not in {"GATING_ONLY", "NO_CONFORMANCE_ASSERTION"}:
        _fail(contract, "verification_scope is invalid")
    if "verification_reason" in payload:
        _string(payload["verification_reason"], contract=contract, path="verification_reason")

    path_lists: dict[str, list[str]] = {}
    for key in (
        "gating_paths",
        "evaluated_gating_paths",
        "observation_only_paths",
        "unresolved_paths",
    ):
        values = _strings(payload[key], contract=contract, path=key, min_items=0)
        if len(values) != len(set(values)) or any(
            value not in _EXPECTATION_POLICY_PATHS for value in values
        ):
            _fail(contract, f"policy evidence {key} contains an invalid or duplicate path")
        path_lists[key] = values

    if path_lists["evaluated_gating_paths"] != path_lists["gating_paths"]:
        _fail(contract, "policy evidence has an incomplete gating scope")
    if not set(path_lists["unresolved_paths"]) <= set(path_lists["observation_only_paths"]):
        _fail(contract, "policy evidence has an inconsistent unresolved scope")

    records = payload["observation_records"]
    if not isinstance(records, list):
        _fail(contract, "policy evidence observation_records must be a list")
    for index, record in enumerate(records):
        _validate_observation_record(record, contract=contract, path=f"observation_records[{index}]")
    record_paths = [record["path"] for record in records]
    if record_paths != sorted(path_lists["observation_only_paths"]):
        _fail(contract, "policy evidence has an incomplete observation scope")

    conformance_assertion = payload["conformance_assertion"]
    if not isinstance(conformance_assertion, bool):
        _fail(contract, "policy evidence conformance_assertion must be boolean")
    if payload["status"] == "NEEDS_REVIEW" and conformance_assertion is not False:
        _fail(contract, "policy evidence NEEDS_REVIEW requires false conformance assertion")
    if scope == "GATING_ONLY":
        if not path_lists["gating_paths"]:
            _fail(contract, "policy evidence has an empty gating scope")
        if payload["status"] == "SETUP_VERIFIED" and conformance_assertion is not True:
            _fail(contract, "policy evidence SETUP_VERIFIED requires conformance assertion")
        if payload["status"] == "NEEDS_REVIEW" and not payload["blockers"]:
            _fail(contract, "policy evidence NEEDS_REVIEW requires blockers")
    else:
        if path_lists["gating_paths"] or conformance_assertion is not False:
            _fail(contract, "policy evidence has a non-empty conformance scope")
        if payload["status"] != "NEEDS_REVIEW":
            _fail(contract, "policy evidence SETUP_VERIFIED cannot have no conformance scope")
        if payload.get("verification_reason") != "EMPTY_GATING_SCOPE":
            _fail(contract, "policy evidence no-conformance scope requires EMPTY_GATING_SCOPE")


def _validate_evidence(payload: dict[str, Any]) -> None:
    contract = "drawing_setup_evidence"
    required = {"schema_version","status","run_id","setup_plan_sha256","audit_sha256","drawing_profile_sha256","template_file_sha256","blockers","verified_by","approval_reference"}
    _common(payload, contract=contract, version="drawing-setup-evidence-1.0", required={"schema_version"})
    _keys(payload, contract=contract, required=required, optional=_EVIDENCE_POLICY_KEYS)
    if payload["status"] not in {"SETUP_VERIFIED","NEEDS_REVIEW"}:
        _fail(contract, "status must be SETUP_VERIFIED or NEEDS_REVIEW")
    _id(payload["run_id"], contract=contract, path="run_id")
    for key in ("setup_plan_sha256","audit_sha256","drawing_profile_sha256","template_file_sha256"):
        _sha(payload[key], contract=contract, path=key)
    blockers = payload["blockers"]
    if not isinstance(blockers, list):
        _fail(contract, "blockers must be a list")
    for index, blocker in enumerate(blockers):
        _validate_blocker(blocker, contract=contract, path=f"blockers[{index}]")
    if payload["status"] == "SETUP_VERIFIED" and blockers:
        _fail(contract, "SETUP_VERIFIED evidence cannot contain blockers")
    _string(payload["verified_by"], contract=contract, path="verified_by")
    _string(payload["approval_reference"], contract=contract, path="approval_reference")
    _validate_policy_evidence(payload, contract=contract)


_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "drawing_definition": _validate_definition,
    "drawing_profile": _validate_profile,
    "domain_pack": _validate_domain_pack,
    "template_manifest": _validate_template_manifest,
    "drawing_setup_plan": _validate_setup_plan,
    "drawing_setup_audit": _validate_audit,
    "drawing_setup_evidence": _validate_evidence,
}


def read_contract(path: Path, *, contract: str) -> dict[str, object]:
    """Read, validate, and return a Drawing Setup contract from JSON."""
    key = contract.replace("-", "_")
    validator = _VALIDATORS.get(key)
    if validator is None:
        raise DrawingContractError(f"unsupported contract kind: {contract}")
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrawingContractError(f"Cannot read {contract}: {source}") from exc
    if not isinstance(payload, dict):
        raise DrawingContractError(f"{contract}: root must be an object")
    validator(payload)
    return payload
