"""Contract-only M3 acceptance composition over the existing repair owners."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pytest

from cad_agent import approved_repair_adapter as r6
from cad_agent import candidate_revision as r4
from cad_agent import component_view_registry as r3
from cad_agent import drawing_artifact_reference as dara
from cad_agent import visual_supervisor_adapter as r5
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.repair_authorization import issue_repair_authorization
from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    normalize_repair_operation,
)
from cad_agent.visual_contracts import validate_visual_contract


@lru_cache(maxsize=1)
def _accepted_r4_fixture():
    path = Path(__file__).parents[2] / "tests" / "test_cad_agent_candidate_revision.py"
    spec = importlib.util.spec_from_file_location("m3_r4_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R4 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _accepted_r6_test_fixture():
    path = Path(__file__).parents[2] / "tests" / "test_cad_agent_approved_repair_adapter.py"
    spec = importlib.util.spec_from_file_location("m3_r6_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R6 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sealed_r5_result(
    *,
    candidate: dict[str, object],
    state: dict[str, object],
    verdict: str,
    request_tag: str,
    latest_mutation_sha256: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": r5.R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION,
        "request_sha256": canonical_json_sha256(
            {"mode": "CONTRACT_ONLY", "request_tag": request_tag}
        ),
        "observation_sha256": canonical_json_sha256(
            {
                "candidate_revision_sha256": candidate["candidate_revision_sha256"],
                "request_tag": request_tag,
            }
        ),
        "verdict": verdict,
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "registry_snapshot_sha256": candidate["change_scope"][
            "registry_snapshot_sha256"
        ],
        "drawing_reference_sha256": canonical_json_sha256(
            {"candidate": candidate["candidate_artifacts"]["reference_sha256"]}
        ),
        "drawing_observation_sha256": canonical_json_sha256(
            {"candidate": candidate["candidate_artifacts"]["artifact_sha256"]}
        ),
        "latest_mutation_sha256": latest_mutation_sha256,
        "task6_thread_id": f"m3-contract-only-{request_tag}",
        "task6_turn_id": f"m3-r5-{request_tag}",
        "regions": [
            {
                "region_id": "m3-line-region",
                "view_id": "m3-line-view",
                "sheet_id": "m3-line-sheet",
                "layout_id": "m3-line-layout",
                "criticality": "CRITICAL",
                "status": verdict,
            }
        ],
    }
    digest = canonical_json_sha256(payload)
    result = {**payload, "verdict_id": digest, "verdict_sha256": digest}
    return r5.validate_visual_verdict_result(
        result,
        expected_request_sha256=payload["request_sha256"],
        expected_candidate_revision_sha256=candidate["candidate_revision_sha256"],
        expected_candidate_state_sha256=state["state_sha256"],
        expected_latest_mutation_sha256=latest_mutation_sha256,
    )


def _line_operation():
    return normalize_repair_operation(
        {
            "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
            "operation": "REPAIR_DXF_PRIMITIVE",
            "target": {"target_handle": "H204", "layer": "M3-TEST"},
            "parameters": {
                "capability": "LINE",
                "geometry": {
                    "type": "line",
                    "start": [0.0, 0.0],
                    "end": [10.0, 0.0],
                },
            },
            "preserve_anchors": ["m3-line-anchor"],
            "constraint_refs": ["m3-line-constraint"],
        }
    )


def _repair_plan(
    *, candidate: dict[str, object], failure: dict[str, object]
) -> dict[str, object]:
    component_id = candidate["change_scope"]["impact"]["component_ids"][0]
    plan = {
        "schema_version": "repair-plan-1.0",
        "repair_id": "repair-plan-m3-line-contract",
        "source_review_id": failure["verdict_id"],
        "run_id": candidate["run_id"],
        "target_drawing_sha256": candidate["candidate_artifacts"]["artifact_sha256"],
        "operations": [
            {
                "operation": "REPLACE_POLYLINE_SEGMENT",
                "target": {"stable_entity_id": component_id, "feature": "LINE"},
                "preserve_anchors": ["m3-line-anchor"],
                "constraint_refs": ["m3-line-constraint"],
            }
        ],
        "affected_regions": ["m3-line-region"],
        "expected_improvements": ["m3-line-region:PASS"],
        "must_not_worsen": ["protected-geometry"],
        "rollback_candidate_sha256": candidate["candidate_artifacts"][
            "artifact_sha256"
        ],
    }
    return validate_visual_contract(plan, contract="repair_plan")


@dataclass
class _RecordingExecutor:
    calls: list[dict[str, object]] = field(default_factory=list)

    def entity_erase(self, target_handle: str) -> None:
        self.calls.append({"operation": "erase", "target_handle": target_handle})

    def entity_create_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        layer: str,
    ) -> dict[str, str]:
        self.calls.append(
            {
                "operation": "create_line",
                "geometry": {"start": [x1, y1], "end": [x2, y2]},
                "layer": layer,
            }
        )
        return {"handle": "H204-NEW"}


def _transition_evidence(
    *,
    parent: dict[str, object],
    child_bytes: bytes,
    r5_failure: dict[str, object],
    r6_result: dict[str, object],
    operation_payload: dict[str, object],
    executor: _RecordingExecutor,
) -> dict[str, object]:
    parent_artifact_sha256 = parent["candidate_artifacts"]["artifact_sha256"]
    post_artifact_sha256 = _sha256_bytes(child_bytes)
    request_sha256 = canonical_json_sha256(
        {
            "candidate_revision_sha256": parent["candidate_revision_sha256"],
            "operation": operation_payload,
        }
    )
    transition: dict[str, object] = {
        "evidence_kind": "POST_REPAIR_TRANSITION",
        "r3_candidate_reference_id": parent["candidate_artifacts"]["reference_id"],
        "r3_candidate_reference_sha256": parent["candidate_artifacts"][
            "reference_sha256"
        ],
        "r5_failure_id": r5_failure["verdict_id"],
        "r5_failure_sha256": r5_failure["verdict_sha256"],
        "r4_transition_id": "r4-transition-m3-line-contract",
        "r4_transition_sha256": canonical_json_sha256(
            {
                "kind": "POST_REPAIR",
                "parent": parent["candidate_revision_sha256"],
                "child": post_artifact_sha256,
            }
        ),
        "r6_mutation_request_id": "r6-request-m3-line-contract",
        "r6_mutation_request_sha256": request_sha256,
        "r6_result_id": r6_result["result_sha256"],
        "r6_result_sha256": r6_result["result_sha256"],
        "executor_result_id": "executor-result-m3-line-contract",
        "executor_result_sha256": canonical_json_sha256(
            {"calls": executor.calls, "returned_handle": "H204-NEW"}
        ),
        "pre_artifact_sha256": parent_artifact_sha256,
        "post_artifact_sha256": post_artifact_sha256,
        "protected_constraints_sha256": canonical_json_sha256(
            {"preserve_anchors": ["m3-line-anchor"], "constraint_refs": ["m3-line-constraint"]}
        ),
        "workspace_evidence_sha256": canonical_json_sha256(r6_result["closure"]),
        "mutation_terminal": "SUCCESS",
        "partial_mutation": False,
        "timed_out": False,
        "rollback_failed": False,
        "cleanup_state": "VERIFIED",
        "accepted_r6_result": copy.deepcopy(r6_result),
    }
    transition["accepted_transition_evidence_sha256"] = canonical_json_sha256(
        transition
    )
    return transition


def _post_repair_candidate(
    *,
    root_args: dict[str, object],
    root: dict[str, object],
    root_reference: dict[str, object],
    root_observation: dict[str, object],
    child_bytes: bytes,
    transition: dict[str, object],
) -> dict[str, object]:
    r4_fixture = _accepted_r4_fixture()
    material = r4_fixture._accepted_r3_material()
    child_reference = dara.issue_drawing_artifact_reference(
        run_id=root["run_id"],
        project_id=root_args["baseline_context"]["reference"]["project_id"],
        drawing_id=root_args["baseline_context"]["reference"]["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=transition,
        parent_reference=root_reference,
        r3_provenance_binding=root_reference["r3_provenance_binding"],
    )
    child_observation = dara.observe_drawing_artifact_currentness(
        reference=child_reference,
        artifact_bytes=child_bytes,
        observation_evidence_sha256=canonical_json_sha256(
            {"candidate": child_reference["reference_sha256"], "mode": "M3"}
        ),
        parent_reference=root_reference,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
    )
    correspondence = r3.finalize_component_view_correspondence(
        registry=material["registry"],
        upstream_context=material["context"],
        parent_reference=root_reference,
        parent_observation=root_observation,
        parent_artifact_bytes=root_args["change_impact"][
            "root_candidate_artifact_bytes"
        ],
        child_reference=child_reference,
        child_observation=child_observation,
        child_artifact_bytes=child_bytes,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
    )
    post_args = {
        "registry": copy.deepcopy(material["registry"]),
        "base_cad_handoff": copy.deepcopy(root_args["base_cad_handoff"]),
        "baseline_context": copy.deepcopy(root_args["baseline_context"]),
        "parent_candidate": copy.deepcopy(root),
        "change_impact": {
            "registry_snapshot_sha256": material["registry"][
                "registry_snapshot_sha256"
            ],
            "impact": copy.deepcopy(material["impact"]),
            "correspondence": correspondence,
            "upstream_context": copy.deepcopy(material["context"]),
            "correspondence_context": {
                "parent_reference": copy.deepcopy(root_reference),
                "parent_observation": copy.deepcopy(root_observation),
                "parent_artifact_bytes": root_args["change_impact"][
                    "root_candidate_artifact_bytes"
                ],
                "child_reference": copy.deepcopy(child_reference),
                "child_observation": copy.deepcopy(child_observation),
                "child_artifact_bytes": child_bytes,
                "accepted_transition_evidence_sha256": transition[
                    "accepted_transition_evidence_sha256"
                ],
            },
        },
        "mutation_evidence": {
            "evidence_kind": "R4_CANDIDATE_BUILD",
            "evidence_id": "r4-build-m3-line-contract",
            "r3_candidate_reference_id": child_reference["reference_id"],
            "r3_candidate_reference_sha256": child_reference["reference_sha256"],
            "candidate_artifact_sha256": child_reference["artifact_sha256"],
            "accepted_transition_evidence_sha256": transition[
                "accepted_transition_evidence_sha256"
            ],
            "latest_mutation_evidence_sha256": canonical_json_sha256(
                {
                    "r6_result_sha256": transition["r6_result_sha256"],
                    "returned_handle": "H204-NEW",
                }
            ),
            "mutation_terminal": "SEALED",
        },
        "lineage_context": r4_fixture._lineage_context(
            root_args["baseline_context"], [root]
        ),
        "schema_version": r4.CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        "candidate_kind": r4.CANDIDATE_REVISION_POST_REPAIR_KIND,
    }
    post_args["mutation_evidence"]["evidence_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in post_args["mutation_evidence"].items()
            if key != "evidence_sha256"
        }
    )
    return r4.build_candidate_revision(**post_args)


def test_m3_v11_root_pre_repair_is_consumable_by_the_existing_r6_planner() -> None:
    r4_fixture = _accepted_r4_fixture()
    root_args = r4_fixture._task3_root_args()
    root = r4.build_candidate_revision(**copy.deepcopy(root_args))
    state = r4.build_candidate_revision_state(
        candidate_revisions=[root],
        current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    failure = _sealed_r5_result(
        candidate=root,
        state=state,
        verdict="FAIL",
        request_tag="v11-pre-repair",
        latest_mutation_sha256=canonical_json_sha256(root["mutation_evidence"]),
    )
    operation = _line_operation()
    plan = _repair_plan(candidate=root, failure=failure)
    context = {
        "run_id": root["run_id"],
        "work_item_id": "work-m3-v11-root",
        "candidate_revision_id": root["revision_id"],
        "candidate_revision_sha256": root["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "request_sha256": failure["request_sha256"],
        "latest_mutation_sha256": failure["latest_mutation_sha256"],
        "r3_target_handles": ["H204"],
        "protected_target_handles": ["H204"],
    }

    prepared = r6.prepare_repair_plan(
        r5_result=failure,
        candidate_revision=root,
        candidate_state=state,
        repair_plan=plan,
        r3_context=context,
    )

    assert prepared["r5_failure_id"] == failure["verdict_id"]
    assert normalize_repair_operation(operation) == operation


def test_m3_r5_pass_cannot_start_the_repair_plan() -> None:
    r4_fixture = _accepted_r4_fixture()
    root_args = r4_fixture._task3_root_args()
    root = r4.build_candidate_revision(**copy.deepcopy(root_args))
    state = r4.build_candidate_revision_state(
        candidate_revisions=[root],
        current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    latest_mutation = canonical_json_sha256(root["mutation_evidence"])
    passed_r5 = _sealed_r5_result(
        candidate=root,
        state=state,
        verdict="PASS",
        request_tag="pass-before-repair",
        latest_mutation_sha256=latest_mutation,
    )
    plan = _repair_plan(candidate=root, failure=passed_r5)
    context = {
        "run_id": root["run_id"],
        "work_item_id": "work-m3-pass-repair",
        "candidate_revision_id": root["revision_id"],
        "candidate_revision_sha256": root["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "request_sha256": passed_r5["request_sha256"],
        "latest_mutation_sha256": latest_mutation,
        "r3_target_handles": ["H204"],
        "protected_target_handles": ["H204"],
    }
    with pytest.raises(Exception, match="FAIL"):
        r6.prepare_repair_plan(
            r5_result=passed_r5,
            candidate_revision=root,
            candidate_state=state,
            repair_plan=plan,
            r3_context=context,
        )


def test_m3_rebound_r5_is_rejected_before_executor_calls() -> None:
    fixtures = _accepted_r6_test_fixture()
    inputs, _owner, executor = fixtures._sealed_executor_inputs()
    inputs["r5_result"]["candidate_revision_sha256"] = "f" * 64

    with pytest.raises(Exception, match="R5|invalid|binding"):
        r6.execute_approved_repair(**inputs)

    assert executor.calls == []


def test_m3_consumed_authorization_cannot_be_replayed() -> None:
    fixtures = _accepted_r6_test_fixture()
    inputs, _owner, executor = fixtures._sealed_executor_inputs()
    r6.execute_approved_repair(**inputs)

    with pytest.raises(Exception, match="AUTHORIZATION|CONSUMED|workspace"):
        r6.execute_approved_repair(**inputs)

    assert len(executor.calls) == 1


def test_m3_post_repair_r5_rejects_stale_candidate_binding(tmp_path: Path) -> None:
    record = run_contract_only_line_epoch(tmp_path)
    stale = copy.deepcopy(record["post_repair_r5"])
    stale["candidate_revision_sha256"] = "f" * 64

    with pytest.raises(Exception, match="R5|invalid|verdict"):
        r5.validate_visual_verdict_result(
            stale,
            expected_candidate_revision_sha256=record["post_repair_candidate"][
                "candidate_revision_sha256"
            ],
            expected_candidate_state_sha256=record["post_repair_r5"][
                "candidate_state_sha256"
            ],
            expected_latest_mutation_sha256=record["post_repair_r5"][
                "latest_mutation_sha256"
            ],
        )


def run_contract_only_line_epoch(tmp_path: Path) -> dict[str, object]:
    """Compose one bounded M3 epoch without claiming live visual evidence."""

    r4_fixture = _accepted_r4_fixture()
    r6_fixture = _accepted_r6_test_fixture()
    root_args = r4_fixture._task3_root_args()
    root = r4.build_candidate_revision(**copy.deepcopy(root_args))
    root_state = r4.build_candidate_revision_state(
        candidate_revisions=[root],
        current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    root_reference = root_args["change_impact"]["root_candidate_reference"]
    root_observation = root_args["change_impact"]["root_candidate_observation"]
    root_bytes = root_args["change_impact"]["root_candidate_artifact_bytes"]
    child_bytes = root_bytes + b"\nM3 contract-only LINE repair child\n"

    protected_paths = {
        "source": tmp_path / "source.dwg",
        "base": tmp_path / "base.dwg",
        "accepted": tmp_path / "accepted.dwg",
    }
    protected_bytes = {
        "source": b"M3 source sentinel",
        "base": b"M3 base sentinel",
        "accepted": b"M3 accepted sentinel",
    }
    for name, path in protected_paths.items():
        path.write_bytes(protected_bytes[name])
    candidate_before_path = tmp_path / "candidate-pre-repair.dwg"
    candidate_after_path = tmp_path / "candidate-post-repair.dwg"
    candidate_before_path.write_bytes(root_bytes)
    candidate_after_path.write_bytes(child_bytes)
    protected_before = {name: _sha256_file(path) for name, path in protected_paths.items()}

    pre_repair_r5 = _sealed_r5_result(
        candidate=root,
        state=root_state,
        verdict="FAIL",
        request_tag="pre-repair",
        latest_mutation_sha256=canonical_json_sha256(root["mutation_evidence"]),
    )
    operation = _line_operation()
    operation_payload = operation.as_executor_payload()
    operation_fingerprint = canonical_json_sha256(operation_payload)
    plan = _repair_plan(candidate=root, failure=pre_repair_r5)
    planner_context = {
        "run_id": root["run_id"],
        "work_item_id": "work-m3-line-contract",
        "candidate_revision_id": root["revision_id"],
        "candidate_revision_sha256": root["candidate_revision_sha256"],
        "candidate_state_sha256": root_state["state_sha256"],
        "request_sha256": pre_repair_r5["request_sha256"],
        "latest_mutation_sha256": pre_repair_r5["latest_mutation_sha256"],
        "r3_target_handles": ["H204"],
        "protected_target_handles": ["H204"],
    }
    prepared = r6.prepare_repair_plan(
        r5_result=pre_repair_r5,
        candidate_revision=root,
        candidate_state=root_state,
        repair_plan=plan,
        r3_context=planner_context,
    )
    repair_context = {
        **planner_context,
        "repair_plan_id": plan["repair_id"],
        "repair_plan_sha256": prepared["repair_plan_sha256"],
        "repair_plan_version": prepared["repair_plan_version"],
        "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": operation_fingerprint,
    }
    authorization = issue_repair_authorization(
        run_id=repair_context["run_id"],
        work_item_id=repair_context["work_item_id"],
        candidate_revision_id=repair_context["candidate_revision_id"],
        candidate_revision_sha256=repair_context["candidate_revision_sha256"],
        r5_failure_id=pre_repair_r5["verdict_id"],
        r5_failure_sha256=pre_repair_r5["verdict_sha256"],
        repair_plan_id=repair_context["repair_plan_id"],
        repair_plan_sha256=repair_context["repair_plan_sha256"],
        repair_plan_version=repair_context["repair_plan_version"],
        repair_operation_contract_version=REPAIR_OPERATION_SCHEMA_VERSION,
        repair_operation_contract_fingerprint=operation_fingerprint,
    )
    workspace_owner = r6_fixture._WorkspaceOwner()
    workspace_lease = r6_fixture._WorkspaceLease(
        workspace_owner,
        candidate_identity=root["revision_id"],
        source_identity=pre_repair_r5["verdict_id"],
        source_fingerprint=pre_repair_r5["verdict_sha256"],
    )
    executor = _RecordingExecutor()
    r6_result = r6.execute_approved_repair(
        authorization=authorization,
        repair_operation=operation,
        repair_context=repair_context,
        candidate_state=root_state,
        r5_result=pre_repair_r5,
        workspace_owner=workspace_owner,
        workspace_lease=workspace_lease,
        executor_client=executor,
    )
    r6_result = r6.validate_approved_repair_result(
        r6_result,
        expected_candidate_revision_id=root["revision_id"],
        expected_candidate_revision_sha256=root["candidate_revision_sha256"],
        expected_candidate_artifact_reference_id=root["candidate_artifacts"][
            "reference_id"
        ],
        expected_candidate_artifact_reference_sha256=root["candidate_artifacts"][
            "reference_sha256"
        ],
        expected_r5_failure_id=pre_repair_r5["verdict_id"],
        expected_r5_failure_sha256=pre_repair_r5["verdict_sha256"],
        expected_repair_plan_id=plan["repair_id"],
        expected_repair_plan_sha256=prepared["repair_plan_sha256"],
        expected_repair_plan_version=prepared["repair_plan_version"],
        expected_repair_operation_contract_version=REPAIR_OPERATION_SCHEMA_VERSION,
        expected_repair_operation_contract_fingerprint=operation_fingerprint,
    )
    assert [call["operation"] for call in executor.calls] == ["erase", "create_line"]

    transition = _transition_evidence(
        parent=root,
        child_bytes=child_bytes,
        r5_failure=pre_repair_r5,
        r6_result=r6_result,
        operation_payload=operation_payload,
        executor=executor,
    )
    post_repair_candidate = _post_repair_candidate(
        root_args=root_args,
        root=root,
        root_reference=root_reference,
        root_observation=root_observation,
        child_bytes=child_bytes,
        transition=transition,
    )
    post_repair_state = r4.build_candidate_revision_state(
        candidate_revisions=[root, post_repair_candidate],
        current_candidate_revision_sha256=post_repair_candidate[
            "candidate_revision_sha256"
        ],
    )
    post_repair_r5 = _sealed_r5_result(
        candidate=post_repair_candidate,
        state=post_repair_state,
        verdict="PASS",
        request_tag="post-repair",
        latest_mutation_sha256=post_repair_candidate["mutation_evidence"][
            "latest_mutation_evidence_sha256"
        ],
    )
    protected_after = {name: _sha256_file(path) for name, path in protected_paths.items()}
    assert protected_after == protected_before

    return {
        "acceptance_mode": "CONTRACT_ONLY",
        "live_auto_cad": "NOT_RUN",
        "pre_repair_r5": pre_repair_r5,
        "repair_plan": prepared,
        "r6_result": r6_result,
        "post_repair_candidate": post_repair_candidate,
        "post_repair_r5": post_repair_r5,
        "repair_attempts": 1,
        "executor_calls": len(executor.calls),
        "executor_call_log": copy.deepcopy(executor.calls),
        "candidate_before_sha256": _sha256_file(candidate_before_path),
        "candidate_after_sha256": _sha256_file(candidate_after_path),
        "protected_file_sha256_before": canonical_json_sha256(protected_before),
        "protected_file_sha256_after": canonical_json_sha256(protected_after),
        "human_intervention_events": [],
        "source_base_accepted_unchanged": True,
        "r5_provider": "contract-only owner validation; no visual provider",
    }

def test_m3_contract_only_line_epoch_composes_fresh_r5_after_one_r6_mutation(
    tmp_path: Path,
) -> None:
    from mcp_integration_lib.tests import test_m3_disposable_repair_acceptance as module

    record = module.run_contract_only_line_epoch(tmp_path)

    assert record["acceptance_mode"] == "CONTRACT_ONLY"
    assert record["pre_repair_r5"]["verdict"] == "FAIL"
    assert record["r6_result"]["mutation_outcome"] == "SUCCESS"
    assert record["r6_result"]["requires_new_r5_cycle"] is True
    assert record["post_repair_r5"]["verdict"] == "PASS"
    assert record["repair_attempts"] == 1
    assert record["executor_calls"] == 2
    assert record["r6_result"]["closure"]["cleanup_outcome"] == "zero_survivors"
    assert record["r6_result"]["closure"]["save_changes"] is False
    assert record["protected_file_sha256_before"] == record["protected_file_sha256_after"]
