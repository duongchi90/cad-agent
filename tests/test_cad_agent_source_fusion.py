from __future__ import annotations

import ast
import copy
import decimal
import importlib
import inspect
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_bundle import (
    SOURCE_BUNDLE_SCHEMA_VERSION,
    source_bundle_sha256,
    validate_source_bundle,
)
from cad_agent.source_integrity import (
    R1C_NUMERIC_POLICY_VERSION,
    SOURCE_CUSTODY_SCHEMA_VERSION,
    canonicalize_r1c_quantity,
    source_custody_sha256,
    validate_source_custody,
)


SOURCE_FUSION_MODULE = "cad_agent.source_fusion"
SOURCE_FUSION_FILE = Path(__file__).parents[1] / "cad_agent" / "source_fusion.py"
SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"

PDF_SHA256 = "1" * 64
IMAGE_SHA256 = "2" * 64
PDF_RASTER_SHA256 = "3" * 64
PDF_RENDER_REFERENCE_SHA256 = "4" * 64
PRIMITIVE_ARTIFACT_SHA256 = "5" * 64
OTHER_PRIMITIVE_ARTIFACT_SHA256 = "6" * 64

_PDF_SOURCE_ID = "PDF-001"
_IMAGE_SOURCE_ID = "IMAGE-001"
_PAGE_A = "PAGE-A"
_PAGE_99 = "PAGE-99"
_PDF_REGION_USER = "PDF-REGION-USER"
_PDF_REGION_RASTER = "PDF-REGION-RASTER"
_IMAGE_REGION_SHEET = "IMAGE-SHEET"
_IMAGE_REGION_VIEW = "IMAGE-VIEW"

_RASTER_CONVENTION = "RASTER_TOP_LEFT_X_RIGHT_Y_DOWN"
_PDF_CONVENTION = "PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP"


def _sf():
    return importlib.import_module(SOURCE_FUSION_MODULE)


def _source_bundle() -> dict[str, object]:
    return validate_source_bundle(
        {
            "schema_version": SOURCE_BUNDLE_SCHEMA_VERSION,
            "bundle_id": "BUNDLE-TASK4",
            "run_id": "RUN-TASK4",
            "created_at_utc": "2026-08-08T14:30:00Z",
            "items": [
                {
                    "source_id": _PDF_SOURCE_ID,
                    "kind": "PDF",
                    "role": "OVERALL",
                    "relative_path": "sources/customer-drawing-99.pdf",
                    "sha256": PDF_SHA256,
                    "media_type": "application/pdf",
                    "page_ids": [_PAGE_99, _PAGE_A],
                    "region_ids": [_PDF_REGION_RASTER, _PDF_REGION_USER],
                    "captured_at_utc": "2026-08-08T14:00:00Z",
                    "quality": {"distortion": "NONE", "legibility": "GOOD"},
                },
                {
                    "source_id": _IMAGE_SOURCE_ID,
                    "kind": "IMAGE",
                    "role": "DETAIL",
                    "relative_path": "sources/customer-image-777.png",
                    "sha256": IMAGE_SHA256,
                    "media_type": "image/png",
                    "page_ids": [],
                    "region_ids": [_IMAGE_REGION_VIEW, _IMAGE_REGION_SHEET],
                    "captured_at_utc": "2026-08-08T14:00:00Z",
                    "quality": {"distortion": "NONE", "legibility": "GOOD"},
                },
            ],
        }
    )


def _custody(bundle: dict[str, object] | None = None) -> dict[str, object]:
    if bundle is None:
        bundle = _source_bundle()
    bundle_digest = source_bundle_sha256(bundle)
    payload = {
        "schema_version": SOURCE_CUSTODY_SCHEMA_VERSION,
        "bundle_id": bundle["bundle_id"],
        "run_id": bundle["run_id"],
        "source_bundle_sha256": bundle_digest,
        "approved_root_id": "ROOT-TASK4",
        "approved_root_revision": "ROOT-REV-4",
        "approved_root_configuration_sha256": "a" * 64,
        "identity_scheme": "HMAC-SHA-256",
        "identity_scheme_version": "r1c-file-identity-v1",
        "identity_key_revision": "KEY-REV-4",
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "status": "READY",
        "eligible_count": 2,
        "blocking_count": 0,
        "items": [
            {
                "source_id": _PDF_SOURCE_ID,
                "kind": "PDF",
                "role": "OVERALL",
                "relative_path": "sources/customer-drawing-99.pdf",
                "declared_sha256": PDF_SHA256,
                "observed_sha256": PDF_SHA256,
                "size_bytes": 4096,
                "declared_media_type": "application/pdf",
                "observed_media_type": "application/pdf",
                "media_metadata": {
                    "format": "PDF",
                    "pdf_version": "1.7",
                    "page_count": 2,
                    "pages": [
                        {
                            "page_index": 0,
                            "media_box": ["0", "0", "72", "144"],
                            "crop_box": ["0", "0", "72", "144"],
                            "rotation": 0,
                            "user_unit": "1",
                        },
                        {
                            "page_index": 1,
                            "media_box": ["0", "0", "144", "72"],
                            "crop_box": ["18", "0", "126", "72"],
                            "rotation": 90,
                            "user_unit": "1.25",
                        },
                    ],
                },
                "page_ids": [_PAGE_99, _PAGE_A],
                "region_ids": [_PDF_REGION_RASTER, _PDF_REGION_USER],
                "file_object_identity_token": "b" * 64,
                "path_binding_sha256": "c" * 64,
                "identity_scheme": "HMAC-SHA-256",
                "identity_scheme_version": "r1c-file-identity-v1",
                "identity_key_revision": "KEY-REV-4",
                "approved_root_revision": "ROOT-REV-4",
                "alias_group_id": None,
                "custody_state": "VERIFIED",
                "blocking_reason_code": None,
            },
            {
                "source_id": _IMAGE_SOURCE_ID,
                "kind": "IMAGE",
                "role": "DETAIL",
                "relative_path": "sources/customer-image-777.png",
                "declared_sha256": IMAGE_SHA256,
                "observed_sha256": IMAGE_SHA256,
                "size_bytes": 2048,
                "declared_media_type": "image/png",
                "observed_media_type": "image/png",
                "media_metadata": {
                    "format": "PNG",
                    "width_px": 640,
                    "height_px": 480,
                    "mode": "RGB",
                    "dpi_x": None,
                    "dpi_y": None,
                },
                "page_ids": [],
                "region_ids": [_IMAGE_REGION_VIEW, _IMAGE_REGION_SHEET],
                "file_object_identity_token": "d" * 64,
                "path_binding_sha256": "e" * 64,
                "identity_scheme": "HMAC-SHA-256",
                "identity_scheme_version": "r1c-file-identity-v1",
                "identity_key_revision": "KEY-REV-4",
                "approved_root_revision": "ROOT-REV-4",
                "alias_group_id": None,
                "custody_state": "VERIFIED",
                "blocking_reason_code": None,
            },
        ],
        "alias_groups": [],
    }
    return validate_source_custody(payload)


