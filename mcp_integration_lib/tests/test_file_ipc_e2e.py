"""Opt-in real AutoCAD Phase 4 smoke test."""
from contextlib import contextmanager
import json
import os
import tempfile
import unittest

import ezdxf
import pytest

from dxf_builder_lib.builder import build_dxf
from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    _validate_file_ipc_result,
    make_windows_command_trigger,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
    MCPToolError,
)
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import review_dxf_live
from dxf_builder_lib.repair import repair_insert_components
from dxf_builder_lib.reviewer import review_dxf
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    make_windows_dotnet_dispatch_trigger,
)


def _preopen_component_fixture(path):
    """Opt-in workstation fixture adapter; never fabricates a native result."""
    pytest.skip("requires explicit pre-opened component fixture preparation")


def test_live_component_factory_requires_explicit_ipc_root(monkeypatch):
    monkeypatch.delenv("CAD_AGENT_FILE_IPC_DIR", raising=False)
    monkeypatch.setenv("CAD_AGENT_AUTOCAD_HWND", "123")
    monkeypatch.setenv("CAD_AGENT_AUTOCAD_LISP_PATH", "C:/approved/dispatcher.lsp")
    with pytest.raises(KeyError, match="CAD_AGENT_FILE_IPC_DIR"):
        FileIPCEndToEndTests()._client()


def test_live_component_factory_has_no_implicit_close_authority(monkeypatch, tmp_path):
    file_root = tmp_path / "lisp"
    dotnet_root = tmp_path / "dotnet"
    file_root.mkdir()
    dotnet_root.mkdir()
    monkeypatch.setenv("CAD_AGENT_FILE_IPC_DIR", str(file_root))
    monkeypatch.setenv("CAD_AGENT_DOTNET_IPC_DIR", str(dotnet_root))
    monkeypatch.setenv("CAD_AGENT_AUTOCAD_HWND", "123")
    monkeypatch.setenv("CAD_AGENT_AUTOCAD_LISP_PATH", "C:/approved/dispatcher.lsp")
    calls = []
    for name in ("make_windows_dispatch_trigger", "make_windows_lisp_trigger",
                 "make_windows_command_trigger"):
        monkeypatch.setitem(globals(), name, lambda _hwnd: lambda *args: calls.append(args))
    client = FileIPCEndToEndTests()._client()
    assert client._dir == file_root
    client._active_drawing_path = "c:\\protected\\source.dwg"
    with pytest.raises(MCPToolError, match="DISPOSABLE_CLOSE_TARGET_NOT_AUTHORIZED"):
        client.drawing_close(save_changes=False)
    assert calls == []
    assert client._active_drawing_path == "c:\\protected\\source.dwg"
    assert not list(dotnet_root.iterdir())


def test_file_ipc_result_requires_exact_per_request_claim() -> None:
    request_id = "a1b2c3d4e5f6"
    claim = "fresh-unpredictable-claim"
    accepted = {
        "request_id": request_id,
        "claim": claim,
        "ok": True,
        "payload": {},
    }

    for rejected in (
        {key: value for key, value in accepted.items() if key != "claim"},
        {**accepted, "claim": "different-claim"},
    ):
        with pytest.raises(MCPToolError, match="IPC_RESULT_INVALID"):
            _validate_file_ipc_result(rejected, request_id, claim)

    assert _validate_file_ipc_result(accepted, request_id, claim) == {}


def test_file_ipc_dispatch_binds_fresh_claim_to_request_and_terminal_result(tmp_path) -> None:
    claims = []

    def trigger() -> None:
        request_path = next(tmp_path.glob("autocad_mcp_cmd_*.json"))
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request_id = request["request_id"]
        claim = request["claim"]
        claims.append(claim)
        (tmp_path / f"autocad_mcp_result_{request_id}.json").write_text(
            json.dumps(
                {
                    "request_id": request_id,
                    "claim": claim,
                    "ok": True,
                    "payload": {"ready": True},
                }
            ),
            encoding="utf-8",
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        legacy_fixture_mode=False,
        timeout_s=0.2,
        poll_interval_s=0.001,
    )

    assert client._dispatch("ping", {}) == {"ready": True}
    assert client._dispatch("ping", {}) == {"ready": True}
    assert len(claims) == 2
    assert claims[0] != claims[1]


