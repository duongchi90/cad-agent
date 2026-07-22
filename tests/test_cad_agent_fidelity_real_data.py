"""Optional private evidence gate for an approved fidelity-PDF run."""

from __future__ import annotations

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
