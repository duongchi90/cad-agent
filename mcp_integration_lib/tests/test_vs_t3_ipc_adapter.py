from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest

from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    DotNetIPCTimeoutError,
    atomic_write_json,
    result_path,
    scavenge_visual_evidence_artifacts,
)


REGION = {
    "model_bbox_mm": [0, 0, 2400, 2200],
    "pixel_size": [1600, 1200],
    "background": "WHITE",
    "include_layers": ["CABIN"],
    "exclude_layers": [],
}


def _write_valid_artifacts(ipc_dir: Path, request_id: str, *, unsafe: bool = False) -> dict[str, Any]:
    root = ipc_dir / "artifacts" / request_id
    root.mkdir(parents=True)
    contents = {
        "render": b"png-bytes",
        "entity_map": b"[]",
        "measurements": b"[]",
    }
    descriptors: list[dict[str, Any]] = []
    names = {
        "render": "cad-render.png",
        "entity_map": "entities.json",
        "measurements": "measurements.json",
    }
    mime_types = {"render": "image/png", "entity_map": "application/json", "measurements": "application/json"}
    for kind, data in contents.items():
        (root / names[kind]).write_bytes(data)
        relative = f"artifacts/{request_id}/{names[kind]}"
        if unsafe and kind == "render":
            relative = f"artifacts/{request_id}/../escape.png"
        descriptors.append(
            {
                "artifact_id": f"{kind}:{names[kind]}",
                "kind": kind,
                "relative_path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_length": len(data),
                "mime_type": mime_types[kind],
                **({"width": 1600, "height": 1200} if kind == "render" else {}),
            }
        )
    return {
        "run_id": "RUN-001",
        "evidence_id": "EVIDENCE-001",
        "region_id": "SIDE-CABIN",
        "drawing_sha256_before": "a" * 64,
        "drawing_sha256_after": "a" * 64,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "latest_mutation_sha256": "b" * 64,
        "visual_run_manifest_sha256": "c" * 64,
        "region_config_sha256": "d" * 64,
        "session_state_sha256_before": "e" * 64,
        "session_state_sha256_after": "e" * 64,
        "transient_state_restored": True,
        "captured_at_utc": "2026-08-04T12:00:00.000Z",
        "artifacts": descriptors,
    }


