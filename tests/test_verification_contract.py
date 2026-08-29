from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOTNET_SOLUTION = "autocad_plugin/CadAgent.AutoCAD2027.sln"
DOTNET_IPC_TEST = "mcp_integration_lib/tests/test_dotnet_ipc.py"
DOTNET_IPC_SOURCE = "mcp_integration_lib/dotnet_ipc.py"
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
        self.assertIn("not real_data and not autocad_mechanical", script)
        self.assertIn("real-data-unavailable.xml", script)
        self.assertIn("autocad-mechanical-unavailable.xml", script)
        self.assertIn("causal_red", script)
        self.assertIn("causal-red.xml", script)
        self.assertIn("check_environment.py", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("ls-files", script)
        self.assertIn('Write-Host "Tesseract: $tesseractPath ($tesseractVersion)"', script)

    def test_causal_red_is_an_independent_expected_failure_gate(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        self.assertIn("Invoke-CausalRedGate", script)
        self.assertIn('-m "causal_red"', script)
        self.assertIn('$causalRedExitCode -ne 1', script)
        self.assertIn("Failures -ne 1", script)
        self.assertIn(
            '"not real_data and not autocad_mechanical and not causal_red"',
            script,
        )

    def test_verify_owns_release_x64_dotnet_solution_gates(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        self.assertIn(DOTNET_SOLUTION, script)
        restore = script.index("dotnet restore")
        build = script.index("dotnet build")
        test = script.index("dotnet test")
        self.assertLess(restore, build)
        self.assertLess(build, test)
        for command in ("dotnet restore", "dotnet build", "dotnet test"):
            self.assertIn(command, script)
        self.assertGreaterEqual(script.count('"-c"'), 2)
        self.assertGreaterEqual(script.count('"Release"'), 2)
        self.assertGreaterEqual(script.count('"-p:Platform=x64"'), 2)
        self.assertIn("BLOCKER:", script)

    def test_verify_runs_dotnet_ipc_gate_and_exact_ruff_targets(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        self.assertIn(DOTNET_IPC_TEST, script)
        self.assertIn(DOTNET_IPC_SOURCE, script)
        self.assertIn(
            '"mcp_integration_lib/tests/test_dotnet_ipc.py"',
            script,
        )
        self.assertIn(
            '"mcp_integration_lib/dotnet_ipc.py"',
            script,
        )

    def test_live_marker_is_explicit_and_not_inferred_from_dotnet_gates(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        live_gate = script.index('-Name "autocad_mechanical live gate"')
        live_marker_branch = script.index('if ($ExpectedState -eq "live")')
        self.assertIn('AutoCAD live marker: PASS', script)
        self.assertIn('AutoCAD live marker: SKIP', script)
        self.assertIn('AutoCAD live marker: NOT RUN', script)
        self.assertIn('ExpectedState "live"', script)
        self.assertIn("CAD_AGENT_FILE_IPC", script)
        self.assertIn("CAD_AGENT_AUTOCAD_HWND", script)
        self.assertIn("CAD_AGENT_AUTOCAD_LISP_PATH", script)
        self.assertGreater(
            script.index('AutoCAD live marker: PASS'),
            live_marker_branch,
        )
        self.assertGreater(
            script.index('AutoCAD live marker: SKIP'),
            live_marker_branch,
        )
        self.assertGreater(script.index('AutoCAD live marker: NOT RUN'), live_gate)

    def test_m2_opt_in_gate_is_separate_from_generic_autocad_live_gate(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"m2_mechanical:', project)
        self.assertIn("autocad_mechanical and not m2_mechanical", script)
        self.assertIn('CAD_AGENT_M2_RECORD_PATH', script)
        self.assertIn('CAD_AGENT_M2_SESSION_ID', script)
        self.assertIn('CAD_AGENT_M2_HUMAN_EVENTS_JSON', script)

    def test_live_unavailability_is_not_reported_as_a_pass(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        not_run = script.index('AutoCAD live marker: NOT RUN')
        self.assertIn("no AutoCAD Mechanical session", script[not_run - 400 : not_run + 200])
        self.assertNotIn("AutoCAD live marker: PASS", script[not_run - 400 : not_run + 200])

    def test_hosted_mode_explicitly_skips_only_autocad_dotnet_gate(self) -> None:
        script = (ROOT / "scripts/verify.ps1").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")

        self.assertIn("[switch]$SkipAutoCADDotNet", script)
        self.assertIn(
            "AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet).",
            script,
        )
        self.assertIn(".\\scripts\\verify.ps1 -SkipAutoCADDotNet", workflow)
        self.assertNotIn(
            ".\\scripts\\verify.ps1\\n",
            workflow.replace(".\\scripts\\verify.ps1 -SkipAutoCADDotNet", ""),
        )

        dotnet_gate = script.index('Invoke-DotNetGate -Name "dotnet restore"')
        skip_marker = script.index(
            "AutoCAD .NET gate: NOT RUN (explicit -SkipAutoCADDotNet)."
        )
        self.assertLess(skip_marker, dotnet_gate)

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

    def test_live_autocad_suite_closes_disposable_drawings(self) -> None:
        suite = (
            ROOT / "mcp_integration_lib/tests/test_file_ipc_e2e.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _opened_disposable_drawing(", suite)
        self.assertGreaterEqual(suite.count("with self._opened_disposable_drawing("), 5)

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
