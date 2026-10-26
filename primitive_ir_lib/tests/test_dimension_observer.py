from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil

import cv2
import numpy as np
import pytest

from cad_agent.visual_contracts import validate_visual_contract
from primitive_ir_lib.dimension_geometry import DimensionGeometryEvidence
from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionObserverError,
    _roi_supports_dimension_line,
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
from primitive_ir_lib.text_extraction import RawText, extract_text_tesseract


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


def test_rotated_ocr_candidate_is_fused_and_mapped_to_original_crop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [],
    )
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


def test_180_degree_only_ocr_candidate_is_parsed_and_mapped_to_original_crop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [],
    )
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


def test_multiple_text_rois_keep_cross_angle_ocr_conflict_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [(10, 10, 40, 30), (80, 10, 110, 30)],
    )
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


def test_unique_roi_with_no_ocr_tokens_falls_back_to_full_cluster_crop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = synthetic_horizontal_dimension()
    full_area = image.shape[0] * image.shape[1]
    seen_areas: list[int] = []

    def reader(crop: np.ndarray) -> list[RawText]:
        area = crop.shape[0] * crop.shape[1]
        seen_areas.append(area)
        if area < full_area:
            return []
        return [RawText(
            id="rawtext-full-crop-4500",
            content="4500",
            bbox_px=(170, 5, 230, 35),
            rotation_deg=0.0,
            confidence=0.92,
            source="text_tesseract",
            parsed_value=4500.0,
            semantic_role="dimension_value",
        )]

    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [],
    )
    baseline = observe_dimension_cluster(
        image,
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=reader,
    )
    assert baseline.observation is not None
    assert baseline.observation["value"] == 4500.0
    seen_areas.clear()

    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [(160, 5, 260, 35)],
    )
    disposition = observe_dimension_cluster(
        image,
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=reader,
    )

    assert seen_areas == [30 * 100] * 4 + [full_area] * 4
    assert disposition.observation is not None
    assert disposition.observation["value"] == 4500.0
    assert disposition.observation["source_evidence"]["crop_sha256"] == baseline.observation[
        "source_evidence"
    ]["crop_sha256"]
    assert disposition.observation["raw_text_candidates"] == ["4500"]
    assert disposition.observation["source_evidence"]["bbox"] == [0.0, 0.0, 420.0, 140.0]
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["attachment_candidates"] == []


def test_unique_roi_cannot_suppress_full_crop_conflict_when_confirmation_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = synthetic_horizontal_dimension()
    full_area = image.shape[0] * image.shape[1]

    def text(value: str, bbox: tuple[int, int, int, int], confidence: float) -> RawText:
        return RawText(
            id=f"rawtext-{value}",
            content=value,
            bbox_px=bbox,
            rotation_deg=0.0,
            confidence=confidence,
            source="text_tesseract",
            parsed_value=float(value),
            semantic_role="dimension_value",
        )

    def reader(crop: np.ndarray) -> list[RawText]:
        if crop.shape[0] * crop.shape[1] < full_area:
            return [text("4500", (20, 5, 80, 25), 0.92)]
        return [
            text("4500", (170, 5, 230, 35), 0.92),
            text("4600", (260, 5, 320, 35), 0.91),
        ]

    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [],
    )
    baseline = observe_dimension_cluster(
        image,
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=reader,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role="REFERENCE",
        default_unit="mm",
    )
    assert baseline.disposition == "CONFLICT"

    monkeypatch.setattr(
        "primitive_ir_lib.dimension_observer.detect_text_candidate_rois",
        lambda _: [(160, 5, 260, 35)],
    )
    candidate = observe_dimension_cluster(
        image,
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=reader,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role="REFERENCE",
        default_unit="mm",
    )

    assert candidate.disposition == "CONFLICT"
    assert candidate.observation is not None
    assert candidate.observation["status"] == "CONFLICT"
    assert set(candidate.observation["raw_text_candidates"]) == {"4500", "4600"}


