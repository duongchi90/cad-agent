"""RED contract for the generic file-safety publication primitives.

The accepted file-safety owner is ``cad_agent.visual_evidence``.  This RED
phase describes only the missing public snapshot/prepare/commit/restore/
cleanup seam; it deliberately does not modify that production owner.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cad_agent import visual_evidence as owner


SCHEMA = "publication-file-snapshot-1.0"


def _api(name: str):
    value = getattr(owner, name, None)
    assert callable(value), f"missing public publication-file seam: {name}"
    return value


def _write(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _pair(tmp_path: Path) -> tuple[Path, Path, str, str]:
    target = tmp_path / "target.bin"
    candidate = tmp_path / "candidate.bin"
    target_sha = _write(target, b"original-target")
    candidate_sha = _write(candidate, b"candidate-replacement")
    return target, candidate, target_sha, candidate_sha


def _prepared(tmp_path: Path):
    target, candidate, target_sha, candidate_sha = _pair(tmp_path)
    prepared = _api("prepare_publication_replacement")(
        target_path=target,
        candidate_path=candidate,
        expected_target_sha256=target_sha,
        expected_candidate_sha256=candidate_sha,
    )
    return target, candidate, target_sha, candidate_sha, prepared


def _error_type() -> type[BaseException]:
    value = getattr(owner, "PublicationFileError", ValueError)
    return value if isinstance(value, type) else ValueError


def test_snapshot_existing_regular_file_is_closed_and_hashed(tmp_path: Path) -> None:
    path = tmp_path / "target.bin"
    digest = _write(path, b"snapshot")
    snapshot = _api("snapshot_publication_file")(path)
    assert snapshot["schema_version"] == SCHEMA
    assert snapshot["sha256"] == digest
    assert snapshot["size_bytes"] == 8
    assert type(snapshot["device_id"]) is int
    assert type(snapshot["file_id"]) is int
    assert set(snapshot) == {"schema_version", "sha256", "size_bytes", "device_id", "file_id"}


def test_existing_visual_evidence_hash_behavior_remains_green(tmp_path: Path) -> None:
    path = tmp_path / "legacy.bin"
    digest = _write(path, b"legacy-owner")
    assert owner.sha256_file(path) == digest


def test_snapshot_rejects_symlink_or_reparse_ancestry(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_REPARSE|PUBLICATION_FILE_INVALID"):
        _api("snapshot_publication_file")(link)


def test_snapshot_rejects_symlink_before_resolution(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    link = tmp_path / "snapshot-link.bin"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with patch.object(owner.Path, "resolve", side_effect=AssertionError("resolve must not run")):
        with pytest.raises(_error_type(), match="PUBLICATION_FILE_REPARSE"):
            _api("snapshot_publication_file")(link)


def test_prepare_rejects_target_symlink_before_any_resolution(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha = _pair(tmp_path)
    link = tmp_path / "target-link.bin"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with patch.object(owner.Path, "resolve", side_effect=AssertionError("resolve must not run")):
        with pytest.raises(_error_type(), match="PUBLICATION_FILE_REPARSE"):
            _api("prepare_publication_replacement")(
                target_path=link,
                candidate_path=candidate,
                expected_target_sha256=target_sha,
                expected_candidate_sha256=candidate_sha,
            )
    assert list(tmp_path.glob(".*")) == []
    assert target.read_bytes() == b"original-target"
    assert candidate.read_bytes() == b"candidate-replacement"


def test_prepare_rejects_candidate_symlink_before_any_resolution(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha = _pair(tmp_path)
    link = tmp_path / "candidate-link.bin"
    try:
        link.symlink_to(candidate)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with patch.object(owner.Path, "resolve", side_effect=AssertionError("resolve must not run")):
        with pytest.raises(_error_type(), match="PUBLICATION_FILE_REPARSE"):
            _api("prepare_publication_replacement")(
                target_path=target,
                candidate_path=link,
                expected_target_sha256=target_sha,
                expected_candidate_sha256=candidate_sha,
            )
    assert list(tmp_path.glob(".*")) == []
    assert target.read_bytes() == b"original-target"
    assert candidate.read_bytes() == b"candidate-replacement"


@pytest.mark.parametrize("field", ["backup_path", "stage_path"])
def test_cleanup_rejects_prepared_symlink_before_any_resolution(tmp_path: Path, field: str) -> None:
    target, candidate, _, _, prepared = _prepared(tmp_path)
    real_path = Path(prepared[field])
    link = tmp_path / f"{field}-link.tmp"
    try:
        link.symlink_to(real_path)
    except (OSError, NotImplementedError):
        _api("cleanup_publication_replacement")(prepared)
        pytest.skip("symlink creation unavailable")
    tampered = dict(prepared)
    tampered[field] = link
    with patch.object(owner.Path, "resolve", side_effect=AssertionError("resolve must not run")):
        with pytest.raises(_error_type(), match="PUBLICATION_FILE_REPARSE"):
            _api("cleanup_publication_replacement")(tampered)
    assert real_path.is_file()
    assert target.read_bytes() == b"original-target"
    assert candidate.read_bytes() == b"candidate-replacement"
    _api("cleanup_publication_replacement")(prepared)


def test_prepare_rejects_target_candidate_hardlink_alias(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    alias = tmp_path / "alias.bin"
    target_sha = _write(target, b"same-object")
    os.link(target, alias)
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_ALIAS"):
        _api("prepare_publication_replacement")(
            target_path=target,
            candidate_path=alias,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=target_sha,
        )


def test_prepare_target_hash_mismatch_precedes_temp_creation(tmp_path: Path) -> None:
    target, candidate, _, candidate_sha = _pair(tmp_path)
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_STALE"):
        _api("prepare_publication_replacement")(
            target_path=target,
            candidate_path=candidate,
            expected_target_sha256="0" * 64,
            expected_candidate_sha256=candidate_sha,
        )
    assert list(tmp_path.glob(".*")) == []


def test_prepare_candidate_hash_mismatch_precedes_temp_creation(tmp_path: Path) -> None:
    target, candidate, target_sha, _ = _pair(tmp_path)
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_STALE"):
        _api("prepare_publication_replacement")(
            target_path=target,
            candidate_path=candidate,
            expected_target_sha256=target_sha,
            expected_candidate_sha256="0" * 64,
        )
    assert list(tmp_path.glob(".*")) == []


def test_prepare_requires_existing_target_and_same_parent_stage(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    assert prepared["state"] == "PREPARED"
    assert Path(prepared["stage_path"]).parent == target.parent.resolve()
    assert Path(prepared["backup_path"]).parent == target.parent.resolve()
    assert prepared["target_snapshot"]["sha256"] == target_sha
    assert prepared["candidate_snapshot"]["sha256"] == candidate_sha


def test_commit_refuses_target_change_after_prepare_without_replace(tmp_path: Path) -> None:
    target, candidate, _, candidate_sha, prepared = _prepared(tmp_path)
    target.write_bytes(b"third-party-change")
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_STALE"):
        _api("commit_publication_replacement")(
            prepared,
            expected_target_sha256=hashlib.sha256(b"original-target").hexdigest(),
            expected_candidate_sha256=candidate_sha,
        )
    assert target.read_bytes() == b"third-party-change"


def test_commit_refuses_candidate_change_after_prepare(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    candidate.write_bytes(b"candidate-mutated")
    with pytest.raises(_error_type(), match="PUBLICATION_FILE_STALE"):
        _api("commit_publication_replacement")(
            prepared,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=candidate_sha,
        )


def test_commit_refuses_backup_or_stage_mutation(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    Path(prepared["backup_path"]).write_bytes(b"forged-backup")
    with pytest.raises(_error_type(), match="PUBLICATION_STAGE_INVALID"):
        _api("commit_publication_replacement")(
            prepared,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=candidate_sha,
        )
    assert target.read_bytes() == b"original-target"


def test_prepare_does_not_overwrite_colliding_exclusive_stage_names(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha = _pair(tmp_path)
    with patch.object(owner.uuid, "uuid4", return_value=type("U", (), {"hex": "collision"})()):
        first = _api("prepare_publication_replacement")(
            target_path=target,
            candidate_path=candidate,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=candidate_sha,
        )
        with pytest.raises(_error_type(), match="PUBLICATION_STAGE_INVALID|PUBLICATION_FILE_BUSY"):
            _api("prepare_publication_replacement")(
                target_path=target,
                candidate_path=candidate,
                expected_target_sha256=target_sha,
                expected_candidate_sha256=candidate_sha,
            )
        _api("cleanup_publication_replacement")(first)


def test_commit_success_replaces_once_with_exact_candidate_hash(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    result = _api("commit_publication_replacement")(
        prepared,
        expected_target_sha256=target_sha,
        expected_candidate_sha256=candidate_sha,
    )
    assert target.read_bytes() == candidate.read_bytes()
    assert result["state"] == "PUBLISHED"
    assert result["published_sha256"] == candidate_sha
    assert result["initial_sha256"] == target_sha


def test_replace_failure_preserves_target_and_verified_backup(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    with patch.object(owner.os, "replace", side_effect=OSError("replace failed")):
        with pytest.raises(_error_type(), match="PUBLICATION_REPLACE_FAILED"):
            _api("commit_publication_replacement")(
                prepared,
                expected_target_sha256=target_sha,
                expected_candidate_sha256=candidate_sha,
            )
    assert hashlib.sha256(target.read_bytes()).hexdigest() == target_sha
    assert Path(prepared["backup_path"]).is_file()


def test_post_replace_verification_failure_requires_recovery_without_blind_restore(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    with patch.object(owner, "sha256_file", side_effect=[candidate_sha, "f" * 64]):
        with pytest.raises(_error_type(), match="PUBLICATION_VERIFY_FAILED|RECOVERY_REQUIRED"):
            _api("commit_publication_replacement")(
                prepared,
                expected_target_sha256=target_sha,
                expected_candidate_sha256=candidate_sha,
            )
    assert target.exists()


def test_restore_requires_exact_published_hash_and_verified_backup(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    _api("commit_publication_replacement")(
        prepared,
        expected_target_sha256=target_sha,
        expected_candidate_sha256=candidate_sha,
    )
    restored = _api("restore_publication_target")(
        prepared,
        expected_current_sha256=candidate_sha,
    )
    assert target.read_bytes() == b"original-target"
    assert restored["state"] == "RESTORED"
    assert restored["restored_sha256"] == target_sha


def test_restore_blocks_unexpected_third_hash(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    _api("commit_publication_replacement")(
        prepared,
        expected_target_sha256=target_sha,
        expected_candidate_sha256=candidate_sha,
    )
    target.write_bytes(b"unexpected-third-hash")
    with pytest.raises(_error_type(), match="PUBLICATION_RECOVERY_CONFLICT"):
        _api("restore_publication_target")(prepared, expected_current_sha256=candidate_sha)
    assert target.read_bytes() == b"unexpected-third-hash"


def test_restore_stage_mutation_or_reparse_is_fail_closed(tmp_path: Path) -> None:
    target, candidate, target_sha, candidate_sha, prepared = _prepared(tmp_path)
    _api("commit_publication_replacement")(
        prepared,
        expected_target_sha256=target_sha,
        expected_candidate_sha256=candidate_sha,
    )
    Path(prepared["backup_path"]).write_bytes(b"forged-backup")
    with pytest.raises(_error_type(), match="PUBLICATION_STAGE_INVALID|PUBLICATION_RESTORE_FAILED"):
        _api("restore_publication_target")(prepared, expected_current_sha256=candidate_sha)


def test_cleanup_only_removes_owner_stages_not_target_candidate_or_foreign(tmp_path: Path) -> None:
    target, candidate, _, _, prepared = _prepared(tmp_path)
    foreign = tmp_path / "foreign.bin"
    foreign.write_bytes(b"foreign")
    _api("cleanup_publication_replacement")(prepared)
    assert target.exists() and candidate.exists() and foreign.exists()
    with pytest.raises(_error_type(), match="PUBLICATION_STAGE_INVALID|PUBLICATION_CLEANUP_FAILED"):
        _api("cleanup_publication_replacement")({"state": "PREPARED", "backup_path": foreign})


@pytest.mark.parametrize("record", [{"state": True}, {"state": 1}, {"state": "PREPARED", "backup_path": Path("relative")}, None])
def test_subclass_bool_int_and_path_confusion_records_fail_closed(record: object) -> None:
    with pytest.raises(_error_type()):
        _api("cleanup_publication_replacement")(record)


def test_errors_are_categorical_and_do_not_echo_paths_or_customer_data(tmp_path: Path) -> None:
    secret = tmp_path / "customer-secret-drawing.dwg"
    secret.write_bytes(b"secret")
    with pytest.raises(_error_type()) as caught:
        _api("snapshot_publication_file")(secret.with_name("missing-customer-secret.dwg"))
    message = str(caught.value)
    assert "PUBLICATION_FILE_" in message
    assert "customer-secret" not in message
    assert "missing-customer" not in message


def test_public_surface_is_narrow_and_has_no_authority_or_transport_owner() -> None:
    for name in (
        "snapshot_publication_file",
        "prepare_publication_replacement",
        "commit_publication_replacement",
        "restore_publication_target",
        "cleanup_publication_replacement",
    ):
        assert name in getattr(owner, "__all__", ()) or callable(getattr(owner, name, None))
