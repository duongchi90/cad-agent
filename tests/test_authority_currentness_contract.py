from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _opening(relative_path: str) -> str:
    return "\n".join(
        (ROOT / relative_path).read_text(encoding="utf-8").splitlines()[:40]
    )


def _compact(value: str) -> str:
    return " ".join(value.split())


def test_legacy_authority_documents_fail_closed_to_live_github_control() -> None:
    for relative_path in ("docs/AI_OPERATING_MODEL.md", "docs/HANDOFF.md"):
        opening = _compact(_opening(relative_path))
        assert "Issue #131" in opening, relative_path
        assert "historical" in opening.casefold(), relative_path
        assert "not live" in opening.casefold(), relative_path
        assert "actual current `main`" in opening, relative_path
        assert "docs/STATUS.md" in opening, relative_path


def test_status_is_historical_evidence_not_currentness_authority() -> None:
    opening = _compact(_opening("docs/STATUS.md"))
    folded = opening.casefold()
    assert "historical" in folded
    assert "not live project state" in folded
    assert "#131" in opening
    assert "actual current `main`" in opening
    assert "not a scheduler" in folded
    assert "merge authority" in folded
    assert "live-action authority" in folded
