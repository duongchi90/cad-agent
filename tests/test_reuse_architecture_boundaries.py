from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_architecture_boundaries.py"
BASELINE = ROOT / "contracts/reuse-integration/architecture-boundaries.json"


def _module():
    spec = importlib.util.spec_from_file_location("check_architecture_boundaries", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tracked_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    return repo


def test_repository_has_no_unbaselined_architecture_violation() -> None:
    module = _module()
    baseline = module.read_baseline(BASELINE)
    assert baseline["base_sha"] == "db91f3585f20984b7892454b3a5f9a6d2c32a567"
    current = set(module.collect_violations(ROOT))
    assert current == set(baseline["accepted_existing_violations"])


def test_reserved_duplicate_package_names_fail() -> None:
    module = _module()
    assert module.reserved_duplicate_name("new_ocr_engine") is True
    assert module.reserved_duplicate_name("parallel_dxf_builder") is True
    assert module.reserved_duplicate_name("second_manifest_store") is True
    assert module.reserved_duplicate_name("source_fusion_adapter") is False


def test_scanner_detects_each_boundary_rule_in_tracked_sources(tmp_path: Path) -> None:
    module = _module()
    repo = _tracked_repo(
        tmp_path,
        {
            "other/new_ocr_engine.py": "import cv2\n",
            "other/dxf_io.py": "import ezdxf\n",
            "other/autocad_api.cs": "using Autodesk.AutoCAD.DatabaseServices;\n",
            "other/mcp_client.py": "import mcp_integration_lib.mcp_client\n",
            "other/manifest_store.py": "MANIFEST_STORE = {}\n",
        },
    )
    violations = set(module.collect_violations(repo))
    assert any(item.startswith("DUPLICATE_PACKAGE_NAME:") for item in violations)
    assert any(item.startswith("DIRECT_OCR_IMPORT_OUTSIDE_PRIMITIVE_OWNER:") for item in violations)
    assert any(item.startswith("DIRECT_DXF_WRITE_OUTSIDE_DXF_BUILDER:") for item in violations)
    assert any(item.startswith("AUTOCAD_API_OUTSIDE_PLUGIN:") for item in violations)
    assert any(item.startswith("AUTOCAD_TRANSPORT_OUTSIDE_APPROVED_BOUNDARY:") for item in violations)
    assert any(item.startswith("SECOND_TRUTH_STORE_NAME:") for item in violations)
    assert tuple(sorted(violations)) == module.collect_violations(repo)


def test_scanner_ignores_untracked_sources_and_allows_approved_boundaries(tmp_path: Path) -> None:
    module = _module()
    repo = _tracked_repo(
        tmp_path,
        {
            "primitive_ir_lib/recognition.py": "import cv2\nimport pytesseract\n",
            "dxf_builder_lib/writer.py": "import ezdxf\n",
            "mcp_integration_lib/transport.py": "import mcp_integration_lib.mcp_client\n",
            "contracts/autocad-ipc/transport.py": "import mcp_integration_lib.mcp_client\n",
            "autocad_plugin/Reader.cs": "using Autodesk.AutoCAD.DatabaseServices;\n",
        },
    )
    untracked = repo / "outside/ocr_engine.py"
    untracked.parent.mkdir()
    untracked.write_text("import cv2\n", encoding="utf-8")
    assert module.collect_violations(repo) == ()


def test_snapshot_command_writes_closed_baseline(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "snapshot",
            "--repo-root",
            str(ROOT),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema_version",
        "base_sha",
        "accepted_existing_violations",
    }
    assert payload["schema_version"] == "architecture-boundaries-1.0"
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert payload["base_sha"] == head
    assert payload["accepted_existing_violations"] == sorted(
        payload["accepted_existing_violations"]
    )


def test_check_command_blocks_a_violation_not_in_the_baseline(tmp_path: Path) -> None:
    repo = _tracked_repo(tmp_path, {"other/new_ocr_engine.py": "import cv2\n"})
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": "architecture-boundaries-1.0",
                "base_sha": "0" * 40,
                "accepted_existing_violations": [],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "check",
            "--repo-root",
            str(repo),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "New architecture boundary violations (blockers):" in result.stdout
