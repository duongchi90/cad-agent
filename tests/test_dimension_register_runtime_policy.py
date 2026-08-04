from __future__ import annotations

import pytest

from cad_agent.visual_contracts import VisualContractError, require_dimension_gate_ready, validate_visual_contract
from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionObserverError,
    build_dimension_register,
    observe_dimension_cluster,
)
from primitive_ir_lib.tests.dimension_test_helpers import (
    fake_ocr_4500,
    fake_ocr_unreadable,
    horizontal_dimension_cluster,
    matching_horizontal_anchors,
    not_a_dimension_disposition,
    synthetic_horizontal_dimension,
    synthetic_isolated_number_crop,
)
from primitive_ir_lib.text_extraction import RawText


def test_zero_detected_clusters_after_full_page_inspection_is_valid() -> None:
    register = build_dimension_register(
        run_id="RUN-VS-T1-EMPTY",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=100,
        inspected_area_px=100,
        detected_cluster_ids=[],
        dispositions=[],
    )
    assert validate_visual_contract(register, contract="dimension_register") == register


def test_duplicate_dispositions_are_rejected() -> None:
    disposition = not_a_dimension_disposition("DIMCLUSTER-001")
    with pytest.raises(DimensionObserverError, match="duplicate"):
        build_dimension_register(
            run_id="RUN-VS-T1-DUPLICATE",
            source_sha256="1" * 64,
            page_id="PAGE-001",
            view_id="SIDE",
            total_area_px=100,
            inspected_area_px=100,
            detected_cluster_ids=["DIMCLUSTER-001"],
            dispositions=[disposition, disposition],
        )


def test_unreadable_cluster_preserves_empty_text_and_nulls() -> None:
    image = synthetic_isolated_number_crop()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-UNREADABLE",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=(),
    )
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_unreadable,
    )
    assert disposition.observation is not None
    assert disposition.observation["display_text"] == ""
    assert disposition.observation["value"] is None
    assert disposition.observation["unit"] is None
    assert disposition.observation["status"] == "UNRESOLVED"


def test_critical_unresolved_observation_blocks_declared_scope() -> None:
    image = synthetic_isolated_number_crop()
    cluster = DimensionCluster("DIMCLUSTER-CRITICAL", (0, 0, 180, 80), ())
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        blocker_scope=["SIDE-CABIN"],
    )
    register = build_dimension_register(
        run_id="RUN-VS-T1-BLOCKER",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=180 * 80,
        inspected_area_px=180 * 80,
        detected_cluster_ids=[cluster.cluster_id],
        dispositions=[disposition],
    )
    with pytest.raises(VisualContractError, match="SIDE-CABIN"):
        require_dimension_gate_ready(register)


def test_not_a_dimension_is_audited_outside_register_dimensions() -> None:
    register = build_dimension_register(
        run_id="RUN-VS-T1-NOTE",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=100,
        inspected_area_px=100,
        detected_cluster_ids=["DIMCLUSTER-NOTE"],
        dispositions=[not_a_dimension_disposition("DIMCLUSTER-NOTE")],
    )
    assert register["coverage"]["clusters_processed"] == 1
    assert register["dimensions"] == []


def test_matching_anchors_without_explicit_role_never_assign_driving() -> None:
    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=matching_horizontal_anchors(),
    )
    assert disposition.observation is not None
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["status"] == "UNRESOLVED"


def test_competing_readings_are_audited_as_conflict() -> None:
    def conflicting_reader(image_bgr) -> list[RawText]:
        del image_bgr
        return [
            RawText("raw-100", "100", (20, 15, 80, 55), 0.0, 0.90, "text_tesseract"),
            RawText("raw-200", "200", (20, 15, 80, 55), 0.0, 0.89, "text_tesseract"),
        ]

    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=conflicting_reader,
    )
    assert disposition.disposition == "CONFLICT"
    assert disposition.observation is not None
    assert disposition.observation["role"] == "CONFLICT"
    assert disposition.observation["status"] == "CONFLICT"
