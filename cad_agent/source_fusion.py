"""Deterministic R1C locator and render-provenance validation.

This module binds caller-supplied locator/provenance records to already-validated
SourceBundle and source-custody facts. It does not inspect source bytes,
render media, or confer approval/publication authority.
"""

from __future__ import annotations

import copy as _copy
import decimal as _decimal
import re as _re
from collections.abc import Mapping as _Mapping

from cad_agent.drawing_contracts import canonical_json_sha256 as _canonical_json_sha256
from cad_agent.source_bundle import (
    source_bundle_sha256 as _source_bundle_sha256,
    validate_source_bundle as _validate_source_bundle,
)
from cad_agent.source_integrity import (
    R1C_NUMERIC_POLICY_VERSION as _R1C_NUMERIC_POLICY_VERSION,
    canonicalize_r1c_quantity as _canonicalize_r1c_quantity,
    source_custody_sha256 as _source_custody_sha256,
    validate_source_custody as _validate_source_custody,
)


SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"


class SourceFusionError(ValueError):
    """Raised when a Task-4 locator/provenance contract fails closed."""


__all__ = [
    "SOURCE_FUSION_SCHEMA_VERSION",
    "SourceFusionError",
    "validate_page_locators",
    "validate_region_locators",
    "validate_render_provenance",
]


_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_PAGE_FIELDS = {
    "page_locator_sha256",
    "source_custody_sha256",
    "numeric_policy_version",
    "source_id",
    "page_id",
    "page_index",
    "observed_pdf_sha256",
    "media_box",
    "crop_box",
    "rotation",
    "user_unit",
}
_RASTER_REGION_FIELDS = {
    "region_locator_sha256",
    "source_custody_sha256",
    "numeric_policy_version",
    "source_id",
    "region_id",
    "locator_kind",
    "coordinate_convention",
    "page_locator_sha256",
    "render_provenance_sha256",
    "raster_sha256",
    "raster_width_px",
    "raster_height_px",
    "bounds",
}
_PDF_REGION_FIELDS = {
    "region_locator_sha256",
    "source_custody_sha256",
    "numeric_policy_version",
    "source_id",
    "region_id",
    "locator_kind",
    "coordinate_convention",
    "page_locator_sha256",
    "box_kind",
    "rotation",
    "user_unit",
    "bounds",
}
_DIRECT_RENDER_FIELDS = {
    "render_provenance_sha256",
    "provenance_kind",
    "source_custody_sha256",
    "numeric_policy_version",
    "source_id",
    "observed_source_sha256",
    "raster_sha256",
    "raster_width_px",
    "raster_height_px",
    "primitive_artifact_sha256",
    "primitive_source_document",
}
_PDF_RENDER_FIELDS = {
    "render_provenance_sha256",
    "provenance_kind",
    "source_custody_sha256",
    "numeric_policy_version",
    "source_id",
    "observed_source_sha256",
    "page_locator_sha256",
    "pdf_page_index",
    "box_kind",
    "selected_box",
    "rotation",
    "user_unit",
    "render_dpi",
    "render_matrix",
    "raster_sha256",
    "raster_width_px",
    "raster_height_px",
    "primitive_artifact_sha256",
    "primitive_source_document",
}
_SOURCE_DOCUMENT_FIELDS = {
    "file_name",
    "page_index",
    "image_width_px",
    "image_height_px",
    "sha256",
}
_BOX_FIELDS = {"unit", "coordinates"}
_SCALAR_FIELDS = {"unit", "value"}
_MATRIX_FIELDS = {"unit", "coefficients"}
_LOCATOR_KINDS = {"SHEET", "VIEW", "CROP", "REGION"}
_BOX_KINDS = {"MEDIA_BOX", "CROP_BOX"}
_RASTER_CONVENTION = "RASTER_TOP_LEFT_X_RIGHT_Y_DOWN"
_PDF_CONVENTION = "PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP"


def _fail(code: str) -> None:
    raise SourceFusionError(code)


def _closed(value: object, fields: set[str], code: str) -> _Mapping[str, object]:
    if not isinstance(value, _Mapping):
        _fail(code)
    if set(value) != fields or any(not isinstance(key, str) for key in value):
        _fail(code)
    return value


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _strict_nonnegative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _strict_positive_int(value: object, code: str) -> int:
    result = _strict_nonnegative_int(value, code)
    if result == 0:
        _fail(code)
    return result


