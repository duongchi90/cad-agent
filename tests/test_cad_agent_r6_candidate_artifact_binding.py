from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from cad_agent import approved_repair_adapter as r6
from cad_agent.drawing_contracts import canonical_json_sha256


def _accepted_r6_fixture_module():
    path = Path(__file__).with_name("test_cad_agent_approved_repair_adapter.py")
    spec = importlib.util.spec_from_file_location("r6_accepted_fixtures_221", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R6 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_result_and_candidate() -> tuple[dict[str, object], dict[str, object]]:
    fixtures = _accepted_r6_fixture_module()
    result = fixtures._valid_r6_result()
    _state, candidate = fixtures._candidate_binding()
    return deepcopy(result), deepcopy(candidate)


def _reseal(result: dict[str, object]) -> dict[str, object]:
    result.pop("result_sha256", None)
    result["result_sha256"] = canonical_json_sha256(result)
    return result


def test_r6_result_binds_current_candidate_artifact_reference() -> None:
    result, candidate = _valid_result_and_candidate()
    candidate_artifacts = candidate["candidate_artifacts"]

    assert result["candidate_artifact_reference_id"] == candidate_artifacts[
        "reference_id"
    ]
    assert result["candidate_artifact_reference_sha256"] == candidate_artifacts[
        "reference_sha256"
    ]
    assert r6.R6_RESULT_SCHEMA_VERSION == "r6-repair-executor-result-1.1"


def test_public_validator_accepts_exact_candidate_artifact_reference_bindings() -> None:
    result, candidate = _valid_result_and_candidate()
    candidate_artifacts = candidate["candidate_artifacts"]

    validated = r6.validate_approved_repair_result(
        result,
        expected_candidate_artifact_reference_id=candidate_artifacts["reference_id"],
        expected_candidate_artifact_reference_sha256=candidate_artifacts[
            "reference_sha256"
        ],
    )

    assert validated == result
    assert validated is not result


@pytest.mark.parametrize(
    ("expected_id", "expected_sha"),
    [
        ("dara-ref-foreign-candidate", None),
        (None, "f" * 64),
    ],
)
def test_public_validator_rejects_foreign_candidate_artifact_binding_privacy_safely(
    expected_id: str | None,
    expected_sha: str | None,
) -> None:
    result, candidate = _valid_result_and_candidate()
    candidate_artifacts = candidate["candidate_artifacts"]
    expected_reference_id = (
        candidate_artifacts["reference_id"] if expected_id is None else expected_id
    )
    expected_reference_sha256 = (
        candidate_artifacts["reference_sha256"] if expected_sha is None else expected_sha
    )

    with pytest.raises(Exception) as exc:
        r6.validate_approved_repair_result(
            result,
            expected_candidate_artifact_reference_id=expected_reference_id,
            expected_candidate_artifact_reference_sha256=expected_reference_sha256,
        )

    message = str(exc.value)
    assert "BINDING_MISMATCH" in message
    assert "foreign-candidate" not in message
    assert "f" * 64 not in message


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("candidate_artifact_reference_id", "dara-ref-resealed-foreign"),
        ("candidate_artifact_reference_sha256", "e" * 64),
    ],
)
def test_resealed_candidate_artifact_substitution_cannot_validate_against_owner_anchor(
    field: str,
    replacement: str,
) -> None:
    result, candidate = _valid_result_and_candidate()
    candidate_artifacts = candidate["candidate_artifacts"]
    candidate_before = deepcopy(candidate)
    result[field] = replacement
    _reseal(result)

    with pytest.raises(Exception, match="BINDING_MISMATCH"):
        r6.validate_approved_repair_result(
            result,
            expected_candidate_artifact_reference_id=candidate_artifacts["reference_id"],
            expected_candidate_artifact_reference_sha256=candidate_artifacts[
                "reference_sha256"
            ],
        )

    assert candidate == candidate_before
