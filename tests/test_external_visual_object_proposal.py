from __future__ import annotations

import importlib

from tests.test_cad_agent_source_fusion import _task6_ready_inputs


def test_compile_only_external_visual_object_proposal_binds_existing_fusion_without_materialization() -> None:
    """RED: an external proposal needs a thin pre-fusion compile-only owner."""

    source_fusion = importlib.import_module("cad_agent.source_fusion")
    fusion = source_fusion.build_source_fusion_packet(**_task6_ready_inputs())
    render = fusion["render_provenance"][0]

    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        "source_sha256": render["observed_source_sha256"],
        "page_index": 0,
        "source_render_sha256": render["raster_sha256"],
        "roi_bbox_px": [100, 100, 220, 220],
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "mirror-top",
                "type": "LINE",
                "start_px": [120, 120],
                "end_px": [200, 120],
            },
            {
                "id": "mirror-right",
                "type": "LINE",
                "start_px": [200, 120],
                "end_px": [200, 200],
            },
        ],
        "object_groups": [
            {
                "group_id": "front-right-mirror-001",
                "proposed_label": "RIGHT_MIRROR_HOUSING",
                "primitive_hypothesis_ids": ["mirror-top", "mirror-right"],
            }
        ],
        "excluded_memberships": [],
    }

    compiler = getattr(
        source_fusion, "compile_external_visual_object_proposal", None
    )
    assert callable(compiler), "compile-only proposal owner is missing"

    result = compiler(proposal=proposal, source_fusion=fusion)

    assert set(result) == {
        "kind",
        "status",
        "exact_source_binding",
        "checks_required",
        "semantic_label_authority",
        "primitive_ir_materialized",
        "semantic_observation_materialized",
        "cad_mutation",
    }
    assert result["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
    assert result["status"] == "PROPOSAL_ONLY"
    assert result["exact_source_binding"] == {
        "source_sha256": render["observed_source_sha256"],
        "page_index": 0,
        "source_render_sha256": render["raster_sha256"],
        "roi_bbox_px": [100, 100, 220, 220],
    }
    assert result["checks_required"] == [
        "EXACT_SOURCE_BINDING",
        "PER_PRIMITIVE_SOURCE_SUPPORT",
        "GROUP_TOPOLOGY",
        "EXCLUSION_CONSISTENCY",
    ]
    assert result["semantic_label_authority"] == "NONE"
    assert result["primitive_ir_materialized"] is False
    assert result["semantic_observation_materialized"] is False
    assert result["cad_mutation"] is False
