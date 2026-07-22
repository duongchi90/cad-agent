"""Command line entry point for the deterministic staged CAD Agent run."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .manifest import (
    MANIFEST_NAME,
    STAGE_NAMES,
    ManifestError,
    completed_artifact,
    new_manifest,
    read_manifest,
    sha256_file,
    verify_source,
    write_manifest,
)
from .live import LiveSafetyError, load_build_evidence, review_dict, review_live, repair_live, write_build_evidence, write_live_report


class CommandError(ValueError):
    """A user-correctable command error."""


def _refuse_fidelity_dxf(dxf: Path) -> None:
    """Keep private visual-fidelity artifacts out of Mechanical workflows."""
    from .fidelity import FIDELITY_MANIFEST_NAME

    if (dxf.parent.parent / FIDELITY_MANIFEST_NAME).is_file():
        raise CommandError("Fidelity layout DXFs are review-only and cannot enter Mechanical review or repair.")


def _configure_console_output() -> None:
    """Keep delegated OCR diagnostics printable in a Windows console."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _artifact(output_dir: Path, stage: str) -> Path:
    return output_dir / {
        "primitive_ir": "primitive_ir.json",
        "semantic_ir": "semantic_ir.json",
        "dxf": "staged.dxf",
    }[stage]


def _write_stage(
    manifest_path: Path,
    manifest: dict[str, Any],
    stage: str,
    state: str,
    artifact: Path | None = None,
    details: str | None = None,
) -> None:
    record = manifest["stages"][stage]
    record["state"] = state
    record["artifact"] = artifact.name if artifact is not None else None
    record["sha256"] = sha256_file(artifact) if artifact is not None and artifact.is_file() else None
    record["details"] = details
    write_manifest(manifest_path, manifest)


def _run_primitive(source: Path, output: Path, scale: float) -> None:
    from primitive_ir_lib.run_image import run

    run(
        image_path=str(source),
        output_path=str(output),
        scale_mm_per_px=scale,
        preset="real_scan_tuned_v1",
        merge_lines=True,
    )


def _run_semantic(primitive_path: Path, output: Path) -> None:
    from semantic_ir_lib.assemble import build_semantic_document
    from semantic_ir_lib.io_utils import load_primitive_ir_document, save_document

    primitive = load_primitive_ir_document(str(primitive_path))
    semantic = build_semantic_document(primitive, primitive_ir_file_name=primitive_path.name)
    save_document(semantic, str(output))


def _run_dxf(primitive_path: Path, semantic_path: Path, output: Path, evidence_path: Path) -> str:
    from dxf_builder_lib.builder import build_dxf
    from dxf_builder_lib.reviewer import review_dxf
    from semantic_ir_lib.constraint_pruning import prune_constraints
    from semantic_ir_lib.constraint_solving import solve_constraints
    from semantic_ir_lib.io_utils import load_primitive_ir_document, load_semantic_ir_document

    primitive = load_primitive_ir_document(str(primitive_path))
    semantic = load_semantic_ir_document(str(semantic_path))
    pruned = prune_constraints(semantic.constraints)
    solved = solve_constraints(primitive, pruned.kept)
    solved_primitives = solved.solved_primitives if solved.status == "okay" else {}
    built = build_dxf(
        primitive,
        str(output),
        semantic_doc=semantic,
        solved_primitives=solved_primitives,
        build_components=True,
    )
    review = review_dxf(built)
    if not review.passed:
        raise CommandError("Headless DXF review failed: " + "; ".join(review.mismatches))
    write_build_evidence(evidence_path, built)
    return f"entities={built.entity_count}; components={built.component_count}; review=PASS"


