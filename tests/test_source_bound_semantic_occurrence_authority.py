from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from cad_agent.source_bound_semantic_occurrence_authority import (
    validate_source_bound_semantic_occurrence_authority,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "source-bound-semantic-occurrence-authority-v1.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_approved_authority_v1_contract_is_validated_fail_closed() -> None:
    """The selected adjacent owner validates the approved contract and oracle."""
    payload = _fixture()
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
    )
    assert result["contract_version"] == "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1"
    assert result["currentness"] == "UNRESOLVED_NON_PASS"
    assert {
        case["case_id"]: case["status"]
        for case in result["oracle_results"]
    } == {
        "DISTINCT_PARALLEL_OCCURRENCES": "DISTINCT",
        "SAME_OCCURRENCE_DUPLICATE_OBSERVATIONS": "SAME_OCCURRENCE",
        "MULTI_MATCH": "UNRESOLVED_NON_PASS",
        "STALE_RENDER_BINDING": "UNRESOLVED_NON_PASS",
    }

    stale_binding = deepcopy(payload["source"])
    stale_binding["render_sha256"] = "333" * 21 + "3"
    stale_result = validate_source_bound_semantic_occurrence_authority(
        payload,
        current_source_binding=stale_binding,
    )
    assert stale_result["currentness"] == "UNRESOLVED_NON_PASS"


def test_self_echoed_binding_without_owner_evidence_cannot_grant_currentness() -> None:
    payload = _fixture()
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
        current_source_binding=payload["source"],
    )
    assert result["currentness"] == "UNRESOLVED_NON_PASS"


def test_zero_match_is_fail_closed() -> None:
    payload = _fixture()
    payload["oracle_cases"].append(
        {
            "case_id": "ZERO_MATCH",
            "observations": [
                {"candidate_id": "RAW-NONE", "matched_occurrence_ids": []}
            ],
            "expected": "UNRESOLVED_NON_PASS",
        }
    )
    try:
        result = validate_source_bound_semantic_occurrence_authority(payload)
    except Exception as exc:  # pragma: no cover - causal RED until ZERO_MATCH exists
        pytest.fail(f"ZERO_MATCH must return a fail-closed result: {exc}")
    assert {
        case["case_id"]: case["status"]
        for case in result["oracle_results"]
    }["ZERO_MATCH"] == "UNRESOLVED_NON_PASS"
