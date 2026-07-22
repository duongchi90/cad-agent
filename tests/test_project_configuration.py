from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "pyproject.toml").open("rb") as stream:
            cls.config = tomllib.load(stream)

    def test_supported_environment_is_exact(self) -> None:
        self.assertEqual(">=3.11,<3.12", self.config["project"]["requires-python"])
        environment = self.config["tool"]["cad_agent"]
        self.assertEqual("windows", environment["supported_os"])
        self.assertEqual("3.11", environment["supported_python"])
        self.assertEqual("AutoCAD LT", environment["supported_autocad"])
        self.assertEqual("5.4.0.20240606", environment["tesseract_version"])

    def test_pytest_registers_specialized_gates_and_errors_on_warnings(self) -> None:
        pytest_config = self.config["tool"]["pytest"]["ini_options"]
        marker_names = {entry.split(":", 1)[0] for entry in pytest_config["markers"]}
        self.assertEqual({"real_data", "autocad_lt"}, marker_names)
        self.assertIn("--strict-markers", pytest_config["addopts"])
        self.assertEqual(["error"], pytest_config["filterwarnings"])

    def test_ruff_scope_remains_the_existing_f401_gate(self) -> None:
        self.assertEqual("py311", self.config["tool"]["ruff"]["target-version"])
        self.assertEqual(["F401"], self.config["tool"]["ruff"]["lint"]["select"])


if __name__ == "__main__":
    unittest.main()
