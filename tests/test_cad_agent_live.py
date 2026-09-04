from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from cad_agent import live as live_module
from cad_agent.live import (
    LiveSafetyError,
    _backup,
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


def test_backup_acquisition_failure_removes_partial_owned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        write_build_evidence(evidence, _build(dxf))
        original_copy = live_module._copy_to_exclusive_backup
        copy_count = 0

        def fail_second_copy(
            source, destination, owned_paths
        ):  # type: ignore[no-untyped-def]
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected evidence backup failure")
            return original_copy(source, destination, owned_paths)

        monkeypatch.setattr(
            "cad_agent.live._copy_to_exclusive_backup", fail_second_copy
        )

        with pytest.raises(LiveSafetyError, match="backup|cleanup"):
            _backup(dxf, evidence, root / "backups")

        assert list((root / "backups").iterdir()) == []


def test_backup_rejects_raced_linked_destination_without_external_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        write_build_evidence(evidence, _build(dxf))

        backups = root / "backups"
        backups.mkdir()
        external = root / "outside.bin"
        external.write_bytes(b"outside sentinel")
        linked_destination = backups / "staged.raced.dxf"
        os.link(external, linked_destination)
        evidence_destination = backups / "evidence.raced.json"

        monkeypatch.setattr(
            "cad_agent.live._backup_paths",
            lambda *_args: (linked_destination, evidence_destination),
        )

        with pytest.raises(LiveSafetyError, match="backup|destination|regular|zero"):
            _backup(dxf, evidence, backups)

        assert external.read_bytes() == b"outside sentinel"
        assert linked_destination.exists()


def test_backup_cleanup_does_not_unlink_replaced_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        write_build_evidence(evidence, _build(dxf))

        backups = root / "backups"
        backups.mkdir()
        external = root / "outside.bin"
        external.write_bytes(b"outside sentinel")
        dxf_destination = backups / "staged.raced.dxf"
        evidence_destination = backups / "evidence.raced.json"
        monkeypatch.setattr(
            "cad_agent.live._backup_paths",
            lambda *_args: (dxf_destination, evidence_destination),
        )
        original_assert = live_module._assert_backup_path_identity

        def replace_then_reject(path, opened_stat):  # type: ignore[no-untyped-def]
            if path == dxf_destination:
                path.unlink()
                os.link(external, path)
            original_assert(path, opened_stat)

        monkeypatch.setattr(
            "cad_agent.live._assert_backup_path_identity", replace_then_reject
        )

        with pytest.raises(LiveSafetyError, match="cleanup|survivors"):
            _backup(dxf, evidence, backups)

        assert external.read_bytes() == b"outside sentinel"
        assert dxf_destination.exists()


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
        assert report["backup"]["verified"] is True
        assert (
            report["backup"]["dxf_source_sha256"]
            == report["backup"]["dxf_backup_sha256"]
        )
        assert (
            report["backup"]["build_evidence_source_sha256"]
            == report["backup"]["build_evidence_backup_sha256"]
        )
        assert json.loads(evidence.read_text(encoding="utf-8"))["build_result"]["handle_by_primitive_id"]


class _BrokenRepairClient(FakeMCPClient):
    def entity_create_line(self, x1, y1, x2, y2, layer=None):  # type: ignore[no-untyped-def]
        return self._create("LINE", layer, {"start": (x1, y1), "end": (99.0, y2)})


class _CloseFailureClient(_BrokenRepairClient):
    def drawing_close(self, save_changes: bool = False) -> None:
        return None


@dataclass
class _FakeRepairResult:
    repaired_count: int = 0
    skipped_count: int = 0
    repaired_primitive_ids: list[str] = field(default_factory=list)
    skipped_primitive_ids: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def test_failed_second_review_does_not_save_and_reopens_canonical_dxf() -> None:
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
        assert client.closed_without_save is True
        assert report["rollback_state"] == "failed_canonical_restored"
        assert client.opened_path == str(dxf)
        assert report["rollback_restore"]["canonical_document_open"] is True


def test_failed_second_review_restores_canonical_dxf_and_build_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        build = _build(dxf)
        write_build_evidence(evidence, build)
        dxf_before = dxf.read_bytes()
        evidence_before = evidence.read_bytes()
        client = _BrokenRepairClient(fail_entity_get=False)
        client.preload_entity("A", "LINE", "0", {"start": (0.0, 0.0), "end": (99.0, 0.0)})

        def mutate_canonical_files(*_args: object, **_kwargs: object) -> _FakeRepairResult:
            dxf.write_bytes(b"mutated staged dxf")
            evidence.write_bytes(b"mutated build evidence")
            return _FakeRepairResult(repaired_count=1)

        monkeypatch.setattr("cad_agent.live.repair_dxf_live", mutate_canonical_files)

        report = repair_live(build, client, dxf, evidence, root / "backups", "change-42")

        assert report["save_state"] == "not_saved"
        assert report["rollback_state"] == "failed_canonical_restored"
        assert client.opened_path == str(dxf)
        assert dxf.read_bytes() == dxf_before
        assert evidence.read_bytes() == evidence_before
        assert load_build_evidence(evidence, dxf).output_path == str(dxf)


def test_rollback_failure_is_terminal_non_pass() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        build = _build(dxf)
        write_build_evidence(evidence, build)
        client = _CloseFailureClient(fail_entity_get=False)
        client.preload_entity(
            "A",
            "LINE",
            "0",
            {"start": (0.0, 0.0), "end": (99.0, 0.0)},
        )

        with pytest.raises(LiveSafetyError, match="rollback|recovery"):
            repair_live(
                build,
                client,
                dxf,
                evidence,
                root / "backups",
                "change-42",
            )


def test_corrupt_backup_aborts_before_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        dxf = root / "staged.dxf"
        dxf.write_bytes(b"staged dxf")
        evidence = root / "build-evidence.json"
        build = _build(dxf)
        write_build_evidence(evidence, build)
        client = _mismatched_client()
        original_copyfileobj = live_module.shutil.copyfileobj

        def corrupting_copyfileobj(
            source, destination, *args, **kwargs
        ):  # type: ignore[no-untyped-def]
            result = original_copyfileobj(source, destination, *args, **kwargs)
            destination.seek(0)
            destination.write(b"corrupt")
            destination.flush()
            return result

        monkeypatch.setattr(
            "cad_agent.live.shutil.copyfileobj", corrupting_copyfileobj
        )

        with pytest.raises(LiveSafetyError, match="backup verification"):
            repair_live(build, client, dxf, evidence, root / "backups", "change-42")

        assert "A" in client._entities
        assert len(client._entities) == 1
        assert list((root / "backups").iterdir()) == []
