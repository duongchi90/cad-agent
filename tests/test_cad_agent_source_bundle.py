from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_bundle import (
    SOURCE_BUNDLE_SCHEMA_VERSION,
    SourceBundleError,
    build_source_bundle,
    source_bundle_sha256,
    validate_source_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "source-bundle.json"
SOURCE_MODULE = Path(__file__).parents[1] / "cad_agent" / "source_bundle.py"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_round_trip_is_deterministic() -> None:
    payload = _fixture()
    normalized = validate_source_bundle(payload)
    assert normalized == payload
    assert normalized is not payload
    assert source_bundle_sha256(payload) == canonical_json_sha256(normalized)


def test_builder_normalizes_item_and_reference_order() -> None:
    payload = _fixture()
    items = list(reversed(payload["items"]))
    items[1]["page_ids"] = ["PAGE-003", "PAGE-002", "PAGE-003"]
    items[1]["region_ids"] = ["REGION-DETAIL-A", "REGION-DETAIL-A"]

    built = build_source_bundle(
        bundle_id=payload["bundle_id"],
        run_id=payload["run_id"],
        created_at_utc=payload["created_at_utc"],
        items=items,
    )

    assert built["schema_version"] == SOURCE_BUNDLE_SCHEMA_VERSION
    assert [item["source_id"] for item in built["items"]] == [
        "BASE-CAD-001",
        "DETAIL-PDF-001",
        "ENGINEER-DECISION-001",
    ]
    assert built["items"][1]["page_ids"] == ["PAGE-002", "PAGE-003"]
    assert built["items"][1]["region_ids"] == ["REGION-DETAIL-A"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.__setitem__("unexpected", True), "unsupported"),
        (lambda value: value.__setitem__("schema_version", "source-bundle-2.0"), "schema_version"),
        (lambda value: value.__setitem__("bundle_id", "bad id"), "bundle_id"),
        (lambda value: value.__setitem__("created_at_utc", "2026-08-05T07:30:00+00:00"), "created_at_utc"),
        (lambda value: value.__setitem__("items", []), "items"),
        (lambda value: value.__setitem__("approved", True), "unsupported"),
    ],
)
def test_root_refusals(mutate, match: str) -> None:
    payload = _fixture()
    mutate(payload)
    with pytest.raises(SourceBundleError, match=match):
        validate_source_bundle(payload)


@pytest.mark.parametrize("field", ["schema_version", "bundle_id", "run_id", "created_at_utc", "items"])
def test_missing_root_fields_are_rejected(field: str) -> None:
    payload = _fixture()
    del payload[field]
    with pytest.raises(SourceBundleError, match=field):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("relative_path", "C:/private/base.dwg", "relative_path"),
        ("relative_path", "/private/base.dwg", "relative_path"),
        ("relative_path", "sources//base.dwg", "relative_path"),
        ("relative_path", "sources/./base.dwg", "relative_path"),
        ("relative_path", "../base.dwg", "relative_path"),
        ("relative_path", "sources\\base\\original.dwg", "relative_path"),
        ("sha256", "A" * 64, "sha256"),
        ("captured_at_utc", "not-a-time", "captured_at_utc"),
        ("verdict", "PASS", "unsupported"),
        ("entity_handles", ["2F"], "unsupported"),
    ],
)
def test_item_refusals(field: str, value: object, match: str) -> None:
    payload = _fixture()
    payload["items"][0][field] = value
    with pytest.raises(SourceBundleError, match=match):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("source_id", "", "source_id"),
        ("source_id", "bad id", "source_id"),
        ("kind", "IMAGE", "kind"),
        ("role", "DETAIL", "role"),
        ("media_type", "", "media_type"),
        ("page_ids", "PAGE-001", "page_ids"),
        ("region_ids", ["REGION A"], "region_ids"),
        ("quality", {"distortion": "NONE"}, "quality"),
    ],
)
def test_item_shape_refusals(field: str, value: object, match: str) -> None:
    payload = _fixture()
    payload["items"][0][field] = value
    with pytest.raises(SourceBundleError, match=match):
        validate_source_bundle(payload)


def test_missing_item_field_is_rejected() -> None:
    payload = _fixture()
    del payload["items"][0]["quality"]
    with pytest.raises(SourceBundleError, match="quality"):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    "field",
    [
        "authoritative",
        "approved",
        "approval",
        "verdict",
        "pass",
        "repair",
        "publication",
        "entity_handles",
        "model_space",
    ],
)
def test_authority_fields_are_rejected(field: str) -> None:
    payload = _fixture()
    payload["items"][0][field] = True
    with pytest.raises(SourceBundleError, match="unsupported"):
        validate_source_bundle(payload)


def test_unhashable_values_fail_closed() -> None:
    payload = _fixture()
    payload["items"][0]["kind"] = []
    with pytest.raises(SourceBundleError, match="kind"):
        validate_source_bundle(payload)

    payload = _fixture()
    payload["items"][0]["quality"]["distortion"] = []
    with pytest.raises(SourceBundleError, match="distortion"):
        validate_source_bundle(payload)


