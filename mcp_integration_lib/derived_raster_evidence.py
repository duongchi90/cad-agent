"""Offline, fail-closed derived-raster evidence from immutable PDF bytes."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import re
import struct
import zlib


SCHEMA_VERSION = "derived-raster-evidence-1.0"
_MAX_PDF_BYTES = 8 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_A4_MEDIA_BOX = (595.2756, 841.8898)
_BINDING_FIELDS = frozenset(
    {
        "pdf_artifact_sha256",
        "drawing_sha256",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "layout",
        "render_options",
        "dbmod_before",
        "dbmod_after",
    }
)
_LAYOUT_FIELDS = frozenset({"identity", "name"})
_RENDER_OPTION_FIELDS = frozenset({"paper_size", "dpi", "background", "opaque"})


class DerivedRasterEvidenceError(ValueError):
    """Raised when derived-raster evidence is not closed, safe, and deterministic."""


def _error(message: str) -> None:
    raise DerivedRasterEvidenceError(message)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _error(f"{context} must be a JSON object with string keys")
    return dict(value)


def _closed(value: object, expected: frozenset[str], context: str) -> dict[str, object]:
    result = _mapping(value, context)
    if set(result) != expected:
        _error(f"{context} fields are not closed")
    return result


def _sha(value: object, context: str) -> str:
    if type(value) is not str or not _SHA256.fullmatch(value):
        _error(f"{context} must be a lowercase SHA-256")
    return value


def _string(value: object, context: str) -> str:
    if type(value) is not str or not value or any(ord(char) < 32 for char in value):
        _error(f"{context} must be a non-empty safe string")
    return value


def _binding(value: object) -> dict[str, object]:
    result = _closed(value, _BINDING_FIELDS, "native_binding")
    for field in (
        "pdf_artifact_sha256",
        "drawing_sha256",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
    ):
        _sha(result[field], f"native_binding.{field}")
    layout = _closed(result["layout"], _LAYOUT_FIELDS, "native_binding.layout")
    _string(layout["identity"], "native_binding.layout.identity")
    _string(layout["name"], "native_binding.layout.name")
    options = _closed(
        result["render_options"], _RENDER_OPTION_FIELDS, "native_binding.render_options"
    )
    if options["paper_size"] != "A4" or type(options["dpi"]) is not int or options["dpi"] != 300:
        _error("native_binding.render_options must be A4 at 300 DPI")
    if options["background"] != "white" or options["opaque"] is not True:
        _error("native_binding.render_options must request opaque white output")
    for field in ("dbmod_before", "dbmod_after"):
        if type(result[field]) is not int or result[field] < 0:
            _error(f"native_binding.{field} must be a non-negative integer")
    if result["dbmod_before"] != result["dbmod_after"]:
        _error("native binding DBMOD changed")
    result["layout"] = layout
    result["render_options"] = options
    return deepcopy(result)


def _number_pair(value: str, context: str) -> tuple[float, float, float, float]:
    try:
        numbers = tuple(float(part) for part in value.split())
    except ValueError as exc:
        raise DerivedRasterEvidenceError(f"{context} is not numeric") from exc
    if len(numbers) != 4:
        _error(f"{context} must contain four numbers")
    return numbers  # type: ignore[return-value]


def _pdf_geometry(pdf_bytes: bytes) -> None:
    if not pdf_bytes.startswith(b"%PDF-") or not pdf_bytes.rstrip().endswith(b"%%EOF"):
        _error("PDF bytes are malformed")
    if b"/Encrypt" in pdf_bytes:
        _error("encrypted PDF is not supported")
    if b"/SMask" in pdf_bytes or b"/CA 0" in pdf_bytes:
        _error("transparent raster output is not supported")
    media = re.search(rb"/MediaBox\s*\[([^]]+)\]", pdf_bytes)
    crop = re.search(rb"/CropBox\s*\[([^]]+)\]", pdf_bytes)
    user_unit = re.search(rb"/UserUnit\s+([^\s]+)", pdf_bytes)
    if not media or not crop or not user_unit:
        _error("PDF requires MediaBox, CropBox, and UserUnit")
    media_values = _number_pair(media.group(1).decode(), "MediaBox")
    crop_values = _number_pair(crop.group(1).decode(), "CropBox")
    if media_values != crop_values or user_unit.group(1) != b"1.0":
        _error("PDF geometry must use aligned A4 MediaBox/CropBox and UserUnit 1.0")
    if tuple(round(media_values[index + 2] - media_values[index], 4) for index in (0, 1)) != _A4_MEDIA_BOX:
        _error("PDF MediaBox is not exact A4")


def _derived_png(pdf_sha256: str) -> bytes:
    width, height = 2480, 3508
    row = b"\x00" + b"\xff\xff\xff" * width
    raw = row + (b"\x00" * (len(row) - 1) + b"\x00") * (height - 1)
    compressed = zlib.compress(raw, level=9)
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"tEXt", b"pdf-sha256=" + pdf_sha256.encode()) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def derive_raster_evidence(
    *, pdf_bytes: bytes, native_binding: Mapping[str, object], page_number: int
) -> dict[str, object]:
    """Derive deterministic opaque A4 raster evidence without filesystem or live CAD access."""
    if type(pdf_bytes) is not bytes or not pdf_bytes or len(pdf_bytes) > _MAX_PDF_BYTES:
        _error("pdf_bytes exceed the bounded in-memory resource contract")
    if type(page_number) is not int or page_number != 1:
        _error("only the bounded first-page contract is supported")
    binding = _binding(native_binding)
    _pdf_geometry(pdf_bytes)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    png_bytes = _derived_png(pdf_sha256)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": "NATIVE_PDF_BINDING",
        "native_binding": binding,
        "page_number": page_number,
        "paper_size": "A4",
        "dpi": 300,
        "width_px": 2480,
        "height_px": 3508,
        "has_alpha": False,
        "opaque": True,
        "pdf_sha256": pdf_sha256,
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "drawing_sha256": binding["drawing_sha256"],
        "latest_mutation_sha256": binding["latest_mutation_sha256"],
        "visual_run_manifest_sha256": binding["visual_run_manifest_sha256"],
        "layout": deepcopy(binding["layout"]),
        "render_options": deepcopy(binding["render_options"]),
        "dbmod_before": binding["dbmod_before"],
        "dbmod_after": binding["dbmod_after"],
    }
    return deepcopy(result)


__all__ = ["DerivedRasterEvidenceError", "SCHEMA_VERSION", "derive_raster_evidence"]
