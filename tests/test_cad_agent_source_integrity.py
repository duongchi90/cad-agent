from __future__ import annotations

import ast
import base64
import copy
import decimal
import importlib
import inspect
import sys
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


def test_pdf_coordinate_conversion_is_invariant_to_preimport_decimal_precision() -> None:
    source_module = importlib.import_module("cad_agent.source_integrity")
    original_context = decimal.getcontext().copy()
    observations: list[tuple[dict[str, str], str]] = []
    try:
        for precision in (3, 6, 80):
            decimal.getcontext().prec = precision
            importlib.reload(source_module)
            normalized = source_module.canonicalize_r1c_quantity(
                "1", quantity="pdf_coordinate", unit="mm"
            )
            observations.append((normalized, canonical_json_sha256(normalized)))
    finally:
        decimal.setcontext(original_context)
        importlib.reload(source_module)
        globals()["SourceIntegrityError"] = source_module.SourceIntegrityError

    with decimal.localcontext() as exact_context:
        exact_context.prec = 80
        exact_points = Decimal("1") * Decimal(72) / Decimal("25.4")
        expected_value = format(
            exact_points.quantize(Decimal("0.001"), rounding=decimal.ROUND_HALF_EVEN),
            "f",
        )
    assert observations[0] == observations[1] == observations[2]
    assert observations[0][0]["value"] == expected_value


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


def _alias_group_payload(group_type: str) -> dict[str, object]:
    payload = _valid_custody_payload()
    first = copy.deepcopy(payload["items"][0])
    second = copy.deepcopy(first)
    second.update(
        {
            "source_id": "IMAGE-002",
            "relative_path": "sources/other.png",
            "file_object_identity_token": "f" * 64,
            "path_binding_sha256": "1" * 64,
        }
    )
    first["alias_group_id"] = "GROUP-001"
    second["alias_group_id"] = "GROUP-001"
    if group_type == "SAME_FILE_ALIAS":
        first.update(
            {
                "custody_state": "SAME_FILE_ALIAS",
                "blocking_reason_code": "SAME_FILE_ALIAS",
            }
        )
        second.update(
            {
                "custody_state": "SAME_FILE_ALIAS",
                "blocking_reason_code": "SAME_FILE_ALIAS",
            }
        )
        tokens = ["d" * 64]
        status = "BLOCKED"
        eligible_count = 0
        blocking_count = 2
        second["file_object_identity_token"] = "d" * 64
    else:
        first.update(
            {"custody_state": "DUPLICATE_BYTES", "blocking_reason_code": None}
        )
        second.update(
            {"custody_state": "DUPLICATE_BYTES", "blocking_reason_code": None}
        )
        tokens = ["d" * 64, "f" * 64]
        status = "READY"
        eligible_count = 2
        blocking_count = 0
    payload.update(
        {
            "status": status,
            "eligible_count": eligible_count,
            "blocking_count": blocking_count,
            "items": [first, second],
            "alias_groups": [
                {
                    "alias_group_id": "GROUP-001",
                    "group_type": group_type,
                    "source_ids": ["IMAGE-001", "IMAGE-002"],
                    "observed_sha256": "c" * 64,
                    "file_object_identity_tokens": tokens,
                    "path_bindings": ["1" * 64, "e" * 64],
                }
            ],
        }
    )
    return payload


def test_same_file_alias_blocks_even_when_items_claim_verified() -> None:
    payload = _alias_group_payload("SAME_FILE_ALIAS")
    for item in payload["items"]:
        item["custody_state"] = "VERIFIED"
        item["blocking_reason_code"] = None
    payload["status"] = "READY"
    payload["eligible_count"] = 2
    payload["blocking_count"] = 0

    with pytest.raises(SourceIntegrityError, match="alias|SAME_FILE_ALIAS|blocking"):
        validate_source_custody(payload)


def test_same_file_alias_members_are_explicitly_blocked() -> None:
    normalized = validate_source_custody(_alias_group_payload("SAME_FILE_ALIAS"))

    assert normalized["status"] == "BLOCKED"
    assert normalized["blocking_count"] == 2
    assert all(
        item["custody_state"] == "SAME_FILE_ALIAS"
        for item in normalized["items"]
    )


def test_duplicate_bytes_requires_a_complete_independent_object_explanation() -> None:
    normalized = validate_source_custody(_alias_group_payload("DUPLICATE_BYTES"))

    assert normalized["status"] == "READY"
    assert normalized["eligible_count"] == 2
    assert normalized["alias_groups"][0]["group_type"] == "DUPLICATE_BYTES"


def test_duplicate_bytes_without_a_matching_group_is_not_eligible() -> None:
    payload = _alias_group_payload("DUPLICATE_BYTES")
    for item in payload["items"]:
        item["alias_group_id"] = None
    payload["alias_groups"] = []

    with pytest.raises(SourceIntegrityError, match="alias_group|duplicate|explanation"):
        validate_source_custody(payload)


