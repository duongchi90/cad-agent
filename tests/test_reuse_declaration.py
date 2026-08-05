from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_reuse_declaration.py"
TEMPLATE = ROOT / ".github/pull_request_template.md"
WORKFLOW = ROOT / ".github/workflows/reuse-declaration.yml"
REQUIRED = (
    "Existing capability inspected:",
    "Existing API reused:",
    "Adapter required:",
    "New capability genuinely missing:",
    "Files allowed to change:",
    "Files forbidden to duplicate:",
    "Compatibility behavior:",
    "Migration and rollback path:",
)


def _module():
    spec = importlib.util.spec_from_file_location("check_reuse_declaration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_only_change_is_exempt() -> None:
    module = _module()
    assert module.implementation_change(["docs/STATUS.md"]) is False


def test_runtime_contract_or_script_change_requires_declaration() -> None:
    module = _module()
    assert module.implementation_change(["cad_agent/cli.py"]) is True
    assert module.implementation_change(["contracts/autocad-ipc/request.schema.json"]) is True
    assert module.implementation_change(["scripts/verify.ps1"]) is True
    assert module.implementation_change([r".github\workflows\reuse-declaration.yml"]) is True
    assert module.implementation_change(["pyproject.toml"]) is True
    assert module.implementation_change([r"requirements\windows-py311.lock"]) is True


def test_complete_declaration_passes() -> None:
    module = _module()
    body = "\n".join(f"{section} value" for section in REQUIRED)
    assert module.REQUIRED_SECTIONS == REQUIRED
    assert module.missing_sections(body) == ()


def test_heading_without_value_is_missing() -> None:
    module = _module()
    body = "\n".join(REQUIRED)
    assert module.missing_sections(body) == REQUIRED


def test_indented_headings_are_checked_after_normalization() -> None:
    module = _module()
    body = "\n".join(f"- {section} value" for section in REQUIRED)
    assert module.missing_sections(body) == ()


def test_cli_accepts_complete_implementation_declaration(tmp_path: Path, capsys) -> None:
    module = _module()
    body_file = tmp_path / "body.txt"
    paths_file = tmp_path / "paths.txt"
    body_file.write_text("\n".join(f"{section} value" for section in REQUIRED), encoding="utf-8")
    paths_file.write_text("cad_agent/cli.py\n", encoding="utf-8")

    assert module.main(["--body-file", str(body_file), "--changed-files", str(paths_file)]) == 0
    assert "Reuse Declaration: PASS" in capsys.readouterr().out


def test_cli_rejects_missing_implementation_declaration(tmp_path: Path, capsys) -> None:
    module = _module()
    body_file = tmp_path / "body.txt"
    paths_file = tmp_path / "paths.txt"
    body_file.write_text("Existing API reused: value\n", encoding="utf-8")
    paths_file.write_text("cad_agent/cli.py\n", encoding="utf-8")

    assert module.main(["--body-file", str(body_file), "--changed-files", str(paths_file)]) == 2
    output = capsys.readouterr().out
    assert "Existing capability inspected:" in output
    assert "Migration and rollback path:" in output


def test_cli_exempts_docs_only_change(tmp_path: Path, capsys) -> None:
    module = _module()
    body_file = tmp_path / "body.txt"
    paths_file = tmp_path / "paths.txt"
    body_file.write_text("", encoding="utf-8")
    paths_file.write_text("docs/STATUS.md\n", encoding="utf-8")

    assert module.main(["--body-file", str(body_file), "--changed-files", str(paths_file)]) == 0
    assert "docs/non-implementation exemption" in capsys.readouterr().out


def test_cli_accepts_utf8_bom_input_files(tmp_path: Path, capsys) -> None:
    module = _module()
    body_file = tmp_path / "body.txt"
    paths_file = tmp_path / "paths.txt"
    body = "\n".join(f"{section} value" for section in REQUIRED)
    body_file.write_text("\ufeff" + body, encoding="utf-8")
    paths_file.write_text("\ufeffcad_agent/cli.py\n", encoding="utf-8")

    assert module.main(["--body-file", str(body_file), "--changed-files", str(paths_file)]) == 0
    assert "Reuse Declaration: PASS" in capsys.readouterr().out


def test_pull_request_template_contains_auditable_declaration() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    for section in REQUIRED:
        assert section in template
    assert "Not applicable: documentation only" in template
    assert "## Summary" in template
    assert "## Verification" in template


def test_workflow_matches_read_only_pull_request_gate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "name: reuse-declaration" in workflow
    assert "types: [opened, edited, synchronize, reopened]" in workflow
    assert "runs-on: windows-2025" in workflow
    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in workflow
    assert "fetch-depth: 0" in workflow
    assert "persist-credentials: false" in workflow
    assert "contents: read" in workflow
    assert 'origin/${{ github.base_ref }}...HEAD' in workflow
    assert "--body-file" in workflow
    assert "--changed-files" in workflow
    assert "secrets." not in workflow
    assert "contents: write" not in workflow