def _validated_custody(custody: object) -> dict[str, object]:
    try:
        normalized = _validate_source_custody(custody)
    except Exception:
        _fail("CUSTODY_INVALID")
    if normalized["status"] != "READY":
        _fail("CUSTODY_NOT_READY")
    if normalized["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
        _fail("CUSTODY_INVALID")
    return normalized


def _custody_digest(custody: dict[str, object]) -> str:
    try:
        return _source_custody_sha256(custody)
    except Exception:
        _fail("CUSTODY_INVALID")


def _custody_items(custody: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(item["source_id"]): item for item in custody["items"]}


def _canonical_quantity(
    value: object,
    *,
    quantity: str,
    unit: object,
    code: str,
) -> str:
    if not isinstance(unit, str):
        _fail(code)
    try:
        return _canonicalize_r1c_quantity(
            value,
            quantity=quantity,
            unit=unit,
        )["value"]
    except Exception:
        _fail(code)


def _canonical_box(value: object, code: str) -> dict[str, object]:
    box = _closed(value, _BOX_FIELDS, code)
    coordinates = box["coordinates"]
    if not isinstance(coordinates, list) or len(coordinates) != 4:
        _fail(code)
    normalized = [
        _canonical_quantity(
            coordinate,
            quantity="pdf_coordinate",
            unit=box["unit"],
            code=code,
        )
        for coordinate in coordinates
    ]
    return {"unit": "pt", "coordinates": normalized}


def _canonical_ratio(value: object, code: str) -> dict[str, str]:
    scalar = _closed(value, _SCALAR_FIELDS, code)
    normalized = _canonical_quantity(
        scalar["value"],
        quantity="scale",
        unit=scalar["unit"],
        code=code,
    )
    return {"unit": "ratio", "value": normalized}


def _canonical_dpi(value: object, code: str) -> dict[str, str]:
    scalar = _closed(value, _SCALAR_FIELDS, code)
    normalized = _canonical_quantity(
        scalar["value"],
        quantity="dpi",
        unit=scalar["unit"],
        code=code,
    )
    return {"unit": "dpi", "value": normalized}


def _canonical_matrix(value: object, code: str) -> dict[str, object]:
    matrix = _closed(value, _MATRIX_FIELDS, code)
    coefficients = matrix["coefficients"]
    if not isinstance(coefficients, list) or len(coefficients) != 6:
        _fail(code)
    normalized = [
        _canonical_quantity(
            coefficient,
            quantity="render_matrix",
            unit=matrix["unit"],
            code=code,
        )
        for coefficient in coefficients
    ]
    return {"unit": "unitless", "coefficients": normalized}


def _page_identity(normalized: dict[str, object]) -> str:
    material = {
        key: value
        for key, value in normalized.items()
        if key != "page_locator_sha256"
    }
    return _canonical_json_sha256(
        {
            "identity_kind": "r1c-page-locator-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **material,
        }
    )


def _region_identity(normalized: dict[str, object]) -> str:
    material = {
        key: value
        for key, value in normalized.items()
        if key != "region_locator_sha256"
    }
    return _canonical_json_sha256(
        {
            "identity_kind": "r1c-region-locator-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **material,
        }
    )


def _render_identity(normalized: dict[str, object]) -> str:
    material = {
        key: value
        for key, value in normalized.items()
        if key != "render_provenance_sha256"
    }
    return _canonical_json_sha256(
        {
            "identity_kind": "r1c-render-provenance-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **material,
        }
    )


def _normalize_page_record(
    value: object,
    *,
    custody: dict[str, object],
    custody_sha256: str,
) -> dict[str, object]:
    record = _closed(value, _PAGE_FIELDS, "PAGE_LOCATOR_INVALID")
    supplied_id = _sha256(record["page_locator_sha256"], "PAGE_LOCATOR_INVALID")
    record_custody = _sha256(
        record["source_custody_sha256"],
        "PAGE_LOCATOR_INVALID",
    )
    if record_custody != custody_sha256:
        _fail("STALE_CUSTODY_HASH")
    if record["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
        _fail("PAGE_LOCATOR_INVALID")
    source_id = _identifier(record["source_id"], "PAGE_LOCATOR_INVALID")
    page_id = _identifier(record["page_id"], "PAGE_LOCATOR_INVALID")
    page_index = _strict_nonnegative_int(
        record["page_index"],
        "PAGE_LOCATOR_INVALID",
    )
    observed_pdf_sha256 = _sha256(
        record["observed_pdf_sha256"],
        "PAGE_LOCATOR_INVALID",
    )
    rotation = record["rotation"]
    if isinstance(rotation, bool) or not isinstance(rotation, int):
        _fail("PAGE_LOCATOR_INVALID")
    media_box = _canonical_box(record["media_box"], "PAGE_LOCATOR_INVALID")
    crop_box = _canonical_box(record["crop_box"], "PAGE_LOCATOR_INVALID")
    user_unit = _canonical_ratio(record["user_unit"], "PAGE_LOCATOR_INVALID")
    normalized = {
        "page_locator_sha256": supplied_id,
        "source_custody_sha256": record_custody,
        "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
        "source_id": source_id,
        "page_id": page_id,
        "page_index": page_index,
        "observed_pdf_sha256": observed_pdf_sha256,
        "media_box": media_box,
        "crop_box": crop_box,
        "rotation": rotation,
        "user_unit": user_unit,
    }

    item = _custody_items(custody).get(source_id)
    if item is None or item["kind"] != "PDF":
        _fail("PAGE_FACT_MISMATCH")
    pages = item["media_metadata"]["pages"]
    if page_index >= len(pages):
        _fail("PAGE_INDEX_OUT_OF_RANGE")
    observed_page = pages[page_index]
    if observed_pdf_sha256 != item["observed_sha256"]:
        _fail("PAGE_FACT_MISMATCH")
    if media_box["coordinates"] != observed_page["media_box"]:
        _fail("PAGE_FACT_MISMATCH")
    if crop_box["coordinates"] != observed_page["crop_box"]:
        _fail("PAGE_FACT_MISMATCH")
    if rotation != observed_page["rotation"]:
        _fail("PAGE_FACT_MISMATCH")
    if user_unit["value"] != observed_page["user_unit"]:
        _fail("PAGE_FACT_MISMATCH")

    if _page_identity(normalized) != supplied_id:
        _fail("DETERMINISTIC_ID_MISMATCH")
    return normalized


def _page_map(
    page_locators: object,
    *,
    custody: dict[str, object],
    custody_sha256: str,
) -> dict[str, dict[str, object]]:
    if not isinstance(page_locators, list):
        _fail("PAGE_LOCATOR_INVALID")
    result: dict[str, dict[str, object]] = {}
    for value in page_locators:
        normalized = _normalize_page_record(
            value,
            custody=custody,
            custody_sha256=custody_sha256,
        )
        digest = str(normalized["page_locator_sha256"])
        if digest in result:
            _fail("PAGE_LOCATOR_INVALID")
        result[digest] = normalized
    return result


def validate_page_locators(
    payload: object,
    *,
    source_bundle: object,
    custody: object,
) -> list[dict[str, object]]:
    """Validate explicit PDF page locators against accepted custody facts."""
    try:
        bundle = _validate_source_bundle(source_bundle)
        bundle_sha256 = _source_bundle_sha256(bundle)
    except Exception:
        _fail("SOURCE_BUNDLE_INVALID")
    normalized_custody = _validated_custody(custody)
    custody_sha256 = _custody_digest(normalized_custody)
    if (
        normalized_custody["bundle_id"] != bundle["bundle_id"]
        or normalized_custody["run_id"] != bundle["run_id"]
        or normalized_custody["source_bundle_sha256"] != bundle_sha256
    ):
        _fail("CUSTODY_CONTEXT_MISMATCH")
    if not isinstance(payload, list):
        _fail("PAGE_LOCATOR_INVALID")

    declared = {
        (str(item["source_id"]), str(page_id))
        for item in bundle["items"]
        if item["kind"] == "PDF"
        for page_id in item["page_ids"]
    }
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, object]] = []
    for value in payload:
        if not isinstance(value, _Mapping):
            _fail("PAGE_LOCATOR_INVALID")
        pair = (str(value.get("source_id")), str(value.get("page_id")))
        if pair in seen:
            _fail("PAGE_LOCATOR_DUPLICATE")
        seen.add(pair)
        normalized.append(
            _normalize_page_record(
                value,
                custody=normalized_custody,
                custody_sha256=custody_sha256,
            )
        )

    if seen != declared:
        _fail("PAGE_LOCATOR_COVERAGE_MISMATCH")
    normalized.sort(
        key=lambda record: (
            str(record["source_id"]),
            str(record["page_id"]),
            int(record["page_index"]),
            str(record["page_locator_sha256"]),
        )
    )
    return _copy.deepcopy(normalized)


