from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


MODULE_NAME = "cad_agent.component_view_registry"
SCHEMA_VERSION = "component-view-registry-1.0"


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


def _upstream_context(
    *,
    primitive_ids: tuple[str, str] = ("prim-a", "prim-b"),
    semantic_part_id: str = "part-a",
) -> dict[str, object]:
    source_fusion_tests = _existing_test_module("test_cad_agent_source_fusion.py")
    source_fusion = importlib.import_module("cad_agent.source_fusion")
    primitive_artifact = source_fusion_tests._task5_primitive_artifact(
        [
            source_fusion_tests._task5_primitive(primitive_ids[0]),
            source_fusion_tests._task5_primitive(primitive_ids[1], end_x=20.0),
        ]
    )
    primitive_observations = source_fusion_tests._task5_project_primitive(
        primitive_artifact
    )
    semantic_artifact = source_fusion_tests._task5_semantic_artifact(
        primitive_ids=list(primitive_ids),
        primitive_count=2,
        part_id=semantic_part_id,
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
    handoff["source_bundle_sha256"] = validated_fusion["source_bundle_sha256"]
    handoff["source_custody_sha256"] = validated_fusion["source_custody_sha256"]
    handoff["source_fusion_sha256"] = source_fusion_sha256
    handoff = base_adapter.validate_base_cad_reuse_handoff(handoff)
    current_live_inspection = r2_tests._live_inspection()
    evaluation = base_adapter.evaluate_frozen_base_cad_reuse(
        handoff=handoff, current_live_inspection=current_live_inspection
    )
    return {
        "source_fusion": validated_fusion,
        "source_fusion_sha256": source_fusion_sha256,
        "reuse_handoff": handoff,
        "reuse_handoff_sha256": base_adapter.base_cad_reuse_handoff_sha256(handoff),
        "reuse_evaluation": evaluation,
        "current_live_inspection": current_live_inspection,
        "candidate": {
            "candidate_id": "candidate-001",
            "candidate_drawing_sha256": handoff["candidate_output_sha256"],
        },
    }


def _replace_handoff(
    context: dict[str, object], handoff: dict[str, object]
) -> dict[str, object]:
    changed = deepcopy(context)
    base_adapter = importlib.import_module("cad_agent.base_cad_adapter")
    normalized = base_adapter.validate_base_cad_reuse_handoff(handoff)
    changed["reuse_handoff"] = normalized
    changed["reuse_handoff_sha256"] = base_adapter.base_cad_reuse_handoff_sha256(
        normalized
    )
    changed["reuse_evaluation"] = base_adapter.evaluate_frozen_base_cad_reuse(
        handoff=normalized,
        current_live_inspection=changed["current_live_inspection"],
    )
    return changed


def _remapped_candidate_context(
    context: dict[str, object], *, candidate_handle: str
) -> dict[str, object]:
    handoff = deepcopy(context["reuse_handoff"])
    handoff["components"][0]["candidate_handle"] = candidate_handle
    handoff["source_handle_to_candidate_handle"][0]["candidate_handle"] = (
        candidate_handle
    )
    return _replace_handoff(context, handoff)


def _renamed_r2_locator_context(
    context: dict[str, object], *, logical_component_id: str
) -> dict[str, object]:
    handoff = deepcopy(context["reuse_handoff"])
    handoff["components"][0]["logical_component_id"] = logical_component_id
    return _replace_handoff(context, handoff)


def _disconnected_r2_lineage_context(
    context: dict[str, object], *, field: str
) -> dict[str, object]:
    handoff = deepcopy(context["reuse_handoff"])
    handoff[field] = "f" * 64
    return _replace_handoff(context, handoff)


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
                    "entity_handle": handoff_component["candidate_handle"],
                    "block_name": handoff_component["source_block"],
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
            "candidate_entity_bindings": [],
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
        "views",
    ]
    assert list(inspect.signature(module.validate_component_view_registry).parameters) == [
        "payload",
        "upstream_context",
    ]
    assert list(inspect.signature(module.component_view_registry_sha256).parameters) == [
        "payload",
        "upstream_context",
    ]
    assert list(inspect.signature(module.project_linked_view_impacts).parameters) == [
        "registry",
        "component_ids",
        "view_ids",
        "upstream_context",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in inspect.signature(
            module.build_component_view_registry
        ).parameters.values()
    )
    impact_parameters = inspect.signature(module.project_linked_view_impacts).parameters
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in impact_parameters.values()
    )
    assert impact_parameters["component_ids"].default == ()
    assert impact_parameters["view_ids"].default == ()
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
    component = registry["components"][0]
    assert set(component) == {
        "component_id",
        "component_type",
        "origin_class",
        "source_projection_refs",
        "semantic_projection_refs",
        "base_cad_provenance_ref",
        "view_ids",
        "candidate_entity_bindings",
    }
    assert component["origin_class"] == "REUSED_UNCHANGED"
    assert component["view_ids"] == []


def test_component_identity_ignores_volatile_binding_metadata_and_order() -> None:
    module = _registry_module()
    context = _upstream_context()
    first_components = _component_inputs(context)
    first = module.build_component_view_registry(
        upstream_context=context, components=first_components
    )
    second_components = list(reversed(deepcopy(first_components)))
    for component in second_components:
        for binding in component["candidate_entity_bindings"]:
            binding["legacy_uuid"] = "new-random-uuid"
            binding["relative_path"] = "renamed/volatile.dwg"
            binding["captured_at_utc"] = "2099-01-01T00:00:00Z"
    second = module.build_component_view_registry(
        upstream_context=context, components=second_components
    )
    first_ids = sorted(item["component_id"] for item in first["components"])
    second_ids = sorted(item["component_id"] for item in second["components"])
    assert first_ids == second_ids


def test_component_id_changes_with_valid_projection_membership_or_component_type() -> None:
    module = _registry_module()
    context = _upstream_context()
    base = _single_component(context)
    first = module.build_component_view_registry(
        upstream_context=context, components=base
    )
    for field, value in (
        ("component_type", "MOUNTING"),
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
        assert (
            result["components"][0]["component_id"]
            != first["components"][0]["component_id"]
        )


def test_reused_candidate_handle_rebind_requires_valid_r2_mapping() -> None:
    module = _registry_module()
    first_context = _upstream_context()
    second_context = _remapped_candidate_context(
        first_context, candidate_handle="D4E5"
    )
    first = module.build_component_view_registry(
        upstream_context=first_context, components=_single_component(first_context)
    )
    second = module.build_component_view_registry(
        upstream_context=second_context, components=_single_component(second_context)
    )
    assert first["components"][0]["component_id"] == second["components"][0][
        "component_id"
    ]
    assert first["registry_snapshot_sha256"] != second["registry_snapshot_sha256"]


def test_reused_candidate_handle_mismatch_fails_closed() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    component["candidate_entity_bindings"][0]["entity_handle"] = "D4E5"
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )


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


@pytest.mark.parametrize(
    "field",
    ["source_bundle_sha256", "source_custody_sha256", "source_fusion_sha256"],
)
def test_r1_r2_lineage_hashes_must_cross_bind(field: str) -> None:
    module = _registry_module()
    context = _upstream_context()
    disconnected = _disconnected_r2_lineage_context(context, field=field)
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=disconnected,
            components=_single_component(disconnected),
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


def test_candidate_output_sha_mismatch_is_a_foreign_snapshot() -> None:
    module = _registry_module()
    context = _upstream_context()
    context["candidate"]["candidate_drawing_sha256"] = "e" * 64
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context, components=_single_component(context)
        )