def _blocked_custody() -> dict[str, object]:
    custody = copy.deepcopy(_custody())
    custody["status"] = "BLOCKED"
    custody["eligible_count"] = 1
    custody["blocking_count"] = 1
    custody["items"][0]["custody_state"] = "MISSING"
    custody["items"][0]["blocking_reason_code"] = "MISSING"
    return validate_source_custody(custody)


def _custody_item(custody: dict[str, object], source_id: str) -> dict[str, object]:
    return next(item for item in custody["items"] if item["source_id"] == source_id)


def _pdf_page(custody: dict[str, object], page_index: int) -> dict[str, object]:
    item = _custody_item(custody, _PDF_SOURCE_ID)
    return item["media_metadata"]["pages"][page_index]


def _box(coords: list[object], unit: str = "pt") -> dict[str, object]:
    return {"unit": unit, "coordinates": list(coords)}


def _ratio(value: object, unit: str = "ratio") -> dict[str, object]:
    return {"unit": unit, "value": value}


def _dpi(value: object) -> dict[str, object]:
    return {"unit": "dpi", "value": value}


def _matrix(values: list[object]) -> dict[str, object]:
    return {"unit": "unitless", "coefficients": list(values)}


def _canonical_box(value: dict[str, object]) -> dict[str, object]:
    return {
        "unit": "pt",
        "coordinates": [
            canonicalize_r1c_quantity(
                coordinate,
                quantity="pdf_coordinate",
                unit=value["unit"],
            )["value"]
            for coordinate in value["coordinates"]
        ],
    }


def _canonical_ratio(value: dict[str, object]) -> dict[str, object]:
    return {
        "unit": "ratio",
        "value": canonicalize_r1c_quantity(
            value["value"],
            quantity="scale",
            unit=value["unit"],
        )["value"],
    }


def _canonical_dpi(value: dict[str, object]) -> dict[str, object]:
    return {
        "unit": "dpi",
        "value": canonicalize_r1c_quantity(
            value["value"],
            quantity="dpi",
            unit=value["unit"],
        )["value"],
    }


def _canonical_matrix(value: dict[str, object]) -> dict[str, object]:
    return {
        "unit": "unitless",
        "coefficients": [
            canonicalize_r1c_quantity(
                coefficient,
                quantity="render_matrix",
                unit=value["unit"],
            )["value"]
            for coefficient in value["coefficients"]
        ],
    }


def _page_normalized(record: dict[str, object]) -> dict[str, object]:
    return {
        "page_locator_sha256": record["page_locator_sha256"],
        "source_custody_sha256": record["source_custody_sha256"],
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": record["source_id"],
        "page_id": record["page_id"],
        "page_index": record["page_index"],
        "observed_pdf_sha256": record["observed_pdf_sha256"],
        "media_box": _canonical_box(record["media_box"]),
        "crop_box": _canonical_box(record["crop_box"]),
        "rotation": record["rotation"],
        "user_unit": _canonical_ratio(record["user_unit"]),
    }


def _page_locator_sha256(record: dict[str, object]) -> str:
    normalized = {
        "source_custody_sha256": record["source_custody_sha256"],
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": record["source_id"],
        "page_id": record["page_id"],
        "page_index": record["page_index"],
        "observed_pdf_sha256": record["observed_pdf_sha256"],
        "media_box": _canonical_box(record["media_box"]),
        "crop_box": _canonical_box(record["crop_box"]),
        "rotation": record["rotation"],
        "user_unit": _canonical_ratio(record["user_unit"]),
    }
    return canonical_json_sha256(
        {
            "identity_kind": "r1c-page-locator-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **normalized,
        }
    )


