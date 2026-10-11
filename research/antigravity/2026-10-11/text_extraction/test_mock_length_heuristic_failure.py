"""test_mock_length_heuristic_failure.py - Empirical failure of length selection heuristic.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Goal:
Empirically demonstrate that the demo_pipeline.py::mock_vision_reader() heuristic:
    "try all 4 rotations and choose longest non-empty string"
(max(candidates, key=len)) fails catastrophically on engineering drawings.

When an ROI is rotated incorrectly, Tesseract frequently hallucinates longer garbage strings
(e.g., 'wo', 'fo.)', 'fs)', 'sexe)') which easily defeat shorter, correct ground truth strings
(e.g., '5', '8', '10', '0.5', 'A', 'C').
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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


def render_crop(text: str, source_angle: int, font_size: int = 24) -> np.ndarray:
    font_path = os.path.join(r"C:\Windows\Fonts", "arial.ttf")
    font = ImageFont.truetype(font_path, font_size) if os.path.exists(font_path) else ImageFont.load_default()

    dummy = Image.new("RGB", (1, 1), "white")
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font)
    pad = 8
    w, h = (bbox[2] - bbox[0]) + 2 * pad, (bbox[3] - bbox[1]) + 2 * pad
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), text, fill="black", font=font)

    if source_angle != 0:
        img = img.rotate(source_angle, expand=True, fillcolor="white")

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def run_length_heuristic_benchmark():
    test_suite = [
        ("5", 0), ("5", 90), ("5", 180), ("5", 270),
        ("8", 0), ("8", 90), ("8", 180), ("8", 270),
        ("10", 0), ("10", 90), ("10", 180), ("10", 270),
        ("0.5", 0), ("0.5", 90), ("0.5", 180), ("0.5", 270),
        ("A", 0), ("A", 90), ("A", 180), ("A", 270),
        ("C", 0), ("C", 90), ("C", 180), ("C", 270),
    ]

    print("=" * 110)
    print("EMPIRICAL BENCHMARK: FAILURE OF STRING LENGTH HEURISTIC (max(candidates, key=len))")
    print("=" * 110)
    print(
        f"{'Ground Truth':<12} | {'Src Rot':<7} | {'Correct Cand':<15} | {'Length Selection':<20} | "
        f"{'Selected Len':<12} | {'Correct Len':<11} | {'Status':<15}"
    )
    print("-" * 110)

    failures = 0
    total = len(test_suite)

    for text, angle in test_suite:
        crop = render_crop(text, source_angle=angle)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        candidates = []
        for k in range(4):
            norm_rot = k * 90
            cand_source = (360 - norm_rot) % 360
            rot_img = np.rot90(gray, k=k)
            # Use PSM 7 as in mock_vision_reader / single line
            t = pytesseract.image_to_string(rot_img, config="--psm 7").strip()
            if t:
                candidates.append((cand_source, t, len(t)))

        # Find candidate corresponding to correct orientation
        correct_cand = [c for c in candidates if c[0] == angle]
        correct_text = correct_cand[0][1] if correct_cand else "<NONE>"
        correct_len = len(correct_text) if correct_cand else 0

        # Run mock selection heuristic: max by length
        if candidates:
            selected = max(candidates, key=lambda c: len(c[1]))
            selected_rot, selected_text, selected_len = selected
        else:
            selected_rot, selected_text, selected_len = None, "<EMPTY>", 0

        is_fail = (selected_rot != angle) or (selected_text != correct_text)
        if is_fail:
            failures += 1
            status = "FAILED (GARBAGE)"
        else:
            status = "PASSED"

        print(
            f"{text:<12} | {angle:<7} | {correct_text:<15} | {selected_text:<20} | "
            f"{selected_len:<12} | {correct_len:<11} | {status:<15}"
        )

    print("-" * 110)
    failure_rate = 100.0 * failures / total
    print(f"TOTAL TESTED: {total} | HEURISTIC FAILURES: {failures} ({failure_rate:.1f}%)")
    print("=" * 110)
    assert failures > 0, "Expected string length heuristic to fail on short strings."
    print("PROOF COMPLETE: 'max(candidates, key=len)' selects confident garbage over correct short text.")


if __name__ == "__main__":
    run_length_heuristic_benchmark()
