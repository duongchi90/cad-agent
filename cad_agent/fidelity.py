"""Private, paper-coordinate PDF layout baseline.

This module intentionally creates a diagnostic layout DXF, not a model-space
conversion. It keeps OCR and scale observations in sidecars so unreviewed text
or calibration can never be mistaken for CAD source geometry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import fitz

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.io_utils import save_document
from primitive_ir_lib.run_image import _configure_tesseract
from primitive_ir_lib.text_extraction import detect_text_candidate_rois, extract_text_tesseract
from primitive_ir_lib.view_calibration import detect_view_candidates

from .manifest import ManifestError, sha256_file, verify_source, write_manifest

FIDELITY_MANIFEST_NAME = "fidelity-run-manifest.json"
FIDELITY_SCHEMA_VERSION = "fidelity-run-1.0"


class FidelityError(ValueError):
    """Raised for an unsafe or unsupported fidelity-layout request."""


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _artifact(path: Path, output_root: Path) -> dict[str, str]:
    return {
        "artifact": str(path.relative_to(output_root)).replace("\\", "/"),
        "sha256": sha256_file(path),
    }


def _title_block_roi(width: int, height: int) -> tuple[int, int, int, int]:
    return (int(width * 0.58), int(height * 0.67), width, height)


def _deduplicate_rois(rois: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    return list(dict.fromkeys(rois))


def _raw_text_payload(text: object) -> dict[str, Any]:
    return {
        "id": text.id,
        "content": text.content,
        "bbox_px": list(text.bbox_px),
        "rotation_deg": text.rotation_deg,
        "confidence": text.confidence,
        "source": text.source,
        "semantic_role": text.semantic_role,
        "parsed_value": text.parsed_value,
    }


def _page_size_mm(page: fitz.Page) -> tuple[float, float]:
    # page.rect is the displayed (rotation-aware) box used by get_pixmap().
    return page.rect.width * 25.4 / 72.0, page.rect.height * 25.4 / 72.0


def new_fidelity_manifest(
    source: Path,
    output_root: Path,
    dpi: int,
    approval: str,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise FidelityError("fidelity-pdf requires an existing PDF input.")
    if dpi <= 0:
        raise FidelityError("--dpi must be positive.")
    if not approval.strip():
        raise FidelityError("fidelity-pdf requires a non-empty source approval reference.")
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    return {
        "schema_version": FIDELITY_SCHEMA_VERSION,
        "private_artifact": True,
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "pdf"},
        "configuration": {"dpi": dpi, "transform": "displayed-page-box-v1", "ocr": "tesseract-local-psm11"},
        "approvals": {"source": {"approved": True, "reference": approval.strip()}},
        "pages": [],
    }


def _audit_page(image, raw_geometry, dpi: int, page_number: int, rendered_path: Path) -> dict[str, Any]:
    height, width = image.shape[:2]
    _configure_tesseract(None)
    rois = _deduplicate_rois([_title_block_roi(width, height), *detect_text_candidate_rois(image)])
    texts = extract_text_tesseract(image, roi_boxes=rois, min_confidence=20, psm=11)
    scale_candidates = detect_view_candidates(texts, raw_geometry.lines, width, height, dpi=dpi)
    return {
        "schema_version": "layout-audit-1.0",
        "status": "needs_review",
        "source_page": {
            "page": page_number,
            "render_sha256": sha256_file(rendered_path),
            "render_width_px": width,
            "render_height_px": height,
            "dpi": dpi,
        },
        "ocr": {"engine": "tesseract-local", "psm": 11, "rois_px": [list(roi) for roi in rois], "texts": [_raw_text_payload(text) for text in texts]},
        "table_audit": {"status": "not_evaluated", "reason": "table-region approval is required before per-cell OCR"},
        "scale_candidates": scale_candidates,
        "unresolved": ["OCR output is sidecar-only", "No model-space view is authorized"],
    }


def run_fidelity_pdf(source: Path, output_root: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != FIDELITY_SCHEMA_VERSION:
        raise ManifestError("Unsupported fidelity manifest schema version.")
    verify_source(manifest, source)
    if not manifest.get("private_artifact"):
        raise FidelityError("Fidelity manifest must be marked private_artifact.")
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise FidelityError("Fidelity manifest already exists; use a new private output root.")

    from dxf_builder_lib.builder import build_dxf
    from dxf_builder_lib.reviewer import review_dxf

    dpi = int(manifest["configuration"]["dpi"])
    zoom = dpi / 72.0
    document = fitz.open(str(source))
    try:
        pages: list[dict[str, Any]] = []
        for number, page in enumerate(document, start=1):
            rendered = output_root / "rendered" / f"page_{number:02d}.png"
            rendered.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(str(rendered))
            image = cv2.imread(str(rendered))
            if image is None:
                raise FidelityError(f"Cannot read rendered page {number}.")
            height, width = image.shape[:2]
            page_width_mm, page_height_mm = _page_size_mm(page)
            scale_x = page_width_mm / width
            scale_y = page_height_mm / height
            if abs(scale_x - scale_y) > 1e-6:
                raise FidelityError("Rendered page has a non-uniform pixel-to-paper transform.")
            raw = extract_raw_geometry(image, preset="real_scan_tuned_v1")
            layout_doc = build_document(
                file_name=rendered.name,
                page_index=number - 1,
                image_width_px=width,
                image_height_px=height,
                calibration=Calibration(
                    unit="mm",
                    pixel_to_unit_scale=scale_x,
                    origin_px=(0.0, float(height)),
                    method="manual_override",
                    reference_note="Fidelity layout: displayed PDF page coordinates in paper millimetres.",
                ),
                raw_lines=raw.lines,
                raw_circles=raw.circles,
                raw_texts=[],
                sha256=sha256_file(rendered),
            )
            layout_ir = output_root / "layout_ir" / f"page_{number:02d}.json"
            layout_ir.parent.mkdir(parents=True, exist_ok=True)
            save_document(layout_doc, str(layout_ir))
            dxf = output_root / "layout_dxf" / f"page_{number:02d}.dxf"
            dxf.parent.mkdir(parents=True, exist_ok=True)
            built = build_dxf(layout_doc, str(dxf), build_components=False)
            review = review_dxf(built)
            if not review.passed:
                raise FidelityError(f"Clean layout DXF failed structural review on page {number}.")
            audit = output_root / "layout_audit" / f"page_{number:02d}.json"
            audit.parent.mkdir(parents=True, exist_ok=True)
            audit.write_text(json.dumps(_audit_page(image, raw, dpi, number, rendered), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            pages.append({
                "page": number,
                "paper_size_mm": [round(page_width_mm, 4), round(page_height_mm, 4)],
                "artifacts": {"rendered_png": _artifact(rendered, output_root), "layout_ir": _artifact(layout_ir, output_root), "layout_dxf": _artifact(dxf, output_root), "layout_audit": _artifact(audit, output_root)},
                "structural_roundtrip": "pass",
                "fidelity_state": "needs_review",
            })
    finally:
        document.close()
    manifest["pages"] = pages
    write_manifest(manifest_path, manifest)
