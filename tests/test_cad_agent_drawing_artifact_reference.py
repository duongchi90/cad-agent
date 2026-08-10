from __future__ import annotations

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
    evidence["accepted_transition_evidence_sha256"] = canonical_json_sha256(evidence)
    return evidence


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
    parent = _issue_r3_candidate()
    child_bytes = _artifact_bytes("repaired")
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_bytes).hexdigest(),
    )
    return parent, child_bytes, mutation


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


def test_dara_public_surface_is_closed_and_versioned() -> None:
    module = _module()
    assert module.DRAWING_ARTIFACT_REFERENCE_SCHEMA_VERSION == (
        "drawing-artifact-reference-1.0"
    )
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
    assert module.validate_drawing_artifact_reference(first) == first
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
    assert module.validate_drawing_artifact_reference(child) == child


def test_post_repair_transition_rejects_baseline_as_r3_candidate_parent() -> None:
    module = _module()
    parent = _issue_baseline()
    child_bytes = _artifact_bytes("repaired")
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
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_baseline_consumption_rejects_an_r3_candidate_reference() -> None:
    module = _module()
    candidate = _issue_r3_candidate()

    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.validate_drawing_artifact_reference(
            candidate, expected_artifact_role="BASELINE"
        )
    assert str(exc.value) == "CATEGORY_CONFUSION"


def test_post_repair_transition_rejects_wrong_r3_candidate_identity() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation["r3_candidate_reference_id"] = "r3-candidate-foreign"

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


def test_post_repair_child_requires_exact_parent_scope_and_hash() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    wrong_parent = module.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id="project-foreign",
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=_artifact_bytes("r3-candidate-foreign"),
        upstream_evidence=_r3_candidate_evidence(),
        r3_provenance_binding=_r3_binding(),
    )
    with pytest.raises(module.DrawingArtifactReferenceError) as exc:
        module.issue_drawing_artifact_reference(
            run_id=parent["run_id"],
            project_id=parent["project_id"],
            drawing_id=parent["drawing_id"],
            artifact_role="R3_CANDIDATE",
            artifact_bytes=child_bytes,
            upstream_evidence=mutation,
            parent_reference=wrong_parent,
            r3_provenance_binding=_r3_binding(),
        )
    assert str(exc.value) in {"SCOPE_MISMATCH", "PARENT_MISMATCH", "WRONG_CANDIDATE"}


def test_post_repair_child_rejects_forged_post_sha_even_when_r6_result_sha_exists() -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation = _mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256="d" * 64,
    )
    assert mutation["r6_result_sha256"] == "5" * 64
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
        "r5_failure_id",
        "r4_transition_id",
        "r6_mutation_request_id",
        "r6_result_id",
        "executor_result_id",
        "pre_artifact_sha256",
        "post_artifact_sha256",
        "protected_constraints_sha256",
        "workspace_evidence_sha256",
    ],
)
def test_post_repair_child_rejects_each_missing_required_evidence_binding(
    field: str,
) -> None:
    module = _module()
    parent, child_bytes, mutation = _post_repair_material()
    mutation.pop(field)

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


@pytest.mark.parametrize(
    ("field", "replacement", "expected_code"),
    [
        ("r5_failure_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("r4_transition_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("r6_mutation_request_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("r6_result_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("executor_result_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("pre_artifact_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("post_artifact_sha256", "f" * 64, "POST_ARTIFACT_MISMATCH"),
        ("protected_constraints_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("workspace_evidence_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
    ],
)
def test_post_repair_child_rejects_each_mismatched_evidence_binding(
    field: str,
    replacement: str,
    expected_code: str,
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
    assert str(exc.value) == expected_code


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
    assert (
        module.drawing_artifact_current_observation_sha256(first)
        == first["lookup_sha256"]
    )
    assert module.validate_drawing_artifact_current_observation(first) == first
    module.require_current_drawing_artifact_reference(
        reference=reference, observation=first
    )


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
            reference=reference, observation=observation
        )
    assert str(exc.value) == "STALE_REFERENCE"


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
            reference=reference, observation=replay
        )


def test_r6_result_sha_is_evidence_only_and_cannot_mint_dara_currentness() -> None:
    module = _module()
    parent, child, _ = _issue_candidate()
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
            reference=child, observation=forged
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
    assert "hashlib" in source  # artifact-byte SHA only; canonical JSON remains delegated.
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


def test_public_surface_has_no_second_currentness_authority_or_in_memory_store() -> None:
    module = _module()
    public_names = {name for name in vars(module) if not name.startswith("_")}
    lowered_names = {name.lower() for name in public_names}

    assert not {
        "currentness_authority",
        "drawing_artifact_current_store",
        "drawing_artifact_candidate_store",
        "candidate_store",
        "current_store",
        "register_current_reference",
        "set_current_reference",
    } & lowered_names
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
