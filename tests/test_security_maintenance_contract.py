from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEQL_SHA = "ff2f1c621b7f889edc0d3c761ac2e6a3f8cdb0dd"


def test_dependabot_monitors_locked_python_and_github_actions_dependencies() -> None:
    path = ROOT / ".github/dependabot.yml"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert 'package-ecosystem: "pip"' in content
    assert 'directory: "/requirements"' in content
    assert 'package-ecosystem: "github-actions"' in content
    assert 'directory: "/"' in content
    assert content.count('interval: "weekly"') == 2


def test_codeql_is_least_privilege_and_pinned_to_exact_action_commit() -> None:
    path = ROOT / ".github/workflows/codeql.yml"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "contents: read" in content
    assert "security-events: write" in content
    assert "language: python" in content
    assert f"github/codeql-action/init@{CODEQL_SHA}" in content
    assert f"github/codeql-action/analyze@{CODEQL_SHA}" in content
    assert not re.search(r"github/codeql-action/(?:init|analyze)@v\\d+", content)


def test_security_policy_requires_private_reporting_without_claiming_release_support() -> None:
    path = ROOT / "SECURITY.md"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    lowered = content.casefold()
    assert "do not post" in lowered
    assert "exploit" in lowered
    assert "private vulnerability reporting" in lowered
    assert "latest main development line" in lowered
