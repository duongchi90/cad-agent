"""Generator for the 81-case Blind Adversarial Circle Admissibility Matrix.

Phase 4 & Phase 5 of ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015.
Generates deterministic synthetic and real test fixtures, computes SHA256 hashes,
and emits BLIND_CIRCLE_MATRIX.json frozen before rule tuning.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

cv2 = importlib.import_module("cv2")


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def create_blank(width: int = 400, height: int = 400, bg: int = 255) -> np.ndarray:
    return np.full((height, width, 3), bg, dtype=np.uint8)


def generate_all_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # POSITIVE REAL-CIRCLE FAMILY (P01 - P24)
    # -------------------------------------------------------------
    # P01: complete thin circle
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 1, cv2.LINE_AA)
    p01_path = FIXTURE_DIR / "P01.png"
    cv2.imwrite(str(p01_path), img)
    cases.append({
        "case_id": "P01", "class": "POSITIVE_REAL_CIRCLE", "name": "complete_thin_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 1.0}],
        "rationale": "Canonical thin complete engineering circle with AA rendering.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 101,
        "fixture_relpath": "fixtures/P01.png", "fixture_sha256": sha256_file(p01_path),
    })

    # P02: complete thick circle
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 4, cv2.LINE_AA)
    p02_path = FIXTURE_DIR / "P02.png"
    cv2.imwrite(str(p02_path), img)
    cases.append({
        "case_id": "P02", "class": "POSITIVE_REAL_CIRCLE", "name": "complete_thick_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 4.0}],
        "rationale": "Heavy lineweight complete circle with double-boundary Canny behavior.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 102,
        "fixture_relpath": "fixtures/P02.png", "fixture_sha256": sha256_file(p02_path),
    })

    # P03: large circle
    img = create_blank(800, 800)
    cv2.circle(img, (400, 400), 320, (0, 0, 0), 2, cv2.LINE_AA)
    p03_path = FIXTURE_DIR / "P03.png"
    cv2.imwrite(str(p03_path), img)
    cases.append({
        "case_id": "P03", "class": "POSITIVE_REAL_CIRCLE", "name": "large_circle",
        "ground_truth": [{"center_px": [400.0, 400.0], "radius_px": 320.0, "stroke_px": 2.0}],
        "rationale": "Large circle radius > 300px requiring large Hough search bound.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 103,
        "fixture_relpath": "fixtures/P03.png", "fixture_sha256": sha256_file(p03_path),
    })

    # P04: small circle
    img = create_blank()
    cv2.circle(img, (200, 200), 12, (0, 0, 0), 1, cv2.LINE_AA)
    p04_path = FIXTURE_DIR / "P04.png"
    cv2.imwrite(str(p04_path), img)
    cases.append({
        "case_id": "P04", "class": "POSITIVE_REAL_CIRCLE", "name": "small_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 12.0, "stroke_px": 1.0}],
        "rationale": "Small pin hole radius 12px testing lower quantization boundary.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.70, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 104,
        "fixture_relpath": "fixtures/P04.png", "fixture_sha256": sha256_file(p04_path),
    })

    # P05: circle intersected by one dimension line
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    # Dimension line passing horizontally across circle
    cv2.line(img, (90, 200), (310, 200), (0, 0, 0), 1, cv2.LINE_AA)
    # Dimension witness lines
    cv2.line(img, (90, 180), (90, 220), (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(img, (310, 180), (310, 220), (0, 0, 0), 1, cv2.LINE_AA)
    # Mask out center for dimension text
    cv2.rectangle(img, (180, 190), (220, 210), (255, 255, 255), -1)
    cv2.putText(img, "50", (188, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
    p05_path = FIXTURE_DIR / "P05.png"
    cv2.imwrite(str(p05_path), img)
    cases.append({
        "case_id": "P05", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_intersected_by_one_dimension_line",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "True circle intersected by dimension line across horizontal diameter.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 105,
        "fixture_relpath": "fixtures/P05.png", "fixture_sha256": sha256_file(p05_path),
    })

    # P06: circle intersected by two dimension lines
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (90, 200), (310, 200), (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(img, (200, 90), (200, 310), (0, 0, 0), 1, cv2.LINE_AA)
    p06_path = FIXTURE_DIR / "P06.png"
    cv2.imwrite(str(p06_path), img)
    cases.append({
        "case_id": "P06", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_intersected_by_two_dimension_lines",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle with 4 intersection points fragmenting contour into 4 quadrants.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 106,
        "fixture_relpath": "fixtures/P06.png", "fixture_sha256": sha256_file(p06_path),
    })

    # P07: circle crossed by extension/witness line
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    # Diagonal witness line crossing chord
    cv2.line(img, (120, 100), (280, 300), (0, 0, 0), 1, cv2.LINE_AA)
    p07_path = FIXTURE_DIR / "P07.png"
    cv2.imwrite(str(p07_path), img)
    cases.append({
        "case_id": "P07", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_crossed_by_witness_line",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Secant witness line creating non-orthogonal Canny junctions.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 107,
        "fixture_relpath": "fixtures/P07.png", "fixture_sha256": sha256_file(p07_path),
    })

    # P08: circle partially obscured by dimension text
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    # White text box placed right over circle perimeter at top (gap approx 35 deg)
    cv2.rectangle(img, (170, 115), (230, 135), (255, 255, 255), -1)
    cv2.putText(img, "R75", (178, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    p08_path = FIXTURE_DIR / "P08.png"
    cv2.imwrite(str(p08_path), img)
    cases.append({
        "case_id": "P08", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_obscured_by_text_box",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle with genuine raster gap of 35 deg created by overlapping annotation text box.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 108,
        "fixture_relpath": "fixtures/P08.png", "fixture_sha256": sha256_file(p08_path),
    })

    # P09: circle with centerlines crossing
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    # Dash-dot centerlines
    for x in range(100, 300, 16):
        cv2.line(img, (x, 200), (x+10, 200), (0, 0, 0), 1, cv2.LINE_AA)
        cv2.circle(img, (x+13, 200), 1, (0, 0, 0), -1)
    for y in range(100, 300, 16):
        cv2.line(img, (200, y), (200, y+10), (0, 0, 0), 1, cv2.LINE_AA)
        cv2.circle(img, (200, y+13), 1, (0, 0, 0), -1)
    p09_path = FIXTURE_DIR / "P09.png"
    cv2.imwrite(str(p09_path), img)
    cases.append({
        "case_id": "P09", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_with_centerlines",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Standard engineering circle with ISO centerline markings.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 109,
        "fixture_relpath": "fixtures/P09.png", "fixture_sha256": sha256_file(p09_path),
    })

    # P10: circle with tangent line
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (50, 275), (350, 275), (0, 0, 0), 2, cv2.LINE_AA)
    p10_path = FIXTURE_DIR / "P10.png"
    cv2.imwrite(str(p10_path), img)
    cases.append({
        "case_id": "P10", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_with_tangent_line",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle tangent to a bottom boundary line.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 110,
        "fixture_relpath": "fixtures/P10.png", "fixture_sha256": sha256_file(p10_path),
    })

    # P11: circle inside dense geometry
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    for k in range(50, 350, 25):
        cv2.line(img, (k, 50), (k, 350), (180, 180, 180), 1, cv2.LINE_AA)
    p11_path = FIXTURE_DIR / "P11.png"
    cv2.imwrite(str(p11_path), img)
    cases.append({
        "case_id": "P11", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_in_dense_geometry",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle superimposed on dense background grid.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.75, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 111,
        "fixture_relpath": "fixtures/P11.png", "fixture_sha256": sha256_file(p11_path),
    })

    # P12: concentric circles
    img = create_blank()
    cv2.circle(img, (200, 200), 40, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (200, 200), 85, (0, 0, 0), 2, cv2.LINE_AA)
    p12_path = FIXTURE_DIR / "P12.png"
    cv2.imwrite(str(p12_path), img)
    cases.append({
        "case_id": "P12", "class": "POSITIVE_REAL_CIRCLE", "name": "concentric_circles",
        "ground_truth": [
            {"center_px": [200.0, 200.0], "radius_px": 40.0, "stroke_px": 2.0},
            {"center_px": [200.0, 200.0], "radius_px": 85.0, "stroke_px": 2.0},
        ],
        "rationale": "Concentric shaft/hole circles with shared center.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 112,
        "fixture_relpath": "fixtures/P12.png", "fixture_sha256": sha256_file(p12_path),
    })

    # P13: annulus / two valid circles
    img = create_blank()
    cv2.circle(img, (200, 200), 60, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (200, 200), 80, (0, 0, 0), 2, cv2.LINE_AA)
    p13_path = FIXTURE_DIR / "P13.png"
    cv2.imwrite(str(p13_path), img)
    cases.append({
        "case_id": "P13", "class": "POSITIVE_REAL_CIRCLE", "name": "close_annulus_circles",
        "ground_truth": [
            {"center_px": [200.0, 200.0], "radius_px": 60.0, "stroke_px": 2.0},
            {"center_px": [200.0, 200.0], "radius_px": 80.0, "stroke_px": 2.0},
        ],
        "rationale": "Narrow wall pipe / sleeve testing radial separation.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 113,
        "fixture_relpath": "fixtures/P13.png", "fixture_sha256": sha256_file(p13_path),
    })

    # P14: circle with hatch inside
    img = create_blank()
    mask = np.zeros((400, 400), dtype=np.uint8)
    cv2.circle(mask, (200, 200), 75, 255, -1)
    hatch = np.full((400, 400, 3), 255, dtype=np.uint8)
    for d in range(-400, 800, 12):
        cv2.line(hatch, (d, 0), (d+400, 400), (0, 0, 0), 1, cv2.LINE_AA)
    img[mask == 255] = hatch[mask == 255]
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    p14_path = FIXTURE_DIR / "P14.png"
    cv2.imwrite(str(p14_path), img)
    cases.append({
        "case_id": "P14", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_with_interior_hatch",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Section view with interior cross-hatching terminating at boundary.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 114,
        "fixture_relpath": "fixtures/P14.png", "fixture_sha256": sha256_file(p14_path),
    })

    # P15: circle with hatch crossing boundary
    img = create_blank()
    for d in range(-400, 800, 14):
        cv2.line(img, (d, 0), (d+400, 400), (120, 120, 120), 1, cv2.LINE_AA)
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 3, cv2.LINE_AA)
    p15_path = FIXTURE_DIR / "P15.png"
    cv2.imwrite(str(p15_path), img)
    cases.append({
        "case_id": "P15", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_with_crossing_hatch",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 3.0}],
        "rationale": "Heavy circle over unbroken hatching lines.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 115,
        "fixture_relpath": "fixtures/P15.png", "fixture_sha256": sha256_file(p15_path),
    })

    # P16: circle at tile seam (centered at 1000, 1000)
    img = create_blank(2000, 2000)
    cv2.circle(img, (1000, 1000), 80, (0, 0, 0), 2, cv2.LINE_AA)
    p16_path = FIXTURE_DIR / "P16.png"
    cv2.imwrite(str(p16_path), img)
    cases.append({
        "case_id": "P16", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_at_tile_seam",
        "ground_truth": [{"center_px": [1000.0, 1000.0], "radius_px": 80.0, "stroke_px": 2.0}],
        "rationale": "Circle exactly on haloed tiling boundary (seam at x=1000, y=1000).",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 116,
        "fixture_relpath": "fixtures/P16.png", "fixture_sha256": sha256_file(p16_path),
    })

    # P17: circle near image border but fully visible
    img = create_blank()
    cv2.circle(img, (60, 60), 45, (0, 0, 0), 2, cv2.LINE_AA)
    p17_path = FIXTURE_DIR / "P17.png"
    cv2.imwrite(str(p17_path), img)
    cases.append({
        "case_id": "P17", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_near_border",
        "ground_truth": [{"center_px": [60.0, 60.0], "radius_px": 45.0, "stroke_px": 2.0}],
        "rationale": "Circle located 15px from image corner, fully in bounds.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 117,
        "fixture_relpath": "fixtures/P17.png", "fixture_sha256": sha256_file(p17_path),
    })

    # P18: low-contrast circle
    img = create_blank(bg=240)
    cv2.circle(img, (200, 200), 75, (200, 200, 200), 2, cv2.LINE_AA)
    p18_path = FIXTURE_DIR / "P18.png"
    cv2.imwrite(str(p18_path), img)
    cases.append({
        "case_id": "P18", "class": "POSITIVE_REAL_CIRCLE", "name": "low_contrast_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Low contrast stroke (intensity diff 40). May remain unresolved if edge detector fails.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": False, "must_reject": False, "may_remain_unresolved": True,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": False,
        "source_support_required": 0.50, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 118,
        "fixture_relpath": "fixtures/P18.png", "fixture_sha256": sha256_file(p18_path),
    })

    # P19: noisy scan circle
    rng = np.random.RandomState(119)
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    noise = rng.normal(0, 15, img.shape).astype(np.int16)
    noisy_img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    p19_path = FIXTURE_DIR / "P19.png"
    cv2.imwrite(str(p19_path), noisy_img)
    cases.append({
        "case_id": "P19", "class": "POSITIVE_REAL_CIRCLE", "name": "noisy_scan_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle with additive Gaussian sensor noise (std=15).",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.70, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 119,
        "fixture_relpath": "fixtures/P19.png", "fixture_sha256": sha256_file(p19_path),
    })

    # P20: blurred circle
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    blurred_img = cv2.GaussianBlur(img, (7, 7), 2.0)
    p20_path = FIXTURE_DIR / "P20.png"
    cv2.imwrite(str(p20_path), blurred_img)
    cases.append({
        "case_id": "P20", "class": "POSITIVE_REAL_CIRCLE", "name": "blurred_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle degraded by optical blur sigma=2.0.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.75, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 120,
        "fixture_relpath": "fixtures/P20.png", "fixture_sha256": sha256_file(p20_path),
    })

    # P21: thick ink / bleed circle
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 6, cv2.LINE_AA)
    bleed_img = cv2.GaussianBlur(img, (5, 5), 1.2)
    p21_path = FIXTURE_DIR / "P21.png"
    cv2.imwrite(str(p21_path), bleed_img)
    cases.append({
        "case_id": "P21", "class": "POSITIVE_REAL_CIRCLE", "name": "thick_bleed_circle",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 6.0}],
        "rationale": "Heavy ink bleed circle stroke thickness 6px.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 121,
        "fixture_relpath": "fixtures/P21.png", "fixture_sha256": sha256_file(p21_path),
    })

    # P22: antialiased vector-render circle (CASE05 Payloadchamber Ø50 crop)
    # Crop around the real payloadchamber circle from source-page-1.png
    real_src = Path(r"D:\Cad agent temp\drawing-craft-491-case05-payloadchamber-source-v1-20261015\source-page-1.png")
    if real_src.is_file():
        full_img = cv2.imread(str(real_src))
        # Crop 372.48, 190.84, radius 106.32
        x0, y0 = int(372.48 - 140), int(190.84 - 140)
        x1, y1 = int(372.48 + 140), int(190.84 + 140)
        crop = full_img[y0:y1, x0:x1].copy()
        p22_path = FIXTURE_DIR / "P22.png"
        cv2.imwrite(str(p22_path), crop)
        p22_cx = 372.48 - x0
        p22_cy = 190.84 - y0
    else:
        # Fallback synthetic if external temp path unreadable
        crop = create_blank()
        cv2.circle(crop, (200, 200), 106, (0, 0, 0), 2, cv2.LINE_AA)
        p22_path = FIXTURE_DIR / "P22.png"
        cv2.imwrite(str(p22_path), crop)
        p22_cx, p22_cy = 200.0, 200.0
    cases.append({
        "case_id": "P22", "class": "POSITIVE_REAL_CIRCLE", "name": "payloadchamber_phi50_real_render",
        "ground_truth": [{"center_px": [float(p22_cx), float(p22_cy)], "radius_px": 106.32, "stroke_px": 2.115}],
        "rationale": "Authentic vector PDF rasterization of Ø50 circle from roguextech payloadchamber.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.80, "oracle": "CASE05_PAYLOADCHAMBER_PDF_VECTOR_PATH_17", "random_seed": 122,
        "fixture_relpath": "fixtures/P22.png", "fixture_sha256": sha256_file(p22_path),
    })

    # P23: multiple circle sizes on same sheet
    img = create_blank(600, 600)
    cv2.circle(img, (150, 150), 25, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (400, 150), 60, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (250, 400), 110, (0, 0, 0), 2, cv2.LINE_AA)
    p23_path = FIXTURE_DIR / "P23.png"
    cv2.imwrite(str(p23_path), img)
    cases.append({
        "case_id": "P23", "class": "POSITIVE_REAL_CIRCLE", "name": "multi_scale_circles",
        "ground_truth": [
            {"center_px": [150.0, 150.0], "radius_px": 25.0, "stroke_px": 2.0},
            {"center_px": [400.0, 150.0], "radius_px": 60.0, "stroke_px": 2.0},
            {"center_px": [250.0, 400.0], "radius_px": 110.0, "stroke_px": 2.0},
        ],
        "rationale": "Multiple circles with distinct radii (25, 60, 110) on single view.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 123,
        "fixture_relpath": "fixtures/P23.png", "fixture_sha256": sha256_file(p23_path),
    })

    # P24: circle with arrow/leader nearby
    img = create_blank()
    cv2.circle(img, (200, 200), 75, (0, 0, 0), 2, cv2.LINE_AA)
    # Leader line pointing to top right circumference at angle 45 deg (253, 147)
    cv2.line(img, (320, 80), (253, 147), (0, 0, 0), 1, cv2.LINE_AA)
    # Arrowhead at (253, 147)
    pts = np.array([[253, 147], [262, 140], [258, 152]], np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 0))
    p24_path = FIXTURE_DIR / "P24.png"
    cv2.imwrite(str(p24_path), img)
    cases.append({
        "case_id": "P24", "class": "POSITIVE_REAL_CIRCLE", "name": "circle_with_leader_arrow",
        "ground_truth": [{"center_px": [200.0, 200.0], "radius_px": 75.0, "stroke_px": 2.0}],
        "rationale": "Circle with radial leader line and terminating arrowhead.",
        "expected_raw_geometry": "CIRCLE", "expected_promotion_role": "ENGINEERING_CIRCLE",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_CANONICAL", "random_seed": 124,
        "fixture_relpath": "fixtures/P24.png", "fixture_sha256": sha256_file(p24_path),
    })

    # -------------------------------------------------------------
    # PARTIAL-CURVE NEGATIVE FAMILY (N01 - N20)
    # -------------------------------------------------------------
    arc_angles = [
        ("N01", 30, "30_degree_arc"),
        ("N02", 60, "60_degree_arc"),
        ("N03", 90, "90_degree_arc"),
        ("N04", 120, "120_degree_arc"),
        ("N05", 180, "180_degree_semicircle"),
        ("N06", 240, "240_degree_arc"),
        ("N07", 270, "270_degree_arc"),
        ("N08", 300, "300_degree_arc"),
        ("N09", 330, "330_degree_arc_open_gap"),
    ]
    for cid, deg, name in arc_angles:
        img = create_blank()
        cv2.ellipse(img, (200, 200), (75, 75), 0, 0, deg, (0, 0, 0), 2, cv2.LINE_AA)
        n_path = FIXTURE_DIR / f"{cid}.png"
        cv2.imwrite(str(n_path), img)
        cases.append({
            "case_id": cid, "class": "PARTIAL_CURVE_NEGATIVE", "name": name,
            "ground_truth": None,  # NOT a circle! It is an ARC.
            "rationale": f"Partial open arc of {deg} deg. MUST NOT be promoted as a complete circle.",
            "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
            "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
            "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
            "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 200 + deg,
            "fixture_relpath": f"fixtures/{cid}.png", "fixture_sha256": sha256_file(n_path),
        })

    # N10: multiple unrelated arcs on same radius
    img = create_blank()
    cv2.ellipse(img, (200, 200), (75, 75), 0, 10, 50, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (200, 200), (75, 75), 0, 120, 160, (0, 0, 0), 2, cv2.LINE_AA)
    n10_path = FIXTURE_DIR / "N10.png"
    cv2.imwrite(str(n10_path), img)
    cases.append({
        "case_id": "N10", "class": "PARTIAL_CURVE_NEGATIVE", "name": "unrelated_co_radial_arcs",
        "ground_truth": None,
        "rationale": "Two isolated small arcs on same circle radius, total span 80 deg. Must be rejected.",
        "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 210,
        "fixture_relpath": "fixtures/N10.png", "fixture_sha256": sha256_file(n10_path),
    })

    # N11: three arc fragments approximately co-circular
    img = create_blank()
    cv2.ellipse(img, (200, 200), (75, 75), 0, 0, 45, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (200, 200), (75, 75), 0, 120, 165, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (200, 200), (75, 75), 0, 240, 285, (0, 0, 0), 2, cv2.LINE_AA)
    n11_path = FIXTURE_DIR / "N11.png"
    cv2.imwrite(str(n11_path), img)
    cases.append({
        "case_id": "N11", "class": "PARTIAL_CURVE_NEGATIVE", "name": "three_disconnected_arc_fragments",
        "ground_truth": None,
        "rationale": "Three 45-deg arcs separated by 75-deg gaps. Total coverage only 37.5%. Must reject.",
        "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 211,
        "fixture_relpath": "fixtures/N11.png", "fixture_sha256": sha256_file(n11_path),
    })

    # N12: fillet
    img = create_blank()
    cv2.line(img, (100, 200), (180, 200), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (180, 220), (20, 20), 0, 270, 360, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (200, 220), (200, 300), (0, 0, 0), 2, cv2.LINE_AA)
    n12_path = FIXTURE_DIR / "N12.png"
    cv2.imwrite(str(n12_path), img)
    cases.append({
        "case_id": "N12", "class": "PARTIAL_CURVE_NEGATIVE", "name": "corner_fillet",
        "ground_truth": None,
        "rationale": "Quarter-circle fillet r=20 joining two orthogonal lines.",
        "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 212,
        "fixture_relpath": "fixtures/N12.png", "fixture_sha256": sha256_file(n12_path),
    })

    # N13: rounded corner
    img = create_blank()
    cv2.ellipse(img, (200, 200), (50, 50), 0, 180, 270, (0, 0, 0), 2, cv2.LINE_AA)
    n13_path = FIXTURE_DIR / "N13.png"
    cv2.imwrite(str(n13_path), img)
    cases.append({
        "case_id": "N13", "class": "PARTIAL_CURVE_NEGATIVE", "name": "isolated_rounded_corner",
        "ground_truth": None,
        "rationale": "90-degree corner arc.",
        "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 213,
        "fixture_relpath": "fixtures/N13.png", "fixture_sha256": sha256_file(n13_path),
    })

    # N14: slot semicircle ends
    img = create_blank()
    cv2.ellipse(img, (150, 200), (30, 30), 0, 90, 270, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (150, 170), (250, 170), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (250, 200), (30, 30), 0, 270, 450, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (150, 230), (250, 230), (0, 0, 0), 2, cv2.LINE_AA)
    n14_path = FIXTURE_DIR / "N14.png"
    cv2.imwrite(str(n14_path), img)
    cases.append({
        "case_id": "N14", "class": "PARTIAL_CURVE_NEGATIVE", "name": "machined_slot_profile",
        "ground_truth": None,
        "rationale": "Slot consisting of two semicircles and straight sides. Semicircles are arcs, not circles.",
        "expected_raw_geometry": "ARC_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ARC", "random_seed": 214,
        "fixture_relpath": "fixtures/N14.png", "fixture_sha256": sha256_file(n14_path),
    })

    # N15: rounded rectangle (stadium / rounded box)
    img = create_blank()
    cv2.ellipse(img, (150, 150), (30, 30), 0, 180, 270, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (150, 120), (250, 120), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (250, 150), (30, 30), 0, 270, 360, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (280, 150), (280, 250), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (250, 250), (30, 30), 0, 0, 90, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (150, 280), (250, 280), (0, 0, 0), 2, cv2.LINE_AA)
    cv2.ellipse(img, (150, 250), (30, 30), 0, 90, 180, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(img, (120, 150), (120, 250), (0, 0, 0), 2, cv2.LINE_AA)
    n15_path = FIXTURE_DIR / "N15.png"
    cv2.imwrite(str(n15_path), img)
    cases.append({
        "case_id": "N15", "class": "PARTIAL_CURVE_NEGATIVE", "name": "rounded_rectangle",
        "ground_truth": None,
        "rationale": "Rounded rectangle. Candidate circle fitted to corner or bounding circle must be rejected.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_NON_CIRCLE", "random_seed": 215,
        "fixture_relpath": "fixtures/N15.png", "fixture_sha256": sha256_file(n15_path),
    })

    # N16: spline approximating circular arc
    img = create_blank()
    pts = []
    for deg in range(0, 180, 5):
        rad = math.radians(deg)
        r = 75.0 + 3.0 * math.sin(4 * rad)  # wavy spline
        pts.append([int(200 + r * math.cos(rad)), int(200 + r * math.sin(rad))])
    cv2.polylines(img, [np.array(pts, np.int32)], False, (0, 0, 0), 2, cv2.LINE_AA)
    n16_path = FIXTURE_DIR / "N16.png"
    cv2.imwrite(str(n16_path), img)
    cases.append({
        "case_id": "N16", "class": "PARTIAL_CURVE_NEGATIVE", "name": "wavy_spline_curve",
        "ground_truth": None,
        "rationale": "Non-circular spline with varying curvature. Must not fit circle.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_NON_CIRCLE", "random_seed": 216,
        "fixture_relpath": "fixtures/N16.png", "fixture_sha256": sha256_file(n16_path),
    })

    # N17: ellipse low eccentricity (a=75, b=74, ratio 1.0135)
    img = create_blank()
    cv2.ellipse(img, (200, 200), (75, 74), 0, 0, 360, (0, 0, 0), 2, cv2.LINE_AA)
    n17_path = FIXTURE_DIR / "N17.png"
    cv2.imwrite(str(n17_path), img)
    cases.append({
        "case_id": "N17", "class": "PARTIAL_CURVE_NEGATIVE", "name": "ellipse_low_eccentricity_1_01",
        "ground_truth": None,
        "rationale": "Near-circular ellipse ratio=1.0135. At 1px resolution, close to quantization limit.",
        "expected_raw_geometry": "ELLIPSE_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": False, "may_remain_unresolved": True,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ELLIPSE", "random_seed": 217,
        "fixture_relpath": "fixtures/N17.png", "fixture_sha256": sha256_file(n17_path),
    })

    # N18: ellipse moderate eccentricity (a=75, b=65, ratio 1.15)
    img = create_blank()
    cv2.ellipse(img, (200, 200), (75, 65), 0, 0, 360, (0, 0, 0), 2, cv2.LINE_AA)
    n18_path = FIXTURE_DIR / "N18.png"
    cv2.imwrite(str(n18_path), img)
    cases.append({
        "case_id": "N18", "class": "PARTIAL_CURVE_NEGATIVE", "name": "ellipse_eccentricity_1_15",
        "ground_truth": None,
        "rationale": "Distinctly non-circular ellipse (axis ratio 1.15). Residual must clearly reject circle.",
        "expected_raw_geometry": "ELLIPSE_OR_NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ELLIPSE", "random_seed": 218,
        "fixture_relpath": "fixtures/N18.png", "fixture_sha256": sha256_file(n18_path),
    })

    # N19: perspective-like oval
    img = create_blank()
    cv2.ellipse(img, (200, 200), (80, 50), 30, 0, 360, (0, 0, 0), 2, cv2.LINE_AA)
    n19_path = FIXTURE_DIR / "N19.png"
    cv2.imwrite(str(n19_path), img)
    cases.append({
        "case_id": "N19", "class": "PARTIAL_CURVE_NEGATIVE", "name": "rotated_oval",
        "ground_truth": None,
        "rationale": "Rotated ellipse from isometric perspective projection.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_ELLIPSE", "random_seed": 219,
        "fixture_relpath": "fixtures/N19.png", "fixture_sha256": sha256_file(n19_path),
    })

    # N20: irregular closed loop
    img = create_blank()
    pts = []
    for deg in range(0, 360, 10):
        rad = math.radians(deg)
        r = 75.0 + 10.0 * math.sin(3 * rad) + 5.0 * math.cos(5 * rad)
        pts.append([int(200 + r * math.cos(rad)), int(200 + r * math.sin(rad))])
    cv2.polylines(img, [np.array(pts, np.int32)], True, (0, 0, 0), 2, cv2.LINE_AA)
    n20_path = FIXTURE_DIR / "N20.png"
    cv2.imwrite(str(n20_path), img)
    cases.append({
        "case_id": "N20", "class": "PARTIAL_CURVE_NEGATIVE", "name": "irregular_closed_loop",
        "ground_truth": None,
        "rationale": "Irregular cam / freeform loop. Must reject as circle.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "SUPPRESSED_NOT_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GROUND_TRUTH_NON_CIRCLE", "random_seed": 220,
        "fixture_relpath": "fixtures/N20.png", "fixture_sha256": sha256_file(n20_path),
    })

    # -------------------------------------------------------------
    # TEXT / ANNOTATION NEGATIVE FAMILY (T01 - T12)
    # -------------------------------------------------------------
    text_glyphs = [
        ("T01", "O", "glyph_O", 1.8),
        ("T02", "0", "glyph_0", 1.8),
        ("T03", "C", "glyph_C", 1.8),
        ("T04", "G", "glyph_G", 1.8),
        ("T05", "o", "glyph_degree_symbol", 0.6),
    ]
    for cid, ch, name, scale in text_glyphs:
        img = create_blank()
        cv2.putText(img, ch, (175, 230), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA)
        t_path = FIXTURE_DIR / f"{cid}.png"
        cv2.imwrite(str(t_path), img)
        cases.append({
            "case_id": cid, "class": "TEXT_ANNOTATION_NEGATIVE", "name": name,
            "ground_truth": None,
            "rationale": f"Text character '{ch}'. Even if round, role is TEXT, not engineering circle.",
            "expected_raw_geometry": "TEXT_GLYPH", "expected_promotion_role": "TEXT_GLYPH_SUPPRESSED",
            "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
            "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
            "source_support_required": 0.0, "oracle": "SYNTHETIC_TEXT_OCR", "random_seed": 300 + ord(ch[0]),
            "fixture_relpath": f"fixtures/{cid}.png", "fixture_sha256": sha256_file(t_path),
        })

    # T06: diameter symbol environment (Ø50)
    img = create_blank()
    cv2.putText(img, "%%C50", (160, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2, cv2.LINE_AA)
    t06_path = FIXTURE_DIR / "T06.png"
    cv2.imwrite(str(t06_path), img)
    cases.append({
        "case_id": "T06", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "diameter_symbol_text",
        "ground_truth": None,
        "rationale": "Diameter symbol prefix in text dimension callout.",
        "expected_raw_geometry": "TEXT_GLYPH", "expected_promotion_role": "TEXT_GLYPH_SUPPRESSED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_TEXT_OCR", "random_seed": 306,
        "fixture_relpath": "fixtures/T06.png", "fixture_sha256": sha256_file(t06_path),
    })

    # T07: leader bubble
    img = create_blank()
    cv2.circle(img, (200, 200), 24, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "1", (194, 208), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(img, (183, 217), (140, 260), (0, 0, 0), 1, cv2.LINE_AA)
    t07_path = FIXTURE_DIR / "T07.png"
    cv2.imwrite(str(t07_path), img)
    cases.append({
        "case_id": "T07", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "item_leader_bubble",
        "ground_truth": None,
        "rationale": "Annotation callout bubble (part item number). Should not be promoted as part circle.",
        "expected_raw_geometry": "ANNOTATION_BUBBLE", "expected_promotion_role": "ANNOTATION_ROLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_ANNOTATION_ROLE", "random_seed": 307,
        "fixture_relpath": "fixtures/T07.png", "fixture_sha256": sha256_file(t07_path),
    })

    # T08: detail bubble (dashed)
    img = create_blank()
    for deg in range(0, 360, 20):
        cv2.ellipse(img, (200, 200), (45, 45), 0, deg, deg+10, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "A", (190, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 1, cv2.LINE_AA)
    t08_path = FIXTURE_DIR / "T08.png"
    cv2.imwrite(str(t08_path), img)
    cases.append({
        "case_id": "T08", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "detail_view_bubble",
        "ground_truth": None,
        "rationale": "Dashed detail view indicator ring.",
        "expected_raw_geometry": "ANNOTATION_BUBBLE", "expected_promotion_role": "ANNOTATION_ROLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_ANNOTATION_ROLE", "random_seed": 308,
        "fixture_relpath": "fixtures/T08.png", "fixture_sha256": sha256_file(t08_path),
    })

    # T09: revision bubble
    img = create_blank()
    cv2.circle(img, (200, 200), 18, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "B", (194, 206), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    t09_path = FIXTURE_DIR / "T09.png"
    cv2.imwrite(str(t09_path), img)
    cases.append({
        "case_id": "T09", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "revision_callout_circle",
        "ground_truth": None,
        "rationale": "Revision letter circle in drawing title or revision table.",
        "expected_raw_geometry": "ANNOTATION_BUBBLE", "expected_promotion_role": "ANNOTATION_ROLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_ANNOTATION_ROLE", "random_seed": 309,
        "fixture_relpath": "fixtures/T09.png", "fixture_sha256": sha256_file(t09_path),
    })

    # T10: circled annotation number
    img = create_blank()
    cv2.circle(img, (200, 200), 20, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(img, "4", (193, 208), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    t10_path = FIXTURE_DIR / "T10.png"
    cv2.imwrite(str(t10_path), img)
    cases.append({
        "case_id": "T10", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "circled_datum_number",
        "ground_truth": None,
        "rationale": "Circled note or datum number.",
        "expected_raw_geometry": "ANNOTATION_BUBBLE", "expected_promotion_role": "ANNOTATION_ROLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_ANNOTATION_ROLE", "random_seed": 310,
        "fixture_relpath": "fixtures/T10.png", "fixture_sha256": sha256_file(t10_path),
    })

    # T11: OCR candidate around O/0
    img = create_blank()
    cv2.putText(img, "NO: 100", (130, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    t11_path = FIXTURE_DIR / "T11.png"
    cv2.imwrite(str(t11_path), img)
    cases.append({
        "case_id": "T11", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "text_word_containing_zeros",
        "ground_truth": None,
        "rationale": "Word 'NO: 100' containing three round characters. Must withhold circle promotion.",
        "expected_raw_geometry": "TEXT_GLYPH", "expected_promotion_role": "TEXT_GLYPH_SUPPRESSED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_TEXT_OCR", "random_seed": 311,
        "fixture_relpath": "fixtures/T11.png", "fixture_sha256": sha256_file(t11_path),
    })

    # T12: dense alphanumeric region containing round glyphs
    img = create_blank(500, 300)
    lines = ["MOTOR MOUNT TOP ASSEMBLY", "DWG NO: MM-2026-001 REV 0", "MATERIAL: AL 6061-T6"]
    for idx, l in enumerate(lines):
        cv2.putText(img, l, (20, 80 + idx * 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    t12_path = FIXTURE_DIR / "T12.png"
    cv2.imwrite(str(t12_path), img)
    cases.append({
        "case_id": "T12", "class": "TEXT_ANNOTATION_NEGATIVE", "name": "title_block_text_block",
        "ground_truth": None,
        "rationale": "Dense title block with 'O' and '0' glyphs. Historical source of false circles in PR #518.",
        "expected_raw_geometry": "TEXT_GLYPH", "expected_promotion_role": "TEXT_GLYPH_SUPPRESSED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_TEXT_OCR", "random_seed": 312,
        "fixture_relpath": "fixtures/T12.png", "fixture_sha256": sha256_file(t12_path),
    })

    # -------------------------------------------------------------
    # STRUCTURAL FALSE-POSITIVE FAMILY (F01 - F13)
    # -------------------------------------------------------------
    # F01: hatch intersections forming approximate ring
    img = create_blank()
    for k in range(0, 400, 20):
        cv2.line(img, (k, 0), (k, 400), (160, 160, 160), 1)
        cv2.line(img, (0, k), (400, k), (160, 160, 160), 1)
    # Mask out outer corners
    f01_path = FIXTURE_DIR / "F01.png"
    cv2.imwrite(str(f01_path), img)
    cases.append({
        "case_id": "F01", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "grid_hatch_intersections",
        "ground_truth": None,
        "rationale": "Orthogonal grid intersections which can create false Hough accumulator peaks.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 401,
        "fixture_relpath": "fixtures/F01.png", "fixture_sha256": sha256_file(f01_path),
    })

    # F02: radial spokes without outer circle
    img = create_blank()
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        cv2.line(img, (200, 200), (int(200 + 75*math.cos(rad)), int(200 + 75*math.sin(rad))), (0, 0, 0), 1, cv2.LINE_AA)
    f02_path = FIXTURE_DIR / "F02.png"
    cv2.imwrite(str(f02_path), img)
    cases.append({
        "case_id": "F02", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "radial_spokes_star",
        "ground_truth": None,
        "rationale": "Radial lines meeting at hub. Tangential support is ZERO despite radial gradients.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 402,
        "fixture_relpath": "fixtures/F02.png", "fixture_sha256": sha256_file(f02_path),
    })

    # F03: polygon with many sides (dodecagon, 12-gon)
    img = create_blank()
    pts = []
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        pts.append([int(200 + 75*math.cos(rad)), int(200 + 75*math.sin(rad))])
    cv2.polylines(img, [np.array(pts, np.int32)], True, (0, 0, 0), 2, cv2.LINE_AA)
    f03_path = FIXTURE_DIR / "F03.png"
    cv2.imwrite(str(f03_path), img)
    cases.append({
        "case_id": "F03", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "regular_dodecagon",
        "ground_truth": None,
        "rationale": "12-sided polygon. Straight facets deviate from circle normal and curvature.",
        "expected_raw_geometry": "LINES_OR_NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 403,
        "fixture_relpath": "fixtures/F03.png", "fixture_sha256": sha256_file(f03_path),
    })

    # F04: bolt pattern with no physical outer circle
    img = create_blank()
    for deg in range(0, 360, 60):
        rad = math.radians(deg)
        bx = int(200 + 75 * math.cos(rad))
        by = int(200 + 75 * math.sin(rad))
        cv2.circle(img, (bx, by), 6, (0, 0, 0), 1, cv2.LINE_AA)
    f04_path = FIXTURE_DIR / "F04.png"
    cv2.imwrite(str(f04_path), img)
    cases.append({
        "case_id": "F04", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "bolt_hole_circle_pattern",
        "ground_truth": [
            # 6 individual holes, but NO physical outer circle of r=75!
            {"center_px": [float(int(200 + 75*math.cos(math.radians(d)))), float(int(200 + 75*math.sin(math.radians(d))))], "radius_px": 6.0}
            for d in range(0, 360, 60)
        ],
        "rationale": "6 bolt holes on pitch circle. The pitch circle (r=75) does NOT exist as physical ink.",
        "expected_raw_geometry": "SMALL_CIRCLES", "expected_promotion_role": "NO_PHANTOM_PITCH_CIRCLE",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 404,
        "fixture_relpath": "fixtures/F04.png", "fixture_sha256": sha256_file(f04_path),
    })

    # F05: noise points approximately circular
    rng = np.random.RandomState(405)
    img = create_blank()
    for _ in range(40):
        deg = rng.uniform(0, 360)
        r = rng.normal(75, 4)
        rad = math.radians(deg)
        x = int(200 + r * math.cos(rad))
        y = int(200 + r * math.sin(rad))
        cv2.circle(img, (x, y), 1, (0, 0, 0), -1)
    f05_path = FIXTURE_DIR / "F05.png"
    cv2.imwrite(str(f05_path), img)
    cases.append({
        "case_id": "F05", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "circular_noise_speckles",
        "ground_truth": None,
        "rationale": "Random dust/speckles clustering roughly around a ring.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 405,
        "fixture_relpath": "fixtures/F05.png", "fixture_sha256": sha256_file(f05_path),
    })

    # F06: rectangular feature with rounded corners
    img = create_blank()
    cv2.rectangle(img, (140, 140), (260, 260), (0, 0, 0), 2)
    f06_path = FIXTURE_DIR / "F06.png"
    cv2.imwrite(str(f06_path), img)
    cases.append({
        "case_id": "F06", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "square_box",
        "ground_truth": None,
        "rationale": "Sharp square box. Hough may vote for inscribed/circumscribed circle.",
        "expected_raw_geometry": "LINES", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 406,
        "fixture_relpath": "fixtures/F06.png", "fixture_sha256": sha256_file(f06_path),
    })

    # F07: two tangent arcs from different features
    img = create_blank()
    cv2.circle(img, (160, 200), 40, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (240, 200), 40, (0, 0, 0), 2, cv2.LINE_AA)
    f07_path = FIXTURE_DIR / "F07.png"
    cv2.imwrite(str(f07_path), img)
    cases.append({
        "case_id": "F07", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "tangent_touching_circles",
        "ground_truth": [
            {"center_px": [160.0, 200.0], "radius_px": 40.0},
            {"center_px": [240.0, 200.0], "radius_px": 40.0},
        ],
        "rationale": "Two touching circles of r=40. Must NOT admit a phantom enclosing circle r=80.",
        "expected_raw_geometry": "TWO_CIRCLES", "expected_promotion_role": "ADMIT_INDIVIDUAL_ONLY",
        "must_admit": True, "must_reject": False, "may_remain_unresolved": False,
        "hard_failure_if_admitted": False, "hard_failure_if_rejected": True,
        "source_support_required": 0.85, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 407,
        "fixture_relpath": "fixtures/F07.png", "fixture_sha256": sha256_file(f07_path),
    })

    # F08: circle-like shadow / scan artifact
    img = create_blank()
    for r in range(40, 80, 2):
        cv2.circle(img, (200, 200), r, (230, 230, 230), 1)
    f08_path = FIXTURE_DIR / "F08.png"
    cv2.imwrite(str(f08_path), img)
    cases.append({
        "case_id": "F08", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "faint_coffee_stain_shadow",
        "ground_truth": None,
        "rationale": "Faint ring shadow from liquid drop or scanner ring artifact. Must reject.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 408,
        "fixture_relpath": "fixtures/F08.png", "fixture_sha256": sha256_file(f08_path),
    })

    # F09: page border corner artifacts
    img = create_blank()
    cv2.line(img, (20, 20), (100, 20), (0, 0, 0), 2)
    cv2.line(img, (20, 20), (20, 100), (0, 0, 0), 2)
    f09_path = FIXTURE_DIR / "F09.png"
    cv2.imwrite(str(f09_path), img)
    cases.append({
        "case_id": "F09", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "drawing_sheet_border_corner",
        "ground_truth": None,
        "rationale": "Right-angle border alignment tick.",
        "expected_raw_geometry": "LINES", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 409,
        "fixture_relpath": "fixtures/F09.png", "fixture_sha256": sha256_file(f09_path),
    })

    # F10: contour of arrowheads around center
    img = create_blank()
    for deg in range(0, 360, 45):
        rad = math.radians(deg)
        x = int(200 + 75 * math.cos(rad))
        y = int(200 + 75 * math.sin(rad))
        cv2.drawMarker(img, (x, y), (0, 0, 0), cv2.MARKER_TRIANGLE_UP, 10, 1)
    f10_path = FIXTURE_DIR / "F10.png"
    cv2.imwrite(str(f10_path), img)
    cases.append({
        "case_id": "F10", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "ring_of_triangles",
        "ground_truth": None,
        "rationale": "Discrete triangle symbols arranged on circle. No continuous contour or normal alignment.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 410,
        "fixture_relpath": "fixtures/F10.png", "fixture_sha256": sha256_file(f10_path),
    })

    # F11: repeated text glyphs producing circular Hough vote
    img = create_blank()
    for deg in range(0, 360, 40):
        rad = math.radians(deg)
        x = int(190 + 75 * math.cos(rad))
        y = int(205 + 75 * math.sin(rad))
        cv2.putText(img, "x", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    f11_path = FIXTURE_DIR / "F11.png"
    cv2.imwrite(str(f11_path), img)
    cases.append({
        "case_id": "F11", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "repeated_text_crosses_ring",
        "ground_truth": None,
        "rationale": "Letters 'x' arranged on a ring.",
        "expected_raw_geometry": "TEXT", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 411,
        "fixture_relpath": "fixtures/F11.png", "fixture_sha256": sha256_file(f11_path),
    })

    # F12: concentric noise artifact
    img = create_blank()
    for r in range(20, 100, 10):
        cv2.circle(img, (200, 200), r, (210, 210, 210), 1)
    f12_path = FIXTURE_DIR / "F12.png"
    cv2.imwrite(str(f12_path), img)
    cases.append({
        "case_id": "F12", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "concentric_moire_noise",
        "ground_truth": None,
        "rationale": "Moire / low contrast concentric rings from raster aliasing.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_NOISE_ORACLE", "random_seed": 412,
        "fixture_relpath": "fixtures/F12.png", "fixture_sha256": sha256_file(f12_path),
    })

    # F13: dimension arrow graphics creating circular fragment pattern
    img = create_blank()
    cv2.line(img, (100, 100), (300, 100), (0, 0, 0), 1)
    cv2.line(img, (100, 100), (100, 300), (0, 0, 0), 1)
    cv2.drawMarker(img, (100, 100), (0, 0, 0), cv2.MARKER_TILTED_CROSS, 8, 1)
    f13_path = FIXTURE_DIR / "F13.png"
    cv2.imwrite(str(f13_path), img)
    cases.append({
        "case_id": "F13", "class": "STRUCTURAL_FALSE_POSITIVE", "name": "dimension_corner_arrow_ticks",
        "ground_truth": None,
        "rationale": "Dimension line termination crosses.",
        "expected_raw_geometry": "LINES", "expected_promotion_role": "NOISE_REJECTED",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "SYNTHETIC_GEOMETRIC_ORACLE", "random_seed": 413,
        "fixture_relpath": "fixtures/F13.png", "fixture_sha256": sha256_file(f13_path),
    })

    # -------------------------------------------------------------
    # DEGENERATE FAMILY (D01 - D12)
    # -------------------------------------------------------------
    # D01: empty image
    img = create_blank()
    d01_path = FIXTURE_DIR / "D01.png"
    cv2.imwrite(str(d01_path), img)
    cases.append({
        "case_id": "D01", "class": "DEGENERATE", "name": "empty_white_canvas",
        "ground_truth": None, "rationale": "Completely blank canvas.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_NO_GEOMETRY",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "EMPTY", "random_seed": 501,
        "fixture_relpath": "fixtures/D01.png", "fixture_sha256": sha256_file(d01_path),
    })

    # D02: all-white 500x500
    img = create_blank(500, 500, 255)
    d02_path = FIXTURE_DIR / "D02.png"
    cv2.imwrite(str(d02_path), img)
    cases.append({
        "case_id": "D02", "class": "DEGENERATE", "name": "large_all_white",
        "ground_truth": None, "rationale": "500x500 all-white canvas.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_NO_GEOMETRY",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "EMPTY", "random_seed": 502,
        "fixture_relpath": "fixtures/D02.png", "fixture_sha256": sha256_file(d02_path),
    })

    # D03: all-black 500x500
    img = create_blank(500, 500, 0)
    d03_path = FIXTURE_DIR / "D03.png"
    cv2.imwrite(str(d03_path), img)
    cases.append({
        "case_id": "D03", "class": "DEGENERATE", "name": "all_black_canvas",
        "ground_truth": None, "rationale": "Solid black canvas.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_NO_GEOMETRY",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "EMPTY", "random_seed": 503,
        "fixture_relpath": "fixtures/D03.png", "fixture_sha256": sha256_file(d03_path),
    })

    # D04: 1x1 image
    img = create_blank(1, 1, 255)
    d04_path = FIXTURE_DIR / "D04.png"
    cv2.imwrite(str(d04_path), img)
    cases.append({
        "case_id": "D04", "class": "DEGENERATE", "name": "single_pixel_canvas",
        "ground_truth": None, "rationale": "1x1 dimension edge case.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_NO_GEOMETRY",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "EMPTY", "random_seed": 504,
        "fixture_relpath": "fixtures/D04.png", "fixture_sha256": sha256_file(d04_path),
    })

    # D05: tiny image (4x4)
    img = create_blank(4, 4, 255)
    d05_path = FIXTURE_DIR / "D05.png"
    cv2.imwrite(str(d05_path), img)
    cases.append({
        "case_id": "D05", "class": "DEGENERATE", "name": "tiny_4x4_canvas",
        "ground_truth": None, "rationale": "4x4 canvas smaller than any possible circle.",
        "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_NO_GEOMETRY",
        "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
        "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
        "source_support_required": 0.0, "oracle": "EMPTY", "random_seed": 505,
        "fixture_relpath": "fixtures/D05.png", "fixture_sha256": sha256_file(d05_path),
    })

    # D06 - D12: Candidate proposal structural degeneracies
    deg_specs = [
        ("D06", "invalid_zero_radius", "Candidate proposal radius <= 0 px"),
        ("D07", "nonfinite_center_nan", "Candidate center (NaN, NaN)"),
        ("D08", "nonfinite_radius_inf", "Candidate radius Inf"),
        ("D09", "huge_coordinate_overflow", "Candidate center at (1e7, 1e7)"),
        ("D10", "crop_edge_truncated", "Candidate centered at (10, 10) with r=80 cut off by frame"),
        ("D11", "exact_duplicate_proposal", "Duplicate Hough proposal at same center/radius"),
        ("D12", "tile_halo_seam_duplicate", "Near duplicate proposal across tile seam (dx=1px)"),
    ]
    for cid, name, rat in deg_specs:
        img = create_blank()
        d_path = FIXTURE_DIR / f"{cid}.png"
        cv2.imwrite(str(d_path), img)
        cases.append({
            "case_id": cid, "class": "DEGENERATE", "name": name,
            "ground_truth": None, "rationale": rat,
            "expected_raw_geometry": "NONE", "expected_promotion_role": "REJECT_DEGENERATE",
            "must_admit": False, "must_reject": True, "may_remain_unresolved": False,
            "hard_failure_if_admitted": True, "hard_failure_if_rejected": False,
            "source_support_required": 0.0, "oracle": "DEGENERATE_SPEC", "random_seed": 500 + int(cid[1:]),
            "fixture_relpath": f"fixtures/{cid}.png", "fixture_sha256": sha256_file(d_path),
        })

    return cases


def main():
    cases = generate_all_cases()
    out_file = Path(__file__).parent / "BLIND_CIRCLE_MATRIX.json"
    matrix_data = {
        "campaign_id": "ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015",
        "frozen_timestamp": "2026-10-15T23:05:00Z",
        "total_cases": len(cases),
        "classes": {
            "POSITIVE_REAL_CIRCLE": len([c for c in cases if c["class"] == "POSITIVE_REAL_CIRCLE"]),
            "PARTIAL_CURVE_NEGATIVE": len([c for c in cases if c["class"] == "PARTIAL_CURVE_NEGATIVE"]),
            "TEXT_ANNOTATION_NEGATIVE": len([c for c in cases if c["class"] == "TEXT_ANNOTATION_NEGATIVE"]),
            "STRUCTURAL_FALSE_POSITIVE": len([c for c in cases if c["class"] == "STRUCTURAL_FALSE_POSITIVE"]),
            "DEGENERATE": len([c for c in cases if c["class"] == "DEGENERATE"]),
        },
        "cases": cases,
    }
    content = json.dumps(matrix_data, indent=2)
    out_file.write_text(content, encoding="utf-8")
    matrix_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    hash_file = Path(__file__).parent / "BLIND_MATRIX_SHA256.txt"
    hash_file.write_text(
        f"BLIND_MATRIX_SHA256={matrix_sha256}\n"
        f"TOTAL_CASES={len(cases)}\n"
        f"TIMESTAMP=2026-10-15T23:05:00Z\n",
        encoding="utf-8",
    )
    print(f"Generated {len(cases)} cases.")
    print(f"BLIND_MATRIX_SHA256={matrix_sha256}")


if __name__ == "__main__":
    main()
