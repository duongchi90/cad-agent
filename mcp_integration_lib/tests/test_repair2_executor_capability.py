from __future__ import annotations

import math

import pytest

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib import repair2
from mcp_integration_lib.mcp_client import MCPTimeoutError, MCPToolError


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.next_handle = "NEW-001"
        self.failure: Exception | None = None

    def entity_erase(self, handle: str) -> None:
        self.calls.append(("entity_erase", (handle,), {}))
        if self.failure is not None:
            raise self.failure

    def entity_create_line(self, *args, **kwargs):
        self.calls.append(("entity_create_line", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return {"handle": self.next_handle}

    def entity_create_circle(self, *args, **kwargs):
        self.calls.append(("entity_create_circle", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return {"handle": self.next_handle}

    def entity_create_arc(self, *args, **kwargs):
        self.calls.append(("entity_create_arc", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return {"handle": self.next_handle}

    def annotation_create_text(self, *args, **kwargs):
        self.calls.append(("annotation_create_text", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return {"handle": self.next_handle}


def _call(client: RecordingClient, **kwargs):
    seam = getattr(repair2, "execute_supported_repair_capability", None)
    if not callable(seam):
        raise AssertionError("repair2 public capability seam is absent")
    return seam(client, **kwargs)


def _geometry(capability: str) -> dict[str, object]:
    return {
        "LINE": {"type": "line", "start": (0.0, 0.0), "end": (1.0, 2.0)},
        "CIRCLE": {"type": "circle", "center": (1.0, 2.0), "radius": 3.0},
        "ARC": {
            "type": "arc",
            "center": (1.0, 2.0),
            "radius": 3.0,
            "start_angle_deg": 0.0,
            "end_angle_deg": 90.0,
        },
        "TEXT": {
            "type": "text",
            "content": "label",
            "insert": (1.0, 2.0),
            "height": 2.5,
            "rotation_deg": 0.0,
        },
    }[capability]


def test_public_executor_capability_seam_is_exposed() -> None:
    assert callable(getattr(repair2, "execute_supported_repair_capability", None))


@pytest.mark.parametrize("capability", ["LINE", "CIRCLE", "ARC", "TEXT"])
def test_recreate_routes_each_supported_primitive_to_existing_mcp_method(capability: str) -> None:
    client = RecordingClient()

    new_handle = _call(
        client,
        capability=capability,
        target_handle="OLD-001",
        geometry=_geometry(capability),
        layer="REPAIR",
    )

    assert new_handle == "NEW-001"
    assert [call[0] for call in client.calls] == [
        "entity_erase",
        {
            "LINE": "entity_create_line",
            "CIRCLE": "entity_create_circle",
            "ARC": "entity_create_arc",
            "TEXT": "annotation_create_text",
        }[capability],
    ]


def test_erase_routes_only_to_entity_erase_and_returns_no_handle() -> None:
    client = RecordingClient()

    assert _call(client, capability="ERASE", target_handle="A1", geometry=None, layer=None) is None
    assert client.calls == [("entity_erase", ("A1",), {})]


def test_unsupported_capability_fails_before_any_client_call() -> None:
    client = RecordingClient()

    with pytest.raises(ValueError, match="UNSUPPORTED_REPAIR_OPERATION"):
        _call(client, capability="MOVE", target_handle=None, geometry=None, layer="L")
    assert client.calls == []


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "line", "start": (0.0, 0.0)},
        {"type": "line", "start": (0.0, 0.0), "end": (1.0, 2.0), "extra": 1},
        {"type": "circle", "center": (0.0, 0.0), "radius": 1.0, "path": "x"},
    ],
)
def test_unknown_missing_or_extra_geometry_fields_fail_before_mutation(geometry) -> None:
    client = RecordingClient()

    with pytest.raises(ValueError, match="REPAIR_GEOMETRY_INVALID"):
        _call(client, capability="LINE", target_handle=None, geometry=geometry, layer="L")
    assert client.calls == []


@pytest.mark.parametrize("bad_number", [True, math.nan, math.inf, -math.inf])
def test_bool_nan_and_inf_geometry_numbers_fail_before_mutation(bad_number) -> None:
    client = RecordingClient()
    geometry = {"type": "circle", "center": (0.0, 0.0), "radius": bad_number}

    with pytest.raises(ValueError, match="REPAIR_GEOMETRY_INVALID"):
        _call(client, capability="CIRCLE", target_handle=None, geometry=geometry, layer="L")
    assert client.calls == []


def test_hostile_string_subclasses_fail_at_capability_handle_and_layer_boundaries() -> None:
    class HostileString(str):
        def __eq__(self, other):
            return True

        def __hash__(self):
            return 0

    client = RecordingClient()
    for kwargs in (
        {"capability": HostileString("LINE"), "target_handle": None, "geometry": _geometry("LINE"), "layer": "L"},
        {"capability": "ERASE", "target_handle": HostileString("A1"), "geometry": None, "layer": None},
        {"capability": "LINE", "target_handle": None, "geometry": _geometry("LINE"), "layer": HostileString("L")},
    ):
        with pytest.raises(ValueError, match="REPAIR_(CAPABILITY|HANDLE|LAYER)_INVALID"):
            _call(client, **kwargs)
    assert client.calls == []


def test_callable_module_and_path_payloads_are_rejected_without_dispatch() -> None:
    client = RecordingClient()
    geometry = _geometry("LINE")
    geometry["callback"] = lambda: None

    with pytest.raises(ValueError, match="REPAIR_GEOMETRY_INVALID"):
        _call(client, capability="LINE", target_handle=None, geometry=geometry, layer="L")
    assert client.calls == []


def test_path_like_layer_payload_is_rejected_without_dispatch() -> None:
    client = RecordingClient()

    with pytest.raises(ValueError, match="REPAIR_LAYER_INVALID"):
        _call(client, capability="LINE", target_handle=None, geometry=_geometry("LINE"), layer="C:\\temp\\x")
    assert client.calls == []


@pytest.mark.parametrize("failure", [MCPTimeoutError("timeout"), MCPToolError("tool")])
def test_fake_client_failure_is_categorical_and_not_a_success(failure: Exception) -> None:
    client = RecordingClient()
    client.failure = failure

    with pytest.raises(MCPToolError, match="REPAIR_CAPABILITY_FAILED"):
        _call(
            client,
            capability="LINE",
            target_handle="OLD-001",
            geometry=_geometry("LINE"),
            layer="L",
        )
    assert client.calls == [("entity_erase", ("OLD-001",), {})]


def test_existing_repair_dxf_live_path_remains_available() -> None:
    assert callable(repair2.repair_dxf_live)
    assert not hasattr(repair2, "execute_repair_command")


@pytest.mark.parametrize("failure", [MCPTimeoutError("timeout"), MCPToolError("tool")])
def test_repair_dxf_live_fails_closed_when_erase_is_uncertain(failure: Exception) -> None:
    class EraseFailureClient(RecordingClient):
        def entity_erase(self, handle: str) -> None:
            self.calls.append(("entity_erase", (handle,), {}))
            raise failure

    build = BuildResult(output_path="fake.dxf", entity_count=1)
    build.handle_by_primitive_id = {"p": "OLD-001"}
    build.layer_by_primitive_id = {"p": "L"}
    build.written_geometry_by_primitive_id = {"p": _geometry("LINE")}
    client = EraseFailureClient()

    with pytest.raises(MCPToolError, match="REPAIR_CAPABILITY_FAILED"):
        repair2.repair_dxf_live(build, ["p: mismatch"], client)

    assert [call[0] for call in client.calls] == ["entity_erase"]
    assert build.handle_by_primitive_id["p"] == "OLD-001"
