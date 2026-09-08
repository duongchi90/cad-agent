"""Shared bound-file identity primitives for fail-closed file operations."""

from __future__ import annotations

import os
import stat
from pathlib import Path


_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class FileIdentityError(ValueError):
    """Raised when a file path cannot be bound to one stable file object."""


def is_regular_non_reparse(stat_result: os.stat_result) -> bool:
    return stat.S_ISREG(stat_result.st_mode) and not bool(
        getattr(stat_result, "st_file_attributes", 0)
        & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def is_single_link_regular_non_reparse(stat_result: os.stat_result) -> bool:
    return is_regular_non_reparse(stat_result) and getattr(stat_result, "st_nlink", 1) == 1


def assert_path_identity(
    path: Path, opened_stat: os.stat_result, *, label: str
) -> None:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise FileIdentityError(f"{label} identity could not be verified.") from exc
    if not is_single_link_regular_non_reparse(path_stat) or not os.path.samestat(
        opened_stat, path_stat
    ):
        raise FileIdentityError(
            f"{label} must remain the same single-link regular non-reparse file."
        )


def open_bound_file(
    path: Path, *, flags: int, label: str
) -> tuple[int, os.stat_result]:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise FileIdentityError(f"{label} identity could not be verified.") from exc
    if not is_single_link_regular_non_reparse(path_stat):
        raise FileIdentityError(
            f"{label} must be a single-link regular non-reparse file."
        )

    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened_stat = os.fstat(descriptor)
        if (
            not is_single_link_regular_non_reparse(opened_stat)
            or not os.path.samestat(path_stat, opened_stat)
        ):
            raise FileIdentityError(f"{label} identity changed while opening.")
        assert_path_identity(path, opened_stat, label=label)
        return descriptor, opened_stat
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise
