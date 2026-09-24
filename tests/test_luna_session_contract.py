from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs/LUNA_SESSION_RUNBOOK.md"
TEMPLATE = ROOT / "docs/templates/luna-resume-state.json"
FIELDS = (
    "GOAL",
    "CURRENT_MAIN",
    "CURRENT_HEAD",
    "ACTIVE_PR",
    "DONE",
    "ACCEPTED_EVIDENCE_REFS",
    "FIRST_UNSATISFIED_BOUNDARY",
    "CURRENT_RISK",
    "ACTIVE_WRITESET",
    "LIVE_LOCK_STATE",
    "UNACKED_CURRENT_ADVISORIES",
    "NEXT_ACTION",
)


def test_runbook_routes_through_canonical_owners() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for target in (
        "PROJECT.md",
        "ARCHITECTURE.md",
        "STATUS.md",
        "QUALITY.md",
        "AI_OPERATING_MODEL.md",
        "superpowers/specs/2026-09-24-luna-session-portable-runbook-design.md",
        "superpowers/plans/2026-09-24-luna-session-portable-runbook.md",
    ):
        assert f"]({target})" in text
    for path in (
        "scripts/bootstrap.ps1",
        "scripts/verify.ps1",
        "autocad_plugin/CadAgent.AutoCAD2027.sln",
        "mcp_integration_lib/mcp_dispatch.lsp",
    ):
        assert path in text


def test_runbook_keeps_cad_load_manual_and_reports_unavailable_gates_truthfully() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for instruction in ("NETLOAD", "APPLOAD", "Load Once", "CADAGENT_HEALTH"):
        assert instruction in text
    for state in ("BLOCKER", "SKIP", "NOT RUN"):
        assert state in text
    assert "Never run `NETLOAD`, `APPLOAD`, `Load Once`, or `CADAGENT_HEALTH`" in text
    assert "accepted/source drawing" in text.lower()


def test_resume_template_contains_only_blank_canonical_305_fields() -> None:
    state = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert tuple(state) == FIELDS
    assert all(value == "" for value in state.values())


def test_agents_routes_luna_operators_to_the_runbook() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "[Luna session runbook](docs/LUNA_SESSION_RUNBOOK.md)" in text
