"""Causal RED for R6 accepted-result binding to the current R4 candidate artifact."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


def _accepted_r6_fixture_module():
    path = Path(__file__).with_name("test_cad_agent_approved_repair_adapter.py")
    spec = importlib.util.spec_from_file_location("accepted_r6_fixtures", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _accepted_result_and_candidate() -> tuple[dict[str, object], dict[str, object]]:
    fixtures = _accepted_r6_fixture_module()
    result = fixtures._execute(fixtures._valid_inputs())
    _state, candidate = fixtures._candidate_binding()
    return result, candidate


def test_accepted_result_exposes_exact_current_candidate_artifact_reference() -> None:
    result, candidate = _accepted_result_and_candidate()
    artifact = candidate["candidate_artifacts"]
    assert result.get("candidate_artifact_reference_id") == artifact["reference_id"]
    assert result.get("candidate_artifact_reference_sha256") == artifact["reference_sha256"]


def test_validator_binds_expected_candidate_artifact_reference_id() -> None:
    fixtures = _accepted_r6_fixture_module()
    result, candidate = _accepted_result_and_candidate()
    validator = fixtures._result_validator()
    artifact = candidate["candidate_artifacts"]
    assert validator(
        result,
        expected_candidate_artifact_reference_id=artifact["reference_id"],
    ) == result
    with pytest.raises(Exception, match="binding|BINDING"):
        validator(
            result,
            expected_candidate_artifact_reference_id="dara-ref-foreign",
        )


def test_validator_binds_expected_candidate_artifact_reference_sha256() -> None:
    fixtures = _accepted_r6_fixture_module()
    result, candidate = _accepted_result_and_candidate()
    validator = fixtures._result_validator()
    artifact = candidate["candidate_artifacts"]
    assert validator(
        result,
        expected_candidate_artifact_reference_sha256=artifact["reference_sha256"],
    ) == result
    with pytest.raises(Exception, match="binding|BINDING"):
        validator(
            result,
            expected_candidate_artifact_reference_sha256="f" * 64,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("candidate_artifact_reference_id", "dara-ref-foreign"),
        ("candidate_artifact_reference_sha256", "f" * 64),
    ],
)
def test_resealed_foreign_candidate_artifact_binding_is_rejected(
    field: str,
    replacement: str,
) -> None:
    fixtures = _accepted_r6_fixture_module()
    result, candidate = _accepted_result_and_candidate()
    artifact = candidate["candidate_artifacts"]
    tampered = deepcopy(result)
    tampered[field] = replacement
    semantic = {key: value for key, value in tampered.items() if key != "result_sha256"}
    tampered["result_sha256"] = canonical_json_sha256(semantic)

    validator = fixtures._result_validator()
    with pytest.raises(Exception, match="binding|BINDING"):
        validator(
            tampered,
            expected_candidate_artifact_reference_id=artifact["reference_id"],
            expected_candidate_artifact_reference_sha256=artifact["reference_sha256"],
        )
