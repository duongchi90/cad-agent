from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
from functools import lru_cache
import inspect
from pathlib import Path
import re

import pytest

from cad_agent import component_view_registry as r3
from cad_agent import drawing_artifact_reference as dara
from cad_agent.drawing_contracts import canonical_json_sha256
import cad_agent.candidate_revision as candidate_module
from cad_agent.candidate_revision import (
    CANDIDATE_REVISION_SCHEMA_VERSION,
    CandidateRevisionError,
    build_candidate_revision,
    validate_candidate_revision,
)


CANDIDATE_SCHEMA_VERSION = "candidate-revision-1.0"
LINEAGE_SCHEMA_VERSION = "candidate-lineage-context-1.0"
SCOPE = {
    "run_id": "run-r4-185-001",
    "project_id": "project-r4-185",
    "drawing_id": "drawing-r4-185",
}


@lru_cache(maxsize=None)
def _accepted_r3_test_module():
    """Load only the accepted main-branch R3 test fixture builder."""
    path = Path(__file__).with_name("test_cad_agent_component_view_registry.py")
    spec = importlib.util.spec_from_file_location("r4_accepted_r3_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R3 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_bytes(tag: str) -> bytes:
    return f"synthetic-r4-candidate-artifact::{tag}".encode("utf-8")


def _baseline_context(
    tag: str = "baseline", *, scope: dict[str, str] | None = None
) -> dict[str, object]:
    artifact_bytes = _artifact_bytes(tag)
    baseline_scope = dict(scope or SCOPE)
    reference = dara.issue_drawing_artifact_reference(
        **baseline_scope,
        artifact_role="BASELINE",
        artifact_bytes=artifact_bytes,
        upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-owner-evidence-185",
            "evidence_sha256": "1" * 64,
        },
    )
    observation = dara.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=artifact_bytes,
        observation_evidence_sha256="2" * 64,
    )
    dara.require_current_drawing_artifact_reference(
        reference=reference,
        observation=observation,
        artifact_bytes=artifact_bytes,
    )
    return {
        "reference": reference,
        "observation": observation,
        "artifact_bytes": artifact_bytes,
    }


def _r3_provenance_binding(registry: dict[str, object]) -> dict[str, object]:
    material = {
        "identity_kind": "r3-component-view-registry-provenance-v1",
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "component_bindings": [
            {
                "component_id": component["component_id"],
                "record_sha256": canonical_json_sha256(component),
            }
            for component in registry["components"]
        ],
    }
    return {
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "provenance_sha256": canonical_json_sha256(material),
    }


def _candidate_reference(
    baseline: dict[str, object], registry: dict[str, object], tag: str
) -> dict[str, object]:
    return dara.issue_drawing_artifact_reference(
        **SCOPE,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes(tag),
        upstream_evidence={
            "evidence_kind": "R3_CANDIDATE_CUSTODY",
            "evidence_id": f"r3-candidate-evidence-{tag}",
            "evidence_sha256": "2" * 64,
        },
        r3_provenance_binding=_r3_provenance_binding(registry),
    )


def _transition_evidence(
    *,
    candidate: dict[str, object],
    child_bytes: bytes,
) -> dict[str, object]:
    evidence = {
        "evidence_kind": "POST_REPAIR_TRANSITION",
        "r3_candidate_reference_id": candidate["reference_id"],
        "r3_candidate_reference_sha256": candidate["reference_sha256"],
        "r5_failure_id": "r5-fail-185",
        "r5_failure_sha256": "2" * 64,
        "r4_transition_id": "r4-transition-185",
        "r4_transition_sha256": "3" * 64,
        "r6_mutation_request_id": "r6-request-185",
        "r6_mutation_request_sha256": "4" * 64,
        "r6_result_id": "r6-result-185",
        "r6_result_sha256": "6" * 64,
        "executor_result_id": "executor-result-185",
        "executor_result_sha256": "7" * 64,
        "pre_artifact_sha256": candidate["artifact_sha256"],
        "post_artifact_sha256": _sha256_bytes(child_bytes),
        "protected_constraints_sha256": "8" * 64,
        "workspace_evidence_sha256": "9" * 64,
        "mutation_terminal": "SUCCESS",
        "partial_mutation": False,
        "timed_out": False,
        "rollback_failed": False,
        "cleanup_state": "VERIFIED",
    }
    r6 = __import__(
        "cad_agent.approved_repair_adapter",
        fromlist=["R6_RESULT_SCHEMA_VERSION", "validate_approved_repair_result"],
    )
    operation = __import__(
        "cad_agent.repair_operation_contract",
        fromlist=["REPAIR_OPERATION_SCHEMA_VERSION"],
    )
    candidate_id = "candidate-r6-r4-185"
    accepted_r6_result: dict[str, object] = {
        "schema_version": r6.R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": candidate_id,
        "candidate_revision_sha256": "c" * 64,
        "r5_failure_id": evidence["r5_failure_id"],
        "r5_failure_sha256": evidence["r5_failure_sha256"],
        "repair_plan_id": "repair-plan-r6-r4-185",
        "repair_plan_sha256": "d" * 64,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": operation.REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": "e" * 64,
        "authorization_id": "authorization-r6-r4-185",
        "executor_capability": "LINE",
        "executor_result_category": "HANDLE_RETURNED",
        "mutation_outcome": "SUCCESS",
        "closure": {
            "lease_id": "lease-r6-r4-185",
            "candidate_identity": candidate_id,
            "source_identity": evidence["r5_failure_id"],
            "source_fingerprint": evidence["r5_failure_sha256"],
            "close_outcome": "closed",
            "cleanup_outcome": "zero_survivors",
            "save_changes": False,
            "lifecycle_state": "closed",
        },
        "requires_new_r5_cycle": True,
    }
    accepted_r6_result["result_sha256"] = canonical_json_sha256(accepted_r6_result)
    accepted_r6_result = r6.validate_approved_repair_result(
        accepted_r6_result,
        expected_r5_failure_id=evidence["r5_failure_id"],
        expected_r5_failure_sha256=evidence["r5_failure_sha256"],
    )
    evidence["accepted_r6_result"] = accepted_r6_result
    evidence["r6_result_id"] = accepted_r6_result["result_sha256"]
    evidence["r6_result_sha256"] = accepted_r6_result["result_sha256"]
    evidence["accepted_transition_evidence_sha256"] = canonical_json_sha256(evidence)
    return evidence


