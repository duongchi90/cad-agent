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
    assert (register_path.parent / "observer-evidence.json").is_file()


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