def test_r2_logical_component_locator_never_becomes_r3_component_id() -> None:
    module = _registry_module()
    first_context = _upstream_context()
    renamed_context = _renamed_r2_locator_context(
        first_context, logical_component_id="component-renamed"
    )
    first = module.build_component_view_registry(
        upstream_context=first_context, components=_single_component(first_context)
    )
    renamed = module.build_component_view_registry(
        upstream_context=renamed_context, components=_single_component(renamed_context)
    )
    first_id = first["components"][0]["component_id"]
    renamed_id = renamed["components"][0]["component_id"]
    assert first_id == renamed_id
    assert first_id != first_context["reuse_handoff"]["components"][0][
        "logical_component_id"
    ]
    assert renamed_id != renamed_context["reuse_handoff"]["components"][0][
        "logical_component_id"
    ]


def test_regenerated_primitive_legacy_ids_do_not_change_r3_component_id() -> None:
    module = _registry_module()
    first_context = _upstream_context(primitive_ids=("prim-a", "prim-b"))
    regenerated_context = _upstream_context(
        primitive_ids=("primitive-regenerated-a", "primitive-regenerated-b")
    )
    first_components = _single_component(first_context)
    regenerated_components = _single_component(regenerated_context)
    assert first_components[0]["source_projection_refs"] != regenerated_components[0][
        "source_projection_refs"
    ]
    first = module.build_component_view_registry(
        upstream_context=first_context, components=first_components
    )
    regenerated = module.build_component_view_registry(
        upstream_context=regenerated_context, components=regenerated_components
    )
    assert first["components"][0]["component_id"] == regenerated["components"][0][
        "component_id"
    ]


def test_r1_elides_semantic_legacy_id_and_r3_component_id_stays_stable() -> None:
    module = _registry_module()
    first_context = _upstream_context(semantic_part_id="part-a")
    regenerated_context = _upstream_context(semantic_part_id="part-regenerated")
    first_components = _single_component(first_context)
    regenerated_components = _single_component(regenerated_context)
    assert first_components[0]["semantic_projection_refs"] == regenerated_components[0][
        "semantic_projection_refs"
    ]
    first = module.build_component_view_registry(
        upstream_context=first_context, components=first_components
    )
    regenerated = module.build_component_view_registry(
        upstream_context=regenerated_context, components=regenerated_components
    )
    assert first["components"][0]["component_id"] == regenerated["components"][0][
        "component_id"
    ]


