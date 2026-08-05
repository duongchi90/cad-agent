from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/superpowers/reuse/2026-08-04-reuse-inventory.json"
SCRIPT = ROOT / "scripts/reuse_inventory.py"

REQUIRED = {
    "image-pdf-recognition",
    "semantic-parts-constraints",
    "ambiguity-proposal-apply",
    "native-dxf-generation",
    "headless-review-repair",
    "autocad-file-ipc",
    "autocad-repair",
    "run-manifest-checkpoint-resume",
    "drawing-setup",
    "dimension-pilot",
    "vs-t1-dimension-observer",
    "vs-t2-geometry-comparator",
    "vs-t3-evidence-exporter",
    "source-bundle-fusion",
    "exact-base-component-extraction",
    "component-view-registry",
    "candidate-revision-synchronization",
    "independent-visual-verdict",
    "codex-repair-planning",
    "verified-promotion",
}


def _module():
    spec = importlib.util.spec_from_file_location("reuse_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_inventory_is_complete_and_path_valid() -> None:
    module = _module()
    inventory = module.read_inventory(INVENTORY)
    module.validate_against_repository(inventory, ROOT)
    ids = {item["capability_id"] for item in inventory["capabilities"]}
    assert ids == REQUIRED


def test_every_new_capability_names_inspected_existing_boundaries() -> None:
    module = _module()
    inventory = module.read_inventory(INVENTORY)
    for item in inventory["capabilities"]:
        if item["classification"] == "NEW_MISSING_CAPABILITY":
            assert item["inspected_paths"]
            assert item["gap_reason"]
            assert all(path != item["current_owner"] for path in item["inspected_paths"])


def test_required_capability_ids_are_exposed_by_validator() -> None:
    module = _module()
    assert module.REQUIRED_CAPABILITY_IDS == REQUIRED


def test_cli_rejects_an_inventory_with_incomplete_capability_set(tmp_path: Path) -> None:
    module = _module()
    source = ROOT / "contracts/reuse-integration/examples/reuse-inventory.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    inventory = tmp_path / "incomplete.json"
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    try:
        module.main(["check", str(inventory), "--repo-root", str(ROOT)])
    except ValueError as exc:
        assert "capability set mismatch" in str(exc)
    else:
        raise AssertionError("incomplete inventory was accepted")