def run_stages(source: Path, output_dir: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    verify_source(manifest, source)
    scale = manifest["configuration"].get("scale_mm_per_px")
    approval = manifest.get("approvals", {}).get("calibration", {})
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise ManifestError("Run manifest has no valid positive manual scale.")
    if approval.get("approved") is not True or not isinstance(approval.get("reference"), str):
        raise ManifestError("Run manifest has no recorded calibration approval.")

    for stage in STAGE_NAMES:
        record = manifest["stages"][stage]
        if completed_artifact(output_dir, record):
            continue
        artifact = _artifact(output_dir, stage)
        try:
            if stage == "primitive_ir":
                _run_primitive(source, artifact, float(scale))
                details = "Primitive IR generated from the approved manual scale."
            elif stage == "semantic_ir":
                _run_semantic(_artifact(output_dir, "primitive_ir"), artifact)
                details = "Semantic IR generated from Primitive IR."
            else:
                details = _run_dxf(
                    _artifact(output_dir, "primitive_ir"),
                    _artifact(output_dir, "semantic_ir"),
                    artifact,
                    output_dir / "build-evidence.json",
                )
            _write_stage(manifest_path, manifest, stage, "completed", artifact, details)
        except Exception as exc:
            _write_stage(manifest_path, manifest, stage, "failed", details=str(exc))
            raise


def doctor_payload() -> dict[str, Any]:
    tesseract = shutil.which("tesseract.exe") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    packages = ("numpy", "opencv-python", "pytesseract", "PyMuPDF", "ezdxf", "python-solvespace")
    installed: dict[str, str | None] = {}
    for package in packages:
        try:
            installed[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            installed[package] = None
    return {
        "supported": {"os": "windows", "python": "3.11", "tesseract": "5.4.0.20240606"},
        "python": sys.version.split()[0],
        "python_supported": sys.version_info[:2] == (3, 11),
        "tesseract_path": tesseract,
        "tesseract_present": os.path.isfile(tesseract),
        "packages": installed,
    }


def _run_command(args: argparse.Namespace) -> int:
    source = args.input.resolve()
    if not source.is_file():
        raise CommandError(f"Input image does not exist: {source}")
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise CommandError("This slice accepts PNG/JPG input. Use primitive_ir_lib.run_pdf for PDF rendering.")
    if args.scale_mm_per_px <= 0:
        raise CommandError("--scale-mm-per-px must be positive.")
    if not args.calibration_approval.strip():
        raise CommandError("--calibration-approval must be a non-empty approval reference.")
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise CommandError(f"Run manifest already exists: {manifest_path}; use resume instead.")
    manifest = new_manifest(source, args.scale_mm_per_px, args.calibration_approval.strip())
    write_manifest(manifest_path, manifest)
    run_stages(source, output_dir, manifest_path, manifest)
    print(manifest_path)
    return 0


def _resume_command(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    manifest = read_manifest(manifest_path)
    source = args.input.resolve()
    run_stages(source, manifest_path.parent, manifest_path, manifest)
    print(manifest_path)
    return 0


def _run_pdf_command(args: argparse.Namespace) -> int:
    from .pdf import PDF_MANIFEST_NAME, new_pdf_manifest, run_pdf_stages

    source = args.input.resolve()
    if not source.is_file():
        raise CommandError(f"Input PDF does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        raise CommandError("run-pdf accepts only a PDF input.")
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / PDF_MANIFEST_NAME
    if manifest_path.exists():
        raise CommandError(f"PDF run manifest already exists: {manifest_path}; use resume-pdf instead.")
    manifest = new_pdf_manifest(
        source,
        args.scale_mm_per_px,
        args.calibration_approval,
        args.dpi,
        auto_ocr_roi=args.auto_ocr_roi,
    )
    write_manifest(manifest_path, manifest)
    run_pdf_stages(source, output_dir, manifest_path, manifest)
    print(manifest_path)
    return 0


def _resume_pdf_command(args: argparse.Namespace) -> int:
    from .pdf import read_pdf_manifest, run_pdf_stages

    manifest_path = args.manifest.resolve()
    run_pdf_stages(args.input.resolve(), manifest_path.parent, manifest_path, read_pdf_manifest(manifest_path))
    print(manifest_path)
    return 0


def _fidelity_pdf_command(args: argparse.Namespace) -> int:
    from .fidelity import FIDELITY_MANIFEST_NAME, new_fidelity_manifest, run_fidelity_pdf

    source = args.input.resolve()
    output_root = args.output_dir.resolve()
    manifest_path = output_root / FIDELITY_MANIFEST_NAME
    if manifest_path.exists():
        raise CommandError(f"Fidelity manifest already exists: {manifest_path}; use a new private output root.")
    manifest = new_fidelity_manifest(
        source,
        output_root,
        args.dpi,
        args.source_approval,
        workspace_root=Path.cwd(),
    )
    run_fidelity_pdf(source, output_root, manifest_path, manifest)
    print(manifest_path)
    return 0


def _fidelity_overlay_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, run_fidelity_overlays

    manifest_path = args.manifest.resolve()
    run_fidelity_overlays(args.input.resolve(), manifest_path.parent, manifest_path, read_fidelity_manifest(manifest_path))
    print(manifest_path)
    return 0


def _fidelity_region_proposal_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, write_region_proposal

    try:
        regions = json.loads(args.regions.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandError(f"Cannot read region input: {args.regions}") from exc
    if not isinstance(regions, dict):
        raise CommandError("Region input must be a JSON object.")
    manifest_path = args.manifest.resolve()
    write_region_proposal(
        args.input.resolve(), manifest_path.parent, manifest_path, read_fidelity_manifest(manifest_path),
        args.page, regions, workspace_root=Path.cwd(), revision=args.revision,
    )
    suffix = "" if args.revision == 1 else f"-r{args.revision}"
    print(manifest_path.parent / "region_proposals" / f"page_{args.page:02d}{suffix}.json")
    return 0


def _fidelity_reconstruct_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, run_fidelity_reconstruct

    manifest_path = args.manifest.resolve()
    outputs = run_fidelity_reconstruct(
        args.input.resolve(), manifest_path.parent, read_fidelity_manifest(manifest_path), args.approval.resolve(), workspace_root=Path.cwd(),
    )
    for output in outputs:
        print(output)
    return 0


def _fidelity_region_approval_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, write_region_approval

    manifest_path = args.manifest.resolve()
    write_region_approval(
        args.input.resolve(), manifest_path.parent, read_fidelity_manifest(manifest_path), args.page,
        args.revision, args.region_id, args.approval_reference, workspace_root=Path.cwd(),
    )
    suffix = "" if args.revision == 1 else f"-r{args.revision}"
    print(manifest_path.parent / "region_approvals" / f"page_{args.page:02d}{suffix}.json")
    return 0


def _fidelity_observe_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, run_fidelity_observations

    manifest_path = args.manifest.resolve()
    for output in run_fidelity_observations(args.input.resolve(), manifest_path.parent, read_fidelity_manifest(manifest_path), workspace_root=Path.cwd()):
        print(output)
    return 0


def _fidelity_compose_command(args: argparse.Namespace) -> int:
    from .fidelity import read_fidelity_manifest, run_fidelity_compose

    manifest_path = args.manifest.resolve()
    print(run_fidelity_compose(args.input.resolve(), manifest_path.parent, read_fidelity_manifest(manifest_path), args.approval.resolve(), workspace_root=Path.cwd()))
    return 0


def _live_client(hwnd: int, dispatcher: Path, timeout_s: float = 10.0):
    from mcp_integration_lib.mcp_client import (
        FileIPCLiveMCPClient,
        make_windows_dispatch_trigger,
        make_windows_lisp_trigger,
    )

    if hwnd <= 0:
        raise CommandError("--hwnd must be a positive AutoCAD window handle.")
    if timeout_s <= 0:
        raise CommandError("--timeout-s must be positive.")
    if not dispatcher.is_file():
        raise CommandError(f"AutoCAD dispatcher does not exist: {dispatcher}")
    return FileIPCLiveMCPClient(
        trigger=make_windows_dispatch_trigger(hwnd),
        raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
        bootstrap_lisp_path=str(dispatcher),
        timeout_s=timeout_s,
    )


def _mechanical_review_command(args: argparse.Namespace) -> int:
    dxf = args.dxf.resolve()
    _refuse_fidelity_dxf(dxf)
    evidence = args.build_evidence.resolve()
    build = load_build_evidence(evidence, dxf)
    review = review_live(build, _live_client(args.hwnd, args.dispatcher.resolve(), args.timeout_s), dxf)
    report = {
        "operation": "mechanical-review",
        "dxf_path": str(dxf),
        "dxf_sha256": sha256_file(dxf),
        "review": review_dict(review),
    }
    write_live_report(args.report.resolve(), report)
    print(args.report.resolve())
    return 0 if review.passed else 1


def _mechanical_repair_command(args: argparse.Namespace) -> int:
    if args.confirm_repair != "APPLY":
        raise CommandError("Production repair requires --confirm-repair APPLY exactly.")
    if not args.approval_reference.strip():
        raise CommandError("Production repair requires a non-empty --approval-reference.")
    dxf = args.dxf.resolve()
    _refuse_fidelity_dxf(dxf)
    evidence = args.build_evidence.resolve()
    build = load_build_evidence(evidence, dxf)
    report = repair_live(
        build,
        _live_client(args.hwnd, args.dispatcher.resolve(), args.timeout_s),
        dxf,
        evidence,
        args.backup_dir.resolve(),
        args.approval_reference.strip(),
    )
    write_live_report(args.report.resolve(), report)
    print(args.report.resolve())
    return 0 if report["save_state"] in {"saved", "not_needed"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cad_agent")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="Report supported prerequisite state")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    run = subcommands.add_parser("run", help="Run the staged image-to-DXF path")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--scale-mm-per-px", type=float, required=True)
    run.add_argument("--calibration-approval", required=True)
    resume = subcommands.add_parser("resume", help="Resume a validated staged run")
    resume.add_argument("--manifest", type=Path, required=True)
    resume.add_argument("--input", type=Path, required=True)
    run_pdf = subcommands.add_parser("run-pdf", help="Run every PDF page through staged DXF generation")
    run_pdf.add_argument("--input", type=Path, required=True)
    run_pdf.add_argument("--output-dir", type=Path, required=True)
    run_pdf.add_argument("--scale-mm-per-px", type=float, required=True)
    run_pdf.add_argument("--calibration-approval", required=True)
    run_pdf.add_argument("--dpi", type=int, default=144)
    run_pdf.add_argument("--auto-ocr-roi", action="store_true", help="Detect OCR regions before PDF scale-label review")
    resume_pdf = subcommands.add_parser("resume-pdf", help="Resume a validated staged PDF run")
    resume_pdf.add_argument("--manifest", type=Path, required=True)
    resume_pdf.add_argument("--input", type=Path, required=True)
    fidelity_pdf = subcommands.add_parser("fidelity-pdf", help="Create a private clean paper-coordinate PDF layout baseline")
    fidelity_pdf.add_argument("--input", type=Path, required=True)
    fidelity_pdf.add_argument("--output-dir", type=Path, required=True)
    fidelity_pdf.add_argument("--source-approval", required=True)
    fidelity_pdf.add_argument("--dpi", type=int, default=144)
    fidelity_overlay = subcommands.add_parser("fidelity-overlay", help="Create review-only PDF-to-clean-DXF comparison overlays")
    fidelity_overlay.add_argument("--input", type=Path, required=True)
    fidelity_overlay.add_argument("--manifest", type=Path, required=True)
    fidelity_regions = subcommands.add_parser("fidelity-region-proposal", help="Write a SHA-bound, review-only page-region proposal")
    fidelity_regions.add_argument("--input", type=Path, required=True)
    fidelity_regions.add_argument("--manifest", type=Path, required=True)
    fidelity_regions.add_argument("--page", type=int, required=True)
    fidelity_regions.add_argument("--regions", type=Path, required=True, help="Private JSON containing regions and excluded_regions")
    fidelity_regions.add_argument("--revision", type=int, default=1)
    fidelity_approval = subcommands.add_parser("fidelity-region-approve", help="Write a SHA-bound approval for selected fidelity regions")
    fidelity_approval.add_argument("--input", type=Path, required=True)
    fidelity_approval.add_argument("--manifest", type=Path, required=True)
    fidelity_approval.add_argument("--page", type=int, required=True)
    fidelity_approval.add_argument("--revision", type=int, default=1)
    fidelity_approval.add_argument("--region-id", action="append", required=True)
    fidelity_approval.add_argument("--approval-reference", required=True)
    fidelity_reconstruct = subcommands.add_parser("fidelity-reconstruct", help="Build fresh clean geometry candidates from approved fidelity regions")
    fidelity_reconstruct.add_argument("--input", type=Path, required=True)
    fidelity_reconstruct.add_argument("--manifest", type=Path, required=True)
    fidelity_reconstruct.add_argument("--approval", type=Path, required=True)
    fidelity_observe = subcommands.add_parser("fidelity-observe", help="Write bounded private table-grid observations for all fidelity pages")
    fidelity_observe.add_argument("--input", type=Path, required=True)
    fidelity_observe.add_argument("--manifest", type=Path, required=True)
    fidelity_compose = subcommands.add_parser("fidelity-compose", help="Compose approved region geometry into a paper-coordinate review page")
    fidelity_compose.add_argument("--input", type=Path, required=True)
    fidelity_compose.add_argument("--manifest", type=Path, required=True)
    fidelity_compose.add_argument("--approval", type=Path, required=True)
    review = subcommands.add_parser("mechanical-review", help="Review a staged DXF through AutoCAD Mechanical")
    repair = subcommands.add_parser("mechanical-repair", help="Repair a staged DXF with explicit approval")
    for command in (review, repair):
        command.add_argument("--dxf", type=Path, required=True)
        command.add_argument("--build-evidence", type=Path, required=True)
        command.add_argument("--hwnd", type=int, required=True)
        command.add_argument("--dispatcher", type=Path, required=True)
        command.add_argument("--report", type=Path, required=True)
        command.add_argument("--timeout-s", type=float, default=10.0, help="File IPC timeout in seconds (default: 10)")
    repair.add_argument("--backup-dir", type=Path, required=True)
    repair.add_argument("--approval-reference", required=True)
    repair.add_argument("--confirm-repair", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_output()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            payload = doctor_payload()
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload)
            return 0
        if args.command == "run":
            return _run_command(args)
        if args.command == "resume":
            return _resume_command(args)
        if args.command == "run-pdf":
            return _run_pdf_command(args)
        if args.command == "resume-pdf":
            return _resume_pdf_command(args)
        if args.command == "fidelity-pdf":
            return _fidelity_pdf_command(args)
        if args.command == "fidelity-overlay":
            return _fidelity_overlay_command(args)
        if args.command == "fidelity-region-proposal":
            return _fidelity_region_proposal_command(args)
        if args.command == "fidelity-reconstruct":
            return _fidelity_reconstruct_command(args)
        if args.command == "fidelity-region-approve":
            return _fidelity_region_approval_command(args)
        if args.command == "fidelity-observe":
            return _fidelity_observe_command(args)
        if args.command == "fidelity-compose":
            return _fidelity_compose_command(args)
        if args.command == "mechanical-review":
            return _mechanical_review_command(args)
        return _mechanical_repair_command(args)
    except (CommandError, ManifestError, LiveSafetyError, OSError, ValueError) as exc:
        print(f"cad_agent: {exc}", file=sys.stderr)
        return 2
