from __future__ import annotations

import ast
import copy
import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_integrity import (
    R1C_EXPIRY_POLICY_VERSION,
    R1C_NUMERIC_POLICY_VERSION,
    SOURCE_CUSTODY_SCHEMA_VERSION,
    SOURCE_FUSION_EVALUATION_SCHEMA_VERSION,
    SourceIntegrityError,
    canonicalize_r1c_quantity,
    r1c_quantity_within_tolerance,
    source_custody_sha256,
    source_fusion_evaluation_sha256,
    validate_source_custody,
    validate_source_fusion_evaluation,
)


SOURCE_MODULE = Path(__file__).parents[1] / "cad_agent" / "source_integrity.py"


@pytest.mark.parametrize(
    ("value", "quantity", "unit", "expected_unit", "expected_value"),
    [
        (1, "physical_length", "mm", "mm", "1"),
        (1.0, "physical_length", "mm", "mm", "1"),
        (Decimal("1.00"), "physical_length", "mm", "mm", "1"),
        ("-0.0004", "physical_length", "mm", "mm", "0"),
        ("25.4", "physical_length", "mm", "mm", "25.4"),
        (1, "physical_length", "in", "mm", "25.4"),
        ("2.3455", "physical_length", "mm", "mm", "2.346"),
        ("2.3445", "physical_length", "mm", "mm", "2.344"),
        (1, "pdf_coordinate", "in", "pt", "72"),
        ("2.54", "pdf_coordinate", "cm", "pt", "72"),
        (7, "pixel_dimension", "px", "px", "7"),
        ("90.0000005", "angle", "degree", "degree", "90"),
        ("0.5000005", "confidence", "unitless", "unitless", "0.5"),
        ("300.0005", "dpi", "dpi", "dpi", "300"),
        ("1.0000000005", "render_matrix", "unitless", "unitless", "1"),
        ("0.1250000005", "scale", "ratio", "ratio", "0.125"),
    ],
)
def test_r1c_quantity_canonicalization_is_closed_and_fixed_point(
    value: object,
    quantity: str,
    unit: str,
    expected_unit: str,
    expected_value: str,
) -> None:
    assert canonicalize_r1c_quantity(value, quantity=quantity, unit=unit) == {
        "policy_version": R1C_NUMERIC_POLICY_VERSION,
        "quantity": quantity,
        "unit": expected_unit,
        "value": expected_value,
    }


@pytest.mark.parametrize(
    ("value", "quantity", "unit"),
    [
        (float("nan"), "physical_length", "mm"),
        (float("inf"), "physical_length", "mm"),
        (Decimal("-Infinity"), "physical_length", "mm"),
        (True, "physical_length", "mm"),
        ("not-a-number", "physical_length", "mm"),
        ("1", "physical_length", "yards"),
        ("1", "unknown_quantity", "mm"),
        ("1", "pixel_dimension", "px_per_mm"),
    ],
)
def test_r1c_quantity_rejects_nonfinite_boolean_and_unsupported_inputs(
    value: object, quantity: str, unit: str
) -> None:
    with pytest.raises(SourceIntegrityError):
        canonicalize_r1c_quantity(value, quantity=quantity, unit=unit)


@pytest.mark.parametrize(
    ("quantity", "unit", "value"),
    [
        ("physical_length", "mm", "1000000000.001"),
        ("physical_length", "mm", "-1000000000.001"),
        ("pdf_coordinate", "pt", "1000000000.001"),
        ("pixel_coordinate", "px", "2147483648"),
        ("pixel_coordinate", "px", "-1"),
        ("angle", "degree", "360000.000001"),
        ("confidence", "unitless", "1.000001"),
        ("confidence", "unitless", "-0.000001"),
        ("dpi", "dpi", "0.000"),
        ("dpi", "dpi", "1000000.001"),
        ("render_matrix", "unitless", "1000000000.000000001"),
        ("scale", "ratio", "-1000000000.000000001"),
    ],
)
def test_r1c_quantity_rejects_values_outside_closed_inclusive_ranges(
    quantity: str, unit: str, value: str
) -> None:
    with pytest.raises(SourceIntegrityError, match="range"):
        canonicalize_r1c_quantity(value, quantity=quantity, unit=unit)


