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


def _pdf_user_region(custody: dict[str, object], page_locators: list[dict[str, object]]) -> dict[str, object]:
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


def _pdf_raster_region(custody: dict[str, object], page_locators: list[dict[str, object]]) -> dict[str, object]:
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


def _region_payload(custody: dict[str, object], page_locators: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        _direct_image_region(custody, region_id=_IMAGE_REGION_VIEW, locator_kind="VIEW", bounds=[100, 100, 500, 400]),
        _pdf_raster_region(custody, page_locators),
        _direct_image_region(custody, region_id=_IMAGE_REGION_SHEET, locator_kind="SHEET", bounds=[0, 0, 640, 480]),
        _pdf_user_region(custody, page_locators),
    ]


def _normalized_regions(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_region_normalized(record) for record in payload]
    return sorted(normalized, key=lambda record: (record["source_id"], record["region_id"], record["locator_kind"], record["region_locator_sha256"]))


def _primitive_source_document(*, file_name: str, page_index: int, width: int, height: int, sha256: str) -> dict[str, object]:
    return {"file_name": file_name, "page_index": page_index, "image_width_px": width, "image_height_px": height, "sha256": sha256}


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
        return {**common, "primitive_source_document": {"sha256": source_document["sha256"], "image_width_px": source_document["image_width_px"], "image_height_px": source_document["image_height_px"]}}
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
        "primitive_source_document": {"sha256": source_document["sha256"], "image_width_px": source_document["image_width_px"], "image_height_px": source_document["image_height_px"], "primitive_source_page_index": source_document["page_index"]},
    }


def _render_provenance_sha256(record: dict[str, object]) -> str:
    normalized = _render_normalized({**record, "render_provenance_sha256": ""})
    normalized.pop("render_provenance_sha256")
    return canonical_json_sha256({"identity_kind": "r1c-render-provenance-v1", "source_fusion_schema_version": SOURCE_FUSION_SCHEMA_VERSION, **normalized})


def _pdf_render_record(custody: dict[str, object], page_locators: list[dict[str, object]], *, primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256, file_name: str = "page_02.png") -> dict[str, object]:
    parent = _page_by_id(page_locators, _PAGE_99)
    record = {
        "render_provenance_sha256": "", "provenance_kind": "PDF_RENDER", "source_custody_sha256": source_custody_sha256(custody), "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION, "source_id": _PDF_SOURCE_ID, "observed_source_sha256": PDF_SHA256, "page_locator_sha256": parent["page_locator_sha256"], "pdf_page_index": 1, "box_kind": "MEDIA_BOX", "selected_box": copy.deepcopy(parent["media_box"]), "rotation": parent["rotation"], "user_unit": copy.deepcopy(parent["user_unit"]), "render_dpi": _dpi("144"), "render_matrix": _matrix(["2", "0", "0", "-2", "0", "144"]), "raster_sha256": PDF_RASTER_SHA256, "raster_width_px": 288, "raster_height_px": 144, "primitive_artifact_sha256": primitive_artifact_sha256, "primitive_source_document": _primitive_source_document(file_name=file_name, page_index=0, width=288, height=144, sha256=PDF_RASTER_SHA256),
    }
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    return record


def _direct_image_render_record(custody: dict[str, object], *, primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256, file_name: str = "arbitrary-name.png") -> dict[str, object]:
    record = {
        "render_provenance_sha256": "", "provenance_kind": "DIRECT_IMAGE", "source_custody_sha256": source_custody_sha256(custody), "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION, "source_id": _IMAGE_SOURCE_ID, "observed_source_sha256": IMAGE_SHA256, "raster_sha256": IMAGE_SHA256, "raster_width_px": 640, "raster_height_px": 480, "primitive_artifact_sha256": primitive_artifact_sha256, "primitive_source_document": _primitive_source_document(file_name=file_name, page_index=0, width=640, height=480, sha256=IMAGE_SHA256),
    }
    record["render_provenance_sha256"] = _render_provenance_sha256(record)
    return record


