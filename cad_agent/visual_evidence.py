"""Freshness validation and atomic persistence for VS-T3 evidence packages."""

from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from ctypes import wintypes
from pathlib import Path

from .visual_contracts import VisualContractError, validate_visual_contract

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CAPTURED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_MAX_BYTES = {"render": 8 * 1024 * 1024, "entity_map": 8 * 1024 * 1024, "measurements": 4 * 1024 * 1024}
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class VisualEvidenceError(ValueError):
    """Raised when VS-T3 evidence cannot be accepted or persisted."""


def _path_contains_windows_reparse_point(path: str | os.PathLike[str]) -> bool:
    """Return whether a path or existing parent is a Windows reparse point."""

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if os.name != "nt":
        return any(component.is_symlink() for component in (candidate, *candidate.parents))

    try:
        get_attributes = ctypes.windll.kernel32.GetFileAttributesW
        get_attributes.argtypes = [wintypes.LPCWSTR]
        get_attributes.restype = wintypes.DWORD
    except AttributeError:
        return candidate.is_symlink()

    components = list(candidate.parts)
    current = Path(components[0])
    for component in components[1:]:
        current /= component
        attributes = get_attributes(str(current))
        if attributes != _INVALID_FILE_ATTRIBUTES and attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    attributes = get_attributes(str(current))
    return attributes != _INVALID_FILE_ATTRIBUTES and bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def snapshot_visual_run_manifest(
    manifest_path: Path,
) -> tuple[bytes, Mapping[str, object], str]:
    """Read and validate one exact manifest byte snapshot."""

    path = Path(manifest_path)
    if _path_contains_windows_reparse_point(path):
        raise VisualEvidenceError(f"Visual Run Manifest path contains a reparse point: {path}")
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


def snapshot_dimension_register(
    register_path: Path,
) -> tuple[bytes, Mapping[str, object], str]:
    """Read and validate one exact Dimension Register byte snapshot."""

    path = Path(register_path)
    if _path_contains_windows_reparse_point(path):
        raise VisualEvidenceError(f"Dimension Register path contains a reparse point: {path}")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisualEvidenceError(f"Cannot snapshot Dimension Register: {path}") from exc
    if not isinstance(payload, Mapping):
        raise VisualEvidenceError("Dimension Register must be a JSON object")
    try:
        validated = validate_visual_contract(payload, contract="dimension_register")
    except VisualContractError as exc:
        raise VisualEvidenceError(str(exc)) from exc
    return raw, validated, hashlib.sha256(raw).hexdigest()


def assert_dimension_register_unchanged(
    register_path: Path,
    expected_raw: bytes,
    expected_digest: str,
) -> None:
    """Reject any Dimension Register byte change across evidence handoff."""

    path = Path(register_path)
    if _path_contains_windows_reparse_point(path):
        raise VisualEvidenceError("Dimension Register path contains a reparse point")
    try:
        current_raw = path.read_bytes()
    except OSError as exc:
        raise VisualEvidenceError("Cannot re-read Dimension Register") from exc
    current_digest = hashlib.sha256(current_raw).hexdigest()
    if current_raw != expected_raw or current_digest != expected_digest:
        raise VisualEvidenceError("Dimension Register changed during evidence export")