def test_r1c_quantity_rejects_fractional_pixels_and_preserves_no_exponent_form() -> None:
    with pytest.raises(SourceIntegrityError, match="integer"):
        canonicalize_r1c_quantity(
            "1.5", quantity="pixel_coordinate", unit="px"
        )

    normalized = canonicalize_r1c_quantity(
        "1E+3", quantity="physical_length", unit="mm"
    )
    assert normalized["value"] == "1000"
    assert "e" not in normalized["value"].lower()


def test_r1c_quantity_equivalence_and_negative_zero_are_canonical() -> None:
    values = [
        canonicalize_r1c_quantity(value, quantity="physical_length", unit="mm")
        for value in (1, 1.0, Decimal("1"))
    ]
    assert values == [values[0], values[0], values[0]]
    assert canonicalize_r1c_quantity(
        "-0.000", quantity="physical_length", unit="mm"
    )["value"] == "0"


def test_tolerance_boundary_is_inclusive_and_classification_is_not_identity() -> None:
    assert r1c_quantity_within_tolerance(
        "10.000",
        left_unit="mm",
        right="10.005",
        right_unit="mm",
        tolerance="0.005",
        tolerance_unit="mm",
        quantity="physical_length",
        tolerance_policy_version="r1c-tolerance-v1",
    ) is True
    assert r1c_quantity_within_tolerance(
        "10.000",
        left_unit="mm",
        right="10.006",
        right_unit="mm",
        tolerance="0.005",
        tolerance_unit="mm",
        quantity="physical_length",
        tolerance_policy_version="r1c-tolerance-v1",
    ) is False

    left = canonicalize_r1c_quantity(
        "10.000", quantity="physical_length", unit="mm"
    )
    right = canonicalize_r1c_quantity(
        "10.005", quantity="physical_length", unit="mm"
    )
    assert canonical_json_sha256(left) != canonical_json_sha256(right)


def _valid_custody_payload() -> dict[str, object]:
    return {
        "schema_version": SOURCE_CUSTODY_SCHEMA_VERSION,
        "bundle_id": "BUNDLE-001",
        "run_id": "RUN-001",
        "source_bundle_sha256": "a" * 64,
        "approved_root_id": "ROOT-SYNTHETIC",
        "approved_root_revision": "ROOT-REV-1",
        "approved_root_configuration_sha256": "b" * 64,
        "identity_scheme": "HMAC-SHA-256",
        "identity_scheme_version": "r1c-file-identity-v1",
        "identity_key_revision": "KEY-REV-1",
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "status": "READY",
        "eligible_count": 1,
        "blocking_count": 0,
        "items": [
            {
                "source_id": "IMAGE-001",
                "kind": "IMAGE",
                "role": "DETAIL",
                "relative_path": "sources/detail.png",
                "declared_sha256": "c" * 64,
                "observed_sha256": "c" * 64,
                "size_bytes": 128,
                "declared_media_type": "image/png",
                "observed_media_type": "image/png",
                "media_metadata": {
                    "format": "PNG",
                    "width_px": 16,
                    "height_px": 16,
                    "mode": "RGB",
                    "dpi_x": None,
                    "dpi_y": None,
                },
                "page_ids": [],
                "region_ids": ["REGION-001"],
                "file_object_identity_token": "d" * 64,
                "path_binding_sha256": "e" * 64,
                "identity_scheme": "HMAC-SHA-256",
                "identity_scheme_version": "r1c-file-identity-v1",
                "identity_key_revision": "KEY-REV-1",
                "approved_root_revision": "ROOT-REV-1",
                "alias_group_id": None,
                "custody_state": "VERIFIED",
                "blocking_reason_code": None,
            }
        ],
        "alias_groups": [],
    }


