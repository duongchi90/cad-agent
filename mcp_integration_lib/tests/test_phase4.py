import unittest
import json
import re
import tempfile
from pathlib import Path

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.mcp_client import FakeMCPClient, FileIPCLiveMCPClient, MCPToolError, MCPTimeoutError
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import review_dxf_live
from mcp_integration_lib.reviewer2 import _same


def _pair(kind="line", entity_get=False):
    build = BuildResult(output_path="fake.dxf", entity_count=1)
    geometry = ({"type": "line", "start": (0.0, 0.0), "end": (1.0, 1.0)}
                if kind == "line" else {"type": "arc", "center": (0.0, 0.0), "radius": 2.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0})
    build.handle_by_primitive_id = {"p": "10"}
    build.layer_by_primitive_id = {"p": "L"}
    build.written_geometry_by_primitive_id = {"p": geometry}
    client = FakeMCPClient(fail_entity_get=not entity_get)
    client.preload_entity("10", kind.upper(), "L", dict(geometry))
    return build, client


class Phase4Tests(unittest.TestCase):
    def test_geometry_comparison_accepts_autocad_z_zero(self):
        self.assertTrue(_same((10.0, 0.0), (10.0, 0.0, 0.0)))
    def test_structural_review_passes_when_entity_get_times_out(self):
        build, client = _pair()
        result = review_dxf_live(build, client)
        self.assertTrue(result.passed)
        self.assertTrue(result.geometry_degraded)

    def test_geometry_mismatch_fails(self):
        build, client = _pair(entity_get=True)
        client.tamper("10", end=(2.0, 2.0))
        self.assertFalse(review_dxf_live(build, client).passed)

    def test_live_review_checks_native_dimension_type_layer_and_measurement(self):
        build, client = _pair(entity_get=True)
        build.dimension_count = 1
        build.dimension_handle_by_cross_validation_id = {"cv-1": "20"}
        build.written_dimension_by_cross_validation_id = {
            "cv-1": {"layer": "DIMENSIONS", "measurement": 80.0}
        }
        client.preload_entity(
            "20",
            "DIMENSION",
            "DIMENSIONS",
            {"measurement": 80.0},
        )
        passed = review_dxf_live(build, client)
        self.assertTrue(passed.passed)
        self.assertEqual(passed.dimension_checked, 1)

        client.tamper("20", measurement=79.0)
        failed = review_dxf_live(build, client)
        self.assertFalse(failed.passed)
        self.assertTrue(any("measurement" in item for item in failed.mismatches))

    def test_repair_restores_review_and_updates_handle(self):
        build, client = _pair()
        client._entities["10"].layer = "BAD"
        repair = repair_dxf_live(build, review_dxf_live(build, client).mismatches, client)
        self.assertEqual(repair.repaired_count, 1)
        self.assertNotEqual(build.handle_by_primitive_id["p"], "10")
        self.assertTrue(review_dxf_live(build, client, open_drawing=False).passed)

    def test_arc_repair(self):
        build, client = _pair("arc")
        client._entities["10"].layer = "BAD"
        self.assertEqual(repair_dxf_live(build, review_dxf_live(build, client).mismatches, client).repaired_count, 1)


