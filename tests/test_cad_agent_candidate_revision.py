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
        "view_bindings": [
            {
                "view_id": view["view_id"],
                "record_sha256": canonical_json_sha256(view),
            }
            for view in registry["views"]
        ],
    }
    return {
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "provenance_sha256": canonical_json_sha256(material),
    }


def _transition_evidence(
    parent: dict[str, object],
    *,
    parent_bytes: bytes,
    child_bytes: bytes,
    tag: str,
) -> dict[str, object]:
    evidence = {
        "evidence_kind": "POST_REPAIR_TRANSITION",
        "r3_candidate_reference_id": parent["reference_id"],
        "r3_candidate_reference_sha256": parent["reference_sha256"],
        "r5_failure_id": f"r5-failure-{tag}",
        "r5_failure_sha256": "3" * 64,
        "r4_transition_id": f"r4-transition-{tag}",
        "r4_transition_sha256": "4" * 64,
        "r6_mutation_request_id": f"r6-request-{tag}",
        "r6_mutation_request_sha256": "5" * 64,
        "r6_result_id": f"r6-result-{tag}",
        "r6_result_sha256": "6" * 64,
        "executor_result_id": f"executor-result-{tag}",
        "executor_result_sha256": "7" * 64,
        "pre_artifact_sha256": _sha256_bytes(parent_bytes),
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
    candidate_id = f"candidate-r6-r4-{tag}"
    accepted_r6_result: dict[str, object] = {
        "schema_version": r6.R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": candidate_id,
        "candidate_revision_sha256": "c" * 64,
        "candidate_artifact_reference_id": parent["reference_id"],
        "candidate_artifact_reference_sha256": parent["reference_sha256"],
        "r5_failure_id": evidence["r5_failure_id"],
        "r5_failure_sha256": evidence["r5_failure_sha256"],
        "repair_plan_id": f"repair-plan-r6-r4-{tag}",
        "repair_plan_sha256": "d" * 64,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": operation.REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": "e" * 64,
        "authorization_id": f"authorization-r6-r4-{tag}",
        "executor_capability": "LINE",
        "executor_result_category": "HANDLE_RETURNED",
        "mutation_outcome": "SUCCESS",
        "closure": {
            "lease_id": f"lease-r6-r4-{tag}",
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
        expected_candidate_artifact_reference_id=parent["reference_id"],
        expected_candidate_artifact_reference_sha256=parent["reference_sha256"],
        expected_r5_failure_id=evidence["r5_failure_id"],
        expected_r5_failure_sha256=evidence["r5_failure_sha256"],
    )
    evidence["accepted_r6_result"] = accepted_r6_result
    evidence["r6_result_id"] = accepted_r6_result["result_sha256"]
    evidence["r6_result_sha256"] = accepted_r6_result["result_sha256"]
    evidence["accepted_transition_evidence_sha256"] = canonical_json_sha256(
        evidence
    )
    return evidence


def _accepted_r3_material(
    *,
    primitive_ids: tuple[str, str] = ("prim-a", "prim-b"),
) -> dict[str, object]:
    r3_tests = _accepted_r3_test_module()
    context = r3_tests._upstream_context(primitive_ids=primitive_ids)
    candidate_bytes = _artifact_bytes("r3-candidate")
    handoff = deepcopy(context["reuse_handoff"])
    handoff["candidate_output_sha256"] = _sha256_bytes(candidate_bytes)
    context = r3_tests._replace_handoff(context, handoff)
    context["candidate"]["candidate_drawing_sha256"] = handoff[
        "candidate_output_sha256"
    ]
    registry = r3.build_component_view_registry(
        upstream_context=context,
        components=r3_tests._component_inputs(context),
    )
    assert r3.validate_component_view_registry(
        registry, upstream_context=context
    ) == registry
    component_ids = [
        component["component_id"] for component in registry["components"]
    ]
    impact = r3.project_linked_view_impacts(
        registry=registry,
        component_ids=component_ids,
        upstream_context=context,
    )
    assert r3.component_view_registry_sha256(
        registry, upstream_context=context
    ) == registry["registry_snapshot_sha256"]
    binding = _r3_provenance_binding(registry)
    parent = dara.issue_drawing_artifact_reference(
        **SCOPE,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=candidate_bytes,
        upstream_evidence={
            "evidence_kind": "R3_CANDIDATE_CUSTODY",
            "evidence_id": "r3-candidate-owner-185",
            "evidence_sha256": "a" * 64,
        },
        r3_provenance_binding=binding,
    )
    child_bytes = _artifact_bytes("r3-candidate-child")
    transition = _transition_evidence(
        parent,
        parent_bytes=candidate_bytes,
        child_bytes=child_bytes,
        tag="185",
    )
    child = dara.issue_drawing_artifact_reference(
        **SCOPE,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=transition,
        parent_reference=parent,
        r3_provenance_binding=binding,
    )
    parent_observation = dara.observe_drawing_artifact_currentness(
        reference=parent,
        artifact_bytes=candidate_bytes,
        observation_evidence_sha256="b" * 64,
    )
    child_observation = dara.observe_drawing_artifact_currentness(
        reference=child,
        artifact_bytes=child_bytes,
        observation_evidence_sha256="c" * 64,
        parent_reference=parent,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
    )
    correspondence = r3.finalize_component_view_correspondence(
        registry=registry,
        upstream_context=context,
        parent_reference=parent,
        parent_observation=parent_observation,
        parent_artifact_bytes=candidate_bytes,
        child_reference=child,
        child_observation=child_observation,
        child_artifact_bytes=child_bytes,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
    )
    return {
        "context": context,
        "registry": registry,
        "impact": impact,
        "correspondence": correspondence,
        "candidate_bytes": candidate_bytes,
        "child_bytes": child_bytes,
        "parent_reference": parent,
        "parent_observation": parent_observation,
        "child_reference": child,
        "child_observation": child_observation,
        "accepted_transition_evidence_sha256": child["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
    }


def _mutation_evidence(material: dict[str, object], tag: str) -> dict[str, object]:
    child = material["child_reference"]
    evidence = {
        "evidence_kind": "R4_CANDIDATE_BUILD",
        "evidence_id": f"r4-build-{tag}",
        "r3_candidate_reference_id": child["reference_id"],
        "r3_candidate_reference_sha256": child["reference_sha256"],
        "candidate_artifact_sha256": child["artifact_sha256"],
        "accepted_transition_evidence_sha256": child["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        "latest_mutation_evidence_sha256": "d" * 64,
        "mutation_terminal": "SEALED",
    }
    evidence["evidence_sha256"] = canonical_json_sha256(evidence)
    return evidence


def _rebind_mutation_evidence_checksum(evidence: dict[str, object]) -> None:
    evidence["evidence_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in evidence.items()
            if key != "evidence_sha256"
        }
    )


def _valid_args(
    *,
    material: dict[str, object] | None = None,
    baseline_context: dict[str, object] | None = None,
    parent_candidate: dict[str, object] | None = None,
    lineage_context: object = (),
    tag: str = "root",
) -> dict[str, object]:
    material = material or _accepted_r3_material()
    return {
        "registry": deepcopy(material["registry"]),
        "base_cad_handoff": deepcopy(material["context"]["reuse_handoff"]),
        "baseline_context": deepcopy(baseline_context or _baseline_context()),
        "parent_candidate": deepcopy(parent_candidate),
        "change_impact": {
            "registry_snapshot_sha256": material["registry"][
                "registry_snapshot_sha256"
            ],
            "impact": deepcopy(material["impact"]),
            "correspondence": deepcopy(material["correspondence"]),
            "upstream_context": deepcopy(material["context"]),
            "correspondence_context": {
                "parent_reference": deepcopy(material["parent_reference"]),
                "parent_observation": deepcopy(material["parent_observation"]),
                "parent_artifact_bytes": material["candidate_bytes"],
                "child_reference": deepcopy(material["child_reference"]),
                "child_observation": deepcopy(material["child_observation"]),
                "child_artifact_bytes": material["child_bytes"],
                "accepted_transition_evidence_sha256": material[
                    "accepted_transition_evidence_sha256"
                ],
            },
        },
        "mutation_evidence": _mutation_evidence(material, tag),
        "lineage_context": deepcopy(lineage_context),
    }


def _root_pre_repair_args(
    *, material: dict[str, object] | None = None
) -> dict[str, object]:
    """Describe the missing root/pre-repair path without R5/R6 authority."""
    material = material or _accepted_r3_material()
    root_reference = deepcopy(material["parent_reference"])
    root_observation = deepcopy(material["parent_observation"])
    root_binding_sha256 = canonical_json_sha256(root_reference["upstream_evidence"])
    root_correspondence = {
        "parent_reference_id": root_reference["reference_id"],
        "parent_reference_sha256": root_reference["reference_sha256"],
        "child_reference_id": root_reference["reference_id"],
        "child_reference_sha256": root_reference["reference_sha256"],
        "registry_snapshot_sha256": material["registry"][
            "registry_snapshot_sha256"
        ],
        "provenance_sha256": material["correspondence"]["provenance_sha256"],
        "component_bindings": deepcopy(
            material["correspondence"]["component_bindings"]
        ),
        "view_bindings": deepcopy(material["correspondence"]["view_bindings"]),
    }
    root_change_impact = {
        "registry_snapshot_sha256": material["registry"][
            "registry_snapshot_sha256"
        ],
        "impact": deepcopy(material["impact"]),
        "correspondence": root_correspondence,
        "upstream_context": deepcopy(material["context"]),
        "correspondence_context": {
            "parent_reference": root_reference,
            "parent_observation": root_observation,
            "parent_artifact_bytes": material["candidate_bytes"],
            "child_reference": root_reference,
            "child_observation": root_observation,
            "child_artifact_bytes": material["candidate_bytes"],
            # A root candidate has no post-repair transition evidence.
            "accepted_transition_evidence_sha256": None,
        },
    }
    root_mutation = {
        "evidence_kind": "R4_CANDIDATE_BUILD",
        "evidence_id": "r4-root-bootstrap-red",
        "r3_candidate_reference_id": root_reference["reference_id"],
        "r3_candidate_reference_sha256": root_reference["reference_sha256"],
        "candidate_artifact_sha256": root_reference["artifact_sha256"],
        # The frozen R4 record keeps this slot, but the root binding is R3
        # custody—not an accepted R6 result or a post-repair transition.
        "accepted_transition_evidence_sha256": root_binding_sha256,
        "latest_mutation_evidence_sha256": root_binding_sha256,
        "mutation_terminal": "SEALED",
    }
    root_mutation["evidence_sha256"] = canonical_json_sha256(root_mutation)
    return {
        "registry": deepcopy(material["registry"]),
        "base_cad_handoff": deepcopy(material["context"]["reuse_handoff"]),
        "baseline_context": deepcopy(_baseline_context()),
        "parent_candidate": None,
        "change_impact": root_change_impact,
        "mutation_evidence": root_mutation,
        "lineage_context": (),
    }


def _lineage_context(
    baseline_context: dict[str, object], ancestors: list[dict[str, object]]
) -> dict[str, object]:
    reference = baseline_context["reference"]
    return {
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "scope": {
            "run_id": reference["run_id"],
            "project_id": reference["project_id"],
            "drawing_id": reference["drawing_id"],
        },
        "baseline_reference": deepcopy(reference),
        "ancestors": [
            {
                "candidate_revision_sha256": ancestor[
                    "candidate_revision_sha256"
                ],
                "candidate_record": deepcopy(ancestor),
            }
            for ancestor in ancestors
        ],
    }


def _child_args(
    root_args: dict[str, object],
    parent: dict[str, object],
    *,
    tag: str,
    lineage_context: object = (),
) -> dict[str, object]:
    args = deepcopy(root_args)
    args["parent_candidate"] = deepcopy(parent)
    args["lineage_context"] = deepcopy(lineage_context)
    args["mutation_evidence"]["evidence_id"] = f"r4-build-{tag}"
    args["mutation_evidence"]["evidence_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in args["mutation_evidence"].items()
            if key != "evidence_sha256"
        }
    )
    return args


def _valid_lineage_chain() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    child_args = _child_args(root_args, root, tag="child")
    child = build_candidate_revision(**deepcopy(child_args))
    grandchild_args = _child_args(root_args, child, tag="grandchild")
    assert root["parent_candidate_revision_sha256"] is None
    assert child["parent_candidate_revision_sha256"] == root[
        "candidate_revision_sha256"
    ]
    assert grandchild_args["parent_candidate"]["candidate_revision_sha256"] == child[
        "candidate_revision_sha256"
    ]
    return root_args, root, child, grandchild_args


def test_root_pre_repair_candidate_requires_no_post_repair_transition() -> None:
    """RED: current main forces a root candidate through R3 child correspondence."""
    args = _root_pre_repair_args()
    root = build_candidate_revision(**deepcopy(args))

    assert root["parent_candidate_revision_sha256"] is None
    assert root["candidate_artifacts"]["reference_id"] == args[
        "mutation_evidence"
    ]["r3_candidate_reference_id"]
    assert root["candidate_artifacts"]["artifact_sha256"] == args[
        "mutation_evidence"
    ]["candidate_artifact_sha256"]
    assert args["change_impact"]["correspondence_context"][
        "accepted_transition_evidence_sha256"
    ] is None
    assert "accepted_r6_result" not in args["mutation_evidence"]

    state = candidate_module.build_candidate_revision_state(
        candidate_revisions=[root],
        current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    assert state["current_candidate_revision_sha256"] == root[
        "candidate_revision_sha256"
    ]


def _candidate_module_source_and_tree() -> tuple[str, ast.Module]:
    path = Path(candidate_module.__file__)
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def _candidate_module_symbol_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _candidate_module_call_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name):
            names.add(function.id)
        elif isinstance(function, ast.Attribute):
            names.add(function.attr)
    return names


def test_public_surface_uses_frozen_build_and_validate_signatures() -> None:
    assert CANDIDATE_REVISION_SCHEMA_VERSION == CANDIDATE_SCHEMA_VERSION
    assert issubclass(CandidateRevisionError, ValueError)
    keyword_only_names = [
        "registry",
        "base_cad_handoff",
        "baseline_context",
        "parent_candidate",
        "change_impact",
        "mutation_evidence",
        "lineage_context",
    ]
    build_parameters = inspect.signature(build_candidate_revision).parameters
    assert list(build_parameters) == keyword_only_names
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in build_parameters.values()
    )
    assert build_parameters["lineage_context"].default == ()
    assert all(
        parameter.default is inspect.Parameter.empty
        for name, parameter in build_parameters.items()
        if name != "lineage_context"
    )

    validate_parameters = inspect.signature(validate_candidate_revision).parameters
    assert list(validate_parameters) == ["payload", *keyword_only_names]
    assert (
        validate_parameters["payload"].kind
        is inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert validate_parameters["payload"].default is inspect.Parameter.empty
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for name, parameter in validate_parameters.items()
        if name != "payload"
    )
    assert validate_parameters["lineage_context"].default == ()
    assert all(
        parameter.default is inspect.Parameter.empty
        for name, parameter in validate_parameters.items()
        if name not in {"payload", "lineage_context"}
    )


def test_public_surface_rejects_omitted_required_arguments() -> None:
    with pytest.raises(TypeError, match="required|missing"):
        build_candidate_revision()
    with pytest.raises(TypeError, match="required|missing"):
        validate_candidate_revision({})


def test_root_revision_is_sealed_closed_and_deterministic() -> None:
    args = _valid_args()
    first = build_candidate_revision(**deepcopy(args))
    replay = build_candidate_revision(**deepcopy(args))
    assert first == replay
    assert set(first) == {
        "schema_version",
        "revision_id",
        "state",
        "run_id",
        "baseline_revision",
        "parent_candidate_revision_sha256",
        "upstream_bindings",
        "candidate_artifacts",
        "change_scope",
        "component_lineage",
        "view_lineage",
        "mutation_evidence",
        "candidate_revision_sha256",
    }
    assert first["schema_version"] == CANDIDATE_SCHEMA_VERSION
    assert first["state"] == "SEALED_CANDIDATE"
    assert first["parent_candidate_revision_sha256"] is None
    assert validate_candidate_revision(first, **deepcopy(args)) == first


def test_replay_is_permutation_invariant() -> None:
    args = _valid_args()
    first = build_candidate_revision(**deepcopy(args))
    permuted = deepcopy(args)
    permuted["registry"]["components"] = list(
        reversed(permuted["registry"]["components"])
    )
    permuted["change_impact"]["impact"]["component_ids"] = list(
        reversed(permuted["change_impact"]["impact"]["component_ids"])
    )
    assert build_candidate_revision(**permuted) == first


def test_build_and_validate_return_deep_detached_copies() -> None:
    args = _valid_args()
    passed_args = deepcopy(args)
    revision = build_candidate_revision(**passed_args)
    frozen = deepcopy(revision)
    passed_args["registry"]["components"][0]["component_type"] = "MUTATED"
    passed_args["baseline_context"]["artifact_bytes"] = b"changed-after-build"
    assert revision == frozen
    normalized = validate_candidate_revision(revision, **deepcopy(args))
    assert normalized == revision
    assert normalized is not revision


@pytest.mark.parametrize(
    "mutation",
    [
        lambda context: context.__setitem__("artifact_bytes", b"changed-bytes"),
        lambda context: context.__setitem__("current", True),
        lambda context: context["reference"].__setitem__(
            "reference_sha256", "f" * 64
        ),
    ],
)
def test_dara_baseline_currentness_is_not_caller_minted(mutation) -> None:
    args = _valid_args()
    mutation(args["baseline_context"])
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)


