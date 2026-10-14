from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from cad_agent import manifest as manifest_owner


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows manifest identity contract")


def _manifest() -> dict[str, object]:
    return {"schema_version": "1.0", "run_id": "security-test", "stages": {}}


def _lock_record(pid: int = 0xFFFFFFFE) -> bytes:
    return json.dumps(
        {
            "schema_version": manifest_owner._MANIFEST_LOCK_SCHEMA_VERSION,
            "pid": pid,
            "start_filetime": 1,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_preexisting_fixed_temp_link_is_neither_followed_nor_removed(tmp_path: Path) -> None:
    destination = tmp_path / "run-manifest.json"
    fixed_temp = destination.with_suffix(destination.suffix + ".tmp")
    sentinel = tmp_path.parent / f"{tmp_path.name}-temp-sentinel.json"
    original = b"owned sentinel bytes\r\n"
    sentinel.write_bytes(original)
    fixed_temp.symlink_to(sentinel)

    manifest_owner.write_manifest(destination, _manifest())

    assert sentinel.read_bytes() == original
    assert fixed_temp.is_symlink()
    assert json.loads(destination.read_bytes()) == _manifest()


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_linked_manifest_destination_is_refused(tmp_path: Path, link_kind: str) -> None:
    destination = tmp_path / "run-manifest.json"
    sentinel = tmp_path / "sentinel.json"
    original = b"existing manifest sentinel\r\n"
    sentinel.write_bytes(original)
    if link_kind == "symlink":
        destination.symlink_to(sentinel)
    else:
        os.link(sentinel, destination)

    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_WRITE_FAILED"):
        manifest_owner.write_manifest(destination, _manifest())

    assert sentinel.read_bytes() == original
    if link_kind == "symlink":
        assert destination.is_symlink()
    else:
        assert os.path.samefile(destination, sentinel)


def test_linked_destination_parent_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "run-manifest.json"
    original = b"outside parent sentinel\r\n"
    sentinel.write_bytes(original)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(manifest_owner.ManifestError):
        manifest_owner.write_manifest(linked_parent / "run-manifest.json", _manifest())

    assert sentinel.read_bytes() == original
    assert linked_parent.is_symlink()


def test_parent_substitution_is_blocked_before_lock_creation(tmp_path: Path, monkeypatch) -> None:
    parent = tmp_path / "output"
    parent.mkdir()
    displaced = tmp_path / "displaced-output"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_manifest = outside / "run-manifest.json"
    outside_sentinel = b"foreign manifest sentinel\r\n"
    outside_manifest.write_bytes(outside_sentinel)
    destination = parent / "run-manifest.json"
    original_open = manifest_owner._open_windows_manifest_lock
    attempts: list[str] = []

    def substitute_before_open(lock_path: Path) -> int:
        try:
            parent.rename(displaced)
        except OSError:
            attempts.append("blocked")
        else:
            attempts.append("substituted")
            parent.symlink_to(outside, target_is_directory=True)
        return original_open(lock_path)

    monkeypatch.setattr(manifest_owner, "_open_windows_manifest_lock", substitute_before_open)
    try:
        manifest_owner.write_manifest(destination, _manifest())
        assert attempts == ["blocked"]
        assert outside_manifest.read_bytes() == outside_sentinel
        assert json.loads(destination.read_bytes()) == _manifest()
    finally:
        if parent.is_symlink():
            parent.unlink()
        if displaced.exists() and not parent.exists():
            displaced.rename(parent)


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_linked_existing_lock_stays_busy_and_intact(tmp_path: Path, link_kind: str) -> None:
    destination = tmp_path / "run-manifest.json"
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    lock_target = tmp_path / "lock-target.json"
    original = _lock_record()
    lock_target.write_bytes(original)
    if link_kind == "symlink":
        lock_path.symlink_to(lock_target)
    else:
        os.link(lock_target, lock_path)

    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
        manifest_owner.write_manifest(destination, _manifest())

    assert lock_target.read_bytes() == original
    assert lock_path.is_symlink() if link_kind == "symlink" else os.path.samefile(lock_path, lock_target)


def test_nonregular_existing_lock_stays_busy(tmp_path: Path) -> None:
    destination = tmp_path / "run-manifest.json"
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    lock_path.mkdir()

    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
        manifest_owner.write_manifest(destination, _manifest())

    assert lock_path.is_dir()


def test_dead_lock_reclaim_does_not_unlink_substituted_foreign_lock(
    tmp_path: Path, monkeypatch
) -> None:
    destination = tmp_path / "run-manifest.json"
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    lock_path.write_bytes(_lock_record())
    foreign = tmp_path / "foreign-lock.json"
    foreign_bytes = b"foreign replacement lock\r\n"
    foreign.write_bytes(foreign_bytes)

    def substitute_then_report_dead(_pid: int, _start_filetime: int) -> bool:
        os.replace(foreign, lock_path)
        return False

    monkeypatch.setattr(manifest_owner, "_manifest_lock_owner_state", substitute_then_report_dead)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
        manifest_owner.write_manifest(destination, _manifest())

    assert lock_path.read_bytes() == foreign_bytes


def test_lock_cleanup_preserves_substituted_foreign_lock(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "run-manifest.json"
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    foreign = tmp_path / "foreign-lock.json"
    foreign_bytes = b"replacement after lock epoch\r\n"
    foreign.write_bytes(foreign_bytes)
    owned_handles: set[int] = set()
    real_write_identity = manifest_owner._write_windows_manifest_lock_identity
    real_kernel_factory = manifest_owner._windows_kernel32

    def write_identity(handle: int) -> None:
        owned_handles.add(handle)
        real_write_identity(handle)

    class KernelProxy:
        def __init__(self, kernel) -> None:
            self._kernel = kernel

        def __getattr__(self, name: str):
            return getattr(self._kernel, name)

        def CloseHandle(self, handle: int) -> bool:
            result = self._kernel.CloseHandle(handle)
            if handle in owned_handles and foreign.exists():
                os.replace(foreign, lock_path)
            return result

    monkeypatch.setattr(manifest_owner, "_write_windows_manifest_lock_identity", write_identity)
    monkeypatch.setattr(
        manifest_owner,
        "_windows_kernel32",
        lambda: KernelProxy(real_kernel_factory()),
    )

    manifest_owner.write_manifest(destination, _manifest())

    assert lock_path.read_bytes() == foreign_bytes


@pytest.mark.parametrize(
    ("name", "payload", "expected_sha256"),
    [
        (
            "image",
            {
                "run_id": "freeze-image-ü",
                "schema_version": "1.0",
                "source": {"path": "drawing ü.png", "sha256": "a" * 64},
                "stages": {"primitive_ir": {"status": "complete"}},
                "publication_lifecycle": None,
            },
            "83d94cc875241f98a71a037b589468a2bcf1e06f32089ce91ca373b8605fe69e",
        ),
        (
            "pdf",
            {
                "run_id": "freeze-pdf-Ω",
                "schema_version": "pdf-run-1.0",
                "source": {"path": "drawing Ω.pdf", "sha256": "b" * 64},
                "pages": [{"page": 1, "status": "complete"}],
                "publication_lifecycle": None,
            },
            "b0b4ee4a96a358ca81f38904e09a6e653668f6f5cee6c293d204d6bf845b28ea",
        ),
    ],
)
def test_frozen_image_and_pdf_manifest_bytes_are_unchanged(
    tmp_path: Path, name: str, payload: dict[str, object], expected_sha256: str
) -> None:
    destination = tmp_path / f"{name}.json"

    manifest_owner.write_manifest(destination, payload)

    assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected_sha256
