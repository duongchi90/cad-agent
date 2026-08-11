"""Closed, data-only contract for executable repair-operation payloads.

This module deliberately does not execute CAD or own any approval, workspace,
revision, evidence, or publication state.  It only normalizes payloads that can
be routed to the already existing DXF primitive/component repair owners.
"""

from __future__ import annotations

import json
import math
import re
from typing import NamedTuple


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


class _Target(NamedTuple):
    target_handle: str | None
    layer: str | None


class _Geometry(NamedTuple):
    kind: str
    values: tuple[object, ...]


class _Parameters(NamedTuple):
    capability: str
    geometry: _Geometry


class RepairOperation(NamedTuple):
    """Immutable normalized operation routed to an existing executor owner."""

    schema_version: str
    operation: str
    target: _Target
    parameters: _Parameters
    preserve_anchors: tuple[str, ...]
    constraint_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        target = _record_target_dict(self.target)
        validated_target = _validate_target(target)
        target = {
            "target_handle": validated_target.target_handle,
            "layer": validated_target.layer,
        }
        parameters = _record_parameters_dict(self.parameters)
        parameters_root = _keys(parameters, {"capability", "geometry"}, "parameters")
        parameters = {
            "capability": _plain_string(parameters_root["capability"], "parameters.capability"),
            "geometry": _geometry_dict(
                _validate_geometry(parameters_root["capability"], parameters_root["geometry"])
            ),
        }
        if type(self.preserve_anchors) is not tuple or any(
            type(item) is not str for item in self.preserve_anchors
        ):
            _fail("preserve_anchors", "is invalid")
        if type(self.constraint_refs) is not tuple or any(
            type(item) is not str for item in self.constraint_refs
        ):
            _fail("constraint_refs", "is invalid")
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "target": target,
            "parameters": parameters,
            "preserve_anchors": list(self.preserve_anchors),
            "constraint_refs": list(self.constraint_refs),
        }

    def as_executor_payload(self) -> dict[str, object]:
        """Return fields that map directly to the accepted A2 executor."""
        canonical = normalize_repair_operation(self)
        return {
            "capability": canonical.parameters.capability,
            "target_handle": canonical.target.target_handle,
            "geometry": _geometry_dict(canonical.parameters.geometry),
            "layer": canonical.target.layer,
        }


def _geometry_dict(geometry: _Geometry) -> dict[str, object]:
    if type(geometry) is not _Geometry or type(geometry.values) is not tuple:
        _fail("parameters.geometry", "is invalid")
    capability = geometry.kind.upper() if type(geometry.kind) is str else None
    values = geometry.values
    if capability == "LINE" and len(values) == 2:
        start, end = values
        return {"type": "line", "start": list(start), "end": list(end)} if (
            type(start) is tuple and type(end) is tuple
        ) else _fail("parameters.geometry", "is invalid")
    if capability == "CIRCLE" and len(values) == 2:
        center, radius = values
        return {"type": "circle", "center": list(center), "radius": radius} if (
            type(center) is tuple
        ) else _fail("parameters.geometry", "is invalid")
    if capability == "ARC" and len(values) == 4:
        center, radius, start_angle, end_angle = values
        return {
            "type": "arc",
            "center": list(center),
            "radius": radius,
            "start_angle_deg": start_angle,
            "end_angle_deg": end_angle,
        } if type(center) is tuple else _fail("parameters.geometry", "is invalid")
    if capability == "TEXT" and len(values) == 4:
        content, insert, height, rotation = values
        return {
            "type": "text",
            "content": content,
            "insert": list(insert),
            "height": height,
            "rotation_deg": rotation,
        } if type(insert) is tuple else _fail("parameters.geometry", "is invalid")
    _fail("parameters.geometry", "is invalid")


def _record_target_dict(target: _Target) -> dict[str, object]:
    if type(target) is not _Target:
        _fail("target", "is invalid")
    handle, layer = target
    if handle is not None and type(handle) is not str:
        _fail("target.target_handle", "is invalid")
    if layer is not None and type(layer) is not str:
        _fail("target.layer", "is invalid")
    return {"target_handle": handle, "layer": layer}


def _record_parameters_dict(parameters: _Parameters) -> dict[str, object]:
    if type(parameters) is not _Parameters or type(parameters.capability) is not str:
        _fail("parameters", "is invalid")
    return {"capability": parameters.capability, "geometry": _geometry_dict(parameters.geometry)}


def _validate_target(target: object) -> _Target:
    target = _keys(target, {"target_handle", "layer"}, "target")
    handle = target["target_handle"]
    if handle is not None and (type(handle) is not str or _HANDLE_RE.fullmatch(handle) is None):
        _fail("target.target_handle", "is invalid")
    layer = target["layer"]
    if layer is not None and (type(layer) is not str or _LAYER_RE.fullmatch(layer) is None):
        _fail("target.layer", "is invalid")
    return _Target(handle, layer)


def _validate_geometry(capability: object, geometry: object) -> _Geometry:
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
        return _Geometry(
            "LINE",
            (
                _point(geometry["start"], "parameters.geometry.start"),
                _point(geometry["end"], "parameters.geometry.end"),
            ),
        )
    if capability == "CIRCLE":
        return _Geometry(
            "CIRCLE",
            (
                _point(geometry["center"], "parameters.geometry.center"),
                _number(geometry["radius"], "parameters.geometry.radius", positive=True),
            ),
        )
    if capability == "ARC":
        return _Geometry(
            "ARC",
            (
                _point(geometry["center"], "parameters.geometry.center"),
                _number(geometry["radius"], "parameters.geometry.radius", positive=True),
                _number(geometry["start_angle_deg"], "parameters.geometry.start_angle_deg"),
                _number(geometry["end_angle_deg"], "parameters.geometry.end_angle_deg"),
            ),
        )
    return _Geometry(
        "TEXT",
        (
            _plain_string(geometry["content"], "parameters.geometry.content"),
            _point(geometry["insert"], "parameters.geometry.insert"),
            _number(geometry["height"], "parameters.geometry.height", positive=True),
            _number(geometry["rotation_deg"], "parameters.geometry.rotation_deg"),
        ),
    )


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
    return RepairOperation(
        schema_version=REPAIR_OPERATION_SCHEMA_VERSION,
        operation=operation,
        target=target,
        parameters=_Parameters(parameters["capability"], parameters["geometry"]),
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