def test_item_group_membership_must_be_bidirectional() -> None:
    payload = _alias_group_payload("DUPLICATE_BYTES")
    third = copy.deepcopy(payload["items"][1])
    third.update(
        {
            "source_id": "IMAGE-003",
            "relative_path": "sources/third.png",
            "file_object_identity_token": "0" * 64,
            "path_binding_sha256": "2" * 64,
            "alias_group_id": None,
        }
    )
    payload["items"].append(third)
    payload["alias_groups"][0]["source_ids"] = ["IMAGE-002", "IMAGE-003"]
    payload["alias_groups"][0]["file_object_identity_tokens"] = [
        "0" * 64,
        "f" * 64,
    ]
    payload["alias_groups"][0]["path_bindings"] = ["1" * 64, "2" * 64]
    payload["eligible_count"] = 3

    with pytest.raises(SourceIntegrityError, match="member|source_ids|alias_group"):
        validate_source_custody(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observed_sha256", "b" * 64),
        ("file_object_identity_tokens", ["d" * 64, "0" * 64]),
        ("path_bindings", ["e" * 64, "0" * 64]),
    ],
)
def test_duplicate_bytes_group_must_match_member_identities(
    field: str, value: object
) -> None:
    payload = _alias_group_payload("DUPLICATE_BYTES")
    payload["alias_groups"][0][field] = value

    with pytest.raises(SourceIntegrityError, match="group|member|duplicate|match"):
        validate_source_custody(payload)


def test_duplicate_bytes_group_type_must_match_member_states() -> None:
    payload = _alias_group_payload("DUPLICATE_BYTES")
    for item in payload["items"]:
        item["custody_state"] = "VERIFIED"

    with pytest.raises(SourceIntegrityError, match="group|DUPLICATE_BYTES|state"):
        validate_source_custody(payload)


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
    source_module = importlib.import_module("cad_agent.source_integrity")
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

    def call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = call_name(node.value)
            return f"{prefix}.{node.attr}"
        return ""

    called_names = {
        call_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert called_names.isdisjoint(forbidden_calls)
    forbidden_clock_calls = {
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "_datetime.datetime.now",
        "_datetime.datetime.utcnow",
    }
    assert called_names.isdisjoint(forbidden_clock_calls)
    for expression, expected_call in (
        ("datetime.now()", "datetime.now"),
        ("_datetime.datetime.utcnow()", "_datetime.datetime.utcnow"),
        ("time.time()", "time.time"),
    ):
        synthetic_calls = {
            call_name(node.func)
            for node in ast.walk(ast.parse(expression))
            if isinstance(node, ast.Call)
        }
        assert expected_call in synthetic_calls
    assert "cad_agent.source_integrity" in source_module.__name__
    assert "datetime.now" not in inspect.getsource(source_module)


def test_tolerance_classification_is_invariant_to_ambient_decimal_precision() -> None:
    original_context = decimal.getcontext().copy()
    observations: list[bool] = []
    try:
        for precision in (3, 6, 12, 28):
            decimal.getcontext().prec = precision
            observations.append(
                r1c_quantity_within_tolerance(
                    "1000000000",
                    left_unit="mm",
                    right="0.001",
                    right_unit="mm",
                    tolerance="999999999.999",
                    tolerance_unit="mm",
                    quantity="physical_length",
                    tolerance_policy_version="r1c-tolerance-v1",
                )
            )
    finally:
        decimal.setcontext(original_context)

    assert observations == [True, True, True, True]


@pytest.mark.parametrize(
    "field",
    [
        "observed_sha256",
        "file_object_identity_token",
        "path_binding_sha256",
        "observed_media_type",
    ],
)
def test_verified_ready_requires_complete_observed_identity_evidence(field: str) -> None:
    payload = _valid_custody_payload()
    payload["items"][0][field] = None

    with pytest.raises(SourceIntegrityError, match="VERIFIED|eligible|observed|identity|path|media"):
        validate_source_custody(payload)


def test_verified_ready_rejects_declared_observed_sha_mismatch() -> None:
    payload = _valid_custody_payload()
    payload["items"][0]["observed_sha256"] = "f" * 64

    with pytest.raises(SourceIntegrityError, match="hash|SHA|declared|observed|VERIFIED"):
        validate_source_custody(payload)


def test_verified_ready_rejects_declared_observed_media_mismatch() -> None:
    payload = _valid_custody_payload()
    payload["items"][0]["observed_media_type"] = "image/jpeg"

    with pytest.raises(SourceIntegrityError, match="media|declared|observed|VERIFIED"):
        validate_source_custody(payload)


def test_alias_group_members_require_distinct_path_bindings() -> None:
    payload = _alias_group_payload("DUPLICATE_BYTES")
    shared_binding = payload["items"][0]["path_binding_sha256"]
    payload["items"][1]["path_binding_sha256"] = shared_binding
    payload["alias_groups"][0]["path_bindings"] = [shared_binding]

    with pytest.raises(SourceIntegrityError, match="path|binding|distinct|member"):
        validate_source_custody(payload)


# --- R1C Task 2: server-keyed opened-handle source-byte custody ---

import hashlib
import cad_agent.source_integrity as _source_integrity_task2


_TASK2_LIMITS = {
    "max_items": 10000,
    "max_total_bytes": 1024 * 1024,
    "max_file_bytes": 1024 * 1024,
    "hash_chunk_size": 3,
    "max_final_path_chars": 32768,
}
_TASK2_KEY = b"server-owned-test-key-32-bytes!!"
_TASK2_ROOT = Path("C:/approved")
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zf5sAAAAASUVORK5CYII="
)
_PNG_1X1_METADATA = {
    "format": "PNG",
    "width_px": 1,
    "height_px": 1,
    "mode": "LA",
    "dpi_x": None,
    "dpi_y": None,
}


