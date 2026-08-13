"""R8-S synthetic acceptance over the accepted R1-R7 public owner chain.

R8 is acceptance-only.  These tests deliberately import the accepted public
owners instead of introducing a pilot dispatcher, store, transport, or hash
implementation.
"""

from __future__ import annotations

import inspect

from cad_agent import approved_repair_adapter as r6
from cad_agent import base_cad_adapter as r2
from cad_agent import candidate_revision as r4
from cad_agent import component_view_registry as r3
from cad_agent import publication_composition as r7
from cad_agent import source_fusion as r1
from cad_agent import visual_supervisor_adapter as r5
from cad_agent.drawing_contracts import canonical_json_sha256


def _public_owner_chain() -> dict[str, tuple[object, ...]]:
    return {
        "r1": (
            r1.validate_page_locators,
            r1.validate_region_locators,
            r1.validate_render_provenance,
        ),
        "r2": (
            r2.validate_base_cad_binding,
            r2.base_cad_binding_sha256,
            r2.validate_base_cad_reuse_handoff,
            r2.base_cad_reuse_handoff_sha256,
            r2.evaluate_frozen_base_cad_reuse,
        ),
        "r3": (
            r3.build_component_view_registry,
            r3.validate_component_view_registry,
            r3.component_view_registry_sha256,
            r3.finalize_component_view_correspondence,
            r3.project_linked_view_impacts,
        ),
        "r4": (
            r4.build_candidate_revision,
            r4.build_candidate_revision_state,
            r4.validate_candidate_revision_state,
        ),
        "r5": (r5.finalize_visual_verdict, r5.validate_visual_verdict_result),
        "r6": (r6.execute_approved_repair, r6.validate_approved_repair_result),
        "r7": (r7.execute_verified_publication, r7.validate_verified_publication_result),
    }


def test_r8_s_accepted_owner_chain_is_public_and_single_owner() -> None:
    chain = _public_owner_chain()
    assert tuple(chain) == ("r1", "r2", "r3", "r4", "r5", "r6", "r7")
    for owner, seams in chain.items():
        assert seams, owner
        assert all(callable(seam) for seam in seams), owner
        assert all(inspect.getmodule(seam) is not None for seam in seams), owner

    # R7 must compose the accepted R4/R5 validators rather than shadowing them.
    assert r7.validate_candidate_revision_state is r4.validate_candidate_revision_state
    assert r7.validate_visual_verdict_result is r5.validate_visual_verdict_result


def test_r8_s_repair_to_fresh_review_to_publication_bindings_are_exposed() -> None:
    r6_params = inspect.signature(r6.validate_approved_repair_result).parameters
    assert "expected_candidate_artifact_reference_id" in r6_params
    assert "expected_candidate_artifact_reference_sha256" in r6_params
    assert "expected_r5_failure_id" in r6_params
    assert "expected_r5_failure_sha256" in r6_params

    r5_params = inspect.signature(r5.validate_visual_verdict_result).parameters
    for required in (
        "expected_candidate_revision_sha256",
        "expected_candidate_state_sha256",
        "expected_latest_mutation_sha256",
    ):
        assert required in r5_params

    r7_params = inspect.signature(r7.execute_verified_publication).parameters
    assert tuple(r7_params) == (
        "run_id",
        "candidate_state",
        "r5_verdict_result",
        "auto_publish_authorization",
        "manifest_path",
        "expected_manifest_sha256",
        "candidate_path",
        "target_path",
    )


def test_r8_s_owner_fingerprint_is_deterministic_and_materially_bound() -> None:
    material = {
        "r3_schema": r3.COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION,
        "r4_revision_schema": r4.CANDIDATE_REVISION_SCHEMA_VERSION,
        "r4_state_schema": r4.CANDIDATE_REVISION_STATE_SCHEMA_VERSION,
        "r5_result_schema": r5.R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION,
        "r6_result_schema": r6.R6_RESULT_SCHEMA_VERSION,
        "r7_result_schema": r7.R7_VERIFIED_PUBLICATION_RESULT_SCHEMA_VERSION,
        "chain": [
            f"{owner}:{seam.__module__}.{seam.__name__}"
            for owner, seams in _public_owner_chain().items()
            for seam in seams
        ],
    }
    seals = [canonical_json_sha256(material) for _ in range(5)]
    assert len(set(seals)) == 1

    foreign = dict(material)
    foreign["r6_result_schema"] = "foreign-r6-schema"
    assert canonical_json_sha256(foreign) != seals[0]


def test_r8_s_r3_boundary_does_not_absorb_downstream_authority() -> None:
    source = inspect.getsource(r3)
    for forbidden in (
        "from cad_agent import candidate_revision",
        "from cad_agent import visual_supervisor_adapter",
        "from cad_agent import approved_repair_adapter",
        "from cad_agent import publication_composition",
    ):
        assert forbidden not in source
