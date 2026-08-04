"""Freshness validation and atomic persistence for VS-T3 evidence packages."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path

from .visual_contracts import VisualContractError, validate_visual_contract

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CAPTURED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_MAX_BYTES = {"render": 8 * 1024 * 1024, "entity_map": 8 * 1024 * 1024, "measurements": 4 * 1024 * 1024}


class VisualEvidenceError(ValueError):
    """Raised when VS-T3 evidence cannot be accepted or persisted."""


def snapshot_visual_run_manifest(
    manifest_path: Path,
) -> tuple[bytes, Mapping[str, object], str]:
    """Read and validate one exact manifest byte snapshot."""

    path = Path(manifest_path)
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisualEvidenceError(f"Cannot snapshot Visual Run Manifest: {path}") from exc
    if not isinstance(payload, Mapping):
        raise VisualEvidenceError("Visual Run Manifest must be a JSON object")
    try:
        validated = validate_visual_contract(payload, contract="visual_run_manifest")
    except VisualContractError as exc:
        raise VisualEvidenceError(str(exc)) from exc
    return raw, validated, hashlib.sha256(raw).hexdigest()


def canonical_region_config_sha256(
    region_config: Mapping[str, object],
) -> str:
    """Hash a canonical region object without changing array order."""

    if not isinstance(region_config, Mapping):
        raise VisualEvidenceError("region configuration must be an object")
    try:
        encoded = json.dumps(
            region_config,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VisualEvidenceError("region configuration is not canonicalizable") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_visual_evidence_freshness(
    evidence: Mapping[str, object],
    manifest_bytes_sha256: str,
    manifest: Mapping[str, object],
    drawing_sha256_before_dispatch: str,
) -> Mapping[str, object]:
    """Validate result identity and no-change invariants against one manifest snapshot."""

    if not isinstance(evidence, Mapping):
        raise VisualEvidenceError("visual evidence result must be an object")
    if not _SHA256.fullmatch(manifest_bytes_sha256):
        raise VisualEvidenceError("manifest byte hash must be a lowercase SHA-256")
    if not _SHA256.fullmatch(drawing_sha256_before_dispatch):
        raise VisualEvidenceError("drawing pre-dispatch hash must be a lowercase SHA-256")
    try:
        validated_manifest = validate_visual_contract(manifest, contract="visual_run_manifest")
    except VisualContractError as exc:
        raise VisualEvidenceError(str(exc)) from exc

    root = evidence
    payload = evidence.get("payload") if isinstance(evidence.get("payload"), Mapping) else evidence
    if not isinstance(payload, Mapping):
        raise VisualEvidenceError("visual evidence payload must be an object")
    if "payload" in root:
        if root.get("operation") != "visual_evidence_export" or root.get("success") is not True:
            raise VisualEvidenceError("only a successful visual_evidence_export result can be accepted")
        if root.get("changed") is not False or root.get("entity_handles") != []:
            raise VisualEvidenceError("visual evidence result is not read-only")
        drawing_path = root.get("drawing_full_path")
        expected_path = validated_manifest["drawing"]["absolute_path"]  # type: ignore[index]
        if not _same_windows_path(drawing_path, expected_path):
            raise VisualEvidenceError("visual evidence drawing path does not match the manifest")

    required = {
        "run_id",
        "evidence_id",
        "region_id",
        "drawing_sha256_before",
        "drawing_sha256_after",
        "dbmod_before",
        "dbmod_after",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "region_config_sha256",
        "session_state_sha256_before",
        "session_state_sha256_after",
        "transient_state_restored",
        "captured_at_utc",
        "artifacts",
    }
    if set(payload) != required:
        raise VisualEvidenceError("visual evidence payload must be closed")
    run_id = payload["run_id"]
    if run_id != validated_manifest["run_id"]:
        raise VisualEvidenceError("visual evidence run_id does not match the manifest")
    for name in ("run_id", "evidence_id", "region_id"):
        if not isinstance(payload[name], str) or not _IDENTIFIER.fullmatch(payload[name]):
            raise VisualEvidenceError(f"visual evidence {name} is invalid")
    for name in (
        "drawing_sha256_before",
        "drawing_sha256_after",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "region_config_sha256",
        "session_state_sha256_before",
        "session_state_sha256_after",
    ):
        if not isinstance(payload[name], str) or not _SHA256.fullmatch(payload[name]):
            raise VisualEvidenceError(f"visual evidence {name} is invalid")
    if payload["drawing_sha256_before"] != drawing_sha256_before_dispatch:
        raise VisualEvidenceError("visual evidence drawing pre-dispatch hash does not match")
    if payload["drawing_sha256_before"] != payload["drawing_sha256_after"]:
        raise VisualEvidenceError("drawing hash changed during evidence capture")
    if payload["latest_mutation_sha256"] != validated_manifest["latest_mutation_sha256"]:
        raise VisualEvidenceError("visual evidence is stale against latest_mutation_sha256")
    if payload["visual_run_manifest_sha256"] != manifest_bytes_sha256:
        raise VisualEvidenceError("visual run manifest byte hash does not match")
    if payload["dbmod_before"] != payload["dbmod_after"]:
        raise VisualEvidenceError("DBMOD changed during evidence capture")
    if payload["session_state_sha256_before"] != payload["session_state_sha256_after"]:
        raise VisualEvidenceError("session state changed during evidence capture")
    if payload["transient_state_restored"] is not True:
        raise VisualEvidenceError("transient AutoCAD state was not restored")
    if not isinstance(payload["captured_at_utc"], str) or not _CAPTURED_AT.fullmatch(payload["captured_at_utc"]):
        raise VisualEvidenceError("captured_at_utc must be RFC3339 UTC")

    _validate_artifact_descriptors(payload["artifacts"])
    return copy.deepcopy(dict(evidence))


def write_visual_evidence(
    evidence_root: Path,
    evidence_result: Mapping[str, object],
    manifest_path: Path,
    evidence_id: str,
) -> Path:
    """Copy verified request artifacts and atomically create one evidence package."""

    raw_manifest, manifest, manifest_hash = snapshot_visual_run_manifest(manifest_path)
    drawing_hash = manifest["drawing"]["initial_sha256"]  # type: ignore[index]
    validated = validate_visual_evidence_freshness(
        evidence_result,
        manifest_hash,
        manifest,
        drawing_hash,
    )
    payload = validated.get("payload") if isinstance(validated.get("payload"), Mapping) else validated
    if not isinstance(payload, Mapping) or payload.get("evidence_id") != evidence_id:
        raise VisualEvidenceError("evidence_id does not match the requested destination")
    artifact_paths = validated.get("_artifact_paths")
    if not isinstance(artifact_paths, Mapping):
        raise VisualEvidenceError("verified request artifact paths are required")

    # Re-read exact bytes immediately before any final destination is created.
    current_raw = Path(manifest_path).read_bytes()
    if current_raw != raw_manifest:
        raise VisualEvidenceError("Visual Run Manifest changed before evidence promotion")

    run_id = str(payload["run_id"])
    region_id = str(payload["region_id"])
    base = Path(evidence_root)
    if base.name == run_id:
        destination = base / "iterations" / region_id / f"evidence-{evidence_id}"
    else:
        destination = base / run_id / "iterations" / region_id / f"evidence-{evidence_id}"
    destination = destination.resolve()
    if destination.exists():
        raise VisualEvidenceError("evidence destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.mkdir()
        copied_artifacts: list[dict[str, object]] = []
        for artifact in payload["artifacts"]:  # type: ignore[union-attr]
            kind = str(artifact["kind"])
            source = Path(artifact_paths[kind])
            if source.is_symlink() or not source.is_file():
                raise VisualEvidenceError(f"artifact source is unsafe or missing: {source}")
            data = source.read_bytes()
            if len(data) != artifact["byte_length"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                raise VisualEvidenceError(f"artifact bytes do not match descriptor: {kind}")
            target_name = {"render": "cad-render.png", "entity_map": "entities.json", "measurements": "measurements.json"}[kind]
            (temporary / target_name).write_bytes(data)
            copied_artifacts.append({**dict(artifact), "relative_path": target_name})

        final_payload = dict(payload)
        final_payload["artifacts"] = copied_artifacts
        final_payload.pop("_artifact_paths", None)
        _write_json_new(temporary / "render-manifest.json", {"artifacts": copied_artifacts})
        _write_json_new(temporary / "evidence-manifest.json", final_payload)
        if Path(manifest_path).read_bytes() != raw_manifest:
            raise VisualEvidenceError("Visual Run Manifest changed during evidence promotion")
        if destination.exists():
            raise VisualEvidenceError("evidence destination already exists")
        os.rename(temporary, destination)
        return destination
    except Exception:
        _remove_tree_if_safe(temporary)
        raise


def _validate_artifact_descriptors(artifacts: object) -> None:
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise VisualEvidenceError("visual evidence must contain exactly three artifacts")
    kinds: set[str] = set()
    total = 0
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise VisualEvidenceError("artifact descriptor must be an object")
        required = {"artifact_id", "kind", "relative_path", "sha256", "byte_length", "mime_type"}
        if set(artifact).difference(required | {"width", "height"}) or not required.issubset(artifact):
            raise VisualEvidenceError("artifact descriptor must be closed")
        kind = artifact["kind"]
        if kind not in _MAX_BYTES or kind in kinds:
            raise VisualEvidenceError("artifact kinds must be unique and supported")
        kinds.add(kind)
        if not isinstance(artifact["relative_path"], str) or not _safe_relative_path(artifact["relative_path"]):
            raise VisualEvidenceError("artifact path is unsafe")
        if not isinstance(artifact["sha256"], str) or not _SHA256.fullmatch(artifact["sha256"]):
            raise VisualEvidenceError("artifact hash is invalid")
        size = artifact["byte_length"]
        if type(size) is not int or not 1 <= size <= _MAX_BYTES[kind]:
            raise VisualEvidenceError("artifact byte length exceeds its kind limit")
        expected_mime = "image/png" if kind == "render" else "application/json"
        if artifact["mime_type"] != expected_mime:
            raise VisualEvidenceError("artifact MIME type is invalid")
        total += size
    if kinds != set(_MAX_BYTES) or total > _MAX_TOTAL_BYTES:
        raise VisualEvidenceError("artifact set is incomplete or exceeds total size")


def _safe_relative_path(value: str) -> bool:
    parts = value.replace("\\", "/").split("/")
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts) and not re.match(r"^[A-Za-z]:", value)


def _same_windows_path(left: object, right: object) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return os.path.normcase(os.path.normpath(left.replace("/", "\\"))) == os.path.normcase(
        os.path.normpath(right.replace("/", "\\"))
    )


def _write_json_new(path: Path, value: object) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _remove_tree_if_safe(path: Path) -> None:
    if not path.exists() or path.is_symlink():
        return
    for child in path.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            _remove_tree_if_safe(child)
    path.rmdir()


__all__ = [
    "VisualEvidenceError",
    "canonical_region_config_sha256",
    "snapshot_visual_run_manifest",
    "validate_visual_evidence_freshness",
    "write_visual_evidence",
]
