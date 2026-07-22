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
import numpy as np

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


def read_fidelity_manifest(path: Path) -> dict[str, Any]:
    """Load the private baseline manifest needed to generate overlays."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read fidelity manifest: {path}") from exc
    if manifest.get("schema_version") != FIDELITY_SCHEMA_VERSION:
        raise ManifestError("Unsupported fidelity manifest schema version.")
    if not manifest.get("private_artifact") or not isinstance(manifest.get("pages"), list):
        raise ManifestError("Fidelity manifest is missing private page records.")
    return manifest


def _safe_artifact_path(output_root: Path, record: dict[str, Any]) -> Path:
    artifact = record.get("artifact")
    if not isinstance(artifact, str) or Path(artifact).is_absolute():
        raise FidelityError("Fidelity artifact path must be a relative path.")
    resolved = (output_root / artifact).resolve()
    if not _is_within(resolved, output_root):
        raise FidelityError("Fidelity artifact path escapes the private output root.")
    if not resolved.is_file() or sha256_file(resolved) != record.get("sha256"):
        raise FidelityError("Fidelity artifact is missing or no longer matches its manifest hash.")
    return resolved


def _normalized_regions(regions: dict[str, Any], width: int, height: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def normalize(items: object, category: str) -> list[dict[str, Any]]:
        if not isinstance(items, list) or not items:
            raise FidelityError(f"Region proposal requires at least one {category} record.")
        result: list[dict[str, Any]] = []
        ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                raise FidelityError(f"Every {category} record requires a non-empty id.")
            if item["id"] in ids:
                raise FidelityError(f"Duplicate {category} id: {item['id']}")
            box = item.get("bbox_px")
            if not isinstance(box, list) or len(box) != 4 or any(isinstance(value, bool) or not isinstance(value, int) for value in box):
                raise FidelityError(f"{category} bbox_px must contain four integer coordinates.")
            x0, y0, x1, y1 = box
            if x0 < 0 or y0 < 0 or x1 > width or y1 > height or x1 - x0 < 30 or y1 - y0 < 30:
                raise FidelityError(f"{category} bbox_px is outside the page or too small.")
            purpose = item.get("purpose")
            expected = "layout-reconstruction" if category == "region" else "exclude"
            if purpose != expected:
                raise FidelityError(f"{category} purpose must be {expected!r}.")
            ids.add(item["id"])
            result.append({"id": item["id"], "bbox_px": box, "purpose": purpose})
        return result

    included = normalize(regions.get("regions"), "region")
    excluded = normalize(regions.get("excluded_regions"), "excluded_region")
    all_regions = [("region", item) for item in included] + [("excluded_region", item) for item in excluded]
    for index, (kind, item) in enumerate(all_regions):
        ax0, ay0, ax1, ay1 = item["bbox_px"]
        for other_kind, other in all_regions[index + 1:]:
            bx0, by0, bx1, by1 = other["bbox_px"]
            horizontal_gap = max(ax0 - bx1, bx0 - ax1, 0)
            vertical_gap = max(ay0 - by1, by0 - ay1, 0)
            if horizontal_gap < 3 and vertical_gap < 3:
                raise FidelityError(f"{kind} {item['id']!r} and {other_kind} {other['id']!r} overlap or lack the required 3 px gutter.")
    return included, excluded


def write_region_proposal(
    source: Path,
    output_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    page_number: int,
    regions: dict[str, Any],
    *,
    workspace_root: Path,
    revision: int = 1,
) -> dict[str, Any]:
    """Write a source-bound, review-only page-region proposal outside the repository."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    if revision <= 0:
        raise FidelityError("Region proposal revision must be positive.")
    if manifest_path.resolve().parent != output_root.resolve():
        raise FidelityError("Fidelity manifest must reside directly in the private output root.")
    verify_source(manifest, source)
    page = next((record for record in manifest.get("pages", []) if record.get("page") == page_number), None)
    if page is None:
        raise FidelityError(f"Fidelity manifest has no page {page_number}.")
    rendered = _safe_artifact_path(output_root, page.get("artifacts", {}).get("rendered_png", {}))
    audit = _safe_artifact_path(output_root, page.get("artifacts", {}).get("layout_audit", {}))
    audit_payload = json.loads(audit.read_text(encoding="utf-8"))
    source_page = audit_payload.get("source_page", {})
    if source_page.get("page") != page_number or source_page.get("render_sha256") != sha256_file(rendered):
        raise FidelityError("Layout audit render hash does not match the manifest artifact.")
    width = source_page.get("render_width_px")
    height = source_page.get("render_height_px")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise FidelityError("Layout audit is missing valid rendered page dimensions.")
    included, excluded = _normalized_regions(regions, width, height)
    definition = {"regions": included, "excluded_regions": excluded}
    definition_sha256 = __import__("hashlib").sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    proposal = {
        "schema_version": "fidelity-region-proposal-1.0",
        "private_artifact": True,
        "state": "needs_human_approval",
        "revision": revision,
        "source": manifest["source"],
        "page": {
            "number": page_number,
            "render_sha256": source_page["render_sha256"],
            "render_width_px": width,
            "render_height_px": height,
            "dpi": source_page["dpi"],
            "coordinate_system": "pixel-top-left",
        },
        "proposal_definition_sha256": definition_sha256,
        "minimum_gutter_px": 3,
        "unclassified_area_state": "needs_classification",
        "regions": included,
        "excluded_regions": excluded,
        "allowed_action": "layout-reconstruction-only",
        "prohibited_actions": ["model-export", "scale-approval", "mechanical-review", "mechanical-repair"],
    }
    suffix = "" if revision == 1 else f"-r{revision}"
    proposal_path = output_root / "region_proposals" / f"page_{page_number:02d}{suffix}.json"
    if proposal_path.exists():
        raise FidelityError(f"Region proposal already exists: {proposal_path}; create a new private staging root to revise it.")
    write_manifest(proposal_path, proposal)
    return proposal


