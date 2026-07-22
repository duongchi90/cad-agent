"""Private, paper-coordinate PDF layout baseline.

This module intentionally creates a diagnostic layout DXF, not a model-space
conversion. It keeps OCR and scale observations in sidecars so unreviewed text
or calibration can never be mistaken for CAD source geometry.
"""

from __future__ import annotations

import json
import os
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
from primitive_ir_lib.table_extraction import build_cells, detect_grid
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


def write_region_approval(
    source: Path, output_root: Path, manifest: dict[str, Any], page_number: int, revision: int,
    region_ids: list[str], approval_reference: str, *, workspace_root: Path,
) -> dict[str, Any]:
    """Freeze an explicit human approval for selected region-proposal records."""
    if _is_within(output_root, workspace_root) or revision <= 0 or not approval_reference.strip():
        raise FidelityError("Region approval requires an external root, positive revision, and approval reference.")
    verify_source(manifest, source)
    suffix = "" if revision == 1 else f"-r{revision}"
    proposal_path = output_root / "region_proposals" / f"page_{page_number:02d}{suffix}.json"
    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Cannot read the region proposal to approve.") from exc
    if proposal.get("state") != "needs_human_approval" or proposal.get("source") != manifest.get("source"):
        raise FidelityError("Region proposal is not eligible for approval.")
    page = proposal.get("page", {})
    if page.get("number") != page_number:
        raise FidelityError("Region proposal page does not match the approval request.")
    available = {item["id"] for item in proposal.get("regions", [])}
    if not region_ids or len(set(region_ids)) != len(region_ids) or not set(region_ids) <= available:
        raise FidelityError("Approval must name one or more unique region ids from the proposal.")
    approval = {
        "schema_version": "fidelity-region-approval-1.0",
        "private_artifact": True,
        "state": "approved-layout-reconstruction-only",
        "source": manifest["source"],
        "page": page,
        "proposal": {"artifact": str(proposal_path.relative_to(output_root)).replace("\\", "/"), "sha256": sha256_file(proposal_path), "definition_sha256": proposal["proposal_definition_sha256"], "revision": revision},
        "approved_region_ids": region_ids,
        "approval_reference": approval_reference.strip(),
        "prohibited_actions": ["model-export", "scale-approval", "mechanical-review", "mechanical-repair"],
    }
    approval_path = output_root / "region_approvals" / f"page_{page_number:02d}{suffix}.json"
    if approval_path.exists():
        raise FidelityError(f"Region approval already exists: {approval_path}")
    write_manifest(approval_path, approval)
    return approval