def _page_record(
    custody: dict[str, object],
    *,
    page_id: str,
    page_index: int,
    unit: str = "pt",
) -> dict[str, object]:
    page = _pdf_page(custody, page_index)
    factor = decimal.Decimal("72") if unit == "in" else decimal.Decimal("1")

    def convert(values: list[str]) -> list[str]:
        if unit == "pt":
            return list(values)
        return [
            format(decimal.Decimal(value) / factor, "f").rstrip("0").rstrip(".") or "0"
            for value in values
        ]

    record = {
        "page_locator_sha256": "",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _PDF_SOURCE_ID,
        "page_id": page_id,
        "page_index": page_index,
        "observed_pdf_sha256": PDF_SHA256,
        "media_box": _box(convert(page["media_box"]), unit),
        "crop_box": _box(convert(page["crop_box"]), unit),
        "rotation": page["rotation"],
        "user_unit": _ratio(page["user_unit"]),
    }
    record["page_locator_sha256"] = _page_locator_sha256(record)
    return record


def _page_payload(custody: dict[str, object], *, unit: str = "pt") -> list[dict[str, object]]:
    # Deliberately map the misleading PAGE-99 label to physical index 1 and
    # PAGE-A to physical index 0. Label text and caller ordering are not authority.
    return [
        _page_record(custody, page_id=_PAGE_A, page_index=0, unit=unit),
        _page_record(custody, page_id=_PAGE_99, page_index=1, unit=unit),
    ]


def _normalized_pages(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_page_normalized(record) for record in payload]
    return sorted(
        normalized,
        key=lambda record: (
            record["source_id"],
            record["page_id"],
            record["page_index"],
            record["page_locator_sha256"],
        ),
    )


def _page_by_id(page_locators: list[dict[str, object]], page_id: str) -> dict[str, object]:
    return next(record for record in page_locators if record["page_id"] == page_id)


def _region_normalized(record: dict[str, object]) -> dict[str, object]:
    common = {
        "region_locator_sha256": record["region_locator_sha256"],
        "source_custody_sha256": record["source_custody_sha256"],
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": record["source_id"],
        "region_id": record["region_id"],
        "locator_kind": record["locator_kind"],
        "coordinate_convention": record["coordinate_convention"],
    }
    if record["coordinate_convention"] == _RASTER_CONVENTION:
        return {
            **common,
            "page_locator_sha256": record["page_locator_sha256"],
            "render_provenance_sha256": record["render_provenance_sha256"],
            "raster_sha256": record["raster_sha256"],
            "raster_width_px": record["raster_width_px"],
            "raster_height_px": record["raster_height_px"],
            "bounds": list(record["bounds"]),
        }
    return {
        **common,
        "page_locator_sha256": record["page_locator_sha256"],
        "box_kind": record["box_kind"],
        "rotation": record["rotation"],
        "user_unit": _canonical_ratio(record["user_unit"]),
        "bounds": _canonical_box(record["bounds"]),
    }


def _region_locator_sha256(record: dict[str, object]) -> str:
    normalized = _region_normalized({**record, "region_locator_sha256": ""})
    normalized.pop("region_locator_sha256")
    return canonical_json_sha256(
        {
            "identity_kind": "r1c-region-locator-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **normalized,
        }
    )


def _direct_image_region(
    custody: dict[str, object],
    *,
    region_id: str,
    locator_kind: str,
    bounds: list[object],
) -> dict[str, object]:
    record = {
        "region_locator_sha256": "",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _IMAGE_SOURCE_ID,
        "region_id": region_id,
        "locator_kind": locator_kind,
        "coordinate_convention": _RASTER_CONVENTION,
        "page_locator_sha256": None,
        "render_provenance_sha256": None,
        "raster_sha256": IMAGE_SHA256,
        "raster_width_px": 640,
        "raster_height_px": 480,
        "bounds": list(bounds),
    }
    record["region_locator_sha256"] = _region_locator_sha256(record)
    return record


def _pdf_user_region(
    custody: dict[str, object],
    page_locators: list[dict[str, object]],
) -> dict[str, object]:
    parent = _page_by_id(page_locators, _PAGE_A)
    record = {
        "region_locator_sha256": "",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _PDF_SOURCE_ID,
        "region_id": _PDF_REGION_USER,
        "locator_kind": "REGION",
        "coordinate_convention": _PDF_CONVENTION,
        "page_locator_sha256": parent["page_locator_sha256"],
        "box_kind": "CROP_BOX",
        "rotation": parent["rotation"],
        "user_unit": copy.deepcopy(parent["user_unit"]),
        "bounds": _box(["6", "12", "60", "120"]),
    }
    record["region_locator_sha256"] = _region_locator_sha256(record)
    return record


def _pdf_raster_region(
    custody: dict[str, object],
    page_locators: list[dict[str, object]],
) -> dict[str, object]:
    parent = _page_by_id(page_locators, _PAGE_99)
    record = {
        "region_locator_sha256": "",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _PDF_SOURCE_ID,
        "region_id": _PDF_REGION_RASTER,
        "locator_kind": "CROP",
        "coordinate_convention": _RASTER_CONVENTION,
        "page_locator_sha256": parent["page_locator_sha256"],
        "render_provenance_sha256": PDF_RENDER_REFERENCE_SHA256,
        "raster_sha256": PDF_RASTER_SHA256,
        "raster_width_px": 288,
        "raster_height_px": 144,
        "bounds": [12, 8, 200, 120],
    }
    record["region_locator_sha256"] = _region_locator_sha256(record)
    return record


