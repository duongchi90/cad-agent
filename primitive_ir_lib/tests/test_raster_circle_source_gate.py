"""Causal checks for raster circle admission against visible source strokes."""

from pathlib import Path

import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import (
    _circle_has_distributed_source_support,
    extract_circles,
    extract_raw_geometry,
)


_BSCM_FALSE_CIRCLE = Path(__file__).parent / "fixtures" / "BSCM_3_4_false_circle_crop.png"
_BSCM_CANDIDATE_CENTER = (122.5, 112.5)
_BSCM_CANDIDATE_RADIUS = 78.3


def _near_bscm_candidate(circle) -> bool:
    return (
        np.hypot(
            circle.center_px[0] - _BSCM_CANDIDATE_CENTER[0],
            circle.center_px[1] - _BSCM_CANDIDATE_CENTER[1],
        ) <= 12.0
        and abs(circle.radius_px - _BSCM_CANDIDATE_RADIUS) <= 15.0
    )


def test_bscm_hough_circle_without_distributed_source_stroke_is_not_admitted() -> None:
    """The public-domain BSCM 3.4 raster contains a linework-induced false circle.

    Source: Mati / BSCM 3.4 (1926), International Six Metre Archive,
    https://6metrearchive.org/the-archive/mati-line-drawing/ (public domain).
    Source PDF SHA-256: 8d074b74f816a992b79d46e264b22d50ff5eb84529dabe7349696f896c181139.
    Fixture is a 230x234 crop of its 72-DPI render; no circle annotation or
    expected editable drawing is asserted by this focused detector regression.
    """
    image = cv2.imread(str(_BSCM_FALSE_CIRCLE), cv2.IMREAD_COLOR)
    assert image is not None, f"missing BSCM fixture: {_BSCM_FALSE_CIRCLE}"

    raw_candidates = extract_circles(image)
    candidate = next((circle for circle in raw_candidates if _near_bscm_candidate(circle)), None)
    assert candidate is not None, "fixture no longer reproduces the BSCM Hough proposal"

    source_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    assert not _circle_has_distributed_source_support(
        source_gray, *candidate.center_px, candidate.radius_px
    ), "the selected BSCM proposal must remain unsupported by a distributed source stroke"

    admitted = extract_raw_geometry(image, preset="real_scan_tuned_v1").circles
    assert not any(_near_bscm_candidate(circle) for circle in admitted), admitted


def test_raster_circle_with_distributed_source_stroke_remains_admitted() -> None:
    image = np.full((500, 500, 3), 220, dtype=np.uint8)
    cv2.circle(image, (250, 250), 100, (25, 25, 25), 3, lineType=cv2.LINE_AA)

    detected = extract_raw_geometry(image).circles

    assert any(
        np.hypot(circle.center_px[0] - 250, circle.center_px[1] - 250) <= 8
        and abs(circle.radius_px - 100) <= 8
        for circle in detected
    ), detected


def test_unsupported_candidate_does_not_deduplicate_nearby_supported_circle(monkeypatch) -> None:
    image = np.full((500, 500, 3), 220, dtype=np.uint8)
    cv2.circle(image, (250, 250), 100, (25, 25, 25), 3, lineType=cv2.LINE_AA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    proposals = np.array([[[265.0, 250.0, 100.0], [250.0, 250.0, 100.0]]])
    monkeypatch.setattr(cv2, "HoughCircles", lambda *_args, **_kwargs: proposals)

    supported = extract_circles(
        image,
        source_support_validator=lambda x, y, radius: (
            _circle_has_distributed_source_support(gray, x, y, radius)
        ),
    )

    assert len(supported) == 1
    assert supported[0].center_px == (250.0, 250.0)