def build_dimension_register_datum_bindings(
    register: Mapping[str, object],
    *,
    datum_ids: set[str],
    run_id: str,
    region_id: str,
    manifest_sha256: str,
    register_sha256: str,
    source_sha256: str,
    allowed_page_ids: set[str],
) -> list[dict[str, str]]:
    """Create wire bindings only from confirmed, mapped register references."""

    if register.get("run_id") != run_id:
        raise VisualEvidenceError("Dimension Register run_id does not match the request")
    if register.get("source_sha256") != source_sha256:
        raise VisualEvidenceError("Dimension Register source_sha256 does not match the manifest")
    if register.get("page_id") not in allowed_page_ids:
        raise VisualEvidenceError("Dimension Register page_id is outside the manifest source scope")
    for name, value in (
        ("visual_run_manifest_sha256", manifest_sha256),
        ("dimension_register_sha256", register_sha256),
    ):
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise VisualEvidenceError(f"{name} must be a lowercase SHA-256")

    candidates: dict[str, list[tuple[str, str | None, str]]] = {datum_id: [] for datum_id in datum_ids}
    dimensions = register.get("dimensions")
    if not isinstance(dimensions, list):
        raise VisualEvidenceError("Dimension Register dimensions must be an array")
    for dimension in dimensions:
        if not isinstance(dimension, Mapping):
            raise VisualEvidenceError("Dimension Register dimension entries must be objects")
        dimension_id = dimension.get("id")
        status = dimension.get("status")
        if not isinstance(dimension_id, str) or not isinstance(status, str):
            raise VisualEvidenceError("Dimension Register dimension identity is invalid")
        for reference_name in ("from_ref", "to_ref"):
            reference = dimension.get(reference_name)
            if not isinstance(reference, Mapping) or reference.get("type") != "DATUM":
                continue
            datum_id = reference.get("id")
            if datum_id not in candidates:
                continue
            candidates[datum_id].append(
                (
                    dimension_id,
                    reference.get("entity_handle")
                    if isinstance(reference.get("entity_handle"), str)
                    else None,
                    status,
                )
            )

    bindings: list[dict[str, str]] = []
    for datum_id in sorted(datum_ids):
        matches = candidates.get(datum_id, [])
        confirmed = [match for match in matches if match[2] == "CONFIRMED"]
        if not confirmed:
            raise VisualEvidenceError(
                f"Dimension Register datum '{datum_id}' is not CONFIRMED"
            )
        mapped_confirmed = [match for match in confirmed if match[1] is not None]
        handles = {match[1] for match in mapped_confirmed}
        if not mapped_confirmed:
            raise VisualEvidenceError(
                f"Dimension Register datum '{datum_id}' has no entity_handle mapping"
            )
        if len(handles) != 1:
            raise VisualEvidenceError(
                f"Dimension Register datum '{datum_id}' has conflicting entity_handle mappings"
            )
        selected_handle = next(iter(handles))
        dimension_id = min(
            match[0] for match in mapped_confirmed if match[1] == selected_handle
        )
        bindings.append(
            {
                "id": datum_id,
                "entity_handle": selected_handle,
                "run_id": run_id,
                "region_id": region_id,
                "visual_run_manifest_sha256": manifest_sha256,
                "dimension_register_sha256": register_sha256,
                "dimension_id": dimension_id,
                "approval": "DIMENSION_REGISTER_CONFIRMED",
            }
        )
    return bindings


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


def sha256_file(path: Path) -> str:
    """Hash the exact current bytes of one drawing file."""

    candidate = Path(path)
    if _path_contains_windows_reparse_point(candidate) or not candidate.is_file():
        raise VisualEvidenceError(f"drawing path is not a regular file: {candidate}")
    try:
        with candidate.open("rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()
    except OSError as exc:
        raise VisualEvidenceError(f"Cannot hash drawing file: {candidate}") from exc


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
    *,
    drawing_path: Path,
    drawing_sha256_before_dispatch: str,
) -> Path:
    """Copy verified request artifacts and atomically create one evidence package."""

    raw_manifest, manifest, manifest_hash = snapshot_visual_run_manifest(manifest_path)
    expected_drawing_path = manifest["drawing"]["absolute_path"]  # type: ignore[index]
    if not _same_windows_path(drawing_path, expected_drawing_path):
        raise VisualEvidenceError("drawing path does not match the Visual Run Manifest")
    if not _SHA256.fullmatch(drawing_sha256_before_dispatch):
        raise VisualEvidenceError("drawing pre-dispatch hash must be a lowercase SHA-256")
    if sha256_file(Path(drawing_path)) != drawing_sha256_before_dispatch:
        raise VisualEvidenceError("drawing changed before evidence promotion started")
    validated = validate_visual_evidence_freshness(
        evidence_result,
        manifest_hash,
        manifest,
        drawing_sha256_before_dispatch,
    )
    payload = validated.get("payload") if isinstance(validated.get("payload"), Mapping) else validated
    if not isinstance(payload, Mapping) or payload.get("evidence_id") != evidence_id:
        raise VisualEvidenceError("evidence_id does not match the requested destination")
    artifact_paths = validated.get("_artifact_paths")
    if not isinstance(artifact_paths, Mapping):
        raise VisualEvidenceError("verified request artifact paths are required")

    # Re-read exact bytes immediately before any final destination is created.
    if _path_contains_windows_reparse_point(manifest_path):
        raise VisualEvidenceError("Visual Run Manifest path contains a reparse point")
    if _path_contains_windows_reparse_point(drawing_path):
        raise VisualEvidenceError("drawing path contains a reparse point")
    current_raw = Path(manifest_path).read_bytes()
    if current_raw != raw_manifest:
        raise VisualEvidenceError("Visual Run Manifest changed before evidence promotion")
    if sha256_file(Path(drawing_path)) != drawing_sha256_before_dispatch:
        raise VisualEvidenceError("drawing changed before evidence promotion")

    run_id = str(payload["run_id"])
    region_id = str(payload["region_id"])
    base = Path(evidence_root)
    if _path_contains_windows_reparse_point(base):
        raise VisualEvidenceError("evidence root contains a reparse point")
    if base.name == run_id:
        destination = base / "iterations" / region_id / f"evidence-{evidence_id}"
    else:
        destination = base / run_id / "iterations" / region_id / f"evidence-{evidence_id}"
    destination = destination.resolve()
    if _path_contains_windows_reparse_point(destination.parent):
        raise VisualEvidenceError("evidence destination parent contains a reparse point")
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
            if _path_contains_windows_reparse_point(source) or not source.is_file():
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
        if sha256_file(Path(drawing_path)) != drawing_sha256_before_dispatch:
            raise VisualEvidenceError("drawing changed during evidence promotion")
        if destination.exists():
            raise VisualEvidenceError("evidence destination already exists")
        os.rename(temporary, destination)
        return destination
    except Exception:
        _remove_tree_if_safe(temporary)
        raise


