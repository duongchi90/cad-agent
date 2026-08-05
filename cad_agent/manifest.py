"""Durable, atomic manifests for deterministic staged runs."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cad_agent.source_bundle import SourceBundleError, source_bundle_sha256, validate_source_bundle


STAGE_NAMES = ("primitive_ir", "semantic_ir", "dxf")
MANIFEST_NAME = "run-manifest.json"
SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION = "source-bundle-reference-1.0"
_SOURCE_BUNDLE_REFERENCE_FIELDS = {
    "schema_version",
    "bundle_id",
    "run_id",
    "source_bundle_sha256",
    "item_count",
}
_SOURCE_BUNDLE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SOURCE_BUNDLE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DRAFT_REFERENCE_FIELDS: dict[str, object] = {
    "release_profile": "DRAFT_REFERENCE",
    "authoritative_release_eligible": False,
    "drawing_setup_evidence": None,
}


class ManifestError(ValueError):
    """Raised when an on-disk run manifest cannot safely be used."""


def validate_source_bundle_reference(value: object) -> dict[str, object]:
    """Return a normalized closed SourceBundle reference or fail closed."""
    if not isinstance(value, Mapping):
        raise ManifestError("SourceBundle reference must be a mapping.")
    missing = sorted(_SOURCE_BUNDLE_REFERENCE_FIELDS - set(value))
    unexpected = sorted((key for key in value if key not in _SOURCE_BUNDLE_REFERENCE_FIELDS), key=str)
    if missing:
        raise ManifestError(f"SourceBundle reference missing required fields: {', '.join(missing)}")
    if unexpected:
        names = ", ".join(str(key) for key in unexpected)
        raise ManifestError(f"SourceBundle reference has unsupported fields: {names}")
    if value["schema_version"] != SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION:
        raise ManifestError("SourceBundle reference has an unsupported schema_version.")
    for field in ("bundle_id", "run_id"):
        identifier = value[field]
        if not isinstance(identifier, str) or not _SOURCE_BUNDLE_IDENTIFIER_RE.fullmatch(identifier):
            raise ManifestError(f"SourceBundle reference has an invalid {field}.")
    digest = value["source_bundle_sha256"]
    if not isinstance(digest, str) or not _SOURCE_BUNDLE_SHA256_RE.fullmatch(digest):
        raise ManifestError("SourceBundle reference has an invalid source_bundle_sha256.")
    item_count = value["item_count"]
    if isinstance(item_count, bool) or not isinstance(item_count, int) or not 1 <= item_count <= 10_000:
        raise ManifestError("SourceBundle reference has an invalid item_count.")
    return {
        "schema_version": SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION,
        "bundle_id": value["bundle_id"],
        "run_id": value["run_id"],
        "source_bundle_sha256": digest,
        "item_count": item_count,
    }


def _source_bundle_reference(source_bundle: object) -> dict[str, object]:
    try:
        normalized = validate_source_bundle(source_bundle)
        reference = {
            "schema_version": SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION,
            "bundle_id": normalized["bundle_id"],
            "run_id": normalized["run_id"],
            "source_bundle_sha256": source_bundle_sha256(normalized),
            "item_count": len(normalized["items"]),
        }
    except SourceBundleError as exc:
        raise ManifestError(f"SourceBundle validation failed: {exc}") from exc
    return validate_source_bundle_reference(reference)


def bind_source_bundle(manifest: Mapping[str, object], source_bundle: object) -> dict[str, Any]:
    """Return a copied manifest bound to one validated SourceBundle."""
    if not isinstance(manifest, Mapping):
        raise ManifestError("Manifest must be a mapping.")
    reference = _source_bundle_reference(source_bundle)
    bound = copy.deepcopy(dict(manifest))
    if "source_bundle" in bound:
        existing = validate_source_bundle_reference(bound["source_bundle"])
        if existing != reference:
            raise ManifestError("source_bundle binding conflict")
        bound["source_bundle"] = existing
    else:
        bound["source_bundle"] = reference
    return bound


def require_source_bundle_match(manifest: Mapping[str, object], source_bundle: object) -> None:
    """Fail when the optional manifest reference does not match the bundle."""
    if not isinstance(manifest, Mapping):
        raise ManifestError("Manifest must be a mapping.")
    if "source_bundle" not in manifest:
        raise ManifestError("Manifest has no source_bundle binding.")
    existing = validate_source_bundle_reference(manifest["source_bundle"])
    reference = _source_bundle_reference(source_bundle)
    if existing != reference:
        raise ManifestError("SourceBundle reference does not match supplied SourceBundle.")


def classify_draft_reference(manifest: dict[str, Any]) -> dict[str, Any]:
    """Apply safe legacy defaults and reject authoritative release claims."""
    for name, expected in _DRAFT_REFERENCE_FIELDS.items():
        actual = manifest.get(name, expected)
        if actual != expected:
            raise ManifestError(f"Legacy run manifest has unsafe {name}.")
    manifest.update(_DRAFT_REFERENCE_FIELDS)
    return manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def new_manifest(source: Path, scale_mm_per_px: float, approval: str) -> dict[str, Any]:
    return classify_draft_reference({
        "schema_version": "1.0",
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "image"},
        "configuration": {"scale_mm_per_px": scale_mm_per_px},
        "approvals": {"calibration": {"approved": True, "reference": approval}},
        "stages": {
            stage: {"state": "pending", "artifact": None, "sha256": None, "details": None}
            for stage in STAGE_NAMES
        },
    })


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
    if "source_bundle" in payload:
        payload["source_bundle"] = validate_source_bundle_reference(payload["source_bundle"])
    return classify_draft_reference(payload)


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
