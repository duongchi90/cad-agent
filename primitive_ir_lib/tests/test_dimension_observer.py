from __future__ import annotations

import cv2
import numpy as np
import pytest

from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionObserverError,
    build_dimension_register,
    detect_dimension_clusters,
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