PUBLICATION_FILE_SNAPSHOT_SCHEMA_VERSION = "publication-file-snapshot-1.0"
_PUBLICATION_FILE_PREPARED_SCHEMA_VERSION = "publication-file-prepared-1.0"
_PUBLICATION_FILE_RESULT_SCHEMA_VERSION = "publication-file-result-1.0"
_PUBLICATION_FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PUBLICATION_FILE_STATES = {"PREPARED", "PUBLISHED", "RESTORED"}


class PublicationFileError(ValueError):
    """Categorical, privacy-safe failure for generic publication-file operations."""


def _publication_file_error(category: str) -> PublicationFileError:
    return PublicationFileError(category)


def _publication_file_sha(value: object) -> str:
    if type(value) is not str or _PUBLICATION_FILE_SHA256.fullmatch(value) is None:
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    return value


def _publication_file_path(value: object) -> Path:
    if not isinstance(value, Path):
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    if not value.is_absolute():
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    return value


def _publication_file_reparse(path: Path) -> bool:
    try:
        return _path_contains_windows_reparse_point(path) or path.is_symlink()
    except (OSError, ValueError):
        return True


def _publication_file_original_path(value: object) -> Path:
    path = _publication_file_path(value)
    if _publication_file_reparse(path):
        raise _publication_file_error("PUBLICATION_FILE_REPARSE")
    return path


def _publication_file_resolve_checked(path: Path) -> Path:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        raise _publication_file_error("PUBLICATION_FILE_INVALID") from None
    if _publication_file_reparse(resolved):
        raise _publication_file_error("PUBLICATION_FILE_REPARSE")
    return resolved


def _publication_file_identity(stat_result: os.stat_result) -> tuple[int, int, int]:
    values = (stat_result.st_dev, stat_result.st_ino, stat_result.st_size)
    if any(type(value) is not int for value in values):
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    return values


def _publication_file_snapshot(path: Path) -> tuple[dict[str, object], bytes]:
    original = _publication_file_original_path(path)
    candidate = _publication_file_resolve_checked(original)
    try:
        before = os.stat(candidate)
        identity_before = _publication_file_identity(before)
        if not os.path.isfile(candidate):
            raise _publication_file_error("PUBLICATION_FILE_INVALID")
        with candidate.open("rb") as stream:
            data = stream.read()
        after = os.stat(candidate)
        identity_after = _publication_file_identity(after)
    except PublicationFileError:
        raise
    except (OSError, ValueError):
        raise _publication_file_error("PUBLICATION_FILE_INVALID") from None
    if identity_before != identity_after:
        raise _publication_file_error("PUBLICATION_FILE_STALE")
    snapshot = {
        "schema_version": PUBLICATION_FILE_SNAPSHOT_SCHEMA_VERSION,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": identity_after[2],
        "device_id": identity_after[0],
        "file_id": identity_after[1],
    }
    return snapshot, data


