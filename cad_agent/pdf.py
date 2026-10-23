"""Resumable PDF-to-staged-DXF orchestration built from existing package APIs."""

from __future__ import annotations

import json
import math
import os
import stat
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


def _completed(
    output_dir: Path,
    stage: dict[str, Any],
    artifact_path: Path | None = None,
) -> bool:
    if artifact_path is None:
        return completed_artifact(output_dir, stage)
    artifact = stage.get("artifact")
    digest = stage.get("sha256")
    if stage.get("state") != "completed" or not isinstance(artifact, str) or not isinstance(digest, str):
        return False
    return artifact_path.is_file() and sha256_file(artifact_path) == digest


def _canonical_pdf_resume_path(path: Path) -> Path:
    resolved = path.resolve()
    if os.name != "nt":
        return resolved

    # Windows can resolve two aliases of the same path to inconsistent 8.3
    # spellings. Expand the deepest existing prefix, then retain any missing
    # leaf components for destinations that have not been created yet.
    missing: list[str] = []
    existing = resolved
    while not existing.exists():
        if existing.parent == existing:
            raise ManifestError("Cannot canonicalize PDF artifact path.")
        missing.append(existing.name)
        existing = existing.parent

    import ctypes

    get_long_path = ctypes.windll.kernel32.GetLongPathNameW
    get_long_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
    get_long_path.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_long_path(str(existing), buffer, len(buffer))
    if not length or length >= len(buffer):
        raise ManifestError("Cannot canonicalize PDF artifact path.")
    return Path(buffer.value).joinpath(*reversed(missing))


def _resolve_pdf_resume_artifact(
    output_root: Path,
    artifact: object,
    expected_relative_path: str,
    owner: str,
) -> Path:
    if not isinstance(artifact, str) or not artifact.strip():
        raise ManifestError(f"PDF {owner} artifact path is missing or invalid.")
    relative = Path(artifact)
    if relative.is_absolute() or relative.drive:
        raise ManifestError(f"PDF {owner} artifact path must be relative to the output root.")
    if os.path.normcase(relative.as_posix()) != os.path.normcase(expected_relative_path):
        raise ManifestError(f"PDF {owner} artifact path does not match its canonical destination.")
    resolved_root = _canonical_pdf_resume_path(output_root)
    resolved = _canonical_pdf_resume_path(output_root / relative)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ManifestError(f"PDF {owner} artifact path escapes the output root.") from exc
    expected_destination = _canonical_pdf_resume_path(output_root / expected_relative_path)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(expected_destination)):
        raise ManifestError(f"PDF {owner} artifact path aliases a different filesystem destination.")
    return resolved


def _validate_pdf_write_roots(output_root: Path, manifest_path: Path) -> None:
    """Reject redirected or multiply-linked existing targets before PDF writes."""
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    pending = [
        output_root / relative
        for relative in ("pdf", "semantic_ir", "dxf", "build_evidence")
    ]
    pending.append(manifest_path)
    while pending:
        path = pending.pop()
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ManifestError(f"Cannot verify PDF output destination: {path}") from exc

        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & reparse_point:
            raise ManifestError(f"PDF output artifact path contains a symlink or reparse point: {path}")
        if stat.S_ISREG(info.st_mode):
            if getattr(info, "st_nlink", 1) > 1:
                raise ManifestError(f"PDF output file has multiple hard links: {path}")
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ManifestError(f"PDF output destination is not a regular file or directory: {path}")
        try:
            pending.extend(path.iterdir())
        except OSError as exc:
            raise ManifestError(f"Cannot inspect PDF output directory: {path}") from exc


