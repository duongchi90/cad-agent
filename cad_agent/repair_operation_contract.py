"""Closed, data-only contract for executable repair-operation payloads.

This module deliberately does not execute CAD or own any approval, workspace,
revision, evidence, or publication state.  It only normalizes payloads that can
be routed to the already existing DXF primitive/component repair owners.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


REPAIR_OPERATION_SCHEMA_VERSION = "repair-operation-1.0"
SUPPORTED_OPERATION_KINDS = frozenset({"REPAIR_DXF_PRIMITIVE", "REPAIR_DXF_COMPONENT"})
_PRIMITIVE_TYPES = frozenset({"LINE", "CIRCLE", "ARC", "TEXT"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class RepairOperationContractError(ValueError):
    """Raised for malformed, unsupported, or unsafe repair-operation data."""


def _fail(path: str, reason: str) -> None:
    raise RepairOperationContractError(f"repair-operation-1.0: {path} {reason}")


def _plain_string(value: object, path: str, *, identifier: bool = False) -> str:
    if type(value) is not str or not value:
        _fail(path, "must be an exact non-empty string")
    if identifier and _ID_RE.fullmatch(value) is None:
        _fail(path, "has an invalid identifier")
    return value


def _number(value: object, path: str, *, positive: bool = False) -> int | float:
    if type(value) not in (int, float):
        _fail(path, "must be a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(path, "must be a finite number")
    if positive and value <= 0:
        _fail(path, "must be positive")
    return value


def _keys(value: object, required: set[str], path: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(path, "must be a closed object")
    if any(type(key) is not str for key in value):
        _fail(path, "contains a non-string property key")
    actual = set(value)
    missing = required - actual
    extra = actual - required
    if missing:
        _fail(path, "is missing a required property")
    if extra:
        _fail(path, "contains an unsupported property")
    return value


def _point(value: object, path: str, *, dimensions: int = 2) -> tuple[int | float, ...]:
    if type(value) is not list or len(value) != dimensions:
        _fail(path, f"must contain exactly {dimensions} coordinates")
    return tuple(_number(item, f"{path}[{index}]") for index, item in enumerate(value))


def _string_list(value: object, path: str) -> tuple[str, ...]:
    if type(value) is not list:
        _fail(path, "must be a list")
    return tuple(_plain_string(item, f"{path}[{index}]", identifier=True) for index, item in enumerate(value))


def _freeze(value: object, path: str) -> object:
    """Freeze an already validated value without retaining caller containers."""
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item, f"{path}.{key}") for key, item in value.items()})
    if type(value) in (list, tuple):
        return tuple(_freeze(item, f"{path}[]") for item in value)
    if type(value) in (str, int, float, bool) or value is None:
        return value
    _fail(path, "contains an unsupported value")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class RepairOperation:
    """Immutable normalized operation routed to an existing executor owner."""

    schema_version: str
    operation: str
    target: Mapping[str, object]
    parameters: Mapping[str, object]
    preserve_anchors: tuple[str, ...]
    constraint_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "target": _thaw(self.target),
            "parameters": _thaw(self.parameters),
            "preserve_anchors": list(self.preserve_anchors),
            "constraint_refs": list(self.constraint_refs),
        }


def _validate_primitive_parameters(parameters: dict[str, object]) -> dict[str, object]:
    entity_type = _plain_string(parameters.get("entity_type"), "parameters.entity_type")
    if entity_type not in _PRIMITIVE_TYPES:
        _fail("parameters.entity_type", "is unsupported")
    required: dict[str, set[str]] = {
        "LINE": {"entity_type", "start", "end"},
        "CIRCLE": {"entity_type", "center", "radius"},
        "ARC": {"entity_type", "center", "radius", "start_angle_deg", "end_angle_deg"},
        "TEXT": {"entity_type", "content", "insert", "height", "rotation_deg"},
    }
    parameters = _keys(parameters, required[entity_type], "parameters")
    if entity_type == "LINE":
        parameters["start"] = _point(parameters["start"], "parameters.start")
        parameters["end"] = _point(parameters["end"], "parameters.end")
    elif entity_type == "CIRCLE":
        parameters["center"] = _point(parameters["center"], "parameters.center")
        parameters["radius"] = _number(parameters["radius"], "parameters.radius", positive=True)
    elif entity_type == "ARC":
        parameters["center"] = _point(parameters["center"], "parameters.center")
        parameters["radius"] = _number(parameters["radius"], "parameters.radius", positive=True)
        parameters["start_angle_deg"] = _number(parameters["start_angle_deg"], "parameters.start_angle_deg")
        parameters["end_angle_deg"] = _number(parameters["end_angle_deg"], "parameters.end_angle_deg")
    else:
        parameters["content"] = _plain_string(parameters["content"], "parameters.content")
        parameters["insert"] = _point(parameters["insert"], "parameters.insert")
        parameters["height"] = _number(parameters["height"], "parameters.height", positive=True)
        parameters["rotation_deg"] = _number(parameters["rotation_deg"], "parameters.rotation_deg")
    return parameters


def _validate_component_parameters(parameters: dict[str, object]) -> dict[str, object]:
    parameters = _keys(
        parameters,
        {"block_name", "insert", "scale", "rotation_deg", "attributes"},
        "parameters",
    )
    _plain_string(parameters["block_name"], "parameters.block_name", identifier=True)
    parameters["insert"] = _point(parameters["insert"], "parameters.insert", dimensions=3)
    scale = _point(parameters["scale"], "parameters.scale", dimensions=3)
    if any(item <= 0 for item in scale):
        _fail("parameters.scale", "must contain positive values")
    parameters["scale"] = scale
    parameters["rotation_deg"] = _number(parameters["rotation_deg"], "parameters.rotation_deg")
    attributes = parameters["attributes"]
    if type(attributes) is not dict or any(type(key) is not str for key in attributes):
        _fail("parameters.attributes", "must be a closed string-keyed object")
    for key, value in attributes.items():
        _plain_string(key, "parameters.attributes key", identifier=True)
        _plain_string(value, "parameters.attributes value")
    return parameters


def normalize_repair_operation(payload: object) -> RepairOperation:
    if isinstance(payload, RepairOperation):
        return payload
    root = _keys(
        payload,
        {"schema_version", "operation", "target", "parameters", "preserve_anchors", "constraint_refs"},
        "operation",
    )
    if type(root["schema_version"]) is not str or root["schema_version"] != REPAIR_OPERATION_SCHEMA_VERSION:
        _fail("schema_version", "is unsupported")
    operation = _plain_string(root["operation"], "operation")
    if operation not in SUPPORTED_OPERATION_KINDS:
        _fail("operation", "is unsupported")
    target = _keys(root["target"], {"stable_entity_id", "feature"}, "target")
    target = {
        "stable_entity_id": _plain_string(target["stable_entity_id"], "target.stable_entity_id", identifier=True),
        "feature": _plain_string(target["feature"], "target.feature", identifier=True),
    }
    if type(root["parameters"]) is not dict:
        _fail("parameters", "must be a closed object")
    # Validate operation-specific keys on a mutable local copy; the caller's
    # containers are never retained by the normalized record.
    parameters = dict(root["parameters"])
    if operation == "REPAIR_DXF_PRIMITIVE":
        parameters = _validate_primitive_parameters(parameters)
    else:
        parameters = _validate_component_parameters(parameters)
    preserve_anchors = _string_list(root["preserve_anchors"], "preserve_anchors")
    constraint_refs = _string_list(root["constraint_refs"], "constraint_refs")
    frozen_target = _freeze(target, "target")
    frozen_parameters = _freeze(parameters, "parameters")
    return RepairOperation(
        schema_version=REPAIR_OPERATION_SCHEMA_VERSION,
        operation=operation,
        target=frozen_target,
        parameters=frozen_parameters,
        preserve_anchors=preserve_anchors,
        constraint_refs=constraint_refs,
    )


def validate_repair_operation(payload: object) -> None:
    """Validate a payload without exposing a second schema/authority owner."""
    normalize_repair_operation(payload)


def canonicalize_repair_operation(payload: object) -> str:
    normalized = normalize_repair_operation(payload)
    return json.dumps(normalized.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


__all__ = [
    "REPAIR_OPERATION_SCHEMA_VERSION",
    "SUPPORTED_OPERATION_KINDS",
    "RepairOperation",
    "RepairOperationContractError",
    "canonicalize_repair_operation",
    "normalize_repair_operation",
    "validate_repair_operation",
]
