from __future__ import annotations

import copy
import importlib
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp_integration_lib import dotnet_ipc
from mcp_integration_lib.dotnet_ipc import (
    DEFAULT_IPC_DIR,
    REQUEST_PREFIX,
    RESULT_PREFIX,
    DotNetIPCClient,
    DotNetIPCProtocolError,
    DotNetIPCResultError,
    DotNetIPCTimeoutError,
    atomic_write_json,
    cleanup_request_files,
    get_ipc_dir,
    normalize_request_id,
    normalize_windows_absolute_path,
    request_filename,
    request_path,
    result_filename,
    result_path,
)


class RecordingUser32:
    def __init__(self) -> None:
        self.class_names: dict[int, str] = {}
        self.enum_calls: list[tuple[int, int]] = []
        self.post_calls: list[tuple[int, int, int, int]] = []

    def EnumChildWindows(self, hwnd, callback, lparam):
        self.enum_calls.append((hwnd, lparam))
        for child, class_name in ((101, "Palette"), (202, "MDIClient"), (303, "Other")):
            self.class_names[child] = class_name
            if not callback(child, lparam):
                break

    def GetClassNameW(self, child, buffer, _length):
        buffer.value = self.class_names[child]
        return len(buffer.value)

    def PostMessageW(self, target, message, wparam, lparam):
        self.post_calls.append((target, message, wparam, lparam))
        return True


class WindowsDotNetTriggerTests(unittest.TestCase):
    def test_rejects_non_positive_or_non_integer_window_handles(self) -> None:
        user32 = RecordingUser32()
        factory = getattr(dotnet_ipc, "make_windows_dotnet_dispatch_trigger", None)
        self.assertTrue(callable(factory))

        with patch.object(dotnet_ipc, "_get_user32", return_value=user32, create=True) as get_user32:
            for hwnd in (0, -1, None, "123", 1.5, True):
                with self.subTest(hwnd=hwnd):
                    with self.assertRaises(ValueError):
                        factory(hwnd)

        get_user32.assert_not_called()

    def test_posts_exact_dispatch_message_sequence_to_mdi_child(self) -> None:
        user32 = RecordingUser32()
        factory = getattr(dotnet_ipc, "make_windows_dotnet_dispatch_trigger", None)
        self.assertTrue(callable(factory))

        with patch.object(dotnet_ipc, "_get_user32", return_value=user32, create=True):
            trigger = factory(9001)
            trigger()

        command = "\x1b\x1bCADAGENT_DISPATCH\r"
        self.assertEqual([(9001, 0)], user32.enum_calls)
        self.assertEqual(
            [(202, 0x0102, ord(character), 0) for character in command],
            user32.post_calls,
        )


def _result(request: dict[str, object], payload: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "request_id": request["request_id"],
        "success": True,
        "operation": request["operation"],
        "drawing_full_path": request["drawing_full_path"],
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [],
        "started_at": "2026-08-01T00:00:00Z",
        "completed_at": "2026-08-01T00:00:00Z",
        "payload": payload or {},
    }