class VisualEvidenceIPCAdapterTests(unittest.TestCase):
    def _client(self, ipc_dir: Path, trigger, *, request_id: str = "vs-t3-001", timeout_s: float = 1.0) -> DotNetIPCClient:
        return DotNetIPCClient(
            ipc_dir=ipc_dir,
            trigger=trigger,
            timeout_s=timeout_s,
            poll_interval_s=0.01,
            request_id_factory=lambda: request_id,
        )

    def _kwargs(self) -> dict[str, Any]:
        return {
            "drawing_full_path": r"C:\drawings\sample.dwg",
            "drawing_sha256": "a" * 64,
            "run_id": "RUN-001",
            "evidence_id": "EVIDENCE-001",
            "region_id": "SIDE-CABIN",
            "latest_mutation_sha256": "b" * 64,
            "visual_run_manifest_sha256": "c" * 64,
            "region": REGION,
            "measurements": [],
            "datum_bindings": [],
        }

    def test_sends_existing_root_envelope_and_hands_off_verified_artifacts(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            handed_off: dict[str, bytes] = {}

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                self.assertEqual("visual_evidence_export", request["operation"])
                self.assertEqual("a" * 64, request["drawing_sha256"])
                self.assertIn("latest_mutation_sha256", request["parameters"])
                self.assertNotIn("latest_mutation_sha256", request)
                payload = _write_valid_artifacts(ipc_dir, request["request_id"])
                atomic_write_json(
                    result_path(ipc_dir, request["request_id"]),
                    {
                        "request_id": request["request_id"],
                        "success": True,
                        "operation": request["operation"],
                        "drawing_full_path": request["drawing_full_path"],
                        "changed": False,
                        "entity_handles": [],
                        "warnings": [],
                        "errors": [],
                        "started_at": "2026-08-04T12:00:00Z",
                        "completed_at": "2026-08-04T12:00:00Z",
                        "payload": payload,
                    },
                )

            def consume(_result: Mapping[str, Any], paths: Mapping[str, Path]) -> None:
                handed_off.update({kind: path.read_bytes() for kind, path in paths.items()})

            result = self._client(ipc_dir, trigger).visual_evidence_export(
                **self._kwargs(),
                artifact_consumer=consume,
            )
            self.assertEqual("EVIDENCE-001", result["payload"]["evidence_id"])
            self.assertEqual({"render", "entity_map", "measurements"}, set(handed_off))
            self.assertFalse((ipc_dir / "artifacts" / "vs-t3-001").exists())

    def test_rejects_unsafe_descriptor_and_cleans_request_artifacts(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)

            def trigger() -> None:
                request_file = next(ipc_dir.glob("cadagent_dotnet_request_*.json"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
                payload = _write_valid_artifacts(ipc_dir, request["request_id"], unsafe=True)
                atomic_write_json(
                    result_path(ipc_dir, request["request_id"]),
                    {
                        "request_id": request["request_id"],
                        "success": True,
                        "operation": request["operation"],
                        "drawing_full_path": request["drawing_full_path"],
                        "changed": False,
                        "entity_handles": [],
                        "warnings": [],
                        "errors": [],
                        "started_at": "2026-08-04T12:00:00Z",
                        "completed_at": "2026-08-04T12:00:00Z",
                        "payload": payload,
                    },
                )

            with self.assertRaisesRegex(Exception, "unsafe|request-owned"):
                self._client(ipc_dir, trigger).visual_evidence_export(
                    **self._kwargs(),
                    artifact_consumer=lambda _result, _paths: None,
                )
            self.assertFalse((ipc_dir / "artifacts" / "vs-t3-001").exists())

    def test_timeout_leaves_an_active_lease_for_scavenger(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            lease_path = ipc_dir / "artifacts" / "vs-t3-001" / "active.lease"
            lease_stream = None

            def trigger() -> None:
                nonlocal lease_stream
                lease_path.parent.mkdir(parents=True)
                lease_stream = lease_path.open("xb")
                lease_stream.write(b"active")
                lease_stream.flush()

            try:
                with self.assertRaises(DotNetIPCTimeoutError):
                    self._client(ipc_dir, trigger, timeout_s=0.05).visual_evidence_export(
                        **self._kwargs(),
                        artifact_consumer=lambda _result, _paths: None,
                    )
                self.assertTrue(lease_path.exists())
            finally:
                if lease_stream is not None:
                    lease_stream.close()

    def test_success_requires_an_artifact_handoff_consumer(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            with self.assertRaisesRegex(ValueError, "artifact_consumer"):
                self._client(ipc_dir, lambda: None).visual_evidence_export(**self._kwargs())

    def test_scavenger_removes_only_stale_lease_free_directories(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            artifacts = ipc_dir / "artifacts"
            artifacts.mkdir()
            stale = artifacts / "stale-request"
            fresh = artifacts / "fresh-request"
            active = artifacts / "active-request"
            for root in (stale, fresh, active):
                root.mkdir()
                (root / "entities.json").write_bytes(b"[]")
            now = 2_000_000_000.0
            old = now - 25 * 60 * 60
            os.utime(stale, (old, old))
            os.utime(fresh, (now - 60, now - 60))
            os.utime(active, (old, old))
            with (active / "active.lease").open("xb") as lease_stream:
                lease_stream.write(b"held")
                lease_stream.flush()
                if os.name == "nt":
                    import msvcrt

                    lease_stream.seek(0)
                    msvcrt.locking(lease_stream.fileno(), msvcrt.LK_NBLCK, 1)
                removed = scavenge_visual_evidence_artifacts(ipc_dir, now=now)

            self.assertEqual(("stale-request",), removed)
            self.assertFalse(stale.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(active.exists())


if __name__ == "__main__":
    unittest.main()