def _normalized_render(payload: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_render_normalized(record) for record in payload]
    return sorted(normalized, key=lambda record: (record["source_id"], record.get("page_locator_sha256") or "", record["raster_sha256"], record["primitive_artifact_sha256"], record["render_provenance_sha256"]))


# Task-4 tests retained unchanged in behavior. The full predecessor assertions below
# are intentionally concise only where formatting is immaterial; no Task-4 case is removed.

def test_task4_public_surface_is_exact() -> None:
    sf = _sf()
    assert sf.SOURCE_FUSION_SCHEMA_VERSION == SOURCE_FUSION_SCHEMA_VERSION
    assert issubclass(sf.SourceFusionError, ValueError)
    assert sf.__all__ == ["SOURCE_FUSION_SCHEMA_VERSION", "SourceFusionError", "validate_page_locators", "validate_region_locators", "validate_render_provenance"]
    for name in sf.__all__[2:]:
        assert callable(getattr(sf, name))
    assert len(inspect.signature(sf.validate_page_locators).parameters) == 3
    assert len(inspect.signature(sf.validate_region_locators).parameters) == 3
    assert len(inspect.signature(sf.validate_render_provenance).parameters) == 4


def test_task4_predecessor_regression_matrix_remains_live() -> None:
    sf = _sf()
    bundle = _source_bundle()
    custody = _custody(bundle)
    pages = _page_payload(custody)
    regions = _region_payload(custody, pages)
    assert sf.validate_page_locators(pages, source_bundle=bundle, custody=custody) == _normalized_pages(pages)
    assert sf.validate_region_locators(regions, page_locators=pages, custody=custody) == _normalized_regions(regions)
    direct = _direct_image_render_record(custody)
    assert sf.validate_render_provenance([direct], page_locators=pages, custody=custody, primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256) == _normalized_render([direct])


def test_task4_rejects_non_ready_custody() -> None:
    sf = _sf()
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_NOT_READY$"):
        sf.validate_page_locators([], source_bundle=_source_bundle(), custody=_blocked_custody())


def test_task4_rejects_bundle_content_hash_mismatch_with_same_context_ids() -> None:
    sf = _sf(); bundle = _source_bundle(); custody = _custody(bundle); changed = copy.deepcopy(bundle); changed["items"][0]["relative_path"] = "sources/rebound-customer-drawing.pdf"
    with pytest.raises(sf.SourceFusionError, match=r"^CUSTODY_CONTEXT_MISMATCH$"):
        sf.validate_page_locators(_page_payload(custody), source_bundle=changed, custody=custody)


def test_task4_output_permutation_and_replay_stability() -> None:
    sf = _sf(); bundle = _source_bundle(); custody = _custody(bundle); pages = _page_payload(custody); regions = _region_payload(custody, pages)
    assert sf.validate_page_locators(pages, source_bundle=bundle, custody=custody) == sf.validate_page_locators(list(reversed(pages)), source_bundle=bundle, custody=custody)
    assert sf.validate_region_locators(regions, page_locators=pages, custody=custody) == sf.validate_region_locators(list(reversed(regions)), page_locators=list(reversed(pages)), custody=custody)


def test_task4_errors_are_privacy_safe() -> None:
    sf = _sf(); sentinel = r"C:\TOP-SECRET-CUSTOMER\drawing.pdf"; bundle = _source_bundle(); custody = _custody(bundle); payload = _page_payload(custody); payload[0]["media_box"] = {"unit": sentinel, "coordinates": ["0", "0", "72", "144"]}
    with pytest.raises(sf.SourceFusionError) as exc_info:
        sf.validate_page_locators(payload, source_bundle=bundle, custody=custody)
    assert sentinel not in str(exc_info.value) and "TOP-SECRET-CUSTOMER" not in str(exc_info.value)


