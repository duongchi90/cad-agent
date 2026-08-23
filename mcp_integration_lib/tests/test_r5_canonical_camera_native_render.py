from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mcp_integration_lib import autocad_render_evidence as contract


FIXTURE = Path(__file__).with_name("fixtures") / "autocad-render-evidence.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _scope() -> dict[str, object]:
    return {
        "schema_version": "visual-review-scope-1.0",
        "scope_id": "scope-camera-001",
        "run_id": "run-001",
        "registry_snapshot_sha256": "1" * 64,
        "candidate_revision_sha256": "2" * 64,
        "candidate_state_sha256": "3" * 64,
        "regions": [
            {
                "region_id": "region-side-cabin",
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-001",
                "criticality": "CRITICAL",
            }
        ],
    }


def _plan() -> dict[str, object]:
    return {
        "schema_version": "visual-capture-plan-1.0",
        "plan_id": "camera-plan-001",
        "run_id": "run-001",
        "scope_id": "scope-camera-001",
        "registry_snapshot_sha256": "1" * 64,
        "candidate_revision_sha256": "2" * 64,
        "candidate_state_sha256": "3" * 64,
        "latest_mutation_sha256": "b" * 64,
        "captures": [
            {
                "capture_id": "global-side",
                "capture_class": "GLOBAL",
                "parent_region_id": None,
                "region_id": None,
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-001",
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
                "region_id": "region-side-cabin",
                "view_id": "view-side",
                "sheet_id": "sheet-a",
                "layout_id": "layout-001",
                "zoom_mode": "WINDOW",
                "wcs_bbox": [0.0, 0.0, 100.0, 50.0],
                "margin_ratio": 0.10,
                "view_direction": "TOP",
                "ucs": "WORLD",
                "visual_style": "2D_WIREFRAME",
            },
        ],
    }


def _base_options() -> dict[str, object]:
    return {
        "background": "white",
        "dpi": 300,
        "fit_to_paper": True,
        "paper_size": "A4",
        "plot_style": "monochrome.ctb",
    }


def _camera_request(capture_id: str = "region-side-cabin") -> dict[str, object]:
    return contract.build_canonical_camera_render_evidence_request(
        request_id=f"render-{capture_id}",
        drawing_sha256="a" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"identity": "layout-001", "name": "Layout1"},
        artifact_kind="PNG",
        render_options=_base_options(),
        requested_at="2026-08-14T05:00:00Z",
        server_scope=_scope(),
        visual_capture_plan=_plan(),
        capture_id=capture_id,
    )


def _camera_evidence(request: dict[str, object]) -> dict[str, object]:
    payload = copy.deepcopy(_fixture()["png"])
    payload["request_id"] = request["request_id"]
    payload["run_id"] = request["run_id"]
    payload["drawing_sha256"] = request["drawing_sha256"]
    payload["latest_mutation_sha256"] = request["latest_mutation_sha256"]
    payload["visual_run_manifest_sha256"] = request["visual_run_manifest_sha256"]
    payload["layout"] = copy.deepcopy(request["layout"])
    payload["render_options"] = copy.deepcopy(request["render_options"])
    camera = request["render_options"]["camera"]
    artifact = payload["artifact"]
    bbox = copy.deepcopy(camera["wcs_bbox"])
    if camera["capture_class"] == "GLOBAL":
        center = [0.0, 0.0]
        width = 1.0
        height = 1.0
    else:
        xmin, ymin, xmax, ymax = bbox
        margin = camera["margin_ratio"]
        center = [(xmin + xmax) / 2.0, (ymin + ymax) / 2.0]
        width = (xmax - xmin) * (1.0 + 2.0 * margin)
        height = (ymax - ymin) * (1.0 + 2.0 * margin)
    payload["visual_capture_receipt"] = {
        "schema_version": "visual-capture-receipt-1.0",
        "receipt_id": f"receipt-{camera['capture_id']}",
        "capture_id": camera["capture_id"],
        "run_id": request["run_id"],
        "scope_id": camera["scope_id"],
        "region_id": camera["region_id"],
        "view_id": camera["view_id"],
        "sheet_id": camera["sheet_id"],
        "layout_id": camera["layout_id"],
        "candidate_revision_sha256": camera["candidate_revision_sha256"],
        "candidate_state_sha256": camera["candidate_state_sha256"],
        "latest_mutation_sha256": request["latest_mutation_sha256"],
        "visual_capture_plan_sha256": camera["visual_capture_plan_sha256"],
        "capture_class": camera["capture_class"],
        "zoom_mode": camera["zoom_mode"],
        "requested_wcs_bbox": bbox,
        "observed_wcs_bbox": copy.deepcopy(bbox),
        "view_center": center,
        "view_width": width,
        "view_height": height,
        "view_direction": camera["view_direction"],
        "ucs": camera["ucs"],
        "visual_style": camera["visual_style"],
        "artifact_sha256": artifact["sha256"],
        "artifact_width": artifact["width"],
        "artifact_height": artifact["height"],
        "captured_at_utc": payload["capture_timestamp"],
        "transient_state_restored": True,
    }
    return payload


def test_legacy_native_render_request_and_evidence_remain_accepted() -> None:
    fixture = _fixture()
    request = contract.validate_render_request(fixture["request"])
    assert "camera" not in request["render_options"]
    assert contract.validate_render_evidence(fixture["png"], request=request) == fixture["png"]


