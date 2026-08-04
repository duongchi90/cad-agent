from __future__ import annotations

import cv2
import numpy as np
import pytest

from cad_agent.visual_contracts import validate_visual_contract
from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionObserverError,
    build_dimension_register,
    detect_dimension_clusters,
    observe_dimension_cluster,
)
from primitive_ir_lib.tests.dimension_test_helpers import (
    fake_ocr_4500,
    fake_ocr_unreadable_leader,
    fake_ocr_unreadable,
    horizontal_dimension_cluster,
    matching_horizontal_anchors,
    not_a_dimension_disposition,
    synthetic_horizontal_dimension,
    synthetic_isolated_number_crop,
    synthetic_leader_annotation,
    synthetic_unreadable_leader_geometry,
    synthetic_page_with_two_unreadable_dimensions_and_note,
)
from primitive_ir_lib.text_extraction import RawText


def test_number_without_attachment_is_unresolved_and_ambiguous() -> None:
    image = synthetic_isolated_number_crop()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-001",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=((20, 20, 100, 55),),
    )
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
    )
    assert disposition.observation is not None
    assert disposition.observation["value"] == 4500.0
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


def test_text_and_geometry_clusters_both_receive_dispositions() -> None:
    page = np.full((300, 700, 3), 255, dtype=np.uint8)
    cv2.putText(page, "TITLE NOTE", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.line(page, (260, 135), (610, 135), (0, 0, 0), 2)
    cv2.line(page, (260, 135), (260, 270), (0, 0, 0), 2)
    cv2.line(page, (610, 135), (610, 270), (0, 0, 0), 2)
    cv2.fillConvexPoly(
        page,
        np.array([[260, 135], [276, 128], [276, 142]], dtype=np.int32),
        (0, 0, 0),
    )
    cv2.fillConvexPoly(
        page,
        np.array([[610, 135], [594, 128], [594, 142]], dtype=np.int32),
        (0, 0, 0),
    )

    clusters = detect_dimension_clusters(page)
    dispositions = [
        observe_dimension_cluster(
            page,
            cluster,
            page_id="PAGE-001",
            view_id="SIDE",
            source_sha256="1" * 64,
            ocr_reader=fake_ocr_unreadable,
        )
        for cluster in clusters
    ]

    assert len(clusters) >= 2
    assert len(dispositions) == len(clusters)
    assert any(
        disposition.observation is not None
        and disposition.observation["extension_geometry"]["dimension_line"] is not None
        for disposition in dispositions
    )


def test_two_geometry_only_regions_each_get_disposition_and_register_accounting() -> None:
    page = synthetic_page_with_two_unreadable_dimensions_and_note()
    clusters = detect_dimension_clusters(page)
    geometry_clusters = [cluster for cluster in clusters if cluster.bbox_px[1] >= 80]
    dispositions = [
        observe_dimension_cluster(
            page,
            cluster,
            page_id="PAGE-001",
            view_id="SIDE",
            source_sha256="1" * 64,
            ocr_reader=fake_ocr_unreadable,
        )
        for cluster in clusters
    ]
    dispositions_by_cluster = {
        disposition.cluster_id: disposition for disposition in dispositions
    }

    register = build_dimension_register(
        run_id="RUN-VS-T1-TWO-GEOMETRY",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=page.shape[0] * page.shape[1],
        inspected_area_px=page.shape[0] * page.shape[1],
        detected_cluster_ids=[cluster.cluster_id for cluster in clusters],
        dispositions=dispositions,
    )

    assert len(geometry_clusters) == 2
    assert all(
        dispositions_by_cluster[cluster.cluster_id].observation is not None
        and dispositions_by_cluster[cluster.cluster_id].observation["extension_geometry"]["dimension_line"]
        is not None
        for cluster in geometry_clusters
    )
    assert len(dispositions) == len(clusters)
    assert register["coverage"] == {
        "clusters_detected": len(clusters),
        "clusters_processed": len(clusters),
        "page_coverage_percent": 100.0,
    }
    assert validate_visual_contract(register, contract="dimension_register") == register


def test_rotated_ocr_candidate_is_fused_and_mapped_to_original_crop() -> None:
    calls = 0

    def rotated_reader(image: np.ndarray) -> list[RawText]:
        nonlocal calls
        calls += 1
        if calls != 2:
            return []
        return [RawText(
            id="rawtext-rotated-4500",
            content="4500",
            bbox_px=(20, 15, 100, 55),
            rotation_deg=0.0,
            confidence=0.95,
            source="text_tesseract",
            parsed_value=4500.0,
            semantic_role="dimension_value",
        )]

    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=rotated_reader,
    )

    assert calls == 3
    assert disposition.observation["value"] == 4500.0
    assert disposition.observation["raw_text_candidates"] == ["4500"]
    assert disposition.observation["ocr_evidence"] == [{
        "id": "rawtext-rotated-4500-rot90",
        "content": "4500",
        "bbox": [15.0, 40.0, 55.0, 120.0],
        "rotation_deg": 90.0,
        "confidence": 0.95,
        "source": "text_tesseract",
    }]
    assert disposition.observation["provenance"]["ocr_rotations_deg"] == [0.0, 90.0, -90.0]