def test_dara_r3_candidate_reference_cannot_be_used_as_baseline() -> None:
    material = _accepted_r3_material()
    candidate_context = {
        "reference": material["parent_reference"],
        "observation": dara.observe_drawing_artifact_currentness(
            reference=material["parent_reference"],
            artifact_bytes=material["candidate_bytes"],
            observation_evidence_sha256="e" * 64,
        ),
        "artifact_bytes": material["candidate_bytes"],
    }
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(
            **_valid_args(baseline_context=candidate_context)
        )


def test_foreign_baseline_scope_cannot_be_rebound() -> None:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    foreign = _baseline_context(
        "foreign",
        scope={**SCOPE, "project_id": "foreign-project"},
    )
    foreign_args = _valid_args(
        baseline_context=foreign,
        parent_candidate=root,
        tag="foreign-baseline",
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**foreign_args)


@pytest.mark.parametrize(
    ("target_name", "mutation"),
    [
        (
            "registry",
            lambda registry: registry.__setitem__(
                "registry_snapshot_sha256", "f" * 64
            ),
        ),
        (
            "change_impact",
            lambda impact: impact.__setitem__("registry_snapshot_sha256", "e" * 64),
        ),
        (
            "change_impact",
            lambda impact: impact["correspondence"].__setitem__(
                "child_reference_sha256", "d" * 64
            ),
        ),
        (
            "change_impact",
            lambda impact: impact["impact"]["component_ids"].clear(),
        ),
    ],
)
def test_r3_registry_impact_correspondence_and_provenance_are_bound(
    target_name, mutation
) -> None:
    args = _valid_args()
    mutation(args[target_name])
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)


