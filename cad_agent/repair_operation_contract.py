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
SUPPORTED_OPERATION_KINDS = frozenset({"REPAIR_DXF_PRIMITIVE"})
_PRIMITIVE_TYPES = frozenset({"LINE", "CIRCLE", "ARC", "TEXT"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_LAYER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


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


@dataclass(frozen=True, slots=True)
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

    def as_executor_payload(self) -> dict[str, object]:
        """Return fields that map directly to the accepted A2 executor."""
        return {
            "capability": self.parameters["capability"],
            "target_handle": self.target["target_handle"],
            "geometry": _thaw(self.parameters["geometry"]),
            "layer": self.target["layer"],
        }


def _validate_target(target: object) -> dict[str, object]:
    target = _keys(target, {"target_handle", "layer"}, "target")
    handle = target["target_handle"]
    if handle is not None and (type(handle) is not str or _HANDLE_RE.fullmatch(handle) is None):
        _fail("target.target_handle", "is invalid")
    layer = target["layer"]
    if layer is not None and (type(layer) is not str or _LAYER_RE.fullmatch(layer) is None):
        _fail("target.layer", "is invalid")
    return {"target_handle": handle, "layer": layer}


def _validate_geometry(capability: object, geometry: object) -> dict[str, object]:
    capability = _plain_string(capability, "parameters.capability")
    if capability not in _PRIMITIVE_TYPES:
        _fail("parameters.capability", "is unsupported")
    if type(geometry) is not dict:
        _fail("parameters.geometry", "must be a closed object")
    expected_fields: dict[str, set[str]] = {
        "LINE": {"type", "start", "end"},
        "CIRCLE": {"type", "center", "radius"},
        "ARC": {"type", "center", "radius", "start_angle_deg", "end_angle_deg"},
        "TEXT": {"type", "content", "insert", "height", "rotation_deg"},
    }
    geometry = _keys(geometry, expected_fields[capability], "parameters.geometry")
    expected_type = capability.lower()
    if type(geometry["type"]) is not str or geometry["type"] != expected_type:
        _fail("parameters.geometry.type", "does not match capability")
    if capability == "LINE":
        return {
            "type": "line",
            "start": _point(geometry["start"], "parameters.geometry.start"),
            "end": _point(geometry["end"], "parameters.geometry.end"),
        }
    if capability == "CIRCLE":
        return {
            "type": "circle",
            "center": _point(geometry["center"], "parameters.geometry.center"),
            "radius": _number(geometry["radius"], "parameters.geometry.radius", positive=True),
        }
    if capability == "ARC":
        return {
            "type": "arc",
            "center": _point(geometry["center"], "parameters.geometry.center"),
            "radius": _number(geometry["radius"], "parameters.geometry.radius", positive=True),
            "start_angle_deg": _number(
                geometry["start_angle_deg"], "parameters.geometry.start_angle_deg"
            ),
            "end_angle_deg": _number(
                geometry["end_angle_deg"], "parameters.geometry.end_angle_deg"
            ),
        }
    return {
        "type": "text",
        "content": _plain_string(geometry["content"], "parameters.geometry.content"),
        "insert": _point(geometry["insert"], "parameters.geometry.insert"),
        "height": _number(geometry["height"], "parameters.geometry.height", positive=True),
        "rotation_deg": _number(geometry["rotation_deg"], "parameters.geometry.rotation_deg"),
    }


def normalize_repair_operation(payload: object) -> RepairOperation:
    if type(payload) is RepairOperation:
        try:
            # Reconstruct from the public record and run the same closed
            # validator; never trust a caller-constructed or mutated instance.
            payload = payload.as_dict()
        except Exception:
            _fail("operation", "is invalid")
    elif isinstance(payload, RepairOperation):
        _fail("operation", "is invalid")
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
    target = _validate_target(root["target"])
    parameters_root = _keys(root["parameters"], {"capability", "geometry"}, "parameters")
    parameters = {
        "capability": _plain_string(parameters_root["capability"], "parameters.capability"),
        "geometry": _validate_geometry(
            parameters_root["capability"], parameters_root["geometry"]
        ),
    }
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
