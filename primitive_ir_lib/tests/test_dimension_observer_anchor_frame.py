from __future__ import annotations

import copy

import numpy as np
import pytest

from primitive_ir_lib.dimension_observer import (
    DimensionCluster,
    DimensionObserverError,
    observe_dimension_cluster,
)
from primitive_ir_lib.tests.dimension_test_helpers import (
    fake_ocr_4500,
    matching_horizontal_anchors,
    synthetic_horizontal_dimension,
)


SOURCE_SHA256 = "a" * 64


def _observe(
    image: np.ndarray,
    cluster: DimensionCluster,
    anchors: list[dict[str, object]],
    *,
    anchor_coordinate_mode: str | None = None,
):
    kwargs: dict[str, object] = {}
    if anchor_coordinate_mode is not None:
        kwargs["anchor_coordinate_mode"] = anchor_coordinate_mode
    return observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-ANCHOR-FRAME",
        view_id="SIDE",
        source_sha256=SOURCE_SHA256,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=anchors,
        explicit_role="REFERENCE",
        default_unit="mm",
        **kwargs,
    )


def _cluster(bbox: tuple[int, int, int, int]) -> DimensionCluster:
    return DimensionCluster(
        cluster_id="DIM-ANCHOR-FRAME-001",
        bbox_px=bbox,
        member_boxes=((bbox[0] + 160, bbox[1] + 5, bbox[0] + 260, bbox[1] + 35),),
    )


def _translated_anchors(dx: int, dy: int) -> list[dict[str, object]]:
    anchors = copy.deepcopy(matching_horizontal_anchors())
    for anchor in anchors:
        point = anchor["point_px"]
        anchor["point_px"] = [point[0] + dx, point[1] + dy]
    return anchors


def test_page_anchors_preserve_attachment_evidence_across_nonzero_crop_translation() -> None:
    crop = synthetic_horizontal_dimension()
    origin_cluster = _cluster((0, 0, 420, 140))
    origin = _observe(crop, origin_cluster, matching_horizontal_anchors(), anchor_coordinate_mode="page")

    translated_page = np.full((210, 500, 3), 255, dtype=np.uint8)
    translated_page[20:160, 30:450] = crop
    translated_cluster = _cluster((30, 20, 450, 160))
    translated = _observe(
        translated_page,
        translated_cluster,
        _translated_anchors(30, 20),
        anchor_coordinate_mode="page",
    )

    assert translated.observation is not None
    assert origin.observation is not None
    assert translated.observation["attachment_candidates"] == origin.observation["attachment_candidates"]
    assert translated.observation["attachment_confidence"] == origin.observation["attachment_confidence"]
    assert translated.observation["extension_geometry"] == origin.observation["extension_geometry"]


def test_omitted_anchor_mode_preserves_legacy_behavior() -> None:
    image = synthetic_horizontal_dimension()
    cluster = _cluster((0, 0, 420, 140))
    anchors = matching_horizontal_anchors()

    implicit_legacy = _observe(image, cluster, anchors)
    explicit_legacy = _observe(image, cluster, anchors, anchor_coordinate_mode="legacy")

    assert explicit_legacy == implicit_legacy


def test_page_anchor_mode_does_not_mutate_caller_anchor_data() -> None:
    image = np.full((210, 500, 3), 255, dtype=np.uint8)
    image[20:160, 30:450] = synthetic_horizontal_dimension()
    anchors = _translated_anchors(30, 20)
    before = copy.deepcopy(anchors)

    _observe(
        image,
        _cluster((30, 20, 450, 160)),
        anchors,
        anchor_coordinate_mode="page",
    )

    assert anchors == before


def test_page_anchor_mode_uses_clipped_crop_origin() -> None:
    image = synthetic_horizontal_dimension()
    anchors = matching_horizontal_anchors()
    origin = _observe(image, _cluster((0, 0, 420, 140)), anchors, anchor_coordinate_mode="page")
    clipped = _observe(image, _cluster((-15, -10, 420, 140)), anchors, anchor_coordinate_mode="page")

    assert clipped.observation is not None
    assert origin.observation is not None
    assert clipped.observation["source_evidence"]["bbox"] == [0.0, 0.0, 420.0, 140.0]
    assert clipped.observation["attachment_candidates"] == origin.observation["attachment_candidates"]


def test_observer_rejects_unsupported_anchor_coordinate_mode() -> None:
    with pytest.raises(DimensionObserverError, match="anchor_coordinate_mode"):
        _observe(
            synthetic_horizontal_dimension(),
            _cluster((0, 0, 420, 140)),
            matching_horizontal_anchors(),
            anchor_coordinate_mode="view",
        )