def test_r3_parent_current_correspondence_swap_fails_closed() -> None:
    args = _valid_args()
    correspondence = args["change_impact"]["correspondence"]
    correspondence["parent_reference_id"], correspondence["child_reference_id"] = (
        correspondence["child_reference_id"],
        correspondence["parent_reference_id"],
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)


def test_r2_candidate_output_mismatch_is_foreign() -> None:
    args = _valid_args()
    args["base_cad_handoff"]["candidate_output_sha256"] = "f" * 64
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)


def test_root_depth_two_and_depth_three_use_closed_lineage_context() -> None:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    child = build_candidate_revision(**_child_args(root_args, root, tag="child"))
    grandchild_args = _child_args(root_args, child, tag="grandchild")
    grandchild_args["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [root]
    )
    grandchild = build_candidate_revision(**grandchild_args)
    assert grandchild["parent_candidate_revision_sha256"] == child[
        "candidate_revision_sha256"
    ]


def test_missing_lineage_context_for_indirect_parent_fails_closed() -> None:
    root_args, _root, _child, grandchild_args = _valid_lineage_chain()
    with pytest.raises(CandidateRevisionError, match="LINEAGE"):
        build_candidate_revision(**grandchild_args)


def test_lineage_conflicting_ancestor_is_refused_independently() -> None:
    root_args, root, _child, grandchild_args = _valid_lineage_chain()
    conflicting = deepcopy(grandchild_args)
    conflicting["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [root, {**root, "run_id": "conflict"}]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**conflicting)


def test_lineage_repeated_ancestor_is_refused_independently() -> None:
    root_args, root, _child, grandchild_args = _valid_lineage_chain()
    repeated = deepcopy(grandchild_args)
    repeated["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [root, root]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**repeated)


def test_lineage_cycle_mutation_is_refused_independently() -> None:
    root_args, root, child, grandchild_args = _valid_lineage_chain()
    cycle = deepcopy(root)
    cycle["parent_candidate_revision_sha256"] = child[
        "candidate_revision_sha256"
    ]
    assert cycle["parent_candidate_revision_sha256"] == child[
        "candidate_revision_sha256"
    ]
    cyclic = deepcopy(grandchild_args)
    cyclic["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [cycle]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**cyclic)


def test_lineage_foreign_ancestor_is_refused_independently() -> None:
    root_args, root, _child, grandchild_args = _valid_lineage_chain()
    foreign = deepcopy(root)
    foreign["baseline_revision"] = "foreign-baseline"
    assert foreign["baseline_revision"] != root["baseline_revision"]
    foreign_context = deepcopy(grandchild_args)
    foreign_context["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [foreign]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**foreign_context)


def test_lineage_scope_and_baseline_context_are_exact() -> None:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    child = build_candidate_revision(**_child_args(root_args, root, tag="child"))
    grandchild_args = _child_args(root_args, child, tag="grandchild")
    context = _lineage_context(root_args["baseline_context"], [root])
    context["scope"]["project_id"] = "foreign-project"
    grandchild_args["lineage_context"] = context
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**grandchild_args)


def test_legal_sibling_forks_preserve_parent_history() -> None:
    root_args = _valid_args()
    parent = build_candidate_revision(**deepcopy(root_args))
    before = deepcopy(parent)
    left = build_candidate_revision(
        **_child_args(root_args, parent, tag="left")
    )
    right = build_candidate_revision(
        **_child_args(root_args, parent, tag="right")
    )
    assert left["candidate_revision_sha256"] != right["candidate_revision_sha256"]
    assert left["parent_candidate_revision_sha256"] == parent[
        "candidate_revision_sha256"
    ]
    assert right["parent_candidate_revision_sha256"] == parent[
        "candidate_revision_sha256"
    ]
    assert parent == before


def test_historical_stale_upstream_parent_can_continue_but_baseline_rollover_cannot() -> None:
    root_args = _valid_args()
    historical = build_candidate_revision(**deepcopy(root_args))
    fresh_material = _accepted_r3_material(
        primitive_ids=("prim-new-a", "prim-new-b")
    )
    child = build_candidate_revision(
        **_valid_args(material=fresh_material, parent_candidate=historical, tag="fresh")
    )
    assert child["parent_candidate_revision_sha256"] == historical[
        "candidate_revision_sha256"
    ]

    rollover = _child_args(root_args, historical, tag="rollover")
    rollover["baseline_context"] = _baseline_context("rolled-baseline")
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**rollover)


@pytest.mark.parametrize(
    "field",
    [
        "current",
        "accepted",
        "published",
        "production_current",
        "visual_verdict",
        "engineering_verdict",
        "approval",
        "repair_permission",
        "release_eligible",
    ],
)
def test_caller_cannot_mint_current_accepted_published_or_approval_authority(field) -> None:
    args = _valid_args()
    revision = build_candidate_revision(**deepcopy(args))
    forged = deepcopy(revision)
    forged[field] = True
    with pytest.raises(CandidateRevisionError):
        validate_candidate_revision(forged, **deepcopy(args))


def test_candidate_state_is_not_selection_acceptance_or_publication() -> None:
    revision = build_candidate_revision(**_valid_args())
    assert revision["state"] == "SEALED_CANDIDATE"
    assert not any(
        key in revision
        for key in ("current", "accepted", "published", "approval", "verdict")
    )
    for forbidden in (
        "select_candidate",
        "accept_candidate",
        "publish_candidate",
        "approve_candidate",
    ):
        assert not hasattr(candidate_module, forbidden)


@pytest.mark.parametrize(
    ("field", "value", "rebind_checksum"),
    [
        ("evidence_kind", "R4_FORGED_MUTATION", True),
        ("mutation_terminal", "SUCCESS", True),
        ("evidence_sha256", "f" * 64, False),
    ],
)
def test_forged_r4_mutation_evidence_is_refused(
    field: str, value: object, rebind_checksum: bool
) -> None:
    args = _valid_args()
    args["mutation_evidence"][field] = value
    if rebind_checksum:
        _rebind_mutation_evidence_checksum(args["mutation_evidence"])
    else:
        assert args["mutation_evidence"][field] == value
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)


def test_unknown_fields_and_caller_minted_checksum_fail_closed() -> None:
    args = _valid_args()
    args["mutation_evidence"]["caller_checksum"] = "f" * 64
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**args)
    revision = build_candidate_revision(**_valid_args())
    forged = deepcopy(revision)
    forged["candidate_revision_sha256"] = "e" * 64
    with pytest.raises(CandidateRevisionError):
        validate_candidate_revision(forged, **_valid_args())


