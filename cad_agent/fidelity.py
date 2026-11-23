"""Private, paper-coordinate PDF layout baseline.

This module intentionally creates a diagnostic layout DXF, not a model-space
conversion. It keeps OCR and scale observations in sidecars so unreviewed text
or calibration can never be mistaken for CAD source geometry.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
import tempfile
from collections import Counter
from collections.abc import Collection
from html import escape
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.geometry_extraction import RawGeometry, extract_raw_geometry
from primitive_ir_lib.io_utils import save_document
from primitive_ir_lib.run_image import _configure_tesseract
from primitive_ir_lib.text_extraction import detect_text_candidate_rois, extract_text_tesseract
from primitive_ir_lib.table_extraction import build_cells, detect_grid
from primitive_ir_lib.view_calibration import detect_view_candidates
from dxf_builder_lib._dxf_snapshot import StyleRecordKey, read_dxf_snapshot
from dxf_builder_lib.builder import _UNICODE_TEXT_STYLE, _ensure_unicode_text_style

from .file_integrity import FileIdentityError, assert_path_identity, open_bound_file, pin_directory_chain
from .manifest import ManifestError, sha256_file, verify_source, write_manifest

FIDELITY_MANIFEST_NAME = "fidelity-run-manifest.json"
FIDELITY_SCHEMA_VERSION = "fidelity-run-1.0"


class FidelityError(ValueError):
    """Raised for an unsafe or unsupported fidelity-layout request."""


def _filter_fidelity_geometry(raw: RawGeometry) -> RawGeometry:
    """Remove only sub-12-pixel strokes from a review-only raw candidate."""
    retained: list[Any] = []
    for line in raw.lines:
        if line.length_px() < 12.0:
            continue
        start, end = sorted((line.p1_px, line.p2_px))
        duplicate_index = next((
            index for index, existing in enumerate(retained)
            if max(abs(start[0] - existing[0][0]), abs(start[1] - existing[0][1]),
                   abs(end[0] - existing[1][0]), abs(end[1] - existing[1][1])) <= 8.0
        ), None)
        if duplicate_index is None:
            retained.append((start, end, line))
        else:
            current = retained[duplicate_index][2]
            if (line.confidence, line.length_px()) > (current.confidence, current.length_px()):
                retained[duplicate_index] = (start, end, line)
    return RawGeometry(
        lines=[item[2] for item in retained],
        circles=list(raw.circles),
    )


def _raw_geometry_edges(raw: RawGeometry, shape: tuple[int, int]) -> np.ndarray:
    canvas = np.full(shape, 255, dtype=np.uint8)
    for line in raw.lines:
        cv2.line(
            canvas,
            tuple(round(value) for value in line.p1_px),
            tuple(round(value) for value in line.p2_px),
            0,
            1,
            lineType=cv2.LINE_AA,
        )
    for circle in raw.circles:
        cv2.circle(
            canvas,
            tuple(round(value) for value in circle.center_px),
            max(1, round(circle.radius_px)),
            0,
            1,
            lineType=cv2.LINE_AA,
        )
    return cv2.Canny(canvas, 50, 150)


def _select_fidelity_geometry(raw: RawGeometry, crop: np.ndarray, scale: float) -> tuple[RawGeometry, dict[str, Any]]:
    """Choose a filtered candidate only if it improves local tolerant edge F1."""
    del scale  # Raw geometry and the cropped PDF share pixel coordinates here.
    source_edges = cv2.Canny(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 50, 150)
    mask = np.full(crop.shape[:2], 255, dtype=np.uint8)
    baseline_edges = _raw_geometry_edges(raw, crop.shape[:2])
    filtered = _filter_fidelity_geometry(raw)
    filtered_edges = _raw_geometry_edges(filtered, crop.shape[:2])
    baseline = {"edge_metric": _edge_metrics(source_edges, baseline_edges, mask), "line_entities": len(raw.lines), "circle_entities": len(raw.circles)}
    filtered_report = {"edge_metric": _edge_metrics(source_edges, filtered_edges, mask), "line_entities": len(filtered.lines), "circle_entities": len(filtered.circles)}
    if filtered_report["edge_metric"]["f1"] > baseline["edge_metric"]["f1"]:
        return filtered, {"selected_profile": "filtered", "baseline": baseline, "filtered": filtered_report}
    return raw, {"selected_profile": "baseline", "baseline": baseline, "filtered": filtered_report}


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _set_file_information_by_handle(handle: object, destination: Path) -> None:
    """Rename an already-identified directory handle without re-resolving its source path."""
    if os.name != "nt":
        raise FileIdentityError("Directory publication requires Windows handle semantics.")
    import ctypes
    from ctypes import wintypes

    class RenameFlags(ctypes.Union):
        _fields_ = [("replace_if_exists", wintypes.BOOLEAN), ("flags", wintypes.DWORD)]

    class RenameInfo(ctypes.Structure):
        _fields_ = [
            ("options", RenameFlags),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    target = str(destination.absolute())
    if target.startswith("\\\\?\\"):
        extended_target = target
    elif target.startswith("\\\\"):
        extended_target = "\\\\?\\UNC\\" + target[2:]
    else:
        extended_target = "\\\\?\\" + target
    encoded_name = (extended_target + "\0").encode("utf-16-le")
    name_offset = RenameInfo.file_name.offset
    buffer_size = ctypes.sizeof(RenameInfo) + len(encoded_name)
    buffer = ctypes.create_string_buffer(buffer_size)
    rename_info = ctypes.cast(buffer, ctypes.POINTER(RenameInfo)).contents
    rename_info.options.replace_if_exists = False
    rename_info.root_directory = None
    rename_info.file_name_length = len(encoded_name) - 2
    ctypes.memmove(ctypes.addressof(rename_info) + name_offset, encoded_name, len(encoded_name))

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    if not kernel.SetFileInformationByHandle(handle, 3, buffer, buffer_size):
        error = ctypes.get_last_error() or 1
        raise ctypes.WinError(error, "Staging directory handle could not be published.")


def _publish_staging_directory(staging: Path, destination: Path, identity: tuple[int, int]) -> None:
    """Publish the exact staged directory object; never rename a replacement at its old path."""
    if os.name != "nt" or not staging.is_absolute() or not destination.is_absolute():
        raise FileIdentityError("Directory publication requires absolute Windows paths.")
    if staging.parent != destination.parent:
        raise FileIdentityError("Staging and final directories must share one pinned parent.")
    try:
        expected = os.stat(staging, follow_symlinks=False)
    except OSError as exc:
        raise FileIdentityError("Staging directory identity could not be verified.") from exc
    if (
        not os.path.isdir(staging)
        or getattr(expected, "st_file_attributes", 0) & 0x0400
        or (expected.st_dev, expected.st_ino) != identity
    ):
        raise FileIdentityError("Staging directory identity changed before publication.")

    import ctypes
    from ctypes import wintypes

    class Information(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
            ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
            ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(Information),
    ]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    handle = kernel.CreateFileW(
        str(staging),
        0x0001 | 0x0080 | 0x00010000 | 0x00100000,
        0x0001 | 0x0002 | 0x0004,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    handle_value = ctypes.cast(handle, ctypes.c_void_p).value
    if handle_value in (None, ctypes.c_void_p(-1).value):
        raise FileIdentityError("Staging directory could not be opened for bound publication.")
    try:
        information = Information()
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(information)):
            raise FileIdentityError("Staging directory handle identity could not be verified.")
        actual = (
            int(information.volume),
            (int(information.index_high) << 32) | int(information.index_low),
        )
        if information.attributes & 0x0400 or actual != identity:
            raise FileIdentityError("Staging directory handle does not match the written object.")
        if os.path.lexists(destination):
            raise FileIdentityError("Final text reconstruction directory already exists.")
        _set_file_information_by_handle(handle, destination)
        try:
            published = os.stat(destination, follow_symlinks=False)
        except OSError as exc:
            raise FileIdentityError("Published directory identity could not be verified.") from exc
        published_identity = (published.st_dev, published.st_ino)
        if (
            not os.path.isdir(destination)
            or getattr(published, "st_file_attributes", 0) & 0x0400
            or published_identity != identity
        ):
            raise FileIdentityError("Published directory is not the staged directory object.")
    finally:
        if not kernel.CloseHandle(handle):
            raise FileIdentityError("Staging directory handle could not be released.")


def _remove_staging_reparse_alias(staging: Path) -> None:
    """Unlink a substituted temporary alias without traversing its target."""
    import stat

    try:
        value = os.stat(staging, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise FileIdentityError("Staging path could not be checked after publication.") from exc
    if not (getattr(value, "st_file_attributes", 0) & 0x0400):
        return
    try:
        if stat.S_ISDIR(value.st_mode):
            os.rmdir(staging)
        else:
            os.unlink(staging)
    except OSError as exc:
        raise FileIdentityError("Substituted staging alias could not be safely unlinked.") from exc


def _read_fidelity_dxf_bytes(path: Path, *, label: str) -> bytes:
    try:
        descriptor, opened_stat = open_bound_file(
            path, flags=os.O_RDONLY | getattr(os, "O_BINARY", 0), label=label,
        )
        with os.fdopen(descriptor, "rb") as stream:
            data = stream.read()
            after = os.fstat(stream.fileno())
            assert_path_identity(path, opened_stat, label=label)
            if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                opened_stat.st_size, opened_stat.st_mtime_ns, opened_stat.st_ctime_ns,
            ):
                raise FileIdentityError(f"{label} changed during snapshot read.")
    except (FileIdentityError, OSError) as exc:
        raise FidelityError(f"{label} must remain a stable non-reparse file during snapshot read.") from exc
    return data


def _read_text_base_snapshot(path: Path) -> tuple[Any, str]:
    """Parse and hash the same immutable bytes with the existing ezdxf readers."""
    data = _read_fidelity_dxf_bytes(path, label="Base layout DXF")
    document, _ = read_dxf_snapshot(data)
    return document, hashlib.sha256(data).hexdigest()


def _read_fidelity_style_document(
    path: Path, *, expected_sha256: str | None = None,
) -> tuple[Any, set[StyleRecordKey]]:
    data = _read_fidelity_dxf_bytes(path, label="Fidelity STYLE input DXF")
    if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
        raise FidelityError("Text owner output hash does not match its report.")
    document, repeated_style_records = read_dxf_snapshot(data, observe_styles=True)
    document.filename = str(path)
    return document, repeated_style_records


def _published_text_reconstruction_matches(
    root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
    base_dxf_sha256: str | None,
    base_text_count: int,
    expected_text_sizing: list[dict[str, Any]],
) -> bool:
    """Recognize only a complete prior publication for these exact inputs."""
    import stat

    output = root / "layout.dxf"
    report_path = root / "report.json"
    try:
        root_stat = os.stat(root, follow_symlinks=False)
        output_stat = os.stat(output, follow_symlinks=False)
        report_stat = os.stat(report_path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or not stat.S_ISREG(output_stat.st_mode)
            or not stat.S_ISREG(report_stat.st_mode)
            or any(getattr(value, "st_file_attributes", 0) & 0x0400
                   for value in (root_stat, output_stat, report_stat))
        ):
            return False
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_source = manifest.get("source", {}).get("sha256")
        published_identity = report.get("staging_directory_identity") if isinstance(report, dict) else None
        if (
            not isinstance(report, dict)
            or report.get("state") != "needs_review"
            or report.get("profile") != "fidelity-layout-text"
            or report.get("source_sha256") != expected_source
            or not isinstance(published_identity, list)
            or len(published_identity) != 2
            or any(type(value) is not int for value in published_identity)
            or tuple(published_identity) != (root_stat.st_dev, root_stat.st_ino)
            or report.get("text_approval_sha256") != sha256_file(approval_path)
            or report.get("base_dxf_sha256") != base_dxf_sha256
            or report.get("output_dxf_sha256") != sha256_file(output)
            or type(report.get("emitted_text_entities")) is not int
            or report.get("text_sizing") != expected_text_sizing
        ):
            return False
        import ezdxf

        try:
            document = ezdxf.readfile(output)
        except ezdxf.DXFError:
            return False
        return len(document.modelspace().query("TEXT")) == (
            base_text_count + report["emitted_text_entities"]
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def _artifact(path: Path, output_root: Path) -> dict[str, str]:
    relative_path = path.resolve().relative_to(output_root.resolve())
    return {
        "artifact": relative_path.as_posix(),
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


def _validated_ocr_roi(
    ocr_roi: object,
    region_width: int,
    region_height: int,
    category: str,
) -> list[int] | None:
    if ocr_roi is None:
        return None
    if (
        not isinstance(ocr_roi, list)
        or len(ocr_roi) != 4
        or any(isinstance(value, bool) or not isinstance(value, int) for value in ocr_roi)
    ):
        raise FidelityError(f"{category} ocr_roi_px must contain four integer coordinates.")
    rx0, ry0, rx1, ry1 = ocr_roi
    if (
        rx0 < 0
        or ry0 < 0
        or rx1 > region_width
        or ry1 > region_height
        or rx1 - rx0 < 30
        or ry1 - ry0 < 30
    ):
        raise FidelityError(f"{category} ocr_roi_px must fit inside bbox_px and be at least 30 px wide/high.")
    return ocr_roi


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
            normalized = {"id": item["id"], "bbox_px": box, "purpose": purpose}
            ocr_roi = _validated_ocr_roi(ocr_roi=item.get("ocr_roi_px"), region_width=x1 - x0, region_height=y1 - y0, category=category)
            if ocr_roi is not None:
                normalized["ocr_roi_px"] = ocr_roi
            ids.add(item["id"])
            result.append(normalized)
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
        selected_raw, quality = _select_fidelity_geometry(raw, crop, scale)
        candidate_root = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"]
        if candidate_root.exists():
            raise FidelityError(f"Reconstruction candidate already exists: {candidate_root}")
        candidate_root.mkdir(parents=True)
        doc = build_document(
            file_name=f"page_{page_number:02d}_{region['id']}.png", page_index=page_number - 1,
            image_width_px=crop.shape[1], image_height_px=crop.shape[0],
            calibration=Calibration(unit="mm", pixel_to_unit_scale=scale, origin_px=(0.0, float(crop.shape[0])), method="manual_override", reference_note="Approved fidelity-layout region in paper millimetres."),
            raw_lines=selected_raw.lines, raw_circles=selected_raw.circles, raw_texts=[], sha256=sha256_file(rendered),
        )
        dxf = candidate_root / "geometry.dxf"
        build_dxf(doc, str(dxf), build_components=False)
        vector = _render_layout_dxf(dxf, crop.shape[1] * scale, crop.shape[0] * scale, crop.shape[1], crop.shape[0])
        source_edges = cv2.Canny(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 50, 150)
        vector_edges = cv2.Canny(cv2.cvtColor(vector, cv2.COLOR_BGR2GRAY), 50, 150)
        overlay = crop.copy(); overlap = (source_edges > 0) & (vector_edges > 0)
        overlay[source_edges > 0] = (0, 0, 255); overlay[vector_edges > 0] = (255, 255, 0); overlay[overlap] = (0, 255, 0)
        cv2.imwrite(str(candidate_root / "source.png"), crop); cv2.imwrite(str(candidate_root / "overlay.png"), overlay)
        (candidate_root / "report.json").write_text(json.dumps({"state": "needs_review", "profile": "fidelity-layout", "approval_sha256": sha256_file(approval_path), "region": region, "entities": {"LINE": len(selected_raw.lines), "CIRCLE": len(selected_raw.circles)}, "quality": quality, "edge_metric": _edge_metrics(source_edges, vector_edges, np.full(crop.shape[:2], 255, dtype=np.uint8)), "unresolved": ["text/dimensions/linetypes/tables remain sidecar-only", "no model export"]}, indent=2) + "\n", encoding="utf-8")
        results.append(candidate_root)
    return results


def _latest_fidelity_owner_output(output_root: Path, prefix: str, page_number: int) -> Path | None:
    candidates = [
        path for path in output_root.glob(f"{prefix}*/page_{page_number:02d}/layout.dxf")
        if path.is_file()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


def _validate_fidelity_owner_output(
    output_root: Path,
    path: Path,
    kind: str,
    page: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    report_path = path.parent / "report.json"
    if not report_path.is_file():
        raise FidelityError(f"{kind} owner output is missing its report.")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError(f"{kind} owner report is invalid JSON.") from exc
    if report.get("output_dxf_sha256") != sha256_file(path):
        raise FidelityError(f"{kind} owner output hash does not match its report.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if kind == "text":
        approval_path = output_root / "fidelity_text_approvals" / f"page_{page['page']:02d}.json"
        if not approval_path.is_file() or report.get("text_approval_sha256") != sha256_file(approval_path):
            raise FidelityError("Text owner output is not bound to its text approval.")
        try:
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FidelityError("Text approval is invalid JSON.") from exc
        if approval.get("source") != manifest.get("source") or approval.get("page") != page["page"]:
            raise FidelityError("Text owner output is bound to a different source or page.")
    elif report.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError(f"{kind} owner output does not match the current rendered page.")
    return report


def _fidelity_region_offsets(
    region: dict[str, Any], page: dict[str, Any], height_px: float,
) -> tuple[float, float, float]:
    x0, _, _, y1 = (float(value) for value in region["bbox_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    return x0 * scale, (height_px - y1) * scale, max(0.25, 3.0 * scale)


def _fidelity_point_in_region(
    point: Any,
    offset_x: float,
    offset_y: float,
    region: dict[str, Any],
    page: dict[str, Any],
    height_px: float,
    tolerance: float,
) -> bool:
    x0, y0, x1, y1 = (float(value) for value in region["bbox_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    return (
        offset_x - tolerance <= float(point.x) <= x1 * scale + tolerance
        and offset_y - tolerance <= float(point.y) <= (height_px - y0) * scale + tolerance
    )


def _fidelity_extended_style_definition(
    style: Any, *, output_encoding: str, repeated_style_records: Collection[StyleRecordKey],
) -> tuple[dict[str, Any], list[tuple[int, Any]]] | None:
    if style is None:
        return None
    style_key = style.doc.styles.key(style.dxf.name)
    if ("handle", style.dxf.handle) in repeated_style_records or ("name", style_key) in repeated_style_records:
        raise FidelityError("Repeated ACAD font declarations in Fidelity STYLE.")
    if not style.has_extended_font_data:
        return None
    tags = [(tag.code, tag.value) for tag in style.get_xdata("ACAD")]
    if (
        len(tags) != 2
        or tags[0][0] != 1000
        or not isinstance(tags[0][1], str)
        or not tags[0][1].strip()
        or any(char in tags[0][1] for char in "\r\n\0")
        or tags[1][0] != 1071
        or type(tags[1][1]) is not int
        or not -(2**31) <= tags[1][1] < 2**31
    ):
        raise FidelityError("Malformed extended font data in Fidelity STYLE.")

    try:
        family_bytes = tags[0][1].encode(output_encoding)
    except UnicodeEncodeError as exc:
        raise FidelityError("Fidelity STYLE font family cannot be preserved in the target DXF encoding.") from exc
    if len(family_bytes) > 255:
        raise FidelityError("Fidelity STYLE font family exceeds the DXF group-1000 limit of 255 encoded bytes.")

    dxf = style.dxf
    # STYLE flags 4 and 64 mean vertical text and referenced, respectively.
    # Shape and xref records cannot be copied as standalone text styles.
    if (
        dxf.flags & ~(4 | 64)
        or dxf.generation_flags & ~(2 | 4)
        or not all(math.isfinite(value) for value in (dxf.height, dxf.width, dxf.oblique))
        or dxf.height < 0
        or dxf.width <= 0
        or any(char in filename for filename in (dxf.font, dxf.bigfont) for char in "\r\n\0")
    ):
        raise FidelityError("Unsupported render fields in extended Fidelity STYLE.")
    try:
        dxf.font.encode(output_encoding)
        dxf.bigfont.encode(output_encoding)
    except UnicodeEncodeError as exc:
        raise FidelityError("Fidelity STYLE filenames cannot be preserved in the target DXF encoding.") from exc

    return {
        "font": dxf.font,
        "bigfont": dxf.bigfont,
        "flags": dxf.flags & 4,
        "height": dxf.height,
        "width": dxf.width,
        "oblique": dxf.oblique,
        "generation_flags": dxf.generation_flags,
    }, tags


def _copy_fidelity_text_style(
    source_document: Any,
    target_document: Any,
    name: str,
    *,
    source_repeated_styles: Collection[StyleRecordKey],
    target_repeated_styles: Collection[StyleRecordKey] = (),
) -> str:
    target_name = name or _UNICODE_TEXT_STYLE
    target_style = target_document.styles.get(target_name) if target_name in target_document.styles else None
    target_definition = _fidelity_extended_style_definition(
        target_style,
        output_encoding=target_document.output_encoding,
        repeated_style_records=target_repeated_styles,
    )
    if not name:
        if target_definition is not None:
            raise FidelityError("Extended Fidelity STYLE conflicts with the Unicode text fallback.")
        return _ensure_unicode_text_style(target_document)

    source_style = source_document.styles.get(name) if name in source_document.styles else None
    source_definition = _fidelity_extended_style_definition(
        source_style,
        output_encoding=target_document.output_encoding,
        repeated_style_records=source_repeated_styles,
    )
    if target_style is not None:
        if source_definition != target_definition:
            raise FidelityError("Conflicting Fidelity STYLE definitions for the same name.")
        return name

    if source_definition is None:
        source_style = source_document.styles.get(name)
        target_document.styles.add(name, font=str(source_style.dxf.get("font", "Arial.ttf")))
        return name

    attributes, tags = source_definition
    font = attributes.pop("font")
    target_style = target_document.styles.add(name, font=font, dxfattribs=attributes)
    target_style.set_xdata("ACAD", tags)
    return name


def _copy_fidelity_linetype(source_document: Any, target_document: Any, name: str) -> None:
    if name in target_document.linetypes or name.upper() in {"BYLAYER", "BYBLOCK", "CONTINUOUS"}:
        return
    source_linetype = source_document.linetypes.get(name)
    pattern = [tag.value for tag in source_linetype.pattern_tags.tags if tag.code == 49]
    length = next((float(tag.value) for tag in source_linetype.pattern_tags.tags if tag.code == 40), 0.0)
    target_document.linetypes.add(
        name,
        pattern or [0.0],
        description=str(source_linetype.dxf.get("description", "")),
        length=length,
    )


def _fidelity_local_point(point: Any, offset_x: float, offset_y: float) -> tuple[float, float, float]:
    return (float(point.x) - offset_x, float(point.y) - offset_y, float(point.z))


def _fidelity_line_matches(
    first: Any,
    second: Any,
    start: Any,
    end: Any,
    tolerance: float,
    *,
    pixel_scale: float = 0.0,
) -> bool:
    def xy(point: Any) -> tuple[float, float]:
        if hasattr(point, "x"):
            return float(point.x), float(point.y)
        return float(point[0]), float(point[1])

    first_x, first_y = xy(first)
    second_x, second_y = xy(second)
    start_x, start_y = xy(start)
    end_x, end_y = xy(end)
    direct = (
        math.hypot(first_x - start_x, first_y - start_y) <= tolerance
        and math.hypot(second_x - end_x, second_y - end_y) <= tolerance
    )
    reverse = (
        math.hypot(first_x - end_x, first_y - end_y) <= tolerance
        and math.hypot(second_x - start_x, second_y - start_y) <= tolerance
    )
    if direct or reverse or pixel_scale <= 0.0:
        return direct or reverse

    # Raster geometry can split/extend the same horizontal source band into
    # different endpoints. Keep this normalization narrow: it is only enabled
    # by the linetype handoff, only for horizontal lines, and only within one
    # additional source pixel of the existing region tolerance.
    alignment_tolerance = tolerance + pixel_scale
    if (
        abs(first_y - second_y) > alignment_tolerance
        or abs(start_y - end_y) > alignment_tolerance
        or abs(((first_y + second_y) - (start_y + end_y)) / 2.0) > alignment_tolerance
    ):
        return False
    first_min, first_max = sorted((first_x, second_x))
    start_min, start_max = sorted((start_x, end_x))
    overlap = max(0.0, min(first_max, start_max) - max(first_min, start_min))
    shorter = min(first_max - first_min, start_max - start_min)
    return shorter > 0.0 and overlap >= 0.5 * shorter


def _merge_fidelity_owner_output_into_region(
    target_document: Any,
    source_document: Any,
    kind: str,
    region: dict[str, Any],
    page: dict[str, Any],
    height_px: float,
    *,
    source_repeated_styles: Collection[StyleRecordKey] = (),
    target_repeated_styles: Collection[StyleRecordKey] = (),
) -> dict[str, int]:
    offset_x, offset_y, tolerance = _fidelity_region_offsets(region, page, height_px)
    target_model = target_document.modelspace()
    counts = {"TEXT": 0, "MTEXT": 0, "DIMENSION": 0, "LINETYPE": 0}
    if kind == "text":
        for entity in source_document.modelspace():
            if entity.dxftype() not in {"TEXT", "MTEXT"}:
                continue
            insert = entity.dxf.insert
            if not _fidelity_point_in_region(insert, offset_x, offset_y, region, page, height_px, tolerance):
                continue
            style = _copy_fidelity_text_style(
                source_document, target_document, str(entity.dxf.get("style", "")),
                source_repeated_styles=source_repeated_styles,
                target_repeated_styles=target_repeated_styles,
            )
            if entity.dxftype() == "TEXT":
                attributes = {"layer": "FIDELITY_TEXT", "height": float(entity.dxf.get("height", 1.0)), "style": style}
                for name in ("rotation", "oblique", "width", "text_generation_flag", "thickness"):
                    if entity.dxf.hasattr(name):
                        attributes[name] = entity.dxf.get(name)
                output = target_model.add_text(str(entity.dxf.text), dxfattribs=attributes)
                output.dxf.insert = _fidelity_local_point(insert, offset_x, offset_y)
                counts["TEXT"] += 1
            else:
                attributes = {"layer": "FIDELITY_TEXT", "char_height": float(entity.dxf.get("char_height", 1.0)), "style": style}
                for name in ("rotation", "width", "attachment_point", "line_spacing_style", "line_spacing_factor"):
                    if entity.dxf.hasattr(name):
                        attributes[name] = entity.dxf.get(name)
                output = target_model.add_mtext(str(entity.text), dxfattribs=attributes)
                output.dxf.insert = _fidelity_local_point(insert, offset_x, offset_y)
                counts["MTEXT"] += 1
    elif kind == "dimension":
        for entity in source_document.modelspace().query("DIMENSION"):
            dimension_type = int(entity.dxf.get("dimtype", 0)) & 0x0F
            if dimension_type != 0:
                raise FidelityError(f"Unsupported fidelity dimension type {dimension_type}; only linear dimensions are supported.")
            if not all(entity.dxf.hasattr(name) for name in ("defpoint", "defpoint2", "defpoint3")):
                raise FidelityError("Only linear fidelity dimensions with definition points are supported.")
            points = [entity.dxf.defpoint, entity.dxf.defpoint2, entity.dxf.defpoint3]
            midpoint = entity.dxf.get("text_midpoint", entity.dxf.defpoint)
            if not all(_fidelity_point_in_region(point, offset_x, offset_y, region, page, height_px, tolerance) for point in [*points, midpoint]):
                continue
            dimstyle = str(entity.dxf.get("dimstyle", "Standard"))
            if dimstyle not in target_document.dimstyles:
                source_style = source_document.dimstyles.get(dimstyle)
                attributes = {key: value for key, value in source_style.dxfattribs().items() if key not in {"handle", "owner", "name"}}
                target_document.dimstyles.add(dimstyle, dxfattribs=attributes)
            output = target_model.add_linear_dim(
                base=_fidelity_local_point(entity.dxf.defpoint, offset_x, offset_y),
                p1=_fidelity_local_point(entity.dxf.defpoint2, offset_x, offset_y),
                p2=_fidelity_local_point(entity.dxf.defpoint3, offset_x, offset_y),
                location=_fidelity_local_point(midpoint, offset_x, offset_y),
                angle=float(entity.dxf.get("angle", 0.0)),
                text=str(entity.dxf.get("text", "<>")),
                dimstyle=dimstyle,
                dxfattribs={"layer": "FIDELITY_DIMENSIONS"},
            )
            output.render()
            counts["DIMENSION"] += 1
    else:
        matched_targets: set[int] = set()
        pixel_scale = float(page["pixel_to_paper_mm"]["used"])
        for entity in source_document.modelspace().query("LINE"):
            line_type = str(entity.dxf.get("linetype", ""))
            if line_type.upper() in {"", "BYLAYER", "BYBLOCK", "CONTINUOUS"}:
                continue
            if not all(_fidelity_point_in_region(point, offset_x, offset_y, region, page, height_px, tolerance) for point in (entity.dxf.start, entity.dxf.end)):
                continue
            start = _fidelity_local_point(entity.dxf.start, offset_x, offset_y)
            end = _fidelity_local_point(entity.dxf.end, offset_x, offset_y)
            matches = [
                candidate for candidate in target_model.query("LINE")
                if _fidelity_line_matches(
                    candidate.dxf.start,
                    candidate.dxf.end,
                    start,
                    end,
                    tolerance,
                    pixel_scale=pixel_scale,
                )
            ]
            if not matches:
                raise FidelityError(f"Linetype owner output line has no matching local region line for {line_type}.")
            matches = [candidate for candidate in matches if id(candidate) not in matched_targets]
            if not matches:
                continue
            exact_matches = [
                candidate for candidate in matches
                if _fidelity_line_matches(
                    candidate.dxf.start,
                    candidate.dxf.end,
                    start,
                    end,
                    tolerance,
                )
            ]
            if len(exact_matches) > 1:
                raise FidelityError(f"Ambiguous exact horizontal linetype match for {line_type}.")
            if len(exact_matches) == 1:
                selected = exact_matches[0]
            elif len(matches) > 1:
                raise FidelityError(f"Ambiguous fuzzy horizontal linetype match for {line_type}.")
            else:
                selected = matches[0]
            _copy_fidelity_linetype(source_document, target_document, line_type)
            selected.dxf.linetype = line_type
            matched_targets.add(id(selected))
            if entity.dxf.hasattr("linetype_scale"):
                selected.dxf.linetype_scale = entity.dxf.linetype_scale
            counts["LINETYPE"] += 1
    return counts


def run_fidelity_semantic_region_handoff(
    source: Path, output_root: Path, manifest: dict[str, Any], approval_path: Path, *, workspace_root: Path,
) -> list[Path]:
    """Transfer existing approved semantic-owner DXFs into approved local candidates."""
    import ezdxf

    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Region approval must reside inside the private fidelity output root.")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("state") != "approved-layout-reconstruction-only" or approval.get("source") != manifest.get("source"):
        raise FidelityError("Region approval is not valid for semantic handoff.")
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
    height_px = float(image.shape[0])
    owner_outputs: dict[str, tuple[Path, str]] = {}
    for kind, prefix in (("text", "text_reconstruction"), ("dimension", "dimension_reconstruction"), ("linetype", "linetype_reconstruction")):
        path = _latest_fidelity_owner_output(output_root, prefix, page_number)
        if path is not None:
            report = _validate_fidelity_owner_output(output_root, path, kind, page, manifest)
            owner_outputs[kind] = (path, report["output_dxf_sha256"])
    if not owner_outputs:
        raise FidelityError("No validated semantic owner output is available for handoff.")
    selected = [item for item in proposal["regions"] if item["id"] in approval["approved_region_ids"]]
    transferred: list[dict[str, Any]] = []
    prepared_candidates = []
    for region in selected:
        candidate_path = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"] / "geometry.dxf"
        if not candidate_path.is_file():
            raise FidelityError(f"Missing approved region candidate: {candidate_path}")
        target_repeated_styles: set[StyleRecordKey] = set()
        if "text" in owner_outputs:
            document, target_repeated_styles = _read_fidelity_style_document(candidate_path)
        else:
            document = ezdxf.readfile(candidate_path)
        counts = {"TEXT": 0, "MTEXT": 0, "DIMENSION": 0, "LINETYPE": 0}
        for kind, (owner_path, owner_sha256) in owner_outputs.items():
            source_repeated_styles: set[StyleRecordKey] = set()
            if kind == "text":
                source_document, source_repeated_styles = _read_fidelity_style_document(
                    owner_path, expected_sha256=owner_sha256,
                )
            else:
                source_document = ezdxf.readfile(owner_path)
            result = _merge_fidelity_owner_output_into_region(
                document, source_document, kind, region, page, height_px,
                source_repeated_styles=source_repeated_styles,
                target_repeated_styles=target_repeated_styles,
            )
            counts = {key: counts[key] + result[key] for key in counts}
        prepared_candidates.append((candidate_path, document))
        transferred.append({"region": region["id"], "candidate": str(candidate_path.relative_to(output_root)).replace("\\", "/"), "counts": counts})
    # A later region may reject a STYLE collision. Resolve all transfers before
    # saving any candidate or publishing the handoff report.
    for candidate_path, document in prepared_candidates:
        document.saveas(candidate_path)
    handoff_root = output_root / "semantic_region_handoff"
    revision = 1
    while (handoff_root / f"page_{page_number:02d}.json").exists():
        revision += 1
        handoff_root = output_root / f"semantic_region_handoff-r{revision}"
    handoff_root.mkdir(parents=True)
    report_path = handoff_root / f"page_{page_number:02d}.json"
    report_path.write_text(json.dumps({
        "state": "needs_review",
        "profile": "fidelity-layout-semantic-region-handoff",
        "source": manifest["source"],
        "page": page_number,
        "render_sha256": sha256_file(rendered),
        "owner_outputs": {
            kind: {"path": path.relative_to(output_root).as_posix(), "sha256": sha256_file(path)}
            for kind, (path, _) in owner_outputs.items()
        },
        "transferred": transferred,
        "unresolved": ["semantic placement and visual fidelity require review", "no model export or production AutoCAD mutation"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [report_path]


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


def run_fidelity_hatch_observations(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> list[Path]:
    """Write hash-bound diagonal-stroke evidence without constructing DXF HATCH entities."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    root = output_root / "fidelity_hatch_observations"
    revision = 2
    while root.exists() and any(root.iterdir()):
        root = output_root / f"fidelity_hatch_observations-r{revision}"
        revision += 1
    root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for page in manifest.get("pages", []):
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        image = cv2.imread(str(rendered))
        if image is None:
            raise FidelityError("Cannot read rendered page for hatch observations.")
        output = root / f"page_{page['page']:02d}.json"
        payload = {
            "schema_version": "fidelity-hatch-observation-1.0",
            "private_artifact": True,
            "state": "needs_review",
            "source": manifest["source"],
            "page": page["page"],
            "source_render_sha256": sha256_file(rendered),
            "candidates": _observe_hatch_candidates(image),
            "unresolved": ["no candidate is emitted as a DXF HATCH without boundary approval"],
        }
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def _normalized_hatch_mappings(
    mappings: object,
    candidates: dict[str, dict[str, Any]],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    if not isinstance(mappings, list) or not mappings:
        raise FidelityError("Hatch approval requires at least one mapping.")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mapping in mappings:
        if not isinstance(mapping, dict) or not isinstance(mapping.get("candidate_id"), str):
            raise FidelityError("Hatch mappings require candidate_id and boundary_px.")
        candidate_id = mapping["candidate_id"]
        if candidate_id in seen or candidate_id not in candidates:
            raise FidelityError(f"Unknown or duplicate hatch candidate: {candidate_id}")
        candidate_box = candidates[candidate_id].get("bbox_px")
        if (
            not isinstance(candidate_box, list)
            or len(candidate_box) != 4
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in candidate_box)
        ):
            raise FidelityError(f"Hatch candidate has no valid bbox: {candidate_id}")
        boundary = mapping.get("boundary_px")
        if not isinstance(boundary, list) or len(boundary) < 3:
            raise FidelityError("Hatch boundary requires at least three points.")
        points: list[list[float]] = []
        for point in boundary:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
            ):
                raise FidelityError("Hatch boundary points must be numeric [x, y] pairs.")
            x, y = float(point[0]), float(point[1])
            if not (0 <= x <= width and 0 <= y <= height):
                raise FidelityError("Hatch boundary point is outside the rendered page.")
            if not (
                float(candidate_box[0]) <= x <= float(candidate_box[2])
                and float(candidate_box[1]) <= y <= float(candidate_box[3])
            ):
                raise FidelityError("Hatch boundary must remain inside its observed candidate bbox.")
            points.append([x, y])
        area = abs(sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        ) / 2.0)
        if area <= 1.0:
            raise FidelityError("Hatch boundary polygon has zero area.")
        angle = mapping.get("angle", 45.0)
        scale = mapping.get("scale", 1.0)
        if (
            isinstance(angle, bool)
            or not isinstance(angle, (int, float))
            or isinstance(scale, bool)
            or not isinstance(scale, (int, float))
            or float(scale) <= 0
        ):
            raise FidelityError("Hatch angle and positive pattern scale are required.")
        normalized.append({
            "candidate_id": candidate_id,
            "boundary_px": points,
            "angle": float(angle),
            "scale": float(scale),
        })
        seen.add(candidate_id)
    return normalized


