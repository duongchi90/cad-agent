from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GuidanceContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
