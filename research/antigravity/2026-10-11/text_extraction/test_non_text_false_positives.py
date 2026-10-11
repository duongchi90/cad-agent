"""test_non_text_false_positives.py - False-Positive Amplification Control for Non-Text ROIs.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Goal:
Trying four orientations multiplies OCR opportunities and could potentially increase false garbage.
Test 11 non-text geometric fixtures:
  1. Single line
  2. Parallel lines
  3. Hatch
  4. Circle
  5. Arc
  6. Crossing lines
  7. Dimension arrowhead
  8. Random noise
  9. Small rectangle
  10. Filled marker
  11. Border corner

Measures:
  - BASELINE_FALSE_TEXTS (0 deg raw)
  - FOUR_ROTATION_FALSE_TEXTS (unfiltered 4-way max length)
  - ACCEPTED_FALSE_TEXTS (under composite evidence selection score >= 75.0)
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from typing import Dict, List, Tuple

import cv2
import numpy as np
import pytesseract

if not shutil.which("tesseract"):
    for cand in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.exists(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            break

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def create_non_text_fixtures() -> Dict[str, np.ndarray]:
    fixtures = {}

    # 1. Single line
    img = np.full((50, 100, 3), 255, dtype=np.uint8)
    cv2.line(img, (10, 25), (90, 25), (0, 0, 0), 2)
    fixtures["single_line"] = img

    # 2. Parallel lines
    img = np.full((50, 100, 3), 255, dtype=np.uint8)
    cv2.line(img, (10, 15), (90, 15), (0, 0, 0), 2)
    cv2.line(img, (10, 35), (90, 35), (0, 0, 0), 2)
    fixtures["parallel_lines"] = img

    # 3. Hatch
    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    for d in range(-60, 120, 10):
        cv2.line(img, (0, d), (60, d + 60), (0, 0, 0), 1)
    fixtures["hatch"] = img

    # 4. Circle
    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    cv2.circle(img, (30, 30), 20, (0, 0, 0), 2)
    fixtures["circle"] = img

    # 5. Arc
    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    cv2.ellipse(img, (30, 30), (20, 20), 0, 0, 180, (0, 0, 0), 2)
    fixtures["arc"] = img

    # 6. Crossing lines
    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    cv2.line(img, (30, 5), (30, 55), (0, 0, 0), 2)
    cv2.line(img, (5, 30), (55, 30), (0, 0, 0), 2)
    fixtures["crossing_lines"] = img

    # 7. Arrowhead
    img = np.full((40, 60, 3), 255, dtype=np.uint8)
    pts = np.array([[10, 20], [45, 10], [45, 30]], np.int32)
    cv2.fillPoly(img, [pts], (0, 0, 0))
    fixtures["arrowhead"] = img

    # 8. Random noise
    np.random.seed(42)
    img = np.random.randint(200, 256, (50, 80, 3), dtype=np.uint8)
    fixtures["random_noise"] = img

    # 9. Small rectangle
    img = np.full((50, 50, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (15, 15), (35, 35), (0, 0, 0), 2)
    fixtures["small_rectangle"] = img

    # 10. Filled marker
    img = np.full((50, 50, 3), 255, dtype=np.uint8)
    cv2.circle(img, (25, 25), 10, (0, 0, 0), -1)
    fixtures["filled_marker"] = img

    # 11. Border corner
    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    cv2.line(img, (15, 15), (55, 15), (0, 0, 0), 3)
    cv2.line(img, (15, 15), (15, 55), (0, 0, 0), 3)
    fixtures["border_corner"] = img

    return fixtures


def compute_composite_score(text: str, mean_conf: float) -> float:
    t = text.strip()
    if not t:
        return -100.0

    score = mean_conf
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,/-_()[]Ø@±°:+")
    garbage_chars = sum(1 for ch in t if ch not in allowed)
    garbage_ratio = garbage_chars / max(len(t), 1)
    if garbage_ratio > 0.0:
        score -= (garbage_ratio * 50.0)

    # Isolated character penalty
    if len(t) == 1:
        if not t.isalnum():
            score -= 60.0
        else:
            score -= 25.0  # isolated single letter like 'O', 'A', 'L' from geometry

    if re.match(r"^\d+([.,]\d+)?$", t):
        score += 25.0
    elif re.match(r"^[A-Z]{1,4}[-_][A-Z0-9]+([-_/][A-Z0-9]+)*$", t):
        score += 25.0
    elif re.match(r"^[RMØ@]\d+([.,]\d+)?$", t, re.IGNORECASE):
        score += 25.0
    elif len(t.split()) >= 2:
        score += 15.0

    return round(score, 2)


def run_false_positive_control():
    fixtures = create_non_text_fixtures()

    print("=" * 115)
    print("NON-TEXT FALSE POSITIVE BENCHMARK: BASELINE VS 4-WAY UNFILTERED VS COMPOSITE SELECTION")
    print("=" * 115)
    print(
        f"{'Fixture':<17} | {'Baseline (0 deg)':<18} | {'4-Way Unfiltered (Mock)':<25} | "
        f"{'Composite Best':<18} | {'Score':<6} | {'Accepted?':<10}"
    )
    print("-" * 115)

    baseline_false = 0
    four_way_unfiltered_false = 0
    composite_accepted_false = 0
    total = len(fixtures)

    # Acceptance threshold for composite score
    ACCEPT_THRESHOLD = 75.0

    for name, img in fixtures.items():
        # Baseline (0 deg only)
        d0 = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 7")
        t0 = " ".join(w.strip() for w in d0["text"] if w.strip())
        if t0:
            baseline_false += 1

        # 4-way unfiltered (mock length heuristic)
        all_cands = []
        best_composite_text = ""
        best_composite_score = -999.0

        for k in range(4):
            rot_img = np.rot90(img, k=k)
            dk = pytesseract.image_to_data(rot_img, output_type=pytesseract.Output.DICT, config="--psm 7")
            tk = " ".join(w.strip() for w in dk["text"] if w.strip())
            if tk:
                ck = [float(c) for w, c in zip(dk["text"], dk["conf"]) if w.strip() and c not in ("-1", "")]
                confk = sum(ck) / len(ck) if ck else 0.0
                all_cands.append(tk)

                scorek = compute_composite_score(tk, confk)
                if scorek > best_composite_score:
                    best_composite_score = scorek
                    best_composite_text = tk

        mock_selected = max(all_cands, key=len) if all_cands else "<EMPTY>"
        if mock_selected != "<EMPTY>":
            four_way_unfiltered_false += 1

        is_accepted = (best_composite_score >= ACCEPT_THRESHOLD)
        if is_accepted:
            composite_accepted_false += 1
            status = "YES (FALSE)"
        else:
            status = "REJECTED (SAFE)"

        print(
            f"{name:<17} | {t0 or '<EMPTY>':<18} | {mock_selected:<25} | "
            f"{best_composite_text or '<EMPTY>':<18} | {best_composite_score:<6.1f} | {status:<10}"
        )

    print("-" * 115)
    print(f"BASELINE_FALSE_TEXTS:         {baseline_false}/{total} ({100.0*baseline_false/total:.1f}%)")
    print(f"FOUR_ROTATION_FALSE_TEXTS:     {four_way_unfiltered_false}/{total} ({100.0*four_way_unfiltered_false/total:.1f}%)")
    print(f"ACCEPTED_FALSE_TEXTS:          {composite_accepted_false}/{total} ({100.0*composite_accepted_false/total:.1f}%)")
    print("=" * 115)
    assert composite_accepted_false <= baseline_false, "Composite selector must not increase false positive acceptance."
    print("FALSE-POSITIVE CONTROL VERIFIED: 4-way composite selection does not amplify non-text garbage.")


if __name__ == "__main__":
    run_false_positive_control()
