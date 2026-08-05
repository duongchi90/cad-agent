"""Closed, deterministic metadata for one multisource reconstruction run."""

from __future__ import annotations

import copy
import datetime as _datetime
import re
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256


SOURCE_BUNDLE_SCHEMA_VERSION = "source-bundle-1.0"

_ROOT_FIELDS = {
    "schema_version",
    "bundle_id",
    "run_id",
    "created_at_utc",
    "items",
}
_ITEM_FIELDS = {
    "source_id",
    "kind",
    "role",
    "relative_path",
    "sha256",
    "media_type",
    "page_ids",
    "region_ids",
    "captured_at_utc",
    "quality",
}
_QUALITY_FIELDS = {"distortion", "legibility"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")

_KINDS = {"IMAGE", "PDF", "EXACT_BASE_CAD", "ENGINEER_RECORD"}
_ROLES = {
    "OVERALL",
    "DETAIL",
    "SECTION",
    "MATERIAL_TABLE",
    "BASE_CAD",
    "MEASUREMENT",
    "DECISION",
}
_DISTORTIONS = {"NONE", "PERSPECTIVE", "UNKNOWN"}
_LEGIBILITY = {"GOOD", "LIMITED", "UNREADABLE"}


class SourceBundleError(ValueError):
    """Raised when a SourceBundle is malformed or outside the closed contract."""


def _closed_object(value: object, *, required: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceBundleError(f"{path} must be an object")
    missing = sorted(required - set(value))
    unsupported = sorted((key for key in value if key not in required), key=str)
    if missing:
        raise SourceBundleError(f"{path} missing required properties: {', '.join(missing)}")
    if unsupported:
        names = ", ".join(str(key) for key in unsupported)
        raise SourceBundleError(f"{path} contains unsupported properties: {names}")
    return value


def _identifier(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise SourceBundleError(f"{path} must be a stable identifier")
    return value


def _timestamp_or_none(value: object, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _UTC_TIMESTAMP_RE.fullmatch(value):
        raise SourceBundleError(f"{path} must be a UTC timestamp ending in Z")
    try:
        _datetime.datetime.fromisoformat(value[:-1])
    except ValueError as exc:
        raise SourceBundleError(f"{path} must be a valid UTC timestamp") from exc
    return value


def _safe_relative_path(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise SourceBundleError(f"{path} must be a safe relative_path")
    if value.startswith("/") or _WINDOWS_DRIVE_RE.match(value):
        raise SourceBundleError(f"{path} must be a safe relative_path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise SourceBundleError(f"{path} must be a safe relative_path")
    return value


def _unique_identifiers(value: object, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise SourceBundleError(f"{path} must be an array of identifiers")
    return [_identifier(item, path=f"{path}[{index}]") for index, item in enumerate(value)]


def _validate_quality(value: object, *, path: str) -> dict[str, str]:
    quality = _closed_object(value, required=_QUALITY_FIELDS, path=path)
    distortion = quality["distortion"]
    legibility = quality["legibility"]
    if not isinstance(distortion, str) or distortion not in _DISTORTIONS:
        raise SourceBundleError(f"{path}.distortion has an invalid value")
    if not isinstance(legibility, str) or legibility not in _LEGIBILITY:
        raise SourceBundleError(f"{path}.legibility has an invalid value")
    return {"distortion": distortion, "legibility": legibility}


def _validate_item(value: object, *, index: int) -> dict[str, Any]:
    path = f"items[{index}]"
    item = _closed_object(value, required=_ITEM_FIELDS, path=path)
    source_id = _identifier(item["source_id"], path=f"{path}.source_id")
    kind = item["kind"]
    role = item["role"]
    media_type = item["media_type"]
    if not isinstance(kind, str) or kind not in _KINDS:
        raise SourceBundleError(f"{path}.kind has an unsupported value")
    if not isinstance(role, str) or role not in _ROLES:
        raise SourceBundleError(f"{path}.role has an unsupported value")
    if not isinstance(media_type, str) or not media_type:
        raise SourceBundleError(f"{path}.media_type must be a non-empty string")
    relative_path = _safe_relative_path(item["relative_path"], path=f"{path}.relative_path")
    sha256 = item["sha256"]
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise SourceBundleError(f"{path}.sha256 must be lowercase hexadecimal SHA-256")
    page_ids = _unique_identifiers(item["page_ids"], path=f"{path}.page_ids")
    region_ids = _unique_identifiers(item["region_ids"], path=f"{path}.region_ids")
    captured_at_utc = _timestamp_or_none(item["captured_at_utc"], path=f"{path}.captured_at_utc")
    quality = _validate_quality(item["quality"], path=f"{path}.quality")

    allowed_roles: set[str]
    allowed_media_types: set[str]
    requires_page = False
    if kind == "EXACT_BASE_CAD":
        allowed_roles = {"BASE_CAD"}
        allowed_media_types = {"application/acad", "application/dxf"}
    elif kind == "IMAGE":
        allowed_roles = {"OVERALL", "DETAIL", "SECTION", "MATERIAL_TABLE"}
        allowed_media_types = {"image/png", "image/jpeg"}
    elif kind == "PDF":
        allowed_roles = {"OVERALL", "DETAIL", "SECTION", "MATERIAL_TABLE"}
        allowed_media_types = {"application/pdf"}
        requires_page = True
    else:
        allowed_roles = {"MEASUREMENT", "DECISION"}
        allowed_media_types = {"application/json"}

    if role not in allowed_roles or media_type not in allowed_media_types:
        raise SourceBundleError(f"{path}.kind/role/media_type combination is unsupported")
    if requires_page and not page_ids:
        raise SourceBundleError(f"{path}.page_ids must contain at least one page for PDF")
    if not requires_page and page_ids:
        raise SourceBundleError(f"{path}.page_ids must be empty for non-PDF items")

    return {
        "source_id": source_id,
        "kind": kind,
        "role": role,
        "relative_path": relative_path,
        "sha256": sha256,
        "media_type": media_type,
        "page_ids": sorted(set(page_ids)),
        "region_ids": sorted(set(region_ids)),
        "captured_at_utc": captured_at_utc,
        "quality": quality,
    }


def validate_source_bundle(payload: object) -> dict[str, object]:
    """Return a deep, normalized SourceBundle copy or fail closed."""
    source = _closed_object(payload, required=_ROOT_FIELDS, path="SourceBundle")
    if source["schema_version"] != SOURCE_BUNDLE_SCHEMA_VERSION:
        raise SourceBundleError("schema_version must equal source-bundle-1.0")
    bundle_id = _identifier(source["bundle_id"], path="bundle_id")
    run_id = _identifier(source["run_id"], path="run_id")
    created_at_utc = _timestamp_or_none(source["created_at_utc"], path="created_at_utc")
    if created_at_utc is None:
        raise SourceBundleError("created_at_utc is required")
    items_value = source["items"]
    if not isinstance(items_value, list) or not items_value or len(items_value) > 10_000:
        raise SourceBundleError("items must contain between 1 and 10000 entries")

    normalized_items = [_validate_item(item, index=index) for index, item in enumerate(items_value)]
    source_ids = [item["source_id"] for item in normalized_items]
    relative_paths = [item["relative_path"] for item in normalized_items]
    if len(set(source_ids)) != len(source_ids):
        raise SourceBundleError("source_id values must be unique")
    if len(set(relative_paths)) != len(relative_paths):
        raise SourceBundleError("relative_path values must be unique")
    normalized_items.sort(key=lambda item: item["source_id"])
    return {
        "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "items": copy.deepcopy(normalized_items),
    }


def build_source_bundle(
    *,
    bundle_id: str,
    run_id: str,
    created_at_utc: str,
    items: object,
) -> dict[str, object]:
    """Validate, normalize, and return one deterministic SourceBundle."""
    return validate_source_bundle(
        {
            "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION,
            "bundle_id": bundle_id,
            "run_id": run_id,
            "created_at_utc": created_at_utc,
            "items": items,
        }
    )


def source_bundle_sha256(payload: object) -> str:
    """Return the canonical SHA-256 of a validated SourceBundle."""
    return canonical_json_sha256(validate_source_bundle(payload))
