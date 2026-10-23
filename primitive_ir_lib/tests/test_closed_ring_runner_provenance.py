from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import cv2
import fitz
import numpy as np
import pytest

from primitive_ir_lib import geometry_extraction
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.geometry_extraction import RawCircle, RawLine
from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.run_image import run
from primitive_ir_lib.run_pdf import _materialize_view_children, run_pdf
from primitive_ir_lib.text_extraction import RawText


CLOSED_RING = "closed_ring_identity_v1"
RING_TOOL = "opencv-contour-ring-identity-v1"


@pytest.mark.parametrize("selector", [" Closed_Ring_Identity_V1 ", None, ["hough"]])
def test_image_invalid_strategy_rejects_before_decode_or_output(
    tmp_path: Path, monkeypatch, selector,
):
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"not decoded")
    output_path = tmp_path / "new" / "ir.json"

    def unexpected(*args, **kwargs):
        raise AssertionError("invalid selector reached image decoding")

    monkeypatch.setattr(cv2, "imread", unexpected)
    with pytest.raises(ValueError):
        run(str(image_path), str(output_path), scale_mm_per_px=1.0,
            circle_strategy=selector)
    assert not output_path.parent.exists()


def test_image_invalid_document_writer_rejects_before_decode_or_output(
    tmp_path: Path, monkeypatch,
):
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"not decoded")
    output_path = tmp_path / "new" / "ir.json"

    monkeypatch.setattr(
        cv2, "imread", lambda *_args, **_kwargs: pytest.fail("image was decoded")
    )
    with pytest.raises(ValueError, match="document_writer must be callable"):
        run(str(image_path), str(output_path), scale_mm_per_px=1.0,
            document_writer=object())
    assert not output_path.parent.exists()


def test_image_invalid_artifact_writer_rejects_before_decode_or_output(
    tmp_path: Path, monkeypatch,
):
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"not decoded")
    output_path = tmp_path / "new" / "ir.json"

    monkeypatch.setattr(
        cv2, "imread", lambda *_args, **_kwargs: pytest.fail("image was decoded")
    )
    with pytest.raises(ValueError, match="artifact_writer must be callable"):
        run(str(image_path), str(output_path), scale_mm_per_px=1.0,
            artifact_writer=object())
    assert not output_path.parent.exists()


@pytest.mark.parametrize("selector", ["closed_ring_identity_v1 ", None, ["hough"]])
def test_pdf_invalid_strategy_rejects_before_open_or_output(
    tmp_path: Path, monkeypatch, selector,
):
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"not opened")
    output_dir = tmp_path / "new-output"

    def unexpected(*args, **kwargs):
        raise AssertionError("invalid selector reached PDF opening")

    monkeypatch.setattr(fitz, "open", unexpected)
    with pytest.raises(ValueError):
        run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0,
                circle_strategy=selector)
    assert not output_dir.exists()


def test_pdf_invalid_document_writer_rejects_before_open_or_output(
    tmp_path: Path, monkeypatch,
):
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"not opened")
    output_dir = tmp_path / "new-output"

    monkeypatch.setattr(
        fitz, "open", lambda *_args, **_kwargs: pytest.fail("PDF was opened")
    )
    with pytest.raises(ValueError, match="document_writer must be callable"):
        run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0,
                document_writer=object())
    assert not output_dir.exists()


def test_pdf_invalid_artifact_writer_rejects_before_open_or_output(
    tmp_path: Path, monkeypatch,
):
    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"not opened")
    output_dir = tmp_path / "new-output"

    monkeypatch.setattr(
        fitz, "open", lambda *_args, **_kwargs: pytest.fail("PDF was opened")
    )
    with pytest.raises(ValueError, match="artifact_writer must be callable"):
        run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0,
                artifact_writer=object())
    assert not output_dir.exists()


def test_artifact_writer_rejects_auto_calibration_before_acquisition_or_staging(
    tmp_path: Path, monkeypatch,
):
    image_path = tmp_path / "input.png"
    pdf_path = tmp_path / "input.pdf"
    image_path.write_bytes(b"not decoded")
    pdf_path.write_bytes(b"not opened")

    monkeypatch.setattr(
        cv2, "imread", lambda *_args, **_kwargs: pytest.fail("image was decoded")
    )
    monkeypatch.setattr(
        fitz, "open", lambda *_args, **_kwargs: pytest.fail("PDF was opened")
    )
    callback = lambda _path, _data: None
    with pytest.raises(ValueError, match="cannot be combined with auto_calibrate"):
        run(str(image_path), str(tmp_path / "image-out" / "ir.json"),
            auto_calibrate=True, artifact_writer=callback)
    with pytest.raises(ValueError, match="cannot be combined with auto_calibrate"):
        run_pdf(pdf_path, tmp_path / "pdf-out", auto_calibrate=True,
                artifact_writer=callback)
    assert not (tmp_path / "image-out").exists()
    assert not (tmp_path / "pdf-out").exists()


@pytest.mark.parametrize("explicit", [False, True])
def test_image_hough_default_and_explicit_selector_preserve_compatibility(
    tmp_path: Path, explicit: bool,
):
    image_path = tmp_path / "input.png"
    assert cv2.imwrite(str(image_path), np.full((80, 100, 3), 255, dtype=np.uint8))
    output_path = tmp_path / "ir.json"
    with patch("primitive_ir_lib.run_image.extract_raw_geometry", return_value=geometry_extraction.RawGeometry()) as extract:
        kwargs = {"circle_strategy": "hough"} if explicit else {}
        run(str(image_path), str(output_path), scale_mm_per_px=1.0, **kwargs)
    assert extract.call_args.kwargs["circle_strategy"] == "hough"


