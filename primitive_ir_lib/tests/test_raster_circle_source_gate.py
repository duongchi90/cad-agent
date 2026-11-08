"""Causal checks for raster circle admission against visible source strokes."""

import hashlib
import os
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

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


def test_bscm_hough_false_circle_remains_an_unsupported_negative_control() -> None:
    """Keep the public-domain BSCM false proposal as an oracle, not an unsafe gate.

    Source: Mati / BSCM 3.4 (1926), International Six Metre Archive,
    https://6metrearchive.org/the-archive/mati-line-drawing/ (public domain).
    Source PDF SHA-256: 8d074b74f816a992b79d46e264b22d50ff5eb84529dabe7349696f896c181139.
    Fixture is a 230x234 crop of its 72-DPI render. This diagnostic verifies
    that the Hough proposal lacks distributed source-stroke support; it does
    not claim the current production path safely rejects it.
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


def test_raster_circle_with_distributed_source_stroke_remains_admitted() -> None:
    image = np.full((500, 500, 3), 220, dtype=np.uint8)
    cv2.circle(image, (250, 250), 100, (25, 25, 25), 3, lineType=cv2.LINE_AA)

    detected = extract_raw_geometry(image, preset="real_scan_tuned_v1").circles

    assert any(
        np.hypot(circle.center_px[0] - 250, circle.center_px[1] - 250) <= 8
        and abs(circle.radius_px - 100) <= 8
        for circle in detected
    ), detected


@pytest.mark.real_data
def test_b041_tuned_raster_only_path_keeps_the_source_m12_circle() -> None:
    """A true full-circle PDF stroke must survive the ordinary Hough-only path."""
    pdf_value = os.environ.get("CAD_AGENT_B041_CIRCLE_PDF")
    if not pdf_value:
        pytest.skip("set CAD_AGENT_B041_CIRCLE_PDF to the approved private B041 PDF")
    pdf_path = Path(pdf_value)
    assert pdf_path.is_file(), "CAD_AGENT_B041_CIRCLE_PDF must point to the approved PDF"
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    ), "B041 source identity changed"

    expected_pdf_circle = (161.55, 401.59, 17.01)
    with fitz.open(pdf_path) as document:
        page = document[0]
        matching_paths = []
        for drawing in page.get_drawings():
            rect = drawing["rect"]
            if (
                abs((rect.x0 + rect.x1) / 2 - expected_pdf_circle[0]) <= 0.01
                and abs((rect.y0 + rect.y1) / 2 - expected_pdf_circle[1]) <= 0.01
                and abs(rect.width / 2 - expected_pdf_circle[2]) <= 0.01
                and abs(rect.height / 2 - expected_pdf_circle[2]) <= 0.01
            ):
                matching_paths.append(drawing)
        path = next(
            (drawing for drawing in matching_paths
             if len(drawing["items"]) == 4 and all(item[0] == "c" for item in drawing["items"])),
            None,
        )
        assert path is not None, "the expected full four-cubic source circle was not found"
        first_point = path["items"][0][1]
        last_point = path["items"][-1][-1]
        assert np.hypot(first_point.x - last_point.x, first_point.y - last_point.y) <= 0.01

        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        assert pixmap.n == 3
        rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, 3
        )
        image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    expected_center_px = (expected_pdf_circle[0] * 2, expected_pdf_circle[1] * 2)
    expected_radius_px = expected_pdf_circle[2] * 2
    detected = extract_raw_geometry(image, preset="real_scan_tuned_v1").circles
    assert any(
        np.hypot(circle.center_px[0] - expected_center_px[0],
                 circle.center_px[1] - expected_center_px[1]) <= 5
        and abs(circle.radius_px - expected_radius_px) <= 5
        for circle in detected
    ), f"raster-only tuned path dropped source circle; proposals={detected}"