def test_file_ipc_dispatch_accepts_exact_claim_on_terminal_error(tmp_path) -> None:
    def trigger() -> None:
        request_path = next(tmp_path.glob("autocad_mcp_cmd_*.json"))
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result_path = tmp_path / f"autocad_mcp_result_{request['request_id']}.json"
        result_path.write_text(
            json.dumps(
                {
                    "request_id": request["request_id"],
                    "claim": request["claim"],
                    "ok": False,
                    "error": "IPC_COMMAND_FAILED",
                }
            ),
            encoding="utf-8",
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        legacy_fixture_mode=False,
        timeout_s=0.2,
        poll_interval_s=0.001,
    )

    with pytest.raises(MCPToolError, match="IPC_COMMAND_FAILED"):
        client._dispatch("ping", {})


@pytest.mark.autocad_mechanical
@unittest.skipUnless(os.getenv("CAD_AGENT_FILE_IPC") == "1", "requires AutoCAD File IPC")
class FileIPCEndToEndTests(unittest.TestCase):
    def _client(self, *disposable_paths):
        ipc_dir = os.environ["CAD_AGENT_FILE_IPC_DIR"]
        dotnet_ipc_dir = os.environ["CAD_AGENT_DOTNET_IPC_DIR"]
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        return FileIPCLiveMCPClient(
            ipc_dir=ipc_dir,
            trigger=make_windows_dispatch_trigger(hwnd),
            raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
            command_trigger=make_windows_command_trigger(hwnd),
            bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            disposable_close_client=DotNetIPCClient(
                ipc_dir=dotnet_ipc_dir,
                trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            ),
            disposable_close_paths=list(disposable_paths),
            document_settle_s=3.0,
        )

    @contextmanager
    def _opened_disposable_drawing(self, client, path):
        client.drawing_open(path)
        try:
            yield
        finally:
            client.drawing_close(save_changes=False)

    def _rebind_component_handle(self, client, build, part_id):
        """Resolve the current AutoCAD handle by the stable PART_ID attribute."""
        candidates = []
        for entity in client.entity_list():
            if str(entity.get("type", "")).upper() != "INSERT":
                continue
            attributes = client.block_get_attributes(entity["handle"])
            if attributes.get("PART_ID") == part_id:
                candidates.append(entity["handle"])
        self.assertEqual(
            len(candidates),
            1,
            f"expected one live INSERT for PART_ID={part_id!r}, got {candidates!r}",
        )
        build.component_handle_by_part_id[part_id] = candidates[0]
        return candidates[0]

    def _repair_component_attribute(self, build, part_id, attribute):
        exported = build.output_path.replace(".dxf", "_roundtrip.dxf")
        client = self._client(build.output_path, exported)
        with self._opened_disposable_drawing(client, build.output_path):
            handle = self._rebind_component_handle(client, build, part_id)
            expected = client.block_get_attributes(handle)[attribute]
            client.block_update_attribute(handle, attribute, "wrong")
            client.drawing_save_as_dxf(exported)
        build.output_path = exported
        before = review_dxf(build)
        self.assertFalse(before.passed)
        self.assertEqual(1, repair_insert_components(build, before.component_mismatches).repaired_count)
        with self._opened_disposable_drawing(client, build.output_path):
            handle = self._rebind_component_handle(client, build, part_id)
            self.assertEqual(expected, client.block_get_attributes(handle)[attribute])
            self.assertTrue(review_dxf(build).passed)

    def test_remaining_components_round_trip_real_autocad(self):
        cases = [
            ("bracket", [Primitive(id="h", type="circle", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=CircleGeometry(center=Point2D(10, 20), radius=4))], "lo_bat_vit", ["h"], "HOLE_DIAMETER_MM"),
            ("panel", [Primitive(id="c", type="circle", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=CircleGeometry(center=Point2D(10, 20), radius=75))], "duong_vien_tron", ["c"], "RADIUS_MM"),
            ("panel_rect", [Primitive(id="a", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(200,0))), Primitive(id="b", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(200,0), end=Point2D(200,100)))], "khung_chu_nhat", ["a","b"], "WIDTH_MM"),
            ("bracket_L", [Primitive(id="a", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(150,0))), Primitive(id="b", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(0,80)))], "gia_do", ["a","b"], "LEG_A_MM"),
            ("hinge", [Primitive(id="a", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(120,0))), Primitive(id="b", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,8), end=Point2D(120,8))), Primitive(id="h1", type="circle", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=CircleGeometry(center=Point2D(0,4), radius=3)), Primitive(id="h2", type="circle", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=CircleGeometry(center=Point2D(120,4), radius=3))], "ban_le", ["a","b","h1","h2"], "GAP_MM"),
            ("node", [Primitive(id="a", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(100,0))), Primitive(id="b", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(0,80))), Primitive(id="c", type="line", source="smoke", confidence=1, trace=Trace(bbox_px=(0,0,1,1)), geometry=LineGeometry(start=Point2D(0,0), end=Point2D(-60,60)))], "diem_noi", ["a","b","c"], "LEG_COUNT"),
        ]
        for name, primitives, part_type, ids, attribute in cases:
            with self.subTest(name=name):
                tmp = tempfile.mkdtemp(prefix="cad_agent_component_")
                source = PrimitiveIRDocument(SourceDocument(file_name=name, page_index=0, image_width_px=1, image_height_px=1), Calibration(unit="mm", pixel_to_unit_scale=1, origin_px=(0,0), method="manual_override"), primitives)
                semantic = SemanticIRDocument(PrimitiveIRRef(file_name=name, primitive_count=len(primitives)), [SemanticPart(part_type=part_type, primitive_ids=ids, confidence=1)], [])
                build = build_dxf(source, os.path.join(tmp, name + ".dxf"), semantic_doc=semantic, build_components=True)
                self._repair_component_attribute(build, semantic.parts[0].id, attribute)

    def test_beam_insert_attribute_round_trip_real_autocad(self):
        tmp = tempfile.mkdtemp(prefix="cad_agent_beam_")
        path = os.path.join(tmp, "beam_smoke.dxf")
        beam = Primitive(
            id="b1", type="line", source="phase4_smoke", confidence=1.0,
            trace=Trace(bbox_px=(0, 0, 500, 1)),
            geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(500, 0)),
        )
        source = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="beam_smoke.png", page_index=0,
                                           image_width_px=500, image_height_px=1),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0,
                                    origin_px=(0, 0), method="manual_override"),
            primitives=[beam],
        )
        semantic = SemanticIRDocument(
            primitive_ir_ref=PrimitiveIRRef(file_name="beam_smoke.json", primitive_count=1),
            parts=[SemanticPart(part_type="thanh_ngang", primitive_ids=["b1"], confidence=1.0)],
            constraints=[],
        )
        build = build_dxf(source, path, semantic_doc=semantic, build_components=True)
        part_id = semantic.parts[0].id
        saved_path = os.path.join(tmp, "beam_smoke_roundtrip.dxf")
        client = self._client(build.output_path, saved_path)
        with self._opened_disposable_drawing(client, build.output_path):
            handle = self._rebind_component_handle(client, build, part_id)
            self.assertEqual(os.path.basename(path), client.drawing_get_variables(["DWGNAME"])["DWGNAME"])
            self.assertEqual("INSERT", client.entity_get(handle)["type"])
            self.assertEqual("COMP_FRAME_BEAM", build.written_component_by_part_id[part_id]["block_name"])
            self.assertEqual(part_id, client.block_get_attributes(handle)["PART_ID"])

            client.block_update_attribute(handle, "PART_ID", "wrong")
            self.assertEqual("wrong", client.block_get_attributes(handle)["PART_ID"])
            client.drawing_save_as_dxf(saved_path)
        build.output_path = saved_path
        saved = ezdxf.readfile(saved_path).entitydb.get(handle)
        self.assertEqual("wrong", {a.dxf.tag: a.dxf.text for a in saved.attribs}["PART_ID"])
        review_before = review_dxf(build)
        self.assertFalse(review_before.passed)
        self.assertTrue(review_before.component_mismatches)
        repaired = repair_insert_components(build, review_before.component_mismatches)
        self.assertEqual(1, repaired.repaired_count)

        with self._opened_disposable_drawing(client, build.output_path):
            new_handle = self._rebind_component_handle(client, build, part_id)
            self.assertEqual("INSERT", client.entity_get(new_handle)["type"])
            self.assertEqual(part_id, client.block_get_attributes(new_handle)["PART_ID"])
            self.assertTrue(review_dxf(build).passed)

    def test_build_and_review_real_dxf(self):
        # AutoCAD keeps the active DXF locked on Windows. Use a disposable IPC
        # directory and leave its cleanup to the OS rather than failing test
        # teardown while the application still has the drawing open.
        tmp = tempfile.mkdtemp(prefix="cad_agent_phase4_")
        path = os.path.join(tmp, "phase4_smoke.dxf")
        with self.subTest(path=path):
            primitive = Primitive(
                id="smoke", type="line", source="phase4_smoke", confidence=1.0,
                trace=Trace(bbox_px=(0, 0, 10, 1)),
                geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(10, 0)),
            )
            source = PrimitiveIRDocument(
                source_document=SourceDocument(file_name="phase4_smoke.png", page_index=0,
                                               image_width_px=10, image_height_px=1),
                calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0,
                                        origin_px=(0, 0), method="manual_override"),
                primitives=[primitive],
            )
            build = build_dxf(source, path)
            client = self._client(path)
            with self._opened_disposable_drawing(client, path):
                self.assertEqual(
                    os.path.basename(path),
                    client.drawing_get_variables(["DWGNAME"])["DWGNAME"],
                    "AutoCAD did not switch to the DXF requested for this smoke test",
                )
                self.assertIn(
                    build.handle_by_primitive_id["smoke"],
                    {entity["handle"] for entity in client.entity_list()},
                    "AutoCAD did not switch to the DXF requested for this smoke test",
                )
                review = review_dxf_live(build, client, open_drawing=False)
                self.assertTrue(
                    review.passed,
                    {"mismatches": review.mismatches,
                     "actual": client.entity_get(build.handle_by_primitive_id["smoke"])},
                )

                # Deliberately replace the entity with incorrect geometry. This
                # proves that review detects a real AutoCAD-side change and that
                # repair can restore the expected primitive through File IPC.
                client.entity_erase(build.handle_by_primitive_id["smoke"])
                client.entity_create_line(0, 0, 99, 0, layer="0")
                mismatched = review_dxf_live(build, client, open_drawing=False)
                self.assertFalse(mismatched.passed)
                repaired = repair_dxf_live(build, mismatched.mismatches, client)
                self.assertEqual(1, repaired.repaired_count)
                final = review_dxf_live(build, client, open_drawing=False)
                self.assertTrue(final.passed, final.mismatches)

    def test_native_dimension_round_trip_real_autocad(self):
        tmp = tempfile.mkdtemp(prefix="cad_agent_dimension_")
        path = os.path.join(tmp, "dimension_smoke.dxf")
        line = Primitive(
            id="dimension-line",
            type="line",
            source="phase4_smoke",
            confidence=1.0,
            trace=Trace(bbox_px=(0, 0, 80, 1)),
            geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(80, 0)),
        )
        validation = CrossValidation(
            text_primitive_id="dimension-text",
            geometry_primitive_id=line.id,
            status="confirmed",
            text_value=80.0,
            geometry_measured_length=80.0,
            delta_percent=0.0,
        )
        source = PrimitiveIRDocument(
            source_document=SourceDocument(
                file_name="dimension_smoke.png",
                page_index=0,
                image_width_px=80,
                image_height_px=1,
            ),
            calibration=Calibration(
                unit="mm",
                pixel_to_unit_scale=1.0,
                origin_px=(0, 0),
                method="manual_override",
            ),
            primitives=[line],
            cross_validations=[validation],
        )
        build = build_dxf(source, path, build_dimensions=True)
        client = self._client(path)
        with self._opened_disposable_drawing(client, path):
            review = review_dxf_live(build, client, open_drawing=False)
            self.assertTrue(review.passed, review.mismatches)
            self.assertEqual(review.dimension_checked, 1)

    def test_same_named_drawings_in_different_directories_use_full_path_identity(self):
        first_dir = tempfile.mkdtemp(prefix="cad_agent_same_a_")
        second_dir = tempfile.mkdtemp(prefix="cad_agent_same_b_")
        first_path = os.path.join(first_dir, "same-name.dxf")
        second_path = os.path.join(second_dir, "same-name.dxf")
        first = ezdxf.new("R2010")
        first.modelspace().add_line((0, 0), (10, 0))
        first.saveas(first_path)
        second = ezdxf.new("R2010")
        second.modelspace().add_circle((5, 5), 2)
        second.saveas(second_path)

        client = self._client(first_path, second_path)
        with self._opened_disposable_drawing(client, first_path):
            with self._opened_disposable_drawing(client, second_path):
                variables = client.drawing_get_variables(["DWGPREFIX", "DWGNAME"])
                active = os.path.normcase(
                    os.path.normpath(
                        os.path.join(variables["DWGPREFIX"], variables["DWGNAME"])
                    )
                )
                self.assertEqual(os.path.normcase(os.path.normpath(second_path)), active)
                open_paths = {
                    os.path.normcase(os.path.normpath(path))
                    for path in client.drawing_list_open_paths()
                }
                self.assertIn(os.path.normcase(os.path.normpath(second_path)), open_paths)
                self.assertEqual({"CIRCLE"}, {entity["type"] for entity in client.entity_list()})

    def test_preopened_component_layout_guard_real_autocad(self):
        """Component acceptance only; generic document-opening failure stays separate."""
        from dxf_builder_lib.tests.test_reviewer import _build_beam_component
        from dxf_builder_lib.reviewer import _DEFAULT_TOLERANCE_MM

        tmp = tempfile.mkdtemp(prefix="cad_agent_layout_guard_")
        build, part_id, source = _build_beam_component(tmp)
        valid_export = os.path.join(tmp, "valid_native.dxf")
        foreign_source = os.path.join(tmp, "tracked_paper_fixture.dxf")
        foreign_export = os.path.join(tmp, "foreign_native.dxf")
        persisted = os.path.join(tmp, "refused_repair_native.dwg")
        reopened_export = os.path.join(tmp, "reopened_native.dxf")
        client = self._client(source, valid_export, foreign_source,
                              foreign_export, persisted, reopened_export)

        def signature(entity):
            return {
                "handle": entity.dxf.handle, "owner": entity.dxf.owner,
                "layout": entity.get_layout().name, "block": entity.dxf.name,
                "layer": entity.dxf.layer, "insert": tuple(entity.dxf.insert),
                "scale": (entity.dxf.xscale, entity.dxf.yscale, entity.dxf.zscale),
                "rotation": entity.dxf.rotation,
                "attributes": [(a.dxf.tag, a.dxf.text, tuple(a.dxf.insert),
                                a.dxf.height, a.dxf.rotation) for a in entity.attribs],
            }

        _preopen_component_fixture(source)
        with self._opened_disposable_drawing(client, source):
            handle = self._rebind_component_handle(client, build, part_id)
            self.assertEqual("Model", client.entity_get(handle)["layout"])
            self.assertEqual(4, client.drawing_get_variables(["INSUNITS"])["INSUNITS"])
            line = client.entity_get(build.handle_by_primitive_id["b1"])
            self.assertEqual([0, 0, 0], line["start"])
            self.assertEqual([500, 0, 0], line["end"])
            client.drawing_save_as_dxf(valid_export)
        build.output_path = valid_export
        self.assertTrue(review_dxf(build).passed)

        # Explicit fault preparation, not production repair: retain tracked handle,
        # geometry and attributes while transferring the INSERT to PaperSpace.
        doc = ezdxf.readfile(valid_export)
        tracked = doc.entitydb[build.component_handle_by_part_id[part_id]]
        doc.modelspace().move_to_layout(tracked, doc.layout("Layout1"))
        doc.saveas(foreign_source)
        _preopen_component_fixture(foreign_source)
        with self._opened_disposable_drawing(client, foreign_source):
            handle = self._rebind_component_handle(client, build, part_id)
            self.assertEqual("Layout1", client.entity_get(handle)["layout"])
            client.drawing_save_as_dxf(foreign_export)
        build.output_path = foreign_export
        before = signature(ezdxf.readfile(foreign_export).entitydb[handle])
        review = review_dxf(build)
        self.assertFalse(review.passed)
        self.assertTrue(review.component_mismatches)
        repaired = repair_insert_components(build, review.component_mismatches)
        self.assertEqual(0, repaired.repaired_count)
        self.assertEqual(1, repaired.skipped_count)
        self.assertEqual(handle, build.component_handle_by_part_id[part_id])
        self.assertEqual(before, signature(ezdxf.readfile(foreign_export).entitydb[handle]))
        self.assertFalse(review_dxf(build).passed)

        _preopen_component_fixture(foreign_export)
        with self._opened_disposable_drawing(client, foreign_export):
            self.assertEqual("Layout1", client.entity_get(handle)["layout"])
            client.drawing_save(persisted)
            client.drawing_open(persisted)  # Rebind the actual SAVEAS identity.
        _preopen_component_fixture(persisted)
        with self._opened_disposable_drawing(client, persisted):
            self.assertEqual("Layout1", client.entity_get(handle)["layout"])
            client.drawing_save_as_dxf(reopened_export)
        after = signature(ezdxf.readfile(reopened_export).entitydb[handle])
        self.assertEqual({k: v for k, v in before.items() if k != "attributes"},
                         {k: v for k, v in after.items() if k != "attributes"})
        self.assertEqual(len(before["attributes"]), len(after["attributes"]))
        for expected, actual in zip(before["attributes"], after["attributes"]):
            self.assertEqual(expected[:2] + expected[3:], actual[:2] + actual[3:])
            self.assertEqual(actual[2], pytest.approx(expected[2],
                             rel=0, abs=_DEFAULT_TOLERANCE_MM))
        build.output_path = reopened_export
        self.assertFalse(review_dxf(build).passed)
