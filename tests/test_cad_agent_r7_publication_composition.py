"""RED/contract tests for the thin R7 publication composition boundary."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


MODULE = "cad_agent.verified_publisher"
SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_ARTIFACT = "c" * 64
SHA_MUTATION = "d" * 64
SHA_R5 = "e" * 64
SHA_TARGET = "f" * 64
SHA_TARGET_ID = "1" * 64
SHA_AUTH = "2" * 64
SHA_MANIFEST = "3" * 64
RUN_ID = "run-r7-231"


def _r7_module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, "R7_VERIFIED_PUBLISHER_MISSING"
    return importlib.import_module(MODULE)


def _state(*, selected_sha: str = SHA_CANDIDATE) -> dict[str, object]:
    return {
        "current_candidate_revision_sha256": selected_sha,
        "state_sha256": SHA_STATE,
        "candidate_revisions": [
            {
                "candidate_revision_sha256": selected_sha,
                "run_id": RUN_ID,
                "candidate_artifacts": {"artifact_sha256": SHA_ARTIFACT},
                "mutation_evidence": {
                    "latest_mutation_evidence_sha256": SHA_MUTATION,
                },
            }
        ],
    }


def _r5(*, verdict: str = "PASS") -> dict[str, object]:
    return {
        "verdict": verdict,
        "verdict_sha256": SHA_R5,
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "latest_mutation_sha256": SHA_MUTATION,
    }


def _authorization() -> dict[str, object]:
    return {
        "authorization_id": "authorization-r7-231",
        "run_id": RUN_ID,
        "target_path": "C:\\synthetic\\target.dwg",
        "expected_initial_sha256": SHA_TARGET,
    }


def _snapshot(sha256: str, *, file_id: int) -> dict[str, object]:
    return {
        "schema_version": "publication-file-snapshot-1.0",
        "sha256": sha256,
        "size_bytes": 128,
        "device_id": 1,
        "file_id": file_id,
    }


def _prepared(target_path: Path, candidate_path: Path) -> dict[str, object]:
    return {
        "schema_version": "publication-file-prepared-1.0",
        "state": "PREPARED",
        "target_path": target_path,
        "candidate_path": candidate_path,
    }


def _invoke(
    module,
    tmp_path: Path,
    *,
    verdict: str = "PASS",
    transition_side_effect=None,
    cleanup_side_effect=None,
    state_validator_side_effect=None,
):
    manifest = tmp_path / "run-manifest.json"
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest.write_text("{}", encoding="utf-8")
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")

    events: list[str] = []
    transitions: list[str] = []

    state_validator = Mock(
        side_effect=state_validator_side_effect
        if state_validator_side_effect is not None
        else lambda _value: copy.deepcopy(_state())
    )
    r5_validator = Mock(side_effect=lambda _value, **_kwargs: copy.deepcopy(_r5(verdict=verdict)))
    snapshot = Mock(
        side_effect=lambda path: (
            _snapshot(SHA_ARTIFACT, file_id=2)
            if path == candidate
            else _snapshot(SHA_TARGET, file_id=3)
        )
    )

    def transition(*_args, **kwargs):
        action = kwargs["action"]
        events.append(action)
        transitions.append(action)
        if transition_side_effect is not None:
            return transition_side_effect(action, kwargs)
        return {"publication_lifecycle": {"publication_state": action}}

    prepare = Mock(
        side_effect=lambda **_kwargs: (
            events.append("PREPARE") or _prepared(target, candidate)
        )
    )
    commit = Mock(
        side_effect=lambda *_args, **_kwargs: (
            events.append("COMMIT")
            or {
                "state": "PUBLISHED",
                "initial_sha256": SHA_TARGET,
                "published_sha256": SHA_ARTIFACT,
                "backup_sha256": SHA_TARGET,
            }
        )
    )
    restore = Mock(
        side_effect=lambda *_args, **_kwargs: (
            events.append("RESTORE")
            or {
                "state": "RESTORED",
                "restored_sha256": SHA_TARGET,
                "previous_sha256": SHA_ARTIFACT,
            }
        )
    )

    def cleanup(*_args, **_kwargs):
        events.append("CLEANUP")
        if cleanup_side_effect is not None:
            return cleanup_side_effect()
        return None

    cleanup_mock = Mock(side_effect=cleanup)

    with (
        patch.object(module, "validate_candidate_revision_state", state_validator),
        patch.object(module, "validate_visual_verdict_result", r5_validator),
        patch.object(module, "snapshot_publication_file", snapshot),
        patch.object(module, "validate_visual_contract", Mock(return_value=_authorization())),
        patch.object(module, "require_auto_publish_authorized", Mock()),
        patch.object(module, "manifest_sha256_file", Mock(return_value=SHA_MANIFEST)),
        patch.object(module, "transition_publication_lifecycle", Mock(side_effect=transition)),
        patch.object(module, "prepare_publication_replacement", prepare),
        patch.object(module, "commit_publication_replacement", commit),
        patch.object(module, "restore_publication_target", restore),
        patch.object(module, "cleanup_publication_replacement", cleanup_mock),
    ):
        result = module.execute_verified_publication(
            run_id=RUN_ID,
            candidate_state=_state(),
            r5_verdict_result=_r5(verdict=verdict),
            auto_publish_authorization=_authorization(),
            manifest_path=manifest,
            expected_manifest_sha256=SHA_MANIFEST,
            candidate_path=candidate,
            target_path=target,
        )
    return result, events, transitions, {
        "state_validator": state_validator,
        "r5_validator": r5_validator,
        "snapshot": snapshot,
        "prepare": prepare,
        "commit": commit,
        "restore": restore,
        "cleanup": cleanup_mock,
    }


def test_r7_publication_composition_module_exists() -> None:
    module = _r7_module()
    assert module.__name__ == MODULE


def test_r7_publication_composition_exposes_exact_public_entrypoints() -> None:
    module = _r7_module()
    execute = getattr(module, "execute_verified_publication", None)
    validate = getattr(module, "validate_verified_publication_result", None)
    error = getattr(module, "VerifiedPublisherError", None)
    version = getattr(module, "R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION", None)

    assert callable(execute), "R7_EXECUTE_PUBLIC_SEAM_MISSING"
    assert callable(validate), "R7_RESULT_VALIDATOR_PUBLIC_SEAM_MISSING"
    assert isinstance(error, type) and issubclass(error, ValueError)
    assert version == "r7-verified-publication-result-1.0"


def test_r7_execute_surface_requires_only_composition_inputs() -> None:
    module = _r7_module()
    execute = getattr(module, "execute_verified_publication", None)
    assert callable(execute), "R7_EXECUTE_PUBLIC_SEAM_MISSING"

    signature = inspect.signature(execute)
    assert list(signature.parameters) == [
        "run_id",
        "candidate_state",
        "r5_verdict_result",
        "auto_publish_authorization",
        "manifest_path",
        "expected_manifest_sha256",
        "candidate_path",
        "target_path",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_happy_path_orders_claim_prepare_commit_published_cleanup_consume(tmp_path: Path) -> None:
    module = _r7_module()
    result, events, transitions, mocks = _invoke(module, tmp_path)
    assert result["schema_version"] == "r7-verified-publication-result-1.0"
    assert result["publication_state"] == "PUBLISHED"
    assert result["published_artifact_sha256"] == SHA_ARTIFACT
    assert events == [
        "CLAIM",
        "PREPARE",
        "COMMIT",
        "RECORD_PUBLISHED",
        "CLEANUP",
        "CONSUME",
    ]
    assert transitions == ["CLAIM", "RECORD_PUBLISHED", "CONSUME"]
    assert mocks["state_validator"].call_count == 2
    assert mocks["r5_validator"].call_count == 2


def test_cleanup_failure_after_publish_does_not_consume_authorization(tmp_path: Path) -> None:
    module = _r7_module()

    def fail_cleanup() -> None:
        raise ValueError("synthetic cleanup failure")

    with pytest.raises(module.VerifiedPublisherError):
        _invoke(module, tmp_path, cleanup_side_effect=fail_cleanup)

    # A second run captures calls without raising from the assertion path itself.
    actions: list[str] = []

    def transition(action: str, _kwargs: dict[str, object]):
        actions.append(action)
        return {"publication_lifecycle": {"publication_state": action}}

    try:
        _invoke(
            module,
            tmp_path / "retry",
            transition_side_effect=transition,
            cleanup_side_effect=fail_cleanup,
        )
    except module.VerifiedPublisherError:
        pass
    assert "RECORD_PUBLISHED" in actions
    assert "CONSUME" not in actions


def test_record_published_failure_after_replace_requires_recovery_before_restore(
    tmp_path: Path,
) -> None:
    module = _r7_module()
    actions: list[str] = []

    def transition(action: str, _kwargs: dict[str, object]):
        actions.append(action)
        if action == "RECORD_PUBLISHED":
            raise ValueError("synthetic manifest transition failure")
        return {"publication_lifecycle": {"publication_state": action}}

    with pytest.raises(module.VerifiedPublisherError):
        _invoke(module, tmp_path, transition_side_effect=transition)

    assert actions[0] == "CLAIM"
    assert "RECORD_PUBLISHED" in actions
    assert "REQUIRE_RECOVERY" in actions
    assert actions.index("REQUIRE_RECOVERY") > actions.index("RECORD_PUBLISHED")
    assert "RECORD_ROLLBACK" in actions
    assert "CONSUME" not in actions


def test_r5_non_pass_fails_before_claim_or_file_mutation(tmp_path: Path) -> None:
    module = _r7_module()
    manifest = tmp_path / "run-manifest.json"
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest.write_text("{}", encoding="utf-8")
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")

    transition = Mock()
    snapshot = Mock()
    prepare = Mock()
    commit = Mock()
    with (
        patch.object(module, "validate_candidate_revision_state", Mock(return_value=_state())),
        patch.object(module, "validate_visual_verdict_result", Mock(return_value=_r5(verdict="FAIL"))),
        patch.object(module, "transition_publication_lifecycle", transition),
        patch.object(module, "snapshot_publication_file", snapshot),
        patch.object(module, "prepare_publication_replacement", prepare),
        patch.object(module, "commit_publication_replacement", commit),
    ):
        with pytest.raises(module.VerifiedPublisherError, match="R7_R5_PASS_REQUIRED"):
            module.execute_verified_publication(
                run_id=RUN_ID,
                candidate_state=_state(),
                r5_verdict_result=_r5(verdict="FAIL"),
                auto_publish_authorization=_authorization(),
                manifest_path=manifest,
                expected_manifest_sha256=SHA_MANIFEST,
                candidate_path=candidate,
                target_path=target,
            )
    transition.assert_not_called()
    snapshot.assert_not_called()
    prepare.assert_not_called()
    commit.assert_not_called()


def test_candidate_file_hash_mismatch_fails_before_claim(tmp_path: Path) -> None:
    module = _r7_module()
    manifest = tmp_path / "run-manifest.json"
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest.write_text("{}", encoding="utf-8")
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    transition = Mock()
    with (
        patch.object(module, "validate_candidate_revision_state", Mock(return_value=_state())),
        patch.object(module, "validate_visual_verdict_result", Mock(return_value=_r5())),
        patch.object(
            module,
            "snapshot_publication_file",
            Mock(side_effect=[_snapshot("9" * 64, file_id=2), _snapshot(SHA_TARGET, file_id=3)]),
        ),
        patch.object(module, "transition_publication_lifecycle", transition),
    ):
        with pytest.raises(module.VerifiedPublisherError, match="R7_CANDIDATE_ARTIFACT_MISMATCH"):
            module.execute_verified_publication(
                run_id=RUN_ID,
                candidate_state=_state(),
                r5_verdict_result=_r5(),
                auto_publish_authorization=_authorization(),
                manifest_path=manifest,
                expected_manifest_sha256=SHA_MANIFEST,
                candidate_path=candidate,
                target_path=target,
            )
    transition.assert_not_called()


def test_result_validator_rejects_unknown_or_mutated_fields() -> None:
    module = _r7_module()
    payload = {
        "schema_version": "r7-verified-publication-result-1.0",
        "publication_id": "publication-r7-231",
        "run_id": RUN_ID,
        "authorization_id": "authorization-r7-231",
        "authorization_sha256": SHA_AUTH,
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "r5_verdict_sha256": SHA_R5,
        "latest_mutation_sha256": SHA_MUTATION,
        "publishable_artifact_sha256": SHA_ARTIFACT,
        "target_snapshot_sha256": SHA_TARGET_ID,
        "published_artifact_sha256": SHA_ARTIFACT,
        "publication_state": "PUBLISHED",
    }
    from cad_agent.drawing_contracts import canonical_json_sha256

    valid = {**payload, "publication_sha256": canonical_json_sha256(payload)}
    assert module.validate_verified_publication_result(valid) == valid

    hostile = {**valid, "unknown": True}
    with pytest.raises(module.VerifiedPublisherError, match="R7_RESULT_INVALID"):
        module.validate_verified_publication_result(hostile)

    mutated = copy.deepcopy(valid)
    mutated["published_artifact_sha256"] = "9" * 64
    with pytest.raises(module.VerifiedPublisherError, match="R7_RESULT_INVALID"):
        module.validate_verified_publication_result(mutated)