def _task2_item(source_id: str, relative_path: str, data: bytes) -> dict[str, object]:
    return {
        "source_id": source_id,
        "kind": "IMAGE",
        "role": "DETAIL",
        "relative_path": relative_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "media_type": "image/png",
        "page_ids": [],
        "region_ids": [f"REGION-{source_id}"],
        "captured_at_utc": "2026-08-07T12:00:00Z",
        "quality": {"distortion": "NONE", "legibility": "GOOD"},
    }


def _task2_bundle(*items: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "source-bundle-1.0",
        "bundle_id": "BUNDLE-TASK2",
        "run_id": "RUN-TASK2",
        "created_at_utc": "2026-08-07T12:00:00Z",
        "items": list(items),
    }


def _fake_file_id(value: int) -> bytes:
    return value.to_bytes(16, "big")


class _FakeHandle:
    def __init__(self, adapter: "_FakeCustodyAdapter", key: str, *, reopen: bool = False) -> None:
        self.adapter = adapter
        self.key = key
        self.reopen = reopen
        self.snapshot_count = 0
        self.offset = 0

    def __enter__(self) -> "_FakeHandle":
        if self.key != "<root>" and not self.reopen:
            self.adapter.custody_open += 1
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.key != "<root>" and not self.reopen:
            self.adapter.custody_open -= 1
        return None


class _FakeCustodyAdapter:
    def __init__(
        self,
        files: dict[str, dict[str, object]],
        *,
        root_final_path: str = r"C:\approved",
        root_identity: tuple[int, int] = (101, 202),
        after_overrides: dict[str, dict[str, object]] | None = None,
        reopen_overrides: dict[str, dict[str, object]] | None = None,
        reparse_paths: set[str] | None = None,
        raw_error: Exception | None = None,
    ) -> None:
        self.files = files
        self.root_final_path = root_final_path
        self.root_identity = root_identity
        self.after_overrides = after_overrides or {}
        self.reopen_overrides = reopen_overrides or {}
        self.reparse_paths = reparse_paths or set()
        self.raw_error = raw_error
        self.read_counts: dict[str, int] = {}
        self.custody_open = 0

    def open_root(self, approved_root: Path, *, max_final_path_chars: int) -> _FakeHandle:
        return _FakeHandle(self, "<root>")

    def open_source(
        self,
        root_handle: _FakeHandle,
        relative_path: str,
        *,
        max_final_path_chars: int,
    ) -> _FakeHandle:
        return _FakeHandle(self, relative_path)

    def reopen_source(
        self,
        root_handle: _FakeHandle,
        relative_path: str,
        *,
        max_final_path_chars: int,
    ) -> _FakeHandle:
        if self.custody_open <= 0:
            raise SourceIntegrityError("UNGUARDED_REOPEN")
        return _FakeHandle(self, relative_path, reopen=True)

    def check_no_reparse(self, root_handle: _FakeHandle, relative_path: str) -> None:
        if relative_path in self.reparse_paths:
            raise SourceIntegrityError("REPARSE_POINT")

    def snapshot(self, handle: _FakeHandle, *, max_final_path_chars: int) -> dict[str, object]:
        if self.raw_error is not None:
            raise self.raw_error
        if handle.key == "<root>":
            return {
                "final_path": self.root_final_path,
                "volume_serial": self.root_identity[0],
                "file_id": _fake_file_id(self.root_identity[1]),
                "size": 0,
                "reparse": False,
            }
        base = dict(self.files[handle.key])
        if handle.reopen:
            base.update(self.reopen_overrides.get(handle.key, {}))
        elif handle.snapshot_count > 0:
            base.update(self.after_overrides.get(handle.key, {}))
        handle.snapshot_count += 1
        return {
            "final_path": base.get(
                "final_path",
                self.root_final_path + "\\" + handle.key.replace("/", "\\"),
            ),
            "volume_serial": base["volume_serial"],
            "file_id": base.get("file_id", _fake_file_id(int(base["file_index"]))),
            "size": len(base["data"]) if "size" not in base else base["size"],
            "reparse": bool(base.get("reparse", False)),
        }

    def rewind(self, handle: _FakeHandle) -> None:
        handle.offset = 0

    def read(self, handle: _FakeHandle, size: int) -> bytes:
        self.read_counts[handle.key] = self.read_counts.get(handle.key, 0) + 1
        data = bytes(self.files[handle.key]["data"])
        result = data[handle.offset : handle.offset + size]
        handle.offset += len(result)
        return result


def _fake_file(
    data: bytes,
    *,
    volume_serial: int,
    file_index: int,
    final_path: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "data": data,
        "volume_serial": volume_serial,
        "file_index": file_index,
    }
    if final_path is not None:
        value["final_path"] = final_path
    return value


def _task2_inspect(
    monkeypatch: pytest.MonkeyPatch,
    adapter: _FakeCustodyAdapter,
    bundle: dict[str, object],
    *,
    root_revision: str = "ROOT-REV-1",
    key: bytes = _TASK2_KEY,
    key_revision: str = "KEY-REV-1",
    policy_limits: dict[str, int] | None = None,
) -> dict[str, object]:
    assert hasattr(_source_integrity_task2, "inspect_source_bundle"), (
        "R1C Task 2 RED: inspect_source_bundle is not implemented"
    )
    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        lambda: adapter,
        raising=False,
    )
    return _source_integrity_task2.inspect_source_bundle(
        approved_root_id="ROOT-SYNTHETIC",
        approved_root_revision=root_revision,
        approved_root=_TASK2_ROOT,
        identity_key=key,
        identity_key_revision=key_revision,
        policy_limits=dict(_TASK2_LIMITS if policy_limits is None else policy_limits),
        source_bundle=bundle,
    )