def _region_payload(
    custody: dict[str, object],
    page_locators: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        _direct_image_region(
            custody,
            region_id=_IMAGE_REGION_VIEW,
            locator_kind="VIEW",
            bounds=[100, 100, 500, 400],
        ),
        _pdf_raster_region(custody, page_locators),
        _direct_image_region(
            custody,
            region_id=_IMAGE_REGION_SHEET,
            locator_kind="SHEET",
            bounds=[0, 0, 640, 480],
        ),
        _pdf_user_region(custody, page_locators),
    ]


def _normalized_regions(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_region_normalized(record) for record in payload]
    return sorted(
        normalized,
        key=lambda record: (
            record["source_id"],
            record["region_id"],
            record["locator_kind"],
            record["region_locator_sha256"],
        ),
    )


def _primitive_source_document(
    *,
    file_name: str,
    page_index: int,
    width: int,
    height: int,
    sha256: str,
) -> dict[str, object]:
    return {
        "file_name": file_name,
        "page_index": page_index,
        "image_width_px": width,
        "image_height_px": height,
        "sha256": sha256,
    }


def _render_normalized(record: dict[str, object]) -> dict[str, object]:
    common = {
        "render_provenance_sha256": record["render_provenance_sha256"],
        "provenance_kind": record["provenance_kind"],
        "source_custody_sha256": record["source_custody_sha256"],
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": record["source_id"],
        "observed_source_sha256": record["observed_source_sha256"],
        "raster_sha256": record["raster_sha256"],
        "raster_width_px": record["raster_width_px"],
        "raster_height_px": record["raster_height_px"],
        "primitive_artifact_sha256": record["primitive_artifact_sha256"],
    }
    source_document = record["primitive_source_document"]
    if record["provenance_kind"] == "DIRECT_IMAGE":
        return {
            **common,
            "primitive_source_document": {
                "sha256": source_document["sha256"],
                "image_width_px": source_document["image_width_px"],
                "image_height_px": source_document["image_height_px"],
            },
        }
    return {
        **common,
        "page_locator_sha256": record["page_locator_sha256"],
        "pdf_page_index": record["pdf_page_index"],
        "box_kind": record["box_kind"],
        "selected_box": _canonical_box(record["selected_box"]),
        "rotation": record["rotation"],
        "user_unit": _canonical_ratio(record["user_unit"]),
        "render_dpi": _canonical_dpi(record["render_dpi"]),
        "render_matrix": _canonical_matrix(record["render_matrix"]),
        "primitive_source_document": {
            "sha256": source_document["sha256"],
            "image_width_px": source_document["image_width_px"],
            "image_height_px": source_document["image_height_px"],
            "primitive_source_page_index": source_document["page_index"],
        },
    }


def _render_provenance_sha256(record: dict[str, object]) -> str:
    normalized = _render_normalized({**record, "render_provenance_sha256": ""})
    normalized.pop("render_provenance_sha256")
    return canonical_json_sha256(
        {
            "identity_kind": "r1c-render-provenance-v1",
            "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION,
            **normalized,
        }
    )


def _pdf_render_record(
    custody: dict[str, object],
    page_locators: list[dict[str, object]],
    *,
    primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256,
    file_name: str = "page_02.png",
) -> dict[str, object]:
    parent = _page_by_id(page_locators, _PAGE_99)
    record = {
        "render_provenance_sha256": "",
        "provenance_kind": "PDF_RENDER",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _PDF_SOURCE_ID,
        "observed_source_sha256": PDF_SHA256,
        "page_locator_sha256": parent["page_locator_sha256"],
        "pdf_page_index": 1,
        "box_kind": "MEDIA_BOX",
        "selected_box": copy.deepcopy(parent["media_box"]),
        "rotation": parent["rotation"],
        "user_unit": copy.deepcopy(parent["user_unit"]),
        "render_dpi": _dpi("144"),
        "render_matrix": _matrix(["2", "0", "0", "-2", "0", "144"]),
        "raster_sha256": PDF_RASTER_SHA256,
        "raster_width_px": 288,
        "raster_height_px": 144,
        "primitive_artifact_sha256": primitive_artifact_sha256,
        "primitive_source_document": _primitive_source_document(
            file_name=file_name,
            page_index=0,
            width=288,
            height=144,
            sha256=PDF_RASTER_SHA256,
        ),
    }
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    return record


def _direct_image_render_record(
    custody: dict[str, object],
    *,
    primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256,
    file_name: str = "arbitrary-name.png",
) -> dict[str, object]:
    record = {
        "render_provenance_sha256": "",
        "provenance_kind": "DIRECT_IMAGE",
        "source_custody_sha256": source_custody_sha256(custody),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "source_id": _IMAGE_SOURCE_ID,
        "observed_source_sha256": IMAGE_SHA256,
        "raster_sha256": IMAGE_SHA256,
        "raster_width_px": 640,
        "raster_height_px": 480,
        "primitive_artifact_sha256": primitive_artifact_sha256,
        "primitive_source_document": _primitive_source_document(
            file_name=file_name,
            page_index=0,
            width=640,
            height=480,
            sha256=IMAGE_SHA256,
        ),
    }
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    return record


