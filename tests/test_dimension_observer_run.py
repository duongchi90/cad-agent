from __future__ import annotations

import json
from pathlib import Path

import pytest

import cad_agent.dimension_observer_run as dimension_observer_run
from cad_agent.dimension_observer_run import DimensionObserverRunError, run_dimension_observer
from cad_agent.manifest import sha256_file
from cad_agent.visual_contracts import read_visual_contract
from primitive_ir_lib.tests.dimension_test_helpers import (
    fake_ocr_4500,
    horizontal_dimension_cluster,
    matching_horizontal_anchors,
    write_synthetic_dimension_page,
)


def test_runner_writes_validated_hash_bound_register(tmp_path: Path) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    register_path = run_dimension_observer(
        run_id="RUN-VS-T1-001",
        source_image=source,
        page_id="PAGE-001",
        view_id="SIDE",
        output_dir=tmp_path / "run",
        ocr_reader=fake_ocr_4500,
    )
    register = read_visual_contract(register_path, contract="dimension_register")
    assert register["source_sha256"] == sha256_file(source)
    evidence = json.loads((register_path.parent / "observer-evidence.json").read_text(encoding="utf-8"))
    assert evidence["semantic_anchors_sha256"] is None
    assert evidence["profile_sha256"] is None


def _write_snapshot_inputs(tmp_path: Path) -> tuple[Path, Path]:
    anchors = tmp_path / "anchors.json"
    anchors.write_text(json.dumps({"anchors": matching_horizontal_anchors()}), encoding="utf-8")
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "schema_version": "dimension-observer-profile-1.0",
        "default_unit": "mm",
        "clusters": {
            "DIMCLUSTER-001": {
                "role": "REFERENCE",
                "critical": False,
                "blocker_scope": [],
            },
        },
    }), encoding="utf-8")
    return anchors, profile


def test_runner_records_exact_anchor_and_profile_snapshot_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    anchors, profile = _write_snapshot_inputs(tmp_path)
    monkeypatch.setattr(
        dimension_observer_run,
        "detect_dimension_clusters",
        lambda image: [horizontal_dimension_cluster()],
    )

    register_path = run_dimension_observer(
        run_id="RUN-VS-T1-SNAPSHOTS",
        source_image=source,
        page_id="PAGE-001",
        view_id="SIDE",
        output_dir=tmp_path / "run",
        semantic_anchors_path=anchors,
        profile_path=profile,
        ocr_reader=fake_ocr_4500,
    )

    evidence = json.loads((register_path.parent / "observer-evidence.json").read_text(encoding="utf-8"))
    assert evidence["source_sha256"] == sha256_file(source)
    assert evidence["semantic_anchors_sha256"] == sha256_file(anchors)
    assert evidence["profile_sha256"] == sha256_file(profile)


def test_runner_rejects_profile_mutation_before_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    anchors, profile = _write_snapshot_inputs(tmp_path)
    monkeypatch.setattr(
        dimension_observer_run,
        "detect_dimension_clusters",
        lambda image: [horizontal_dimension_cluster()],
    )
    original_observer = dimension_observer_run.observe_dimension_cluster

    def mutate_profile(*args: object, **kwargs: object):
        profile.write_bytes(profile.read_bytes() + b"\n")
        return original_observer(*args, **kwargs)

    monkeypatch.setattr(dimension_observer_run, "observe_dimension_cluster", mutate_profile)
    output = tmp_path / "run"

    with pytest.raises(DimensionObserverRunError, match="profile.*changed"):
        run_dimension_observer(
            run_id="RUN-VS-T1-PROFILE-MUTATION",
            source_image=source,
            page_id="PAGE-001",
            view_id="SIDE",
            output_dir=output,
            semantic_anchors_path=anchors,
            profile_path=profile,
            ocr_reader=fake_ocr_4500,
        )
    assert not output.exists()


def test_runner_rejects_anchor_mutation_before_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    anchors, profile = _write_snapshot_inputs(tmp_path)
    monkeypatch.setattr(
        dimension_observer_run,
        "detect_dimension_clusters",
        lambda image: [horizontal_dimension_cluster()],
    )
    original_observer = dimension_observer_run.observe_dimension_cluster

    def mutate_anchors(*args: object, **kwargs: object):
        anchors.write_bytes(anchors.read_bytes() + b"\n")
        return original_observer(*args, **kwargs)

    monkeypatch.setattr(dimension_observer_run, "observe_dimension_cluster", mutate_anchors)
    output = tmp_path / "run"

    with pytest.raises(DimensionObserverRunError, match="semantic anchors.*changed"):
        run_dimension_observer(
            run_id="RUN-VS-T1-ANCHORS-MUTATION",
            source_image=source,
            page_id="PAGE-001",
            view_id="SIDE",
            output_dir=output,
            semantic_anchors_path=anchors,
            profile_path=profile,
            ocr_reader=fake_ocr_4500,
        )
    assert not output.exists()


def test_runner_passes_profile_critical_flag_independently_of_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    monkeypatch.setattr(
        dimension_observer_run,
        "detect_dimension_clusters",
        lambda image: [horizontal_dimension_cluster()],
    )
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({
            "schema_version": "dimension-observer-profile-1.0",
            "default_unit": "mm",
            "clusters": {
                "DIMCLUSTER-001": {
                    "role": "REFERENCE",
                    "critical": False,
                    "blocker_scope": ["SIDE-CABIN"],
                },
            },
        }),
        encoding="utf-8",
    )

    register_path = run_dimension_observer(
        run_id="RUN-VS-T1-PROFILE-CRITICAL",
        source_image=source,
        page_id="PAGE-001",
        view_id="SIDE",
        output_dir=tmp_path / "run",
        profile_path=profile,
        ocr_reader=fake_ocr_4500,
    )

    register = read_visual_contract(register_path, contract="dimension_register")
    assert register["dimensions"][0]["critical"] is False
    assert register["dimensions"][0]["blocker_scope"] == ["SIDE-CABIN"]


def test_runner_refuses_nonempty_output_directory(tmp_path: Path) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    output = tmp_path / "run"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(DimensionObserverRunError, match="non-empty"):
        run_dimension_observer(
            run_id="RUN-VS-T1-001",
            source_image=source,
            page_id="PAGE-001",
            view_id="SIDE",
            output_dir=output,
            ocr_reader=fake_ocr_4500,
        )