def _truthful_downstream_custody_fixture(
    evidence: dict[str, object],
    *,
    observed_media_type: str,
    media_metadata: dict[str, object],
) -> dict[str, object]:
    """Build complete downstream custody from explicit parser facts, never Task-2 inference."""
    items = []
    groups = copy.deepcopy(evidence["alias_groups"])
    group_by_source: dict[str, tuple[str, str]] = {}
    for group in groups:
        for source_id in group["source_ids"]:
            group_by_source[str(source_id)] = (
                str(group["alias_group_id"]),
                str(group["group_type"]),
            )
    for observed in evidence["items"]:
        source_id = str(observed["source_id"])
        membership = group_by_source.get(source_id)
        group_type = membership[1] if membership else None
        state = group_type or "VERIFIED"
        blocking = "SAME_FILE_ALIAS" if state == "SAME_FILE_ALIAS" else None
        items.append(
            {
                "source_id": source_id,
                "kind": observed["kind"],
                "role": observed["role"],
                "relative_path": observed["relative_path"],
                "declared_sha256": observed["declared_sha256"],
                "observed_sha256": observed["observed_sha256"],
                "size_bytes": observed["size_bytes"],
                "declared_media_type": observed["declared_media_type"],
                "observed_media_type": observed_media_type,
                "media_metadata": copy.deepcopy(media_metadata),
                "page_ids": observed["page_ids"],
                "region_ids": observed["region_ids"],
                "file_object_identity_token": observed["file_object_identity_token"],
                "path_binding_sha256": observed["path_binding_sha256"],
                "identity_scheme": evidence["identity_scheme"],
                "identity_scheme_version": evidence["identity_scheme_version"],
                "identity_key_revision": evidence["identity_key_revision"],
                "approved_root_revision": evidence["approved_root_revision"],
                "alias_group_id": membership[0] if membership else None,
                "custody_state": state,
                "blocking_reason_code": blocking,
            }
        )
    blocking_count = sum(item["custody_state"] == "SAME_FILE_ALIAS" for item in items)
    return {
        "schema_version": SOURCE_CUSTODY_SCHEMA_VERSION,
        "bundle_id": evidence["bundle_id"],
        "run_id": evidence["run_id"],
        "source_bundle_sha256": evidence["source_bundle_sha256"],
        "approved_root_id": evidence["approved_root_id"],
        "approved_root_revision": evidence["approved_root_revision"],
        "approved_root_configuration_sha256": evidence[
            "approved_root_configuration_sha256"
        ],
        "identity_scheme": evidence["identity_scheme"],
        "identity_scheme_version": evidence["identity_scheme_version"],
        "identity_key_revision": evidence["identity_key_revision"],
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "status": "BLOCKED" if blocking_count else "READY",
        "eligible_count": len(items) - blocking_count,
        "blocking_count": blocking_count,
        "items": items,
        "alias_groups": groups,
    }


def _png_downstream_custody(evidence: dict[str, object]) -> dict[str, object]:
    return _truthful_downstream_custody_fixture(
        evidence,
        observed_media_type="image/png",
        media_metadata=_PNG_1X1_METADATA,
    )


def test_task2_hardlink_same_object_is_blocking_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"same-object"
    bundle = _task2_bundle(
        _task2_item("IMAGE-001", "sources/a.png", data),
        _task2_item("IMAGE-002", "sources/b.png", data),
    )
    adapter = _FakeCustodyAdapter(
        {
            "sources/a.png": _fake_file(data, volume_serial=7, file_index=99),
            "sources/b.png": _fake_file(data, volume_serial=7, file_index=99),
        }
    )
    evidence = _task2_inspect(monkeypatch, adapter, bundle)
    first, second = evidence["items"]
    assert first["file_object_identity_token"] == second["file_object_identity_token"]
    assert first["path_binding_sha256"] != second["path_binding_sha256"]
    assert {item["byte_custody_state"] for item in evidence["items"]} == {
        "SAME_FILE_ALIAS"
    }
    assert evidence["alias_groups"][0]["group_type"] == "SAME_FILE_ALIAS"


def test_task2_rename_keeps_object_token_but_changes_path_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"rename"
    old_bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/old.png", data))
    new_bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/new.png", data))
    old = _task2_inspect(
        monkeypatch,
        _FakeCustodyAdapter(
            {"sources/old.png": _fake_file(data, volume_serial=4, file_index=8)}
        ),
        old_bundle,
    )
    new = _task2_inspect(
        monkeypatch,
        _FakeCustodyAdapter(
            {"sources/new.png": _fake_file(data, volume_serial=4, file_index=8)}
        ),
        new_bundle,
    )
    assert old["items"][0]["file_object_identity_token"] == new["items"][0][
        "file_object_identity_token"
    ]
    assert old["items"][0]["path_binding_sha256"] != new["items"][0][
        "path_binding_sha256"
    ]


