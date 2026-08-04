from __future__ import annotations

from pathlib import Path

import pytest

from cad_agent.geometry_comparison_run import GeometryComparisonRunError, run_geometry_comparison
from cad_agent.run_geometry_comparison import main as run_geometry_comparison_cli
from cad_agent.manifest import sha256_file
from cad_agent.visual_contracts import read_visual_contract
from primitive_ir_lib.tests.geometry_test_helpers import (
    identity_anchor_pairs,
    rectangle_mask,
    write_anchor_file,
    write_mask,
)


def test_runner_writes_validated_hash_bound_comparison(tmp_path: Path) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", identity_anchor_pairs())
    output = run_geometry_comparison(
        run_id="RUN-VS-T2-001",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "comparison",
    )
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["cad_render_sha256"] == sha256_file(cad)
    assert payload["alignment"]["status"] == "ALIGNED"
    assert (output.parent / "overlay.png").is_file()
    assert (output.parent / "comparison-manifest.json").is_file()


def test_runner_records_failed_alignment_without_aligned_artifacts(tmp_path: Path) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", [identity_anchor_pairs()[0]])
    output = run_geometry_comparison(
        run_id="RUN-VS-T2-002",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "failed-comparison",
    )
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["alignment"]["status"] == "FAILED"
    assert payload["metrics"] == {}
    assert payload["trend"] == "BASELINE"
    assert not (output.parent / "overlay.png").exists()
    assert (output.parent / "alignment-failure.json").is_file()


def test_runner_rejects_source_changed_during_run(tmp_path: Path, monkeypatch) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", identity_anchor_pairs())
    monkeypatch.setattr(
        "cad_agent.geometry_comparison_run._verify_unchanged",
        lambda path, expected_sha256: False,
    )
    with pytest.raises(GeometryComparisonRunError, match="changed"):
        run_geometry_comparison(
            run_id="RUN-VS-T2-003",
            region_id="SIDE-CABIN",
            reference_image=reference,
            cad_image=cad,
            reference_package_sha256="5" * 64,
            mutation_sha256="3" * 64,
            anchors_path=anchors,
            output_dir=tmp_path / "changed-input",
        )


def test_cli_writes_comparison_from_explicit_arguments(tmp_path: Path, capsys) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", identity_anchor_pairs())
    output_dir = tmp_path / "cli-comparison"
    result = run_geometry_comparison_cli(
        [
            "--run-id",
            "RUN-VS-T2-CLI",
            "--region-id",
            "SIDE-CABIN",
            "--reference",
            str(reference),
            "--cad-render",
            str(cad),
            "--reference-package-sha256",
            "5" * 64,
            "--mutation-sha256",
            "3" * 64,
            "--anchors",
            str(anchors),
            "--output",
            str(output_dir),
        ]
    )
    assert result == 0
    assert capsys.readouterr().out.strip().endswith("geometry-comparison.json")
