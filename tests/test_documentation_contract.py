from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_status_is_evidence_based(self) -> None:
        status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        self.assertIn("908d016", status)
        self.assertIn("255 passed, 11 skipped, 3 warnings", status)
        self.assertIn("Verified", status)
        self.assertIn("Partially verified", status)
        self.assertIn("Unverified", status)
        self.assertIn("NOT RUN", status)

    def test_quality_defines_every_required_gate(self) -> None:
        quality = (ROOT / "docs/QUALITY.md").read_text(encoding="utf-8")
        for term in (
            "offline",
            "contract",
            "real_data",
            "autocad_mechanical",
            "P0",
            "P1",
            "P2",
            "P3",
            "scripts/verify.ps1",
            "human approval",
        ):
            self.assertIn(term, quality)

    def test_readme_is_a_short_router_without_evergreen_test_counts(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(readme.splitlines()), 120)
        self.assertIn("docs/PROJECT.md", readme)
        self.assertIn("docs/ARCHITECTURE.md", readme)
        self.assertIn("docs/STATUS.md", readme)
        self.assertIn("docs/QUALITY.md", readme)
        self.assertNotIn("57/57", readme)
        self.assertNotIn("220 passed", readme)

    def test_current_documents_agree_on_environment_command_and_gate_states(self) -> None:
        documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/STATUS.md", "docs/QUALITY.md")
        }
        for path, content in documents.items():
            for term in (
                "Supported release environment",
                "Windows",
                "Python 3.11",
                "AutoCAD Mechanical 2027",
                "Tesseract 5.4.0.20240606",
                r".\scripts\verify.ps1",
                "`real_data`",
                "`autocad_mechanical`",
                "SKIP",
                "NOT RUN",
            ):
                self.assertIn(term, content, f"{term!r} missing from {path}")

    def test_plan_checkboxes_are_not_treated_as_current_status(self) -> None:
        planning = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
        self.assertIn("Unchecked boxes are not status evidence", planning)
        self.assertIn("Base SHA", planning)
        self.assertIn("Completion Head SHA", planning)
        self.assertIn("docs/STATUS.md", planning)

    def test_project_routes_to_current_status_and_quality(self) -> None:
        project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("docs/STATUS.md", project)
        self.assertIn("docs/QUALITY.md", project)
        self.assertIn("docs/superpowers/README.md", project)

    def test_canonical_docs_route_the_m2_setup_gate_and_preserve_boundaries(self) -> None:
        documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in ("docs/PROJECT.md", "docs/ARCHITECTURE.md", "docs/STATUS.md")
        }
        design = "docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md"
        plan = "docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md"
        for path, content in documents.items():
            self.assertIn(design, content, f"{design!r} missing from {path}")
            self.assertIn(plan, content, f"{plan!r} missing from {path}")

        project = documents["docs/PROJECT.md"]
        normalized_project = " ".join(project.split())
        self.assertIn("Drawing Initialization Gate", project)
        self.assertIn("configurable", project)
        self.assertIn(
            "The existing image/PDF pipeline remains `DRAFT_REFERENCE`; it cannot "
            "become authoritative until a separate dimension-first path presents "
            "hash-bound `SETUP_VERIFIED` evidence.",
            normalized_project,
        )

        architecture = documents["docs/ARCHITECTURE.md"]
        normalized_architecture = " ".join(architecture.split())
        self.assertIn(
            "Their configurable values and provenance are hash-bound. An "
            "authoritative drawing path must present `SETUP_VERIFIED` evidence "
            "before geometry creation; the existing image/PDF path remains "
            "`DRAFT_REFERENCE` until that separate dimension-first path exists.",
            normalized_architecture,
        )
        self.assertIn(
            "does not move CAD algorithms into `cad_agent`", normalized_architecture
        )
        self.assertIn(
            "does not replace the .NET/File IPC boundary", normalized_architecture
        )

        status = documents["docs/STATUS.md"]
        m2_status = status.split("## M2 Drawing Initialization Gate", 1)[1].split(
            "## AutoCAD .NET plugin", 1
        )[0]
        normalized_m2_status = " ".join(m2_status.split())
        self.assertIn("1969dc9", m2_status)
        self.assertIn(
            "T2 Drawing Setup contracts and validation merged at `2b7a756`.",
            normalized_m2_status,
        )
        self.assertIn(
            "State: **Executing**. The approved M0-M8 rollout merged at `1969dc9`",
            normalized_m2_status,
        )
        self.assertIn(
            "Full M2 is still executing and has not produced `SETUP_VERIFIED` "
            "acceptance.",
            normalized_m2_status,
        )
        self.assertIn(
            "required private-data gate is `NOT RUN`; the unavailable-state "
            "`real_data` probe is `SKIP`; and the AutoCAD/.NET live gate is "
            "`NOT RUN`.",
            normalized_m2_status,
        )
        self.assertIn(
            "Hosted evidence does not promote AutoCAD/.NET/private gates to "
            "`PASS`.",
            normalized_m2_status,
        )

    def test_historical_documents_route_to_canonical_sources(self) -> None:
        for relative_path in ("HANDOFF.md", "CAD-Agent-Kien-Truc-v1_3.md"):
            opening = "\n".join(
                (ROOT / relative_path).read_text(encoding="utf-8").splitlines()[:8]
            )
            self.assertIn("Historical record", opening)
            self.assertIn("docs/STATUS.md", opening)
            self.assertIn("docs/ARCHITECTURE.md", opening)

    def test_foundation_certificate_is_well_formed_when_present(self) -> None:
        status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        if "## Foundation certificate" not in status:
            self.assertIn("| Reproducible foundation | Unverified |", status)
            return

        certificate = status.split("## Foundation certificate", 1)[1]
        review_path = ROOT / "docs/reviews/2026-07-22-reproducible-foundation.md"
        review = review_path.read_text(encoding="utf-8")
        for term in (
            "State: **Verified**",
            "Exit code: `0`",
            "Python: `3.11.",
            "Tesseract executable:",
            "Dependencies:",
            "Offline JUnit:",
            "`real_data`: `SKIP`",
            "`autocad_lt`: `SKIP`",
            "Unexpected warnings: `0`",
            "Remaining risks:",
            "docs/reviews/2026-07-22-reproducible-foundation.md",
        ):
            self.assertIn(term, certificate)
        certificate_head = certificate.split(
            "Reviewed implementation Head SHA: `", 1
        )[1].split("`", 1)[0]
        review_head = review.split("Candidate Head SHA: `", 1)[1].split("`", 1)[0]
        self.assertRegex(certificate_head, r"^[0-9a-f]{40}$")
        self.assertEqual(certificate_head, review_head)
        self.assertRegex(
            certificate,
            r"Offline JUnit: `tests=\d+; failures=0; errors=0; skipped=0`",
        )
        for marker in ("real_data", "autocad_lt"):
            totals = re.search(
                rf"`{marker}`: `SKIP`.*`tests=(\d+); skipped=(\d+)`",
                certificate,
            )
            self.assertIsNotNone(totals)
            self.assertGreater(int(totals.group(1)), 0)
            self.assertEqual(totals.group(1), totals.group(2))
        self.assertGreaterEqual(len(re.findall(r"\b[0-9a-f]{64}\b", review.lower())), 7)
        self.assertIn("Unresolved P0/P1: `0`", review)

    def test_plan_lifecycle_metadata_is_well_formed(self) -> None:
        plan = (
            ROOT
            / "docs/superpowers/plans/2026-07-22-reproducible-foundation.md"
        ).read_text(encoding="utf-8")
        status_match = re.search(r"\*\*Status:\*\* (Planned|Completed)", plan)
        self.assertIsNotNone(status_match)
        self.assertIn("**Verification command:** `scripts/verify.ps1`", plan)
        if status_match.group(1) == "Completed":
            self.assertRegex(
                plan,
                r"\*\*Completion Head SHA:\*\* `[0-9a-f]{40}`",
            )
            self.assertIn("**Verification result:** `PASS`", plan)
            self.assertIn("`real_data`: `SKIP` probe, live gate `NOT RUN`", plan)
            self.assertIn("`autocad_lt`: `SKIP` probe, live gate `NOT RUN`", plan)
        else:
            self.assertIn(
                "Completion Head SHA:** Not recorded until the final evidence commit exists.",
                plan,
            )
            self.assertIn(
                "**Verification result:** Not recorded until execution completes.",
                plan,
            )

    def test_project_document_records_the_approved_scope(self) -> None:
        project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("Windows", project)
        self.assertIn("Python 3.11", project)
        self.assertIn("AutoCAD Mechanical 2027", project)
        self.assertIn("No GUI, web service, or VPS", project)
        self.assertIn("Incremental hardening", project)

    def test_architecture_names_every_package_and_schema(self) -> None:
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        for package in (
            "primitive_ir_lib",
            "semantic_ir_lib",
            "agent_lib",
            "dxf_builder_lib",
            "mcp_integration_lib",
        ):
            self.assertIn(package, architecture)
        for schema in (
            "primitive_ir.schema.json",
            "semantic_ir.schema.json",
            "agent_ir.schema.json",
        ):
            self.assertIn(schema, architecture)
        self.assertIn("cad_agent", architecture)
        self.assertIn("staged", architecture)
        self.assertIn("contains no recognition or CAD algorithms", architecture)
        self.assertIn("mechanical-repair", architecture)
        self.assertIn("DXF/evidence backup", architecture)
        self.assertIn("before it saves", architecture)
        self.assertIn("pruned, solver-ready constraints", architecture)
        self.assertIn("raw detections in memory", architecture)
        self.assertIn("PruneResult", architecture)
        self.assertIn("SolveResult", architecture)
        self.assertIn("agent_lib.run", architecture)
        self.assertIn("advisory and non-mutating by default", architecture)
        self.assertIn("--confirm-agent-actions APPLY", architecture)
        self.assertIn("--agent-action-approval", architecture)
        self.assertIn("agent_application.json", architecture)

    def test_visual_supervisor_t0_documentation_preserves_contract_boundaries(self) -> None:
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        for term in (
            "Visual Supervisor contract boundary",
            "Codex cannot self-approve",
            "VS-T0 contract-only",
        ):
            self.assertIn(term, architecture)
        for term in ("real_data: NOT RUN", "autocad_mechanical: NOT RUN", "OpenAI API: NOT RUN"):
            self.assertIn(term, status)


if __name__ == "__main__":
    unittest.main()
