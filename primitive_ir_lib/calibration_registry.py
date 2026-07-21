"""Auditable, hash-bound manual calibration records for real drawings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_record(
    registry_path: Path,
    identifier: str,
    image_path: Path,
    scale_mm_per_px: float,
    evidence: str,
    status: str = "verified",
) -> dict:
    """Ghi 1 bản ghi calibration. status mặc định 'verified' (giữ hành vi cũ,
    dùng khi người dùng đã tự kiểm tra scale). Truyền status='needs_verification'
    cho các bản ghi đến từ auto_estimate_calibration() — get_verified_scale()
    sẽ TỪ CHỐI các bản ghi này cho tới khi ai đó đổi lại thành 'verified',
    đúng nguyên tắc không tự tin dùng calibration suy đoán cho DXF sản xuất."""
    if scale_mm_per_px <= 0:
        raise ValueError("scale_mm_per_px must be positive")
    if not evidence.strip():
        raise ValueError("evidence is required")
    if status not in ("verified", "needs_verification"):
        raise ValueError("status must be 'verified' or 'needs_verification'")
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"schema_version": "1.0", "records": []}
    record = {"id": identifier, "file_name": image_path.name, "sha256": file_sha256(image_path), "scale_mm_per_px": scale_mm_per_px, "evidence": evidence, "status": status}
    registry["records"] = [item for item in registry.get("records", []) if item["id"] != identifier] + [record]
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return record


def get_verified_scale(registry_path: Path, identifier: str, image_path: Path) -> float:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    record = next((item for item in registry.get("records", []) if item["id"] == identifier), None)
    if record is None or record.get("status") != "verified":
        raise ValueError(f"No verified calibration record: {identifier}")
    if record.get("sha256") != file_sha256(image_path):
        raise ValueError("Calibration image hash does not match; recalibration is required")
    return float(record["scale_mm_per_px"])