class FileIPCClientTests(unittest.TestCase):
    def test_maps_drawing_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual((command["command"], command["params"]), ("drawing-open", {"path": "a.dxf"}))
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(json.dumps({"request_id": command["request_id"], "ok": True, "payload": {"path": "a.dxf"}}))
            self.assertEqual(FileIPCLiveMCPClient(tmp, trigger, .1, .001).drawing_open("a.dxf"), {"path": "a.dxf"})

    def test_entity_get_reads_dimension_measurement_through_raw_lisp(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)

            def trigger():
                command = json.loads(
                    next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text()
                )
                result = ipc_dir / (
                    f"autocad_mcp_result_{command['request_id']}.json"
                )
                result.write_text(
                    json.dumps({
                        "request_id": command["request_id"],
                        "ok": True,
                        "payload": {
                            "type": "DIMENSION",
                            "handle": "20",
                            "layer": "DIMENSIONS",
                        },
                    })
                )

            def raw_lisp_trigger(_expression):
                measurement = next(
                    ipc_dir.glob("autocad_mcp_dimension_measurement_*.txt")
                )
                measurement.write_text("80.000000", encoding="utf-8")

            client = FileIPCLiveMCPClient(
                tmp,
                trigger,
                .1,
                .001,
                raw_lisp_trigger=raw_lisp_trigger,
            )
            self.assertEqual(client.entity_get("20")["measurement"], 80.0)

    def test_maps_drawing_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual((command["command"], command["params"]), ("drawing-save", {"path": "a.dxf"}))
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(json.dumps({"request_id": command["request_id"], "ok": True, "payload": {}}))
            self.assertIsNone(FileIPCLiveMCPClient(tmp, trigger, .1, .001).drawing_save("a.dxf"))

    def test_maps_drawing_save_as_dxf(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual((command["command"], command["params"]), ("drawing-save-as-dxf", {"path": "a.dxf"}))
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(json.dumps({"request_id": command["request_id"], "ok": True, "payload": {}}))
            self.assertIsNone(FileIPCLiveMCPClient(tmp, trigger, .1, .001).drawing_save_as_dxf("a.dxf"))

    def test_normalizes_windows_dxf_export_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual(command["params"], {"path": "C:/temp/out.dxf"})
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(json.dumps({"request_id": command["request_id"], "ok": True, "payload": {}}))
            FileIPCLiveMCPClient(tmp, trigger, .1, .001).drawing_save_as_dxf(r"C:\temp\out.dxf")

    def test_maps_drawing_get_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual(
                    (command["command"], command["params"]),
                    ("drawing-get-variables", {"names_str": "DWGNAME;INSUNITS"}),
                )
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(
                    json.dumps({"request_id": command["request_id"], "ok": True,
                                "payload": {"DWGNAME": "a.dxf", "INSUNITS": 4}}))
            client = FileIPCLiveMCPClient(tmp, trigger, .1, .001)
            self.assertEqual(client.drawing_get_variables(["DWGNAME", "INSUNITS"]),
                             {"DWGNAME": "a.dxf", "INSUNITS": 4})

    def test_maps_block_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual((command["command"], command["params"]),
                                 ("block-get-attributes", {"entity_id": "10"}))
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(
                    json.dumps({"request_id": command["request_id"], "ok": True,
                                "payload": {"attributes": {"PART_ID": "beam-1"}}}))
            self.assertEqual(FileIPCLiveMCPClient(tmp, trigger, .1, .001).block_get_attributes("10"),
                             {"PART_ID": "beam-1"})

    def test_maps_block_attribute_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual((command["command"], command["params"]),
                                 ("block-update-attribute", {"entity_id": "10", "tag": "PART_ID", "value": "wrong"}))
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(
                    json.dumps({"request_id": command["request_id"], "ok": True, "payload": {}}))
            self.assertIsNone(FileIPCLiveMCPClient(tmp, trigger, .1, .001).block_update_attribute("10", "PART_ID", "wrong"))

    def test_uses_raw_lisp_bootstrap_to_open_a_new_document(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}
            if command == "drawing-get-variables" else {}
        )
        client.drawing_open("C:/work/a.dxf")
        self.assertEqual(2, len(raw_commands))
        self.assertIn('vla-open', raw_commands[0])
        self.assertIn('C:/work/a.dxf', raw_commands[0])
        self.assertEqual('(load "C:/tools/mcp_dispatch.lsp")', raw_commands[1])

    def test_raw_lisp_close_queues_no_save_command_without_com_close(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_commands.append,
            document_settle_s=0,
        )

        client.drawing_close(save_changes=False)

        self.assertEqual(['(command-s "_.CLOSE" "_N")'], raw_commands)

    def test_command_trigger_closes_without_save_at_command_boundary(self):
        raw_commands = []
        command_sequences = []
        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_commands.append,
            command_trigger=command_sequences.append,
            document_settle_s=0,
        )

        client.drawing_close(save_changes=False)

        self.assertEqual(["_.CLOSE\r_N"], command_sequences)
        self.assertEqual([], raw_commands)

    def test_drawing_open_falls_back_to_command_when_start_tab_has_no_document(self):
        raw_commands = []
        command_sequences = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            command_trigger=command_sequences.append,
            timeout_s=0.01,
            poll_interval_s=0,
            document_settle_s=0,
        )
        ping_calls = 0

        def dispatch(command, params):
            nonlocal ping_calls
            if command == "ping":
                ping_calls += 1
                if not command_sequences:
                    raise MCPTimeoutError("Start tab has no dispatcher")
                return {}
            if command == "drawing-get-variables":
                return {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}
            return {}

        client._dispatch = dispatch

        assert client.drawing_open("C:/work/a.dxf") == {"path": "C:/work/a.dxf"}
        self.assertEqual(['_.OPEN\r"C:/work/a.dxf"'], command_sequences)

    def test_raw_lisp_close_with_save_keeps_com_save_path(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            raw_lisp_trigger=raw_commands.append,
            document_settle_s=0,
        )

        client.drawing_close(save_changes=True)

        self.assertEqual(
            [
                "(progn (vl-load-com) "
                "(vla-close (vla-get-ActiveDocument (vlax-get-acad-object)) "
                ":vlax-true))"
            ],
            raw_commands,
        )

    def test_bootstrap_waits_for_dispatcher_ping(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        calls = []
        client._dispatch = lambda command, params: (
            calls.append((command, params))
            or (
                {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"}
                if command == "drawing-get-variables" else {}
            )
        )
        client.drawing_open("C:/work/a.dxf")
        self.assertEqual(
            [
                ("ping", {}),
                ("drawing-get-variables", {"names_str": "DWGPREFIX;DWGNAME"}),
            ],
            calls,
        )

    def test_bootstrap_retries_when_requested_document_is_not_active(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        documents = iter(
            [
                {"DWGPREFIX": "C:/old/", "DWGNAME": "old.dxf"},
                {"DWGPREFIX": "C:/work/", "DWGNAME": "a.dxf"},
            ]
        )

        def dispatch(command, params):
            if command == "drawing-get-variables":
                return next(documents)
            return {}

        client._dispatch = dispatch
        self.assertEqual(
            {"path": "C:/work/a.dxf"},
            client.drawing_open("C:/work/a.dxf"),
        )
        self.assertEqual(4, len(raw_commands))

    def test_bootstrap_retries_same_named_document_in_different_directory(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        documents = iter(
            [
                {"DWGPREFIX": "C:/other/", "DWGNAME": "same.dxf"},
                {"DWGPREFIX": "C:/target/", "DWGNAME": "same.dxf"},
            ]
        )

        def dispatch(command, params):
            if command == "drawing-get-variables":
                return next(documents)
            return {}

        client._dispatch = dispatch
        self.assertEqual(
            {"path": "C:/target/same.dxf"},
            client.drawing_open("C:/target/same.dxf"),
        )
        self.assertEqual(4, len(raw_commands))

    def test_bootstrap_refuses_same_named_document_in_different_directory(self):
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=lambda command: None,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        client._dispatch = lambda command, params: (
            {"DWGPREFIX": "C:/other/", "DWGNAME": "same.dxf"}
            if command == "drawing-get-variables" else {}
        )

        with self.assertRaisesRegex(MCPToolError, "active drawing is"):
            client.drawing_open("C:/target/same.dxf")

    def test_raw_lisp_lists_open_document_full_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            def raw_trigger(command):
                match = re.search(r'\(open "([^"]+)" "w"\)', command)
                self.assertIsNotNone(match)
                Path(match.group(1)).write_text(
                    "C:/work/a.dxf\nC:/work/b.dxf\n",
                    encoding="utf-8",
                )

            client = FileIPCLiveMCPClient(
                ipc_dir=tmp,
                trigger=lambda: None,
                raw_lisp_trigger=raw_trigger,
                document_settle_s=0,
            )

            self.assertEqual(
                ["C:/work/a.dxf", "C:/work/b.dxf"],
                client.drawing_list_open_paths(),
            )

    def test_block_attribute_read_retries_one_timeout(self):
        client = FileIPCLiveMCPClient(trigger=lambda: None)
        calls = []

        def dispatch(command, params):
            calls.append((command, params))
            if len(calls) == 1:
                raise MCPTimeoutError("transient")
            return {"attributes": {"PART_ID": "beam-1"}}

        client._dispatch = dispatch
        self.assertEqual(
            {"PART_ID": "beam-1"},
            client.block_get_attributes("10"),
        )
        self.assertEqual(2, len(calls))

    def test_raises_timeout_without_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MCPTimeoutError):
                FileIPCLiveMCPClient(tmp, lambda: None, .01, .001).entity_list()

    def test_raises_tool_error_from_dispatcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(json.dumps({"request_id": command["request_id"], "ok": False, "error": "missing"}))
            with self.assertRaises(MCPToolError):
                FileIPCLiveMCPClient(tmp, trigger, .1, .001).entity_get("10")
    def test_maps_entity_list_to_dispatcher_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            ipc_dir = Path(tmp)
            def trigger():
                command = json.loads(next(ipc_dir.glob("autocad_mcp_cmd_*.json")).read_text())
                self.assertEqual(command["command"], "entity-list")
                (ipc_dir / f"autocad_mcp_result_{command['request_id']}.json").write_text(
                    json.dumps({"request_id": command["request_id"], "ok": True,
                                "payload": {"entities": [{"handle": "10", "type": "LINE", "layer": "0"}]}}))
            client = FileIPCLiveMCPClient(ipc_dir=tmp, trigger=trigger, timeout_s=0.1, poll_interval_s=0.001)
            self.assertEqual(client.entity_list(), [{"handle": "10", "type": "LINE", "layer": "0"}])
