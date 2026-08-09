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
    R1C_TOLERANCE_POLICY_VERSION,
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
        "project_primitive_observations",
        "project_semantic_observations",
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
        "os", "pathlib", "subprocess", "requests", "hashlib", "uuid", "random",
        "datetime", "time", "PIL", "pypdf", "fitz", "cv2", "pytesseract",
        "primitive_ir_lib", "agent_lib", "autocad_plugin", "mcp_integration_lib",
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

    called_names = {call_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    forbidden_calls = {"open", "Path", "read_text", "read_bytes", "write_text", "write_bytes", "mkdir", "unlink", "replace", "remove", "run", "Popen", "system", "uuid4", "random", "time", "now", "utcnow"}
    assert called_names.isdisjoint(forbidden_calls)
    source = SOURCE_FUSION_FILE.read_text(encoding="utf-8").lower()
    for forbidden_text in ("pypdf", "pymupdf", "tesseract", "openai", "anthropic", "autocad", "file ipc"):
        assert forbidden_text not in source


def test_task4_rejects_bundle_content_hash_mismatch_with_same_context_ids() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    changed_bundle = copy.deepcopy(bundle)
    changed_bundle["items"][0]["relative_path"] = "sources/rebound-customer-drawing.pdf"
    assert changed_bundle["bundle_id"] == bundle["bundle_id"]
    assert changed_bundle["run_id"] == bundle["run_id"]
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_CONTEXT_MISMATCH$"):
        sf.validate_page_locators(_page_payload(custody), source_bundle=changed_bundle, custody=custody)


def test_page_locator_rejects_mismatched_observed_pdf_sha256() -> None:
    sf = _sf(); bundle = _source_bundle(); custody = _custody(bundle); payload = _page_payload(custody)
    payload[0]["observed_pdf_sha256"] = "9" * 64
    payload[0]["page_locator_sha256"] = _page_locator_sha256(payload[0])
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_FACT_MISMATCH$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locator_rejects_mismatched_numeric_policy_version() -> None:
    sf = _sf(); bundle = _source_bundle(); custody = _custody(bundle); payload = _page_payload(custody)
    payload[0]["numeric_policy_version"] = "r1c-numeric-policy-untrusted"
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_INVALID$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


def test_page_locator_rejects_bool_physical_index() -> None:
    sf = _sf(); bundle = _source_bundle(); custody = _custody(bundle); payload = _page_payload(custody)
    payload[0]["page_index"] = True
    with pytest.raises(sf.SourceFusionError, match=r"^PAGE_LOCATOR_INVALID$"):
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)


@pytest.mark.parametrize("bounds", [["12", "12", "12", "60"], ["60", "12", "12", "60"]])
def test_pdf_region_rejects_reversed_or_degenerate_bounds(bounds: list[str]) -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER)
    target["bounds"] = _box(bounds); target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_BOUNDS_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_pdf_region_rejects_bounds_inside_media_box_but_outside_selected_crop_box() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER); parent = _page_by_id(pages, _PAGE_99)
    target["page_locator_sha256"] = parent["page_locator_sha256"]; target["box_kind"] = "CROP_BOX"; target["rotation"] = parent["rotation"]; target["user_unit"] = copy.deepcopy(parent["user_unit"]); target["bounds"] = _box(["0", "10", "10", "20"]); target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_BOUNDS_OUT_OF_RANGE$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_region_rejects_arbitrary_third_coordinate_convention() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _PDF_REGION_USER); target["coordinate_convention"] = "PDF_TOP_LEFT_X_RIGHT_Y_DOWN"
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_LOCATOR_INVALID$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


@pytest.mark.parametrize("field", ["page_locator_sha256", "render_provenance_sha256"])
def test_direct_image_raster_region_rejects_non_null_parent_refs(field: str) -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); payload = _region_payload(custody, pages)
    target = next(record for record in payload if record["region_id"] == _IMAGE_REGION_VIEW); target[field] = "a" * 64; target["region_locator_sha256"] = _region_locator_sha256(target)
    with pytest.raises(sf.SourceFusionError, match=r"^REGION_PARENT_MISMATCH$"):
        sf.validate_region_locators(payload, page_locators=pages, custody=custody)


def test_render_provenance_rejects_unknown_kind() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _pdf_render_record(custody, pages); record["provenance_kind"] = "PDF_RASTERIZED"
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_pdf_render_accepts_valid_crop_box_binding() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); parent = _page_by_id(pages, _PAGE_99); record = _pdf_render_record(custody, pages)
    record["box_kind"] = "CROP_BOX"; record["selected_box"] = copy.deepcopy(parent["crop_box"]); record["render_provenance_sha256"] = _render_provenance_sha256(record)
    assert sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256) == _normalized_render([record])


@pytest.mark.parametrize("field,value", [("sha256", "9" * 64), ("image_width_px", 639), ("image_height_px", 479)])
def test_direct_image_render_rejects_nested_primitive_source_document_mismatch(field: str, value: object) -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _direct_image_render_record(custody); record["primitive_source_document"][field] = value; record["render_provenance_sha256"] = _render_provenance_sha256(record)
    with pytest.raises(sf.SourceFusionError, match=r"^PRIMITIVE_BINDING_MISMATCH$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


@pytest.mark.parametrize("field,bad_value", [("render_dpi", float("nan")), ("render_dpi", float("inf")), ("render_matrix", float("nan")), ("render_matrix", float("-inf"))])
def test_pdf_render_rejects_nonfinite_dpi_or_matrix(field: str, bad_value: float) -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _pdf_render_record(custody, pages)
    record[field] = _dpi(bad_value) if field == "render_dpi" else _matrix([bad_value, "0", "0", "-2", "0", "144"])
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


@pytest.mark.parametrize("field,bad_value", [("raster_width_px", True), ("raster_height_px", -1)])
def test_direct_image_render_rejects_bool_or_negative_raster_dimensions(field: str, bad_value: object) -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _direct_image_render_record(custody); record[field] = bad_value
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_pdf_render_rejects_bool_pdf_page_index() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _pdf_render_record(custody, pages); record["pdf_page_index"] = True
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_pdf_render_rejects_negative_primitive_source_page_index() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _pdf_render_record(custody, pages); record["primitive_source_document"]["page_index"] = -1
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_pdf_render_filename_is_not_identity_authority() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); first = _pdf_render_record(custody, pages, file_name="customer-secret-page.png"); second = _pdf_render_record(custody, pages, file_name="renamed-transient-output.png")
    assert first["render_provenance_sha256"] == second["render_provenance_sha256"]
    assert sf.validate_render_provenance([first], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256) == sf.validate_render_provenance([second], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_render_provenance_closed_record_rejects_extra_path_field() -> None:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _pdf_render_record(custody, pages); record["relative_path"] = r"C:\customer\volatile\render.png"
    with pytest.raises(sf.SourceFusionError, match=r"^RENDER_PROVENANCE_INVALID$"):
        sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256)


