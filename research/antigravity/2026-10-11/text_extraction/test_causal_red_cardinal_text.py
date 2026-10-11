"""test_causal_red_cardinal_text.py - Public Causal RED for Cardinal Rotated Text Extraction.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Goal:
Demonstrate that current production extract_text_tesseract() in primitive_ir_lib/text_extraction.py
fails on text rotated at 90 deg, 180 deg, and 270 deg across 6 core text classes (A-F):
  A. Pure dimension number: '1700'
  B. Decimal dimension: '12.5'
  C. Drawing code: 'TP-TL-A001/07/26'
  D. Short Latin engineering label: 'R12', 'M20', '@20' (Ø20)
  E. Vietnamese label: 'VAT LIEU', 'SO LUONG'
  F. Short general note: 'TYP 4 PLACES'

Measured variables:
  - SOURCE_ROTATION
  - EXPECTED_TEXT
  - OCR_TEXT
  - OCR_CONFIDENCE
  - RAW_TEXT_ROTATION_DEG
  - SEMANTIC_ROLE
  - PARSED_VALUE
  - EXACT_MATCH
  - NORMALIZED_MATCH
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

# Configure Tesseract path if on Windows
if not shutil.which("tesseract"):
    for cand in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.exists(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            break

# Ensure project root is in sys.path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from primitive_ir_lib.text_extraction import extract_text_tesseract, RawText


def render_text_fixture(
    text: str,
    angle_deg: int,
    font_size: int = 26,
    pad_px: int = 10,
    font_name: str = "arial.ttf",
) -> np.ndarray:
    """Render a clean synthetic text crop and rotate it by angle_deg (CCW)."""
    font_path = os.path.join(r"C:\Windows\Fonts", font_name)
    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    dummy = Image.new("RGB", (1, 1), "white")
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    w, h = tw + 2 * pad_px, th + 2 * pad_px
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((pad_px - bbox[0], pad_px - bbox[1]), text, fill="black", font=font)

    if angle_deg != 0:
        img = img.rotate(angle_deg, expand=True, fillcolor="white")

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def run_public_causal_red() -> Dict[str, any]:
    """Test current public extract_text_tesseract() across 0, 90, 180, 270 degrees."""
    test_cases = [
        ("A", "Pure Dimension", "1700"),
        ("B", "Decimal", "12.5"),
        ("C", "Drawing Code", "TP-TL-A001/07/26"),
        ("D", "Latin Label (R)", "R12"),
        ("D", "Latin Label (M)", "M20"),
        ("E", "Vietnamese (Unaccented)", "VAT LIEU"),
        ("F", "General Note", "TYP 4 PLACES"),
    ]

    rotations = [0, 90, 180, 270]
    results = []

    print("=" * 105)
    print("PUBLIC CAUSAL RED: CURRENT MAIN extract_text_tesseract() ACROSS CARDINAL ROTATIONS")
    print("=" * 105)
    print(
        f"{'Class':<5} | {'Source':<18} | {'Rot':<4} | {'OCR Text':<18} | {'Conf':<5} | "
        f"{'Rot_Deg':<7} | {'Role':<15} | {'Val':<8} | {'Exact':<5} | {'Norm':<5}"
    )
    print("-" * 105)

    failures_by_angle = {0: 0, 90: 0, 180: 0, 270: 0}
    total_by_angle = {0: 0, 90: 0, 180: 0, 270: 0}

    for cls_id, cls_name, expected in test_cases:
        for rot in rotations:
            total_by_angle[rot] += 1
            crop = render_text_fixture(expected, angle_deg=rot)
            h, w = crop.shape[:2]

            # Call current main public API
            raw_results: List[RawText] = extract_text_tesseract(
                crop, roi_boxes=[(0, 0, w, h)], lang="eng"
            )

            if raw_results:
                r = raw_results[0]
                ocr_text = r.content.strip()
                ocr_conf = r.confidence
                out_rot = r.rotation_deg
                role = r.semantic_role
                val = str(r.parsed_value) if r.parsed_value is not None else "None"
            else:
                ocr_text = "<EMPTY>"
                ocr_conf = 0.0
                out_rot = 0.0
                role = "unknown"
                val = "None"

            exact = ocr_text == expected
            # Normalized match: stripped, lowercase, whitespace collapsed
            norm_expected = "".join(expected.split()).lower()
            norm_actual = "".join(ocr_text.split()).lower()
            norm_match = norm_expected == norm_actual

            if not exact:
                failures_by_angle[rot] += 1

            results.append({
                "class": cls_id,
                "expected": expected,
                "source_rotation": rot,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_conf,
                "raw_text_rotation_deg": out_rot,
                "semantic_role": role,
                "parsed_value": val,
                "exact_match": exact,
                "normalized_match": norm_match,
            })

            print(
                f"{cls_id:<5} | {expected:<18} | {rot:<4} | {ocr_text:<18} | {ocr_conf:<5.2f} | "
                f"{out_rot:<7.1f} | {role:<15} | {val:<8} | {str(exact):<5} | {str(norm_match):<5}"
            )

    print("-" * 105)
    print("SUMMARY BY SOURCE ROTATION:")
    for rot in rotations:
        fail_count = failures_by_angle[rot]
        total = total_by_angle[rot]
        exact_pct = 100.0 * (total - fail_count) / total
        print(f"  Rotation {rot:3d} deg: Exact Match = {total - fail_count}/{total} ({exact_pct:5.1f}%), Failures = {fail_count}/{total}")

    print("=" * 105)
    assert failures_by_angle[0] == 0, "Upright 0-deg text must succeed on clean synthetic fixtures."
    assert failures_by_angle[90] == total_by_angle[90], "90-deg text must fail 100% on current main (causal RED)."
    assert failures_by_angle[180] == total_by_angle[180], "180-deg text must fail 100% on current main (causal RED)."
    assert failures_by_angle[270] == total_by_angle[270], "270-deg text must fail 100% on current main (causal RED)."
    print("CAUSAL RED VERIFIED: 100% failure rate for all rotated text (90, 180, 270 deg) on current main.")
    return {"results": results, "failures_by_angle": failures_by_angle}


if __name__ == "__main__":
    run_public_causal_red()
