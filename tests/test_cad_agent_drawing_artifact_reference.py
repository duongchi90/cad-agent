from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib
import inspect
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


REFERENCE_FIELDS = {
    "schema_version",
    "reference_id",
    "run_id",
    "project_id",
    "drawing_id",
    "artifact_role",
    "artifact_sha256",
    "reference_sha256",
    "upstream_evidence",
    "parent_reference_id",
    "parent_reference_sha256",
    "r3_provenance_binding",
}
CURRENT_OBSERVATION_FIELDS = {
    "schema_version",
    "lookup_id",
    "lookup_sha256",
    "run_id",
    "project_id",
    "drawing_id",
    "reference_id",
    "reference_sha256",
    "expected_artifact_sha256",
    "observed_artifact_sha256",
    "comparison",
    "observation_evidence_sha256",
}
def _module():
    return importlib.import_module("cad_agent.drawing_artifact_reference")


def _artifact_bytes(tag: str = "baseline") -> bytes:
    return f"synthetic-drawing-artifact::{tag}".encode("utf-8")


def _baseline_evidence() -> dict[str, object]:
    return {
        "evidence_kind": "BASELINE_CUSTODY",
        "evidence_id": "baseline-evidence-001",
        "evidence_sha256": "1" * 64,
    }


def _mutation_evidence(
    *,
    candidate_reference: dict[str, object],
    pre_sha256: str,
    post_sha256: str,
) -> dict[str, object]:
    evidence = {
        "evidence_kind": "POST_REPAIR_TRANSITION",
        "r3_candidate_reference_id": candidate_reference["reference_id"],
        "r3_candidate_reference_sha256": candidate_reference["reference_sha256"],
        "r5_failure_id": "r5-fail-001",
        "r5_failure_sha256": "2" * 64,
        "r4_transition_id": "r4-transition-001",
        "r4_transition_sha256": "3" * 64,
        "r6_mutation_request_id": "r6-request-001",
        "r6_mutation_request_sha256": "4" * 64,
        "r6_result_id": "r6-result-001",
        "r6_result_sha256": "5" * 64,
        "executor_result_id": "executor-result-001",
        "executor_result_sha256": "6" * 64,
        "pre_artifact_sha256": pre_sha256,
        "post_artifact_sha256": post_sha256,
        "protected_constraints_sha256": "7" * 64,
        "workspace_evidence_sha256": "8" * 64,
        "mutation_terminal": "SUCCESS",
        "partial_mutation": False,
        "timed_out": False,
        "rollback_failed": False,
        "cleanup_state": "VERIFIED",
    }
    accepted_r6_result = _accepted_r6_result_for_transition(evidence)
    evidence["accepted_r6_result"] = accepted_r6_result
    evidence["r6_result_id"] = accepted_r6_result["result_sha256"]
    evidence["r6_result_sha256"] = accepted_r6_result["result_sha256"]
    return evidence


def _issue_test_integrity_sha256(
    payload: dict[str, object],
    *,
    domain: str | None = None,
) -> str:
    del domain
    return canonical_json_sha256(payload)


def _seal_mutation_evidence(
    evidence: dict[str, object],
) -> dict[str, object]:
    """Recompute the canonical integrity digest after a test mutation."""
    evidence.pop("accepted_transition_evidence_sha256", None)
    evidence["accepted_transition_evidence_sha256"] = _issue_test_integrity_sha256(
        evidence,
        domain="drawing-artifact-reference-1.0:transition",
    )
    return evidence


def _reseal_reference(
    reference: dict[str, object],
) -> dict[str, object]:
    """Rebind canonical reference integrity fields after one targeted mutation."""
    identity_payload = dict(reference)
    identity_payload.pop("reference_id")
    identity_payload.pop("reference_sha256")
    reference["reference_id"] = "dara-ref-" + _issue_test_integrity_sha256(
        identity_payload,
        domain="drawing-artifact-reference-1.0:reference",
    )
    hash_payload = dict(reference)
    hash_payload.pop("reference_sha256")
    reference["reference_sha256"] = canonical_json_sha256(hash_payload)
    return reference


def _reseal_current_observation(
    observation: dict[str, object],
) -> dict[str, object]:
    """Rebind canonical observation integrity fields after one targeted mutation."""
    identity_payload = dict(observation)
    identity_payload.pop("lookup_id")
    identity_payload.pop("lookup_sha256")
    observation["lookup_id"] = "dara-lookup-" + _issue_test_integrity_sha256(
        identity_payload,
        domain="drawing-artifact-current-observation-1.0:observation",
    )
    hash_payload = dict(observation)
    hash_payload.pop("lookup_sha256")
    observation["lookup_sha256"] = canonical_json_sha256(hash_payload)
    return observation


def _r3_binding() -> dict[str, object]:
    return {
        "registry_snapshot_sha256": "9" * 64,
        "provenance_sha256": "a" * 64,
    }


def _r3_candidate_evidence() -> dict[str, object]:
    return {
        "evidence_kind": "R3_CANDIDATE_CUSTODY",
        "evidence_id": "r3-candidate-evidence-001",
        "evidence_sha256": "b" * 64,
    }


def _issue_baseline():
    module = _module()
    return module.issue_drawing_artifact_reference(
        run_id="run-182-001",
        project_id="project-001",
        drawing_id="drawing-001",
        artifact_role="BASELINE",
        artifact_bytes=_artifact_bytes(),
        upstream_evidence=_baseline_evidence(),
    )


def _issue_r3_candidate():
    module = _module()
    return module.issue_drawing_artifact_reference(
        run_id="run-182-001",
        project_id="project-001",
        drawing_id="drawing-001",
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes("r3-candidate"),
        upstream_evidence=_r3_candidate_evidence(),
        r3_provenance_binding=_r3_binding(),
    )


def _post_repair_material():
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("repaired")
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(mutation)
    issued = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=mutation,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )
    return parent, child_bytes, deepcopy(issued["upstream_evidence"])


def _issue_candidate():
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    child = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=mutation,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )
    return parent, child, child_bytes


def _caller_resealed_parent_child_chain():
    """Build a fully self-consistent custody chain from opaque evidence."""
    parent, child, child_bytes = _issue_candidate()
    forged_parent = deepcopy(parent)
    forged_parent["artifact_sha256"] = "c" * 64
    forged_parent["upstream_evidence"]["evidence_id"] = "caller-resealed-parent-evidence"
    _reseal_reference(
        forged_parent,
    )

    forged_child = deepcopy(child)
    evidence = forged_child["upstream_evidence"]
    forged_child["parent_reference_id"] = forged_parent["reference_id"]
    forged_child["parent_reference_sha256"] = forged_parent["reference_sha256"]
    evidence["r3_candidate_reference_id"] = forged_parent["reference_id"]
    evidence["r3_candidate_reference_sha256"] = forged_parent["reference_sha256"]
    evidence["pre_artifact_sha256"] = forged_parent["artifact_sha256"]
    evidence["executor_result_id"] = "caller-minted-custody-success"
    evidence["executor_result_sha256"] = "e" * 64
    _seal_mutation_evidence(
        evidence,
    )
    _reseal_reference(
        forged_child,
    )
    return forged_parent, forged_child, child_bytes


