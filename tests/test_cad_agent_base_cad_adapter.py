from __future__ import annotations

from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


_FIELDS = {
    "schema_version", "run_id", "source_bundle_sha256", "source_custody_sha256",
    "source_fusion_sha256", "base_source", "inspection_id", "inspection_sha256",
    "target_drawing_sha256", "eligible_component_ids", "transform_policy", "state",
}
_BASE_SOURCE_FIELDS = {"source_id", "sha256", "revision"}


def _module():
    return importlib.import_module("cad_agent.base_cad_adapter")


def _binding() -> dict[str, object]:
    return {
        "schema_version": "base-cad-binding-1.0",
        "run_id": "run-R2-171-001",
        "source_bundle_sha256": "1" * 64,
        "source_custody_sha256": "2" * 64,
        "source_fusion_sha256": "3" * 64,
        "base_source": {"source_id": "base-cad-001", "sha256": "4" * 64, "revision": "rev-A"},
        "inspection_id": "inspection-001",
        "inspection_sha256": "5" * 64,
        "target_drawing_sha256": "6" * 64,
        "eligible_component_ids": ["component-B", "component-A"],
        "transform_policy": "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        "state": "READY_FOR_SELECTION",
    }


def test_fixture_is_closed_and_canonical_hashable() -> None:
    payload = _binding()
    assert set(payload) == _FIELDS
    assert set(payload["base_source"]) == _BASE_SOURCE_FIELDS
    assert canonical_json_sha256(payload) == canonical_json_sha256(deepcopy(payload))


def test_offline_kernel_surface_is_exact_and_builder_locked() -> None:
    module = _module()
    assert module.BASE_CAD_BINDING_SCHEMA_VERSION == "base-cad-binding-1.0"
    assert issubclass(module.BaseCadAdapterError, ValueError)
    assert callable(module.validate_base_cad_binding)
    assert callable(module.base_cad_binding_sha256)
    assert not hasattr(module, "build_base_cad_binding")


def test_validation_returns_detached_sorted_normalized_copy() -> None:
    module = _module()
    payload = _binding()
    normalized = module.validate_base_cad_binding(payload)
    assert normalized is not payload
    assert normalized["base_source"] is not payload["base_source"]
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]
    payload["base_source"]["revision"] = "mutated"
    payload["eligible_component_ids"].append("component-C")
    assert normalized["base_source"]["revision"] == "rev-A"
    assert normalized["eligible_component_ids"] == ["component-A", "component-B"]


@pytest.mark.parametrize("payload", [None, [], "binding", 42, True])
def test_non_mapping_root_fails_closed(payload: object) -> None:
    module = _module()
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize("field", ["inspection_sha256", "base_source.revision"])
def test_missing_fields_fail_closed(field: str) -> None:
    module = _module()
    payload = _binding()
    if "." in field:
        del payload["base_source"][field.split(".", 1)[1]]
    else:
        del payload[field]
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "base-cad-binding-2.0"),
        ("source_bundle_sha256", "A" * 64),
        ("run_id", "bad id"),
        ("base_source.source_id", "../source"),
        ("eligible_component_ids", ["component-A", "component-A"]),
        ("state", "STALE_SOURCE"),
        ("transform_policy", "ARBITRARY_MATRIX"),
    ],
)
def test_invalid_authority_or_identity_fails_closed(field: str, value: object) -> None:
    module = _module()
    payload = _binding()
    if "." in field:
        payload["base_source"][field.split(".", 1)[1]] = value
    else:
        payload[field] = value
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    "forbidden",
    ["path", "relative_path", "approval", "verdict", "repair", "publication",
     "source_handle", "candidate_handle", "units", "ucs", "wcs", "renderer",
     "transport", "registry_id", "revision_store"],
)
def test_private_live_and_downstream_authority_fields_fail_closed(forbidden: str) -> None:
    module = _module()
    payload = _binding()
    payload[forbidden] = "forbidden"
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_component_permutations_have_one_hash_identity() -> None:
    module = _module()
    first = _binding()
    second = _binding()
    second["eligible_component_ids"] = list(reversed(second["eligible_component_ids"]))
    assert module.validate_base_cad_binding(first) == module.validate_base_cad_binding(second)
    assert module.base_cad_binding_sha256(first) == module.base_cad_binding_sha256(second)


def test_authoritative_mutations_change_hash_and_stale_state_rejects() -> None:
    module = _module()
    baseline = _binding()
    changed = _binding()
    changed["base_source"]["revision"] = "rev-B"
    assert module.base_cad_binding_sha256(changed) != module.base_cad_binding_sha256(baseline)
    stale = deepcopy(changed)
    stale["state"] = "SOURCE_DRIFTED"
    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(stale)


def test_hash_uses_existing_canonical_owner_and_no_second_hash_or_live_owner() -> None:
    module = _module()
    assert module.base_cad_binding_sha256(_binding()) == canonical_json_sha256(
        module.validate_base_cad_binding(_binding())
    )
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "canonical_json_sha256" in source
    for forbidden in (
        "hashlib", "json.dumps", "source_bundle", "source_integrity", "source_fusion",
        "mcp_integration_lib", "DotNetIPCClient", "subprocess", "socket", "open(",
    ):
        assert forbidden not in source