def test_image_document_writer_failure_propagates_without_default_writer_fallback(
    tmp_path: Path, monkeypatch,
):
    image_path = tmp_path / "input.png"
    output_path = tmp_path / "out" / "ir.json"
    assert cv2.imwrite(str(image_path), np.full((80, 100, 3), 255, dtype=np.uint8))

    def fail_writer(_document, _output_path):
        raise RuntimeError("injected writer failure")

    monkeypatch.setattr(
        "primitive_ir_lib.run_image.save_document",
        lambda *_args, **_kwargs: pytest.fail("default writer fallback executed"),
    )
    with pytest.raises(RuntimeError, match="injected writer failure"):
        run(str(image_path), str(output_path), scale_mm_per_px=1.0,
            circle_strategy=CLOSED_RING, document_writer=fail_writer)
    assert not output_path.exists()


def test_image_serializes_actual_closed_ring_with_truthful_provenance(tmp_path: Path, monkeypatch):
    image = np.full((128, 160, 3), 255, dtype=np.uint8)
    cv2.circle(image, (64, 64), 22, (0, 0, 0), 2, cv2.LINE_8)
    image_path = tmp_path / "ring.png"
    output_path = tmp_path / "ring.json"
    assert cv2.imwrite(str(image_path), image)

    monkeypatch.setattr(
        geometry_extraction.cv2, "HoughCircles",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Hough called")),
    )
    run(str(image_path), str(output_path), scale_mm_per_px=1.0,
        circle_strategy=CLOSED_RING)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    circles = [item for item in payload["primitives"] if item["type"] == "circle"]
    assert len(circles) == 1
    assert circles[0]["trace"]["extraction_tool"] == RING_TOOL
    assert circles[0]["confidence"] == 0.75
    center = circles[0]["geometry"]["center"]
    assert center["x"] == pytest.approx(64.0, abs=0.1)
    assert center["y"] == pytest.approx(64.0, abs=0.1)
    assert circles[0]["geometry"]["radius"] == pytest.approx(22.0, abs=0.2)
    assert payload["calibration"]["status"] == "verified"


def test_assembly_changes_circle_provenance_only():
    document = build_document(
        "drawing.png", 0, 100, 80,
        Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0.0, 80.0),
                    method="manual_override"),
        [RawLine("line", (1.0, 2.0), (20.0, 2.0), 1.0, (1.0, 2.0, 20.0, 2.0))],
        [RawCircle("circle", (30.0, 30.0), 8.0, 0.75, (22.0, 22.0, 38.0, 38.0))],
        [RawText("text", "100", (1, 1, 20, 10), 0.0, 1.0, "text_tesseract")],
        circle_extraction_tool=RING_TOOL,
    )
    by_type = {item.type: item for item in document.primitives}
    assert by_type["line"].trace.extraction_tool == "opencv-canny-hough-v1"
    assert by_type["circle"].trace.extraction_tool == RING_TOOL
    assert by_type["text"].trace.extraction_tool == "tesseract-5.3"


def test_pdf_forwards_same_selector_to_every_page(tmp_path: Path):
    pdf_path = tmp_path / "two-pages.pdf"
    document = fitz.open()
    document.new_page(width=100, height=80)
    document.new_page(width=100, height=80)
    document.save(str(pdf_path))
    document.close()
    output_dir = tmp_path / "pdf-output"
    seen: list[str] = []
    writers: list[object] = []
    artifact_writers: list[object] = []

    def fake_run(image_path, output_path, scale_mm_per_px=None, **kwargs):
        seen.append(kwargs["circle_strategy"])
        writers.append(kwargs.get("document_writer"))
        artifact_writers.append(kwargs.get("artifact_writer"))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps({
            "primitives": [], "cross_validations": [],
            "calibration": {"method": "manual_override", "pixel_to_unit_scale": 1.0},
        }), encoding="utf-8")
        Path(kwargs["view_candidates_output_path"]).write_text("[]", encoding="utf-8")
        return output_path

    writer = lambda _document, _path: None
    def artifact_writer(path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)
    with patch("primitive_ir_lib.run_pdf.run", side_effect=fake_run):
        run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0,
                circle_strategy=CLOSED_RING, document_writer=writer,
                artifact_writer=artifact_writer)
    assert seen == [CLOSED_RING, CLOSED_RING]
    assert writers == [writer, writer]
    assert artifact_writers == [artifact_writer, artifact_writer]


def test_pdf_view_child_forwards_selector_and_keeps_unverified_calibration(tmp_path: Path):
    rendered = tmp_path / "page.png"
    assert cv2.imwrite(str(rendered), np.full((100, 100, 3), 255, dtype=np.uint8))
    candidate = {
        "bbox_px": [30, 30, 60, 60], "region_bbox_px": [20, 20, 70, 70],
        "dimension_evidence": {"geometry_primitive_id": "line"},
        "pixel_to_unit_scale": 0.5,
    }
    captured: dict = {}

    def fake_run(image_path, output_path, scale_mm_per_px=None, **kwargs):
        captured.update(kwargs)
        Path(output_path).write_text(json.dumps({
            "calibration": {"status": kwargs["calibration_status"],
                           "source_sha256": kwargs["calibration_source_sha256"]},
        }), encoding="utf-8")
        return output_path

    writer = lambda _document, _path: None

    def artifact_writer(path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)

    with patch("primitive_ir_lib.run_pdf.run", side_effect=fake_run):
        _materialize_view_children([candidate], rendered, tmp_path / "out", 1,
                                   "default", False, circle_strategy=CLOSED_RING,
                                   document_writer=writer,
                                   artifact_writer=artifact_writer)
    assert captured["circle_strategy"] == CLOSED_RING
    assert captured["document_writer"] is writer
    assert captured["artifact_writer"] is artifact_writer
    assert captured["calibration_status"] == "needs_verification"
