"""RED contract for the R7 durable publication lifecycle owner.

This file intentionally describes the public manifest seam before production
implementation exists.  The RED phase must fail because the owner extension
is absent, while legacy manifest reads remain backward compatible.
"""

from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cad_agent import manifest as manifest_owner
from cad_agent.drawing_contracts import canonical_json_sha256


SCHEMA_VERSION = "publication-lifecycle-1.0"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source": {"name": "drawing.png", "sha256": SHA_A, "kind": "image"},
        "configuration": {"scale_mm_per_px": 0.5},
        "approvals": {"calibration": {"approved": True, "reference": "ticket-227"}},
        "stages": {
            stage: {"state": "pending", "artifact": None, "sha256": None, "details": None}
            for stage in ("primitive_ir", "semantic_ir", "dxf")
        },
    }


def _intent(**overrides: object) -> dict[str, object]:
    value = {
        "candidate_revision_sha256": SHA_A,
        "r5_verdict_sha256": SHA_B,
        "publishable_artifact_sha256": SHA_C,
        "target_identity_sha256": SHA_D,
    }
    value.update(overrides)
    return value


def _result(**overrides: object) -> dict[str, object]:
    value = {
        "result_sha256": SHA_A,
        "published_artifact_sha256": SHA_B,
        "target_snapshot_sha256": SHA_C,
        "publication_outcome": "PUBLISHED",
    }
    value.update(overrides)
    return value


def _recovery(**overrides: object) -> dict[str, object]:
    value = {
        "recovery_sha256": SHA_A,
        "target_snapshot_sha256": SHA_B,
        "restored_artifact_sha256": SHA_C,
        "recovery_outcome": "ROLLED_BACK",
    }
    value.update(overrides)
    return value


def _write(path: Path, payload: dict[str, object] | None = None) -> str:
    manifest = payload or _manifest()
    manifest_owner.write_manifest(path, manifest)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _api(name: str):
    value = getattr(manifest_owner, name, None)
    if not callable(value):
        raise manifest_owner.ManifestError("PUBLICATION_LIFECYCLE_INVALID")
    return value


def _transition(path: Path, expected: str, *, action: str = "CLAIM", **kwargs: object):
    return _api("transition_publication_lifecycle")(
        path,
        expected_manifest_sha256=expected,
        action=action,
        publication_id=kwargs.pop("publication_id", "publication-227"),
        authorization_id=kwargs.pop("authorization_id", "authorization-227"),
        authorization_sha256=kwargs.pop("authorization_sha256", SHA_D),
        intent=kwargs.pop("intent", _intent()),
        result=kwargs.pop("result", None),
        recovery=kwargs.pop("recovery", None),
        **kwargs,
    )