def _exact_base_fixture() -> dict[str, object]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "exact-base-xref-inspection.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _exact_base_extraction_result_payload() -> dict[str, object]:
    return {
        "accepted_target_overwrite": False,
        "candidate_changed_during_operation": True,
        "candidate_input_path": r"C:\temp\candidate-input.dwg",
        "candidate_input_sha256": "b" * 64,
        "candidate_output_path": r"C:\temp\candidate-output.dwg",
        "candidate_output_sha256": "c" * 64,
        "components": [
            {
                "candidate_handle": "E001",
                "logical_component_id": "chassis-main",
                "provenance": "REUSED_FROM_BASE_CAD",
                "source_block": "CHASSIS_MAIN",
                "source_handle": "A1B2",
                "source_layer": "BODY",
                "source_revision": "rev-2026-08-05-01",
                "source_sha256": "a" * 64,
                "transform": {
                    "rotation_degrees": 0.0,
                    "translation": {"x": 10.0, "y": 20.0, "z": 0.0},
                    "uniform_scale": 1.0,
                },
            },
            {
                "candidate_handle": "E002",
                "logical_component_id": "cabin-main",
                "provenance": "REUSED_FROM_BASE_CAD",
                "source_block": "CABIN_MAIN",
                "source_handle": "C3D4",
                "source_layer": "BODY",
                "source_revision": "rev-2026-08-05-01",
                "source_sha256": "a" * 64,
                "transform": {
                    "rotation_degrees": 2.5,
                    "translation": {"x": 0.0, "y": 0.0, "z": 5.0},
                    "uniform_scale": 1.0,
                },
            },
        ],
        "live_preflight": {
            "dbmod_after": 0,
            "dbmod_before": 0,
            "eligible": True,
            "evidence_sha256": "d" * 64,
            "inspection_id": "inspection-002",
            "source_sha256": "a" * 64,
            "target_drawing_sha256": "b" * 64,
            "xref": {"name": "BASE_XREF", "read_only": True, "status": "INSPECTED"},
        },
        "plan_id": "extraction-plan-001",
        "request_id": "xref-request-001",
        "run_id": "run-001",
        "save_performed": True,
        "schema_version": "exact-base-xref-extraction-result-1.0",
        "source_handle_to_candidate_handle": [
            {"source_handle": "A1B2", "candidate_handle": "E001"},
            {"source_handle": "C3D4", "candidate_handle": "E002"},
        ],
        "source_mutated": False,
        "source_revision": "rev-2026-08-05-01",
        "source_saved": False,
        "source_sha256_after": "a" * 64,
        "source_sha256_before": "a" * 64,
        "warnings": [],
    }


def _exact_result(
    request: dict[str, object],
    payload: dict[str, object],
    *,
    changed: bool,
    entity_handles: list[str],
) -> dict[str, object]:
    result = _result(request, payload)
    result["changed"] = changed
    result["entity_handles"] = entity_handles
    return result


def _nested_mapping_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for nested in value.values()
            for key in _nested_mapping_keys(nested)
        }
    if isinstance(value, list):
        return {key for nested in value for key in _nested_mapping_keys(nested)}
    return set()


class FakeDispatcher:
    def __init__(self, ipc_dir: Path, payload: dict[str, object] | None = None) -> None:
        self.ipc_dir = ipc_dir
        self.payload = payload or {}
        self.requests: list[dict[str, object]] = []
        self.request_bytes = b""

    def __call__(self) -> None:
        request_files = list(self.ipc_dir.glob("cadagent_dotnet_request_*.json"))
        self.assert_one_request(request_files)
        self.request_bytes = request_files[0].read_bytes()
        request = json.loads(self.request_bytes.decode("utf-8"))
        self.requests.append(request)
        atomic_write_json(
            result_path(self.ipc_dir, str(request["request_id"])),
            _result(request, self.payload),
        )

    @staticmethod
    def assert_one_request(request_files: list[Path]) -> None:
        if len(request_files) != 1:
            raise AssertionError(f"expected one request file, got {request_files!r}")