def test_task4_architecture_uses_only_accepted_internal_owners_and_no_authority_surfaces() -> None:
    _sf(); tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8"))
    allowed_internal_modules = {"cad_agent.drawing_contracts", "cad_agent.source_bundle", "cad_agent.source_integrity"}
    internal_modules: set[str] = set(); imported_roots: set[str] = set(); canonical_owner_imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
                if alias.name == "cad_agent" or alias.name.startswith("cad_agent."):
                    internal_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
            if node.module == "cad_agent" or node.module.startswith("cad_agent."):
                internal_modules.add(node.module)
            if node.module == "cad_agent.source_integrity":
                canonical_owner_imported = canonical_owner_imported or any(alias.name == "canonicalize_r1c_quantity" for alias in node.names)
    assert internal_modules <= allowed_internal_modules
    assert canonical_owner_imported
    forbidden_import_roots = {"importlib", "socket", "urllib", "http", "tempfile", "glob", "shutil", "os", "pathlib", "subprocess", "requests", "builtins", "io", "PIL", "pypdf", "fitz", "cv2", "pytesseract", "primitive_ir_lib", "agent_lib", "autocad_plugin", "mcp_integration_lib"}
    assert imported_roots.isdisjoint(forbidden_import_roots)

    def call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Attribute):
            prefix = call_name(node.value); return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    called_names = {call_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    forbidden_calls = {"__import__", "builtins.__import__", "importlib.import_module", "open", "builtins.open", "io.open", "eval", "exec"}
    assert called_names.isdisjoint(forbidden_calls)
    assert not any(name == "round" or name.endswith(".quantize") or name.endswith(".normalize") for name in called_names)
    assert "_canonicalize_r1c_quantity" in called_names


# ----------------------------------------------------------------- Task 5 RED ---

TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256 = "7" * 64
TASK5_SEMANTIC_ARTIFACT_SHA256 = "8" * 64
_TASK5_PRIMITIVE_IR_BASENAME = "primitive_ir.json"


def _task5_source_bindings(primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256) -> list[dict[str, object]]:
    sf = _sf()
    custody = _custody()
    pages = _page_payload(custody)
    record = _direct_image_render_record(custody, primitive_artifact_sha256=primitive_artifact_sha256, file_name="volatile-render-name.png")
    return sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=primitive_artifact_sha256)


def _task5_primitive(primitive_id: str, *, end_x: object = 10.0, start_x: object = 0.0, handle: object = "ABCD", extracted_at: object = "2026-08-08T12:00:00Z", validation_status: str = "unreviewed", validation_notes: object = "volatile reviewer note") -> dict[str, object]:
    return {"id": primitive_id, "type": "line", "source": "geometry_opencv", "confidence": 0.875, "layer": "GEOMETRY", "handle": handle, "trace": {"bbox_px": [0, 0, 10, 10], "extraction_tool": "opencv-line", "extracted_at": extracted_at}, "validation": {"status": validation_status, "notes": validation_notes}, "geometry": {"start": {"x": start_x, "y": 0.0}, "end": {"x": end_x, "y": 0.0}}}


def _task5_primitive_artifact(primitives: list[dict[str, object]] | None = None, *, file_name: str = "source-customer-name.png", unit: str = "mm", pixel_to_unit_scale: object = 1.0, origin_x: object = 0.0, reference_note: object = "volatile calibration note") -> dict[str, object]:
    if primitives is None:
        primitives = [_task5_primitive("prim-a")]
    calibration = {"unit": unit, "pixel_to_unit_scale": pixel_to_unit_scale, "origin_px": [origin_x, 480.0], "method": "manual_override", "status": "verified", "source_sha256": IMAGE_SHA256}
    if reference_note is not None:
        calibration["reference_note"] = reference_note
    return {"schema_version": "1.0.0", "source_document": {"file_name": file_name, "page_index": 0, "image_width_px": 640, "image_height_px": 480, "sha256": IMAGE_SHA256}, "calibration": calibration, "primitives": copy.deepcopy(primitives), "cross_validations": []}


def _task5_project_primitive(artifact: dict[str, object], *, artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256, bindings: list[dict[str, object]] | None = None):
    sf = _sf()
    if bindings is None:
        bindings = _task5_source_bindings(artifact_sha256)
    return sf.project_primitive_observations(primitive_artifact=artifact, primitive_artifact_sha256=artifact_sha256, source_bindings=bindings)


def _task5_primitive_signature(projection: object) -> list[tuple[str, int]]:
    assert isinstance(projection, list)
    result = []
    for record in projection:
        assert isinstance(record, dict)
        key = record["observation_key"]
        count = record["occurrence_count"]
        assert isinstance(key, str) and len(key) == 64
        assert isinstance(count, int) and not isinstance(count, bool) and count > 0
        result.append((key, count))
    return sorted(result)


def _task5_semantic_artifact(*, primitive_ids: list[str], primitive_count: int, file_name: str = _TASK5_PRIMITIVE_IR_BASENAME, primitive_sha256: object = None, part_id: str = "part-a", constraint_id: str = "cst-a", reverse_membership: bool = False) -> dict[str, object]:
    ref = {"file_name": file_name, "primitive_count": primitive_count}
    if primitive_sha256 is not None:
        ref["sha256"] = primitive_sha256
    member_ids = list(reversed(primitive_ids)) if reverse_membership else list(primitive_ids)
    parts = [{"id": part_id, "part_type": "thanh_ngang", "primitive_ids": member_ids, "confidence": 0.9, "source": "rule_geometry", "validation": {"status": "unreviewed", "notes": "volatile semantic review"}, "geometry_summary": {"length_mm": 10.0, "orientation_deg": -0.0}}]
    constraints = []
    if len(primitive_ids) >= 2:
        constraints.append({"id": constraint_id, "type": "parallel", "primitive_ids": member_ids[:2], "confidence": 0.8, "tolerance": {"angle_deg": 1.0}, "measured": {"angle_diff_deg": -0.0}})
    return {"schema_version": "1.0.0", "primitive_ir_ref": ref, "parts": parts, "constraints": constraints}