def test_candidate_module_has_no_io_live_or_second_store_authority() -> None:
    source, tree = _candidate_module_source_and_tree()
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            imported_modules.add(node.module)

    allowed_internal_modules = {
        "cad_agent",
        "cad_agent.base_cad_adapter",
        "cad_agent.component_view_registry",
        "cad_agent.drawing_artifact_reference",
        "cad_agent.drawing_contracts",
    }
    internal_modules = {
        module
        for module in imported_modules
        if module == "cad_agent" or module.startswith("cad_agent.")
    }
    assert internal_modules <= allowed_internal_modules

    forbidden_import_roots = {
        "anthropic",
        "autocad",
        "azure",
        "boto3",
        "calendar",
        "datetime",
        "google",
        "httpx",
        "io",
        "mcp_integration_lib",
        "openai",
        "os",
        "pathlib",
        "pyautocad",
        "pythoncom",
        "random",
        "requests",
        "secrets",
        "shelve",
        "shutil",
        "socket",
        "sqlite3",
        "subprocess",
        "tempfile",
        "time",
        "win32com",
        "zoneinfo",
    }
    imported_roots = {module.split(".", 1)[0].lower() for module in imported_modules}
    assert imported_roots.isdisjoint(forbidden_import_roots)

    forbidden_tokens = (
        "sqlite3",
        "shelve.open",
        "subprocess.",
        "requests.",
        "httpx.",
        "socket.",
        "os.system",
        "open(",
        "Path(",
        "manifest_store",
        "revision_store",
        "current_store",
        "registry_store",
        "current_pointer",
        "selection_authority",
        "owner_authority",
        "replacement_authority",
        "set_current",
        "select_candidate",
        "accept_candidate",
        "publish_candidate",
        "promote_candidate",
        "approve_candidate",
        "AutoCAD",
        "File IPC",
    )
    assert not any(token in source for token in forbidden_tokens)