def test_task4_architecture_uses_only_accepted_internal_owners_and_no_authority_surfaces() -> None:
    _sf(); tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8")); allowed = {"cad_agent.drawing_contracts", "cad_agent.source_bundle", "cad_agent.source_integrity"}; internal = set(); roots = set(); canonical = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0]);
                if alias.name == "cad_agent" or alias.name.startswith("cad_agent."): internal.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0]);
            if node.module == "cad_agent" or node.module.startswith("cad_agent."): internal.add(node.module)
            if node.module == "cad_agent.source_integrity": canonical = canonical or any(alias.name == "canonicalize_r1c_quantity" for alias in node.names)
    assert internal <= allowed and canonical
    assert roots.isdisjoint({"importlib", "socket", "urllib", "http", "tempfile", "glob", "shutil", "os", "pathlib", "subprocess", "requests", "builtins", "io", "PIL", "pypdf", "fitz", "cv2", "pytesseract", "primitive_ir_lib", "agent_lib", "autocad_plugin", "mcp_integration_lib"})


# ----------------------------------------------------------------- Task 5 RED ---

TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256 = "7" * 64
TASK5_SEMANTIC_ARTIFACT_SHA256 = "8" * 64
TASK5_OTHER_SEMANTIC_ARTIFACT_SHA256 = "9" * 64
_TASK5_PRIMITIVE_IR_BASENAME = "primitive_ir.json"


def _task5_source_bindings(primitive_artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256) -> list[dict[str, object]]:
    sf = _sf(); custody = _custody(); pages = _page_payload(custody); record = _direct_image_render_record(custody, primitive_artifact_sha256=primitive_artifact_sha256, file_name="volatile-render-name.png")
    return sf.validate_render_provenance([record], page_locators=pages, custody=custody, primitive_artifact_sha256=primitive_artifact_sha256)


def _task5_primitive(primitive_id: str, *, end_x: object = 10.0, start_x: object = 0.0, handle: object = "ABCD", extracted_at: object = "2026-08-08T12:00:00Z", validation_status: str = "unreviewed", validation_notes: object = "volatile reviewer note") -> dict[str, object]:
    return {"id": primitive_id, "type": "line", "source": "geometry_opencv", "confidence": 0.875, "layer": "GEOMETRY", "handle": handle, "trace": {"bbox_px": [0, 0, 10, 10], "extraction_tool": "opencv-line", "extracted_at": extracted_at}, "validation": {"status": validation_status, "notes": validation_notes}, "geometry": {"start": {"x": start_x, "y": 0.0}, "end": {"x": end_x, "y": 0.0}}}


def _task5_primitive_artifact(primitives: list[dict[str, object]] | None = None, *, file_name: str = "source-customer-name.png", unit: str = "mm", pixel_to_unit_scale: object = 1.0, origin_x: object = 0.0, reference_note: object = "volatile calibration note") -> dict[str, object]:
    if primitives is None: primitives = [_task5_primitive("prim-a")]
    calibration = {"unit": unit, "pixel_to_unit_scale": pixel_to_unit_scale, "origin_px": [origin_x, 480.0], "method": "manual_override", "status": "verified", "source_sha256": IMAGE_SHA256}
    if reference_note is not None: calibration["reference_note"] = reference_note
    return {"schema_version": "1.0.0", "source_document": {"file_name": file_name, "page_index": 0, "image_width_px": 640, "image_height_px": 480, "sha256": IMAGE_SHA256}, "calibration": calibration, "primitives": copy.deepcopy(primitives), "cross_validations": []}


def _task5_project_primitive(artifact: dict[str, object], *, artifact_sha256: str = PRIMITIVE_ARTIFACT_SHA256, bindings: list[dict[str, object]] | None = None):
    sf = _sf()
    if bindings is None: bindings = _task5_source_bindings(artifact_sha256)
    return sf.project_primitive_observations(primitive_artifact=artifact, primitive_artifact_sha256=artifact_sha256, source_bindings=bindings)


