from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "source-bound-semantic-occurrence-authority-v1.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.causal_red
def test_approved_authority_v1_contract_has_no_selected_validator_yet() -> None:
    """The approved contract is red until an owner is selected and supplied."""
    payload = _fixture()
    assert payload["contract_version"] == "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1"
    assert {
        case["expected"] for case in payload["oracle_cases"]
    } == {"DISTINCT", "SAME_OCCURRENCE", "UNRESOLVED_NON_PASS"}

    selected_validator = None
    assert callable(selected_validator), (
        "Causal RED: no production validator has been selected or authorized "
        "for SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1."
    )
