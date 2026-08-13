"""R8-D disposable live acceptance harness over accepted public owners.

The offline tests in this module are always collected.  Live AutoCAD/File-IPC
execution is separately opt-in and remains read-only in this Gate-0 slice.
R8-D is acceptance-only: this module must not become an owner, store, transport,
revision authority, verdict authority, repair executor, or publisher.
"""

from __future__ import annotations

import ast
import inspect
import os
import unittest
from pathlib import Path

import pytest

from cad_agent import approved_repair_adapter as r6
from cad_agent import base_cad_adapter as r2
from cad_agent import candidate_revision as r4
from cad_agent import component_view_registry as r3
from cad_agent import publication_composition as r7
from cad_agent import source_fusion as r1
from cad_agent import visual_supervisor_adapter as r5
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    make_windows_dispatch_trigger,
)


REQUIRED_PUBLIC_SEAMS: dict[str, tuple[object, ...]] = {
    "r1": (
        r1.validate_page_locators,
        r1.validate_region_locators,
        r1.validate_render_provenance,
    ),
    "r2": (
        r2.validate_base_cad_binding,
        r2.base_cad_binding_sha256,
        r2.validate_base_cad_reuse_handoff,
        r2.base_cad_reuse_handoff_sha256,
        r2.evaluate_frozen_base_cad_reuse,
    ),
    "r3": (
        r3.build_component_view_registry,
        r3.validate_component_view_registry,
        r3.component_view_registry_sha256,
        r3.finalize_component_view_correspondence,
        r3.project_linked_view_impacts,
    ),
    "r4": (
        r4.build_candidate_revision,
        r4.build_candidate_revision_state,
        r4.validate_candidate_revision_state,
    ),
    "r5": (r5.finalize_visual_verdict, r5.validate_visual_verdict_result),
    "r6": (r6.execute_approved_repair, r6.validate_approved_repair_result),
    "r7": (r7.execute_verified_publication, r7.validate_verified_publication_result),
}

_EXPECTED_OWNER_MODULES = {
    "r1": r1,
    "r2": r2,
    "r3": r3,
    "r4": r4,
    "r5": r5,
    "r6": r6,
    "r7": r7,
}


def test_r8_d_required_public_seams_remain_accepted_single_owner() -> None:
    assert tuple(REQUIRED_PUBLIC_SEAMS) == ("r1", "r2", "r3", "r4", "r5", "r6", "r7")
    for owner, seams in REQUIRED_PUBLIC_SEAMS.items():
        expected_module = _EXPECTED_OWNER_MODULES[owner]
        assert seams, owner
        assert all(callable(seam) for seam in seams), owner
        assert all(inspect.getmodule(seam) is expected_module for seam in seams), owner


def test_r8_d_r7_reuses_exact_r4_r5_validation_owners() -> None:
    assert r7.validate_candidate_revision_state is r4.validate_candidate_revision_state
    assert r7.validate_visual_verdict_result is r5.validate_visual_verdict_result


def test_r8_d_r3_boundary_does_not_absorb_downstream_authority() -> None:
    source = inspect.getsource(r3)
    for forbidden in (
        "from cad_agent import candidate_revision",
        "from cad_agent import visual_supervisor_adapter",
        "from cad_agent import approved_repair_adapter",
        "from cad_agent import publication_composition",
    ):
        assert forbidden not in source


def _file_ipc_smoke_constructor_calls() -> list[ast.Call]:
    smoke_path = Path(__file__).with_name("test_file_ipc_live.py")
    tree = ast.parse(smoke_path.read_text(encoding="utf-8"), filename=str(smoke_path))
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id == "FileIPCLiveMCPClient":
            calls.append(node)
    return calls


def test_file_ipc_smoke_binds_explicit_canonical_ipc_root() -> None:
    """Causal RED: the historical smoke caller still omits mandatory ipc_dir."""

    calls = _file_ipc_smoke_constructor_calls()
    assert len(calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in calls[0].keywords if keyword.arg}
    assert "ipc_dir" in keywords
    root_expression = ast.unparse(keywords["ipc_dir"])
    assert root_expression in {
        "os.environ['CAD_AGENT_FILE_IPC_DIR']",
        'os.environ["CAD_AGENT_FILE_IPC_DIR"]',
    }


def _r8_d_live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_R8_D_LIVE") == "1"
        and os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and all(
            bool(os.getenv(name))
            for name in (
                "CAD_AGENT_FILE_IPC_DIR",
                "CAD_AGENT_AUTOCAD_HWND",
                "CAD_AGENT_R8_D_DISPOSABLE_DWG",
            )
        )
    )


@unittest.skipUnless(
    _r8_d_live_prerequisites_available(),
    "requires explicit R8-D disposable AutoCAD/File-IPC local gate",
)
@pytest.mark.autocad_mechanical
class R8DDisposableFileIPCPreflight(unittest.TestCase):
    def test_live_file_ipc_read_only_preflight_uses_explicit_root(self) -> None:
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        client = FileIPCLiveMCPClient(
            ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
            trigger=make_windows_dispatch_trigger(hwnd),
        )
        self.assertIsInstance(client.entity_list(), list)
