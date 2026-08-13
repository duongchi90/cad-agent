"""Thin offline R7 composition over accepted publication owners.

This module composes existing R4, R5, authorization, manifest-lifecycle and
safe-file owners. It does not own revision selection, visual verdicts,
approval, persistence, file policy, CAD transport, or publication targets.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from pathlib import Path

from cad_agent.candidate_revision import validate_candidate_revision_state
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.manifest import sha256_file as manifest_sha256_file
from cad_agent.manifest import transition_publication_lifecycle
from cad_agent.visual_contracts import require_auto_publish_authorized, validate_visual_contract
from cad_agent.visual_evidence import (
    PublicationFileError,
    cleanup_publication_replacement,
    commit_publication_replacement,
    prepare_publication_replacement,
    restore_publication_target,
    snapshot_publication_file,
)
from cad_agent.visual_supervisor_adapter import validate_visual_verdict_result


R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION = "r7-verified-publication-result-1.0"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_RESULT_FIELDS = {
    "schema_version",
    "publication_id",
    "publication_sha256",
    "run_id",
    "authorization_id",
    "authorization_sha256",
    "candidate_revision_sha256",
    "candidate_state_sha256",
    "r5_verdict_sha256",
    "latest_mutation_sha256",
    "publishable_artifact_sha256",
    "target_snapshot_sha256",
    "published_artifact_sha256",
    "publication_state",
}


class VerifiedPublisherError(ValueError):
    """Categorical refusal at the R7 composition boundary."""


def _fail(code: str) -> None:
    raise VerifiedPublisherError(code)


def _identifier(value: object, *, code: str = "R7_INPUT_INVALID") -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(code)
    return value


def _sha(value: object, *, code: str = "R7_INPUT_INVALID") -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(code)
    return value


def _mapping(value: object, *, code: str = "R7_INPUT_INVALID") -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(code)
    return value


def _current_candidate(
    candidate_state: object,
    *,
    run_id: str,
) -> tuple[dict[str, object], dict[str, object], str, str, str, str]:
    try:
        state = validate_candidate_revision_state(candidate_state)
    except Exception as error:
        raise VerifiedPublisherError("R7_R4_CURRENT_INVALID") from error
    selected_sha = _sha(
        state.get("current_candidate_revision_sha256"), code="R7_R4_CURRENT_INVALID"
    )
    records = state.get("candidate_revisions")
    if type(records) is not list:
        _fail("R7_R4_CURRENT_INVALID")
    selected = next(
        (
            record
            for record in records
            if type(record) is dict
            and record.get("candidate_revision_sha256") == selected_sha
        ),
        None,
    )
    if type(selected) is not dict or selected.get("run_id") != run_id:
        _fail("R7_R4_CURRENT_INVALID")
    artifacts = _mapping(selected.get("candidate_artifacts"), code="R7_R4_CURRENT_INVALID")
    mutation = _mapping(selected.get("mutation_evidence"), code="R7_R4_CURRENT_INVALID")
    artifact_sha = _sha(artifacts.get("artifact_sha256"), code="R7_R4_CURRENT_INVALID")
    latest_mutation_sha = _sha(
        mutation.get("latest_mutation_evidence_sha256"), code="R7_R4_CURRENT_INVALID"
    )
    state_sha = _sha(state.get("state_sha256"), code="R7_R4_CURRENT_INVALID")
    return (
        state,
        copy.deepcopy(selected),
        selected_sha,
        state_sha,
        artifact_sha,
        latest_mutation_sha,
    )


def _fresh_r5(
    result: object,
    *,
    candidate_sha: str,
    state_sha: str,
    latest_mutation_sha: str,
) -> dict[str, object]:
    try:
        validated = validate_visual_verdict_result(
            result,
            expected_candidate_revision_sha256=candidate_sha,
            expected_candidate_state_sha256=state_sha,
            expected_latest_mutation_sha256=latest_mutation_sha,
        )
    except Exception as error:
        raise VerifiedPublisherError("R7_R5_VERDICT_INVALID") from error
    if validated.get("verdict") != "PASS":
        _fail("R7_R5_PASS_REQUIRED")
    return validated


def _target_identity(snapshot: Mapping[str, object]) -> str:
    stable = {
        "schema_version": snapshot.get("schema_version"),
        "sha256": snapshot.get("sha256"),
        "size_bytes": snapshot.get("size_bytes"),
        "device_id": snapshot.get("device_id"),
        "file_id": snapshot.get("file_id"),
    }
    try:
        return canonical_json_sha256(stable)
    except Exception as error:
        raise VerifiedPublisherError("R7_TARGET_INVALID") from error


def _authorization_identity(authorization: Mapping[str, object]) -> str:
    stable_fields = (
        "schema_version",
        "authorization_id",
        "run_id",
        "policy",
        "expected_initial_sha256",
        "single_use",
        "expires_after_run",
        "consumed",
        "authorized_by",
        "approval_reference",
        "status",
    )
    stable = {field: authorization[field] for field in stable_fields}
    try:
        return canonical_json_sha256(stable)
    except Exception as error:
        raise VerifiedPublisherError("R7_AUTHORIZATION_INVALID") from error


def _manifest_sha(path: Path) -> str:
    try:
        return _sha(manifest_sha256_file(path), code="R7_MANIFEST_INVALID")
    except VerifiedPublisherError:
        raise
    except Exception as error:
        raise VerifiedPublisherError("R7_MANIFEST_INVALID") from error


def _publication_result_record(
    *,
    publication_id: str,
    published_sha: str,
    target_snapshot_sha: str,
    outcome: str,
) -> dict[str, object]:
    material = {
        "publication_id": publication_id,
        "published_artifact_sha256": published_sha,
        "target_snapshot_sha256": target_snapshot_sha,
        "publication_outcome": outcome,
    }
    return {
        "result_sha256": canonical_json_sha256(material),
        "published_artifact_sha256": published_sha,
        "target_snapshot_sha256": target_snapshot_sha,
        "publication_outcome": outcome,
    }


def _recovery_record(
    *,
    publication_id: str,
    target_snapshot_sha: str,
    restored_sha: str,
    outcome: str,
) -> dict[str, object]:
    material = {
        "publication_id": publication_id,
        "target_snapshot_sha256": target_snapshot_sha,
        "restored_artifact_sha256": restored_sha,
        "recovery_outcome": outcome,
    }
    return {
        "recovery_sha256": canonical_json_sha256(material),
        "target_snapshot_sha256": target_snapshot_sha,
        "restored_artifact_sha256": restored_sha,
        "recovery_outcome": outcome,
    }


def _transition(
    manifest_path: Path,
    *,
    expected_manifest_sha: str,
    action: str,
    publication_id: str,
    authorization_id: str,
    authorization_sha: str,
    intent: Mapping[str, object],
    result: Mapping[str, object] | None = None,
    recovery: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        return transition_publication_lifecycle(
            manifest_path,
            expected_manifest_sha256=expected_manifest_sha,
            action=action,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha256=authorization_sha,
            intent=intent,
            result=result,
            recovery=recovery,
        )
    except Exception as error:
        raise VerifiedPublisherError("R7_LIFECYCLE_INVALID") from error


def _record_failed(
    manifest_path: Path,
    *,
    publication_id: str,
    authorization_id: str,
    authorization_sha: str,
    intent: Mapping[str, object],
    artifact_sha: str,
    target_snapshot_sha: str,
) -> None:
    result = _publication_result_record(
        publication_id=publication_id,
        published_sha=artifact_sha,
        target_snapshot_sha=target_snapshot_sha,
        outcome="FAILED",
    )
    _transition(
        manifest_path,
        expected_manifest_sha=_manifest_sha(manifest_path),
        action="RECORD_FAILED",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha=authorization_sha,
        intent=intent,
        result=result,
    )


def _recover_after_replace(
    manifest_path: Path,
    prepared: Mapping[str, object],
    *,
    publication_id: str,
    authorization_id: str,
    authorization_sha: str,
    intent: Mapping[str, object],
    artifact_sha: str,
    original_target_sha: str,
    target_snapshot_sha: str,
) -> None:
    required = _recovery_record(
        publication_id=publication_id,
        target_snapshot_sha=target_snapshot_sha,
        restored_sha=original_target_sha,
        outcome="RECOVERY_REQUIRED",
    )
    _transition(
        manifest_path,
        expected_manifest_sha=_manifest_sha(manifest_path),
        action="REQUIRE_RECOVERY",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha=authorization_sha,
        intent=intent,
        recovery=required,
    )
    try:
        restored = restore_publication_target(
            prepared,
            expected_current_sha256=artifact_sha,
        )
        restored_sha = _sha(restored.get("restored_sha256"), code="R7_RECOVERY_REQUIRED")
    except Exception as error:
        raise VerifiedPublisherError("R7_RECOVERY_REQUIRED") from error
    rollback = _recovery_record(
        publication_id=publication_id,
        target_snapshot_sha=target_snapshot_sha,
        restored_sha=restored_sha,
        outcome="ROLLED_BACK",
    )
    _transition(
        manifest_path,
        expected_manifest_sha=_manifest_sha(manifest_path),
        action="RECORD_ROLLBACK",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha=authorization_sha,
        intent=intent,
        recovery=rollback,
    )
    try:
        cleanup_publication_replacement(prepared)
    except Exception as error:
        raise VerifiedPublisherError("R7_CLEANUP_FAILED") from error


def execute_verified_publication(
    *,
    run_id: object,
    candidate_state: object,
    r5_verdict_result: object,
    auto_publish_authorization: object,
    manifest_path: object,
    expected_manifest_sha256: object,
    candidate_path: object,
    target_path: object,
) -> dict[str, object]:
    """Validate accepted owners, publish once, and return bounded R7 evidence."""

    run = _identifier(run_id)
    expected_manifest_sha = _sha(expected_manifest_sha256)
    if not all(isinstance(path, Path) for path in (manifest_path, candidate_path, target_path)):
        _fail("R7_INPUT_INVALID")

    (
        state,
        _selected,
        candidate_sha,
        state_sha,
        artifact_sha,
        latest_mutation_sha,
    ) = _current_candidate(candidate_state, run_id=run)
    r5 = _fresh_r5(
        r5_verdict_result,
        candidate_sha=candidate_sha,
        state_sha=state_sha,
        latest_mutation_sha=latest_mutation_sha,
    )
    r5_sha = _sha(r5.get("verdict_sha256"), code="R7_R5_VERDICT_INVALID")

    try:
        candidate_snapshot = snapshot_publication_file(candidate_path)
        target_snapshot = snapshot_publication_file(target_path)
    except Exception as error:
        raise VerifiedPublisherError("R7_PUBLICATION_FILE_INVALID") from error
    if candidate_snapshot.get("sha256") != artifact_sha:
        _fail("R7_CANDIDATE_ARTIFACT_MISMATCH")
    original_target_sha = _sha(target_snapshot.get("sha256"), code="R7_TARGET_INVALID")
    target_snapshot_sha = _target_identity(target_snapshot)

    try:
        authorization = validate_visual_contract(
            _mapping(auto_publish_authorization, code="R7_AUTHORIZATION_INVALID"),
            contract="auto_publish_authorization",
        )
        require_auto_publish_authorized(
            authorization,
            run_id=run,
            target_path=str(target_path),
            target_sha256=original_target_sha,
        )
    except Exception as error:
        raise VerifiedPublisherError("R7_AUTHORIZATION_INVALID") from error
    authorization_id = _identifier(
        authorization.get("authorization_id"), code="R7_AUTHORIZATION_INVALID"
    )
    authorization_sha = _authorization_identity(authorization)

    intent = {
        "candidate_revision_sha256": candidate_sha,
        "r5_verdict_sha256": r5_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_identity_sha256": target_snapshot_sha,
    }
    identity_material = {
        "run_id": run,
        "authorization_sha256": authorization_sha,
        "candidate_revision_sha256": candidate_sha,
        "candidate_state_sha256": state_sha,
        "r5_verdict_sha256": r5_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_snapshot_sha256": target_snapshot_sha,
    }
    publication_id = "publication:" + canonical_json_sha256(identity_material)

    claim_manifest = _transition(
        manifest_path,
        expected_manifest_sha=expected_manifest_sha,
        action="CLAIM",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha=authorization_sha,
        intent=intent,
    )
    claim_lifecycle = claim_manifest.get("publication_lifecycle")
    if (
        type(claim_lifecycle) is not dict
        or claim_lifecycle.get("authorization_state") != "CLAIMED"
        or claim_lifecycle.get("publication_state") != "INTENT_RECORDED"
        or _manifest_sha(manifest_path) == expected_manifest_sha
    ):
        _fail("R7_CLAIM_REPLAY")

    prepared: Mapping[str, object] | None = None
    try:
        prepared = prepare_publication_replacement(
            target_path=target_path,
            candidate_path=candidate_path,
            expected_target_sha256=original_target_sha,
            expected_candidate_sha256=artifact_sha,
        )

        (
            _state_again,
            _selected_again,
            candidate_sha_again,
            state_sha_again,
            artifact_sha_again,
            latest_mutation_sha_again,
        ) = _current_candidate(candidate_state, run_id=run)
        if (
            candidate_sha_again != candidate_sha
            or state_sha_again != state_sha
            or artifact_sha_again != artifact_sha
            or latest_mutation_sha_again != latest_mutation_sha
        ):
            _fail("R7_R4_CURRENT_INVALID")
        r5_again = _fresh_r5(
            r5_verdict_result,
            candidate_sha=candidate_sha,
            state_sha=state_sha,
            latest_mutation_sha=latest_mutation_sha,
        )
        if r5_again.get("verdict_sha256") != r5_sha:
            _fail("R7_R5_VERDICT_INVALID")

        committed = commit_publication_replacement(
            prepared,
            expected_target_sha256=original_target_sha,
            expected_candidate_sha256=artifact_sha,
        )
    except PublicationFileError as error:
        if prepared is not None and str(error) == "PUBLICATION_VERIFY_FAILED":
            _recover_after_replace(
                manifest_path,
                prepared,
                publication_id=publication_id,
                authorization_id=authorization_id,
                authorization_sha=authorization_sha,
                intent=intent,
                artifact_sha=artifact_sha,
                original_target_sha=original_target_sha,
                target_snapshot_sha=target_snapshot_sha,
            )
            raise VerifiedPublisherError("R7_PUBLICATION_ROLLED_BACK") from error
        _record_failed(
            manifest_path,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        if prepared is not None:
            try:
                cleanup_publication_replacement(prepared)
            except Exception:
                pass
        raise VerifiedPublisherError("R7_PUBLICATION_FAILED") from error
    except VerifiedPublisherError:
        _record_failed(
            manifest_path,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        if prepared is not None:
            try:
                cleanup_publication_replacement(prepared)
            except Exception:
                pass
        raise
    except Exception as error:
        _record_failed(
            manifest_path,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        if prepared is not None:
            try:
                cleanup_publication_replacement(prepared)
            except Exception:
                pass
        raise VerifiedPublisherError("R7_PUBLICATION_FAILED") from error

    published_sha = _sha(committed.get("published_sha256"), code="R7_PUBLICATION_FAILED")
    if published_sha != artifact_sha:
        _recover_after_replace(
            manifest_path,
            prepared,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            original_target_sha=original_target_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        _fail("R7_PUBLICATION_ROLLED_BACK")

    published_record = _publication_result_record(
        publication_id=publication_id,
        published_sha=published_sha,
        target_snapshot_sha=target_snapshot_sha,
        outcome="PUBLISHED",
    )
    try:
        _transition(
            manifest_path,
            expected_manifest_sha=_manifest_sha(manifest_path),
            action="RECORD_PUBLISHED",
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            result=published_record,
        )
    except VerifiedPublisherError as error:
        _recover_after_replace(
            manifest_path,
            prepared,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            original_target_sha=original_target_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        raise VerifiedPublisherError("R7_PUBLICATION_ROLLED_BACK") from error

    try:
        cleanup_publication_replacement(prepared)
    except Exception as error:
        raise VerifiedPublisherError("R7_CLEANUP_FAILED") from error

    try:
        _transition(
            manifest_path,
            expected_manifest_sha=_manifest_sha(manifest_path),
            action="CONSUME",
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
        )
    except VerifiedPublisherError as error:
        _recover_after_replace(
            manifest_path,
            prepared,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha=authorization_sha,
            intent=intent,
            artifact_sha=artifact_sha,
            original_target_sha=original_target_sha,
            target_snapshot_sha=target_snapshot_sha,
        )
        raise VerifiedPublisherError("R7_PUBLICATION_ROLLED_BACK") from error

    result_payload = {
        "schema_version": R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION,
        "publication_id": publication_id,
        "run_id": run,
        "authorization_id": authorization_id,
        "authorization_sha256": authorization_sha,
        "candidate_revision_sha256": candidate_sha,
        "candidate_state_sha256": state_sha,
        "r5_verdict_sha256": r5_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_snapshot_sha256": target_snapshot_sha,
        "published_artifact_sha256": published_sha,
        "publication_state": "PUBLISHED",
    }
    result = {
        **result_payload,
        "publication_sha256": canonical_json_sha256(result_payload),
    }
    return validate_verified_publication_result(
        result,
        expected_candidate_revision_sha256=candidate_sha,
        expected_candidate_state_sha256=state_sha,
        expected_r5_verdict_sha256=r5_sha,
        expected_latest_mutation_sha256=latest_mutation_sha,
    )


def validate_verified_publication_result(
    result: object,
    *,
    expected_candidate_revision_sha256: str | None = None,
    expected_candidate_state_sha256: str | None = None,
    expected_r5_verdict_sha256: str | None = None,
    expected_latest_mutation_sha256: str | None = None,
) -> dict[str, object]:
    """Validate a closed R7 success record without mutating owner state."""

    try:
        if type(result) is not dict or set(result) != _RESULT_FIELDS:
            _fail("R7_RESULT_INVALID")
        if result.get("schema_version") != R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION:
            _fail("R7_RESULT_INVALID")
        publication_id = _identifier(result.get("publication_id"), code="R7_RESULT_INVALID")
        if not publication_id.startswith("publication:"):
            _fail("R7_RESULT_INVALID")
        _identifier(result.get("run_id"), code="R7_RESULT_INVALID")
        _identifier(result.get("authorization_id"), code="R7_RESULT_INVALID")
        for field in (
            "publication_sha256",
            "authorization_sha256",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "r5_verdict_sha256",
            "latest_mutation_sha256",
            "publishable_artifact_sha256",
            "target_snapshot_sha256",
            "published_artifact_sha256",
        ):
            _sha(result.get(field), code="R7_RESULT_INVALID")
        if result.get("publication_state") != "PUBLISHED":
            _fail("R7_RESULT_INVALID")
        if result.get("publishable_artifact_sha256") != result.get("published_artifact_sha256"):
            _fail("R7_RESULT_INVALID")
        payload = copy.deepcopy(result)
        supplied_sha = payload.pop("publication_sha256")
        if canonical_json_sha256(payload) != supplied_sha:
            _fail("R7_RESULT_INVALID")
        payload["publication_sha256"] = supplied_sha
        for expected, field in (
            (expected_candidate_revision_sha256, "candidate_revision_sha256"),
            (expected_candidate_state_sha256, "candidate_state_sha256"),
            (expected_r5_verdict_sha256, "r5_verdict_sha256"),
            (expected_latest_mutation_sha256, "latest_mutation_sha256"),
        ):
            if expected is not None and _sha(expected, code="R7_RESULT_INVALID") != payload[field]:
                _fail("R7_RESULT_INVALID")
        return copy.deepcopy(payload)
    except VerifiedPublisherError:
        raise
    except Exception as error:
        raise VerifiedPublisherError("R7_RESULT_INVALID") from error


__all__ = [
    "R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION",
    "VerifiedPublisherError",
    "execute_verified_publication",
    "validate_verified_publication_result",
]