def test_custody_candidate_is_closed_normalized_and_not_real_byte_authority() -> None:
    payload = _valid_custody_payload()
    original = copy.deepcopy(payload)
    normalized = validate_source_custody(payload)

    assert normalized == original
    assert normalized is not payload
    assert normalized["status"] == "READY"
    assert "real_bytes_verified" not in normalized
    payload["items"][0]["region_ids"].append("REGION-002")
    assert normalized["items"][0]["region_ids"] == ["REGION-001"]


def test_custody_normalizes_items_and_identity_collections_deterministically() -> None:
    payload = _valid_custody_payload()
    item = copy.deepcopy(payload["items"][0])
    item["source_id"] = "IMAGE-002"
    item["relative_path"] = "sources/other.png"
    item["region_ids"] = ["REGION-002", "REGION-001", "REGION-002"]
    payload["items"].append(item)
    payload["eligible_count"] = 2

    reversed_payload = copy.deepcopy(payload)
    reversed_payload["items"] = list(reversed(reversed_payload["items"]))
    normalized = validate_source_custody(payload)
    reversed_normalized = validate_source_custody(reversed_payload)

    assert normalized == reversed_normalized
    assert [item["source_id"] for item in normalized["items"]] == [
        "IMAGE-001",
        "IMAGE-002",
    ]
    assert normalized["items"][1]["region_ids"] == [
        "REGION-001",
        "REGION-002",
    ]
    assert source_custody_sha256(payload) == source_custody_sha256(reversed_payload)


@pytest.mark.parametrize(
    "field",
    [
        "approved",
        "approval",
        "approval_reference",
        "authority",
        "engineering_pass",
        "visual_pass",
        "repair",
        "publication",
        "reusable",
        "verdict",
    ],
)
def test_custody_rejects_authority_fields(field: str) -> None:
    payload = _valid_custody_payload()
    payload[field] = True
    with pytest.raises(SourceIntegrityError, match="unsupported"):
        validate_source_custody(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("eligible_count", 0),
        ("blocking_count", 1),
        ("status", "BLOCKED"),
        ("schema_version", "source-custody-2.0"),
        ("source_bundle_sha256", "A" * 64),
    ],
)
def test_custody_count_status_and_version_invariants_fail_closed(
    field: str, value: object
) -> None:
    payload = _valid_custody_payload()
    payload[field] = value
    with pytest.raises(SourceIntegrityError):
        validate_source_custody(payload)


def test_custody_blocked_state_requires_sanitized_item_reason_and_counts() -> None:
    payload = _valid_custody_payload()
    item = payload["items"][0]
    item["custody_state"] = "HASH_MISMATCH"
    item["blocking_reason_code"] = "HASH_MISMATCH"
    payload["status"] = "BLOCKED"
    payload["eligible_count"] = 0
    payload["blocking_count"] = 1

    normalized = validate_source_custody(payload)
    assert normalized["status"] == "BLOCKED"
    assert normalized["items"][0]["blocking_reason_code"] == "HASH_MISMATCH"


def test_custody_hash_is_canonical_and_changes_with_contract_content() -> None:
    payload = _valid_custody_payload()
    same_content_different_order = copy.deepcopy(payload)
    same_content_different_order["items"] = list(
        reversed(same_content_different_order["items"])
    )
    assert source_custody_sha256(payload) == source_custody_sha256(
        same_content_different_order
    )

    changed = copy.deepcopy(payload)
    changed["approved_root_revision"] = "ROOT-REV-2"
    changed["items"][0]["approved_root_revision"] = "ROOT-REV-2"
    assert source_custody_sha256(payload) != source_custody_sha256(changed)


def _valid_evaluation_payload() -> dict[str, object]:
    return {
        "schema_version": SOURCE_FUSION_EVALUATION_SCHEMA_VERSION,
        "run_id": "RUN-001",
        "source_fusion_sha256": "f" * 64,
        "fusion_input_sha256": "1" * 64,
        "evaluation_time_utc": "2026-08-06T16:00:00.000000Z",
        "evaluation_time_source": "SERVER-CLOCK-EVIDENCE-1",
        "evaluation_time_evidence_sha256": "2" * 64,
        "expiry_policy_version": R1C_EXPIRY_POLICY_VERSION,
        "evaluated_reference_hashes": ["3" * 64],
        "status": "REUSABLE",
        "blocking_codes": [],
    }