def test_dara_public_surface_is_closed_and_versioned() -> None:
    module = _module()
    assert module.DRAWING_ARTIFACT_REFERENCE_SCHEMA_VERSION == ("drawing-artifact-reference-1.0")
    assert module.DRAWING_ARTIFACT_CURRENT_OBSERVATION_SCHEMA_VERSION == (
        "drawing-artifact-current-observation-1.0"
    )
    assert issubclass(module.DrawingArtifactReferenceError, ValueError)
    for name in (
        "issue_drawing_artifact_reference",
        "validate_drawing_artifact_reference",
        "drawing_artifact_reference_sha256",
        "observe_drawing_artifact_currentness",
        "validate_drawing_artifact_current_observation",
        "drawing_artifact_current_observation_sha256",
        "require_current_drawing_artifact_reference",
    ):
        assert callable(getattr(module, name))


def test_dara_uses_integrity_identity_hashes_not_secret_credentials() -> None:
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "_OWNER_AUTHENTICITY_KEY" not in source
    assert "import hmac" not in source
    assert "AUTHENTICITY" not in source

    reference = _issue_baseline()
    expected_reference_identity = "dara-ref-" + canonical_json_sha256(
        {
            key: value
            for key, value in reference.items()
            if key not in {"reference_id", "reference_sha256"}
        }
    )
    assert reference["reference_id"] == expected_reference_identity

    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="d" * 64,
    )
    expected_observation_identity = "dara-lookup-" + canonical_json_sha256(
        {
            key: value
            for key, value in observation.items()
            if key not in {"lookup_id", "lookup_sha256"}
        }
    )
    assert observation["lookup_id"] == expected_observation_identity


def test_integrity_api_has_no_caller_trust_hooks() -> None:
    module = _module()
    forbidden = {"owner_authenticity_issuer", "owner_authenticity_anchor"}

    for name in (
        "issue_drawing_artifact_reference",
        "validate_drawing_artifact_reference",
        "observe_drawing_artifact_currentness",
        "validate_drawing_artifact_current_observation",
        "require_current_drawing_artifact_reference",
    ):
        assert forbidden.isdisjoint(inspect.signature(getattr(module, name)).parameters)

    assert not hasattr(module, "DrawingArtifactAuthenticityIssuer")
    assert not hasattr(module, "DrawingArtifactAuthenticityAnchor")


def test_module_issues_and_validates_integrity_records_without_caller_capabilities() -> None:
    module = _module()
    reference = module.issue_drawing_artifact_reference(
        run_id="run-182-001",
        project_id="project-001",
        drawing_id="drawing-001",
        artifact_role="BASELINE",
        artifact_bytes=_artifact_bytes(),
        upstream_evidence=_baseline_evidence(),
    )
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="d" * 64,
    )

    assert module.validate_drawing_artifact_reference(reference) == reference
    assert module.validate_drawing_artifact_current_observation(observation) == observation
    module.require_current_drawing_artifact_reference(
        reference=reference,
        observation=observation,
        artifact_bytes=_artifact_bytes(),
    )


def test_baseline_reference_is_deterministic_closed_and_owner_observed() -> None:
    module = _module()
    first = _issue_baseline()
    second = _issue_baseline()

    assert first == second
    assert set(first) == REFERENCE_FIELDS
    assert first["artifact_role"] == "BASELINE"
    assert first["artifact_sha256"] == hashlib.sha256(_artifact_bytes()).hexdigest()
    assert first["parent_reference_id"] is None
    assert first["parent_reference_sha256"] is None
    assert first["r3_provenance_binding"] is None
    assert (
        module.validate_drawing_artifact_reference(
            first,
        )
        == first
    )
    assert module.drawing_artifact_reference_sha256(first) == first["reference_sha256"]


def test_reference_identity_changes_when_authoritative_artifact_bytes_change() -> None:
    module = _module()
    first = _issue_baseline()
    changed = module.issue_drawing_artifact_reference(
        run_id=first["run_id"],
        project_id=first["project_id"],
        drawing_id=first["drawing_id"],
        artifact_role="BASELINE",
        artifact_bytes=_artifact_bytes("changed"),
        upstream_evidence=_baseline_evidence(),
    )
    assert changed["artifact_sha256"] != first["artifact_sha256"]
    assert changed["reference_sha256"] != first["reference_sha256"]
    assert changed["reference_id"] != first["reference_id"]


def test_legacy_caller_trust_hooks_are_rejected_by_public_api() -> None:
    module = _module()

    with pytest.raises(TypeError):
        module.issue_drawing_artifact_reference(
            owner_authenticity_issuer=lambda domain, payload_sha256: payload_sha256,
            run_id="run-182-001",
            project_id="project-001",
            drawing_id="drawing-001",
            artifact_role="BASELINE",
            artifact_bytes=_artifact_bytes(),
            upstream_evidence=_baseline_evidence(),
        )
    reference = _issue_baseline()
    with pytest.raises(TypeError):
        module.validate_drawing_artifact_reference(
            reference,
            owner_authenticity_anchor=lambda domain, payload_sha256, signature: True,
        )


def test_integrity_only_resealing_is_structurally_valid_and_currentness_uses_observed_bytes() -> None:
    module = _module()
    reference = _issue_baseline()
    forged_reference = deepcopy(reference)
    forged_reference["upstream_evidence"]["evidence_id"] = "caller-minted-custody"
    _reseal_reference(forged_reference)

    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="d" * 64,
    )
    forged_observation = deepcopy(observation)
    forged_observation["observation_evidence_sha256"] = "e" * 64
    _reseal_current_observation(forged_observation)

    assert module.validate_drawing_artifact_reference(forged_reference) == forged_reference
    assert (
        module.validate_drawing_artifact_current_observation(forged_observation)
        == forged_observation
    )

    observed = module.observe_drawing_artifact_currentness(
        reference=forged_reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="e" * 64,
    )
    assert observed["comparison"] == "CURRENT"


def test_reference_and_observation_identities_are_bound_to_record_shape() -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="d" * 64,
    )
    forged_reference = deepcopy(reference)
    forged_reference["reference_id"] = "dara-ref-" + observation["lookup_id"].removeprefix(
        "dara-lookup-"
    )
    forged_reference["reference_sha256"] = canonical_json_sha256(
        {key: value for key, value in forged_reference.items() if key != "reference_sha256"}
    )

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(forged_reference)

    assert str(exc.value) == "CANONICAL_HASH_MISMATCH"