def _normalized_render(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_render_normalized(record) for record in payload]
    return sorted(
        normalized,
        key=lambda record: (
            record["source_id"],
            record.get("page_locator_sha256") or "",
            record["raster_sha256"],
            record["primitive_artifact_sha256"],
            record["render_provenance_sha256"],
        ),
    )


def test_task4_public_surface_is_exact() -> None:
    sf = _sf()
    assert sf.SOURCE_FUSION_SCHEMA_VERSION == SOURCE_FUSION_SCHEMA_VERSION
    assert issubclass(sf.SourceFusionError, ValueError)
    assert sf.__all__ == [
        "SOURCE_FUSION_SCHEMA_VERSION",
        "SourceFusionError",
        "validate_page_locators",
        "validate_region_locators",
        "validate_render_provenance",
    ]
    for name in sf.__all__[2:]:
        assert callable(getattr(sf, name))
    assert len(inspect.signature(sf.validate_page_locators).parameters) == 3
    assert len(inspect.signature(sf.validate_region_locators).parameters) == 3
    assert len(inspect.signature(sf.validate_render_provenance).parameters) == 4


def test_task4_rejects_non_ready_custody() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _blocked_custody()
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_NOT_READY$"):
        sf.validate_page_locators([], source_bundle=bundle, custody=custody)


def test_task4_rejects_invalid_source_bundle_categorically() -> None:
    sf = _sf()
    custody = _custody()
    sentinel = r"C:\\customer\\private\\source.pdf"
    bad_bundle = {"schema_version": "source-bundle-1.0", "private_path": sentinel}
    with pytest.raises(sf.SourceFusionError, match=r"^SOURCE_BUNDLE_INVALID$") as exc_info:
        sf.validate_page_locators([], source_bundle=bad_bundle, custody=custody)
    assert sentinel not in str(exc_info.value)


def test_task4_rejects_invalid_custody_without_leaking_upstream_text() -> None:
    sf = _sf()
    bundle = _source_bundle()
    sentinel = r"C:\customer\private\drawing.pdf"
    bad = {"status": "READY", "private_path": sentinel}
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_INVALID$") as exc_info:
        sf.validate_page_locators([], source_bundle=bundle, custody=bad)
    assert sentinel not in str(exc_info.value)


def test_task4_rejects_bundle_custody_context_mismatch() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    changed_bundle = copy.deepcopy(bundle)
    changed_bundle["run_id"] = "RUN-TASK4-OTHER"
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_CONTEXT_MISMATCH$"):
        sf.validate_page_locators(
            _page_payload(custody),
            source_bundle=changed_bundle,
            custody=custody,
        )


def test_task4_rejects_stale_custody_hash() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["source_custody_sha256"] = "f" * 64
    payload[0]["page_locator_sha256"] = _page_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^STALE_CUSTODY_HASH$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locators_require_exact_declared_page_coverage() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_COVERAGE_MISMATCH$"):
        sf.validate_page_locators(
            _page_payload(custody)[:1],
            source_bundle=bundle,
            custody=custody,
        )


def test_page_locators_reject_extra_page_label() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    extra = copy.deepcopy(payload[0])
    extra["page_id"] = "PAGE-EXTRA"
    extra["page_locator_sha256"] = _page_locator_sha256(extra)
    payload.append(extra)
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_COVERAGE_MISMATCH$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locators_reject_duplicate_page_label() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload.append(copy.deepcopy(payload[0]))
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_DUPLICATE$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locators_reject_out_of_range_physical_index() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["page_index"] = 2
    payload[0]["page_locator_sha256"] = _page_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_INDEX_OUT_OF_RANGE$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locators_do_not_infer_index_from_page_name() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    normalized = sf.validate_page_locators(
        payload,
        source_bundle=bundle,
        custody=custody,
    )
    by_label = {record["page_id"]: record["page_index"] for record in normalized}
    assert by_label == {_PAGE_99: 1, _PAGE_A: 0}


def test_page_locators_do_not_infer_index_from_input_order() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    forward = sf.validate_page_locators(
        payload,
        source_bundle=bundle,
        custody=custody,
    )
    reverse = sf.validate_page_locators(
        list(reversed(payload)),
        source_bundle=bundle,
        custody=custody,
    )
    assert forward == reverse == _normalized_pages(payload)


@pytest.mark.parametrize("field", ["media_box", "crop_box", "rotation", "user_unit"])
def test_page_locator_binds_exact_pdf_structural_facts(field: str) -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    if field in {"media_box", "crop_box"}:
        payload[0][field] = _box(["0", "0", "71", "144"])
    elif field == "rotation":
        payload[0][field] = 180
    else:
        payload[0][field] = _ratio("2")
    payload[0]["page_locator_sha256"] = _page_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_FACT_MISMATCH$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locator_accepts_equivalent_pdf_units() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    pt_payload = _page_payload(custody, unit="pt")
    inch_payload = _page_payload(custody, unit="in")
    pt_normalized = sf.validate_page_locators(
        pt_payload,
        source_bundle=bundle,
        custody=custody,
    )
    inch_normalized = sf.validate_page_locators(
        inch_payload,
        source_bundle=bundle,
        custody=custody,
    )
    assert pt_normalized == inch_normalized == _normalized_pages(pt_payload)


