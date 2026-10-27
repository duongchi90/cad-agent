from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GuidanceContractTests(unittest.TestCase):
    def test_po_model_guard_is_required_without_creating_authority(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/po_model_guard.py --repair", agents)
        self.assertIn("verify the exact fresh runtime turn", agents)
        for term in (
            "`gpt-6-luna` / `medium`", "`gpt-6.1-sol` / `high`",
            "no other active PO", "explicit call settings and runtime checks",
            "without descendants or review", "hold only the hard decision",
            "NOT_VERIFIED until merge", "old session changed model",
        ):
            self.assertIn(term.lower(), model.lower())

    def test_agents_is_concise_and_routes_to_canonical_sources(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(agents.splitlines()), 160)
        for reference in (
            "docs/PROJECT.md",
            "docs/ARCHITECTURE.md",
            "docs/STATUS.md",
            "docs/QUALITY.md",
            "scripts/bootstrap.ps1",
            "scripts/verify.ps1",
        ):
            self.assertIn(reference, agents)
        self.assertIn("one writer", agents.lower())
        self.assertIn("human approval", agents.lower())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Agent working agreement: `AGENTS.md`", readme)

    def test_claude_adapter_is_thin_and_forbids_status_invention(self) -> None:
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(claude.splitlines()), 40)
        self.assertIn("AGENTS.md", claude)
        self.assertIn("docs/STATUS.md", claude)
        self.assertIn("Do not infer", claude)
        self.assertIn("review packet", claude.lower())

    def test_every_review_template_has_its_required_contract(self) -> None:
        requirements = {
            "TASK_BRIEF.md": ("Task ID", "Acceptance criteria", "Risk tier", "Base SHA"),
            "REVIEW_PACKET.md": (
                "Base SHA",
                "Head SHA",
                "Test evidence",
                "Diff scope",
                "self-contained",
                "SHA-256",
            ),
            "REVIEW_FINDING.md": ("Finding ID", "Severity", "Evidence", "Reproduction"),
            "ADJUDICATION.md": ("Decision", "Reason", "Owner", "Verification"),
            "RELEASE_CHECKLIST.md": ("Rollback", "Human approval", "P0/P1", "Head SHA"),
        }
        for file_name, required_terms in requirements.items():
            content = (ROOT / "docs/templates" / file_name).read_text(encoding="utf-8")
            for term in required_terms:
                self.assertIn(term, content, f"{term!r} missing from {file_name}")

    def test_chat_mode_recovery_does_not_inflate_delivery_or_verdict(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        self.assertIn("one-time `Stay in chat`", agents)
        self.assertIn("opaque thread/content-reference are not delivery or a verdict", agents)
        for term in (
            "select it at most once",
            "verify the UI is back in that same conversation",
            "does not prove submission, delivery, or receipt of a verdict",
            "`SUBMITTED`, `GENERATING`, `COMPLETED`, `ERROR`, and `UNOBSERVABLE`",
            "opaque `content-reference` placeholder alone is not inspectable reviewer output",
            "`ROLE`, `REQUEST_ID`, `CONTROLLING_ATTEMPT_ID`, `BASE`, `HEAD`, and `TREE`",
            "keep the review `PENDING`",
            "Do not bypass CAPTCHA, identity verification, or anti-automation/security challenges",
            "Retire the old channel for that packet before transfer",
        ):
            with self.subTest(term=term):
                self.assertIn(term, model)


if __name__ == "__main__":
    unittest.main()
