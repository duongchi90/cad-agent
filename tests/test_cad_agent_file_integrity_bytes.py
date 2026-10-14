from __future__ import annotations

from pathlib import Path

import pytest

from cad_agent import file_integrity


def _write_bound_bytes():
    writer = getattr(file_integrity, "write_bound_bytes", None)
    assert callable(writer), "file_integrity must expose the shared bytes publisher"
    return writer


def _sentinel(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"owned sentinel bytes")
    return path.read_bytes()


def test_bound_bytes_writer_creates_and_replaces_an_ordinary_destination(tmp_path: Path):
    writer = _write_bound_bytes()
    destination = tmp_path / "created" / "candidate.bin"
    payload = b"candidate\x00bytes\r\n"

    writer(destination, payload, label="Test artifact")
    assert destination.read_bytes() == payload

    replacement = b"replacement\x00bytes\n"
    writer(destination, replacement, label="Test artifact")
    assert destination.read_bytes() == replacement


def test_bound_bytes_writer_rejects_non_bytes_before_directory_creation(tmp_path: Path):
    writer = _write_bound_bytes()
    destination = tmp_path / "not-created" / "candidate.bin"

    with pytest.raises((TypeError, ValueError), match="bytes"):
        writer(destination, "not bytes", label="Test artifact")

    assert not destination.parent.exists()


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_bound_bytes_writer_rejects_linked_destination_without_mutating_sentinel(
    tmp_path: Path, link_kind: str,
):
    writer = _write_bound_bytes()
    destination = tmp_path / "run" / "candidate.bin"
    sentinel = tmp_path / "owned" / "sentinel.bin"
    before = _sentinel(sentinel)
    destination.parent.mkdir()
    if link_kind == "symlink":
        destination.symlink_to(sentinel)
    else:
        destination.hardlink_to(sentinel)

    with pytest.raises(file_integrity.FileIdentityError):
        writer(destination, b"replacement bytes", label="Test artifact")

    assert sentinel.read_bytes() == before
    assert destination.is_symlink() if link_kind == "symlink" else destination.exists()


def test_bound_bytes_writer_rejects_linked_parent_without_mutating_sentinel(
    tmp_path: Path,
):
    writer = _write_bound_bytes()
    outside = tmp_path / "owned-parent"
    sentinel = outside / "candidate.bin"
    before = _sentinel(sentinel)
    linked_parent = tmp_path / "run" / "nested"
    linked_parent.parent.mkdir()
    linked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(file_integrity.FileIdentityError):
        writer(linked_parent / "candidate.bin", b"replacement bytes", label="Test artifact")

    assert sentinel.read_bytes() == before
    assert linked_parent.is_symlink()