def test_page_locator_normalizes_half_even_and_negative_zero() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    page_a = next(record for record in payload if record["page_id"] == _PAGE_A)
    page_a["media_box"] = _box(["-0.0004", "-0.0004", "72.0005", "144.0005"])
    page_a["crop_box"] = copy.deepcopy(page_a["media_box"])
    page_a["page_locator_sha256"] = _page_locator_sha256(page_a)
    normalized = sf.validate_page_locators(
        payload,
        source_bundle=bundle,
        custody=custody,
    )
    page = next(record for record in normalized if record["page_id"] == _PAGE_A)
    assert page["media_box"] == {
        "unit": "pt",
        "coordinates": ["0", "0", "72", "144"],
    }


def test_page_locator_rejects_wrong_deterministic_id() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["page_locator_sha256"] = "0" * 64
    with pytest.raises(sf.SourceFusionError, match=r"^DETERMINISTIC_ID_MISMATCH$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_region_locators_reject_stale_custody_hash() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    payload[0]["source_custody_sha256"] = "f" * 64
    payload[0]["region_locator_sha256"] = _region_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^STALE_CUSTODY_HASH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_region_locators_require_exact_declared_region_coverage() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_COVERAGE_MISMATCH$"):
        sf.validate_region_locators(payload[:-1], page_locators=pages, custody=custody)


def test_region_locators_reject_extra_or_duplicate_region_labels() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)

    extra = copy.deepcopy(payload[0])
    extra["region_id"] = "UNDECLARED-REGION"
    extra["region_locator_sha256"] = _region_locator_sha256(extra)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_COVERAGE_MISMATCH$"):
        sf.validate_region_locators(
            [*payload, extra],
            page_locators=pages,
            custody=custody,
        )

    duplicate = [*payload, copy.deepcopy(payload[0])]
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(
            duplicate,
            page_locators=pages,
            custody=custody,
        )


@pytest.mark.parametrize("locator_kind", ["SHEET", "VIEW", "CROP", "REGION"])
def test_region_kinds_are_closed_without_name_inference(locator_kind: str) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)
    target["locator_kind"] = locator_kind
    target["region_locator_sha256"] = _region_locator_sha256(target)
    normalized = sf.validate_region_locators(payload, page_locators=pages, custody=custody)
    result = next(record for record in normalized if record["region_id"] == _IMAGE_REGION_VIEW)
    assert result["locator_kind"] == locator_kind


def test_region_kinds_reject_unapproved_kind() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    payload[0]["locator_kind"] = "WINDOW"
    payload[0]["region_locator_sha256"] = _region_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_raster_region_requires_top_left_coordinate_convention() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)
    target["coordinate_convention"] = _PDF_CONVENTION
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize("bad_coordinate", [True, 1.5])
def test_raster_region_requires_strict_integer_coordinates(bad_coordinate: object) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)
    target["bounds"] = [0, 0, bad_coordinate, 20]
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_BOUNDS_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize(
    "bounds,code",
    [
        ([10, 10, 10, 20], "REGION_BOUNDS_INVALID"),
        ([20, 10, 10, 20], "REGION_BOUNDS_INVALID"),
        ([-1, 0, 10, 20], "REGION_BOUNDS_OUT_OF_RANGE"),
        ([0, 0, 641, 20], "REGION_BOUNDS_OUT_OF_RANGE"),
        ([0, 0, 10, 481], "REGION_BOUNDS_OUT_OF_RANGE"),
    ],
)
def test_raster_region_rejects_reversed_or_out_of_bounds_rectangle(
    bounds: list[int],
    code: str,
) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)
    target["bounds"] = bounds
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=rf"^{code}$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize(
    "field,value",
    [
        ("raster_sha256", "9" * 64),
        ("raster_width_px", 639),
        ("raster_height_px", 479),
    ],
)
def test_direct_image_region_binds_exact_custody_raster(field: str, value: object) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)
    target[field] = value
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_PARENT_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize("field", ["page_locator_sha256", "render_provenance_sha256"])
def test_pdf_raster_region_requires_page_and_render_parent_refs(field: str) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_RASTER)
    target[field] = None
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_PARENT_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_pdf_region_requires_bottom_left_coordinate_convention() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    target["coordinate_convention"] = _RASTER_CONVENTION
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_pdf_region_requires_exact_page_parent() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    target["page_locator_sha256"] = "9" * 64
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_PARENT_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize("field", ["rotation", "user_unit"])
def test_pdf_region_binds_exact_parent_rotation_and_user_unit(field: str) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    if field == "rotation":
        target[field] = 90
    else:
        target[field] = _ratio("2")
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_PARENT_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_pdf_region_box_kind_is_closed() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    target["box_kind"] = "BLEED_BOX"
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_pdf_region_rejects_bounds_outside_selected_box() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    target["bounds"] = _box(["-1", "0", "60", "120"])
    target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_BOUNDS_OUT_OF_RANGE$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_region_locator_id_is_parent_kind_and_geometry_bound() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    base = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW)

    alternate = copy.deepcopy(base)
    alternate["locator_kind"] = "REGION"
    alternate["region_locator_sha256"] = _region_locator_sha256(alternate)
    assert alternate["region_locator_sha256"] != base["region_locator_sha256"]

    normalized = sf.validate_region_locators(
        [alternate if item["region_id"] == _IMAGE_REGION_VIEW else item for item in payload],
        page_locators=pages,
        custody=custody,
    )
    assert next(
        item["region_locator_sha256"]
        for item in normalized
        if item["region_id"] == _IMAGE_REGION_VIEW
    ) == alternate["region_locator_sha256"]


