"""Safety boundary for AutoCAD Mechanical File IPC review and repair."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
import stat
import shutil
from pathlib import Path
from typing import Any

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import LiveReviewResult, review_dxf_live

from .manifest import sha256_file


BUILD_EVIDENCE_SCHEMA_VERSION = "1.0"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class LiveSafetyError(ValueError):
    """Raised when a live drawing operation cannot meet its safety contract."""


def _normalized_document_path(path: str | Path) -> str:
    return ntpath.normpath(str(path).replace("/", "\\")).casefold()


def _build_result_dict(build: BuildResult) -> dict[str, Any]:
    return {
        "output_path": build.output_path,
        "handle_by_primitive_id": build.handle_by_primitive_id,
        "layer_by_primitive_id": build.layer_by_primitive_id,
        "written_geometry_by_primitive_id": build.written_geometry_by_primitive_id,
        "skipped_primitive_ids": build.skipped_primitive_ids,
        "entity_count": build.entity_count,
        "dimension_count": build.dimension_count,
        "dimension_handle_by_cross_validation_id": (
            build.dimension_handle_by_cross_validation_id
        ),
        "written_dimension_by_cross_validation_id": (
            build.written_dimension_by_cross_validation_id
        ),
        "component_handle_by_part_id": build.component_handle_by_part_id,
        "component_type_by_part_id": build.component_type_by_part_id,
        "skipped_part_ids": build.skipped_part_ids,
        "skipped_part_reasons": build.skipped_part_reasons,
        "component_count": build.component_count,
        "written_component_by_part_id": build.written_component_by_part_id,
    }


def _build_result_from_dict(payload: dict[str, Any]) -> BuildResult:
    try:
        return BuildResult(**payload)
    except TypeError as exc:
        raise LiveSafetyError("Build evidence has an invalid BuildResult payload.") from exc


def write_build_evidence(path: Path, build: BuildResult) -> None:
    dxf = Path(build.output_path)
    if not dxf.is_file():
        raise LiveSafetyError(f"Staged DXF does not exist: {dxf}")
    payload = {
        "schema_version": BUILD_EVIDENCE_SCHEMA_VERSION,
        "dxf": {"name": dxf.name, "sha256": sha256_file(dxf)},
        "build_result": _build_result_dict(build),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_build_evidence(path: Path, dxf: Path) -> BuildResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveSafetyError(f"Cannot read build evidence: {path}") from exc
    if payload.get("schema_version") != BUILD_EVIDENCE_SCHEMA_VERSION:
        raise LiveSafetyError("Unsupported build evidence schema version.")
    if not dxf.is_file():
        raise LiveSafetyError(f"DXF does not exist: {dxf}")
    expected = payload.get("dxf", {}).get("sha256")
    if not isinstance(expected, str) or sha256_file(dxf) != expected:
        raise LiveSafetyError("DXF SHA-256 does not match build evidence; live operation is refused.")
    build = _build_result_from_dict(payload.get("build_result", {}))
    build.output_path = str(dxf)
    return build


def review_dict(review: LiveReviewResult) -> dict[str, Any]:
    return asdict(review)


def write_live_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _backup_paths(dxf: Path, evidence: Path, backup_dir: Path) -> tuple[Path, Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in range(1000):
        label = stamp if suffix == 0 else f"{stamp}-{suffix:03d}"
        dxf_backup = backup_dir / f"{dxf.stem}.{label}{dxf.suffix}"
        evidence_backup = backup_dir / f"{evidence.stem}.{label}{evidence.suffix}"
        if not dxf_backup.exists() and not evidence_backup.exists():
            return dxf_backup, evidence_backup
    raise LiveSafetyError("Could not allocate a unique backup path.")


def _is_regular_non_reparse(stat_result: os.stat_result) -> bool:
    return stat.S_ISREG(stat_result.st_mode) and not bool(
        getattr(stat_result, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _is_single_link_regular_non_reparse(stat_result: os.stat_result) -> bool:
    return _is_regular_non_reparse(stat_result) and getattr(stat_result, "st_nlink", 1) == 1


def _assert_path_identity(
    path: Path, opened_stat: os.stat_result, *, label: str
) -> None:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise LiveSafetyError(f"{label} identity could not be verified.") from exc
    if not _is_single_link_regular_non_reparse(path_stat) or not os.path.samestat(
        opened_stat, path_stat
    ):
        raise LiveSafetyError(
            f"{label} must remain the same single-link regular non-reparse file."
        )


def _assert_backup_path_identity(path: Path, opened_stat: os.stat_result) -> None:
    _assert_path_identity(path, opened_stat, label="Backup destination")


def _copy_to_exclusive_backup(
    source: Path,
    destination: Path,
    owned_paths: dict[Path, os.stat_result | None],
) -> str:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise LiveSafetyError(
            "Backup destination must be a new regular non-reparse file."
        ) from exc

    owned_paths[destination] = None
    try:
        opened_stat = os.fstat(descriptor)
        if not _is_regular_non_reparse(opened_stat):
            raise LiveSafetyError("Backup destination is not a regular file.")
        owned_paths[destination] = opened_stat
        with source.open("rb") as source_handle, os.fdopen(
            descriptor, "w+b"
        ) as destination_handle:
            descriptor = -1
            shutil.copyfileobj(source_handle, destination_handle)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
            destination_handle.seek(0)
            digest = hashlib.sha256()
            for chunk in iter(lambda: destination_handle.read(1024 * 1024), b""):
                digest.update(chunk)
        _assert_backup_path_identity(destination, opened_stat)
        return digest.hexdigest()
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _cleanup_backup_artifacts(
    paths: tuple[Path, Path], owned_paths: dict[Path, os.stat_result | None]
) -> None:
    cleanup_failures: list[Path] = []
    for path, opened_stat in owned_paths.items():
        if opened_stat is None:
            cleanup_failures.append(path)
            continue
        try:
            path_stat = os.stat(path, follow_symlinks=False)
            if not _is_regular_non_reparse(path_stat) or not os.path.samestat(
                opened_stat, path_stat
            ):
                cleanup_failures.append(path)
                continue
            path.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
        except OSError:
            cleanup_failures.append(path)
    survivors = [
        path
        for path in owned_paths
        if path.exists() or path.is_symlink()
    ]
    if cleanup_failures or survivors:
        raise LiveSafetyError(
            "Backup acquisition cleanup failed; zero owned survivors cannot be proven."
        )


def _backup(dxf: Path, evidence: Path, backup_dir: Path) -> dict[str, Any]:
    dxf_backup, evidence_backup = _backup_paths(dxf, evidence, backup_dir)
    backup_paths = (dxf_backup, evidence_backup)
    owned_paths: dict[Path, os.stat_result | None] = {}
    try:
        dxf_source_before = sha256_file(dxf)
        evidence_source_before = sha256_file(evidence)
        dxf_backup_hash = _copy_to_exclusive_backup(dxf, dxf_backup, owned_paths)
        evidence_backup_hash = _copy_to_exclusive_backup(
            evidence, evidence_backup, owned_paths
        )
        dxf_source_after = sha256_file(dxf)
        evidence_source_after = sha256_file(evidence)
        verified = (
            dxf_source_before == dxf_source_after == dxf_backup_hash
            and evidence_source_before == evidence_source_after == evidence_backup_hash
        )
        if not verified:
            raise LiveSafetyError(
                "Production backup verification failed; repair is refused before mutation."
            )
        return {
            "dxf_path": str(dxf_backup),
            "dxf_source_sha256": dxf_source_before,
            "dxf_backup_sha256": dxf_backup_hash,
            "build_evidence_path": str(evidence_backup),
            "build_evidence_source_sha256": evidence_source_before,
            "build_evidence_backup_sha256": evidence_backup_hash,
            "verified": True,
        }
    except Exception as exc:
        try:
            _cleanup_backup_artifacts(backup_paths, owned_paths)
        except LiveSafetyError as cleanup_exc:
            raise LiveSafetyError(
                "backup acquisition failed; cleanup could not prove zero survivors."
            ) from cleanup_exc
        if isinstance(exc, LiveSafetyError):
            raise exc
        raise LiveSafetyError(
            "backup acquisition failed; zero owned survivors were proven."
        ) from exc


def _open_bound_file(path: Path, *, flags: int, label: str) -> tuple[int, os.stat_result]:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise LiveSafetyError(f"{label} identity could not be verified.") from exc
    if not _is_single_link_regular_non_reparse(path_stat):
        raise LiveSafetyError(
            f"{label} must be a single-link regular non-reparse file."
        )

    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened_stat = os.fstat(descriptor)
        if (
            not _is_single_link_regular_non_reparse(opened_stat)
            or not os.path.samestat(path_stat, opened_stat)
        ):
            raise LiveSafetyError(f"{label} identity changed while opening.")
        _assert_path_identity(path, opened_stat, label=label)
        return descriptor, opened_stat
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _sha256_open_file(handle: Any) -> str:
    handle.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    handle.seek(0)
    return digest.hexdigest()


def _open_restore_pair(
    stack: ExitStack,
    source: Path,
    destination: Path,
    *,
    expected_backup_sha256: str,
    destination_label: str,
) -> tuple[Any, Any, os.stat_result, os.stat_result]:
    binary = getattr(os, "O_BINARY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    source_fd, source_stat = _open_bound_file(
        source,
        flags=os.O_RDONLY | binary | no_follow,
        label="Rollback backup source",
    )
    source_handle = stack.enter_context(os.fdopen(source_fd, "rb"))
    destination_fd, destination_stat = _open_bound_file(
        destination,
        flags=os.O_RDWR | binary | no_follow,
        label=destination_label,
    )
    destination_handle = stack.enter_context(os.fdopen(destination_fd, "r+b"))
    source_sha256 = _sha256_open_file(source_handle)
    if source_sha256 != expected_backup_sha256:
        raise LiveSafetyError("Rollback backup integrity verification failed.")
    return source_handle, destination_handle, source_stat, destination_stat


def _restore_bound_file(
    source: Path,
    destination: Path,
    *,
    source_handle: Any,
    destination_handle: Any,
    source_stat: os.stat_result,
    destination_stat: os.stat_result,
    expected_destination_sha256: str,
) -> str:
    _assert_path_identity(source, source_stat, label="Rollback backup source")
    _assert_path_identity(destination, destination_stat, label="Rollback destination")
    source_handle.seek(0)
    os.ftruncate(destination_handle.fileno(), 0)
    shutil.copyfileobj(source_handle, destination_handle)
    destination_handle.flush()
    os.fsync(destination_handle.fileno())
    restored_sha256 = _sha256_open_file(destination_handle)
    if restored_sha256 != expected_destination_sha256:
        raise LiveSafetyError("Canonical rollback restoration verification failed.")
    _assert_path_identity(source, source_stat, label="Rollback backup source")
    _assert_path_identity(destination, destination_stat, label="Rollback destination")
    return restored_sha256


def _restore_canonical(
    *,
    client: Any,
    dxf: Path,
    evidence_path: Path,
    backup: dict[str, Any],
) -> dict[str, Any]:
    """Restore verified backup bytes and reopen the canonical staged artifact."""

    backup_dxf = Path(backup["dxf_path"])
    backup_evidence = Path(backup["build_evidence_path"])
    open_paths_before_restore = {
        _normalized_document_path(path)
        for path in client.drawing_list_open_paths()
    }
    canonical_path = _normalized_document_path(dxf)
    if canonical_path in open_paths_before_restore:
        raise LiveSafetyError(
            "Rollback document close verification failed: the modified "
            "canonical staged DXF is still open."
        )

    with ExitStack() as stack:
        dxf_pair = _open_restore_pair(
            stack,
            backup_dxf,
            dxf,
            expected_backup_sha256=backup["dxf_backup_sha256"],
            destination_label="Rollback destination",
        )
        evidence_pair = _open_restore_pair(
            stack,
            backup_evidence,
            evidence_path,
            expected_backup_sha256=backup["build_evidence_backup_sha256"],
            destination_label="Rollback destination",
        )
        dxf_sha256 = _restore_bound_file(
            backup_dxf,
            dxf,
            source_handle=dxf_pair[0],
            destination_handle=dxf_pair[1],
            source_stat=dxf_pair[2],
            destination_stat=dxf_pair[3],
            expected_destination_sha256=backup["dxf_source_sha256"],
        )
        evidence_sha256 = _restore_bound_file(
            backup_evidence,
            evidence_path,
            source_handle=evidence_pair[0],
            destination_handle=evidence_pair[1],
            source_stat=evidence_pair[2],
            destination_stat=evidence_pair[3],
            expected_destination_sha256=backup["build_evidence_source_sha256"],
        )

    client.drawing_open(str(dxf))
    open_paths = {
        _normalized_document_path(path)
        for path in client.drawing_list_open_paths()
    }
    backup_path = _normalized_document_path(backup_dxf)
    if canonical_path not in open_paths or backup_path in open_paths:
        raise LiveSafetyError(
            "Rollback document verification failed: the canonical staged DXF "
            "is not the only restored document open."
        )
    load_build_evidence(evidence_path, dxf)
    return {
        "dxf_path": str(dxf),
        "dxf_sha256": dxf_sha256,
        "build_evidence_path": str(evidence_path),
        "build_evidence_sha256": evidence_sha256,
        "canonical_document_open": True,
    }


def review_live(build: BuildResult, client: Any, dxf: Path) -> LiveReviewResult:
    build.output_path = str(dxf)
    return review_dxf_live(build, client, open_drawing=True)


def _attest_saved_candidate(
    build: BuildResult,
    client: Any,
    dxf: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    """Reopen and revalidate the exact persisted candidate before PASS."""
    expected_path = _normalized_document_path(dxf)
    try:
        client.drawing_close(save_changes=False)
        client.drawing_open(str(dxf))
        open_paths = {
            _normalized_document_path(path)
            for path in client.drawing_list_open_paths()
        }
    except Exception as exc:
        raise LiveSafetyError(
            "POST_SAVE_REOPEN_FAILED: persisted candidate could not be rebound."
        ) from exc

    if expected_path not in open_paths:
        raise LiveSafetyError(
            "POST_SAVE_TARGET_NOT_OPEN: persisted candidate is not the open target."
        )

    active_path = getattr(client, "_active_drawing_path", None)
    if active_path is None:
        active_path = getattr(client, "opened_path", None)
    if active_path is not None and _normalized_document_path(active_path) != expected_path:
        raise LiveSafetyError(
            "POST_SAVE_ACTIVE_TARGET_MISMATCH: active drawing is not the persisted candidate."
        )

    try:
        variables = client.drawing_get_variables(["DWGPREFIX", "DWGNAME"])
    except Exception as exc:
        raise LiveSafetyError(
            "POST_SAVE_IDENTITY_READ_FAILED: active drawing identity could not be read."
        ) from exc
    prefix = variables.get("DWGPREFIX")
    name = variables.get("DWGNAME")
    if isinstance(prefix, str) and isinstance(name, str) and prefix and name:
        variable_path = _normalized_document_path(ntpath.join(prefix, name))
        if variable_path != expected_path:
            raise LiveSafetyError(
                "POST_SAVE_VARIABLE_TARGET_MISMATCH: AutoCAD active variables do not match the candidate."
            )

    try:
        persisted_build = load_build_evidence(evidence_path, dxf)
    except LiveSafetyError:
        raise
    except Exception as exc:
        raise LiveSafetyError(
            "POST_SAVE_EVIDENCE_READ_FAILED: persisted build evidence could not be loaded."
        ) from exc
    persisted_review = review_dxf_live(persisted_build, client, open_drawing=False)
    if not persisted_review.passed:
        raise LiveSafetyError(
            "POST_SAVE_REVIEW_FAILED: persisted candidate did not pass fresh live review."
        )
    if persisted_review.geometry_degraded:
        raise LiveSafetyError(
            "POST_SAVE_REVIEW_DEGRADED: persisted candidate geometry was not freshly revalidated."
        )
    return {
        "closed_without_save": True,
        "reopened": True,
        "active_path": str(dxf),
        "open_paths": sorted(open_paths),
        "evidence_verified": True,
        "dxf_sha256": sha256_file(dxf),
        "evidence_sha256": sha256_file(evidence_path),
        "review": review_dict(persisted_review),
    }


def repair_live(
    build: BuildResult,
    client: Any,
    dxf: Path,
    evidence_path: Path,
    backup_dir: Path,
    approval_reference: str,
) -> dict[str, Any]:
    """Repair a live staged DXF only after recording a recoverable backup."""
    if not approval_reference.strip():
        raise LiveSafetyError("A non-empty production repair approval reference is required.")
    if not dxf.is_file() or not evidence_path.is_file():
        raise LiveSafetyError("Both staged DXF and build evidence must exist before live repair.")

    build.output_path = str(dxf)
    before = review_dxf_live(build, client, open_drawing=True)
    report: dict[str, Any] = {
        "operation": "mechanical-repair",
        "approval_reference": approval_reference,
        "dxf_path": str(dxf),
        "dxf_sha256_before": sha256_file(dxf),
        "build_evidence_sha256_before": sha256_file(evidence_path),
        "before_review": review_dict(before),
        "backup": None,
        "repair": None,
        "after_review": None,
        "save_state": "not_needed" if before.passed else "not_saved",
    }
    if before.passed:
        return report

    backup = _backup(dxf, evidence_path, backup_dir)
    report["backup"] = backup
    repaired = repair_dxf_live(build, before.mismatches, client)
    report["repair"] = asdict(repaired)
    after = review_dxf_live(build, client, open_drawing=False)
    report["after_review"] = review_dict(after)
    if after.passed and repaired.repaired_count > 0:
        client.drawing_save()
        build.output_path = str(dxf)
        write_build_evidence(evidence_path, build)
        report["dxf_sha256_after"] = sha256_file(dxf)
        report["save_state"] = "saved"
        report["post_save_attestation"] = _attest_saved_candidate(
            build, client, dxf, evidence_path
        )
        return report

    try:
        client.drawing_close(save_changes=False)
        report["rollback_restore"] = _restore_canonical(
            client=client,
            dxf=dxf,
            evidence_path=evidence_path,
            backup=backup,
        )
        report["rollback_state"] = "failed_canonical_restored"
    except Exception as exc:  # pragma: no cover - exercised by live transport failures
        raise LiveSafetyError(
            "rollback failed; unrecoverable recovery is terminal and non-pass."
        ) from exc
    return report