def test_candidate_module_has_no_duplicate_store_or_database_symbols() -> None:
    _source, tree = _candidate_module_source_and_tree()
    symbols = _candidate_module_symbol_names(tree)
    store_symbols = {
        symbol
        for symbol in symbols
        if re.search(r"(?:store|repository|database)", symbol, re.IGNORECASE)
    }
    assert store_symbols == set()


def test_candidate_module_has_no_current_pointer_or_selection_symbols() -> None:
    _source, tree = _candidate_module_source_and_tree()
    symbols = _candidate_module_symbol_names(tree)
    pointer_symbols = {
        symbol
        for symbol in symbols
        if re.search(
            r"(?:^|_)(?:current|selected|accepted|published|promoted|pointer)(?:_|$)",
            symbol,
            re.IGNORECASE,
        )
    }
    assert pointer_symbols == set()


def test_candidate_module_has_no_owner_authority_or_replacement_mutators() -> None:
    source, tree = _candidate_module_source_and_tree()
    symbols = _candidate_module_symbol_names(tree)
    calls = _candidate_module_call_names(tree)
    mutator_prefixes = (
        "set_",
        "assign_",
        "grant_",
        "issue_",
        "mint_",
        "promote_",
        "publish_",
        "approve_",
    )
    authority_mutators = {
        name
        for name in symbols | calls
        if any(name.lower().startswith(prefix) for prefix in mutator_prefixes)
        and any(
            fragment in name.lower()
            for fragment in ("owner", "authority", "approval", "verdict", "publication")
        )
    }
    assert authority_mutators == set()
    assert not any(
        token in source.lower()
        for token in (
            "owner_authority",
            "replacement_authority",
            "selection_authority",
            "current_authority",
            "approval_authority",
            "publication_authority",
        )
    )


