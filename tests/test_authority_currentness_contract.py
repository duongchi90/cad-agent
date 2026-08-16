from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_authority_documents_fail_closed_to_live_github_control() -> None:
    for relative_path in ("docs/AI_OPERATING_MODEL.md", "docs/HANDOFF.md"):
        opening = "\n".join(
            (ROOT / relative_path).read_text(encoding="utf-8").splitlines()[:32]
        )
        assert "Issue #131" in opening, relative_path
        assert "historical" in opening.casefold(), relative_path
        assert "not live" in opening.casefold(), relative_path
        assert "docs/STATUS.md" in opening, relative_path
        assert "docs/SOL_HANDOFF.md" in opening, relative_path
        assert "actual current `main`" in opening, relative_path
