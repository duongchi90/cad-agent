"""Thin offline R7 composition over accepted publication owners.

R7 does not own revision selection, visual verdicts, approval, persistence, file
mutation, CAD transport, or publication target policy.  It validates and binds
those accepted owners, sequences their public transitions, and returns only a
closed deterministic publication result.
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
from cad_agent.visual_contracts import (
    require_auto_publish_authorized,
    validate_visual_contract,
)
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
    """Categorical fail-closed refusal at the R7 composition boundary."""


def _fail(code: str) -> None:
    raise VerifiedPublisherError(code)


def _identifier(value: object) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail("R7_INPUT_INVALID")
    return value


def _sha(value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail("R7_INPUT_INVALID")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail("R7_INPUT_INVALID")
    return value


def _selected_candidate(
    candidate_state: object,
    *,
    run_id: str,
) -> tuple[dict[str, object], dict[str, object], str, str, str]:
    try:
        state = validate_candidate_revision_state(candidate_state)
    except Exception as error:
        raise VerifiedPublisherError("R7_R4_CURRENT_INVALID") from error
    selected_sha = state.get("current_candidate_revision_sha256")
    if type(selected_sha) is not str or _SHA256.fullmatch(selected_sha) is None:
        _fail("R7_R4_CURRENT_INVALID")
    records = state.get("candidate_revisions")
    if type(records) is not list:
        _fail("R7_R4_CURRENT_INVALID")
    selected = next(
        (
            record
            for record in records
            if isinstance(record, Mapping)
            and record.get("candidate_revision_sha256") == selected_sha
        ),
        None,
    )
    if not isinstance(selected, dict) or selected.get("run_id") != run_id:
        _fail("R7_R4_CURRENT_INVALID")
    artifacts = _mapping(selected.get("candidate_artifacts"))
    mutation = _mapping(selected.get("mutation_evidence"))
    artifact_sha = _sha(artifacts.get("artifact_sha256"))
    latest_mutation_sha = _sha(mutation.get("latest_mutation_evidence_sha256"))
    state_sha = _sha(state.get("state_sha256"))
    return state, copy.deepcopy(selected), selected_sha, state_sha, artifact_sha


def _validated_r5(
    result: object,
    *,
    selected_sha: str,
    state_sha: str,
    latest_mutation_sha: str,
) -> dict[str, object]:
    try:
        validated = validate_visual_verdict_result(
            result,
            expected_candidate_revision_sha256=selected_sha,
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


def _manifest_hash(path: Path) -> str:
    try:
        return _sha(manifest_sha256_file(path))
    except Exception as error:
        raise VerifiedPublisherError("R7_MANIFEST_INVALID") from error


def _lifecycle_result(
    *,
    published_artifact_sha256: str,
    target_snapshot_sha256: str,
    publication_id: str,
) -> dict[str, object]:
    payload = {
        "publication_id": publication_id,
        "published_artifact_sha256": published_artifact_sha256,
        "target_snapshot_sha256": target_snapshot_sha256,
        "publication_outcome": "PUBLISHED",
    }
    return {
        "result_sha256": canonical_json_sha256(payload),
        "published_artifact_sha256": published_artifact_sha256,
        "target_snapshot_sha256": target_snapshot_sha256,
        "publication_outcome": "PUBLISHED",
    }


def _failed_lifecycle_result(
    *,
    publishable_artifact_sha256: str,
    target_snapshot_sha256: str,
    publication_id: str,
) -> dict[str, object]:
    payload = {
        "publication_id": publication_id,
        "publishable_artifact_sha256": publishable_artifact_sha256,
        "target_snapshot_sha256": target_snapshot_sha256,
        "publication_outcome": "FAILED",
    }
    return {
        "result_sha256": canonical_json_sha256(payload),
        "published_artifact_sha256": publishable_artifact_sha256,
        "target_snapshot_sha256": target_snapshot_sha256,
        "publication_outcome": "FAILED",
    }


def _recovery_record(
    *,
    target_snapshot_sha256: str,
    restored_artifact_sha256: str,
    publication_id: str,
    outcome: str,
) -> dict[str, object]:
    payload = {
        "publication_id": publication_id,
        "target_snapshot_sha256": target_snapshot_sha256,
        "restored_artifact_sha256": restored_artifact_sha256,
        "recovery_outcome": outcome,
    }
    return {
        "recovery_sha256": canonical_json_sha256(payload),
        "target_snapshot_sha256": target_snapshot_sha256,
        "restored_artifact_sha256": restored_artifact_sha256,
        "recovery_outcome": outcome,
    }


def _transition(
    manifest_path: Path,
    *,
    expected_manifest_sha256: str,
    action: str,
    publication_id: str,
    authorization_id: str,
    authorization_sha256: str,
    intent: Mapping[str, object],
    result: Mapping[str, object] | None = None,
    recovery: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        return transition_publication_lifecycle(
            manifest_path,
            expected_manifest_sha256=expected_manifest_sha256,
            action=action,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha256=authorization_sha256,
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
    authorization_sha256: str,
    intent: Mapping[str, object],
    publishable_artifact_sha256: str,
    target_snapshot_sha256: str,
) -> None:
    result = _failed_lifecycle_result(
        publishable_artifact_sha256=publishable_artifact_sha256,
        target_snapshot_sha256=target_snapshot_sha256,
        publication_id=publication_id,
    )
    _transition(
        manifest_path,
        expected_manifest_sha256=_manifest_hash(manifest_path),
        action="RECORD_FAILED",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha256=authorization_sha256,
        intent=intent,
        result=result,
    )


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
    """Compose current R4 + fresh R5 PASS + exact authorization into one R7 publish."""

    run = _identifier(run_id)
    expected_manifest = _sha(expected_manifest_sha256)
    if type(manifest_path) is not Path or type(candidate_path) is not Path or type(target_path) is not Path:
        _fail("R7_INPUT_INVALID")

    state, selected, selected_sha, state_sha, artifact_sha = _selected_candidate(
        candidate_state,
        run_id=run,
    )
    latest_mutation_sha = _sha(
        _mapping(selected.get("mutation_evidence")).get(
            "latest_mutation_evidence_sha256"
        )
    )
    r5 = _validated_r5(
        r5_verdict_result,
        selected_sha=selected_sha,
        state_sha=state_sha,
        latest_mutation_sha=latest_mutation_sha,
    )
    r5_sha = _sha(r5.get("verdict_sha256"))

    try:
        candidate_snapshot = snapshot_publication_file(candidate_path)
        target_snapshot = snapshot_publication_file(target_path)
    except Exception as error:
        raise VerifiedPublisherError("R7_PUBLICATION_FILE_INVALID") from error
    if candidate_snapshot.get("sha256") != artifact_sha:
        _fail("R7_CANDIDATE_ARTIFACT_MISMATCH")
    target_sha = _sha(target_snapshot.get("sha256"))
    target_identity_sha = _target_identity(target_snapshot)

    authorization = _mapping(auto_publish_authorization)
    try:
        validated_authorization = validate_visual_contract(
            authorization,
            contract="auto_publish_authorization",
        )
        require_auto_publish_authorized(
            validated_authorization,
            run_id=run,
            target_path=str(target_path),
            target_sha256=target_sha,
        )
    except Exception as error:
        raise VerifiedPublisherError("R7_AUTHORIZATION_INVALID") from error
    authorization_id = _identifier(validated_authorization.get("authorization_id"))
    try:
        authorization_sha = canonical_json_sha256(validated_authorization)
    except Exception as error:
        raise VerifiedPublisherError("R7_AUTHORIZATION_INVALID") from error

    intent = {
        "candidate_revision_sha256": selected_sha,
        "r5_verdict_sha256": r5_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_identity_sha256": target_identity_sha,
    }
    publication_material = {
        "run_id": run,
        "candidate_revision_sha256": selected_sha,
        "candidate_state_sha256": state_sha,
        "r5_verdict_sha256": r5_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_identity_sha256": target_identity_sha,
    }
    publication_id = "publication:" + canonical_json_sha256(publication_material)

    _transition(
        manifest_path,
        expected_manifest_sha256=expected_manifest,
        action="CLAIM",
        publication_id=publication_id,
        authorization_id=authorization_id,
        authorization_sha256=authorization_sha,
        intent=intent,
    )

    prepared: Mapping[str, object] | None = None
    try:
        prepared = prepare_publication_replacement(
            target_path=target_path,
            candidate_path=candidate_path,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=artifact_sha,
        )

        # Freshly re-run both accepted currentness/verdict validators after CLAIM
        # and immediately before the irreversible owner commit.
        state_again, _selected_again, selected_again, state_sha_again, artifact_again = (
            _selected_candidate(state, run_id=run)
        )
        if selected_again != selected_sha or state_sha_again != state_sha or artifact_again != artifact_sha:
            _fail("R7_R4_CURRENT_INVALID")
        _validated_r5(
            r5,
            selected_sha=selected_sha,
            state_sha=state_sha,
            latest_mutation_sha=latest_mutation_sha,
        )

        committed = commit_publication_replacement(
            prepared,
            expected_target_sha256=target_sha,
            expected_candidate_sha256=artifact_sha,
        )
    except PublicationFileError as error:
        category = str(error)
        if prepared is not None and category == "PUBLICATION_VERIFY_FAILED":
            recovery_required = _recovery_record(
                target_snapshot_sha256=target_identity_sha,
                restored_artifact_sha256=target_sha,
                publication_id=publication_id,
                outcome="RECOVERY_REQUIRED",
            )
            _transition(
                manifest_path,
                expected_manifest_sha256=_manifest_hash(manifest_path),
                action="REQUIRE_RECOVERY",
                publication_id=publication_id,
                authorization_id=authorization_id,
                authorization_sha256=authorization_sha,
                intent=intent,
                recovery=recovery_required,
            )
            try:
                restored = restore_publication_target(
                    prepared,
                    expected_current_sha256=artifact_sha,
                )
                restored_sha = _sha(restored.get("restored_sha256"))
                rollback = _recovery_record(
                    target_snapshot_sha256=target_identity_sha,
                    restored_artifact_sha256=restored_sha,
                    publication_id=publication_id,
                    outcome="ROLLED_BACK",
                )
                _transition(
                    manifest_path,
                    expected_manifest_sha256=_manifest_hash(manifest_path),
                    action="RECORD_ROLLBACK",
                    publication_id=publication_id,
                    authorization_id=authorization_id,
                    authorization_sha256=authorization_sha,
                    intent=intent,
                    recovery=rollback,
                )
            except Exception as recovery_error:
                raise VerifiedPublisherError("R7_RECOVERY_REQUIRED") from recovery_error
            finally:
                try:
                    cleanup_publication_replacement(prepared)
                except Exception:
                    pass
            _fail("R7_PUBLICATION_ROLLED_BACK")
        _record_failed(
            manifest_path,
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha256=authorization_sha,
            intent=intent,
            publishable_artifact_sha256=artifact_sha,
            target_snapshot_sha256=target_identity_sha,
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
            authorization_sha256=authorization_sha,
            intent=intent,
            publishable_artifact_sha256=artifact_sha,
            target_snapshot_sha256=target_identity_sha,
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
            authorization_sha256=authorization_sha,
            intent=intent,
            publishable_artifact_sha256=artifact_sha,
            target_snapshot_sha256=target_identity_sha,
        )
        if prepared is not None:
            try:
                cleanup_publication_replacement(prepared)
            except Exception:
                pass
        raise VerifiedPublisherError("R7_PUBLICATION_FAILED") from error

    published_sha = _sha(committed.get("published_sha256"))
    lifecycle_result = _lifecycle_result(
        published_artifact_sha256=published_sha,
        target_snapshot_sha256=target_identity_sha,
        publication_id=publication_id,
    )
    try:
        _transition(
            manifest_path,
            expected_manifest_sha256=_manifest_hash(manifest_path),
            action="RECORD_PUBLISHED",
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha256=authorization_sha,
            intent=intent,
            result=lifecycle_result,
        )
        _transition(
            manifest_path,
            expected_manifest_sha256=_manifest_hash(manifest_path),
            action="CONSUME",
            publication_id=publication_id,
            authorization_id=authorization_id,
            authorization_sha256=authorization_sha,
            intent=intent,
        )
    except Exception as error:
        raise VerifiedPublisherError("R7_LIFECYCLE_INVALID") from error
    finally:
        if prepared is not None:
            try:
                cleanup_publication_replacement(prepared)
            except Exception:
                pass

    result_payload = {
        "schema_version": R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION,
        "publication_id": publication_id,
        "run_id": run,
        "authorization_id": authorization_id,
        "authorization_sha256": authorization_sha,
        "candidate_revision_sha256": selected_sha,
        "candidate_state_sha256": state_sha,
        "r5_verdict_sha256": r5_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "publishable_artifact_sha256": artifact_sha,
        "target_snapshot_sha256": target_identity_sha,
        "published_artifact_sha256": published_sha,
        "publication_state": "PUBLISHED",
    }
    publication_sha = canonical_json_sha256(result_payload)
    return validate_verified_publication_result(
        {**result_payload, "publication_sha256": publication_sha},
        expected_candidate_revision_sha256=selected_sha,
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
    """Validate one closed R7 success record without mutating lifecycle or files."""

    try:
        if type(result) is not dict or set(result) != _RESULT_FIELDS:
            _fail("R7_RESULT_INVALID")
        if result.get("schema_version") != R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION:
            _fail("R7_RESULT_INVALID")
        _identifier(result.get("publication_id"))
        _identifier(result.get("run_id"))
        _identifier(result.get("authorization_id"))
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
            _sha(result.get(field))
        if result.get("publication_state") != "PUBLISHED":
            _fail("R7_RESULT_INVALID")
        if result.get("publishable_artifact_sha256") != result.get(
            "published_artifact_sha256"
        ):
            _fail("R7_RESULT_INVALID")
        normalized = copy.deepcopy(result)
        supplied_hash = normalized.pop("publication_sha256")
        if canonical_json_sha256(normalized) != supplied_hash:
            _fail("R7_RESULT_INVALID")
        normalized["publication_sha256"] = supplied_hash
        for expected, field in (
            (expected_candidate_revision_sha256, "candidate_revision_sha256"),
            (expected_candidate_state_sha256, "candidate_state_sha256"),
            (expected_r5_verdict_sha256, "r5_verdict_sha256"),
            (expected_latest_mutation_sha256, "latest_mutation_sha256"),
        ):
            if expected is not None and _sha(expected) != normalized[field]:
                _fail("R7_RESULT_INVALID")
        return copy.deepcopy(normalized)
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