def test_reference_validation_returns_a_detached_copy() -> None:
    module = _module()
    payload = _issue_baseline()
    normalized = module.validate_drawing_artifact_reference(payload)
    assert normalized is not payload
    assert normalized["upstream_evidence"] is not payload["upstream_evidence"]
    payload["upstream_evidence"]["evidence_id"] = "mutated-after-validation"
    assert normalized["upstream_evidence"]["evidence_id"] == "baseline-evidence-001"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda value: value.pop("drawing_id"), "INVALID_REFERENCE"),
        (lambda value: value.__setitem__("unexpected", True), "INVALID_REFERENCE"),
        (
            lambda value: value.__setitem__("artifact_role", "ACCEPTED"),
            "CATEGORY_CONFUSION",
        ),
        (
            lambda value: value.__setitem__("reference_sha256", "f" * 64),
            "CANONICAL_HASH_MISMATCH",
        ),
        (
            lambda value: value.__setitem__("artifact_sha256", "e" * 64),
            "CANONICAL_HASH_MISMATCH",
        ),
    ],
)
def test_malformed_forged_or_category_confused_reference_fails_closed(
    mutation,
    expected_code: str,
) -> None:
    module = _module()
    payload = deepcopy(_issue_baseline())
    mutation(payload)
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(payload)
    assert str(exc.value) == expected_code


def test_valid_post_repair_child_preserves_immutable_parent_history() -> None:
    module = _module()
    parent, child, child_bytes = _issue_candidate()
    parent_before = deepcopy(parent)

    assert child["artifact_role"] == "R3_CANDIDATE"
    assert child["artifact_sha256"] == hashlib.sha256(child_bytes).hexdigest()
    assert child["parent_reference_id"] == parent["reference_id"]
    assert child["parent_reference_sha256"] == parent["reference_sha256"]
    assert child["r3_provenance_binding"] == _r3_binding()
    assert child["reference_id"] != parent["reference_id"]
    assert parent == parent_before
    assert (
        module.validate_drawing_artifact_reference(
            child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=child["upstream_evidence"][
                "accepted_transition_evidence_sha256"
            ],
        )
        == child
    )


@pytest.mark.parametrize(
    ("field", "replacement", "expected_code"),
    [
        (
            "r3_candidate_reference_id",
            "dara-ref-foreign-candidate",
            "WRONG_CANDIDATE",
        ),
        ("r3_candidate_reference_sha256", "c" * 64, "WRONG_CANDIDATE"),
        ("pre_artifact_sha256", "not-a-sha256", "MUTATION_EVIDENCE_MISSING"),
        ("post_artifact_sha256", "d" * 64, "POST_ARTIFACT_MISMATCH"),
        ("mutation_terminal", "FAILED", "MUTATION_NOT_SUCCESSFUL"),
        ("partial_mutation", True, "MUTATION_NOT_SUCCESSFUL"),
        ("timed_out", True, "MUTATION_NOT_SUCCESSFUL"),
        ("rollback_failed", True, "MUTATION_NOT_SUCCESSFUL"),
        ("cleanup_state", "UNCERTAIN", "CLEANUP_UNCERTAIN"),
    ],
)
def test_public_validation_rejects_resealed_parented_child_transition_defects(
    field: str,
    replacement: object,
    expected_code: str,
) -> None:
    module = _module()
    parent, child, _ = _issue_candidate()
    resealed_child = deepcopy(child)
    resealed_child["upstream_evidence"][field] = replacement
    _seal_mutation_evidence(
        resealed_child["upstream_evidence"],
    )
    _reseal_reference(resealed_child)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(
            resealed_child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=resealed_child["upstream_evidence"][
                "accepted_transition_evidence_sha256"
            ],
        )

    assert str(exc.value) == expected_code


def test_currentness_refuses_resealed_parented_child_with_failed_cleanup() -> None:
    module = _module()
    parent, child, child_bytes = _issue_candidate()
    observation = module.observe_drawing_artifact_currentness(
        reference=child,
        parent_reference=parent,
        accepted_transition_evidence_sha256=child["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        artifact_bytes=child_bytes,
        observation_evidence_sha256="b" * 64,
    )
    resealed_child = deepcopy(child)
    resealed_child["upstream_evidence"]["cleanup_state"] = "UNCERTAIN"
    _seal_mutation_evidence(
        resealed_child["upstream_evidence"],
    )
    _reseal_reference(resealed_child)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.require_current_drawing_artifact_reference(
            reference=resealed_child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=resealed_child["upstream_evidence"][
                "accepted_transition_evidence_sha256"
            ],
            observation=observation,
            artifact_bytes=child_bytes,
        )

    assert str(exc.value) == "CLEANUP_UNCERTAIN"


def test_post_repair_child_requires_supplied_transition_evidence_digest() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("repaired-without-seal")
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "MUTATION_EVIDENCE_MISSING"


def test_parented_reference_consumption_requires_independent_sealed_anchors() -> None:
    module = _module()
    parent, child, _ = _issue_candidate()
    accepted_transition_sha256 = child["upstream_evidence"]["accepted_transition_evidence_sha256"]

    assert (
        module.validate_drawing_artifact_reference(
            child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=accepted_transition_sha256,
        )
        == child
    )

    with pytest.raises(module.DrawingArtifactReferenceError) as parent_exc:
        module.validate_drawing_artifact_reference(
            child,
            accepted_transition_evidence_sha256=accepted_transition_sha256,
        )
    assert str(parent_exc.value) == "PARENT_MISMATCH"

    with pytest.raises(module.DrawingArtifactReferenceError) as transition_exc:
        module.validate_drawing_artifact_reference(
            child,
            parent_reference=parent,
        )
    assert str(transition_exc.value) == "MUTATION_EVIDENCE_MISSING"


def test_integrity_only_accepts_a_fully_resealed_parent_transition() -> None:
    module = _module()
    forged_parent, forged_child, _ = _caller_resealed_parent_child_chain()

    assert module.validate_drawing_artifact_reference(
        forged_child,
        parent_reference=forged_parent,
        accepted_transition_evidence_sha256=forged_child["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
    ) == forged_child


def test_integrity_only_currentness_is_recomputed_from_observed_bytes() -> None:
    module = _module()
    forged_parent, forged_child, child_bytes = _caller_resealed_parent_child_chain()

    observation = module.observe_drawing_artifact_currentness(
        reference=forged_child,
        parent_reference=forged_parent,
        accepted_transition_evidence_sha256=forged_child["upstream_evidence"][
            "accepted_transition_evidence_sha256"
        ],
        artifact_bytes=child_bytes,
        observation_evidence_sha256="d" * 64,
    )
    assert observation["comparison"] == "CURRENT"


def test_resealed_observation_remains_integrity_material_only() -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="d" * 64,
    )
    forged_observation = deepcopy(observation)
    forged_observation["observation_evidence_sha256"] = "e" * 64
    _reseal_current_observation(forged_observation)

    assert module.validate_drawing_artifact_current_observation(forged_observation) == (
        forged_observation
    )
    module.require_current_drawing_artifact_reference(
        reference=reference,
        observation=forged_observation,
        artifact_bytes=_artifact_bytes(),
    )


@pytest.mark.parametrize(
    ("field", "owner_observed_failure", "caller_claimed_success"),
    [
        ("mutation_terminal", "FAILED", "SUCCESS"),
        ("partial_mutation", True, False),
        ("timed_out", True, False),
        ("rollback_failed", True, False),
        ("cleanup_state", "UNCERTAIN", "VERIFIED"),
        ("executor_result_sha256", "6" * 64, "e" * 64),
    ],
)
def test_integrity_digest_allows_opaque_evidence_but_semantic_gate_still_applies(
    field: str,
    owner_observed_failure: object,
    caller_claimed_success: object,
) -> None:
    module = _module()
    parent, child_bytes, transition = _post_repair_material()
    owner_observed_transition = deepcopy(transition)
    owner_observed_transition[field] = owner_observed_failure
    _seal_mutation_evidence(owner_observed_transition)
    caller_minted_transition = deepcopy(owner_observed_transition)
    caller_minted_transition[field] = caller_claimed_success
    _seal_mutation_evidence(
        caller_minted_transition,
    )

    issued = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=caller_minted_transition,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )
    assert issued["upstream_evidence"][field] == caller_claimed_success


