"""Deterministic read/hash-only PC3/PMP integrity manifest recipe."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from cad_agent.drawing_contracts import canonical_json_sha256


PC3_PMP_INTEGRITY_MANIFEST_VERSION = "pc3-pmp-integrity-manifest-1.0"


class PC3PMPIntegrityError(ValueError):
    """Raised when PC3/PMP integrity evidence cannot be produced safely."""


def _is_reparse(metadata: object) -> bool:
    return bool(
        int(getattr(metadata, "st_file_attributes", 0))
        & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _file_identity(metadata: object) -> tuple[int, int, int, int, int, int]:
    return (
        int(getattr(metadata, "st_dev", 0)),
        int(getattr(metadata, "st_ino", 0)),
        int(getattr(metadata, "st_mode", 0)),
        int(getattr(metadata, "st_size", 0)),
        int(getattr(metadata, "st_mtime_ns", 0)),
        int(getattr(metadata, "st_file_attributes", 0)),
    )


def canonicalize_pc3_pmp_relative_path(relative_path: str) -> str:
    """Return the canonical privacy-internal identity for a root-relative path."""
    if not isinstance(relative_path, str) or not relative_path:
        raise PC3PMPIntegrityError("relative path must be a non-empty string")
    if relative_path.startswith(("/", "\\")) or ":" in relative_path:
        raise PC3PMPIntegrityError("relative path must remain inside its root")

    parts: list[str] = []
    for backslash_part in relative_path.split("\\"):
        for part in backslash_part.split("/"):
            if part in {"", ".", ".."}:
                raise PC3PMPIntegrityError("relative path must remain inside its root")
            parts.append(part.casefold())

    if not parts:
        raise PC3PMPIntegrityError("relative path must be non-empty")
    return "/".join(parts)


def _validate_root(root: object) -> tuple[Path, tuple[int, int, int, int, int, int]]:
    if not isinstance(root, Path):
        raise PC3PMPIntegrityError("plotter root must be a Path")
    try:
        if root.is_symlink():
            raise PC3PMPIntegrityError("plotter root symlink or reparse is forbidden")
        metadata = root.lstat()
    except OSError as exc:
        raise PC3PMPIntegrityError("plotter root must exist and be readable") from exc
    if _is_reparse(metadata):
        raise PC3PMPIntegrityError("plotter root reparse or junction is forbidden")
    if not stat.S_ISDIR(int(getattr(metadata, "st_mode", 0))):
        raise PC3PMPIntegrityError("plotter root must be a directory")
    return root, _file_identity(metadata)


def _require_directory_identity(
    directory: Path,
    expected_identity: tuple[int, int, int, int, int, int],
) -> None:
    try:
        if directory.is_symlink():
            raise PC3PMPIntegrityError("directory identity changed to symlink or reparse")
        metadata = directory.lstat()
    except OSError as exc:
        raise PC3PMPIntegrityError("directory identity became unreadable") from exc
    if _is_reparse(metadata):
        raise PC3PMPIntegrityError("directory identity changed to reparse or junction")
    if not stat.S_ISDIR(int(getattr(metadata, "st_mode", 0))):
        raise PC3PMPIntegrityError("directory identity changed during traversal")
    if _file_identity(metadata) != expected_identity:
        raise PC3PMPIntegrityError("directory identity drifted during traversal")


def _read_selected_file(
    entry: Path,
    before: object,
) -> tuple[bytes, object]:
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    try:
        descriptor = os.open(entry, flags)
    except OSError as exc:
        raise PC3PMPIntegrityError(
            "selected file open failed due to missing, unreadable, or raced state"
        ) from exc

    try:
        opened = os.fstat(descriptor)
        if _is_reparse(opened):
            raise PC3PMPIntegrityError("selected file opened as a reparse target")
        if not stat.S_ISREG(int(getattr(opened, "st_mode", 0))):
            raise PC3PMPIntegrityError("selected file opened as a non-regular object")
        if _file_identity(opened) != _file_identity(before):
            raise PC3PMPIntegrityError("selected file identity changed before read")

        expected_size = int(getattr(opened, "st_size", 0))
        data = os.read(descriptor, expected_size + 1)
        if len(data) != expected_size:
            raise PC3PMPIntegrityError("selected file byte length drifted during read")

        opened_after = os.fstat(descriptor)
        if _file_identity(opened_after) != _file_identity(opened):
            raise PC3PMPIntegrityError("selected file opened identity drifted during read")
    finally:
        os.close(descriptor)

    try:
        if entry.is_symlink():
            raise PC3PMPIntegrityError("selected file path changed to symlink or reparse")
        after = entry.lstat()
    except OSError as exc:
        raise PC3PMPIntegrityError("selected file path changed during read") from exc
    if _is_reparse(after):
        raise PC3PMPIntegrityError("selected file path changed to reparse or junction")
    if not stat.S_ISREG(int(getattr(after, "st_mode", 0))):
        raise PC3PMPIntegrityError("selected file path changed during read")
    if _file_identity(before) != _file_identity(after):
        raise PC3PMPIntegrityError("selected file identity drifted during read")
    return data, after


def _collect_records(
    root: Path,
    root_slot: int,
    directory: Path,
    directory_identity: tuple[int, int, int, int, int, int],
    records: list[dict[str, object]],
    seen_identities: list[tuple[int, str]],
) -> None:
    _require_directory_identity(directory, directory_identity)
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise PC3PMPIntegrityError("plotter root traversal failed") from exc
    _require_directory_identity(directory, directory_identity)

    for entry in entries:
        try:
            if entry.is_symlink():
                raise PC3PMPIntegrityError("entry symlink or reparse is forbidden")
            before = entry.lstat()
        except OSError as exc:
            raise PC3PMPIntegrityError("entry metadata read failed") from exc

        if _is_reparse(before):
            raise PC3PMPIntegrityError("entry reparse or junction is forbidden")

        mode = int(getattr(before, "st_mode", 0))
        if stat.S_ISDIR(mode):
            _collect_records(
                root,
                root_slot,
                entry,
                _file_identity(before),
                records,
                seen_identities,
            )
            continue
        if not stat.S_ISREG(mode):
            continue
        if entry.suffix.casefold() not in {".pc3", ".pmp"}:
            continue

        try:
            relative = canonicalize_pc3_pmp_relative_path(
                entry.relative_to(root).as_posix()
            )
        except ValueError as exc:
            raise PC3PMPIntegrityError("entry escaped its plotter root") from exc

        identity = (root_slot, relative)
        if identity in seen_identities:
            raise PC3PMPIntegrityError("duplicate normalized path collision")
        seen_identities.append(identity)

        data, _ = _read_selected_file(entry, before)
        records.append(
            {
                "root_slot": root_slot,
                "relative_path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )


def build_pc3_pmp_integrity_manifest(
    *,
    plotter_roots: tuple[Path, ...],
) -> dict[str, object]:
    """Build the closed public integrity result for exactly two explicit roots."""
    if not isinstance(plotter_roots, (tuple, list)) or len(plotter_roots) != 2:
        raise PC3PMPIntegrityError("exactly two explicit plotter roots are required")

    validated_roots = [_validate_root(candidate_root) for candidate_root in plotter_roots]
    if _file_identity(validated_roots[0][0].lstat()) == _file_identity(
        validated_roots[1][0].lstat()
    ):
        raise PC3PMPIntegrityError("two explicit plotter roots must be distinct")

    records: list[dict[str, object]] = []
    seen_identities: list[tuple[int, str]] = []

    for root_slot, validated_root in enumerate(validated_roots):
        root, root_identity = validated_root
        _collect_records(
            root,
            root_slot,
            root,
            root_identity,
            records,
            seen_identities,
        )

    ordered_records = sorted(
        records,
        key=lambda record: (record["root_slot"], record["relative_path"]),
    )
    payload: dict[str, object] = {
        "manifest_version": PC3_PMP_INTEGRITY_MANIFEST_VERSION,
        "records": ordered_records,
    }
    aggregate_sha256 = canonical_json_sha256(payload)
    return {
        "manifest_version": PC3_PMP_INTEGRITY_MANIFEST_VERSION,
        "count": len(ordered_records),
        "aggregate_sha256": aggregate_sha256,
    }
