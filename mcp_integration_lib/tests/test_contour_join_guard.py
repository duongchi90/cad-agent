"""Source-declared fillet connections must survive the packaged review caller."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent import cli
from cad_agent.live import LiveSafetyError, load_build_evidence, repair_live, write_build_evidence
from dxf_builder_lib.tests.dxf_test_support import build_fillet_join_fixture
from dxf_builder_lib.reviewer import review_dxf
from mcp_integration_lib.mcp_client import FakeMCPClient, MCPToolError
from mcp_integration_lib.reviewer2 import review_dxf_live




@pytest.mark.parametrize("radius,coupled,offset,want_exit", [
    (1.0, False, 0.0, 0), (1.1, False, 0.0, 1),
    (1.1, True, 0.0, 0), (1.1, False, 100_000_000.0, 1),
], ids=["nominal", "radius-only-open", "coupled-closed", "large-coordinate-open"])
def test_packaged_review_checks_declared_fillet_joins(
    tmp_path: Path, monkeypatch, radius, coupled, offset, want_exit,
):
    built = build_fillet_join_fixture(tmp_path, radius, coupled, offset)
    headless = review_dxf(built)
    assert headless.passed == (want_exit == 0)
    assert headless.contour_checked_count == 2
    if want_exit:
        assert any("open" in item for item in headless.contour_mismatches)
    evidence = tmp_path / "build-evidence.json"
    write_build_evidence(evidence, built)
    restored = load_build_evidence(evidence, Path(built.output_path))
    assert restored.contour_join_by_id == built.contour_join_by_id
    client = FakeMCPClient(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = built.written_geometry_by_primitive_id[pid]
        if geometry["type"] == "arc":
            geometry = dict(geometry, extrusion=(0.0, 0.0, 1.0))
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    before = Path(built.output_path).read_bytes(), evidence.read_bytes()
    report_path = tmp_path / "review.json"
    exit_code = cli.main([
        "mechanical-review", "--dxf", built.output_path,
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "transport.lsp"), "--report", str(report_path),
    ])
    review = json.loads(report_path.read_text(encoding="utf-8"))["review"]
    assert exit_code == want_exit
    assert review["passed"] == (want_exit == 0)
    assert review["contour_checked"] == 2
    assert review["geometry_checked"] == 3
    assert (Path(built.output_path).read_bytes(), evidence.read_bytes()) == before


def test_unreadable_declared_join_cannot_pass(tmp_path, monkeypatch):
    built = build_fillet_join_fixture(tmp_path, 1.0, False)
    class UnreadableArc(FakeMCPClient):
        def entity_get(self, handle):
            if handle == built.handle_by_primitive_id["fillet"]:
                raise MCPToolError("ARC unavailable")
            return super().entity_get(handle)
    client = UnreadableArc(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = built.written_geometry_by_primitive_id[pid]
        if geometry["type"] == "arc":
            geometry = dict(geometry, extrusion=(0.0, 0.0, 1.0))
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    evidence = tmp_path / "build-evidence.json"
    write_build_evidence(evidence, built)
    report_path = tmp_path / "review.json"
    assert cli.main([
        "mechanical-review", "--dxf", built.output_path,
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "transport.lsp"), "--report", str(report_path),
    ]) == 1
    review = json.loads(report_path.read_text(encoding="utf-8"))["review"]
    assert not review["passed"]
    assert review["geometry_degraded"]
    assert any("unavailable" in message for message in review["contour_mismatches"])


@pytest.mark.parametrize("arc_plane", [None, (0.0, 1.0, 0.0)], ids=["unknown-plane", "unsupported-plane"])
def test_native_join_needs_observed_supported_arc_plane(tmp_path, arc_plane):
    built = build_fillet_join_fixture(tmp_path, 1.0, False)
    client = FakeMCPClient(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = dict(built.written_geometry_by_primitive_id[pid])
        if pid == "fillet" and arc_plane is not None:
            geometry["extrusion"] = arc_plane
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    assert not review_dxf_live(built, client).passed


def test_structural_only_review_does_not_discharge_contour_obligations(tmp_path):
    built = build_fillet_join_fixture(tmp_path, 1.0, False)
    client = FakeMCPClient(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = dict(built.written_geometry_by_primitive_id[pid], extrusion=(0.0, 0.0, 1.0))
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    assert not review_dxf_live(built, client, attempt_geometry=False).passed


def test_open_plan_is_not_repaired_by_recreating_unchanged_entities(tmp_path):
    built = build_fillet_join_fixture(tmp_path, 1.1, False)
    # Deliberately collide the obligation ID with a primitive ID. A topology
    # verdict must not become a primitive erase/recreate instruction.
    built.contour_join_by_id["fillet"] = built.contour_join_by_id.pop("top-fillet")
    evidence = tmp_path / "evidence.json"
    write_build_evidence(evidence, built)
    client = FakeMCPClient(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = dict(built.written_geometry_by_primitive_id[pid], extrusion=(0.0, 0.0, 1.0))
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    before = Path(built.output_path).read_bytes(), evidence.read_bytes(), client.entity_list()
    backup = tmp_path / "backup"
    with pytest.raises(LiveSafetyError, match="CONTOUR_JOIN_REPAIR_UNSUPPORTED"):
        repair_live(built, client, Path(built.output_path), evidence, backup, "synthetic-approval")
    assert (Path(built.output_path).read_bytes(), evidence.read_bytes(), client.entity_list()) == before
    assert not backup.exists()


def test_legacy_review_does_not_infer_contour_connections(tmp_path):
    built = build_fillet_join_fixture(tmp_path, 1.1, False)
    built.contour_join_by_id.clear()
    assert review_dxf(built).passed


def test_malformed_loaded_obligation_is_nonpass(tmp_path):
    built = build_fillet_join_fixture(tmp_path, 1.0, False)
    built.contour_join_by_id["top-fillet"]["first"]["endpoint"] = "nearest"
    assert not review_dxf(built).passed


@pytest.mark.parametrize("layout", ["Layout1", None], ids=["paper-space", "unknown-space"])
def test_native_join_needs_observed_model_space(tmp_path, layout):
    built = build_fillet_join_fixture(tmp_path, 1.0, False)
    client = FakeMCPClient(fail_entity_get=False)
    for pid, handle in built.handle_by_primitive_id.items():
        geometry = dict(built.written_geometry_by_primitive_id[pid],
                        extrusion=(0.0, 0.0, 1.0), layout=layout if pid == "top" else "Model")
        geometry = dict(geometry, layout=geometry.get("layout", "Model"))
        client.preload_entity(handle, geometry["type"].upper(), built.layer_by_primitive_id[pid], geometry)
    review = review_dxf_live(built, client)
    assert not review.passed
    assert any("unavailable" in message for message in review.contour_mismatches)