def _validate_publication_file_snapshot(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "sha256", "size_bytes", "device_id", "file_id"
    }:
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    if type(value["schema_version"]) is not str or value["schema_version"] != PUBLICATION_FILE_SNAPSHOT_SCHEMA_VERSION:
        raise _publication_file_error("PUBLICATION_FILE_INVALID")
    sha = _publication_file_sha(value["sha256"])
    for name in ("size_bytes", "device_id", "file_id"):
        if type(value[name]) is not int or value[name] < 0:
            raise _publication_file_error("PUBLICATION_FILE_INVALID")
    return {
        "schema_version": PUBLICATION_FILE_SNAPSHOT_SCHEMA_VERSION,
        "sha256": sha,
        "size_bytes": value["size_bytes"],
        "device_id": value["device_id"],
        "file_id": value["file_id"],
    }


def snapshot_publication_file(path: Path) -> dict[str, object]:
    """Return a closed identity/hash snapshot for one safe regular file."""

    snapshot, _ = _publication_file_snapshot(path)
    return snapshot


def _publication_file_read_verified(path: Path, expected: Mapping[str, object]) -> bytes:
    expected_snapshot = _validate_publication_file_snapshot(expected)
    observed, data = _publication_file_snapshot(path)
    if observed != expected_snapshot:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    return data


