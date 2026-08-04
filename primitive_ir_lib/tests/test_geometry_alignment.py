from __future__ import annotations

import numpy as np
import pytest

from primitive_ir_lib.geometry_alignment import (
    estimate_photograph_alignment,
    estimate_similarity_alignment,
    warp_to_reference,
)
from primitive_ir_lib.tests.geometry_test_helpers import (
    four_collinear_anchors,
    four_perspective_anchors,
    five_perspective_anchors,
    identity_anchor_pairs,
    nonuniform_three_anchor_pairs,
    reflected_anchor_pairs,
    synthetic_similarity_anchor_pairs,
)


def test_similarity_fit_recovers_controlled_transform() -> None:
    anchors = synthetic_similarity_anchor_pairs(
        translation=(12.0, -7.0), rotation_deg=2.0, scale=1.1
    )
    result = estimate_similarity_alignment(anchors)
    assert result.status == "ALIGNED"
    assert result.method == "VERIFIED_ANCHOR_SIMILARITY"
    assert result.residual_rms_px == pytest.approx(0.0, abs=1e-6)

    matrix = np.asarray(result.matrix, dtype=np.float64)
    cad_point = np.array([*anchors[0].cad_px, 1.0], dtype=np.float64)
    assert matrix @ cad_point == pytest.approx((*anchors[0].reference_px,), abs=1e-6)


def test_similarity_fit_refuses_one_anchor() -> None:
    result = estimate_similarity_alignment([identity_anchor_pairs()[0]])
    assert result.status == "FAILED"
    assert "two" in " ".join(result.reasons).lower()


def test_similarity_fit_refuses_reflection_and_three_point_nonuniform_mapping() -> None:
    assert estimate_similarity_alignment(reflected_anchor_pairs()).status == "FAILED"
    assert estimate_similarity_alignment(nonuniform_three_anchor_pairs()).status == "FAILED"


def test_similarity_fit_is_deterministic() -> None:
    source = identity_anchor_pairs()
    assert estimate_similarity_alignment(source) == estimate_similarity_alignment(source)


def test_homography_requires_photograph_flag() -> None:
    result = estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=False
    )
    assert result.status == "FAILED"


def test_homography_requires_boolean_photograph_flag() -> None:
    result = estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=1  # type: ignore[arg-type]
    )
    assert result.status == "FAILED"


def test_homography_accepts_exactly_four_noncollinear_anchors() -> None:
    result = estimate_photograph_alignment(
        four_perspective_anchors(), source_is_photograph=True
    )
    assert result.status == "ALIGNED"
    assert result.method == "APPROVED_PHOTOGRAPH_HOMOGRAPHY"
    assert result.residual_rms_px == pytest.approx(0.0, abs=1e-6)


def test_homography_refuses_wrong_count_and_collinearity() -> None:
    assert estimate_photograph_alignment(
        five_perspective_anchors(), source_is_photograph=True
    ).status == "FAILED"
    assert estimate_photograph_alignment(
        four_collinear_anchors(), source_is_photograph=True
    ).status == "FAILED"


def test_warp_to_reference_uses_controlled_mask_interpolation() -> None:
    image = np.zeros((4, 4), dtype=np.uint8)
    image[1, 1] = 255
    alignment = estimate_similarity_alignment(
        [
            *identity_anchor_pairs()[:2],
        ]
    )
    warped = warp_to_reference(image, alignment, output_size=(6, 6), is_mask=True)
    assert warped.dtype == np.uint8
    assert set(np.unique(warped)) <= {0, 255}
    assert warped[1, 1] == 255


def test_warp_to_reference_rejects_failed_alignment() -> None:
    failed = estimate_similarity_alignment([identity_anchor_pairs()[0]])
    with pytest.raises(ValueError, match="ALIGNED"):
        warp_to_reference(np.zeros((4, 4), dtype=np.uint8), failed, output_size=(4, 4), is_mask=True)