def _normalize_raster_bounds(
    value: object,
    *,
    width: int,
    height: int,
) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        _fail("REGION_BOUNDS_INVALID")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        _fail("REGION_BOUNDS_INVALID")
    x0, y0, x1, y1 = value
    if x0 >= x1 or y0 >= y1:
        _fail("REGION_BOUNDS_INVALID")
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        _fail("REGION_BOUNDS_OUT_OF_RANGE")
    return [x0, y0, x1, y1]


def _normalize_pdf_bounds(
    value: object,
    *,
    selected_box: dict[str, object],
) -> dict[str, object]:
    bounds = _canonical_box(value, "REGION_LOCATOR_INVALID")
    numeric = [_decimal.Decimal(str(item)) for item in bounds["coordinates"]]
    selected = [
        _decimal.Decimal(str(item))
        for item in selected_box["coordinates"]
    ]
    if numeric[0] >= numeric[2] or numeric[1] >= numeric[3]:
        _fail("REGION_BOUNDS_INVALID")
    if (
        numeric[0] < selected[0]
        or numeric[1] < selected[1]
        or numeric[2] > selected[2]
        or numeric[3] > selected[3]
    ):
        _fail("REGION_BOUNDS_OUT_OF_RANGE")
    return bounds


def _normalize_region_record(
    value: object,
    *,
    custody: dict[str, object],
    custody_sha256: str,
    pages: dict[str, dict[str, object]],
) -> dict[str, object]:
    if not isinstance(value, _Mapping):
        _fail("REGION_LOCATOR_INVALID")
    convention = value.get("coordinate_convention")
    if convention == _RASTER_CONVENTION:
        record = _closed(
            value,
            _RASTER_REGION_FIELDS,
            "REGION_LOCATOR_INVALID",
        )
    elif convention == _PDF_CONVENTION:
        record = _closed(value, _PDF_REGION_FIELDS, "REGION_LOCATOR_INVALID")
    else:
        _fail("REGION_LOCATOR_INVALID")

    supplied_id = _sha256(
        record["region_locator_sha256"],
        "REGION_LOCATOR_INVALID",
    )
    record_custody = _sha256(
        record["source_custody_sha256"],
        "REGION_LOCATOR_INVALID",
    )
    if record_custody != custody_sha256:
        _fail("STALE_CUSTODY_HASH")
    if record["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
        _fail("REGION_LOCATOR_INVALID")
    source_id = _identifier(record["source_id"], "REGION_LOCATOR_INVALID")
    region_id = _identifier(record["region_id"], "REGION_LOCATOR_INVALID")
    locator_kind = record["locator_kind"]
    if locator_kind not in _LOCATOR_KINDS:
        _fail("REGION_LOCATOR_INVALID")
    item = _custody_items(custody).get(source_id)
    if item is None:
        _fail("REGION_PARENT_MISMATCH")

    if convention == _RASTER_CONVENTION:
        raster_sha256 = _sha256(
            record["raster_sha256"],
            "REGION_LOCATOR_INVALID",
        )
        width = _strict_positive_int(
            record["raster_width_px"],
            "REGION_LOCATOR_INVALID",
        )
        height = _strict_positive_int(
            record["raster_height_px"],
            "REGION_LOCATOR_INVALID",
        )
        page_ref = record["page_locator_sha256"]
        render_ref = record["render_provenance_sha256"]
        if item["kind"] == "IMAGE":
            if page_ref is not None or render_ref is not None:
                _fail("REGION_PARENT_MISMATCH")
            metadata = item["media_metadata"]
            if (
                raster_sha256 != item["observed_sha256"]
                or width != metadata["width_px"]
                or height != metadata["height_px"]
            ):
                _fail("REGION_PARENT_MISMATCH")
            normalized_page_ref = None
            normalized_render_ref = None
        elif item["kind"] == "PDF":
            normalized_page_ref = _sha256(
                page_ref,
                "REGION_PARENT_MISMATCH",
            )
            normalized_render_ref = _sha256(
                render_ref,
                "REGION_PARENT_MISMATCH",
            )
            parent = pages.get(normalized_page_ref)
            if parent is None or parent["source_id"] != source_id:
                _fail("REGION_PARENT_MISMATCH")
        else:
            _fail("REGION_PARENT_MISMATCH")
        bounds = _normalize_raster_bounds(
            record["bounds"],
            width=width,
            height=height,
        )
        normalized = {
            "region_locator_sha256": supplied_id,
            "source_custody_sha256": record_custody,
            "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
            "source_id": source_id,
            "region_id": region_id,
            "locator_kind": locator_kind,
            "coordinate_convention": _RASTER_CONVENTION,
            "page_locator_sha256": normalized_page_ref,
            "render_provenance_sha256": normalized_render_ref,
            "raster_sha256": raster_sha256,
            "raster_width_px": width,
            "raster_height_px": height,
            "bounds": bounds,
        }
    else:
        if item["kind"] != "PDF":
            _fail("REGION_PARENT_MISMATCH")
        page_ref = _sha256(
            record["page_locator_sha256"],
            "REGION_PARENT_MISMATCH",
        )
        parent = pages.get(page_ref)
        if parent is None or parent["source_id"] != source_id:
            _fail("REGION_PARENT_MISMATCH")
        box_kind = record["box_kind"]
        if box_kind not in _BOX_KINDS:
            _fail("REGION_LOCATOR_INVALID")
        rotation = record["rotation"]
        if isinstance(rotation, bool) or not isinstance(rotation, int):
            _fail("REGION_LOCATOR_INVALID")
        user_unit = _canonical_ratio(
            record["user_unit"],
            "REGION_LOCATOR_INVALID",
        )
        if rotation != parent["rotation"] or user_unit != parent["user_unit"]:
            _fail("REGION_PARENT_MISMATCH")
        selected_box = (
            parent["media_box"]
            if box_kind == "MEDIA_BOX"
            else parent["crop_box"]
        )
        bounds = _normalize_pdf_bounds(record["bounds"], selected_box=selected_box)
        normalized = {
            "region_locator_sha256": supplied_id,
            "source_custody_sha256": record_custody,
            "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
            "source_id": source_id,
            "region_id": region_id,
            "locator_kind": locator_kind,
            "coordinate_convention": _PDF_CONVENTION,
            "page_locator_sha256": page_ref,
            "box_kind": box_kind,
            "rotation": rotation,
            "user_unit": user_unit,
            "bounds": bounds,
        }

    if _region_identity(normalized) != supplied_id:
        _fail("DETERMINISTIC_ID_MISMATCH")
    return normalized


def validate_region_locators(
    payload: object,
    *,
    page_locators: object,
    custody: object,
) -> list[dict[str, object]]:
    """Validate explicit region locators and exact parent bindings."""
    normalized_custody = _validated_custody(custody)
    custody_sha256 = _custody_digest(normalized_custody)
    pages = _page_map(
        page_locators,
        custody=normalized_custody,
        custody_sha256=custody_sha256,
    )
    if not isinstance(payload, list):
        _fail("REGION_LOCATOR_INVALID")
    declared = {
        (str(item["source_id"]), str(region_id))
        for item in normalized_custody["items"]
        for region_id in item["region_ids"]
    }
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, object]] = []
    for value in payload:
        if not isinstance(value, _Mapping):
            _fail("REGION_LOCATOR_INVALID")
        pair = (str(value.get("source_id")), str(value.get("region_id")))
        if pair in seen:
            _fail("REGION_LOCATOR_INVALID")
        seen.add(pair)
        normalized.append(
            _normalize_region_record(
                value,
                custody=normalized_custody,
                custody_sha256=custody_sha256,
                pages=pages,
            )
        )
    if seen != declared:
        _fail("REGION_LOCATOR_COVERAGE_MISMATCH")
    normalized.sort(
        key=lambda record: (
            str(record["source_id"]),
            str(record["region_id"]),
            str(record["locator_kind"]),
            str(record["region_locator_sha256"]),
        )
    )
    return _copy.deepcopy(normalized)