def run_fidelity_reconstruct(
    source: Path, output_root: Path, manifest: dict[str, Any], approval_path: Path, *, workspace_root: Path,
) -> list[Path]:
    """Build fresh, clean geometry candidates for explicitly approved regions."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root):
        raise FidelityError("Region approval must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Cannot read region approval.") from exc
    if approval.get("state") != "approved-layout-reconstruction-only" or approval.get("source") != manifest.get("source"):
        raise FidelityError("Region approval is not valid for this source.")
    proposal_record = approval.get("proposal", {})
    proposal_path = _safe_artifact_path(output_root, {"artifact": proposal_record.get("artifact"), "sha256": proposal_record.get("sha256")})
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    if proposal.get("proposal_definition_sha256") != proposal_record.get("definition_sha256"):
        raise FidelityError("Approved proposal definition no longer matches its approval.")
    page_number = approval.get("page", {}).get("number")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Approved page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if approval["page"].get("render_sha256") != sha256_file(rendered):
        raise FidelityError("Region approval render hash no longer matches the page artifact.")
    image = cv2.imread(str(rendered))
    if image is None:
        raise FidelityError("Cannot read approved rendered page.")
    selected = [item for item in proposal["regions"] if item["id"] in approval["approved_region_ids"]]
    from dxf_builder_lib.builder import build_dxf
    results: list[Path] = []
    scale = float(page["pixel_to_paper_mm"]["used"])
    for region in selected:
        x0, y0, x1, y1 = region["bbox_px"]
        crop = image[y0:y1, x0:x1]
        raw = extract_raw_geometry(crop, preset="real_scan_tuned_v1")
        candidate_root = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"]
        if candidate_root.exists():
            raise FidelityError(f"Reconstruction candidate already exists: {candidate_root}")
        candidate_root.mkdir(parents=True)
        doc = build_document(
            file_name=f"page_{page_number:02d}_{region['id']}.png", page_index=page_number - 1,
            image_width_px=crop.shape[1], image_height_px=crop.shape[0],
            calibration=Calibration(unit="mm", pixel_to_unit_scale=scale, origin_px=(0.0, float(crop.shape[0])), method="manual_override", reference_note="Approved fidelity-layout region in paper millimetres."),
            raw_lines=raw.lines, raw_circles=raw.circles, raw_texts=[], sha256=sha256_file(rendered),
        )
        dxf = candidate_root / "geometry.dxf"
        build_dxf(doc, str(dxf), build_components=False)
        vector = _render_layout_dxf(dxf, crop.shape[1] * scale, crop.shape[0] * scale, crop.shape[1], crop.shape[0])
        source_edges = cv2.Canny(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 50, 150)
        vector_edges = cv2.Canny(cv2.cvtColor(vector, cv2.COLOR_BGR2GRAY), 50, 150)
        overlay = crop.copy(); overlap = (source_edges > 0) & (vector_edges > 0)
        overlay[source_edges > 0] = (0, 0, 255); overlay[vector_edges > 0] = (255, 255, 0); overlay[overlap] = (0, 255, 0)
        cv2.imwrite(str(candidate_root / "source.png"), crop); cv2.imwrite(str(candidate_root / "overlay.png"), overlay)
        (candidate_root / "report.json").write_text(json.dumps({"state": "needs_review", "profile": "fidelity-layout", "approval_sha256": sha256_file(approval_path), "region": region, "entities": {"LINE": len(raw.lines), "CIRCLE": len(raw.circles)}, "edge_metric": _edge_metrics(source_edges, vector_edges, np.full(crop.shape[:2], 255, dtype=np.uint8)), "unresolved": ["text/dimensions/linetypes/tables remain sidecar-only", "no model export"]}, indent=2) + "\n", encoding="utf-8")
        results.append(candidate_root)
    return results


def run_fidelity_observations(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> list[Path]:
    """Record bounded table-grid observations for every private fidelity page."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    outputs: list[Path] = []
    for page in manifest.get("pages", []):
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        image = cv2.imread(str(rendered))
        if image is None:
            raise FidelityError("Cannot read rendered page for observations.")
        height, width = image.shape[:2]
        roi = (0, int(height * 0.65), width, height)
        raw = extract_raw_geometry(image, preset="real_scan_tuned_v1")
        xs, ys = detect_grid(raw.lines, roi)
        cells = build_cells(xs, ys, roi)
        status = "needs_review" if len(xs) >= 3 and len(ys) >= 3 and len(cells) <= 200 else "not_evaluated"
        reason = None if status == "needs_review" else "grid requires at least three axes each and no more than 200 cells"
        output = output_root / "fidelity_observations" / f"page_{page['page']:02d}.json"
        if output.exists():
            raise FidelityError(f"Fidelity observation already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "fidelity-observation-1.0", "private_artifact": True, "state": status, "source_render_sha256": sha256_file(rendered), "table_grid": {"roi_px": list(roi), "vertical_axes_px": xs, "horizontal_axes_px": ys, "cells": [list(cell.bbox_px) for cell in cells] if status == "needs_review" else [], "reason": reason}, "line_patterns": _observe_line_patterns(raw.lines), "unresolved": ["no cell OCR or DXF text is emitted without table-region approval", "line patterns do not define a DXF linetype without an explicit approved mapping"]}
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def run_fidelity_text_observations(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> list[Path]:
    """Write hash-bound OCR candidates for later per-text review, never DXF text."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    outputs: list[Path] = []
    for page in manifest.get("pages", []):
        audit_record = page["artifacts"]["layout_audit"]
        audit_path = _safe_artifact_path(output_root, audit_record)
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        raw_texts = audit.get("ocr", {}).get("texts", [])
        candidates = [
            {
                "id": item["id"],
                "content": item["content"].strip(),
                "bbox_px": item["bbox_px"],
                "rotation_deg": item["rotation_deg"],
                "confidence": item["confidence"],
                "source": item["source"],
                "semantic_role": item["semantic_role"],
                "parsed_value": item["parsed_value"],
            }
            for item in raw_texts
            if isinstance(item, dict) and isinstance(item.get("content"), str) and item["content"].strip()
        ]
        output = output_root / "fidelity_text_observations" / f"page_{page['page']:02d}.json"
        if output.exists():
            raise FidelityError(f"Fidelity text observation already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "fidelity-text-observation-1.0",
            "private_artifact": True,
            "state": "needs_human_approval" if candidates else "not_evaluated",
            "source": manifest["source"],
            "page": page["page"],
            "source_layout_audit": audit_record,
            "candidates": candidates,
            "unresolved": ["no OCR candidate is emitted as DXF TEXT or MTEXT without per-text approval and a Unicode glyph-render check"],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def run_fidelity_compose(source: Path, output_root: Path, manifest: dict[str, Any], approval_path: Path, *, workspace_root: Path) -> Path:
    """Place approved local geometry back into a paper-coordinate review page."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root):
        raise FidelityError("Region approval must reside inside the private fidelity output root.")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("state") != "approved-layout-reconstruction-only" or approval.get("source") != manifest.get("source"):
        raise FidelityError("Region approval is not valid for composition.")
    page_number = approval["page"]["number"]
    page = next((item for item in manifest["pages"] if item["page"] == page_number), None)
    if page is None:
        raise FidelityError("Approved page is absent from the fidelity manifest.")
    rendered_for_hash = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if approval["page"].get("render_sha256") != sha256_file(rendered_for_hash):
        raise FidelityError("Region approval render hash no longer matches the page artifact.")
    proposal_path = _safe_artifact_path(output_root, approval["proposal"])
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    selected = [item for item in proposal["regions"] if item["id"] in approval["approved_region_ids"]]
    suffix = "" if approval["proposal"]["revision"] == 1 else f"-r{approval['proposal']['revision']}"
    root = output_root / "reconstruction_pages" / f"page_{page_number:02d}{suffix}"
    if root.exists():
        raise FidelityError(f"Composed fidelity page already exists: {root}")
    import ezdxf

    composed = ezdxf.new("R2010")
    composed.header["$INSUNITS"] = 4
    model = composed.modelspace()
    scale = float(page["pixel_to_paper_mm"]["used"])
    height_px = approval["page"]["render_height_px"]
    for region in selected:
        candidate = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"] / "geometry.dxf"
        if not candidate.is_file():
            raise FidelityError(f"Missing approved region candidate: {candidate}")
        x0, _, _, y1 = region["bbox_px"]
        offset_x, offset_y = x0 * scale, (height_px - y1) * scale
        for entity in ezdxf.readfile(candidate).modelspace():
            if entity.dxftype() == "LINE":
                a, b = entity.dxf.start, entity.dxf.end
                model.add_line((a.x + offset_x, a.y + offset_y), (b.x + offset_x, b.y + offset_y), dxfattribs={"layer": "FIDELITY_GEOMETRY"})
            elif entity.dxftype() == "CIRCLE":
                c = entity.dxf.center
                model.add_circle((c.x + offset_x, c.y + offset_y), entity.dxf.radius, dxfattribs={"layer": "FIDELITY_GEOMETRY"})
    root.mkdir(parents=True)
    dxf = root / "layout.dxf"; composed.saveas(dxf)
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    image = cv2.imread(str(rendered))
    if image is None:
        raise FidelityError("Cannot read rendered page for composition.")
    # The drawing renderer fits model extents to a page. Render each local
    # candidate at its native crop size and paste it back at the approved pixel
    # rectangle so the comparison preserves sheet coordinates.
    vector = np.full_like(image, 255)
    for region in selected:
        x0, y0, x1, y1 = region["bbox_px"]
        candidate = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"] / "geometry.dxf"
        local_vector = _render_layout_dxf(candidate, (x1 - x0) * scale, (y1 - y0) * scale, x1 - x0, y1 - y0)
        vector[y0:y1, x0:x1] = local_vector
    source_edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 50, 150); vector_edges = cv2.Canny(cv2.cvtColor(vector, cv2.COLOR_BGR2GRAY), 50, 150)
    overlay = image.copy(); overlap = (source_edges > 0) & (vector_edges > 0); overlay[source_edges > 0] = (0, 0, 255); overlay[vector_edges > 0] = (255, 255, 0); overlay[overlap] = (0, 255, 0)
    cv2.imwrite(str(root / "overlay.png"), overlay)
    (root / "report.json").write_text(json.dumps({"state": "needs_review", "profile": "fidelity-layout", "approval_sha256": sha256_file(approval_path), "edge_metric": _edge_metrics(source_edges, vector_edges, np.full(image.shape[:2], 255, dtype=np.uint8)), "unresolved": ["unselected content remains absent", "no text/dimensions/linetypes/tables/model export"]}, indent=2) + "\n", encoding="utf-8")
    return root


def write_fidelity_review_index(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> Path:
    """Write a private static index linking the existing per-page review artifacts."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    index = output_root / "fidelity_review" / "index.html"
    if index.exists():
        raise FidelityError(f"Fidelity review index already exists: {index}")
    cards: list[str] = []
    for page in manifest.get("pages", []):
        artifacts = page["artifacts"]
        rendered = _safe_artifact_path(output_root, artifacts["rendered_png"])
        overlay_record = artifacts.get("fidelity_overlay")
        overlay = _safe_artifact_path(output_root, overlay_record) if isinstance(overlay_record, dict) else None
        observation = output_root / "fidelity_observations" / f"page_{page['page']:02d}.json"
        table_state = "not run"
        if observation.is_file():
            table_state = json.loads(observation.read_text(encoding="utf-8")).get("state", "unknown")
        rel_rendered = Path(os.path.relpath(rendered, index.parent)).as_posix()
        rel_overlay = Path(os.path.relpath(overlay, index.parent)).as_posix() if overlay else None
        overlay_html = f'<img src="{rel_overlay}" alt="overlay page {page["page"]}">' if rel_overlay else "<p>overlay not generated</p>"
        cards.append(f'<section><h2>Page {page["page"]} <small>table: {table_state}</small></h2><div><figure><figcaption>PDF render</figcaption><img src="{rel_rendered}" alt="PDF page {page["page"]}"></figure><figure><figcaption>DXF overlay</figcaption>{overlay_html}</figure></div></section>')
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("<!doctype html><meta charset='utf-8'><title>Private Fidelity Review</title><style>body{font:14px sans-serif;margin:20px;background:#f5f5f5}section{background:#fff;padding:12px;margin:12px 0}section>div{display:flex;gap:12px}figure{width:48%;margin:0}img{max-width:100%;border:1px solid #bbb}small{font-weight:normal;color:#666}</style><h1>Private fidelity review - needs review</h1>" + "\n".join(cards), encoding="utf-8")
    return index


def write_fidelity_review_queue(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> Path:
    """Summarize page-level private review work without promoting any candidate."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    queue_path = output_root / "fidelity_review" / "queue.json"
    if queue_path.exists():
        raise FidelityError(f"Fidelity review queue already exists: {queue_path}")
    items: list[dict[str, Any]] = []
    for page in manifest.get("pages", []):
        number = page["page"]
        observation = output_root / "fidelity_observations" / f"page_{number:02d}.json"
        table_state = "not_run"
        if observation.is_file():
            table_state = json.loads(observation.read_text(encoding="utf-8")).get("state", "unknown")
        approvals = sorted((output_root / "region_approvals").glob(f"page_{number:02d}*.json")) if (output_root / "region_approvals").is_dir() else []
        items.append({"page": number, "state": "needs_review", "priority": 1 if number == 5 else 2, "table_observation": table_state, "approved_region_records": [path.relative_to(output_root).as_posix() for path in approvals], "next_action": "reconstruct approved region" if approvals else "select and approve a reconstruction region"})
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps({"schema_version": "fidelity-review-queue-1.0", "private_artifact": True, "state": "needs_review", "items": items}, indent=2) + "\n", encoding="utf-8")
    return queue_path


def _observe_line_patterns(lines: list[Any]) -> list[dict[str, Any]]:
    """Find conservative runs of separated, axis-aligned raw segments."""
    result: list[dict[str, Any]] = []
    for axis in ("horizontal", "vertical"):
        groups: dict[int, list[tuple[float, float]]] = {}
        for line in lines:
            x0, y0, x1, y1 = line.bbox_px
            if axis == "horizontal" and abs(y1 - y0) <= 3 and x1 - x0 >= 8:
                groups.setdefault(round((y0 + y1) / 2 / 4) * 4, []).append((x0, x1))
            if axis == "vertical" and abs(x1 - x0) <= 3 and y1 - y0 >= 8:
                groups.setdefault(round((x0 + x1) / 2 / 4) * 4, []).append((y0, y1))
        for coordinate, spans in groups.items():
            spans.sort()
            if len(spans) < 3:
                continue
            gaps = [round(spans[index + 1][0] - spans[index][1], 2) for index in range(len(spans) - 1)]
            positive = [gap for gap in gaps if 2 <= gap <= 40]
            if len(positive) >= 2:
                result.append({"axis": axis, "coordinate_px": coordinate, "segment_count": len(spans), "median_gap_px": float(np.median(positive)), "status": "needs_review"})
    return result


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
    if _is_within(output_root, Path.cwd()) or manifest_path.resolve().parent != output_root.resolve():
        raise FidelityError("Fidelity overlay requires a private manifest directly under its external output root.")
    for page in manifest.get("pages", []):
        artifacts = page["artifacts"]
        rendered = _safe_artifact_path(output_root, artifacts["rendered_png"])
        dxf = _safe_artifact_path(output_root, artifacts["layout_dxf"])
        overlay = output_root / "fidelity_overlay" / f"page_{page['page']:02d}.png"
        report_path = output_root / "fidelity_report" / f"page_{page['page']:02d}.json"
        report = _fidelity_report(rendered, dxf, page["paper_size_mm"], overlay)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        artifacts["fidelity_overlay"] = _artifact(overlay, output_root)
        artifacts["fidelity_report"] = _artifact(report_path, output_root)
    write_manifest(manifest_path, manifest)
