from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cad_agent.geometry_comparison_run import GeometryComparisonRunError, run_geometry_comparison
from cad_agent.manifest import sha256_file
from cad_agent.visual_contracts import read_visual_contract
from primitive_ir_lib.geometry_alignment import (
    estimate_photograph_alignment,
    estimate_similarity_alignment,
)
from primitive_ir_lib.tests.geometry_test_helpers import (
    four_collinear_anchors,
    four_perspective_anchors,
    five_perspective_anchors,
    identity_anchor_pairs,
    nonuniform_three_anchor_pairs,
    rectangle_mask,
    reflected_anchor_pairs,
    write_anchor_file,
    write_mask,
)


def _comparison_inputs(tmp_path: Path, *, name: str = "run") -> tuple[Path, Path, Path]:
    reference = write_mask(tmp_path / f"{name}-reference.png", rectangle_mask())
    cad = write_mask(tmp_path / f"{name}-cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / f"{name}-anchors.json", identity_anchor_pairs())
    return reference, cad, anchors


def test_policy_rejects_unsupported_similarity_mappings() -> None:
    assert estimate_similarity_alignment(reflected_anchor_pairs()).status == "FAILED"
    assert estimate_similarity_alignment(nonuniform_three_anchor_pairs()).status == "FAILED"


def test_policy_requires_photo_flag_four_anchors_and_non_collinearity() -> None:
    assert estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=False
    ).status == "FAILED"
    assert estimate_photograph_alignment(
        five_perspective_anchors(), source_is_photograph=True
    ).status == "FAILED"
    assert estimate_photograph_alignment(
        four_collinear_anchors(), source_is_photograph=True
    ).status == "FAILED"


def test_failed_alignment_has_no_fake_artifacts_or_authority(tmp_path: Path) -> None:
    reference = write_mask(tmp_path / "reference.png", rectangle_mask())
    cad = write_mask(tmp_path / "cad.png", rectangle_mask())
    anchors = write_anchor_file(tmp_path / "anchors.json", [identity_anchor_pairs()[0]])
    output = run_geometry_comparison(
        run_id="RUN-VS-T2-POLICY-FAILED",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "failed",
    )
    payload = read_visual_contract(output, contract="geometry_comparison")
    assert payload["metrics"] == {}
    assert payload["trend"] == "BASELINE"
    assert set(payload) == {
        "schema_version",
        "comparison_id",
        "run_id",
        "region_id",
        "reference_package_sha256",
        "cad_render_sha256",
        "mutation_sha256",
        "alignment",
        "metrics",
        "trend",
        "previous_comparison_sha256",
    }
    assert not list(output.parent.glob("*aligned*"))
    assert not (output.parent / "overlay.png").exists()
    assert not (output.parent / "missing-mask.png").exists()
    assert not (output.parent / "extra-mask.png").exists()


def test_previous_comparison_identity_mismatch_is_refused(tmp_path: Path) -> None:
    reference, cad, anchors = _comparison_inputs(tmp_path, name="previous")
    previous = run_geometry_comparison(
        run_id="RUN-VS-T2-POLICY-PREVIOUS",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "previous-output",
    )
    with pytest.raises(GeometryComparisonRunError, match="region_id"):
        run_geometry_comparison(
            run_id="RUN-VS-T2-POLICY-CURRENT",
            region_id="TOP-CABIN",
            reference_image=reference,
            cad_image=cad,
            reference_package_sha256="5" * 64,
            mutation_sha256="4" * 64,
            anchors_path=anchors,
            output_dir=tmp_path / "current-output",
            previous_comparison_path=previous,
        )


def test_identical_input_bytes_produce_identical_evidence(tmp_path: Path) -> None:
    reference, cad, anchors = _comparison_inputs(tmp_path, name="deterministic")
    first = run_geometry_comparison(
        run_id="RUN-VS-T2-POLICY-DETERMINISTIC",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "deterministic-1",
    )
    second = run_geometry_comparison(
        run_id="RUN-VS-T2-POLICY-DETERMINISTIC",
        region_id="SIDE-CABIN",
        reference_image=reference,
        cad_image=cad,
        reference_package_sha256="5" * 64,
        mutation_sha256="3" * 64,
        anchors_path=anchors,
        output_dir=tmp_path / "deterministic-2",
    )
    assert first.read_bytes() == second.read_bytes()
    first_manifest = json.loads((first.parent / "comparison-manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second.parent / "comparison-manifest.json").read_text(encoding="utf-8"))
    first_for_compare = copy.deepcopy(first_manifest)
    second_for_compare = copy.deepcopy(second_manifest)
    first_for_compare.pop("created_at_utc")
    second_for_compare.pop("created_at_utc")
    for manifest in (first_for_compare, second_for_compare):
        for artifact in manifest["artifacts"]:
            artifact.pop("timestamp_utc")
    assert first_for_compare == second_for_compare
    first_hashes = {item["relative_path"]: item["sha256"] for item in first_manifest["artifacts"]}
    second_hashes = {item["relative_path"]: item["sha256"] for item in second_manifest["artifacts"]}
    assert first_hashes == second_hashes
    assert all(sha256_file(first.parent / name) == digest for name, digest in first_hashes.items())