def _primitive_source_document(
    value: object,
    code: str,
) -> _Mapping[str, object]:
    document = _closed(value, _SOURCE_DOCUMENT_FIELDS, code)
    if not isinstance(document["file_name"], str):
        _fail(code)
    _strict_nonnegative_int(document["page_index"], code)
    _strict_positive_int(document["image_width_px"], code)
    _strict_positive_int(document["image_height_px"], code)
    _sha256(document["sha256"], code)
    return document


def _normalize_render_record(
    value: object,
    *,
    custody: dict[str, object],
    custody_sha256: str,
    pages: dict[str, dict[str, object]],
    primitive_artifact_sha256: str,
) -> dict[str, object]:
    if not isinstance(value, _Mapping):
        _fail("RENDER_PROVENANCE_INVALID")
    kind = value.get("provenance_kind")
    if kind == "DIRECT_IMAGE":
        record = _closed(
            value,
            _DIRECT_RENDER_FIELDS,
            "RENDER_PROVENANCE_INVALID",
        )
    elif kind == "PDF_RENDER":
        record = _closed(
            value,
            _PDF_RENDER_FIELDS,
            "RENDER_PROVENANCE_INVALID",
        )
    else:
        _fail("RENDER_PROVENANCE_INVALID")

    supplied_id = _sha256(
        record["render_provenance_sha256"],
        "RENDER_PROVENANCE_INVALID",
    )
    record_custody = _sha256(
        record["source_custody_sha256"],
        "RENDER_PROVENANCE_INVALID",
    )
    if record_custody != custody_sha256:
        _fail("STALE_CUSTODY_HASH")
    if record["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
        _fail("RENDER_PROVENANCE_INVALID")
    source_id = _identifier(record["source_id"], "RENDER_PROVENANCE_INVALID")
    observed_source_sha256 = _sha256(
        record["observed_source_sha256"],
        "RENDER_PROVENANCE_INVALID",
    )
    raster_sha256 = _sha256(
        record["raster_sha256"],
        "RENDER_PROVENANCE_INVALID",
    )
    raster_width = _strict_positive_int(
        record["raster_width_px"],
        "RENDER_PROVENANCE_INVALID",
    )
    raster_height = _strict_positive_int(
        record["raster_height_px"],
        "RENDER_PROVENANCE_INVALID",
    )
    record_artifact_sha256 = _sha256(
        record["primitive_artifact_sha256"],
        "RENDER_PROVENANCE_INVALID",
    )
    if record_artifact_sha256 != primitive_artifact_sha256:
        _fail("PRIMITIVE_BINDING_MISMATCH")
    document = _primitive_source_document(
        record["primitive_source_document"],
        "RENDER_PROVENANCE_INVALID",
    )
    item = _custody_items(custody).get(source_id)
    if item is None:
        _fail("RENDER_SOURCE_MISMATCH")

    common = {
        "render_provenance_sha256": supplied_id,
        "provenance_kind": kind,
        "source_custody_sha256": record_custody,
        "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
        "source_id": source_id,
        "observed_source_sha256": observed_source_sha256,
        "raster_sha256": raster_sha256,
        "raster_width_px": raster_width,
        "raster_height_px": raster_height,
        "primitive_artifact_sha256": record_artifact_sha256,
    }

    if kind == "DIRECT_IMAGE":
        if item["kind"] != "IMAGE" or observed_source_sha256 != item["observed_sha256"]:
            _fail("RENDER_SOURCE_MISMATCH")
        metadata = item["media_metadata"]
        if (
            raster_sha256 != item["observed_sha256"]
            or raster_width != metadata["width_px"]
            or raster_height != metadata["height_px"]
        ):
            _fail("RENDER_FACT_MISMATCH")
        if (
            document["sha256"] != raster_sha256
            or document["image_width_px"] != raster_width
            or document["image_height_px"] != raster_height
        ):
            _fail("PRIMITIVE_BINDING_MISMATCH")
        normalized = {
            **common,
            "primitive_source_document": {
                "sha256": document["sha256"],
                "image_width_px": document["image_width_px"],
                "image_height_px": document["image_height_px"],
            },
        }
    else:
        if item["kind"] != "PDF" or observed_source_sha256 != item["observed_sha256"]:
            _fail("RENDER_SOURCE_MISMATCH")
        page_ref = _sha256(
            record["page_locator_sha256"],
            "RENDER_PROVENANCE_INVALID",
        )
        parent = pages.get(page_ref)
        if parent is None or parent["source_id"] != source_id:
            _fail("RENDER_PAGE_MISMATCH")
        pdf_page_index = _strict_nonnegative_int(
            record["pdf_page_index"],
            "RENDER_PROVENANCE_INVALID",
        )
        if pdf_page_index != parent["page_index"]:
            _fail("RENDER_PAGE_MISMATCH")
        box_kind = record["box_kind"]
        if box_kind not in _BOX_KINDS:
            _fail("RENDER_PROVENANCE_INVALID")
        selected_box = _canonical_box(
            record["selected_box"],
            "RENDER_PROVENANCE_INVALID",
        )
        expected_box = (
            parent["media_box"]
            if box_kind == "MEDIA_BOX"
            else parent["crop_box"]
        )
        rotation = record["rotation"]
        if isinstance(rotation, bool) or not isinstance(rotation, int):
            _fail("RENDER_PROVENANCE_INVALID")
        user_unit = _canonical_ratio(
            record["user_unit"],
            "RENDER_PROVENANCE_INVALID",
        )
        if (
            selected_box != expected_box
            or rotation != parent["rotation"]
            or user_unit != parent["user_unit"]
        ):
            _fail("RENDER_FACT_MISMATCH")
        render_dpi = _canonical_dpi(
            record["render_dpi"],
            "RENDER_PROVENANCE_INVALID",
        )
        render_matrix = _canonical_matrix(
            record["render_matrix"],
            "RENDER_PROVENANCE_INVALID",
        )
        if (
            document["sha256"] != raster_sha256
            or document["image_width_px"] != raster_width
            or document["image_height_px"] != raster_height
        ):
            _fail("PRIMITIVE_BINDING_MISMATCH")
        normalized = {
            **common,
            "page_locator_sha256": page_ref,
            "pdf_page_index": pdf_page_index,
            "box_kind": box_kind,
            "selected_box": selected_box,
            "rotation": rotation,
            "user_unit": user_unit,
            "render_dpi": render_dpi,
            "render_matrix": render_matrix,
            "primitive_source_document": {
                "sha256": document["sha256"],
                "image_width_px": document["image_width_px"],
                "image_height_px": document["image_height_px"],
                "primitive_source_page_index": document["page_index"],
            },
        }

    if _render_identity(normalized) != supplied_id:
        _fail("DETERMINISTIC_ID_MISMATCH")
    return normalized


def validate_render_provenance(
    payload: object,
    *,
    page_locators: object,
    custody: object,
    primitive_artifact_sha256: object,
) -> list[dict[str, object]]:
    """Validate PDF-render/direct-image provenance against accepted facts."""
    normalized_custody = _validated_custody(custody)
    custody_sha256 = _custody_digest(normalized_custody)
    artifact_sha256 = _sha256(
        primitive_artifact_sha256,
        "RENDER_PROVENANCE_INVALID",
    )
    pages = _page_map(
        page_locators,
        custody=normalized_custody,
        custody_sha256=custody_sha256,
    )
    if not isinstance(payload, list):
        _fail("RENDER_PROVENANCE_INVALID")
    normalized = [
        _normalize_render_record(
            value,
            custody=normalized_custody,
            custody_sha256=custody_sha256,
            pages=pages,
            primitive_artifact_sha256=artifact_sha256,
        )
        for value in payload
    ]
    normalized.sort(
        key=lambda record: (
            str(record["source_id"]),
            str(record.get("page_locator_sha256") or ""),
            str(record["raster_sha256"]),
            str(record["primitive_artifact_sha256"]),
            str(record["render_provenance_sha256"]),
        )
    )
    return _copy.deepcopy(normalized)