def _audit_page(image, raw_geometry, dpi: int, page_number: int, rendered_path: Path) -> dict[str, Any]:
    height, width = image.shape[:2]
    _configure_tesseract(None)
    page_area = width * height
    detected = [
        roi for roi in detect_text_candidate_rois(image)
        if (roi[2] - roi[0]) * (roi[3] - roi[1]) <= page_area * 0.08
    ]
    # Hough-connected drawing strokes can form thousands of false text ROIs.
    # Audit a bounded set and retain the count so an omitted ROI is visible to
    # review instead of letting a private batch hang indefinitely.
    detected.sort(key=lambda roi: (roi[2] - roi[0]) * (roi[3] - roi[1]), reverse=True)
    rois = _deduplicate_rois([_title_block_roi(width, height), *detected[:8]])
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
        "ocr": {"engine": "tesseract-local", "psm": 11, "roi_limit": 9, "detected_roi_count": len(detected), "rois_px": [list(roi) for roi in rois], "texts": [_raw_text_payload(text) for text in texts]},
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
            relative_scale_delta = abs(scale_x - scale_y) / max(scale_x, scale_y)
            if relative_scale_delta > 0.002:
                raise FidelityError("Rendered page has a non-uniform pixel-to-paper transform.")
            # Raster dimensions are integral while PDF page boxes are not, so
            # a small X/Y difference is normal rounding. Use their mean for
            # the scalar Primitive IR contract and retain the page dimensions
            # in the manifest for the layout audit.
            paper_scale = (scale_x + scale_y) / 2.0
            raw = extract_raw_geometry(image, preset="real_scan_tuned_v1")
            layout_doc = build_document(
                file_name=rendered.name,
                page_index=number - 1,
                image_width_px=width,
                image_height_px=height,
                calibration=Calibration(
                    unit="mm",
                    pixel_to_unit_scale=paper_scale,
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
                "pixel_to_paper_mm": {"x": scale_x, "y": scale_y, "used": paper_scale},
                "artifacts": {"rendered_png": _artifact(rendered, output_root), "layout_ir": _artifact(layout_ir, output_root), "layout_dxf": _artifact(dxf, output_root), "layout_audit": _artifact(audit, output_root)},
                "structural_roundtrip": "pass",
                "fidelity_state": "needs_review",
            })
    finally:
        document.close()
    manifest["pages"] = pages
    write_manifest(manifest_path, manifest)


