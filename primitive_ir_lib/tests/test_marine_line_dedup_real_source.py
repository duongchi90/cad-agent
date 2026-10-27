"""Real-source regression for exact duplicate raster LINEs after PDF extraction."""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from primitive_ir_lib.run_pdf import run_pdf

pytestmark = pytest.mark.real_data
_SOURCE_ENV = "CAD_AGENT_GUNNERUS_MARINE_PDF"
_SOURCE_SHA256 = "c4ec405ff866bbec40cdc15a86a1165f255d583af4e0c592767d5f6d65cd7ae3"


def test_gunnerus_pdf_merge_has_no_exact_duplicate_line_geometry(tmp_path: Path) -> None:
    source_value = os.environ.get(_SOURCE_ENV)
    if not source_value:
        pytest.skip(f"set {_SOURCE_ENV} to the privately held, approved PDF")
    source = Path(source_value)
    assert source.is_file(), f"{_SOURCE_ENV} must point to the approved PDF"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == _SOURCE_SHA256

    output = tmp_path / "candidate"
    result = run_pdf(
        source,
        output,
        scale_mm_per_px=1.0,
        dpi=72,
        preset="real_scan_tuned_v1",
        merge_lines=True,
        auto_ocr_roi=False,
        auto_calibrate=False,
    )
    assert result["status"] == "complete"

    page = json.loads((output / "primitive_ir" / "page_01.json").read_text(encoding="utf-8"))
    geometries = Counter()
    for primitive in page["primitives"]:
        if primitive.get("type") != "line":
            continue
        geometry = primitive["geometry"]
        start = (geometry["start"]["x"], geometry["start"]["y"])
        end = (geometry["end"]["x"], geometry["end"]["y"])
        geometries[tuple(sorted((start, end)))] += 1

    duplicate_extras = sum(count - 1 for count in geometries.values() if count > 1)
    assert duplicate_extras == 0, f"exact duplicate LINE extras: {duplicate_extras}"