def test_unrelated_text_roi_away_from_dimension_line_is_not_selected() -> None:
    geometry = DimensionGeometryEvidence(
        dimension_line=((20.0, 50.0), (180.0, 50.0)),
        extension_lines=(),
        arrow_points=((20.0, 50.0), (180.0, 50.0)),
        leader_lines=(),
        kind_hint="HORIZONTAL_DISTANCE",
        confidence=0.85,
    )

    assert _roi_supports_dimension_line((80, 38, 120, 48), geometry)
    assert not _roi_supports_dimension_line((80, 5, 120, 25), geometry)


@pytest.mark.real_data
def test_nakuja_unique_rotated_text_roi_recovers_value_without_resolving_association(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_value = os.environ.get("CAD_AGENT_CASE01_LINE_IMAGE")
    if not image_value:
        pytest.skip("set CAD_AGENT_CASE01_LINE_IMAGE to run the frozen Nakuja OCR regression")
    image_path = Path(image_value)
    image_bytes = image_path.read_bytes()
    assert hashlib.sha256(image_bytes).hexdigest() == (
        "5732b6014ec1c1d3b05e14c598b43ebec84a4d6198951264215a69fb7b0a0bc8"
    )

    tesseract = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if not tesseract and Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").is_file():
        tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if not tesseract:
        pytest.skip("Tesseract is unavailable for the frozen Nakuja OCR regression")
    import pytesseract

    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", tesseract)
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    cluster = next(
        cluster for cluster in detect_dimension_clusters(image)
        if cluster.cluster_id == "DIMCLUSTER-001"
    )

    def read_english_psm11(crop: np.ndarray) -> list[RawText]:
        height, width = crop.shape[:2]
        return extract_text_tesseract(
            crop,
            roi_boxes=[(0, 0, width, height)],
            lang="eng",
            psm=11,
        )

    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-NAKUJA-P01",
        view_id="SIDE",
        source_sha256=(
            "c9411e6769725c252425da18380a76b4db07036ad2b7801ceabc11d17f8a246c"
        ),
        ocr_reader=read_english_psm11,
    )

    assert disposition.disposition == "UNRESOLVED"
    assert disposition.observation is not None
    assert disposition.observation["display_text"] == "10,00"
    assert disposition.observation["value"] == 10.0
    assert "10,00" in disposition.observation["raw_text_candidates"]
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["attachment_candidates"] == []
    assert disposition.observation["source_evidence"]["bbox"] == [
        122.0,
        206.0,
        178.0,
        381.0,
    ]
    assert disposition.observation["source_evidence"]["crop_sha256"] == (
        "3c573e3b1543c62718da457fe8025a5005b3d277cacf31209573360fd7321f00"
    )
    assert disposition.observation["extension_geometry"]["dimension_line"] == [
        [38.0, 18.0],
        [38.0, 157.0],
    ]
    assert any(
        item["content"] == "10,00" and item["rotation_deg"] == 90.0
        for item in disposition.observation["ocr_evidence"]
    )


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