def _task5_project_semantic(semantic_artifact: dict[str, object], primitive_projection: object, *, semantic_artifact_sha256: str = TASK5_SEMANTIC_ARTIFACT_SHA256, primitive_checkpoint_sha256: str = PRIMITIVE_ARTIFACT_SHA256):
    return _sf().project_semantic_observations(semantic_artifact=semantic_artifact, semantic_artifact_sha256=semantic_artifact_sha256, primitive_checkpoint_sha256=primitive_checkpoint_sha256, primitive_observations=primitive_projection)


def _task5_semantic_signature(projection: object) -> list[tuple[str, tuple[str, ...]]]:
    assert isinstance(projection, list)
    result = []
    for record in projection:
        assert isinstance(record, dict)
        key = record["observation_key"]
        primitive_keys = tuple(sorted(record["primitive_observation_keys"]))
        assert isinstance(key, str) and len(key) == 64
        result.append((key, primitive_keys))
    return sorted(result)


def test_task5_public_surface_adds_exactly_two_projection_apis() -> None:
    sf = _sf()
    assert sf.__all__ == ["SOURCE_FUSION_SCHEMA_VERSION", "SourceFusionError", "validate_page_locators", "validate_region_locators", "validate_render_provenance", "project_primitive_observations", "project_semantic_observations"]
    assert list(inspect.signature(sf.project_primitive_observations).parameters) == ["primitive_artifact", "primitive_artifact_sha256", "source_bindings"]
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in inspect.signature(sf.project_primitive_observations).parameters.values())
    assert list(inspect.signature(sf.project_semantic_observations).parameters) == ["semantic_artifact", "semantic_artifact_sha256", "primitive_checkpoint_sha256", "primitive_observations"]
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in inspect.signature(sf.project_semantic_observations).parameters.values())


def test_task5_primitive_identity_ignores_uuid_handle_timestamp_notes_filename_and_order() -> None:
    first = _task5_primitive_artifact([_task5_primitive("prim-a", handle="HANDLE-A", extracted_at="2026-08-08T12:00:00Z"), _task5_primitive("prim-b", end_x=20.0, handle="HANDLE-B")], file_name="customer-secret-a.png", reference_note="reference A")
    second = _task5_primitive_artifact([_task5_primitive("regen-222", end_x=20, handle=None, extracted_at=None, validation_status="reviewer2_fail", validation_notes="different volatile review"), _task5_primitive("regen-111", handle="CHANGED", extracted_at="2099-01-01T00:00:00Z", validation_status="repaired", validation_notes=None)], file_name=r"C:\volatile\renamed-source.png", reference_note=None)
    assert _task5_primitive_signature(_task5_project_primitive(first)) == _task5_primitive_signature(_task5_project_primitive(second))


def test_task5_primitive_equivalent_units_numeric_forms_and_negative_zero_are_canonical() -> None:
    mm = _task5_primitive_artifact([_task5_primitive("prim-a", start_x=-0.0, end_x=10)], unit="mm", pixel_to_unit_scale=1, origin_x=-0.0)
    cm = _task5_primitive_artifact([_task5_primitive("prim-z", start_x=0, end_x=10.0, handle=None, extracted_at=None)], unit="cm", pixel_to_unit_scale=0.1, origin_x=0)
    assert _task5_primitive_signature(_task5_project_primitive(mm)) == _task5_primitive_signature(_task5_project_primitive(cm))


def test_task5_primitive_content_change_changes_observation_key() -> None:
    first = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a", end_x=10)]))
    second = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a", end_x=11)]))
    assert _task5_primitive_signature(first) != _task5_primitive_signature(second)


def test_task5_primitive_checkpoint_must_match_task4_binding() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact(); bindings = _task5_source_bindings(PRIMITIVE_ARTIFACT_SHA256)
    with pytest.raises(sf.SourceFusionError):
        sf.project_primitive_observations(primitive_artifact=artifact, primitive_artifact_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256, source_bindings=bindings)


@pytest.mark.parametrize("field,value", [("sha256", "f" * 64), ("image_width_px", 639), ("image_height_px", 479), ("page_index", 1)])
def test_task5_primitive_source_document_must_match_task4_binding(field: str, value: object) -> None:
    sf = _sf(); artifact = _task5_primitive_artifact(); artifact["source_document"][field] = value
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact)


def test_task5_primitive_identical_observations_form_deterministic_multiset() -> None:
    projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("legacy-a"), _task5_primitive("legacy-b", handle=None, extracted_at=None, validation_status="reviewer1_fail", validation_notes=None)]))
    signature = _task5_primitive_signature(projection)
    assert len(signature) == 1 and signature[0][1] == 2


def test_task5_primitive_duplicate_legacy_ids_fail_closed() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("legacy-dup"), _task5_primitive("legacy-dup", end_x=20)])
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact)


def test_task5_artifact_checkpoint_and_task4_render_hash_are_not_observation_identity() -> None:
    first = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-old")]), artifact_sha256=PRIMITIVE_ARTIFACT_SHA256, bindings=_task5_source_bindings(PRIMITIVE_ARTIFACT_SHA256))
    second = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-regenerated", handle=None, extracted_at=None)]), artifact_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256, bindings=_task5_source_bindings(TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256))
    assert _task5_primitive_signature(first) == _task5_primitive_signature(second)


def test_task5_semantic_identity_ignores_part_constraint_uuid_and_order() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a"), _task5_primitive("prim-b", end_x=20)]))
    first = _task5_semantic_artifact(primitive_ids=["prim-a", "prim-b"], primitive_count=2, part_id="part-old", constraint_id="constraint-old")
    second = _task5_semantic_artifact(primitive_ids=["prim-a", "prim-b"], primitive_count=2, part_id="part-regenerated", constraint_id="constraint-regenerated", reverse_membership=True)
    second["parts"] = list(reversed(second["parts"])); second["constraints"] = list(reversed(second["constraints"]))
    assert _task5_semantic_signature(_task5_project_semantic(first, primitive_projection)) == _task5_semantic_signature(_task5_project_semantic(second, primitive_projection))


