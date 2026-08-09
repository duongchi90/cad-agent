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


def _set_field(payload: dict[str, object], field_path: str, value: object) -> None:
    if field_path.startswith("base_source."):
        payload["base_source"][field_path.split(".", 1)[1]] = value
    else:
        payload[field_path] = value


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


@pytest.mark.parametrize("payload", [None, [], "binding", 42, True])
def test_validate_rejects_non_mapping_root_with_categorical_error(payload: object) -> None:
    module = _module()

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize("payload", [None, [], "base-source", 42, True])
def test_validate_rejects_non_mapping_base_source_with_categorical_error(
    payload: object,
) -> None:
    module = _module()
    binding = _binding()
    binding["base_source"] = payload

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(binding)


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
        ("state", "STALE_SOURCE"),
        ("state", "SOURCE_DRIFTED"),
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
@pytest.mark.parametrize(
    "invalid_sha",
    [None, 7, "", "a" * 63, "a" * 65, "g" * 64, "A" * 64],
)
def test_validate_requires_lowercase_sha256(
    field_path: str, invalid_sha: object
) -> None:
    module = _module()
    payload = _binding()
    _set_field(payload, field_path, invalid_sha)

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        ("run_id", ""),
        ("run_id", "bad id with spaces"),
        ("run_id", None),
        ("inspection_id", "../inspection"),
        ("inspection_id", 9),
        ("base_source.source_id", "base/source"),
        ("base_source.source_id", ["base-cad-001"]),
        ("base_source.revision", "rev A"),
        ("base_source.revision", None),
    ],
)
def test_validate_requires_safe_identifiers(field_path: str, value: object) -> None:
    module = _module()
    payload = _binding()
    _set_field(payload, field_path, value)

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


@pytest.mark.parametrize(
    "invalid_components",
    [
        [],
        "component-A",
        ("component-A",),
        7,
        ["component-A", "component-A"],
        ["component-A", 7],
        [None],
        ["bad component"],
    ],
)
def test_component_ids_are_nonempty_unique_and_typed(
    invalid_components: object,
) -> None:
    module = _module()
    payload = _binding()
    payload["eligible_component_ids"] = invalid_components

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_component_id_permutations_normalize_deterministically() -> None:
    module = _module()
    first = _binding()
    second = _binding()
    second["eligible_component_ids"] = list(reversed(second["eligible_component_ids"]))

    assert module.validate_base_cad_binding(first) == module.validate_base_cad_binding(second)
    assert module.base_cad_binding_sha256(first) == module.base_cad_binding_sha256(second)


def test_hash_uses_validated_normalized_binding_and_existing_canonical_owner() -> None:
    module = _module()
    payload = _binding()
    normalized = module.validate_base_cad_binding(payload)

    assert module.base_cad_binding_sha256(payload) == canonical_json_sha256(normalized)


@pytest.mark.parametrize(
    "invalid_payload",
    [
        None,
        [],
        "binding",
        {**_binding(), "base_source": None},
        {**_binding(), "source_bundle_sha256": "bad"},
        {**_binding(), "run_id": None},
        {**_binding(), "eligible_component_ids": "component-A"},
        {**_binding(), "unexpected": "authority"},
    ],
)
def test_hash_rejects_invalid_binding_with_same_categorical_error(
    invalid_payload: object,
) -> None:
    module = _module()

    with pytest.raises(module.BaseCadAdapterError):
        module.base_cad_binding_sha256(invalid_payload)


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
    _set_field(mutated, field_path, value)

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
        "provenance",
        "source_handle",
        "source_handles",
        "candidate_handle",
        "units",
        "unit_conversion",
        "ucs",
        "wcs",
        "coordinate_system",
        "renderer",
        "transport",
        "registry_id",
        "revision_store",
    ],
)
def test_upstream_or_downstream_authority_fields_fail_closed(
    forbidden_field: str,
) -> None:
    module = _module()
    payload = _binding()
    payload[forbidden_field] = "forbidden"

    with pytest.raises(module.BaseCadAdapterError):
        module.validate_base_cad_binding(payload)


def test_stale_source_identity_cannot_be_silently_relabelled() -> None:
    module = _module()
    baseline = _binding()
    changed_hash = _binding()
    changed_revision = _binding()
    changed_hash["base_source"]["sha256"] = "a" * 64
    changed_revision["base_source"]["revision"] = "rev-B"

    baseline_hash = module.base_cad_binding_sha256(baseline)
    assert module.base_cad_binding_sha256(changed_hash) != baseline_hash
    assert module.base_cad_binding_sha256(changed_revision) != baseline_hash

    for stale_state in ("STALE_SOURCE", "SOURCE_DRIFTED"):
        payload = deepcopy(changed_hash)
        payload["state"] = stale_state
        with pytest.raises(module.BaseCadAdapterError):
            module.validate_base_cad_binding(payload)


def test_five_replays_and_component_permutations_have_one_identity() -> None:
    module = _module()
    payloads = []
    for index in range(5):
        payload = _binding()
        if index % 2:
            payload["eligible_component_ids"] = list(
                reversed(payload["eligible_component_ids"])
            )
        payloads.append(payload)

    normalized = [module.validate_base_cad_binding(payload) for payload in payloads]
    hashes = [module.base_cad_binding_sha256(payload) for payload in payloads]

    assert all(item == normalized[0] for item in normalized)
    assert len(set(hashes)) == 1


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
