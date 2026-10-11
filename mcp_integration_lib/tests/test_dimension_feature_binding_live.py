"""Opt-in native consumer gate; no private/source drawing is modified."""
import os
from pathlib import Path

import pytest

from cad_agent.cli import _live_client
from dxf_builder_lib.tests.dxf_test_support import build_dimension_feature_binding_fixture
from mcp_integration_lib.reviewer2 import review_dxf_live

pytestmark = pytest.mark.autocad_mechanical


@pytest.mark.skipif(
    os.getenv("CAD_AGENT_FILE_IPC") != "1"
    or not os.getenv("CAD_AGENT_FILE_IPC_DIR")
    or not os.getenv("CAD_AGENT_AUTOCAD_HWND")
    or not os.getenv("CAD_AGENT_AUTOCAD_LISP_PATH"),
    reason="requires explicit AutoCAD Mechanical File IPC root/HWND/dispatcher",
)
def test_native_dimension_extension_origins_bind_to_declared_line(tmp_path):
    client = _live_client(int(os.environ["CAD_AGENT_AUTOCAD_HWND"]),
                          Path(os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"]), 10.0)
    for shifted in (False, True):
        root = tmp_path / ("wrong-feature" if shifted else "bound")
        root.mkdir()
        origins = ((0, 25, 0), (80, 25, 0)) if shifted else None
        built, _, _ = build_dimension_feature_binding_fixture(root, origins)
        candidate = Path(built.output_path)
        before = candidate.read_bytes()
        opened = False
        try:
            client.drawing_open(built.output_path)
            opened = True
            result = review_dxf_live(built, client, open_drawing=False)
            assert not result.geometry_degraded
            assert result.geometry_checked == 1
            assert result.dimension_checked == 1
            assert result.passed == (not shifted)
            assert bool(result.dimension_feature_mismatches) == shifted
        finally:
            if opened:
                client.drawing_close(save_changes=False)
        assert candidate.read_bytes() == before
