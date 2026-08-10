from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
from functools import lru_cache
import inspect
from pathlib import Path

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


def _baseline_context(tag: str = "baseline") -> dict[str, object]:
    artifact_bytes = _artifact_bytes(tag)
    reference = dara.issue_drawing_artifact_reference(
        **SCOPE,
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
    registry = r3.build_component_view_registry(
        upstream_context=context,
        components=r3_tests._component_inputs(context),
    )
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
        "child_reference": child,
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
        },
        "mutation_evidence": _mutation_evidence(material, tag),
        "lineage_context": deepcopy(lineage_context),
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


def test_public_surface_is_frozen_and_keyword_only() -> None:
    assert CANDIDATE_REVISION_SCHEMA_VERSION == CANDIDATE_SCHEMA_VERSION
    assert issubclass(CandidateRevisionError, ValueError)
    expected = [
        "registry",
        "base_cad_handoff",
        "baseline_context",
        "parent_candidate",
        "change_impact",
        "mutation_evidence",
        "lineage_context",
    ]
    for function in (build_candidate_revision, validate_candidate_revision):
        parameters = inspect.signature(function).parameters
        assert list(parameters) == expected
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in parameters.values()
        )


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
    revision = build_candidate_revision(**deepcopy(args))
    frozen = deepcopy(revision)
    args["registry"]["components"][0]["component_type"] = "MUTATED"
    args["baseline_context"]["artifact_bytes"] = b"changed-after-build"
    assert revision == frozen
    normalized = validate_candidate_revision(revision, **deepcopy(_valid_args()))
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
    foreign = _baseline_context("foreign")
    foreign["reference"]["project_id"] = "foreign-project"
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**_valid_args(baseline_context=foreign))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda registry: registry.__setitem__("registry_snapshot_sha256", "f" * 64),
        lambda impact: impact.__setitem__("registry_snapshot_sha256", "e" * 64),
        lambda impact: impact["correspondence"].__setitem__(
            "child_reference_sha256", "d" * 64
        ),
        lambda impact: impact["impact"]["component_ids"].clear(),
    ],
)
def test_r3_registry_impact_correspondence_and_provenance_are_bound(mutation) -> None:
    args = _valid_args()
    target = args["registry"] if mutation.__name__ == "<lambda>" else args["change_impact"]
    try:
        mutation(args["registry"])
    except (KeyError, TypeError):
        mutation(args["change_impact"])
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
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    child = build_candidate_revision(**_child_args(root_args, root, tag="child"))
    grandchild_args = _child_args(root_args, child, tag="grandchild")
    with pytest.raises(CandidateRevisionError, match="LINEAGE"):
        build_candidate_revision(**grandchild_args)


def test_lineage_rejects_missing_conflicting_repeated_cycle_and_foreign_ancestors() -> None:
    root_args = _valid_args()
    root = build_candidate_revision(**deepcopy(root_args))
    child = build_candidate_revision(**_child_args(root_args, root, tag="child"))
    grandchild_args = _child_args(root_args, child, tag="grandchild")

    missing = deepcopy(grandchild_args)
    missing["lineage_context"] = _lineage_context(
        root_args["baseline_context"], []
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**missing)

    conflicting = deepcopy(grandchild_args)
    conflicting["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [root, {**root, "run_id": "conflict"}]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**conflicting)

    repeated = deepcopy(grandchild_args)
    repeated["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [root, root]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**repeated)

    cycle = deepcopy(root)
    cycle["parent_candidate_revision_sha256"] = child[
        "candidate_revision_sha256"
    ]
    cyclic = deepcopy(grandchild_args)
    cyclic["lineage_context"] = _lineage_context(
        root_args["baseline_context"], [cycle]
    )
    with pytest.raises(CandidateRevisionError):
        build_candidate_revision(**cyclic)

    foreign = deepcopy(root)
    foreign["baseline_revision"] = "foreign-baseline"
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
    source = Path(candidate_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    assert imported.isdisjoint(
        {
            "sqlite3",
            "shelve",
            "socket",
            "requests",
            "httpx",
            "subprocess",
        }
    )
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
        "AutoCAD",
        "File IPC",
    )
    assert not any(token in source for token in forbidden_tokens)
