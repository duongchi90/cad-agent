"""R8-S synthetic acceptance over the accepted R1-R7 public owner chain.

R8 is acceptance-only. These tests deliberately import the accepted public
owners instead of introducing a pilot dispatcher, store, transport, or hash
implementation.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cad_agent import approved_repair_adapter as r6
from cad_agent import base_cad_adapter as r2
from cad_agent import candidate_revision as r4
from cad_agent import component_view_registry as r3
from cad_agent import publication_composition as r7
from cad_agent import source_fusion as r1
from cad_agent import visual_supervisor_adapter as r5
from cad_agent.drawing_contracts import canonical_json_sha256


def _public_owner_chain() -> dict[str, tuple[object, ...]]:
    return {
        "r1": (
            r1.validate_page_locators,
            r1.validate_region_locators,
            r1.validate_render_provenance,
        ),
        "r2": (
            r2.validate_base_cad_binding,
            r2.base_cad_binding_sha256,
            r2.validate_base_cad_reuse_handoff,
            r2.base_cad_reuse_handoff_sha256,
            r2.evaluate_frozen_base_cad_reuse,
        ),
        "r3": (
            r3.build_component_view_registry,
            r3.validate_component_view_registry,
            r3.component_view_registry_sha256,
            r3.finalize_component_view_correspondence,
            r3.project_linked_view_impacts,
        ),
        "r4": (
            r4.build_candidate_revision,
            r4.build_candidate_revision_state,
            r4.validate_candidate_revision_state,
        ),
        "r5": (r5.finalize_visual_verdict, r5.validate_visual_verdict_result),
        "r6": (r6.execute_approved_repair, r6.validate_approved_repair_result),
        "r7": (r7.execute_verified_publication, r7.validate_verified_publication_result),
    }


def _fixture_module(filename: str, module_name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r8_s_accepted_owner_chain_is_public_and_single_owner() -> None:
    chain = _public_owner_chain()
    assert tuple(chain) == ("r1", "r2", "r3", "r4", "r5", "r6", "r7")
    for owner, seams in chain.items():
        assert seams, owner
        assert all(callable(seam) for seam in seams), owner
        assert all(inspect.getmodule(seam) is not None for seam in seams), owner

    # R7 must compose the accepted R4/R5 validators rather than shadowing them.
    assert r7.validate_candidate_revision_state is r4.validate_candidate_revision_state
    assert r7.validate_visual_verdict_result is r5.validate_visual_verdict_result


def test_r8_s_repair_to_fresh_review_to_publication_bindings_are_exposed() -> None:
    r6_params = inspect.signature(r6.validate_approved_repair_result).parameters
    assert "expected_candidate_artifact_reference_id" in r6_params
    assert "expected_candidate_artifact_reference_sha256" in r6_params
    assert "expected_r5_failure_id" in r6_params
    assert "expected_r5_failure_sha256" in r6_params

    r5_params = inspect.signature(r5.validate_visual_verdict_result).parameters
    for required in (
        "expected_candidate_revision_sha256",
        "expected_candidate_state_sha256",
        "expected_latest_mutation_sha256",
    ):
        assert required in r5_params

    r7_params = inspect.signature(r7.execute_verified_publication).parameters
    assert tuple(r7_params) == (
        "run_id",
        "candidate_state",
        "r5_verdict_result",
        "auto_publish_authorization",
        "manifest_path",
        "expected_manifest_sha256",
        "candidate_path",
        "target_path",
    )


def test_r8_s_owner_fingerprint_is_deterministic_and_materially_bound() -> None:
    material = {
        "r3_schema": r3.COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "r4_revision_schema": r4.CANDIDATE_REVISION_SCHEMA_VERSION,
        "r4_state_schema": r4.CANDIDATE_REVISION_STATE_SCHEMA_VERSION,
        "r5_result_schema": r5.R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION,
        "r6_result_schema": r6.R6_RESULT_SCHEMA_VERSION,
        "r7_result_schema": r7.R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION,
        "chain": [
            f"{owner}:{seam.__module__}.{seam.__name__}"
            for owner, seams in _public_owner_chain().items()
            for seam in seams
        ],
    }
    seals = [canonical_json_sha256(material) for _ in range(5)]
    assert len(set(seals)) == 1

    foreign = dict(material)
    foreign["r6_result_schema"] = "foreign-r6-schema"
    assert canonical_json_sha256(foreign) != seals[0]


def test_r8_s_r3_boundary_does_not_absorb_downstream_authority() -> None:
    source = inspect.getsource(r3)
    for forbidden in (
        "from cad_agent import candidate_revision",
        "from cad_agent import visual_supervisor_adapter",
        "from cad_agent import approved_repair_adapter",
        "from cad_agent import publication_composition",
    ):
        assert forbidden not in source


def test_r8_s_r6_rejects_foreign_r5_and_r4_before_mutation_or_consume() -> None:
    fixtures = _fixture_module(
        "test_cad_agent_approved_repair_adapter.py", "r8_r6_fixtures"
    )

    foreign_r5 = fixtures._valid_inputs()
    foreign_r5["r5_failure"]["candidate_revision_sha256"] = "f" * 64
    with pytest.raises(Exception, match="candidate|binding|repair"):
        r6.execute_approved_repair(**foreign_r5)
    assert foreign_r5["executor_client"].calls == []
    assert fixtures._consume_exact(foreign_r5["authorization"]) is foreign_r5["authorization"]

    foreign_r4 = fixtures._valid_inputs()
    foreign_r4["candidate_state"]["current_candidate_revision_sha256"] = "f" * 64
    with pytest.raises(Exception, match="candidate|current|state|binding"):
        r6.execute_approved_repair(**foreign_r4)
    assert foreign_r4["executor_client"].calls == []
    assert fixtures._consume_exact(foreign_r4["authorization"]) is foreign_r4["authorization"]


def test_r8_s_post_r6_mutation_invalidates_pre_repair_r5_and_fresh_cycle_passes() -> None:
    fixtures = _fixture_module(
        "test_cad_agent_visual_supervisor_adapter.py", "r8_r5_fixtures"
    )

    stale = fixtures._valid_inputs()
    stale["authoritative_state"]["pre_repair_r5_verdict"] = {
        "verdict": "PASS",
        "latest_mutation_sha256": "0" * 64,
    }
    with pytest.raises(Exception, match="stale|R6|mutation|review"):
        fixtures._finalize(stale)

    fresh = fixtures._valid_inputs()
    latest_mutation = fresh["authoritative_state"]["visual_run_manifest"][
        "latest_mutation_sha256"
    ]
    fresh["authoritative_state"]["pre_repair_r5_verdict"] = {
        "verdict": "PASS",
        "latest_mutation_sha256": latest_mutation,
    }
    result = fixtures._finalize(fresh)
    assert result["verdict"] == "PASS"
    assert result["latest_mutation_sha256"] == latest_mutation


def test_r8_s_r7_rejects_stale_pre_repair_r5_before_file_mutation(tmp_path: Path) -> None:
    fixtures = _fixture_module(
        "test_cad_agent_visual_supervisor_adapter.py", "r8_r5_for_r7_fixtures"
    )
    r5_result = fixtures._finalize(fixtures._valid_inputs())
    stale_mutation = "2" * 64
    candidate_state = {
        "current_candidate_revision_sha256": r5_result["candidate_revision_sha256"],
        "state_sha256": r5_result["candidate_state_sha256"],
        "candidate_revisions": [
            {
                "candidate_revision_sha256": r5_result["candidate_revision_sha256"],
                "run_id": "run-r8-r7-stale",
                "candidate_artifacts": {"artifact_sha256": "3" * 64},
                "mutation_evidence": {
                    "latest_mutation_evidence_sha256": stale_mutation,
                },
            }
        ],
    }
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")
    prepare = Mock()

    with (
        patch.object(
            r7,
            "validate_candidate_revision_state",
            Mock(return_value=copy.deepcopy(candidate_state)),
        ),
        patch.object(r7, "prepare_publication_replacement", prepare),
    ):
        with pytest.raises(Exception, match="R5|verdict|mutation|invalid"):
            r7.execute_verified_publication(
                run_id="run-r8-r7-stale",
                candidate_state=candidate_state,
                r5_verdict_result=r5_result,
                auto_publish_authorization={},
                manifest_path=manifest,
                expected_manifest_sha256="4" * 64,
                candidate_path=candidate,
                target_path=target,
            )
    prepare.assert_not_called()


def test_r8_s_r7_consumed_replay_refuses_before_prepare_or_commit(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")

    run_id = "run-r8-r7-replay"
    candidate_sha = "a" * 64
    state_sha = "b" * 64
    artifact_sha = "c" * 64
    mutation_sha = "d" * 64
    r5_sha = "e" * 64
    target_sha = "f" * 64
    expected_manifest_sha = "1" * 64
    state = {
        "current_candidate_revision_sha256": candidate_sha,
        "state_sha256": state_sha,
        "candidate_revisions": [
            {
                "candidate_revision_sha256": candidate_sha,
                "run_id": run_id,
                "candidate_artifacts": {"artifact_sha256": artifact_sha},
                "mutation_evidence": {
                    "latest_mutation_evidence_sha256": mutation_sha,
                },
            }
        ],
    }
    verdict = {"verdict": "PASS", "verdict_sha256": r5_sha}
    auth = {
        "schema_version": "auto-publish-authorization-1.0",
        "authorization_id": "auth-r8-r7-replay",
        "run_id": run_id,
        "policy": "PASS_AND_APPROVED_ONLY",
        "target_path": "C:\\synthetic\\target.dwg",
        "expected_initial_sha256": target_sha,
        "allowed_backup_root": "C:\\synthetic\\backup",
        "single_use": True,
        "expires_after_run": True,
        "consumed": False,
        "authorized_by": "owner",
        "approval_reference": "approval-r8",
        "status": "APPROVED",
    }

    def snapshot(sha: str, file_id: int) -> dict[str, object]:
        return {
            "schema_version": "publication-file-snapshot-1.0",
            "path": "ignored",
            "sha256": sha,
            "size_bytes": 8,
            "device_id": 1,
            "file_id": file_id,
        }

    prepare = Mock()
    commit = Mock()
    consumed_claim = {
        "publication_lifecycle": {
            "authorization_state": "CONSUMED",
            "publication_state": "PUBLISHED",
        }
    }
    with (
        patch.object(r7, "validate_candidate_revision_state", Mock(return_value=copy.deepcopy(state))),
        patch.object(r7, "validate_visual_verdict_result", Mock(return_value=verdict)),
        patch.object(r7, "validate_visual_contract", Mock(return_value=auth)),
        patch.object(r7, "require_auto_publish_authorized", Mock()),
        patch.object(
            r7,
            "snapshot_publication_file",
            Mock(side_effect=[snapshot(artifact_sha, 2), snapshot(target_sha, 3)]),
        ),
        patch.object(r7, "transition_publication_lifecycle", Mock(return_value=consumed_claim)),
        patch.object(r7, "prepare_publication_replacement", prepare),
        patch.object(r7, "commit_publication_replacement", commit),
    ):
        with pytest.raises(Exception, match="REPLAY|CLAIM|CONSUMED"):
            r7.execute_verified_publication(
                run_id=run_id,
                candidate_state=state,
                r5_verdict_result=verdict,
                auto_publish_authorization=auth,
                manifest_path=manifest,
                expected_manifest_sha256=expected_manifest_sha,
                candidate_path=candidate,
                target_path=target,
            )
    prepare.assert_not_called()
    commit.assert_not_called()


def test_r8_s_r7_cleanup_failure_keeps_authorization_unconsumed(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.dwg"
    target = tmp_path / "target.dwg"
    manifest = tmp_path / "manifest.json"
    candidate.write_bytes(b"candidate")
    target.write_bytes(b"target")
    manifest.write_text("{}", encoding="utf-8")

    run_id = "run-r8-r7-cleanup"
    candidate_sha = "a" * 64
    state_sha = "b" * 64
    artifact_sha = "c" * 64
    mutation_sha = "d" * 64
    r5_sha = "e" * 64
    target_sha = "f" * 64
    state = {
        "current_candidate_revision_sha256": candidate_sha,
        "state_sha256": state_sha,
        "candidate_revisions": [
            {
                "candidate_revision_sha256": candidate_sha,
                "run_id": run_id,
                "candidate_artifacts": {"artifact_sha256": artifact_sha},
                "mutation_evidence": {
                    "latest_mutation_evidence_sha256": mutation_sha,
                },
            }
        ],
    }
    verdict = {"verdict": "PASS", "verdict_sha256": r5_sha}
    auth = {
        "schema_version": "auto-publish-authorization-1.0",
        "authorization_id": "auth-r8-r7-cleanup",
        "run_id": run_id,
        "policy": "PASS_AND_APPROVED_ONLY",
        "target_path": "C:\\synthetic\\target.dwg",
        "expected_initial_sha256": target_sha,
        "allowed_backup_root": "C:\\synthetic\\backup",
        "single_use": True,
        "expires_after_run": True,
        "consumed": False,
        "authorized_by": "owner",
        "approval_reference": "approval-r8",
        "status": "APPROVED",
    }

    def snapshot(sha: str, file_id: int) -> dict[str, object]:
        return {
            "schema_version": "publication-file-snapshot-1.0",
            "path": "ignored",
            "sha256": sha,
            "size_bytes": 8,
            "device_id": 1,
            "file_id": file_id,
        }

    actions: list[str] = []
    claimed = {
        "publication_lifecycle": {
            "authorization_state": "CLAIMED",
            "publication_state": "INTENT_RECORDED",
        }
    }

    def transition(*_args, action: str, **_kwargs):
        actions.append(action)
        return copy.deepcopy(claimed)

    with (
        patch.object(r7, "validate_candidate_revision_state", Mock(return_value=copy.deepcopy(state))),
        patch.object(r7, "validate_visual_verdict_result", Mock(return_value=verdict)),
        patch.object(r7, "validate_visual_contract", Mock(return_value=auth)),
        patch.object(r7, "require_auto_publish_authorized", Mock()),
        patch.object(
            r7,
            "snapshot_publication_file",
            Mock(side_effect=[snapshot(artifact_sha, 2), snapshot(target_sha, 3)]),
        ),
        patch.object(r7, "_transition", transition),
        patch.object(r7, "_manifest_sha", Mock(return_value="2" * 64)),
        patch.object(r7, "prepare_publication_replacement", Mock(return_value={})),
        patch.object(
            r7,
            "commit_publication_replacement",
            Mock(return_value={"published_sha256": artifact_sha}),
        ),
        patch.object(
            r7,
            "cleanup_publication_replacement",
            Mock(side_effect=OSError("cleanup blocked")),
        ),
    ):
        with pytest.raises(Exception, match="R7_CLEANUP_FAILED"):
            r7.execute_verified_publication(
                run_id=run_id,
                candidate_state=state,
                r5_verdict_result=verdict,
                auto_publish_authorization=auth,
                manifest_path=manifest,
                expected_manifest_sha256="1" * 64,
                candidate_path=candidate,
                target_path=target,
            )
    assert actions == ["CLAIM", "RECORD_PUBLISHED"]
