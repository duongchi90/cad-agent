from __future__ import annotations

import copy

import pytest

from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    prepare_visual_evidence_camera_capture,
)


RUN_ID = "run-r5-camera-001"
REGION_ID = "region-side-cabin"
MUTATION_SHA = "d" * 64


def _scope() -> dict[str, object]:
    return {
        "schema_version": "visual-review-scope-1.0",
        "scope_id": "scope-r5-camera-001",
        "run_id": RUN_ID,
        "registry_snapshot_sha256": "a" * 64,
        "candidate_revision_sha256": "b" * 64,
        "candidate_state_sha256": "c" * 64,
        "regions": [
            {
                "region_id": REGION_ID,
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-model",
                "criticality": "CRITICAL",
            }
        ],
    }


def _plan() -> dict[str, object]:
    return {
        "schema_version": "visual-capture-plan-1.0",
        "plan_id": "camera-plan-r5-001",
        "run_id": RUN_ID,
        "scope_id": "scope-r5-camera-001",
        "registry_snapshot_sha256": "a" * 64,
        "candidate_revision_sha256": "b" * 64,
        "candidate_state_sha256": "c" * 64,
        "latest_mutation_sha256": MUTATION_SHA,
        "captures": [
            {
                "capture_id": "global-side",
                "capture_class": "GLOBAL",
                "parent_region_id": None,
                "region_id": None,
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-model",
                "zoom_mode": "EXTENTS",
                "wcs_bbox": None,
                "margin_ratio": 0.05,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
            {
                "capture_id": "region-side-cabin",
                "capture_class": "REGION",
                "parent_region_id": None,
                "region_id": REGION_ID,
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-model",
                "zoom_mode": "WINDOW",
                "wcs_bbox": [0.0, 0.0, 2400.0, 2200.0],
                "margin_ratio": 0.10,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
        ],
    }


def _region() -> dict[str, object]:
    return {
        "model_bbox_mm": [0.0, 0.0, 2400.0, 2200.0],
        "pixel_size": [1600, 1200],
        "background": "WHITE",
        "include_layers": ["CABIN"],
        "exclude_layers": [],
    }


def _base_parameters() -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "evidence_id": "evidence-side-cabin-001",
        "region_id": REGION_ID,
        "latest_mutation_sha256": MUTATION_SHA,
        "visual_run_manifest_sha256": "e" * 64,
        "artifact_policy_version": "vs-t3-artifacts-1",
        "artifact_directory": "artifacts/request-r5-camera-001",
        "region": _region(),
        "measurements": [],
        "datum_bindings": [],
    }


def test_prepare_visual_evidence_camera_capture_binds_exact_server_plan_region() -> None:
    prepared = prepare_visual_evidence_camera_capture(
        server_scope=_scope(),
        visual_capture_plan=_plan(),
        capture_id="region-side-cabin",
        region=_region(),
    )

    assert prepared == {
        "schema_version": "visual-evidence-camera-capture-1.0",
        "capture_id": "region-side-cabin",
        "capture_class": "REGION",
        "run_id": RUN_ID,
        "scope_id": "scope-r5-camera-001",
        "region_id": REGION_ID,
        "view_id": "view-side",
        "sheet_id": "sheet-a",
        "layout_id": "layout-model",
        "zoom_mode": "WINDOW",
        "wcs_bbox": [0.0, 0.0, 2400.0, 2200.0],
        "margin_ratio": 0.10,
        "view_direction": "TOP",
        "ucs": "WORLD",
        "visual_style": "2D_WIREFRAME",
        "candidate_revision_sha256": "b" * 64,
        "candidate_state_sha256": "c" * 64,
        "latest_mutation_sha256": MUTATION_SHA,
        "visual_capture_plan_sha256": prepared["visual_capture_plan_sha256"],
    }
    assert len(prepared["visual_capture_plan_sha256"]) == 64


def test_prepare_visual_evidence_camera_capture_rejects_non_region_capture() -> None:
    with pytest.raises(ValueError, match="REGION"):
        prepare_visual_evidence_camera_capture(
            server_scope=_scope(),
            visual_capture_plan=_plan(),
            capture_id="global-side",
            region=_region(),
        )


def test_prepare_visual_evidence_camera_capture_rejects_foreign_region_identity() -> None:
    plan = _plan()
    plan["captures"][1]["region_id"] = "foreign-region"
    with pytest.raises(ValueError, match="scope|region"):
        prepare_visual_evidence_camera_capture(
            server_scope=_scope(),
            visual_capture_plan=plan,
            capture_id="region-side-cabin",
            region=_region(),
        )


def test_prepare_visual_evidence_camera_capture_rejects_region_bbox_mismatch() -> None:
    region = _region()
    region["model_bbox_mm"] = [0.0, 0.0, 2500.0, 2200.0]
    with pytest.raises(ValueError, match="bbox|region"):
        prepare_visual_evidence_camera_capture(
            server_scope=_scope(),
            visual_capture_plan=_plan(),
            capture_id="region-side-cabin",
            region=region,
        )


def test_prepare_visual_evidence_camera_capture_is_deterministic_for_scope_region_order() -> None:
    scope = _scope()
    scope["regions"].append(
        {
            "region_id": "region-extra",
            "view_id": "view-side",
            "sheet_id": "sheet-a",
            "layout_id": "layout-model",
            "criticality": "NORMAL",
        }
    )
    plan = _plan()
    plan["captures"].append(
        {
            "capture_id": "region-extra",
            "capture_class": "REGION",
            "parent_region_id": None,
            "region_id": "region-extra",
            "view_id": "view-side",
            "sheet_id": "sheet-a",
            "layout_id": "layout-model",
            "zoom_mode": "WINDOW",
            "wcs_bbox": [3000.0, 0.0, 3500.0, 500.0],
            "margin_ratio": 0.10,
            "view_direction": "TOP",
            "ucs": "WORLD",
            "visual_style": "2D_WIREFRAME",
        }
    )

    first = prepare_visual_evidence_camera_capture(
        server_scope=scope,
        visual_capture_plan=plan,
        capture_id="region-side-cabin",
        region=_region(),
    )
    reversed_scope = copy.deepcopy(scope)
    reversed_scope["regions"] = list(reversed(reversed_scope["regions"]))
    second = prepare_visual_evidence_camera_capture(
        server_scope=reversed_scope,
        visual_capture_plan=plan,
        capture_id="region-side-cabin",
        region=_region(),
    )
    assert first == second


def test_visual_evidence_ipc_parameters_accept_only_prepared_camera_capture() -> None:
    parameters = _base_parameters()
    parameters["camera_capture"] = prepare_visual_evidence_camera_capture(
        server_scope=_scope(),
        visual_capture_plan=_plan(),
        capture_id="region-side-cabin",
        region=_region(),
    )
    DotNetIPCClient._validate_visual_evidence_parameters(parameters)

    forged = copy.deepcopy(parameters)
    forged["camera_capture"]["margin_ratio"] = 0.05
    with pytest.raises(ValueError, match="camera_capture|margin"):
        DotNetIPCClient._validate_visual_evidence_parameters(forged)


def test_legacy_visual_evidence_ipc_parameters_remain_accepted_without_camera() -> None:
    DotNetIPCClient._validate_visual_evidence_parameters(_base_parameters())