@pytest.mark.parametrize(
    "field_mutation",
    [
        ("missing_provenance", lambda component: component.pop("base_cad_provenance_ref")),
        (
            "reused_without_provenance",
            lambda component: component.update(
                {"origin_class": "REUSED_UNCHANGED", "base_cad_provenance_ref": None}
            ),
        ),
        (
            "unknown_origin",
            lambda component: component.__setitem__("origin_class", "UNKNOWN"),
        ),
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


def test_snapshot_hash_uses_canonical_owner_and_rejects_tampered_seal() -> None:
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

    tampered = deepcopy(registry)
    tampered["components"][0]["candidate_entity_bindings"][0][
        "entity_handle"
    ] = "tampered-after-seal"
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(tampered, upstream_context=context)
    with pytest.raises(module.ComponentViewRegistryError):
        module.component_view_registry_sha256(tampered, upstream_context=context)

    changed_context = _remapped_candidate_context(context, candidate_handle="D4E5")
    changed_registry = module.build_component_view_registry(
        upstream_context=changed_context,
        components=_single_component(changed_context),
    )
    assert changed_registry["components"][0]["component_id"] == registry[
        "components"
    ][0]["component_id"]
    assert changed_registry["registry_snapshot_sha256"] != expected


def test_errors_are_categorical_and_privacy_safe() -> None:
    module = _registry_module()
    context = _upstream_context()
    component = _single_component(context)[0]
    sentinel = r"C:\customer\secret.dwg"
    component["private_path"] = sentinel
    with pytest.raises(module.ComponentViewRegistryError) as caught:
        module.build_component_view_registry(
            upstream_context=context, components=[component]
        )
    assert sentinel not in str(caught.value)
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
        "mcp_integration_lib",
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


def _task2_layout(
    layout_id: str,
    *,
    display_name: str,
    legacy_uuid: str,
    relative_path: str,
    captured_at_utc: str,
) -> dict[str, str]:
    return {
        "layout_id": layout_id,
        "display_name": display_name,
        "legacy_uuid": legacy_uuid,
        "relative_path": relative_path,
        "captured_at_utc": captured_at_utc,
    }


def _task2_view_inputs(module, context: dict[str, object]) -> list[dict[str, object]]:
    components = _component_inputs(context)
    task1 = module.build_component_view_registry(
        upstream_context=context, components=components
    )
    reused = next(
        item for item in task1["components"] if item["origin_class"] == "REUSED_UNCHANGED"
    )
    reconstructed = next(
        item for item in task1["components"] if item["origin_class"] == "RECONSTRUCTED_NEW"
    )
    semantic_ref = context["source_fusion"]["semantic_observations"][0][
        "observation_key"
    ]
    return [
        {
            "view_role": "PRIMARY",
            "component_ids": [reused["component_id"]],
            "source_projection_refs": list(reused["source_projection_refs"]),
            "semantic_projection_refs": [semantic_ref],
            "candidate_entity_bindings": deepcopy(reused["candidate_entity_bindings"]),
            "layout_bindings": [
                _task2_layout(
                    "layout-main",
                    display_name="Main Layout",
                    legacy_uuid="layout-uuid-a",
                    relative_path="layouts/main.dwg",
                    captured_at_utc="2026-08-10T00:00:00Z",
                )
            ],
        },
        {
            "view_role": "DETAIL",
            "component_ids": [reused["component_id"], reconstructed["component_id"]],
            "source_projection_refs": list(reconstructed["source_projection_refs"]),
            "semantic_projection_refs": [semantic_ref],
            "candidate_entity_bindings": deepcopy(reused["candidate_entity_bindings"]),
            "layout_bindings": [
                _task2_layout(
                    "layout-detail",
                    display_name="Detail Layout",
                    legacy_uuid="layout-uuid-b",
                    relative_path="layouts/detail.dwg",
                    captured_at_utc="2026-08-10T00:00:01Z",
                )
            ],
        },
    ]


def _task2_registry(module, context: dict[str, object]) -> dict[str, object]:
    components = _component_inputs(context)
    views = _task2_view_inputs(module, context)
    return module.build_component_view_registry(
        upstream_context=context,
        components=components,
        views=views,
    )


def _reseal_registry(registry: dict[str, object]) -> dict[str, object]:
    changed = deepcopy(registry)
    material = deepcopy(changed)
    material.pop("registry_snapshot_sha256", None)
    changed["registry_snapshot_sha256"] = canonical_json_sha256(material)
    return changed


def _view_by_role(registry: dict[str, object], role: str) -> dict[str, object]:
    return next(view for view in registry["views"] if view["view_role"] == role)


def test_task2_builds_closed_views_and_derives_all_closed_link_classes() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    assert registry["schema_version"] == SCHEMA_VERSION
    assert len(registry["views"]) == 2
    for view in registry["views"]:
        assert set(view) == {
            "view_id",
            "view_role",
            "component_ids",
            "source_projection_refs",
            "semantic_projection_refs",
            "candidate_entity_bindings",
            "layout_bindings",
        }
    assert {link["relation_type"] for link in registry["links"]} == {
        "COMPONENT_HAS_VIEW",
        "VIEWS_SHARE_COMPONENT",
        "VIEWS_SHARE_PARAMETER_EVIDENCE",
        "VIEW_PRESENTED_ON_LAYOUT",
    }
    for link in registry["links"]:
        assert set(link) == {
            "link_id",
            "relation_type",
            "source_id",
            "target_id",
            "evidence_refs",
        }


def test_task2_view_identity_ignores_handle_layout_display_uuid_time_path_and_order() -> None:
    module = _registry_module()
    first_context = _upstream_context()
    second_context = _remapped_candidate_context(
        first_context, candidate_handle="D4E5"
    )
    first = _task2_registry(module, first_context)
    second_views = _task2_view_inputs(module, second_context)
    for view in second_views:
        view["component_ids"] = list(reversed(view["component_ids"]))
        view["source_projection_refs"] = list(reversed(view["source_projection_refs"]))
        view["semantic_projection_refs"] = list(
            reversed(view["semantic_projection_refs"])
        )
        for layout in view["layout_bindings"]:
            layout["display_name"] = "Renamed volatile display"
            layout["legacy_uuid"] = "new-random-layout-uuid"
            layout["relative_path"] = "renamed/volatile-layout.dwg"
            layout["captured_at_utc"] = "2099-01-01T00:00:00Z"
    second = module.build_component_view_registry(
        upstream_context=second_context,
        components=list(reversed(_component_inputs(second_context))),
        views=list(reversed(second_views)),
    )
    assert {
        view["view_role"]: view["view_id"] for view in first["views"]
    } == {
        view["view_role"]: view["view_id"] for view in second["views"]
    }
    assert first["registry_snapshot_sha256"] != second["registry_snapshot_sha256"]


@pytest.mark.parametrize("mutation", ["role", "component", "projection"])
def test_task2_stable_membership_or_projection_mutation_changes_view_id(mutation: str) -> None:
    module = _registry_module()
    context = _upstream_context()
    components = _component_inputs(context)
    views = _task2_view_inputs(module, context)
    baseline = module.build_component_view_registry(
        upstream_context=context, components=components, views=views
    )
    baseline_primary = _view_by_role(baseline, "PRIMARY")
    changed_views = deepcopy(views)
    primary = next(view for view in changed_views if view["view_role"] == "PRIMARY")
    if mutation == "role":
        primary["view_role"] = "AUXILIARY"
    elif mutation == "component":
        task1 = module.build_component_view_registry(
            upstream_context=context, components=components
        )
        extra_component = next(
            item
            for item in task1["components"]
            if item["component_id"] not in primary["component_ids"]
        )
        primary["component_ids"].append(extra_component["component_id"])
    else:
        accepted = [
            item["observation_key"]
            for item in context["source_fusion"]["primitive_observations"]
        ]
        primary["source_projection_refs"] = [
            ref for ref in accepted if ref not in primary["source_projection_refs"]
        ][:1]
    changed = module.build_component_view_registry(
        upstream_context=context, components=components, views=changed_views
    )
    changed_primary = next(
        view
        for view in changed["views"]
        if view["view_role"] == primary["view_role"]
    )
    assert changed_primary["view_id"] != baseline_primary["view_id"]


def test_task2_component_ids_are_preserved_when_views_are_added() -> None:
    module = _registry_module()
    context = _upstream_context()
    task1 = module.build_component_view_registry(
        upstream_context=context, components=_component_inputs(context)
    )
    task2 = _task2_registry(module, context)
    assert sorted(component["component_id"] for component in task1["components"]) == sorted(
        component["component_id"] for component in task2["components"]
    )
    explicit_empty = module.build_component_view_registry(
        upstream_context=context,
        components=_component_inputs(context),
        views=[],
    )
    assert explicit_empty == task1


def test_task2_component_view_membership_and_component_has_view_links_are_exact() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    expected_pairs = {
        (component_id, view["view_id"])
        for view in registry["views"]
        for component_id in view["component_ids"]
    }
    actual_pairs = {
        (link["source_id"], link["target_id"])
        for link in registry["links"]
        if link["relation_type"] == "COMPONENT_HAS_VIEW"
    }
    assert actual_pairs == expected_pairs
    for component in registry["components"]:
        expected_view_ids = sorted(
            view["view_id"]
            for view in registry["views"]
            if component["component_id"] in view["component_ids"]
        )
        assert component["view_ids"] == expected_view_ids


def test_task2_permutations_are_byte_equivalent_and_hash_equal() -> None:
    module = _registry_module()
    context = _upstream_context()
    components = _component_inputs(context)
    views = _task2_view_inputs(module, context)
    first = module.build_component_view_registry(
        upstream_context=context, components=components, views=views
    )
    permuted = deepcopy(views)
    for view in permuted:
        view["component_ids"].reverse()
        view["source_projection_refs"].reverse()
        view["semantic_projection_refs"].reverse()
        view["candidate_entity_bindings"].reverse()
        view["layout_bindings"].reverse()
    second = module.build_component_view_registry(
        upstream_context=context,
        components=list(reversed(deepcopy(components))),
        views=list(reversed(permuted)),
    )
    assert first == second
    assert first["registry_snapshot_sha256"] == second["registry_snapshot_sha256"]


def test_task2_view_candidate_binding_must_belong_to_the_current_candidate_graph() -> None:
    module = _registry_module()
    context = _upstream_context()
    views = _task2_view_inputs(module, context)
    views[0]["candidate_entity_bindings"][0]["candidate_id"] = "foreign-candidate"
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


@pytest.mark.parametrize("attack", ["unknown_relation", "dangling", "duplicate", "self_link"])
def test_task2_link_attacks_fail_closed_even_after_caller_reseals(attack: str) -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    attacked = deepcopy(registry)
    if attack == "unknown_relation":
        attacked["links"][0]["relation_type"] = "CALLER_DEFINED_RELATION"
    elif attack == "dangling":
        attacked["links"][0]["target_id"] = "f" * 64
    elif attack == "duplicate":
        attacked["links"].append(deepcopy(attacked["links"][0]))
    else:
        shared = next(
            link
            for link in attacked["links"]
            if link["relation_type"] == "VIEWS_SHARE_COMPONENT"
        )
        shared["target_id"] = shared["source_id"]
    attacked = _reseal_registry(attacked)
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(attacked, upstream_context=context)


def test_task2_duplicate_or_foreign_view_membership_fails_closed() -> None:
    module = _registry_module()
    context = _upstream_context()
    views = _task2_view_inputs(module, context)
    views[0]["component_ids"].append(views[0]["component_ids"][0])
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )
    views = _task2_view_inputs(module, context)
    views[0]["component_ids"] = ["f" * 64]
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


def test_task2_internal_completeness_rejects_omitted_view_with_valid_self_hash() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    attacked = deepcopy(registry)
    attacked["views"] = attacked["views"][:-1]
    attacked = _reseal_registry(attacked)
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(attacked, upstream_context=context)


def test_task2_internal_completeness_rejects_unpaired_foreign_layout_binding() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    attacked = deepcopy(registry)
    attacked["views"][0]["layout_bindings"].append(
        _task2_layout(
            "layout-forged",
            display_name="Forged",
            legacy_uuid="forged-layout-uuid",
            relative_path="forged/layout.dwg",
            captured_at_utc="2099-01-01T00:00:00Z",
        )
    )
    attacked = _reseal_registry(attacked)
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(attacked, upstream_context=context)


def test_task2_impact_closure_is_complete_deterministic_and_explanatory() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    seed = next(
        component["component_id"]
        for component in registry["components"]
        if component["origin_class"] == "REUSED_UNCHANGED"
    )
    before = deepcopy(registry)
    impact = module.project_linked_view_impacts(
        registry=registry,
        component_ids=[seed],
        upstream_context=context,
    )
    assert registry == before
    assert set(impact) == {
        "component_ids",
        "view_ids",
        "layout_bindings",
        "link_ids",
    }
    assert impact["component_ids"] == sorted(
        component["component_id"] for component in registry["components"]
    )
    assert impact["view_ids"] == sorted(view["view_id"] for view in registry["views"])
    assert impact["layout_bindings"] == sorted(
        [
            deepcopy(layout)
            for view in registry["views"]
            for layout in view["layout_bindings"]
        ],
        key=lambda layout: layout["layout_id"],
    )
    assert impact["link_ids"] == sorted(link["link_id"] for link in registry["links"])
    replay = module.project_linked_view_impacts(
        registry=deepcopy(registry),
        component_ids=[seed],
        upstream_context=context,
    )
    assert replay == impact


def test_task2_impact_from_view_reaches_linked_components_and_views() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    primary = _view_by_role(registry, "PRIMARY")
    impact = module.project_linked_view_impacts(
        registry=registry,
        view_ids=[primary["view_id"]],
        upstream_context=context,
    )
    assert primary["view_id"] in impact["view_ids"]
    assert set(primary["component_ids"]).issubset(impact["component_ids"])
    assert impact["link_ids"]


@pytest.mark.parametrize(
    ("component_ids", "view_ids"),
    [(["f" * 64], []), ([], ["e" * 64]), ([], [])],
)
def test_task2_unknown_or_empty_impact_seeds_fail_closed(
    component_ids: list[str], view_ids: list[str]
) -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    with pytest.raises(module.ComponentViewRegistryError):
        module.project_linked_view_impacts(
            registry=registry,
            component_ids=component_ids,
            view_ids=view_ids,
            upstream_context=context,
        )


def test_task2_impact_output_never_becomes_visual_or_mutation_authority() -> None:
    module = _registry_module()
    context = _upstream_context()
    registry = _task2_registry(module, context)
    seed = registry["components"][0]["component_id"]
    impact = module.project_linked_view_impacts(
        registry=registry,
        component_ids=[seed],
        upstream_context=context,
    )
    rendered = repr(impact).casefold()
    for forbidden in (
        "region",
        "critical",
        "sheet_id",
        "acceptance_scope",
        "approval",
        "verdict",
        "revision",
        "repair",
        "publication",
        "publish",
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("field", "foreign_ref"),
    [
        ("source_projection_refs", "f" * 64),
        ("semantic_projection_refs", "e" * 64),
    ],
)
def test_task2_view_projection_membership_rejects_foreign_refs(
    field: str, foreign_ref: str
) -> None:
    module = _registry_module()
    context = _upstream_context()
    accepted = {
        item["observation_key"]
        for collection in ("primitive_observations", "semantic_observations")
        for item in context["source_fusion"][collection]
    }
    assert foreign_ref not in accepted
    views = _task2_view_inputs(module, context)
    views[0][field] = [foreign_ref]
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


@pytest.mark.parametrize("field", ["source_projection_refs", "semantic_projection_refs"])
def test_task2_view_projection_membership_rejects_duplicate_refs(field: str) -> None:
    module = _registry_module()
    context = _upstream_context()
    views = _task2_view_inputs(module, context)
    views[0][field].append(views[0][field][0])
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


def _task2_discriminating_context() -> dict[str, object]:
    context = _upstream_context()
    source_fusion_tests = _existing_test_module("test_cad_agent_source_fusion.py")
    source_fusion = importlib.import_module("cad_agent.source_fusion")
    primitive_ids = ("prim-a", "prim-b")
    primitive_artifact = source_fusion_tests._task5_primitive_artifact(
        [
            source_fusion_tests._task5_primitive(primitive_ids[0]),
            source_fusion_tests._task5_primitive(primitive_ids[1], end_x=20.0),
        ]
    )
    primitive_observations = source_fusion_tests._task5_project_primitive(
        primitive_artifact
    )
    semantic_artifact = source_fusion_tests._task5_semantic_artifact(
        primitive_ids=[primitive_ids[0]],
        primitive_count=2,
        part_id="part-a",
        constraint_id="cst-a",
    )
    second_part = deepcopy(semantic_artifact["parts"][0])
    second_part["id"] = "part-b"
    second_part["primitive_ids"] = [primitive_ids[1]]
    semantic_artifact["parts"].append(second_part)
    semantic_observations = source_fusion_tests._task5_project_semantic(
        semantic_artifact, primitive_observations
    )
    assert len(semantic_observations) == 2
    fusion_inputs = source_fusion_tests._task6_ready_inputs(
        primitive_observations=primitive_observations,
        semantic_observations=semantic_observations,
    )
    fusion = source_fusion.build_source_fusion_packet(**fusion_inputs)
    validated_fusion = source_fusion.validate_source_fusion_packet(fusion)
    fusion_sha256 = source_fusion.source_fusion_sha256(validated_fusion)
    context["source_fusion"] = validated_fusion
    context["source_fusion_sha256"] = fusion_sha256
    handoff = deepcopy(context["reuse_handoff"])
    handoff["source_bundle_sha256"] = validated_fusion["source_bundle_sha256"]
    handoff["source_custody_sha256"] = validated_fusion["source_custody_sha256"]
    handoff["source_fusion_sha256"] = fusion_sha256
    return _replace_handoff(context, handoff)


def _task2_discriminating_views(
    module, context: dict[str, object]
) -> list[dict[str, object]]:
    components = _component_inputs(context)
    task1 = module.build_component_view_registry(
        upstream_context=context, components=components
    )
    reused = next(
        item for item in task1["components"] if item["origin_class"] == "REUSED_UNCHANGED"
    )
    reconstructed = next(
        item for item in task1["components"] if item["origin_class"] == "RECONSTRUCTED_NEW"
    )
    semantic_refs = [
        item["observation_key"]
        for item in context["source_fusion"]["semantic_observations"]
    ]
    assert len(semantic_refs) == 2
    return [
        {
            "view_role": "PRIMARY",
            "component_ids": [reused["component_id"]],
            "source_projection_refs": list(reused["source_projection_refs"]),
            "semantic_projection_refs": [semantic_refs[0]],
            "candidate_entity_bindings": deepcopy(reused["candidate_entity_bindings"]),
            "layout_bindings": [
                _task2_layout(
                    "layout-main",
                    display_name="Main Layout",
                    legacy_uuid="layout-uuid-a",
                    relative_path="layouts/main.dwg",
                    captured_at_utc="2026-08-10T00:00:00Z",
                )
            ],
        },
        {
            "view_role": "DETAIL",
            "component_ids": [reused["component_id"], reconstructed["component_id"]],
            "source_projection_refs": list(reconstructed["source_projection_refs"]),
            "semantic_projection_refs": [semantic_refs[0]],
            "candidate_entity_bindings": deepcopy(reused["candidate_entity_bindings"]),
            "layout_bindings": [
                _task2_layout(
                    "layout-detail",
                    display_name="Detail Layout",
                    legacy_uuid="layout-uuid-b",
                    relative_path="layouts/detail.dwg",
                    captured_at_utc="2026-08-10T00:00:01Z",
                )
            ],
        },
        {
            "view_role": "ISOLATED",
            "component_ids": [reconstructed["component_id"]],
            "source_projection_refs": list(reconstructed["source_projection_refs"]),
            "semantic_projection_refs": [semantic_refs[1]],
            "candidate_entity_bindings": [],
            "layout_bindings": [
                _task2_layout(
                    "layout-isolated",
                    display_name="Isolated Layout",
                    legacy_uuid="layout-uuid-c",
                    relative_path="layouts/isolated.dwg",
                    captured_at_utc="2026-08-10T00:00:02Z",
                )
            ],
        },
    ]


def test_task2_derived_links_exist_iff_the_relationship_exists() -> None:
    module = _registry_module()
    context = _task2_discriminating_context()
    components = _component_inputs(context)
    registry = module.build_component_view_registry(
        upstream_context=context,
        components=components,
        views=_task2_discriminating_views(module, context),
    )
    by_role = {view["view_role"]: view for view in registry["views"]}
    primary = by_role["PRIMARY"]
    detail = by_role["DETAIL"]
    isolated = by_role["ISOLATED"]

    expected_component_edges = {
        (component_id, view["view_id"])
        for view in registry["views"]
        for component_id in view["component_ids"]
    }
    actual_component_edges = {
        (link["source_id"], link["target_id"])
        for link in registry["links"]
        if link["relation_type"] == "COMPONENT_HAS_VIEW"
    }
    assert actual_component_edges == expected_component_edges

    expected_shared_component_pairs = {
        frozenset((primary["view_id"], detail["view_id"])),
        frozenset((detail["view_id"], isolated["view_id"])),
    }
    actual_shared_component_pairs = {
        frozenset((link["source_id"], link["target_id"]))
        for link in registry["links"]
        if link["relation_type"] == "VIEWS_SHARE_COMPONENT"
    }
    assert actual_shared_component_pairs == expected_shared_component_pairs
    assert frozenset((primary["view_id"], isolated["view_id"])) not in (
        actual_shared_component_pairs
    )

    expected_shared_evidence_pairs = {
        frozenset((primary["view_id"], detail["view_id"]))
    }
    parameter_links = [
        link
        for link in registry["links"]
        if link["relation_type"] == "VIEWS_SHARE_PARAMETER_EVIDENCE"
    ]
    actual_shared_evidence_pairs = {
        frozenset((link["source_id"], link["target_id"]))
        for link in parameter_links
    }
    assert actual_shared_evidence_pairs == expected_shared_evidence_pairs
    assert frozenset((primary["view_id"], isolated["view_id"])) not in (
        actual_shared_evidence_pairs
    )
    assert frozenset((detail["view_id"], isolated["view_id"])) not in (
        actual_shared_evidence_pairs
    )
    views_by_id = {view["view_id"]: view for view in registry["views"]}
    for link in parameter_links:
        left = views_by_id[link["source_id"]]
        right = views_by_id[link["target_id"]]
        expected_evidence = sorted(
            set(left["semantic_projection_refs"])
            & set(right["semantic_projection_refs"])
        )
        assert expected_evidence
        assert link["evidence_refs"] == expected_evidence

    expected_layout_edges = {
        (view["view_id"], layout["layout_id"])
        for view in registry["views"]
        for layout in view["layout_bindings"]
    }
    actual_layout_edges = {
        (link["source_id"], link["target_id"])
        for link in registry["links"]
        if link["relation_type"] == "VIEW_PRESENTED_ON_LAYOUT"
    }
    assert actual_layout_edges == expected_layout_edges


def test_task2_overlinked_closed_relation_is_rejected_after_reseal() -> None:
    module = _registry_module()
    context = _task2_discriminating_context()
    registry = module.build_component_view_registry(
        upstream_context=context,
        components=_component_inputs(context),
        views=_task2_discriminating_views(module, context),
    )
    primary = _view_by_role(registry, "PRIMARY")
    isolated = _view_by_role(registry, "ISOLATED")
    assert set(primary["component_ids"]).isdisjoint(isolated["component_ids"])
    attacked = deepcopy(registry)
    attacked["links"].append(
        {
            "link_id": "f" * 64,
            "relation_type": "VIEWS_SHARE_COMPONENT",
            "source_id": primary["view_id"],
            "target_id": isolated["view_id"],
            "evidence_refs": [],
        }
    )
    attacked = _reseal_registry(attacked)
    with pytest.raises(module.ComponentViewRegistryError):
        module.validate_component_view_registry(attacked, upstream_context=context)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sheet_id", "sheet-forged"),
        ("region_id", "region-forged"),
        ("criticality", "CRITICAL"),
        ("visual_review_scope", ["region-forged"]),
        ("acceptance_scope", ["view-forged"]),
        ("verdict", "PASS"),
        ("approval", "APPROVED"),
        ("unknown_authority", {"owner": "caller"}),
    ],
)
def test_task2_nested_layout_authority_injection_fails_closed(
    field: str, value: object
) -> None:
    module = _registry_module()
    context = _upstream_context()
    views = _task2_view_inputs(module, context)
    views[0]["layout_bindings"][0][field] = value
    with pytest.raises(module.ComponentViewRegistryError):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