def test_legacy_manifest_reads_without_injected_publication_lifecycle(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    _write(path)
    loaded = manifest_owner.read_manifest(path)
    assert "publication_lifecycle" not in loaded


def test_claim_persists_closed_intent_and_canonical_intent_hash_before_result(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    claimed = _transition(path, expected)
    lifecycle = claimed["publication_lifecycle"]
    assert lifecycle["schema_version"] == SCHEMA_VERSION
    assert lifecycle["authorization_state"] == "CLAIMED"
    assert lifecycle["publication_state"] == "INTENT_RECORDED"
    assert lifecycle["result"] is None
    assert lifecycle["intent"] == _intent()
    assert lifecycle["intent_sha256"] == canonical_json_sha256(_intent())


def test_exact_claim_replay_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    first = _transition(path, expected)
    replay = _transition(path, hashlib.sha256(path.read_bytes()).hexdigest())
    assert replay == first


def test_second_publication_cannot_claim_existing_lifecycle(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_AUTHORIZATION_CONFLICT"):
        _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), publication_id="foreign-publication")


def test_foreign_authorization_id_or_hash_cannot_overwrite_claim(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    current = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_AUTHORIZATION_CONFLICT"):
        _transition(path, current, authorization_id="foreign-authorization")
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_AUTHORIZATION_CONFLICT"):
        _transition(path, current, authorization_sha256=SHA_C)


def test_altered_intent_cannot_replay_claim(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_AUTHORIZATION_CONFLICT"):
        _transition(
            path,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            intent=_intent(publishable_artifact_sha256=SHA_D),
        )


def test_stale_expected_manifest_refuses_without_disk_mutation(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    _write(path)
    before = path.read_bytes()
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_STALE"):
        _transition(path, "0" * 64)
    assert path.read_bytes() == before


def test_crashed_manifest_writer_lock_is_reclaimed_after_exact_owner_exit(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected_manifest = _manifest()
    _write(path, expected_manifest)
    before = path.read_bytes()
    lock_path = path.with_suffix(path.suffix + ".lock")
    child_code = """
import os
import sys
from pathlib import Path
from cad_agent.manifest import _manifest_lock

lock = _manifest_lock(Path(sys.argv[1]))
lock.__enter__()
os._exit(0)
"""
    completed = subprocess.run(
        [sys.executable, "-c", child_code, str(path)],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )

    assert completed.returncode == 0
    assert lock_path.is_file()

    manifest_owner.write_manifest(path, expected_manifest)

    assert not lock_path.exists()
    assert path.read_bytes() == before


def test_manifest_lock_without_owner_identity_remains_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected_manifest = _manifest()
    _write(path, expected_manifest)
    before = path.read_bytes()
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.write_bytes(b"")

    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
        manifest_owner.write_manifest(path, expected_manifest)

    assert path.read_bytes() == before
    assert lock_path.is_file()


def test_live_manifest_lock_owner_remains_busy_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected_manifest = _manifest()
    _write(path, expected_manifest)
    ready_path = tmp_path / "owner-ready"
    child_code = """
import sys
import time
from pathlib import Path
from cad_agent.manifest import _manifest_lock

path = Path(sys.argv[1])
ready = Path(sys.argv[2])
with _manifest_lock(path):
    ready.write_text("ready", encoding="utf-8")
    time.sleep(2)
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(path), str(ready_path)],
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        deadline = time.monotonic() + 5
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready_path.is_file()
        with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
            manifest_owner.write_manifest(path, expected_manifest)
    finally:
        assert child.wait(timeout=5) == 0


def test_lock_contention_has_one_transition_success_and_no_lost_update(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    results: list[object] = []

    def claim() -> None:
        try:
            results.append(_transition(path, expected))
        except Exception as exc:  # noqa: BLE001 - categorical RED oracle
            results.append(exc)

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    successes = [value for value in results if isinstance(value, dict)]
    failures = [value for value in results if isinstance(value, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "PUBLICATION_MANIFEST_BUSY" in str(failures[0]) or "PUBLICATION_MANIFEST_STALE" in str(failures[0])


def test_ordinary_write_manifest_honors_active_publication_lock(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    transition = _api("transition_publication_lifecycle")
    entered = threading.Event()
    release = threading.Event()
    original_replace = manifest_owner.os.replace

    def blocking_replace(source: object, target: object) -> None:
        if Path(target) == path and not entered.is_set():
            entered.set()
            assert release.wait(timeout=5)
        original_replace(source, target)

    monkeypatch.setattr(manifest_owner.os, "replace", blocking_replace)
    errors: list[Exception] = []

    def claim() -> None:
        try:
            transition(
                path,
                expected_manifest_sha256=expected,
                action="CLAIM",
                publication_id="publication-227",
                authorization_id="authorization-227",
                authorization_sha256=SHA_D,
                intent=_intent(),
            )
        except Exception as exc:  # noqa: BLE001 - bounded concurrency oracle
            errors.append(exc)

    worker = threading.Thread(target=claim)
    worker.start()
    assert entered.wait(timeout=5)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_MANIFEST_BUSY"):
        manifest_owner.write_manifest(path, _manifest())
    release.set()
    worker.join(timeout=5)
    assert not errors


@pytest.mark.parametrize(
    ("action", "result", "recovery", "publication_state"),
    [
        ("RECORD_PUBLISHED", _result(), None, "PUBLISHED"),
        ("RECORD_FAILED", _result(publication_outcome="FAILED"), None, "FAILED"),
        ("REQUIRE_RECOVERY", None, _recovery(recovery_outcome="RECOVERY_REQUIRED"), "RECOVERY_REQUIRED"),
        ("RECORD_ROLLBACK", None, _recovery(), "ROLLED_BACK"),
    ],
)
def test_terminal_lifecycle_transitions_bind_existing_claim(
    tmp_path: Path,
    action: str,
    result: dict[str, object] | None,
    recovery: dict[str, object] | None,
    publication_state: str,
) -> None:
    path = tmp_path / f"{action}.json"
    expected = _write(path)
    _transition(path, expected)
    updated = _transition(
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        action=action,
        result=result,
        recovery=recovery,
    )
    lifecycle = updated["publication_lifecycle"]
    assert lifecycle["publication_state"] == publication_state
    assert lifecycle["authorization_state"] == "CLAIMED"


def test_failure_recovery_and_rollback_never_return_grant_to_unused(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    updated = _transition(
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        action="RECORD_FAILED",
        result=_result(publication_outcome="FAILED"),
    )
    assert updated["publication_lifecycle"]["authorization_state"] == "CLAIMED"


def test_consume_before_published_refuses_without_releasing_claim(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_TRANSITION_INVALID"):
        _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME")
    current = manifest_owner.read_manifest(path)
    assert current["publication_lifecycle"]["authorization_state"] == "CLAIMED"


def test_consume_requires_exact_pair_and_replay_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    _transition(
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        action="RECORD_PUBLISHED",
        result=_result(),
    )
    consumed = _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME")
    replay = _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME")
    assert consumed == replay
    assert consumed["publication_lifecycle"]["authorization_state"] == "CONSUMED"


def test_consumed_lifecycle_cannot_be_revived_by_different_pair(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="RECORD_PUBLISHED", result=_result())
    _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME")
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_REPLAY_MISMATCH"):
        _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME", publication_id="other")


@pytest.mark.parametrize(
    "bad_intent",
    [
        {"unknown": True},
        {"candidate_revision_sha256": True},
        {"candidate_revision_sha256": 1},
        {"candidate_revision_sha256": "not-a-hash"},
        {"candidate_revision_sha256": "A" * 64},
        {"candidate_revision_sha256": "a" * 64, "__class__": "spoof"},
    ],
)
def test_malformed_or_confusing_intent_fails_closed(tmp_path: Path, bad_intent: dict[str, object]) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_LIFECYCLE_INVALID"):
        _transition(path, expected, intent=bad_intent)


def test_replace_failure_preserves_prior_manifest_and_does_not_consume(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    before = path.read_bytes()

    def fail_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(manifest_owner.os, "replace", fail_replace)
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_TRANSITION_INVALID"):
        _transition(path, expected)
    assert path.read_bytes() == before


def test_concurrent_same_grant_claims_have_at_most_one_semantic_claim(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    outcomes: list[object] = []

    def claim() -> None:
        try:
            outcomes.append(_transition(path, expected))
        except Exception as exc:  # noqa: BLE001 - RED concurrency oracle
            outcomes.append(exc)

    workers = [threading.Thread(target=claim) for _ in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sum(isinstance(value, dict) for value in outcomes) <= 1


def test_errors_are_categorical_and_do_not_echo_targets_or_authorizations(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    secret_path = "customer-private-target-227.dxf"
    with pytest.raises(manifest_owner.ManifestError) as caught:
        _transition(
            path,
            expected,
            publication_id=secret_path,
            authorization_id="customer-secret-authorization",
            intent=_intent(target_identity_sha256=secret_path),
        )
    assert str(caught.value) in {
        "PUBLICATION_LIFECYCLE_INVALID",
        "PUBLICATION_AUTHORIZATION_CONFLICT",
        "PUBLICATION_TRANSITION_INVALID",
    }
    assert secret_path not in str(caught.value)


def test_publication_owner_does_not_import_downstream_authority_or_live_owners() -> None:
    source = inspect.getsource(manifest_owner)
    forbidden = ("visual_contracts", "approved_repair_adapter", "visual_supervisor_adapter", "autocad", "file_ipc", "publisher")
    assert not any(name in source.lower() for name in forbidden)


def test_validator_rejects_published_state_with_failed_outcome(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    published = _transition(
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        action="RECORD_PUBLISHED",
        result=_result(),
    )
    lifecycle = published["publication_lifecycle"]
    assert isinstance(lifecycle, dict)
    result = lifecycle["result"]
    assert isinstance(result, dict)
    result["publication_outcome"] = "FAILED"
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_LIFECYCLE_INVALID"):
        manifest_owner.validate_publication_lifecycle(lifecycle)


def test_record_published_rejects_failed_outcome_and_cannot_consume(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    expected = _write(path)
    _transition(path, expected)
    before = path.read_bytes()
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_TRANSITION_INVALID"):
        _transition(
            path,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            action="RECORD_PUBLISHED",
            result=_result(publication_outcome="FAILED"),
        )
    assert path.read_bytes() == before
    current = manifest_owner.read_manifest(path)
    lifecycle = current["publication_lifecycle"]
    assert lifecycle["authorization_state"] == "CLAIMED"
    assert lifecycle["publication_state"] == "INTENT_RECORDED"
    assert lifecycle["result"] is None
    with pytest.raises(manifest_owner.ManifestError, match="PUBLICATION_TRANSITION_INVALID"):
        _transition(path, hashlib.sha256(path.read_bytes()).hexdigest(), action="CONSUME")
