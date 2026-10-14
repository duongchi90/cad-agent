from __future__ import annotations

import json
from pathlib import Path

import fitz
import numpy as np
import pytest

from cad_agent.cli import (
    ManifestError,
    _run_primitive_with_strategy,
    _write_contour_auxiliary_artifact,
    _write_contour_primitive_ir,
)
from cad_agent.pdf import _ensure_rendered, _stage
from primitive_ir_lib import run_pdf as run_pdf_module
from primitive_ir_lib import run_image as run_image_module

cv2 = run_image_module.cv2


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


@pytest.mark.parametrize(
    "artifact_kind",
    ["rendered_png", "rendered_parent", "view_candidates", "pdf_summary"],
)
def test_pdf_contour_auxiliary_publication_rejects_links_without_mutating_sentinel(
    tmp_path: Path, artifact_kind: str,
):
    source = tmp_path / "source.pdf"
    output_root = tmp_path / "run"
    pdf_root = output_root / "pdf"
    _pdf(source)
    pdf_root.mkdir(parents=True)
    if artifact_kind == "rendered_png":
        target = pdf_root / "rendered" / "page_01.png"
        linked_path = target
        sentinel = tmp_path / "owned" / "sentinel.png"
        before = _sentinel(sentinel)
        target.parent.mkdir()
        target.symlink_to(sentinel)
    elif artifact_kind == "rendered_parent":
        linked_dir = tmp_path / "owned-rendered"
        sentinel = linked_dir / "page_01.png"
        before = _sentinel(sentinel)
        linked_path = pdf_root / "rendered"
        linked_path.symlink_to(linked_dir, target_is_directory=True)
    elif artifact_kind == "view_candidates":
        target = pdf_root / "primitive_ir" / "page_01.view_candidates.json"
        linked_path = target
        sentinel = tmp_path / "owned" / "sentinel.json"
        before = _sentinel(sentinel)
        target.parent.mkdir()
        target.symlink_to(sentinel)
    else:
        target = pdf_root / "manifest.json"
        linked_path = target
        sentinel = tmp_path / "owned" / "sentinel.json"
        before = _sentinel(sentinel)
        target.symlink_to(sentinel)

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

    error = None
    try:
        _ensure_rendered(source, output_root, output_root / "manifest.json", manifest)
    except Exception as exc:  # The security boundary must fail closed.
        error = exc

    assert sentinel.read_bytes() == before
    assert linked_path.is_symlink()
    assert isinstance(error, ManifestError)
    assert manifest["render"]["state"] == "pending"


def test_pdf_view_child_image_publication_rejects_preexisting_symlink(
    tmp_path: Path, monkeypatch,
):
    rendered = tmp_path / "rendered.png"
    output_root = tmp_path / "run"
    child_root = output_root / "view_ir" / "page_01"
    child_image = child_root / "view_01.png"
    sentinel = tmp_path / "owned" / "sentinel.png"
    assert cv2.imwrite(str(rendered), np.full((100, 100, 3), 255, dtype=np.uint8))
    before = _sentinel(sentinel)
    child_root.mkdir(parents=True)
    child_image.symlink_to(sentinel)
    candidate = {
        "bbox_px": [20, 20, 60, 60],
        "region_bbox_px": [20, 20, 60, 60],
        "dimension_evidence": {"geometry_primitive_id": "line-1"},
        "pixel_to_unit_scale": 1.0,
    }

    def fake_run(*, output_path, **_kwargs):
        Path(output_path).write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(run_pdf_module, "run", fake_run)
    with pytest.raises(ManifestError, match="auxiliary publication"):
        run_pdf_module._materialize_view_children(
            [candidate], rendered, output_root, 1, "default", False,
            circle_strategy=STRATEGY,
            artifact_writer=_write_contour_auxiliary_artifact,
        )

    assert sentinel.read_bytes() == before
    assert child_image.is_symlink()


def test_pdf_artifact_callback_preserves_png_pixels_and_json_bytes(
    tmp_path: Path, monkeypatch,
):
    source = tmp_path / "source.pdf"
    default_root = tmp_path / "default"
    protected_root = tmp_path / "protected"
    _pdf(source)
    candidate = {
        "bbox_px": [20, 20, 60, 60],
        "region_bbox_px": [20, 20, 60, 60],
        "dimension_evidence": {"geometry_primitive_id": "line-1"},
        "pixel_to_unit_scale": 1.0,
    }
    monkeypatch.setattr(
        run_image_module, "_configure_tesseract", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        run_image_module, "extract_text_tesseract", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        run_image_module,
        "detect_view_candidates",
        lambda *_args, **_kwargs: [candidate.copy()],
    )

    run_pdf_module.run_pdf(
        source, default_root, scale_mm_per_px=1.0, dpi=72,
        circle_strategy=STRATEGY,
        document_writer=_write_contour_primitive_ir,
    )
    writes: list[str] = []

    def write_artifact(path: str, data: bytes) -> None:
        writes.append(Path(path).relative_to(protected_root).as_posix())
        _write_contour_auxiliary_artifact(path, data)

    run_pdf_module.run_pdf(
        source, protected_root, scale_mm_per_px=1.0, dpi=72,
        circle_strategy=STRATEGY,
        document_writer=_write_contour_primitive_ir,
        artifact_writer=write_artifact,
    )

    assert np.array_equal(
        cv2.imread(str(default_root / "rendered" / "page_01.png")),
        cv2.imread(str(protected_root / "rendered" / "page_01.png")),
    )
    assert (
        (default_root / "primitive_ir" / "page_01.view_candidates.json").read_bytes()
        == (protected_root / "primitive_ir" / "page_01.view_candidates.json").read_bytes()
    )
    assert (default_root / "manifest.json").read_bytes() == (
        protected_root / "manifest.json"
    ).read_bytes()
    default_child = default_root / "view_ir" / "page_01" / "view_01.png"
    protected_child = protected_root / "view_ir" / "page_01" / "view_01.png"
    assert np.array_equal(cv2.imread(str(default_child)), cv2.imread(str(protected_child)))
    assert writes.count("primitive_ir/page_01.view_candidates.json") == 2
    assert "rendered/page_01.png" in writes
    assert "view_ir/page_01/view_01.png" in writes
    assert "manifest.json" in writes
