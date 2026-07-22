from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cad_agent.live import (
    LiveSafetyError,
    load_build_evidence,
    repair_live,
    write_build_evidence,
)
from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.mcp_client import FakeMCPClient


def _build(path: Path) -> BuildResult:
    return BuildResult(
        output_path=str(path),
        handle_by_primitive_id={"line-1": "A"},
        layer_by_primitive_id={"line-1": "0"},
        written_geometry_by_primitive_id={
            "line-1": {"type": "line", "start": [0.0, 0.0], "end": [10.0, 0.0]}
        },
        entity_count=1,
    )


def _mismatched_client() -> FakeMCPClient:
    client = FakeMCPClient(fail_entity_get=False)
    client.preload_entity("A", "LINE", "0", {"start": (0.0, 0.0), "end": (99.0, 0.0)})
    return client


def test_build_evidence_round_trips_and_binds_dxf_hash() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        write_build_evidence(evidence, _build(dxf))

        loaded = load_build_evidence(evidence, dxf)

        assert loaded.handle_by_primitive_id == {"line-1": "A"}
        assert loaded.written_geometry_by_primitive_id["line-1"]["end"] == [10.0, 0.0]


def test_repair_requires_approval_before_backup_or_mutation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        write_build_evidence(evidence, _build(dxf))

        with pytest.raises(LiveSafetyError, match="approval"):
            repair_live(_build(dxf), _mismatched_client(), dxf, evidence, root / "backups", "")

        assert not (root / "backups").exists()


def test_repair_creates_backup_saves_only_after_second_review_passes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        build = _build(dxf)
        write_build_evidence(evidence, build)

        report = repair_live(
            build, _mismatched_client(), dxf, evidence, root / "backups", "change-42"
        )

        assert report["save_state"] == "saved"
        assert report["repair"]["repaired_count"] == 1
        assert report["after_review"]["passed"] is True
        assert Path(report["backup"]["dxf_path"]).is_file()
        assert Path(report["backup"]["build_evidence_path"]).is_file()
        assert json.loads(evidence.read_text(encoding="utf-8"))["build_result"]["handle_by_primitive_id"]


class _BrokenRepairClient(FakeMCPClient):
    def entity_create_line(self, x1, y1, x2, y2, layer=None):  # type: ignore[no-untyped-def]
        return self._create("LINE", layer, {"start": (x1, y1), "end": (99.0, y2)})


def test_failed_second_review_does_not_save_and_reopens_backup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        build = _build(dxf)
        write_build_evidence(evidence, build)
        client = _BrokenRepairClient(fail_entity_get=False)
        client.preload_entity("A", "LINE", "0", {"start": (0.0, 0.0), "end": (99.0, 0.0)})

        report = repair_live(build, client, dxf, evidence, root / "backups", "change-42")

        assert report["save_state"] == "not_saved"
        assert report["after_review"]["passed"] is False
        assert client.opened_path == report["backup"]["dxf_path"]
