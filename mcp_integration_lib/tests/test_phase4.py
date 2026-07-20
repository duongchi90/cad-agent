import unittest
import json
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

    def test_uses_raw_lisp_bootstrap_to_open_a_new_document(self):
        raw_commands = []
        client = FileIPCLiveMCPClient(
            trigger=lambda: None,
            raw_lisp_trigger=raw_commands.append,
            bootstrap_lisp_path="C:/tools/mcp_dispatch.lsp",
            document_settle_s=0,
        )
        client.drawing_open("C:/work/a.dxf")
        self.assertEqual(2, len(raw_commands))
        self.assertIn('vla-open', raw_commands[0])
        self.assertIn('C:/work/a.dxf', raw_commands[0])
        self.assertEqual('(load "C:/tools/mcp_dispatch.lsp")', raw_commands[1])

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
