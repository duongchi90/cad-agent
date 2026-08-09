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


canonicalize_r1c_quantity = _canonicalize_r1c_quantity
canonical_json_sha256 = _canonical_json_sha256

_TASK5_PRIMITIVE_REQUIRED_FIELDS = {
    "id",
    "type",
    "source",
    "confidence",
    "layer",
    "handle",
    "trace",
    "validation",
}
_TASK5_PRIMITIVE_OPTIONAL_FIELDS = {"geometry", "text_data"}
_TASK5_PRIMITIVE_ARTIFACT_FIELDS = {
    "schema_version",
    "source_document",
    "calibration",
    "primitives",
    "cross_validations",
}
_TASK5_CALIBRATION_REQUIRED_FIELDS = {
    "unit",
    "pixel_to_unit_scale",
    "origin_px",
    "method",
    "status",
}
_TASK5_CALIBRATION_OPTIONAL_FIELDS = {"reference_note", "source_sha256"}
_TASK5_TRACE_REQUIRED_FIELDS = {"bbox_px"}
_TASK5_TRACE_OPTIONAL_FIELDS = {"extraction_tool", "extracted_at"}
_TASK5_VALIDATION_REQUIRED_FIELDS = {"status"}
_TASK5_VALIDATION_OPTIONAL_FIELDS = {"notes"}
_TASK5_POINT_FIELDS = {"x", "y"}
_TASK5_LINE_FIELDS = {"start", "end"}
_TASK5_CIRCLE_FIELDS = {"center", "radius"}
_TASK5_ARC_FIELDS = {"center", "radius", "start_angle_deg", "end_angle_deg"}
_TASK5_TEXT_FIELDS = {
    "content",
    "position",
    "rotation_deg",
    "height",
    "parsed_value",
    "semantic_role",
}
_TASK5_CROSS_VALIDATION_REQUIRED_FIELDS = {
    "id",
    "text_primitive_id",
    "geometry_primitive_id",
    "status",
    "match_threshold_percent",
}
_TASK5_CROSS_VALIDATION_OPTIONAL_FIELDS = {
    "text_value",
    "geometry_measured_length",
    "delta_percent",
}
_TASK5_SEMANTIC_ARTIFACT_FIELDS = {
    "schema_version",
    "primitive_ir_ref",
    "parts",
    "constraints",
}
_TASK5_PRIMITIVE_REF_REQUIRED_FIELDS = {"file_name", "primitive_count"}
_TASK5_PRIMITIVE_REF_OPTIONAL_FIELDS = {"sha256"}
_TASK5_PART_REQUIRED_FIELDS = {
    "id",
    "part_type",
    "primitive_ids",
    "confidence",
    "source",
    "validation",
}
_TASK5_PART_OPTIONAL_FIELDS = {"geometry_summary"}
_TASK5_GEOMETRY_SUMMARY_FIELDS = {"length_mm", "orientation_deg", "radius_mm"}
_TASK5_CONSTRAINT_REQUIRED_FIELDS = {
    "id",
    "type",
    "primitive_ids",
    "confidence",
    "tolerance",
}
_TASK5_CONSTRAINT_OPTIONAL_FIELDS = {"measured"}
_TASK5_DIRECT_BINDING_DOCUMENT_FIELDS = {
    "sha256",
    "image_width_px",
    "image_height_px",
}
_TASK5_PDF_BINDING_DOCUMENT_FIELDS = {
    "sha256",
    "image_width_px",
    "image_height_px",
    "primitive_source_page_index",
}
_TASK5_PRIMITIVE_REF_BASENAME = "primitive_ir.json"
_TASK5_TOLERANCE_QUANTITIES = {
    "angle_deg": ("angle", "degree"),
    "length_percent": ("scale", "ratio"),
    "distance_mm": ("physical_length", "mm"),
}
_TASK5_MEASURED_QUANTITIES = {
    "angle_diff_deg": ("angle", "degree"),
    "length_diff_percent": ("scale", "ratio"),
    "endpoint_distance_mm": ("physical_length", "mm"),
    "tangent_gap_mm": ("physical_length", "mm"),
    "center_distance_mm": ("physical_length", "mm"),
}


def _task5_closed_with_optional(
    value: object,
    *,
    required: set[str],
    optional: set[str],
    code: str,
):
    if not isinstance(value, _Mapping):
        _fail(code)
    keys = set(value)
    if any(not isinstance(key, str) for key in keys):
        _fail(code)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        _fail(code)
    return value


