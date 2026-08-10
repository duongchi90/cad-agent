"""Neutral immutable drawing-artifact custody and currentness records."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib

from cad_agent.drawing_contracts import canonical_json_sha256


DRAWING_ARTIFACT_REFERENCE_SCHEMA_VERSION = "drawing-artifact-reference-1.0"
DRAWING_ARTIFACT_CURRENT_OBSERVATION_SCHEMA_VERSION = "drawing-artifact-current-observation-1.0"
class DrawingArtifactReferenceError(ValueError):
    """A categorical refusal from the drawing-artifact reference boundary."""


def _fail(code: str) -> None:
    raise DrawingArtifactReferenceError(code)


def _sha256_bytes(value: object) -> str:
    if not isinstance(value, bytes):
        _fail("INVALID_REFERENCE")
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_integrity_sha256(
    payload: Mapping[str, object],
    code: str,
) -> str:
    try:
        return canonical_json_sha256(payload)
    except DrawingArtifactReferenceError:
        raise
    except (TypeError, ValueError):
        _fail(code)


def _verify_canonical_integrity_sha256(
    payload: Mapping[str, object],
    integrity_sha256: object,
    code: str,
) -> None:
    if not _is_sha256(integrity_sha256):
        _fail(code)
    expected = _canonical_integrity_sha256(payload, code)
    if expected != integrity_sha256:
        _fail(code)


def _require_scope(record: Mapping[str, object]) -> None:
    for field in ("run_id", "project_id", "drawing_id"):
        if not isinstance(record.get(field), str) or not record[field]:
            _fail("INVALID_REFERENCE")


def _reference_hash_payload(record: Mapping[str, object]) -> dict[str, object]:
    payload = dict(record)
    payload.pop("reference_sha256", None)
    return payload


def _observation_hash_payload(record: Mapping[str, object]) -> dict[str, object]:
    payload = dict(record)
    payload.pop("lookup_sha256", None)
    return payload


def _reference_identity_payload(record: Mapping[str, object]) -> dict[str, object]:
    payload = _reference_hash_payload(record)
    payload.pop("reference_id", None)
    return payload


def _issue_reference_identity(
    record: Mapping[str, object],
) -> str:
    return "dara-ref-" + _canonical_integrity_sha256(
        _reference_identity_payload(record), "INVALID_REFERENCE"
    )


def _verify_reference_identity(
    record: Mapping[str, object],
) -> None:
    reference_id = record.get("reference_id")
    if not isinstance(reference_id, str) or not reference_id.startswith("dara-ref-"):
        _fail("INVALID_REFERENCE")
    _verify_canonical_integrity_sha256(
        _reference_identity_payload(record),
        reference_id.removeprefix("dara-ref-"),
        "CANONICAL_HASH_MISMATCH",
    )


def _observation_identity_payload(record: Mapping[str, object]) -> dict[str, object]:
    payload = _observation_hash_payload(record)
    payload.pop("lookup_id", None)
    return payload


def _issue_observation_identity(
    record: Mapping[str, object],
) -> str:
    return "dara-lookup-" + _canonical_integrity_sha256(
        _observation_identity_payload(record), "CURRENT_LOOKUP_INVALID"
    )


def _verify_observation_identity(
    record: Mapping[str, object],
) -> None:
    lookup_id = record.get("lookup_id")
    if not isinstance(lookup_id, str) or not lookup_id.startswith("dara-lookup-"):
        _fail("CURRENT_LOOKUP_INVALID")
    _verify_canonical_integrity_sha256(
        _observation_identity_payload(record),
        lookup_id.removeprefix("dara-lookup-"),
        "CURRENTNESS_FORGED",
    )


def _require_exact_keys(record: Mapping[str, object], keys: tuple[str, ...], code: str) -> None:
    if set(record) != set(keys):
        _fail(code)


def _require_sha_field(record: Mapping[str, object], field: str, code: str) -> None:
    if not _is_sha256(record.get(field)):
        _fail(code)


def _validate_binding(binding: object) -> dict[str, object]:
    if not isinstance(binding, Mapping):
        _fail("CUSTODY_EVIDENCE_MISSING")
    _require_exact_keys(
        binding,
        ("registry_snapshot_sha256", "provenance_sha256"),
        "CUSTODY_EVIDENCE_MISMATCH",
    )
    _require_sha_field(binding, "registry_snapshot_sha256", "CUSTODY_EVIDENCE_MISMATCH")
    _require_sha_field(binding, "provenance_sha256", "CUSTODY_EVIDENCE_MISMATCH")
    return deepcopy(dict(binding))


def _validate_initial_evidence(evidence: object, artifact_role: str) -> dict[str, object]:
    if not isinstance(evidence, Mapping):
        _fail("CUSTODY_EVIDENCE_MISSING")
    required_kind = "BASELINE_CUSTODY" if artifact_role == "BASELINE" else "R3_CANDIDATE_CUSTODY"
    _require_exact_keys(
        evidence,
        ("evidence_kind", "evidence_id", "evidence_sha256"),
        "CUSTODY_EVIDENCE_MISSING",
    )
    if evidence.get("evidence_kind") != required_kind:
        _fail("CATEGORY_CONFUSION")
    if not isinstance(evidence.get("evidence_id"), str) or not evidence["evidence_id"]:
        _fail("CUSTODY_EVIDENCE_MISSING")
    _require_sha_field(evidence, "evidence_sha256", "CUSTODY_EVIDENCE_MISSING")
    return deepcopy(dict(evidence))


def _validate_transition_evidence(
    evidence: object,
    *,
    parent_reference_id: str,
    parent_reference_sha256: str,
    artifact_sha256: str,
    parent_artifact_sha256: str | None = None,
    accepted_transition_evidence_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(evidence, Mapping):
        _fail("MUTATION_EVIDENCE_MISSING")
    required_fields = (
        "evidence_kind",
        "r3_candidate_reference_id",
        "r3_candidate_reference_sha256",
        "r5_failure_id",
        "r5_failure_sha256",
        "r4_transition_id",
        "r4_transition_sha256",
        "r6_mutation_request_id",
        "r6_mutation_request_sha256",
        "r6_result_id",
        "r6_result_sha256",
        "executor_result_id",
        "executor_result_sha256",
        "pre_artifact_sha256",
        "post_artifact_sha256",
        "protected_constraints_sha256",
        "workspace_evidence_sha256",
        "mutation_terminal",
        "partial_mutation",
        "timed_out",
        "rollback_failed",
        "cleanup_state",
        "accepted_transition_evidence_sha256",
    )
    if not set(required_fields).issubset(evidence):
        _fail("MUTATION_EVIDENCE_MISSING")
    if set(evidence) != set(required_fields):
        _fail("MUTATION_EVIDENCE_MISMATCH")
    if evidence.get("evidence_kind") != "POST_REPAIR_TRANSITION":
        _fail("MUTATION_EVIDENCE_MISMATCH")
    accepted = evidence.get("accepted_transition_evidence_sha256")
    if not _is_sha256(accepted):
        _fail("MUTATION_EVIDENCE_MISSING")
    if accepted_transition_evidence_sha256 is not None:
        if not _is_sha256(accepted_transition_evidence_sha256):
            _fail("MUTATION_EVIDENCE_MISSING")
        if accepted != accepted_transition_evidence_sha256:
            _fail("MUTATION_EVIDENCE_MISMATCH")
    sealed = dict(evidence)
    sealed.pop("accepted_transition_evidence_sha256")
    _verify_canonical_integrity_sha256(sealed, accepted, "MUTATION_EVIDENCE_MISMATCH")
    if evidence.get("r3_candidate_reference_id") != parent_reference_id:
        _fail("WRONG_CANDIDATE")
    if evidence.get("r3_candidate_reference_sha256") != parent_reference_sha256:
        _fail("WRONG_CANDIDATE")
    for field in (
        "r5_failure_id",
        "r4_transition_id",
        "r6_mutation_request_id",
        "r6_result_id",
        "executor_result_id",
    ):
        if not isinstance(evidence.get(field), str) or not evidence[field]:
            _fail("MUTATION_EVIDENCE_MISSING")
    for field in (
        "r5_failure_sha256",
        "r4_transition_sha256",
        "r6_mutation_request_sha256",
        "r6_result_sha256",
        "executor_result_sha256",
        "pre_artifact_sha256",
        "post_artifact_sha256",
        "protected_constraints_sha256",
        "workspace_evidence_sha256",
    ):
        _require_sha_field(evidence, field, "MUTATION_EVIDENCE_MISSING")
    if (
        parent_artifact_sha256 is not None
        and evidence["pre_artifact_sha256"] != parent_artifact_sha256
    ):
        _fail("MUTATION_EVIDENCE_MISMATCH")
    if evidence["post_artifact_sha256"] != artifact_sha256:
        _fail("POST_ARTIFACT_MISMATCH")
    if evidence.get("mutation_terminal") != "SUCCESS":
        _fail("MUTATION_NOT_SUCCESSFUL")
    if any(
        evidence.get(field) is not False
        for field in ("partial_mutation", "timed_out", "rollback_failed")
    ):
        _fail("MUTATION_NOT_SUCCESSFUL")
    if evidence.get("cleanup_state") != "VERIFIED":
        _fail("CLEANUP_UNCERTAIN")
    return deepcopy(dict(evidence))


def _issue_transition_evidence(
    evidence: object,
    *,
    parent_reference_id: str,
    parent_reference_sha256: str,
    artifact_sha256: str,
    parent_artifact_sha256: str,
) -> dict[str, object]:
    if not isinstance(evidence, Mapping):
        _fail("MUTATION_EVIDENCE_MISSING")
    issued = deepcopy(dict(evidence))
    accepted = issued.pop("accepted_transition_evidence_sha256", None)
    if accepted is None:
        _fail("MUTATION_EVIDENCE_MISSING")
    issued["accepted_transition_evidence_sha256"] = accepted
    return _validate_transition_evidence(
        issued,
        parent_reference_id=parent_reference_id,
        parent_reference_sha256=parent_reference_sha256,
        artifact_sha256=artifact_sha256,
        parent_artifact_sha256=parent_artifact_sha256,
        accepted_transition_evidence_sha256=issued["accepted_transition_evidence_sha256"],
    )


def drawing_artifact_reference_sha256(reference: Mapping[str, object]) -> str:
    if not isinstance(reference, Mapping):
        _fail("INVALID_REFERENCE")
    try:
        return canonical_json_sha256(_reference_hash_payload(reference))
    except (TypeError, ValueError):
        _fail("INVALID_REFERENCE")


def validate_drawing_artifact_reference(
    reference: Mapping[str, object],
    expected_artifact_role: str | None = None,
    *,
    parent_reference: Mapping[str, object] | None = None,
    accepted_transition_evidence_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(reference, Mapping):
        _fail("INVALID_REFERENCE")
    fields = (
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
    )
    _require_exact_keys(reference, fields, "INVALID_REFERENCE")
    if reference.get("schema_version") != DRAWING_ARTIFACT_REFERENCE_SCHEMA_VERSION:
        _fail("INVALID_REFERENCE")
    _require_scope(reference)
    artifact_role = reference.get("artifact_role")
    if not isinstance(artifact_role, str) or artifact_role not in {
        "BASELINE",
        "R3_CANDIDATE",
    }:
        _fail("CATEGORY_CONFUSION")
    if expected_artifact_role is not None and artifact_role != expected_artifact_role:
        _fail("CATEGORY_CONFUSION")
    if not _is_sha256(reference.get("artifact_sha256")):
        _fail("INVALID_REFERENCE")
    if not isinstance(reference.get("reference_id"), str) or not reference["reference_id"]:
        _fail("INVALID_REFERENCE")
    _require_sha_field(reference, "reference_sha256", "INVALID_REFERENCE")
    try:
        if drawing_artifact_reference_sha256(reference) != reference["reference_sha256"]:
            _fail("CANONICAL_HASH_MISMATCH")
        _verify_reference_identity(reference)
    except DrawingArtifactReferenceError:
        raise
    except (TypeError, ValueError):
        _fail("INVALID_REFERENCE")
    parent_id = reference.get("parent_reference_id")
    parent_sha = reference.get("parent_reference_sha256")
    if (parent_id is None) != (parent_sha is None):
        _fail("PARENT_MISMATCH")
    if parent_id is not None or parent_sha is not None:
        if (
            artifact_role != "R3_CANDIDATE"
            or not isinstance(parent_id, str)
            or not _is_sha256(parent_sha)
        ):
            _fail("PARENT_MISMATCH")
    if artifact_role == "BASELINE":
        if parent_reference is not None or accepted_transition_evidence_sha256 is not None:
            _fail("PARENT_MISMATCH")
        if reference.get("r3_provenance_binding") is not None:
            _fail("CATEGORY_CONFUSION")
        _validate_initial_evidence(reference["upstream_evidence"], artifact_role)
    else:
        _validate_binding(reference.get("r3_provenance_binding"))
        if parent_id is None:
            if parent_reference is not None or accepted_transition_evidence_sha256 is not None:
                _fail("PARENT_MISMATCH")
            _validate_initial_evidence(reference["upstream_evidence"], artifact_role)
        else:
            if parent_reference is None:
                _fail("PARENT_MISMATCH")
            if accepted_transition_evidence_sha256 is None:
                _fail("MUTATION_EVIDENCE_MISSING")
            parent = _validated_parent(parent_reference)
            if parent["artifact_role"] != "R3_CANDIDATE":
                _fail("CATEGORY_CONFUSION")
            if parent["reference_id"] != parent_id or parent["reference_sha256"] != parent_sha:
                _fail("PARENT_MISMATCH")
            if any(
                reference[field] != parent[field]
                for field in ("run_id", "project_id", "drawing_id")
            ):
                _fail("SCOPE_MISMATCH")
            _validate_transition_evidence(
                reference["upstream_evidence"],
                parent_reference_id=parent["reference_id"],
                parent_reference_sha256=parent["reference_sha256"],
                artifact_sha256=reference["artifact_sha256"],
                parent_artifact_sha256=parent["artifact_sha256"],
                accepted_transition_evidence_sha256=(accepted_transition_evidence_sha256),
            )
    return deepcopy(dict(reference))


def _validated_parent(
    parent_reference: object,
) -> dict[str, object]:
    if not isinstance(parent_reference, Mapping):
        _fail("PARENT_MISMATCH")
    try:
        return validate_drawing_artifact_reference(
            parent_reference,
        )
    except DrawingArtifactReferenceError as error:
        if str(error) == "CANONICAL_HASH_MISMATCH" and _is_sha256(
            parent_reference.get("reference_sha256")
        ):
            try:
                _verify_reference_identity(
                    parent_reference,
                )
            except DrawingArtifactReferenceError:
                _fail("HISTORICAL_MUTATION")
            except (TypeError, ValueError):
                pass
        raise


def issue_drawing_artifact_reference(
    *,
    run_id: str,
    project_id: str,
    drawing_id: str,
    artifact_role: str,
    artifact_bytes: bytes,
    upstream_evidence: Mapping[str, object],
    parent_reference: Mapping[str, object] | None = None,
    r3_provenance_binding: Mapping[str, object] | None = None,
    claimed_artifact_sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(artifact_role, str) or artifact_role not in {
        "BASELINE",
        "R3_CANDIDATE",
    }:
        _fail("CATEGORY_CONFUSION")
    artifact_sha256 = _sha256_bytes(artifact_bytes)
    if claimed_artifact_sha256 is not None and claimed_artifact_sha256 != artifact_sha256:
        _fail("ARTIFACT_SHA_MISMATCH")
    scope = {"run_id": run_id, "project_id": project_id, "drawing_id": drawing_id}
    _require_scope(scope)
    if parent_reference is None:
        if artifact_role == "BASELINE":
            if r3_provenance_binding is not None:
                _fail("CATEGORY_CONFUSION")
            evidence = _validate_initial_evidence(upstream_evidence, artifact_role)
            binding: dict[str, object] | None = None
        else:
            evidence = _validate_initial_evidence(upstream_evidence, artifact_role)
            binding = _validate_binding(r3_provenance_binding)
        parent_id: str | None = None
        parent_sha: str | None = None
    else:
        if artifact_role != "R3_CANDIDATE":
            _fail("CATEGORY_CONFUSION")
        parent = _validated_parent(parent_reference)
        if parent["artifact_role"] != "R3_CANDIDATE":
            _fail("CATEGORY_CONFUSION")
        if any(scope[field] != parent[field] for field in scope):
            _fail("SCOPE_MISMATCH")
        binding = _validate_binding(r3_provenance_binding)
        evidence = _issue_transition_evidence(
            upstream_evidence,
            parent_reference_id=parent["reference_id"],
            parent_reference_sha256=parent["reference_sha256"],
            artifact_sha256=artifact_sha256,
            parent_artifact_sha256=parent["artifact_sha256"],
        )
        parent_id = parent["reference_id"]
        parent_sha = parent["reference_sha256"]
    record: dict[str, object] = {
        "schema_version": DRAWING_ARTIFACT_REFERENCE_SCHEMA_VERSION,
        "reference_id": "",
        "run_id": run_id,
        "project_id": project_id,
        "drawing_id": drawing_id,
        "artifact_role": artifact_role,
        "artifact_sha256": artifact_sha256,
        "reference_sha256": "",
        "upstream_evidence": evidence,
        "parent_reference_id": parent_id,
        "parent_reference_sha256": parent_sha,
        "r3_provenance_binding": binding,
    }
    record["reference_id"] = _issue_reference_identity(record)
    record["reference_sha256"] = drawing_artifact_reference_sha256(record)
    if parent_reference is None:
        return validate_drawing_artifact_reference(
            record,
        )
    return validate_drawing_artifact_reference(
        record,
        parent_reference=parent,
        accepted_transition_evidence_sha256=evidence["accepted_transition_evidence_sha256"],
    )


def drawing_artifact_current_observation_sha256(observation: Mapping[str, object]) -> str:
    if not isinstance(observation, Mapping):
        _fail("CURRENT_LOOKUP_INVALID")
    try:
        return canonical_json_sha256(_observation_hash_payload(observation))
    except (TypeError, ValueError):
        _fail("CURRENT_LOOKUP_INVALID")


def validate_drawing_artifact_current_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(observation, Mapping):
        _fail("CURRENT_LOOKUP_INVALID")
    fields = (
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
    )
    _require_exact_keys(observation, fields, "CURRENT_LOOKUP_INVALID")
    if observation.get("schema_version") != DRAWING_ARTIFACT_CURRENT_OBSERVATION_SCHEMA_VERSION:
        _fail("CURRENT_LOOKUP_INVALID")
    _require_scope(observation)
    if not isinstance(observation.get("lookup_id"), str) or not observation["lookup_id"]:
        _fail("CURRENT_LOOKUP_INVALID")
    for field in (
        "lookup_sha256",
        "reference_sha256",
        "expected_artifact_sha256",
        "observed_artifact_sha256",
        "observation_evidence_sha256",
    ):
        _require_sha_field(observation, field, "CURRENT_LOOKUP_INVALID")
    if not isinstance(observation.get("reference_id"), str) or not observation["reference_id"]:
        _fail("CURRENT_LOOKUP_INVALID")
    try:
        if drawing_artifact_current_observation_sha256(observation) != observation["lookup_sha256"]:
            _fail("CANONICAL_HASH_MISMATCH")
        _verify_observation_identity(observation)
    except DrawingArtifactReferenceError:
        raise
    except (TypeError, ValueError):
        _fail("CURRENT_LOOKUP_INVALID")
    comparison = observation.get("comparison")
    if not isinstance(comparison, str) or comparison not in {"CURRENT", "STALE"}:
        _fail("CURRENTNESS_FORGED")
    expected = observation["expected_artifact_sha256"]
    observed = observation["observed_artifact_sha256"]
    if (comparison == "CURRENT") != (expected == observed):
        _fail("CURRENTNESS_FORGED")
    return deepcopy(dict(observation))


def observe_drawing_artifact_currentness(
    *,
    reference: Mapping[str, object],
    artifact_bytes: bytes,
    observation_evidence_sha256: str,
    parent_reference: Mapping[str, object] | None = None,
    accepted_transition_evidence_sha256: str | None = None,
    claimed_artifact_sha256: str | None = None,
    claimed_comparison: str | None = None,
) -> dict[str, object]:
    sealed_reference = validate_drawing_artifact_reference(
        reference,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
    )
    observed_artifact_sha256 = _sha256_bytes(artifact_bytes)
    if claimed_artifact_sha256 is not None and claimed_artifact_sha256 != observed_artifact_sha256:
        _fail("ARTIFACT_SHA_MISMATCH")
    comparison = (
        "CURRENT" if observed_artifact_sha256 == sealed_reference["artifact_sha256"] else "STALE"
    )
    if claimed_comparison is not None and claimed_comparison != comparison:
        _fail("CURRENTNESS_FORGED")
    if not _is_sha256(observation_evidence_sha256):
        _fail("CURRENT_LOOKUP_INVALID")
    observation: dict[str, object] = {
        "schema_version": DRAWING_ARTIFACT_CURRENT_OBSERVATION_SCHEMA_VERSION,
        "lookup_id": "",
        "lookup_sha256": "",
        "run_id": sealed_reference["run_id"],
        "project_id": sealed_reference["project_id"],
        "drawing_id": sealed_reference["drawing_id"],
        "reference_id": sealed_reference["reference_id"],
        "reference_sha256": sealed_reference["reference_sha256"],
        "expected_artifact_sha256": sealed_reference["artifact_sha256"],
        "observed_artifact_sha256": observed_artifact_sha256,
        "comparison": comparison,
        "observation_evidence_sha256": observation_evidence_sha256,
    }
    observation["lookup_id"] = _issue_observation_identity(observation)
    observation["lookup_sha256"] = drawing_artifact_current_observation_sha256(observation)
    return validate_drawing_artifact_current_observation(
        observation,
    )


def require_current_drawing_artifact_reference(
    *,
    reference: Mapping[str, object],
    observation: Mapping[str, object],
    artifact_bytes: bytes,
    parent_reference: Mapping[str, object] | None = None,
    accepted_transition_evidence_sha256: str | None = None,
) -> None:
    sealed_reference = validate_drawing_artifact_reference(
        reference,
        parent_reference=parent_reference,
        accepted_transition_evidence_sha256=accepted_transition_evidence_sha256,
    )
    sealed_observation = validate_drawing_artifact_current_observation(
        observation,
    )
    for field in ("run_id", "project_id", "drawing_id"):
        if sealed_observation[field] != sealed_reference[field]:
            _fail("SCOPE_MISMATCH")
    if (
        sealed_observation["reference_id"] != sealed_reference["reference_id"]
        or sealed_observation["reference_sha256"] != sealed_reference["reference_sha256"]
    ):
        _fail("FOREIGN_REFERENCE")
    if sealed_observation["expected_artifact_sha256"] != sealed_reference["artifact_sha256"]:
        _fail("REPLAY_MISMATCH")
    freshly_observed_artifact_sha256 = _sha256_bytes(artifact_bytes)
    if (
        sealed_observation["comparison"] != "CURRENT"
        or freshly_observed_artifact_sha256 != sealed_reference["artifact_sha256"]
    ):
        _fail("STALE_REFERENCE")