def test_task5_semantic_membership_maps_to_primitive_observation_keys() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")]))
    primitive_key = _task5_primitive_signature(primitive_projection)[0][0]
    semantic = _task5_project_semantic(_task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1), primitive_projection)
    assert _task5_semantic_signature(semantic)[0][1] == (primitive_key,)


def test_task5_semantic_proper_subset_of_duplicate_class_fails_exact_ambiguity_code() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("dup-a"), _task5_primitive("dup-b", handle=None)])); semantic = _task5_semantic_artifact(primitive_ids=["dup-a"], primitive_count=2)
    with pytest.raises(sf.SourceFusionError, match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$"):
        _task5_project_semantic(semantic, primitive_projection)


def test_task5_semantic_complete_duplicate_class_is_deterministic() -> None:
    first_primitives = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("dup-a"), _task5_primitive("dup-b", handle=None)]))
    second_primitives = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("regen-b", handle="changed", extracted_at=None), _task5_primitive("regen-a", handle=None, extracted_at="2099-01-01T00:00:00Z")]))
    first_semantic = _task5_semantic_artifact(primitive_ids=["dup-a", "dup-b"], primitive_count=2)
    second_semantic = _task5_semantic_artifact(primitive_ids=["regen-b", "regen-a"], primitive_count=2, part_id="new-part-id", reverse_membership=True)
    assert _task5_semantic_signature(_task5_project_semantic(first_semantic, first_primitives)) == _task5_semantic_signature(_task5_project_semantic(second_semantic, second_primitives))


def test_task5_semantic_missing_primitive_reference_fails_closed() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); semantic = _task5_semantic_artifact(primitive_ids=["missing-legacy-id"], primitive_count=1)
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(semantic, primitive_projection)


def test_task5_primitive_ir_ref_allows_optional_sha_absent() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")]))
    semantic = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1, primitive_sha256=None)
    _task5_project_semantic(semantic, primitive_projection)


def test_task5_primitive_ir_ref_optional_sha_must_equal_external_checkpoint() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")]))
    matching = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1, primitive_sha256=PRIMITIVE_ARTIFACT_SHA256)
    _task5_project_semantic(matching, primitive_projection)
    mismatch = copy.deepcopy(matching); mismatch["primitive_ir_ref"]["sha256"] = TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(mismatch, primitive_projection)


@pytest.mark.parametrize("field,value", [("file_name", "wrong-name.json"), ("primitive_count", 2)])
def test_task5_primitive_ir_ref_wrong_filename_or_total_multiplicity_blocks(field: str, value: object) -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")]))
    semantic = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1); semantic["primitive_ir_ref"][field] = value
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(semantic, primitive_projection)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_task5_projection_rejects_nonfinite_numeric_evidence(bad: float) -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["primitives"][0]["confidence"] = bad
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact)


def test_task5_projection_rejects_noncanonical_numeric_evidence() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["primitives"][0]["geometry"]["end"]["x"] = object()
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact)


def test_task5_projection_replay_and_permutation_are_deterministic() -> None:
    primitives = [_task5_primitive("prim-a"), _task5_primitive("prim-b", end_x=20), _task5_primitive("prim-c", end_x=30)]
    first_artifact = _task5_primitive_artifact(primitives); second_artifact = _task5_primitive_artifact(list(reversed(primitives)))
    first = _task5_project_primitive(copy.deepcopy(first_artifact)); second = _task5_project_primitive(copy.deepcopy(second_artifact))
    assert _task5_primitive_signature(first) == _task5_primitive_signature(second) == _task5_primitive_signature(_task5_project_primitive(copy.deepcopy(first_artifact)))


def test_task5_projection_errors_are_privacy_safe() -> None:
    sf = _sf(); sentinel = r"C:\TOP-SECRET-CUSTOMER\primitive.json"; artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["source_document"]["file_name"] = sentinel; artifact["primitives"][0]["confidence"] = float("nan")
    with pytest.raises(sf.SourceFusionError) as exc_info:
        _task5_project_primitive(artifact)
    assert sentinel not in str(exc_info.value) and "TOP-SECRET-CUSTOMER" not in str(exc_info.value)


def test_task5_cross_platform_canonical_digest_fixture_uses_existing_hash_owner() -> None:
    expected_material = {
        "identity_kind": "r1c-task5-projection-fixture-v1",
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "task4_lineage": {
            "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
            "observed_source_sha256": IMAGE_SHA256,
            "primitive_source_document": {
                "image_height_px": 480,
                "image_width_px": 640,
                "sha256": IMAGE_SHA256,
            },
            "provenance_kind": "DIRECT_IMAGE",
            "raster_height_px": 480,
            "raster_sha256": IMAGE_SHA256,
            "raster_width_px": 640,
            "source_custody_sha256": "ca0fc7efafdd73b0b7c77e1ca78cfd7e0ca38b6da80030a4b25d960cf4f3d4d9",
            "source_id": _IMAGE_SOURCE_ID,
        },
        "source_id": _IMAGE_SOURCE_ID,
        "content": {
            "kind": "line",
            "confidence": "0.875",
            "start_mm": ["0", "0"],
            "end_mm": ["10", "0"],
        },
    }
    assert canonical_json_sha256(expected_material) == "edba06cc715888c38f5471ec1c482a17f4618d5a531c0d814fda1ec5f64be58a"
    projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")]))
    assert _task5_primitive_signature(projection)[0][0] == canonical_json_sha256(expected_material)


def test_task5_static_no_second_owner_gates_cover_projection_dependencies() -> None:
    _sf(); tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8"))
    forbidden = {"hashlib", "json", "uuid", "random", "datetime", "time", "os", "pathlib", "subprocess", "requests", "socket", "urllib", "http", "tempfile", "glob", "shutil", "sqlite3", "PIL", "pypdf", "fitz", "cv2", "pytesseract", "primitive_ir_lib", "semantic_ir_lib", "agent_lib", "autocad_plugin", "mcp_integration_lib"}
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: roots.add(node.module.split(".")[0])
    assert roots.isdisjoint(forbidden)
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert {"open", "__import__", "round", "hash"}.isdisjoint(calls)