def test_task2_copy_equal_bytes_has_distinct_objects_and_duplicate_group(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"copied-bytes"
    bundle = _task2_bundle(
        _task2_item("IMAGE-001", "sources/a.png", data),
        _task2_item("IMAGE-002", "sources/b.png", data),
    )
    evidence = _task2_inspect(
        monkeypatch,
        _FakeCustodyAdapter(
            {
                "sources/a.png": _fake_file(data, volume_serial=7, file_index=10),
                "sources/b.png": _fake_file(data, volume_serial=7, file_index=11),
            }
        ),
        bundle,
    )
    assert len({item["observed_sha256"] for item in evidence["items"]}) == 1
    assert len({item["file_object_identity_token"] for item in evidence["items"]}) == 2
    assert {item["byte_custody_state"] for item in evidence["items"]} == {
        "DUPLICATE_BYTES"
    }
    assert evidence["alias_groups"][0]["group_type"] == "DUPLICATE_BYTES"


def test_task2_same_path_equal_byte_replacement_stales_prior_custody(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _PNG_1X1
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    initial_adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
    )
    initial = _task2_inspect(monkeypatch, initial_adapter, bundle)
    custody = _png_downstream_custody(initial)
    replacement_adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=11)}
    )
    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        lambda: replacement_adapter,
        raising=False,
    )
    with pytest.raises(SourceIntegrityError, match="CUSTODY_STALE|IDENTITY"):
        _source_integrity_task2.require_source_custody_match(
            approved_root_id="ROOT-SYNTHETIC",
            approved_root_revision="ROOT-REV-1",
            approved_root=_TASK2_ROOT,
            identity_key=_TASK2_KEY,
            identity_key_revision="KEY-REV-1",
            policy_limits=dict(_TASK2_LIMITS),
            source_bundle=bundle,
            custody=custody,
        )


@pytest.mark.parametrize(
    ("root_revision", "key_revision", "match"),
    [
        ("ROOT-REV-2", "KEY-REV-1", "ROOT|CUSTODY_STALE"),
        ("ROOT-REV-1", "KEY-REV-2", "KEY|CUSTODY_STALE"),
    ],
)
def test_task2_root_or_key_revision_drift_invalidates_custody(
    monkeypatch: pytest.MonkeyPatch,
    root_revision: str,
    key_revision: str,
    match: str,
) -> None:
    data = _PNG_1X1
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
    )
    initial = _task2_inspect(monkeypatch, adapter, bundle)
    custody = _png_downstream_custody(initial)
    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        lambda: adapter,
        raising=False,
    )
    with pytest.raises(SourceIntegrityError, match=match):
        _source_integrity_task2.require_source_custody_match(
            approved_root_id="ROOT-SYNTHETIC",
            approved_root_revision=root_revision,
            approved_root=_TASK2_ROOT,
            identity_key=_TASK2_KEY,
            identity_key_revision=key_revision,
            policy_limits=dict(_TASK2_LIMITS),
            source_bundle=bundle,
            custody=custody,
        )


def test_task2_hmac_domains_and_unrelated_keys_are_separate(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"domain"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
    )
    first = _task2_inspect(monkeypatch, adapter, bundle)
    second = _task2_inspect(monkeypatch, adapter, bundle, key=b"unrelated-server-key")
    item = first["items"][0]
    assert item["file_object_identity_token"] != item["path_binding_sha256"]
    assert item["file_object_identity_token"] != second["items"][0][
        "file_object_identity_token"
    ]
    assert item["path_binding_sha256"] != second["items"][0]["path_binding_sha256"]


def test_task2_artifacts_and_errors_do_not_expose_raw_identity_or_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"privacy"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=123456, file_index=987654)}
    )
    evidence = _task2_inspect(monkeypatch, adapter, bundle, key=b"TOP-SECRET-KEY")
    rendered = repr(evidence)
    assert r"C:\approved" not in rendered
    assert "123456" not in rendered
    assert "987654" not in rendered
    assert "TOP-SECRET-KEY" not in rendered
    assert "volume_serial" not in rendered
    assert "file_id" not in rendered

    raw = OSError(r"C:\secret\drawing.png volume=123456 handle=99 TOP-SECRET-KEY")
    bad_adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=1, file_index=2)},
        raw_error=raw,
    )
    with pytest.raises(SourceIntegrityError) as exc_info:
        _task2_inspect(monkeypatch, bad_adapter, bundle)
    message = str(exc_info.value)
    assert "secret" not in message.lower()
    assert "123456" not in message
    assert "TOP-SECRET-KEY" not in message


def test_task2_final_handle_outside_root_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"escape"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {
            "sources/a.png": _fake_file(
                data,
                volume_serial=7,
                file_index=10,
                final_path=r"C:\outside\a.png",
            )
        }
    )
    with pytest.raises(SourceIntegrityError, match="FINAL_PATH_OUTSIDE_ROOT"):
        _task2_inspect(monkeypatch, adapter, bundle)


def test_task2_reparse_evidence_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"reparse"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)},
        reparse_paths={"sources/a.png"},
    )
    with pytest.raises(SourceIntegrityError, match="REPARSE_POINT"):
        _task2_inspect(monkeypatch, adapter, bundle)


@pytest.mark.parametrize(
    "override",
    [
        {"file_index": 11},
        {"size": 999},
        {"final_path": r"C:\approved\sources\renamed.png"},
    ],
)
def test_task2_identity_path_or_size_change_during_read_fails_closed(
    monkeypatch: pytest.MonkeyPatch, override: dict[str, object]
) -> None:
    data = b"race"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)},
        after_overrides={"sources/a.png": override},
    )
    with pytest.raises(SourceIntegrityError, match="CHANGED_DURING_READ|IDENTITY_CHANGED"):
        _task2_inspect(monkeypatch, adapter, bundle)