class DotNetIPCClientTests(unittest.TestCase):
    def test_request_preserves_utf8_and_request_id(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir, {"message": "Đường kính Ω"})
            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=dispatcher,
                request_id_factory=lambda: "health-20260801-001",
            )

            result = client.request(
                "health",
                approval={"note": "Kiểm tra Ω"},
            )

            self.assertEqual("health-20260801-001", result["request_id"])
            self.assertEqual("Kiểm tra Ω", dispatcher.requests[0]["approval"]["note"])
            self.assertIn("Kiểm tra Ω".encode("utf-8"), dispatcher.request_bytes)
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))

    def test_exact_base_xref_inspection_sends_only_validated_expectations(self) -> None:
        fixture = _exact_base_fixture()
        inspection = fixture["inspection"]
        requests: list[dict[str, object]] = []

        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                requests.append(request)
                atomic_write_json(
                    result_path(ipc_dir, str(request["request_id"])),
                    _exact_result(
                        request,
                        copy.deepcopy(inspection),
                        changed=False,
                        entity_handles=[],
                    ),
                )

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)
            result = client.exact_base_xref_inspection(
                r"C:\temp\inspection-host.dwg",
                drawing_sha256="b" * 64,
                source_full_path=r"C:\approved\base-vehicle.dwg",
                inspection=inspection,
                request_id="xref-request-001",
            )

        request = requests[0]
        parameters = request["parameters"]
        self.assertEqual(
            {
                "run_id",
                "source_full_path",
                "source_revision",
                "inspection_expectations",
                "target_role",
            },
            set(parameters),
        )
        self.assertEqual("INSPECTION_HOST", parameters["target_role"])
        self.assertIsNone(request["approval"])
        self.assertEqual(
            "rev-2026-08-05-01",
            parameters["inspection_expectations"]["source"]["revision"],
        )
        self.assertNotIn(
            "observed",
            _nested_mapping_keys(parameters["inspection_expectations"]),
        )
        self.assertFalse(
            {
                "status",
                "eligible",
                "changed",
                "dbmod_before",
                "dbmod_after",
                "live_bounds",
                "live_hashes",
                "live_timestamps",
            }
            & _nested_mapping_keys(parameters["inspection_expectations"])
        )
        self.assertFalse(result["changed"])
        self.assertEqual([], result["entity_handles"])

    def test_exact_base_xref_extraction_validates_plan_and_binds_approval(self) -> None:
        fixture = _exact_base_fixture()
        inspection = fixture["inspection"]
        plan = copy.deepcopy(fixture["plan"])
        plan["approval"] = {"reference": "approval-001", "status": "APPROVED"}
        requests: list[dict[str, object]] = []

        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                requests.append(request)
                atomic_write_json(
                    result_path(ipc_dir, str(request["request_id"])),
                    _exact_result(
                        request,
                        _exact_base_extraction_result_payload(),
                        changed=True,
                        entity_handles=["E001", "E002"],
                    ),
                )

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)
            result = client.exact_base_xref_extraction(
                r"C:\temp\candidate-input.dwg",
                drawing_sha256="b" * 64,
                source_full_path=r"C:\approved\base-vehicle.dwg",
                inspection=inspection,
                extraction_plan=plan,
                candidate_output_path=r"C:\temp\candidate-output.dwg",
                approval=plan["approval"],
                request_id="xref-request-001",
            )

        request = requests[0]
        parameters = request["parameters"]
        self.assertEqual(
            {
                "run_id",
                "source_full_path",
                "source_revision",
                "inspection_expectations",
                "extraction_plan",
                "target_role",
                "candidate_output_path",
            },
            set(parameters),
        )
        self.assertEqual(plan["approval"], request["approval"])
        self.assertEqual("APPROVED", request["approval"]["status"])
        self.assertEqual("DISPOSABLE_CANDIDATE", parameters["target_role"])
        self.assertEqual(plan, parameters["extraction_plan"])
        self.assertNotIn(
            "eligible",
            _nested_mapping_keys(parameters["inspection_expectations"]),
        )
        self.assertTrue(result["changed"])
        self.assertEqual(["E001", "E002"], result["entity_handles"])
        self.assertFalse(result["payload"]["source_mutated"])
        self.assertFalse(result["payload"]["accepted_target_overwrite"])
        self.assertEqual(
            2,
            len(result["payload"]["source_handle_to_candidate_handle"]),
        )

    def test_exact_base_xref_rejects_invalid_offline_inputs_before_transport(self) -> None:
        fixture = _exact_base_fixture()
        inspection = fixture["inspection"]
        plan = copy.deepcopy(fixture["plan"])
        plan["approval"] = {"reference": "approval-001", "status": "APPROVED"}
        trigger_calls = 0

        with TemporaryDirectory() as temporary:

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)
            common = {
                "drawing_full_path": r"C:\temp\candidate-input.dwg",
                "drawing_sha256": "b" * 64,
                "source_full_path": r"C:\approved\base-vehicle.dwg",
                "inspection": inspection,
                "extraction_plan": plan,
                "candidate_output_path": r"C:\temp\candidate-output.dwg",
                "approval": plan["approval"],
            }
            uninspected_plan = copy.deepcopy(plan)
            uninspected_plan["components"][0]["logical_component_id"] = "not-inspected"
            cases = [
                {
                    "source_full_path": "approved/base-vehicle.dwg",
                    "message": "absolute Windows path",
                },
                {"drawing_sha256": "B" * 64, "message": "lowercase"},
                {
                    "source_revision": "wrong-revision",
                    "message": "source revision",
                },
                {
                    "source_full_path": r"C:\temp\candidate-input.dwg",
                    "message": "source path",
                },
                {
                    "candidate_output_path": r"C:\approved\base-vehicle.dwg",
                    "message": "candidate output",
                },
                {
                    "approval": {"reference": "other", "status": "APPROVED"},
                    "message": "approval",
                },
                {
                    "extraction_plan": uninspected_plan,
                    "message": "uninspected component",
                },
            ]
            for case in cases:
                with self.subTest(message=case["message"]):
                    kwargs = dict(common)
                    kwargs.update({key: value for key, value in case.items() if key != "message"})
                    with self.assertRaises(ValueError):
                        client.exact_base_xref_extraction(**kwargs)

        self.assertEqual(0, trigger_calls)

    def test_exact_base_xref_rejects_live_owned_offline_evidence(self) -> None:
        fixture = _exact_base_fixture()
        inspection = copy.deepcopy(fixture["inspection"])
        inspection["components"][0]["observed"] = True
        trigger_calls = 0

        with TemporaryDirectory() as temporary:

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)
            with self.assertRaises(ValueError):
                client.exact_base_xref_inspection(
                    r"C:\temp\inspection-host.dwg",
                    drawing_sha256="b" * 64,
                    source_full_path=r"C:\approved\base-vehicle.dwg",
                    inspection=inspection,
                )

        self.assertEqual(0, trigger_calls)

    def test_exact_base_xref_rejects_mutated_extraction_evidence(self) -> None:
        fixture = _exact_base_fixture()
        plan = copy.deepcopy(fixture["plan"])
        plan["approval"] = {"reference": "approval-001", "status": "APPROVED"}
        payload = _exact_base_extraction_result_payload()
        payload["source_mutated"] = True

        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                atomic_write_json(
                    result_path(ipc_dir, str(request["request_id"])),
                    _exact_result(request, payload, changed=True, entity_handles=["E001", "E002"]),
                )

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)
            with self.assertRaises(DotNetIPCProtocolError):
                client.exact_base_xref_extraction(
                    r"C:\temp\candidate-input.dwg",
                    drawing_sha256="b" * 64,
                    source_full_path=r"C:\approved\base-vehicle.dwg",
                    inspection=fixture["inspection"],
                    extraction_plan=plan,
                    candidate_output_path=r"C:\temp\candidate-output.dwg",
                    approval=plan["approval"],
                    request_id="xref-request-001",
                )

    def test_health_allows_null_drawing_path(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            client.health()

            self.assertEqual("health", dispatcher.requests[0]["operation"])
            self.assertIsNone(dispatcher.requests[0]["drawing_full_path"])
            self.assertEqual({}, dispatcher.requests[0]["parameters"])

    def test_review_sends_handles_and_normalized_path(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            dispatcher = FakeDispatcher(ipc_dir)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            client.review(r"C:/drawings/parts/../sample.dwg", ["10", "A0"])

            request = dispatcher.requests[0]
            self.assertEqual("review", request["operation"])
            self.assertEqual(r"C:\drawings\sample.dwg", request["drawing_full_path"])
            self.assertEqual({"handles": ["10", "A0"]}, request["parameters"])

    def test_mechanical_bom_sends_empty_parameters_and_preserves_payload(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            payload = {
                "component_count": 1,
                "components": [
                    {
                        "handle": "2F",
                        "block_name": "COMP_FRAME",
                        "attributes": [{"tag": "PART_ID", "value": "FRAME-001"}],
                    }
                ],
            }
            dispatcher = FakeDispatcher(ipc_dir, payload)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            result = client.mechanical_bom(r"C:\temp\bom.dxf", request_id="bom-001")

            self.assertEqual("mechanical_bom", dispatcher.requests[0]["operation"])
            self.assertEqual({}, dispatcher.requests[0]["parameters"])
            self.assertEqual(payload, result["payload"])

    def test_mechanical_bom_rejects_unsupported_parameters_before_trigger(self) -> None:
        with TemporaryDirectory() as temporary:
            trigger_calls = 0

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)

            with self.assertRaisesRegex(ValueError, "mechanical_bom parameters"):
                client.request(
                    "mechanical_bom",
                    r"C:\temp\bom.dxf",
                    parameters={"filter": "COMP_FRAME"},
                )

            self.assertEqual(0, trigger_calls)

    def test_drawing_setup_audit_uses_empty_parameters_and_preserves_hash(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            payload = {"dbmod_before": 0, "dbmod_after": 0, "changed": False}
            dispatcher = FakeDispatcher(ipc_dir, payload)
            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher)

            result = client.drawing_setup_audit(
                r"C:\temp\setup-lite.dwg",
                drawing_sha256="a" * 64,
                request_id="setup-lite-001",
            )

            request = dispatcher.requests[0]
            self.assertEqual("drawing_setup_audit", request["operation"])
            self.assertEqual({}, request["parameters"])
            self.assertEqual("a" * 64, request["drawing_sha256"])
            self.assertFalse(result["changed"])
            self.assertEqual(payload, result["payload"])

    def test_drawing_setup_audit_rejects_a_mutating_result(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                result = _result(request)
                result["changed"] = True
                result["entity_handles"] = ["2F"]
                atomic_write_json(result_path(ipc_dir, str(request["request_id"])), result)

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)

            with self.assertRaisesRegex(DotNetIPCProtocolError, "read-only"):
                client.drawing_setup_audit(
                    r"C:\temp\setup-lite.dwg",
                    drawing_sha256="a" * 64,
                )

    def test_close_disposable_rejects_unsafe_flags_before_trigger(self) -> None:
        with TemporaryDirectory() as temporary:
            trigger_calls = 0

            def trigger() -> None:
                nonlocal trigger_calls
                trigger_calls += 1

            client = DotNetIPCClient(ipc_dir=temporary, trigger=trigger)
            for kwargs in ({"disposable": False}, {"save_changes": True}):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        client.close_disposable(r"C:\temp\sample.dwg", **kwargs)

            self.assertEqual(0, trigger_calls)

    def test_timeout_is_bounded_and_cleans_only_this_request(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            old_file = ipc_dir / "autocad_mcp_result_legacy.json"
            old_file.write_text("legacy", encoding="utf-8")
            request_id = "timeout-001"
            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=lambda: None,
                timeout_s=0.05,
                poll_interval_s=0.01,
                request_id_factory=lambda: request_id,
            )

            started = time.monotonic()
            with self.assertRaises(DotNetIPCTimeoutError):
                client.health()
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertFalse(request_path(ipc_dir, request_id).exists())
            self.assertFalse(result_path(ipc_dir, request_id).exists())
            self.assertTrue(old_file.exists())

    def test_non_success_result_raises_and_cleans_request(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                failed = _result(request)
                failed["success"] = False
                failed["errors"] = ["document mismatch"]
                atomic_write_json(result_path(ipc_dir, str(request["request_id"])), failed)

            client = DotNetIPCClient(ipc_dir=ipc_dir, trigger=trigger)
            with self.assertRaises(DotNetIPCResultError) as context:
                client.review(r"C:\temp\sample.dwg", ["10"])

            self.assertIn("document mismatch", str(context.exception))
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))

    def test_oversized_result_is_rejected_by_bounded_read(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                oversized = _result(request, {"data": "x" * 256})
                result_file = result_path(ipc_dir, str(request["request_id"]))
                result_file.write_text(json.dumps(oversized), encoding="utf-8")

            client = DotNetIPCClient(
                ipc_dir=ipc_dir,
                trigger=trigger,
                max_read_bytes=128,
            )
            with self.assertRaises(ValueError):
                client.health()
            self.assertFalse(list(ipc_dir.glob("cadagent_dotnet_*.json")))

    def _disposable_client(self, ipc_dir: Path, root: Path, dispatcher=None) -> DotNetIPCClient:
        return DotNetIPCClient(
            ipc_dir=ipc_dir,
            trigger=dispatcher,
        )

    @staticmethod
    def _issue_disposable(client: DotNetIPCClient, root: Path):
        issue = getattr(client, "issue_disposable_workspace", None)
        if not callable(issue):
            raise AssertionError("DotNetIPCClient must expose owner-issued disposable workspaces")
        return issue(
            candidate_identity="candidate-001",
            source_identity="source-001",
            source_fingerprint="a" * 64,
            purpose="r6-gate-0",
            workspace_root=root,
        )

    def test_owner_issues_one_server_owned_disposable_workspace_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            client = self._disposable_client(ipc_dir, root, lambda: None)

            lease = self._issue_disposable(client, root)

            self.assertIs(type(lease), dotnet_ipc.DisposableWorkspaceLease)
            self.assertRegex(lease.lease_id, r"^[0-9a-f]{32}$")
            self.assertTrue(lease.disposable)
            self.assertFalse(lease.save_changes)
            self.assertEqual("active", lease.lifecycle_state)
            self.assertEqual("candidate-001", lease.candidate_identity)
            self.assertEqual("source-001", lease.source_identity)
            self.assertTrue(lease.workspace_path.is_dir())
            self.assertEqual(root.resolve(), lease.workspace_path.parent.resolve())

    def test_disposable_workspace_rejects_outside_or_traversal_root_without_path_leak(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            client = self._disposable_client(ipc_dir, root, lambda: None)
            for requested_root in (ipc_dir / "outside", root / ".." / "outside"):
                with self.subTest(requested_root=requested_root):
                    with self.assertRaisesRegex(ValueError, "disposable workspace root") as context:
                        self._issue_disposable(client, requested_root)
                    self.assertNotIn(str(requested_root), str(context.exception))

    def test_disposable_workspace_rejects_equal_field_copy_and_foreign_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            client = self._disposable_client(ipc_dir, root, lambda: None)
            lease = self._issue_disposable(client, root)
            fake = copy.copy(lease)
            close = getattr(client, "close_disposable_workspace", None)
            self.assertTrue(callable(close))

            for candidate in (fake, object()):
                with self.subTest(candidate=type(candidate).__name__):
                    with self.assertRaises(dotnet_ipc.DotNetIPCProtocolError):
                        close(
                            candidate,
                            candidate_identity="candidate-001",
                            source_identity="source-001",
                            source_fingerprint="a" * 64,
                        )
            self.assertEqual("active", lease.lifecycle_state)

    def test_disposable_workspace_rejects_hostile_string_and_path_subclasses(self) -> None:
        class HostileString(str):
            def __hash__(self):
                return 0

            def __eq__(self, other):
                return True

        class HostilePath(type(Path())):
            pass

        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            client = self._disposable_client(ipc_dir, root, lambda: None)
            issue = getattr(client, "issue_disposable_workspace")
            with self.assertRaises(ValueError):
                issue(
                    candidate_identity=HostileString("candidate-001"),
                    source_identity="source-001",
                    source_fingerprint="a" * 64,
                    purpose="r6-gate-0",
                    workspace_root=root,
                )
            with self.assertRaises(ValueError):
                issue(
                    candidate_identity="candidate-001",
                    source_identity="source-001",
                    source_fingerprint="a" * 64,
                    purpose="r6-gate-0",
                    workspace_root=HostilePath(root),
                )

    def test_disposable_workspace_fingerprint_mismatch_does_not_change_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            client = self._disposable_client(ipc_dir, root, lambda: None)
            lease = self._issue_disposable(client, root)
            close = getattr(client, "close_disposable_workspace")

            with self.assertRaises(dotnet_ipc.DotNetIPCProtocolError):
                close(
                    lease,
                    candidate_identity="candidate-001",
                    source_identity="source-001",
                    source_fingerprint="b" * 64,
                )
            self.assertEqual("active", lease.lifecycle_state)
            self.assertTrue(lease.workspace_path.exists())

    def test_disposable_workspace_close_emits_immutable_zero_survivor_evidence(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            dispatcher = FakeDispatcher(ipc_dir)
            client = self._disposable_client(ipc_dir, root, dispatcher)
            lease = self._issue_disposable(client, root)
            close = getattr(client, "close_disposable_workspace")

            closure = close(
                lease,
                candidate_identity="candidate-001",
                source_identity="source-001",
                source_fingerprint="a" * 64,
            )

            self.assertIs(type(closure), dotnet_ipc.DisposableWorkspaceClosure)
            self.assertEqual(lease.lease_id, closure.lease_id)
            self.assertEqual("closed", closure.close_outcome)
            self.assertEqual("zero_survivors", closure.cleanup_outcome)
            self.assertFalse(closure.save_changes)
            self.assertEqual("closed", closure.lifecycle_state)
            self.assertFalse(closure.workspace_path.exists())
            with self.assertRaises(Exception):
                closure.lifecycle_state = "active"

    def test_disposable_workspace_close_is_terminal_and_replay_safe(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            dispatcher = FakeDispatcher(ipc_dir)
            client = self._disposable_client(ipc_dir, root, dispatcher)
            lease = self._issue_disposable(client, root)
            close = getattr(client, "close_disposable_workspace")
            kwargs = {
                "candidate_identity": "candidate-001",
                "source_identity": "source-001",
                "source_fingerprint": "a" * 64,
            }

            first = close(lease, **kwargs)
            second = close(lease, **kwargs)

            self.assertIs(first, second)
            self.assertEqual(1, len(dispatcher.requests))
            self.assertEqual("closed", lease.lifecycle_state)

    def test_disposable_workspace_failed_close_is_fail_closed_without_false_success(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"

            def failed_dispatcher() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                failed = _result(request)
                failed["success"] = False
                failed["errors"] = ["close failed"]
                atomic_write_json(result_path(ipc_dir, str(request["request_id"])), failed)

            client = self._disposable_client(ipc_dir, root, failed_dispatcher)
            lease = self._issue_disposable(client, root)
            close = getattr(client, "close_disposable_workspace")

            with self.assertRaises(dotnet_ipc.DisposableWorkspaceClosureError) as context:
                close(
                    lease,
                    candidate_identity="candidate-001",
                    source_identity="source-001",
                    source_fingerprint="a" * 64,
                )
            self.assertEqual("close_failed", context.exception.closure.lifecycle_state)
            self.assertEqual("failed", context.exception.closure.close_outcome)
            self.assertNotEqual("closed", context.exception.closure.close_outcome)
            self.assertEqual("active", lease.lifecycle_state)
            self.assertTrue(lease.workspace_path.exists())

    def test_disposable_workspace_cleanup_requires_zero_survivors(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            root = ipc_dir / "disposable-workspaces"
            dispatcher = FakeDispatcher(ipc_dir)
            client = self._disposable_client(ipc_dir, root, dispatcher)
            lease = self._issue_disposable(client, root)
            close = getattr(client, "close_disposable_workspace")

            with patch.object(dotnet_ipc, "_remove_tree_without_reparse", side_effect=OSError):
                with self.assertRaises(dotnet_ipc.DisposableWorkspaceClosureError) as context:
                    close(
                        lease,
                        candidate_identity="candidate-001",
                        source_identity="source-001",
                        source_fingerprint="a" * 64,
                    )
            self.assertEqual("cleanup_failed", context.exception.closure.lifecycle_state)
            self.assertEqual("failed", context.exception.closure.cleanup_outcome)
            self.assertEqual("active", lease.lifecycle_state)
            self.assertTrue(lease.workspace_path.exists())


class PathUtilityTests(unittest.TestCase):
    def test_autocad_marker_is_scoped_to_live_smoke_class(self) -> None:
        live_module = importlib.import_module(
            "mcp_integration_lib.tests.test_dotnet_ipc_live"
        )

        self.assertNotIn("pytestmark", vars(live_module))
        live_markers = getattr(live_module.DotNetIPCLiveSmokeTests, "pytestmark", [])
        self.assertEqual(["autocad_mechanical"], [marker.name for marker in live_markers])
        setup_markers = getattr(live_module.PersonalSetupLiveTests, "pytestmark", [])
        self.assertEqual(["autocad_mechanical"], [marker.name for marker in setup_markers])
        self.assertFalse(hasattr(live_module.DisposableCleanupTests, "pytestmark"))

    def test_request_and_result_names_use_the_new_prefix(self) -> None:
        request_id = "health-20260801-001"

        self.assertEqual(
            f"{REQUEST_PREFIX}{request_id}.json",
            request_filename(request_id),
        )
        self.assertEqual(
            f"{RESULT_PREFIX}{request_id}.json",
            result_filename(request_id),
        )

    def test_request_ids_are_safe_for_file_names(self) -> None:
        self.assertEqual("abc-123_X", normalize_request_id("abc-123_X"))

        for invalid in ("", " ", "../escape", "bad.id", "a\\b", "a" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_request_id(invalid)

    def test_paths_are_scoped_to_the_ipc_directory(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request = request_path(ipc_dir, "one")
            result = result_path(ipc_dir, "one")

            resolved_ipc_dir = ipc_dir.resolve()
            self.assertEqual(
                resolved_ipc_dir / "cadagent_dotnet_request_one.json",
                request,
            )
            self.assertEqual(
                resolved_ipc_dir / "cadagent_dotnet_result_one.json",
                result,
            )

    def test_normalizes_absolute_windows_paths_and_rejects_relative_paths(self) -> None:
        self.assertEqual(
            r"C:\drawings\sample.dwg",
            normalize_windows_absolute_path(r"C:/drawings/parts/../sample.dwg"),
        )
        self.assertEqual(
            r"\\server\share\sample.dwg",
            normalize_windows_absolute_path(r"\\server\share\folder\..\sample.dwg"),
        )

        for invalid in ("sample.dwg", r"C:sample.dwg", "", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_windows_absolute_path(invalid)

    def test_ipc_directory_env_override_is_resolved(self) -> None:
        with TemporaryDirectory() as temporary:
            previous = os.environ.get("CAD_AGENT_DOTNET_IPC_DIR")
            try:
                os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = temporary
                self.assertEqual(Path(temporary).resolve(), get_ipc_dir())
            finally:
                if previous is None:
                    os.environ.pop("CAD_AGENT_DOTNET_IPC_DIR", None)
                else:
                    os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = previous

        self.assertEqual(Path(DEFAULT_IPC_DIR), Path(r"C:\temp"))

    def test_cleanup_removes_only_the_requested_pair(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            result_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            request_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            result_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            old_dispatcher = ipc_dir / "autocad_mcp_result_legacy.json"
            old_dispatcher.write_text("legacy", encoding="utf-8")

            cleanup_request_files(ipc_dir, "one")

            self.assertFalse(request_path(ipc_dir, "one").exists())
            self.assertFalse(result_path(ipc_dir, "one").exists())
            self.assertTrue(request_path(ipc_dir, "two").exists())
            self.assertTrue(result_path(ipc_dir, "two").exists())
            self.assertTrue(old_dispatcher.exists())


if __name__ == "__main__":
    unittest.main()