def test_task2_nested_layout_privacy_injection_is_rejected_without_echo() -> None:
    module = _registry_module()
    context = _upstream_context()
    views = _task2_view_inputs(module, context)
    sentinel = r"C:\customer\private\secret-layout.dwg"
    views[0]["layout_bindings"][0]["acceptance_scope"] = {
        "region_id": "region-forged",
        "private_path": sentinel,
    }
    with pytest.raises(module.ComponentViewRegistryError) as caught:
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )
    assert sentinel not in str(caught.value)
    assert "secret-layout.dwg" not in str(caught.value)


def test_task2_view_source_projection_rejects_accepted_semantic_key() -> None:
    module = _registry_module()
    context = _upstream_context()
    semantic_key = context["source_fusion"]["semantic_observations"][0][
        "observation_key"
    ]
    primitive_keys = {
        item["observation_key"]
        for item in context["source_fusion"]["primitive_observations"]
    }
    assert semantic_key not in primitive_keys
    views = _task2_view_inputs(module, context)
    views[0]["source_projection_refs"] = [semantic_key]
    with pytest.raises(
        module.ComponentViewRegistryError, match="FOREIGN_SOURCE_PROJECTION"
    ):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


def test_task2_view_semantic_projection_rejects_accepted_primitive_key() -> None:
    module = _registry_module()
    context = _upstream_context()
    primitive_key = context["source_fusion"]["primitive_observations"][0][
        "observation_key"
    ]
    semantic_keys = {
        item["observation_key"]
        for item in context["source_fusion"]["semantic_observations"]
    }
    assert primitive_key not in semantic_keys
    views = _task2_view_inputs(module, context)
    views[0]["semantic_projection_refs"] = [primitive_key]
    with pytest.raises(
        module.ComponentViewRegistryError, match="FOREIGN_SEMANTIC_PROJECTION"
    ):
        module.build_component_view_registry(
            upstream_context=context,
            components=_component_inputs(context),
            views=views,
        )