def test_post_repair_child_accepts_structurally_valid_opaque_external_evidence() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    fixture_child = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=mutation,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )
    opaque_external_evidence = {
        "r4_transition_id": "opaque-transition-beta",
        "r4_transition_sha256": "d" * 64,
        "r6_mutation_request_id": "opaque-request-gamma",
        "r6_mutation_request_sha256": "e" * 64,
        "executor_result_id": "opaque-executor-epsilon",
        "executor_result_sha256": "0" * 64,
        "protected_constraints_sha256": "1" * 64,
        "workspace_evidence_sha256": "a" * 64,
    }
    mutation.update(opaque_external_evidence)
    _seal_mutation_evidence(mutation)

    child = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=mutation,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )

    assert {
        field: child["upstream_evidence"][field] for field in opaque_external_evidence
    } == opaque_external_evidence
    assert child["parent_reference_id"] == parent["reference_id"]
    assert child["parent_reference_sha256"] == parent["reference_sha256"]
    assert child["artifact_sha256"] == hashlib.sha256(child_bytes).hexdigest()
    assert child["reference_id"] != fixture_child["reference_id"]
    assert child["reference_sha256"] != fixture_child["reference_sha256"]
    assert (
        module.validate_drawing_artifact_reference(
            child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=child["upstream_evidence"][
                "accepted_transition_evidence_sha256"
            ],
        )
        == child
    )