# -------------------------------------------------------- Task 5 hardened RED ---

TASK5_OTHER_SEMANTIC_ARTIFACT_SHA256 = "9" * 64


def _task5_three_duplicate_projection() -> object:
    return _task5_project_primitive(
        _task5_primitive_artifact(
            [
                _task5_primitive("dup-a"),
                _task5_primitive("dup-b", handle=None, extracted_at=None),
                _task5_primitive("dup-c", handle="CHANGED", extracted_at="2099-01-01T00:00:00Z"),
            ]
        )
    )


def _task5_alternate_valid_source_binding(
    primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256,
) -> list[dict[str, object]]:
    sf = _sf()
    alternate = copy.deepcopy(_custody())
    alternate["approved_root_revision"] = "ROOT-REV-ALT"
    for item in alternate["items"]:
        item["approved_root_revision"] = "ROOT-REV-ALT"
    alternate = validate_source_custody(alternate)
    pages = _page_payload(alternate)
    record = _direct_image_render_record(
        alternate,
        primitive_artifact_sha256=primitive_artifact_sha256,
        file_name="other-valid-task4-binding.png",
    )
    return sf.validate_render_provenance(
        [record],
        page_locators=pages,
        custody=alternate,
        primitive_artifact_sha256=primitive_artifact_sha256,
    )


def _task5_mapping_contains_authoritative_binding(
    value: object,
    binding: dict[str, object],
) -> bool:
    required = {
        "render_provenance_sha256",
        "source_custody_sha256",
        "source_id",
        "observed_source_sha256",
        "raster_sha256",
        "raster_width_px",
        "raster_height_px",
    }
    if isinstance(value, dict):
        if required.issubset(value) and all(value[key] == binding[key] for key in required):
            return True
        return any(
            _task5_mapping_contains_authoritative_binding(child, binding)
            for child in value.values()
        )
    if isinstance(value, list):
        return any(
            _task5_mapping_contains_authoritative_binding(child, binding)
            for child in value
        )
    return False


def _task5_reachable_calls(function_name: str) -> set[str]:
    tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert function_name in functions

    def call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    pending = [function_name]
    visited: set[str] = set()
    calls: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        node = functions[current]
        direct = {
            call_name(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        }
        calls.update(direct)
        pending.extend(name for name in direct if name in functions and name not in visited)
    return calls


def test_task5_duplicate_class_multiplicity_three_requires_complete_selection() -> None:
    sf = _sf()
    primitive_projection = _task5_three_duplicate_projection()
    for selected in (["dup-a"], ["dup-a", "dup-b"]):
        semantic = _task5_semantic_artifact(
            primitive_ids=list(selected),
            primitive_count=3,
        )
        with pytest.raises(
            sf.SourceFusionError,
            match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$",
        ):
            _task5_project_semantic(semantic, primitive_projection)

    complete = _task5_semantic_artifact(
        primitive_ids=["dup-a", "dup-b", "dup-c"],
        primitive_count=3,
    )
    complete["constraints"][0]["primitive_ids"] = ["dup-a", "dup-b", "dup-c"]
    reverse = _task5_semantic_artifact(
        primitive_ids=["dup-c", "dup-b", "dup-a"],
        primitive_count=3,
        part_id="part-regenerated",
    )
    reverse["constraints"][0]["primitive_ids"] = ["dup-c", "dup-b", "dup-a"]
    assert _task5_semantic_signature(
        _task5_project_semantic(complete, primitive_projection)
    ) == _task5_semantic_signature(
        _task5_project_semantic(reverse, primitive_projection)
    )


def test_task5_reused_legacy_ids_cannot_spoof_duplicate_multiplicity() -> None:
    sf = _sf()
    primitive_projection = _task5_three_duplicate_projection()
    repeated = _task5_semantic_artifact(
        primitive_ids=["dup-a", "dup-a", "dup-a"],
        primitive_count=3,
    )
    with pytest.raises(
        sf.SourceFusionError,
        match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$",
    ):
        _task5_project_semantic(repeated, primitive_projection)

    split = _task5_semantic_artifact(
        primitive_ids=["dup-a"],
        primitive_count=3,
    )
    split["parts"] = [
        {**copy.deepcopy(split["parts"][0]), "id": "part-a", "primitive_ids": ["dup-a"]},
        {**copy.deepcopy(split["parts"][0]), "id": "part-b", "primitive_ids": ["dup-b"]},
        {**copy.deepcopy(split["parts"][0]), "id": "part-c", "primitive_ids": ["dup-c"]},
    ]
    with pytest.raises(
        sf.SourceFusionError,
        match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$",
    ):
        _task5_project_semantic(split, primitive_projection)


@pytest.mark.parametrize("same_content", [True, False])
def test_task5_duplicate_primitive_legacy_id_always_fails_closed(
    same_content: bool,
) -> None:
    sf = _sf()
    second = _task5_primitive("legacy-dup", end_x=10 if same_content else 20)
    artifact = _task5_primitive_artifact(
        [_task5_primitive("legacy-dup"), second]
    )
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact)


def test_task5_task4_binding_duplicates_are_order_neutral_but_incompatible_valid_bindings_fail() -> None:
    sf = _sf()
    artifact = _task5_primitive_artifact()
    first = _task5_source_bindings()
    duplicated = [copy.deepcopy(first[0]), copy.deepcopy(first[0])]
    forward = _task5_project_primitive(artifact, bindings=duplicated)
    reverse = _task5_project_primitive(artifact, bindings=list(reversed(duplicated)))
    single = _task5_project_primitive(artifact, bindings=first)
    assert _task5_primitive_signature(forward) == _task5_primitive_signature(reverse)
    assert _task5_primitive_signature(forward) == _task5_primitive_signature(single)

    alternate = _task5_alternate_valid_source_binding()
    assert alternate[0]["raster_sha256"] == first[0]["raster_sha256"]
    assert alternate[0]["source_custody_sha256"] != first[0]["source_custody_sha256"]
    for bindings in ([first[0], alternate[0]], [alternate[0], first[0]]):
        with pytest.raises(sf.SourceFusionError):
            _task5_project_primitive(artifact, bindings=list(bindings))

    stale = copy.deepcopy(first[0])
    stale["primitive_artifact_sha256"] = TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256
    with pytest.raises(sf.SourceFusionError):
        _task5_project_primitive(artifact, bindings=[first[0], stale])