def _task5_canonical_quantity(
    value: object,
    *,
    quantity: str,
    unit: str,
    code: str,
) -> str:
    try:
        return canonicalize_r1c_quantity(
            value,
            quantity=quantity,
            unit=unit,
        )["value"]
    except Exception:
        _fail(code)


def _task5_decimal(value: object, code: str):
    canonical = _task5_canonical_quantity(
        value,
        quantity="scale",
        unit="ratio",
        code=code,
    )
    return _decimal.Decimal(canonical)


def _task5_physical_coordinate(
    value: object,
    *,
    calibration_unit: str,
    scale: _decimal.Decimal,
    code: str,
) -> str:
    raw = _task5_decimal(value, code)
    return _task5_canonical_quantity(
        raw * scale,
        quantity="physical_length",
        unit=calibration_unit,
        code=code,
    )


def _task5_point_mm(
    value: object,
    *,
    calibration_unit: str,
    scale: _decimal.Decimal,
    code: str,
) -> list[str]:
    point = _closed(value, _TASK5_POINT_FIELDS, code)
    return [
        _task5_physical_coordinate(
            point[axis],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        for axis in ("x", "y")
    ]


def _task5_validate_trace(value: object, code: str) -> None:
    trace = _task5_closed_with_optional(
        value,
        required=_TASK5_TRACE_REQUIRED_FIELDS,
        optional=_TASK5_TRACE_OPTIONAL_FIELDS,
        code=code,
    )
    bbox = trace["bbox_px"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        _fail(code)
    for coordinate in bbox:
        _task5_decimal(coordinate, code)
    extraction_tool = trace.get("extraction_tool")
    if extraction_tool is not None and not isinstance(extraction_tool, str):
        _fail(code)
    extracted_at = trace.get("extracted_at")
    if extracted_at is not None and not isinstance(extracted_at, str):
        _fail(code)


def _task5_validate_validation(value: object, code: str) -> None:
    validation = _task5_closed_with_optional(
        value,
        required=_TASK5_VALIDATION_REQUIRED_FIELDS,
        optional=_TASK5_VALIDATION_OPTIONAL_FIELDS,
        code=code,
    )
    if not isinstance(validation["status"], str):
        _fail(code)
    if validation.get("notes") is not None and not isinstance(
        validation["notes"],
        str,
    ):
        _fail(code)


def _task5_normalize_binding(
    value: object,
    *,
    primitive_artifact_sha256: str,
    source_document: _Mapping[str, object],
) -> dict[str, object]:
    code = "PRIMITIVE_BINDING_MISMATCH"
    if not isinstance(value, _Mapping):
        _fail(code)
    kind = value.get("provenance_kind")
    if kind == "DIRECT_IMAGE":
        record = _closed(value, _DIRECT_RENDER_FIELDS, code)
        document_fields = _TASK5_DIRECT_BINDING_DOCUMENT_FIELDS
    elif kind == "PDF_RENDER":
        record = _closed(value, _PDF_RENDER_FIELDS, code)
        document_fields = _TASK5_PDF_BINDING_DOCUMENT_FIELDS
    else:
        _fail(code)
    normalized = _copy.deepcopy(dict(record))
    _sha256(normalized["render_provenance_sha256"], code)
    _sha256(normalized["source_custody_sha256"], code)
    _identifier(normalized["source_id"], code)
    _sha256(normalized["observed_source_sha256"], code)
    _sha256(normalized["raster_sha256"], code)
    _strict_positive_int(normalized["raster_width_px"], code)
    _strict_positive_int(normalized["raster_height_px"], code)
    if normalized["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
        _fail(code)
    if (
        _sha256(normalized["primitive_artifact_sha256"], code)
        != primitive_artifact_sha256
    ):
        _fail(code)
    document = _closed(
        normalized["primitive_source_document"],
        document_fields,
        code,
    )
    _sha256(document["sha256"], code)
    _strict_positive_int(document["image_width_px"], code)
    _strict_positive_int(document["image_height_px"], code)
    if kind == "PDF_RENDER":
        _strict_nonnegative_int(document["primitive_source_page_index"], code)
        _sha256(normalized["page_locator_sha256"], code)
        _strict_nonnegative_int(normalized["pdf_page_index"], code)
        if normalized["box_kind"] not in _BOX_KINDS:
            _fail(code)
        _canonical_box(normalized["selected_box"], code)
        rotation = normalized["rotation"]
        if isinstance(rotation, bool) or not isinstance(rotation, int):
            _fail(code)
        _canonical_ratio(normalized["user_unit"], code)
        _canonical_dpi(normalized["render_dpi"], code)
        _canonical_matrix(normalized["render_matrix"], code)
    if _render_identity(normalized) != normalized["render_provenance_sha256"]:
        _fail(code)
    if (
        document["sha256"] != source_document["sha256"]
        or document["image_width_px"] != source_document["image_width_px"]
        or document["image_height_px"] != source_document["image_height_px"]
    ):
        _fail(code)
    source_page_index = _strict_nonnegative_int(source_document["page_index"], code)
    if kind == "DIRECT_IMAGE":
        if source_page_index != 0:
            _fail(code)
    elif source_page_index != document["primitive_source_page_index"]:
        _fail(code)
    return normalized


def _task5_select_source_binding(
    source_bindings: object,
    *,
    primitive_artifact_sha256: str,
    source_document: _Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(source_bindings, list) or not source_bindings:
        _fail("PRIMITIVE_BINDING_MISMATCH")
    unique: dict[str, dict[str, object]] = {}
    for value in source_bindings:
        normalized = _task5_normalize_binding(
            value,
            primitive_artifact_sha256=primitive_artifact_sha256,
            source_document=source_document,
        )
        digest = canonical_json_sha256(normalized)
        unique.setdefault(digest, normalized)
    if len(unique) != 1:
        _fail("PRIMITIVE_BINDING_AMBIGUITY")
    return _copy.deepcopy(next(iter(unique.values())))


def _task5_task4_lineage_material(
    binding: _Mapping[str, object],
) -> dict[str, object]:
    """Return stable Task-4 evidence that belongs in primitive identity."""
    return {
        key: _copy.deepcopy(value)
        for key, value in binding.items()
        if key not in {"render_provenance_sha256", "primitive_artifact_sha256"}
    }


def _task5_calibration(
    value: object,
    source_sha256: str,
) -> tuple[str, _decimal.Decimal]:
    code = "PRIMITIVE_ARTIFACT_INVALID"
    calibration = _task5_closed_with_optional(
        value,
        required=_TASK5_CALIBRATION_REQUIRED_FIELDS,
        optional=_TASK5_CALIBRATION_OPTIONAL_FIELDS,
        code=code,
    )
    unit = calibration["unit"]
    if unit not in {"mm", "cm", "m"}:
        _fail(code)
    scale_text = _task5_canonical_quantity(
        calibration["pixel_to_unit_scale"],
        quantity="scale",
        unit="ratio",
        code=code,
    )
    scale = _decimal.Decimal(scale_text)
    if scale <= 0:
        _fail(code)
    origin = calibration["origin_px"]
    if not isinstance(origin, list) or len(origin) != 2:
        _fail(code)
    for coordinate in origin:
        _task5_decimal(coordinate, code)
    if not isinstance(calibration["method"], str):
        _fail(code)
    if not isinstance(calibration["status"], str):
        _fail(code)
    calibration_source = calibration.get("source_sha256")
    if calibration_source is not None:
        if _sha256(calibration_source, code) != source_sha256:
            _fail(code)
    reference_note = calibration.get("reference_note")
    if reference_note is not None and not isinstance(reference_note, str):
        _fail(code)
    return str(unit), scale


def _task5_validate_cross_validations(value: object) -> None:
    code = "PRIMITIVE_ARTIFACT_INVALID"
    if not isinstance(value, list):
        _fail(code)
    for item in value:
        record = _task5_closed_with_optional(
            item,
            required=_TASK5_CROSS_VALIDATION_REQUIRED_FIELDS,
            optional=_TASK5_CROSS_VALIDATION_OPTIONAL_FIELDS,
            code=code,
        )
        _identifier(record["id"], code)
        _identifier(record["text_primitive_id"], code)
        _identifier(record["geometry_primitive_id"], code)
        if not isinstance(record["status"], str):
            _fail(code)
        _task5_canonical_quantity(
            record["match_threshold_percent"],
            quantity="scale",
            unit="ratio",
            code=code,
        )
        if "text_value" in record:
            _task5_canonical_quantity(
                record["text_value"],
                quantity="measurement",
                unit="mm",
                code=code,
            )
        if "geometry_measured_length" in record:
            _task5_canonical_quantity(
                record["geometry_measured_length"],
                quantity="physical_length",
                unit="mm",
                code=code,
            )
        if "delta_percent" in record:
            _task5_canonical_quantity(
                record["delta_percent"],
                quantity="scale",
                unit="ratio",
                code=code,
            )


def _task5_primitive_content(
    value: object,
    *,
    calibration_unit: str,
    scale: _decimal.Decimal,
) -> tuple[str, dict[str, object]]:
    code = "PRIMITIVE_ARTIFACT_INVALID"
    primitive = _task5_closed_with_optional(
        value,
        required=_TASK5_PRIMITIVE_REQUIRED_FIELDS,
        optional=_TASK5_PRIMITIVE_OPTIONAL_FIELDS,
        code=code,
    )
    legacy_id = _identifier(primitive["id"], code)
    kind = primitive["type"]
    if kind not in {"line", "circle", "arc", "text"}:
        _fail(code)
    if not isinstance(primitive["source"], str):
        _fail(code)
    if not isinstance(primitive["layer"], str):
        _fail(code)
    if primitive["handle"] is not None and not isinstance(
        primitive["handle"],
        str,
    ):
        _fail(code)
    _task5_validate_trace(primitive["trace"], code)
    _task5_validate_validation(primitive["validation"], code)
    confidence = _task5_canonical_quantity(
        primitive["confidence"],
        quantity="confidence",
        unit="unitless",
        code=code,
    )
    content: dict[str, object] = {"kind": kind, "confidence": confidence}
    if kind == "line":
        geometry = _closed(primitive.get("geometry"), _TASK5_LINE_FIELDS, code)
        if primitive.get("text_data") is not None:
            _fail(code)
        content["start_mm"] = _task5_point_mm(
            geometry["start"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["end_mm"] = _task5_point_mm(
            geometry["end"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
    elif kind == "circle":
        geometry = _closed(primitive.get("geometry"), _TASK5_CIRCLE_FIELDS, code)
        if primitive.get("text_data") is not None:
            _fail(code)
        content["center_mm"] = _task5_point_mm(
            geometry["center"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["radius_mm"] = _task5_physical_coordinate(
            geometry["radius"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
    elif kind == "arc":
        geometry = _closed(primitive.get("geometry"), _TASK5_ARC_FIELDS, code)
        if primitive.get("text_data") is not None:
            _fail(code)
        content["center_mm"] = _task5_point_mm(
            geometry["center"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["radius_mm"] = _task5_physical_coordinate(
            geometry["radius"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["start_angle_deg"] = _task5_canonical_quantity(
            geometry["start_angle_deg"],
            quantity="angle",
            unit="degree",
            code=code,
        )
        content["end_angle_deg"] = _task5_canonical_quantity(
            geometry["end_angle_deg"],
            quantity="angle",
            unit="degree",
            code=code,
        )
    else:
        if primitive.get("geometry") is not None:
            _fail(code)
        text = _closed(primitive.get("text_data"), _TASK5_TEXT_FIELDS, code)
        if not isinstance(text["content"], str):
            _fail(code)
        if not isinstance(text["semantic_role"], str):
            _fail(code)
        content["text"] = text["content"]
        content["position_mm"] = _task5_point_mm(
            text["position"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["rotation_deg"] = _task5_canonical_quantity(
            text["rotation_deg"],
            quantity="angle",
            unit="degree",
            code=code,
        )
        content["height_mm"] = _task5_physical_coordinate(
            text["height"],
            calibration_unit=calibration_unit,
            scale=scale,
            code=code,
        )
        content["semantic_role"] = text["semantic_role"]
        if text["parsed_value"] is not None:
            content["parsed_value_mm"] = _task5_canonical_quantity(
                text["parsed_value"],
                quantity="measurement",
                unit=calibration_unit,
                code=code,
            )
    return legacy_id, content


def project_primitive_observations(
    *,
    primitive_artifact: object,
    primitive_artifact_sha256: object,
    source_bindings: object,
) -> list[dict[str, object]]:
    code = "PRIMITIVE_ARTIFACT_INVALID"
    artifact_sha256 = _sha256(primitive_artifact_sha256, code)
    artifact = _closed(
        primitive_artifact,
        _TASK5_PRIMITIVE_ARTIFACT_FIELDS,
        code,
    )
    if artifact["schema_version"] != "1.0.0":
        _fail(code)
    source_document = _primitive_source_document(artifact["source_document"], code)
    binding = _task5_select_source_binding(
        source_bindings,
        primitive_artifact_sha256=artifact_sha256,
        source_document=source_document,
    )
    calibration_unit, scale = _task5_calibration(
        artifact["calibration"],
        str(source_document["sha256"]),
    )
    if not isinstance(artifact["primitives"], list):
        _fail(code)
    _task5_validate_cross_validations(artifact["cross_validations"])

    seen_ids: set[str] = set()
    classes: dict[str, dict[str, object]] = {}
    source_id = str(binding["source_id"])
    for primitive in artifact["primitives"]:
        legacy_id, content = _task5_primitive_content(
            primitive,
            calibration_unit=calibration_unit,
            scale=scale,
        )
        if legacy_id in seen_ids:
            _fail("DUPLICATE_PRIMITIVE_LEGACY_ID")
        seen_ids.add(legacy_id)
        material = {
            "identity_kind": "r1c-task5-projection-fixture-v1",
            "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
            "task4_lineage": _task5_task4_lineage_material(binding),
            "source_id": source_id,
            "content": content,
        }
        observation_key = canonical_json_sha256(material)
        record = classes.get(observation_key)
        if record is None:
            classes[observation_key] = {
                "observation_key": observation_key,
                "occurrence_count": 1,
                "legacy_ids": [legacy_id],
                "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
                "primitive_artifact_sha256": artifact_sha256,
                "source_binding": _copy.deepcopy(binding),
                "content": content,
            }
        else:
            record["occurrence_count"] = int(record["occurrence_count"]) + 1
            record["legacy_ids"].append(legacy_id)
    normalized = list(classes.values())
    for record in normalized:
        record["legacy_ids"] = sorted(record["legacy_ids"])
    normalized.sort(key=lambda record: str(record["observation_key"]))
    return _copy.deepcopy(normalized)


def _task5_validate_primitive_observations(
    primitive_observations: object,
    *,
    primitive_checkpoint_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], int]:
    code = "PRIMITIVE_OBSERVATIONS_INVALID"
    if not isinstance(primitive_observations, list):
        _fail(code)
    normalized: list[dict[str, object]] = []
    by_legacy_id: dict[str, dict[str, object]] = {}
    seen_observation_keys: set[str] = set()
    total = 0
    for value in primitive_observations:
        if not isinstance(value, _Mapping):
            _fail(code)
        required = {
            "observation_key",
            "occurrence_count",
            "legacy_ids",
            "numeric_policy_version",
            "primitive_artifact_sha256",
            "source_binding",
            "content",
        }
        record = _closed(value, required, code)
        observation_key = _sha256(record["observation_key"], code)
        if observation_key in seen_observation_keys:
            _fail(code)
        seen_observation_keys.add(observation_key)
        occurrence_count = _strict_positive_int(record["occurrence_count"], code)
        if record["numeric_policy_version"] != _R1C_NUMERIC_POLICY_VERSION:
            _fail(code)
        if (
            _sha256(record["primitive_artifact_sha256"], code)
            != primitive_checkpoint_sha256
        ):
            _fail("PRIMITIVE_CHECKPOINT_MISMATCH")
        legacy_ids = record["legacy_ids"]
        if not isinstance(legacy_ids, list) or len(legacy_ids) != occurrence_count:
            _fail(code)
        normalized_ids: list[str] = []
        for legacy_id in legacy_ids:
            normalized_id = _identifier(legacy_id, code)
            if normalized_id in normalized_ids or normalized_id in by_legacy_id:
                _fail(code)
            normalized_ids.append(normalized_id)
        cloned = _copy.deepcopy(dict(record))
        cloned["observation_key"] = observation_key
        cloned["legacy_ids"] = sorted(normalized_ids)
        for legacy_id in normalized_ids:
            by_legacy_id[legacy_id] = cloned
        normalized.append(cloned)
        total += occurrence_count
    normalized.sort(key=lambda record: str(record["observation_key"]))
    return normalized, by_legacy_id, total


def _task5_resolve_membership(
    primitive_ids: object,
    *,
    by_legacy_id: dict[str, dict[str, object]],
) -> list[str]:
    code = "SEMANTIC_REFERENCE_INVALID"
    if not isinstance(primitive_ids, list) or not primitive_ids:
        _fail(code)
    selected_by_key: dict[str, list[str]] = {}
    for value in primitive_ids:
        legacy_id = _identifier(value, code)
        record = by_legacy_id.get(legacy_id)
        if record is None:
            _fail(code)
        selected_by_key.setdefault(
            str(record["observation_key"]),
            [],
        ).append(legacy_id)
    keys: list[str] = []
    for observation_key, ids in selected_by_key.items():
        record = by_legacy_id[ids[0]]
        expected_ids = set(record["legacy_ids"])
        if len(ids) != len(set(ids)):
            if int(record["occurrence_count"]) > 1:
                _fail("DUPLICATE_OBSERVATION_AMBIGUITY")
            _fail(code)
        if int(record["occurrence_count"]) > 1 and set(ids) != expected_ids:
            _fail("DUPLICATE_OBSERVATION_AMBIGUITY")
        keys.extend([observation_key] * len(ids))
    keys.sort()
    return keys


def _task5_semantic_numeric_mapping(
    value: object,
    *,
    quantities: dict[str, tuple[str, str]],
    code: str,
) -> dict[str, str]:
    if not isinstance(value, _Mapping) or not value:
        _fail(code)
    if any(not isinstance(key, str) or key not in quantities for key in value):
        _fail(code)
    result: dict[str, str] = {}
    for key in sorted(value):
        quantity, unit = quantities[key]
        result[key] = _task5_canonical_quantity(
            value[key],
            quantity=quantity,
            unit=unit,
            code=code,
        )
    return result


def _task5_part_content(
    value: object,
    *,
    by_legacy_id: dict[str, dict[str, object]],
) -> tuple[dict[str, object], list[str]]:
    code = "SEMANTIC_ARTIFACT_INVALID"
    part = _task5_closed_with_optional(
        value,
        required=_TASK5_PART_REQUIRED_FIELDS,
        optional=_TASK5_PART_OPTIONAL_FIELDS,
        code=code,
    )
    _identifier(part["id"], code)
    if not isinstance(part["part_type"], str):
        _fail(code)
    if not isinstance(part["source"], str):
        _fail(code)
    _task5_validate_validation(part["validation"], code)
    confidence = _task5_canonical_quantity(
        part["confidence"],
        quantity="confidence",
        unit="unitless",
        code=code,
    )
    primitive_keys = _task5_resolve_membership(
        part["primitive_ids"],
        by_legacy_id=by_legacy_id,
    )
    content: dict[str, object] = {
        "kind": "part",
        "part_type": part["part_type"],
        "source": part["source"],
        "confidence": confidence,
        "primitive_observation_keys": primitive_keys,
    }
    if "geometry_summary" in part:
        summary = part["geometry_summary"]
        if not isinstance(summary, _Mapping):
            _fail(code)
        if any(
            not isinstance(key, str)
            or key not in _TASK5_GEOMETRY_SUMMARY_FIELDS
            for key in summary
        ):
            _fail(code)
        geometry: dict[str, str] = {}
        for key in sorted(summary):
            if key == "orientation_deg":
                geometry[key] = _task5_canonical_quantity(
                    summary[key],
                    quantity="angle",
                    unit="degree",
                    code=code,
                )
            else:
                geometry[key] = _task5_canonical_quantity(
                    summary[key],
                    quantity="physical_length",
                    unit="mm",
                    code=code,
                )
        content["geometry_summary"] = geometry
    return content, primitive_keys


def _task5_constraint_content(
    value: object,
    *,
    by_legacy_id: dict[str, dict[str, object]],
) -> tuple[dict[str, object], list[str]]:
    code = "SEMANTIC_ARTIFACT_INVALID"
    constraint = _task5_closed_with_optional(
        value,
        required=_TASK5_CONSTRAINT_REQUIRED_FIELDS,
        optional=_TASK5_CONSTRAINT_OPTIONAL_FIELDS,
        code=code,
    )
    _identifier(constraint["id"], code)
    if not isinstance(constraint["type"], str):
        _fail(code)
    confidence = _task5_canonical_quantity(
        constraint["confidence"],
        quantity="confidence",
        unit="unitless",
        code=code,
    )
    primitive_keys = _task5_resolve_membership(
        constraint["primitive_ids"],
        by_legacy_id=by_legacy_id,
    )
    content: dict[str, object] = {
        "kind": "constraint",
        "constraint_type": constraint["type"],
        "confidence": confidence,
        "primitive_observation_keys": primitive_keys,
        "tolerance": _task5_semantic_numeric_mapping(
            constraint["tolerance"],
            quantities=_TASK5_TOLERANCE_QUANTITIES,
            code=code,
        ),
    }
    if "measured" in constraint:
        content["measured"] = _task5_semantic_numeric_mapping(
            constraint["measured"],
            quantities=_TASK5_MEASURED_QUANTITIES,
            code=code,
        )
    return content, primitive_keys


def project_semantic_observations(
    *,
    semantic_artifact: object,
    semantic_artifact_sha256: object,
    primitive_checkpoint_sha256: object,
    primitive_observations: object,
) -> list[dict[str, object]]:
    code = "SEMANTIC_ARTIFACT_INVALID"
    semantic_sha256 = _sha256(semantic_artifact_sha256, code)
    checkpoint_sha256 = _sha256(primitive_checkpoint_sha256, code)
    artifact = _closed(
        semantic_artifact,
        _TASK5_SEMANTIC_ARTIFACT_FIELDS,
        code,
    )
    if artifact["schema_version"] != "1.0.0":
        _fail(code)
    primitive_records, by_legacy_id, total_multiplicity = (
        _task5_validate_primitive_observations(
            primitive_observations,
            primitive_checkpoint_sha256=checkpoint_sha256,
        )
    )
    ref = _task5_closed_with_optional(
        artifact["primitive_ir_ref"],
        required=_TASK5_PRIMITIVE_REF_REQUIRED_FIELDS,
        optional=_TASK5_PRIMITIVE_REF_OPTIONAL_FIELDS,
        code=code,
    )
    if ref["file_name"] != _TASK5_PRIMITIVE_REF_BASENAME:
        _fail("PRIMITIVE_IR_REF_MISMATCH")
    primitive_count = _strict_nonnegative_int(ref["primitive_count"], code)
    if primitive_count != total_multiplicity:
        _fail("PRIMITIVE_IR_REF_MISMATCH")
    if "sha256" in ref:
        if _sha256(ref["sha256"], code) != checkpoint_sha256:
            _fail("PRIMITIVE_CHECKPOINT_MISMATCH")
    if not isinstance(artifact["parts"], list):
        _fail(code)
    if not isinstance(artifact["constraints"], list):
        _fail(code)

    part_payloads: list[tuple[dict[str, object], list[str]]] = []
    for value in artifact["parts"]:
        content, primitive_keys = _task5_part_content(
            value,
            by_legacy_id=by_legacy_id,
        )
        part_payloads.append((content, primitive_keys))

    output: list[dict[str, object]] = []
    for content, primitive_keys in part_payloads:
        material = {
            "identity_kind": "r1c-semantic-observation-v1",
            "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
            "content": content,
        }
        output.append(
            {
                "observation_key": canonical_json_sha256(material),
                "primitive_observation_keys": list(primitive_keys),
                "semantic_artifact_sha256": semantic_sha256,
                "primitive_checkpoint_sha256": checkpoint_sha256,
                "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
                "content": content,
            }
        )
    for value in artifact["constraints"]:
        content, primitive_keys = _task5_constraint_content(
            value,
            by_legacy_id=by_legacy_id,
        )
        material = {
            "identity_kind": "r1c-semantic-observation-v1",
            "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
            "content": content,
        }
        output.append(
            {
                "observation_key": canonical_json_sha256(material),
                "primitive_observation_keys": list(primitive_keys),
                "semantic_artifact_sha256": semantic_sha256,
                "primitive_checkpoint_sha256": checkpoint_sha256,
                "numeric_policy_version": _R1C_NUMERIC_POLICY_VERSION,
                "content": content,
            }
        )
    output.sort(
        key=lambda record: (
            str(record["observation_key"]),
            tuple(record["primitive_observation_keys"]),
        )
    )
    return _copy.deepcopy(output)


__all__ = [
    "SOURCE_FUSION_SCHEMA_VERSION",
    "SourceFusionError",
    "validate_page_locators",
    "validate_region_locators",
    "validate_render_provenance",
    "project_primitive_observations",
    "project_semantic_observations",
]