# R4 Task2 RED contract.  These names intentionally use the existing
# candidate-revision owner without introducing a second store or authority
# owner.  The production seam is not present on this RED head, so the helper
# fails at the causal boundary rather than hiding the missing implementation
# behind fixture setup.
TASK2_STATE_SCHEMA_VERSION = "candidate-revision-state-1.0"
TASK2_TRANSITION_SCHEMA_VERSION = "candidate-revision-state-transition-1.0"
TASK2_STATE_FIELDS = (
    "schema_version",
    "candidate_revisions",
    "current_candidate_revision_sha256",
    "state_sha256",
)


def _task2_api():
    names = (
        "build_candidate_revision_state",
        "transition_candidate_revision_state",
        "validate_candidate_revision_state",
    )
    missing = [
        name for name in names if not callable(getattr(candidate_module, name, None))
    ]
    assert not missing, f"R4 Task2 production seam missing: {', '.join(missing)}"
    return tuple(getattr(candidate_module, name) for name in names)


def _task2_state(
    candidates: list[dict[str, object]],
    *,
    current: str | None = None,
) -> dict[str, object]:
    build_state, _transition, _validate = _task2_api()
    return build_state(
        candidate_revisions=candidates,
        current_candidate_revision_sha256=current,
    )


def _task2_transition(
    kind: str,
    candidate: dict[str, object],
    *,
    expected_current: str | None,
) -> dict[str, object]:
    return {
        "schema_version": TASK2_TRANSITION_SCHEMA_VERSION,
        "transition_kind": kind,
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "expected_current_candidate_revision_sha256": expected_current,
    }