def _validate_pdf_resume_artifacts(
    output_root: Path,
    manifest_path: Path,
    source: Path,
    manifest: dict[str, Any],
) -> dict[tuple[int | str, str], Path]:
    """Resolve and validate every PDF checkpoint destination before it is consumed."""
    resolved_root = output_root.resolve()
    manifest_lexical = manifest_path.absolute()
    # Create only the requested output root so physical directory identity can
    # be checked. `Path.resolve()` can retain a Windows 8.3 alias on one path
    # while returning the long path on another, even when both name this root.
    resolved_root.mkdir(parents=True, exist_ok=True)
    _validate_pdf_write_roots(resolved_root, manifest_path)
    if manifest_path.exists() and source.exists():
        try:
            manifest_aliases_source = os.path.samefile(manifest_path, source)
        except OSError as exc:
            raise ManifestError("Cannot verify PDF run manifest identity.") from exc
        if manifest_aliases_source:
            raise ManifestError("PDF run manifest aliases the source PDF.")
    try:
        manifest_parent_matches = os.path.samefile(manifest_lexical.parent, resolved_root)
    except OSError:
        manifest_parent_matches = False
    if (
        not manifest_parent_matches
        or manifest_path.is_symlink()
        or (manifest_path.exists() and not manifest_path.is_file())
    ):
        raise ManifestError("PDF run manifest must be a regular file in the output root.")
    paths: dict[tuple[int | str, str], Path] = {}
    owners: list[tuple[str, Path]] = []

    def register(owner: str, key: tuple[int | str, str], path: Path) -> None:
        protected = [("source PDF", source.resolve()), ("run manifest", manifest_path.resolve())]
        for protected_owner, protected_path in protected:
            if os.path.normcase(str(path)) == os.path.normcase(str(protected_path)):
                raise ManifestError(f"PDF {owner} artifact aliases the {protected_owner}.")
            if path.is_file() and protected_path.is_file():
                try:
                    aliases = os.path.samefile(path, protected_path)
                except OSError as exc:
                    raise ManifestError(f"Cannot verify PDF {owner} artifact identity.") from exc
                if aliases:
                    raise ManifestError(f"PDF {owner} artifact aliases the {protected_owner}.")
        for prior_owner, prior_path in owners:
            if os.path.normcase(str(path)) == os.path.normcase(str(prior_path)):
                raise ManifestError(f"PDF {owner} artifact aliases {prior_owner}.")
            if path.is_file() and prior_path.is_file():
                try:
                    aliases = os.path.samefile(path, prior_path)
                except OSError as exc:
                    raise ManifestError(f"Cannot verify PDF {owner} artifact identity.") from exc
                if aliases:
                    raise ManifestError(f"PDF {owner} artifact aliases {prior_owner}.")
        paths[key] = path
        owners.append((owner, path))

    render_record = manifest.get("render")
    if not isinstance(render_record, dict):
        raise ManifestError("PDF run manifest has no valid render checkpoint.")
    render_path = _resolve_pdf_resume_artifact(
        resolved_root,
        render_record.get("artifact"),
        "pdf/manifest.json",
        "render manifest",
    )
    register("render manifest", ("run", "render"), render_path)

    # These fixed owner directories must not redirect writes outside the run
    # root, including when the run has not produced page records yet.
    for relative in (
        "pdf/rendered/page_01.png",
        "pdf/primitive_ir/page_01.json",
        "semantic_ir/page_01.json",
        "dxf/page_01.dxf",
        "build_evidence/page_01.json",
    ):
        _resolve_pdf_resume_artifact(resolved_root, relative, relative, "output directory")

    pages = manifest.get("pages")
    if not isinstance(pages, list):
        raise ManifestError("PDF run manifest has invalid page checkpoints.")
    if not pages:
        if render_record.get("state") == "completed":
            raise ManifestError("Completed PDF render checkpoint has no page records.")
        return paths
    page_numbers: set[int] = set()
    stage_paths = {
        "primitive_ir": "pdf/primitive_ir/page_{page:02d}.json",
        "semantic_ir": "semantic_ir/page_{page:02d}.json",
        "dxf": "dxf/page_{page:02d}.dxf",
        "build_evidence": "build_evidence/page_{page:02d}.json",
    }
    for page in pages:
        if not isinstance(page, dict):
            raise ManifestError("PDF run manifest contains an invalid page checkpoint.")
        page_number = page.get("page")
        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise ManifestError("PDF page checkpoint has an invalid page identity.")
        if page_number in page_numbers:
            raise ManifestError("PDF run manifest contains duplicate page identities.")
        page_numbers.add(page_number)

        rendered_record = page.get("rendered_png")
        if not isinstance(rendered_record, dict):
            raise ManifestError(f"PDF page {page_number} has no rendered-page checkpoint.")
        rendered_path = _resolve_pdf_resume_artifact(
            resolved_root,
            rendered_record.get("artifact"),
            f"pdf/rendered/page_{page_number:02d}.png",
            f"page {page_number} rendered-page",
        )
        register(f"page {page_number} rendered-page", (page_number, "rendered_png"), rendered_path)

        stages = page.get("stages")
        if not isinstance(stages, dict):
            raise ManifestError(f"PDF page {page_number} has invalid stages.")
        for stage_name, template in stage_paths.items():
            stage = stages.get(stage_name)
            if not isinstance(stage, dict):
                raise ManifestError(f"PDF page {page_number} has no {stage_name} checkpoint.")
            expected = template.format(page=page_number)
            artifact = stage.get("artifact")
            if artifact is None and stage.get("state") != "completed" and stage_name != "primitive_ir":
                artifact = expected
            path = _resolve_pdf_resume_artifact(
                resolved_root,
                artifact,
                expected,
                f"page {page_number} {stage_name}",
            )
            register(f"page {page_number} {stage_name}", (page_number, stage_name), path)
    return paths


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