def test_region_locator_rejects_wrong_deterministic_id() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    payload = _region_payload(custody, pages)
    payload[0]["region_locator_sha256"] = "0" * 64
    with pytest.raises(sf.SourceFusionError, match=r"^DETERMINISTIC_ID_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_render_provenance_rejects_stale_custody_hash() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record["source_custody_sha256"] = "f" * 64
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=r"^STALE_CUSTODY_HASH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


def test_pdf_render_provenance_binds_complete_chain() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    normalized = sf.validate_render_provenance(
        [record],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert normalized == _normalized_render([record])


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("source_id", _IMAGE_SOURCE_ID, "RENDER_SOURCE_MISMATCH"),
        ("observed_source_sha256", "9" * 64, "RENDER_SOURCE_MISMATCH"),
        ("page_locator_sha256", "9" * 64, "RENDER_PAGE_MISMATCH"),
        ("pdf_page_index", 0, "RENDER_PAGE_MISMATCH"),
    ],
)
def test_pdf_render_rejects_wrong_source_or_page_binding(
    field: str,
    value: object,
    code: str,
) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record[field] = value
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=rf"^{code}$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


@pytest.mark.parametrize("field", ["selected_box", "rotation", "user_unit", "box_kind"])
def test_pdf_render_rejects_box_rotation_or_user_unit_mismatch(field: str) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    if field == "selected_box":
        record[field] = _box(["0", "0", "143", "72"])
    elif field == "rotation":
        record[field] = 180
    elif field == "user_unit":
        record[field] = _ratio("2")
    else:
        record[field] = "CROP_BOX"
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_FACT_MISMATCH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


def test_pdf_render_canonicalizes_dpi_and_matrix() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    equivalent = copy.deepcopy(record)
    equivalent["render_dpi"] = _dpi("144.0004")
    equivalent["render_matrix"] = _matrix(
        ["2.0000000004", "-0.0000000004", "0", "-2", "-0", "144.0000000004"]
    )
    equivalent["render_provenance_sha256"] = _render_provenance_sha256(equivalent)

    first = sf.validate_render_provenance(
        [record],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    second = sf.validate_render_provenance(
        [equivalent],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert first == second


def test_render_provenance_id_is_content_bound() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    first = _pdf_render_record(custody, pages)
    second = copy.deepcopy(first)
    second["render_dpi"] = _dpi("288")
    second["render_provenance_sha256"] = _render_provenance_sha256(second)
    assert first["render_provenance_sha256"] != second["render_provenance_sha256"]

    normalized = sf.validate_render_provenance(
        [second],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert normalized[0]["render_provenance_sha256"] == second["render_provenance_sha256"]


def test_render_provenance_rejects_wrong_deterministic_id() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record["render_provenance_sha256"] = "0" * 64
    with pytest.raises(sf.SourceFusionError, match=r"^DETERMINISTIC_ID_MISMATCH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


@pytest.mark.parametrize("length", [4, 5, 7])
def test_pdf_render_requires_six_coefficient_matrix(length: int) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record["render_matrix"] = _matrix(["1"] * length)
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


def test_pdf_render_rejects_raster_primitive_sha_mismatch() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record["primitive_source_document"]["sha256"] = "9" * 64
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=r"^PRIMITIVE_BINDING_MISMATCH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_width_px", 287),
        ("image_height_px", 143),
    ],
)
def test_pdf_render_rejects_raster_primitive_dimension_mismatch(
    field: str,
    value: int,
) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    record["primitive_source_document"][field] = value
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=r"^PRIMITIVE_BINDING_MISMATCH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


def test_pdf_render_rejects_wrong_primitive_artifact_sha() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    with pytest.raises(sf.SourceFusionError, match=r"^PRIMITIVE_BINDING_MISMATCH$"):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=OTHER_PRIMITIVE_ARTIFACT_SHA256,
        )


def test_pdf_render_keeps_pdf_and_primitive_page_indices_separate() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _pdf_render_record(custody, pages)
    assert record["pdf_page_index"] == 1
    assert record["primitive_source_document"]["page_index"] == 0
    normalized = sf.validate_render_provenance(
        [record],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert normalized[0]["pdf_page_index"] == 1
    assert normalized[0]["primitive_source_document"]["primitive_source_page_index"] == 0


def test_direct_image_provenance_binds_sha_and_dimensions() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _direct_image_render_record(custody)
    normalized = sf.validate_render_provenance(
        [record],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert normalized == _normalized_render([record])
    assert normalized[0]["observed_source_sha256"] == IMAGE_SHA256
    assert normalized[0]["raster_sha256"] == IMAGE_SHA256


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_source_sha256", "9" * 64),
        ("raster_sha256", "9" * 64),
        ("raster_width_px", 639),
        ("raster_height_px", 479),
    ],
)
def test_direct_image_provenance_rejects_sha_or_dimension_mismatch(
    field: str,
    value: object,
) -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _direct_image_render_record(custody)
    record[field] = value
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(
        sf.SourceFusionError,
        match=r"^(RENDER_SOURCE_MISMATCH|RENDER_FACT_MISMATCH|PRIMITIVE_BINDING_MISMATCH)$",
    ):
        sf.validate_render_provenance(
            [record],
            page_locators=pages,
            custody=custody,
            primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        )