def test_evaluation_candidate_is_closed_normalized_and_deterministic() -> None:
    payload = _valid_evaluation_payload()
    normalized = validate_source_fusion_evaluation(payload)
    assert normalized == payload
    assert normalized is not payload
    assert source_fusion_evaluation_sha256(payload) == source_fusion_evaluation_sha256(
        copy.deepcopy(payload)
    )

    reordered = copy.deepcopy(payload)
    reordered["evaluated_reference_hashes"] = ["4" * 64, "3" * 64, "4" * 64]
    normalized_reordered = validate_source_fusion_evaluation(reordered)
    assert normalized_reordered["evaluated_reference_hashes"] == [
        "3" * 64,
        "4" * 64,
    ]


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-06T16:00:00Z",
        "2026-08-06T16:00:00.000000+00:00",
        "2026-08-06T16:00:00.000Z",
        "2026-08-06T16:00:00.0000000Z",
        "2026-08-06 16:00:00.000000Z",
        "2026-08-06T16:00:60.000000Z",
    ],
)
def test_evaluation_rejects_noncanonical_or_invalid_utc_evidence(timestamp: str) -> None:
    payload = _valid_evaluation_payload()
    payload["evaluation_time_utc"] = timestamp
    with pytest.raises(SourceIntegrityError, match="evaluation_time_utc"):
        validate_source_fusion_evaluation(payload)


@pytest.mark.parametrize("field", ["approval", "verdict", "ready", "publication", "authority"])
def test_evaluation_rejects_authority_fields(field: str) -> None:
    payload = _valid_evaluation_payload()
    payload[field] = "PASS"
    with pytest.raises(SourceIntegrityError, match="unsupported"):
        validate_source_fusion_evaluation(payload)


def test_evaluation_status_and_reference_invariants_fail_closed() -> None:
    payload = _valid_evaluation_payload()
    payload["status"] = "REUSABLE"
    payload["blocking_codes"] = ["EXPIRED"]
    with pytest.raises(SourceIntegrityError):
        validate_source_fusion_evaluation(payload)

    payload = _valid_evaluation_payload()
    payload["status"] = "BLOCKED_EXPIRED"
    payload["blocking_codes"] = []
    with pytest.raises(SourceIntegrityError):
        validate_source_fusion_evaluation(payload)

    payload = _valid_evaluation_payload()
    payload["evaluated_reference_hashes"] = ["A" * 64]
    with pytest.raises(SourceIntegrityError):
        validate_source_fusion_evaluation(payload)


def test_evaluation_hash_changes_with_injected_evidence_not_ambient_time() -> None:
    payload = _valid_evaluation_payload()
    changed = copy.deepcopy(payload)
    changed["evaluation_time_evidence_sha256"] = "4" * 64
    assert source_fusion_evaluation_sha256(payload) != source_fusion_evaluation_sha256(
        changed
    )


def test_task1_module_has_no_filesystem_parser_model_or_clock_authority() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "os",
        "pathlib",
        "subprocess",
        "requests",
        "PIL",
        "pypdf",
        "ezdxf",
        "mcp_integration_lib",
        "autocad_plugin",
        "agent_lib",
        "primitive_ir_lib",
        "semantic_ir_lib",
        "dxf_builder_lib",
    }
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(forbidden_import_roots)

    forbidden_calls = {
        "now",
        "utcnow",
        "time",
        "open",
        "read_text",
        "write_text",
        "unlink",
        "replace",
        "remove",
        "run",
        "Popen",
        "system",
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(forbidden_calls)
    assert "datetime.now" not in inspect.getsource(__import__("cad_agent.source_integrity"))
