from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from cad_agent.cli import build_parser
from cad_agent.manifest import read_manifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_cli_contract.py"
BASELINE = ROOT / "contracts/reuse-integration/legacy-cli-baseline.json"
LEGACY_MANIFEST = ROOT / "tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json"


def _module():
    spec = importlib.util.spec_from_file_location("export_cli_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_parser_preserves_the_committed_cli_contract() -> None:
    module = _module()
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert module.parser_contract(build_parser()) == expected


def test_current_contract_keeps_all_legacy_and_existing_fidelity_commands() -> None:
    module = _module()
    commands = module.parser_contract(build_parser())["commands"]
    expected = {
        "doctor",
        "run",
        "resume",
        "run-pdf",
        "resume-pdf",
        "drawing-setup-plan",
        "drawing-setup-audit",
        "drawing-setup-verify",
        "dimension-pilot-run",
        "mechanical-review",
        "mechanical-repair",
        "fidelity-pdf",
        "fidelity-overlay",
        "fidelity-region-proposal",
        "fidelity-region-approve",
        "fidelity-reconstruct",
        "fidelity-observe",
        "fidelity-text-observe",
        "fidelity-table-text-observe",
        "fidelity-table-text-approve",
        "fidelity-table-text-reconstruct",
        "fidelity-dimension-observe",
        "fidelity-dimension-reconstruct",
        "fidelity-hatch-observe",
        "fidelity-hatch-approve",
        "fidelity-hatch-reconstruct",
        "fidelity-dimension-review-index",
        "fidelity-linetype-reconstruct",
        "fidelity-text-approve",
        "fidelity-text-review-index",
        "fidelity-text-approve-selection",
        "fidelity-text-reconstruct",
        "fidelity-compose",
        "fidelity-promote",
        "fidelity-mechanical-review",
        "fidelity-review-index",
        "fidelity-review-queue",
    }
    assert expected <= set(commands)


def test_legacy_run_manifest_remains_readable_with_safe_defaults() -> None:
    manifest = read_manifest(LEGACY_MANIFEST)
    assert manifest["schema_version"] == "1.0"
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None


def test_legacy_fixture_omits_new_release_fields() -> None:
    payload = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
    assert "release_profile" not in payload
    assert "authoritative_release_eligible" not in payload
    assert "drawing_setup_evidence" not in payload


def test_exporter_cli_runs_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "legacy-cli-baseline-1.0"
