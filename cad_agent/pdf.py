"""Resumable PDF-to-staged-DXF orchestration built from existing package APIs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .manifest import (
    ManifestError,
    classify_draft_reference,
    completed_artifact,
    sha256_file,
    validate_source_custody_reference,
    validate_source_fusion_evaluation_reference,
    validate_source_fusion_reference,
    validate_source_bundle_reference,
    verify_source,
    write_manifest,
)


PDF_MANIFEST_SCHEMA_VERSION = "pdf-run-1.0"
PDF_MANIFEST_NAME = "pdf-run-manifest.json"
PAGE_STAGES = ("primitive_ir", "semantic_ir", "dxf", "build_evidence")
NO_CALIBRATION_CANDIDATE_RESULT = "CALIBRATION_CANDIDATE_EXTRACTION_NOT_SUPPORTED_FOR_THIS_SOURCE"


def _is_valid_manual_scale(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _is_valid_resumed_manual_scale(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        scale = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(scale) and scale > 0


def _stage(state: str = "pending", artifact: str | None = None, digest: str | None = None) -> dict[str, Any]:
    return {"state": state, "artifact": artifact, "sha256": digest, "details": None}


def new_pdf_manifest(
    source: Path,
    scale_mm_per_px: float,
    approval: str,
    dpi: int,
    *,
    auto_ocr_roi: bool = False,
) -> dict[str, Any]:
    if not source.is_file():
        raise ManifestError(f"Input PDF does not exist: {source}")
    if not _is_valid_manual_scale(scale_mm_per_px):
        raise ManifestError("PDF manual scale must be a finite positive number.")
    if dpi <= 0:
        raise ManifestError("PDF DPI must be positive.")
    if not approval.strip():
        raise ManifestError("PDF run requires a non-empty calibration approval reference.")
    return classify_draft_reference({
        "schema_version": PDF_MANIFEST_SCHEMA_VERSION,
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "pdf"},
        "configuration": {
            "scale_mm_per_px": scale_mm_per_px,
            "dpi": dpi,
            "auto_ocr_roi": auto_ocr_roi,
        },
        "approvals": {"calibration": {"approved": True, "reference": approval.strip()}},
        "render": _stage(artifact="pdf/manifest.json"),
        "pages": [],
    })


def read_pdf_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read PDF run manifest: {path}") from exc
    if manifest.get("schema_version") != PDF_MANIFEST_SCHEMA_VERSION:
        raise ManifestError("Unsupported PDF run manifest schema version.")
    if not isinstance(manifest.get("pages"), list) or not isinstance(manifest.get("render"), dict):
        raise ManifestError("PDF run manifest is missing render or page checkpoints.")
    if "source_bundle" in manifest:
        manifest["source_bundle"] = validate_source_bundle_reference(manifest["source_bundle"])
    for key, validator in {
        "source_custody": validate_source_custody_reference,
        "source_fusion": validate_source_fusion_reference,
        "source_fusion_evaluation": validate_source_fusion_evaluation_reference,
    }.items():
        if key in manifest:
            manifest[key] = validator(manifest[key])
    return classify_draft_reference(manifest)


def _write_page_stage(
    manifest_path: Path,
    manifest: dict[str, Any],
    page: dict[str, Any],
    stage_name: str,
    artifact: Path,
    details: str,
) -> None:
    page["stages"][stage_name] = _stage(
        "completed",
        str(artifact.relative_to(manifest_path.parent)).replace("\\", "/"),
        sha256_file(artifact),
    )
    page["stages"][stage_name]["details"] = details
    write_manifest(manifest_path, manifest)


def _completed(output_dir: Path, stage: dict[str, Any]) -> bool:
    return completed_artifact(output_dir, stage)


def _requires_auto_ocr_checkpoint_regeneration(primitive_path: Path) -> bool:
    """Return whether a cached auto-OCR Primitive IR violates current policy."""
    try:
        primitive = json.loads(primitive_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    validations = primitive.get("cross_validations") if isinstance(primitive, dict) else None
    if not isinstance(validations, list):
        return True
    return any(
        not isinstance(validation, dict) or validation.get("status") != "unverified"
        for validation in validations
    )


def _page_record(
    number: int,
    primitive: Path,
    rendered: Path,
    output_dir: Path,
    scale_label_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "page": number,
        "scale_label_candidates": scale_label_candidates,
        "rendered_png": _stage(
            "completed",
            str(rendered.relative_to(output_dir)).replace("\\", "/"),
            sha256_file(rendered),
        ),
        "stages": {
            "primitive_ir": _stage(
                "completed",
                str(primitive.relative_to(output_dir)).replace("\\", "/"),
                sha256_file(primitive),
            ),
            "semantic_ir": _stage(),
            "dxf": _stage(),
            "build_evidence": _stage(),
        },
    }


def _ensure_rendered(source: Path, output_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    render = manifest["render"]
    if _completed(output_dir, render):
        return
    from primitive_ir_lib.run_pdf import run_pdf

    config = manifest["configuration"]
    run_pdf(
        source,
        output_dir / "pdf",
        scale_mm_per_px=float(config["scale_mm_per_px"]),
        dpi=int(config["dpi"]),
        preset="real_scan_tuned_v1",
        merge_lines=True,
        auto_ocr_roi=bool(config.get("auto_ocr_roi", False)),
    )
    rendered_manifest = output_dir / "pdf" / "manifest.json"
    if not rendered_manifest.is_file():
        raise ManifestError("PDF rendering did not produce its manifest.")
    manifest["render"] = _stage("completed", "pdf/manifest.json", sha256_file(rendered_manifest))
    manifest["render"]["details"] = "Primitive IR rendered and extracted for every PDF page."
    rendered = json.loads(rendered_manifest.read_text(encoding="utf-8"))
    pages: list[dict[str, Any]] = []
    for item in rendered.get("pages", []):
        primitive = output_dir / "pdf" / item["primitive_ir"]
        rendered_png = output_dir / "pdf" / item["rendered_png"]
        if not primitive.is_file():
            raise ManifestError(f"PDF render manifest references missing Primitive IR: {primitive}")
        if not rendered_png.is_file():
            raise ManifestError(f"PDF render manifest references missing rendered page: {rendered_png}")
        candidates = item.get("scale_label_candidates", [])
        if not isinstance(candidates, list):
            raise ManifestError("PDF render manifest has invalid scale-label candidates.")
        pages.append(_page_record(
            int(item["page"]),
            primitive,
            rendered_png,
            output_dir,
            candidates,
        ))
    if not pages:
        raise ManifestError("PDF contains no renderable pages.")
    manifest["pages"] = pages
    write_manifest(manifest_path, manifest)


def run_pdf_calibration_candidate(
    source: Path,
    output_dir: Path,
    manifest_path: Path,
    dpi: int,
    *,
    auto_ocr_roi: bool = True,
) -> dict[str, Any]:
    """Create review-only calibration evidence and stop before Semantic IR/DXF."""
    if not source.is_file():
        raise ManifestError(f"Input PDF does not exist: {source}")
    if dpi <= 0:
        raise ManifestError("PDF DPI must be positive.")
    if manifest_path.exists():
        raise ManifestError(f"PDF run manifest already exists: {manifest_path}; use resume-pdf instead.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ManifestError(f"Calibration-candidate output directory is not empty: {output_dir}")

    manifest = classify_draft_reference({
        "schema_version": PDF_MANIFEST_SCHEMA_VERSION,
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "pdf"},
        "configuration": {
            "calibration_mode": "auto_candidate",
            "dpi": dpi,
            "auto_ocr_roi": auto_ocr_roi,
        },
        "approvals": {"calibration": {"approved": False, "reference": None}},
        "result": "RUNNING",
        "render": _stage(artifact="pdf/manifest.json"),
        "pages": [],
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest_path, manifest)

    from primitive_ir_lib.run_image import CalibrationCandidateUnavailableError
    from primitive_ir_lib.run_pdf import run_pdf as run_primitive_pdf

    registry_path = output_dir / "calibration-registry.json"
    try:
        primitive_manifest = run_primitive_pdf(
            source,
            output_dir / "pdf",
            scale_mm_per_px=None,
            dpi=dpi,
            preset="real_scan_tuned_v1",
            merge_lines=True,
            auto_ocr_roi=auto_ocr_roi,
            auto_calibrate=True,
            calibration_registry_path=registry_path,
            calibration_id_prefix="run_pdf",
        )
    except CalibrationCandidateUnavailableError as exc:
        manifest["result"] = NO_CALIBRATION_CANDIDATE_RESULT
        manifest["details"] = str(exc)[:500]
        write_manifest(manifest_path, manifest)
        return manifest

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = {record.get("id"): record for record in registry.get("records", [])}
    lower_manifest_path = output_dir / "pdf" / "manifest.json"
    manifest["render"] = _stage(
        "completed",
        "pdf/manifest.json",
        sha256_file(lower_manifest_path),
    )
    manifest["render"]["details"] = "Pages rendered for review-only calibration candidates."

    for item in primitive_manifest.get("pages", []):
        page_number = int(item["page"])
        candidate_id = f"run_pdf_page{page_number:02d}"
        rendered = output_dir / "pdf" / item["rendered_png"]
        primitive = output_dir / "pdf" / item["primitive_ir"]
        if not rendered.is_file() or not primitive.is_file():
            raise ManifestError(f"Calibration candidate page {page_number} is missing an artifact.")
        primitive_payload = json.loads(primitive.read_text(encoding="utf-8"))
        calibration = primitive_payload.get("calibration")
        record = records.get(candidate_id)
        rendered_sha256 = sha256_file(rendered)
        if (
            not isinstance(calibration, dict)
            or calibration.get("status") != "needs_verification"
            or calibration.get("source_sha256") != rendered_sha256
            or not isinstance(record, dict)
            or record.get("status") != "needs_verification"
            or record.get("sha256") != rendered_sha256
        ):
            raise ManifestError(
                f"Calibration candidate page {page_number} is not hash-bound and needs_verification."
            )
        manifest["pages"].append({
            "page": page_number,
            "rendered_png": _stage(
                "completed",
                str(rendered.relative_to(output_dir)).replace("\\", "/"),
                rendered_sha256,
            ),
            "calibration": {
                "candidate_id": candidate_id,
                "status": "needs_verification",
                "estimated_scale_mm_per_px": calibration.get("pixel_to_unit_scale"),
                "method": calibration.get("method"),
                "source_sha256": rendered_sha256,
                "unit_interpretation": "unverified hypothesis; not source-proven physical units",
            },
            "stages": {
                "primitive_ir": _stage(
                    "completed",
                    str(primitive.relative_to(output_dir)).replace("\\", "/"),
                    sha256_file(primitive),
                ),
                "semantic_ir": _stage(),
                "dxf": _stage(),
                "build_evidence": _stage(),
            },
        })

    if not manifest["pages"]:
        raise ManifestError("PDF produced no reviewable calibration-candidate pages.")
    manifest["result"] = "CALIBRATION_NEEDS_VERIFICATION"
    manifest["approvals"]["calibration"] = {
        "approved": False,
        "reference": None,
        "status": "needs_verification",
    }
    write_manifest(manifest_path, manifest)
    return manifest


def run_pdf_stages(source: Path, output_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    verify_source(manifest, source)
    if manifest.get("configuration", {}).get("calibration_mode") == "auto_candidate":
        if manifest.get("result") == NO_CALIBRATION_CANDIDATE_RESULT:
            details = manifest.get("details")
            approvals = manifest.get("approvals")
            calibration_approval = approvals.get("calibration") if isinstance(approvals, dict) else None
            valid_terminal = (
                isinstance(details, str)
                and bool(details.strip())
                and len(details) <= 500
                and manifest.get("release_profile") == "DRAFT_REFERENCE"
                and manifest.get("authoritative_release_eligible") is False
                and isinstance(calibration_approval, dict)
                and calibration_approval.get("approved") is False
                and calibration_approval.get("reference") is None
                and isinstance(manifest.get("render"), dict)
                and manifest["render"].get("state") == "pending"
                and manifest.get("pages") == []
            )
            if not valid_terminal:
                raise ManifestError("Persisted no-candidate terminal diagnostics are invalid.")
            raise ManifestError(NO_CALIBRATION_CANDIDATE_RESULT)
        raise ManifestError("Auto-calibration candidate manifests cannot be resumed.")
    if not _is_valid_resumed_manual_scale(manifest.get("configuration", {}).get("scale_mm_per_px")):
        raise ManifestError("PDF manual scale must be a finite positive number.")
    approval = manifest.get("approvals", {}).get("calibration", {})
    if approval.get("approved") is not True or not isinstance(approval.get("reference"), str):
        raise ManifestError("PDF run manifest has no recorded calibration approval.")
    _ensure_rendered(source, output_dir, manifest_path, manifest)

    # Import late to keep the PDF module usable independently of CLI argument parsing.
    from .cli import _run_dxf, _run_primitive, _run_semantic

    for page in manifest["pages"]:
        stages = page["stages"]
        primitive = output_dir / stages["primitive_ir"]["artifact"]
        primitive_completed = _completed(output_dir, stages["primitive_ir"])
        if (
            primitive_completed
            and bool(manifest["configuration"].get("auto_ocr_roi", False))
            and _requires_auto_ocr_checkpoint_regeneration(primitive)
        ):
            primitive_completed = False
        if not primitive_completed:
            stages["primitive_ir"] = _stage(artifact=stages["primitive_ir"].get("artifact"))
            stages["semantic_ir"] = _stage(artifact=stages["semantic_ir"].get("artifact"))
            stages["dxf"] = _stage(artifact=stages["dxf"].get("artifact"))
            stages["build_evidence"] = _stage(artifact=stages["build_evidence"].get("artifact"))
            write_manifest(manifest_path, manifest)
            rendered = output_dir / page["rendered_png"]["artifact"]
            if not _completed(output_dir, page.get("rendered_png", {})):
                raise ManifestError(f"PDF page {page['page']} rendered-page checkpoint is invalid.")
            _run_primitive(
                rendered,
                primitive,
                float(manifest["configuration"]["scale_mm_per_px"]),
                auto_ocr_roi=bool(manifest["configuration"].get("auto_ocr_roi", False)),
            )
            _write_page_stage(manifest_path, manifest, page, "primitive_ir", primitive, "Primitive IR regenerated from verified rendered page.")
        semantic = output_dir / "semantic_ir" / f"page_{page['page']:02d}.json"
        dxf = output_dir / "dxf" / f"page_{page['page']:02d}.dxf"
        evidence = output_dir / "build_evidence" / f"page_{page['page']:02d}.json"
        if not _completed(output_dir, stages["semantic_ir"]):
            semantic.parent.mkdir(parents=True, exist_ok=True)
            _run_semantic(primitive, semantic)
            _write_page_stage(manifest_path, manifest, page, "semantic_ir", semantic, "Semantic IR generated.")
            stages["dxf"] = _stage()
            stages["build_evidence"] = _stage()
            write_manifest(manifest_path, manifest)
        if not _completed(output_dir, stages["dxf"]):
            dxf.parent.mkdir(parents=True, exist_ok=True)
            evidence.parent.mkdir(parents=True, exist_ok=True)
            _run_dxf(primitive, semantic, dxf, evidence)
            _write_page_stage(manifest_path, manifest, page, "dxf", dxf, "Staged DXF built and headlessly reviewed.")
            _write_page_stage(manifest_path, manifest, page, "build_evidence", evidence, "SHA-bound BuildResult evidence persisted.")
        elif not _completed(output_dir, stages["build_evidence"]):
            stages["dxf"] = _stage()
            stages["build_evidence"] = _stage()
            write_manifest(manifest_path, manifest)
            _run_dxf(primitive, semantic, dxf, evidence)
            _write_page_stage(manifest_path, manifest, page, "dxf", dxf, "Staged DXF rebuilt with fresh evidence.")
            _write_page_stage(manifest_path, manifest, page, "build_evidence", evidence, "SHA-bound BuildResult evidence persisted.")
