from __future__ import annotations

import copy
from unittest.mock import Mock, patch

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from tests.test_cad_agent_visual_supervisor_adapter import (
    SHA_STATE,
    SHA_MUTATION,
    _request_fixture,
    _valid_inputs,
)


def _camera_plan(scope: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "visual-capture-plan-1.0",
        "plan_id": "plan-r5-camera-001",
        "run_id": scope["run_id"],
        "scope_id": scope["scope_id"],
        "registry_snapshot_sha256": scope["registry_snapshot_sha256"],
        "candidate_revision_sha256": scope["candidate_revision_sha256"],
        "candidate_state_sha256": scope["candidate_state_sha256"],
        "latest_mutation_sha256": SHA_MUTATION,
        "captures": [
            {
                "capture_id": "global-view-1",
                "capture_class": "GLOBAL",
                "parent_region_id": None,
                "region_id": None,
                "view_id": "view-1",
                "sheet_id": "sheet-1",
                "layout_id": "layout-1",
                "zoom_mode": "EXTENTS",
                "wcs_bbox": None,
                "margin_ratio": 0.05,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
            {
                "capture_id": "region-critical",
                "capture_class": "REGION",
                "parent_region_id": None,
                "region_id": "critical-region",
                "view_id": "view-1",
                "sheet_id": "sheet-1",
                "layout_id": "layout-1",
                "zoom_mode": "WINDOW",
                "wcs_bbox": [0.0, 0.0, 10.0, 10.0],
                "margin_ratio": 0.10,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
            {
                "capture_id": "region-normal",
                "capture_class": "REGION",
                "parent_region_id": None,
                "region_id": "normal-region",
                "view_id": "view-1",
                "sheet_id": "sheet-1",
                "layout_id": "layout-1",
                "zoom_mode": "WINDOW",
                "wcs_bbox": [20.0, 0.0, 30.0, 10.0],
                "margin_ratio": 0.10,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
        ],
    }


def _receipt(
    plan: dict[str, object],
    *,
    capture_id: str,
    artifact_sha256: str,
    artifact_width: int,
    artifact_height: int,
) -> dict[str, object]:
    capture = next(item for item in plan["captures"] if item["capture_id"] == capture_id)
    bbox = capture["wcs_bbox"]
    if bbox is None:
        center = [0.0, 0.0]
        width = 100.0
        height = 100.0
    else:
        xmin, ymin, xmax, ymax = bbox
        margin = capture["margin_ratio"]
        center = [(xmin + xmax) / 2.0, (ymin + ymax) / 2.0]
        width = (xmax - xmin) * (1.0 + 2.0 * margin)
        height = (ymax - ymin) * (1.0 + 2.0 * margin)
    return {
        "schema_version": "visual-capture-receipt-1.0",
        "receipt_id": f"receipt-{capture_id}",
        "capture_id": capture_id,
        "run_id": plan["run_id"],
        "scope_id": plan["scope_id"],
        "region_id": capture["region_id"],
        "view_id": capture["view_id"],
        "sheet_id": capture["sheet_id"],
        "layout_id": capture["layout_id"],
        "candidate_revision_sha256": plan["candidate_revision_sha256"],
        "candidate_state_sha256": plan["candidate_state_sha256"],
        "latest_mutation_sha256": plan["latest_mutation_sha256"],
        "visual_capture_plan_sha256": canonical_json_sha256(plan),
        "capture_class": capture["capture_class"],
        "zoom_mode": capture["zoom_mode"],
        "requested_wcs_bbox": copy.deepcopy(bbox),
        "observed_wcs_bbox": copy.deepcopy(bbox),
        "view_center": center,
        "view_width": width,
        "view_height": height,
        "view_direction": capture["view_direction"],
        "ucs": capture["ucs"],
        "visual_style": capture["visual_style"],
        "artifact_sha256": artifact_sha256,
        "artifact_width": artifact_width,
        "artifact_height": artifact_height,
        "captured_at_utc": "2026-08-13T00:00:00Z",
        "transient_state_restored": True,
    }


def _declare_camera(inputs: dict[str, object]) -> None:
    scope = inputs["server_scope"]
    plan = _camera_plan(scope)
    receipts = [
        _receipt(
            plan,
            capture_id="global-view-1",
            artifact_sha256="6" * 64,
            artifact_width=1200,
            artifact_height=800,
        ),
        _receipt(
            plan,
            capture_id="region-critical",
            artifact_sha256="7" * 64,
            artifact_width=100,
            artifact_height=80,
        ),
        _receipt(
            plan,
            capture_id="region-normal",
            artifact_sha256="7" * 64,
            artifact_width=100,
            artifact_height=80,
        ),
    ]
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_capture_plan"] = copy.deepcopy(plan)
        state["visual_capture_receipts"] = copy.deepcopy(receipts)


def _camera_finalize(inputs: dict[str, object]) -> tuple[dict[str, object], Mock]:
    import cad_agent.visual_supervisor_adapter as module

    candidate_validator = Mock(
        side_effect=lambda payload: {
            "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
            "state_sha256": SHA_STATE,
        }
    )
    dara_validator = Mock()
    evidence_validator = Mock(side_effect=lambda evidence, *_args, **_kwargs: copy.deepcopy(evidence))
    consume = Mock()
    request_handoff, worker_binding, authority_context, worker_context, resume = _request_fixture(inputs)
    with (
        patch.object(module, "validate_candidate_revision_state", candidate_validator),
        patch.object(module, "require_current_drawing_artifact_reference", dara_validator),
        patch.object(module, "validate_visual_evidence_freshness", evidence_validator),
        patch.object(module, "resume_worker_thread", resume),
        patch.object(module, "consume_task6_result", consume),
    ):
        result = module.finalize_visual_verdict(
            **inputs,
            request_handoff=request_handoff,
            worker_binding=worker_binding,
            authority_context=authority_context,
            worker_context=worker_context,
        )
    assert consume.call_count == 1
    return result, evidence_validator


def test_canonical_camera_complete_coverage_can_finalize_pass() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    result, evidence_validator = _camera_finalize(inputs)
    assert result["verdict"] == "PASS"
    assert evidence_validator.call_count == 4
    camera_calls = [
        call
        for call in evidence_validator.call_args_list
        if call.kwargs.get("visual_capture_plan") is not None
    ]
    assert len(camera_calls) == 4
    assert {
        call.kwargs["visual_capture_receipt"]["region_id"] for call in camera_calls
    } == {"critical-region", "normal-region"}


def test_declared_camera_requires_receipts_in_both_owner_snapshots() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    del inputs["authoritative_state"]["visual_capture_receipts"]
    with pytest.raises(Exception, match="camera|receipt|capture"):
        _camera_finalize(inputs)


def test_canonical_camera_requires_exact_receipt_coverage_for_plan() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_capture_receipts"] = [
            receipt
            for receipt in state["visual_capture_receipts"]
            if receipt["capture_id"] != "global-view-1"
        ]
    with pytest.raises(Exception, match="GLOBAL|coverage|receipt|capture"):
        _camera_finalize(inputs)


def test_canonical_camera_rejects_duplicate_or_foreign_receipt() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        duplicate = copy.deepcopy(state["visual_capture_receipts"][1])
        duplicate["receipt_id"] = "receipt-duplicate"
        state["visual_capture_receipts"].append(duplicate)
    with pytest.raises(Exception, match="duplicate|coverage|capture"):
        _camera_finalize(inputs)


def test_canonical_camera_snapshot_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    inputs["post_provider_state"]["visual_capture_receipts"][0]["artifact_sha256"] = "5" * 64
    with pytest.raises(Exception, match="camera|receipt|changed|fresh"):
        _camera_finalize(inputs)


def test_region_receipt_is_bound_into_existing_visual_evidence_freshness_call() -> None:
    inputs = _valid_inputs()
    _declare_camera(inputs)
    _, evidence_validator = _camera_finalize(inputs)
    for call in evidence_validator.call_args_list:
        receipt = call.kwargs.get("visual_capture_receipt")
        plan = call.kwargs.get("visual_capture_plan")
        assert plan is not None
        assert receipt is not None
        evidence_region = call.args[0]["payload"]["region_id"]
        assert receipt["region_id"] == evidence_region
        render = next(
            item for item in call.args[0]["payload"]["artifacts"] if item["kind"] == "render"
        )
        assert receipt["artifact_sha256"] == render["sha256"]
        assert receipt["artifact_width"] == render["width"]
        assert receipt["artifact_height"] == render["height"]


def test_camera_identities_are_bound_into_r5_request_hash_input() -> None:
    import cad_agent.visual_supervisor_adapter as module

    inputs = _valid_inputs()
    _declare_camera(inputs)
    captured_payloads: list[object] = []
    real_hash = canonical_json_sha256

    def capture_hash(payload: object) -> str:
        captured_payloads.append(copy.deepcopy(payload))
        return real_hash(payload)

    candidate_validator = Mock(
        side_effect=lambda payload: {
            "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
            "state_sha256": SHA_STATE,
        }
    )
    request_handoff, worker_binding, authority_context, worker_context, resume = _request_fixture(inputs)
    with (
        patch.object(module, "validate_candidate_revision_state", candidate_validator),
        patch.object(module, "require_current_drawing_artifact_reference", Mock()),
        patch.object(
            module,
            "validate_visual_evidence_freshness",
            Mock(side_effect=lambda evidence, *_args, **_kwargs: copy.deepcopy(evidence)),
        ),
        patch.object(module, "resume_worker_thread", resume),
        patch.object(module, "consume_task6_result", Mock()),
        patch.object(module, "canonical_json_sha256", side_effect=capture_hash),
    ):
        result = module.finalize_visual_verdict(
            **inputs,
            request_handoff=request_handoff,
            worker_binding=worker_binding,
            authority_context=authority_context,
            worker_context=worker_context,
        )
    assert result["verdict"] == "PASS"
    request_payload = next(
        payload
        for payload in captured_payloads
        if isinstance(payload, dict) and "visual_scope" in payload
    )
    assert "visual_capture_plan_sha256" in request_payload
    assert "visual_capture_receipts" in request_payload
    assert {item["capture_class"] for item in request_payload["visual_capture_receipts"]} == {
        "GLOBAL",
        "REGION",
    }
