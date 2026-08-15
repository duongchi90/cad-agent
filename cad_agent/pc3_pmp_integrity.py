"""Deterministic read/hash-only PC3/PMP integrity manifest recipe."""

from __future__ import annotations

import hashlib
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


def _validate_root(root: object) -> Path:
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
    return root


def _collect_records(
    root: Path,
    root_slot: int,
    directory: Path,
    records: list[dict[str, object]],
    seen_identities: list[tuple[int, str]],
) -> None:
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise PC3PMPIntegrityError("plotter root traversal failed") from exc

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
            _collect_records(root, root_slot, entry, records, seen_identities)
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

        try:
            data = entry.read_bytes()
            after = entry.lstat()
        except OSError as exc:
            raise PC3PMPIntegrityError(
                "selected file read failed due to missing, unreadable, or raced state"
            ) from exc

        if entry.is_symlink() or _is_reparse(after):
            raise PC3PMPIntegrityError("selected file identity changed during read")
        if not stat.S_ISREG(int(getattr(after, "st_mode", 0))):
            raise PC3PMPIntegrityError("selected file identity changed during read")
        if _file_identity(before) != _file_identity(after):
            raise PC3PMPIntegrityError("selected file identity drifted during read")

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

    roots = list(plotter_roots)
    records: list[dict[str, object]] = []
    seen_identities: list[tuple[int, str]] = []

    for root_slot, candidate_root in enumerate(roots):
        root = _validate_root(candidate_root)
        _collect_records(root, root_slot, root, records, seen_identities)

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
