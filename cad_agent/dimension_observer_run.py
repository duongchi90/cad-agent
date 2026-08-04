"""Hash-bound offline Dimension Observer runner."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import cv2
import numpy as np

from cad_agent.manifest import sha256_file
from cad_agent.visual_contracts import validate_visual_contract
from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionDisposition,
    OcrReader,
    build_dimension_register,
    detect_dimension_clusters,
    observe_dimension_cluster,
)
from primitive_ir_lib.text_extraction import extract_text_tesseract


class DimensionObserverRunError(ValueError):
    """Raised when an offline observer run cannot be safely committed."""


def _read_json_snapshot(snapshot: bytes, *, label: str) -> object:
    try:
        return json.loads(snapshot.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DimensionObserverRunError(f"Cannot parse JSON snapshot: {label}") from exc


def _snapshot_input(path: Path | None, *, label: str) -> tuple[bytes | None, str | None]:
    if path is None:
        return None, None
    try:
        snapshot = path.read_bytes()
    except OSError as exc:
        raise DimensionObserverRunError(f"Cannot snapshot {label}: {path}") from exc
    return snapshot, hashlib.sha256(snapshot).hexdigest()


def _assert_snapshot(path: Path | None, snapshot: bytes | None, *, label: str) -> None:
    if path is None or snapshot is None:
        return
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise DimensionObserverRunError(f"{label} changed during observer run") from exc
    if current != snapshot:
        raise DimensionObserverRunError(f"{label} changed during observer run")


def _read_anchors(snapshot: bytes | None) -> list[Mapping[str, object]]:
    if snapshot is None:
        return []
    payload = _read_json_snapshot(snapshot, label="semantic anchors")
    if isinstance(payload, dict):
        anchors = payload.get("anchors")
    else:
        anchors = payload
    if not isinstance(anchors, list) or not all(isinstance(item, dict) for item in anchors):
        raise DimensionObserverRunError("semantic anchors must be a JSON array or an object with anchors")
    return anchors


def _read_profile(snapshot: bytes | None) -> dict[str, Any]:
    if snapshot is None:
        return {"default_unit": None, "clusters": {}}
    payload = _read_json_snapshot(snapshot, label="observer profile")
    if not isinstance(payload, dict):
        raise DimensionObserverRunError("observer profile must be an object")
    if set(payload) != {"schema_version", "default_unit", "clusters"}:
        raise DimensionObserverRunError("observer profile has unexpected properties")
    if payload["schema_version"] != "dimension-observer-profile-1.0":
        raise DimensionObserverRunError("unsupported observer profile schema")
    if not isinstance(payload["default_unit"], str) or not payload["default_unit"].strip():
        raise DimensionObserverRunError("observer profile default_unit must be non-empty")
    clusters = payload["clusters"]
    if not isinstance(clusters, dict):
        raise DimensionObserverRunError("observer profile clusters must be an object")
    for cluster_id, entry in clusters.items():
        if not isinstance(cluster_id, str) or not isinstance(entry, dict):
            raise DimensionObserverRunError("observer profile cluster entries are malformed")
        if set(entry) != {"role", "critical", "blocker_scope"}:
            raise DimensionObserverRunError(f"observer profile entry {cluster_id} is not closed")
        if entry["role"] not in {"DRIVING", "REFERENCE", "DERIVED"}:
            raise DimensionObserverRunError(f"observer profile entry {cluster_id} has invalid role")
        if not isinstance(entry["critical"], bool):
            raise DimensionObserverRunError(f"observer profile entry {cluster_id} critical must be boolean")
        if not isinstance(entry["blocker_scope"], list) or not all(
            isinstance(item, str) and item for item in entry["blocker_scope"]
        ):
            raise DimensionObserverRunError(f"observer profile entry {cluster_id} blocker_scope is malformed")
    return {"default_unit": payload["default_unit"], "clusters": clusters}


def _default_ocr_reader(*, lang: str, tesseract_cmd: str | None) -> OcrReader:
    if tesseract_cmd:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def read(crop_bgr: np.ndarray) -> list[Any]:
        height, width = crop_bgr.shape[:2]
        return extract_text_tesseract(
            crop_bgr,
            roi_boxes=[(0, 0, width, height)],
            min_confidence=0,
            lang=lang,
            psm=11,
        )

    return read


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _disposition_payload(disposition: DimensionDisposition) -> dict[str, object]:
    return {
        "cluster_id": disposition.cluster_id,
        "disposition": disposition.disposition,
        "observation": disposition.observation,
        "reasons": list(disposition.reasons),
    }


def _crop_path(root: Path, cluster: DimensionCluster) -> Path:
    return root / "crops" / f"{cluster.cluster_id}.png"


def run_dimension_observer(
    *,
    run_id: str,
    source_image: Path,
    page_id: str,
    view_id: str,
    output_dir: Path,
    ocr_lang: str = "vie+eng",
    tesseract_cmd: str | None = None,
    semantic_anchors_path: Path | None = None,
    profile_path: Path | None = None,
    ocr_reader: OcrReader | None = None,
) -> Path:
    """Write crops, observer evidence, and a validated register atomically."""
    source = Path(source_image).resolve()
    output = Path(output_dir).resolve()
    if not source.is_file():
        raise DimensionObserverRunError(f"source image does not exist: {source}")
    if output.exists():
        if not output.is_dir():
            raise DimensionObserverRunError(f"output path is not a directory: {output}")
        if any(output.iterdir()):
            raise DimensionObserverRunError(f"output directory is non-empty: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    decoded = cv2.imdecode(np.frombuffer(source_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.size == 0:
        raise DimensionObserverRunError("source image cannot be decoded")
    height, width = decoded.shape[:2]
    clusters = detect_dimension_clusters(decoded)
    anchors_path = Path(semantic_anchors_path).resolve() if semantic_anchors_path else None
    profile_input_path = Path(profile_path).resolve() if profile_path else None
    anchors_snapshot, anchors_sha256 = _snapshot_input(anchors_path, label="semantic anchors")
    profile_snapshot, profile_sha256 = _snapshot_input(profile_input_path, label="profile")
    anchors = _read_anchors(anchors_snapshot)
    profile = _read_profile(profile_snapshot)
    reader = ocr_reader or _default_ocr_reader(lang=ocr_lang, tesseract_cmd=tesseract_cmd)

    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    try:
        (temporary / "crops").mkdir(parents=True, exist_ok=True)
        dispositions: list[DimensionDisposition] = []
        for cluster in clusters:
            x0, y0, x1, y1 = cluster.bbox_px
            crop = decoded[y0:y1, x0:x1]
            crop_path = _crop_path(temporary, cluster)
            if not cv2.imwrite(str(crop_path), crop):
                raise DimensionObserverRunError(f"cannot write crop: {crop_path}")
            profile_entry = profile["clusters"].get(cluster.cluster_id, {})
            dispositions.append(
                observe_dimension_cluster(
                    decoded,
                    cluster,
                    page_id=page_id,
                    view_id=view_id,
                    source_sha256=source_sha256,
                    ocr_reader=reader,
                    semantic_anchors=anchors,
                    explicit_role=profile_entry.get("role"),
                    default_unit=profile["default_unit"],
                    blocker_scope=profile_entry.get("blocker_scope", ()),
                    critical=profile_entry.get("critical", False),
                )
            )

        register = build_dimension_register(
            run_id=run_id,
            source_sha256=source_sha256,
            page_id=page_id,
            view_id=view_id,
            total_area_px=width * height,
            inspected_area_px=width * height,
            detected_cluster_ids=[cluster.cluster_id for cluster in clusters],
            dispositions=dispositions,
        )
        register = validate_visual_contract(register, contract="dimension_register")
        register_path = temporary / "dimension-register.json"
        _write_json(register_path, register)

        artifacts = []
        for path in sorted(temporary.rglob("*")):
            if path.is_file() and path.name != "observer-evidence.json":
                artifacts.append({
                    "path": str(path.relative_to(temporary)).replace("\\", "/"),
                    "sha256": sha256_file(path),
                })
        evidence = {
            "schema_version": "dimension-observer-evidence-1.0",
            "run_id": run_id,
            "source_sha256": source_sha256,
            "semantic_anchors_sha256": anchors_sha256,
            "profile_sha256": profile_sha256,
            "page_id": page_id,
            "view_id": view_id,
            "image_size_px": {"width": width, "height": height},
            "dispositions": [_disposition_payload(item) for item in dispositions],
            "artifacts": artifacts,
        }
        _write_json(temporary / "observer-evidence.json", evidence)
        _assert_snapshot(source, source_bytes, label="source image")
        _assert_snapshot(anchors_path, anchors_snapshot, label="semantic anchors")
        _assert_snapshot(profile_input_path, profile_snapshot, label="profile")
        if output.exists():
            output.rmdir()
        os.replace(temporary, output)
        return output / "dimension-register.json"
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


__all__ = ["DimensionObserverRunError", "run_dimension_observer"]
