"""Shared bound-file identity primitives for fail-closed file operations."""

from __future__ import annotations

import os
import stat
import sys
from contextlib import contextmanager
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


@contextmanager
def pin_directory_chain(path: Path):
    """Create/hold an absolute Windows directory chain without following reparses.

    Each parent is held without delete sharing before a child is inspected or
    created, so a checked directory cannot be renamed underneath publication.
    This extends the existing bound-file owner; it is not a runtime authority.
    """
    if sys.platform != "win32" or not path.is_absolute():
        raise FileIdentityError("Directory identity requires an absolute Windows path.")
    import ctypes
    from ctypes import wintypes

    class Information(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
            ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
            ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(Information)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handles = []
    try:
        for component in (*reversed(path.parents), path):
            try:
                expected = os.stat(component, follow_symlinks=False)
            except FileNotFoundError:
                component.mkdir()
                expected = os.stat(component, follow_symlinks=False)
            if not stat.S_ISDIR(expected.st_mode) or getattr(expected, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise FileIdentityError("Directory chain must remain regular and non-reparse.")
            handle = kernel.CreateFileW(str(component), 0x1 | 0x80 | 0x100000, 0x1 | 0x2, None, 3,
                                        0x02000000 | 0x00200000, None)
            value = ctypes.cast(handle, ctypes.c_void_p).value
            if value in (None, ctypes.c_void_p(-1).value):
                raise FileIdentityError("Directory chain could not be pinned.")
            handles.append(handle)
            information = Information()
            if not kernel.GetFileInformationByHandle(handle, ctypes.byref(information)):
                raise FileIdentityError("Directory handle identity could not be verified.")
            identity = (int(information.volume), (int(information.index_high) << 32) | int(information.index_low))
            if information.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or identity != (expected.st_dev, expected.st_ino):
                raise FileIdentityError("Directory identity changed before use.")
        yield
    except OSError as error:
        raise FileIdentityError("Directory identity could not be established.") from error
    finally:
        active_error = sys.exc_info()[0] is not None
        closed = [bool(kernel.CloseHandle(handle)) for handle in reversed(handles)]
        if not all(closed) and not active_error:
            raise FileIdentityError("Directory handles could not be released.")
