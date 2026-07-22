from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_project_document_records_the_approved_scope(self) -> None:
        project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("Windows", project)
        self.assertIn("Python 3.11", project)
        self.assertIn("AutoCAD LT", project)
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
        self.assertIn("not implemented in this slice", architecture)
        self.assertIn("detected constraints only", architecture)
        self.assertIn("PruneResult", architecture)
        self.assertIn("SolveResult", architecture)
        self.assertIn("agent_lib.run", architecture)
        self.assertIn("automatically calls `apply_agent_report()`", architecture)
        self.assertIn("not an approved production mutation path", architecture)


if __name__ == "__main__":
    unittest.main()
