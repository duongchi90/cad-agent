"""Offline, hash-bound orchestration for deterministic geometry comparison."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import cv2
import numpy as np

from primitive_ir_lib.geometry_alignment import (
    AnchorPair,
    AlignmentResult,
    estimate_photograph_alignment,
    estimate_similarity_alignment,
)
from primitive_ir_lib.geometry_comparator import (
    compare_curve_profile,
    compare_metric_trend,
    create_comparison_artifacts,
)
from primitive_ir_lib.geometry_metrics import GeometryMetrics, compute_geometry_metrics

from .manifest import sha256_file
from .visual_contracts import VisualContractError, read_visual_contract, validate_visual_contract


class GeometryComparisonRunError(ValueError):
    """Raised when geometry comparison evidence cannot be produced safely."""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ANCHOR_AUTHORITIES = {
    "DATUM",
    "DRIVING_DIMENSION",
    "STABLE_ENTITY",
    "VISUAL_FEATURE",
}
_ALIGNMENT_CONFIG: dict[str, object] = {
    "algorithm": "geometry-comparator-1.0",
    "max_rotation_deg": 5.0,
    "min_uniform_scale": 0.5,
    "max_uniform_scale": 2.0,
    "max_residual_px": 3.0,
}


def _canonical_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GeometryComparisonRunError("Cannot canonicalize geometry comparison evidence") from exc


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _require_identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise GeometryComparisonRunError(f"{name} has invalid identifier format")
    return value


def _require_sha256(value: str, name: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise GeometryComparisonRunError(f"{name} must be a lowercase SHA-256")
    return value


def _verify_unchanged(path: Path, expected_sha256: str) -> bool:
    return path.is_file() and sha256_file(path) == expected_sha256


def _read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeometryComparisonRunError(f"Cannot read {description}: {path}") from exc
    if not isinstance(payload, dict):
        raise GeometryComparisonRunError(f"{description} must be a JSON object: {path}")
    return payload


def _point(value: object, path: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise GeometryComparisonRunError(f"{path} must contain exactly two coordinates")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise GeometryComparisonRunError(f"{path} must contain numeric coordinates")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise GeometryComparisonRunError(f"{path} must contain finite coordinates")
    return point


def _read_anchors(path: Path) -> list[AnchorPair]:
    payload = _read_json(path, "anchor file")
    if set(payload) != {"schema_version", "anchors"}:
        raise GeometryComparisonRunError("anchor file has unexpected or missing properties")
    if payload["schema_version"] != "geometry-anchors-1.0":
        raise GeometryComparisonRunError("unsupported anchor schema version")
    raw_anchors = payload["anchors"]
    if not isinstance(raw_anchors, list):
        raise GeometryComparisonRunError("anchor file anchors must be a list")

    anchors: list[AnchorPair] = []
    for index, raw in enumerate(raw_anchors):
        path_prefix = f"anchors[{index}]"
        if not isinstance(raw, dict):
            raise GeometryComparisonRunError(f"{path_prefix} must be an object")
        expected_keys = {
            "anchor_id",
            "reference_px",
            "cad_px",
            "authority",
            "confidence",
        }
        if set(raw) != expected_keys:
            raise GeometryComparisonRunError(f"{path_prefix} has unexpected or missing properties")
        anchor_id = raw["anchor_id"]
        if not isinstance(anchor_id, str) or _ID_RE.fullmatch(anchor_id) is None:
            raise GeometryComparisonRunError(f"{path_prefix}.anchor_id is invalid")
        authority = raw["authority"]
        if authority not in _ANCHOR_AUTHORITIES:
            raise GeometryComparisonRunError(f"{path_prefix}.authority is invalid")
        confidence = raw["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise GeometryComparisonRunError(f"{path_prefix}.confidence must be numeric")
        if not math.isfinite(float(confidence)) or not 0.0 <= float(confidence) <= 1.0:
            raise GeometryComparisonRunError(f"{path_prefix}.confidence must be finite in [0, 1]")
        anchors.append(
            AnchorPair(
                anchor_id=anchor_id,
                reference_px=_point(raw["reference_px"], f"{path_prefix}.reference_px"),
                cad_px=_point(raw["cad_px"], f"{path_prefix}.cad_px"),
                authority=authority,
                confidence=float(confidence),
            )
        )
    return anchors


def _load_image(path: Path, description: str) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise GeometryComparisonRunError(f"Cannot decode {description}: {path}")
    if image.ndim not in {2, 3}:
        raise GeometryComparisonRunError(f"{description} must be grayscale or color: {path}")
    if image.ndim == 3 and image.shape[2] not in {1, 3, 4}:
        raise GeometryComparisonRunError(f"{description} has unsupported channel count: {path}")
    return image


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_image(path: Path, image: np.ndarray) -> None:
    if not cv2.imwrite(str(path), image):
        raise GeometryComparisonRunError(f"Cannot write comparison artifact: {path}")


def _alignment_record(
    alignment: AlignmentResult,
    *,
    reference_image_sha256: str,
    cad_render_sha256: str,
    anchors_sha256: str,
    alignment_config: dict[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    anchor_ids = list(alignment.anchor_ids)
    if alignment.status == "ALIGNED":
        if alignment.matrix is None:
            raise GeometryComparisonRunError("aligned result is missing its transform matrix")
        transform_sha256 = _canonical_sha256({"matrix": alignment.matrix})
        return (
            {
                "status": alignment.status,
                "method": alignment.method,
                "anchor_ids": anchor_ids,
                "transform_sha256": transform_sha256,
            },
            None,
        )

    failure_record: dict[str, object] = {
        "schema_version": "geometry-alignment-failure-1.0",
        "status": alignment.status,
        "method": alignment.method,
        "anchor_ids": anchor_ids,
        "reasons": list(alignment.reasons),
        "reference_image_sha256": reference_image_sha256,
        "cad_render_sha256": cad_render_sha256,
        "anchors_sha256": anchors_sha256,
        "alignment_config": alignment_config,
    }
    transform_sha256 = _canonical_sha256(failure_record)
    return (
        {
            "status": alignment.status,
            "method": alignment.method,
            "anchor_ids": anchor_ids,
            "transform_sha256": transform_sha256,
        },
        failure_record,
    )


def _comparison_id(
    *,
    run_id: str,
    region_id: str,
    reference_image_sha256: str,
    cad_render_sha256: str,
    reference_package_sha256: str,
    mutation_sha256: str,
    anchors_sha256: str,
    alignment_config: dict[str, object],
) -> str:
    source = {
        "run_id": run_id,
        "region_id": region_id,
        "reference_image_sha256": reference_image_sha256,
        "cad_render_sha256": cad_render_sha256,
        "reference_package_sha256": reference_package_sha256,
        "mutation_sha256": mutation_sha256,
        "anchors_sha256": anchors_sha256,
        "alignment_config": alignment_config,
    }
    return f"GC-{region_id}-{_canonical_sha256(source)[:16]}"


def _previous_metrics(
    path: Path | None,
    *,
    region_id: str,
    reference_package_sha256: str,
) -> tuple[str | None, GeometryMetrics | None]:
    if path is None:
        return None, None
    source = Path(path)
    if not source.is_file():
        raise GeometryComparisonRunError(f"Previous comparison does not exist: {source}")
    expected_sha256 = sha256_file(source)
    try:
        payload = read_visual_contract(source, contract="geometry_comparison")
    except VisualContractError as exc:
        raise GeometryComparisonRunError(f"Previous comparison is invalid: {source}") from exc
    if not _verify_unchanged(source, expected_sha256):
        raise GeometryComparisonRunError("Previous comparison changed during the run")
    if payload["region_id"] != region_id:
        raise GeometryComparisonRunError("Previous comparison region_id does not match the current run")
    if payload["reference_package_sha256"] != reference_package_sha256:
        raise GeometryComparisonRunError(
            "Previous comparison reference_package_sha256 does not match the current run"
        )
    alignment = payload["alignment"]
    metrics = payload["metrics"]
    if alignment["status"] != "ALIGNED" or not metrics:
        return expected_sha256, None
    return expected_sha256, GeometryMetrics(**metrics)


def _artifact_record(
    root: Path,
    path: Path,
    *,
    timestamp: str,
    run_id: str,
    region_id: str,
    reference_image_sha256: str,
    reference_package_sha256: str,
    cad_render_sha256: str,
    mutation_sha256: str,
    alignment: dict[str, object],
) -> dict[str, object]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "run_id": run_id,
        "region_id": region_id,
        "reference_image_sha256": reference_image_sha256,
        "reference_package_sha256": reference_package_sha256,
        "cad_render_sha256": cad_render_sha256,
        "mutation_sha256": mutation_sha256,
        "alignment_method": alignment["method"],
        "alignment_status": alignment["status"],
        "timestamp_utc": timestamp,
    }


def run_geometry_comparison(
    *,
    run_id: str,
    region_id: str,
    reference_image: Path,
    cad_image: Path,
    reference_package_sha256: str,
    mutation_sha256: str,
    anchors_path: Path,
    output_dir: Path,
    previous_comparison_path: Path | None = None,
    source_is_photograph: bool = False,
) -> Path:
    """Write validated geometry-comparison.json and evidence atomically."""

    run_id = _require_identifier(run_id, "run_id")
    region_id = _require_identifier(region_id, "region_id")
    reference_package_sha256 = _require_sha256(reference_package_sha256, "reference_package_sha256")
    mutation_sha256 = _require_sha256(mutation_sha256, "mutation_sha256")
    if source_is_photograph is not True and source_is_photograph is not False:
        raise GeometryComparisonRunError("source_is_photograph must be boolean")

    reference_path = Path(reference_image)
    cad_path = Path(cad_image)
    anchors_path = Path(anchors_path)
    output_path = Path(output_dir)
    for path, name in (
        (reference_path, "reference image"),
        (cad_path, "CAD image"),
        (anchors_path, "anchor file"),
    ):
        if not path.is_file():
            raise GeometryComparisonRunError(f"{name} does not exist: {path}")
    if output_path.exists():
        raise GeometryComparisonRunError(f"output directory already exists: {output_path}")

    reference_image_sha256 = sha256_file(reference_path)
    cad_render_sha256 = sha256_file(cad_path)
    anchors_sha256 = sha256_file(anchors_path)
    anchors = _read_anchors(anchors_path)
    reference = _load_image(reference_path, "reference image")
    cad = _load_image(cad_path, "CAD image")
    alignment_config = dict(_ALIGNMENT_CONFIG)
    alignment_config["source_is_photograph"] = source_is_photograph
    if not all(
        _verify_unchanged(path, expected)
        for path, expected in (
            (reference_path, reference_image_sha256),
            (cad_path, cad_render_sha256),
            (anchors_path, anchors_sha256),
        )
    ):
        raise GeometryComparisonRunError("an input changed during the run")

    if source_is_photograph:
        alignment = estimate_photograph_alignment(
            anchors,
            source_is_photograph=True,
            max_residual_px=float(_ALIGNMENT_CONFIG["max_residual_px"]),
        )
    else:
        alignment = estimate_similarity_alignment(
            anchors,
            max_rotation_deg=float(_ALIGNMENT_CONFIG["max_rotation_deg"]),
            min_uniform_scale=float(_ALIGNMENT_CONFIG["min_uniform_scale"]),
            max_uniform_scale=float(_ALIGNMENT_CONFIG["max_uniform_scale"]),
            max_residual_px=float(_ALIGNMENT_CONFIG["max_residual_px"]),
        )
    alignment_record, failure_record = _alignment_record(
        alignment,
        reference_image_sha256=reference_image_sha256,
        cad_render_sha256=cad_render_sha256,
        anchors_sha256=anchors_sha256,
        alignment_config=alignment_config,
    )
    comparison_id = _comparison_id(
        run_id=run_id,
        region_id=region_id,
        reference_image_sha256=reference_image_sha256,
        cad_render_sha256=cad_render_sha256,
        reference_package_sha256=reference_package_sha256,
        mutation_sha256=mutation_sha256,
        anchors_sha256=anchors_sha256,
        alignment_config=alignment_config,
    )
    previous_sha256, previous_metrics = _previous_metrics(
        previous_comparison_path,
        region_id=region_id,
        reference_package_sha256=reference_package_sha256,
    )

    metrics: dict[str, object] = {}
    trend = "BASELINE"
    artifacts: dict[str, np.ndarray] = {}
    curve_profile: dict[str, float] | None = None
    if alignment.status == "ALIGNED":
        try:
            comparison_artifacts = create_comparison_artifacts(reference, cad, alignment)
            geometry_metrics = compute_geometry_metrics(
                reference,
                comparison_artifacts.aligned_cad,
            )
            curve_profile = compare_curve_profile(
                reference,
                comparison_artifacts.aligned_cad,
            )
        except (ValueError, cv2.error) as exc:
            raise GeometryComparisonRunError("aligned geometry evidence could not be computed") from exc
        metrics = {
            key: getattr(geometry_metrics, key)
            for key in geometry_metrics.__dataclass_fields__
        }
        trend = compare_metric_trend(geometry_metrics, previous_metrics)
        artifacts = {
            "aligned-cad.png": comparison_artifacts.aligned_cad,
            "overlay.png": comparison_artifacts.overlay,
            "missing-mask.png": comparison_artifacts.missing_mask,
            "extra-mask.png": comparison_artifacts.extra_mask,
            "absolute-difference.png": comparison_artifacts.absolute_difference,
        }
    if trend == "BASELINE":
        previous_sha256 = None

    payload: dict[str, object] = {
        "schema_version": "geometry-comparison-1.0",
        "comparison_id": comparison_id,
        "run_id": run_id,
        "region_id": region_id,
        "reference_package_sha256": reference_package_sha256,
        "cad_render_sha256": cad_render_sha256,
        "mutation_sha256": mutation_sha256,
        "alignment": alignment_record,
        "metrics": metrics,
        "trend": trend,
        "previous_comparison_sha256": previous_sha256,
    }
    try:
        payload = validate_visual_contract(payload, contract="geometry_comparison")
    except VisualContractError as exc:
        raise GeometryComparisonRunError("generated geometry comparison violates its contract") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(tempfile.mkdtemp(prefix=f".{output_path.name}.", dir=str(output_path.parent)))
    try:
        if failure_record is not None:
            _write_json(temporary_root / "alignment-failure.json", failure_record)
        for name, image in artifacts.items():
            _write_image(temporary_root / name, image)
        if curve_profile is not None:
            _write_json(temporary_root / "curve-profile.json", curve_profile)
        comparison_path = temporary_root / "geometry-comparison.json"
        _write_json(comparison_path, payload)

        timestamp = datetime.now(timezone.utc).isoformat()
        artifact_paths = sorted(
            path
            for path in temporary_root.iterdir()
            if path.is_file() and path.name != "comparison-manifest.json"
        )
        manifest = {
            "schema_version": "geometry-comparison-manifest-1.0",
            "comparison_id": comparison_id,
            "run_id": run_id,
            "region_id": region_id,
            "reference_image_sha256": reference_image_sha256,
            "reference_package_sha256": reference_package_sha256,
            "cad_render_sha256": cad_render_sha256,
            "mutation_sha256": mutation_sha256,
            "anchors_sha256": anchors_sha256,
            "alignment_config": alignment_config,
            "alignment": alignment_record,
            "created_at_utc": timestamp,
            "artifacts": [
                _artifact_record(
                    temporary_root,
                    path,
                    timestamp=timestamp,
                    run_id=run_id,
                    region_id=region_id,
                    reference_image_sha256=reference_image_sha256,
                    reference_package_sha256=reference_package_sha256,
                    cad_render_sha256=cad_render_sha256,
                    mutation_sha256=mutation_sha256,
                    alignment=alignment_record,
                )
                for path in artifact_paths
            ],
        }
        _write_json(temporary_root / "comparison-manifest.json", manifest)
        if output_path.exists():
            raise GeometryComparisonRunError(f"output directory already exists: {output_path}")
        os.replace(temporary_root, output_path)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    return output_path / "geometry-comparison.json"


__all__ = ["GeometryComparisonRunError", "run_geometry_comparison"]