def _pdf_page_identity(page: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "page_index",
        "page",
        "page_rotation",
        "page_cropbox",
        "page_rotation_matrix",
        "render_scale_px_per_point",
        "pixmap_origin_px",
    )
    if any(key not in page for key in keys):
        raise ManifestError("PDF page render identity is incomplete.")
    return {key: page[key] for key in keys}


def _regenerate_primitive_from_pdf(
    source: Path,
    output_dir: Path,
    page: dict[str, Any],
    primitive: Path,
    manifest: dict[str, Any],
    manifest_path: Path,
    artifact_paths: dict[tuple[int | str, str], Path],
) -> None:
    """Regenerate one invalid page IR through the source-aware PDF owner."""
    import shutil
    import tempfile

    from primitive_ir_lib.run_pdf import run_pdf

    config = manifest["configuration"]
    source_info = manifest.get("source")
    source_sha256 = source_info.get("sha256") if isinstance(source_info, dict) else None
    render_stage = manifest.get("render")
    if (
        not isinstance(source_sha256, str)
        or not isinstance(render_stage, dict)
        or not _completed(output_dir, render_stage, artifact_paths[("run", "render")])
    ):
        raise ManifestError("PDF source or render checkpoint is invalid for Primitive IR recovery.")

    existing_render_manifest_path = artifact_paths[("run", "render")]
    try:
        existing_render_manifest = json.loads(
            existing_render_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError("PDF render manifest cannot be read for Primitive IR recovery.") from exc
    if (
        existing_render_manifest.get("status") != "complete"
        or existing_render_manifest.get("source_pdf_sha256") != source_sha256
        or existing_render_manifest.get("render_dpi") != int(config["dpi"])
        or existing_render_manifest.get("scale_mm_per_px") != float(config["scale_mm_per_px"])
    ):
        raise ManifestError("PDF render manifest identity does not match the run configuration.")

    page_number = page.get("page")
    page_index = page_number - 1 if isinstance(page_number, int) else None
    existing_pages = [
        item for item in existing_render_manifest.get("pages", [])
        if isinstance(item, dict)
        and item.get("page") == page_number
        and item.get("page_index") == page_index
    ]
    if len(existing_pages) != 1:
        raise ManifestError("PDF render manifest does not identify exactly one requested page.")
    existing_page = existing_pages[0]
    old_rendered = artifact_paths[(page_number, "rendered_png")]
    if (
        not _completed(output_dir, page.get("rendered_png", {}), old_rendered)
        or existing_page.get("rendered_png_sha256") != page["rendered_png"].get("sha256")
        or sha256_file(old_rendered) != page["rendered_png"].get("sha256")
    ):
        raise ManifestError("Verified rendered page does not match its PDF source identity.")

    identity = _pdf_page_identity(existing_page)
    if identity["page"] != page_number or identity["page_index"] != page_index:
        raise ManifestError("PDF render manifest page identity does not match the requested page.")

    with tempfile.TemporaryDirectory(
        prefix="cad-agent-pdf-resume-",
        dir=output_dir.parent,
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        regenerated_manifest = run_pdf(
            source,
            temporary_root / "pdf",
            scale_mm_per_px=float(config["scale_mm_per_px"]),
            dpi=int(config["dpi"]),
            preset="real_scan_tuned_v1",
            merge_lines=True,
            auto_ocr_roi=bool(config.get("auto_ocr_roi", False)),
        )
        if (
            sha256_file(source) != source_sha256
            or regenerated_manifest.get("status") != "complete"
            or regenerated_manifest.get("source_pdf_sha256") != source_sha256
            or regenerated_manifest.get("render_dpi") != int(config["dpi"])
            or regenerated_manifest.get("scale_mm_per_px") != float(config["scale_mm_per_px"])
        ):
            raise ManifestError("Source PDF changed or regenerated extraction identity is invalid.")

        regenerated_pages = [
            item for item in regenerated_manifest.get("pages", [])
            if isinstance(item, dict)
            and item.get("page") == page_number
            and item.get("page_index") == page_index
        ]
        if len(regenerated_pages) != 1:
            raise ManifestError("Regenerated PDF does not identify exactly one requested page.")
        regenerated_page = regenerated_pages[0]
        if _pdf_page_identity(regenerated_page) != identity:
            raise ManifestError("Regenerated PDF page transform does not match the verified page.")

        temporary_pdf_root = temporary_root / "pdf"
        regenerated_render = _resolve_pdf_resume_artifact(
            temporary_pdf_root,
            regenerated_page.get("rendered_png"),
            f"rendered/page_{page_number:02d}.png",
            f"regenerated page {page_number} rendered-page",
        )
        regenerated_render_sha256 = sha256_file(regenerated_render)
        if (
            regenerated_page.get("rendered_png_sha256") != regenerated_render_sha256
            or regenerated_render_sha256 != page["rendered_png"].get("sha256")
        ):
            raise ManifestError("Regenerated PDF page render differs from its verified checkpoint.")

        regenerated_primitive = _resolve_pdf_resume_artifact(
            temporary_pdf_root,
            regenerated_page.get("primitive_ir"),
            f"primitive_ir/page_{page_number:02d}.json",
            f"regenerated page {page_number} Primitive IR",
        )
        try:
            regenerated_payload = json.loads(regenerated_primitive.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError("Regenerated Primitive IR cannot be read.") from exc
        primitives = regenerated_payload.get("primitives") if isinstance(regenerated_payload, dict) else None
        source_document = (
            regenerated_payload.get("source_document")
            if isinstance(regenerated_payload, dict)
            else None
        )
        if (
            not isinstance(source_document, dict)
            or source_document.get("page_index") != page_index
            or not isinstance(primitives, list)
            or len(primitives) != regenerated_page.get("primitive_count")
        ):
            raise ManifestError("Regenerated Primitive IR does not match its PDF page record.")

        latest_paths = _validate_pdf_resume_artifacts(output_dir, manifest_path, source, manifest)
        latest_primitive = latest_paths[(page_number, "primitive_ir")]
        if latest_primitive != primitive:
            raise ManifestError("PDF Primitive IR destination changed during recovery.")
        latest_primitive.parent.mkdir(parents=True, exist_ok=True)
        temporary_primitive: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{latest_primitive.name}.",
                suffix=".tmp",
                dir=latest_primitive.parent,
                delete=False,
            ) as target:
                temporary_primitive = Path(target.name)
                with regenerated_primitive.open("rb") as source_file:
                    shutil.copyfileobj(source_file, target)
                target.flush()
                os.fsync(target.fileno())
            latest_paths = _validate_pdf_resume_artifacts(output_dir, manifest_path, source, manifest)
            latest_primitive = latest_paths[(page_number, "primitive_ir")]
            if latest_primitive != primitive:
                raise ManifestError("PDF Primitive IR destination changed before promotion.")
            os.replace(temporary_primitive, latest_primitive)
            temporary_primitive = None
        finally:
            if temporary_primitive is not None:
                temporary_primitive.unlink(missing_ok=True)

        if sha256_file(latest_primitive) != sha256_file(regenerated_primitive):
            raise ManifestError("Regenerated Primitive IR promotion failed hash verification.")


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


def _ensure_rendered(
    source: Path,
    output_dir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    render_path: Path,
) -> None:
    render = manifest["render"]
    if _completed(output_dir, render, render_path):
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
    rendered_manifest = render_path
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
    output_dir = output_dir.resolve()
    manifest_path = manifest_path.absolute()
    artifact_paths = _validate_pdf_resume_artifacts(output_dir, manifest_path, source, manifest)
    _ensure_rendered(source, output_dir, manifest_path, manifest, artifact_paths[("run", "render")])
    artifact_paths = _validate_pdf_resume_artifacts(output_dir, manifest_path, source, manifest)

    # Import late to keep the PDF module usable independently of CLI argument parsing.
    from .cli import _run_dxf, _run_semantic

    for page in manifest["pages"]:
        page_number = page["page"]
        stages = page["stages"]
        primitive = artifact_paths[(page_number, "primitive_ir")]
        semantic = artifact_paths[(page_number, "semantic_ir")]
        dxf = artifact_paths[(page_number, "dxf")]
        evidence = artifact_paths[(page_number, "build_evidence")]
        primitive_completed = _completed(output_dir, stages["primitive_ir"], primitive)
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
            _regenerate_primitive_from_pdf(
                source,
                output_dir,
                page,
                primitive,
                manifest,
                manifest_path,
                artifact_paths,
            )
            _write_page_stage(manifest_path, manifest, page, "primitive_ir", primitive, "Primitive IR regenerated from verified rendered page.")
        if not _completed(output_dir, stages["semantic_ir"], semantic):
            semantic.parent.mkdir(parents=True, exist_ok=True)
            _run_semantic(primitive, semantic)
            _write_page_stage(manifest_path, manifest, page, "semantic_ir", semantic, "Semantic IR generated.")
            stages["dxf"] = _stage()
            stages["build_evidence"] = _stage()
            write_manifest(manifest_path, manifest)
        if not _completed(output_dir, stages["dxf"], dxf):
            dxf.parent.mkdir(parents=True, exist_ok=True)
            evidence.parent.mkdir(parents=True, exist_ok=True)
            _run_dxf(primitive, semantic, dxf, evidence)
            _write_page_stage(manifest_path, manifest, page, "dxf", dxf, "Staged DXF built and headlessly reviewed.")
            _write_page_stage(manifest_path, manifest, page, "build_evidence", evidence, "SHA-bound BuildResult evidence persisted.")
        elif not _completed(output_dir, stages["build_evidence"], evidence):
            stages["dxf"] = _stage()
            stages["build_evidence"] = _stage()
            write_manifest(manifest_path, manifest)
            _run_dxf(primitive, semantic, dxf, evidence)
            _write_page_stage(manifest_path, manifest, page, "dxf", dxf, "Staged DXF rebuilt with fresh evidence.")
            _write_page_stage(manifest_path, manifest, page, "build_evidence", evidence, "SHA-bound BuildResult evidence persisted.")