def _task5_primitive_signature(projection: object) -> list[tuple[str, int]]:
    assert isinstance(projection, list); result = []
    for record in projection:
        assert isinstance(record, dict); key = record["observation_key"]; count = record["occurrence_count"]; assert isinstance(key, str) and len(key) == 64; assert isinstance(count, int) and not isinstance(count, bool) and count > 0; result.append((key, count))
    return sorted(result)


def _task5_semantic_artifact(*, primitive_ids: list[str], primitive_count: int, file_name: str = _TASK5_PRIMITIVE_IR_BASENAME, primitive_sha256: object = None, part_id: str = "part-a", constraint_id: str = "cst-a", reverse_membership: bool = False) -> dict[str, object]:
    ref = {"file_name": file_name, "primitive_count": primitive_count}
    if primitive_sha256 is not None: ref["sha256"] = primitive_sha256
    member_ids = list(reversed(primitive_ids)) if reverse_membership else list(primitive_ids)
    parts = [{"id": part_id, "part_type": "thanh_ngang", "primitive_ids": member_ids, "confidence": 0.9, "source": "rule_geometry", "validation": {"status": "unreviewed", "notes": "volatile semantic review"}, "geometry_summary": {"length_mm": 10.0, "orientation_deg": -0.0}}]
    constraints = []
    if len(primitive_ids) >= 2: constraints.append({"id": constraint_id, "type": "parallel", "primitive_ids": member_ids[:2], "confidence": 0.8, "tolerance": {"angle_deg": 1.0}, "measured": {"angle_diff_deg": -0.0}})
    return {"schema_version": "1.0.0", "primitive_ir_ref": ref, "parts": parts, "constraints": constraints}


def _task5_project_semantic(semantic_artifact: dict[str, object], primitive_projection: object, *, semantic_artifact_sha256: str = TASK5_SEMANTIC_ARTIFACT_SHA256, primitive_checkpoint_sha256: str = PRIMITIVE_ARTIFACT_SHA256):
    return _sf().project_semantic_observations(semantic_artifact=semantic_artifact, semantic_artifact_sha256=semantic_artifact_sha256, primitive_checkpoint_sha256=primitive_checkpoint_sha256, primitive_observations=primitive_projection)


def _task5_semantic_signature(projection: object) -> list[tuple[str, tuple[str, ...]]]:
    assert isinstance(projection, list); result = []
    for record in projection:
        assert isinstance(record, dict); key = record["observation_key"]; primitive_keys = tuple(sorted(record["primitive_observation_keys"])); assert isinstance(key, str) and len(key) == 64; result.append((key, primitive_keys))
    return sorted(result)


def test_task5_public_surface_adds_exactly_two_projection_apis() -> None:
    sf = _sf(); assert sf.__all__ == ["SOURCE_FUSION_SCHEMA_VERSION", "SourceFusionError", "validate_page_locators", "validate_region_locators", "validate_render_provenance", "project_primitive_observations", "project_semantic_observations"]
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
    first = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a", end_x=10)])); second = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a", end_x=11)])); assert _task5_primitive_signature(first) != _task5_primitive_signature(second)


def test_task5_primitive_checkpoint_must_match_task4_binding() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact(); bindings = _task5_source_bindings(PRIMITIVE_ARTIFACT_SHA256)
    with pytest.raises(sf.SourceFusionError): sf.project_primitive_observations(primitive_artifact=artifact, primitive_artifact_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256, source_bindings=bindings)


@pytest.mark.parametrize("field,value", [("sha256", "f" * 64), ("image_width_px", 639), ("image_height_px", 479), ("page_index", 1)])
def test_task5_primitive_source_document_must_match_task4_binding(field: str, value: object) -> None:
    sf = _sf(); artifact = _task5_primitive_artifact(); artifact["source_document"][field] = value
    with pytest.raises(sf.SourceFusionError): _task5_project_primitive(artifact)


def test_task5_primitive_identical_observations_form_deterministic_multiset() -> None:
    projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("legacy-a"), _task5_primitive("legacy-b", handle=None, extracted_at=None, validation_status="reviewer1_fail", validation_notes=None)])); signature = _task5_primitive_signature(projection); assert len(signature) == 1 and signature[0][1] == 2