def test_task2_final_reopen_detects_replacement_race(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"reopen-race"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)},
        reopen_overrides={"sources/a.png": {"file_index": 12}},
    )
    with pytest.raises(SourceIntegrityError, match="IDENTITY_CHANGED|REPLACED"):
        _task2_inspect(monkeypatch, adapter, bundle)


def test_task2_final_path_evidence_unavailable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"unavailable"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)},
        raw_error=OSError("GetFinalPathNameByHandleW failed raw=5"),
    )
    with pytest.raises(SourceIntegrityError, match="EVIDENCE_UNAVAILABLE"):
        _task2_inspect(monkeypatch, adapter, bundle)


def test_task2_unsupported_platform_has_no_path_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"unsupported"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))

    def unavailable() -> object:
        raise SourceIntegrityError("WINDOWS_HANDLE_EVIDENCE_UNAVAILABLE")

    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        unavailable,
        raising=False,
    )
    with pytest.raises(SourceIntegrityError, match="WINDOWS_HANDLE_EVIDENCE_UNAVAILABLE"):
        _source_integrity_task2.inspect_source_bundle(
            approved_root_id="ROOT-SYNTHETIC",
            approved_root_revision="ROOT-REV-1",
            approved_root=_TASK2_ROOT,
            identity_key=_TASK2_KEY,
            identity_key_revision="KEY-REV-1",
            policy_limits=dict(_TASK2_LIMITS),
            source_bundle=bundle,
        )


def test_task2_does_not_fabricate_media_or_ready_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"no-media-parser"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    evidence = _task2_inspect(
        monkeypatch,
        _FakeCustodyAdapter(
            {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
        ),
        bundle,
    )
    assert "status" not in evidence
    assert "observed_media_type" not in evidence["items"][0]
    assert "media_metadata" not in evidence["items"][0]
    assert evidence["items"][0]["byte_custody_state"] == "VERIFIED_BYTES"


def test_task2_policy_limits_are_closed_and_server_owned(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"limits"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
    )
    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        lambda: adapter,
        raising=False,
    )
    for bad_limits in (
        {},
        {**_TASK2_LIMITS, "unknown": 1},
        {**_TASK2_LIMITS, "hash_chunk_size": True},
        {**_TASK2_LIMITS, "max_file_bytes": -1},
    ):
        with pytest.raises(SourceIntegrityError, match="POLICY_LIMITS"):
            _source_integrity_task2.inspect_source_bundle(
                approved_root_id="ROOT-SYNTHETIC",
                approved_root_revision="ROOT-REV-1",
                approved_root=_TASK2_ROOT,
                identity_key=_TASK2_KEY,
                identity_key_revision="KEY-REV-1",
                policy_limits=bad_limits,
                source_bundle=bundle,
            )


# --- R1C Task 2 consolidated remediation matrix ---


def test_task2_win32_adapter_declares_explicit_abi_prototypes() -> None:
    source = inspect.getsource(_source_integrity_task2._WindowsHandleAdapter.__init__)
    for name in (
        "CreateFileW",
        "GetFileAttributesW",
        "GetFinalPathNameByHandleW",
        "GetFileInformationByHandle",
        "GetFileInformationByHandleEx",
        "SetFilePointerEx",
        "ReadFile",
        "CloseHandle",
    ):
        assert f"{name}.argtypes" in source, f"missing explicit argtypes for {name}"
        assert f"{name}.restype" in source, f"missing explicit restype for {name}"
    assert "CreateFileW.restype = wintypes.HANDLE" in source
    assert "GetFileAttributesW.restype = wintypes.DWORD" in source


def test_task2_win32_source_open_does_not_grant_write_share() -> None:
    source = inspect.getsource(_source_integrity_task2._WindowsHandleAdapter._create)
    assert "_FILE_SHARE_WRITE" not in source
    assert "_FILE_SHARE_READ | self._FILE_SHARE_DELETE" in source


def test_task2_uses_opened_handle_file_id_info_identity() -> None:
    source = inspect.getsource(_source_integrity_task2._WindowsHandleAdapter.snapshot)
    assert "GetFileInformationByHandleEx" in source
    assert "_FILE_ID_INFO_CLASS" in source
    assert "file_id" in source
    assert "nFileIndexHigh" not in source
    assert "nFileIndexLow" not in source