def test_parent_history_is_immutable_before_child_issuance_and_resealing_is_refused() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    parent_before_child_issuance = deepcopy(parent)
    attempted_historical_mutation = deepcopy(parent)
    attempted_historical_mutation["upstream_evidence"]["evidence_id"] = "mutated-historical-parent"
    attempted_historical_mutation["reference_sha256"] = canonical_json_sha256(
        attempted_historical_mutation
    )
    child_bytes = _artifact_bytes("resealed-parent-child")
    resealed_transition = _mutation_evidence(
        candidate_reference=attempted_historical_mutation,
        pre_sha256=attempted_historical_mutation["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(resealed_transition)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=resealed_transition,
            parent_reference=attempted_historical_mutation,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "HISTORICAL_MUTATION"
    assert parent == parent_before_child_issuance

    _issue_candidate()
    assert parent == parent_before_child_issuance


def test_post_repair_transition_rejects_baseline_as_r3_candidate_parent() -> None:
    module = _module()
    parent = _issue_baseline()
    child_bytes = _artifact_bytes("repaired")
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(mutation)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_baseline_consumption_rejects_an_r3_candidate_reference() -> None:
    module = _module()
    candidate = _issue_r3_candidate()

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(
            candidate,
            expected_artifact_role="BASELINE",
        )
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_post_repair_transition_rejects_wrong_r3_candidate_identity() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation["r3_candidate_reference_id"] = "r3-candidate-foreign"
    _seal_mutation_evidence(mutation)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "WRONG_CANDIDATE"


@pytest.mark.parametrize(
    ("scope_field", "foreign_value"),
    [
        pytest.param("run_id", "run-foreign", id="run-scope"),
        pytest.param("project_id", "project-foreign", id="project-scope"),
        pytest.param("drawing_id", "drawing-foreign", id="drawing-scope"),
    ],
)
def test_post_repair_child_rejects_each_foreign_parent_scope_after_binding_its_evidence(
    scope_field: str,
    foreign_value: str,
) -> None:
    module = _module()
    parent, child_bytes, _ = _post_repair_material()
    foreign_scope = {
        "run_id": parent["run_id"],
        "project_id": parent["project_id"],
        "drawing_id": parent["drawing_id"],
    }
    foreign_scope[scope_field] = foreign_value
    substituted_parent = module.issue_drawing_artifact_reference(
        **foreign_scope,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes("r3-candidate-foreign"),
        upstream_evidence=_r3_candidate_evidence(),
        r3_provenance_binding=_r3_binding(),
    )
    mutation = _mutation_evidence(
        candidate_reference=substituted_parent,
        pre_sha256=substituted_parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(mutation)
    assert mutation["r3_candidate_reference_id"] == substituted_parent["reference_id"]
    assert mutation["r3_candidate_reference_sha256"] == substituted_parent["reference_sha256"]

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=substituted_parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "SCOPE_MISMATCH"


def test_post_repair_child_rejects_substituted_parent_with_tampered_hash_custody() -> None:
    module = _module()
    parent, child_bytes, _ = _post_repair_material()
    substituted_parent = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes("r3-candidate-hash-substitution"),
        upstream_evidence=_r3_candidate_evidence(),
        r3_provenance_binding=_r3_binding(),
    )
    substituted_parent["reference_sha256"] = "f" * 64
    mutation = _mutation_evidence(
        candidate_reference=substituted_parent,
        pre_sha256=substituted_parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(mutation)
    assert mutation["r3_candidate_reference_id"] == substituted_parent["reference_id"]
    assert mutation["r3_candidate_reference_sha256"] == substituted_parent["reference_sha256"]

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=substituted_parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "CANONICAL_HASH_MISMATCH"


def test_post_repair_child_rejects_forged_post_sha_even_when_r6_result_sha_exists() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256="d" * 64,
    )
    _seal_mutation_evidence(mutation)
    assert mutation["r6_result_sha256"] == mutation["accepted_r6_result"]["result_sha256"]
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "POST_ARTIFACT_MISMATCH"


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("r5_failure_id", id="r5-failure-id"),
        pytest.param("r5_failure_sha256", id="r5-failure-sha256"),
        pytest.param("r4_transition_id", id="r4-transition-id"),
        pytest.param("r4_transition_sha256", id="r4-transition-sha256"),
        pytest.param("r6_mutation_request_id", id="r6-mutation-request-id"),
        pytest.param("r6_mutation_request_sha256", id="r6-mutation-request-sha256"),
        pytest.param("r6_result_id", id="r6-result-id"),
        pytest.param("r6_result_sha256", id="r6-result-sha256"),
        pytest.param("executor_result_id", id="executor-result-id"),
        pytest.param("executor_result_sha256", id="executor-result-sha256"),
        pytest.param("pre_artifact_sha256", id="pre-artifact-sha256"),
        pytest.param("post_artifact_sha256", id="post-artifact-sha256"),
        pytest.param("protected_constraints_sha256", id="protected-constraints-sha256"),
        pytest.param("workspace_evidence_sha256", id="workspace-evidence-sha256"),
    ],
)
def test_post_repair_child_rejects_each_missing_required_evidence_binding(
    field: str,
) -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation.pop(field)
    _seal_mutation_evidence(mutation)
    r3_provenance_binding = _r3_binding()

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=r3_provenance_binding,
        )
    assert str(exc.value) == "MUTATION_EVIDENCE_MISSING"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        pytest.param(
            "r5_failure_id",
            "opaque-failure-replacement",
            id="r5-failure-id",
        ),
        ("r5_failure_sha256", "f" * 64),
        pytest.param(
            "r4_transition_id",
            "opaque-transition-replacement",
            id="r4-transition-id",
        ),
        ("r4_transition_sha256", "f" * 64),
        pytest.param(
            "r6_mutation_request_id",
            "opaque-request-replacement",
            id="r6-mutation-request-id",
        ),
        ("r6_mutation_request_sha256", "f" * 64),
        pytest.param(
            "r6_result_id",
            "opaque-result-replacement",
            id="r6-result-id",
        ),
        ("r6_result_sha256", "f" * 64),
        pytest.param(
            "executor_result_id",
            "opaque-executor-replacement",
            id="executor-result-id",
        ),
        ("executor_result_sha256", "f" * 64),
        ("protected_constraints_sha256", "f" * 64),
        ("workspace_evidence_sha256", "f" * 64),
    ],
)
def test_post_repair_child_rejects_each_unsealed_opaque_evidence_mutation(
    field: str,
    replacement: str,
) -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation[field] = replacement

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    expected_code = (
        "R6_RESULT_INVALID"
        if field in {"r5_failure_id", "r5_failure_sha256", "r6_result_id", "r6_result_sha256"}
        else "MUTATION_EVIDENCE_MISMATCH"
    )
    assert str(exc.value) == expected_code


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        pytest.param("r5_failure_id", "", id="r5-failure-id"),
        pytest.param("r4_transition_id", 4, id="r4-transition-id"),
        pytest.param("r6_mutation_request_id", None, id="r6-mutation-request-id"),
        pytest.param("r6_result_id", [], id="r6-result-id"),
        pytest.param("executor_result_id", {}, id="executor-result-id"),
        pytest.param("r5_failure_sha256", "not-a-sha256", id="r5-failure-sha256"),
        pytest.param("r4_transition_sha256", "D" * 64, id="r4-transition-sha256"),
        pytest.param(
            "r6_mutation_request_sha256",
            "e" * 63,
            id="r6-mutation-request-sha256",
        ),
        pytest.param("r6_result_sha256", 6, id="r6-result-sha256"),
        pytest.param("executor_result_sha256", None, id="executor-result-sha256"),
        pytest.param(
            "protected_constraints_sha256",
            "g" * 64,
            id="protected-constraints-sha256",
        ),
        pytest.param(
            "workspace_evidence_sha256",
            False,
            id="workspace-evidence-sha256",
        ),
    ],
)
def test_post_repair_child_rejects_each_malformed_opaque_evidence_binding(
    field: str,
    replacement: object,
) -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation[field] = replacement
    _seal_mutation_evidence(mutation)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    expected_code = (
        "R6_RESULT_INVALID"
        if field in {"r6_result_id", "r6_result_sha256"}
        else "MUTATION_EVIDENCE_MISSING"
    )
    assert str(exc.value) == expected_code


def test_post_repair_child_rejects_transition_evidence_category_confusion() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation["evidence_kind"] = "R6_MUTATION_RESULT"
    _seal_mutation_evidence(mutation)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "MUTATION_EVIDENCE_MISMATCH"


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("r5_failure_id", None, "MUTATION_EVIDENCE_MISSING"),
        ("pre_artifact_sha256", "b" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("mutation_terminal", "FAILED", "MUTATION_NOT_SUCCESSFUL"),
        ("partial_mutation", True, "MUTATION_NOT_SUCCESSFUL"),
        ("timed_out", True, "MUTATION_NOT_SUCCESSFUL"),
        ("rollback_failed", True, "MUTATION_NOT_SUCCESSFUL"),
        ("cleanup_state", "UNCERTAIN", "CLEANUP_UNCERTAIN"),
    ],
)
def test_post_repair_child_rejects_incomplete_or_uncertain_mutation_evidence(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    if value is None:
        mutation.pop(field)
    else:
        mutation[field] = value
    _seal_mutation_evidence(mutation)
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == expected_code


def test_candidate_requires_exact_r3_provenance_binding_but_dara_does_not_infer_it() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=parent,
            r3_provenance_binding=None,
        )
    assert str(exc.value) == "CUSTODY_EVIDENCE_MISSING"


def test_current_observation_is_owner_observed_and_deterministic() -> None:
    module = _module()
    reference = _issue_baseline()
    first = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    second = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    assert first == second
    assert set(first) == CURRENT_OBSERVATION_FIELDS
    assert first["comparison"] == "CURRENT"
    assert first["observed_artifact_sha256"] == reference["artifact_sha256"]
    assert module.drawing_artifact_current_observation_sha256(first) == first["lookup_sha256"]
    assert module.validate_drawing_artifact_current_observation(first) == first
    module.require_current_drawing_artifact_reference(
        reference=reference,
        observation=first,
        artifact_bytes=_artifact_bytes(),
    )


def test_current_requirement_recomputes_from_fresh_owner_observed_bytes() -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    require_current = module.require_current_drawing_artifact_reference

    if "artifact_bytes" not in inspect.signature(require_current).parameters:
        require_current(reference=reference, observation=observation)
        pytest.fail("currentness gate accepted caller observation without fresh owner bytes")

    require_current(
        reference=reference,
        observation=observation,
        artifact_bytes=_artifact_bytes(),
    )
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        require_current(
            reference=reference,
            observation=observation,
            artifact_bytes=_artifact_bytes("changed-after-observation"),
        )
    assert str(exc.value) == "STALE_REFERENCE"


