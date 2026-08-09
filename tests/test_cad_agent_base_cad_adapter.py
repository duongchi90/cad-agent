from __future__ import annotations

from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


_BINDING_FIELDS = {
    "schema_version",
    "run_id",
    "source_bundle_sha256",
    "source_custody_sha256",
    "source_fusion_sha256",
    "base_source",
    "inspection_id",
    "inspection_sha256",
    "target_drawing_sha256",
    "eligible_component_ids",
    "transform_policy",
    "state",
}
_BASE_SOURCE_FIELDS = {"source_id", "sha256", "revision"}


def _binding() -> dict[str, object]:
    return {
        "schema_version": "base-cad-binding-1.0",
        "run_id": "run-R2-001",
        "source_bundle_sha256": "1" * 64,
        "source_custody_sha256": "2" * 64,
        "source_fusion_sha256": "3" * 64,
        "base_source": {
            "source_id": "base-cad-001",
            "sha256": "4" * 64,
            "revision": "rev-A",
        },
        "inspection_id": "inspection-001",
        "inspection_sha256": "5" * 64,
        "target_drawing_sha256": "6" * 64,
        "eligible_component_ids": ["component-B", "component-A"],
        "transform_policy": "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        "state": "READY_FOR_SELECTION",
    }


def _module():
    return importlib.import_module("cad_agent.base_cad_adapter")


def test_fixture_is_closed_and_canonical_hashable() -> None:
    payload = _binding()

    assert set(payload) == _BINDING_FIELDS
    assert set(payload["base_source"]) == _BASE_SOURCE_FIELDS
    assert canonical_json_sha256(payload) == canonical_json_sha256(deepcopy(payload))


def test_offline_kernel_surface_is_exact_and_builder_remains_locked() -> None:
    module = _module()

    assert module.BASE_CAD_BINDING_SCHEMA_VERSION == "base-cad-binding-1.0"
    assert issubclass(module.BaseCadAdapterError, ValueError)
    assert callable(module.validate_base_cad_binding)
    assert callable(module.base_cad_binding_sha256)
    assert not hasattr(module, "build_base_cad_binding")


def test_validate_accepts_closed_binding_and_returns_detached_normalized_copy() -> None:
    module = _module()
    payload = _binding()

    normalized = module.validate_base_cad_binding(payload)

    assert normalized is not payload
    assert normalized["base_source"] is not payload["base_source"]
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]
    payload["base_source"]["revision"] = "rev-mutated"
    payload["eligible_component_ids"].append("component-C")
    assert normalized["base_source"]["revision"] == "rev-A"
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        (lambda value: value.pop("inspection_sha256"), "inspection_sha256"),
        (lambda value: value.__setitem__("absolute_path", "C:/private/base.dwg"), "absolute_path"),
        (
            lambda value: value["base_source"].pop("revision"),
            "base_source.revision",
        ),
        (
            lambda value: value["base_source"].__setitem__("relative_path", "base.dwg"),
            "base_source.relative_path",
        ),
    ],
)
def test_validate_rejects_missing_or_unknown_fields(mutation, field: str) -> None:
    module = _module()
    payload = _binding()
    mutation(payload)

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "base-cad-binding-2.0"),
        ("state", "CURRENT"),
        ("transform_policy", "ARBITRARY_MATRIX"),
    ],
)
def test_validate_rejects_wrong_locked_values(field: str, value: object) -> None:
    module = _module()
    payload = _binding()
    payload[field] = value

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    "field_path",
    [
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
        "base_source.sha256",
        "inspection_sha256",
        "target_drawing_sha256",
    ],
)
def test_validate_requires_lowercase_sha256(field_path: str) -> None:
    module = _module()
    payload = _binding()
    if field_path.startswith("base_source."):
        payload["base_source"][field_path.split(".", 1)[1]] = "A" * 64
    else:
        payload[field_path] = "A" * 64

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        ("run_id", ""),
        ("run_id", "bad id with spaces"),
        ("inspection_id", "../inspection"),
        ("base_source.source_id", "base/source"),
        ("base_source.revision", "rev A"),
    ],
)
def test_validate_requires_safe_identifiers(field_path: str, value: str) -> None:
    module = _module()
    payload = _binding()
    if field_path.startswith("base_source."):
        payload["base_source"][field_path.split(".", 1)[1]] = value
    else:
        payload[field_path] = value

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_component_ids_are_nonempty_unique_and_permutation_normalized() -> None:
    module = _module()
    first = _binding()
    second = _binding()
    second["eligible_component_ids"] = list(reversed(second["eligible_component_ids"]))

    assert module.validate_base_cad_binding(first) == module.validate_base_cad_binding(second)
    assert module.base_cad_binding_sha256(first) == module.base_cad_binding_sha256(second)

    for invalid in ([], ["component-A", "component-A"], ["bad component"]):
        payload = _binding()
        payload["eligible_component_ids"] = invalid
        with pytest.raises(module.BaseCadAdapterError):
            module.validate_base_cad_binding(payload)


def test_hash_uses_validated_normalized_binding_and_existing_canonical_owner() -> None:
    module = _module()
    payload = _binding()
    normalized = module.validate_base_cad_binding(payload)

    assert module.base_cad_binding_sha256(payload) == canonical_json_sha256(normalized)


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        ("source_bundle_sha256", "a" * 64),
        ("source_custody_sha256", "b" * 64),
        ("source_fusion_sha256", "c" * 64),
        ("base_source.sha256", "d" * 64),
        ("base_source.revision", "rev-B"),
        ("inspection_id", "inspection-002"),
        ("inspection_sha256", "e" * 64),
        ("target_drawing_sha256", "f" * 64),
        ("eligible_component_ids", ["component-C"]),
    ],
)
def test_authoritative_mutation_changes_binding_hash(field_path: str, value: object) -> None:
    module = _module()
    baseline = _binding()
    mutated = _binding()
    if field_path.startswith("base_source."):
        mutated["base_source"][field_path.split(".", 1)[1]] = value
    else:
        mutated[field_path] = value

    assert module.base_cad_binding_sha256(mutated) != module.base_cad_binding_sha256(baseline)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "path",
        "relative_path",
        "timestamp",
        "approval",
        "verdict",
        "current",
        "published",
        "repair",
    ],
)
def test_authority_fields_outside_binding_contract_fail_closed(forbidden_field: str) -> None:
    module = _module()
    payload = _binding()
    payload[forbidden_field] = "forbidden"

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_offline_kernel_has_no_upstream_live_or_second_hash_owner_imports() -> None:
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "canonical_json_sha256" in source
    for forbidden in (
        "hashlib",
        "json.dumps",
        "cad_agent.source_bundle",
        "cad_agent.source_integrity",
        "cad_agent.source_fusion",
        "mcp_integration_lib",
        "DotNetIPCClient",
        "subprocess",
        "socket",
        "pathlib.Path(",
        "open(",
    ):
        assert forbidden not in source