class _MutateAtHashBoundaryAdapter(_FakeCustodyAdapter):
    def __init__(self, *args: object, replacement: bytes, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.replacement = replacement
        self.mutated = False
        self.mutation_blocked = False

    def read(self, handle: _FakeHandle, size: int) -> bytes:
        result = super().read(handle, size)
        if not result and handle.key != "<root>" and not self.mutated:
            if self.custody_open > 0:
                self.mutation_blocked = True
                raise SourceIntegrityError("WRITE_SHARING_DENIED")
            self.files[handle.key]["data"] = self.replacement
            self.mutated = True
        return result


def test_task2_same_object_same_size_mutation_after_hash_cannot_silently_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = b"AAAA"
    mutated = b"BBBB"
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", original))
    adapter = _MutateAtHashBoundaryAdapter(
        {"sources/a.png": _fake_file(original, volume_serial=7, file_index=10)},
        replacement=mutated,
    )
    with pytest.raises(SourceIntegrityError, match="WRITE_SHARING_DENIED"):
        _task2_inspect(monkeypatch, adapter, bundle)
    assert adapter.mutation_blocked is True
    assert adapter.mutated is False


@pytest.mark.parametrize(
    ("scope", "field", "mutated_value"),
    [
        ("root", "bundle_id", "BUNDLE-TAMPERED"),
        ("root", "run_id", "RUN-TAMPERED"),
        ("item", "kind", "PDF"),
        ("item", "role", "OVERALL"),
        ("item", "declared_media_type", "image/jpeg"),
        ("item", "page_ids", ["PAGE-TAMPERED"]),
        ("item", "region_ids", ["REGION-TAMPERED"]),
    ],
)
def test_task2_require_match_cross_binds_r1a_declarations(
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    field: str,
    mutated_value: object,
) -> None:
    data = _PNG_1X1
    bundle = _task2_bundle(_task2_item("IMAGE-001", "sources/a.png", data))
    adapter = _FakeCustodyAdapter(
        {"sources/a.png": _fake_file(data, volume_serial=7, file_index=10)}
    )
    evidence = _task2_inspect(monkeypatch, adapter, bundle)
    custody = _png_downstream_custody(evidence)
    if scope == "root":
        custody[field] = mutated_value
    else:
        custody["items"][0][field] = mutated_value
        if field == "declared_media_type":
            custody["items"][0]["observed_media_type"] = mutated_value
    monkeypatch.setattr(
        _source_integrity_task2,
        "_WINDOWS_ADAPTER_FACTORY",
        lambda: adapter,
        raising=False,
    )
    with pytest.raises(SourceIntegrityError, match="CUSTODY_STALE_DECLARATION"):
        _source_integrity_task2.require_source_custody_match(
            approved_root_id="ROOT-SYNTHETIC",
            approved_root_revision="ROOT-REV-1",
            approved_root=_TASK2_ROOT,
            identity_key=_TASK2_KEY,
            identity_key_revision="KEY-REV-1",
            policy_limits=dict(_TASK2_LIMITS),
            source_bundle=bundle,
            custody=custody,
        )


def test_task2_test_fixture_requires_explicit_downstream_parser_facts() -> None:
    function_names = {
        node.name
        for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
    }
    assert "_task2_custody_from_evidence" not in function_names
    signature = inspect.signature(_truthful_downstream_custody_fixture)
    assert "observed_media_type" in signature.parameters
    assert "media_metadata" in signature.parameters
    assert signature.parameters["observed_media_type"].default is inspect.Parameter.empty
    assert signature.parameters["media_metadata"].default is inspect.Parameter.empty


def test_task2_aggregate_budget_rejects_before_second_file_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = b"1111"
    second = b"2222"
    bundle = _task2_bundle(
        _task2_item("IMAGE-001", "sources/a.png", first),
        _task2_item("IMAGE-002", "sources/b.png", second),
    )
    adapter = _FakeCustodyAdapter(
        {
            "sources/a.png": _fake_file(first, volume_serial=7, file_index=10),
            "sources/b.png": _fake_file(second, volume_serial=7, file_index=11),
        }
    )
    limits = dict(_TASK2_LIMITS)
    limits.update(max_file_bytes=4, max_total_bytes=6, hash_chunk_size=2)
    with pytest.raises(SourceIntegrityError, match="RESOURCE_LIMIT"):
        _task2_inspect(monkeypatch, adapter, bundle, policy_limits=limits)
    assert adapter.read_counts.get("sources/b.png", 0) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-native custody evidence")
def test_task2_windows_native_adapter_opens_hashes_reopens_and_denies_write(
    tmp_path: Path,
) -> None:
    data = b"native-windows-custody"
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(data)
    adapter = _source_integrity_task2._WindowsHandleAdapter()
    with adapter.open_root(tmp_path, max_final_path_chars=32768) as root_handle:
        with adapter.open_source(
            root_handle,
            "source.bin",
            max_final_path_chars=32768,
        ) as source_handle:
            before = adapter.snapshot(source_handle, max_final_path_chars=32768)
            digest, size = _source_integrity_task2._stream_handle_sha256(
                adapter,
                source_handle,
                chunk_size=4,
                max_file_bytes=1024,
            )
            assert digest == hashlib.sha256(data).hexdigest()
            assert size == len(data)
            writer = adapter._kernel32.CreateFileW(
                str(source_path),
                0x40000000,
                adapter._FILE_SHARE_READ | adapter._FILE_SHARE_DELETE,
                None,
                adapter._OPEN_EXISTING,
                0,
                None,
            )
            writer_value = __import__("ctypes").cast(
                writer, __import__("ctypes").c_void_p
            ).value
            assert writer_value in {None, adapter._invalid_handle}
            with adapter.reopen_source(
                root_handle,
                "source.bin",
                max_final_path_chars=32768,
            ) as reopened_handle:
                reopened = adapter.snapshot(reopened_handle, max_final_path_chars=32768)
                assert _source_integrity_task2._snapshot_identity(reopened) == (
                    _source_integrity_task2._snapshot_identity(before)
                )


# --- R1C Task 3 RED: read-only media adapters and strict Engineer JSON ---

_TASK3_MEDIA_LIMITS = {
    "max_image_pixels": 16_000_000,
    "max_pdf_pages": 64,
    "max_cad_header_bytes": 4096,
    "max_json_depth": 16,
    "max_json_containers": 4096,
    "max_json_string_chars": 65_536,
    "max_json_key_chars": 1024,
    "max_json_number_chars": 128,
}


def _task3_observe(kind: str, media_type: str, payload: bytes) -> dict[str, object]:
    import io

    observer = getattr(_source_integrity_task2, "_observe_media", None)
    assert observer is not None, "R1C Task 3 RED: media observer is missing"
    return observer(
        kind=kind,
        declared_media_type=media_type,
        parser_file=io.BytesIO(payload),
        media_limits=dict(_TASK3_MEDIA_LIMITS),
    )


def test_task3_requires_parser_isolated_duplicate_handle_api() -> None:
    assert hasattr(_source_integrity_task2._WindowsHandleAdapter, "duplicate_for_parser"), (
        "R1C Task 3 RED: parser-isolated duplicate-handle custody is missing"
    )


def test_task3_requires_complete_media_custody_entrypoint() -> None:
    assert hasattr(_source_integrity_task2, "inspect_source_bundle_media"), (
        "R1C Task 3 RED: complete media-custody entrypoint is missing"
    )


def test_task3_png_content_observation_is_bounded_and_structural() -> None:
    observed = _task3_observe("IMAGE", "image/png", _PNG_1X1)
    assert observed["observed_media_type"] == "image/png"
    assert observed["media_metadata"] == _PNG_1X1_METADATA


@pytest.mark.parametrize(
    "payload",
    [
        b"not-an-image",
        b"\x89PNG\r\n\x1a\ntruncated",
    ],
)
def test_task3_image_malformed_or_truncated_blocks(payload: bytes) -> None:
    with pytest.raises(SourceIntegrityError, match="UNSUPPORTED_MEDIA|MALFORMED_MEDIA"):
        _task3_observe("IMAGE", "image/png", payload)


def test_task3_declared_vs_observed_media_mismatch_blocks() -> None:
    with pytest.raises(SourceIntegrityError, match="MEDIA_MISMATCH"):
        _task3_observe("IMAGE", "image/jpeg", _PNG_1X1)


def test_task3_pdf_strict_parser_observes_only_bounded_structure() -> None:
    import io
    from pypdf import PdfWriter

    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=144)
    writer.write(buffer)
    observed = _task3_observe("PDF", "application/pdf", buffer.getvalue())
    assert observed["observed_media_type"] == "application/pdf"
    metadata = observed["media_metadata"]
    assert metadata["format"] == "PDF"
    assert metadata["page_count"] == 1
    assert "text" not in repr(metadata).lower()


