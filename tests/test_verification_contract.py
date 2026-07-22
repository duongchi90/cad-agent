from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
UPLOAD_ARTIFACT_SHA = "b7c566a772e6b6bfb58ed0dc250532a479d7789f"


class VerificationContractTests(unittest.TestCase):
    def test_verify_script_owns_all_checks(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        for test_root in (
            "tests",
            "primitive_ir_lib/tests",
            "semantic_ir_lib/tests",
            "dxf_builder_lib/tests",
            "mcp_integration_lib/tests",
            "agent_lib/tests",
        ):
            self.assertIn(test_root, script)
        self.assertIn("-m pytest", script)
        self.assertIn("-p no:cacheprovider", script)
        self.assertIn("-m ruff check", script)
        self.assertIn("git diff --check", script)
        self.assertIn("git diff --cached --check", script)
        self.assertIn("--junitxml", script)
        self.assertIn("importlib.metadata", script)
        self.assertIn("not real_data and not autocad_lt", script)
        self.assertIn("real-data-unavailable.xml", script)
        self.assertIn("autocad-lt-unavailable.xml", script)
        self.assertIn("check_environment.py", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("ls-files", script)
        self.assertIn('Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"', script)

    def test_workflow_is_pinned_and_least_privilege(self) -> None:
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", workflow)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_SHA}", workflow)
        self.assertIn(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", workflow)
        action_refs = re.findall(
            r"^\s*uses:\s*actions/[^@\s]+@([^\s#]+)", workflow, re.MULTILINE
        )
        self.assertEqual(3, len(action_refs))
        for ref in action_refs:
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(".\\scripts\\bootstrap.ps1 -PythonExe python", workflow)
        self.assertIn(".\\scripts\\verify.ps1", workflow)
        self.assertIn("path: .artifacts/test-results/", workflow)
        self.assertNotIn("python -m pytest primitive_ir_lib", workflow)


if __name__ == "__main__":
    unittest.main()