def _render_layout_dxf(dxf: Path, width_mm: float, height_mm: float, width_px: int, height_px: int) -> np.ndarray:
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext, layout
    from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

    document = ezdxf.readfile(dxf)
    backend = PyMuPdfBackend()
    Frontend(RenderContext(document), backend).draw_layout(document.modelspace(), finalize=True)
    png = backend.get_replay(layout.Page(width_mm, height_mm)).get_pixmap(144, alpha=True).tobytes("png")
    rendered = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if rendered is None:
        raise FidelityError("Could not rasterize clean layout DXF.")
    if rendered.shape[2] == 4:
        alpha = rendered[:, :, 3:4].astype(np.float32) / 255.0
        rendered = (rendered[:, :, :3].astype(np.float32) * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return cv2.resize(rendered, (width_px, height_px), interpolation=cv2.INTER_AREA)


def _edge_metrics(source_edges: np.ndarray, vector_edges: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    source = np.logical_and(source_edges > 0, mask > 0)
    vector = np.logical_and(vector_edges > 0, mask > 0)
    tolerance = cv2.dilate(source.astype(np.uint8), np.ones((7, 7), dtype=np.uint8)) > 0
    reverse_tolerance = cv2.dilate(vector.astype(np.uint8), np.ones((7, 7), dtype=np.uint8)) > 0
    precision = float(np.logical_and(vector, tolerance).sum() / max(1, vector.sum()))
    recall = float(np.logical_and(source, reverse_tolerance).sum() / max(1, source.sum()))
    return {"precision": round(precision, 6), "recall": round(recall, 6), "f1": round(2 * precision * recall / max(1e-12, precision + recall), 6)}


def _fidelity_report(rendered: Path, dxf: Path, paper_size: list[float], overlay: Path) -> dict[str, Any]:
    source = cv2.imread(str(rendered))
    if source is None:
        raise FidelityError("Could not read rendered PDF page for fidelity overlay.")
    height, width = source.shape[:2]
    vector = _render_layout_dxf(dxf, float(paper_size[0]), float(paper_size[1]), width, height)
    source_edges = cv2.Canny(cv2.cvtColor(source, cv2.COLOR_BGR2GRAY), 50, 150)
    vector_edges = cv2.Canny(cv2.cvtColor(vector, cv2.COLOR_BGR2GRAY), 50, 150)
    full_mask = np.full((height, width), 255, dtype=np.uint8)
    content_mask = full_mask.copy()
    content_mask[: int(height * 0.03), :] = 0
    content_mask[-int(height * 0.25):, :] = 0
    content_mask[:, : int(width * 0.03)] = 0
    content_mask[:, -int(width * 0.03):] = 0
    overlay_image = source.copy()
    overlap = np.logical_and(source_edges > 0, vector_edges > 0)
    overlay_image[source_edges > 0] = (0, 0, 255)
    overlay_image[vector_edges > 0] = (255, 255, 0)
    overlay_image[overlap] = (0, 255, 0)
    overlay.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(overlay), overlay_image):
        raise FidelityError("Could not write fidelity overlay.")
    return {
        "schema_version": "fidelity-report-1.0",
        "state": "needs_review",
        "metric": {"renderer": "ezdxf-pymupdf", "edge_detector": "canny-50-150", "tolerance_px": 3},
        "source_sha256": sha256_file(rendered),
        "dxf_sha256": sha256_file(dxf),
        "overlay_sha256": sha256_file(overlay),
        "full_page": _edge_metrics(source_edges, vector_edges, full_mask),
        "content_roi": _edge_metrics(source_edges, vector_edges, content_mask),
    }


def run_fidelity_overlays(source: Path, output_root: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != FIDELITY_SCHEMA_VERSION:
        raise ManifestError("Unsupported fidelity manifest schema version.")
    verify_source(manifest, source)
    for page in manifest.get("pages", []):
        artifacts = page["artifacts"]
        rendered = output_root / artifacts["rendered_png"]["artifact"]
        dxf = output_root / artifacts["layout_dxf"]["artifact"]
        overlay = output_root / "fidelity_overlay" / f"page_{page['page']:02d}.png"
        report_path = output_root / "fidelity_report" / f"page_{page['page']:02d}.json"
        report = _fidelity_report(rendered, dxf, page["paper_size_mm"], overlay)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        artifacts["fidelity_overlay"] = _artifact(overlay, output_root)
        artifacts["fidelity_report"] = _artifact(report_path, output_root)
    write_manifest(manifest_path, manifest)