def test_camera_request_is_derived_from_exact_server_owned_plan_capture() -> None:
    request = _camera_request()
    camera = request["render_options"]["camera"]
    assert camera == {
        "schema_version": "canonical-camera-render-1.0",
        "capture_id": "region-side-cabin",
        "capture_class": "REGION",
        "parent_region_id": None,
        "region_id": "region-side-cabin",
        "scope_id": "scope-camera-001",
        "view_id": "view-side",
        "sheet_id": "sheet-a",
        "layout_id": "layout-001",
        "candidate_revision_sha256": "2" * 64,
        "candidate_state_sha256": "3" * 64,
        "visual_capture_plan_sha256": camera["visual_capture_plan_sha256"],
        "zoom_mode": "WINDOW",
        "wcs_bbox": [0.0, 0.0, 100.0, 50.0],
        "margin_ratio": 0.10,
        "view_direction": "TOP",
        "ucs": "WORLD",
        "visual_style": "2D_WIREFRAME",
    }
    assert len(camera["visual_capture_plan_sha256"]) == 64
    assert request["latest_mutation_sha256"] == "b" * 64


def test_camera_request_supports_global_extents_from_the_same_plan() -> None:
    request = _camera_request("global-side")
    camera = request["render_options"]["camera"]
    assert camera["capture_class"] == "GLOBAL"
    assert camera["zoom_mode"] == "EXTENTS"
    assert camera["wcs_bbox"] is None
    assert camera["margin_ratio"] == 0.05


def test_camera_request_rejects_unknown_capture_and_layout_substitution() -> None:
    with pytest.raises(contract.AutoCADRenderEvidenceError, match="capture"):
        _camera_request("missing-capture")

    with pytest.raises(contract.AutoCADRenderEvidenceError, match="layout"):
        contract.build_canonical_camera_render_evidence_request(
            request_id="render-region-side-cabin",
            drawing_sha256="a" * 64,
            visual_run_manifest_sha256="c" * 64,
            layout={"identity": "foreign-layout", "name": "Layout1"},
            artifact_kind="PNG",
            render_options=_base_options(),
            requested_at="2026-08-14T05:00:00Z",
            server_scope=_scope(),
            visual_capture_plan=_plan(),
            capture_id="region-side-cabin",
        )


def test_camera_request_accepts_native_pdf_stage_and_rejects_forged_policy() -> None:
    request = contract.build_canonical_camera_render_evidence_request(
        request_id="render-region-side-cabin",
        drawing_sha256="a" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"identity": "layout-001", "name": "Layout1"},
        artifact_kind="PDF",
        render_options=_base_options(),
        requested_at="2026-08-14T05:00:00Z",
        server_scope=_scope(),
        visual_capture_plan=_plan(),
        capture_id="region-side-cabin",
    )
    assert request["artifact_kind"] == "PDF"

    forged = _camera_request()
    forged["render_options"]["camera"]["margin_ratio"] = 0.05
    with pytest.raises(contract.AutoCADRenderEvidenceError, match="margin"):
        contract.validate_render_request(forged)


def test_camera_render_evidence_requires_closed_receipt_bound_to_artifact() -> None:
    request = _camera_request()
    evidence = _camera_evidence(request)
    validated = contract.validate_render_evidence(evidence, request=request)
    receipt = validated["visual_capture_receipt"]
    assert receipt["artifact_sha256"] == validated["artifact"]["sha256"]
    assert receipt["artifact_width"] == validated["artifact"]["width"]
    assert receipt["artifact_height"] == validated["artifact"]["height"]
    assert receipt["capture_id"] == request["render_options"]["camera"]["capture_id"]


def test_camera_render_evidence_rejects_missing_receipt() -> None:
    request = _camera_request()
    evidence = _camera_evidence(request)
    del evidence["visual_capture_receipt"]
    with pytest.raises(contract.AutoCADRenderEvidenceError, match="receipt"):
        contract.validate_render_evidence(evidence, request=request)


def test_camera_render_evidence_rejects_receipt_artifact_or_camera_mismatch() -> None:
    request = _camera_request()
    for field, value in (
        ("artifact_sha256", "f" * 64),
        ("artifact_width", 1),
        ("capture_id", "global-side"),
        ("requested_wcs_bbox", [0.0, 0.0, 101.0, 50.0]),
    ):
        evidence = _camera_evidence(request)
        evidence["visual_capture_receipt"][field] = value
        with pytest.raises(contract.AutoCADRenderEvidenceError, match="receipt|artifact|camera|bbox|capture"):
            contract.validate_render_evidence(evidence, request=request)


def test_legacy_request_rejects_unsolicited_camera_receipt() -> None:
    request = copy.deepcopy(_fixture()["request"])
    evidence = copy.deepcopy(_fixture()["png"])
    evidence["visual_capture_receipt"] = _camera_evidence(_camera_request())["visual_capture_receipt"]
    with pytest.raises(contract.AutoCADRenderEvidenceError, match="receipt|camera|unknown"):
        contract.validate_render_evidence(evidence, request=request)


def test_canonical_camera_request_accepts_native_pdf_stage_without_png_media() -> None:
    request = contract.build_canonical_camera_render_evidence_request(
        request_id="render-global-side-pdf",
        drawing_sha256="a" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"identity": "layout-001", "name": "Layout1"},
        artifact_kind="PDF",
        render_options=_base_options(),
        requested_at="2026-08-14T05:00:00Z",
        server_scope=_scope(),
        visual_capture_plan=_plan(),
        capture_id="global-side",
    )

    assert request["artifact_kind"] == "PDF"
    assert request["render_options"]["camera"]["capture_id"] == "global-side"
