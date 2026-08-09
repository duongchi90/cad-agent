from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


MODULE_NAME = "cad_agent.component_view_registry"
SCHEMA_VERSION = "component-view-registry-1.0"
ORIGIN_CLASSES = {
    "REUSED_UNCHANGED",
    "RECONSTRUCTED_CHANGED",
    "RECONSTRUCTED_NEW",
    "MIXED_UNRESOLVED",
}


def _registry_module():
    return importlib.import_module(MODULE_NAME)


@lru_cache(maxsize=None)
def _existing_test_module(filename: str):
    path = Path(__file__).with_name(filename)
    module_name = f"r3_fixture_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"fixture loader unavailable: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upstream_context() -> dict[str, object]:
    source_fusion_tests = _existing_test_module("test_cad_agent_source_fusion.py")
    source_fusion = importlib.import_module("cad_agent.source_fusion")
    primitive_artifact = source_fusion_tests._task5_primitive_artifact(
        [
            source_fusion_tests._task5_primitive("prim-a"),
            source_fusion_tests._task5_primitive("prim-b", end_x=20.0),
        ]
    )
    primitive_observations = source_fusion_tests._task5_project_primitive(
        primitive_artifact
    )
    semantic_artifact = source_fusion_tests._task5_semantic_artifact(
        primitive_ids=["prim-a", "prim-b"], primitive_count=2
    )
    semantic_observations = source_fusion_tests._task5_project_semantic(
        semantic_artifact, primitive_observations
    )
    fusion_inputs = source_fusion_tests._task6_ready_inputs(
        primitive_observations=primitive_observations,
        semantic_observations=semantic_observations,
    )
    fusion = source_fusion.build_source_fusion_packet(**fusion_inputs)
    validated_fusion = source_fusion.validate_source_fusion_packet(fusion)
    source_fusion_sha256 = source_fusion.source_fusion_sha256(validated_fusion)

    r2_tests = _existing_test_module("test_cad_agent_base_cad_adapter.py")
    base_adapter = importlib.import_module("cad_agent.base_cad_adapter")
    handoff = deepcopy(r2_tests._handoff())
    handoff["source_fusion_sha256"] = source_fusion_sha256
    handoff = base_adapter.validate_base_cad_reuse_handoff(handoff)
    current_live_inspection = r2_tests._live_inspection()
    evaluation = base_adapter.evaluate_frozen_base_cad_reuse(
        handoff=handoff, current_live_inspection=current_live_inspection
    )
    return {
        "source_fusion": fusion,
        "source_fusion_sha256": source_fusion_sha256,
        "reuse_handoff": handoff,
        "reuse_handoff_sha256": base_adapter.base_cad_reuse_handoff_sha256(handoff),
        "reuse_evaluation": evaluation,
        "current_live_inspection": current_live_inspection,
        "candidate": {
            "candidate_id": "candidate-001",
            "candidate_drawing_sha256": "9" * 64,
        },
    }


def _component_inputs(context: dict[str, object]) -> list[dict[str, object]]:
    fusion = context["source_fusion"]
    handoff_component = context["reuse_handoff"]["components"][0]
    primitive_keys = [
        item["observation_key"] for item in fusion["primitive_observations"]
    ]
    semantic_keys = [
        item["observation_key"] for item in fusion["semantic_observations"]
    ]
    return [
        {
            "component_type": "STRUCTURAL",
            "origin_class": "REUSED_UNCHANGED",
            "source_projection_refs": [primitive_keys[0]],
            "semantic_projection_refs": [semantic_keys[0]],
            "base_cad_provenance_ref": deepcopy(handoff_component),
            "candidate_entity_bindings": [
                {
                    "target_namespace": "CANDIDATE",
                    "candidate_id": "candidate-001",
                    "entity_handle": "C3D4",
                    "block_name": "CHASSIS_MAIN",
                    "legacy_uuid": "uuid-a",
                    "relative_path": "candidate/revision-a.dwg",
                    "captured_at_utc": "2026-08-10T00:00:00Z",
                }
            ],
        },
        {
            "component_type": "STRUCTURAL",
            "origin_class": "RECONSTRUCTED_NEW",
            "source_projection_refs": [primitive_keys[1]],
            "semantic_projection_refs": [semantic_keys[0]],
            "candidate_entity_bindings": [
                {
                    "target_namespace": "CANDIDATE",
                    "candidate_id": "candidate-001",
                    "entity_handle": "E5F6",
                    "block_name": "CABIN_MAIN",
                    "legacy_uuid": "uuid-b",
                    "relative_path": "candidate/revision-b.dwg",
                    "captured_at_utc": "2026-08-10T00:00:00Z",
                }
            ],
        },
    ]


