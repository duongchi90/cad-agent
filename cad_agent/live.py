"""Safety boundary for AutoCAD Mechanical File IPC review and repair."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
from typing import Any

from dxf_builder_lib.builder import BuildResult
from mcp_integration_lib.repair2 import repair_dxf_live
from mcp_integration_lib.reviewer2 import LiveReviewResult, review_dxf_live

from .manifest import sha256_file


BUILD_EVIDENCE_SCHEMA_VERSION = "1.0"


class LiveSafetyError(ValueError):
    """Raised when a live drawing operation cannot meet its safety contract."""


def _build_result_dict(build: BuildResult) -> dict[str, Any]:
    return {
        "output_path": build.output_path,
        "handle_by_primitive_id": build.handle_by_primitive_id,
        "layer_by_primitive_id": build.layer_by_primitive_id,
        "written_geometry_by_primitive_id": build.written_geometry_by_primitive_id,
        "skipped_primitive_ids": build.skipped_primitive_ids,
        "entity_count": build.entity_count,
        "component_handle_by_part_id": build.component_handle_by_part_id,
        "component_type_by_part_id": build.component_type_by_part_id,
        "skipped_part_ids": build.skipped_part_ids,
        "skipped_part_reasons": build.skipped_part_reasons,
        "component_count": build.component_count,
        "written_component_by_part_id": build.written_component_by_part_id,
    }


def _build_result_from_dict(payload: dict[str, Any]) -> BuildResult:
    try:
        return BuildResult(**payload)
    except TypeError as exc:
        raise LiveSafetyError("Build evidence has an invalid BuildResult payload.") from exc


def write_build_evidence(path: Path, build: BuildResult) -> None:
    dxf = Path(build.output_path)
    if not dxf.is_file():
        raise LiveSafetyError(f"Staged DXF does not exist: {dxf}")
    payload = {
        "schema_version": BUILD_EVIDENCE_SCHEMA_VERSION,
        "dxf": {"name": dxf.name, "sha256": sha256_file(dxf)},
        "build_result": _build_result_dict(build),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_build_evidence(path: Path, dxf: Path) -> BuildResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveSafetyError(f"Cannot read build evidence: {path}") from exc
    if payload.get("schema_version") != BUILD_EVIDENCE_SCHEMA_VERSION:
        raise LiveSafetyError("Unsupported build evidence schema version.")
    if not dxf.is_file():
        raise LiveSafetyError(f"DXF does not exist: {dxf}")
    expected = payload.get("dxf", {}).get("sha256")
    if not isinstance(expected, str) or sha256_file(dxf) != expected:
        raise LiveSafetyError("DXF SHA-256 does not match build evidence; live operation is refused.")
    build = _build_result_from_dict(payload.get("build_result", {}))
    build.output_path = str(dxf)
    return build


def review_dict(review: LiveReviewResult) -> dict[str, Any]:
    return asdict(review)


def write_live_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _backup_paths(dxf: Path, evidence: Path, backup_dir: Path) -> tuple[Path, Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in range(1000):
        label = stamp if suffix == 0 else f"{stamp}-{suffix:03d}"
        dxf_backup = backup_dir / f"{dxf.stem}.{label}{dxf.suffix}"
        evidence_backup = backup_dir / f"{evidence.stem}.{label}{evidence.suffix}"
        if not dxf_backup.exists() and not evidence_backup.exists():
            return dxf_backup, evidence_backup
    raise LiveSafetyError("Could not allocate a unique backup path.")


def _backup(dxf: Path, evidence: Path, backup_dir: Path) -> dict[str, str]:
    dxf_backup, evidence_backup = _backup_paths(dxf, evidence, backup_dir)
    shutil.copy2(dxf, dxf_backup)
    shutil.copy2(evidence, evidence_backup)
    return {
        "dxf_path": str(dxf_backup),
        "dxf_sha256": sha256_file(dxf_backup),
        "build_evidence_path": str(evidence_backup),
        "build_evidence_sha256": sha256_file(evidence_backup),
    }


def review_live(build: BuildResult, client: Any, dxf: Path) -> LiveReviewResult:
    build.output_path = str(dxf)
    return review_dxf_live(build, client, open_drawing=True)


def repair_live(
    build: BuildResult,
    client: Any,
    dxf: Path,
    evidence_path: Path,
    backup_dir: Path,
    approval_reference: str,
) -> dict[str, Any]:
    """Repair a live staged DXF only after recording a recoverable backup."""
    if not approval_reference.strip():
        raise LiveSafetyError("A non-empty production repair approval reference is required.")
    if not dxf.is_file() or not evidence_path.is_file():
        raise LiveSafetyError("Both staged DXF and build evidence must exist before live repair.")

    build.output_path = str(dxf)
    before = review_dxf_live(build, client, open_drawing=True)
    report: dict[str, Any] = {
        "operation": "mechanical-repair",
        "approval_reference": approval_reference,
        "dxf_path": str(dxf),
        "dxf_sha256_before": sha256_file(dxf),
        "before_review": review_dict(before),
        "backup": None,
        "repair": None,
        "after_review": None,
        "save_state": "not_needed" if before.passed else "not_saved",
    }
    if before.passed:
        return report

    backup = _backup(dxf, evidence_path, backup_dir)
    report["backup"] = backup
    repaired = repair_dxf_live(build, before.mismatches, client)
    report["repair"] = asdict(repaired)
    after = review_dxf_live(build, client, open_drawing=False)
    report["after_review"] = review_dict(after)
    if after.passed and repaired.repaired_count > 0:
        client.drawing_save()
        build.output_path = str(dxf)
        write_build_evidence(evidence_path, build)
        report["dxf_sha256_after"] = sha256_file(dxf)
        report["save_state"] = "saved"
        return report

    try:
        client.drawing_open(backup["dxf_path"])
        report["rollback_state"] = "backup_reopened"
    except Exception as exc:  # pragma: no cover - exercised by live transport failures
        report["rollback_state"] = f"backup_reopen_failed: {exc}"
    return report
