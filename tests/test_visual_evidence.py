from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from cad_agent.visual_evidence import (
    VisualEvidenceError,
    canonical_region_config_sha256,
    snapshot_visual_run_manifest,
    validate_visual_evidence_freshness,
    write_visual_evidence,
)
from tests.visual_supervisor_fixtures import (
    MUTATION_SHA,
    REGION_ID,
    RUN_ID,
    valid_visual_run_manifest,
)


REGION = {
    "model_bbox_mm": [0, 0, 2400, 2200],
    "pixel_size": [1600, 1200],
    "background": "WHITE",
    "include_layers": ["CABIN"],
    "exclude_layers": [],
}


def _evidence(artifact_paths: dict[str, Path], drawing_path: Path, drawing_sha: str) -> dict[str, object]:
    data = {
        "render": artifact_paths["render"].read_bytes(),
        "entity_map": artifact_paths["entity_map"].read_bytes(),
        "measurements": artifact_paths["measurements"].read_bytes(),
    }
    names = {"render": "cad-render.png", "entity_map": "entities.json", "measurements": "measurements.json"}
    mimes = {"render": "image/png", "entity_map": "application/json", "measurements": "application/json"}
    artifacts = [
        {
            "artifact_id": f"{kind}:{names[kind]}",
            "kind": kind,
            "relative_path": f"artifacts/REQ-001/{names[kind]}",
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_length": len(content),
            "mime_type": mimes[kind],
            **({"width": 1600, "height": 1200} if kind == "render" else {}),
        }
        for kind, content in data.items()
    ]
    payload = {
        "run_id": RUN_ID,
        "evidence_id": "EVIDENCE-001",
        "region_id": REGION_ID,
        "drawing_sha256_before": drawing_sha,
        "drawing_sha256_after": drawing_sha,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "latest_mutation_sha256": MUTATION_SHA,
        "visual_run_manifest_sha256": "pending",
        "region_config_sha256": canonical_region_config_sha256(REGION),
        "session_state_sha256_before": "4" * 64,
        "session_state_sha256_after": "4" * 64,
        "transient_state_restored": True,
        "captured_at_utc": "2026-08-04T12:00:00.000Z",
        "artifacts": artifacts,
    }
    return {
        "request_id": "REQ-001",
        "success": True,
        "operation": "visual_evidence_export",
        "drawing_full_path": str(drawing_path),
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [],
        "started_at": "2026-08-04T12:00:00Z",
        "completed_at": "2026-08-04T12:00:00Z",
        "payload": payload,
        "_artifact_paths": artifact_paths,
    }


def _prepare(tmp: Path) -> tuple[Path, dict[str, object], dict[str, Path], Path, str]:
    drawing_path = tmp / "drawing.dwg"
    drawing_path.write_bytes(b"current drawing")
    drawing_sha = hashlib.sha256(drawing_path.read_bytes()).hexdigest()
    manifest_payload = valid_visual_run_manifest()
    manifest_payload["drawing"]["absolute_path"] = str(drawing_path)  # type: ignore[index]
    manifest = tmp / "manifest.json"
    manifest.write_text(json.dumps(manifest_payload, sort_keys=True), encoding="utf-8")
    paths = {}
    for kind, name, data in (
        ("render", "cad-render.png", b"png"),
        ("entity_map", "entities.json", b"[]"),
        ("measurements", "measurements.json", b"[]"),
    ):
        path = tmp / name
        path.write_bytes(data)
        paths[kind] = path
    raw, validated, digest = snapshot_visual_run_manifest(manifest)
    evidence = _evidence(paths, drawing_path, drawing_sha)
    evidence["payload"]["visual_run_manifest_sha256"] = digest  # type: ignore[index]
    return manifest, evidence, paths, drawing_path, drawing_sha


def test_manifest_snapshot_hashes_exact_bytes_and_validates_contract() -> None:
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "manifest.json"
        raw = json.dumps(valid_visual_run_manifest(), sort_keys=True).encode("utf-8")
        path.write_bytes(raw)
        actual, manifest, digest = snapshot_visual_run_manifest(path)
        assert actual == raw
        assert manifest["latest_mutation_sha256"] == MUTATION_SHA
        assert digest == hashlib.sha256(raw).hexdigest()