def _shifted_dimension_page(*, ambiguous_continuation: bool = False) -> tuple[np.ndarray, DimensionCluster, list[dict[str, object]]]:
    page = np.full((360, 760, 3), 255, dtype=np.uint8)
    source = synthetic_horizontal_dimension()
    offset_x, offset_y = 130, 70
    page[offset_y : offset_y + source.shape[0], offset_x : offset_x + source.shape[1]] = source
    first_feature_y = offset_y + 115
    cv2.line(
        page,
        (offset_x + 80, first_feature_y),
        (offset_x + 340, first_feature_y),
        (0, 0, 0),
        2,
    )
    anchors = [
        {
            "type": "FEATURE",
            "id": "FEATURE-LEFT-TOP",
            "view_id": "SIDE",
            "point_px": [float(offset_x + 80), float(first_feature_y)],
            "confidence": 1.0,
        },
        {
            "type": "FEATURE",
            "id": "FEATURE-RIGHT-TOP",
            "view_id": "SIDE",
            "point_px": [float(offset_x + 340), float(first_feature_y)],
            "confidence": 1.0,
        },
    ]
    if ambiguous_continuation:
        second_feature_y = first_feature_y + 20
        for x in (offset_x + 80, offset_x + 340):
            cv2.line(page, (x, first_feature_y), (x, second_feature_y), (0, 0, 0), 2)
        cv2.line(
            page,
            (offset_x + 80, second_feature_y),
            (offset_x + 340, second_feature_y),
            (0, 0, 0),
            2,
        )
        anchors.extend(
            [
                {
                    "type": "FEATURE",
                    "id": "FEATURE-LEFT-CONTINUATION",
                    "view_id": "SIDE",
                    "point_px": [float(offset_x + 80), float(second_feature_y)],
                    "confidence": 1.0,
                },
                {
                    "type": "FEATURE",
                    "id": "FEATURE-RIGHT-CONTINUATION",
                    "view_id": "SIDE",
                    "point_px": [float(offset_x + 340), float(second_feature_y)],
                    "confidence": 1.0,
                },
            ]
        )
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-SHIFTED",
        bbox_px=(offset_x, offset_y, offset_x + 420, offset_y + 60),
        member_boxes=((offset_x + 160, offset_y + 5, offset_x + 260, offset_y + 35),),
    )
    return page, cluster, anchors


def test_source_context_preserves_dimension_identity_and_translates_page_anchors() -> None:
    page, cluster, anchors = _shifted_dimension_page()
    forward = observe_dimension_cluster(
        page,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=anchors,
    )
    reverse = observe_dimension_cluster(
        page,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=list(reversed(anchors)),
    )

    assert forward.observation is not None and reverse.observation is not None
    assert forward.observation["source_evidence"]["bbox"] == [130.0, 70.0, 550.0, 130.0]
    assert forward.observation["extension_geometry"]["dimension_line"][0][1] == 33.0
    assert len(forward.observation["extension_geometry"]["extension_lines"]) == 2
    assert "attachment_unresolved" not in forward.reasons
    assert forward.observation["status"] == "UNRESOLVED"
    assert "role_unresolved" in forward.reasons
    assert forward.observation["attachment_candidates"][0] == reverse.observation["attachment_candidates"][0]
    assert {
        forward.observation["attachment_candidates"][0]["from_ref"]["id"],
        forward.observation["attachment_candidates"][0]["to_ref"]["id"],
    } == {"FEATURE-LEFT-TOP", "FEATURE-RIGHT-TOP"}
    assert {
        forward.observation["attachment_candidates"][0]["from_ref"]["type"],
        forward.observation["attachment_candidates"][0]["to_ref"]["type"],
    } == {"FEATURE"}


def test_wrong_view_anchors_are_excluded_from_association_candidates() -> None:
    anchors = matching_horizontal_anchors()
    for anchor in anchors:
        anchor["type"] = "FEATURE"
        anchor["view_id"] = "OTHER"
        anchor["confidence"] = 3.0

    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=anchors,
        explicit_role="DRIVING",
        default_unit="mm",
    )

    assert disposition.observation is not None
    assert disposition.observation["attachment_candidates"] == []
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf"), 3.0])
def test_out_of_range_anchor_confidence_cannot_resolve_association(confidence: float) -> None:
    anchors = matching_horizontal_anchors()
    for anchor in anchors:
        anchor["type"] = "FEATURE"
        anchor["confidence"] = confidence

    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=anchors,
        explicit_role="DRIVING",
        default_unit="mm",
    )

    assert disposition.observation is not None
    assert disposition.observation["attachment_candidates"] == []
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


def test_competing_feature_intersections_on_a_collinear_continuation_stay_unresolved() -> None:
    page, cluster, anchors = _shifted_dimension_page(ambiguous_continuation=True)
    disposition = observe_dimension_cluster(
        page,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=anchors,
    )

    assert disposition.observation is not None
    candidates = disposition.observation["attachment_candidates"]
    assert sum(float(item["confidence"]) >= 0.85 for item in candidates) >= 2
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


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