def _task2_apply(
    state: dict[str, object],
    candidate: dict[str, object],
    transition: dict[str, object],
) -> dict[str, object]:
    _build_state, apply_transition, _validate_state = _task2_api()
    return apply_transition(
        state=state,
        candidate_revision=candidate,
        transition=transition,
    )


def _task2_state_sha256(state: dict[str, object]) -> str:
    return canonical_json_sha256(
        {
            key: value
            for key, value in state.items()
            if key != "state_sha256"
        }
    )


def _task2_mutable_module_bindings() -> dict[str, object]:
    mutable_types = (dict, list, set, bytearray)
    return {
        name: deepcopy(value)
        for name, value in vars(candidate_module).items()
        if not name.startswith("__") and isinstance(value, mutable_types)
    }


def _task2_selected_and_superseded() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    _root_args, root, left, right = _task2_graph()
    selected = _task2_apply(
        _task2_state([root, left, right]),
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


def _task2_graph() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    left = build_candidate_revision(**_child_args(root_args, root, tag="task2-left"))
    right = build_candidate_revision(**_child_args(root_args, root, tag="task2-right"))
    return root_args, root, left, right


def test_task2_state_replay_and_candidate_permutation_are_deterministic() -> None:
    _root_args, root, left, right = _task2_graph()
    first = _task2_state([right, root, left])
    replay = _task2_state([left, right, root])
    assert first == replay
    assert first["schema_version"] == TASK2_STATE_SCHEMA_VERSION
    assert first["current_candidate_revision_sha256"] is None

    select_root = _task2_transition("SELECT", root, expected_current=None)
    assert _task2_apply(first, root, select_root) == _task2_apply(
        replay, root, select_root
    )


def test_task2_validator_accepts_and_returns_a_valid_canonical_state() -> None:
    _root_args, root, _left, _right = _task2_graph()
    state = _task2_state([root])
    _build_state, _transition, validate_state = _task2_api()

    assert validate_state(state) == state


def test_task2_state_schema_checksum_and_current_membership_are_explicit() -> None:
    _root_args, root, left, _right = _task2_graph()
    candidates = [root, left]
    candidates_before = deepcopy(candidates)
    state = _task2_state(candidates)

    assert set(state) == set(TASK2_STATE_FIELDS)
    assert state["schema_version"] == TASK2_STATE_SCHEMA_VERSION
    assert isinstance(state["candidate_revisions"], list)
    assert state["current_candidate_revision_sha256"] is None
    assert "state_sha256" in state
    assert state["state_sha256"] == _task2_state_sha256(state)
    assert candidates == candidates_before

    with pytest.raises(CandidateRevisionError, match="CURRENT|CANDIDATE|MEMBER"):
        _task2_state([root], current=left["candidate_revision_sha256"])


def test_task2_operations_preserve_original_caller_owned_inputs() -> None:
    _root_args, root, left, _right = _task2_graph()
    candidates = [root, left]
    candidates_before = deepcopy(candidates)
    state = _task2_state(candidates)
    state_before = deepcopy(state)
    transition = _task2_transition("SELECT", root, expected_current=None)
    transition_before = deepcopy(transition)
    root_before = deepcopy(root)

    result = _task2_apply(state, root, transition)

    assert candidates == candidates_before
    assert state == state_before
    assert root == root_before
    assert transition == transition_before
    assert result is not state


def test_task2_outputs_are_independent_and_module_has_no_mutable_owner() -> None:
    _root_args, root, _left, _right = _task2_graph()
    _source, tree = _candidate_module_source_and_tree()
    mutable_module_bindings_before = _task2_mutable_module_bindings()
    top_level_assignments = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            top_level_assignments.extend(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            top_level_assignments.append(node.target.id)
    assert not any(
        any(fragment in name.lower() for fragment in ("current", "store", "owner", "authority"))
        for name in top_level_assignments
    )

    first = _task2_state([root])
    second = _task2_state([root])
    assert first == second
    assert first is not second

    first["candidate_revisions"].clear()
    assert second["candidate_revisions"]
    assert _task2_state([root]) == second
    assert _task2_mutable_module_bindings() == mutable_module_bindings_before


def test_task2_selecting_the_same_candidate_twice_is_rejected_as_replay() -> None:
    _root_args, root, _left, _right = _task2_graph()
    state = _task2_state([root])
    select_root = _task2_transition("SELECT", root, expected_current=None)
    selected = _task2_apply(state, root, select_root)
    with pytest.raises(CandidateRevisionError, match="CURRENT|REPLAY|SELECT"):
        _task2_apply(selected, root, select_root)


def test_task2_superseding_a_non_current_candidate_fails_closed() -> None:
    _root_args, root, left, right = _task2_graph()
    state = _task2_apply(
        _task2_state([root, left, right]),
        root,
        _task2_transition("SELECT", root, expected_current=None),
    )
    state = _task2_apply(
        state,
        left,
        _task2_transition(
            "SUPERSEDE",
            left,
            expected_current=root["candidate_revision_sha256"],
        ),
    )
    with pytest.raises(CandidateRevisionError, match="CURRENT|PARENT|SUPERSEDE"):
        _task2_apply(
            state,
            right,
            _task2_transition(
                "SUPERSEDE",
                right,
                expected_current=left["candidate_revision_sha256"],
            ),
        )


def test_task2_supersede_rejects_tampered_candidate_identity() -> None:
    _root_args, root, left, _right = _task2_graph()
    selected = _task2_apply(
        _task2_state([root, left]),
        root,
        _task2_transition("SELECT", root, expected_current=None),
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
