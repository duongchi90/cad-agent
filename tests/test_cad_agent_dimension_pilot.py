from __future__ import annotations

import json
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import cad_agent.dimension_pilot as dimension_pilot
from cad_agent.dimension_pilot import (
    DimensionPilotError,
    run_dimension_pilot,
    write_dimension_evidence,
)
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.manifest import sha256_file
from dxf_builder_lib.reviewer import ReviewResult
from dimension_pilot_fixtures import (
    offline_dimension_evidence,
    rebind_artifact_hashes,
    write_dimension_pilot_inputs,
)


def run_with(inputs: SimpleNamespace):
    return run_dimension_pilot(
        plan=inputs.plan,
        setup_plan=inputs.setup_plan,
        setup_evidence=inputs.setup_evidence,
        source_path=inputs.source,
        primitive_ir_path=inputs.primitive_ir,
        semantic_ir_path=inputs.semantic_ir,
        output_dxf=inputs.output_dxf,
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_pilot_refuses_before_build_when_setup_is_not_verified(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.setup_evidence["status"] = "NEEDS_REVIEW"
    inputs.setup_evidence["blockers"] = [
        {
            "code": "setup_incomplete",
            "path": "$.styles.dimension",
            "expected": "VX_DIM_20",
            "actual": None,
            "severity": "error",
        }
    ]
    inputs.plan["setup"]["evidence_sha256"] = canonical_json_sha256(
        inputs.setup_evidence
    )

    run = run_with(inputs)

    assert run.build_result is None
    assert not inputs.output_dxf.exists()
    assert [item["code"] for item in run.evidence["blockers"]] == [
        "setup_incomplete"
    ]
    assert run.evidence["acceptance"] == "NOT_RUN"


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("source", "source_changed"),
        ("primitive_ir", "primitive_ir_changed"),
        ("semantic_ir", "semantic_ir_changed"),
    ],
)
def test_changed_hash_refuses_before_solver(
    tmp_path: Path,
    field: str,
    code: str,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    getattr(inputs, field).write_bytes(b"changed")

    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [code]
    assert run.evidence["solver"]["status"] == "not_run"
    assert run.build_result is None


def test_unresolved_attachment_and_missing_constraint_fail_closed(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.plan["dimensions"][0]["from"]["primitive_id"] = "missing-line"
    inputs.plan["dimensions"][0]["to"]["primitive_id"] = "missing-line"
    inputs.plan["constraint_ids"] = ["missing-constraint"]

    run = run_with(inputs)

    assert {item["code"] for item in run.evidence["blockers"]} == {
        "attachment_unresolved",
        "constraint_missing",
    }
    assert run.build_result is None


def test_matching_file_hashes_do_not_bypass_source_provenance(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    primitive = json.loads(inputs.primitive_ir.read_text(encoding="utf-8"))
    primitive["source_document"]["sha256"] = "0" * 64
    _write_json(inputs.primitive_ir, primitive)
    rebind_artifact_hashes(inputs)

    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [
        "source_provenance_mismatch"
    ]
    assert run.build_result is None


def test_matching_file_hashes_do_not_bypass_primitive_provenance(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    semantic = json.loads(inputs.semantic_ir.read_text(encoding="utf-8"))
    semantic["primitive_ir_ref"]["sha256"] = "0" * 64
    _write_json(inputs.semantic_ir, semantic)
    inputs.plan["semantic_ir_sha256"] = sha256_file(inputs.semantic_ir)

    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [
        "primitive_provenance_mismatch"
    ]
    assert run.build_result is None


def test_datum_attachment_must_match_approved_origin(tmp_path: Path) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.plan["datum"]["origin_mm"] = [5.0, 0.0]

    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [
        "datum_mismatch"
    ]
    assert run.build_result is None


def test_closed_dimension_pilot_builds_and_reads_native_dimension(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)

    run = run_with(inputs)

    assert run.evidence["offline_passed"] is True
    assert run.evidence["acceptance"] == "NOT_RUN"
    assert run.evidence["blockers"] == []
    assert run.evidence["solver"]["status"] == "okay"
    assert run.evidence["solver"]["model_dof"] == 0
    assert inputs.output_dxf.is_file()
    measurement = run.evidence["measurements"][0]
    assert measurement["dimension_id"] == "DIM-001"
    assert measurement["approved_value_mm"] == 80.0
    assert measurement["readback_value_mm"] == pytest.approx(80.0)
    assert measurement["residual_mm"] <= 0.1


def test_rotated_datum_is_solved_locally_and_written_in_world_frame(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    primitive = json.loads(inputs.primitive_ir.read_text(encoding="utf-8"))
    primitive["primitives"][0]["geometry"]["start"] = {"x": 10.0, "y": 20.0}
    primitive["primitives"][0]["geometry"]["end"] = {"x": 10.0, "y": 120.0}
    _write_json(inputs.primitive_ir, primitive)
    inputs.plan["datum"]["origin_mm"] = [10.0, 20.0]
    inputs.plan["datum"]["x_axis"] = [0.0, 1.0]
    inputs.plan["datum"]["y_axis"] = [-1.0, 0.0]
    rebind_artifact_hashes(inputs)

    run = run_with(inputs)

    assert run.evidence["offline_passed"] is True
    written = run.build_result.written_geometry_by_primitive_id["line-1"]
    assert written["start"] == pytest.approx((10.0, 20.0))
    assert written["end"] == pytest.approx((10.0, 100.0))


def test_underconstrained_or_conflicting_model_never_builds(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path, disconnected=True)
    run = run_with(inputs)
    assert not run.evidence["offline_passed"]
    assert "underconstrained" in {
        item["code"] for item in run.evidence["blockers"]
    }
    assert not inputs.output_dxf.exists()


def test_unreferenced_line_never_enters_a_closed_pilot_build(
    tmp_path: Path,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    primitive = json.loads(inputs.primitive_ir.read_text(encoding="utf-8"))
    rogue = copy.deepcopy(primitive["primitives"][0])
    rogue["id"] = "rogue-line"
    rogue["geometry"]["start"] = {"x": 0.0, "y": 500.0}
    rogue["geometry"]["end"] = {"x": 999.0, "y": 500.0}
    primitive["primitives"].append(rogue)
    _write_json(inputs.primitive_ir, primitive)
    rebind_artifact_hashes(inputs)

    run = run_with(inputs)

    assert run.build_result is None
    assert "underconstrained" in {
        item["code"] for item in run.evidence["blockers"]
    }
    assert not inputs.output_dxf.exists()


def test_primitive_ir_change_during_load_is_refused(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    original_load = dimension_pilot._load_models

    def mutate_then_load(primitive_path, semantic_path):
        primitive = json.loads(inputs.primitive_ir.read_text(encoding="utf-8"))
        primitive["primitives"][0]["geometry"]["end"]["x"] = 120.0
        _write_json(inputs.primitive_ir, primitive)
        return original_load(primitive_path, semantic_path)

    monkeypatch.setattr(dimension_pilot, "_load_models", mutate_then_load)
    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [
        "primitive_ir_changed"
    ]
    assert run.build_result is None


def test_ir_loader_receives_immutable_snapshots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    original_load = dimension_pilot._load_models

    def assert_bytes_then_load(primitive_payload, semantic_payload):
        assert isinstance(primitive_payload, bytes)
        assert isinstance(semantic_payload, bytes)
        return original_load(primitive_payload, semantic_payload)

    monkeypatch.setattr(dimension_pilot, "_load_models", assert_bytes_then_load)
    run = run_with(inputs)

    assert run.evidence["offline_passed"] is True


def test_semantic_ir_change_during_load_is_refused(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    original_load = dimension_pilot._load_models

    def mutate_then_load(primitive_path, semantic_path):
        semantic = json.loads(inputs.semantic_ir.read_text(encoding="utf-8"))
        semantic["schema_version"] = "mutated-during-run"
        _write_json(inputs.semantic_ir, semantic)
        return original_load(primitive_path, semantic_path)

    monkeypatch.setattr(dimension_pilot, "_load_models", mutate_then_load)
    run = run_with(inputs)

    assert [item["code"] for item in run.evidence["blockers"]] == [
        "semantic_ir_changed"
    ]
    assert run.build_result is None


def test_dxf_changed_during_review_cannot_receive_offline_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)

    def tamper_then_pass(built, **_kwargs):
        Path(built.output_path).write_bytes(b"tampered-after-build")
        return ReviewResult(
            passed=True,
            checked_count=1,
            dimension_checked_count=1,
            dimension_measurement_by_id={"DIM-001": 80.0},
        )

    monkeypatch.setattr(dimension_pilot, "review_dxf", tamper_then_pass)
    run = run_with(inputs)

    assert run.evidence["offline_passed"] is False
    assert run.evidence["dxf_sha256"] is None
    assert "headless_review_failed" in {
        item["code"] for item in run.evidence["blockers"]
    }


def test_dxf_publish_refuses_a_concurrent_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    original_build = dimension_pilot.build_dxf

    def compete_then_build(document, output_path, **kwargs):
        inputs.output_dxf.write_bytes(b"sentinel")
        return original_build(document, output_path, **kwargs)

    monkeypatch.setattr(dimension_pilot, "build_dxf", compete_then_build)

    with pytest.raises(DimensionPilotError, match="already exists"):
        run_with(inputs)
    assert inputs.output_dxf.read_bytes() == b"sentinel"


def test_dxf_changed_after_review_hash_cannot_receive_offline_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    original_rename = dimension_pilot.os.rename

    def tamper_then_publish(source, destination):
        Path(source).write_bytes(b"tampered-after-review-hash")
        return original_rename(source, destination)

    monkeypatch.setattr(dimension_pilot.os, "rename", tamper_then_publish)

    with pytest.raises(DimensionPilotError, match="published DXF changed"):
        run_with(inputs)
    assert not inputs.output_dxf.exists()


    inputs = write_dimension_pilot_inputs(tmp_path / "conflict", conflicting=True)
    run = run_with(inputs)
    assert "solver_conflict" in {
        item["code"] for item in run.evidence["blockers"]
    }
    assert set(run.evidence["solver"]["conflict_ids"]) >= {
        "DIM-001",
        "DIM-002",
    }
    assert not inputs.output_dxf.exists()


def test_failed_headless_review_never_records_dxf_hash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    monkeypatch.setattr(
        dimension_pilot,
        "review_dxf",
        lambda *_args, **_kwargs: ReviewResult(
            passed=False,
            checked_count=1,
            mismatches=["tampered"],
            dimension_measurement_by_id={"DIM-001": 80.0},
        ),
    )

    run = run_with(inputs)

    assert run.evidence["offline_passed"] is False
    assert run.evidence["dxf_sha256"] is None
    assert [item["code"] for item in run.evidence["blockers"]] == [
        "headless_review_failed"
    ]


def test_evidence_writer_is_validated_atomic_and_non_overwriting(
    tmp_path: Path,
) -> None:
    output = tmp_path / "evidence.json"
    payload = offline_dimension_evidence()

    write_dimension_evidence(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert output.read_text(encoding="utf-8").find('"acceptance"') < output.read_text(
        encoding="utf-8"
    ).find('"schema_version"')
    with pytest.raises(DimensionPilotError, match="already exists"):
        write_dimension_evidence(output, payload)
