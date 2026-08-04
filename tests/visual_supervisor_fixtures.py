from __future__ import annotations

import copy
from typing import Any

RUN_ID = "RUN-VISUAL-SYNTHETIC-001"
SOURCE_SHA = "1" * 64
DRAWING_SHA = "2" * 64
MUTATION_SHA = "3" * 64
RENDER_SHA = "4" * 64
REFERENCE_PACKAGE_SHA = "5" * 64
COMPARISON_SHA = "6" * 64
REVIEW_SHA = "7" * 64
INITIAL_TARGET_SHA = "8" * 64
PAGE_ID = "PAGE-001"
VIEW_ID = "SIDE"
REGION_ID = "SIDE-CABIN"
TARGET_PATH = "D:\\Synthetic\\drawing.dwg"
BACKUP_ROOT = "D:\\Synthetic\\Backups"


def clone(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def valid_visual_run_manifest() -> dict[str, Any]:
    return {
        "schema_version": "visual-run-manifest-1.0",
        "run_id": RUN_ID,
        "state": "CREATED",
        "authority": "DISPOSABLE_REVIEW",
        "source": {
            "source_type": "PDF",
            "source_sha256": SOURCE_SHA,
            "page_ids": [PAGE_ID],
        },
        "drawing": {
            "absolute_path": TARGET_PATH,
            "initial_sha256": DRAWING_SHA,
        },
        "evidence_root": "runs/RUN-VISUAL-SYNTHETIC-001",
        "latest_mutation_sha256": MUTATION_SHA,
    }


def valid_dimension_register() -> dict[str, Any]:
    return {
        "schema_version": "dimension-register-1.0",
        "run_id": RUN_ID,
        "source_sha256": SOURCE_SHA,
        "page_id": PAGE_ID,
        "view_id": VIEW_ID,
        "coverage": {
            "clusters_detected": 1,
            "clusters_processed": 1,
            "page_coverage_percent": 100.0,
        },
        "summary": {
            "confirmed": 1,
            "unresolved": 0,
            "conflicts": 0,
        },
        "dimensions": [
            {
                "id": "DIM-SIDE-001",
                "display_text": "4500",
                "value": 4500.0,
                "unit": "mm",
                "kind": "HORIZONTAL_DISTANCE",
                "role": "DRIVING",
                "status": "CONFIRMED",
                "critical": True,
                "from_ref": {"type": "DATUM", "id": "FRONT_AXLE_CENTER"},
                "to_ref": {"type": "DATUM", "id": "REAR_AXLE_CENTER"},
                "source_evidence": {
                    "crop_id": "DIMCLUSTER-001",
                    "bbox": [100, 200, 600, 260],
                    "crop_sha256": REFERENCE_PACKAGE_SHA,
                },
                "text_confidence": 0.99,
                "attachment_confidence": 0.96,
                "blocker_scope": [],
            }
        ],
    }


def valid_geometry_comparison() -> dict[str, Any]:
    return {
        "schema_version": "geometry-comparison-1.0",
        "comparison_id": "GC-SIDE-CABIN-001",
        "run_id": RUN_ID,
        "region_id": REGION_ID,
        "reference_package_sha256": REFERENCE_PACKAGE_SHA,
        "cad_render_sha256": RENDER_SHA,
        "mutation_sha256": MUTATION_SHA,
        "alignment": {
            "status": "ALIGNED",
            "method": "VERIFIED_DATUM_SIMILARITY",
            "anchor_ids": ["FRONT_AXLE_CENTER", "REAR_AXLE_CENTER"],
            "transform_sha256": COMPARISON_SHA,
        },
        "metrics": {
            "silhouette_iou": 0.92,
            "chamfer_distance_normalized": 0.02,
            "hausdorff_p95_normalized": 0.03,
            "centroid_offset_x_ratio": 0.01,
            "centroid_offset_y_ratio": 0.01,
            "width_ratio_error": 0.02,
            "height_ratio_error": 0.02,
            "missing_edge_ratio": 0.01,
            "extra_edge_ratio": 0.01,
            "connected_component_difference": 0,
        },
        "trend": "IMPROVED",
        "previous_comparison_sha256": COMPARISON_SHA,
    }


def valid_visual_review() -> dict[str, Any]:
    return {
        "schema_version": "visual-review-1.0",
        "review_id": "VR-SIDE-CABIN-001",
        "run_id": RUN_ID,
        "region_id": REGION_ID,
        "iteration": 1,
        "reference_package_sha256": REFERENCE_PACKAGE_SHA,
        "cad_render_sha256": RENDER_SHA,
        "mutation_sha256": MUTATION_SHA,
        "geometry_comparison_sha256": COMPARISON_SHA,
        "verdict": "FAIL",
        "severity": "MAJOR",
        "confidence": 0.94,
        "findings": [
            {
                "finding_id": "FIND-001",
                "category": "SHAPE_MISMATCH",
                "feature": "CABIN_ROOF",
                "severity": "MAJOR",
                "description": "Roof contour is too high relative to the approved source.",
                "evidence_refs": ["overlay.png", "difference-mask.png"],
            }
        ],
        "repair_intent": {
            "change": ["LOWER_CABIN_ROOF_MIDPOINT"],
            "preserve": ["FRONT_AXLE_CENTER", "CABIN_BOTTOM_DATUM"],
            "required_measurements": ["CABIN_MAX_HEIGHT"],
            "requested_next_evidence": [],
        },
    }


def valid_repair_plan() -> dict[str, Any]:
    return {
        "schema_version": "repair-plan-1.0",
        "repair_id": "RP-SIDE-CABIN-001",
        "source_review_id": "VR-SIDE-CABIN-001",
        "run_id": RUN_ID,
        "target_drawing_sha256": DRAWING_SHA,
        "operations": [
            {
                "operation": "ADJUST_SPLINE_CONTROL_REGION",
                "target": {
                    "stable_entity_id": "PART:CABIN_OUTER",
                    "feature": "ROOF",
                },
                "preserve_anchors": ["CABIN_ROOF_FRONT", "CABIN_ROOF_REAR"],
                "constraint_refs": ["DIM-SIDE-008"],
            }
        ],
        "affected_regions": [REGION_ID, "SIDE-ANNOTATION-R02"],
        "expected_improvements": ["height_ratio_error:DECREASE"],
        "must_not_worsen": ["engineering_constraints", "centroid_offset_x_ratio"],
        "rollback_candidate_sha256": DRAWING_SHA,
    }