def _accepted_r3_material(
    *,
    primitive_ids: tuple[str, str] = ("prim-r4-a", "prim-r4-b"),
    component_id: str = "cmp-r4-185",
    kind: str = "beam",
    candidate_tag: str = "candidate-185",
) -> dict[str, object]:
    fixture = _accepted_r3_test_module()
    registry, source = fixture._build_single_component_registry(
        primitive_ids=primitive_ids,
        component_id=component_id,
        kind=kind,
    )
    baseline = _baseline_context()
    correspondence = r3.build_correspondence_evidence(
        source_primitives=source,
        observed_primitives=[deepcopy(item) for item in source],
    )
    impact = r3.build_impact_evidence(registry, correspondence)
    candidate = _candidate_reference(baseline, registry, candidate_tag)
    child_bytes = _artifact_bytes(f"{candidate_tag}-post-repair")
    transition = _transition_evidence(candidate=candidate, child_bytes=child_bytes)
    child = dara.issue_drawing_artifact_reference(
        **SCOPE,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=transition,
        parent_reference=candidate,
        r3_provenance_binding=_r3_provenance_binding(registry),
    )
    observation = dara.observe_drawing_artifact_currentness(
        reference=child,
        parent_reference=candidate,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
        artifact_bytes=child_bytes,
        observation_evidence_sha256="a" * 64,
    )
    dara.require_current_drawing_artifact_reference(
        reference=child,
        parent_reference=candidate,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
        observation=observation,
        artifact_bytes=child_bytes,
    )
    return {
        "baseline": baseline,
        "registry": registry,
        "source": source,
        "correspondence": correspondence,
        "impact": impact,
        "candidate_parent": candidate,
        "candidate": child,
        "candidate_observation": observation,
        "candidate_bytes": child_bytes,
    }


def _component_context(
    material: dict[str, object], component_id: str = "cmp-r4-185"
) -> dict[str, object]:
    registry = material["registry"]
    component = next(
        item for item in registry["components"] if item["component_id"] == component_id
    )
    evidence = material["correspondence"]
    mapping = next(
        item
        for item in evidence["mappings"]
        if item["component_id"] == component_id
    )
    impact = next(
        item
        for item in material["impact"]["components"]
        if item["component_id"] == component_id
    )
    return {
        "schema_version": "r4-component-context-1.0",
        "component_id": component_id,
        "component_record_sha256": canonical_json_sha256(component),
        "correspondence_evidence_sha256": r3.correspondence_evidence_sha256(evidence),
        "correspondence_mapping_sha256": canonical_json_sha256(mapping),
        "impact_evidence_sha256": r3.impact_evidence_sha256(material["impact"]),
        "impact_component_sha256": canonical_json_sha256(impact),
    }


