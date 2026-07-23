"""Optional private evidence gate for an approved fidelity-PDF run."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cad_agent.fidelity import read_fidelity_manifest
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
        assert page["fidelity_state"] == "needs_review"
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