def test_task3_pdf_malformed_blocks_without_non_strict_fallback() -> None:
    with pytest.raises(SourceIntegrityError, match="MALFORMED_MEDIA|UNSUPPORTED_MEDIA"):
        _task3_observe("PDF", "application/pdf", b"%PDF-1.7\nnot-a-real-pdf")


@pytest.mark.parametrize(
    ("media_type", "payload", "expected_format"),
    [
        ("application/acad", b"AC1032\x00rest", "DWG"),
        ("application/dxf", b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1032\n", "DXF"),
        ("application/dxf", b"AutoCAD Binary DXF\r\n\x1a\x00rest", "DXF"),
    ],
)
def test_task3_cad_header_only_observation(
    media_type: str, payload: bytes, expected_format: str
) -> None:
    observed = _task3_observe("EXACT_BASE_CAD", media_type, payload)
    assert observed["observed_media_type"] == media_type
    assert observed["media_metadata"]["format"] == expected_format
    assert set(observed["media_metadata"]) <= {"format", "version"}


@pytest.mark.parametrize(
    "payload",
    [b"AC10", b"UNKNOWN", b"0\nSECTION\n2\nENTITIES\n"],
)
def test_task3_cad_unknown_or_non_header_input_blocks(payload: bytes) -> None:
    with pytest.raises(SourceIntegrityError, match="UNSUPPORTED_MEDIA|MALFORMED_MEDIA"):
        _task3_observe("EXACT_BASE_CAD", "application/acad", payload)


def test_task3_engineer_json_is_strict_and_structural() -> None:
    observed = _task3_observe(
        "ENGINEER_RECORD",
        "application/json",
        b'{"alpha":1,"nested":{"ok":true}}',
    )
    assert observed["observed_media_type"] == "application/json"
    metadata = observed["media_metadata"]
    assert metadata["format"] == "JSON"
    assert metadata["root_type"] == "object"
    assert "alpha" not in repr(metadata)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"a":1,"a":2}',
        b'{"n":NaN}',
        b'{"n":Infinity}',
        b'[]',
        b'\xff',
    ],
)
def test_task3_engineer_json_rejects_ambiguous_or_unsafe_inputs(payload: bytes) -> None:
    with pytest.raises(SourceIntegrityError, match="JSON_|UNSUPPORTED_MEDIA|RESOURCE_LIMIT"):
        _task3_observe("ENGINEER_RECORD", "application/json", payload)


def test_task3_engineer_json_depth_limit_is_server_owned() -> None:
    deep = ("{\"a\":" * 20 + "0" + "}" * 20).encode("utf-8")
    with pytest.raises(SourceIntegrityError, match="RESOURCE_LIMIT"):
        _task3_observe("ENGINEER_RECORD", "application/json", deep)


def test_task3_source_contains_no_ezdxf_ocr_model_provider_or_autocad_authority() -> None:
    source = SOURCE_MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "import ezdxf",
        "primitive_ir_lib",
        "pytesseract",
        "openai",
        "anthropic",
        "autocad_plugin",
        "mcp_integration_lib",
    ):
        assert forbidden not in source
