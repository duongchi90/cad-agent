from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootstrapContractTests(unittest.TestCase):
    def test_dependency_roles_are_explicit(self) -> None:
        runtime = (ROOT / "requirements/runtime.in").read_text(encoding="utf-8")
        vision = (ROOT / "requirements/vision.in").read_text(encoding="utf-8")
        solver = (ROOT / "requirements/solver.in").read_text(encoding="utf-8")
        dev = (ROOT / "requirements/dev.in").read_text(encoding="utf-8")
        root_shim = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        phase1_shim = (ROOT / "primitive_ir_lib/requirements.txt").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("anthropic", runtime.lower())
        self.assertNotIn("solvespace", runtime.lower())
        self.assertNotIn("pytest", runtime.lower())
        self.assertEqual("anthropic>=0.117", vision.strip())
        self.assertEqual("python-solvespace", solver.strip())
        self.assertIn("-r runtime.in", dev)
        self.assertIn("-r vision.in", dev)
        self.assertIn("-r solver.in", dev)
        self.assertIn("pip-tools==7.6.0", dev)
        self.assertIn("-r requirements/runtime.in", root_shim)
        self.assertIn("-r ../requirements/runtime.in", phase1_shim)

    def test_lock_is_current_fully_pinned_and_hashed(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/lock_contract.py"),
                "check",
                str(ROOT / "requirements/windows-py311.lock"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_bootstrap_checks_the_installed_environment(self) -> None:
        bootstrap = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")
        lock_guard = (ROOT / "scripts/lock_contract.py").read_text(encoding="utf-8")
        self.assertIn("lock_contract.py", bootstrap)
        self.assertIn("check_environment.py", bootstrap)
        self.assertIn('choices=("compile", "check")', lock_guard)
        self.assertNotIn('choices=("stamp", "check")', lock_guard)
        self.assertIn("generated_path.replace(lock_path)", lock_guard)

    def test_lock_stamp_rejects_a_changed_direct_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_requirements = Path(tmp)
            for name in (
                "runtime.in",
                "vision.in",
                "solver.in",
                "dev.in",
                "windows-py311.lock",
            ):
                shutil.copy2(ROOT / "requirements" / name, temporary_requirements / name)
            with (temporary_requirements / "runtime.in").open("a", encoding="utf-8") as stream:
                stream.write("\n# changed after lock generation\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/lock_contract.py"),
                    "check",
                    str(temporary_requirements / "windows-py311.lock"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("input digest is missing or stale", completed.stdout + completed.stderr)

    def test_bootstrap_rejects_a_non_311_interpreter(self) -> None:
        bootstrap = ROOT / "scripts/bootstrap.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            fake_python = Path(tmp) / "fake-python.cmd"
            fake_python.write_text("@echo 3.10\n", encoding="ascii")
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(bootstrap),
                    "-PythonExe",
                    str(fake_python),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        output = completed.stdout + completed.stderr
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("Python 3.11 is required", output)

    def test_bootstrap_never_deletes_an_existing_environment(self) -> None:
        bootstrap = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")
        self.assertNotIn("Remove-Item", bootstrap)


if __name__ == "__main__":
    unittest.main()
