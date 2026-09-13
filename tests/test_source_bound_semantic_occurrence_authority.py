from __future__ import annotations

import importlib
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
def test_source_fusion_has_a_seam_for_the_approved_authority_v1_fixture() -> None:
    """The approved contract currently has no existing owner entry point."""
    payload = _fixture()
    assert payload["contract_version"] == "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1"
    assert {
        case["expected"] for case in payload["oracle_cases"]
    } == {"DISTINCT", "SAME_OCCURRENCE", "UNRESOLVED_NON_PASS"}

    source_fusion = importlib.import_module("cad_agent.source_fusion")
    validator = getattr(
        source_fusion,
        "validate_source_bound_semantic_occurrence_authority",
        None,
    )
    assert callable(validator), (
        "Causal RED: the existing Source Fusion owner has no public seam for "
        "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1."
    )
