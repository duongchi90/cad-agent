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

    def test_every_cad_edit_uses_engineering_first_and_measured_acceptance(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Apply engineering-first reasoning to every CAD operation", agents)
        self.assertIn("measure geometry rather than labels or appearance", agents)
        self.assertIn("proportionate to scope", agents)
        self.assertIn("docs/AI_OPERATING_MODEL.md", agents)

        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8").lower()
        for term in (
            "revision:** reuse a trustworthy native base",
            "source-supported bounded delta",
            "reconstruction:** understand the full drawing",
            "native_edit:** reuse correct native geometry and verify only the edited scope",
            "driving",
            "reference",
            "redundant",
            "conflicting",
            "unresolved",
            "associate each with the feature or relationship it measures",
            "ocr text is evidence to classify, not an automatic constraint",
            "mark missing or conflicting information instead of silently guessing",
            "datums, centerlines, intersections, tangency, concentricity, parallel/perpendicular, symmetry, and dependencies",
            "construction order",
            "do not follow image stroke order",
            "derive only geometry determined by dimensions, relationships, and constraints",
            "use pixel evidence only for geometry the source does not determine",
            "never invent missing geometry",
            "dimension_observer",
            "constraint_solving",
            "dimension_pilot",
            "dxf_builder",
            "native cad owners",
            "create native cad dimensions only when required",
            "derive their measured values from constructed geometry",
            "never use text overrides to mask a mismatch",
            "measure actual cad lengths, angles, radii/diameters, positions, alignment, center distances, chain/overall dimensions, and applicable constraints within the affected scope",
            "compare them with source values and tolerances",
            "dimension text or visual appearance alone is not proof",
            "identify the first causal boundary",
            "re-measure affected geometry and relationships",
            "native readback and save/reopen when applicable",
            "reuse validated knowledge",
            "keep simple-task checks proportionate",
            "do not claim `verified` until critical checks within the applicable scope and acceptance gates pass",
        ):
            with self.subTest(term=term):
                self.assertIn(term, model)

    def test_new_solution_design_checks_prior_art_and_reuses_closed_research(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        model = (ROOT / "docs/AI_OPERATING_MODEL.md").read_text(encoding="utf-8")
        for term in (
            "existing implementations/APIs/libraries",
            "evidence-backed methods",
            "reuse, quality, cost, and owner fit",
            "smallest real-case A/B",
            "design anew only when evidence shows they fall short",
            "Keep research proportionate",
        ):
            with self.subTest(term=term):
                self.assertIn(term, agents)
        for term in (
            "inspect current implementations, APIs, and libraries",
            "established methods, algorithms, or research",
            "source code or reproducible evidence",
            "reuse potential, quality, cost, and fit with existing owners",
            "smallest real-case A/B",
            "evidence shows existing options cannot meet the requirement",
            "Keep research proportionate to difficulty",
            "reuse completed findings unless new evidence changes the decision",
        ):
            with self.subTest(term=term):
                self.assertIn(term, model)

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
