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
        self.assertIn("Do not claim durable policy adoption from a document edit alone", agents)
        self.assertIn("fresh repository-only session recovery without chat history", agents)
        self.assertIn("PERSISTENCE_ACCEPTANCE_GATE=NOT_VERIFIED", agents)
        self.assertIn("human approval", agents.lower())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Agent working agreement: `AGENTS.md`", readme)

    def test_hard_engineering_work_starts_from_domain_and_source_evidence(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for term in (
            "domain conventions and physical assumptions",
            "human workflow",
            "industry-tool practice",
            "current CAD-Agent owner",
            "source-grounded evidence with falsifying controls",
            "smallest testable change",
            "not a new approval gate",
        ):
            with self.subTest(term=term):
                self.assertIn(term, agents)

    def test_workstation_limits_and_recovery_policy_are_durable(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        for term in (
            "one heavy local job by default",
            "one Luna-managed Edge window by default, maximum two",
            "one Luna-managed DWG by default, maximum two",
            "one exclusive mutable AutoCAD lane",
            "Do not open a third window/drawing",
            "never blindly retry",
            "A blocked lane does not stop independent authorized work",
        ):
            self.assertIn(term, agents)
        for term in (
            "Run one heavy local job by default",
            "Keep one Luna-managed Edge window by default and at most two",
            "Keep one Luna-managed DWG open by default and at most two",
            "one exclusive mutable AutoCAD lane",
            "never close a user-owned drawing",
            "Close only tabs/windows Luna opened and verified it owns",
            "Retry only after the relevant condition changes",
            "continue independently authorized work",
            "A blocked action or lane is not a project stop",
            "one controlling review attempt per role and exact packet",
            "do not create bot-to-bot confirmation loops",
            "completed closed batches",
        ):
            self.assertIn(term.lower(), model.lower())

    def test_review_liveness_keeps_delivery_response_and_receipt_distinct(self) -> None:
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        for term in (
            "`REQUEST_RECORDED`",
            "`DELIVERY_CONFIRMED`",
            "`RESPONSE_OBSERVED`",
            "`TERMINAL_CURRENT`",
            "A GitHub request comment proves only `REQUEST_RECORDED`",
            "required canonical review receipt must be present on GitHub",
            "about 5 minutes",
            "about 15 minutes",
            "at 30 minutes",
            "These are diagnostic checkpoints, not response deadlines or automatic failover triggers",
            "Do not repeatedly reopen or poll when the same state is already established",
            "do not create a background monitor",
            "For `IDLE_NO_SUBSTANTIVE_RESPONSE` or `COMPLETE_NONTERMINAL`",
            "If a reviewer is visibly generating, do not message or interrupt",
            "`OBSERVABILITY_UNKNOWN`",
            "`DELIVERY_STATE=UNKNOWN`",
            "Before failover, fresh-read PR identity and GitHub receipts",
            "Fail over only to the same reviewer role",
            "a current canonical receipt prevents redispatch",
            "A HEAD change makes old verdicts stale",
            "Do not blindly resend or duplicate a review",
        ):
            self.assertIn(term, model)

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


    def test_disk_policy_checks_capacity_and_preserves_closed_evidence(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        for term in (
            "free space and expected output size",
            "KEEP",
            "REGENERABLE",
            "DISPOSABLE",
            "dirty, active, unpushed, or unverified worktrees",
        ):
            with self.subTest(term=term):
                self.assertIn(term, agents)
        for term in (
            "Z:\\DuongChi\\Cad Agent",
            "copy → hash/readback verification → reference reconciliation",
            "DISK_FREE_BEFORE",
            "DISK_FREE_AFTER",
            "RECLAIMED_GB",
        ):
            with self.subTest(term=term):
                self.assertIn(term, model)


if __name__ == "__main__":
    unittest.main()