def write_fidelity_hatch_approval(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    page_number: int,
    observation_path: Path,
    base_dxf: Path,
    mappings: list[dict[str, Any]],
    approval_reference: str,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    """Record explicit polygon boundaries for observed hatch candidates."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(observation_path, output_root) or not observation_path.is_file():
        raise FidelityError("Hatch observation must reside inside the private fidelity output root.")
    if not _is_within(base_dxf, output_root) or not base_dxf.is_file():
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    if not isinstance(page_number, int) or not isinstance(mappings, list) or not mappings:
        raise FidelityError("Hatch approval requires a page number and at least one mapping.")
    if not approval_reference.strip():
        raise FidelityError("Hatch approval requires a non-empty approval reference.")
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Hatch observation is invalid JSON.") from exc
    if (
        observation.get("schema_version") != "fidelity-hatch-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("state") != "needs_review"
        or observation.get("source") != manifest.get("source")
        or observation.get("page") != page_number
    ):
        raise FidelityError("Hatch observation is not valid for approval.")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Hatch approval page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Hatch observation does not match the rendered page.")
    image = cv2.imread(str(rendered))
    if image is None:
        raise FidelityError("Cannot read rendered page for hatch approval.")
    height, width = image.shape[:2]
    candidates = {item.get("id"): item for item in observation.get("candidates", []) if isinstance(item, dict)}
    normalized = _normalized_hatch_mappings(mappings, candidates, width, height)
    output = output_root / "fidelity_hatch_approvals" / f"page_{page_number:02d}.json"
    if output.exists():
        raise FidelityError(f"Hatch approval already exists: {output}")
    payload = {
        "schema_version": "fidelity-hatch-approval-1.0",
        "private_artifact": True,
        "state": "approved-hatch-boundaries",
        "source": manifest["source"],
        "page": page_number,
        "observation": _artifact(observation_path, output_root),
        "base_dxf": _artifact(base_dxf, output_root),
        "approval_reference": approval_reference.strip(),
        "mappings": normalized,
        "unresolved": ["hatch fill remains a visual fidelity candidate", "no model export or production AutoCAD mutation"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def run_fidelity_hatch_reconstruct(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
    base_dxf: Path,
    *,
    workspace_root: Path,
) -> Path:
    """Emit explicitly approved polygon boundaries as review-only DXF HATCHes."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Hatch approval must reside inside the private fidelity output root.")
    if not _is_within(base_dxf, output_root) or not base_dxf.is_file():
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Hatch approval is invalid JSON.") from exc
    if (
        approval.get("schema_version") != "fidelity-hatch-approval-1.0"
        or approval.get("private_artifact") is not True
        or approval.get("state") != "approved-hatch-boundaries"
        or approval.get("source") != manifest.get("source")
    ):
        raise FidelityError("Hatch approval has an unsupported schema.")
    if not isinstance(approval.get("approval_reference"), str) or not approval["approval_reference"].strip():
        raise FidelityError("Hatch approval requires a non-empty approval reference.")
    base_record = approval.get("base_dxf")
    if not isinstance(base_record, dict):
        raise FidelityError("Hatch approval is missing base DXF provenance.")
    try:
        approved_base = _safe_artifact_path(output_root, base_record)
    except FidelityError as exc:
        raise FidelityError("Approved base DXF is missing or no longer matches its hash.") from exc
    if approved_base != base_dxf.resolve():
        raise FidelityError("Requested base DXF does not match the approved base DXF.")
    observation_record = approval.get("observation")
    if not isinstance(observation_record, dict):
        raise FidelityError("Hatch approval is missing observation provenance.")
    observation_path = _safe_artifact_path(output_root, observation_record)
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Hatch observation is invalid JSON.") from exc
    if (
        observation.get("schema_version") != "fidelity-hatch-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("source") != manifest.get("source")
        or observation.get("page") != approval.get("page")
    ):
        raise FidelityError("Hatch observation does not match its approval.")
    page_number = approval.get("page")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Hatch approval page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Hatch observation does not match the rendered page.")
    image = cv2.imread(str(rendered))
    if image is None:
        raise FidelityError("Cannot read rendered page for hatch reconstruction.")
    height, width = image.shape[:2]
    audit = json.loads(_safe_artifact_path(output_root, page["artifacts"]["layout_audit"]).read_text(encoding="utf-8"))
    height_px = int(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    import ezdxf

    document = ezdxf.readfile(base_dxf)
    model = document.modelspace()
    if "FIDELITY_HATCH" not in document.layers:
        document.layers.new("FIDELITY_HATCH", dxfattribs={"color": 8})
    candidates = {item.get("id"): item for item in observation.get("candidates", []) if isinstance(item, dict)}
    mappings = _normalized_hatch_mappings(approval.get("mappings"), candidates, width, height)
    emitted: list[dict[str, Any]] = []
    for mapping in mappings:
        candidate_id = mapping["candidate_id"]
        boundary = mapping["boundary_px"]
        points = [(float(point[0]) * scale, (height_px - float(point[1])) * scale) for point in boundary]
        hatch = model.add_hatch(dxfattribs={"layer": "FIDELITY_HATCH"})
        hatch.paths.add_polyline_path(points, is_closed=True)
        hatch.set_pattern_fill("ANSI31", scale=float(mapping.get("scale", 1.0)), angle=float(mapping.get("angle", 45.0)))
        emitted.append({"candidate_id": candidate_id, "dimension": len(points), "hatch_handle": hatch.dxf.handle})
    root_base = output_root / "hatch_reconstruction"
    root = root_base / f"page_{page_number:02d}"
    revision = 2
    while root.exists():
        root = output_root / f"hatch_reconstruction-r{revision}" / f"page_{page_number:02d}"
        revision += 1
    root.mkdir(parents=True)
    output = root / "layout.dxf"
    document.saveas(output)
    report = {
        "state": "needs_review",
        "profile": "fidelity-layout-hatch",
        "source": manifest["source"],
        "page": page_number,
        "source_render_sha256": sha256_file(rendered),
        "observation_sha256": sha256_file(observation_path),
        "approval_sha256": sha256_file(approval_path),
        "base_dxf_sha256": sha256_file(base_dxf),
        "output_dxf_sha256": sha256_file(output),
        "emitted_hatch_entities": len(emitted),
        "mappings": emitted,
        "unresolved": ["hatch boundaries and pattern need visual review", "no model export or production AutoCAD mutation"],
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


_APPROVED_REGION_OCR_TILE_LIMIT = 320
_APPROVED_REGION_OCR_CALL_LIMIT = 64
_APPROVED_REGION_OCR_CANVAS_PIXEL_LIMIT = 16_000_000


def _region_proposal_definition_sha256(proposal: dict[str, Any]) -> str:
    definition = {
        "regions": proposal.get("regions"),
        "excluded_regions": proposal.get("excluded_regions"),
    }
    return __import__("hashlib").sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_approved_region_text_proposal(
    proposal: object,
    proposal_record: dict[str, Any],
    manifest: dict[str, Any],
    page: dict[str, Any],
    rendered: Path,
    output_root: Path,
    page_number: int,
) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise FidelityError("Approved region proposal is invalid JSON.")
    if (
        proposal.get("schema_version") != "fidelity-region-proposal-1.0"
        or proposal.get("private_artifact") is not True
        or proposal.get("state") != "needs_human_approval"
        or proposal.get("source") != manifest.get("source")
    ):
        raise FidelityError("Approved region proposal is not current for text observation.")
    proposal_page = proposal.get("page")
    if not isinstance(proposal_page, dict) or proposal_page.get("number") != page_number:
        raise FidelityError("Approved region proposal page does not match the approval page.")
    audit = json.loads(_safe_artifact_path(output_root, page["artifacts"]["layout_audit"]).read_text(encoding="utf-8"))
    source_page = audit.get("source_page", {})
    expected_page = {
        "render_sha256": sha256_file(rendered),
        "render_width_px": source_page.get("render_width_px"),
        "render_height_px": source_page.get("render_height_px"),
        "dpi": source_page.get("dpi"),
    }
    if any(proposal_page.get(key) != value for key, value in expected_page.items()):
        raise FidelityError("Approved region proposal render metadata is stale.")
    render_width = source_page.get("render_width_px")
    render_height = source_page.get("render_height_px")
    if not isinstance(render_width, int) or not isinstance(render_height, int):
        raise FidelityError("Approved region proposal render dimensions are invalid.")
    _normalized_regions(
        {"regions": proposal.get("regions"), "excluded_regions": proposal.get("excluded_regions")},
        render_width,
        render_height,
    )
    if proposal.get("proposal_definition_sha256") != _region_proposal_definition_sha256(proposal):
        raise FidelityError("Approved region proposal definition is stale.")
    if proposal.get("proposal_definition_sha256") != proposal_record.get("definition_sha256"):
        raise FidelityError("Approved proposal definition no longer matches its approval.")
    return proposal


def _approved_region_text_candidates(
    image: np.ndarray,
    regions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the existing OCR owner over explicitly approved region ROIs only."""
    candidates: list[dict[str, Any]] = []
    detector_roi_count = 0
    ocr_call_count = 0
    for region in regions:
        x0, y0, x1, y1 = (int(value) for value in region["bbox_px"])
        crop = image[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        for rotation in (0, 90):
            rotated = crop if rotation == 0 else cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
            detected = detect_text_candidate_rois(rotated, min_cluster_components=1)
            detector_roi_count += len(detected)
            if detector_roi_count > _APPROVED_REGION_OCR_TILE_LIMIT:
                raise FidelityError("Approved-region OCR exceeded the bounded tile limit.")
            original_height = crop.shape[0]
            tiles: list[tuple[int, tuple[int, int, int, int], tuple[int, int, int, int], np.ndarray]] = []
            canvas_y = 10
            canvas_width = 1
            for roi in detected:
                rx0, ry0, rx1, ry1 = roi
                expanded = (
                    max(0, rx0 - 20),
                    max(0, ry0 - 5),
                    min(rotated.shape[1], rx1 + 20),
                    min(rotated.shape[0], ry1 + 5),
                )
                patch = rotated[expanded[1]:expanded[3], expanded[0]:expanded[2]]
                if patch.size == 0:
                    continue
                tiles.append((canvas_y, expanded, roi, patch))
                canvas_y += patch.shape[0] + 10
                canvas_width = max(canvas_width, patch.shape[1])
            if not tiles:
                continue
            if ocr_call_count >= _APPROVED_REGION_OCR_CALL_LIMIT:
                raise FidelityError("Approved-region OCR exceeded the bounded invocation limit.")
            if canvas_y * canvas_width > _APPROVED_REGION_OCR_CANVAS_PIXEL_LIMIT:
                raise FidelityError("Approved-region OCR exceeded the bounded canvas limit.")
            canvas = np.full((canvas_y, canvas_width, 3), 255, dtype=np.uint8)
            for tile_y, _, _, patch in tiles:
                canvas[tile_y:tile_y + patch.shape[0], :patch.shape[1]] = patch
            recognized = extract_text_tesseract(
                canvas,
                roi_boxes=[(0, 0, canvas.shape[1], canvas.shape[0])],
                min_confidence=20,
                psm=11,
            )
            ocr_call_count += 1
            for text in recognized:
                tx0, ty0, tx1, ty1 = text.bbox_px
                center_y = (ty0 + ty1) / 2.0
                tile = next((item for item in tiles if item[0] <= center_y <= item[0] + item[3].shape[0]), None)
                if tile is None:
                    continue
                tile_y, expanded, roi, _ = tile
                local_bbox = (
                    tx0 + expanded[0],
                    ty0 - tile_y + expanded[1],
                    tx1 + expanded[0],
                    ty1 - tile_y + expanded[1],
                )
                lx0, ly0, lx1, ly1 = local_bbox
                if rotation == 0:
                    mapped = (x0 + lx0, y0 + ly0, x0 + lx1, y0 + ly1)
                else:
                    mapped = (
                        x0 + ly0,
                        y0 + original_height - lx1,
                        x0 + ly1,
                        y0 + original_height - lx0,
                    )
                if not (
                    x0 <= mapped[0] < mapped[2] <= x1
                    and y0 <= mapped[1] < mapped[3] <= y1
                ):
                    continue
                candidate = _raw_text_payload(text)
                candidate["bbox_px"] = list(mapped)
                candidate["rotation_deg"] = float(rotation)
                candidate["approved_region_id"] = region["id"]
                candidate["roi_px"] = list(roi)
                candidates.append(candidate)
        block_roi = _validated_ocr_roi(
            ocr_roi=region.get("ocr_roi_px"),
            region_width=x1 - x0,
            region_height=y1 - y0,
            category="approved region",
        )
        if block_roi is not None:
            rx0, ry0, rx1, ry1 = block_roi
            block_crop = crop[ry0:ry1, rx0:rx1]
            block_scale = 3
            scaled_width = (rx1 - rx0) * block_scale
            scaled_height = (ry1 - ry0) * block_scale
            if scaled_width * scaled_height > _APPROVED_REGION_OCR_CANVAS_PIXEL_LIMIT:
                raise FidelityError("Approved-region OCR exceeded the bounded canvas limit.")
            if ocr_call_count >= _APPROVED_REGION_OCR_CALL_LIMIT:
                raise FidelityError("Approved-region OCR exceeded the bounded invocation limit.")
            block_image = cv2.resize(
                block_crop,
                None,
                fx=block_scale,
                fy=block_scale,
                interpolation=cv2.INTER_CUBIC,
            )
            recognized = extract_text_tesseract(
                block_image,
                roi_boxes=[(0, 0, block_image.shape[1], block_image.shape[0])],
                min_confidence=20,
                psm=6,
            )
            ocr_call_count += 1
            for text in recognized:
                tx0, ty0, tx1, ty1 = text.bbox_px
                mapped = (
                    x0 + rx0 + int(tx0 / block_scale),
                    y0 + ry0 + int(ty0 / block_scale),
                    x0 + rx0 + int(tx1 / block_scale),
                    y0 + ry0 + int(ty1 / block_scale),
                )
                if not (
                    x0 <= mapped[0] < mapped[2] <= x1
                    and y0 <= mapped[1] < mapped[3] <= y1
                ):
                    continue
                candidate = _raw_text_payload(text)
                candidate["bbox_px"] = list(mapped)
                candidate["rotation_deg"] = 0.0
                candidate["approved_region_id"] = region["id"]
                candidate["roi_px"] = list(block_roi)
                candidates.append(candidate)
    return candidates, {"detector_roi_count": detector_roi_count, "ocr_call_count": ocr_call_count}


def _approved_region_selection(
    output_root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
) -> tuple[int, list[dict[str, Any]]]:
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Region approval must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Region approval is invalid JSON.") from exc
    if (
        approval.get("schema_version") != "fidelity-region-approval-1.0"
        or approval.get("private_artifact") is not True
        or approval.get("state") != "approved-layout-reconstruction-only"
        or approval.get("source") != manifest.get("source")
    ):
        raise FidelityError("Region approval is not valid for fresh OCR reconstruction.")
    page_record = approval.get("page")
    page_number = page_record.get("number") if isinstance(page_record, dict) else None
    if page_number != 1:
        raise FidelityError("Approved-region text reconstruction is page 1 only.")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Region approval page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if page_record.get("render_sha256") != sha256_file(rendered):
        raise FidelityError("Region approval render hash no longer matches the page artifact.")
    proposal_record = approval.get("proposal")
    if not isinstance(proposal_record, dict):
        raise FidelityError("Region approval is missing its proposal provenance.")
    proposal_path = _safe_artifact_path(output_root, proposal_record)
    proposal = _validate_approved_region_text_proposal(
        json.loads(proposal_path.read_text(encoding="utf-8")),
        proposal_record,
        manifest,
        page,
        rendered,
        output_root,
        page_number,
    )
    approved_ids = approval.get("approved_region_ids")
    if not isinstance(approved_ids, list) or not approved_ids:
        raise FidelityError("Region approval must name approved regions.")
    selected = [item for item in proposal.get("regions", []) if isinstance(item, dict) and item.get("id") in approved_ids]
    if len(selected) != len(approved_ids):
        raise FidelityError("Region approval names an unknown region.")
    return page_number, selected


def _fresh_fidelity_ocr_candidates(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    page: dict[str, Any],
    observation: dict[str, Any],
) -> list[dict[str, Any]]:
    page_number = page.get("page")
    dpi = manifest.get("configuration", {}).get("dpi")
    if type(page_number) is not int or page_number < 1 or type(dpi) is not int or dpi <= 0:
        raise FidelityError("Fresh OCR requires valid source page and render DPI metadata.")
    try:
        with fitz.open(source) as document:
            if page_number > len(document):
                raise FidelityError("Fresh OCR page is absent from the source PDF.")
            pixmap = document[page_number - 1].get_pixmap(
                matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False,
            )
        fresh_image = cv2.imdecode(np.frombuffer(pixmap.tobytes("png"), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, RuntimeError, ValueError) as exc:
        raise FidelityError("Could not render the source PDF page for fresh OCR.") from exc
    if fresh_image is None:
        raise FidelityError("Fresh OCR could not decode the source PDF page render.")

    rendered_path = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    stored_image = cv2.imread(str(rendered_path))
    if stored_image is None or stored_image.shape != fresh_image.shape or not np.array_equal(stored_image, fresh_image):
        raise FidelityError("Fresh OCR source render does not match the reviewed page frame.")
    audit_path = _safe_artifact_path(output_root, page["artifacts"]["layout_audit"])
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    source_page = audit.get("source_page", {})
    if (
        type(source_page.get("page")) is not int
        or
        source_page.get("page") != page_number
        or source_page.get("render_width_px") != fresh_image.shape[1]
        or source_page.get("render_height_px") != fresh_image.shape[0]
    ):
        raise FidelityError("Fresh OCR source page does not match the reviewed audit frame.")

    candidates = _fidelity_text_candidate_records(fresh_image)
    region_record = observation.get("region_approval")
    if region_record is None:
        regions = []
    elif not isinstance(region_record, dict):
        raise FidelityError("Text observation has invalid approved-region provenance.")
    else:
        region_path = _safe_artifact_path(output_root, region_record)
        region_page, regions = _approved_region_selection(output_root, manifest, region_path)
        if region_page != page_number:
            raise FidelityError("Text observation approved-region page does not match fresh OCR page.")
    if regions:
        extra, _ = _approved_region_text_candidates(fresh_image, regions)
        candidates.extend(extra)
    return candidates


class _NativePdfThinStrokeCheck:
    """Bind PDF glyph and paint evidence for narrow stroke and fill decisions."""

    _SCALE = 24
    _PAIR_LIMIT = 64
    _FILL_PAIR_LIMIT = 2
    _FILL_PADDING_PT = 0.002
    _PAIR_PIXELS = 2_000_000
    _PAGE_PIXELS = 8_000_000
    _SVG_BYTES_LIMIT = 4 * 1024 * 1024
    _SVG_NODE_LIMIT = 10_000
    _FONT_ROW_LIMIT = 16
    _FONT_PROGRAM_LIMIT = 8
    _FONT_BYTES_LIMIT = 4 * 1024 * 1024
    _PATH_OPERATION_LIMIT = 10_000
    _SVG_NS = "{http://www.w3.org/2000/svg}"
    _HREF = "{http://www.w3.org/1999/xlink}href"

    def __init__(self, page: fitz.Page, paint_log: Collection[Any]) -> None:
        self.page = page
        self.paint_log = paint_log
        self.export_ready = False
        self.paths: dict[int, Any] = {}
        self.glyphs: dict[tuple[str, int], list[tuple[Any, tuple[float, ...]]]] = {}
        self.definitions: dict[str, Any] = {}
        self.fonts: dict[str, Any] = {}
        self.base14_fonts: dict[str, fitz.Font | None] = {}
        self.base14_trace_bounds: dict[int, dict[tuple[int, tuple[Any, ...]], fitz.Rect] | None] = {}
        self.base14_stroke_geometry: dict[int, tuple[dict[str, Any], tuple[fitz.Rect, ...], fitz.Rect] | None] = {}
        self.font_resources: dict[str, list[tuple[Any, ...]]] | None = None
        self.font_programs: dict[int, bytes | None] = {}
        self.font_bytes = 0
        self.path_operations = 0
        self.preparation_exhausted = False
        self.strokes: dict[int, str | None] = {}
        self.fill_bounds: dict[int, list[tuple[float, ...]] | None] = {}
        self.ink_bounds: dict[tuple[int, float, tuple[int, int] | None], list[tuple[float, ...]] | None] = {}
        self.fill_separations: dict[tuple[int, int, float, tuple[int, int] | None], bool] = {}
        self.masks: dict[tuple[Any, ...], np.ndarray | None] = {}
        self.pairs = 0
        self.fill_attempts = 0
        self.pixels = 0

    @staticmethod
    def _matrix(node: Any) -> tuple[float, ...]:
        transform = re.fullmatch(r"matrix\(([^)]+)\)", node.get("transform", ""))
        if transform is None:
            raise ValueError("Expected an explicit SVG paint transform")
        matrix = tuple(float(value) for value in re.split(r"[\s,]+", transform[1].strip()))
        if len(matrix) != 6 or not all(math.isfinite(value) for value in matrix):
            raise ValueError("Invalid SVG paint transform")
        return matrix

    @staticmethod
    def _color_matches(color: str, rgb: Any) -> bool:
        return (
            re.fullmatch(r"#[0-9a-fA-F]{6}", color) is not None
            and isinstance(rgb, (list, tuple)) and len(rgb) == 3
            and all(abs(int(color[i:i + 2], 16) / 255 - value) <= 0.5 / 255 + 1e-7
                    for i, value in zip((1, 3, 5), rgb))
        )

    @staticmethod
    def _path_data(node: Any) -> str:
        path = node.get("d", "")
        if not re.fullmatch(r"[MLHVCSQTAZmlhvcsqtaz0-9eE.+, \t\r\n-]+", path):
            raise ValueError("Unsupported SVG path data")
        return path

    def _prepare_export(self) -> None:
        from xml.etree import ElementTree

        self.export_ready = True
        svg = self.page.get_svg_image(text_as_path=True)
        if (len(svg) > self._SVG_BYTES_LIMIT
                or not svg.isascii() and len(svg.encode("utf-8")) > self._SVG_BYTES_LIMIT
                or "<!" in svg):
            return

        class BoundedTreeBuilder(ElementTree.TreeBuilder):
            def __init__(self, limit: int) -> None:
                super().__init__()
                self.limit = limit
                self.nodes = 0

            def start(self, tag, attrs):
                if self.nodes >= self.limit:
                    raise ValueError("SVG node budget exhausted")
                self.nodes += 1
                return super().start(tag, attrs)

        parser = ElementTree.XMLParser(target=BoundedTreeBuilder(self._SVG_NODE_LIMIT))
        root = ElementTree.fromstring(svg, parser=parser)
        ns = self._SVG_NS
        if root.tag != ns + "svg" or not set(root.attrib) <= {"width", "height", "viewBox", "version"}:
            return
        if tuple(map(float, root.attrib["viewBox"].split())) != (
            0.0, 0.0, round(self.page.rect.width, 3), round(self.page.rect.height, 3),
        ):
            return
        if any(child.tag not in {ns + "defs", ns + "path", ns + "use"} for child in root):
            return
        defs = root.findall(ns + "defs")
        if len(defs) != 1:
            return
        definitions = {node.get("id"): node for node in defs[0]}
        if len(definitions) != len(defs[0]) or None in definitions:
            return
        path_nodes = [node for node in root if node.tag == ns + "path"]
        path_sequences = [(i, paint[0]) for i, paint in enumerate(self.paint_log)
                          if paint[0] in ("stroke-path", "fill-path")]
        if len(path_nodes) != len(path_sequences):
            return
        indexed = {}
        for node in root:
            if node.tag != ns + "use":
                continue
            match = re.fullmatch(r"#(font_\d+_(\d+))", node.get(self._HREF, ""))
            if match is None or match[1] not in definitions:
                return
            key = (node.get("data-text"), int(match[2]))
            indexed.setdefault(key, []).append((node, self._matrix(node)))
        for (index, kind), node in zip(path_sequences, path_nodes):
            if (node.get("stroke", "none") != "none") != (kind == "stroke-path"):
                return
        self.glyphs = indexed
        self.definitions = definitions
        self.paths = {index: node for (index, _), node in zip(path_sequences, path_nodes)}

    def _base14_font(self, trace: dict[str, Any]) -> fitz.Font | None:
        font_name = trace.get("font")
        base14_names = {
            "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
            "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
            "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic", "Symbol", "ZapfDingbats",
        }
        if not isinstance(font_name, str) or font_name not in base14_names:
            return None
        if font_name not in self.base14_fonts:
            self.base14_fonts[font_name] = None
            document = self.page.parent
            if document is None:
                return None
            resources = [resource for resource in self.page.get_fonts(full=True)
                         if len(resource) >= 6 and resource[3] == font_name]
            if len(resources) != 1:
                return None
            resource = resources[0]
            if (resource[1] != "n/a" or resource[2] != "Type1"
                    or resource[5] not in ("WinAnsiEncoding", "StandardEncoding", "MacRomanEncoding")):
                return None
            extracted = document.extract_font(resource[0])
            if len(extracted) != 4 or extracted[1:3] != ("n/a", "Type1") or extracted[3]:
                return None
            try:
                font = fitz.Font(font_name)
            except (RuntimeError, ValueError, TypeError):
                return None
            if font.name == font_name:
                self.base14_fonts[font_name] = font
        return self.base14_fonts.get(font_name)

    def _base14_trace_glyph_rects(
        self, trace: dict[str, Any],
    ) -> dict[tuple[int, tuple[Any, ...]], fitz.Rect] | None:
        trace_order_idx = trace.get("_trace_order_idx")
        if type(trace_order_idx) is not int or trace_order_idx < 0:
            return None
        if trace_order_idx in self.base14_trace_bounds:
            return self.base14_trace_bounds[trace_order_idx]
        self.base14_trace_bounds[trace_order_idx] = None
        if (
            trace.get("type") != 0 or trace.get("opacity") != 1 or trace.get("layer")
            or trace.get("wmode") != 0 or trace.get("dir") != (1.0, 0.0)
            or not isinstance(trace.get("size"), (int, float))
            or trace.get("_effective_v_size", trace.get("size")) != trace.get("size")
        ):
            return None
        font = self._base14_font(trace)
        if font is None:
            return None
        chars = trace.get("chars")
        if not isinstance(chars, (tuple, list)) or len(chars) < 2:
            return None
        scale = float(trace["size"])
        for left, right in zip(chars, chars[1:]):
            if (
                not isinstance(left, (tuple, list)) or len(left) < 4
                or not isinstance(right, (tuple, list)) or len(right) < 3
                or type(left[0]) is not int
                or type(left[1]) is not int
                or not isinstance(left[2], (tuple, list)) or len(left[2]) != 2
                or not isinstance(right[2], (tuple, list)) or len(right[2]) != 2
                or font.has_glyph(left[0]) != left[1]
                or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (*left[2], *right[2]))
            ):
                return None
            expected_advance = font.glyph_advance(left[0]) * scale
            actual_advance = float(right[2][0]) - float(left[2][0])
            if not math.isfinite(expected_advance) or expected_advance <= 0 or abs(actual_advance - expected_advance) > 0.01:
                return None
        bounds = {}
        for glyph in chars:
            if (
                not isinstance(glyph, (tuple, list)) or len(glyph) < 4
                or type(glyph[0]) is not int or type(glyph[1]) is not int
                or not isinstance(glyph[2], (tuple, list)) or len(glyph[2]) != 2
                or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in glyph[2])
                or font.has_glyph(glyph[0]) != glyph[1]
            ):
                return None
            local_box = font.glyph_bbox(glyph[0])
            if not local_box.is_valid or local_box.is_empty:
                continue
            key = (glyph[0], tuple(glyph[2]))
            if key in bounds:
                return None
            ox, oy = float(glyph[2][0]), float(glyph[2][1])
            bounds[key] = fitz.Rect(
                ox + float(local_box.x0) * scale,
                oy - float(local_box.y1) * scale,
                ox + float(local_box.x1) * scale,
                oy - float(local_box.y0) * scale,
            )
        self.base14_trace_bounds[trace_order_idx] = bounds or None
        return self.base14_trace_bounds[trace_order_idx]

    def _base14_glyph_rect(
        self, trace: dict[str, Any], glyph: tuple[Any, ...], span_size: Any,
    ) -> fitz.Rect | None:
        if (
            not isinstance(span_size, (int, float)) or not math.isfinite(float(span_size))
            or not isinstance(trace.get("size"), (int, float))
            or abs(float(trace["size"]) - float(span_size)) > 0.001
            or not isinstance(glyph, (tuple, list)) or len(glyph) < 3
            or type(glyph[0]) is not int
            or not isinstance(glyph[2], (tuple, list)) or len(glyph[2]) != 2
        ):
            return None
        rects = self._base14_trace_glyph_rects(trace)
        return rects.get((glyph[0], tuple(glyph[2]))) if rects is not None else None

    def _base14_stroke_is_disjoint(
        self, drawing: dict[str, Any], trace: dict[str, Any],
        glyph: tuple[Any, ...], span_size: Any,
    ) -> bool:
        """Prove vertical separation for a simple horizontal stroke and Base-14 glyph."""
        if (
            trace.get("type") != 0 or trace.get("opacity") != 1 or trace.get("layer")
            or trace.get("wmode") != 0 or trace.get("dir") != (1.0, 0.0)
            or not isinstance(span_size, (int, float)) or not math.isfinite(float(span_size))
            or not isinstance(trace.get("size"), (int, float))
            or abs(float(trace["size"]) - float(span_size)) > 0.001
            or trace.get("_effective_v_size", trace.get("size")) != trace.get("size")
            or not isinstance(glyph, (tuple, list)) or len(glyph) < 4
            or type(glyph[0]) is not int or type(glyph[1]) is not int
            or not isinstance(glyph[2], (tuple, list)) or len(glyph[2]) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in glyph[2])
        ):
            return False
        glyph_box = self._base14_glyph_rect(trace, glyph, span_size)
        if glyph_box is None or not glyph_box.is_valid or glyph_box.is_empty:
            return False

        items = drawing.get("items")
        width = drawing.get("width")
        if (
            drawing.get("type") != "s" or drawing.get("dashes") != "[] 0"
            or not isinstance(items, (tuple, list)) or not items
            or not isinstance(width, (int, float)) or not math.isfinite(float(width)) or float(width) <= 0
        ):
            return False
        stroke_pad = float(width) / 2.0 + 0.05
        cache_key = id(drawing)
        cached_geometry = self.base14_stroke_geometry.get(cache_key)
        if cached_geometry is not None and cached_geometry[0] is drawing:
            stroke_rects, stroke_bounds = cached_geometry[1], cached_geometry[2]
        else:
            rects: list[fitz.Rect] = []
            for item in items:
                if not isinstance(item, (tuple, list)) or not item:
                    return False
                if item[0] == "l" and len(item) == 3 and all(isinstance(point, fitz.Point) for point in item[1:]):
                    left, right = item[1:]
                    rects.append(fitz.Rect(
                        min(left.x, right.x) - stroke_pad,
                        min(left.y, right.y) - stroke_pad,
                        max(left.x, right.x) + stroke_pad,
                        max(left.y, right.y) + stroke_pad,
                    ))
                elif item[0] == "re" and len(item) >= 2 and isinstance(item[1], fitz.Rect):
                    rect = item[1]
                    rects.extend((
                        fitz.Rect(rect.x0 - stroke_pad, rect.y0 - stroke_pad,
                                  rect.x1 + stroke_pad, rect.y0 + stroke_pad),
                        fitz.Rect(rect.x0 - stroke_pad, rect.y1 - stroke_pad,
                                  rect.x1 + stroke_pad, rect.y1 + stroke_pad),
                        fitz.Rect(rect.x0 - stroke_pad, rect.y0 - stroke_pad,
                                  rect.x0 + stroke_pad, rect.y1 + stroke_pad),
                        fitz.Rect(rect.x1 - stroke_pad, rect.y0 - stroke_pad,
                                  rect.x1 + stroke_pad, rect.y1 + stroke_pad),
                    ))
                else:
                    return False
            if not rects:
                return False
            stroke_bounds = fitz.Rect(
                min(rect.x0 for rect in rects), min(rect.y0 for rect in rects),
                max(rect.x1 for rect in rects), max(rect.y1 for rect in rects),
            )
            stroke_rects = tuple(rects)
            self.base14_stroke_geometry[cache_key] = (drawing, stroke_rects, stroke_bounds)
        if (
            stroke_bounds.x1 < glyph_box.x0 - 0.05 or stroke_bounds.x0 > glyph_box.x1 + 0.05
            or stroke_bounds.y1 < glyph_box.y0 - 0.05 or stroke_bounds.y0 > glyph_box.y1 + 0.05
        ):
            return True
        return not any(
            not (
                rect.x1 < glyph_box.x0 - 0.05 or rect.x0 > glyph_box.x1 + 0.05
                or rect.y1 < glyph_box.y0 - 0.05 or rect.y0 > glyph_box.y1 + 0.05
            )
            for rect in stroke_rects
        )

    def _bound_stroke(self, sequence: int, drawing: dict[str, Any]) -> str | None:
        from fontTools.pens.recordingPen import RecordingPen
        from fontTools.svgLib.path import parse_path

        node = self.paths.get(sequence)
        allowed = {"d", "transform", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke",
                   "fill", "stroke-opacity", "opacity"}
        if node is None or not set(node.attrib) <= allowed or drawing.get("type") != "s":
            return None
        if (drawing.get("seqno") != sequence or drawing.get("layer") or drawing.get("closePath")
                or drawing.get("dashes") != "[] 0" or drawing.get("stroke_opacity") != 1
                or tuple(drawing.get("lineCap", ())) != (1, 1, 1) or drawing.get("lineJoin") != 1
                or node.get("stroke-linecap") != "round" or node.get("stroke-linejoin") != "round"
                or node.get("fill") != "none"
                or float(node.get("stroke-opacity", "1")) != 1 or float(node.get("opacity", "1")) != 1):
            return None
        stroke = node.get("stroke", "")
        if not self._color_matches(stroke, drawing.get("color")):
            return None
        a, b, c, d, e, f = self._matrix(node)
        scale = math.hypot(a, b)
        width = float(node.get("stroke-width", "0"))
        if (scale <= 0 or abs(math.hypot(c, d) - scale) > 1e-6 or abs(a * c + b * d) > 1e-6
                or not width > 0 or abs(width * scale - drawing["width"]) > 1e-5):
            return None

        path = self._path_data(node)
        pen = RecordingPen()
        parse_path(path, self._metered_pen(pen))
        transform = fitz.Matrix(a, b, c, d, e, f)
        previous = None
        segments = []
        for command, points in pen.value:
            if command == "moveTo":
                previous = fitz.Point(points[0]) * transform
            elif command == "lineTo" and previous is not None:
                endpoint = fitz.Point(points[0]) * transform
                segments.append((previous, endpoint))
                previous = endpoint
            elif command != "endPath":
                return None
        original = drawing.get("items", ())
        if len(segments) != len(original) or not segments:
            return None
        for segment, (kind, *points) in zip(segments, original):
            if kind != "l" or len(points) != 2 or not all(
                abs(v - original_v) <= 0.002
                for point, expected in zip(segment, points)
                for v, original_v in zip(point, expected)
            ):
                return None
        matrix = " ".join(map(str, (a, b, c, d, e, f)))
        return (f'<path d="{path}" transform="matrix({matrix})" fill="none" stroke="{stroke}" '
                f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')

    def _charge_path_operations(self, count: int = 1) -> None:
        if self.path_operations + count > self._PATH_OPERATION_LIMIT:
            self.preparation_exhausted = True
            raise ValueError("SVG path operation budget exhausted")
        self.path_operations += count

    def _metered_pen(self, output_pen: Any, glyph_set: Any = None) -> Any:
        from fontTools.pens.filterPen import DecomposingFilterPen

        charge = self._charge_path_operations

        class MeteredPen(DecomposingFilterPen):
            def moveTo(self, point):
                charge()
                super().moveTo(point)

            def lineTo(self, point):
                charge()
                super().lineTo(point)

            def curveTo(self, *points):
                charge(max(1, len(points) - 2))
                super().curveTo(*points)

            def qCurveTo(self, *points):
                charge(max(1, len(points) - 1))
                super().qCurveTo(*points)

            def closePath(self):
                charge()
                super().closePath()

            def endPath(self):
                charge()
                super().endPath()

            def addComponent(self, glyph_name, transform):
                charge()
                super().addComponent(glyph_name, transform)

        return MeteredPen(output_pen, glyph_set, skipMissingComponents=False)

    @staticmethod
    def _object_reference(kind: str, value: str) -> int | None:
        if kind != "xref":
            return None
        match = re.fullmatch(r"(\d+) 0 R", value)
        return int(match[1]) if match is not None else None

    def _font_program_reference(self, document: fitz.Document, resource: tuple[Any, ...]) -> int | None:
        if resource[1:3] != ("ttf", "Type0") or resource[5] != "Identity-H" or resource[6] != 0:
            return None
        kind, descendant = document.xref_get_key(resource[0], "DescendantFonts")
        if kind == "xref":
            reference = self._object_reference(kind, descendant)
            if reference is None:
                return None
            descendant = document.xref_object(reference)
        elif kind != "array":
            return None
        descendant_ref = re.fullmatch(r"\s*\[\s*(\d+) 0 R\s*\]\s*", descendant)
        if descendant_ref is None:
            return None
        descendant_xref = int(descendant_ref[1])
        if document.xref_get_key(descendant_xref, "CIDToGIDMap") != ("name", "/Identity"):
            return None
        descriptor = self._object_reference(*document.xref_get_key(descendant_xref, "FontDescriptor"))
        if descriptor is None:
            return None
        # Bind to the exact stream that the pinned extractor would select.
        if any(document.xref_get_key(descriptor, key)[0] != "null" for key in ("FontFile", "FontFile3")):
            return None
        reference = self._object_reference(*document.xref_get_key(descriptor, "FontFile2"))
        return reference if reference is not None and document.xref_is_stream(reference) else None

    def _load_font_program(self, document: fitz.Document, reference: int, font_xref: int) -> bytes | None:
        if reference in self.font_programs:
            return self.font_programs[reference]
        if len(self.font_programs) >= self._FONT_PROGRAM_LIMIT or self.font_bytes >= self._FONT_BYTES_LIMIT:
            self.preparation_exhausted = True
            return None
        self.font_programs[reference] = None
        # Native extraction can allocate before returning. Charge only actual bytes.
        program = document.extract_font(font_xref)[3]
        if not program:
            return None
        if self.font_bytes + len(program) > self._FONT_BYTES_LIMIT:
            self.preparation_exhausted = True
            return None
        self.font_bytes += len(program)
        self.font_programs[reference] = program
        return program

    def _embedded_font(self, name: str) -> Any:
        from io import BytesIO

        from fontTools.ttLib import TTFont

        document = self.page.parent
        if document is None or self.preparation_exhausted:
            return None
        if self.font_resources is None:
            resources = self.page.get_fonts(full=True)
            if len(resources) > self._FONT_ROW_LIMIT:
                self.preparation_exhausted = True
                return None
            self.font_resources = {}
            for resource in resources:
                trace_name = resource[3].split("+", 1)[-1]
                self.font_resources.setdefault(trace_name, []).append(resource)

        references = {}
        for resource in self.font_resources.get(name, ()):
            reference = self._font_program_reference(document, resource)
            if reference is None:
                return None
            references.setdefault(reference, resource[0])
        program = None
        for reference, font_xref in references.items():
            data = self._load_font_program(document, reference, font_xref)
            if data is None or program is not None and data != program:
                return None
            program = data
        return TTFont(BytesIO(program), lazy=True) if program is not None else None

    def _bound_glyph(
        self, trace: dict[str, Any], glyph: tuple[Any, ...], span_size: float, *,
        allow_quarter_turn: bool = False,
    ) -> tuple[Any, str, tuple[float, ...], str, Any, float] | None:
        code, gid, (ox, oy), _ = glyph
        if trace.get("type") != 0 or trace.get("opacity") != 1 or trace.get("layer") or trace.get("wmode") != 0:
            return None
        if not isinstance(gid, int) or gid < 0:
            return None
        candidates = [(node, matrix) for node, matrix in self.glyphs.get((chr(code), gid), ())
                      if abs(matrix[4] - ox) <= 0.001 and abs(matrix[5] - oy) <= 0.001]
        if len(candidates) != 1:
            return None
        node, (a, b, c, d, e, f) = candidates[0]
        if not set(node.attrib) <= {"data-text", self._HREF, "transform", "fill"}:
            return None
        direction = tuple(trace.get("dir", ()))
        if direction == (1.0, 0.0) and b == 0 and c == 0:
            advance, cross = a, -d
        elif allow_quarter_turn and direction in ((0.0, -1.0), (0.0, 1.0)) and a == 0 and d == 0:
            advance, cross = b * direction[1], c * direction[1]
        else:
            return None
        if advance <= 0 or cross <= 0:
            return None
        if abs(advance - trace["size"]) > 0.001 or abs(math.sqrt(advance * cross) - span_size) > 0.001:
            return None
        fill = node.get("fill", "#000000")
        if not self._color_matches(fill, trace.get("color")):
            return None
        definition = self.definitions[node.attrib[self._HREF][1:]]
        if definition.tag != self._SVG_NS + "path" or set(definition.attrib) != {"id", "d"}:
            return None
        font_name = trace["font"]
        if font_name not in self.fonts:
            self.fonts[font_name] = None
            self.fonts[font_name] = self._embedded_font(font_name)
        font = self.fonts[font_name]
        if font is None:
            return None
        units = font["head"].unitsPerEm
        order = font.getGlyphOrder()
        if gid >= len(order) or units <= 0:
            return None
        return font.getGlyphSet(), order[gid], (a, b, c, d, e, f), fill, definition, 1.0 / units

    def _glyph_paths(
        self, trace: dict[str, Any], glyph: tuple[Any, ...], span_size: float,
    ) -> tuple[str, str] | None:
        from fontTools.pens.basePen import NullPen
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.svgLib.path import parse_path

        bound = self._bound_glyph(trace, glyph, span_size)
        if bound is None:
            return None
        glyph_set, name, matrix, fill, definition, unit = bound
        pen = SVGPathPen(glyph_set)
        source_path = self._path_data(definition)
        parse_path(source_path, self._metered_pen(NullPen()))
        metered = self._metered_pen(pen, glyph_set)
        glyph_set[name].draw(TransformPen(metered, (unit, 0, 0, unit, 0, 0)))
        font_path = pen.getCommands()
        if not font_path:
            return None
        transform = " ".join(map(str, matrix))
        return tuple(f'<path d="{path}" transform="matrix({transform})" fill="{fill}"/>'
                     for path in (source_path, font_path))

    def _glyph_control_bounds(
        self, trace: dict[str, Any], glyph: tuple[Any, ...], span_size: float,
    ) -> tuple[float, ...]:
        from fontTools.pens.basePen import BasePen
        from fontTools.pens.boundsPen import ControlBoundsPen
        from fontTools.pens.teePen import TeePen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.svgLib.path import parse_path

        class CubicOutlinePen(BasePen):
            """Normalize quadratic and cubic encodings for outline comparison."""

            def __init__(self) -> None:
                super().__init__(None)
                self.operations = []
                self.start = None

            def _moveTo(self, point):
                self.start = point
                self.operations.append(("move", (point,)))

            def _lineTo(self, point):
                if point != self._getCurrentPoint():
                    self.operations.append(("line", (point,)))

            def _curveToOne(self, *points):
                self.operations.append(("curve", points))

            def _closePath(self):
                self._lineTo(self.start)
                self.operations.append(("close", ()))

            def _endPath(self):
                self.operations.append(("end", ()))

        bound = self._bound_glyph(trace, glyph, span_size, allow_quarter_turn=True)
        if bound is None:
            raise ValueError("Glyph cannot be uniquely bound to the embedded font and SVG")
        glyph_set, name, matrix, _, definition, unit = bound
        svg_outline, font_outline = CubicOutlinePen(), CubicOutlinePen()
        svg_bounds, font_bounds = ControlBoundsPen(None), ControlBoundsPen(None)
        if definition.get("d"):
            path = self._path_data(definition)
            if "A" in path or "a" in path:
                raise ValueError("Arc conversion does not prove complete glyph bounds")
            output = TeePen(svg_outline, TransformPen(svg_bounds, matrix))
            parse_path(path, self._metered_pen(output))
        output = TeePen(font_outline, TransformPen(font_bounds, matrix))
        glyph_set[name].draw(TransformPen(self._metered_pen(output, glyph_set), (unit, 0, 0, unit, 0, 0)))
        svg_ops, font_ops = svg_outline.operations, font_outline.operations
        if not svg_ops and not font_ops:
            return ()  # Both independently bound outlines are empty.
        if (
            svg_bounds.bounds is None or font_bounds.bounds is None
            or len(svg_ops) != len(font_ops)
            or any(
                svg_op != font_op or len(svg_points) != len(font_points)
                or any(
                    not math.isfinite(s) or not math.isfinite(f) or abs(s - f) > 2e-6
                    for svg_point, font_point in zip(svg_points, font_points)
                    for s, f in zip(svg_point, font_point)
                )
                for (svg_op, svg_points), (font_op, font_points) in zip(svg_ops, font_ops)
            )
        ):
            raise ValueError("Glyph outlines disagree")
        svg_box, font_box = svg_bounds.bounds, font_bounds.bounds
        if not all(math.isfinite(value) for value in (*svg_box, *font_box)):
            raise ValueError("Glyph bounds must be finite")
        return (
            min(svg_box[0], font_box[0]), min(svg_box[1], font_box[1]),
            max(svg_box[2], font_box[2]), max(svg_box[3], font_box[3]),
        )

    def _bound_fill_components(
        self, sequence: int, drawing: dict[str, Any], components: list[fitz.Rect],
    ) -> list[tuple[float, ...]] | None:
        from fontTools.pens.recordingPen import RecordingPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.svgLib.path import parse_path

        node = self.paths.get(sequence)
        allowed = {"d", "transform", "fill", "fill-opacity", "fill-rule", "opacity"}
        if node is None or not set(node.attrib) <= allowed or drawing.get("type") != "f":
            return None
        rule = node.get("fill-rule", "nonzero")
        if (
            drawing.get("seqno") != sequence or drawing.get("layer") or drawing.get("fill_opacity") != 1
            or float(node.get("fill-opacity", "1")) != 1 or float(node.get("opacity", "1")) != 1
            or rule not in ("nonzero", "evenodd") or (rule == "evenodd") != drawing.get("even_odd")
            or not self._color_matches(node.get("fill", "#000000"), drawing.get("fill"))
        ):
            return None

        path = self._path_data(node)
        if "A" in path or "a" in path:
            return None
        pen = RecordingPen()
        parse_path(path, self._metered_pen(TransformPen(pen, self._matrix(node))))
        svg_components: list[list[tuple[float, float]]] = []
        for operation, points in pen.value:
            if operation == "moveTo":
                svg_components.append([])
            if not svg_components:
                return None
            svg_components[-1].extend(points)
        if len(svg_components) != len(components):
            return None

        bounds = []
        for points, drawing_box in zip(svg_components, components):
            if not points or not all(math.isfinite(v) for point in points for v in point):
                return None
            xs, ys = zip(*points)
            svg_box = (min(xs), min(ys), max(xs), max(ys))
            if not all(abs(s - d) <= self._FILL_PADDING_PT for s, d in zip(svg_box, drawing_box)):
                return None
            bounds.extend((svg_box, tuple(drawing_box)))
        return bounds or None

    @classmethod
    def _strict_fill_separation(cls, ink: tuple[float, ...], fill: tuple[float, ...]) -> bool:
        padding = cls._FILL_PADDING_PT
        return any(
            left_end + padding < right_start - padding
            for left_end, right_start in (
                (ink[2], fill[0]), (fill[2], ink[0]), (ink[3], fill[1]), (fill[3], ink[1]),
            )
        )

    def separates_dark_fill(
        self, sequence: int, drawing: dict[str, Any], components: list[fitz.Rect],
        trace: dict[str, Any], span_size: Any, *, work_budget: Any = None,
    ) -> bool:
        if not isinstance(span_size, (int, float)) or not math.isfinite(span_size) or span_size <= 0:
            return False
        trace_index = trace.get("_trace_order_idx")
        if type(trace_index) is not int or trace_index < 0:
            return False
        if "_source_character_range" in trace:
            character_range = trace["_source_character_range"]
            aggregate_count = trace.get("_aggregate_trace_char_count")
            chars = trace.get("chars")
            if (
                not isinstance(character_range, (tuple, list)) or len(character_range) != 2
                or type(aggregate_count) is not int or not isinstance(chars, (tuple, list))
            ):
                return False
            start, end = character_range
            if (
                type(start) is not int or type(end) is not int
                or not 0 <= start < end <= aggregate_count or len(chars) != end - start
            ):
                return False
            scope = (start, end)
        elif "_aggregate_trace_char_count" in trace or "_aggregate_trace_bbox" in trace:
            return False
        else:
            scope = None  # Whole-trace proofs are distinct even from a full-length selection.
        trace_key = (trace_index, span_size, scope)
        pair_key = (sequence, *trace_key)
        if pair_key in self.fill_separations:
            return self.fill_separations[pair_key]
        if self.preparation_exhausted or self.fill_attempts >= self._FILL_PAIR_LIMIT:
            return False
        self.fill_attempts += 1
        self.fill_separations[pair_key] = False
        try:
            if not self.export_ready:
                self._prepare_export()
            if sequence not in self.fill_bounds:
                self.fill_bounds[sequence] = None
                self.fill_bounds[sequence] = self._bound_fill_components(sequence, drawing, components)
            fills = self.fill_bounds[sequence]
            if fills is None:
                return False
            if trace_key not in self.ink_bounds:
                self.ink_bounds[trace_key] = None
                base14_bounds = self._base14_trace_glyph_rects(trace)
                if base14_bounds is not None:
                    boxes = [
                        tuple(base14_bounds[(glyph[0], tuple(glyph[2]))])
                        for glyph in trace["chars"]
                        if (glyph[0], tuple(glyph[2])) in base14_bounds
                    ]
                    if len(boxes) != len(trace["chars"]):
                        return False
                else:
                    boxes = [self._glyph_control_bounds(trace, glyph, span_size) for glyph in trace["chars"]]
                self.ink_bounds[trace_key] = [box for box in boxes if box]
            ink = self.ink_bounds[trace_key]
            comparison_budget = work_budget or _GlyphPairWorkBudget(_GlyphPairWorkBudget.DEFAULT_LIMIT)
            if not comparison_budget.reserve(ink, fills):
                return False
            separated = bool(ink) and all(self._strict_fill_separation(glyph_box, fill_box)
                                          for glyph_box in ink for fill_box in fills)
            self.fill_separations[pair_key] = separated
            return separated
        except Exception:
            # Unavailable fill evidence leaves the conservative metric veto in place.
            return False

    def _dark_mask(self, markup: str, bounds: fitz.IRect) -> np.ndarray:
        scale = self._SCALE
        width, height = bounds.width, bounds.height
        image = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="{bounds.x0 / scale} {bounds.y0 / scale} {width / scale} {height / scale}">'
            f'{markup}</svg>'
        )
        with fitz.open(stream=image.encode(), filetype="svg") as document:
            raster = document[0].get_pixmap(colorspace=fitz.csGRAY)
            if raster.width != width or raster.height != height:
                raise ValueError("SVG raster and bounded clip do not match")
            return np.frombuffer(raster.samples, np.uint8).reshape(height, width) < 128

    def overlaps_below_baseline(
        self, sequence: int, drawing: dict[str, Any], trace: dict[str, Any],
        glyph: tuple[Any, ...], span_size: Any, clip: fitz.Rect,
    ) -> bool | None:
        if self._base14_stroke_is_disjoint(drawing, trace, glyph, span_size):
            return False
        if (
            self.preparation_exhausted
            or self.pairs >= self._PAIR_LIMIT
            or not isinstance(span_size, (int, float))
            or not math.isfinite(span_size) or span_size <= 0
        ):
            return None
        self.pairs += 1
        try:
            if not self.export_ready:
                self._prepare_export()
            if not self.paths or not self.page.rect.contains(clip):
                return None
            if sequence not in self.strokes:
                self.strokes[sequence] = None
                self.strokes[sequence] = self._bound_stroke(sequence, drawing)
            stroke = self.strokes[sequence]
            if stroke is None:
                return None
            bounds = (clip * fitz.Matrix(self._SCALE, self._SCALE)).irect
            key = (trace["_trace_order_idx"], glyph[0], glyph[1], tuple(glyph[2]), span_size, tuple(bounds))
            cached = key in self.masks
            pixels = bounds.width * bounds.height
            pair_pixels = pixels * (2 if cached else 3)
            if pixels <= 0 or pair_pixels > self._PAIR_PIXELS or self.pixels + pair_pixels > self._PAGE_PIXELS:
                return None
            self.pixels += pair_pixels
            if not cached:
                self.masks[key] = None
                paths = self._glyph_paths(trace, glyph, span_size)
                bound_mask = None
                if paths is not None:
                    svg_mask = self._dark_mask(paths[0], bounds)
                    if np.array_equal(svg_mask, self._dark_mask(paths[1], bounds)):
                        bound_mask = svg_mask
                self.masks[key] = bound_mask
            glyph_mask = self.masks[key]
            if glyph_mask is None or not np.any(glyph_mask):
                return None
            # The expanded clip covers ink outside nominal metrics; only actual
            # source glyph pixels can trigger a veto for this candidate.
            return bool(np.any(glyph_mask & self._dark_mask(stroke, bounds)))
        except Exception:
            # Absence of a completed proof is distinct from verified separation.
            return None



class _GlyphPairWorkBudget:
    """Bound cumulative Cartesian glyph comparisons and fail closed on exhaustion."""

    DEFAULT_LIMIT = 100_000

    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("Glyph pair work limit must be nonnegative.")
        self.limit = limit
        self.work = 0

    def reserve(self, left: Collection[Any], right: Collection[Any]) -> bool:
        work = len(left) * len(right)
        if self.work + work > self.limit:
            return False
        self.work += work
        return True

def _native_pdf_glyph_source_key(glyph: tuple[Any, ...]) -> tuple[Any, tuple[Any, ...]]:
    return glyph[0], tuple(glyph[2])


def _native_pdf_below_baseline_candidate_overlaps(
    glyph_lookup: dict[tuple[Any, tuple[Any, ...]], list[Any]],
    codepoint: int,
    origin_x: float,
    origin_y: float,
    proof_key_prefix: tuple[Any, ...],
    protected_results: dict[tuple[Any, ...], bool],
    *,
    span_font_size: Any,
    clip: fitz.Rect,
    deferred_fills: list[bool] | None,
    proof: Any,
) -> bool:
    matches = glyph_lookup.get((codepoint, (origin_x, origin_y)), [])
    if len(matches) != 1:
        return deferred_fills is None
    glyph = matches[0]
    proof_key = proof_key_prefix + (
        glyph[0], glyph[1], tuple(glyph[2]), span_font_size, tuple(clip),
    )
    if deferred_fills is None:
        return protected_results.get(proof_key) is not False
    decision = proof(glyph)
    if decision is not None:
        protected_results[proof_key] = decision
    # An unavailable pixel proof cannot clear a metric-box contact veto.
    return decision is not False


def _native_pdf_text_span_records(
    source_page: fitz.Page,
    page_number: int,
    source_sha256: str,
    render_sha256: str,
    render_width: int,
    render_height: int,
    transform: str,
) -> list[dict[str, Any]]:
    """Map native PDF spans into the reviewed page frame without approving them."""
    displayed = source_page.rect
    if source_page.get_text("text").strip() and (
        source_page.rotation != 0
        or any(abs(float(left) - float(right)) > 1e-6 for left, right in zip(source_page.cropbox, source_page.mediabox))
        or any(abs(float(left) - float(right)) > 1e-6 for left, right in zip(source_page.cropbox, displayed))
        or transform != "displayed-page-box-v1"
        or render_width <= 0
        or render_height <= 0
    ):
        raise FidelityError("Unsupported native PDF text mapping frame.")
    if not source_page.get_text("text").strip():
        return []

    def b041_aigdt_glyph_observation(
        content: str, span_font: Any, trace: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Decode only B041's exact embedded AIGDT diameter glyph as an observation."""
        if content != "n" or span_font not in ("AIGDT", "ADSINV+AIGDT"):
            return None
        chars = trace.get("chars")
        if not isinstance(chars, (tuple, list)) or len(chars) != 1:
            return None
        char = chars[0]
        if not isinstance(char, (tuple, list)) or len(char) < 2 or char[0] != ord("n") or char[1] != 80:
            return None
        document = source_page.parent
        if document is None:
            return None
        try:
            from fontTools.ttLib import TTFont
            from io import BytesIO

            matches: list[tuple[int, bytes]] = []
            for resource in source_page.get_fonts(full=True):
                if len(resource) < 5 or resource[3] != "ADSINV+AIGDT" or resource[4] != "F5":
                    continue
                extracted = document.extract_font(resource[0])
                if len(extracted) == 4 and isinstance(extracted[3], bytes):
                    font_bytes = extracted[3]
                    if hashlib.sha256(font_bytes).hexdigest() == "aac3c6c7451139928755b08a4bc193a63ed93b51df58ed2fdd559c450696029b":
                        matches.append((resource[0], font_bytes))
            if len(matches) != 1:
                return None
            font_xref, font_bytes = matches[0]
            font = TTFont(BytesIO(font_bytes), lazy=False)
            glyph_order = font.getGlyphOrder()
            if len(glyph_order) <= 80 or glyph_order[80] != "uniF06E":
                return None
            cmap_matches = [
                table for table in font["cmap"].tables
                if table.platformID == 3 and table.platEncID == 0 and table.format == 4
                and table.cmap.get(0xF06E) == "uniF06E"
            ]
            if len(cmap_matches) != 1:
                return None
            return {
                "content": "\u2300",
                "source_text_raw": content,
                "source_font_resource": {
                    "xref": font_xref,
                    "resource_name": "F5",
                    "base_font": "ADSINV+AIGDT",
                },
                "source_font_file_sha256": "aac3c6c7451139928755b08a4bc193a63ed93b51df58ed2fdd559c450696029b",
                "source_glyph_id": 80,
                "source_glyph_name": "uniF06E",
                "source_cmap_codepoint": 0xF06E,
            }
        except (ImportError, AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError):
            return None

    try:
        paint_traces = source_page.get_texttrace()
        paint_log = source_page.get_bboxlog()
    except (AttributeError, RuntimeError, ValueError):
        # Native text is selectable only when the PDF backend can establish
        # that the extracted span has a corresponding visible paint operation.
        return []
    if not isinstance(paint_traces, (list, tuple)) or not isinstance(paint_log, (list, tuple)):
        return []

    def compact_text(value: str) -> str:
        return "".join(value.split())

    def trace_text_agreement(span_text: str, trace_text: str) -> str | None:
        span_compact = compact_text(span_text)
        trace_compact = compact_text(trace_text)
        if span_compact == trace_compact:
            return "exact"
        if "\ufffd" not in span_compact or len(span_compact) != len(trace_compact):
            return None
        if any(
            source_char != "\ufffd" and source_char != trace_char
            for source_char, trace_char in zip(span_compact, trace_compact)
        ):
            return None
        if any(
            source_char == "\ufffd" and (not trace_char.isprintable() or trace_char == "\ufffd")
            for source_char, trace_char in zip(span_compact, trace_compact)
        ):
            return None
        return "trace_recovered_replacement_characters"

    def overlap_ratio(left: fitz.Rect, right: fitz.Rect) -> float:
        intersection = left & right
        if intersection.is_empty:
            return 0.0
        smaller_area = min(left.get_area(), right.get_area())
        return intersection.get_area() / smaller_area if smaller_area > 0 else 0.0

    def exact_source_span_trace_range(
        span: dict[str, Any], span_rect: fitz.Rect, line_direction: Any,
        trace: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Narrow an aggregate paint trace only when source text and glyph geometry bind uniquely."""
        content = span.get("text")
        origin = span.get("origin")
        span_font = span.get("font")
        span_size = span.get("size")
        chars = trace.get("chars")
        trace_font = trace.get("font")
        trace_size = trace.get("size")
        trace_direction = trace.get("dir")
        trace_bbox = trace.get("bbox")
        sequence_number = trace.get("seqno")
        if (
            not isinstance(content, str) or not content or "\ufffd" in content
            or not isinstance(origin, (tuple, list)) or len(origin) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in origin)
            or not isinstance(span_font, str) or trace_font != span_font
            or not isinstance(span_size, (int, float)) or not math.isfinite(float(span_size)) or span_size <= 0
            or not isinstance(trace_size, (int, float)) or not math.isfinite(float(trace_size)) or float(trace_size) <= 0
            or not (0.5 <= float(span_size) / float(trace_size) <= 2.0)
            or not isinstance(line_direction, (tuple, list)) or len(line_direction) != 2
            or not isinstance(trace_direction, (tuple, list)) or len(trace_direction) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in line_direction)
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in trace_direction)
            or math.dist(tuple(float(value) for value in line_direction), tuple(float(value) for value in trace_direction)) > 0.001
            or not isinstance(chars, (tuple, list)) or not chars
            or type(sequence_number) is not int
            or not isinstance(trace_bbox, (tuple, list)) or len(trace_bbox) != 4
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in trace_bbox)
            or float(trace_bbox[2]) <= span_rect.x0
            or float(trace_bbox[0]) >= span_rect.x1
            or float(trace_bbox[3]) <= span_rect.y0
            or float(trace_bbox[1]) >= span_rect.y1
        ):
            return None

        trace_codepoints: list[int] = []
        for char in chars:
            if (
                not isinstance(char, (tuple, list)) or len(char) < 4
                or type(char[0]) is not int or not 0 <= char[0] <= 0x10FFFF
                or not isinstance(char[2], (tuple, list)) or len(char[2]) != 2
                or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in char[2])
                or not isinstance(char[3], (tuple, list)) or len(char[3]) != 4
                or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in char[3])
            ):
                return None
            trace_codepoints.append(char[0])

        source_codepoints = [ord(character) for character in content]
        if not source_codepoints or len(source_codepoints) > len(trace_codepoints):
            return None
        matches: list[tuple[int, fitz.Rect]] = []
        for start in range(len(trace_codepoints) - len(source_codepoints) + 1):
            end = start + len(source_codepoints)
            if trace_codepoints[start:end] != source_codepoints:
                continue
            first_origin = chars[start][2]
            if math.dist(tuple(float(value) for value in origin), tuple(float(value) for value in first_origin)) > 0.35:
                continue
            selected_chars = chars[start:end]
            selected_bbox = fitz.Rect(
                min(float(char[3][0]) for char in selected_chars),
                min(float(char[3][1]) for char in selected_chars),
                max(float(char[3][2]) for char in selected_chars),
                max(float(char[3][3]) for char in selected_chars),
            )
            if (
                selected_bbox.is_empty or not selected_bbox.is_valid
                or overlap_ratio(span_rect, selected_bbox) < 0.99
            ):
                continue
            matches.append((start, selected_bbox))
        if len(matches) != 1:
            return None

        start, selected_bbox = matches[0]
        end = start + len(source_codepoints)
        narrowed = dict(trace)
        narrowed["chars"] = list(chars[start:end])
        narrowed["bbox"] = tuple(float(value) for value in selected_bbox)
        narrowed["_source_character_range"] = (start, end)
        narrowed["_aggregate_trace_char_count"] = len(chars)
        narrowed["_aggregate_trace_bbox"] = tuple(float(value) for value in trace_bbox)
        narrowed["_later_intra_trace_chars"] = list(chars[end:])
        return narrowed

    indexed_paint_traces: list[dict[str, Any]] = []
    traces_by_sequence: dict[int, list[dict[str, Any]]] = {}
    for trace_order_idx, raw_trace in enumerate(paint_traces):
        if isinstance(raw_trace, dict):
            tagged_trace = dict(raw_trace)
            tagged_trace["_trace_order_idx"] = trace_order_idx
            indexed_paint_traces.append(tagged_trace)
            if type(tagged_trace.get("seqno")) is int:
                traces_by_sequence.setdefault(tagged_trace["seqno"], []).append(tagged_trace)
    paint_traces = indexed_paint_traces

    try:
        raw_drawings = source_page.get_drawings()
    except (AttributeError, RuntimeError, ValueError, TypeError):
        raw_drawings = ()
    drawings_by_sequence: dict[int, list[dict[str, Any]]] = {}
    if isinstance(raw_drawings, (list, tuple)):
        for drawing in raw_drawings:
            if isinstance(drawing, dict) and type(drawing.get("seqno")) is int:
                d_seq = drawing["seqno"]
                drawings_by_sequence.setdefault(d_seq, []).append(drawing)
                if drawing.get("type") == "fs":
                    drawings_by_sequence.setdefault(d_seq + 1, []).append(drawing)

    below_baseline_ink_glyphs = frozenset("fgjpqyQJ$,;()[]{}_|@#&§µçşğı")
    deep_descender_glyphs = frozenset("gjpqyQ$,;")
    baseline_punct_glyphs = frozenset(".:/\\=")
    narrow_advance_glyphs = frozenset(".,:;!'\"|ilI1()[]{}-/\\` ")

    def stroke_color_is_dark_visible(color: Any) -> bool:
        if not isinstance(color, (tuple, list)) or len(color) not in (1, 3, 4):
            return False
        if not all(isinstance(v, (int, float)) and math.isfinite(float(v)) and 0.0 <= float(v) <= 1.0 for v in color):
            return False
        if len(color) == 1:
            r = g = b = float(color[0])
        elif len(color) == 3:
            r, g, b = float(color[0]), float(color[1]), float(color[2])
        else:
            c, m, y, k = (float(v) for v in color)
            r = (1.0 - c) * (1.0 - k)
            g = (1.0 - m) * (1.0 - k)
            b = (1.0 - y) * (1.0 - k)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) <= 0.35

    glyph_entries_cache: dict[tuple[int, bool], tuple[Any, list[tuple[int, tuple[float, float], fitz.Rect]]]] = {}

    def glyph_entries_from_chars(
        chars: Any,
        *,
        skip_spaces: bool = True,
    ) -> list[tuple[int, tuple[float, float], fitz.Rect]] | None:
        if not isinstance(chars, (tuple, list)) or not chars:
            return None
        cache_key = (id(chars), skip_spaces)
        cached = glyph_entries_cache.get(cache_key)
        if cached is not None and cached[0] is chars:
            return cached[1]
        entries: list[tuple[int, tuple[float, float], fitz.Rect]] = []
        for char in chars:
            if (
                not isinstance(char, (tuple, list)) or len(char) < 4
                or type(char[0]) is not int or not 0 <= char[0] <= 0x10FFFF
                or not isinstance(char[2], (tuple, list)) or len(char[2]) != 2
                or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in char[2])
                or not isinstance(char[3], (tuple, list)) or len(char[3]) != 4
                or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in char[3])
            ):
                return None
            if skip_spaces and chr(char[0]).isspace():
                continue
            grect = fitz.Rect(char[3])
            if grect.is_empty or not grect.is_valid:
                # A whitespace codepoint may be a visible glyph remapped by /ToUnicode.
                # Without nonempty bounds it cannot prove an intersecting fill is harmless.
                return None
            entries.append((char[0], (float(char[2][0]), float(char[2][1])), grect))
        glyph_entries_cache[cache_key] = (chars, entries)
        return entries

    def nonspace_glyph_entries_from_chars(
        chars: Any,
    ) -> list[tuple[int, tuple[float, float], fitz.Rect]] | None:
        return glyph_entries_from_chars(chars, skip_spaces=True)

    def nonspace_glyph_entries(
        candidate_trace: dict[str, Any],
    ) -> list[tuple[int, tuple[float, float], fitz.Rect]] | None:
        return glyph_entries_from_chars(candidate_trace.get("chars"), skip_spaces=True)

    def expand_glyph_rect_for_condensation(
        origin_pt: tuple[float, float],
        grect: fitz.Rect,
        ux: float,
        uy: float,
        vx: float,
        vy: float,
        v_scale: float,
    ) -> fitz.Rect:
        if abs(v_scale - 1.0) <= 1e-3:
            return grect
        ox, oy = origin_pt
        corners = ((grect.x0, grect.y0), (grect.x1, grect.y0), (grect.x1, grect.y1), (grect.x0, grect.y1))
        us = [(cx - ox) * ux + (cy - oy) * uy for cx, cy in corners]
        vs = [((cx - ox) * vx + (cy - oy) * vy) * v_scale for cx, cy in corners]
        u0, u1 = min(us), max(us)
        v0, v1 = min(vs), max(vs)
        mapped = [
            (ox + u_c * ux + v_c * vx, oy + u_c * uy + v_c * vy)
            for u_c in (u0, u1)
            for v_c in (v0, v1)
        ]
        return fitz.Rect(
            min(px for px, _ in mapped),
            min(py for _, py in mapped),
            max(px for px, _ in mapped),
            max(py for _, py in mapped),
        )

    source_text_blocks = source_page.get_text("dict").get("blocks", [])
    try:
        occluder_text_blocks = source_page.get_text("dict", flags=0).get("blocks", [])
    except TypeError:
        occluder_text_blocks = source_text_blocks

    dict_span_candidates: list[tuple[str | None, float, float, float, float, float, fitz.Rect]] = []
    for blk in occluder_text_blocks:
        if not isinstance(blk, dict):
            continue
        for ln in blk.get("lines", []):
            if not isinstance(ln, dict) or ln.get("wmode") != 0:
                continue
            ldir = ln.get("dir", (1.0, 0.0))
            if (
                not isinstance(ldir, (tuple, list)) or len(ldir) != 2
                or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in ldir)
            ):
                continue
            ldn = math.hypot(float(ldir[0]), float(ldir[1]))
            if ldn <= 1e-6:
                continue
            lux, luy = float(ldir[0]) / ldn, float(ldir[1]) / ldn
            for sp in ln.get("spans", []):
                if not isinstance(sp, dict):
                    continue
                sp_sz = sp.get("size")
                sp_bb = sp.get("bbox")
                sp_org = sp.get("origin")
                if (
                    not isinstance(sp_sz, (int, float)) or not math.isfinite(float(sp_sz)) or float(sp_sz) <= 0.0
                    or not isinstance(sp_bb, (tuple, list)) or len(sp_bb) != 4
                    or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in sp_bb)
                    or not isinstance(sp_org, (tuple, list)) or len(sp_org) != 2
                    or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in sp_org)
                ):
                    continue
                sp_r = fitz.Rect(sp_bb)
                if sp_r.is_empty or not sp_r.is_valid:
                    continue
                sp_f = sp.get("font") if isinstance(sp.get("font"), str) else None
                dict_span_candidates.append((sp_f, lux, luy, float(sp_sz), float(sp_org[0]), float(sp_org[1]), sp_r))

    for tr in paint_traces:
        tr_bb = tr.get("bbox")
        tr_sz = tr.get("size")
        tr_dir = tr.get("dir", (1.0, 0.0))
        if (
            tr.get("type") != 0
            or tr.get("wmode") != 0
            or not isinstance(tr_bb, (tuple, list)) or len(tr_bb) != 4
            or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in tr_bb)
            or not isinstance(tr_sz, (int, float)) or not math.isfinite(float(tr_sz)) or float(tr_sz) <= 0.0
            or not isinstance(tr_dir, (tuple, list)) or len(tr_dir) != 2
            or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in tr_dir)
        ):
            continue
        tdn = math.hypot(float(tr_dir[0]), float(tr_dir[1]))
        if tdn <= 1e-6:
            continue
        tux, tuy = float(tr_dir[0]) / tdn, float(tr_dir[1]) / tdn
        tvx, tvy = tuy, -tux
        tr_r = fitz.Rect(tr_bb)
        if not tr_r.is_valid:
            continue
        tr_sz_f = float(tr_sz)
        raw_gl = glyph_entries_from_chars(tr.get("chars"), skip_spaces=False)
        if raw_gl is None:
            continue
        if not raw_gl:
            tr["_occluder_bbox"] = tr_r
            tr["_occluder_glyphs"] = []
            tr["_occluder_v_expanded"] = False
            tr["_effective_v_size"] = tr_sz_f
            continue
        tr_f = tr.get("font") if isinstance(tr.get("font"), str) else None
        matched_max_sp_sz = 0.0
        for sp_f, lux, luy, sp_sz_f, sox, soy, sp_r in dict_span_candidates:
            if sp_f != tr_f or math.dist((tux, tuy), (lux, luy)) > 1e-2 or (tr_r & sp_r).is_empty:
                continue
            v_tol = max(0.75, 0.20 * max(tr_sz_f, sp_sz_f))
            if any(
                abs((sox - cox) * tvx + (soy - coy) * tvy) <= v_tol and overlap_ratio(cgr, sp_r) >= 0.75
                for _cp, (cox, coy), cgr in raw_gl
            ):
                if sp_sz_f > matched_max_sp_sz:
                    matched_max_sp_sz = sp_sz_f
        if matched_max_sp_sz > tr_sz_f * 1.005:
            eff_v = min(tr_sz_f * 1024.0, (matched_max_sp_sz * matched_max_sp_sz) / tr_sz_f)
            v_sc = eff_v / tr_sz_f
            exp_gl = [
                (cp, org, expand_glyph_rect_for_condensation(org, cgr, tux, tuy, tvx, tvy, v_sc))
                for cp, org, cgr in raw_gl
            ]
            occ_r = fitz.Rect(
                min([tr_r.x0] + [gr.x0 for _c, _o, gr in exp_gl]),
                min([tr_r.y0] + [gr.y0 for _c, _o, gr in exp_gl]),
                max([tr_r.x1] + [gr.x1 for _c, _o, gr in exp_gl]),
                max([tr_r.y1] + [gr.y1 for _c, _o, gr in exp_gl]),
            )
            tr["_occluder_bbox"] = occ_r
            tr["_occluder_glyphs"] = exp_gl
            tr["_occluder_v_expanded"] = True
            tr["_effective_v_size"] = eff_v
        else:
            tr["_occluder_bbox"] = tr_r
            tr["_occluder_glyphs"] = raw_gl
            tr["_occluder_v_expanded"] = False
            tr["_effective_v_size"] = tr_sz_f

    glyph_pair_work_limit = _GlyphPairWorkBudget.DEFAULT_LIMIT

    def has_valid_glyph_progression(
        ordered_traces: list[dict[str, Any]],
        line_dir: Any,
        span_font_size: Any,
    ) -> bool:
        if (
            not isinstance(line_dir, (tuple, list)) or len(line_dir) != 2
            or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in line_dir)
        ):
            return False
        dn = math.hypot(float(line_dir[0]), float(line_dir[1]))
        if dn <= 1e-6:
            return False
        ux, uy = float(line_dir[0]) / dn, float(line_dir[1]) / dn
        vx, vy = uy, -ux
        abs_ux, abs_uy = abs(ux), abs(uy)
        two_ux_uy = 2.0 * abs(ux * uy)
        sp_sz = float(span_font_size) if isinstance(span_font_size, (int, float)) and math.isfinite(float(span_font_size)) and float(span_font_size) > 0 else 0.0
        ordered_glyphs: list[tuple[int, tuple[float, float], fitz.Rect, float]] = []
        for mt in ordered_traces:
            mt_size = mt.get("size")
            if not isinstance(mt_size, (int, float)) or not math.isfinite(float(mt_size)) or float(mt_size) <= 0:
                return False
            entries = nonspace_glyph_entries(mt)
            if entries is None:
                return False
            for cp, org, gr in entries:
                ordered_glyphs.append((cp, org, gr, float(mt_size)))
        if len(ordered_glyphs) * max(0, len(ordered_glyphs) - 1) // 2 > glyph_pair_work_limit:
            return False
        for idx_a in range(len(ordered_glyphs)):
            cp_a, (ox_a, oy_a), gr_a, sz_a = ordered_glyphs[idx_a]
            adv_a = max(0.0, (gr_a.width * abs_ux + gr_a.height * abs_uy) - sz_a * two_ux_uy)
            for idx_b in range(idx_a + 1, len(ordered_glyphs)):
                _cp_b, (ox_b, oy_b), gr_b, sz_b = ordered_glyphs[idx_b]
                du = (ox_b - ox_a) * ux + (oy_b - oy_a) * uy
                dv = abs((ox_b - ox_a) * vx + (oy_b - oy_a) * vy)
                u_em = min(sz_a, sz_b)
                eff_v = max(sz_a, sz_b, (sp_sz * sp_sz) / u_em if sp_sz > 0 and u_em > 0 else sz_a)
                if dv > 0.15 * eff_v:
                    return False
                min_du = (0.16 if chr(cp_a) in narrow_advance_glyphs else 0.27) * u_em
                if du < min_du:
                    return False
                adv_b = max(0.0, (gr_b.width * abs_ux + gr_b.height * abs_uy) - sz_b * two_ux_uy)
                min_adv = min(adv_a, adv_b)
                if min_adv > 1e-6:
                    ov_u = max(0.0, min(adv_a, du + adv_b) - max(0.0, du)) / min_adv
                    if ov_u > 0.18:
                        return False
        return True

    def protected_stroke_glyph_rect(
        cp: int, origin_pt: tuple[float, float], grect: fitz.Rect, trace_dir: tuple[float, float],
    ) -> fitz.Rect:
        """Reproduce stroke eligibility only. This rectangle does not clear a fill."""
        if chr(cp) in below_baseline_ink_glyphs or cp >= 0x80:
            return grect
        ox, oy = origin_pt
        dx, dy = trace_dir
        if abs(dx - 1.0) <= 1e-3 and abs(dy) <= 1e-3 and grect.y0 < oy < grect.y1:
            return fitz.Rect(grect.x0, grect.y0, grect.x1, oy)
        if abs(dx) <= 1e-3 and abs(dy + 1.0) <= 1e-3 and grect.x0 < ox < grect.x1:
            return fitz.Rect(grect.x0, grect.y0, ox, grect.y1)
        if abs(dx) <= 1e-3 and abs(dy - 1.0) <= 1e-3 and grect.x0 < ox < grect.x1:
            return fitz.Rect(ox, grect.y0, grect.x1, grect.y1)
        return grect

    def extract_fill_subpath_rects(drawing: dict[str, Any]) -> list[fitz.Rect] | None:
        items = drawing.get("items")
        if not isinstance(items, (tuple, list)) or not items:
            return None
        sub_rects: list[fitz.Rect] = []
        cur_pts: list[tuple[float, float]] = []
        last_pt: tuple[float, float] | None = None

        def flush_subpath() -> None:
            nonlocal cur_pts
            if cur_pts:
                xs = [pt[0] for pt in cur_pts]
                ys = [pt[1] for pt in cur_pts]
                sub_rects.append(fitz.Rect(min(xs), min(ys), max(xs), max(ys)))
                cur_pts = []

        for item in items:
            if not isinstance(item, (tuple, list)) or not item:
                return None
            op = item[0]
            if op == "re" and len(item) >= 2:
                flush_subpath()
                r = fitz.Rect(item[1])
                if not r.is_valid:
                    return None
                sub_rects.append(r)
                last_pt = None
            elif op == "qu" and len(item) >= 2:
                flush_subpath()
                q = item[1]
                qpts = [(float(p.x), float(p.y)) for p in (q.ul, q.ur, q.lr, q.ll)]
                if not all(math.isfinite(px) and math.isfinite(py) for px, py in qpts):
                    return None
                sub_rects.append(fitz.Rect(
                    min(px for px, _ in qpts), min(py for _, py in qpts),
                    max(px for px, _ in qpts), max(py for _, py in qpts),
                ))
                last_pt = None
            elif op in ("l", "c") and len(item) >= (3 if op == "l" else 5):
                pts = [(float(p.x), float(p.y)) for p in item[1:]]
                if not all(math.isfinite(px) and math.isfinite(py) for px, py in pts):
                    return None
                if last_pt is None or abs(pts[0][0] - last_pt[0]) > 1e-3 or abs(pts[0][1] - last_pt[1]) > 1e-3:
                    flush_subpath()
                cur_pts.extend(pts)
                last_pt = pts[-1]
            else:
                return None
        flush_subpath()
        return sub_rects or None

    def extract_stroke_segments(
        drawing: dict[str, Any],
    ) -> tuple[
        list[tuple[float, float, float, float, tuple[float, float], tuple[float, float], float]],
        fitz.Rect,
        fitz.Rect,
        float,
        bool,
        int,
    ] | None:
        items = drawing.get("items")
        if not isinstance(items, (tuple, list)) or not items:
            return None
        raw_w = drawing.get("width")
        if raw_w is None:
            width = 0.0
        elif isinstance(raw_w, (int, float)) and math.isfinite(float(raw_w)) and float(raw_w) >= 0.0:
            width = float(raw_w)
        else:
            return None
        raw_join = drawing.get("lineJoin", 0)
        line_join = int(raw_join) if isinstance(raw_join, (int, float)) and math.isfinite(float(raw_join)) else 0
        raw_cap = drawing.get("lineCap", 0)
        if isinstance(raw_cap, (tuple, list)):
            if not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in raw_cap):
                return None
            has_proj_cap = any(int(v) == 2 for v in raw_cap)
        elif isinstance(raw_cap, (int, float)) and math.isfinite(float(raw_cap)):
            has_proj_cap = int(raw_cap) == 2
        else:
            return None
        half = 0.5 * width
        proj_cap_pad = ((math.sqrt(2.0) - 1.0) * half) if has_proj_cap else 0.0
        segs: list[tuple[float, float, float, float, tuple[float, float], tuple[float, float], float]] = []
        all_xs: list[float] = []
        all_ys: list[float] = []
        has_diagonal = False
        prev_seg_pts: tuple[tuple[float, float], tuple[float, float]] | None = None
        subpath_first_seg: tuple[tuple[float, float], tuple[float, float]] | None = None
        subpath_just_closed = False

        def emit_miter_join(
            in_seg: tuple[tuple[float, float], tuple[float, float]],
            out_seg: tuple[tuple[float, float], tuple[float, float]],
        ) -> None:
            q0, q1 = in_seg
            r0, r1 = out_seg
            if abs(r0[0] - q1[0]) > 1e-3 or abs(r0[1] - q1[1]) > 1e-3:
                return
            l_in = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
            l_out = math.hypot(r1[0] - r0[0], r1[1] - r0[1])
            if l_in <= 1e-6 or l_out <= 1e-6:
                return
            uin_x, uin_y = (q1[0] - q0[0]) / l_in, (q1[1] - q0[1]) / l_in
            uout_x, uout_y = (r1[0] - r0[0]) / l_out, (r1[1] - r0[1]) / l_out
            dot = max(-1.0, min(1.0, uin_x * uout_x + uin_y * uout_y))
            if dot < -0.2:
                sin_half = math.sqrt(max(0.0, 0.5 * (1.0 + dot)))
                if sin_half > 1e-4 and (1.0 / sin_half) <= 10.05:
                    bx, by = uin_x - uout_x, uin_y - uout_y
                    bn = math.hypot(bx, by)
                    if bn > 1e-6:
                        miter_len = half / sin_half
                        tip = (q1[0] + (bx / bn) * miter_len, q1[1] + (by / bn) * miter_len)
                        segs.append((
                            min(q1[0], tip[0]) - half,
                            min(q1[1], tip[1]) - half,
                            max(q1[0], tip[0]) + half,
                            max(q1[1], tip[1]) + half,
                            q1,
                            tip,
                            0.0,
                        ))

        def add_seg(p1: tuple[float, float], p2: tuple[float, float], pad: float = 0.0, track_join: bool = False) -> bool:
            nonlocal has_diagonal, prev_seg_pts, subpath_first_seg, subpath_just_closed
            if not (math.isfinite(p1[0]) and math.isfinite(p1[1]) and math.isfinite(p2[0]) and math.isfinite(p2[1])):
                return False
            dx_s, dy_s = p2[0] - p1[0], p2[1] - p1[1]
            if abs(dx_s) > 1e-4 and abs(dy_s) > 1e-4:
                has_diagonal = True
            eff_pad = pad + proj_cap_pad
            h_pad = half + eff_pad
            segs.append((
                min(p1[0], p2[0]) - h_pad,
                min(p1[1], p2[1]) - h_pad,
                max(p1[0], p2[0]) + h_pad,
                max(p1[1], p2[1]) + h_pad,
                p1,
                p2,
                eff_pad,
            ))
            all_xs.extend((p1[0], p2[0]))
            all_ys.extend((p1[1], p2[1]))
            if track_join:
                if math.hypot(dx_s, dy_s) > 1e-6:
                    if (
                        prev_seg_pts is not None
                        and abs(p1[0] - prev_seg_pts[1][0]) <= 1e-3
                        and abs(p1[1] - prev_seg_pts[1][1]) <= 1e-3
                    ):
                        if line_join == 0 and half > 0.0:
                            emit_miter_join(prev_seg_pts, (p1, p2))
                        if subpath_just_closed:
                            subpath_first_seg = (p1, p2)
                            subpath_just_closed = False
                        elif (
                            subpath_first_seg is not None
                            and abs(p2[0] - subpath_first_seg[0][0]) <= 1e-3
                            and abs(p2[1] - subpath_first_seg[0][1]) <= 1e-3
                        ):
                            if line_join == 0 and half > 0.0:
                                emit_miter_join((p1, p2), subpath_first_seg)
                            subpath_just_closed = True
                    else:
                        subpath_first_seg = (p1, p2)
                        subpath_just_closed = False
                    prev_seg_pts = (p1, p2)
            else:
                prev_seg_pts = None
                subpath_first_seg = None
                subpath_just_closed = False
            return True

        for item in items:
            if not isinstance(item, (tuple, list)) or not item:
                return None
            op = item[0]
            if op == "l" and len(item) >= 3:
                if not add_seg((float(item[1].x), float(item[1].y)), (float(item[2].x), float(item[2].y)), 0.0, True):
                    return None
            elif op == "re" and len(item) >= 2:
                prev_seg_pts = None
                subpath_first_seg = None
                subpath_just_closed = False
                r = fitz.Rect(item[1])
                if not r.is_valid:
                    return None
                cs = ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1))
                for idx_c in range(4):
                    if not add_seg(cs[idx_c], cs[(idx_c + 1) % 4]):
                        return None
            elif op == "qu" and len(item) >= 2:
                prev_seg_pts = None
                subpath_first_seg = None
                subpath_just_closed = False
                q = item[1]
                cs_q = [(float(p.x), float(p.y)) for p in (q.ul, q.ll, q.lr, q.ur)]
                for idx_c in range(4):
                    if not add_seg(cs_q[idx_c], cs_q[(idx_c + 1) % 4], 0.0, True):
                        return None
                prev_seg_pts = None
                subpath_first_seg = None
                subpath_just_closed = False
            elif op == "c" and len(item) >= 5:
                p0, p1, p2, p3 = ((float(p.x), float(p.y)) for p in item[1:5])
                if not all(math.isfinite(px) and math.isfinite(py) for px, py in (p0, p1, p2, p3)):
                    return None
                all_xs.extend((p0[0], p1[0], p2[0], p3[0]))
                all_ys.extend((p0[1], p1[1], p2[1], p3[1]))
                has_diagonal = True
                d2a = math.hypot(p0[0] - 2.0 * p1[0] + p2[0], p0[1] - 2.0 * p1[1] + p2[1])
                d2b = math.hypot(p1[0] - 2.0 * p2[0] + p3[0], p1[1] - 2.0 * p2[1] + p3[1])
                bulge_pad = (3.0 / 256.0) * max(d2a, d2b)
                prev = p0
                for step in range(1, 9):
                    t = step / 8.0
                    mt = 1.0 - t
                    cur = (
                        mt**3 * p0[0] + 3.0 * mt**2 * t * p1[0] + 3.0 * mt * t**2 * p2[0] + t**3 * p3[0],
                        mt**3 * p0[1] + 3.0 * mt**2 * t * p1[1] + 3.0 * mt * t**2 * p2[1] + t**3 * p3[1],
                    )
                    if not add_seg(prev, cur, bulge_pad, True):
                        return None
                    prev = cur
            else:
                return None
        if not segs:
            return None
        raw_bounds = fitz.Rect(min(all_xs), min(all_ys), max(all_xs), max(all_ys))
        bounds = fitz.Rect(
            min(s[0] for s in segs),
            min(s[1] for s in segs),
            max(s[2] for s in segs),
            max(s[3] for s in segs),
        )
        return segs, raw_bounds, bounds, width, has_diagonal, line_join

    def is_safe_adjacent_text_overlap(left_trace: dict[str, Any], right_trace: dict[str, Any]) -> bool:
        """Ignore only a tiny shared glyph edge between matching same-baseline text paints."""
        def finite_pair(value: Any) -> bool:
            return (
                isinstance(value, (tuple, list)) and len(value) == 2
                and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)
            )

        def finite_quad(value: Any) -> bool:
            return (
                isinstance(value, (tuple, list)) and len(value) == 4
                and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)
            )

        left_chars = left_trace.get("chars")
        right_chars = right_trace.get("chars")
        left_bbox = left_trace.get("bbox")
        right_bbox = right_trace.get("bbox")
        if (
            not isinstance(left_chars, (tuple, list)) or not left_chars
            or not isinstance(right_chars, (tuple, list)) or not right_chars
            or not finite_quad(left_bbox) or not finite_quad(right_bbox)
            or left_trace.get("wmode") != 0 or right_trace.get("wmode") != 0
            or left_trace.get("type") != 0
            or right_trace.get("type") != 0
            or left_trace.get("font") != right_trace.get("font")
            or left_trace.get("layer") != right_trace.get("layer")
            or left_trace.get("colorspace") != right_trace.get("colorspace")
            or left_trace.get("color") != right_trace.get("color")
            or left_trace.get("opacity") != right_trace.get("opacity")
            or not isinstance(left_trace.get("opacity"), (int, float))
            or not math.isfinite(float(left_trace["opacity"]))
            or not isinstance(left_trace.get("size"), (int, float))
            or not math.isfinite(float(left_trace["size"]))
            or float(left_trace["size"]) <= 0
            or not isinstance(right_trace.get("size"), (int, float))
            or not math.isfinite(float(right_trace["size"]))
            or float(right_trace["size"]) <= 0
        ):
            return False
        left_dir = left_trace.get("dir")
        right_dir = right_trace.get("dir")
        if (
            not finite_pair(left_dir) or not finite_pair(right_dir)
            or abs(float(left_dir[0]) - 1.0) > 1e-6 or abs(float(left_dir[1])) > 1e-6
            or abs(float(right_dir[0]) - 1.0) > 1e-6 or abs(float(right_dir[1])) > 1e-6
        ):
            return False
        left_origin = left_chars[0][2] if isinstance(left_chars[0], (tuple, list)) and len(left_chars[0]) > 2 else None
        right_origin = right_chars[0][2] if isinstance(right_chars[0], (tuple, list)) and len(right_chars[0]) > 2 else None
        if (
            not finite_pair(left_origin) or not finite_pair(right_origin)
            or abs(float(left_origin[1]) - float(right_origin[1])) > 0.01
            or float(right_origin[0]) <= float(left_origin[0])
        ):
            return False
        left_rect = fitz.Rect(left_bbox)
        right_rect = fitz.Rect(right_bbox)
        intersection = left_rect & right_rect
        if not left_rect.is_valid or not right_rect.is_valid:
            return False
        smaller_area = min(left_rect.get_area(), right_rect.get_area())
        smaller_height = min(left_rect.height, right_rect.height)
        smaller_font_size = min(float(left_trace["size"]), float(right_trace["size"]))
        if intersection.is_empty:
            if right_rect.x0 < left_rect.x1:
                return False
            adjoining_width = right_rect.x0 - left_rect.x1
            overlap_area_ratio = 0.0
            overlap_height_ratio = (
                max(0.0, min(left_rect.y1, right_rect.y1) - max(left_rect.y0, right_rect.y0))
                / smaller_height if smaller_height > 0 else 0.0
            )
        else:
            adjoining_width = intersection.width
            overlap_area_ratio = intersection.get_area() / smaller_area if smaller_area > 0 else 1.0
            overlap_height_ratio = intersection.height / smaller_height if smaller_height > 0 else 0.0
        return (
            0 <= adjoining_width <= min(0.05, smaller_font_size * 0.005)
            and smaller_area > 0
            and smaller_height > 0
            and overlap_area_ratio <= 0.005
            and overlap_height_ratio >= 0.95
            and right_rect.x0 >= left_rect.x0
        )

    fill_seq_cache: dict[int, tuple[list[fitz.Rect], bool] | None] = {}
    stroke_seq_cache: dict[
        int,
        list[
            tuple[
                list[tuple[float, float, float, float, tuple[float, float], tuple[float, float], float]],
                fitz.Rect,
                float,
                bool,
                bool,
            ]
        ] | None,
    ] = {}

    def get_verified_fill_seq(index: int, paint_rect: fitz.Rect) -> tuple[list[fitz.Rect], bool] | None:
        if index in fill_seq_cache:
            return fill_seq_cache[index]
        seq_drawings = drawings_by_sequence.get(index, [])
        if not seq_drawings:
            fill_seq_cache[index] = None
            return None
        parsed_fills = [
            extract_fill_subpath_rects(d) if d.get("type") in ("f", "fs") else None
            for d in seq_drawings
        ]
        if not all(sub is not None for sub in parsed_fills):
            fill_seq_cache[index] = None
            return None
        flat_subs = [sr for sub in parsed_fills if sub is not None for sr in sub]
        union_fill = fitz.Rect(
            min(r.x0 for r in flat_subs), min(r.y0 for r in flat_subs),
            max(r.x1 for r in flat_subs), max(r.y1 for r in flat_subs),
        )
        coord_diff = max(
            abs(float(paint_rect.x0) - float(union_fill.x0)),
            abs(float(paint_rect.y0) - float(union_fill.y0)),
            abs(float(paint_rect.x1) - float(union_fill.x1)),
            abs(float(paint_rect.y1) - float(union_fill.y1)),
        )
        if coord_diff > 1.5:
            inter = paint_rect & union_fill
            max_area = max(paint_rect.get_area(), union_fill.get_area())
            protrusion = max(
                float(union_fill.x0) - float(paint_rect.x0),
                float(union_fill.y0) - float(paint_rect.y0),
                float(paint_rect.x1) - float(union_fill.x1),
                float(paint_rect.y1) - float(union_fill.y1),
            )
            if inter.is_empty or max_area <= 0.0 or inter.get_area() / max_area < 0.85 or protrusion > 1.5:
                fill_seq_cache[index] = None
                return None
        all_dark_opaque_fills = all(
            (
                d.get("fill_opacity") is None
                or (
                    isinstance(d.get("fill_opacity"), (int, float))
                    and math.isfinite(float(d["fill_opacity"]))
                    and float(d["fill_opacity"]) >= 0.99
                )
            )
            and stroke_color_is_dark_visible(d.get("fill"))
            for d in seq_drawings
        )
        res = (flat_subs, all_dark_opaque_fills)
        fill_seq_cache[index] = res
        return res

    svg_stroke_safety_cache: list[tuple[bool, list[fitz.Rect]]] = []

    def get_unsafe_svg_stroke_info() -> tuple[bool, list[fitz.Rect]]:
        if svg_stroke_safety_cache:
            return svg_stroke_safety_cache[0]
        if not hasattr(source_page, "get_svg_image"):
            res = (False, [])
            svg_stroke_safety_cache.append(res)
            return res
        try:
            svg_txt = source_page.get_svg_image(text_as_path=False)
        except Exception:
            res = (True, [])
            svg_stroke_safety_cache.append(res)
            return res
        max_svg_bytes = _NativePdfThinStrokeCheck._SVG_BYTES_LIMIT
        if not isinstance(svg_txt, str) or len(svg_txt) > max_svg_bytes:
            res = (True, [])
            svg_stroke_safety_cache.append(res)
            return res
        try:
            if len(svg_txt.encode("utf-8")) > max_svg_bytes:
                res = (True, [])
                svg_stroke_safety_cache.append(res)
                return res
        except UnicodeError:
            res = (True, [])
            svg_stroke_safety_cache.append(res)
            return res
        max_svg_nodes = _NativePdfThinStrokeCheck._SVG_NODE_LIMIT
        svg_node_count = 0
        for _ in re.finditer(r"<[A-Za-z][^>]*>", svg_txt):
            svg_node_count += 1
            if svg_node_count > max_svg_nodes:
                res = (True, [])
                svg_stroke_safety_cache.append(res)
                return res
        unsafe_rects: list[fitz.Rect] = []
        tok_re = re.compile(r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
        total_tokens = 0
        for tag_match in re.finditer(r"<path\b[^>]*>", svg_txt):
            tag = tag_match.group(0)
            if 'stroke="none"' in tag or "stroke=" not in tag:
                continue
            a, b, c, d, e, f = 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
            m_mat = re.search(r'transform="matrix\(([^"]+)\)"', tag)
            is_aniso = False
            smax = 1.0
            if m_mat:
                m_vals = [float(x) for x in re.split(r"[\s,]+", m_mat.group(1).strip()) if x]
                if len(m_vals) != 6 or not all(math.isfinite(v) for v in m_vals):
                    res = (True, [])
                    svg_stroke_safety_cache.append(res)
                    return res
                a, b, c, d, e, f = m_vals
                tr_m = a * a + b * b + c * c + d * d
                det_m = abs(a * d - b * c)
                disc_m = math.sqrt(max(0.0, tr_m * tr_m - 4.0 * det_m * det_m))
                smax = math.sqrt(max(0.0, 0.5 * (tr_m + disc_m)))
                smin = math.sqrt(max(0.0, 0.5 * (tr_m - disc_m)))
                if smin <= 1e-9 or smax / smin > 1.02:
                    is_aniso = True
            m_mit = re.search(r'stroke-miterlimit="([^"]+)"', tag)
            mit_val = float(m_mit.group(1)) if m_mit else 10.0
            if not math.isfinite(mit_val):
                res = (True, [])
                svg_stroke_safety_cache.append(res)
                return res
            if not is_aniso and mit_val <= 10.05:
                continue
            m_sw = re.search(r'stroke-width="([^"]+)"', tag)
            sw_val = float(m_sw.group(1)) if m_sw else 1.0
            m_d = re.search(r'\bd="([^"]+)"', tag)
            if not m_d or not math.isfinite(sw_val):
                res = (True, [])
                svg_stroke_safety_cache.append(res)
                return res
            tokens: list[str] = []
            for token_match in tok_re.finditer(m_d.group(1)):
                total_tokens += 1
                if total_tokens > 100_000:
                    res = (True, [])
                    svg_stroke_safety_cache.append(res)
                    return res
                tokens.append(token_match.group(0))
            pxs: list[float] = []
            pys: list[float] = []
            cx_u = cy_u = sx_u = sy_u = 0.0
            cmd = "M"
            idx_t = 0
            ok_d = True
            while idx_t < len(tokens):
                tk = tokens[idx_t]
                if tk.isalpha():
                    cmd = tk
                    idx_t += 1
                    if cmd in ("Z", "z"):
                        cx_u, cy_u = sx_u, sy_u
                        continue
                    if idx_t >= len(tokens):
                        break
                if cmd in ("M", "L", "m", "l"):
                    if idx_t + 1 >= len(tokens) or tokens[idx_t].isalpha() or tokens[idx_t + 1].isalpha():
                        ok_d = False
                        break
                    vx_u, vy_u = float(tokens[idx_t]), float(tokens[idx_t + 1])
                    idx_t += 2
                    cx_u = (cx_u + vx_u) if cmd.islower() else vx_u
                    cy_u = (cy_u + vy_u) if cmd.islower() else vy_u
                    if cmd in ("M", "m"):
                        sx_u, sy_u = cx_u, cy_u
                        cmd = "l" if cmd == "m" else "L"
                    pxs.append(a * cx_u + c * cy_u + e)
                    pys.append(b * cx_u + d * cy_u + f)
                elif cmd in ("H", "h"):
                    if tokens[idx_t].isalpha():
                        ok_d = False
                        break
                    vx_u = float(tokens[idx_t])
                    idx_t += 1
                    cx_u = (cx_u + vx_u) if cmd == "h" else vx_u
                    pxs.append(a * cx_u + c * cy_u + e)
                    pys.append(b * cx_u + d * cy_u + f)
                elif cmd in ("V", "v"):
                    if tokens[idx_t].isalpha():
                        ok_d = False
                        break
                    vy_u = float(tokens[idx_t])
                    idx_t += 1
                    cy_u = (cy_u + vy_u) if cmd == "v" else vy_u
                    pxs.append(a * cx_u + c * cy_u + e)
                    pys.append(b * cx_u + d * cy_u + f)
                elif cmd in ("C", "c"):
                    if idx_t + 5 >= len(tokens) or any(tokens[idx_t + k].isalpha() for k in range(6)):
                        ok_d = False
                        break
                    ox_u, oy_u = (cx_u, cy_u) if cmd == "c" else (0.0, 0.0)
                    for k in (0, 2, 4):
                        qx, qy = ox_u + float(tokens[idx_t + k]), oy_u + float(tokens[idx_t + k + 1])
                        pxs.append(a * qx + c * qy + e)
                        pys.append(b * qx + d * qy + f)
                    cx_u, cy_u = ox_u + float(tokens[idx_t + 4]), oy_u + float(tokens[idx_t + 5])
                    idx_t += 6
                else:
                    ok_d = False
                    break
            if not ok_d or not pxs:
                res = (True, [])
                svg_stroke_safety_cache.append(res)
                return res
            pad_u = max(1.0, smax * max(mit_val, 1.0) * max(sw_val, 0.0) + 1.0)
            unsafe_rects.append(fitz.Rect(min(pxs) - pad_u, min(pys) - pad_u, max(pxs) + pad_u, max(pys) + pad_u))
        res = (False, unsafe_rects)
        svg_stroke_safety_cache.append(res)
        return res

    def get_verified_stroke_seq(
        index: int, paint_rect: fitz.Rect,
    ) -> list[
        tuple[
            list[tuple[float, float, float, float, tuple[float, float], tuple[float, float], float]],
            fitz.Rect,
            float,
            bool,
            bool,
        ]
    ] | None:
        if index in stroke_seq_cache:
            return stroke_seq_cache[index]
        all_unsafe_svg, unsafe_svg_rects = get_unsafe_svg_stroke_info()
        if all_unsafe_svg or any(not (paint_rect & ur).is_empty for ur in unsafe_svg_rects):
            stroke_seq_cache[index] = None
            return None
        seq_drawings = drawings_by_sequence.get(index, [])
        if not seq_drawings:
            stroke_seq_cache[index] = None
            return None
        parsed_strokes = [
            extract_stroke_segments(d) if d.get("type") in ("s", "fs") else None
            for d in seq_drawings
        ]
        if not all(ps is not None for ps in parsed_strokes):
            stroke_seq_cache[index] = None
            return None
        raw_rects = [ps[1] for ps in parsed_strokes if ps is not None]
        union_raw = fitz.Rect(
            min(r.x0 for r in raw_rects), min(r.y0 for r in raw_rects),
            max(r.x1 for r in raw_rects), max(r.y1 for r in raw_rects),
        )
        max_w = max((ps[3] for ps in parsed_strokes if ps is not None), default=0.0)
        any_diag = any(ps[4] for ps in parsed_strokes if ps is not None)
        any_miter = any(ps[5] == 0 for ps in parsed_strokes if ps is not None)
        margins = (
            float(union_raw.x0) - float(paint_rect.x0),
            float(union_raw.y0) - float(paint_rect.y0),
            float(paint_rect.x1) - float(union_raw.x1),
            float(paint_rect.y1) - float(union_raw.y1),
        )
        min_m, max_m = min(margins), max(margins)
        allowed_max_m = (10.05 * max_w + 0.25) if (any_diag and any_miter) else (0.5 * max_w + 0.25)
        if min_m < -0.5 or (max_m - min_m) > max(1.5, 0.5 * max_w) or max_m > allowed_max_m:
            stroke_seq_cache[index] = None
            return None
        entries_out = []
        for d, ps in zip(seq_drawings, parsed_strokes):
            assert ps is not None
            segs, _raw_b, d_bounds, width, _has_diag, _ljoin = ps
            raw_sop = d.get("stroke_opacity")
            sop_opaque = (
                raw_sop is None
                or (isinstance(raw_sop, (int, float)) and math.isfinite(float(raw_sop)) and float(raw_sop) >= 0.99)
            )
            dark_vis = stroke_color_is_dark_visible(d.get("color"))
            entries_out.append((segs, d_bounds, width, sop_opaque, dark_vis))
        stroke_seq_cache[index] = entries_out
        return entries_out

    thin_stroke_check = _NativePdfThinStrokeCheck(source_page, paint_log)
    protected_stroke_results: dict[tuple[Any, ...], bool] = {}
    translated_fill_separations: dict[tuple[Any, ...], bool] = {}

    def separates_verified_fill(
        index: int, drawing: dict[str, Any], components: list[fitz.Rect],
        trace: dict[str, Any], span_font_size: Any, work_budget: Any,
    ) -> bool:
        """Reuse a completed separation proof for identical translated geometry."""
        chars = trace.get("chars")
        font_name = trace.get("font")
        trace_size = trace.get("size")
        if (
            not isinstance(chars, (tuple, list)) or not chars
            or not isinstance(font_name, str)
            or not isinstance(trace_size, (int, float)) or not math.isfinite(float(trace_size))
        ):
            return thin_stroke_check.separates_dark_fill(
                index, drawing, components, trace, span_font_size, work_budget=work_budget,
            )
        first = chars[0]
        if (
            not isinstance(first, (tuple, list)) or len(first) < 3
            or not isinstance(first[2], (tuple, list)) or len(first[2]) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in first[2])
        ):
            return thin_stroke_check.separates_dark_fill(
                index, drawing, components, trace, span_font_size, work_budget=work_budget,
            )
        origin_x, origin_y = (float(value) for value in first[2])
        normalized_chars = []
        for glyph in chars:
            if (
                not isinstance(glyph, (tuple, list)) or len(glyph) < 4
                or not isinstance(glyph[2], (tuple, list)) or len(glyph[2]) != 2
                or not isinstance(glyph[3], (tuple, list)) or len(glyph[3]) != 4
                or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (*glyph[2], *glyph[3]))
            ):
                return thin_stroke_check.separates_dark_fill(
                    index, drawing, components, trace, span_font_size, work_budget=work_budget,
                )
            normalized_chars.append((
                glyph[0], glyph[1],
                tuple(round(float(value) - offset, 5) for value, offset in zip(glyph[2], (origin_x, origin_y))),
                tuple(round(float(value) - offset, 5) for value, offset in zip(
                    glyph[3], (origin_x, origin_y, origin_x, origin_y),
                )),
            ))
        normalized_components = tuple(sorted(
            tuple(round(value, 5) for value in (
                component.x0 - origin_x, component.y0 - origin_y,
                component.x1 - origin_x, component.y1 - origin_y,
            ))
            for component in components
        ))
        normalized_span_size = (
            round(float(span_font_size), 5)
            if isinstance(span_font_size, (int, float)) and math.isfinite(float(span_font_size)) else None
        )
        key = (
            font_name, round(float(trace_size), 5), normalized_span_size,
            tuple(normalized_chars), normalized_components,
        )
        if key in translated_fill_separations:
            return translated_fill_separations[key]
        result = thin_stroke_check.separates_dark_fill(
            index, drawing, components, trace, span_font_size, work_budget=work_budget,
        )
        translated_fill_separations[key] = result
        return result

    def has_later_paint_overlap(
        trace: dict[str, Any],
        member_trace_order_ids: tuple[int, ...],
        span_font_size: Any,
        *,
        deferred_fills: list[bool] | None = None,
    ) -> bool:
        sequence_number = trace.get("seqno")
        trace_bbox = trace.get("bbox")
        trace_order_id = trace.get("_trace_order_idx")
        if (
            type(sequence_number) is not int
            or type(trace_order_id) is not int
            or not isinstance(trace_bbox, (tuple, list))
            or len(trace_bbox) != 4
        ):
            return True
        trace_rect = fitz.Rect(trace_bbox)
        # PyMuPDF's text trace box can omit italic paint overhang. Use the
        # matching source paint bound only to keep later operations in the
        # candidate set; the glyph/paint proofs below still decide visibility.
        source_candidate_rect = trace_rect
        if 0 <= sequence_number < len(paint_log):
            source_paint_item = paint_log[sequence_number]
            if (
                isinstance(source_paint_item, (tuple, list))
                and len(source_paint_item) == 2
                and source_paint_item[0] in ("fill-text", "stroke-text")
                and isinstance(source_paint_item[1], (tuple, list))
                and len(source_paint_item[1]) == 4
                and all(
                    isinstance(value, (int, float)) and math.isfinite(float(value))
                    for value in source_paint_item[1]
                )
            ):
                source_paint_rect = fitz.Rect(source_paint_item[1])
                if not source_paint_rect.is_empty:
                    source_candidate_rect = fitz.Rect(
                        min(trace_rect.x0, source_paint_rect.x0),
                        min(trace_rect.y0, source_paint_rect.y0),
                        max(trace_rect.x1, source_paint_rect.x1),
                        max(trace_rect.y1, source_paint_rect.y1),
                    )
        # Keep paint geometry for glyphs that a ToUnicode map reports as whitespace.
        # Such a codepoint can still be visible ink and a later fill must mask the whole span.
        raw_target_glyphs = glyph_entries_from_chars(trace.get("chars"), skip_spaces=False)
        if raw_target_glyphs is not None and not raw_target_glyphs:
            return False
        raw_dir = trace.get("dir", (1.0, 0.0))
        raw_size = trace.get("size")
        dir_ok = (
            isinstance(raw_dir, (tuple, list)) and len(raw_dir) == 2
            and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in raw_dir)
            and math.hypot(float(raw_dir[0]), float(raw_dir[1])) > 1e-6
        )
        size_ok = isinstance(raw_size, (int, float)) and math.isfinite(float(raw_size)) and float(raw_size) > 0.0
        if dir_ok:
            d_norm = math.hypot(float(raw_dir[0]), float(raw_dir[1]))
            ux, uy = float(raw_dir[0]) / d_norm, float(raw_dir[1]) / d_norm
            vx, vy = uy, -ux
        else:
            ux = uy = vx = vy = 0.0
        trace_size = float(raw_size) if size_ok else 0.0
        sp_sz = (
            float(span_font_size)
            if isinstance(span_font_size, (int, float)) and math.isfinite(float(span_font_size)) and float(span_font_size) > 0.0
            else trace_size
        )
        if trace_size > 0.0 and sp_sz > trace_size * 1.005:
            effective_v_size = min(trace_size * 1024.0, (sp_sz * sp_sz) / trace_size)
        elif trace_size > 0.0 and sp_sz < trace_size * 0.995:
            effective_v_size = max(0.5, (sp_sz * sp_sz) / trace_size)
        else:
            effective_v_size = trace_size
        v_scale = (effective_v_size / trace_size) if (dir_ok and trace_size > 0.0) else 1.0
        if raw_target_glyphs is not None and abs(v_scale - 1.0) > 1e-3:
            target_glyphs: list[tuple[int, tuple[float, float], fitz.Rect]] | None = [
                (cp, org, expand_glyph_rect_for_condensation(org, gr, ux, uy, vx, vy, v_scale))
                for cp, org, gr in raw_target_glyphs
            ]
            trace_rect = fitz.Rect(
                min([trace_rect.x0] + [gr.x0 for _c, _o, gr in target_glyphs]),
                min([trace_rect.y0] + [gr.y0 for _c, _o, gr in target_glyphs]),
                max([trace_rect.x1] + [gr.x1 for _c, _o, gr in target_glyphs]),
                max([trace_rect.y1] + [gr.y1 for _c, _o, gr in target_glyphs]),
            )
        else:
            target_glyphs = raw_target_glyphs
        member_id_set = set(member_trace_order_ids)
        glyph_pair_work = _GlyphPairWorkBudget(glyph_pair_work_limit)
        glyph_lookup_by_source_position: dict[tuple[int, tuple[Any, ...]], list[Any]] | None = None

        def trace_glyphs_hit_target(lt: dict[str, Any], lt_glyphs: list[tuple[int, tuple[float, float], fitz.Rect]]) -> bool:
            assert target_glyphs is not None
            base14_rects = thin_stroke_check._base14_trace_glyph_rects(lt)
            if base14_rects is not None:
                lt_glyphs = [
                    (
                        codepoint,
                        origin,
                        fitz.Rect(
                            min(nominal_rect.x0, base14_rects.get((codepoint, tuple(origin)), nominal_rect).x0),
                            min(nominal_rect.y0, base14_rects.get((codepoint, tuple(origin)), nominal_rect).y0),
                            max(nominal_rect.x1, base14_rects.get((codepoint, tuple(origin)), nominal_rect).x1),
                            max(nominal_rect.y1, base14_rects.get((codepoint, tuple(origin)), nominal_rect).y1),
                        ),
                    )
                    for codepoint, origin, nominal_rect in lt_glyphs
                ]
            if not glyph_pair_work.reserve(target_glyphs, lt_glyphs):
                if deferred_fills is not None:
                    deferred_fills.clear()
                return True
            lt_dir = lt.get("dir")
            lt_size = lt.get("size")
            same_oblique_dir = (
                dir_ok
                and size_ok
                and abs(uy) > 1e-3
                and isinstance(lt_dir, (tuple, list))
                and len(lt_dir) == 2
                and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in lt_dir)
                and math.dist((ux, uy), (float(lt_dir[0]), float(lt_dir[1]))) <= 1e-3
                and isinstance(lt_size, (int, float))
                and math.isfinite(float(lt_size))
                and float(lt_size) > 0
            )
            if same_oblique_dir:
                raw_asc_a, raw_desc_a = trace.get("ascender"), trace.get("descender")
                raw_asc_b, raw_desc_b = lt.get("ascender"), lt.get("descender")
                lt_eff_v = float(lt.get("_effective_v_size", lt_size))
                asc_a = max(
                    0.75,
                    float(raw_asc_a) if isinstance(raw_asc_a, (int, float)) and math.isfinite(float(raw_asc_a)) else 0.85,
                ) * effective_v_size
                desc_a = min(
                    -0.15,
                    float(raw_desc_a) if isinstance(raw_desc_a, (int, float)) and math.isfinite(float(raw_desc_a)) else -0.25,
                ) * effective_v_size
                asc_b = max(
                    0.75,
                    float(raw_asc_b) if isinstance(raw_asc_b, (int, float)) and math.isfinite(float(raw_asc_b)) else 0.85,
                ) * lt_eff_v
                desc_b = min(
                    -0.15,
                    float(raw_desc_b) if isinstance(raw_desc_b, (int, float)) and math.isfinite(float(raw_desc_b)) else -0.25,
                ) * lt_eff_v
                for _cp, (ox_a, oy_a), gr in target_glyphs:
                    for _lcp, (ox_b, oy_b), lgr in lt_glyphs:
                        if (gr & lgr).is_empty:
                            continue
                        dv_orig = (ox_b - ox_a) * vx + (oy_b - oy_a) * vy
                        if max(desc_a, dv_orig + desc_b) < min(asc_a, dv_orig + asc_b):
                            return True
                return False
            return any(
                not (gr & lgr).is_empty
                for _cp, _org, gr in target_glyphs
                for _lcp, _lorg, lgr in lt_glyphs
            )

        try:
            later_intra_chars = trace.get("_later_intra_trace_chars")
            if later_intra_chars:
                if target_glyphs is None:
                    return True
                intra_glyphs = glyph_entries_from_chars(later_intra_chars, skip_spaces=False)
                if intra_glyphs is None:
                    return True
                if not glyph_pair_work.reserve(target_glyphs, intra_glyphs):
                    if deferred_fills is not None:
                        deferred_fills.clear()
                    return True
                if abs(v_scale - 1.0) > 1e-3:
                    intra_glyphs = [
                        (icp, iorg, expand_glyph_rect_for_condensation(iorg, igr, ux, uy, vx, vy, v_scale))
                        for icp, iorg, igr in intra_glyphs
                    ]
                if any(
                    not (gr & igr).is_empty
                    for _cp, _org, gr in target_glyphs
                    for _icp, _iorg, igr in intra_glyphs
                ):
                    return True

            if 0 <= sequence_number < len(paint_log):
                same_seq_item = paint_log[sequence_number]
                if not isinstance(same_seq_item, (tuple, list)) or len(same_seq_item) != 2:
                    return True
                same_seq_type, same_seq_bbox = same_seq_item
                seq_all_traces = traces_by_sequence.get(sequence_number, [])
                same_seq_later = [
                    lt for lt in seq_all_traces
                    if type(lt.get("_trace_order_idx")) is int
                    and lt["_trace_order_idx"] > trace_order_id
                    and lt["_trace_order_idx"] not in member_id_set
                ]
                if same_seq_later:
                    if (
                        same_seq_type != "fill-text"
                        or target_glyphs is None
                        or not isinstance(same_seq_bbox, (tuple, list))
                        or len(same_seq_bbox) != 4
                        or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in same_seq_bbox)
                        or not seq_all_traces
                        or not all(
                            isinstance(st, dict)
                            and st.get("type") == 0
                            and st.get("wmode") == 0
                            and isinstance(st.get("_occluder_bbox"), fitz.Rect)
                            for st in seq_all_traces
                        )
                    ):
                        return True
                    same_seq_rect = fitz.Rect(same_seq_bbox)
                    st_rects = [st["_occluder_bbox"] for st in seq_all_traces]
                    union_st = fitz.Rect(
                        min(r.x0 for r in st_rects), min(r.y0 for r in st_rects),
                        max(r.x1 for r in st_rects), max(r.y1 for r in st_rects),
                    )
                    max_st_sz = max(float(st.get("_effective_v_size", st.get("size", 0.0))) for st in seq_all_traces)
                    st_protrusion = max(
                        float(union_st.x0) - float(same_seq_rect.x0),
                        float(union_st.y0) - float(same_seq_rect.y0),
                        float(same_seq_rect.x1) - float(union_st.x1),
                        float(same_seq_rect.y1) - float(union_st.y1),
                    )
                    if st_protrusion > max(1.5, 0.20 * max_st_sz):
                        return True
                    for lt in same_seq_later:
                        lt_r = lt["_occluder_bbox"]
                        if (trace_rect & lt_r).is_empty:
                            continue
                        if not lt.get("_occluder_v_expanded") and is_safe_adjacent_text_overlap(trace, lt):
                            continue
                        lt_glyphs = lt.get("_occluder_glyphs")
                        if lt_glyphs is None or trace_glyphs_hit_target(lt, lt_glyphs):
                            return True

            for index, paint_item in enumerate(paint_log):
                if not isinstance(paint_item, (tuple, list)) or len(paint_item) != 2:
                    return True
                paint_type, paint_bbox = paint_item
                if index <= sequence_number or paint_type == "ignore-text":
                    continue
                if (
                    isinstance(paint_bbox, (tuple, list))
                    and len(paint_bbox) == 4
                    and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in paint_bbox)
                    and (
                        float(paint_bbox[2]) <= source_candidate_rect.x0
                        or float(paint_bbox[0]) >= source_candidate_rect.x1
                        or float(paint_bbox[3]) <= source_candidate_rect.y0
                        or float(paint_bbox[1]) >= source_candidate_rect.y1
                    )
                ):
                    continue
                paint_rect = fitz.Rect(paint_bbox)
                if overlap_ratio(source_candidate_rect, paint_rect) <= 0:
                    continue
                later_traces = traces_by_sequence.get(index, [])
                if (
                    paint_type == "fill-text"
                    and later_traces
                    and all(
                        isinstance(lt, dict)
                        and lt.get("type") == 0
                        and lt.get("_trace_order_idx") in member_id_set
                        for lt in later_traces
                    )
                ):
                    continue
                if (
                    later_traces
                    and paint_type == "fill-text"
                    and target_glyphs is not None
                    and all(
                        isinstance(lt, dict)
                        and lt.get("type") == 0
                        and lt.get("wmode") == 0
                        and isinstance(lt.get("_occluder_bbox"), fitz.Rect)
                        and isinstance(lt.get("size"), (int, float))
                        and math.isfinite(float(lt["size"]))
                        and float(lt["size"]) > 0
                        for lt in later_traces
                    )
                ):
                    lt_rects = [lt["_occluder_bbox"] for lt in later_traces]
                    expand_single_lt_y = False
                    if len(lt_rects) == 1 and not later_traces[0].get("_occluder_v_expanded"):
                        r0 = lt_rects[0]
                        if paint_rect.y0 < r0.y0 - 0.5 or paint_rect.y1 > r0.y1 + 0.5:
                            lt_rects = [fitz.Rect(r0.x0, min(r0.y0, paint_rect.y0), r0.x1, max(r0.y1, paint_rect.y1))]
                            expand_single_lt_y = True
                    union_lt = fitz.Rect(
                        min(r.x0 for r in lt_rects), min(r.y0 for r in lt_rects),
                        max(r.x1 for r in lt_rects), max(r.y1 for r in lt_rects),
                    )
                    max_lt_sz = max(float(lt.get("_effective_v_size", lt["size"])) for lt in later_traces)
                    lt_protrusion = max(
                        float(union_lt.x0) - float(paint_rect.x0),
                        float(union_lt.y0) - float(paint_rect.y0),
                        float(paint_rect.x1) - float(union_lt.x1),
                        float(paint_rect.y1) - float(union_lt.y1),
                    )
                    p_area = paint_rect.get_area()
                    lt_covered = (
                        ((paint_rect & union_lt).get_area() / p_area >= 0.85)
                        if p_area > 0.0
                        else not (paint_rect & union_lt).is_empty
                    )
                    if lt_covered and lt_protrusion <= max(1.5, 0.20 * max_lt_sz):
                        glyph_hit = False
                        for lt, lt_r in zip(later_traces, lt_rects):
                            if lt.get("_trace_order_idx") in member_id_set:
                                continue
                            trace_paint_protrusion = max(
                                abs(float(paint_rect.x0) - float(lt_r.x0)),
                                abs(float(paint_rect.y0) - float(lt_r.y0)),
                                abs(float(paint_rect.x1) - float(lt_r.x1)),
                                abs(float(paint_rect.y1) - float(lt_r.y1)),
                            )
                            if (
                                (trace_rect & lt_r).is_empty
                                and len(later_traces) == 1
                                and max(lt_protrusion, trace_paint_protrusion) <= 1.5
                            ):
                                # Preserve the cheap non-overlap path unless the compound
                                # paint extends materially beyond its trace union.
                                continue
                            lt_glyphs = lt.get("_occluder_glyphs")
                            if lt_glyphs is None:
                                glyph_hit = True
                                break
                            if expand_single_lt_y:
                                lt_glyphs = [
                                    (lcp, lorg, fitz.Rect(
                                        lgr.x0, min(lgr.y0, paint_rect.y0),
                                        lgr.x1, max(lgr.y1, paint_rect.y1),
                                    ))
                                    for lcp, lorg, lgr in lt_glyphs
                                ]
                            glyph_contact = trace_glyphs_hit_target(lt, lt_glyphs)
                            if not glyph_contact:
                                if lt_protrusion > 1.5:
                                    # A disjoint run cannot be attributed as harmless
                                    # when the paint extent has significant overhang.
                                    glyph_hit = True
                                    break
                                continue
                            if (
                                not expand_single_lt_y
                                and not lt.get("_occluder_v_expanded")
                                and is_safe_adjacent_text_overlap(trace, lt)
                            ):
                                continue
                            glyph_hit = True
                            break
                        if not glyph_hit:
                            continue
                        return True

                if paint_type == "fill-path" and target_glyphs is not None:
                    verified_fill = get_verified_fill_seq(index, paint_rect)
                    if verified_fill is not None:
                        flat_subs, all_dark_opaque_fills = verified_fill
                        if not glyph_pair_work.reserve(target_glyphs, flat_subs):
                            if deferred_fills is not None:
                                deferred_fills.clear()
                            return True
                        metric_hit = any(
                            not (glyph_rect & subpath).is_empty
                            for subpath in flat_subs
                            if not (trace_rect & subpath).is_empty
                            for _, _, glyph_rect in target_glyphs
                        )
                        if metric_hit:
                            if not all_dark_opaque_fills:
                                return True
                            if deferred_fills is not None:
                                if not deferred_fills:
                                    deferred_fills.append(True)
                                direction = (ux, uy) if dir_ok else (1.0, 0.0)
                                if not glyph_pair_work.reserve(target_glyphs, flat_subs):
                                    # Exhaustion is a terminal veto, not optional
                                    # work for the fresh-budget replay pass.
                                    deferred_fills.clear()
                                    return True
                                if any(
                                    not (protected_stroke_glyph_rect(cp, origin, rect, direction) & subpath).is_empty
                                    for subpath in flat_subs
                                    if not (trace_rect & subpath).is_empty
                                    for cp, origin, rect in target_glyphs
                                ):
                                    return True
                            else:
                                fill_drawings = drawings_by_sequence.get(index, [])
                                if len(fill_drawings) != 1 or not separates_verified_fill(
                                    index, fill_drawings[0], flat_subs, trace, span_font_size,
                                    work_budget=glyph_pair_work,
                                ):
                                    return True
                        else:
                            fill_probe_pad = max(1.0, 0.15 * effective_v_size)
                            fill_probe_rect = fitz.Rect(
                                trace_rect.x0 - fill_probe_pad, trace_rect.y0 - fill_probe_pad,
                                trace_rect.x1 + fill_probe_pad, trace_rect.y1 + fill_probe_pad,
                            )
                            if any(not (fill_probe_rect & subpath).is_empty for subpath in flat_subs):
                                fill_drawings = drawings_by_sequence.get(index, [])
                                if len(fill_drawings) != 1 or not separates_verified_fill(
                                    index, fill_drawings[0], flat_subs, trace, span_font_size,
                                    work_budget=glyph_pair_work,
                                ):
                                    return True
                        continue

                if (
                    paint_type == "stroke-path"
                    and target_glyphs is not None
                    and dir_ok
                    and size_ok
                ):
                    verified_strokes = get_verified_stroke_seq(index, paint_rect)
                    if verified_strokes is not None:
                        stroke_hit = False
                        ink_contact_candidates = []
                        trace_probe_pad = max(1.0, 0.15 * effective_v_size)
                        for segs, d_bounds, width, sop_opaque, dark_vis in verified_strokes:
                            if (source_candidate_rect & d_bounds).is_empty:
                                continue
                            # Trace metrics can underbound italic ink, but the
                            # expanded trace filter keeps unrelated strokes out.
                            cand_segs = [
                                segment for segment in segs
                                if segment[2] >= trace_rect.x0 - trace_probe_pad
                                and segment[0] <= trace_rect.x1 + trace_probe_pad
                                and segment[3] >= trace_rect.y0 - trace_probe_pad
                                and segment[1] <= trace_rect.y1 + trace_probe_pad
                            ]
                            if not cand_segs:
                                continue
                            if any(
                                (fitz.Rect(segment[0], segment[1], segment[2], segment[3]) & trace_rect).is_empty
                                and not (
                                    fitz.Rect(segment[0], segment[1], segment[2], segment[3])
                                    & source_candidate_rect
                                ).is_empty
                                for segment in cand_segs
                            ):
                                # A verified stroke in source paint overhang is a
                                # possible strike even when nominal glyph metrics
                                # miss it; keep that span out of review admission.
                                return True
                            if not glyph_pair_work.reserve(target_glyphs, cand_segs):
                                if deferred_fills is not None:
                                    deferred_fills.clear()
                                return True
                            thin_cad_stroke = (
                                sop_opaque
                                and dark_vis
                                and width <= 0.30 * effective_v_size
                            )
                            ink_probe_pad = max(1.0, 0.15 * effective_v_size)
                            for cp, (ox, oy), gr in target_glyphs:
                                if (gr & d_bounds).is_empty:
                                    continue
                                if not thin_cad_stroke:
                                    if any(
                                        sx1 + half >= gr.x0 - ink_probe_pad
                                        and sx0 - half <= gr.x1 + ink_probe_pad
                                        and sy1 + half >= gr.y0 - ink_probe_pad
                                        and sy0 - half <= gr.y1 + ink_probe_pad
                                        for sx0, sy0, sx1, sy1, _sp1, _sp2, seg_pad in cand_segs
                                        for half in (0.5 * width + seg_pad,)
                                    ):
                                        stroke_hit = True
                                        break
                                gx0, gy0, gx1, gy1 = gr.x0, gr.y0, gr.x1, gr.y1
                                corners = ((gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1))
                                us = [(cx - ox) * ux + (cy - oy) * uy for cx, cy in corners]
                                vs = [(cx - ox) * vx + (cy - oy) * vy for cx, cy in corners]
                                u0, u1 = min(us), max(us)
                                v0, v1 = min(vs), max(vs)
                                ch = chr(cp)
                                if thin_cad_stroke:
                                    v_top = v1
                                    if ch in deep_descender_glyphs:
                                        v_bot = max(v0, -0.22 * effective_v_size)
                                    elif ch in below_baseline_ink_glyphs or (cp >= 0x80 and ch not in "°′″±"):
                                        v_bot = max(v0, -0.09 * effective_v_size)
                                    elif ch in baseline_punct_glyphs:
                                        v_bot = max(v0, 0.01 * effective_v_size)
                                    else:
                                        v_bot = max(v0, 0.0)
                                    # Metric-side trimming is not source-bound proof that a
                                    # font's outer glyph region contains no ink. Keep the
                                    # full horizontal glyph box in the stroke-overlap veto.
                                    box_u0, box_u1 = u0, u1
                                    box_v0, box_v1 = min(v_bot, v_top), max(v_bot, v_top)
                                else:
                                    box_u0, box_u1, box_v0, box_v1 = u0, u1, v0, v1
                                for sx0, sy0, sx1, sy1, sp1, sp2, seg_pad in cand_segs:
                                    if (
                                        sx1 < gx0 - ink_probe_pad or sx0 > gx1 + ink_probe_pad
                                        or sy1 < gy0 - ink_probe_pad or sy0 > gy1 + ink_probe_pad
                                    ):
                                        continue
                                    su1 = (sp1[0] - ox) * ux + (sp1[1] - oy) * uy
                                    sv1 = (sp1[0] - ox) * vx + (sp1[1] - oy) * vy
                                    su2 = (sp2[0] - ox) * ux + (sp2[1] - oy) * uy
                                    sv2 = (sp2[0] - ox) * vx + (sp2[1] - oy) * vy
                                    du, dv = su2 - su1, sv2 - sv1
                                    half = 0.5 * width + seg_pad
                                    eu0, eu1 = box_u0 - half, box_u1 + half
                                    ev0, ev1 = box_v0 - half, box_v1 + half
                                    if eu1 < eu0 or ev1 < ev0:
                                        continue
                                    t0, t1 = 0.0, 1.0
                                    clipped = True
                                    for p_val, q_val in (
                                        (-du, su1 - eu0),
                                        (du, eu1 - su1),
                                        (-dv, sv1 - ev0),
                                        (dv, ev1 - sv1),
                                    ):
                                        if abs(p_val) < 1e-12:
                                            if q_val < 0.0:
                                                clipped = False
                                                break
                                        else:
                                            t_val = q_val / p_val
                                            if p_val < 0.0:
                                                if t_val > t1:
                                                    clipped = False
                                                    break
                                                t0 = max(t0, t_val)
                                            else:
                                                if t_val < t0:
                                                    clipped = False
                                                    break
                                                t1 = min(t1, t_val)
                                    if clipped and t0 <= t1:
                                        stroke_hit = True
                                        break
                                    if (
                                        thin_cad_stroke
                                        and min(abs(ux), abs(uy)) <= 1e-3
                                        and max(sy0, gy0 - ink_probe_pad) < min(sy1, gy1 + ink_probe_pad)
                                        and max(sx0, gx0 - ink_probe_pad) < min(sx1, gx1 + ink_probe_pad)
                                    ):
                                        ink_contact_candidates.append((cp, ox, oy, gr))
                                if stroke_hit:
                                    break
                            if stroke_hit:
                                break
                        if stroke_hit:
                            return True
                        seq_drawings = drawings_by_sequence.get(index, [])
                        if deferred_fills is None and ink_contact_candidates and len(seq_drawings) != 1:
                            return True
                        if ink_contact_candidates and len(seq_drawings) == 1:
                            if glyph_lookup_by_source_position is None:
                                source_chars = trace.get("chars")
                                if not isinstance(source_chars, (tuple, list)):
                                    return True
                                if not glyph_pair_work.reserve(source_chars, (None,)):
                                    if deferred_fills is not None:
                                        deferred_fills.clear()
                                    return True
                                glyph_lookup_by_source_position = {}
                                for glyph in source_chars:
                                    key = _native_pdf_glyph_source_key(glyph)
                                    glyph_lookup_by_source_position.setdefault(key, []).append(glyph)
                            checked_glyphs = set()
                            for cp, ox, oy, glyph_rect in ink_contact_candidates:
                                key = (cp, ox, oy)
                                if key in checked_glyphs:
                                    continue
                                checked_glyphs.add(key)
                                clip = fitz.Rect(
                                    glyph_rect.x0 - ink_probe_pad, glyph_rect.y0 - ink_probe_pad,
                                    glyph_rect.x1 + ink_probe_pad, glyph_rect.y1 + ink_probe_pad,
                                )
                                if _native_pdf_below_baseline_candidate_overlaps(
                                    glyph_lookup_by_source_position,
                                    cp,
                                    ox,
                                    oy,
                                    (index, trace_order_id, trace.get("_source_character_range")),
                                    protected_stroke_results,
                                    span_font_size=span_font_size,
                                    clip=clip,
                                    deferred_fills=deferred_fills,
                                    proof=lambda matched_glyph: thin_stroke_check.overlaps_below_baseline(
                                        index, seq_drawings[0], trace, matched_glyph, span_font_size, clip,
                                    ),
                                ):
                                    return True
                        continue

                if overlap_ratio(trace_rect, paint_rect) > 0:
                    return True
        except (TypeError, ValueError, RuntimeError):
            return True
        return False

    # Candidate trace lookup for span binding. The exact validator below is
    # intentionally strict, but scanning every paint trace for every source
    # span makes ordinary pages quadratic (and expensive because it constructs
    # PyMuPDF rectangles for obviously remote traces). Bucket each validated
    # trace bbox across every horizontal cell it touches; queries are
    # deliberately over-inclusive and the exact bbox predicate remains the
    # authority. Very wide or malformed traces use the conservative fallback.
    trace_bucket_width = 64.0
    max_trace_bucket_span = 64
    trace_indices_by_font_x_bucket: dict[tuple[str, int], list[int]] = {}
    wide_trace_indices_by_font: dict[str, list[int]] = {}
    trace_bounds: list[tuple[float, float, float, float] | None] = []
    for trace_index, trace in enumerate(paint_traces):
        bbox = trace.get("bbox")
        if (
            not isinstance(bbox, (tuple, list)) or len(bbox) != 4
            or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in bbox)
        ):
            trace_bounds.append(None)
            continue
        bounds = tuple(float(value) for value in bbox)
        x0, y0, x1, y1 = bounds
        trace_bounds.append(bounds)
        trace_font = trace.get("font")
        if not isinstance(trace_font, str):
            continue
        if x1 <= x0 or y1 <= y0:
            wide_trace_indices_by_font.setdefault(trace_font, []).append(trace_index)
            continue
        first_bucket = math.floor(x0 / trace_bucket_width)
        last_bucket = math.floor(x1 / trace_bucket_width)
        if last_bucket - first_bucket > max_trace_bucket_span:
            wide_trace_indices_by_font.setdefault(trace_font, []).append(trace_index)
            continue
        for bucket in range(first_bucket, last_bucket + 1):
            trace_indices_by_font_x_bucket.setdefault((trace_font, bucket), []).append(trace_index)

    span_trace_ranges: dict[tuple[int, int, int], tuple[int, dict[str, Any]]] = {}
    trace_range_coverage: dict[int, list[tuple[int, int]]] = {}
    for block_index, block in enumerate(source_text_blocks):
        for line_index, line in enumerate(block.get("lines", [])):
            if line.get("wmode") != 0:
                continue
            line_direction = line.get("dir", (1.0, 0.0))
            for span_index, span in enumerate(line.get("spans", [])):
                bbox = span.get("bbox")
                if not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
                    continue
                if not all(
                    isinstance(value, (int, float)) and math.isfinite(float(value))
                    for value in bbox
                ):
                    continue
                span_rect = fitz.Rect(bbox)
                if span_rect.is_empty or not span_rect.is_valid:
                    continue
                first_bucket = math.floor(span_rect.x0 / trace_bucket_width)
                last_bucket = math.floor(span_rect.x1 / trace_bucket_width)
                span_font = span.get("font")
                if not isinstance(span_font, str):
                    continue
                if last_bucket - first_bucket > max_trace_bucket_span:
                    possible_trace_indices = (
                        trace_index for trace_index, trace in enumerate(paint_traces)
                        if trace.get("font") == span_font
                    )
                else:
                    possible_trace_indices = sorted({
                        *wide_trace_indices_by_font.get(span_font, ()),
                        *(trace_index
                          for bucket in range(first_bucket, last_bucket + 1)
                          for trace_index in trace_indices_by_font_x_bucket.get((span_font, bucket), ())),
                    })
                candidates = []
                for trace_index in possible_trace_indices:
                    bounds = trace_bounds[trace_index]
                    if bounds is None:
                        continue
                    x0, y0, x1, y1 = bounds
                    if x1 <= span_rect.x0 or x0 >= span_rect.x1 or y1 <= span_rect.y0 or y0 >= span_rect.y1:
                        continue
                    mapped = exact_source_span_trace_range(span, span_rect, line_direction, paint_traces[trace_index])
                    if mapped is not None:
                        candidates.append((trace_index, mapped))
                if len(candidates) != 1:
                    continue
                trace_index, mapped = candidates[0]
                span_trace_ranges[(block_index, line_index, span_index)] = (trace_index, mapped)
                trace_range_coverage.setdefault(trace_index, []).append(mapped["_source_character_range"])

    complete_trace_partitions: set[int] = set()
    for trace_index, trace in enumerate(paint_traces):
        ranges = sorted(trace_range_coverage.get(trace_index, []))
        cursor = 0
        if not ranges:
            continue
        for start, end in ranges:
            if start != cursor or end <= start:
                break
            cursor = end
        else:
            if cursor == len(trace.get("chars", [])):
                complete_trace_partitions.add(trace_index)

    scale_x = render_width / displayed.width
    scale_y = render_height / displayed.height
    records: list[dict[str, Any]] = []
    pending_fill_checks: dict[int, tuple[list[dict[str, Any]], tuple[int, ...], Any]] = {}
    for block_index, block in enumerate(source_text_blocks):
        for line_index, line in enumerate(block.get("lines", [])):
            direction = line.get("dir", (1.0, 0.0))
            writing_mode = line.get("wmode")
            if writing_mode != 0:
                continue
            for span_index, span in enumerate(line.get("spans", [])):
                content = span.get("text")
                bbox = span.get("bbox")
                if not isinstance(content, str) or not content or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                    continue
                if not all(
                    isinstance(value, (int, float)) and math.isfinite(float(value))
                    for value in bbox
                ):
                    continue
                rect = fitz.Rect(bbox)
                if rect.is_empty or not rect.is_valid:
                    continue
                compact_content = compact_text(content)
                if not compact_content:
                    continue
                matching_traces: list[tuple[dict[str, Any], str, str]] = []
                rx0, ry0, rx1, ry1 = rect.x0, rect.y0, rect.x1, rect.y1
                for trace in paint_traces:
                    trace_bbox = trace.get("bbox")
                    if (
                        not isinstance(trace_bbox, (tuple, list))
                        or len(trace_bbox) != 4
                        or not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in trace_bbox)
                        or float(trace_bbox[2]) <= rx0
                        or float(trace_bbox[0]) >= rx1
                        or float(trace_bbox[3]) <= ry0
                        or float(trace_bbox[1]) >= ry1
                    ):
                        continue
                    if overlap_ratio(rect, fitz.Rect(trace_bbox)) < 0.9:
                        continue
                    chars = trace.get("chars")
                    trace_text = "".join(
                        chr(char[0]) for char in chars
                        if isinstance(char, (tuple, list)) and char and type(char[0]) is int
                    ) if isinstance(chars, (tuple, list)) else ""
                    agreement = trace_text_agreement(content, trace_text)
                    if (
                        not isinstance(chars, (tuple, list))
                        or not chars
                        or any(
                            isinstance(ch, (tuple, list))
                            and len(ch) >= 4
                            and isinstance(ch[3], (tuple, list))
                            and len(ch[3]) == 4
                            and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in ch[3])
                            and not (rect & fitz.Rect(ch[3])).is_empty
                            for ch in chars
                        )
                    ):
                        matching_traces.append((trace, trace_text, agreement or ""))
                if len(matching_traces) == 1 and matching_traces[0][2]:
                    member_traces = [matching_traces[0][0]]
                    trace_text = matching_traces[0][1]
                    text_agreement = matching_traces[0][2]
                else:
                    complete_b041_partition: list[dict[str, Any]] | None = None
                    ordered_matches = sorted(
                        matching_traces,
                        key=lambda item: item[0].get("seqno", -1),
                    )
                    candidate_traces = [item[0] for item in ordered_matches]
                    sequence_numbers = [trace.get("seqno") for trace in candidate_traces]
                    candidate_text = "".join(item[1] for item in ordered_matches)
                    common_fields = ("type", "font", "layer", "colorspace", "color", "opacity", "wmode", "dir", "size")
                    first_trace = candidate_traces[0] if candidate_traces else {}
                    common_style = all(
                        all(trace.get(field) == first_trace.get(field) for field in common_fields)
                        for trace in candidate_traces
                    )
                    if (
                        len(candidate_traces) >= 2
                        and all(type(sequence) is int for sequence in sequence_numbers)
                        and len(set(sequence_numbers)) == len(sequence_numbers)
                        and common_style
                        and candidate_text == content
                        and compact_content
                    ):
                        cand_rects = [fitz.Rect(trace["bbox"]) for trace in candidate_traces]
                        union_cand = fitz.Rect(
                            min(r.x0 for r in cand_rects), min(r.y0 for r in cand_rects),
                            max(r.x1 for r in cand_rects), max(r.y1 for r in cand_rects),
                        )
                        if overlap_ratio(rect, union_cand) >= 0.9:
                            complete_b041_partition = candidate_traces
                            trace_text = candidate_text
                    if complete_b041_partition is not None:
                        member_traces = complete_b041_partition
                        text_agreement = "exact"
                    else:
                        range_candidate = span_trace_ranges.get((block_index, line_index, span_index))
                        if (
                            range_candidate is None
                            or range_candidate[0] not in complete_trace_partitions
                        ):
                            continue
                        member_traces = [range_candidate[1]]
                        trace_text = content
                        text_agreement = "exact"
                if not has_valid_glyph_progression(member_traces, direction, span.get("size")):
                    continue
                member_sequences = {trace["seqno"] for trace in member_traces}
                member_trace_order_ids = tuple(
                    trace["_trace_order_idx"]
                    for trace in member_traces
                    if type(trace.get("_trace_order_idx")) is int
                )
                if len(member_trace_order_ids) != len(member_traces):
                    continue
                member_paint_evidence = []
                for trace in member_traces:
                    trace_chars = trace.get("chars")
                    if not isinstance(trace_chars, (tuple, list)) or not trace_chars:
                        member_paint_evidence = []
                        break
                    member_evidence = {
                        "sequence_number": trace["seqno"],
                        "text": "".join(
                            chr(char[0]) for char in trace_chars
                            if isinstance(char, (tuple, list)) and char and type(char[0]) is int
                        ),
                        "glyph_ids": [
                            char[1] for char in trace_chars
                            if isinstance(char, (tuple, list)) and len(char) > 1 and type(char[1]) is int
                        ],
                        "bbox_pt": [float(value) for value in trace["bbox"]],
                        "type": trace.get("type"),
                        "opacity": trace.get("opacity"),
                        "wmode": trace.get("wmode"),
                        "layer": trace.get("layer") or None,
                    }
                    if isinstance(trace.get("_source_character_range"), (tuple, list)):
                        member_evidence["character_range"] = list(trace["_source_character_range"])
                        member_evidence["aggregate_trace_bbox_pt"] = list(trace["_aggregate_trace_bbox"])
                    member_paint_evidence.append(member_evidence)
                if len(member_paint_evidence) != len(member_traces):
                    continue
                paint_trace = member_traces[0]
                glyph_observation = b041_aigdt_glyph_observation(content, span.get("font"), paint_trace)
                paint_type = paint_trace.get("type")
                paint_opacity = paint_trace.get("opacity")
                paint_wmode = paint_trace.get("wmode")
                paint_layer = paint_trace.get("layer")
                if (
                    paint_type not in (0, 1)
                    or not isinstance(paint_opacity, (int, float))
                    or not math.isfinite(float(paint_opacity))
                    or paint_opacity <= 0
                    or paint_wmode != 0
                ):
                    continue
                deferred_fills: list[bool] = []
                blocked = any(
                    has_later_paint_overlap(
                        trace, member_trace_order_ids, span.get("size"), deferred_fills=deferred_fills,
                    )
                    for trace in member_traces
                )
                if blocked and not deferred_fills:
                    continue
                corners = [
                    fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x1, rect.y0),
                    fitz.Point(rect.x1, rect.y1), fitz.Point(rect.x0, rect.y1),
                ]
                mapped = [point * source_page.rotation_matrix for point in corners]
                x0 = (min(point.x for point in mapped) - displayed.x0) * scale_x
                y0 = (min(point.y for point in mapped) - displayed.y0) * scale_y
                x1 = (max(point.x for point in mapped) - displayed.x0) * scale_x
                y1 = (max(point.y for point in mapped) - displayed.y0) * scale_y
                if x0 < 0 or y0 < 0 or x1 > render_width or y1 > render_height or x1 <= x0 or y1 <= y0:
                    continue
                origin = span.get("origin")
                source_origin = None
                if isinstance(origin, (list, tuple)) and len(origin) == 2:
                    values = [float(value) for value in origin]
                    if all(math.isfinite(value) for value in values):
                        source_origin = values
                font_size = span.get("size")
                source_font_size = float(font_size) if isinstance(font_size, (int, float)) and math.isfinite(font_size) and font_size > 0 else None
                font_name = span.get("font")
                source_paint_evidence = {
                    "type": paint_type,
                    "opacity": float(paint_opacity),
                    "wmode": paint_wmode,
                    "layer": paint_layer or None,
                    "sequence_number": paint_trace.get("seqno"),
                    "member_sequence_numbers": sorted(member_sequences),
                    "member_traces": member_paint_evidence,
                    "bbox_pt": [float(value) for value in paint_trace["bbox"]],
                }
                if isinstance(paint_trace.get("_source_character_range"), (tuple, list)):
                    source_paint_evidence["aggregate_trace_bbox_pt"] = list(paint_trace["_aggregate_trace_bbox"])
                records.append({
                    "id": f"native-pdf-p{page_number:02d}-b{block_index:03d}-l{line_index:03d}-s{span_index:03d}",
                    "content": trace_text if text_agreement == "trace_recovered_replacement_characters" else content,
                    "source_text_agreement": text_agreement,
                    "bbox_px": [x0, y0, x1, y1],
                    "rotation_deg": math.degrees(math.atan2(float(direction[1]), float(direction[0]))),
                    "source_wmode": writing_mode,
                    "evidence_kind": "native_pdf",
                    "visibility": "unverified",
                    "source_span_bbox_pt": [float(value) for value in bbox],
                    "source_paint_evidence": source_paint_evidence,
                    "source_origin_pt": source_origin,
                    "source_font_name": str(font_name) if isinstance(font_name, str) else None,
                    "source_font_size_pt": source_font_size,
                    "source_sha256": source_sha256,
                    "render_sha256": render_sha256,
                    "mapping_version": "displayed-page-box-v1",
                    "semantic_role": None,
                })
                if glyph_observation is not None:
                    records[-1].update(glyph_observation)
                if deferred_fills:
                    pending_fill_checks[len(records) - 1] = (member_traces, member_trace_order_ids, font_size)

    # Preserve source order and finish the original stroke traversal before optional fill work.
    rejected = {
        index for index, (traces, trace_ids, font_size) in pending_fill_checks.items()
        if any(has_later_paint_overlap(trace, trace_ids, font_size) for trace in traces)
    }
    return [record for index, record in enumerate(records) if index not in rejected]


def run_fidelity_text_observations(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    *,
    workspace_root: Path,
    region_approval_path: Path | None = None,
) -> list[Path]:
    """Write hash-bound OCR candidates for later per-text review, never DXF text."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    approved_regions_by_page: dict[int, list[dict[str, Any]]] = {}
    region_approval_record: dict[str, str] | None = None
    if region_approval_path is not None:
        page_number, selected = _approved_region_selection(output_root, manifest, region_approval_path)
        approved_regions_by_page[page_number] = selected
        region_approval_record = _artifact(region_approval_path, output_root)
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
        native_candidates: list[dict[str, Any]] = []
        source_document = fitz.open(source)
        try:
            page_number = page.get("page")
            if type(page_number) is not int or page_number < 1 or page_number > len(source_document):
                raise FidelityError("Native PDF text mapping has invalid manifest page metadata.")
            source_page = source_document[page_number - 1]
            source_page_audit = audit.get("source_page", {})
            rendered_path = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
            rendered_image = cv2.imread(str(rendered_path))
            if rendered_image is None:
                raise FidelityError("Native PDF text mapping cannot read the rendered page.")
            render_sha256 = sha256_file(rendered_path)
            render_width = source_page_audit.get("render_width_px")
            render_height = source_page_audit.get("render_height_px")
            if source_page.get_text("text").strip() and (
                type(source_page_audit.get("page")) is not int
                or source_page_audit.get("page") != page_number
                or source_page_audit.get("render_sha256") != render_sha256
                or type(render_width) is not int or type(render_height) is not int
                or render_width <= 0 or render_height <= 0
                or rendered_image.shape[1] != render_width
                or rendered_image.shape[0] != render_height
            ):
                raise FidelityError("Native PDF text mapping is missing current render provenance.")
            native_candidates = _native_pdf_text_span_records(
                source_page,
                page_number,
                manifest["source"]["sha256"],
                render_sha256,
                int(render_width),
                int(render_height),
                manifest.get("configuration", {}).get("transform"),
            )
        finally:
            source_document.close()
        approved_region_ocr: dict[str, Any] | None = None
        if page["page"] in approved_regions_by_page:
            rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
            image = cv2.imread(str(rendered))
            if image is None:
                raise FidelityError("Cannot read rendered page for approved-region text observation.")
            extra_candidates, stats = _approved_region_text_candidates(
                image, approved_regions_by_page[page["page"]],
            )
            candidates.extend(extra_candidates)
            approved_region_ocr = {
                "regions": [region["id"] for region in approved_regions_by_page[page["page"]]],
                "rotations_deg": [0, 90],
                **stats,
            }
        output = output_root / "fidelity_text_observations" / f"page_{page['page']:02d}.json"
        if output.exists():
            raise FidelityError(f"Fidelity text observation already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "fidelity-text-observation-1.0",
            "private_artifact": True,
            "state": "needs_human_approval" if candidates or native_candidates else "not_evaluated",
            "source": manifest["source"],
            "page": page["page"],
            "source_layout_audit": audit_record,
            "candidates": candidates,
            "native_pdf_spans": native_candidates,
            "unresolved": ["no OCR candidate is emitted as DXF TEXT or MTEXT without per-text approval and a Unicode glyph-render check"],
        }
        if native_candidates:
            payload["unresolved"].append(
                "native PDF spans are separate unverified evidence; they are not OCR approval or reconstruction candidates"
            )
        if region_approval_record is not None and page["page"] in approved_regions_by_page:
            payload["region_approval"] = region_approval_record
            payload["approved_region_ocr"] = approved_region_ocr
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def run_fidelity_table_text_observations(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> list[Path]:
    """OCR only previously observed table cells; preserve every result as review-only evidence."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    _configure_tesseract(None)
    base_root = output_root / "fidelity_table_text_observations"
    observation_root = base_root
    revision = 2
    while observation_root.exists() and any(observation_root.iterdir()):
        observation_root = output_root / f"fidelity_table_text_observations-r{revision}"
        revision += 1
    outputs: list[Path] = []
    for page in manifest.get("pages", []):
        number = page["page"]
        observation_path = output_root / "fidelity_observations" / f"page_{number:02d}.json"
        if not observation_path.is_file():
            raise FidelityError(f"Missing table observation for page {number}; run fidelity-observe first.")
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        table = observation.get("table_grid", {})
        cells = table.get("cells", []) if observation.get("state") == "needs_review" else []
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        image = cv2.imread(str(rendered))
        if image is None:
            raise FidelityError("Cannot read rendered page for table-cell OCR.")
        candidates = []
        roi = table.get("roi_px")
        if cells and isinstance(roi, list) and len(roi) == 4:
            recognized = extract_text_tesseract(
                image, roi_boxes=[tuple(int(v) for v in roi)], min_confidence=20, psm=6,
            )
            for text in recognized:
                x0, y0, x1, y1 = text.bbox_px
                center_x, center_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                matches = [
                    (index, bbox) for index, bbox in enumerate(cells)
                    if isinstance(bbox, list) and len(bbox) == 4 and bbox[0] <= center_x <= bbox[2] and bbox[1] <= center_y <= bbox[3]
                ]
                candidates.append({
                    "cell_index": matches[0][0] if len(matches) == 1 else None,
                    "cell_bbox_px": matches[0][1] if len(matches) == 1 else None,
                    "text": _raw_text_payload(text),
                    "cell_match_state": "matched" if len(matches) == 1 else "needs_review",
                })
        output = observation_root / f"page_{number:02d}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "fidelity-table-text-observation-1.0",
            "private_artifact": True,
            "state": "needs_human_approval" if candidates else "not_evaluated",
            "source": manifest["source"],
            "page": number,
            "source_render_sha256": sha256_file(rendered),
            "source_table_observation": _artifact(observation_path, output_root),
            "candidates": candidates,
            "unresolved": ["no table-cell OCR candidate is emitted as DXF text or a table entity without per-cell approval"],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def write_fidelity_table_text_approval(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    page_number: int,
    observation_path: Path,
    candidate_ids: list[str],
    approval_reference: str,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    """Record explicit approval for matched table-cell OCR candidates."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(observation_path, output_root) or not observation_path.is_file():
        raise FidelityError("Table text observation must reside inside the private fidelity output root.")
    if not isinstance(page_number, int) or not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
        raise FidelityError("Table text approval requires unique candidate ids and a page number.")
    if not approval_reference.strip():
        raise FidelityError("Table text approval requires a non-empty approval reference.")
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Table text observation is invalid JSON.") from exc
    if (
        observation.get("schema_version") != "fidelity-table-text-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("state") != "needs_human_approval"
        or observation.get("source") != manifest.get("source")
        or observation.get("page") != page_number
    ):
        raise FidelityError("Table text observation is not valid for approval.")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Table text approval page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Table text observation does not match the rendered page.")
    candidates = {item.get("id"): item for item in observation.get("candidates", []) if isinstance(item, dict)}
    for candidate_id in candidate_ids:
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise FidelityError(f"Unknown table text candidate: {candidate_id}")
        if candidate.get("cell_match_state") != "matched":
            raise FidelityError(f"Table text candidate is not a matched cell: {candidate_id}")
    output = output_root / "fidelity_table_text_approvals" / f"page_{page_number:02d}.json"
    if output.exists():
        raise FidelityError(f"Table text approval already exists: {output}")
    payload = {
        "schema_version": "fidelity-table-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-table-text-candidates",
        "source": manifest["source"],
        "page": page_number,
        "observation": _artifact(observation_path, output_root),
        "approval_reference": approval_reference.strip(),
        "approved_candidate_ids": candidate_ids,
        "unresolved": [
            "table text placement, height, and style remain reviewable",
            "no table entity or production AutoCAD mutation",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def run_fidelity_table_text_reconstruct(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
    base_dxf: Path,
    *,
    workspace_root: Path,
) -> Path:
    """Emit only explicitly approved table-cell OCR into a private fidelity DXF."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Table text approval must reside inside the private fidelity output root.")
    if not _is_within(base_dxf, output_root) or not base_dxf.is_file():
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Table text approval is invalid JSON.") from exc
    if (
        approval.get("schema_version") != "fidelity-table-text-approval-1.0"
        or approval.get("private_artifact") is not True
        or approval.get("state") != "approved-table-text-candidates"
        or approval.get("source") != manifest.get("source")
    ):
        raise FidelityError("Table text approval has an unsupported schema.")
    observation_record = approval.get("observation")
    if not isinstance(observation_record, dict):
        raise FidelityError("Table text approval is missing observation provenance.")
    observation_path = _safe_artifact_path(output_root, observation_record)
    if sha256_file(observation_path) != observation_record.get("sha256"):
        raise FidelityError("Table text observation no longer matches its approval hash.")
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    if (
        observation.get("schema_version") != "fidelity-table-text-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("source") != manifest.get("source")
        or observation.get("page") != approval.get("page")
    ):
        raise FidelityError("Table text observation does not match its approval.")
    page_number = approval.get("page")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Table text observation page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Table text observation does not match the rendered page.")
    approved_ids = approval.get("approved_candidate_ids")
    if not isinstance(approved_ids, list) or not approved_ids or len(set(approved_ids)) != len(approved_ids):
        raise FidelityError("Table text approval requires unique candidate ids.")
    candidates_by_id = {
        candidate.get("id"): candidate
        for candidate in observation.get("candidates", [])
        if isinstance(candidate, dict)
    }
    audit = json.loads(_safe_artifact_path(output_root, page["artifacts"]["layout_audit"]).read_text(encoding="utf-8"))
    height_px = int(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    import ezdxf

    document = ezdxf.readfile(base_dxf)
    model = document.modelspace()
    emitted = 0
    for candidate_id in approved_ids:
        candidate = candidates_by_id.get(candidate_id)
        if not isinstance(candidate, dict) or candidate.get("cell_match_state") != "matched":
            raise FidelityError(f"Table text approval references an unmatched candidate: {candidate_id}")
        text = candidate.get("text", {})
        content, bbox = text.get("content"), text.get("bbox_px") if isinstance(text, dict) else (None, None)
        if not isinstance(content, str) or not content.strip() or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        x0, _, _, y1 = (float(value) for value in bbox)
        height = max(1.5, min(8.0, (float(bbox[3]) - float(bbox[1])) * scale))
        entity = model.add_text(content.strip(), dxfattribs={"layer": "FIDELITY_TABLE_TEXT", "height": height, "style": _ensure_unicode_text_style(document)})
        entity.set_placement((x0 * scale, (height_px - y1) * scale))
        emitted += 1
    base_root = output_root / "table_text_reconstruction"
    revision = 2
    while (base_root / f"page_{page_number:02d}").exists():
        base_root = output_root / f"table_text_reconstruction-r{revision}"
        revision += 1
    root = base_root / f"page_{page_number:02d}"
    root.mkdir(parents=True)
    output = root / "layout.dxf"
    document.saveas(output)
    (root / "report.json").write_text(json.dumps({"state": "needs_review", "profile": "fidelity-layout-table-text", "source_render_sha256": sha256_file(rendered), "approval_sha256": sha256_file(approval_path), "observation_sha256": sha256_file(observation_path), "base_dxf_sha256": sha256_file(base_dxf), "emitted_text_entities": emitted, "unresolved": ["table OCR text is candidate-only and requires visual review", "unmatched OCR is intentionally excluded"]}, indent=2) + "\n", encoding="utf-8")
    return output


_DIMENSION_VALUE = re.compile(r"^(?:[Ø⌀Rr]\s*)?\d+(?:[.,]\d+)?(?:\s*(?:mm|cm|m|°))?$")


def run_fidelity_dimension_observations(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> list[Path]:
    """Write review-only dimension-like OCR candidates with nearby line evidence."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    base_root = output_root / "fidelity_dimension_observations"
    observation_root = base_root
    revision = 2
    while observation_root.exists() and any(observation_root.iterdir()):
        observation_root = output_root / f"fidelity_dimension_observations-r{revision}"
        revision += 1
    outputs: list[Path] = []
    for page in manifest.get("pages", []):
        number = page["page"]
        text_path = output_root / "fidelity_text_observations" / f"page_{number:02d}.json"
        if not text_path.is_file():
            raise FidelityError(f"Missing text observation for page {number}; run fidelity-text-observe first.")
        text_observation = json.loads(text_path.read_text(encoding="utf-8"))
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        image = cv2.imread(str(rendered))
        if image is None:
            raise FidelityError("Cannot read rendered page for dimension observation.")
        raw = extract_raw_geometry(image, preset="real_scan_tuned_v1")
        candidates = []
        for text in text_observation.get("candidates", []):
            content = str(text.get("content", "")).strip()
            if not _DIMENSION_VALUE.fullmatch(content):
                continue
            x0, y0, x1, y1 = (float(value) for value in text["bbox_px"])
            nearby_lines = [
                {
                    "id": line.id,
                    "p1_px": [line.p1_px[0], line.p1_px[1]],
                    "p2_px": [line.p2_px[0], line.p2_px[1]],
                    "bbox_px": list(line.bbox_px),
                    "length_px": line.length_px(),
                }
                for line in raw.lines
                if line.bbox_px[0] <= x1 + 30 and line.bbox_px[2] >= x0 - 30
                and line.bbox_px[1] <= y1 + 30 and line.bbox_px[3] >= y0 - 30
            ][:12]
            candidates.append({
                "text": text,
                "nearby_line_ids": [line["id"] for line in nearby_lines],
                "nearby_lines": nearby_lines,
                "state": "needs_human_approval",
            })
        output = observation_root / f"page_{number:02d}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "fidelity-dimension-observation-1.0", "private_artifact": True, "state": "needs_human_approval" if candidates else "not_evaluated", "source": manifest["source"], "page": number, "source_render_sha256": sha256_file(rendered), "source_text_observation": _artifact(text_path, output_root), "candidates": candidates, "unresolved": ["no candidate is emitted as a DXF DIMENSION without explicit mapping approval"]}
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    return outputs


def run_fidelity_dimension_reconstruct(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
    base_dxf: Path,
    *,
    workspace_root: Path,
) -> Path:
    """Emit explicitly approved linear dimension observations into a private DXF."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Dimension approval must reside inside the private fidelity output root.")
    if not _is_within(base_dxf, output_root) or not base_dxf.is_file():
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Dimension approval is invalid JSON.") from exc
    if (
        approval.get("schema_version") != "fidelity-dimension-approval-1.0"
        or approval.get("private_artifact") is not True
        or approval.get("state") != "approved-dimension-mappings"
        or approval.get("source") != manifest.get("source")
        or not str(approval.get("approval_reference", "")).strip()
    ):
        raise FidelityError("Dimension approval has an unsupported or incomplete schema.")

    page_number = approval.get("page")
    if not isinstance(page_number, int):
        raise FidelityError("Dimension approval page must be an integer.")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Approved dimension page is absent from the fidelity manifest.")

    def resolve_hash_bound_artifact(record: object, label: str) -> Path:
        if not isinstance(record, dict):
            raise FidelityError(f"Dimension approval is missing {label} provenance.")
        relative = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(relative, str) or Path(relative).is_absolute() or not isinstance(expected_hash, str):
            raise FidelityError(f"Dimension approval {label} provenance is invalid.")
        path = (output_root / relative).resolve()
        if not _is_within(path, output_root) or not path.is_file():
            raise FidelityError(f"Dimension approval {label} is outside or missing.")
        if sha256_file(path) != expected_hash:
            raise FidelityError(f"Dimension approval {label} no longer matches its hash.")
        return path

    observation_path = resolve_hash_bound_artifact(approval.get("observation"), "observation")
    approved_base = resolve_hash_bound_artifact(approval.get("base_dxf"), "base DXF")
    if approved_base.resolve() != base_dxf.resolve():
        raise FidelityError("Dimension approval base DXF does not match the requested base DXF.")

    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Dimension observation is invalid JSON.") from exc
    if (
        observation.get("schema_version") != "fidelity-dimension-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("source") != manifest.get("source")
        or observation.get("page") != page_number
    ):
        raise FidelityError("Dimension observation does not match the approval.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Dimension observation does not match the rendered page.")

    candidates = {
        item.get("text", {}).get("id"): item
        for item in observation.get("candidates", [])
        if isinstance(item, dict) and isinstance(item.get("text"), dict)
    }
    mappings = approval.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise FidelityError("Dimension approval requires at least one mapping.")
    selected: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    candidate_ids: set[str] = set()
    line_ids: set[str] = set()
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise FidelityError("Dimension approval mappings must be objects.")
        candidate_id = mapping.get("candidate_id")
        line_evidence_id = mapping.get("line_evidence_id")
        if not isinstance(candidate_id, str) or not isinstance(line_evidence_id, str):
            raise FidelityError("Dimension mapping requires candidate_id and line_evidence_id.")
        if candidate_id in candidate_ids or line_evidence_id in line_ids:
            raise FidelityError("Dimension mappings must not reuse candidates or line evidence.")
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise FidelityError(f"Unknown dimension candidate: {candidate_id}")
        if mapping.get("dimension_kind", "linear") != "linear":
            raise FidelityError("Only linear dimension mappings are supported.")
        evidence = next((
            item for item in candidate.get("nearby_lines", [])
            if isinstance(item, dict) and item.get("id") == line_evidence_id
        ), None)
        if evidence is None:
            raise FidelityError(f"Unknown line evidence for dimension candidate: {line_evidence_id}")
        candidate_ids.add(candidate_id)
        line_ids.add(line_evidence_id)
        selected.append((mapping, candidate, evidence))

    audit_path = _safe_artifact_path(output_root, page["artifacts"]["layout_audit"])
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    height_px = int(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    import ezdxf

    document = ezdxf.readfile(base_dxf)
    if "FIDELITY_DIMENSIONS" not in document.layers:
        document.layers.new("FIDELITY_DIMENSIONS", dxfattribs={"color": 2})
    model = document.modelspace()
    emitted: list[dict[str, Any]] = []
    for _, candidate, evidence in selected:
        p1_px = evidence.get("p1_px")
        p2_px = evidence.get("p2_px")
        bbox = candidate["text"].get("bbox_px")
        if (
            not isinstance(p1_px, list) or len(p1_px) != 2
            or not isinstance(p2_px, list) or len(p2_px) != 2
            or not isinstance(bbox, list) or len(bbox) != 4
        ):
            raise FidelityError("Dimension line evidence has invalid pixel geometry.")
        p1 = (float(p1_px[0]) * scale, (height_px - float(p1_px[1])) * scale)
        p2 = (float(p2_px[0]) * scale, (height_px - float(p2_px[1])) * scale)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise FidelityError("Dimension line evidence has zero length.")
        midpoint = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        normal = (-dy / length, dx / length)
        text_center_px = ((float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0)
        text_center = (text_center_px[0] * scale, (height_px - text_center_px[1]) * scale)
        source_signed_normal_distance = (
            normal[0] * (text_center[0] - midpoint[0])
            + normal[1] * (text_center[1] - midpoint[1])
        )
        location = (
            midpoint[0] + normal[0] * source_signed_normal_distance,
            midpoint[1] + normal[1] * source_signed_normal_distance,
        )
        text_value = candidate["text"].get("parsed_value")
        dimension_text = "<>"
        if text_value is not None:
            dimension_text = format(text_value, "g") if isinstance(text_value, (int, float)) else str(text_value)
        dimension = model.add_linear_dim(
            base=midpoint,
            p1=p1,
            p2=p2,
            location=location,
            angle=math.degrees(math.atan2(dy, dx)),
            text=dimension_text,
            dxfattribs={"layer": "FIDELITY_DIMENSIONS"},
        )
        dimension.render()
        emitted.append({
            "candidate_id": candidate["text"]["id"],
            "line_evidence_id": evidence["id"],
            "text_value": candidate["text"].get("parsed_value"),
            "measured_paper_length": length,
            "dimension_handle": dimension.dimension.dxf.handle,
        })

    root_base = output_root / "dimension_reconstruction"
    root = root_base / f"page_{page_number:02d}"
    revision = 2
    while root.exists():
        root = output_root / f"dimension_reconstruction-r{revision}" / f"page_{page_number:02d}"
        revision += 1
    root.mkdir(parents=True)
    output = root / "layout.dxf"
    document.saveas(output)
    report = {
        "state": "needs_review",
        "profile": "fidelity-layout-dimension",
        "page": page_number,
        "source": manifest["source"],
        "source_render_sha256": sha256_file(rendered),
        "observation_sha256": sha256_file(observation_path),
        "approval_sha256": sha256_file(approval_path),
        "base_dxf_sha256": sha256_file(base_dxf),
        "output_dxf_sha256": sha256_file(output),
        "emitted_dimension_entities": len(emitted),
        "mappings": emitted,
        "unresolved": [
            "native dimensions are a review candidate and require visual approval",
            "only linear dimensions are supported",
            "no model export or production AutoCAD mutation",
        ],
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def run_fidelity_linetype_reconstruct(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    observation_path: Path,
    base_dxf: Path,
    *,
    workspace_root: Path,
) -> Path:
    """Apply hash-bound horizontal dashed-pattern evidence to a private DXF clone."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(observation_path, output_root) or not observation_path.is_file():
        raise FidelityError("Linetype observation must reside inside the private fidelity output root.")
    if not _is_within(base_dxf, output_root) or not base_dxf.is_file():
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FidelityError("Linetype observation is invalid JSON.") from exc
    if observation.get("schema_version") != "fidelity-linetype-observation-1.0" or observation.get("private_artifact") is not True:
        raise FidelityError("Linetype observation has an unsupported schema.")
    page_number = observation.get("page")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Linetype observation page is absent from the fidelity manifest.")
    rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    if observation.get("source_render_sha256") != sha256_file(rendered):
        raise FidelityError("Linetype observation does not match the rendered page.")
    patterns = observation.get("patterns")
    if not isinstance(patterns, list):
        raise FidelityError("Linetype observation patterns are invalid.")
    audit_path = _safe_artifact_path(output_root, page["artifacts"]["layout_audit"])
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    height_px = int(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    linetype_specs = {
        "DASHED": ("FIDELITY_DASHED", [0.0, 4.0, -2.0]),
        "CENTER": ("FIDELITY_CENTER", [0.0, 4.0, -1.0, 1.0, -1.0]),
    }
    coordinates = [
        ((height_px - float(pattern["coordinate_px"])) * scale, linetype_specs[linetype][0])
        for pattern in patterns
        if isinstance(pattern, dict)
        and pattern.get("axis") == "horizontal"
        and isinstance(pattern.get("coordinate_px"), (int, float))
        and (linetype := str(pattern.get("suggested_linetype", "")).upper()) in linetype_specs
    ]
    import ezdxf

    document = ezdxf.readfile(base_dxf)
    required_linetype_names = {"FIDELITY_DASHED"} | {name for _, name in coordinates}
    for name, pattern in linetype_specs.values():
        if name in required_linetype_names and name not in document.linetypes:
            document.linetypes.add(name, pattern)
    tolerance_mm = max(0.25, 3.0 * scale)
    changed = 0
    for entity in document.modelspace().query("LINE"):
        start, end = entity.dxf.start, entity.dxf.end
        if abs(float(start.y) - float(end.y)) > tolerance_mm:
            continue
        linetype = next(
            (name for coordinate, name in coordinates if abs(float(start.y) - coordinate) <= tolerance_mm),
            None,
        )
        if linetype is not None:
            entity.dxf.linetype = linetype
            changed += 1
    base_root = output_root / "linetype_reconstruction"
    revision = 2
    while (base_root / f"page_{page_number:02d}").exists():
        base_root = output_root / f"linetype_reconstruction-r{revision}"
        revision += 1
    root = base_root / f"page_{page_number:02d}"
    root.mkdir(parents=True)
    output = root / "layout.dxf"
    document.saveas(output)
    report = {
        "state": "needs_review",
        "profile": "fidelity-layout-linetype",
        "page": page_number,
        "source_render_sha256": sha256_file(rendered),
        "observation_sha256": sha256_file(observation_path),
        "base_dxf_sha256": sha256_file(base_dxf),
        "output_dxf_sha256": sha256_file(output),
        "matched_horizontal_pattern_count": len(coordinates),
        "changed_line_entities": changed,
        "tolerance_mm": tolerance_mm,
        "unresolved": ["non-default linetype mapping is a fidelity candidate and needs visual review", "no model export"],
    }
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output


def write_fidelity_dimension_review_index(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> Path:
    """Write a private browser index for review-only dimension candidates."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    root = output_root / "fidelity_dimension_review"
    index = root / "index.html"
    revision = 2
    while index.exists():
        index = root / f"index-r{revision}.html"
        revision += 1
    cards = []
    for page in manifest.get("pages", []):
        path = output_root / "fidelity_dimension_observations" / f"page_{page['page']:02d}.json"
        if not path.is_file():
            raise FidelityError(f"Missing dimension observation for page {page['page']}; run fidelity-dimension-observe first.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        rows = "".join(f"<tr><td>{escape(str(item['text']['content']))}</td><td>{escape(str(item['text']['bbox_px']))}</td><td>{len(item['nearby_line_ids'])}</td></tr>" for item in payload.get("candidates", []))
        rel = Path(os.path.relpath(rendered, index.parent)).as_posix()
        cards.append(f"<section><h2>Trang {page['page']} <small>{len(payload.get('candidates', []))} ứng viên</small></h2><img src='{rel}' alt='Trang {page['page']}'><table><tr><th>Giá trị</th><th>Khung pixel</th><th>Nét gần</th></tr>{rows}</table></section>")
    root.mkdir(parents=True, exist_ok=True)
    index.write_text("<!doctype html><meta charset='utf-8'><title>Duyệt kích thước</title><style>body{font:15px system-ui;margin:20px;background:#f4f6f8}section{background:#fff;padding:16px;margin:14px 0;border-radius:10px}img{max-width:100%;border:1px solid #aaa}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{padding:7px;border-bottom:1px solid #ddd;text-align:left}small{font-weight:400;color:#667}</style><h1>Duyệt ứng viên kích thước</h1><p>Chỉ là quan sát; chưa tạo DXF DIMENSION.</p>" + "\n".join(cards), encoding="utf-8")
    return index


def _unicode_glyph_render_check(content: str) -> dict[str, Any]:
    """Prove each non-space codepoint has a non-replacement glyph in the approved font."""
    font_path = Path(os.environ.get("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\arial.ttf"))
    if not font_path.is_file():
        raise FidelityError(f"Fidelity Unicode glyph-render font is unavailable: {font_path}")
    try:
        font = ImageFont.truetype(str(font_path), size=32)
    except OSError as exc:
        raise FidelityError(f"Cannot load fidelity Unicode glyph-render font: {font_path}") from exc
    replacement = bytes(font.getmask("\ufffd"))
    unsupported = [char for char in content if not char.isspace() and (not any(font.getmask(char)) or bytes(font.getmask(char)) == replacement)]
    bounds = font.getbbox(content)
    image = Image.new("L", (max(1, bounds[2] - bounds[0] + 4), max(1, bounds[3] - bounds[1] + 4)))
    ImageDraw.Draw(image).text((2 - bounds[0], 2 - bounds[1]), content, font=font, fill=255)
    return {
        "passed": not unsupported and image.getbbox() is not None,
        "font": {"name": font_path.name, "sha256": sha256_file(font_path)},
        "unsupported_codepoints": [f"U+{ord(char):04X}" for char in unsupported],
        "rendered_nonempty": image.getbbox() is not None,
    }


def _fresh_fidelity_native_pdf_spans(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    page: dict[str, Any],
    observation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Re-render and re-extract native spans in the exact reviewed source frame."""
    page_number = page.get("page")
    dpi = manifest.get("configuration", {}).get("dpi")
    if type(page_number) is not int or page_number < 1 or type(dpi) is not int or dpi <= 0:
        raise FidelityError("Native PDF reconstruction requires valid page and render DPI metadata.")
    try:
        with fitz.open(source) as document:
            if page_number > len(document):
                raise FidelityError("Native PDF reconstruction page is absent from the source.")
            source_page = document[page_number - 1]
            pixmap = source_page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
            fresh_image = cv2.imdecode(np.frombuffer(pixmap.tobytes("png"), dtype=np.uint8), cv2.IMREAD_COLOR)
            if fresh_image is None:
                raise FidelityError("Native PDF reconstruction could not decode the fresh source render.")
            rendered_record = page.get("artifacts", {}).get("rendered_png")
            rendered_path = _safe_artifact_path(output_root, rendered_record)
            stored_image = cv2.imread(str(rendered_path))
            if stored_image is None or stored_image.shape != fresh_image.shape or not np.array_equal(stored_image, fresh_image):
                raise FidelityError("Native PDF source render no longer matches the reviewed pixels.")
            audit_record = page.get("artifacts", {}).get("layout_audit")
            audit_path = _safe_artifact_path(output_root, audit_record)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            source_audit = audit.get("source_page", {})
            if (
                type(source_audit.get("page")) is not int
                or source_audit.get("page") != page_number
                or source_audit.get("render_width_px") != fresh_image.shape[1]
                or source_audit.get("render_height_px") != fresh_image.shape[0]
                or source_audit.get("render_sha256") != sha256_file(rendered_path)
                or observation.get("source_layout_audit") != audit_record
            ):
                raise FidelityError("Native PDF source render does not match its audited page frame.")
            fresh = _native_pdf_text_span_records(
                source_page,
                page_number,
                manifest["source"]["sha256"],
                sha256_file(rendered_path),
                fresh_image.shape[1],
                fresh_image.shape[0],
                manifest.get("configuration", {}).get("transform"),
            )
    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, FidelityError):
            raise
        raise FidelityError("Could not freshly validate native PDF text spans.") from exc
    observed = observation.get("native_pdf_spans")
    if not isinstance(observed, list) or observed != fresh:
        raise FidelityError("Native PDF spans no longer match the exact source and reviewed render.")
    return fresh


def _fidelity_text_bbox(record: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = record.get("bbox_px")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise FidelityError("Mixed OCR/native text selection has invalid bounds.")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in bbox
    ):
        raise FidelityError("Mixed OCR/native text selection has invalid bounds.")
    x0, y0, x1, y1 = (float(value) for value in bbox)
    if x1 <= x0 or y1 <= y0:
        raise FidelityError("Mixed OCR/native text selection has invalid bounds.")
    return x0, y0, x1, y1


def _fidelity_text_boxes_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return (
        max(left[0], right[0]) < min(left[2], right[2])
        and max(left[1], right[1]) < min(left[3], right[3])
    )


def write_fidelity_text_approval(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    page_number: int,
    observation_path: Path,
    candidate_ids: list[str],
    approval_reference: str,
    *,
    workspace_root: Path,
    native_span_ids: list[str] | None = None,
    native_span_reviews: list[dict[str, Any]] | None = None,
    selection_path: Path | None = None,
) -> dict[str, Any]:
    """Record explicit OCR or typed native-span approvals after glyph checks."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(observation_path, output_root) or not observation_path.is_file():
        raise FidelityError("Text observation must reside inside the private fidelity output root.")
    native_span_ids = native_span_ids or []
    native_span_reviews = native_span_reviews or []
    if (
        (not candidate_ids and not native_span_ids)
        or any(not isinstance(item, str) for item in candidate_ids)
        or any(not isinstance(item, str) for item in native_span_ids)
        or len(set(candidate_ids)) != len(candidate_ids)
        or len(set(native_span_ids)) != len(native_span_ids)
    ):
        raise FidelityError("Text approval requires one or more unique typed item ids.")
    if not approval_reference.strip():
        raise FidelityError("Text approval requires a non-empty approval reference.")
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    if observation.get("state") != "needs_human_approval" or observation.get("source") != manifest.get("source"):
        raise FidelityError("Text observation is not valid for approval.")
    if observation.get("page") != page_number:
        raise FidelityError("Text approval page does not match its observation.")
    candidates = {item.get("id"): item for item in observation.get("candidates", []) if isinstance(item, dict)}
    if any(candidate_id not in candidates for candidate_id in candidate_ids):
        raise FidelityError("Text approval references an unknown OCR candidate.")
    approved_candidates = []
    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        glyph_render = _unicode_glyph_render_check(candidate["content"])
        if not glyph_render["passed"]:
            raise FidelityError(f"Unicode glyph-render check failed for OCR candidate: {candidate_id}")
        approved_candidates.append({"candidate": candidate, "glyph_render": glyph_render})
    approved_native_spans = []
    native_selection_artifact = None
    if native_span_ids:
        if selection_path is None or not _is_within(selection_path, output_root) or not selection_path.is_file():
            raise FidelityError("Native PDF text approval requires its private source-bound selection artifact.")
        try:
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FidelityError("Native PDF text selection is invalid JSON.") from exc
        page_selection = next((item for item in selection.get("selections", []) if isinstance(item, dict) and item.get("page") == page_number), None)
        if (
            not isinstance(selection, dict)
            or selection.get("schema_version") != "fidelity-text-selection-1.0"
            or selection.get("source") != manifest.get("source")
            or not isinstance(page_selection, dict)
            or page_selection.get("native_span_ids") != native_span_ids
            or page_selection.get("native_span_reviews") != native_span_reviews
        ):
            raise FidelityError("Native PDF text selection does not match its source-bound page review.")
        native_candidates = {
            item.get("id"): item
            for item in observation.get("native_pdf_spans", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if candidate_ids:
            for candidate_id in candidate_ids:
                candidate = candidates[candidate_id]
                candidate_bbox = _fidelity_text_bbox(candidate)
                for span_id in native_span_ids:
                    span = native_candidates.get(span_id)
                    if span is None:
                        raise FidelityError("Text approval references an unknown native PDF span.")
                    span_bbox = _fidelity_text_bbox(span)
                    if _fidelity_text_boxes_overlap(candidate_bbox, span_bbox):
                        raise FidelityError(
                            "overlapping OCR and native PDF text selections require separate adjudication."
                        )
        reviews_by_id: dict[str, dict[str, Any]] = {}
        for review in native_span_reviews:
            span = review.get("span") if isinstance(review, dict) else None
            span_id = span.get("id") if isinstance(span, dict) else None
            if not isinstance(span_id, str) or span_id in reviews_by_id:
                raise FidelityError("Native PDF text selection contains an invalid or duplicate reviewed span.")
            reviews_by_id[span_id] = review
        if set(reviews_by_id) != set(native_span_ids):
            raise FidelityError("Native PDF text selection must review every selected span exactly once.")
        selection_record = _artifact(selection_path, output_root)
        native_selection_artifact = selection_record
        for span_id in native_span_ids:
            span = native_candidates.get(span_id)
            review = reviews_by_id[span_id]
            if (
                span is None
                or review.get("span") != span
                or review.get("visible_and_legible") is not True
                or span.get("evidence_kind") != "native_pdf"
                or span.get("visibility") != "unverified"
                or span.get("source_sha256") != manifest["source"].get("sha256")
                or not isinstance(span.get("render_sha256"), str)
                or span.get("mapping_version") != "displayed-page-box-v1"
            ):
                raise FidelityError("Native PDF text selection does not bind an explicitly reviewed current source span.")
            content = span.get("content")
            if not isinstance(content, str) or not content.strip():
                raise FidelityError("Native PDF text selection contains invalid text content.")
            glyph_render = _unicode_glyph_render_check(content)
            if not glyph_render["passed"]:
                raise FidelityError(f"Unicode glyph-render check failed for native PDF span: {span_id}")
            span_sha256 = hashlib.sha256(
                json.dumps(span, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            approved_native_spans.append({
                "span": span,
                "glyph_render": glyph_render,
                "visibility_review": {
                    "decision": "visible_and_legible",
                    "source_sha256": span["source_sha256"],
                    "render_sha256": span["render_sha256"],
                    "span_id": span_id,
                    "span_sha256": span_sha256,
                    "selection": selection_record,
                },
            })
    output = output_root / "fidelity_text_approvals" / f"page_{page_number:02d}.json"
    payload = {
        "schema_version": "fidelity-text-approval-2.0" if native_span_ids else "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-items-only" if native_span_ids else "approved-text-candidates-only",
        "source": manifest["source"],
        "page": page_number,
        "observation": _artifact(observation_path, output_root),
        "approval_reference": approval_reference.strip(),
        "approved_candidates": approved_candidates,
        "unresolved": ["approved text items are not emitted into DXF by this command", "text placement, height, style, and DXF emission require the existing reconstruction step"],
    }
    if native_span_ids:
        payload["approved_native_spans"] = approved_native_spans
        payload["native_selection"] = native_selection_artifact
        payload["unresolved"].append("native span visibility is an explicit item review bound to the selected source, render, and span; no semantic role or association is inferred")
    try:
        with pin_directory_chain(output.parent.absolute()):
            if not _is_within(output.parent, output_root):
                raise FidelityError("Fidelity text approval output escaped the private root.")
            if output.exists():
                raise FidelityError(f"Fidelity text approval already exists: {output}")
            descriptor = os.open(
                output,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as approval_file:
                approval_file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileIdentityError as exc:
        raise FidelityError("Fidelity text approval output directory is unsafe.") from exc
    except FileExistsError as exc:
        raise FidelityError(f"Fidelity text approval already exists: {output}") from exc
    return payload


def write_fidelity_text_approvals_from_selection(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    selection_path: Path,
    approval_reference: str,
    *,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    """Apply an exported browser selection as separate, explicit per-page approvals."""
    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError(f"Cannot read text selection file: {selection_path}") from exc
    if (
        not isinstance(selection, dict)
        or selection.get("schema_version") != "fidelity-text-selection-1.0"
        or selection.get("source") != manifest.get("source")
    ):
        raise FidelityError("Text selection does not match the private fidelity source.")
    selections = selection.get("selections")
    if not isinstance(selections, list) or not selections:
        raise FidelityError("Text selection requires at least one page selection.")
    results = []
    for item in selections:
        if (
            not isinstance(item, dict)
            or type(item.get("page")) is not int
            or not isinstance(item.get("candidate_ids", []), list)
            or not isinstance(item.get("native_span_ids", []), list)
            or not isinstance(item.get("native_span_reviews", []), list)
        ):
            raise FidelityError("Text selection page records are invalid.")
        observation = output_root / "fidelity_text_observations" / f"page_{item['page']:02d}.json"
        results.append(write_fidelity_text_approval(
            source, output_root, manifest, item["page"], observation, item.get("candidate_ids", []), approval_reference,
            workspace_root=workspace_root,
            native_span_ids=item.get("native_span_ids", []),
            native_span_reviews=item.get("native_span_reviews", []),
            selection_path=selection_path if item.get("native_span_ids") else None,
        ))
    return results


def _measure_visible_glyph_bbox(image: np.ndarray, bbox: list[int]) -> list[int] | None:
    """Find a conservative visible-glyph band inside one OCR box.

    OCR boxes can include line spacing and nearby ruled-cell pixels.  A text
    band is accepted only when its strongest contiguous row run is separated
    from an OCR-box edge by a substantial margin; otherwise the original box
    remains the safer measurement.
    """
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x0, y0, x1, y1 = (int(round(value)) for value in bbox)
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0 or image is None or image.size == 0:
        return None
    page_height, page_width = image.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(page_width, x1), min(page_height, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    crop = gray[y0:y1, x0:x1]
    ink = crop < 180
    crop_height, crop_width = ink.shape
    row_counts = ink.sum(axis=1)
    row_threshold = max(3, int(round(crop_width * 0.03)))
    # A ruled border spanning most of the OCR box is not a glyph band.
    row_active = (row_counts >= row_threshold) & (row_counts < crop_width * 0.8)
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, active in enumerate(row_active):
        if active and start is None:
            start = index
        elif not active and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, crop_height))
    if not runs:
        return None
    band_start, band_end = max(runs, key=lambda item: (item[1] - item[0], int(row_counts[item[0]:item[1]].sum())))
    top_margin = band_start
    bottom_margin = crop_height - band_end
    if max(top_margin, bottom_margin) < max(2, math.ceil(crop_height * 0.25)):
        return [x0, y0, x1, y1]
    band = ink[band_start:band_end]
    columns = np.where(band.any(axis=0))[0]
    if columns.size == 0:
        return None
    return [x0 + int(columns[0]), y0 + band_start, x0 + int(columns[-1]) + 1, y0 + band_end]


def _derive_text_reconstruction_size(
    image: np.ndarray,
    content: str,
    bbox: list[int],
    scale: float,
    *,
    allow_tight_box_font_metric: bool = False,
) -> dict[str, Any]:
    """Map visible source glyph extents to DXF TEXT size without moving its anchor."""
    original = [int(round(value)) for value in bbox]
    original_height = max(1.5, min(10.0, (original[3] - original[1]) * scale))
    visible = _measure_visible_glyph_bbox(image, original)
    if visible is None or (visible == original and not allow_tight_box_font_metric):
        return {
            "glyph_bbox_px": original,
            "height_mm": original_height,
            "width_factor": 1.0,
            "insertion_px": [original[0], original[3]],
        }
    font_path = Path(os.environ.get("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\arial.ttf"))
    try:
        font = ImageFont.truetype(str(font_path), size=32)
        mask = font.getmask(content)
        mask_bbox = mask.getbbox()
    except (OSError, ValueError):
        mask_bbox = None
    visible_width = max(1, visible[2] - visible[0])
    visible_height = max(1, visible[3] - visible[1])
    if mask_bbox is None or mask_bbox[2] <= mask_bbox[0] or mask_bbox[3] <= mask_bbox[1]:
        width_factor = 1.0
    else:
        natural_width = visible_height * font.getlength(content) / max(1, mask_bbox[3] - mask_bbox[1])
        width_factor = max(0.5, min(2.0, visible_width / max(1.0, natural_width)))
    return {
        "glyph_bbox_px": visible,
        "height_mm": max(1.5, min(10.0, visible_height * scale)),
        "width_factor": width_factor,
        "insertion_px": [original[0], original[3]],
    }


def run_fidelity_text_reconstruct(
    source: Path,
    output_root: Path,
    manifest: dict[str, Any],
    approval_path: Path,
    *,
    base_dxf: Path | None = None,
    workspace_root: Path,
) -> Path:
    """Emit approved OCR and native PDF text as paper-coordinate TEXT."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    if not _is_within(approval_path, output_root) or not approval_path.is_file():
        raise FidelityError("Text approval must reside inside the private fidelity output root.")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Text approval is invalid JSON.") from exc
    schema_version = approval.get("schema_version") if isinstance(approval, dict) else None
    native_approval = schema_version == "fidelity-text-approval-2.0"
    if (
        not isinstance(approval, dict)
        or schema_version not in {"fidelity-text-approval-1.0", "fidelity-text-approval-2.0"}
        or approval.get("private_artifact") is not True
        or approval.get("state") != ("approved-text-items-only" if native_approval else "approved-text-candidates-only")
        or approval.get("source") != manifest.get("source")
        or not isinstance(approval.get("approval_reference"), str)
        or not approval["approval_reference"].strip()
    ):
        raise FidelityError("Text approval has an unsupported or incomplete schema.")
    page_number = approval.get("page")
    if type(page_number) is not int or page_number <= 0:
        raise FidelityError("Text approval page must be a positive integer.")
    page = next((item for item in manifest.get("pages", []) if item.get("page") == page_number), None)
    if page is None:
        raise FidelityError("Text approval page is absent from the fidelity manifest.")

    observation_record = approval.get("observation")
    if not isinstance(observation_record, dict):
        raise FidelityError("Text approval is missing hash-bound OCR observation provenance.")
    canonical_observation = output_root / "fidelity_text_observations" / f"page_{page_number:02d}.json"
    canonical_record_path = canonical_observation.resolve().relative_to(output_root.resolve()).as_posix()
    if observation_record.get("artifact") != canonical_record_path:
        raise FidelityError("Text approval must reference the canonical OCR observation.")
    observation_path = _safe_artifact_path(output_root, observation_record)
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FidelityError("Text observation is invalid JSON.") from exc
    if (
        not isinstance(observation, dict)
        or observation.get("schema_version") != "fidelity-text-observation-1.0"
        or observation.get("private_artifact") is not True
        or observation.get("state") != "needs_human_approval"
        or observation.get("source") != manifest.get("source")
        or type(observation.get("page")) is not int
        or observation.get("page") != page_number
        or observation.get("source_layout_audit") != page.get("artifacts", {}).get("layout_audit")
    ):
        raise FidelityError("Text observation does not match the approval source and page.")

    observation_candidates = observation.get("candidates")
    if not isinstance(observation_candidates, list):
        raise FidelityError("Text observation has no OCR candidate list.")
    ocr_candidates: dict[str, dict[str, Any]] = {}
    for item in observation_candidates:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise FidelityError("Text observation contains an invalid OCR candidate.")
        if item.get("source") != "text_tesseract":
            raise FidelityError("Text observation contains evidence that is not from the OCR path.")
        if item["id"] in ocr_candidates:
            raise FidelityError("Text observation contains duplicate OCR candidate ids.")
        ocr_candidates[item["id"]] = item
    approved_records = approval.get("approved_candidates")
    if not isinstance(approved_records, list) or (not approved_records and not native_approval):
        raise FidelityError("Text approval requires approved typed text items.")
    approved_candidates = []
    approved_ids: set[str] = set()
    if approved_records:
        fresh_candidates = _fresh_fidelity_ocr_candidates(source, output_root, manifest, page, observation)
        fresh_candidate_evidence = Counter(_ocr_candidate_evidence_key(item) for item in fresh_candidates)
    else:
        fresh_candidate_evidence = Counter()
    for approved in approved_records:
        candidate = approved.get("candidate") if isinstance(approved, dict) else None
        candidate_id = candidate.get("id") if isinstance(candidate, dict) else None
        if not isinstance(candidate_id, str) or candidate_id not in ocr_candidates:
            raise FidelityError("Text approval references an unknown OCR candidate.")
        if candidate_id in approved_ids or candidate != ocr_candidates[candidate_id]:
            raise FidelityError("Text approval candidate does not match its hash-bound OCR observation.")
        glyph_render = approved.get("glyph_render")
        content = candidate.get("content")
        if not isinstance(content, str) or not content.strip():
            raise FidelityError("Text approval contains an invalid OCR candidate.")
        evidence_key = _ocr_candidate_evidence_key(candidate)
        if fresh_candidate_evidence[evidence_key] <= 0:
            raise FidelityError("Text approval candidate does not match fresh OCR evidence from the source PDF.")
        fresh_candidate_evidence[evidence_key] -= 1
        current_glyph_render = _unicode_glyph_render_check(content)
        if (
            not isinstance(glyph_render, dict)
            or not current_glyph_render["passed"]
            or glyph_render != current_glyph_render
        ):
            raise FidelityError("Text approval is missing matching passing Unicode glyph-render evidence.")
        approved_ids.add(candidate_id)
        approved_candidates.append({"candidate": ocr_candidates[candidate_id], "glyph_render": glyph_render})

    approved_native: list[dict[str, Any]] = []
    native_to_emit: list[dict[str, Any]] = []
    if native_approval:
        native_records = approval.get("approved_native_spans")
        selection_record = approval.get("native_selection")
        if not isinstance(native_records, list) or not native_records or not isinstance(selection_record, dict):
            raise FidelityError("Native text approval requires selected spans and their reviewed selection artifact.")
        selection_path = _safe_artifact_path(output_root, selection_record)
        try:
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FidelityError("Native text selection artifact is invalid JSON.") from exc
        page_selections = [
            item for item in selection.get("selections", [])
            if isinstance(item, dict) and item.get("page") == page_number
        ] if isinstance(selection, dict) else []
        if (
            not isinstance(selection, dict)
            or selection.get("schema_version") != "fidelity-text-selection-1.0"
            or selection.get("source") != manifest.get("source")
            or len(page_selections) != 1
        ):
            raise FidelityError("Native text selection does not match its source and approval page.")
        fresh_native = _fresh_fidelity_native_pdf_spans(source, output_root, manifest, page, observation)
        native_by_id = {item["id"]: item for item in fresh_native}
        selected_ids = page_selections[0].get("native_span_ids")
        reviews = page_selections[0].get("native_span_reviews")
        selected_ocr_ids = page_selections[0].get("candidate_ids")
        if (
            not isinstance(selected_ocr_ids, list)
            or any(not isinstance(item, str) for item in selected_ocr_ids)
            or len(set(selected_ocr_ids)) != len(selected_ocr_ids)
            or set(selected_ocr_ids) != approved_ids
        ):
            raise FidelityError("Native text selection OCR ids do not match approved OCR candidates.")
        if (
            not isinstance(selected_ids, list)
            or not selected_ids
            or any(not isinstance(item, str) for item in selected_ids)
            or len(set(selected_ids)) != len(selected_ids)
            or not isinstance(reviews, list)
            or len(reviews) != len(selected_ids)
            or len(native_records) != len(selected_ids)
        ):
            raise FidelityError("Native text selection contains missing or duplicate span reviews.")
        reviews_by_id: dict[str, dict[str, Any]] = {}
        for review in reviews:
            span = review.get("span") if isinstance(review, dict) else None
            span_id = span.get("id") if isinstance(span, dict) else None
            if not isinstance(span_id, str) or span_id in reviews_by_id:
                raise FidelityError("Native text selection contains an invalid or duplicate span review.")
            reviews_by_id[span_id] = review
        approval_by_id: dict[str, dict[str, Any]] = {}
        for record in native_records:
            span = record.get("span") if isinstance(record, dict) else None
            span_id = span.get("id") if isinstance(span, dict) else None
            if not isinstance(span_id, str) or span_id in approval_by_id:
                raise FidelityError("Native text approval contains an invalid or duplicate span.")
            approval_by_id[span_id] = record
        if set(selected_ids) != set(reviews_by_id) or set(selected_ids) != set(approval_by_id):
            raise FidelityError("Native text approval does not match every explicitly selected span.")
        for span_id in selected_ids:
            span = native_by_id.get(span_id)
            review = reviews_by_id[span_id]
            record = approval_by_id[span_id]
            visibility = record.get("visibility_review")
            content = span.get("content") if isinstance(span, dict) else None
            glyph_render = record.get("glyph_render")
            expected_span_sha256 = hashlib.sha256(
                json.dumps(span, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest() if isinstance(span, dict) else None
            current_glyph_render = _unicode_glyph_render_check(content) if isinstance(content, str) else None
            if (
                span is None
                or record.get("span") != span
                or review.get("span") != span
                or review.get("visible_and_legible") is not True
                or not isinstance(visibility, dict)
                or visibility.get("decision") != "visible_and_legible"
                or visibility.get("source_sha256") != manifest["source"].get("sha256")
                or visibility.get("render_sha256") != span.get("render_sha256")
                or visibility.get("span_id") != span_id
                or visibility.get("span_sha256") != expected_span_sha256
                or visibility.get("selection") != selection_record
                or span.get("evidence_kind") != "native_pdf"
                or span.get("visibility") != "unverified"
                or not isinstance(span.get("source_origin_pt"), list)
                or len(span["source_origin_pt"]) != 2
                or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in span["source_origin_pt"])
                or not isinstance(span.get("source_font_size_pt"), (int, float))
                or not math.isfinite(span["source_font_size_pt"])
                or span["source_font_size_pt"] <= 0
                or not isinstance(span.get("rotation_deg"), (int, float))
                or not math.isfinite(span["rotation_deg"])
                or not isinstance(content, str)
                or not content.strip()
                or not isinstance(glyph_render, dict)
                or current_glyph_render is None
                or not current_glyph_render["passed"]
                or glyph_render != current_glyph_render
            ):
                raise FidelityError("Native text approval is stale, unsupported, unselected, or missing current glyph evidence.")
            approved_native.append({"span": span, "glyph_render": glyph_render})
        for approved_ocr in approved_candidates:
            ocr_bbox = _fidelity_text_bbox(approved_ocr["candidate"])
            for approved_span in approved_native:
                if _fidelity_text_boxes_overlap(ocr_bbox, _fidelity_text_bbox(approved_span["span"])):
                    raise FidelityError("OCR and native PDF text overlap and cannot be reconstructed together.")
        audit_path = _safe_artifact_path(output_root, page["artifacts"]["layout_audit"])
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        render_width = audit.get("source_page", {}).get("render_width_px")
        render_height = audit.get("source_page", {}).get("render_height_px")
        scale = page.get("pixel_to_paper_mm", {}).get("used")
        if (
            type(render_width) is not int or render_width <= 0
            or type(render_height) is not int or render_height <= 0
            or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0
        ):
            raise FidelityError("Native text reconstruction has an invalid audited page scale.")
        with fitz.open(source) as source_document:
            if page_number > len(source_document):
                raise FidelityError("Native text reconstruction page is absent from the source.")
            displayed = source_document[page_number - 1].rect
            if displayed.width <= 0 or displayed.height <= 0:
                raise FidelityError("Native text reconstruction has an invalid source page frame.")
            scale_x = render_width / displayed.width
            scale_y = render_height / displayed.height
            for approved in approved_native:
                span = approved["span"]
                origin_x, origin_y = span["source_origin_pt"]
                direction = math.radians(float(span["rotation_deg"]))
                dx = math.cos(direction) * scale_x
                dy = math.sin(direction) * scale_y
                insertion = (
                    (origin_x - displayed.x0) * scale_x * float(scale),
                    (render_height - (origin_y - displayed.y0) * scale_y) * float(scale),
                )
                height_mm = float(span["source_font_size_pt"]) * scale_y * float(scale)
                rotation_deg = math.degrees(math.atan2(-dy, dx))
                if (
                    not all(math.isfinite(value) for value in (*insertion, height_mm, rotation_deg))
                    or height_mm <= 0
                    or insertion[0] < 0 or insertion[1] < 0
                    or insertion[0] > render_width * float(scale)
                    or insertion[1] > render_height * float(scale)
                ):
                    raise FidelityError("Native text baseline or font size maps outside the supported page frame.")
                native_to_emit.append({
                    "span": span,
                    "insertion_mm": insertion,
                    "height_mm": height_mm,
                    "rotation_deg": rotation_deg,
                })
    elif approval.get("approved_native_spans") or approval.get("native_selection"):
        raise FidelityError("Native text cannot be added to an OCR-only approval record.")
    if base_dxf is not None and (not _is_within(base_dxf, output_root) or not base_dxf.is_file()):
        raise FidelityError("Base layout DXF must reside inside the private fidelity output root.")
    import ezdxf

    if base_dxf is not None:
        document, base_dxf_sha256 = _read_text_base_snapshot(base_dxf)
    else:
        document, base_dxf_sha256 = ezdxf.new("R2010"), None
    base_text_count = len(document.modelspace().query("TEXT"))
    document.header["$INSUNITS"] = 4
    model = document.modelspace()
    scale = float(page["pixel_to_paper_mm"]["used"])
    audit_path = _safe_artifact_path(output_root, page["artifacts"]["layout_audit"])
    height_px = int(json.loads(audit_path.read_text(encoding="utf-8"))["source_page"]["render_height_px"])
    rendered_path = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
    source_image = cv2.imread(str(rendered_path))
    if source_image is None:
        raise FidelityError("Cannot read rendered page for text reconstruction sizing.")
    emitted = 0
    sizing_records: list[dict[str, Any]] = []
    for approved in approved_candidates:
        candidate = approved.get("candidate", {})
        content = candidate.get("content")
        bbox = candidate.get("bbox_px")
        if not isinstance(content, str) or not content.strip() or not isinstance(bbox, list) or len(bbox) != 4:
            raise FidelityError("Text approval contains an invalid candidate.")
        x0, _, _, y1 = (float(value) for value in bbox)
        sizing = _derive_text_reconstruction_size(
            source_image,
            content,
            bbox,
            scale,
            allow_tight_box_font_metric=page["page"] == 1,
        )
        text_height = sizing["height_mm"]
        entity = model.add_text(content, dxfattribs={"layer": "FIDELITY_TEXT", "height": text_height, "width": sizing["width_factor"], "style": _ensure_unicode_text_style(document)})
        entity.set_placement((x0 * scale, (height_px - y1) * scale))
        sizing_records.append({
            "id": candidate.get("id"),
            **sizing,
            "insertion_mm": [x0 * scale, (height_px - y1) * scale],
            "mapping_version": "rendered-page-pixel-to-paper-v1",
        })
        emitted += 1
    for approved in native_to_emit:
        span = approved["span"]
        entity = model.add_text(span["content"], dxfattribs={
            "layer": "FIDELITY_TEXT",
            "height": approved["height_mm"],
            "width": 1.0,
            "rotation": approved["rotation_deg"],
            "style": _ensure_unicode_text_style(document),
        })
        entity.set_placement(approved["insertion_mm"])
        sizing_records.append({
            "id": span["id"],
            "height_mm": approved["height_mm"],
            "width_factor": 1.0,
            "insertion_mm": list(approved["insertion_mm"]),
            "rotation_deg": approved["rotation_deg"],
            "mapping_version": "displayed-page-baseline-v1",
            "source_font_name": span["source_font_name"],
            "source_font_size_pt": span["source_font_size_pt"],
        })
        emitted += 1
    root = output_root / "text_reconstruction" / f"page_{page['page']:02d}"
    try:
        with pin_directory_chain(root.parent.absolute()):
            if not _is_within(root, output_root):
                raise FidelityError("Text reconstruction output escaped the private fidelity root.")
            if root.exists():
                if _published_text_reconstruction_matches(
                    root, manifest, approval_path, base_dxf_sha256, base_text_count, sizing_records,
                ):
                    return root / "layout.dxf"
                raise FidelityError(f"Text reconstruction already exists: {root}")
            with tempfile.TemporaryDirectory(
                prefix=f".{root.name}.staging-", dir=root.parent,
            ) as staging_directory:
                staging_root = Path(staging_directory)
                if not _is_within(staging_root, output_root):
                    raise FidelityError("Text reconstruction staging escaped the private fidelity root.")
                output = staging_root / "layout.dxf"
                with pin_directory_chain(staging_root.absolute()):
                    staging_stat = os.stat(staging_root, follow_symlinks=False)
                    staging_identity = (staging_stat.st_dev, staging_stat.st_ino)
                    document.saveas(output)
                    report = {
                        "state": "needs_review",
                        "profile": "fidelity-layout-text",
                        "source_sha256": manifest["source"]["sha256"],
                        "staging_directory_identity": list(staging_identity),
                        "text_approval_sha256": sha256_file(approval_path),
                        "base_dxf_sha256": base_dxf_sha256,
                        "output_dxf_sha256": sha256_file(output),
                        "emitted_text_entities": emitted,
                        "text_sizing": sizing_records,
                        "unresolved": [
                            "text content was human-approved but placement/height/style remain reviewable",
                            "no model export",
                        ],
                    }
                    try:
                        (staging_root / "report.json").write_text(
                            json.dumps(report, indent=2) + "\n", encoding="utf-8",
                        )
                    except OSError as exc:
                        raise FidelityError("Text reconstruction report could not be published.") from exc
                if not _is_within(staging_root, output_root):
                    raise FidelityError("Text reconstruction staging escaped before publication.")
                if root.exists():
                    raise FidelityError(f"Text reconstruction already exists: {root}")
                try:
                    _publish_staging_directory(staging_root, root, staging_identity)
                except FileIdentityError as exc:
                    if _published_text_reconstruction_matches(
                        root, manifest, approval_path, base_dxf_sha256, base_text_count, sizing_records,
                    ):
                        try:
                            _remove_staging_reparse_alias(staging_root)
                        except FileIdentityError as cleanup_exc:
                            raise FidelityError(
                                "Text reconstruction was published and verified, but publication finalization "
                                "and staging cleanup failed; an exact-input retry can safely reuse the output."
                            ) from cleanup_exc
                        raise FidelityError(
                            "Text reconstruction was published and verified, but publication finalization failed; "
                            "an exact-input retry can safely reuse the output."
                        ) from exc
                    raise
                try:
                    _remove_staging_reparse_alias(staging_root)
                except FileIdentityError as exc:
                    if _published_text_reconstruction_matches(
                        root, manifest, approval_path, base_dxf_sha256, base_text_count, sizing_records,
                    ):
                        raise FidelityError(
                            "Text reconstruction was published and verified, but staging cleanup failed; "
                            "an exact-input retry can safely reuse the output."
                        ) from exc
                    raise
    except FileIdentityError as exc:
        raise FidelityError("Text reconstruction output must use a stable, non-reparse directory inside the private fidelity root.") from exc
    return root / "layout.dxf"


def write_fidelity_text_review_index(source: Path, output_root: Path, manifest: dict[str, Any], *, workspace_root: Path) -> Path:
    """Create a private review page with separately typed OCR/native text choices."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    review_root = output_root / "fidelity_text_review"
    index = review_root / "index.html"
    revision = 2
    while index.exists():
        index = review_root / f"index-r{revision}.html"
        revision += 1
    cards: list[str] = []
    native_by_page: dict[str, dict[str, dict[str, Any]]] = {}
    for page in manifest.get("pages", []):
        number = page["page"]
        observation_path = output_root / "fidelity_text_observations" / f"page_{number:02d}.json"
        if not observation_path.is_file():
            raise FidelityError(f"Missing text observation for page {number}; run fidelity-text-observe first.")
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        if observation.get("source") != manifest.get("source") or observation.get("page") != number:
            raise FidelityError(f"Text observation for page {number} does not match the fidelity manifest.")
        rendered = _safe_artifact_path(output_root, page["artifacts"]["rendered_png"])
        ocr_rows = []
        for candidate in observation.get("candidates", []):
            candidate_id = escape(str(candidate.get("id", "")))
            content = escape(str(candidate.get("content", "")))
            confidence = escape(str(candidate.get("confidence", "")))
            bbox = escape(str(candidate.get("bbox_px", "")))
            ocr_rows.append(f'<tr><td><input type="checkbox" data-kind="ocr" data-page="{number}" value="{candidate_id}"></td><td><code>{candidate_id}</code></td><td>{content}</td><td>{confidence}</td><td><code>{bbox}</code></td></tr>')
        native_rows = []
        overlay_rects = []
        native_by_page[str(number)] = {}
        native_spans = observation.get("native_pdf_spans", [])
        rendered_image = cv2.imread(str(rendered))
        if rendered_image is None:
            raise FidelityError(f"Cannot read the rendered page for native text review: {rendered}")
        for span in native_spans:
            if not isinstance(span, dict) or not isinstance(span.get("id"), str):
                raise FidelityError(f"Native PDF text observation for page {number} contains an invalid span.")
            span_id = span["id"]
            native_by_page[str(number)][span_id] = span
            candidate_id = escape(span_id)
            content = escape(str(span.get("content", "")))
            bbox_value = span.get("bbox_px", [])
            bbox = escape(str(bbox_value))
            font_name = escape(str(span.get("source_font_name") or "unknown"))
            font_size = escape(str(span.get("source_font_size_pt") or "unknown"))
            if isinstance(bbox_value, list) and len(bbox_value) == 4:
                x0, y0, x1, y1 = (float(value) for value in bbox_value)
                if all(math.isfinite(value) for value in (x0, y0, x1, y1)) and x1 > x0 and y1 > y0:
                    overlay_rects.append(
                        f'<rect data-span-id="{candidate_id}" x="{x0:.3f}" y="{y0:.3f}" width="{x1-x0:.3f}" height="{y1-y0:.3f}"/>'
                    )
            native_rows.append(
                f'<tr><td><label><input type="checkbox" class="native-span-review" data-kind="native_pdf_spans" data-page="{number}" value="{candidate_id}"> visible and legible in this source render</label></td>'
                f'<td><code>{candidate_id}</code></td><td>{content}</td><td><code>{bbox}</code></td>'
                f'<td>{font_name}</td><td>{font_size} pt</td></tr>'
            )
        rel_rendered = Path(os.path.relpath(rendered, index.parent)).as_posix()
        image_width = rendered_image.shape[1]
        image_height = rendered_image.shape[0]
        source_frame = (
            f'<div class="source-frame"><img src="{escape(rel_rendered, quote=True)}" alt="PDF page {number} with native span bboxes">'
            f'<svg viewBox="0 0 {image_width} {image_height}" preserveAspectRatio="none" aria-label="Native PDF span bounding boxes">{"".join(overlay_rects)}</svg></div>'
        )
        cards.append(
            f'<section><h2>Trang {number} <small>{len(ocr_rows)} OCR candidates; {len(native_rows)} native_pdf_spans</small></h2>'
            f'<h3>Source render and native span bounds</h3>{source_frame}'
            f'<div class="scroll"><table><thead><tr><th>OCR selection</th><th>ID</th><th>OCR content</th><th>Confidence</th><th>Bbox px</th></tr></thead><tbody>{"".join(ocr_rows)}</tbody></table></div>'
            f'<h3>Native PDF spans</h3><p>Checking a row confirms this exact span is visible and legible in the displayed source render. It remains a separate native span selection; it is not OCR approval and does not create DXF.</p>'
            f'<div class="scroll"><table><thead><tr><th>Per-span visibility review</th><th>ID</th><th>Exact PDF text</th><th>Bbox px</th><th>Source font</th><th>Source size</th></tr></thead><tbody>{"".join(native_rows)}</tbody></table></div></section>'
        )
    source_json = json.dumps(manifest["source"], ensure_ascii=False).replace("<", "\\u003c")
    native_by_page_json = json.dumps(native_by_page, ensure_ascii=True).replace("<", "\\u003c")
    page_html = """<!doctype html><meta charset='utf-8'><title>Duyệt chữ PDF riêng tư</title><style>body{font:15px system-ui,sans-serif;margin:20px;background:#f4f6f8;color:#18212b}header,section{background:#fff;border:1px solid #d9e0e6;border-radius:10px;padding:16px;margin:14px 0}h1{margin:0 0 6px}h2{margin:0 0 12px;font-size:18px}h3{margin:20px 0 8px}small{font-weight:400;color:#5d6b78}button{padding:10px 14px;border:0;border-radius:7px;background:#075985;color:#fff;font-weight:600;margin-right:8px}p{line-height:1.45}.scroll{overflow-x:auto;margin-top:12px}table{border-collapse:collapse;width:100%;min-width:720px}th,td{border-bottom:1px solid #e4e9ed;padding:8px;text-align:left;vertical-align:top}th{background:#f8fafc}code{font-size:12px}.source-frame{position:relative;width:100%;line-height:0}.source-frame img{display:block;width:100%;height:auto;border:1px solid #cad3dc}.source-frame svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.source-frame rect{fill:rgba(255,165,0,.15);stroke:#e65100;stroke-width:2;vector-effect:non-scaling-stroke}label{cursor:pointer}</style><header><h1>Duyệt ứng viên chữ - riêng tư</h1><p>OCR and native PDF spans use separate selection fields. A native checkbox records your per-span visibility review for the exact source render. The separate approval step is still required; selection alone never creates DXF.</p><button onclick='copyIds()'>Sao chép ID</button><button onclick='downloadSelection()'>Tải tệp lựa chọn</button><p id='result' aria-live='polite'></p></header>""" + "\n".join(cards) + f"""<script>const source={source_json};const nativeByPage={native_by_page_json};function selected(){{const byPage={{}};document.querySelectorAll('input[data-kind]:checked').forEach(x=>{{const entry=byPage[x.dataset.page]??={{page:Number(x.dataset.page),candidate_ids:[],native_span_ids:[],native_span_reviews:[]}};if(x.dataset.kind==='native_pdf_spans'){{entry.native_span_ids.push(x.value);entry.native_span_reviews.push({{span:nativeByPage[x.dataset.page][x.value],visible_and_legible:true}});}}else{{entry.candidate_ids.push(x.value);}}byPage[x.dataset.page]=entry;}});return Object.values(byPage);}}function copyIds(){{const items=selected();const text=items.map(x=>'Trang '+x.page+': OCR '+x.candidate_ids.join(', ')+'; native '+x.native_span_ids.join(', ')).join('\\n');navigator.clipboard.writeText(text);document.querySelector('#result').textContent=text?'Đã sao chép.':'Chưa chọn ứng viên nào.';}}function downloadSelection(){{const selections=selected();if(!selections.length){{document.querySelector('#result').textContent='Chưa chọn ứng viên nào.';return;}}const blob=new Blob([JSON.stringify({{schema_version:'fidelity-text-selection-1.0',source,selections}},null,2)],{{type:'application/json'}});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='fidelity-text-selection.json';link.click();URL.revokeObjectURL(link.href);document.querySelector('#result').textContent='Đã tải tệp lựa chọn.';}}</script>"""
    review_root.mkdir(parents=True, exist_ok=True)
    index.write_text(page_html, encoding="utf-8")
    return index


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

    def offset_point(point: Any, offset_x: float, offset_y: float) -> tuple[float, float, float]:
        return (float(point.x) + offset_x, float(point.y) + offset_y, float(point.z))

    def copy_linetype(source_document: Any, name: str) -> None:
        if name in composed.linetypes or name.upper() in {"BYLAYER", "BYBLOCK", "CONTINUOUS"}:
            return
        source_linetype = source_document.linetypes.get(name)
        pattern = [tag.value for tag in source_linetype.pattern_tags.tags if tag.code == 49]
        length = next((float(tag.value) for tag in source_linetype.pattern_tags.tags if tag.code == 40), 0.0)
        composed.linetypes.add(
            name,
            pattern or [0.0],
            description=str(source_linetype.dxf.get("description", "")),
            length=length,
        )

    def add_text_entity(
        source_document: Any, entity: Any, offset_x: float, offset_y: float,
        source_repeated_styles: set[StyleRecordKey],
    ) -> None:
        style = _copy_fidelity_text_style(
            source_document, composed, str(entity.dxf.get("style", "")),
            source_repeated_styles=source_repeated_styles,
        )
        if entity.dxftype() == "TEXT":
            attributes = {
                "layer": "FIDELITY_TEXT",
                "height": float(entity.dxf.get("height", 1.0)),
                "style": style,
            }
            for name in ("rotation", "oblique", "width", "text_generation_flag", "thickness"):
                if entity.dxf.hasattr(name):
                    attributes[name] = entity.dxf.get(name)
            text = model.add_text(str(entity.dxf.text), dxfattribs=attributes)
            text.dxf.insert = offset_point(entity.dxf.insert, offset_x, offset_y)
            return
        attributes = {
            "layer": "FIDELITY_TEXT",
            "char_height": float(entity.dxf.get("char_height", 1.0)),
            "style": style,
        }
        for name in ("rotation", "width", "attachment_point", "line_spacing_style", "line_spacing_factor"):
            if entity.dxf.hasattr(name):
                attributes[name] = entity.dxf.get(name)
        mtext = model.add_mtext(str(entity.text), dxfattribs=attributes)
        mtext.dxf.insert = offset_point(entity.dxf.insert, offset_x, offset_y)

    def add_dimension_entity(source_document: Any, entity: Any, offset_x: float, offset_y: float) -> None:
        dimension_type = int(entity.dxf.get("dimtype", 0)) & 0x0F
        if dimension_type != 0:
            raise FidelityError(
                f"Unsupported fidelity dimension type {dimension_type}; only linear dimensions are supported."
            )
        if not all(entity.dxf.hasattr(name) for name in ("defpoint", "defpoint2", "defpoint3")):
            raise FidelityError("Only linear fidelity dimensions with definition points are supported.")
        dimstyle = str(entity.dxf.get("dimstyle", "Standard"))
        if dimstyle not in composed.dimstyles:
            source_style = source_document.dimstyles.get(dimstyle)
            attributes = {
                key: value for key, value in source_style.dxfattribs().items()
                if key not in {"handle", "owner", "name"}
            }
            composed.dimstyles.add(dimstyle, dxfattribs=attributes)
        midpoint = entity.dxf.get("text_midpoint", entity.dxf.defpoint)
        override = model.add_linear_dim(
            base=offset_point(entity.dxf.defpoint, offset_x, offset_y),
            p1=offset_point(entity.dxf.defpoint2, offset_x, offset_y),
            p2=offset_point(entity.dxf.defpoint3, offset_x, offset_y),
            location=offset_point(midpoint, offset_x, offset_y),
            angle=float(entity.dxf.get("angle", 0.0)),
            text=str(entity.dxf.get("text", "<>")),
            dimstyle=dimstyle,
            dxfattribs={"layer": "FIDELITY_DIMENSIONS"},
        )
        override.render()

    for region in selected:
        candidate = output_root / "reconstruction_candidates" / f"page_{page_number:02d}" / region["id"] / "geometry.dxf"
        if not candidate.is_file():
            raise FidelityError(f"Missing approved region candidate: {candidate}")
        x0, _, _, y1 = region["bbox_px"]
        offset_x, offset_y = x0 * scale, (height_px - y1) * scale
        source_document, source_repeated_styles = _read_fidelity_style_document(candidate)
        for entity in source_document.modelspace():
            if entity.dxftype() == "LINE":
                a, b = entity.dxf.start, entity.dxf.end
                line_type = str(entity.dxf.get("linetype", "BYLAYER"))
                copy_linetype(source_document, line_type)
                attributes = {"layer": "FIDELITY_GEOMETRY", "linetype": line_type}
                if entity.dxf.hasattr("linetype_scale"):
                    attributes["linetype_scale"] = entity.dxf.linetype_scale
                model.add_line(offset_point(a, offset_x, offset_y), offset_point(b, offset_x, offset_y), dxfattribs=attributes)
            elif entity.dxftype() == "CIRCLE":
                c = entity.dxf.center
                line_type = str(entity.dxf.get("linetype", "BYLAYER"))
                copy_linetype(source_document, line_type)
                model.add_circle(offset_point(c, offset_x, offset_y), entity.dxf.radius, dxfattribs={"layer": "FIDELITY_GEOMETRY", "linetype": line_type})
            elif entity.dxftype() in {"TEXT", "MTEXT"}:
                add_text_entity(source_document, entity, offset_x, offset_y, source_repeated_styles)
            elif entity.dxftype() == "DIMENSION":
                add_dimension_entity(source_document, entity, offset_x, offset_y)
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
    (root / "report.json").write_text(json.dumps({"state": "needs_review", "profile": "fidelity-layout", "approval_sha256": sha256_file(approval_path), "edge_metric": _edge_metrics(source_edges, vector_edges, np.full(image.shape[:2], 255, dtype=np.uint8)), "unresolved": ["unselected content remains absent", "semantic owner handoff remains review-only", "no model export"]}, indent=2) + "\n", encoding="utf-8")
    return root


def _fidelity_dxf_signature(dxf: Path) -> dict[str, Any]:
    """Return the read-only structure that AutoCAD must reproduce."""
    import ezdxf

    entities = list(ezdxf.readfile(dxf).modelspace())
    type_layers = Counter(
        f"{entity.dxftype()}|{str(entity.dxf.layer)}" for entity in entities
    )
    return {
        "entity_count": len(entities),
        "types": dict(sorted(Counter(entity.dxftype() for entity in entities).items())),
        "layers": dict(
            sorted(Counter(str(entity.dxf.layer) for entity in entities).items())
        ),
        "type_layers": dict(sorted(type_layers.items())),
    }


def _live_entity_signature(entities: list[dict[str, Any]]) -> dict[str, Any]:
    type_layers = Counter(
        f"{str(entity.get('type', '')).upper()}|{str(entity.get('layer', ''))}"
        for entity in entities
    )
    return {
        "entity_count": len(entities),
        "types": dict(
            sorted(Counter(str(entity.get("type", "")).upper() for entity in entities).items())
        ),
        "layers": dict(
            sorted(Counter(str(entity.get("layer", "")) for entity in entities).items())
        ),
        "type_layers": dict(sorted(type_layers.items())),
    }


def promote_fidelity_page(
    source: Path,
    output_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    page_number: int,
    composed_root: Path,
    approval_reference: str,
    *,
    workspace_root: Path,
    revision: int = 1,
) -> Path:
    """Promote one visually approved composition into the canonical checkpoint."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    if manifest_path.resolve().parent != output_root.resolve():
        raise FidelityError("Fidelity manifest must reside directly under its output root.")
    verify_source(manifest, source)
    if not approval_reference.strip():
        raise FidelityError("Fidelity promotion requires a non-empty visual approval reference.")
    if revision < 1:
        raise FidelityError("Fidelity promotion revision must be positive.")
    page = next(
        (item for item in manifest.get("pages", []) if item.get("page") == page_number),
        None,
    )
    if page is None:
        raise FidelityError("Promoted page is absent from the fidelity manifest.")
    composed_root = composed_root.resolve()
    expected_parent = (output_root / "reconstruction_pages").resolve()
    if (
        composed_root.parent != expected_parent
        or not composed_root.name.startswith(f"page_{page_number:02d}")
    ):
        raise FidelityError("Composed page is not the requested reconstruction page.")
    dxf = composed_root / "layout.dxf"
    overlay = composed_root / "overlay.png"
    report_path = composed_root / "report.json"
    if not all(path.is_file() for path in (dxf, overlay, report_path)):
        raise FidelityError("Composed page is missing its DXF, overlay, or report.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("state") != "needs_review" or report.get("profile") != "fidelity-layout":
        raise FidelityError("Composed page is not a reviewable fidelity-layout candidate.")
    approval_sha256 = report.get("approval_sha256")
    approvals = list((output_root / "region_approvals").glob(f"page_{page_number:02d}*.json"))
    matching_approval = next(
        (
            path
            for path in approvals
            if isinstance(approval_sha256, str) and sha256_file(path) == approval_sha256
        ),
        None,
    )
    if matching_approval is None:
        raise FidelityError("Composed page is not bound to a current region approval.")

    suffix = "" if revision == 1 else f"-r{revision}"
    promotion_path = (
        output_root
        / "fidelity_promotions"
        / f"page_{page_number:02d}{suffix}.json"
    )
    if promotion_path.exists():
        raise FidelityError(f"Fidelity promotion already exists: {promotion_path}")
    promotion = {
        "schema_version": "fidelity-promotion-1.0",
        "private_artifact": True,
        "state": "approved_for_mechanical_review",
        "source": manifest["source"],
        "page": page_number,
        "revision": revision,
        "visual_approval": {
            "approved": True,
            "reference": approval_reference.strip(),
        },
        "inputs": {
            "region_approval": _artifact(matching_approval, output_root),
            "composition_report": _artifact(report_path, output_root),
            "overlay": _artifact(overlay, output_root),
            "dxf": _artifact(dxf, output_root),
        },
        "expected_structure": _fidelity_dxf_signature(dxf),
        "allowed_actions": ["mechanical-review-read-only"],
        "prohibited_actions": ["mechanical-repair", "model-export", "production-save"],
    }
    write_manifest(promotion_path, promotion)
    page["artifacts"]["promotion"] = _artifact(promotion_path, output_root)
    page["artifacts"]["promoted_reconstruction_dxf"] = _artifact(dxf, output_root)
    page["fidelity_state"] = "approved_for_mechanical_review"
    page["mechanical_review"] = {
        "state": "pending",
        "artifact": None,
        "sha256": None,
    }
    write_manifest(manifest_path, manifest)
    return promotion_path


def review_promoted_fidelity_page(
    source: Path,
    output_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    page_number: int,
    client: Any,
    *,
    workspace_root: Path,
) -> tuple[Path, bool]:
    """Open and structurally verify a promoted page in AutoCAD, without saving."""
    if _is_within(output_root, workspace_root):
        raise FidelityError("Fidelity output must be outside the Git worktree.")
    verify_source(manifest, source)
    page = next(
        (item for item in manifest.get("pages", []) if item.get("page") == page_number),
        None,
    )
    if page is None or page.get("fidelity_state") != "approved_for_mechanical_review":
        raise FidelityError("Page has no visual approval for Mechanical review.")
    promotion_path = _safe_artifact_path(output_root, page["artifacts"]["promotion"])
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    if (
        promotion.get("state") != "approved_for_mechanical_review"
        or promotion.get("source") != manifest.get("source")
        or promotion.get("page") != page_number
        or promotion.get("allowed_actions") != ["mechanical-review-read-only"]
    ):
        raise FidelityError("Fidelity promotion is invalid for read-only Mechanical review.")
    dxf = _safe_artifact_path(output_root, promotion["inputs"]["dxf"])
    opened = client.drawing_open(str(dxf))
    entities = client.entity_list()
    actual = _live_entity_signature(entities)
    expected = promotion["expected_structure"]
    passed = actual == expected
    variables = client.drawing_get_variables(["DWGPREFIX", "DWGNAME", "INSUNITS"])
    promotion_suffix = promotion_path.stem.removeprefix(f"page_{page_number:02d}")
    report_path = (
        output_root
        / "fidelity_mechanical_review"
        / f"page_{page_number:02d}{promotion_suffix}.json"
    )
    if report_path.exists():
        raise FidelityError(f"Fidelity Mechanical review already exists: {report_path}")
    report = {
        "schema_version": "fidelity-mechanical-review-1.0",
        "private_artifact": True,
        "operation": "mechanical-review-read-only",
        "state": "passed" if passed else "failed",
        "source": manifest["source"],
        "page": page_number,
        "promotion_sha256": sha256_file(promotion_path),
        "dxf": _artifact(dxf, output_root),
        "open_result": opened,
        "drawing_variables": variables,
        "expected_structure": expected,
        "actual_structure": actual,
        "save_performed": False,
        "repair_performed": False,
    }
    write_manifest(report_path, report)
    page["mechanical_review"] = {
        "state": "completed" if passed else "failed",
        **_artifact(report_path, output_root),
    }
    page["fidelity_state"] = "mechanical_reviewed" if passed else "mechanical_review_failed"
    write_manifest(manifest_path, manifest)
    return report_path, passed


def _advanced_fidelity_reviews(output_root: Path, page_number: int) -> list[dict[str, Any]]:
    """Collect known advanced fidelity sidecars without promoting them."""
    directories = {
        "text": ("fidelity_text_observations", "fidelity_text_approvals", "text_reconstruction"),
        "table_text": ("fidelity_table_text_observations", "fidelity_table_text_approvals", "table_text_reconstruction"),
        "dimension": ("fidelity_dimension_observations", "dimension_reconstruction"),
        "hatch": ("fidelity_hatch_observations", "fidelity_hatch_approvals", "hatch_reconstruction"),
        "linetype": ("linetype_reconstruction",),
    }
    records: list[dict[str, Any]] = []
    page_name = f"page_{page_number:02d}"
    for kind, prefixes in directories.items():
        paths: set[Path] = set()
        for prefix in prefixes:
            roots = [output_root / prefix]
            roots.extend(sorted(output_root.glob(f"{prefix}-r*")))
            for root in roots:
                paths.update(root.glob(f"{page_name}.json"))
                paths.update(root.glob(f"{page_name}/*.json"))
        for path in sorted(path for path in paths if path.is_file()):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                state = payload.get("state", "unknown") if isinstance(payload, dict) else "invalid_artifact"
            except (OSError, json.JSONDecodeError):
                state = "invalid_artifact"
            next_action = (
                "run the bounded observation step"
                if state == "not_run"
                else "visually review the private candidate; no production action"
            )
            records.append({
                "kind": kind,
                "state": state,
                "artifact": _artifact(path, output_root),
                "next_action": next_action,
            })
        if not any(record["kind"] == kind for record in records):
            records.append({
                "kind": kind,
                "state": "not_run",
                "artifact": None,
                "next_action": "run the bounded observation step",
            })
    return records


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
        advanced = _advanced_fidelity_reviews(output_root, page["page"])
        advanced_html = "<ul>" + "".join(
            f"<li>{item['kind']}: {item['state']}</li>" for item in advanced
        ) + "</ul>"
        rel_rendered = Path(os.path.relpath(rendered, index.parent)).as_posix()
        rel_overlay = Path(os.path.relpath(overlay, index.parent)).as_posix() if overlay else None
        overlay_html = f'<img src="{rel_overlay}" alt="overlay page {page["page"]}">' if rel_overlay else "<p>overlay not generated</p>"
        cards.append(f'<section><h2>Page {page["page"]} <small>table: {table_state}</small></h2><h3>Advanced fidelity</h3>{advanced_html}<div><figure><figcaption>PDF render</figcaption><img src="{rel_rendered}" alt="PDF page {page["page"]}"></figure><figure><figcaption>DXF overlay</figcaption>{overlay_html}</figure></div></section>')
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
        advanced_reviews = _advanced_fidelity_reviews(output_root, number)
        approvals = sorted((output_root / "region_approvals").glob(f"page_{number:02d}*.json")) if (output_root / "region_approvals").is_dir() else []
        items.append({"page": number, "state": "needs_review", "priority": 1 if number == 5 else 2, "table_observation": table_state, "advanced_reviews": advanced_reviews, "approved_region_records": [path.relative_to(output_root).as_posix() for path in approvals], "next_action": "reconstruct approved region" if approvals else "select and approve a reconstruction region"})
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


def _observe_hatch_candidates(image: np.ndarray) -> list[dict[str, Any]]:
    """Record dense diagonal-stroke cells as review-only hatch evidence."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    segments = cv2.HoughLinesP(
        cv2.Canny(gray, 50, 150), 1, np.pi / 180, threshold=15,
        minLineLength=12, maxLineGap=2,
    )
    groups: dict[tuple[int, int], int] = {}
    if segments is not None:
        for x0, y0, x1, y1 in segments.reshape(-1, 4):
            dx, dy = int(x1) - int(x0), int(y1) - int(y0)
            if abs(dx) < 10 or abs(dy) < 10:
                continue
            key = (int((int(x0) + int(x1)) / 2) // 100, int((int(y0) + int(y1)) / 2) // 100)
            groups[key] = groups.get(key, 0) + 1
    height, width = image.shape[:2]
    candidates = [
        {
            "bbox_px": [column * 100, row * 100, min(width, (column + 1) * 100), min(height, (row + 1) * 100)],
            "diagonal_segment_count": count,
            "state": "needs_review",
        }
        for (column, row), count in sorted(groups.items())
        if count >= 5
    ]
    return [{"id": f"hatch-{index:03d}", **candidate} for index, candidate in enumerate(candidates, start=1)]


def _fidelity_page_text_rois(image: np.ndarray) -> tuple[int, list[tuple[int, int, int, int]]]:
    height, width = image.shape[:2]
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
    return len(detected), rois


def _fidelity_page_text_ocr(
    image: np.ndarray,
    rois: list[tuple[int, int, int, int]] | None = None,
) -> list[Any]:
    _configure_tesseract(None)
    if rois is None:
        _, rois = _fidelity_page_text_rois(image)
    return extract_text_tesseract(image, roi_boxes=rois, min_confidence=20, psm=11)


def _fidelity_text_candidate_records(image: np.ndarray) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "content": item.content.strip(),
            "bbox_px": list(item.bbox_px),
            "rotation_deg": item.rotation_deg,
            "confidence": item.confidence,
            "source": item.source,
            "semantic_role": item.semantic_role,
            "parsed_value": item.parsed_value,
        }
        for item in _fidelity_page_text_ocr(image)
        if isinstance(item.content, str) and item.content.strip()
    ]


def _ocr_candidate_evidence_key(candidate: dict[str, Any]) -> str:
    # Candidate IDs are run-local labels; OCR provenance is the exact recognized
    # content and geometry produced again from the current source render.
    evidence = {key: value for key, value in candidate.items() if key != "id"}
    return json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _audit_page(image, raw_geometry, dpi: int, page_number: int, rendered_path: Path) -> dict[str, Any]:
    height, width = image.shape[:2]
    detected_count, rois = _fidelity_page_text_rois(image)
    texts = _fidelity_page_text_ocr(image, rois)
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
        "ocr": {"engine": "tesseract-local", "psm": 11, "roi_limit": 9, "detected_roi_count": detected_count, "rois_px": [list(roi) for roi in rois], "texts": [_raw_text_payload(text) for text in texts]},
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
    page = layout.Page(width_mm, height_mm)
    render_box = layout.BoundingBox2d([(0.0, 0.0), (float(width_mm), float(height_mm))])
    png = backend.get_replay(page, render_box=render_box).get_pixmap(144, alpha=True).tobytes("png")
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
