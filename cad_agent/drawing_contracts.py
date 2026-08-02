"""Strict Drawing Setup contracts and canonical hashing.

This module is intentionally pure Python.  It validates the boundary consumed by
the later setup-plan, AutoCAD, and release-gate tasks without adding jsonschema
or any other runtime dependency.
"""

from __future__ import annotations

import hashlib
import json
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


class DrawingContractError(ValueError):
    """Raised when a Drawing Setup contract is absent, malformed, or unapproved."""


def canonical_json_sha256(payload: Mapping[str, object]) -> str:
    """Return SHA-256 for the canonical UTF-8 JSON representation of a mapping."""
    if not isinstance(payload, Mapping):
        raise TypeError("canonical JSON hashing requires a mapping")
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


def _common(payload: dict[str, Any], *, contract: str, version: str, required: set[str]) -> None:
    if "schema_version" not in payload:
        _fail(contract, "missing required properties: schema_version")
    if required != {"schema_version"}:
        _keys(payload, contract=contract, required=required)
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


def _validate_expectations(value: object, *, contract: str) -> None:
    item = _object(value, contract=contract, path="setup_expectations")
    _keys(item, contract=contract, required=_EXPECTATION_KEYS)
    variables = _object(item["variables"], contract=contract, path="setup_expectations.variables")
    _keys(variables, contract=contract, required=_VARIABLES)
    for key in _VARIABLES:
        _number(variables[key], contract=contract, path=f"setup_expectations.variables.{key}")
    _string(item["current_layer"], contract=contract, path="setup_expectations.current_layer")
    layers = item["required_layers"]
    if not isinstance(layers, list) or not layers:
        _fail(contract, "setup_expectations.required_layers must be non-empty")
    for index, layer in enumerate(layers):
        _validate_layer(layer, contract=contract, path=f"setup_expectations.required_layers[{index}]")
    styles = _object(item["required_styles"], contract=contract, path="setup_expectations.required_styles")
    _keys(styles, contract=contract, required={"text","dimension","mleader","table"})
    for key in ("text","dimension","mleader","table"):
        _strings(styles[key], contract=contract, path=f"setup_expectations.required_styles.{key}")
    layouts = item["layouts"]
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
        for scale in layout_item["viewport_scales"]:
            number = _number(scale, contract=contract, path=f"setup_expectations.layouts[{index}].viewport_scales")
            if number <= 0:
                _fail(contract, "viewport scales must be positive")
        _bool(layout_item["locked"], contract=contract, path=f"setup_expectations.layouts[{index}].locked")
    font = _object(item["font_policy"], contract=contract, path="setup_expectations.font_policy")
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
        elif key in {"id","revision"}:
            _string(item[key], contract=contract, path=f"{path}.{key}")


def _validate_setup_plan(payload: dict[str, Any]) -> None:
    contract = "drawing_setup_plan"
    required = {"schema_version","run_id","state","definition","drawing_profile","domain_pack","template","setup_expectations"}
    _common(payload, contract=contract, version="drawing-setup-plan-1.0", required=required)
    _string(payload["run_id"], contract=contract, path="run_id")
    if payload["state"] != "SETUP_PENDING":
        _fail(contract, "state must be SETUP_PENDING")
    _validate_ref(payload["definition"], contract=contract, path="definition", fields={"id","sha256"})
    _validate_ref(payload["drawing_profile"], contract=contract, path="drawing_profile", fields={"id","revision","sha256"})
    _validate_ref(payload["domain_pack"], contract=contract, path="domain_pack", fields={"id","revision","sha256"})
    _validate_ref(payload["template"], contract=contract, path="template", fields={"id","revision","file_sha256","embedded_settings_sha256"})
    _validate_expectations(payload["setup_expectations"], contract=contract)


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
    for key in ("text","dimension","mleader","table"):
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


def _validate_evidence(payload: dict[str, Any]) -> None:
    contract = "drawing_setup_evidence"
    required = {"schema_version","status","run_id","setup_plan_sha256","audit_sha256","drawing_profile_sha256","template_file_sha256","blockers","verified_by","approval_reference"}
    _common(payload, contract=contract, version="drawing-setup-evidence-1.0", required={"schema_version"})
    _keys(payload, contract=contract, required=required)
    if payload["status"] not in {"SETUP_VERIFIED","NEEDS_REVIEW"}:
        _fail(contract, "status must be SETUP_VERIFIED or NEEDS_REVIEW")
    _string(payload["run_id"], contract=contract, path="run_id")
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
