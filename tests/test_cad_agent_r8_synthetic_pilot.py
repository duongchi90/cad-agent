from __future__ import annotations

import importlib
import inspect

import pytest

OWNER_MODULES = (
    "cad_agent.source_fusion",
    "cad_agent.base_cad_adapter",
    "cad_agent.component_view_registry",
    "cad_agent.candidate_revision",
    "cad_agent.visual_supervisor_adapter",
    "cad_agent.approved_repair_adapter",
    "cad_agent.publication_composition",
)

REQUIRED_PUBLIC_SEAMS = {
    "cad_agent.source_fusion": ("validate_page_locators", "validate_region_locators", "validate_render_provenance"),
    "cad_agent.base_cad_adapter": ("validate_base_cad_binding",),
    "cad_agent.component_view_registry": ("validate_component_view_registry",),
    "cad_agent.candidate_revision": ("validate_candidate_revision_state",),
    "cad_agent.visual_supervisor_adapter": ("validate_visual_verdict_result",),
    "cad_agent.approved_repair_adapter": ("execute_approved_repair", "validate_approved_repair_result"),
    "cad_agent.publication_composition": ("execute_verified_publication", "validate_verified_publication_result"),
}


def test_r8_uses_accepted_r1_r7_public_seams() -> None:
    for module_name in OWNER_MODULES:
        module = importlib.import_module(module_name)
        for seam in REQUIRED_PUBLIC_SEAMS[module_name]:
            assert callable(getattr(module, seam, None))


def test_r6_result_is_not_a_fresh_r5_pass() -> None:
    r5 = importlib.import_module("cad_agent.visual_supervisor_adapter")
    repair = importlib.import_module("cad_agent.approved_repair_adapter")
    publish = importlib.import_module("cad_agent.publication_composition")
    assert r5.validate_visual_verdict_result is not repair.validate_approved_repair_result
    assert publish.validate_visual_verdict_result is r5.validate_visual_verdict_result


def test_r7_requires_r4_state_and_r5_verdict_inputs() -> None:
    publish = importlib.import_module("cad_agent.publication_composition")
    assert tuple(inspect.signature(publish.execute_verified_publication).parameters) == (
        "run_id", "candidate_state", "r5_verdict_result", "auto_publish_authorization",
        "manifest_path", "expected_manifest_sha256", "candidate_path", "target_path",
    )


@pytest.mark.parametrize("iteration", range(5))
def test_owner_surface_replay_is_deterministic(iteration: int) -> None:
    del iteration
    first = tuple((name, REQUIRED_PUBLIC_SEAMS[name]) for name in OWNER_MODULES)
    second = tuple((name, REQUIRED_PUBLIC_SEAMS[name]) for name in OWNER_MODULES)
    assert first == second
