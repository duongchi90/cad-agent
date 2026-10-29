from __future__ import annotations

import json
import os
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


@pytest.mark.real_data
def test_fastening_bar_dimension_uses_source_bound_context_without_losing_cluster_identity(
    tmp_path: Path,
) -> None:
    source_value = os.environ.get("CAD_AGENT_FASTENING_BAR_IMAGE")
    anchors_value = os.environ.get("CAD_AGENT_FASTENING_BAR_ANCHORS")
    if not source_value or not anchors_value:
        pytest.skip(
            "set CAD_AGENT_FASTENING_BAR_IMAGE and CAD_AGENT_FASTENING_BAR_ANCHORS "
            "to run the approved real-source association check"
        )

    source = Path(source_value)
    anchors = Path(anchors_value)
    assert source.is_file(), "CAD_AGENT_FASTENING_BAR_IMAGE must point to the approved source PNG"
    assert anchors.is_file(), "CAD_AGENT_FASTENING_BAR_ANCHORS must point to caller-supplied source anchors"
    assert sha256_file(source) == "dd48f438b2771773bddb20568d693b5f7a52a75fc71cb40c67404c7171de3db6"
    tesseract_cmd = os.environ.get("CAD_AGENT_TESSERACT_CMD")
    if not tesseract_cmd:
        default_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        assert default_tesseract.is_file(), "set CAD_AGENT_TESSERACT_CMD to the supported Tesseract executable"
        tesseract_cmd = str(default_tesseract)

    register_path = run_dimension_observer(
        run_id="RUN-FASTENING-BAR-DIMENSION-CONTEXT",
        source_image=source,
        page_id="PAGE-001",
        view_id="TOP",
        output_dir=tmp_path / "run",
        ocr_lang="eng",
        tesseract_cmd=tesseract_cmd,
        semantic_anchors_path=anchors,
    )
    register = read_visual_contract(register_path, contract="dimension_register")
    observer = json.loads((register_path.parent / "observer-evidence.json").read_text(encoding="utf-8"))
    disposition = next(
        item for item in observer["dispositions"]
        if item["observation"] is not None
        and item["observation"]["display_text"] == "93,00"
    )
    observation = disposition["observation"]

    assert observation["value"] == 93.0
    assert disposition["cluster_id"] == "DIMCLUSTER-001"
    assert observation["source_evidence"]["bbox"] == [434.0, 127.0, 814.0, 175.0]
    geometry = observation["extension_geometry"]
    assert geometry["dimension_line"] is not None
    assert len(geometry["extension_lines"]) == 2
    assert all(abs(line[0][1] - 30.0) <= 2.0 for line in [geometry["dimension_line"]])
    assert all(
        abs(extension[0][0] - extension[1][0]) <= 2.0
        for extension in geometry["extension_lines"]
    )

    candidates = observation["attachment_candidates"]
    assert candidates, "context should recover source-supported extension-to-feature candidates"
    expected_ids = {"BAR-TOP-LEFT", "BAR-TOP-RIGHT"}
    best = candidates[0]
    assert {best["from_ref"]["id"], best["to_ref"]["id"]} == expected_ids
    assert best["confidence"] >= 0.85
    assert "attachment_unresolved" not in disposition["reasons"]
    # Feature association can be resolved while semantic role remains caller-owned.
    assert observation["status"] == "UNRESOLVED"
    assert "role_unresolved" in disposition["reasons"]

    neighbor = next(
        item for item in observer["dispositions"]
        if item["observation"] is not None
        and item["observation"]["display_text"] == "12,70"
    )
    assert neighbor["observation"]["attachment_confidence"] < 0.85
    assert "attachment_unresolved" in neighbor["reasons"]


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