def test_region_hash_is_stable_for_object_property_order() -> None:
    assert canonical_region_config_sha256({"b": 2, "a": [1, 2]}) == canonical_region_config_sha256(
        {"a": [1, 2], "b": 2}
    )


def test_freshness_rejects_manifest_byte_hash_and_mutation_mismatch() -> None:
    with TemporaryDirectory() as temporary:
        manifest_path, evidence, _, drawing_path, drawing_sha = _prepare(Path(temporary))
        raw, manifest, digest = snapshot_visual_run_manifest(manifest_path)
        with pytest.raises(VisualEvidenceError, match="byte hash"):
            validate_visual_evidence_freshness(evidence, "0" * 64, manifest, drawing_sha)
        evidence["payload"]["latest_mutation_sha256"] = "9" * 64  # type: ignore[index]
        with pytest.raises(VisualEvidenceError, match="stale"):
            validate_visual_evidence_freshness(evidence, digest, manifest, drawing_sha)


def test_manifest_byte_race_is_rejected_and_no_destination_is_created() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path, evidence, paths, drawing_path, drawing_sha = _prepare(root)
        raw, manifest, digest = snapshot_visual_run_manifest(manifest_path)
        evidence["payload"]["visual_run_manifest_sha256"] = digest  # type: ignore[index]
        # Change bytes without changing latest_mutation_sha256.
        manifest_path.write_text(json.dumps({**manifest, "state": "REPAIRING"}), encoding="utf-8")
        with pytest.raises(VisualEvidenceError, match="byte hash"):
            write_visual_evidence(
                root / "runs",
                evidence,
                manifest_path,
                "EVIDENCE-001",
                drawing_path=drawing_path,
                drawing_sha256_before_dispatch=drawing_sha,
            )
        assert not (root / "runs" / RUN_ID / "iterations" / REGION_ID / "evidence-EVIDENCE-001").exists()


def test_writer_promotes_once_and_refuses_overwrite() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path, evidence, paths, drawing_path, drawing_sha = _prepare(root)
        destination = write_visual_evidence(
            root / "runs",
            evidence,
            manifest_path,
            "EVIDENCE-001",
            drawing_path=drawing_path,
            drawing_sha256_before_dispatch=drawing_sha,
        )
        assert destination.is_dir()
        assert (destination / "cad-render.png").read_bytes() == b"png"
        assert (destination / "evidence-manifest.json").is_file()
        with pytest.raises(VisualEvidenceError, match="already exists"):
            write_visual_evidence(
                root / "runs",
                evidence,
                manifest_path,
                "EVIDENCE-001",
                drawing_path=drawing_path,
                drawing_sha256_before_dispatch=drawing_sha,
            )


def test_writer_rejects_drawing_changed_after_result_before_atomic_promote() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest_path, evidence, _, drawing_path, drawing_sha = _prepare(root)
        with patch(
            "cad_agent.visual_evidence.sha256_file",
            side_effect=[drawing_sha, drawing_sha, "f" * 64],
        ):
            with pytest.raises(VisualEvidenceError, match="drawing changed"):
                write_visual_evidence(
                    root / "runs",
                    evidence,
                    manifest_path,
                    "EVIDENCE-001",
                    drawing_path=drawing_path,
                    drawing_sha256_before_dispatch=drawing_sha,
                )
        assert not (root / "runs" / RUN_ID / "iterations" / REGION_ID / "evidence-EVIDENCE-001").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point regression")
def test_manifest_snapshot_rejects_a_junction_component() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / "target"
        junction = root / "junction"
        target.mkdir()
        (target / "manifest.json").write_text(
            json.dumps(valid_visual_run_manifest(), sort_keys=True),
            encoding="utf-8",
        )
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(f"mklink /J unavailable: {result.stderr.strip()}")
        with pytest.raises(VisualEvidenceError, match="reparse point"):
            snapshot_visual_run_manifest(junction / "manifest.json")