# R3 Task3 Gate0: the registry remains the R3 correspondence/provenance owner.
# These fixtures intentionally use synthetic bytes and the accepted local DARA
# contract; no provider, workspace, AutoCAD, or publication surface is involved.
TASK3_RESULT_FIELDS = frozenset(
    {
        "parent_reference_id",
        "parent_reference_sha256",
        "child_reference_id",
        "child_reference_sha256",
        "registry_snapshot_sha256",
        "provenance_sha256",
        "component_bindings",
        "view_bindings",
    }
)
TASK3_COMPONENT_BINDING_FIELDS = frozenset({"component_id", "record_sha256"})
TASK3_VIEW_BINDING_FIELDS = frozenset({"view_id", "record_sha256"})


def _task3_record_bindings(
    registry: dict[str, object],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    component_bindings = [
        {
            "component_id": str(component["component_id"]),
            "record_sha256": canonical_json_sha256(component),
        }
        for component in registry["components"]
    ]
    view_bindings = [
        {
            "view_id": str(view["view_id"]),
            "record_sha256": canonical_json_sha256(view),
        }
        for view in registry["views"]
    ]
    return component_bindings, view_bindings


def _task3_provenance_material(
    registry: dict[str, object],
) -> dict[str, object]:
    component_bindings, view_bindings = _task3_record_bindings(registry)
    return {
        "identity_kind": "r3-component-view-registry-provenance-v1",
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "component_bindings": component_bindings,
        "view_bindings": view_bindings,
    }


def _task3_binding(registry: dict[str, object]) -> dict[str, object]:
    snapshot_sha256 = registry["registry_snapshot_sha256"]
    return {
        "registry_snapshot_sha256": snapshot_sha256,
        "provenance_sha256": canonical_json_sha256(
            _task3_provenance_material(registry)
        ),
    }


def _task3_material() -> dict[str, object]:
    registry_module = _registry_module()
    context = _upstream_context()
    registry = registry_module.build_component_view_registry(
        upstream_context=context,
        components=_component_inputs(context),
        views=_task2_view_inputs(registry_module, context),
    )

    dara = importlib.import_module("cad_agent.drawing_artifact_reference")
    dara_tests = _existing_test_module("test_cad_agent_drawing_artifact_reference.py")
    binding = _task3_binding(registry)
    parent_artifact_bytes = b"synthetic-r3-parent-artifact"
    child_artifact_bytes = b"synthetic-r3-repaired-child-artifact"
    parent = dara.issue_drawing_artifact_reference(
        run_id="run-180-001",
        project_id="project-180-001",
        drawing_id="drawing-180-001",
        artifact_role="R3_CANDIDATE",
        artifact_bytes=parent_artifact_bytes,
        upstream_evidence=dara_tests._r3_candidate_evidence(),
        r3_provenance_binding=binding,
    )
    transition = dara_tests._mutation_evidence(
        candidate_reference=parent,
        pre_sha256=parent["artifact_sha256"],
        post_sha256=hashlib.sha256(child_artifact_bytes).hexdigest(),
    )
    dara_tests._seal_mutation_evidence(transition)
    child = dara.issue_drawing_artifact_reference(
        run_id=parent["run_id"],
        project_id=parent["project_id"],
        drawing_id=parent["drawing_id"],
        artifact_role="R3_CANDIDATE",
        artifact_bytes=child_artifact_bytes,
        upstream_evidence=transition,
        parent_reference=parent,
        r3_provenance_binding=binding,
    )
    parent_observation = dara.observe_drawing_artifact_currentness(
        reference=parent,
        artifact_bytes=parent_artifact_bytes,
        observation_evidence_sha256="1" * 64,
    )
    child_observation = dara.observe_drawing_artifact_currentness(
        reference=child,
        artifact_bytes=child_artifact_bytes,
        observation_evidence_sha256="2" * 64,
        parent_reference=parent,
        accepted_transition_evidence_sha256=transition[
            "accepted_transition_evidence_sha256"
        ],
    )
    component_bindings, view_bindings = _task3_record_bindings(registry)
    return {
        "context": context,
        "registry": registry,
        "parent": parent,
        "child": child,
        "parent_artifact_bytes": parent_artifact_bytes,
        "child_artifact_bytes": child_artifact_bytes,
        "parent_observation": parent_observation,
        "child_observation": child_observation,
        "transition": transition,
        "binding": binding,
        "component_bindings": component_bindings,
        "view_bindings": view_bindings,
        "provenance_material": _task3_provenance_material(registry),
    }


def _task3_finalize(
    material: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    module = _registry_module()
    finalizer = getattr(module, "finalize_component_view_correspondence", None)
    assert callable(
        finalizer
    ), "R3 Task3 finalizer is omitted from component_view_registry.py"
    values = {
        "registry": material["registry"],
        "upstream_context": material["context"],
        "parent_reference": material["parent"],
        "parent_observation": material["parent_observation"],
        "parent_artifact_bytes": material["parent_artifact_bytes"],
        "child_reference": material["child"],
        "child_observation": material["child_observation"],
        "child_artifact_bytes": material["child_artifact_bytes"],
        "accepted_transition_evidence_sha256": material["transition"][
            "accepted_transition_evidence_sha256"
        ],
    }
    values.update(overrides)
    return finalizer(**values)


def test_task3_public_surface_preserves_task2_and_adds_r3_correspondence_gate() -> None:
    module = _registry_module()
    assert list(inspect.signature(module.build_component_view_registry).parameters) == [
        "upstream_context",
        "components",
        "views",
    ]
    assert list(inspect.signature(module.validate_component_view_registry).parameters) == [
        "payload",
        "upstream_context",
    ]
    assert callable(getattr(module, "finalize_component_view_correspondence", None))
    wildcard_namespace: dict[str, object] = {}
    exec("from cad_agent.component_view_registry import *", wildcard_namespace)
    assert (
        wildcard_namespace["finalize_component_view_correspondence"]
        is module.finalize_component_view_correspondence
    )


def test_task3_finalizes_deterministic_correspondence_against_immutable_parent() -> None:
    material = _task3_material()
    parent_before = deepcopy(material["parent"])
    first = _task3_finalize(material)
    second = _task3_finalize(material)

    assert first == second
    assert first["parent_reference_id"] == material["parent"]["reference_id"]
    assert first["parent_reference_sha256"] == material["parent"]["reference_sha256"]
    assert first["child_reference_id"] == material["child"]["reference_id"]
    assert first["child_reference_sha256"] == material["child"]["reference_sha256"]
    assert first["registry_snapshot_sha256"] == material["registry"][
        "registry_snapshot_sha256"
    ]
    assert material["parent"] == parent_before


def test_task3_result_is_closed_and_binds_every_component_and_view_record() -> None:
    material = _task3_material()
    result = _task3_finalize(material)

    assert set(result) == TASK3_RESULT_FIELDS
    assert result["component_bindings"] == material["component_bindings"]
    assert result["view_bindings"] == material["view_bindings"]
    assert result["component_bindings"]
    assert result["view_bindings"]
    assert all(
        set(binding) == TASK3_COMPONENT_BINDING_FIELDS
        for binding in result["component_bindings"]
    )
    assert all(
        set(binding) == TASK3_VIEW_BINDING_FIELDS
        for binding in result["view_bindings"]
    )
    assert result["provenance_sha256"] == canonical_json_sha256(
        material["provenance_material"]
    )


@pytest.mark.parametrize(
    "mutation", ["omit_component", "omit_view", "duplicate_component"]
)
def test_task3_omitted_or_ambiguous_registry_records_fail_closed(
    mutation: str,
) -> None:
    material = _task3_material()
    forged_registry = deepcopy(material["registry"])
    if mutation == "omit_component":
        forged_registry["components"] = forged_registry["components"][1:]
    elif mutation == "omit_view":
        forged_registry["views"] = forged_registry["views"][1:]
    else:
        forged_registry["components"].append(
            deepcopy(forged_registry["components"][0])
        )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, registry=forged_registry)
    assert str(caught.value) in {
        "REGISTRY_SNAPSHOT_MISMATCH",
        "DUPLICATE_COMPONENT",
        "COMPONENT_VIEW_IDS_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_provenance_seal_uses_the_canonical_json_sha256_owner(monkeypatch) -> None:
    material = _task3_material()
    module = _registry_module()
    calls: list[object] = []
    owner = module.canonical_json_sha256

    def record(payload: object) -> str:
        calls.append(payload)
        return owner(payload)

    monkeypatch.setattr(module, "canonical_json_sha256", record)
    _task3_finalize(material)
    assert calls


def test_task3_finalizer_delegates_reference_and_currentness_authority_to_dara(
    monkeypatch,
) -> None:
    material = _task3_material()
    dara = importlib.import_module("cad_agent.drawing_artifact_reference")
    calls: list[str] = []
    validate_reference = dara.validate_drawing_artifact_reference
    require_current = dara.require_current_drawing_artifact_reference

    def record_reference(*args, **kwargs):
        calls.append("validate_drawing_artifact_reference")
        return validate_reference(*args, **kwargs)

    def record_current(*args, **kwargs):
        calls.append("require_current_drawing_artifact_reference")
        return require_current(*args, **kwargs)

    monkeypatch.setattr(
        dara, "validate_drawing_artifact_reference", record_reference
    )
    monkeypatch.setattr(
        dara, "require_current_drawing_artifact_reference", record_current
    )
    _task3_finalize(material)
    assert calls.count("validate_drawing_artifact_reference") >= 2
    assert calls.count("require_current_drawing_artifact_reference") >= 2


def test_task3_provenance_sha256_is_recomputed_and_caller_claims_are_rejected() -> None:
    material = _task3_material()
    forged_child = deepcopy(material["child"])
    forged_child["r3_provenance_binding"]["provenance_sha256"] = "f" * 64
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_reference(
        forged_child
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=forged_child)
    assert str(caught.value) in {
        "PROVENANCE_MISMATCH",
        "CANONICAL_HASH_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("run_id", "run-foreign"),
        ("project_id", "project-foreign"),
        ("drawing_id", "drawing-foreign"),
    ],
)
def test_task3_foreign_scope_is_categorical_and_privacy_safe(
    field: str, replacement: str
) -> None:
    material = _task3_material()
    foreign_child = deepcopy(material["child"])
    foreign_child[field] = replacement
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_reference(
        foreign_child
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=foreign_child)
    assert str(caught.value) in {"SCOPE_MISMATCH", "FOREIGN_REFERENCE", "CORRESPONDENCE_MISMATCH"}
    assert replacement not in str(caught.value)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("artifact_role", "BASELINE"),
        ("parent_reference_id", "dara-ref-foreign-parent"),
        ("parent_reference_sha256", "f" * 64),
    ],
)
def test_task3_wrong_role_or_parent_binding_fails_closed(
    field: str, replacement: object
) -> None:
    material = _task3_material()
    forged_child = deepcopy(material["child"])
    forged_child[field] = replacement
    dara_tests = _existing_test_module("test_cad_agent_drawing_artifact_reference.py")
    dara_tests._reseal_reference(forged_child)
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=forged_child)
    assert str(caught.value) in {
        "CATEGORY_CONFUSION",
        "PARENT_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


@pytest.mark.parametrize("target", ["parent", "child"])
def test_task3_baseline_role_cannot_enter_the_r3_parent_child_correspondence(
    target: str,
) -> None:
    material = _task3_material()
    forged = deepcopy(material[target])
    forged["artifact_role"] = "BASELINE"
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_reference(
        forged
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, **{f"{target}_reference": forged})
    assert str(caught.value) in {
        "CATEGORY_CONFUSION",
        "PARENT_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_stale_parent_binding_cannot_be_reused_for_repaired_child() -> None:
    material = _task3_material()
    forged_child = deepcopy(material["child"])
    forged_child["r3_provenance_binding"] = {
        "registry_snapshot_sha256": "f" * 64,
        "provenance_sha256": "e" * 64,
    }
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_reference(
        forged_child
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=forged_child)
    assert str(caught.value) in {"STALE_PARENT_BINDING", "PROVENANCE_MISMATCH", "CORRESPONDENCE_MISMATCH"}


@pytest.mark.parametrize(
    ("field", "replacement", "expected"),
    [
        ("pre_artifact_sha256", "f" * 64, "MUTATION_EVIDENCE_MISMATCH"),
        ("post_artifact_sha256", "e" * 64, "POST_ARTIFACT_MISMATCH"),
    ],
)
def test_task3_transition_sha_bindings_must_match_parent_and_child(
    field: str, replacement: str, expected: str
) -> None:
    material = _task3_material()
    forged_child = deepcopy(material["child"])
    transition = forged_child["upstream_evidence"]
    transition[field] = replacement
    dara_tests = _existing_test_module("test_cad_agent_drawing_artifact_reference.py")
    dara_tests._seal_mutation_evidence(transition)
    dara_tests._reseal_reference(forged_child)
    overrides = {"child_reference": forged_child}
    if field == "post_artifact_sha256":
        overrides["accepted_transition_evidence_sha256"] = transition[
            "accepted_transition_evidence_sha256"
        ]
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, **overrides)
    assert str(caught.value) in {expected, "CORRESPONDENCE_MISMATCH"}


def test_task3_wrong_accepted_transition_digest_is_not_authority() -> None:
    material = _task3_material()
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, accepted_transition_evidence_sha256="f" * 64)
    assert str(caught.value) in {"MUTATION_EVIDENCE_MISMATCH", "CORRESPONDENCE_MISMATCH"}


