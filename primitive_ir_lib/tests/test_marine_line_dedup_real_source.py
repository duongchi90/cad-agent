"""Real-source regression for exact duplicate raster LINEs after PDF extraction."""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from primitive_ir_lib.run_pdf import run_pdf
from primitive_ir_lib.run_image import run
from primitive_ir_lib.validator import validate_document

_SOURCE_ENV = "CAD_AGENT_GUNNERUS_MARINE_PDF"
_SOURCE_SHA256 = "c4ec405ff866bbec40cdc15a86a1165f255d583af4e0c592767d5f6d65cd7ae3"


def _line_signature(line: dict) -> str:
    signature = {key: value for key, value in line.items() if key not in {"id", "confidence"}}
    trace = signature.get("trace")
    if isinstance(trace, dict):
        signature["trace"] = {
            key: value for key, value in trace.items() if key != "extracted_at"
        }
    geometry = signature["geometry"]
    signature["geometry"] = sorted(
        (tuple(geometry[endpoint][axis] for axis in ("x", "y"))
         for endpoint in ("start", "end"))
    )
    return json.dumps(signature, sort_keys=True)


def test_line_signature_ignores_extraction_timestamp():
    first = {
        "id": "line-a",
        "type": "line",
        "source": "geometry_opencv",
        "confidence": 0.9,
        "geometry": {"start": {"x": 0.0, "y": 0.0}, "end": {"x": 10.0, "y": 0.0}},
        "trace": {"bbox_px": [0.0, 0.0, 10.0, 0.0], "extraction_tool": "opencv", "extracted_at": "2026-11-02T00:00:00Z"},
    }
    second = {
        **first,
        "id": "line-b",
        "trace": {**first["trace"], "extracted_at": "2026-11-02T00:00:01Z"},
    }

    assert _line_signature(first) == _line_signature(second)
    different_source = {
        **second,
        "trace": {**second["trace"], "extraction_tool": "different-source"},
    }
    assert _line_signature(first) != _line_signature(different_source)


@pytest.mark.real_data
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


@pytest.mark.real_data
def test_gunnerus_default_raster_path_emits_no_exact_duplicate_lines(tmp_path):
    source = os.environ.get("CAD_AGENT_GUNNERUS_MARINE_RENDER")
    if not source:
        pytest.skip("CAD_AGENT_GUNNERUS_MARINE_RENDER is not configured")
    image = Path(source)
    assert hashlib.sha256(image.read_bytes()).hexdigest() == (
        "1f07aa5b136568e0eee3bffbe2768b8912e4326dcb4ed01f23a031279f0dcd07"
    )
    output = tmp_path / "ir.json"
    run(str(image), str(output), scale_mm_per_px=21.876,
        calibration_status="needs_verification", require_pdf_vector_circle_witness=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    lines = [p for p in payload["primitives"] if p["type"] == "line"]
    assert lines
    signatures = [_line_signature(line) for line in lines]
    assert len(signatures) == len(set(signatures))
    assert payload["calibration"]["status"] == "needs_verification"
    assert validate_document(payload) == []
