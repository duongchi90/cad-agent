"""Opt-in disposable AutoCAD Mechanical live gate for VS-T3."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import ezdxf
import pytest

from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    make_windows_dotnet_dispatch_trigger,
    normalize_windows_absolute_path,
)
from mcp_integration_lib.mcp_client import FileIPCLiveMCPClient, make_windows_dispatch_trigger, make_windows_lisp_trigger


def _enabled() -> bool:
    return all(
        os.getenv(name)
        for name in (
            "CAD_AGENT_VS_T3_LIVE",
            "CAD_AGENT_AUTOCAD_HWND",
            "CAD_AGENT_AUTOCAD_LISP_PATH",
            "CAD_AGENT_DOTNET_IPC_DIR",
        )
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(
    _enabled(),
    "requires CAD_AGENT_VS_T3_LIVE=1, AutoCAD HWND, LISP path and .NET IPC directory",
)
@pytest.mark.autocad_mechanical
class VisualEvidenceAutoCADLiveTests(unittest.TestCase):
    def test_disposable_visual_evidence_is_hash_and_dbmod_stable(self) -> None:
        test_directory = Path(tempfile.mkdtemp(prefix="cad_agent_vs_t3_live_", dir=r"C:\temp"))
        drawing_path = test_directory / "vs_t3_live.dxf"
        manifest_path = test_directory / "visual-run-manifest.json"
        try:
            drawing = ezdxf.new("R2010")
            drawing.modelspace().add_line((0, 0), (1000, 0), dxfattribs={"layer": "0"})
            drawing.saveas(drawing_path)
            drawing_sha = _sha256(drawing_path)
            run_id = "RUN-VS-T3-LIVE-001"
            mutation_sha = "3" * 64
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "visual-run-manifest-1.0",
                        "run_id": run_id,
                        "state": "DRAFT_GENERATED",
                        "authority": "DISPOSABLE_REVIEW",
                        "source": {"source_type": "PDF", "source_sha256": "1" * 64, "page_ids": ["PAGE-001"]},
                        "drawing": {"absolute_path": normalize_windows_absolute_path(str(drawing_path)), "initial_sha256": drawing_sha},
                        "evidence_root": f"runs/{run_id}",
                        "latest_mutation_sha256": mutation_sha,
                    }
                ),
                encoding="utf-8",
            )

            hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
            legacy = FileIPCLiveMCPClient(
                trigger=make_windows_dispatch_trigger(hwnd),
                raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            )
            legacy.drawing_open(str(drawing_path))
            client = DotNetIPCClient(
                ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
                trigger=make_windows_dotnet_dispatch_trigger(hwnd),
                timeout_s=30.0,
            )
            copied: dict[str, bytes] = {}

            def consume(_result, paths) -> None:
                copied.update({kind: path.read_bytes() for kind, path in paths.items()})

            result = client.visual_evidence_export(
                normalize_windows_absolute_path(str(drawing_path)),
                drawing_sha256=drawing_sha,
                run_id=run_id,
                evidence_id="EVIDENCE-001",
                region_id="SIDE-CABIN",
                latest_mutation_sha256=mutation_sha,
                visual_run_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                visual_run_manifest_path=manifest_path,
                region={
                    "model_bbox_mm": [-100, -100, 1100, 100],
                    "pixel_size": [1600, 400],
                    "background": "WHITE",
                    "include_layers": [],
                    "exclude_layers": [],
                },
                measurements=[],
                artifact_consumer=consume,
                request_id="vs-t3-live-001",
            )
            self.assertTrue(result["success"])
            self.assertFalse(result["changed"])
            self.assertEqual([], result["entity_handles"])
            self.assertEqual(drawing_sha, _sha256(drawing_path))
            payload = result["payload"]
            self.assertEqual(payload["dbmod_before"], payload["dbmod_after"])
            self.assertEqual(payload["drawing_sha256_before"], payload["drawing_sha256_after"])
            self.assertEqual(payload["session_state_sha256_before"], payload["session_state_sha256_after"])
            self.assertTrue(payload["transient_state_restored"])
            self.assertEqual({"render", "entity_map", "measurements"}, set(copied))
        finally:
            # The live gate is disposable: close without saving when the
            # prerequisite session was available, then remove its private root.
            if os.getenv("CAD_AGENT_AUTOCAD_HWND"):
                try:
                    client = locals().get("client")
                    if client is not None:
                        client.close_disposable(
                            normalize_windows_absolute_path(str(drawing_path)),
                            request_id="vs-t3-live-close",
                        )
                except Exception:
                    pass
            shutil.rmtree(test_directory, ignore_errors=True)