@pytest.mark.parametrize(
    "file_name",
    [
        "../primitive_ir.json",
        r"C:\primitive_ir.json",
        r"\\server\share\primitive_ir.json",
        "folder/primitive_ir.json",
        r"folder\primitive_ir.json",
        ".primitive_ir.json",
        "Primitive_IR.json",
    ],
)
def test_task5_primitive_ir_ref_filename_is_literal_compatibility_only(
    file_name: str,
) -> None:
    sf = _sf()
    primitive_projection = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-a")])
    )
    semantic = _task5_semantic_artifact(
        primitive_ids=["prim-a"],
        primitive_count=1,
        file_name=file_name,
    )
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(semantic, primitive_projection)


@pytest.mark.parametrize("bad_count", [True, -1, 1.5])
def test_task5_primitive_count_rejects_bool_negative_and_nonintegral(
    bad_count: object,
) -> None:
    sf = _sf()
    primitive_projection = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-a")])
    )
    semantic = _task5_semantic_artifact(
        primitive_ids=["prim-a"],
        primitive_count=1,
    )
    semantic["primitive_ir_ref"]["primitive_count"] = bad_count
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(semantic, primitive_projection)


def test_task5_semantic_identity_ignores_artifact_sha_and_matching_checkpoint_rewrite() -> None:
    first_primitives = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-old")]),
        artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
        bindings=_task5_source_bindings(PRIMITIVE_ARTIFACT_SHA256),
    )
    second_primitives = _task5_project_primitive(
        _task5_primitive_artifact(
            [_task5_primitive("prim-regenerated", handle=None, extracted_at=None)]
        ),
        artifact_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256,
        bindings=_task5_source_bindings(TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256),
    )
    first_semantic = _task5_semantic_artifact(
        primitive_ids=["prim-old"],
        primitive_count=1,
        primitive_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    second_semantic = _task5_semantic_artifact(
        primitive_ids=["prim-regenerated"],
        primitive_count=1,
        primitive_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256,
        part_id="part-regenerated",
    )
    first = _task5_project_semantic(
        first_semantic,
        first_primitives,
        semantic_artifact_sha256=TASK5_SEMANTIC_ARTIFACT_SHA256,
        primitive_checkpoint_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    second = _task5_project_semantic(
        second_semantic,
        second_primitives,
        semantic_artifact_sha256=TASK5_OTHER_SEMANTIC_ARTIFACT_SHA256,
        primitive_checkpoint_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256,
    )
    assert _task5_semantic_signature(first) == _task5_semantic_signature(second)


@pytest.mark.parametrize(
    "target,bad",
    [
        ("primitive_confidence", True),
        ("primitive_confidence", float("nan")),
        ("primitive_geometry", True),
        ("primitive_geometry", float("inf")),
        ("primitive_geometry", object()),
        ("semantic_part_confidence", True),
        ("semantic_part_confidence", float("-inf")),
        ("semantic_geometry", True),
        ("semantic_geometry", object()),
        ("semantic_constraint_confidence", True),
        ("semantic_constraint_confidence", float("nan")),
        ("semantic_tolerance", True),
        ("semantic_tolerance", float("inf")),
        ("semantic_measured", True),
        ("semantic_measured", object()),
    ],
)
def test_task5_numeric_rejection_covers_primitive_and_semantic_fields(
    target: str,
    bad: object,
) -> None:
    sf = _sf()
    if target.startswith("primitive_"):
        artifact = _task5_primitive_artifact([_task5_primitive("prim-a")])
        if target == "primitive_confidence":
            artifact["primitives"][0]["confidence"] = bad
        else:
            artifact["primitives"][0]["geometry"]["end"]["x"] = bad
        with pytest.raises(sf.SourceFusionError):
            _task5_project_primitive(artifact)
        return

    primitive_projection = _task5_project_primitive(
        _task5_primitive_artifact(
            [_task5_primitive("prim-a"), _task5_primitive("prim-b", end_x=20)]
        )
    )
    semantic = _task5_semantic_artifact(
        primitive_ids=["prim-a", "prim-b"],
        primitive_count=2,
    )
    if target == "semantic_part_confidence":
        semantic["parts"][0]["confidence"] = bad
    elif target == "semantic_geometry":
        semantic["parts"][0]["geometry_summary"]["length_mm"] = bad
    elif target == "semantic_constraint_confidence":
        semantic["constraints"][0]["confidence"] = bad
    elif target == "semantic_tolerance":
        semantic["constraints"][0]["tolerance"]["angle_deg"] = bad
    else:
        semantic["constraints"][0]["measured"]["angle_diff_deg"] = bad
    with pytest.raises(sf.SourceFusionError):
        _task5_project_semantic(semantic, primitive_projection)


@pytest.mark.parametrize(
    "projection_api",
    ["project_primitive_observations", "project_semantic_observations"],
)
def test_task5_projection_callgraphs_reach_existing_numeric_and_hash_owners(
    projection_api: str,
) -> None:
    tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8"))
    imported = {
        (node.module, alias.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
    }
    assert ("cad_agent.source_integrity", "canonicalize_r1c_quantity") in imported
    assert ("cad_agent.drawing_contracts", "canonical_json_sha256") in imported
    reachable = _task5_reachable_calls(projection_api)
    assert "canonicalize_r1c_quantity" in reachable
    assert "canonical_json_sha256" in reachable


def test_task5_calibration_reference_note_add_change_remove_is_volatile() -> None:
    variants = [
        _task5_primitive_artifact(reference_note=None),
        _task5_primitive_artifact(reference_note="calibration note A"),
        _task5_primitive_artifact(reference_note="calibration note B"),
    ]
    signatures = {
        tuple(_task5_primitive_signature(_task5_project_primitive(variant)))
        for variant in variants
    }
    assert len(signatures) == 1


def _task5_replay_semantic(
    ids: list[str],
    *,
    reverse: bool,
) -> dict[str, object]:
    semantic = _task5_semantic_artifact(
        primitive_ids=ids[:2],
        primitive_count=3,
        part_id=f"part-{ids[0]}",
        constraint_id=f"constraint-{ids[0]}",
        reverse_membership=reverse,
    )
    second_part = copy.deepcopy(semantic["parts"][0])
    second_part["id"] = f"part-{ids[2]}"
    second_part["primitive_ids"] = [ids[2]]
    second_part["confidence"] = 0.7
    second_part["geometry_summary"] = {
        "length_mm": 30.0,
        "orientation_deg": 0.0,
    }
    second_constraint = copy.deepcopy(semantic["constraints"][0])
    second_constraint["id"] = f"constraint-{ids[2]}"
    second_constraint["primitive_ids"] = [ids[1], ids[2]]
    second_constraint["confidence"] = 0.7
    semantic["parts"].append(second_part)
    semantic["constraints"].append(second_constraint)
    if reverse:
        semantic["parts"] = list(reversed(semantic["parts"]))
        semantic["constraints"] = list(reversed(semantic["constraints"]))
        for part in semantic["parts"]:
            part["primitive_ids"] = list(reversed(part["primitive_ids"]))
        for constraint in semantic["constraints"]:
            constraint["primitive_ids"] = list(reversed(constraint["primitive_ids"]))
    return semantic


def test_task5_focused_projection_replay_permutation_is_stable_for_five_executions() -> None:
    baseline_primitive = None
    baseline_semantic = None
    for iteration in range(5):
        ids = [f"regen-{iteration}-{index}" for index in range(3)]
        primitives = [
            _task5_primitive(
                ids[0],
                start_x=-0.0 if iteration % 2 == 0 else 0,
                end_x=10,
                handle=None if iteration % 2 else f"H-{iteration}-0",
                extracted_at=None if iteration % 2 else f"2026-08-0{iteration + 1}T00:00:00Z",
            ),
            _task5_primitive(
                ids[1],
                end_x=20.0,
                handle=f"H-{iteration}-1" if iteration % 2 else None,
                extracted_at="2099-01-01T00:00:00Z" if iteration % 2 else None,
            ),
            _task5_primitive(
                ids[2],
                end_x=30,
                handle=None,
                extracted_at=None,
            ),
        ]
        if iteration % 2:
            primitives = list(reversed(primitives))
        artifact = _task5_primitive_artifact(
            primitives,
            unit="cm" if iteration % 2 else "mm",
            pixel_to_unit_scale=0.1 if iteration % 2 else 1,
            origin_x=0 if iteration % 2 else -0.0,
            reference_note=None if iteration % 2 else f"volatile-{iteration}",
        )
        bindings = _task5_source_bindings()
        bindings = [copy.deepcopy(bindings[0]), copy.deepcopy(bindings[0])]
        if iteration % 2:
            bindings.reverse()
        primitive_projection = _task5_project_primitive(artifact, bindings=bindings)
        semantic = _task5_replay_semantic(ids, reverse=bool(iteration % 2))
        semantic_projection = _task5_project_semantic(
            semantic,
            primitive_projection,
            semantic_artifact_sha256=(hex(iteration + 10)[2:] * 64)[:64],
        )
        primitive_signature = _task5_primitive_signature(primitive_projection)
        semantic_signature = _task5_semantic_signature(semantic_projection)
        if baseline_primitive is None:
            baseline_primitive = primitive_signature
            baseline_semantic = semantic_signature
        else:
            assert primitive_signature == baseline_primitive
            assert semantic_signature == baseline_semantic


def test_task5_primitive_projection_preserves_full_task4_custody_binding_semantics() -> None:
    binding = _task5_source_bindings()[0]
    projection = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-a")]),
        bindings=[binding],
    )
    assert isinstance(projection, list) and projection
    for record in projection:
        assert isinstance(record, dict)
        assert _task5_mapping_contains_authoritative_binding(record, binding)


def _task5_stable_task4_lineage_material(binding: dict[str, object]) -> dict[str, object]:
    return {
        key: copy.deepcopy(value)
        for key, value in binding.items()
        if key not in {"render_provenance_sha256", "primitive_artifact_sha256"}
    }


def test_task5_primitive_identity_changes_across_distinct_authoritative_task4_lineage() -> None:
    artifact = _task5_primitive_artifact([_task5_primitive("prim-a")])
    first_binding = _task5_source_bindings()[0]
    alternate_binding = _task5_alternate_valid_source_binding()[0]

    assert first_binding["source_id"] == alternate_binding["source_id"]
    assert first_binding["observed_source_sha256"] == alternate_binding["observed_source_sha256"]
    assert first_binding["raster_sha256"] == alternate_binding["raster_sha256"]
    assert first_binding["source_custody_sha256"] != alternate_binding["source_custody_sha256"]
    assert (
        _task5_stable_task4_lineage_material(first_binding)
        != _task5_stable_task4_lineage_material(alternate_binding)
    )

    first = _task5_project_primitive(artifact, bindings=[first_binding])
    alternate = _task5_project_primitive(artifact, bindings=[alternate_binding])
    assert _task5_primitive_signature(first) != _task5_primitive_signature(alternate)


def test_task5_primitive_identity_lineage_mutation_is_not_binding_order_authority() -> None:
    artifact = _task5_primitive_artifact([_task5_primitive("prim-a")])
    for binding in (
        _task5_source_bindings()[0],
        _task5_alternate_valid_source_binding()[0],
    ):
        duplicated = [copy.deepcopy(binding), copy.deepcopy(binding)]
        forward = _task5_project_primitive(artifact, bindings=duplicated)
        reverse = _task5_project_primitive(artifact, bindings=list(reversed(duplicated)))
        single = _task5_project_primitive(artifact, bindings=[binding])
        assert _task5_primitive_signature(forward) == _task5_primitive_signature(reverse)
        assert _task5_primitive_signature(forward) == _task5_primitive_signature(single)


@pytest.mark.parametrize(
    "constraint_ids",
    [
        ["dup-a"],
        ["dup-a", "dup-b"],
    ],
    ids=["constraint-selects-1-of-3", "constraint-selects-2-of-3"],
)
def test_task5_each_semantic_object_rejects_its_own_duplicate_class_proper_subset(
    constraint_ids: list[str],
) -> None:
    sf = _sf()
    primitive_projection = _task5_three_duplicate_projection()
    semantic = _task5_semantic_artifact(
        primitive_ids=["dup-a", "dup-b", "dup-c"],
        primitive_count=3,
    )
    assert semantic["parts"][0]["primitive_ids"] == ["dup-a", "dup-b", "dup-c"]
    semantic["constraints"][0]["primitive_ids"] = list(constraint_ids)

    with pytest.raises(
        sf.SourceFusionError,
        match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$",
    ):
        _task5_project_semantic(semantic, primitive_projection)


def test_task5_each_semantic_object_complete_duplicate_class_is_permutation_stable() -> None:
    primitive_projection = _task5_three_duplicate_projection()
    forward = _task5_semantic_artifact(
        primitive_ids=["dup-a", "dup-b", "dup-c"],
        primitive_count=3,
    )
    forward["constraints"][0]["primitive_ids"] = ["dup-a", "dup-b", "dup-c"]
    reverse = _task5_semantic_artifact(
        primitive_ids=["dup-c", "dup-b", "dup-a"],
        primitive_count=3,
        part_id="part-regenerated",
        constraint_id="constraint-regenerated",
    )
    reverse["constraints"][0]["primitive_ids"] = ["dup-c", "dup-b", "dup-a"]

    assert _task5_semantic_signature(
        _task5_project_semantic(forward, primitive_projection)
    ) == _task5_semantic_signature(
        _task5_project_semantic(reverse, primitive_projection)
    )


# -------------------------------------------------------- Task 6 RED ---


def _task6_tolerance_policy() -> dict[str, object]:
    return {
        "tolerance_policy_version": R1C_TOLERANCE_POLICY_VERSION,
        "quantity": "physical_length",
        "unit": "mm",
        "value": "0.001",
    }


def _task6_ready_inputs(
    *,
    primitive_observations: object | None = None,
    semantic_observations: object | None = None,
    custody: dict[str, object] | None = None,
) -> dict[str, object]:
    sf = _sf()
    bundle = _source_bundle()
    if custody is None:
        custody = _custody(bundle)
    pages = sf.validate_page_locators(
        _page_payload(custody),
        source_bundle=bundle,
        custody=custody,
    )
    regions = sf.validate_region_locators(
        _region_payload(custody, pages),
        page_locators=pages,
        custody=custody,
    )
    renders = sf.validate_render_provenance(
        [_direct_image_render_record(custody)],
        page_locators=pages,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )
    if primitive_observations is None:
        primitive_observations = _task5_project_primitive(
            _task5_primitive_artifact([_task5_primitive("prim-a")])
        )
    if semantic_observations is None:
        semantic_observations = _task5_project_semantic(
            _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1),
            primitive_observations,
        )
    return {
        "source_bundle": bundle,
        "custody": custody,
        "page_locators": pages,
        "region_locators": regions,
        "render_provenance": renders,
        "primitive_observations": primitive_observations,
        "semantic_observations": semantic_observations,
        "tolerance_policy": _task6_tolerance_policy(),
    }


def test_task6_public_surface_adds_only_the_four_planned_packet_apis() -> None:
    sf = _sf()
    expected = [
        "SOURCE_FUSION_SCHEMA_VERSION",
        "SourceFusionError",
        "validate_page_locators",
        "validate_region_locators",
        "validate_render_provenance",
        "project_primitive_observations",
        "project_semantic_observations",
        "build_source_fusion_packet",
        "validate_source_fusion_packet",
        "source_fusion_sha256",
        "require_source_fusion_match",
    ]
    assert sf.__all__ == expected
    assert list(inspect.signature(sf.build_source_fusion_packet).parameters) == [
        "source_bundle",
        "custody",
        "page_locators",
        "region_locators",
        "render_provenance",
        "primitive_observations",
        "semantic_observations",
        "tolerance_policy",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in inspect.signature(sf.build_source_fusion_packet).parameters.values()
    )


def test_task6_ready_packet_is_deterministic_over_existing_task4_task5_evidence() -> None:
    sf = _sf()
    inputs = _task6_ready_inputs()
    first = sf.build_source_fusion_packet(**inputs)
    replay = sf.build_source_fusion_packet(
        **{
            **inputs,
            "page_locators": list(reversed(inputs["page_locators"])),
            "region_locators": list(reversed(inputs["region_locators"])),
            "render_provenance": list(reversed(inputs["render_provenance"])),
            "primitive_observations": list(reversed(inputs["primitive_observations"])),
            "semantic_observations": list(reversed(inputs["semantic_observations"])),
        }
    )
    assert sf.validate_source_fusion_packet(first)["status"] == "READY"
    assert sf.source_fusion_sha256(first) == sf.source_fusion_sha256(replay)
    assert first == replay


def test_task6_competing_geometry_evidence_is_preserved_as_unresolved_blocker() -> None:
    sf = _sf()
    first_primitive = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-a", end_x=10)])
    )
    second_primitive = _task5_project_primitive(
        _task5_primitive_artifact([_task5_primitive("prim-a", end_x=11)])
    )
    first_semantic = _task5_project_semantic(
        _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1),
        first_primitive,
    )
    second_semantic = _task5_project_semantic(
        _task5_semantic_artifact(
            primitive_ids=["prim-a"],
            primitive_count=1,
            part_id="part-regenerated",
            constraint_id="constraint-regenerated",
        ),
        second_primitive,
    )
    packet = sf.build_source_fusion_packet(
        **_task6_ready_inputs(
            primitive_observations=first_primitive + second_primitive,
            semantic_observations=first_semantic + second_semantic,
        )
    )
    assert packet["status"] == "BLOCKED_UNRESOLVED"
    assert packet["conflicts"]
    assert all(conflict["state"] == "UNRESOLVED" for conflict in packet["conflicts"])
    assert len(packet["primitive_observations"]) == 2
    assert len(packet["semantic_observations"]) == 2


def test_task6_non_ready_custody_produces_no_fusion_packet() -> None:
    sf = _sf()
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_NOT_READY$"):
        sf.build_source_fusion_packet(**_task6_ready_inputs(custody=_blocked_custody()))