def test_duplicate_source_id_is_rejected() -> None:
    payload = _fixture()
    payload["items"][1]["source_id"] = payload["items"][0]["source_id"]
    with pytest.raises(SourceBundleError, match="source_id"):
        validate_source_bundle(payload)


def test_duplicate_relative_path_is_rejected() -> None:
    payload = _fixture()
    payload["items"][1]["relative_path"] = payload["items"][0]["relative_path"]
    with pytest.raises(SourceBundleError, match="relative_path"):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    ("quality_field", "value"),
    [("distortion", "BAD"), ("legibility", "BAD")],
)
def test_invalid_quality_values_are_rejected(quality_field: str, value: str) -> None:
    payload = _fixture()
    payload["items"][0]["quality"][quality_field] = value
    with pytest.raises(SourceBundleError, match=quality_field):
        validate_source_bundle(payload)


def test_more_than_ten_thousand_items_is_rejected() -> None:
    payload = _fixture()
    template = copy.deepcopy(payload["items"][0])
    payload["items"] = [
        {**copy.deepcopy(template), "source_id": f"BASE-{index:05d}"}
        for index in range(10_001)
    ]
    with pytest.raises(SourceBundleError, match="items"):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    ("kind", "role", "media_type", "page_ids"),
    [
        ("EXACT_BASE_CAD", "DETAIL", "application/acad", []),
        ("EXACT_BASE_CAD", "BASE_CAD", "application/pdf", []),
        ("IMAGE", "MEASUREMENT", "image/png", []),
        ("IMAGE", "DETAIL", "application/pdf", []),
        ("PDF", "DETAIL", "application/pdf", []),
        ("ENGINEER_RECORD", "OVERALL", "application/json", []),
        ("ENGINEER_RECORD", "DECISION", "image/png", []),
    ],
)
def test_kind_role_media_combinations_fail_closed(
    kind: str,
    role: str,
    media_type: str,
    page_ids: list[str],
) -> None:
    payload = _fixture()
    item = payload["items"][0]
    item.update(
        kind=kind,
        role=role,
        media_type=media_type,
        page_ids=page_ids,
    )
    with pytest.raises(SourceBundleError):
        validate_source_bundle(payload)


def test_pdf_requires_page_ids() -> None:
    payload = _fixture()
    item = payload["items"][0]
    item.update(
        kind="PDF",
        role="DETAIL",
        media_type="application/pdf",
        relative_path="sources/details/detail.pdf",
    )
    with pytest.raises(SourceBundleError, match="page_ids"):
        validate_source_bundle(payload)


def test_non_pdf_rejects_page_ids() -> None:
    payload = _fixture()
    payload["items"][0]["page_ids"] = ["PAGE-001"]
    with pytest.raises(SourceBundleError, match="page_ids"):
        validate_source_bundle(payload)


def test_exact_base_cad_allows_dxf_media() -> None:
    payload = _fixture()
    payload["items"][0]["media_type"] = "application/dxf"
    assert validate_source_bundle(payload)["items"][0]["media_type"] == "application/dxf"


@pytest.mark.parametrize(
    "identifier",
    ["PAGE 001", "PAGE\t001", "PAGE\n001", "PAGE/001", "PAGE\\001"],
)
def test_page_and_region_identifiers_reject_whitespace_and_controls(identifier: str) -> None:
    payload = _fixture()
    payload["items"][1]["page_ids"] = [identifier]
    with pytest.raises(SourceBundleError, match="page_ids"):
        validate_source_bundle(payload)

    payload = _fixture()
    payload["items"][1]["region_ids"] = [identifier]
    with pytest.raises(SourceBundleError, match="region_ids"):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-05T07:30:00+00:00",
        "2026-08-05T07:30:00.1234567Z",
        "2026-08-05T07:30:60Z",
    ],
)
def test_timestamps_require_strict_utc_z_form(timestamp: str) -> None:
    payload = _fixture()
    payload["created_at_utc"] = timestamp
    with pytest.raises(SourceBundleError, match="created_at_utc"):
        validate_source_bundle(payload)


def test_nested_unknown_quality_field_is_rejected() -> None:
    payload = _fixture()
    payload["items"][0]["quality"]["approved"] = True
    with pytest.raises(SourceBundleError, match="unsupported"):
        validate_source_bundle(payload)


def test_source_module_has_no_forbidden_or_runtime_integration_imports() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    forbidden = {
        "ctypes",
        "subprocess",
        "mcp_integration_lib",
        "autocad_plugin",
        "primitive_ir_lib",
        "semantic_ir_lib",
        "dxf_builder_lib",
        "agent_lib",
        "cad_agent.manifest",
        "cad_agent.cli",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {name for name in imported if any(name == item or name.startswith(f"{item}.") for item in forbidden)}


def test_source_module_contains_no_filesystem_or_process_calls() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    forbidden_calls = {"open", "read_text", "write_text", "run", "Popen", "system"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint(forbidden_calls)