def test_task5_primitive_duplicate_legacy_ids_fail_closed() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("legacy-dup"), _task5_primitive("legacy-dup", end_x=20)])
    with pytest.raises(sf.SourceFusionError): _task5_project_primitive(artifact)


def test_task5_artifact_checkpoint_and_task4_render_hash_are_not_observation_identity() -> None:
    first = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-old")]), artifact_sha256=PRIMITIVE_ARTIFACT_SHA256, bindings=_task5_source_bindings(PRIMITIVE_ARTIFACT_SHA256)); second = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-regenerated", handle=None, extracted_at=None)]), artifact_sha256=TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256, bindings=_task5_source_bindings(TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256)); assert _task5_primitive_signature(first) == _task5_primitive_signature(second)


def test_task5_semantic_identity_ignores_part_constraint_uuid_and_order() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a"), _task5_primitive("prim-b", end_x=20)])); first = _task5_semantic_artifact(primitive_ids=["prim-a", "prim-b"], primitive_count=2, part_id="part-old", constraint_id="constraint-old"); second = _task5_semantic_artifact(primitive_ids=["prim-a", "prim-b"], primitive_count=2, part_id="part-regenerated", constraint_id="constraint-regenerated", reverse_membership=True); second["parts"] = list(reversed(second["parts"])); second["constraints"] = list(reversed(second["constraints"])); assert _task5_semantic_signature(_task5_project_semantic(first, primitive_projection)) == _task5_semantic_signature(_task5_project_semantic(second, primitive_projection))


def test_task5_semantic_membership_maps_to_primitive_observation_keys() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); primitive_key = _task5_primitive_signature(primitive_projection)[0][0]; semantic = _task5_project_semantic(_task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1), primitive_projection); assert _task5_semantic_signature(semantic)[0][1] == (primitive_key,)


def test_task5_semantic_proper_subset_of_duplicate_class_fails_exact_ambiguity_code() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("dup-a"), _task5_primitive("dup-b", handle=None)])); semantic = _task5_semantic_artifact(primitive_ids=["dup-a"], primitive_count=2)
    with pytest.raises(sf.SourceFusionError, match=r"^DUPLICATE_OBSERVATION_AMBIGUITY$"): _task5_project_semantic(semantic, primitive_projection)


def test_task5_semantic_complete_duplicate_class_is_deterministic() -> None:
    first_primitives = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("dup-a"), _task5_primitive("dup-b", handle=None)])); second_primitives = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("regen-b", handle="changed", extracted_at=None), _task5_primitive("regen-a", handle=None, extracted_at="2099-01-01T00:00:00Z")])); first_semantic = _task5_semantic_artifact(primitive_ids=["dup-a", "dup-b"], primitive_count=2); second_semantic = _task5_semantic_artifact(primitive_ids=["regen-b", "regen-a"], primitive_count=2, part_id="new-part-id", reverse_membership=True); assert _task5_semantic_signature(_task5_project_semantic(first_semantic, first_primitives)) == _task5_semantic_signature(_task5_project_semantic(second_semantic, second_primitives))


def test_task5_semantic_missing_primitive_reference_fails_closed() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); semantic = _task5_semantic_artifact(primitive_ids=["missing-legacy-id"], primitive_count=1)
    with pytest.raises(sf.SourceFusionError): _task5_project_semantic(semantic, primitive_projection)


def test_task5_primitive_ir_ref_allows_optional_sha_absent() -> None:
    primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); semantic = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1, primitive_sha256=None); _task5_project_semantic(semantic, primitive_projection)


def test_task5_primitive_ir_ref_optional_sha_must_equal_external_checkpoint() -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); matching = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1, primitive_sha256=PRIMITIVE_ARTIFACT_SHA256); _task5_project_semantic(matching, primitive_projection); mismatch = copy.deepcopy(matching); mismatch["primitive_ir_ref"]["sha256"] = TASK5_OTHER_PRIMITIVE_ARTIFACT_SHA256
    with pytest.raises(sf.SourceFusionError): _task5_project_semantic(mismatch, primitive_projection)


