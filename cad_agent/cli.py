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


def _live_client(hwnd: int, dispatcher: Path):
    from mcp_integration_lib.mcp_client import (
        FileIPCLiveMCPClient,
        make_windows_dispatch_trigger,
        make_windows_lisp_trigger,
    )

    if hwnd <= 0:
        raise CommandError("--hwnd must be a positive AutoCAD window handle.")
    if not dispatcher.is_file():
        raise CommandError(f"AutoCAD dispatcher does not exist: {dispatcher}")
    return FileIPCLiveMCPClient(
        trigger=make_windows_dispatch_trigger(hwnd),
        raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
        bootstrap_lisp_path=str(dispatcher),
    )


def _mechanical_review_command(args: argparse.Namespace) -> int:
    dxf = args.dxf.resolve()
    evidence = args.build_evidence.resolve()
    build = load_build_evidence(evidence, dxf)
    review = review_live(build, _live_client(args.hwnd, args.dispatcher.resolve()), dxf)
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
    evidence = args.build_evidence.resolve()
    build = load_build_evidence(evidence, dxf)
    report = repair_live(
        build,
        _live_client(args.hwnd, args.dispatcher.resolve()),
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
    review = subcommands.add_parser("mechanical-review", help="Review a staged DXF through AutoCAD Mechanical")
    repair = subcommands.add_parser("mechanical-repair", help="Repair a staged DXF with explicit approval")
    for command in (review, repair):
        command.add_argument("--dxf", type=Path, required=True)
        command.add_argument("--build-evidence", type=Path, required=True)
        command.add_argument("--hwnd", type=int, required=True)
        command.add_argument("--dispatcher", type=Path, required=True)
        command.add_argument("--report", type=Path, required=True)
    repair.add_argument("--backup-dir", type=Path, required=True)
    repair.add_argument("--approval-reference", required=True)
    repair.add_argument("--confirm-repair", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
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
        if args.command == "mechanical-review":
            return _mechanical_review_command(args)
        return _mechanical_repair_command(args)
    except (CommandError, ManifestError, LiveSafetyError, OSError, ValueError) as exc:
        print(f"cad_agent: {exc}", file=sys.stderr)
        return 2
