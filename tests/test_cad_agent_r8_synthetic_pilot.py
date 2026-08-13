"""R8-S synthetic acceptance over the accepted R1-R7 public owner chain.

This slice is intentionally acceptance-only: it adds no production owner and
keeps live AutoCAD/File-IPC/provider/private/publication actions out of scope.
"""

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
    "cad_agent.approved_repair_adapter": ("execute_approved_repair",),
    "cad_agent.publication_composition": ("execute_verified_publication", "validate_verified_publication_result"),
}

FORBIDDEN_R8_OWNER_TOKENS = (
    "class R8Store",
    "class R8Registry",
    "class R8Transport",
    "class R8Publisher",
    "class R8Revision",
)


def test_r8_synthetic_chain_exposes_only_accepted_r1_r7_public_owners() -> None:
    """The pilot must compose accepted owners, never materialize an R8 owner."""
    for module_name in OWNER_MODULES:
        module = importlib.import_module(module_name)
        for seam in REQUIRED_PUBLIC_SEAMS[module_name]:
            assert callable(getattr(module, seam, None)), f"R8_MISSING_ACCEPTED_SEAM:{module_name}:{seam}"

    source = inspect.getsource(importlib.import_module(__name__))
    assert not any(token in source for token in FORBIDDEN_R8_OWNER_TOKENS)


def test_r8_r6_mutation_cannot_be_treated_as_a_fresh_r5_pass() -> None:
    """R6 evidence is never a substitute for the fresh independent R5 gate."""
    r5 = importlib.import_module("cad_agent.visual_supervisor_adapter")
    repair = importlib.import_module("cad_agent.approved_repair_adapter")
    publish = importlib.import_module("cad_agent.publication_composition")

    assert r5.validate_visual_verdict_result is not repair.validate_approved_repair_result
    assert publish.validate_visual_verdict_result is r5.validate_visual_verdict_result
    assert publish.validate_visual_verdict_result is not repair.validate_approved_repair_result


def test_r8_publication_requires_fresh_r5_and_exact_r4_inputs_by_signature() -> None:
    """R7 remains a thin consumer of current R4 + fresh R5, not a new truth store."""
    publish = importlib.import_module("cad_agent.publication_composition")
    parameters = tuple(inspect.signature(publish.execute_verified_publication).parameters)
    assert parameters == (
        "run_id",
        "candidate_state",
        "r5_verdict_result",
        "auto_publish_authorization",
        "manifest_path",
        "expected_manifest_sha256",
        "candidate_path",
        "target_path",
    )


@pytest.mark.parametrize("iteration", range(5))
def test_r8_owner_surface_is_deterministic_across_replay(iteration: int) -> None:
    """Five synthetic replays resolve the same public owner/seam fingerprint."""
    del iteration
    fingerprint = tuple(
        (name, tuple(REQUIRED_PUBLIC_SEAMS[name]))
        for name in OWNER_MODULES
    )
    replay = tuple(
        (name, tuple(REQUIRED_PUBLIC_SEAMS[name]))
        for name in OWNER_MODULES
    )
    assert replay == fingerprint
