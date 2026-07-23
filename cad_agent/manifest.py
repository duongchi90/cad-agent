"""Durable, atomic manifests for deterministic staged runs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


STAGE_NAMES = ("primitive_ir", "semantic_ir", "dxf")
MANIFEST_NAME = "run-manifest.json"


class ManifestError(ValueError):
    """Raised when an on-disk run manifest cannot safely be used."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def new_manifest(source: Path, scale_mm_per_px: float, approval: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "image"},
        "configuration": {"scale_mm_per_px": scale_mm_per_px},
        "approvals": {"calibration": {"approved": True, "reference": approval}},
        "stages": {
            stage: {"state": "pending", "artifact": None, "sha256": None, "details": None}
            for stage in STAGE_NAMES
        },
    }


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read run manifest: {path}") from exc
    if payload.get("schema_version") != "1.0":
        raise ManifestError("Unsupported run manifest schema version.")
    if not isinstance(payload.get("source"), dict) or not isinstance(payload.get("stages"), dict):
        raise ManifestError("Run manifest is missing source or stage records.")
    for stage in STAGE_NAMES:
        if stage not in payload["stages"]:
            raise ManifestError(f"Run manifest is missing the {stage!r} stage.")
    return payload


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_source(manifest: dict[str, Any], source: Path) -> None:
    if not source.is_file():
        raise ManifestError(f"Input image does not exist: {source}")
    expected = manifest["source"].get("sha256")
    if not isinstance(expected, str) or sha256_file(source) != expected:
        raise ManifestError("Input SHA-256 does not match the run manifest; resume is refused.")


def completed_artifact(output_dir: Path, stage: dict[str, Any]) -> bool:
    artifact = stage.get("artifact")
    digest = stage.get("sha256")
    if stage.get("state") != "completed" or not isinstance(artifact, str) or not isinstance(digest, str):
        return False
    path = output_dir / artifact
    return path.is_file() and sha256_file(path) == digest
