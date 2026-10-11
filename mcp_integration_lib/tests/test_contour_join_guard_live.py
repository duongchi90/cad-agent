"""One opt-in native gate for source-declared LINE/ARC endpoint incidence."""
import os
from pathlib import Path

import pytest

from cad_agent.cli import _live_client
from dxf_builder_lib.tests.dxf_test_support import build_fillet_join_fixture
from mcp_integration_lib.reviewer2 import review_dxf_live

pytestmark = pytest.mark.autocad_mechanical


@pytest.mark.skipif(
    os.getenv("CAD_AGENT_FILE_IPC") != "1"
    or not os.getenv("CAD_AGENT_AUTOCAD_HWND")
    or not os.getenv("CAD_AGENT_AUTOCAD_LISP_PATH"),
    reason="requires explicit AutoCAD Mechanical File IPC session/HWND/dispatcher",
)
def test_native_fillet_join_review(tmp_path):
    client = _live_client(
        int(os.environ["CAD_AGENT_AUTOCAD_HWND"]),
        Path(os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"]), 10.0,
    )
    for coupled in (False, True):
        case_root = tmp_path / ("coupled" if coupled else "radius-only")
        case_root.mkdir()
        built = build_fillet_join_fixture(case_root, 1.1, coupled)
        candidate = Path(built.output_path)
        before = candidate.read_bytes()
        opened = False
        try:
            client.drawing_open(built.output_path)
            opened = True
            review = review_dxf_live(built, client, open_drawing=False)
            assert review.geometry_checked == 3
            assert not review.geometry_degraded
            assert review.contour_checked == 2
            assert review.passed == coupled
            assert bool(review.contour_mismatches) == (not coupled)
        finally:
            if opened:
                client.drawing_close(save_changes=False)
        assert candidate.read_bytes() == before
