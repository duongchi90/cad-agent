from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
UPLOAD_ARTIFACT_SHA = "b7c566a772e6b6bfb58ed0dc250532a479d7789f"
TESSERACT_INSTALLER_SHA = (
    "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9"
)


class VerificationContractTests(unittest.TestCase):
    def test_verify_records_clean_candidate_provenance_before_test_gates(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        self.assertIn("status --porcelain=v1 --untracked-files=all", script)
        self.assertIn("rev-parse HEAD", script)
        self.assertIn("^[0-9a-f]{40}$", script)
        self.assertIn('Write-Host "Commit SHA: $candidateHead"', script)
        self.assertIn(
            'Write-Host "Repository: clean at verification start."', script
        )
        clean_guard = script.index("status --porcelain=v1 --untracked-files=all")
        first_test_gate = script.index("Invoke-PytestGate `")
        self.assertLess(clean_guard, first_test_gate)

    def test_verification_scratch_paths_are_git_ignored(self) -> None:
        for probe in (
            ".artifacts/test-results/contract-probe.xml",
            ".superpowers/sdd/contract-probe.md",
        ):
            completed = subprocess.run(
                ["git", "check-ignore", "--quiet", "--no-index", probe],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, f"not ignored: {probe}")

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

    def test_verify_discovers_tesseract_with_bootstrap_precedence(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        environment_override = script.index(
            "$tesseractPath = $env:CAD_AGENT_TESSERACT_CMD"
        )
        path_lookup = script.index(
            '$tesseractCommand = Get-Command "tesseract.exe" '
            "-ErrorAction SilentlyContinue"
        )
        resolved_source = script.index("$tesseractPath = $tesseractCommand.Source")
        default_path = script.index(
            '$tesseractPath = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"'
        )
        self.assertLess(environment_override, path_lookup)
        self.assertLess(path_lookup, resolved_source)
        self.assertLess(resolved_source, default_path)

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

    def test_workflow_hash_verifies_native_tesseract_before_execution(self) -> None:
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("choco install tesseract", workflow.lower())
        self.assertIn(
            "https://github.com/UB-Mannheim/tesseract/releases/download/"
            "v5.4.0.20240606/"
            "tesseract-ocr-w64-setup-5.4.0.20240606.exe",
            workflow,
        )
        digest_match = re.search(
            r'\$tesseractSha256\s*=\s*"([0-9a-fA-F]{64})"', workflow
        )
        self.assertIsNotNone(digest_match, "native installer needs a SHA-256 identity")
        assert digest_match is not None
        self.assertEqual(TESSERACT_INSTALLER_SHA, digest_match.group(1).lower())
        hash_check = workflow.index("Get-FileHash")
        execution = workflow.index("Start-Process")
        self.assertLess(digest_match.start(), hash_check)
        self.assertLess(hash_check, execution)
        self.assertIn("-Algorithm SHA256", workflow)
        self.assertIn("Tesseract installer SHA-256 mismatch", workflow)


if __name__ == "__main__":
    unittest.main()