def _publication_file_prepared(value: object) -> dict[str, object]:
    required = {
        "schema_version", "state", "target_path", "candidate_path", "backup_path", "stage_path",
        "target_snapshot", "candidate_snapshot", "backup_snapshot", "stage_snapshot",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    if type(value["schema_version"]) is not str or value["schema_version"] != _PUBLICATION_FILE_PREPARED_SCHEMA_VERSION:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    if value["state"] not in _PUBLICATION_FILE_STATES:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    path_names = ("target_path", "candidate_path", "backup_path", "stage_path")
    originals = {name: _publication_file_original_path(value[name]) for name in path_names}
    paths = {name: _publication_file_resolve_checked(originals[name]) for name in path_names}
    snapshots = {name: _validate_publication_file_snapshot(value[f"{name}_snapshot"]) for name in ("target", "candidate", "backup", "stage")}
    if paths["target_path"].parent != paths["candidate_path"].parent or paths["target_path"].parent != paths["backup_path"].parent or paths["target_path"].parent != paths["stage_path"].parent:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    if len(set(paths.values())) != 4:
        raise _publication_file_error("PUBLICATION_FILE_ALIAS")
    return {"schema_version": _PUBLICATION_FILE_PREPARED_SCHEMA_VERSION, "state": value["state"], **paths, **{f"{name}_snapshot": snapshot for name, snapshot in snapshots.items()}}


def _publication_file_assert_expected(value: object, expected: str) -> None:
    if _publication_file_sha(expected) != _validate_publication_file_snapshot(value)["sha256"]:
        raise _publication_file_error("PUBLICATION_FILE_STALE")


def prepare_publication_replacement(
    *,
    target_path: Path,
    candidate_path: Path,
    expected_target_sha256: str,
    expected_candidate_sha256: str,
) -> dict[str, object]:
    """Stage a verified candidate beside an existing target without replacing it."""

    expected_target = _publication_file_sha(expected_target_sha256)
    expected_candidate = _publication_file_sha(expected_candidate_sha256)
    original_target = _publication_file_original_path(target_path)
    original_candidate = _publication_file_original_path(candidate_path)
    target = _publication_file_resolve_checked(original_target)
    candidate = _publication_file_resolve_checked(original_candidate)
    if target.parent != candidate.parent:
        raise _publication_file_error("PUBLICATION_FILE_ALIAS")
    target_snapshot, target_data = _publication_file_snapshot(target)
    candidate_snapshot, candidate_data = _publication_file_snapshot(candidate)
    if target_snapshot["sha256"] != expected_target or candidate_snapshot["sha256"] != expected_candidate:
        raise _publication_file_error("PUBLICATION_FILE_STALE")
    try:
        if os.path.samefile(target, candidate):
            raise _publication_file_error("PUBLICATION_FILE_ALIAS")
    except FileNotFoundError:
        raise _publication_file_error("PUBLICATION_FILE_INVALID") from None
    backup = target.parent / f".{target.name}.publication-backup-{uuid.uuid4().hex}.tmp"
    stage = target.parent / f".{target.name}.publication-stage-{uuid.uuid4().hex}.tmp"
    created: list[Path] = []
    try:
        for path, data in ((backup, target_data), (stage, candidate_data)):
            with path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            created.append(path)
        backup_snapshot, _ = _publication_file_snapshot(backup)
        stage_snapshot, _ = _publication_file_snapshot(stage)
        if backup_snapshot["sha256"] != target_snapshot["sha256"] or stage_snapshot["sha256"] != candidate_snapshot["sha256"]:
            raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    except PublicationFileError:
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        raise
    except (OSError, ValueError):
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        raise _publication_file_error("PUBLICATION_STAGE_INVALID") from None
    return {
        "schema_version": _PUBLICATION_FILE_PREPARED_SCHEMA_VERSION,
        "state": "PREPARED",
        "target_path": target,
        "candidate_path": candidate,
        "backup_path": backup,
        "stage_path": stage,
        "target_snapshot": target_snapshot,
        "candidate_snapshot": candidate_snapshot,
        "backup_snapshot": backup_snapshot,
        "stage_snapshot": stage_snapshot,
    }


def commit_publication_replacement(
    prepared: Mapping[str, object], *,
    expected_target_sha256: str,
    expected_candidate_sha256: str,
) -> dict[str, object]:
    """Atomically replace the target after revalidating every prepared identity."""

    record = _publication_file_prepared(prepared)
    if record["state"] != "PREPARED":
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    target = record["target_path"]
    candidate = record["candidate_path"]
    target_snapshot, _ = _publication_file_snapshot(target)
    candidate_snapshot, _ = _publication_file_snapshot(candidate)
    if target_snapshot != record["target_snapshot"] or candidate_snapshot != record["candidate_snapshot"]:
        raise _publication_file_error("PUBLICATION_FILE_STALE")
    if target_snapshot["sha256"] != _publication_file_sha(expected_target_sha256) or candidate_snapshot["sha256"] != _publication_file_sha(expected_candidate_sha256):
        raise _publication_file_error("PUBLICATION_FILE_STALE")
    backup_snapshot, _ = _publication_file_snapshot(record["backup_path"])
    stage_snapshot, _ = _publication_file_snapshot(record["stage_path"])
    if backup_snapshot != record["backup_snapshot"] or stage_snapshot != record["stage_snapshot"]:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    try:
        os.replace(record["stage_path"], target)
    except (OSError, ValueError):
        raise _publication_file_error("PUBLICATION_REPLACE_FAILED") from None
    try:
        # Two reads make a post-replace verifier failure observable without restoring blindly.
        observed_hash = sha256_file(target)
        observed_hash_again = sha256_file(target)
        if observed_hash != candidate_snapshot["sha256"] or observed_hash_again != candidate_snapshot["sha256"]:
            raise _publication_file_error("PUBLICATION_VERIFY_FAILED")
        final_snapshot, _ = _publication_file_snapshot(target)
    except PublicationFileError:
        raise
    except (OSError, ValueError):
        raise _publication_file_error("PUBLICATION_VERIFY_FAILED") from None
    if final_snapshot["sha256"] != candidate_snapshot["sha256"]:
        raise _publication_file_error("PUBLICATION_VERIFY_FAILED")
    return {
        "schema_version": _PUBLICATION_FILE_RESULT_SCHEMA_VERSION,
        "state": "PUBLISHED",
        "initial_sha256": target_snapshot["sha256"],
        "published_sha256": final_snapshot["sha256"],
        "backup_sha256": backup_snapshot["sha256"],
    }


def restore_publication_target(
    prepared: Mapping[str, object], *,
    expected_current_sha256: str,
) -> dict[str, object]:
    """Restore the verified original target over one exact published hash."""

    record = _publication_file_prepared(prepared)
    if record["state"] not in {"PREPARED", "PUBLISHED"}:
        raise _publication_file_error("PUBLICATION_RESTORE_FAILED")
    expected_current = _publication_file_sha(expected_current_sha256)
    target_snapshot, _ = _publication_file_snapshot(record["target_path"])
    if target_snapshot["sha256"] != expected_current:
        raise _publication_file_error("PUBLICATION_RECOVERY_CONFLICT")
    backup_snapshot, backup_data = _publication_file_snapshot(record["backup_path"])
    if backup_snapshot != record["backup_snapshot"] or backup_snapshot["sha256"] != record["target_snapshot"]["sha256"]:
        raise _publication_file_error("PUBLICATION_STAGE_INVALID")
    restore_stage = record["target_path"].parent / f".{record['target_path'].name}.publication-restore-{uuid.uuid4().hex}.tmp"
    try:
        with restore_stage.open("xb") as stream:
            stream.write(backup_data)
            stream.flush()
            os.fsync(stream.fileno())
        restore_snapshot, _ = _publication_file_snapshot(restore_stage)
        if restore_snapshot["sha256"] != record["target_snapshot"]["sha256"]:
            raise _publication_file_error("PUBLICATION_RESTORE_FAILED")
        current_again, _ = _publication_file_snapshot(record["target_path"])
        if current_again["sha256"] != expected_current:
            raise _publication_file_error("PUBLICATION_RECOVERY_CONFLICT")
        os.replace(restore_stage, record["target_path"])
        final_snapshot, _ = _publication_file_snapshot(record["target_path"])
        if final_snapshot["sha256"] != record["target_snapshot"]["sha256"]:
            raise _publication_file_error("PUBLICATION_RESTORE_FAILED")
    except PublicationFileError:
        try:
            if restore_stage.exists():
                restore_stage.unlink()
        except OSError:
            pass
        raise
    except (OSError, ValueError):
        try:
            if restore_stage.exists():
                restore_stage.unlink()
        except OSError:
            pass
        raise _publication_file_error("PUBLICATION_RESTORE_FAILED") from None
    return {
        "schema_version": _PUBLICATION_FILE_RESULT_SCHEMA_VERSION,
        "state": "RESTORED",
        "restored_sha256": final_snapshot["sha256"],
        "previous_sha256": expected_current,
    }


def cleanup_publication_replacement(prepared: Mapping[str, object]) -> None:
    """Delete only the exact owner-created stage files from a prepared record."""

    record = _publication_file_prepared(prepared)
    for name in ("backup_path", "stage_path"):
        path = record[name]
        if path.parent != record["target_path"].parent or path in {record["target_path"], record["candidate_path"]}:
            raise _publication_file_error("PUBLICATION_CLEANUP_FAILED")
        try:
            if _publication_file_reparse(path):
                raise _publication_file_error("PUBLICATION_CLEANUP_FAILED")
            if path.exists():
                current, _ = _publication_file_snapshot(path)
                if current != record[name.replace("_path", "_snapshot")]:
                    raise _publication_file_error("PUBLICATION_CLEANUP_FAILED")
                path.unlink()
        except PublicationFileError:
            raise
        except (OSError, ValueError):
            raise _publication_file_error("PUBLICATION_CLEANUP_FAILED") from None


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
    if isinstance(left, Path):
        left = str(left)
    if isinstance(right, Path):
        right = str(right)
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
    if not path.exists() or _path_contains_windows_reparse_point(path):
        return
    for child in path.iterdir():
        if _path_contains_windows_reparse_point(child):
            return
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            _remove_tree_if_safe(child)
    path.rmdir()


__all__ = [
    "PUBLICATION_FILE_SNAPSHOT_SCHEMA_VERSION",
    "PublicationFileError",
    "VisualEvidenceError",
    "assert_dimension_register_unchanged",
    "build_dimension_register_datum_bindings",
    "canonical_region_config_sha256",
    "sha256_file",
    "snapshot_publication_file",
    "prepare_publication_replacement",
    "commit_publication_replacement",
    "restore_publication_target",
    "cleanup_publication_replacement",
    "snapshot_dimension_register",
    "snapshot_visual_run_manifest",
    "validate_visual_evidence_freshness",
    "write_visual_evidence",
]
