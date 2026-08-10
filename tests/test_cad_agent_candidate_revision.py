from __future__ import annotations

from cad_agent.candidate_revision import (
    CANDIDATE_REVISION_SCHEMA_VERSION,
    CandidateRevisionError,
    build_candidate_revision,
    validate_candidate_revision,
)


def test_r4_candidate_revision_api_is_missing_until_production_green() -> None:
    """Causal RED: the second production path is intentionally not present yet."""
    assert CANDIDATE_REVISION_SCHEMA_VERSION == "candidate-revision-1.0"
    assert issubclass(CandidateRevisionError, ValueError)
    assert callable(build_candidate_revision)
    assert callable(validate_candidate_revision)
