from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md"
ARCHITECTURE = ROOT / "docs/ARCHITECTURE.md"
STATUS = ROOT / "docs/STATUS.md"
OLD_ROLLOUT = ROOT / "docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md"


def test_rebaseline_audit_records_required_future_plan_queue() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    for section in (
        "## 1. Audit identity and exact base SHA",
        "## 2. Inventory validation command and result",
        "## 3. Existing capability ownership map",
        "## 4. Reuse classifications and reasons",
        "## 5. Genuine missing capabilities",
        "## 6. Compatibility baseline",
        "## 7. Architecture-ratchet baseline",
        "## 8. Risks and rollback",
        "## 9. Locked future plan queue",
        "## 10. Gates not run",
    ):
        assert section in text
    for marker in (
        "R0 Reuse Integration Rebaseline",
        "S1 Codex SDK Windows compatibility spike",
        "S2 AutoCAD-native render/plot evidence spike",
        "S3 Exact-base Xref extraction spike",
        "R1 Source Bundle and Fusion Adapter",
        "R2 Base CAD Adapter",
        "R3 Component/View Registry",
        "R4 Candidate Revision Orchestrator",
        "R5 Visual Supervisor Adapter",
        "R6 Repair Executor Adapter",
        "R7 Verified Publisher",
        "R8 Synthetic and real pilots",
    ):
        assert marker in text
    queue = text.split("## 9. Locked future plan queue", 1)[1].split(
        "## 10. Gates not run", 1
    )[0]
    ordered_markers = (
        "R0 Reuse Integration Rebaseline",
        "S1 Codex SDK Windows compatibility spike",
        "S2 AutoCAD-native render/plot evidence spike",
        "S3 Exact-base Xref extraction spike",
        "R1 Source Bundle and Fusion Adapter",
        "R2 Base CAD Adapter",
        "R3 Component/View Registry",
        "R4 Candidate Revision Orchestrator",
        "R5 Visual Supervisor Adapter",
        "R6 Repair Executor Adapter",
        "R7 Verified Publisher",
        "R8 Synthetic and real pilots",
    )
    assert [queue.index(marker) for marker in ordered_markers] == sorted(
        queue.index(marker) for marker in ordered_markers
    )
    for evidence_path in (
        "docs/superpowers/reuse/2026-08-04-reuse-inventory.json",
        "contracts/reuse-integration/legacy-cli-baseline.json",
        "contracts/reuse-integration/architecture-boundaries.json",
        "docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md",
        "docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md",
    ):
        assert evidence_path in text
    assert "does not authorize runtime work" in text


def test_old_rollout_is_explicitly_superseded_after_vs_t3() -> None:
    text = OLD_ROLLOUT.read_text(encoding="utf-8")
    assert "Superseded after VS-T3" in text
    assert "Do not execute VS-T4 through VS-T8 unchanged" in text
    for historical_marker in (
        "### VS-T0",
        "### VS-T4",
        "### VS-T8",
        "Program verification policy",
        "Program completion criteria",
    ):
        assert historical_marker in text


def test_architecture_and_status_reference_the_reuse_inventory() -> None:
    inventory_path = "docs/superpowers/reuse/2026-08-04-reuse-inventory.json"
    assert inventory_path in ARCHITECTURE.read_text(encoding="utf-8")
    status = STATUS.read_text(encoding="utf-8")
    assert inventory_path in status
    assert "State: **Executing**" in status
    assert "Private-data gate: **NOT RUN**" in status
    assert "AutoCAD Mechanical live gate: **NOT RUN**" in status
    assert "Codex SDK spike: **NOT RUN**" in status