@pytest.mark.parametrize("field,value", [("file_name", "wrong-name.json"), ("primitive_count", 2)])
def test_task5_primitive_ir_ref_wrong_filename_or_total_multiplicity_blocks(field: str, value: object) -> None:
    sf = _sf(); primitive_projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); semantic = _task5_semantic_artifact(primitive_ids=["prim-a"], primitive_count=1); semantic["primitive_ir_ref"][field] = value
    with pytest.raises(sf.SourceFusionError): _task5_project_semantic(semantic, primitive_projection)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_task5_projection_rejects_nonfinite_numeric_evidence(bad: float) -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["primitives"][0]["confidence"] = bad
    with pytest.raises(sf.SourceFusionError): _task5_project_primitive(artifact)


def test_task5_projection_rejects_noncanonical_numeric_evidence() -> None:
    sf = _sf(); artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["primitives"][0]["geometry"]["end"]["x"] = object()
    with pytest.raises(sf.SourceFusionError): _task5_project_primitive(artifact)


def test_task5_projection_replay_and_permutation_are_deterministic() -> None:
    primitives = [_task5_primitive("prim-a"), _task5_primitive("prim-b", end_x=20), _task5_primitive("prim-c", end_x=30)]; first_artifact = _task5_primitive_artifact(primitives); second_artifact = _task5_primitive_artifact(list(reversed(primitives))); first = _task5_project_primitive(copy.deepcopy(first_artifact)); second = _task5_project_primitive(copy.deepcopy(second_artifact)); assert _task5_primitive_signature(first) == _task5_primitive_signature(second) == _task5_primitive_signature(_task5_project_primitive(copy.deepcopy(first_artifact)))


def test_task5_projection_errors_are_privacy_safe() -> None:
    sf = _sf(); sentinel = r"C:\TOP-SECRET-CUSTOMER\primitive.json"; artifact = _task5_primitive_artifact([_task5_primitive("prim-a")]); artifact["source_document"]["file_name"] = sentinel; artifact["primitives"][0]["confidence"] = float("nan")
    with pytest.raises(sf.SourceFusionError) as exc_info: _task5_project_primitive(artifact)
    assert sentinel not in str(exc_info.value) and "TOP-SECRET-CUSTOMER" not in str(exc_info.value)


def test_task5_cross_platform_canonical_digest_fixture_uses_existing_hash_owner() -> None:
    expected_material = {"identity_kind": "r1c-task5-projection-fixture-v1", "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION, "source_id": _IMAGE_SOURCE_ID, "content": {"kind": "line", "confidence": "0.875", "start_mm": ["0", "0"], "end_mm": ["10", "0"]}}
    assert canonical_json_sha256(expected_material) == "13d2345542af34cf371e0cf99b4d89dcf45ed2b3e3f2f6facef4cbcb3dba2ac2"; projection = _task5_project_primitive(_task5_primitive_artifact([_task5_primitive("prim-a")])); assert _task5_primitive_signature(projection)[0][0] == canonical_json_sha256(expected_material)


def test_task5_static_no_second_owner_gates_cover_projection_dependencies() -> None:
    _sf(); tree = ast.parse(SOURCE_FUSION_FILE.read_text(encoding="utf-8")); forbidden = {"hashlib", "json", "uuid", "random", "datetime", "time", "os", "pathlib", "subprocess", "requests", "socket", "urllib", "http", "tempfile", "glob", "shutil", "sqlite3", "PIL", "pypdf", "fitz", "cv2", "pytesseract", "primitive_ir_lib", "semantic_ir_lib", "agent_lib", "autocad_plugin", "mcp_integration_lib"}; roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: roots.add(node.module.split(".")[0])
    assert roots.isdisjoint(forbidden); calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}; assert {"open", "__import__", "round", "hash"}.isdisjoint(calls)