def test_current_observation_marks_changed_bytes_stale_and_current_requirement_refuses() -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes("changed"),
        observation_evidence_sha256="b" * 64,
    )
    assert observation["comparison"] == "STALE"
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.require_current_drawing_artifact_reference(
            reference=reference,
            observation=observation,
            artifact_bytes=_artifact_bytes("changed"),
        )
    assert str(exc.value) == "STALE_REFERENCE"


def test_unhashable_artifact_role_is_a_categorical_reference_refusal() -> None:
    module = _module()
    reference = _issue_baseline()
    reference["artifact_role"] = []

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(reference)
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_unhashable_artifact_role_is_a_categorical_issue_refusal() -> None:
    module = _module()

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id="run-182-001",
            project_id="project-001",
            drawing_id="drawing-001",
            artifact_role=[],
            artifact_bytes=_artifact_bytes(),
            upstream_evidence=_baseline_evidence(),
        )
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_unhashable_observation_comparison_is_a_categorical_currentness_refusal() -> None:
    module = _module()
    observation = module.observe_drawing_artifact_currentness(
        reference=_issue_baseline(),
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    observation["comparison"] = []
    _reseal_current_observation(observation)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_current_observation(observation)
    assert str(exc.value) == "CURRENTNESS_FORGED"


def test_caller_cannot_flip_stale_observation_to_current() -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes("changed"),
        observation_evidence_sha256="b" * 64,
    )
    forged = deepcopy(observation)
    forged["comparison"] = "CURRENT"
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_current_observation(forged)
    assert str(exc.value) in {"CURRENTNESS_FORGED", "CANONICAL_HASH_MISMATCH"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "run-foreign"),
        ("project_id", "project-foreign"),
        ("drawing_id", "drawing-foreign"),
        ("reference_id", "reference-foreign"),
        ("reference_sha256", "c" * 64),
    ],
)
def test_cross_scope_or_foreign_observation_replay_is_refused(
    field: str,
    value: str,
) -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    replay = deepcopy(observation)
    replay[field] = value
    with pytest.raises(module.DrawingArtifactReferenceError):
        module.require_current_drawing_artifact_reference(
            reference=reference,
            observation=replay,
            artifact_bytes=_artifact_bytes(),
        )


@pytest.mark.parametrize(
    ("scope_field", "foreign_value"),
    [
        ("run_id", "run-foreign"),
        ("project_id", "project-foreign"),
        ("drawing_id", "drawing-foreign"),
    ],
)
def test_valid_cross_scope_replay_is_refused_when_logical_evidence_is_reused(
    scope_field: str,
    foreign_value: str,
) -> None:
    module = _module()
    reference = _issue_baseline()
    foreign_scope = {
        "run_id": reference["run_id"],
        "project_id": reference["project_id"],
        "drawing_id": reference["drawing_id"],
    }
    foreign_scope[scope_field] = foreign_value
    foreign_reference = module.issue_drawing_artifact_reference(
        **foreign_scope,
        artifact_role="BASELINE",
        artifact_bytes=_artifact_bytes(),
        upstream_evidence=_baseline_evidence(),
    )
    foreign_observation = module.observe_drawing_artifact_currentness(
        reference=foreign_reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )

    assert foreign_reference["upstream_evidence"] == reference["upstream_evidence"]
    assert foreign_reference["artifact_sha256"] == reference["artifact_sha256"]
    assert (
        module.validate_drawing_artifact_current_observation(
            foreign_observation,
        )
        == foreign_observation
    )
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.require_current_drawing_artifact_reference(
            reference=reference,
            observation=foreign_observation,
            artifact_bytes=_artifact_bytes(),
        )
    assert str(exc.value) in {
        "SCOPE_MISMATCH",
        "FOREIGN_REFERENCE",
        "REPLAY_MISMATCH",
    }


def test_r6_result_sha_is_evidence_only_and_cannot_mint_dara_currentness() -> None:
    module = _module()
    parent, child, child_bytes = _issue_candidate()
    mutation = child["upstream_evidence"]
    forged = {
        "schema_version": "drawing-artifact-current-observation-1.0",
        "lookup_id": "r6-result-as-lookup",
        "lookup_sha256": mutation["r6_result_sha256"],
        "run_id": child["run_id"],
        "project_id": child["project_id"],
        "drawing_id": child["drawing_id"],
        "reference_id": child["reference_id"],
        "reference_sha256": child["reference_sha256"],
        "expected_artifact_sha256": child["artifact_sha256"],
        "observed_artifact_sha256": child["artifact_sha256"],
        "comparison": "CURRENT",
        "observation_evidence_sha256": mutation["r6_result_sha256"],
    }
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.require_current_drawing_artifact_reference(
            reference=child,
            parent_reference=parent,
            accepted_transition_evidence_sha256=mutation["accepted_transition_evidence_sha256"],
            observation=forged,
            artifact_bytes=child_bytes,
        )
    assert str(exc.value) in {
        "CURRENT_LOOKUP_INVALID",
        "CURRENTNESS_FORGED",
        "CANONICAL_HASH_MISMATCH",
    }
    assert parent["reference_id"] == child["parent_reference_id"]


def test_r6_result_sha_alone_cannot_mint_post_repair_dara_custody() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    r6_result_only = {
        "evidence_kind": "POST_REPAIR_TRANSITION",
        "r6_result_sha256": mutation["r6_result_sha256"],
    }

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=r6_result_only,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "MUTATION_EVIDENCE_MISSING"


def test_caller_claimed_sha_and_currentness_cannot_override_owner_observed_bytes() -> None:
    module = _module()
    reference = _issue_baseline()
    caller_claimed_sha256 = reference["artifact_sha256"]
    owner_observed_bytes = _artifact_bytes("owner-observed-mismatch")

    with pytest.raises(module.DrawingArtifactReferenceError) as custody_exc:
        module.issue_drawing_artifact_reference(
            run_id=reference["run_id"],
            project_id=reference["project_id"],
            drawing_id=reference["drawing_id"],
            artifact_role="BASELINE",
            artifact_bytes=owner_observed_bytes,
            upstream_evidence=_baseline_evidence(),
            claimed_artifact_sha256=caller_claimed_sha256,
        )
    assert str(custody_exc.value) == "ARTIFACT_SHA_MISMATCH"

    with pytest.raises(module.DrawingArtifactReferenceError) as currentness_exc:
        module.observe_drawing_artifact_currentness(
            reference=reference,
            artifact_bytes=owner_observed_bytes,
            observation_evidence_sha256="b" * 64,
            claimed_artifact_sha256=caller_claimed_sha256,
            claimed_comparison="CURRENT",
        )
    assert str(currentness_exc.value) == "ARTIFACT_SHA_MISMATCH"