def _valid_args(
    *,
    baseline_context: dict[str, object] | None = None,
    material: dict[str, object] | None = None,
    tag: str = "root",
    parent: dict[str, object] | None = None,
    parent_transition: dict[str, object] | None = None,
) -> dict[str, object]:
    baseline = baseline_context or _baseline_context()
    material = material or _accepted_r3_material()
    return {
        "run_id": SCOPE["run_id"],
        "project_id": SCOPE["project_id"],
        "drawing_id": SCOPE["drawing_id"],
        "revision_id": f"revision-r4-{tag}",
        "baseline_reference": baseline["reference"],
        "baseline_current_observation": baseline["observation"],
        "baseline_artifact_bytes": baseline["artifact_bytes"],
        "candidate_reference": material["candidate"],
        "candidate_current_observation": material["candidate_observation"],
        "candidate_artifact_bytes": material["candidate_bytes"],
        "candidate_parent_reference": material["candidate_parent"],
        "accepted_transition_evidence_sha256": material["candidate"]["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        "registry_snapshot_sha256": material["registry"]["registry_snapshot_sha256"],
        "component_contexts": [_component_context(material)],
        "parent_candidate_revision": parent,
        "parent_transition": parent_transition,
        "state": "PROVISIONAL",
    }


def _valid_candidate(
    *,
    baseline_context: dict[str, object] | None = None,
    material: dict[str, object] | None = None,
    tag: str = "root",
    parent: dict[str, object] | None = None,
    parent_transition: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_candidate_revision(
        **_valid_args(
            baseline_context=baseline_context,
            material=material,
            tag=tag,
            parent=parent,
            parent_transition=parent_transition,
        )
    )


def _valid_transition(
    parent: dict[str, object], child: dict[str, object], *, tag: str = "child"
) -> dict[str, object]:
    payload = {
        "schema_version": "candidate-transition-evidence-1.0",
        "transition_id": f"transition-r4-{tag}",
        "parent_candidate_revision_id": parent["revision_id"],
        "parent_candidate_revision_sha256": parent["candidate_revision_sha256"],
        "child_candidate_revision_id": child["revision_id"],
        "candidate_reference_id": child["candidate_reference"]["reference_id"],
        "candidate_reference_sha256": child["candidate_reference"]["reference_sha256"],
        "accepted_transition_evidence_sha256": child["accepted_transition_evidence_sha256"],
        "registry_snapshot_sha256": child["registry_snapshot_sha256"],
    }
    payload["transition_sha256"] = canonical_json_sha256(payload)
    return payload


def _build_lineage_pair() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    root = _valid_candidate(tag="root")
    child_material = _accepted_r3_material(
        primitive_ids=("prim-r4-child-a", "prim-r4-child-b"),
        candidate_tag="candidate-child",
    )
    provisional_child_args = _valid_args(
        material=child_material,
        tag="child",
        parent=root,
        parent_transition=None,
    )
    child_seed = dict(provisional_child_args)
    child_seed["parent_transition"] = {
        "schema_version": "candidate-transition-evidence-1.0",
        "transition_id": "transition-r4-child",
        "parent_candidate_revision_id": root["revision_id"],
        "parent_candidate_revision_sha256": root["candidate_revision_sha256"],
        "child_candidate_revision_id": "revision-r4-child",
        "candidate_reference_id": child_material["candidate"]["reference_id"],
        "candidate_reference_sha256": child_material["candidate"]["reference_sha256"],
        "accepted_transition_evidence_sha256": child_material["candidate"]["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        "registry_snapshot_sha256": child_material["registry"]["registry_snapshot_sha256"],
    }
    transition_without_hash = deepcopy(child_seed["parent_transition"])
    transition_without_hash["transition_sha256"] = canonical_json_sha256(
        transition_without_hash
    )
    child_seed["parent_transition"] = transition_without_hash
    child = build_candidate_revision(**child_seed)
    return root, child, transition_without_hash


def test_public_surface_exists_and_is_closed() -> None:
    assert CANDIDATE_REVISION_SCHEMA_VERSION == CANDIDATE_SCHEMA_VERSION
    assert issubclass(CandidateRevisionError, ValueError)
    assert callable(build_candidate_revision)
    assert callable(validate_candidate_revision)


def test_candidate_revision_is_deterministic_and_owner_bound() -> None:
    first = _valid_candidate()
    second = _valid_candidate()
    assert first == second
    assert first["schema_version"] == CANDIDATE_SCHEMA_VERSION
    assert first["run_id"] == SCOPE["run_id"]
    assert first["project_id"] == SCOPE["project_id"]
    assert first["drawing_id"] == SCOPE["drawing_id"]
    assert first["state"] == "PROVISIONAL"
    assert first["baseline_reference"]["artifact_role"] == "BASELINE"
    assert first["candidate_reference"]["artifact_role"] == "R3_CANDIDATE"
    assert first["candidate_revision_sha256"] == canonical_json_sha256(
        {key: value for key, value in first.items() if key != "candidate_revision_sha256"}
    )
    assert validate_candidate_revision(first) == first


def test_candidate_validation_returns_detached_copy() -> None:
    candidate = _valid_candidate()
    sealed = validate_candidate_revision(candidate)
    assert sealed is not candidate
    assert sealed["component_contexts"] is not candidate["component_contexts"]
    candidate["component_contexts"][0]["component_id"] = "mutated"
    assert sealed["component_contexts"][0]["component_id"] == "cmp-r4-185"


def test_baseline_must_be_current_and_scope_bound() -> None:
    baseline = _baseline_context()
    stale = dara.observe_drawing_artifact_currentness(
        reference=baseline["reference"],
        artifact_bytes=_artifact_bytes("changed"),
        observation_evidence_sha256="3" * 64,
    )
    with pytest.raises(CandidateRevisionError, match="BASELINE|CURRENT|STALE"):
        build_candidate_revision(
            **{
                **_valid_args(baseline_context=baseline),
                "baseline_current_observation": stale,
            }
        )

    foreign = _baseline_context(
        "foreign-baseline",
        scope={
            "run_id": "run-foreign",
            "project_id": "project-foreign",
            "drawing_id": "drawing-foreign",
        },
    )
    with pytest.raises(CandidateRevisionError, match="SCOPE|BASELINE"):
        build_candidate_revision(**_valid_args(baseline_context=foreign))


def test_candidate_reference_must_be_current_post_repair_r3_candidate() -> None:
    material = _accepted_r3_material()
    stale = dara.observe_drawing_artifact_currentness(
        reference=material["candidate"],
        parent_reference=material["candidate_parent"],
        accepted_transition_evidence_sha256=material["candidate"]["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        artifact_bytes=_artifact_bytes("changed-candidate"),
        observation_evidence_sha256="b" * 64,
    )
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|CURRENT|STALE"):
        build_candidate_revision(
            **{
                **_valid_args(material=material),
                "candidate_current_observation": stale,
            }
        )

    baseline_ref = _baseline_context()["reference"]
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|CATEGORY|R3"):
        build_candidate_revision(
            **{
                **_valid_args(material=material),
                "candidate_reference": baseline_ref,
                "candidate_parent_reference": None,
                "accepted_transition_evidence_sha256": None,
            }
        )


def test_candidate_reference_parent_and_transition_anchors_are_required() -> None:
    args = _valid_args()
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|PARENT|TRANSITION|MUTATION"):
        build_candidate_revision(
            **{
                **args,
                "candidate_parent_reference": None,
            }
        )
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|TRANSITION|MUTATION"):
        build_candidate_revision(
            **{
                **args,
                "accepted_transition_evidence_sha256": None,
            }
        )


def test_r3_registry_snapshot_binding_must_match_candidate_reference() -> None:
    with pytest.raises(CandidateRevisionError, match="R3|REGISTRY|PROVENANCE|BINDING"):
        build_candidate_revision(
            **{
                **_valid_args(),
                "registry_snapshot_sha256": "f" * 64,
            }
        )


def test_component_context_must_bind_accepted_r3_correspondence_and_impact() -> None:
    material = _accepted_r3_material()
    args = _valid_args(material=material)
    context = deepcopy(args["component_contexts"])
    context[0]["correspondence_mapping_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError, match="R3|CORRESPONDENCE|BINDING"):
        build_candidate_revision(**{**args, "component_contexts": context})

    context = deepcopy(args["component_contexts"])
    context[0]["impact_component_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError, match="R3|IMPACT|BINDING"):
        build_candidate_revision(**{**args, "component_contexts": context})


def test_component_context_rejects_foreign_component_substitution() -> None:
    material = _accepted_r3_material()
    args = _valid_args(material=material)
    context = deepcopy(args["component_contexts"])
    context[0]["component_id"] = "foreign-component"
    with pytest.raises(CandidateRevisionError, match="R3|COMPONENT|BINDING"):
        build_candidate_revision(**{**args, "component_contexts": context})


def test_candidate_reference_rejects_foreign_r3_registry_binding() -> None:
    material = _accepted_r3_material()
    candidate = deepcopy(material["candidate"])
    candidate["r3_provenance_binding"]["registry_snapshot_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|R3|REGISTRY|PROVENANCE|HASH"):
        build_candidate_revision(
            **{
                **_valid_args(material=material),
                "candidate_reference": candidate,
            }
        )


def test_post_repair_transition_rejects_pre_repair_r5_pass_claim() -> None:
    material = _accepted_r3_material()
    child = deepcopy(material["candidate"])
    child["upstream_evidence"]["r5_verdict"] = "PASS"
    child["upstream_evidence"]["accepted_transition_evidence_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in child["upstream_evidence"].items()
            if key != "accepted_transition_evidence_sha256"
        }
    )
    child["reference_sha256"] = dara.drawing_artifact_reference_sha256(child)
    with pytest.raises(CandidateRevisionError, match="R5|TRANSITION|CANDIDATE|MUTATION"):
        build_candidate_revision(
            **{
                **_valid_args(material=material),
                "candidate_reference": child,
            }
        )


def test_parent_lineage_requires_exact_parent_candidate_and_transition() -> None:
    root, child, transition = _build_lineage_pair()
    assert child["parent_candidate_revision_sha256"] == root["candidate_revision_sha256"]
    assert child["parent_transition_sha256"] == transition["transition_sha256"]
    assert validate_candidate_revision(child) == child

    foreign_root = _valid_candidate(tag="foreign")
    with pytest.raises(CandidateRevisionError, match="PARENT|LINEAGE|BINDING"):
        build_candidate_revision(
            **{
                **_valid_args(tag="child-foreign-parent", parent=foreign_root),
                "parent_transition": transition,
            }
        )


def test_parent_transition_cannot_be_resealed_after_parent_candidate_changes() -> None:
    root, child, transition = _build_lineage_pair()
    tampered_parent = deepcopy(root)
    tampered_parent["state"] = "SUPERSEDED"
    transition = deepcopy(transition)
    transition["parent_candidate_revision_sha256"] = canonical_json_sha256(tampered_parent)
    transition["transition_sha256"] = canonical_json_sha256(
        {key: value for key, value in transition.items() if key != "transition_sha256"}
    )
    with pytest.raises(CandidateRevisionError, match="PARENT|LINEAGE|BINDING|HASH"):
        build_candidate_revision(
            **{
                **_valid_args(tag="child-tampered", parent=tampered_parent),
                "parent_transition": transition,
            }
        )


def test_candidate_revision_rejects_unknown_downstream_authority_fields() -> None:
    candidate = _valid_candidate()
    for field in (
        "accepted",
        "approved",
        "current",
        "published",
        "publication_id",
        "r5_verdict",
        "r5_pass",
        "r6_execution_state",
        "approval_id",
        "workspace_id",
        "current_reference_store_id",
    ):
        forged = deepcopy(candidate)
        forged[field] = True
        with pytest.raises(CandidateRevisionError, match="FIELD|CANDIDATE|UNKNOWN"):
            validate_candidate_revision(forged)


def test_candidate_revision_rejects_malformed_and_hash_mismatch() -> None:
    candidate = _valid_candidate()
    malformed = deepcopy(candidate)
    malformed["run_id"] = ""
    with pytest.raises(CandidateRevisionError, match="SCOPE|CANDIDATE"):
        validate_candidate_revision(malformed)

    forged = deepcopy(candidate)
    forged["candidate_revision_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError, match="HASH|CANDIDATE"):
        validate_candidate_revision(forged)


def test_candidate_revision_public_api_has_no_live_or_approval_authority() -> None:
    forbidden = {
        "approve",
        "verdict",
        "publish",
        "autocad",
        "provider",
        "workspace",
        "file_ipc",
        "manifest",
        "current_store",
        "candidate_store",
    }
    for function in (build_candidate_revision, validate_candidate_revision):
        parameters = set(inspect.signature(function).parameters)
        assert all(fragment not in name for name in parameters for fragment in forbidden)


def test_static_boundary_reuses_only_accepted_owners_and_has_no_second_store() -> None:
    source = Path(candidate_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = (
        "sqlite3",
        "shelve",
        "pickle",
        "requests",
        "socket",
        "subprocess",
        "mcp_integration_lib",
        "cad_agent.live",
        "candidate_store",
        "current_store",
        "publication_store",
        "approval_store",
    )
    assert all(item not in source for item in forbidden)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "cad_agent.drawing_artifact_reference" in imports
    assert "cad_agent.component_view_registry" in imports
    assert "cad_agent.drawing_contracts" in imports


def test_errors_are_categorical_and_do_not_echo_private_values() -> None:
    candidate = _valid_candidate()
    private_value = "C:/private/customer/r4-secret.dwg"
    forged = deepcopy(candidate)
    forged["private_path"] = private_value
    with pytest.raises(CandidateRevisionError) as exc:
        validate_candidate_revision(forged)
    assert private_value not in str(exc.value)


def test_candidate_revision_rejects_cross_scope_drawing_or_project_swap() -> None:
    baseline = _baseline_context(
        "foreign-scope",
        scope={
            "run_id": SCOPE["run_id"],
            "project_id": "project-foreign",
            "drawing_id": "drawing-foreign",
        },
    )
    with pytest.raises(CandidateRevisionError, match="SCOPE|BASELINE"):
        build_candidate_revision(**_valid_args(baseline_context=baseline))


def test_candidate_revision_id_is_not_a_downstream_currentness_token() -> None:
    candidate = _valid_candidate()
    assert candidate["state"] == "PROVISIONAL"
    assert "current" not in candidate
    assert "accepted" not in candidate
    assert "published" not in candidate


def _valid_lineage_chain() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    root_args = _valid_args(tag="lineage-root")
    root = build_candidate_revision(**root_args)
    child_args = _valid_args(
        tag="lineage-child",
        parent=root,
        parent_transition={
            "schema_version": "candidate-transition-evidence-1.0",
            "transition_id": "transition-lineage-child",
            "parent_candidate_revision_id": root["revision_id"],
            "parent_candidate_revision_sha256": root["candidate_revision_sha256"],
            "child_candidate_revision_id": "revision-r4-lineage-child",
            "candidate_reference_id": _valid_args(tag="lineage-child-seed")[
                "candidate_reference"
            ]["reference_id"],
            "candidate_reference_sha256": _valid_args(tag="lineage-child-seed")[
                "candidate_reference"
            ]["reference_sha256"],
            "accepted_transition_evidence_sha256": _valid_args(
                tag="lineage-child-seed"
            )["accepted_transition_evidence_sha256"],
            "registry_snapshot_sha256": _valid_args(tag="lineage-child-seed")[
                "registry_snapshot_sha256"
            ],
        },
    )
    child_args["parent_transition"]["transition_sha256"] = canonical_json_sha256(
        child_args["parent_transition"]
    )
    child = build_candidate_revision(**child_args)
    grandchild_args = _valid_args(
        tag="lineage-grandchild",
        parent=child,
        parent_transition={
            "schema_version": "candidate-transition-evidence-1.0",
            "transition_id": "transition-lineage-grandchild",
            "parent_candidate_revision_id": child["revision_id"],
            "parent_candidate_revision_sha256": child["candidate_revision_sha256"],
            "child_candidate_revision_id": "revision-r4-lineage-grandchild",
            "candidate_reference_id": _valid_args(tag="lineage-grandchild-seed")[
                "candidate_reference"
            ]["reference_id"],
            "candidate_reference_sha256": _valid_args(tag="lineage-grandchild-seed")[
                "candidate_reference"
            ]["reference_sha256"],
            "accepted_transition_evidence_sha256": _valid_args(
                tag="lineage-grandchild-seed"
            )["accepted_transition_evidence_sha256"],
            "registry_snapshot_sha256": _valid_args(tag="lineage-grandchild-seed")[
                "registry_snapshot_sha256"
            ],
        },
    )
    grandchild_args["parent_transition"]["transition_sha256"] = canonical_json_sha256(
        grandchild_args["parent_transition"]
    )
    return root_args, root, child, grandchild_args


def _validate_lineage_state(
    candidate_revisions: list[dict[str, object]],
    current_candidate_revision_sha256: str | None,
) -> dict[str, object]:
    return candidate_module.build_candidate_revision_state(
        candidate_revisions=candidate_revisions,
        current_candidate_revision_sha256=current_candidate_revision_sha256,
    )


def test_candidate_revision_state_public_surface_exists() -> None:
    for name in (
        "build_candidate_revision_state",
        "validate_candidate_revision_state",
        "candidate_revision_state_sha256",
        "transition_candidate_revision_state",
    ):
        assert callable(getattr(candidate_module, name))


def test_candidate_revision_state_is_closed_deterministic_and_current_pointer_is_optional() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([child, root], None)
    assert set(state) == {
        "schema_version",
        "candidate_revisions",
        "current_candidate_revision_sha256",
        "state_sha256",
    }
    assert state["schema_version"] == "candidate-revision-state-1.0"
    assert state["current_candidate_revision_sha256"] is None
    assert state["candidate_revisions"] == sorted(
        [root, child], key=lambda value: value["candidate_revision_sha256"]
    )
    assert candidate_module.validate_candidate_revision_state(state) == state
    assert candidate_module.candidate_revision_state_sha256(state) == state["state_sha256"]


def test_candidate_revision_state_rejects_unknown_fields_and_hash_mismatch() -> None:
    _root_args, root, _child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([root], None)
    unknown = deepcopy(state)
    unknown["caller_field"] = True
    with pytest.raises(CandidateRevisionError, match="STATE|FIELD|UNKNOWN"):
        candidate_module.validate_candidate_revision_state(unknown)
    forged = deepcopy(state)
    forged["state_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError, match="STATE|HASH"):
        candidate_module.validate_candidate_revision_state(forged)


def test_candidate_revision_state_rejects_duplicate_or_foreign_lineage() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    with pytest.raises(CandidateRevisionError, match="DUPLICATE|STATE|CANDIDATE"):
        _validate_lineage_state([root, root], None)

    foreign_baseline = _baseline_context(
        "foreign-lineage-state",
        scope={
            "run_id": "run-foreign-state",
            "project_id": "project-foreign-state",
            "drawing_id": "drawing-foreign-state",
        },
    )
    foreign = _valid_candidate(
        baseline_context=foreign_baseline,
        tag="foreign-lineage-state",
    )
    with pytest.raises(CandidateRevisionError, match="SCOPE|STATE|CANDIDATE"):
        _validate_lineage_state([root, child, foreign], None)


def test_candidate_revision_state_current_pointer_must_reference_member() -> None:
    _root_args, root, _child, _grandchild_args = _valid_lineage_chain()
    with pytest.raises(CandidateRevisionError, match="CURRENT|STATE|CANDIDATE"):
        _validate_lineage_state([root], "f" * 64)


def test_candidate_revision_state_rejects_dangling_or_tampered_parent_transition() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    with pytest.raises(CandidateRevisionError, match="PARENT|LINEAGE|STATE"):
        _validate_lineage_state([child], None)

    tampered_child = deepcopy(child)
    tampered_child["parent_transition_sha256"] = "f" * 64
    tampered_child["candidate_revision_sha256"] = canonical_json_sha256(
        {key: value for key, value in tampered_child.items() if key != "candidate_revision_sha256"}
    )
    with pytest.raises(CandidateRevisionError, match="PARENT|LINEAGE|TRANSITION|STATE"):
        _validate_lineage_state([root, tampered_child], None)


def test_candidate_revision_state_rejects_cycle() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    root_cycle = deepcopy(root)
    root_cycle["parent_candidate_revision_sha256"] = child["candidate_revision_sha256"]
    root_cycle["parent_transition_sha256"] = "f" * 64
    root_cycle["candidate_revision_sha256"] = canonical_json_sha256(
        {key: value for key, value in root_cycle.items() if key != "candidate_revision_sha256"}
    )
    child_cycle = deepcopy(child)
    child_cycle["parent_candidate_revision_sha256"] = root_cycle["candidate_revision_sha256"]
    child_cycle["candidate_revision_sha256"] = canonical_json_sha256(
        {key: value for key, value in child_cycle.items() if key != "candidate_revision_sha256"}
    )
    with pytest.raises(CandidateRevisionError, match="LINEAGE|PARENT|CYCLE|STATE"):
        _validate_lineage_state([root_cycle, child_cycle], None)


def test_candidate_revision_state_transition_select_supersede_and_rollback() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([root, child], None)
    selected = candidate_module.transition_candidate_revision_state(
        state,
        transition_kind="SELECT",
        candidate_revision_sha256=root["candidate_revision_sha256"],
        expected_current_candidate_revision_sha256=None,
    )
    assert selected["current_candidate_revision_sha256"] == root["candidate_revision_sha256"]

    superseded = candidate_module.transition_candidate_revision_state(
        selected,
        transition_kind="SUPERSEDE",
        candidate_revision_sha256=child["candidate_revision_sha256"],
        expected_current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    assert superseded["current_candidate_revision_sha256"] == child[
        "candidate_revision_sha256"
    ]

    rolled_back = candidate_module.transition_candidate_revision_state(
        superseded,
        transition_kind="ROLLBACK",
        candidate_revision_sha256=root["candidate_revision_sha256"],
        expected_current_candidate_revision_sha256=child["candidate_revision_sha256"],
    )
    assert rolled_back["current_candidate_revision_sha256"] == root[
        "candidate_revision_sha256"
    ]


def test_candidate_revision_state_transition_rejects_replay_or_stale_expected_current() -> None:
    _root_args, root, child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([root, child], None)
    selected = candidate_module.transition_candidate_revision_state(
        state,
        transition_kind="SELECT",
        candidate_revision_sha256=root["candidate_revision_sha256"],
        expected_current_candidate_revision_sha256=None,
    )
    with pytest.raises(CandidateRevisionError, match="CURRENT|REPLAY|STATE"):
        candidate_module.transition_candidate_revision_state(
            selected,
            transition_kind="SELECT",
            candidate_revision_sha256=root["candidate_revision_sha256"],
            expected_current_candidate_revision_sha256=None,
        )
    with pytest.raises(CandidateRevisionError, match="CURRENT|EXPECTED|STALE|STATE"):
        candidate_module.transition_candidate_revision_state(
            selected,
            transition_kind="SUPERSEDE",
            candidate_revision_sha256=child["candidate_revision_sha256"],
            expected_current_candidate_revision_sha256="f" * 64,
        )


def test_candidate_revision_state_transition_rejects_non_member_or_invalid_kind() -> None:
    _root_args, root, _child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([root], None)
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|STATE|MEMBER"):
        candidate_module.transition_candidate_revision_state(
            state,
            transition_kind="SELECT",
            candidate_revision_sha256="f" * 64,
            expected_current_candidate_revision_sha256=None,
        )
    with pytest.raises(CandidateRevisionError, match="TRANSITION|KIND|STATE"):
        candidate_module.transition_candidate_revision_state(
            state,
            transition_kind="UNKNOWN",
            candidate_revision_sha256=root["candidate_revision_sha256"],
            expected_current_candidate_revision_sha256=None,
        )


def test_candidate_revision_state_transition_returns_detached_state() -> None:
    _root_args, root, _child, _grandchild_args = _valid_lineage_chain()
    state = _validate_lineage_state([root], None)
    selected = candidate_module.transition_candidate_revision_state(
        state,
        transition_kind="SELECT",
        candidate_revision_sha256=root["candidate_revision_sha256"],
        expected_current_candidate_revision_sha256=None,
    )
    assert selected is not state
    assert selected["candidate_revisions"] is not state["candidate_revisions"]
    assert state["current_candidate_revision_sha256"] is None


def test_candidate_revision_state_public_api_has_no_downstream_or_live_authority() -> None:
    forbidden_fragments = {
        "approve",
        "verdict",
        "publish",
        "autocad",
        "provider",
        "workspace",
        "file_ipc",
        "manifest",
    }
    for name in (
        "build_candidate_revision_state",
        "validate_candidate_revision_state",
        "transition_candidate_revision_state",
    ):
        parameters = set(inspect.signature(getattr(candidate_module, name)).parameters)
        assert all(
            fragment not in parameter
            for parameter in parameters
            for fragment in forbidden_fragments
        )


TASK2_STATE_SCHEMA_VERSION = "candidate-revision-state-2.0"
TASK2_TRANSITION_SCHEMA_VERSION = "candidate-current-transition-1.0"
TASK2_MODULE_SOURCE = Path(candidate_module.__file__).read_text(encoding="utf-8")


def _task2_api(name: str):
    value = getattr(candidate_module, name, None)
    assert callable(value), f"missing public API: {name}"
    return value


def _task2_graph() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    root_args = _valid_args(tag="task2-root")
    root = build_candidate_revision(**root_args)
    left_material = _accepted_r3_material(
        primitive_ids=("task2-left-a", "task2-left-b"),
        candidate_tag="task2-left",
    )
    left_seed = _valid_args(
        material=left_material,
        tag="task2-left",
        parent=root,
        parent_transition=None,
    )
    left_transition = {
        "schema_version": "candidate-transition-evidence-1.0",
        "transition_id": "transition-task2-left",
        "parent_candidate_revision_id": root["revision_id"],
        "parent_candidate_revision_sha256": root["candidate_revision_sha256"],
        "child_candidate_revision_id": left_seed["revision_id"],
        "candidate_reference_id": left_seed["candidate_reference"]["reference_id"],
        "candidate_reference_sha256": left_seed["candidate_reference"]["reference_sha256"],
        "accepted_transition_evidence_sha256": left_seed[
            "accepted_transition_evidence_sha256"
        ],
        "registry_snapshot_sha256": left_seed["registry_snapshot_sha256"],
    }
    left_transition["transition_sha256"] = canonical_json_sha256(left_transition)
    left = build_candidate_revision(**{**left_seed, "parent_transition": left_transition})

    right_material = _accepted_r3_material(
        primitive_ids=("task2-right-a", "task2-right-b"),
        candidate_tag="task2-right",
    )
    right_seed = _valid_args(
        material=right_material,
        tag="task2-right",
        parent=root,
        parent_transition=None,
    )
    right_transition = {
        "schema_version": "candidate-transition-evidence-1.0",
        "transition_id": "transition-task2-right",
        "parent_candidate_revision_id": root["revision_id"],
        "parent_candidate_revision_sha256": root["candidate_revision_sha256"],
        "child_candidate_revision_id": right_seed["revision_id"],
        "candidate_reference_id": right_seed["candidate_reference"]["reference_id"],
        "candidate_reference_sha256": right_seed["candidate_reference"]["reference_sha256"],
        "accepted_transition_evidence_sha256": right_seed[
            "accepted_transition_evidence_sha256"
        ],
        "registry_snapshot_sha256": right_seed["registry_snapshot_sha256"],
    }
    right_transition["transition_sha256"] = canonical_json_sha256(right_transition)
    right = build_candidate_revision(**{**right_seed, "parent_transition": right_transition})
    return root_args, root, left, right


def _task2_state(candidates: list[dict[str, object]]) -> dict[str, object]:
    return _task2_api("build_candidate_revision_state")(
        candidate_revisions=candidates,
        current_candidate_revision_sha256=None,
    )


def _task2_transition(
    transition_kind: str,
    candidate: dict[str, object],
    *,
    expected_current: str | None,
) -> dict[str, object]:
    return {
        "schema_version": TASK2_TRANSITION_SCHEMA_VERSION,
        "transition_kind": transition_kind,
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "expected_current_candidate_revision_sha256": expected_current,
    }


def _task2_apply(
    state: dict[str, object],
    candidate: dict[str, object],
    transition: dict[str, object],
) -> dict[str, object]:
    return _task2_api("transition_candidate_revision_state")(
        state=state,
        candidate_revision=candidate,
        transition_evidence=transition,
    )


def _task2_state_sha256(state: dict[str, object]) -> str:
    return _task2_api("candidate_revision_state_sha256")(state)


def _task2_selected_and_superseded() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    _root_args, root, left, right = _task2_graph()
    state = _task2_state([root, left, right])
    selected = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    superseded = _task2_apply(
        selected,
        left,
        _task2_transition(
            "SUPERSEDE",
            left,
            expected_current=root["candidate_revision_sha256"],
        ),
    )
    return root, left, right, superseded


def test_task2_public_surface_exists_and_is_versioned() -> None:
    assert getattr(candidate_module, "CANDIDATE_REVISION_STATE_SCHEMA_VERSION", None) == (
        TASK2_STATE_SCHEMA_VERSION
    )
    assert getattr(candidate_module, "CANDIDATE_CURRENT_TRANSITION_SCHEMA_VERSION", None) == (
        TASK2_TRANSITION_SCHEMA_VERSION
    )
    for name in (
        "build_candidate_revision_state",
        "validate_candidate_revision_state",
        "candidate_revision_state_sha256",
        "transition_candidate_revision_state",
    ):
        assert callable(getattr(candidate_module, name, None))


def test_task2_source_is_stateless_and_has_no_store_or_persistence_edge() -> None:
    source = TASK2_MODULE_SOURCE.lower()
    for forbidden in (
        "sqlite3",
        "shelve",
        "pickle",
        "current_store",
        "candidate_store",
        "set_current_reference",
        "register_current_reference",
        "publication_store",
        "approval_store",
        "write_manifest",
        "requests",
        "socket",
        "subprocess",
    ):
        assert forbidden not in source


def test_task2_public_api_has_no_live_r5_r6_approval_or_publication_authority() -> None:
    forbidden_fragments = (
        "approve",
        "approval",
        "verdict",
        "r5_",
        "r6_",
        "publish",
        "publication",
        "autocad",
        "provider",
        "workspace",
        "file_ipc",
        "manifest",
    )
    for name in (
        "build_candidate_revision_state",
        "validate_candidate_revision_state",
        "transition_candidate_revision_state",
    ):
        parameters = set(inspect.signature(_task2_api(name)).parameters)
        assert all(
            fragment not in parameter
            for parameter in parameters
            for fragment in forbidden_fragments
        )


def test_task2_state_is_deterministic_closed_and_accepts_sibling_forks() -> None:
    _root_args, root, left, right = _task2_graph()
    first = _task2_state([right, root, left])
    second = _task2_state([left, right, root])
    assert first == second
    assert set(first) == {
        "schema_version",
        "candidate_revisions",
        "current_candidate_revision_sha256",
        "transition_evidence_sha256",
        "state_sha256",
    }
    assert first["schema_version"] == TASK2_STATE_SCHEMA_VERSION
    assert first["current_candidate_revision_sha256"] is None
    assert first["transition_evidence_sha256"] is None
    assert [
        candidate["candidate_revision_sha256"] for candidate in first["candidate_revisions"]
    ] == sorted(
        [
            root["candidate_revision_sha256"],
            left["candidate_revision_sha256"],
            right["candidate_revision_sha256"],
        ]
    )
    assert _task2_api("validate_candidate_revision_state")(first) == first
    assert _task2_state_sha256(first) == first["state_sha256"]


def test_task2_select_binds_current_pointer_without_minting_candidate() -> None:
    _root_args, root, left, right = _task2_graph()
    state = _task2_state([root, left, right])
    selected = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    assert selected["current_candidate_revision_sha256"] == root["candidate_revision_sha256"]
    assert selected["candidate_revisions"] == state["candidate_revisions"]
    assert selected["state_sha256"] == _task2_state_sha256(selected)
    assert selected["transition_evidence_sha256"] is not None


def test_task2_select_rejects_foreign_or_tampered_candidate() -> None:
    _root_args, root, left, _right = _task2_graph()
    state = _task2_state([root, left])
    foreign = _valid_candidate(tag="task2-foreign")
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|MEMBER|STATE"):
        _task2_apply(
            state,
            foreign,
            _task2_transition("SELECT", foreign, expected_current=None),
        )
    tampered = deepcopy(root)
    tampered["state"] = "FORGED_CANDIDATE"
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|BINDING|CHECKSUM"):
        _task2_apply(
            state,
            tampered,
            _task2_transition("SELECT", root, expected_current=None),
        )


def test_task2_select_replay_and_expected_current_conflict_fail_closed() -> None:
    _root_args, root, left, _right = _task2_graph()
    state = _task2_state([root, left])
    selected = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    with pytest.raises(CandidateRevisionError, match="REPLAY|CURRENT|EXPECTED"):
        _task2_apply(
            selected,
            root,
            _task2_transition("SELECT", root, expected_current=None),
        )
    with pytest.raises(CandidateRevisionError, match="CURRENT|EXPECTED|STALE"):
        _task2_apply(
            selected,
            left,
            _task2_transition("SELECT", left, expected_current="f" * 64),
        )


def test_task2_supersede_binds_direct_child_and_keeps_history() -> None:
    root, left, right, superseded = _task2_selected_and_superseded()
    assert superseded["current_candidate_revision_sha256"] == left[
        "candidate_revision_sha256"
    ]
    assert superseded["candidate_revisions"] == sorted(
        [root, left, right],
        key=lambda candidate: candidate["candidate_revision_sha256"],
    )


def test_task2_supersede_rejects_sibling_foreign_or_tampered_candidate() -> None:
    _root_args, root, left, right = _task2_graph()
    state = _task2_state([root, left, right])
    selected = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    with pytest.raises(CandidateRevisionError, match="PARENT|CURRENT|SIBLING"):
        _task2_apply(
            selected,
            right,
            _task2_transition(
                "SUPERSEDE",
                right,
                expected_current=root["candidate_revision_sha256"],
            ),
        )
    foreign = _valid_candidate(tag="task2-foreign-super")
    with pytest.raises(CandidateRevisionError, match="CANDIDATE|MEMBER|STATE"):
        _task2_apply(
            selected,
            foreign,
            _task2_transition(
                "SUPERSEDE",
                foreign,
                expected_current=root["candidate_revision_sha256"],
            ),
        )
    tampered_left = deepcopy(left)
    tampered_left["state"] = "FORGED_CANDIDATE"

    with pytest.raises(CandidateRevisionError, match="CANDIDATE|BINDING|CHECKSUM"):
        _task2_apply(
            selected,
            tampered_left,
            _task2_transition(
                "SUPERSEDE",
                left,
                expected_current=root["candidate_revision_sha256"],
            ),
        )


def test_task2_supersede_replay_and_expected_current_conflict_fail_closed() -> None:
    root, left, _right, superseded = _task2_selected_and_superseded()
    replay = _task2_transition(
        "SUPERSEDE",
        left,
        expected_current=root["candidate_revision_sha256"],
    )

    with pytest.raises(CandidateRevisionError, match="REPLAY|CURRENT|EXPECTED"):
        _task2_apply(superseded, left, replay)

    with pytest.raises(CandidateRevisionError, match="CURRENT|EXPECTED|STALE"):
        _task2_apply(
            _task2_apply(
                _task2_state([root, left]),
                root,
                _task2_transition("SELECT", root, expected_current=None),
            ),
            left,
            _task2_transition("SUPERSEDE", left, expected_current="f" * 64),
        )


def test_task2_stale_current_selected_token_and_state_are_rejected() -> None:
    _root_args, root, left, _right = _task2_graph()
    state = _task2_apply(
        _task2_state([root, left]),
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    with pytest.raises(CandidateRevisionError, match="CURRENT|STALE"):
        _task2_apply(
            state,
            left,
            _task2_transition("SUPERSEDE", left, expected_current=None),
        )

    stale_state = deepcopy(state)
    stale_state["current_candidate_revision_sha256"] = None
    with pytest.raises(CandidateRevisionError, match="CHECKSUM|STATE|CURRENT"):
        _task2_apply(
            stale_state,
            left,
            _task2_transition(
                "SUPERSEDE",
                left,
                expected_current=root["candidate_revision_sha256"],
            ),
        )


def test_task2_cross_scope_candidate_swap_is_rejected() -> None:
    _root_args, root, _left, _right = _task2_graph()
    foreign_baseline = _baseline_context(
        "task2-foreign-scope",
        scope={
            **SCOPE,
            "run_id": "foreign-run",
            "project_id": "foreign-project",
            "drawing_id": "foreign-drawing",
        },
    )
    foreign = build_candidate_revision(
        **_valid_args(baseline_context=foreign_baseline, tag="foreign-scope")
    )
    state = _task2_state([root])
    with pytest.raises(CandidateRevisionError, match="SCOPE|BASELINE|CANDIDATE"):
        _task2_apply(
            state,
            foreign,
            _task2_transition("SELECT", foreign, expected_current=None),
        )
    with pytest.raises(CandidateRevisionError, match="SCOPE|BASELINE"):
        _task2_state([root, foreign])


def test_task2_stale_dara_baseline_and_r3_r2_bindings_cannot_enter_state() -> None:
    _root_args, root, _left, _right = _task2_graph()
    stale_baseline = build_candidate_revision(
        **_valid_args(baseline_context=_baseline_context("stale-dara"), tag="stale-dara")
    )
    foreign_material = _accepted_r3_material(
        primitive_ids=("task2-foreign-prim-a", "task2-foreign-prim-b")
    )
    stale_upstream = build_candidate_revision(
        **_valid_args(material=foreign_material, tag="stale-r3-r2")
    )
    with pytest.raises(CandidateRevisionError, match="BASELINE|DARA|SCOPE"):
        _task2_state([root, stale_baseline])
    with pytest.raises(CandidateRevisionError, match="UPSTREAM|R3|R2|BINDING"):
        _task2_state([root, stale_upstream])


def test_task2_parent_child_and_sibling_forks_cannot_be_confused() -> None:
    _root_args, root, left, right = _task2_graph()
    state = _task2_state([root, left, right])
    selected = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    superseded = _task2_apply(
        selected,
        left,
        _task2_transition("SUPERSEDE", left, expected_current=root["candidate_revision_sha256"]),
    )
    with pytest.raises(CandidateRevisionError, match="PARENT|CURRENT|SIBLING"):
        _task2_apply(
            superseded,
            right,
            _task2_transition(
                "SUPERSEDE",
                right,
                expected_current=left["candidate_revision_sha256"],
            ),
        )


def test_task2_logical_rollback_selects_historical_identity_without_rewriting_lineage() -> None:
    _root_args, root, left, right = _task2_graph()
    original_root = deepcopy(root)
    original_left = deepcopy(left)
    state = _task2_state([root, left, right])
    state = _task2_apply(
        state,
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    state = _task2_apply(
        state,
        left,
        _task2_transition("SUPERSEDE", left, expected_current=root["candidate_revision_sha256"]),
    )
    rolled_back = _task2_apply(
        state,
        root,
        _task2_transition(
            "ROLLBACK",
            root,
            expected_current=left["candidate_revision_sha256"],
        ),
    )
    assert rolled_back["current_candidate_revision_sha256"] == root[
        "candidate_revision_sha256"
    ]
    assert rolled_back["candidate_revisions"] == sorted(
        [original_left, original_root, right],
        key=lambda candidate: candidate["candidate_revision_sha256"],
    )
    assert next(
        candidate
        for candidate in rolled_back["candidate_revisions"]
        if candidate["candidate_revision_sha256"] == left["candidate_revision_sha256"]
    )["parent_candidate_revision_sha256"] == root["candidate_revision_sha256"]


def test_task2_rollback_rejects_tampered_candidate_identity() -> None:
    root, left, _right, superseded = _task2_selected_and_superseded()
    tampered_root = deepcopy(root)
    tampered_root["state"] = "FORGED_CANDIDATE"

    with pytest.raises(CandidateRevisionError, match="CANDIDATE|BINDING|CHECKSUM"):
        _task2_apply(
            superseded,
            tampered_root,
            _task2_transition(
                "ROLLBACK",
                root,
                expected_current=left["candidate_revision_sha256"],
            ),
        )


def test_task2_rollback_replay_and_expected_current_conflict_fail_closed() -> None:
    root, left, _right, superseded = _task2_selected_and_superseded()
    rollback = _task2_transition(
        "ROLLBACK",
        root,
        expected_current=left["candidate_revision_sha256"],
    )
    rolled_back = _task2_apply(superseded, root, rollback)

    with pytest.raises(CandidateRevisionError, match="REPLAY|CURRENT|EXPECTED"):
        _task2_apply(rolled_back, root, rollback)

    with pytest.raises(CandidateRevisionError, match="CURRENT|EXPECTED|STALE"):
        _task2_apply(
            superseded,
            root,
            _task2_transition(
                "ROLLBACK",
                root,
                expected_current=root["candidate_revision_sha256"],
            ),
        )


def test_task2_conflicting_expected_current_identity_fails_closed() -> None:
    _root_args, root, left, _right = _task2_graph()
    state = _task2_apply(
        _task2_state([root, left]),
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    with pytest.raises(CandidateRevisionError, match="EXPECTED|CURRENT|STALE"):
        _task2_apply(
            state,
            left,
            _task2_transition("SUPERSEDE", left, expected_current="f" * 64),
        )


@pytest.mark.parametrize(
    "authority_field",
    [
        "accepted",
        "approved",
        "published",
        "verdict",
        "current",
        "timestamps",
        "uuid",
        "path",
        "handle",
    ],
)
def test_task2_caller_cannot_inject_authority_or_server_fields(authority_field: str) -> None:
    _root_args, root, _left, _right = _task2_graph()
    state = _task2_state([root])
    forged = _task2_transition("SELECT", root, expected_current=None)
    forged[authority_field] = True
    with pytest.raises(CandidateRevisionError, match="TRANSITION|FIELD|AUTHORITY"):
        _task2_apply(state, root, forged)


@pytest.mark.parametrize(
    "malformed",
    [
        {"transition_kind": "SELECT"},
        {
            "schema_version": TASK2_TRANSITION_SCHEMA_VERSION,
            "transition_kind": "UNKNOWN",
            "candidate_revision_sha256": "f" * 64,
            "expected_current_candidate_revision_sha256": None,
        },
        {
            "schema_version": TASK2_TRANSITION_SCHEMA_VERSION,
            "transition_kind": "SELECT",
            "candidate_revision_sha256": "f" * 64,
            "expected_current_candidate_revision_sha256": None,
            "unknown": True,
        },
    ],
)
def test_task2_malformed_or_unknown_transition_fields_fail_closed(
    malformed: dict[str, object],
) -> None:
    _root_args, root, _left, _right = _task2_graph()
    with pytest.raises(CandidateRevisionError, match="TRANSITION|FIELD|UNKNOWN"):
        _task2_apply(_task2_state([root]), root, malformed)


@pytest.mark.parametrize("transition_kind", [[], {}])
def test_task2_unhashable_transition_kind_fails_closed(
    transition_kind: object,
) -> None:
    _root_args, root, _left, _right = _task2_graph()
    transition = _task2_transition("SELECT", root, expected_current=None)
    transition["transition_kind"] = transition_kind

    with pytest.raises(CandidateRevisionError, match="TRANSITION|KIND|FIELD|UNKNOWN"):
        _task2_apply(_task2_state([root]), root, transition)


def test_task2_state_checksum_mutation_and_unknown_fields_fail_closed() -> None:
    _root_args, root, _left, _right = _task2_graph()
    state = _task2_state([root])
    assert "state_sha256" in state
    assert state["state_sha256"] == _task2_state_sha256(state)
    mutated_checksum = deepcopy(state)
    mutated_checksum["state_sha256"] = "f" * 64
    assert mutated_checksum["state_sha256"] != _task2_state_sha256(mutated_checksum)
    with pytest.raises(CandidateRevisionError, match="CHECKSUM"):
        _task2_apply(
            mutated_checksum,
            root,
            _task2_transition("SELECT", root, expected_current=None),
        )
    unknown_field = deepcopy(state)
    unknown_field["caller_path"] = "C:/forbidden"
    with pytest.raises(CandidateRevisionError, match="STATE|FIELD|UNKNOWN"):
        _task2_apply(
            unknown_field,
            root,
            _task2_transition("SELECT", root, expected_current=None),
        )
