from __future__ import annotations

import copy
from unittest.mock import Mock, patch

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from tests.test_cad_agent_visual_supervisor_adapter import (
    SHA_DRAWING,
    SHA_MANIFEST,
    SHA_MUTATION,
    SHA_STATE,
    _request_fixture,
    _valid_inputs,
)


def _camera_plan(scope: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "visual-capture-plan-1.0",
        "plan_id": "native-camera-plan-r5-001",
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


def _native_evidence(
    scope: dict[str, object],
    plan: dict[str, object],
    capture_id: str,
    artifact_sha256: str,
) -> dict[str, object]:
    capture = next(
        item for item in plan["captures"] if item["capture_id"] == capture_id
    )
    plan_sha = canonical_json_sha256(plan)
    camera = {
        "schema_version": "canonical-camera-render-1.0",
        "capture_id": capture["capture_id"],
        "capture_class": capture["capture_class"],
        "parent_region_id": capture["parent_region_id"],
        "region_id": capture["region_id"],
        "scope_id": plan["scope_id"],
        "view_id": capture["view_id"],
        "sheet_id": capture["sheet_id"],
        "layout_id": capture["layout_id"],
        "candidate_revision_sha256": plan["candidate_revision_sha256"],
        "candidate_state_sha256": plan["candidate_state_sha256"],
        "visual_capture_plan_sha256": plan_sha,
        "zoom_mode": capture["zoom_mode"],
        "wcs_bbox": copy.deepcopy(capture["wcs_bbox"]),
        "margin_ratio": capture["margin_ratio"],
        "view_direction": capture["view_direction"],
        "ucs": capture["ucs"],
        "visual_style": capture["visual_style"],
    }
    bbox = copy.deepcopy(camera["wcs_bbox"])
    if bbox is None:
        center = [0.0, 0.0]
        view_width = 1.0
        view_height = 1.0
    else:
        xmin, ymin, xmax, ymax = bbox
        margin = camera["margin_ratio"]
        center = [(xmin + xmax) / 2.0, (ymin + ymax) / 2.0]
        view_width = (xmax - xmin) * (1.0 + 2.0 * margin)
        view_height = (ymax - ymin) * (1.0 + 2.0 * margin)
    return {
        "schema_version": "autocad-native-render-evidence-1.0",
        "request_id": f"request-{capture_id}",
        "run_id": scope["run_id"],
        "drawing_sha256": SHA_DRAWING,
        "latest_mutation_sha256": SHA_MUTATION,
        "visual_run_manifest_sha256": SHA_MANIFEST,
        "layout": {"identity": "layout-1", "name": "Layout1"},
        "artifact_kind": "PNG",
        "render_options": {
            "background": "white",
            "dpi": 300,
            "fit_to_paper": True,
            "paper_size": "A4",
            "plot_style": "monochrome.ctb",
            "camera": camera,
        },
        "renderer": "AUTOCAD_NATIVE",
        "artifact": {
            "relative_path": f"artifacts/{capture_id}.png",
            "sha256": artifact_sha256,
            "width": 100,
            "height": 80,
        },
        "capture_timestamp": "2026-08-14T05:30:01Z",
        "changed": False,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "warnings": [],
        "visual_capture_receipt": {
            "schema_version": "visual-capture-receipt-1.0",
            "receipt_id": f"receipt-{capture_id}",
            "capture_id": capture_id,
            "run_id": scope["run_id"],
            "scope_id": camera["scope_id"],
            "region_id": camera["region_id"],
            "view_id": camera["view_id"],
            "sheet_id": camera["sheet_id"],
            "layout_id": camera["layout_id"],
            "candidate_revision_sha256": camera["candidate_revision_sha256"],
            "candidate_state_sha256": camera["candidate_state_sha256"],
            "latest_mutation_sha256": SHA_MUTATION,
            "visual_capture_plan_sha256": plan_sha,
            "capture_class": camera["capture_class"],
            "zoom_mode": camera["zoom_mode"],
            "requested_wcs_bbox": copy.deepcopy(bbox),
            "observed_wcs_bbox": copy.deepcopy(bbox),
            "view_center": center,
            "view_width": view_width,
            "view_height": view_height,
            "view_direction": camera["view_direction"],
            "ucs": camera["ucs"],
            "visual_style": camera["visual_style"],
            "artifact_sha256": artifact_sha256,
            "artifact_width": 100,
            "artifact_height": 80,
            "captured_at_utc": "2026-08-14T05:30:01Z",
            "transient_state_restored": True,
        },
    }


def _declare_native_camera(inputs: dict[str, object]) -> None:
    scope = inputs["server_scope"]
    plan = _camera_plan(scope)
    evidence = [
        _native_evidence(scope, plan, "global-view-1", "4" * 64),
        _native_evidence(scope, plan, "region-critical", "5" * 64),
        _native_evidence(scope, plan, "region-normal", "6" * 64),
    ]
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_capture_plan"] = copy.deepcopy(plan)
        state["native_render_evidence"] = copy.deepcopy(evidence)


def _declare_pdf_camera_composition(inputs: dict[str, object]) -> None:
    _declare_native_camera(inputs)
    for index, state in enumerate(
        (inputs["authoritative_state"], inputs["post_provider_state"])
    ):
        for evidence in state["native_render_evidence"]:
            receipt = evidence.pop("visual_capture_receipt")
            capture_id = receipt["capture_id"]
            pdf_sha = f"{index + 7}" * 64
            png_sha = f"{index + 4}" * 64
            evidence["artifact_kind"] = "PDF"
            evidence["artifact"] = {
                "relative_path": f"artifacts/{capture_id}.pdf",
                "sha256": pdf_sha,
                "page_count": 1,
            }
            evidence["native_camera_observation"] = {
                **{
                    key: value
                    for key, value in receipt.items()
                    if key not in {"receipt_id", "artifact_sha256", "artifact_width", "artifact_height"}
                },
                "schema_version": "native-camera-observation-1.0",
                "observation_id": f"observation-{capture_id}",
            }
            evidence["derived_raster_evidence"] = {
                "schema_version": "derived-raster-evidence-1.0",
                "source": "NATIVE_PDF_BINDING",
                "native_binding": {
                    "pdf_artifact_sha256": pdf_sha,
                    "drawing_sha256": SHA_DRAWING,
                    "latest_mutation_sha256": SHA_MUTATION,
                    "visual_run_manifest_sha256": SHA_MANIFEST,
                    "layout": {"identity": "layout-1", "name": "Layout1"},
                    "render_options": {
                        "paper_size": "A4",
                        "dpi": 300,
                        "background": "white",
                        "opaque": True,
                    },
                    "dbmod_before": 0,
                    "dbmod_after": 0,
                },
                "page_number": 1,
                "paper_size": "A4",
                "dpi": 300,
                "width_px": 2480,
                "height_px": 3508,
                "has_alpha": False,
                "opaque": True,
                "pdf_sha256": pdf_sha,
                "png_sha256": png_sha,
                "drawing_sha256": SHA_DRAWING,
                "latest_mutation_sha256": SHA_MUTATION,
                "visual_run_manifest_sha256": SHA_MANIFEST,
                "layout": {"identity": "layout-1", "name": "Layout1"},
                "render_options": {
                    "paper_size": "A4",
                    "dpi": 300,
                    "background": "white",
                    "opaque": True,
                },
                "dbmod_before": 0,
                "dbmod_after": 0,
            }
            evidence["visual_capture_receipt"] = {
                **receipt,
                "artifact_sha256": png_sha,
                "artifact_width": 2480,
                "artifact_height": 3508,
            }


def test_native_pdf_camera_composition_binds_pdf_observation_to_derived_png() -> None:
    inputs = _valid_inputs()
    _declare_pdf_camera_composition(inputs)

    result, _ = _finalize_native(inputs)

    assert result["verdict"] == "PASS"


def _finalize_native(inputs: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    import cad_agent.visual_supervisor_adapter as module

    candidate_validator = Mock(
        side_effect=lambda payload: {
            "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
            "state_sha256": SHA_STATE,
        }
    )
    evidence_validator = Mock(side_effect=lambda evidence, *_args: copy.deepcopy(evidence))
    calls: list[str] = []
    real_validate = module.validate_visual_contract

    def validating(
        payload: object, *, contract: str, server_scope: object | None = None
    ) -> object:
        calls.append(contract)
        return real_validate(payload, contract=contract, server_scope=server_scope)

    request_handoff, worker_binding, authority_context, worker_context, resume = _request_fixture(inputs)
    with (
        patch.object(module, "validate_candidate_revision_state", candidate_validator),
        patch.object(module, "require_current_drawing_artifact_reference", Mock()),
        patch.object(module, "validate_visual_evidence_freshness", evidence_validator),
        patch.object(module, "validate_visual_contract", side_effect=validating),
        patch.object(module, "resume_worker_thread", resume),
        patch.object(module, "consume_task6_result", Mock()),
    ):
        result = module.finalize_visual_verdict(
            **inputs,
            request_handoff=request_handoff,
            worker_binding=worker_binding,
            authority_context=authority_context,
            worker_context=worker_context,
        )
    return result, calls


def test_legacy_r5_without_declared_camera_still_finalizes() -> None:
    result, calls = _finalize_native(_valid_inputs())
    assert result["verdict"] == "PASS"
    assert "visual_capture_plan" not in calls
    assert "visual_capture_receipt" not in calls


def test_declared_native_camera_complete_coverage_can_finalize_pass() -> None:
    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    result, calls = _finalize_native(inputs)
    assert result["verdict"] == "PASS"
    assert calls.count("visual_capture_plan") >= 2
    assert calls.count("visual_capture_receipt") == 6


def test_declared_camera_requires_plan_and_native_evidence_together() -> None:
    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    del inputs["authoritative_state"]["native_render_evidence"]
    with pytest.raises(Exception, match="camera|native|evidence|plan"):
        _finalize_native(inputs)


def test_native_camera_requires_exact_evidence_coverage_for_every_plan_capture() -> None:
    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["native_render_evidence"] = [
            evidence
            for evidence in state["native_render_evidence"]
            if evidence["visual_capture_receipt"]["capture_id"] != "global-view-1"
        ]
    with pytest.raises(Exception, match="coverage|GLOBAL|capture|native"):
        _finalize_native(inputs)


def test_native_camera_rejects_duplicate_capture_evidence() -> None:
    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        duplicate = copy.deepcopy(state["native_render_evidence"][1])
        duplicate["request_id"] = "request-duplicate"
        state["native_render_evidence"].append(duplicate)
    with pytest.raises(Exception, match="duplicate|coverage|capture"):
        _finalize_native(inputs)


def test_native_camera_rejects_stale_mutation_or_manifest_identity() -> None:
    for field, value in (
        ("latest_mutation_sha256", "9" * 64),
        ("visual_run_manifest_sha256", "8" * 64),
        ("drawing_sha256", "7" * 64),
    ):
        inputs = _valid_inputs()
        _declare_native_camera(inputs)
        for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
            state["native_render_evidence"][1][field] = value
        with pytest.raises(Exception, match="stale|mutation|manifest|drawing|native"):
            _finalize_native(inputs)


def test_native_camera_snapshot_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    inputs["post_provider_state"]["native_render_evidence"][0]["artifact"]["sha256"] = "9" * 64
    inputs["post_provider_state"]["native_render_evidence"][0]["visual_capture_receipt"][
        "artifact_sha256"
    ] = "9" * 64
    with pytest.raises(Exception, match="camera|native|changed|evidence|fresh"):
        _finalize_native(inputs)


def test_native_receipts_are_revalidated_against_full_server_owned_plan() -> None:
    import cad_agent.visual_supervisor_adapter as module

    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    calls: list[str] = []
    real_validate = module.validate_visual_contract

    def validating(payload: object, *, contract: str, server_scope: object | None = None) -> object:
        calls.append(contract)
        return real_validate(payload, contract=contract, server_scope=server_scope)

    request_handoff, worker_binding, authority_context, worker_context, resume = _request_fixture(inputs)
    with (
        patch.object(
            module,
            "validate_candidate_revision_state",
            Mock(
                side_effect=lambda payload: {
                    "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
                    "state_sha256": SHA_STATE,
                }
            ),
        ),
        patch.object(module, "require_current_drawing_artifact_reference", Mock()),
        patch.object(
            module,
            "validate_visual_evidence_freshness",
            Mock(side_effect=lambda evidence, *_args: copy.deepcopy(evidence)),
        ),
        patch.object(module, "validate_visual_contract", side_effect=validating),
        patch.object(module, "resume_worker_thread", resume),
        patch.object(module, "consume_task6_result", Mock()),
    ):
        result = module.finalize_visual_verdict(
            **inputs,
            request_handoff=request_handoff,
            worker_binding=worker_binding,
            authority_context=authority_context,
            worker_context=worker_context,
        )
    assert result["verdict"] == "PASS"
    assert calls.count("visual_capture_plan") >= 2
    assert calls.count("visual_capture_receipt") == 6


def test_native_camera_identities_are_sealed_into_r5_request_hash() -> None:
    import cad_agent.visual_supervisor_adapter as module

    inputs = _valid_inputs()
    _declare_native_camera(inputs)
    captured_payloads: list[object] = []
    real_hash = canonical_json_sha256

    def capture_hash(payload: object) -> str:
        captured_payloads.append(copy.deepcopy(payload))
        return real_hash(payload)

    request_handoff, worker_binding, authority_context, worker_context, resume = _request_fixture(inputs)
    with (
        patch.object(
            module,
            "validate_candidate_revision_state",
            Mock(
                side_effect=lambda payload: {
                    "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
                    "state_sha256": SHA_STATE,
                }
            ),
        ),
        patch.object(module, "require_current_drawing_artifact_reference", Mock()),
        patch.object(
            module,
            "validate_visual_evidence_freshness",
            Mock(side_effect=lambda evidence, *_args: copy.deepcopy(evidence)),
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
    assert "native_camera_evidence" in request_payload
    identities = request_payload["native_camera_evidence"]
    assert {item["capture_id"] for item in identities} == {
        "global-view-1",
        "region-critical",
        "region-normal",
    }
    assert all("artifact_sha256" in item for item in identities)
    assert all("visual_capture_receipt_sha256" in item for item in identities)
