"""Causal RED and replay contract for the R7 publication composition boundary."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


MODULE = "cad_agent.publication_composition"
SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_ARTIFACT = "c" * 64
SHA_MUTATION = "d" * 64
SHA_R5 = "e" * 64
SHA_TARGET = "f" * 64
SHA_MANIFEST = "1" * 64
RUN_ID = "run-r7-replay"


def _r7_module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, "R7_PUBLICATION_COMPOSITION_MISSING"
    return importlib.import_module(MODULE)


def _state() -> dict[str, object]:
    return {
        "current_candidate_revision_sha256": SHA_CANDIDATE,
        "state_sha256": SHA_STATE,
        "candidate_revisions": [
            {
                "candidate_revision_sha256": SHA_CANDIDATE,
                "run_id": RUN_ID,
                "candidate_artifacts": {"artifact_sha256": SHA_ARTIFACT},
                "mutation_evidence": {
                    "latest_mutation_evidence_sha256": SHA_MUTATION,
                },
            }
        ],
    }


def _r5() -> dict[str, object]:
    return {"verdict": "PASS", "verdict_sha256": SHA_R5}


def _auth() -> dict[str, object]:
    return {
        "schema_version": "auto-publish-authorization-1.0",
        "authorization_id": "auth-r7-replay",
        "run_id": RUN_ID,
        "policy": "PASS_AND_APPROVED_ONLY",
        "target_path": "C:\\synthetic\\target.dwg",
        "expected_initial_sha256": SHA_TARGET,
        "allowed_backup_root": "C:\\synthetic\\backup",
        "single_use": True,
        "expires_after_run": True,
        "consumed": False,
        "authorized_by": "owner",
        "approval_reference": "approval-r7",
        "status": "APPROVED",
    }


def _snapshot(sha: str, file_id: int) -> dict[str, object]:
    return {
        "schema_version": "publication-file-snapshot-1.0",
        "path": "ignored",
        "sha256": sha,
        "size_bytes": 8,
        "device_id": 1,
        "file_id": file_id,
    }


def test_r7_publication_composition_module_exists() -> None:
    module = _r7_module()
    assert module.__name__ == MODULE


def test_r7_publication_composition_exposes_exact_public_entrypoints() -> None:
    module = _r7_module()
    assert callable(getattr(module, "execute_verified_publication", None))
    assert callable(getattr(module, "validate_verified_publication_result", None))
    error = getattr(module, "VerifiedPublisherError", None)
    assert isinstance(error, type) and issubclass(error, ValueError)
    assert (
        getattr(module, "R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION", None)
        == "r7-verified-publication-result-1.0"
    )


def test_r7_execute_surface_requires_only_composition_inputs() -> None:
    module = _r7_module()
    signature = inspect.signature(module.execute_verified_publication)
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


def test_consumed_exact_claim_replay_refuses_before_prepare_or_commit(tmp_path: Path) -> None:
    module = _r7_module()
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")

    prepare = Mock()
    commit = Mock()
    consumed_claim = {
        "publication_lifecycle": {
            "authorization_state": "CONSUMED",
            "publication_state": "PUBLISHED",
        }
    }
    with (
        patch.object(module, "validate_candidate_revision_state", Mock(return_value=copy.deepcopy(_state()))),
        patch.object(module, "validate_visual_verdict_result", Mock(return_value=_r5())),
        patch.object(module, "validate_visual_contract", Mock(return_value=_auth())),
        patch.object(module, "require_auto_publish_authorized", Mock()),
        patch.object(
            module,
            "snapshot_publication_file",
            Mock(side_effect=[_snapshot(SHA_ARTIFACT, 2), _snapshot(SHA_TARGET, 3)]),
        ),
        patch.object(module, "transition_publication_lifecycle", Mock(return_value=consumed_claim)),
        patch.object(module, "prepare_publication_replacement", prepare),
        patch.object(module, "commit_publication_replacement", commit),
    ):
        with pytest.raises(module.VerifiedPublisherError, match="REPLAY|CLAIM|CONSUMED"):
            module.execute_verified_publication(
                run_id=RUN_ID,
                candidate_state=_state(),
                r5_verdict_result=_r5(),
                auto_publish_authorization=_auth(),
                manifest_path=manifest,
                expected_manifest_sha256=SHA_MANIFEST,
                candidate_path=candidate,
                target_path=target,
            )
    prepare.assert_not_called()
    commit.assert_not_called()


def test_claimed_exact_claim_replay_refuses_before_prepare(tmp_path: Path) -> None:
    module = _r7_module()
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")
    prepare = Mock()
    claimed = {"publication_lifecycle": {"authorization_state": "CLAIMED", "publication_state": "INTENT_RECORDED"}}
    with (
        patch.object(module, "validate_candidate_revision_state", Mock(return_value=copy.deepcopy(_state()))),
        patch.object(module, "validate_visual_verdict_result", Mock(return_value=_r5())),
        patch.object(module, "validate_visual_contract", Mock(return_value=_auth())),
        patch.object(module, "require_auto_publish_authorized", Mock()),
        patch.object(module, "snapshot_publication_file", Mock(side_effect=[_snapshot(SHA_ARTIFACT, 2), _snapshot(SHA_TARGET, 3)])),
        patch.object(module, "transition_publication_lifecycle", Mock(return_value=claimed)),
        patch.object(module, "_manifest_sha", Mock(return_value=SHA_MANIFEST)),
        patch.object(module, "prepare_publication_replacement", prepare),
    ):
        with pytest.raises(module.VerifiedPublisherError, match="REPLAY|CLAIM"):
            module.execute_verified_publication(
                run_id=RUN_ID,
                candidate_state=_state(),
                r5_verdict_result=_r5(),
                auto_publish_authorization=_auth(),
                manifest_path=manifest,
                expected_manifest_sha256=SHA_MANIFEST,
                candidate_path=candidate,
                target_path=target,
            )
    prepare.assert_not_called()


def test_cleanup_failure_keeps_authorization_unconsumed(tmp_path: Path) -> None:
    module = _r7_module()
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")
    actions: list[str] = []
    claimed = {"publication_lifecycle": {"authorization_state": "CLAIMED", "publication_state": "INTENT_RECORDED"}}

    def transition(*_args, action: str, **_kwargs):
        actions.append(action)
        return copy.deepcopy(claimed)

    with (
        patch.object(module, "validate_candidate_revision_state", Mock(return_value=copy.deepcopy(_state()))),
        patch.object(module, "validate_visual_verdict_result", Mock(return_value=_r5())),
        patch.object(module, "validate_visual_contract", Mock(return_value=_auth())),
        patch.object(module, "require_auto_publish_authorized", Mock()),
        patch.object(module, "snapshot_publication_file", Mock(side_effect=[_snapshot(SHA_ARTIFACT, 2), _snapshot(SHA_TARGET, 3)])),
        patch.object(module, "_transition", transition),
        patch.object(module, "_manifest_sha", Mock(return_value="2" * 64)),
        patch.object(module, "prepare_publication_replacement", Mock(return_value={})),
        patch.object(module, "commit_publication_replacement", Mock(return_value={"published_sha256": SHA_ARTIFACT})),
        patch.object(module, "cleanup_publication_replacement", Mock(side_effect=OSError("cleanup blocked"))),
    ):
        with pytest.raises(module.VerifiedPublisherError, match="R7_CLEANUP_FAILED"):
            module.execute_verified_publication(
                run_id=RUN_ID,
                candidate_state=_state(),
                r5_verdict_result=_r5(),
                auto_publish_authorization=_auth(),
                manifest_path=manifest,
                expected_manifest_sha256=SHA_MANIFEST,
                candidate_path=candidate,
                target_path=target,
            )
    assert actions == ["CLAIM", "RECORD_PUBLISHED"]