def _single_component(context: dict[str, object]) -> list[dict[str, object]]:
    return [_component_inputs(context)[0]]


def test_public_surface_uses_the_accepted_parameter_modes() -> None:
    module = _registry_module()
    assert module.COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION == SCHEMA_VERSION
    assert issubclass(module.ComponentViewRegistryError, ValueError)
    assert list(inspect.signature(module.build_component_view_registry).parameters) == [
        "upstream_context",
        "components",
    ]
    assert list(inspect.signature(module.validate_component_view_registry).parameters) == [
        "payload",
        "upstream_context",
    ]
    assert list(inspect.signature(module.component_view_registry_sha256).parameters) == [
        "payload",
        "upstream_context",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in inspect.signature(
            module.build_component_view_registry
        ).parameters.values()
    )
    for function in (
        module.validate_component_view_registry,
        module.component_view_registry_sha256,
    ):
        parameters = inspect.signature(function).parameters
        assert parameters["payload"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters["upstream_context"].kind is inspect.Parameter.KEYWORD_ONLY


def test_builds_closed_task_one_registry_with_empty_views_and_links() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = module.build_component_view_registry(
        upstream_context=context, components=_single_component(context)
    )
    assert set(registry) == {
        "schema_version",
        "upstream_bindings",
        "components",
        "views",
        "links",
        "registry_snapshot_sha256",
    }
    assert registry["schema_version"] == SCHEMA_VERSION
    assert registry["views"] == []
    assert registry["links"] == []
    assert registry["components"][0]["origin_class"] == "REUSED_UNCHANGED"
    assert registry["components"][0]["view_ids"] == []


def test_component_identity_ignores_volatile_bindings_and_order() -> None:
    module = _registry_module()
    context = _upstream_context()
    first_components = _component_inputs(context)
    first = module.build_component_view_registry(
        upstream_context=context, components=first_components
    )
    second_components = deepcopy(first_components)
    second_components.reverse()
    for component in second_components:
        binding = component["candidate_entity_bindings"][0]
        binding["entity_handle"] = "VOLATILE-CHANGED"
        binding["legacy_uuid"] = "new-random-uuid"
        binding["relative_path"] = "renamed/volatile.dwg"
        binding["captured_at_utc"] = "2099-01-01T00:00:00Z"
    second = module.build_component_view_registry(
        upstream_context=context, components=second_components
    )
    first_ids = sorted(item["component_id"] for item in first["components"])
    second_ids = sorted(item["component_id"] for item in second["components"])
    assert first_ids == second_ids
    assert first["registry_snapshot_sha256"] != second["registry_snapshot_sha256"]


def test_stable_projection_membership_type_origin_and_base_identity_change_id() -> None:
    module = _registry_module()
    context = _upstream_context()
    base = _single_component(context)
    first = module.build_component_view_registry(
        upstream_context=context, components=base
    )
    for field, value in (
        ("component_type", "MOUNTING"),
        ("origin_class", "RECONSTRUCTED_CHANGED"),
        (
            "source_projection_refs",
            [_component_inputs(context)[1]["source_projection_refs"][0]],
        ),
    ):
        changed = deepcopy(base)
        changed[0][field] = value
        result = module.build_component_view_registry(
            upstream_context=context, components=changed
        )
        assert result["components"][0]["component_id"] != first["components"][0]["component_id"]


def test_candidate_binding_change_preserves_logical_id_but_changes_snapshot() -> None:
    module = _registry_module()
    context = _upstream_context()
    first = module.build_component_view_registry(
        upstream_context=context, components=_single_component(context)
    )
    changed = _single_component(context)
    changed[0]["candidate_entity_bindings"][0]["entity_handle"] = "CHANGED"
    second = module.build_component_view_registry(
        upstream_context=context, components=changed
    )
    assert first["components"][0]["component_id"] == second["components"][0]["component_id"]
    assert first["registry_snapshot_sha256"] != second["registry_snapshot_sha256"]


def test_build_is_deterministic_for_replay_and_component_permutation() -> None:
    module = _registry_module()
    context = _upstream_context()
    components = _component_inputs(context)
    first = module.build_component_view_registry(
        upstream_context=context, components=components
    )
    replay = module.build_component_view_registry(
        upstream_context=context, components=list(reversed(deepcopy(components)))
    )
    assert first == replay
    assert module.component_view_registry_sha256(first, upstream_context=context) == first[
        "registry_snapshot_sha256"
    ]


def test_reused_component_requires_fresh_current_r2_evidence() -> None:
    module = _registry_module()
    context = _upstream_context()
    context["current_live_inspection"]["base_source"]["sha256"] = "c" * 64
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=_single_component(context)
        )


