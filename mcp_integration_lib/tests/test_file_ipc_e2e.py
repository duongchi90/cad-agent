"""Opt-in real AutoCAD Phase 4 smoke test."""
import os
import tempfile
import unittest

import ezdxf

from dxf_builder_lib.builder import build_dxf
from primitive_ir_lib.models import (
    Calibration,
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
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import review_dxf_live
from dxf_builder_lib.repair import repair_insert_components
from dxf_builder_lib.reviewer import review_dxf


@unittest.skipUnless(os.getenv("CAD_AGENT_FILE_IPC") == "1", "requires AutoCAD File IPC")
class FileIPCEndToEndTests(unittest.TestCase):
    def _client(self):
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        return FileIPCLiveMCPClient(
            trigger=make_windows_dispatch_trigger(hwnd),
            raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
            bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
        )

    def test_beam_insert_attribute_round_trip_real_autocad(self):
        tmp = tempfile.mkdtemp(prefix="cad_agent_beam_", dir="C:/temp")
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
        handle = build.component_handle_by_part_id[part_id]
        client = self._client()
        client.drawing_open(build.output_path)
        self.assertEqual(os.path.basename(path), client.drawing_get_variables(["DWGNAME"])["DWGNAME"])
        self.assertEqual("INSERT", client.entity_get(handle)["type"])
        self.assertEqual("COMP_FRAME_BEAM", build.written_component_by_part_id[part_id]["block_name"])
        self.assertEqual(part_id, client.block_get_attributes(handle)["PART_ID"])

        client.block_update_attribute(handle, "PART_ID", "wrong")
        self.assertEqual("wrong", client.block_get_attributes(handle)["PART_ID"])
        saved_path = os.path.join(tmp, "beam_smoke_roundtrip.dxf")
        client.drawing_save_as_dxf(saved_path)
        build.output_path = saved_path
        saved = ezdxf.readfile(saved_path).entitydb.get(handle)
        self.assertEqual("wrong", {a.dxf.tag: a.dxf.text for a in saved.attribs}["PART_ID"])
        review_before = review_dxf(build)
        self.assertFalse(review_before.passed)
        self.assertTrue(review_before.component_mismatches)
        repaired = repair_insert_components(build, review_before.component_mismatches)
        self.assertEqual(1, repaired.repaired_count)

        new_handle = build.component_handle_by_part_id[part_id]
        client.drawing_open(build.output_path)
        self.assertEqual("INSERT", client.entity_get(new_handle)["type"])
        self.assertEqual(part_id, client.block_get_attributes(new_handle)["PART_ID"])
        self.assertTrue(review_dxf(build).passed)

    def test_build_and_review_real_dxf(self):
        # AutoCAD keeps the active DXF locked on Windows. Use a disposable IPC
        # directory and leave its cleanup to the OS rather than failing test
        # teardown while the application still has the drawing open.
        tmp = tempfile.mkdtemp(prefix="cad_agent_phase4_", dir="C:/temp")
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
            client = self._client()
            client.drawing_open(path)
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
