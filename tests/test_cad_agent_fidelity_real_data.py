"""Optional private evidence gate for an approved fidelity-PDF run."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cad_agent.fidelity import (
    new_fidelity_manifest,
    read_fidelity_manifest,
    run_fidelity_pdf,
    run_fidelity_text_observations,
)
from cad_agent.manifest import sha256_file

pytestmark = pytest.mark.real_data


def test_private_fidelity_pdf_has_nine_hash_bound_layout_pages() -> None:
    source = os.environ.get("CAD_AGENT_FIDELITY_PDF")
    manifest_path = os.environ.get("CAD_AGENT_FIDELITY_MANIFEST")
    if not source or not manifest_path:
        pytest.skip("set CAD_AGENT_FIDELITY_PDF and CAD_AGENT_FIDELITY_MANIFEST to run the fidelity private-data gate")
    pdf = Path(source)
    manifest_file = Path(manifest_path)
    manifest = read_fidelity_manifest(manifest_file)
    assert pdf.is_file()
    assert manifest["source"]["sha256"] == sha256_file(pdf)
    assert len(manifest["pages"]) == 9
    root = manifest_file.parent
    for page in manifest["pages"]:
        assert page["fidelity_state"] in {
            "needs_review",
            "approved_for_mechanical_review",
            "mechanical_reviewed",
        }
        for key in ("rendered_png", "layout_dxf", "layout_audit"):
            record = page["artifacts"][key]
            artifact = root / record["artifact"]
            assert artifact.is_file()
            assert sha256_file(artifact) == record["sha256"]
    if os.environ.get("CAD_AGENT_FIDELITY_REQUIRE_RECONSTRUCTION") == "1":
        for page in manifest["pages"]:
            number = page["page"]
            approvals = sorted((root / "region_approvals").glob(f"page_{number:02d}*.json"))
            assert approvals, f"page {number} has no reconstruction approval"
            approval = json.loads(approvals[-1].read_text(encoding="utf-8"))
            for region_id in approval["approved_region_ids"]:
                candidate = root / "reconstruction_candidates" / f"page_{number:02d}" / region_id
                assert (candidate / "geometry.dxf").is_file()
                assert (candidate / "report.json").is_file()
            revision = approval["proposal"]["revision"]
            suffix = "" if revision == 1 else f"-r{revision}"
            composed = root / "reconstruction_pages" / f"page_{number:02d}{suffix}"
            assert (composed / "layout.dxf").is_file()
            assert (composed / "report.json").is_file()
            assert page["fidelity_state"] == "mechanical_reviewed"
            promotion_record = page["artifacts"]["promotion"]
            promotion_path = root / promotion_record["artifact"]
            assert sha256_file(promotion_path) == promotion_record["sha256"]
            promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
            assert promotion["state"] == "approved_for_mechanical_review"
            assert promotion["source"] == manifest["source"]
            assert promotion["page"] == number
            assert promotion["allowed_actions"] == ["mechanical-review-read-only"]
            for record in promotion["inputs"].values():
                assert sha256_file(root / record["artifact"]) == record["sha256"]
            mechanical_record = page["mechanical_review"]
            assert mechanical_record["state"] == "completed"
            mechanical_path = root / mechanical_record["artifact"]
            assert sha256_file(mechanical_path) == mechanical_record["sha256"]
            mechanical = json.loads(mechanical_path.read_text(encoding="utf-8"))
            assert mechanical["state"] == "passed"
            assert mechanical["save_performed"] is False
            assert mechanical["repair_performed"] is False


def test_case01_asteriti_aggregate_trace_text_remains_review_only(tmp_path: Path) -> None:
    source_value = os.environ.get("CAD_AGENT_CASE01_ASTERITI_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_CASE01_ASTERITI_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert sha256_file(source) == "1970e92e81d888437f55369c4605d0a5f71127177898fb6d5012084ae22fe162"

    output = tmp_path / "case01-fidelity"
    manifest = new_fidelity_manifest(
        source,
        output,
        144,
        "Approved private source-only evaluation per #491 CASE01 checkpoint 6613335500; reference DWG remains sealed",
        workspace_root=Path.cwd(),
    )
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = observation["native_pdf_spans"]

    assert len(native) == 71
    assert all(item["source_sha256"] == manifest["source"]["sha256"] for item in native)
    assert all(item["visibility"] == "unverified" for item in native)
    assert all(item["semantic_role"] is None for item in native)
    assert all(item["evidence_kind"] == "native_pdf" for item in native)
    assert all(
        "".join(trace["text"] for trace in item["source_paint_evidence"]["member_traces"]) == item["content"]
        for item in native
    )
    assert all(
        item["source_paint_evidence"].get("character_range")
        or item["source_paint_evidence"]["member_traces"][0]["text"] == item["content"]
        for item in native
    )
    target_counts = {
        text: sum(item["content"] == text for item in native)
        for text in ("414 MM", "71.5 MM", "34 MM", "21.3 MM", "36 MM", "21 MM")
    }
    assert target_counts == {
        "414 MM": 2,
        "71.5 MM": 2,
        "34 MM": 3,
        "21.3 MM": 3,
        "36 MM": 1,
        "21 MM": 1,
    }
    assert "DIMENSION" not in observation and "TEXT" not in observation