@pytest.mark.parametrize(
    "forbidden",
    [
        "current",
        "accepted",
        "published",
        "approved",
        "approval",
        "verdict",
        "selection",
        "r4_revision_id",
        "workspace_path",
        "backup_path",
        "provider_output",
        "r4_candidate_revision_id",
        "r4_selection_state",
        "r4_publication_state",
        "r5_verdict_id",
        "r5_verdict_state",
        "r6_mutation_request_id",
        "r6_execution_state",
        "approval_id",
        "approval_state",
        "workspace_id",
        "workspace_lease_id",
        "publication_id",
        "publication_target",
        "current_reference_store_id",
        "revision_store_id",
        "manifest_checkpoint_id",
    ],
)
def test_reference_rejects_downstream_or_ambient_authority_fields(
    forbidden: str,
) -> None:
    module = _module()
    payload = deepcopy(_issue_baseline())
    payload[forbidden] = True
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(payload)
    assert str(exc.value) == "INVALID_REFERENCE"


@pytest.mark.parametrize(
    "forbidden",
    [
        "r4_candidate_revision_id",
        "r5_verdict_id",
        "r6_execution_state",
        "approval_id",
        "workspace_id",
        "publication_id",
        "current_reference_store_id",
        "revision_store_id",
        "manifest_checkpoint_id",
    ],
)
def test_current_observation_rejects_downstream_authority_fields_and_second_store_claims(
    forbidden: str,
) -> None:
    module = _module()
    reference = _issue_baseline()
    observation = module.observe_drawing_artifact_currentness(
        reference=reference,
        artifact_bytes=_artifact_bytes(),
        observation_evidence_sha256="b" * 64,
    )
    observation[forbidden] = "forbidden-authority"
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_current_observation(observation)
    assert str(exc.value) == "CURRENT_LOOKUP_INVALID"


def test_hashing_reuses_canonical_json_owner_and_static_boundary_has_no_second_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    reference = _issue_baseline()
    calls: list[dict[str, object]] = []
    owner = canonical_json_sha256

    def _record(payload):
        calls.append(deepcopy(dict(payload)))
        return owner(payload)

    monkeypatch.setattr(module, "canonical_json_sha256", _record)
    assert module.drawing_artifact_reference_sha256(reference) == reference["reference_sha256"]
    assert calls

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "canonical_json_sha256" in source
    assert "hashlib" in source
    assert "hmac" not in source
    for forbidden in (
        "json.dumps",
        "sqlite3",
        "shelve",
        "pickle",
        "cad_agent.manifest.write_manifest",
        "cad_agent.live.repair_live",
        "dxf_builder_lib.repair",
        "mcp_integration_lib.repair2",
        "subprocess",
        "socket",
        "requests",
        "currentness_authority",
        "candidate_store",
        "current_store",
    ):
        assert forbidden not in source


def test_static_authority_boundary_is_stateless_and_allows_no_seam_imports() -> None:
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_stdlib_modules = {
        "__future__",
        "collections",
        "copy",
        "dataclasses",
        "hashlib",
        "importlib",
        "typing",
    }
    canonical_imports: list[ast.ImportFrom] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".", 1)[0] in allowed_stdlib_modules for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            if node.module == "cad_agent.drawing_contracts":
                canonical_imports.append(node)
                assert [(alias.name, alias.asname) for alias in node.names] == [
                    ("canonical_json_sha256", None)
                ]
            else:
                assert node.module is not None
                assert node.module.split(".", 1)[0] in allowed_stdlib_modules

    assert len(canonical_imports) == 1
    assert module.canonical_json_sha256 is canonical_json_sha256
    assert "from cad_agent.approved_repair_adapter" not in source

    mutable_nodes = (
        ast.Dict,
        ast.DictComp,
        ast.List,
        ast.ListComp,
        ast.Set,
        ast.SetComp,
    )
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            assert value is not None
            assert not isinstance(value, mutable_nodes)
            assert not isinstance(value, ast.Call)
        if isinstance(statement, ast.ClassDef):
            assert statement.name == "DrawingArtifactReferenceError"

    for function in (
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        assert not any(
            isinstance(default, mutable_nodes)
            for default in (*function.args.defaults, *function.args.kw_defaults)
            if default is not None
        )

    assert not any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"__import__", "compile", "eval", "exec", "open"}
        for node in ast.walk(tree)
    )


def test_public_surface_has_no_second_currentness_authority_or_in_memory_store() -> None:
    module = _module()
    public_names = {name for name in vars(module) if not name.startswith("_")}
    lowered_names = {name.lower() for name in public_names}

    assert (
        not {
            "currentness_authority",
            "drawing_artifact_current_store",
            "drawing_artifact_candidate_store",
            "candidate_store",
            "current_store",
            "register_current_reference",
            "set_current_reference",
            "r4_revision_store",
            "r4_currentness_authority",
            "r5_verdict_authority",
            "r6_workspace_authority",
            "approval_authority",
            "workspace_authority",
            "publication_authority",
            "manifest_authority",
            "checkpoint_authority",
        }
        & lowered_names
    )
    assert not {
        name
        for name in lowered_names
        if name.startswith(
            (
                "r4_",
                "r5_",
                "r6_",
                "approval_",
                "workspace_",
                "publication_",
                "manifest_",
                "checkpoint_",
            )
        )
    }
    assert not {
        name
        for name in lowered_names
        if ("candidate" in name or "current" in name)
        and ("store" in name or "cache" in name or "registry" in name)
    }


def test_public_api_has_no_r4_r5_r6_decision_or_live_execution_parameters() -> None:
    module = _module()
    forbidden_parameter_fragments = {
        "approve",
        "verdict",
        "publish",
        "select",
        "workspace_path",
        "backup_path",
        "autocad",
        "provider",
        "file_ipc",
        "r4_",
        "r5_",
        "r6_",
        "manifest",
        "checkpoint",
    }
    for name in (
        "issue_drawing_artifact_reference",
        "observe_drawing_artifact_currentness",
        "require_current_drawing_artifact_reference",
    ):
        parameters = set(inspect.signature(getattr(module, name)).parameters)
        assert all(
            fragment not in parameter
            for parameter in parameters
            for fragment in forbidden_parameter_fragments
        )


def test_errors_are_categorical_and_do_not_echo_private_values() -> None:
    module = _module()
    payload = deepcopy(_issue_baseline())
    private_value = "C:/private/customer/secret.dwg"
    payload["unexpected_private_path"] = private_value
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(payload)
    assert str(exc.value) == "INVALID_REFERENCE"
    assert private_value not in str(exc.value)