def test_cross_angle_ocr_conflict_is_not_resolved_by_rotation_majority() -> None:
    values = ("4500", "4600", "4700")
    calls = 0

    def conflicting_reader(image: np.ndarray) -> list[RawText]:
        nonlocal calls
        value = values[calls]
        calls += 1
        numeric_value = float(value)
        return [RawText(
            id=f"rawtext-{value}",
            content=value,
            bbox_px=(20, 15, 100, 55),
            rotation_deg=0.0,
            confidence=0.90,
            source="text_tesseract",
            parsed_value=numeric_value,
            semantic_role="dimension_value",
        )]

    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=conflicting_reader,
    )

    assert calls == 3
    assert disposition.disposition == "CONFLICT"
    assert disposition.observation["raw_text_candidates"] == ["4500", "4600", "4700"]
    assert [item["rotation_deg"] for item in disposition.observation["ocr_evidence"]] == [
        0.0,
        90.0,
        -90.0,
    ]


def test_leader_lines_are_preserved_in_closed_observer_evidence() -> None:
    image = synthetic_leader_annotation()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-LEADER",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=(),
    )
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
    )

    assert len(disposition.observation["extension_geometry"]["leader_lines"]) == 1
    register = build_dimension_register(
        run_id="RUN-VS-T1-LEADER",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=image.shape[0] * image.shape[1],
        inspected_area_px=image.shape[0] * image.shape[1],
        detected_cluster_ids=[cluster.cluster_id],
        dispositions=[disposition],
    )
    assert validate_visual_contract(register, contract="dimension_register")["dimensions"][0][
        "extension_geometry"
    ]["leader_lines"]


def test_unreadable_leader_ocr_is_unresolved_with_null_value_and_leader_evidence() -> None:
    image = synthetic_unreadable_leader_geometry()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-UNREADABLE-LEADER",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=(),
    )

    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_unreadable_leader,
    )

    assert disposition.disposition == "UNRESOLVED"
    assert disposition.observation is not None
    assert disposition.observation["value"] is None
    assert disposition.observation["unit"] is None
    assert disposition.observation["raw_text_candidates"] == ["8O?O"]
    assert disposition.observation["extension_geometry"]["dimension_line"] is None
    assert disposition.observation["extension_geometry"]["leader_lines"]


def test_critical_flag_is_independent_of_blocker_scope() -> None:
    image = synthetic_isolated_number_crop()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-001",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=((20, 20, 100, 55),),
    )

    critical_without_scope = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        critical=True,
    )
    noncritical_with_scope = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        critical=False,
        blocker_scope=["SIDE-CABIN"],
    )

    assert critical_without_scope.observation["critical"] is True
    assert critical_without_scope.observation["blocker_scope"] == []
    assert noncritical_with_scope.observation["critical"] is False
    assert noncritical_with_scope.observation["blocker_scope"] == ["SIDE-CABIN"]


def test_resolved_attachment_without_explicit_role_remains_unresolved() -> None:
    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role=None,
    )
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "role_unresolved" in disposition.reasons


def test_explicit_reference_role_may_confirm_resolved_observation() -> None:
    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role="REFERENCE",
        default_unit="mm",
    )
    assert disposition.observation["role"] == "REFERENCE"
    assert disposition.observation["status"] == "CONFIRMED"


def test_register_rejects_missing_cluster_disposition() -> None:
    with pytest.raises(DimensionObserverError, match="disposition"):
        build_dimension_register(
            run_id="RUN-VS-T1-001",
            source_sha256="1" * 64,
            page_id="PAGE-001",
            view_id="SIDE",
            total_area_px=10000,
            inspected_area_px=10000,
            detected_cluster_ids=["DIMCLUSTER-001", "DIMCLUSTER-002"],
            dispositions=[not_a_dimension_disposition("DIMCLUSTER-001")],
        )
