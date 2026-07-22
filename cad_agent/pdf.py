"""Resumable PDF-to-staged-DXF orchestration built from existing package APIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import ManifestError, completed_artifact, sha256_file, verify_source, write_manifest


PDF_MANIFEST_SCHEMA_VERSION = "pdf-run-1.0"
PDF_MANIFEST_NAME = "pdf-run-manifest.json"
PAGE_STAGES = ("primitive_ir", "semantic_ir", "dxf", "build_evidence")


def _stage(state: str = "pending", artifact: str | None = None, digest: str | None = None) -> dict[str, Any]:
    return {"state": state, "artifact": artifact, "sha256": digest, "details": None}


def new_pdf_manifest(source: Path, scale_mm_per_px: float, approval: str, dpi: int) -> dict[str, Any]:
    if not source.is_file():
        raise ManifestError(f"Input PDF does not exist: {source}")
    if scale_mm_per_px <= 0:
        raise ManifestError("PDF manual scale must be positive.")
    if dpi <= 0:
        raise ManifestError("PDF DPI must be positive.")
    if not approval.strip():
        raise ManifestError("PDF run requires a non-empty calibration approval reference.")
    return {
        "schema_version": PDF_MANIFEST_SCHEMA_VERSION,
        "source": {"name": source.name, "sha256": sha256_file(source), "kind": "pdf"},
        "configuration": {"scale_mm_per_px": scale_mm_per_px, "dpi": dpi},
        "approvals": {"calibration": {"approved": True, "reference": approval.strip()}},
        "render": _stage(artifact="pdf/manifest.json"),
        "pages": [],
    }


def read_pdf_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read PDF run manifest: {path}") from exc
    if manifest.get("schema_version") != PDF_MANIFEST_SCHEMA_VERSION:
        raise ManifestError("Unsupported PDF run manifest schema version.")
    if not isinstance(manifest.get("pages"), list) or not isinstance(manifest.get("render"), dict):
        raise ManifestError("PDF run manifest is missing render or page checkpoints.")
    return manifest


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


def _page_record(number: int, primitive: Path, rendered: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "page": number,
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
        pages.append(_page_record(int(item["page"]), primitive, rendered_png, output_dir))
    if not pages:
        raise ManifestError("PDF contains no renderable pages.")
    manifest["pages"] = pages
    write_manifest(manifest_path, manifest)


def run_pdf_stages(source: Path, output_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    verify_source(manifest, source)
    approval = manifest.get("approvals", {}).get("calibration", {})
    if approval.get("approved") is not True or not isinstance(approval.get("reference"), str):
        raise ManifestError("PDF run manifest has no recorded calibration approval.")
    _ensure_rendered(source, output_dir, manifest_path, manifest)

    # Import late to keep the PDF module usable independently of CLI argument parsing.
    from .cli import _run_dxf, _run_primitive, _run_semantic

    for page in manifest["pages"]:
        stages = page["stages"]
        primitive = output_dir / stages["primitive_ir"]["artifact"]
        if not _completed(output_dir, stages["primitive_ir"]):
            rendered = output_dir / page["rendered_png"]["artifact"]
            if not _completed(output_dir, page.get("rendered_png", {})):
                raise ManifestError(f"PDF page {page['page']} rendered-page checkpoint is invalid.")
            _run_primitive(rendered, primitive, float(manifest["configuration"]["scale_mm_per_px"]))
            _write_page_stage(manifest_path, manifest, page, "primitive_ir", primitive, "Primitive IR regenerated from verified rendered page.")
            stages["semantic_ir"] = _stage()
            stages["dxf"] = _stage()
            stages["build_evidence"] = _stage()
            write_manifest(manifest_path, manifest)
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
