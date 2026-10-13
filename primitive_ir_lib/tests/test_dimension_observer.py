from __future__ import annotations

import hashlib

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
    frozen_dimension_witness_image,
    frozen_dimension_witness_png,
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


def _observe_frozen_dimension_witness(case: str):
    image = frozen_dimension_witness_image(case)
    interrupted = case in {"interrupted", "unrelated_collinear_fragment", "competing_witness"}
    text_bbox = (90, 52, 126, 71) if interrupted else (90, 30, 126, 50)
    text = RawText(
        id=f"synthetic-{case}-value-140",
        content="140",
        bbox_px=text_bbox,
        rotation_deg=0.0,
        confidence=1.0,
        source="synthetic-fixture-acquisition",
        parsed_value=140.0,
        semantic_role="dimension_value",
    )
    calls = 0

    def one_observed_text(_crop: np.ndarray) -> list[RawText]:
        nonlocal calls
        calls += 1
        return [text] if calls == 1 else []

    cluster = DimensionCluster(
        cluster_id=f"SYNTH-{case.upper()}",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=(text_bbox,),
    )
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="SYNTH_PAGE",
        view_id="SYNTH_VIEW",
        source_sha256=hashlib.sha256(frozen_dimension_witness_png(case)).hexdigest(),
        ocr_reader=one_observed_text,
        semantic_anchors=[
            {"type": "SYNTHETIC_DATUM", "id": "A1", "view_id": "SYNTH_VIEW", "point_px": [40.0, 120.0], "confidence": 1.0},
            {"type": "SYNTHETIC_DATUM", "id": "A2", "view_id": "SYNTH_VIEW", "point_px": [180.0, 120.0], "confidence": 1.0},
        ],
        explicit_role="DRIVING",
        default_unit="fixture_unit",
    )
    return disposition, calls


def test_frozen_interrupted_witness_resolves_through_actual_observer() -> None:
    disposition, calls = _observe_frozen_dimension_witness("interrupted")

    assert calls == 4
    assert disposition.disposition == "CONFIRMED"
    assert disposition.observation is not None
    assert disposition.observation["status"] == "CONFIRMED"
    line = disposition.observation["extension_geometry"]["dimension_line"]
    assert abs(line[0][0] - 40.0) <= 1.0
    assert abs(line[1][0] - 180.0) <= 1.0
    assert abs(line[0][1] - 60.0) <= 1.0
    assert abs(line[1][1] - 60.0) <= 1.0
    assert len(disposition.observation["extension_geometry"]["extension_lines"]) == 2


def test_frozen_complete_witness_observer_compatibility_is_preserved() -> None:
    disposition, calls = _observe_frozen_dimension_witness("complete")

    assert calls == 4
    assert disposition.disposition == "CONFIRMED"
    assert disposition.observation is not None
    assert disposition.observation["status"] == "CONFIRMED"
    assert len(disposition.observation["extension_geometry"]["extension_lines"]) == 2


def test_insufficient_extension_evidence_stays_unresolved_in_observer() -> None:
    disposition, _ = _observe_frozen_dimension_witness("insufficient_association")

    assert disposition.disposition == "UNRESOLVED"
    assert disposition.observation is not None
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


def test_competing_witnesses_remain_unresolved_in_actual_observer() -> None:
    disposition, _ = _observe_frozen_dimension_witness("competing_witness")

    assert disposition.disposition == "UNRESOLVED"
    assert disposition.observation is not None
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


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

    assert calls == 4
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
    assert disposition.observation["provenance"]["ocr_rotations_deg"] == [0.0, 90.0, -90.0, 180.0]


def test_180_degree_only_ocr_candidate_is_parsed_and_mapped_to_original_crop() -> None:
    images: list[np.ndarray] = []
    image = synthetic_horizontal_dimension()

    def upside_down_reader(rotated: np.ndarray) -> list[RawText]:
        images.append(rotated.copy())
        if len(images) != 4:
            return []
        return [RawText(
            id="rawtext-rotated-1700",
            content="1700",
            bbox_px=(20, 15, 100, 55),
            rotation_deg=0.0,
            confidence=0.96,
            source="text_tesseract",
            parsed_value=1700.0,
            semantic_role="dimension_value",
        )]

    try:
        disposition = observe_dimension_cluster(
            image,
            horizontal_dimension_cluster(),
            page_id="PAGE-001",
            view_id="SIDE",
            source_sha256="1" * 64,
            ocr_reader=upside_down_reader,
        )
    except DimensionObserverError as exc:
        pytest.fail(f"180-degree OCR candidate was rejected: {exc}")

    assert len(images) == 4
    assert np.array_equal(images[3], cv2.rotate(images[0], cv2.ROTATE_180))
    assert disposition.observation is not None
    assert disposition.observation["value"] == 1700.0
    assert disposition.observation["raw_text_candidates"] == ["1700"]
    assert disposition.observation["ocr_evidence"] == [{
        "id": "rawtext-rotated-1700-rot180",
        "content": "1700",
        "bbox": [320.0, 85.0, 400.0, 125.0],
        "rotation_deg": 180.0,
        "confidence": 0.96,
        "source": "text_tesseract",
    }]
    assert disposition.observation["provenance"]["ocr_rotations_deg"] == [0.0, 90.0, -90.0, 180.0]


def test_cross_angle_ocr_conflict_is_not_resolved_by_rotation_majority() -> None:
    values = ("4500", "4600", "4700", "4800")
    calls = 0
    image = synthetic_horizontal_dimension()
    cluster = horizontal_dimension_cluster()

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
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=conflicting_reader,
    )

    assert calls == 4
    assert disposition.disposition == "CONFLICT"
    assert disposition.observation["raw_text_candidates"] == ["4500", "4600", "4700", "4800"]
    assert [item["rotation_deg"] for item in disposition.observation["ocr_evidence"]] == [
        0.0,
        90.0,
        -90.0,
        180.0,
    ]

    register = build_dimension_register(
        run_id="RUN-VS-T1-CONFLICT-SUMMARY",
        source_sha256="1" * 64,
        page_id="PAGE-001",
        view_id="SIDE",
        total_area_px=image.shape[0] * image.shape[1],
        inspected_area_px=image.shape[0] * image.shape[1],
        detected_cluster_ids=[cluster.cluster_id],
        dispositions=[disposition],
    )
    assert register["summary"] == {"confirmed": 0, "unresolved": 0, "conflicts": 1}
    assert validate_visual_contract(register, contract="dimension_register") == register


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
