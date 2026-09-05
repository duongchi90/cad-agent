"""Safety boundary for AutoCAD Mechanical File IPC review and repair."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import ntpath
import os
import stat
import shutil
import sys
from pathlib import Path
from ctypes import wintypes
from typing import Any

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import LiveReviewResult, review_dxf_live

from .manifest import sha256_file


BUILD_EVIDENCE_SCHEMA_VERSION = "1.0"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
BackupDirectoryIdentity = tuple[tuple[Path, os.stat_result], ...]


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
    _write_json_artifact(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        label="Build evidence",
    )


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
    _write_json_artifact(
        path,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        label="Live report",
    )


def _is_directory_non_reparse(stat_result: os.stat_result) -> bool:
    return stat.S_ISDIR(stat_result.st_mode) and not bool(
        getattr(stat_result, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _DirectoryChainBinding:
    """Pin a verified directory chain against Windows rename/reparse races."""

    _FILE_LIST_DIRECTORY = 0x0001
    _FILE_READ_ATTRIBUTES = 0x0080
    _SYNCHRONIZE = 0x100000
    _FILE_SHARE_READ = 0x0001
    _FILE_SHARE_WRITE = 0x0002
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    def __init__(self, path: Path, identity: BackupDirectoryIdentity) -> None:
        self.path = path
        self.identity = identity
        self._kernel32: Any | None = None
        self._handles: list[int] = []

    def __enter__(self) -> "_DirectoryChainBinding":
        try:
            if sys.platform != "win32":
                raise LiveSafetyError(
                    "Directory identity cannot be safely pinned on this platform."
                )
            self._open_windows_chain()
            self.assert_current()
            return self
        except Exception:
            self._close_handles()
            raise

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        close_error = self._close_handles()
        if close_error is not None and exc_type is None:
            raise close_error

    def assert_current(self) -> None:
        _assert_backup_directory_identity(self.path, self.identity)

    def _open_windows_chain(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32

        for component, expected in self.identity:
            handle = kernel32.CreateFileW(
                str(component),
                self._FILE_LIST_DIRECTORY | self._FILE_READ_ATTRIBUTES | self._SYNCHRONIZE,
                self._FILE_SHARE_READ | self._FILE_SHARE_WRITE,
                None,
                self._OPEN_EXISTING,
                self._FILE_FLAG_BACKUP_SEMANTICS | self._FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
            value = ctypes.cast(handle, ctypes.c_void_p).value
            if value in {None, self._INVALID_HANDLE_VALUE}:
                raise LiveSafetyError("Verified directory chain could not be pinned.")
            info = _ByHandleFileInformation()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                kernel32.CloseHandle(handle)
                raise LiveSafetyError("Pinned directory identity could not be verified.")
            handle_identity = (
                int(info.dwVolumeSerialNumber),
                (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
            )
            expected_identity = (int(expected.st_dev), int(expected.st_ino))
            if (
                bool(info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT)
                or handle_identity != expected_identity
            ):
                kernel32.CloseHandle(handle)
                raise LiveSafetyError("Pinned directory identity changed before use.")
            self._handles.append(int(value))

    def _close_handles(self) -> LiveSafetyError | None:
        close_error: LiveSafetyError | None = None
        if self._kernel32 is not None:
            for value in reversed(self._handles):
                if not self._kernel32.CloseHandle(wintypes.HANDLE(value)):
                    close_error = LiveSafetyError(
                        "Pinned directory handle could not be closed safely."
                    )
        self._handles.clear()
        return close_error


def _backup_directory_components(backup_dir: Path) -> tuple[Path, ...]:
    if not backup_dir.is_absolute():
        raise LiveSafetyError("Backup directory must be an absolute path.")
    components: list[Path] = []
    current = backup_dir
    while True:
        components.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return tuple(reversed(components))


def _stat_backup_directory_component(path: Path) -> os.stat_result | None:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LiveSafetyError(
            "Backup directory identity could not be verified."
        ) from exc
    if not _is_directory_non_reparse(path_stat):
        raise LiveSafetyError(
            "Backup directory must remain a regular non-reparse directory chain."
        )
    return path_stat


def _capture_backup_directory_identity(backup_dir: Path) -> BackupDirectoryIdentity:
    components = _backup_directory_components(backup_dir)
    identity: list[tuple[Path, os.stat_result]] = []
    for component in components:
        path_stat = _stat_backup_directory_component(component)
        if path_stat is None:
            raise LiveSafetyError("Backup directory chain is incomplete.")
        identity.append((component, path_stat))
    return tuple(identity)


def _prepare_backup_directory(backup_dir: Path) -> BackupDirectoryIdentity:
    components = _backup_directory_components(backup_dir)
    first_missing: int | None = None
    identity: list[tuple[Path, os.stat_result]] = []
    for index, component in enumerate(components):
        path_stat = _stat_backup_directory_component(component)
        if path_stat is None:
            first_missing = index
            break
        identity.append((component, path_stat))

    if first_missing is not None:
        for component in components[first_missing:]:
            if identity:
                _assert_backup_directory_identity(identity[-1][0], tuple(identity))
            try:
                component.mkdir()
            except FileExistsError as exc:
                raise LiveSafetyError(
                    "Backup directory changed while creating its identity-safe chain."
                ) from exc
            except OSError as exc:
                raise LiveSafetyError(
                    "Backup directory could not be created safely."
                ) from exc
            component_stat = _stat_backup_directory_component(component)
            if component_stat is None:
                raise LiveSafetyError("Backup directory disappeared while creating it.")
            identity.append((component, component_stat))

    return _capture_backup_directory_identity(backup_dir)


def _assert_backup_directory_identity(
    backup_dir: Path, expected: BackupDirectoryIdentity | None = None
) -> BackupDirectoryIdentity:
    current = _capture_backup_directory_identity(backup_dir)
    if expected is not None:
        if len(current) != len(expected) or any(
            current_path != expected_path
            or not os.path.samestat(current_stat, expected_stat)
            for (current_path, current_stat), (expected_path, expected_stat) in zip(
                current, expected
            )
        ):
            raise LiveSafetyError("Backup directory chain identity changed.")
    return current


def _capture_output_destination(
    path: Path, *, label: str
) -> os.stat_result | None:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LiveSafetyError(f"{label} destination identity could not be verified.") from exc
    if not _is_single_link_regular_non_reparse(path_stat):
        raise LiveSafetyError(
            f"{label} destination must be a single-link regular non-reparse file."
        )
    return path_stat


def _assert_output_destination_identity(
    path: Path,
    expected: os.stat_result | None,
    *,
    label: str,
) -> None:
    current = _capture_output_destination(path, label=label)
    if expected is None:
        if current is not None:
            raise LiveSafetyError(f"{label} destination appeared during the write.")
        return
    if current is None or not os.path.samestat(expected, current):
        raise LiveSafetyError(f"{label} destination identity changed during the write.")


def _write_json_artifact(path: Path, text: str, *, label: str) -> None:
    if not path.is_absolute():
        raise LiveSafetyError(f"{label} path must be absolute.")
    parent_identity = _prepare_backup_directory(path.parent)
    temporary = path.with_suffix(path.suffix + ".tmp")
    owned_temp_stat: os.stat_result | None = None
    payload = text.encode("utf-8")
    with _DirectoryChainBinding(path.parent, parent_identity) as directory_binding:
        destination_before = _capture_output_destination(path, label=label)
        try:
            directory_binding.assert_current()
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(temporary, flags, 0o600)
            except OSError as exc:
                raise LiveSafetyError(f"{label} temporary destination is not safely available.") from exc
            try:
                owned_temp_stat = os.fstat(descriptor)
                if not _is_single_link_regular_non_reparse(owned_temp_stat):
                    raise LiveSafetyError(f"{label} temporary destination is not a regular file.")
                with os.fdopen(descriptor, "wb") as stream:
                    descriptor = -1
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)

            directory_binding.assert_current()
            _assert_path_identity(temporary, owned_temp_stat, label=f"{label} temporary")
            _assert_output_destination_identity(path, destination_before, label=label)
            os.replace(temporary, path)
            directory_binding.assert_current()
            destination_after = _capture_output_destination(path, label=label)
            if destination_after is None or not os.path.samestat(
                owned_temp_stat, destination_after
            ):
                raise LiveSafetyError(f"{label} destination identity was not preserved.")

            read_flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                read_flags |= os.O_NOFOLLOW
            read_descriptor, opened_stat = _open_bound_file(
                path, flags=read_flags, label=f"{label} destination"
            )
            with os.fdopen(read_descriptor, "rb") as stream:
                persisted = stream.read()
            if not os.path.samestat(owned_temp_stat, opened_stat):
                raise LiveSafetyError(f"{label} destination identity changed after publish.")
            if persisted != payload or hashlib.sha256(persisted).hexdigest() != hashlib.sha256(payload).hexdigest():
                raise LiveSafetyError(f"{label} persisted bytes could not be verified.")
            directory_binding.assert_current()
        except Exception as exc:
            if owned_temp_stat is not None:
                try:
                    _cleanup_backup_artifacts(
                        (temporary, temporary),
                        {temporary: owned_temp_stat},
                        directory_identity=parent_identity,
                        directory_binding=directory_binding,
                    )
                except LiveSafetyError as cleanup_exc:
                    raise LiveSafetyError(
                        f"{label} cleanup could not prove zero temporary survivors."
                    ) from cleanup_exc
            if isinstance(exc, LiveSafetyError):
                raise
            raise LiveSafetyError(f"{label} write failed.") from exc


def _backup_paths(dxf: Path, evidence: Path, backup_dir: Path) -> tuple[Path, Path]:
    _prepare_backup_directory(backup_dir)
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
    *,
    directory_binding: _DirectoryChainBinding | None = None,
) -> str:
    if directory_binding is not None:
        directory_binding.assert_current()
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
        if directory_binding is not None:
            directory_binding.assert_current()
        return digest.hexdigest()
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _cleanup_backup_artifacts(
    paths: tuple[Path, Path],
    owned_paths: dict[Path, os.stat_result | None],
    *,
    directory_identity: BackupDirectoryIdentity | None = None,
    directory_binding: _DirectoryChainBinding | None = None,
) -> None:
    cleanup_failures: list[Path] = []
    directory_safe = True
    if directory_binding is not None:
        try:
            directory_binding.assert_current()
        except LiveSafetyError:
            directory_safe = False
            cleanup_failures.extend(owned_paths)
    elif directory_identity is not None:
        try:
            _assert_backup_directory_identity(paths[0].parent, directory_identity)
        except LiveSafetyError:
            directory_safe = False
            cleanup_failures.extend(owned_paths)

    if directory_safe:
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


def _backup(
    dxf: Path,
    evidence: Path,
    backup_dir: Path,
    *,
    owned_paths: dict[Path, os.stat_result | None] | None = None,
    directory_identity_out: list[tuple[Path, os.stat_result]] | None = None,
) -> dict[str, Any]:
    directory_identity = _prepare_backup_directory(backup_dir)
    owned_paths = {} if owned_paths is None else owned_paths
    with _DirectoryChainBinding(backup_dir, directory_identity) as directory_binding:
        dxf_backup, evidence_backup = _backup_paths(dxf, evidence, backup_dir)
        backup_paths = (dxf_backup, evidence_backup)
        _assert_backup_directory_identity(backup_dir, directory_identity)
        if directory_identity_out is not None:
            directory_identity_out.extend(directory_identity)
        try:
            dxf_source_before = sha256_file(dxf)
            evidence_source_before = sha256_file(evidence)
            directory_binding.assert_current()
            dxf_backup_hash = _copy_to_exclusive_backup(
                dxf,
                dxf_backup,
                owned_paths,
                directory_binding=directory_binding,
            )
            directory_binding.assert_current()
            evidence_backup_hash = _copy_to_exclusive_backup(
                evidence,
                evidence_backup,
                owned_paths,
                directory_binding=directory_binding,
            )
            directory_binding.assert_current()
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
                _cleanup_backup_artifacts(
                    backup_paths,
                    owned_paths,
                    directory_identity=directory_identity,
                    directory_binding=directory_binding,
                )
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
    if open_paths != {expected_path}:
        raise LiveSafetyError(
            "POST_SAVE_OPEN_DOCUMENT_SET_MISMATCH: open documents are not canonical-only."
        )

    active_path = getattr(client, "_active_drawing_path", None)
    if active_path is None:
        active_path = getattr(client, "opened_path", None)
    if active_path is None or not str(active_path).strip():
        raise LiveSafetyError(
            "POST_SAVE_ACTIVE_TARGET_UNAVAILABLE: authoritative active document identity is missing."
        )
    if _normalized_document_path(active_path) != expected_path:
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
    if not (
        isinstance(prefix, str)
        and isinstance(name, str)
        and prefix.strip()
        and name.strip()
    ):
        raise LiveSafetyError(
            "POST_SAVE_VARIABLE_IDENTITY_UNAVAILABLE: AutoCAD active variables are incomplete."
        )
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

    owned_backup_paths: dict[Path, os.stat_result | None] = {}
    backup_directory_identity: list[tuple[Path, os.stat_result]] = []
    backup = _backup(
        dxf,
        evidence_path,
        backup_dir,
        owned_paths=owned_backup_paths,
        directory_identity_out=backup_directory_identity,
    )
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
        post_save_attestation = _attest_saved_candidate(
            build, client, dxf, evidence_path
        )
        try:
            _cleanup_backup_artifacts(
                (
                    Path(backup["dxf_path"]),
                    Path(backup["build_evidence_path"]),
                ),
                owned_backup_paths,
                directory_identity=tuple(backup_directory_identity),
            )
        except Exception as exc:
            raise LiveSafetyError(
                "post-save backup cleanup failed; unrecoverable recovery is terminal and non-pass."
            ) from exc
        report["post_save_attestation"] = post_save_attestation
        report["backup_cleanup"] = {"zero_survivors": True}
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
