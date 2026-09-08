"""Opt-in smoke test for an AutoCAD File IPC session.

Run with CAD_AGENT_FILE_IPC=1, CAD_AGENT_FILE_IPC_DIR, and
CAD_AGENT_AUTOCAD_HWND after AutoCAD loads mcp_dispatch.lsp.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

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
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPToolError,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)


pytestmark = pytest.mark.autocad_mechanical


def _live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and bool(os.getenv("CAD_AGENT_FILE_IPC_DIR"))
        and bool(os.getenv("CAD_AGENT_AUTOCAD_HWND"))
    )


def _live_json_number_prerequisites_available() -> bool:
    return _live_prerequisites_available() and bool(
        os.getenv("CAD_AGENT_AUTOCAD_LISP_PATH")
    )


def _live_file_ipc_client(
    hwnd: int,
    *,
    raw_lisp_trigger=None,
    bootstrap_lisp_path=None,
    timeout_s: float = 10.0,
) -> FileIPCLiveMCPClient:
    return FileIPCLiveMCPClient(
        ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
        trigger=make_windows_dispatch_trigger(hwnd),
        raw_lisp_trigger=raw_lisp_trigger,
        bootstrap_lisp_path=bootstrap_lisp_path,
        timeout_s=timeout_s,
    )


@unittest.skipUnless(
    _live_prerequisites_available(),
    "requires live AutoCAD File IPC with explicit IPC root and HWND",
)
class FileIPCLiveSmokeTests(unittest.TestCase):
    def test_active_drawing_is_readable(self):
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        client = _live_file_ipc_client(hwnd)
        self.assertIsInstance(client.entity_list(), list)


@unittest.skipUnless(
    _live_json_number_prerequisites_available(),
    "requires live AutoCAD File IPC, explicit IPC root/HWND, and dispatcher path",
)
class FileIPCLiveJsonNumberTests(unittest.TestCase):
    def test_real_json_numbers_parse_through_file_ipc_with_dimzin_modes(self):
        test_directory = Path(
            tempfile.mkdtemp(prefix="cad_agent_json_numbers_", dir=r"C:\temp")
        )
        drawing_path = test_directory / "json_numbers.dxf"
        client = None
        opened = False
        try:
            line = Primitive(
                id="json-number-line",
                type="line",
                source="geometry_opencv",
                confidence=1.0,
                trace=Trace(bbox_px=(0, 0, 1, 1)),
                geometry=LineGeometry(
                    start=Point2D(0.5, -0.5),
                    end=Point2D(1.5, -1.5),
                ),
            )
            drawing_document = PrimitiveIRDocument(
                source_document=SourceDocument(
                    file_name="json_numbers.png",
                    page_index=0,
                    image_width_px=1,
                    image_height_px=1,
                ),
                calibration=Calibration(
                    unit="mm",
                    pixel_to_unit_scale=1.0,
                    origin_px=(0, 0),
                    method="manual_override",
                ),
                primitives=[line],
            )
            build_dxf(drawing_document, str(drawing_path))

            hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
            raw_lisp_trigger = make_windows_lisp_trigger(hwnd)
            client = _live_file_ipc_client(
                hwnd,
                raw_lisp_trigger=raw_lisp_trigger,
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
                timeout_s=60.0,
            )
            client.drawing_open(str(drawing_path))
            opened = True
            entities = client.entity_list()
            line = next(
                entity for entity in entities if entity.get("type") == "LINE"
            )
            handle = str(line["handle"])
            original_dimzin = client.drawing_get_variables(["DIMZIN"])["DIMZIN"]

            try:
                for dimzin in (0, 4):
                    raw_lisp_trigger(f'(setvar "DIMZIN" {dimzin})')
                    payload = client.entity_get(handle)
                    self.assertEqual([0.5, -0.5, 0.0], payload["start"])
                    self.assertEqual([1.5, -1.5, 0.0], payload["end"])
                    self.assertTrue(client.last_exchange_evidence["terminal"])
            finally:
                raw_lisp_trigger(f'(setvar "DIMZIN" {original_dimzin})')
        finally:
            if opened and client is not None and client._active_drawing_path is not None:
                raw_lisp_trigger('(setvar "DBMOD" 0)')
                try:
                    client.drawing_close(save_changes=False)
                except MCPToolError as exc:
                    if str(exc) != "DRAWING_CLOSE_NOT_CONFIRMED":
                        raise
            shutil.rmtree(test_directory, ignore_errors=True)