def test_foreign_projection_reference_fails_closed() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    component["source_projection_refs"] = ["f" * 64]
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )


def test_caller_minted_r2_hash_or_fusion_hash_is_not_authority() -> None:
    module = _registry_module()
    context = _upstream_context()
    context["reuse_handoff_sha256"] = "f" * 64
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=_single_component(context)
        )

    context = _upstream_context()
    context["source_fusion_sha256"] = "f" * 64
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=_single_component(context)
        )


@pytest.mark.parametrize(
    "field_mutation",
    [
        ("missing_provenance", lambda component: component.pop("base_cad_provenance_ref")),
        ("reused_without_provenance", lambda component: component.update(
            {"origin_class": "REUSED_UNCHANGED", "base_cad_provenance_ref": None}
        )),
        ("unknown_origin", lambda component: component.__setitem__("origin_class", "UNKNOWN")),
    ],
)
def test_origin_class_invariants_fail_closed(field_mutation) -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    _, mutation = field_mutation
    mutation(component)
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )


def test_reconstructed_origin_cannot_claim_reused_provenance() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    component["origin_class"] = "RECONSTRUCTED_NEW"
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )


def test_candidate_only_target_namespace_and_binding_closure_are_enforced() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    component["candidate_entity_bindings"][0]["target_namespace"] = "SOURCE"
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda components: components.append(deepcopy(components[0])),
        lambda components: components[0].__setitem__("unknown", "x"),
        lambda components: components[0]["candidate_entity_bindings"].append(
            deepcopy(components[0]["candidate_entity_bindings"][0])
        ),
    ],
)
def test_duplicate_or_unknown_component_records_fail_closed(mutation) -> None:
    module = _registry_module()
    context = _upstream_context()
    components = _single_component(context)
    mutation(components)
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=components
        )


def test_validation_is_closed_detached_and_rejects_views_or_links_in_task_one() -> None:
    module = _registry_module()
    context = _upstream_context()
    original = _single_component(context)
    registry = module.build_component_view_registry(
        upstream_context=context, components=original
    )
    normalized = module.validate_component_view_registry(
        registry, upstream_context=context
    )
    assert normalized is not registry
    assert normalized["components"] is not registry["components"]
    registry["components"][0]["component_id"] = "mutated"
    assert normalized["components"][0]["component_id"] != "mutated"
    invalid = deepcopy(normalized)
    invalid["views"] = [{"view_id": "view-001"}]
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(invalid, upstream_context=context)
    invalid = deepcopy(normalized)
    invalid["links"] = [{"link_id": "link-001"}]
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(invalid, upstream_context=context)
    invalid = deepcopy(normalized)
    invalid["components"][0]["view_ids"] = ["view-001"]
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(invalid, upstream_context=context)


def test_canonical_hash_delegation_and_snapshot_mutation_sensitivity() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = module.build_component_view_registry(
        upstream_context=context, components=_single_component(context)
    )
    material = deepcopy(registry)
    expected = material.pop("registry_snapshot_sha256")
    assert expected == canonical_json_sha256(material)
    assert module.component_view_registry_sha256(
        registry, upstream_context=context
    ) == expected
    registry["components"][0]["candidate_entity_bindings"][0]["entity_handle"] = "MUTATED"
    assert module.component_view_registry_sha256(
        registry, upstream_context=context
    ) != expected


def test_errors_are_categorical_and_privacy_safe() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    component["candidate_entity_bindings"][0]["relative_path"] = r"C:\customer\secret.dwg"
    with pytest.raises(module.ComponentViewRegistryError) as caught:
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )
    assert "C:\\customer" not in str(caught.value)
    assert "secret.dwg" not in str(caught.value)


def test_static_boundary_has_no_parser_transport_store_or_second_owner() -> None:
    module = _registry_module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "canonical_json_sha256" in source
    for forbidden in (
        "ezdxf",
        "pypdf",
        "PIL",
        "ocr",
        "socket",
        "subprocess",
        "DotNetIPCClient",
        "FileIPC",
        "manifest",
        "revision_store",
        "approval",
        "verdict",
        "publisher",
        "open(",
        "Path(",
    ):
        assert forbidden not in source
