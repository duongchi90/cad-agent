"""A correct DIM value does not prove that it measures the declared LINE."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent import cli
from cad_agent.live import LiveSafetyError, repair_live, write_build_evidence
from dxf_builder_lib.reviewer import review_dxf
from dxf_builder_lib.tests.dxf_test_support import (
    build_dimension_feature_binding_fixture, build_fillet_dimension_fixture,
    build_native_dimension_consumer_fixture,
    translate_fixture_elevation_for_test,
)
from mcp_integration_lib.mcp_client import FakeMCPClient
from mcp_integration_lib.reviewer2 import review_dxf_live


@pytest.mark.parametrize("kind", ["line-dimension", "fillet-dimension"])
@pytest.mark.parametrize("elevation_mm", [0.0, 2.0])
def test_joint_native_elevation_preserves_relations_but_must_match_source(
    tmp_path, kind, elevation_mm,
):
    if kind == "line-dimension":
        built, _, _ = build_dimension_feature_binding_fixture(tmp_path)
    else:
        built, _ = build_fillet_dimension_fixture(tmp_path, 1.0, False, False)
    records = translate_fixture_elevation_for_test(built, elevation_mm)
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    before = Path(built.output_path).read_bytes()
    headless = review_dxf(built)
    live = review_dxf_live(built, client)
    # Incidence and measured-feature placement are still correct. The source
    # geometry check independently owns rejection of joint Z displacement.
    assert not headless.contour_mismatches
    assert not headless.dimension_mismatches
    assert not live.contour_mismatches
    assert not live.dimension_feature_mismatches
    assert live.passed == (elevation_mm == 0)
    assert headless.passed == (elevation_mm == 0)
    if elevation_mm:
        assert headless.mismatches and live.mismatches
    assert Path(built.output_path).read_bytes() == before


@pytest.mark.parametrize("shift,reverse,want_exit", [
    ((0, 0, 0), False, 0), ((0, 0, 0), True, 0),
    ((0, 25, 0), False, 1), ((0, 0, 2), False, 1),
    ((100_000_000, 0, 0), False, 1),
], ids=["bound", "reversed-equivalent", "other-parallel-feature", "different-elevation", "large-coordinate"])
def test_packaged_dimension_review_requires_declared_feature(
    tmp_path, monkeypatch, shift, reverse, want_exit,
):
    points = [(shift[0], shift[1], shift[2]), (80 + shift[0], shift[1], shift[2])]
    if reverse:
        points.reverse()
    built, records, measurement = build_dimension_feature_binding_fixture(tmp_path, points)
    assert measurement == 80
    headless = review_dxf(built)

    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    evidence = tmp_path / "evidence.json"
    write_build_evidence(evidence, built)
    candidate = Path(built.output_path)
    before = candidate.read_bytes(), evidence.read_bytes()
    report_path = tmp_path / "review.json"
    assert cli.main([
        "mechanical-review", "--dxf", str(candidate),
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "dispatcher.lsp"), "--report", str(report_path),
    ]) == want_exit
    result = json.loads(report_path.read_text(encoding="utf-8"))["review"]
    assert headless.passed == (want_exit == 0)
    assert result["passed"] == (want_exit == 0)
    if want_exit:
        assert any("feature" in item for item in result["dimension_feature_mismatches"])
    assert (candidate.read_bytes(), evidence.read_bytes()) == before


@pytest.mark.parametrize("change", ["paper", "unknown-line-space", "nonfinite", "angular", "missing-line", "structural-only"])
def test_dimension_feature_needs_actual_supported_readback(tmp_path, change):
    built, records, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    dim_handle = next(iter(built.dimension_handle_by_cross_validation_id.values()))
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        if handle == dim_handle:
            if change == "paper":
                geometry["layout"] = "Layout1"
            elif change == "nonfinite":
                geometry["defpoint2"] = (float("nan"), 0, 0)
            elif change == "angular":
                geometry["dimtype"] = 34
        elif change == "missing-line":
            continue
        elif change == "unknown-line-space":
            geometry.pop("layout")
        client.preload_entity(handle, entity_type, layer, geometry)
    result = review_dxf_live(built, client, attempt_geometry=change != "structural-only")
    assert not result.passed
    assert any("feature binding" in item for item in result.dimension_feature_mismatches)


@pytest.mark.parametrize("dimtype,want_pass", [
    (0, True), (1, True), (32, True), (33, True),
    (128, True), (129, True), (160, True), (161, True),
    (34, False), (35, False), (36, False), (37, False), (38, False),
    (64, False), (65, False), (96, False), (97, False), (256, False),
    (-1, False), (True, False),
], ids=["rotated", "aligned", "rotated-block-bit", "aligned-block-bit",
        "rotated-moved-text", "aligned-moved-text", "rotated-block-moved-text", "aligned-block-moved-text",
        "angular", "diameter", "radius", "angular-three-point", "ordinate",
        "invalid-ordinate-flag-rotated", "invalid-ordinate-flag-aligned",
        "invalid-block-ordinate-flag-rotated", "invalid-block-ordinate-flag-aligned", "unknown-high-bit",
        "invalid-negative", "invalid-boolean"])
def test_measured_feature_binding_rejects_other_native_dimension_types(tmp_path, dimtype, want_pass):
    # External native transport only is replayed; the real reviewer decides.
    built, records, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        if entity_type == "DIMENSION":
            geometry["dimtype"] = dimtype
        client.preload_entity(handle, entity_type, layer, geometry)
    result = review_dxf_live(built, client)
    assert result.passed == want_pass
    assert bool(result.dimension_feature_mismatches) == (not want_pass)


@pytest.mark.parametrize("dimtype,want_pass", [
    (128, True), (129, True), (160, True), (161, True),
    (64, False), (65, False), (96, False), (97, False), (256, False),
])
def test_saved_dimension_type_flags_cannot_discharge_wrong_native_type(tmp_path, dimtype, want_pass):
    built, records, measurement = build_dimension_feature_binding_fixture(tmp_path, dimtype=dimtype)
    assert measurement == 80
    headless = review_dxf(built)
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    live = review_dxf_live(built, client)
    assert headless.passed == want_pass
    assert live.passed == want_pass
    assert bool(live.dimension_feature_mismatches) == (not want_pass)


def test_legacy_unbound_dimension_does_not_acquire_feature_obligation(tmp_path):
    built, records, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    for expected in built.written_dimension_by_cross_validation_id.values():
        expected.pop("geometry_primitive_id")
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    assert review_dxf_live(built, client, attempt_geometry=False).passed


@pytest.mark.parametrize("missing", ["dimtype", "defpoint2", "defpoint3", "layout"])
def test_bound_dimension_unreadable_definition_cannot_pass(tmp_path, monkeypatch, missing):
    built, _, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    dim_handle = next(iter(built.dimension_handle_by_cross_validation_id.values()))
    client = FakeMCPClient(fail_entity_get=False)
    client.preload_entity(built.handle_by_primitive_id["line"], "LINE", "UNCLASSIFIED", {
        "start": (0, 0, 0), "end": (80, 0, 0), "layout": "Model",
    })
    definition = {"measurement": 80, "dimtype": 32, "defpoint2": (0, 0, 0),
                  "defpoint3": (80, 0, 0), "layout": "Model"}
    definition.pop(missing)
    client.preload_entity(dim_handle, "DIMENSION", "DIMENSIONS", definition)
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    evidence = tmp_path / "evidence.json"
    write_build_evidence(evidence, built)
    report = tmp_path / "review.json"
    assert cli.main([
        "mechanical-review", "--dxf", built.output_path,
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "dispatcher.lsp"), "--report", str(report),
    ]) == 1
    result = json.loads(report.read_text(encoding="utf-8"))["review"]
    assert any("feature" in item for item in result["dimension_feature_mismatches"])


def test_dimension_id_collision_cannot_erase_referenced_line(tmp_path):
    built, records, _ = build_native_dimension_consumer_fixture(tmp_path, 80, 80, "")
    built.dimension_handle_by_cross_validation_id["line"] = built.dimension_handle_by_cross_validation_id.pop("exact")
    built.written_dimension_by_cross_validation_id["line"] = built.written_dimension_by_cross_validation_id.pop("exact")
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        if entity_type == "DIMENSION":
            geometry["defpoint2"], geometry["defpoint3"] = (0, 25, 0), (80, 25, 0)
        client.preload_entity(handle, entity_type, layer, geometry)
    candidate = Path(built.output_path)
    evidence = tmp_path / "evidence.json"
    write_build_evidence(evidence, built)
    before = candidate.read_bytes(), evidence.read_bytes(), client.entity_list(), dict(built.handle_by_primitive_id)
    backup = tmp_path / "backup"
    with pytest.raises(LiveSafetyError, match="DIMENSION_FEATURE_REPAIR_UNSUPPORTED"):
        repair_live(built, client, candidate, evidence, backup, "synthetic-approval")
    assert (candidate.read_bytes(), evidence.read_bytes(), client.entity_list(), built.handle_by_primitive_id) == before
    assert not backup.exists()


@pytest.mark.parametrize("radius,coupled,wrong_dimension,want_pass,want_contour", [
    (1.0, False, False, True, False), (1.1, False, False, False, True),
    (1.1, True, True, False, False),
], ids=["both-proven", "open-contour-correct-dim", "closed-contour-wrong-dim"])
def test_one_candidate_must_satisfy_both_contour_and_dimension_obligations(
    tmp_path, radius, coupled, wrong_dimension, want_pass, want_contour,
):
    built, records = build_fillet_dimension_fixture(tmp_path, radius, coupled, wrong_dimension)
    headless = review_dxf(built)
    assert headless.passed == want_pass
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    review = review_dxf_live(built, client)
    assert review.passed == want_pass
    assert review.dimension_checked == 1
    assert review.contour_checked == 2
    assert bool(review.contour_mismatches) == want_contour
    assert bool(review.dimension_feature_mismatches) == wrong_dimension