def _accepted_r6_result_for_transition(
    transition: dict[str, object],
) -> dict[str, object]:
    r6 = importlib.import_module("cad_agent.approved_repair_adapter")
    operation = importlib.import_module("cad_agent.repair_operation_contract")
    candidate_id = "candidate-r6-dara-215"
    candidate_sha256 = "c" * 64
    result: dict[str, object] = {
        "schema_version": r6.R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": candidate_id,
        "candidate_revision_sha256": candidate_sha256,
        "candidate_artifact_reference_id": transition["r3_candidate_reference_id"],
        "candidate_artifact_reference_sha256": transition[
            "r3_candidate_reference_sha256"
        ],
        "r5_failure_id": transition["r5_failure_id"],
        "r5_failure_sha256": transition["r5_failure_sha256"],
        "repair_plan_id": "repair-plan-r6-dara-215",
        "repair_plan_sha256": "d" * 64,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": operation.REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": "e" * 64,
        "authorization_id": "authorization-r6-dara-215",
        "executor_capability": "LINE",
        "executor_result_category": "HANDLE_RETURNED",
        "mutation_outcome": "SUCCESS",
        "closure": {
            "lease_id": "lease-r6-dara-215",
            "candidate_identity": candidate_id,
            "source_identity": transition["r5_failure_id"],
            "source_fingerprint": transition["r5_failure_sha256"],
            "close_outcome": "closed",
            "cleanup_outcome": "zero_survivors",
            "save_changes": False,
            "lifecycle_state": "closed",
        },
        "requires_new_r5_cycle": True,
    }
    result["result_sha256"] = canonical_json_sha256(result)
    accepted = r6.validate_approved_repair_result(
        result,
        expected_candidate_artifact_reference_id=transition[
            "r3_candidate_reference_id"
        ],
        expected_candidate_artifact_reference_sha256=transition[
            "r3_candidate_reference_sha256"
        ],
        expected_r5_failure_id=transition["r5_failure_id"],
        expected_r5_failure_sha256=transition["r5_failure_sha256"],
    )
    assert accepted == result
    return result


def _mutation_evidence_with_accepted_r6_result(
    *,
    candidate_reference: dict[str, object],
    pre_sha256: str,
    post_sha256: str,
) -> dict[str, object]:
    transition = _mutation_evidence(
        candidate_reference=candidate_reference,
        pre_sha256=pre_sha256,
        post_sha256=post_sha256,
    )
    accepted_r6_result = _accepted_r6_result_for_transition(transition)
    transition["accepted_r6_result"] = accepted_r6_result
    transition["r6_result_id"] = accepted_r6_result["result_sha256"]
    transition["r6_result_sha256"] = accepted_r6_result["result_sha256"]
    return _seal_mutation_evidence(transition)


def _reseal_r6_result(result: dict[str, object]) -> dict[str, object]:
    result.pop("result_sha256", None)
    result["result_sha256"] = canonical_json_sha256(result)
    return result


def test_post_repair_child_accepts_owner_validated_r6_result_binding() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("r6-owner-bound-child")
    transition = _mutation_evidence_with_accepted_r6_result(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    transition_before = deepcopy(transition)

    child = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_bytes,
        upstream_evidence=transition,
        parent_reference=parent,
        r3_provenance_binding=_r3_binding(),
    )

    assert transition == transition_before
    assert child["upstream_evidence"]["accepted_r6_result"] == transition[
        "accepted_r6_result"
    ]
    assert child["upstream_evidence"]["accepted_r6_result"] is not transition[
        "accepted_r6_result"
    ]
    assert child["upstream_evidence"]["r6_result_id"] == transition[
        "accepted_r6_result"
    ]["result_sha256"]
    assert child["upstream_evidence"]["r6_result_sha256"] == transition[
        "accepted_r6_result"
    ]["result_sha256"]


def test_post_repair_child_rejects_generic_resealed_r6_pair_without_owner_result() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("generic-r6-pair-child")
    transition = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    transition.pop("accepted_r6_result")
    transition["r6_result_id"] = "caller-resealed-generic-result"
    transition["r6_result_sha256"] = "f" * 64
    _seal_mutation_evidence(transition)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=transition,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )

    assert str(exc.value) == "R6_RESULT_INVALID"


def test_post_repair_child_rejects_embedded_r6_result_bound_to_foreign_parent_artifact() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    foreign_parent = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes("foreign-r6-parent"),
        upstream_evidence={
            "evidence_kind": "R3_CANDIDATE_CUSTODY",
            "evidence_id": "r3-candidate-evidence-foreign-r6",
            "evidence_sha256": "f" * 64,
        },
        r3_provenance_binding=_r3_binding(),
    )
    child_bytes = _artifact_bytes("foreign-r6-parent-child")
    transition = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    result = deepcopy(transition["accepted_r6_result"])
    result["candidate_artifact_reference_id"] = foreign_parent["reference_id"]
    result["candidate_artifact_reference_sha256"] = foreign_parent["reference_sha256"]
    _reseal_r6_result(result)

    r6 = importlib.import_module("cad_agent.approved_repair_adapter")
    assert r6.validate_approved_repair_result(
        result,
        expected_candidate_artifact_reference_id=foreign_parent["reference_id"],
        expected_candidate_artifact_reference_sha256=foreign_parent[
            "reference_sha256"
        ],
        expected_r5_failure_id=transition["r5_failure_id"],
        expected_r5_failure_sha256=transition["r5_failure_sha256"],
    ) == result

    transition["accepted_r6_result"] = result
    transition["r6_result_id"] = result["result_sha256"]
    transition["r6_result_sha256"] = result["result_sha256"]
    _seal_mutation_evidence(transition)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=transition,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "R6_RESULT_INVALID"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda result: result.__setitem__("result_sha256", "f" * 64),
        lambda result: _reseal_r6_result({**result, "mutation_outcome": "FAILED"}),
        lambda result: _reseal_r6_result({**result, "requires_new_r5_cycle": False}),
        lambda result: _reseal_r6_result({**result, "executor_result_category": "FOREIGN"}),
    ],
)
def test_post_repair_child_rejects_invalid_embedded_r6_result(mutator) -> None:
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("invalid-r6-result-child")
    transition = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    result = deepcopy(transition["accepted_r6_result"])
    mutated = mutator(result)
    if mutated is not None:
        result = mutated
    transition["accepted_r6_result"] = result
    _seal_mutation_evidence(transition)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=transition,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "R6_RESULT_INVALID"


def test_post_repair_child_rejects_r5_substitution_against_embedded_r6_result() -> None:
    module = _module()
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("foreign-r5-child")
    transition = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    transition["r5_failure_id"] = "foreign-r5-failure"
    _seal_mutation_evidence(transition)

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=transition,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "R6_RESULT_INVALID"


def test_hostile_embedded_r6_result_is_refused_before_mapping_protocol_traversal() -> None:
    module = _module()

    class HostileResult(dict):
        touched = False

        def items(self):
            type(self).touched = True
            raise AssertionError("hostile result mapping protocol invoked")

    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("hostile-r6-result-child")
    transition = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    _seal_mutation_evidence(transition)
    transition["accepted_r6_result"] = HostileResult(transition["accepted_r6_result"])
    HostileResult.touched = False

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=transition,
            parent_reference=parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) == "R6_RESULT_INVALID"
    assert HostileResult.touched is False