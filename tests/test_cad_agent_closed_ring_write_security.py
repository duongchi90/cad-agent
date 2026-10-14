from __future__ import annotations

import json
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

from cad_agent.cli import ManifestError, _run_primitive_with_strategy
from cad_agent.pdf import _ensure_rendered, _stage


STRATEGY = "closed_ring_identity_v1"


def _image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), np.full((96, 128, 3), 255, dtype=np.uint8))


def _pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    document.new_page(width=128, height=96)
    document.save(str(path))
    document.close()


def _sentinel(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"owned-sentinel: do not replace")
    return path.read_bytes()


def test_image_contour_publication_rejects_preexisting_destination_symlink(
    tmp_path: Path,
):
    source = tmp_path / "source.png"
    output_root = tmp_path / "run"
    artifact = output_root / "primitive_ir.json"
    sentinel = tmp_path / "owned" / "sentinel.json"
    _image(source)
    before = _sentinel(sentinel)
    output_root.mkdir()
    artifact.symlink_to(sentinel)

    with pytest.raises(ManifestError, match="link|symlink|hardlink|artifact"):
        _run_primitive_with_strategy(source, artifact, 1.0, circle_strategy=STRATEGY)

    assert sentinel.read_bytes() == before


def test_image_contour_publication_rejects_linked_destination_parent(tmp_path: Path):
    source = tmp_path / "source.png"
    output_root = tmp_path / "run"
    outside = tmp_path / "owned-output"
    sentinel = outside / "primitive_ir.json"
    _image(source)
    before = _sentinel(sentinel)
    output_root.mkdir()
    (output_root / "nested").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ManifestError, match="link|symlink|artifact|outside|non-reparse"):
        _run_primitive_with_strategy(
            source, output_root / "nested" / "primitive_ir.json", 1.0,
            circle_strategy=STRATEGY,
        )

    assert sentinel.read_bytes() == before


def test_image_contour_publication_rejects_hardlinked_destination(tmp_path: Path):
    source = tmp_path / "source.png"
    output_root = tmp_path / "run"
    artifact = output_root / "primitive_ir.json"
    sentinel = tmp_path / "owned" / "sentinel.json"
    _image(source)
    before = _sentinel(sentinel)
    output_root.mkdir()
    artifact.hardlink_to(sentinel)

    with pytest.raises(ManifestError, match="link|symlink|hardlink|artifact"):
        _run_primitive_with_strategy(source, artifact, 1.0, circle_strategy=STRATEGY)

    assert sentinel.read_bytes() == before


def test_pdf_rendered_page_contour_publication_rejects_preexisting_symlink(
    tmp_path: Path,
):
    source = tmp_path / "source.pdf"
    output_root = tmp_path / "run"
    pdf_root = output_root / "pdf"
    artifact = pdf_root / "primitive_ir" / "page_01.json"
    sentinel = tmp_path / "owned" / "sentinel.json"
    _pdf(source)
    before = _sentinel(sentinel)
    artifact.parent.mkdir(parents=True)
    artifact.symlink_to(sentinel)
    manifest = {
        "render": _stage(),
        "configuration": {
            "scale_mm_per_px": 1.0,
            "dpi": 72,
            "auto_ocr_roi": False,
            "circle_strategy": STRATEGY,
        },
        "pages": [],
    }

    with pytest.raises(ManifestError, match="link|symlink|hardlink|artifact"):
        _ensure_rendered(source, output_root, output_root / "manifest.json", manifest)

    assert sentinel.read_bytes() == before


def test_image_contour_publication_still_writes_an_ordinary_candidate(tmp_path: Path):
    source = tmp_path / "source.png"
    artifact = tmp_path / "run" / "primitive_ir.json"
    _image(source)

    _run_primitive_with_strategy(source, artifact, 1.0, circle_strategy=STRATEGY)

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["calibration"]["status"] == "verified"
    assert payload["primitives"] == []