def test_task3_missing_parent_is_not_treated_as_a_fresh_correspondence() -> None:
    material = _task3_material()
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, parent_reference=None)
    assert str(caught.value) in {
        "PARENT_MISMATCH",
        "MISSING_PARENT",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_parent_child_reference_swap_is_rejected() -> None:
    material = _task3_material()
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(
            material,
            parent_reference=material["child"],
            child_reference=material["parent"],
        )
    assert str(caught.value) in {
        "CATEGORY_CONFUSION",
        "PARENT_MISMATCH",
        "REPLAY_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_unsealed_transition_mutation_is_rejected_by_dara() -> None:
    material = _task3_material()
    forged_child = deepcopy(material["child"])
    forged_child["upstream_evidence"]["executor_result_sha256"] = "f" * 64
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=forged_child)
    assert str(caught.value) in {
        "MUTATION_EVIDENCE_MISMATCH",
        "CANONICAL_HASH_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


@pytest.mark.parametrize(
    "observation_field",
    ["parent_observation", "child_observation"],
)
def test_task3_stale_or_replayed_current_observation_is_refused(
    observation_field: str,
) -> None:
    material = _task3_material()
    replayed = material["parent_observation"]
    if observation_field == "parent_observation":
        overrides = {"parent_observation": material["child_observation"]}
    else:
        overrides = {"child_observation": replayed}
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, **overrides)
    assert str(caught.value) in {
        "STALE_REFERENCE",
        "REPLAY_MISMATCH",
        "SCOPE_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_owner_observed_bytes_are_recomputed_and_alteration_is_stale() -> None:
    material = _task3_material()
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(
            material,
            child_artifact_bytes=b"synthetic-r3-repaired-child-artifact-altered",
        )
    assert str(caught.value) in {"STALE_REFERENCE", "ARTIFACT_SHA_MISMATCH", "CORRESPONDENCE_MISMATCH"}


def test_task3_caller_resealed_current_observation_cannot_override_owner_bytes() -> None:
    material = _task3_material()
    forged_observation = deepcopy(material["child_observation"])
    forged_observation["expected_artifact_sha256"] = "f" * 64
    forged_observation["observed_artifact_sha256"] = "f" * 64
    forged_observation["comparison"] = "CURRENT"
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_current_observation(
        forged_observation
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(
            material,
            child_observation=forged_observation,
            child_artifact_bytes=b"caller-resealed-but-not-owner-observed",
        )
    assert str(caught.value) in {
        "STALE_REFERENCE",
        "CURRENTNESS_FORGED",
        "REPLAY_MISMATCH",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_replayed_observation_after_transition_evidence_changes_is_rejected() -> None:
    material = _task3_material()
    dara_tests = _existing_test_module("test_cad_agent_drawing_artifact_reference.py")
    replayed_child = deepcopy(material["child"])
    changed_transition = deepcopy(replayed_child["upstream_evidence"])
    changed_transition["executor_result_sha256"] = "f" * 64
    dara_tests._seal_mutation_evidence(changed_transition)
    replayed_child["upstream_evidence"] = changed_transition
    dara_tests._reseal_reference(replayed_child)
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(
            material,
            child_reference=replayed_child,
            accepted_transition_evidence_sha256=changed_transition[
                "accepted_transition_evidence_sha256"
            ],
        )
    assert str(caught.value) in {
        "REPLAY_MISMATCH",
        "SCOPE_MISMATCH",
        "CURRENTNESS_FORGED",
        "CORRESPONDENCE_MISMATCH",
    }


def test_task3_cross_registry_binding_replay_is_rejected() -> None:
    material = _task3_material()
    other_context = _upstream_context(primitive_ids=("foreign-a", "foreign-b"))
    other_registry = _registry_module().build_component_view_registry(
        upstream_context=other_context,
        components=_component_inputs(other_context),
        views=_task2_view_inputs(_registry_module(), other_context),
    )
    replayed_child = deepcopy(material["child"])
    replayed_child["r3_provenance_binding"]["registry_snapshot_sha256"] = other_registry[
        "registry_snapshot_sha256"
    ]
    _existing_test_module("test_cad_agent_drawing_artifact_reference.py")._reseal_reference(
        replayed_child
    )
    with pytest.raises(_registry_module().ComponentViewRegistryError) as caught:
        _task3_finalize(material, child_reference=replayed_child)
    assert str(caught.value) in {"PROVENANCE_MISMATCH", "CROSS_REGISTRY_REPLAY", "CORRESPONDENCE_MISMATCH"}


def test_task3_dara_currentness_cannot_mint_r3_registry_current_or_r4_selection() -> None:
    material = _task3_material()
    result = _task3_finalize(material)
    forbidden_authority_fields = {
        "registry_current",
        "current_authority",
        "r4_selected",
        "r4_current",
        "selection_authority",
    }
    assert forbidden_authority_fields.isdisjoint(result)
    source = Path(_registry_module().__file__).read_text(encoding="utf-8")
    for forbidden in ("r4_selected", "selection_authority", "current_authority"):
        assert forbidden not in source


# R3 public-seam RED (Issue #273): the existing Task3 provenance material is
# canonical R3-owned behavior.  The follow-up GREEN must expose that behavior
# through one public importable/exported seam that validates the exact upstream
# context, returns owner-derived provenance evidence, and never lets a caller
# copy or mint a second provenance/hash authority.  These tests are intentionally
# RED on current main because that seam does not exist yet.
TASK4_PUBLIC_PROVENANCE_NAME = "component_view_registry_provenance_evidence"
TASK4_RESULT_FIELDS = frozenset(
    {
        "identity_kind",
        "registry_snapshot_sha256",
        "provenance_sha256",
        "component_bindings",
        "view_bindings",
    }
)


def _task4_public_provenance(material: dict[str, object]) -> object:
    module = _registry_module()
    public = getattr(module, TASK4_PUBLIC_PROVENANCE_NAME, None)
    assert callable(
        public
    ), "R3 public provenance-evidence seam is missing from component_view_registry.py"
    return public(material["registry"], upstream_context=material["context"])


def test_task4_public_provenance_evidence_is_importable_and_exported() -> None:
    module = _registry_module()
    public = getattr(module, TASK4_PUBLIC_PROVENANCE_NAME, None)
    assert callable(public)
    assert list(inspect.signature(public).parameters) == [
        "registry",
        "upstream_context",
    ]
    assert inspect.signature(public).parameters["upstream_context"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )
    assert TASK4_PUBLIC_PROVENANCE_NAME in module.__all__
    wildcard_namespace: dict[str, object] = {}
    exec("from cad_agent.component_view_registry import *", wildcard_namespace)
    assert wildcard_namespace[TASK4_PUBLIC_PROVENANCE_NAME] is public


def test_task4_public_provenance_evidence_is_closed_and_owner_derived() -> None:
    material = _task3_material()
    result = _task4_public_provenance(material)

    assert set(result) == TASK4_RESULT_FIELDS
    assert result["identity_kind"] == material["provenance_material"]["identity_kind"]
    assert result["registry_snapshot_sha256"] == material["registry"][
        "registry_snapshot_sha256"
    ]
    assert result["component_bindings"] == material["component_bindings"]
    assert result["view_bindings"] == material["view_bindings"]
    assert result["provenance_sha256"] == canonical_json_sha256(
        material["provenance_material"]
    )


def test_task4_public_provenance_evidence_reuses_private_owner_not_a_copied_recipe(
    monkeypatch,
) -> None:
    material = _task3_material()
    module = _registry_module()
    owner = getattr(module, "_task3_provenance_material", None)
    assert callable(owner)
    calls: list[dict[str, object]] = []

    def record(registry: dict[str, object]) -> dict[str, object]:
        calls.append(registry)
        return owner(registry)

    monkeypatch.setattr(module, "_task3_provenance_material", record)
    _task4_public_provenance(material)
    assert calls
    assert calls[0] is not material["registry"]


def test_task4_public_provenance_evidence_is_deterministic_detached_and_non_mutating() -> None:
    material = _task3_material()
    registry_before = deepcopy(material["registry"])
    first = _task4_public_provenance(material)
    second = _task4_public_provenance(material)

    assert first == second
    first["component_bindings"][0]["component_id"] = "caller-forged"
    replay = _task4_public_provenance(material)
    assert material["registry"] == registry_before
    assert replay["component_bindings"][0]["component_id"] != "caller-forged"


@pytest.mark.parametrize("context_factory", [
    lambda context: _upstream_context(primitive_ids=("foreign-a", "foreign-b")),
    lambda context: _remapped_candidate_context(context, candidate_handle="FOREIGN"),
    lambda context: _disconnected_r2_lineage_context(
        context, field="source_fusion_sha256"
    ),
    lambda context: dict(deepcopy(context), source_fusion_sha256="f" * 64),
])
def test_task4_public_provenance_evidence_rejects_foreign_or_stale_upstream_context(
    context_factory,
) -> None:
    material = _task3_material()
    bad_context = context_factory(material["context"])
    module = _registry_module()
    public = getattr(module, TASK4_PUBLIC_PROVENANCE_NAME, None)
    assert callable(public)
    with pytest.raises(module.ComponentViewRegistryError):
        public(material["registry"], upstream_context=bad_context)


def test_task4_public_provenance_evidence_rejects_registry_snapshot_cross_binding() -> None:
    material = _task3_material()
    forged_registry = deepcopy(material["registry"])
    forged_registry["registry_snapshot_sha256"] = "f" * 64
    module = _registry_module()
    public = getattr(module, TASK4_PUBLIC_PROVENANCE_NAME, None)
    assert callable(public)
    with pytest.raises(module.ComponentViewRegistryError):
        public(forged_registry, upstream_context=material["context"])