def test_direct_image_provenance_does_not_use_filename_as_authority() -> None:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    first = _direct_image_render_record(custody, file_name="first-private-name.png")
    second = _direct_image_render_record(custody, file_name="totally-different.jpg")
    assert first["render_provenance_sha256"] == second["render_provenance_sha256"]
    assert sf.validate_render_provenance(
        [first],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    ) == sf.validate_render_provenance(
        [second],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )


def test_all_task4_outputs_are_permutation_stable() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    pages = _page_payload(custody)
    regions = _region_payload(custody, pages)

    normalized_pages = sf.validate_page_locators(
        pages,
        source_bundle=bundle,
        custody=custody,
    )
    reversed_pages = sf.validate_page_locators(
        list(reversed(pages)),
        source_bundle=bundle,
        custody=custody,
    )
    assert normalized_pages == reversed_pages

    normalized_regions = sf.validate_region_locators(
        regions,
        page_locators=pages,
        custody=custody,
    )
    reversed_regions = sf.validate_region_locators(
        list(reversed(regions)),
        page_locators=list(reversed(pages)),
        custody=custody,
    )
    assert normalized_regions == reversed_regions

    direct = _direct_image_render_record(custody)
    pdf = _pdf_render_record(custody, pages)
    # A single validation call is bound to one Primitive artifact SHA. Use the
    # same explicit artifact SHA for both synthetic records in this permutation test.
    provenance = [pdf, direct]
    forward = sf.validate_render_provenance(
        provenance,
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    reverse = sf.validate_render_provenance(
        list(reversed(provenance)),
        page_locators=list(reversed(pages)),
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    assert forward == reverse


def test_all_task4_outputs_are_replay_stable() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    pages = _page_payload(custody)
    regions = _region_payload(custody, pages)
    render = [_pdf_render_record(custody, pages)]

    assert sf.validate_page_locators(
        copy.deepcopy(pages),
        source_bundle=copy.deepcopy(bundle),
        custody=copy.deepcopy(custody),
    ) == sf.validate_page_locators(
        copy.deepcopy(pages),
        source_bundle=copy.deepcopy(bundle),
        custody=copy.deepcopy(custody),
    )
    assert sf.validate_region_locators(
        copy.deepcopy(regions),
        page_locators=copy.deepcopy(pages),
        custody=copy.deepcopy(custody),
    ) == sf.validate_region_locators(
        copy.deepcopy(regions),
        page_locators=copy.deepcopy(pages),
        custody=copy.deepcopy(custody),
    )
    assert sf.validate_render_provenance(
        copy.deepcopy(render),
        page_locators=copy.deepcopy(pages),
        custody=copy.deepcopy(custody),
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    ) == sf.validate_render_provenance(
        copy.deepcopy(render),
        page_locators=copy.deepcopy(pages),
        custody=copy.deepcopy(custody),
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_task4_rejects_nonfinite_numbers(bad_value: float) -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["media_box"]["coordinates"][0] = bad_value
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_INVALID$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_task4_rejects_numeric_range_overflow() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["media_box"]["coordinates"][0] = "1000000000.001"
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_INVALID$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_task4_never_uses_relative_path_as_locator_identity() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    normalized = sf.validate_page_locators(
        _page_payload(custody),
        source_bundle=bundle,
        custody=custody,
    )
    for record in normalized:
        assert "relative_path" not in record
        assert "path" not in record
        assert "file_name" not in record


def test_task4_errors_are_privacy_safe() -> None:
    sf = _sf()
    sentinel = r"C:\TOP-SECRET-CUSTOMER\drawing.pdf"
    bundle = _source_bundle()
    custody = _custody(bundle)
    payload = _page_payload(custody)
    payload[0]["media_box"] = {"unit": sentinel, "coordinates": ["0", "0", "72", "144"]}
    with pytest.raises(sf.SourceFusionError) as exc_info:
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)
    assert sentinel not in str(exc_info.value)
    assert "TOP-SECRET-CUSTOMER" not in str(exc_info.value)


def test_task4_has_no_parser_renderer_ocr_model_provider_autocad_or_filesystem_owner() -> None:
    _sf()
    tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "os",
        "pathlib",
        "subprocess",
        "requests",
        "hashlib",
        "uuid",
        "random",
        "datetime",
        "time",
        "PIL",
        "pypdf",
        "fitz",
        "cv2",
        "pytesseract",
        "primitive_ir_lib",
        "agent_lib",
        "autocad_plugin",
        "mcp_integration_lib",
    }
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(forbidden_import_roots)

    def call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    called_names = {
        call_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    forbidden_calls = {
        "open",
        "Path",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "replace",
        "remove",
        "run",
        "Popen",
        "system",
        "uuid4",
        "random",
        "time",
        "now",
        "utcnow",
    }
    assert called_names.isdisjoint(forbidden_calls)
    source = SOURCE_FUSION_FILE.read_text(encoding="utf-8").lower()
    for forbidden_text in (
        "pypdf",
        "pymupdf",
        "tesseract",
        "openai",
        "anthropic",
        "autocad",
        "file ipc",
    ):
        assert forbidden_text not in source
