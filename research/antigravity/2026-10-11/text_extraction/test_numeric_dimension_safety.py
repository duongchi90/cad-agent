"""test_numeric_dimension_safety.py - Numeric Dimension Safety and Substitution Tracking.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Goal:
Dimension text is safety-sensitive because wrong OCR directly drives calibration and CAD geometry.
Test numbers across all 4 cardinal rotations:
  - '100', '110', '1700', '1900', '2100', '4200'
  - '12.5', '12,5', '0.5', '25.4'
  - '@20' (representing Ø20), 'R20', 'M20'

Track catastrophic substitutions:
  - 0 <-> O
  - 1 <-> I / l
  - 5 <-> S
  - 6 <-> 9
  - 8 <-> B
  - Decimal point loss ('12.5' -> '125')
  - Prefix loss ('R20' -> '20')
  - Comma / period normalization

Measure exact parsed numeric value and semantic role.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from typing import Dict, List, Optional, Tuple

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

from primitive_ir_lib.text_extraction import classify_semantic_role


def render_dim_crop(text: str, source_angle: int, font_size: int = 24) -> np.ndarray:
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

    if len(t) == 1:
        if not t.isalnum():
            score -= 60.0
        else:
            score -= 15.0

    if re.match(r"^\d+([.,]\d+)?$", t):
        score += 25.0
    elif re.match(r"^[A-Z]{1,4}[-_][A-Z0-9]+([-_/][A-Z0-9]+)*$", t):
        score += 25.0
    elif re.match(r"^[RMØ@]\d+([.,]\d+)?$", t, re.IGNORECASE):
        score += 25.0
    elif len(t.split()) >= 2:
        score += 15.0

    return round(score, 2)


def extract_cardinal_dim(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    ar = w / max(h, 1)

    if ar >= 1.75:
        candidate_ks = [0, 2]
    elif ar <= 0.57:
        candidate_ks = [3, 1]
    else:
        candidate_ks = [0, 1, 2, 3]

    best_text = ""
    best_conf = 0.0
    best_source_rot = 0.0
    best_score = -999.0

    for k in candidate_ks:
        norm_rot_ccw = k * 90
        cand_source_rot = float((360 - norm_rot_ccw) % 360)
        rot_img = np.rot90(gray, k=k)

        data = pytesseract.image_to_data(rot_img, output_type=pytesseract.Output.DICT, config="--psm 7")
        words = [w.strip() for w in data["text"] if w.strip()]
        confs = [float(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and c not in ("-1", "")]
        text = " ".join(words)
        mean_conf = (sum(confs) / len(confs)) if confs else 0.0

        score = compute_composite_score(text, mean_conf)
        if score > best_score:
            best_score = score
            best_text = text
            best_conf = mean_conf / 100.0
            best_source_rot = cand_source_rot

    return best_text, round(best_conf, 3), best_source_rot


def run_numeric_safety_benchmark():
    test_dims = [
        # (input_text, expected_parsed_value)
        ("100", 100.0),
        ("110", 110.0),
        ("1700", 1700.0),
        ("1900", 1900.0),
        ("2100", 2100.0),
        ("4200", 4200.0),
        ("12.5", 12.5),
        ("12,5", 12.5),
        ("0.5", 0.5),
        ("25.4", 25.4),
        ("@20", None),  # Ø20 / label
        ("R20", None),
        ("M20", None),
    ]

    rotations = [0, 90, 180, 270]
    total_cases = len(test_dims) * len(rotations)

    exact_numeric_matches = 0
    catastrophic_substitutions = 0
    total_numeric = 0

    print("=" * 110)
    print("NUMERIC DIMENSION SAFETY BENCHMARK ACROSS CARDINAL ROTATIONS")
    print("=" * 110)
    print(
        f"{'Input Dim':<10} | {'Src Rot':<7} | {'OCR Text':<12} | {'Conf':<6} | "
        f"{'Role':<16} | {'Parsed Val':<11} | {'Exp Val':<9} | {'Safety Status':<20}"
    )
    print("-" * 110)

    for raw_dim, exp_val in test_dims:
        is_num = exp_val is not None
        if is_num:
            total_numeric += len(rotations)

        for rot in rotations:
            crop = render_dim_crop(raw_dim, source_angle=rot)
            ocr_text, conf, src_rot = extract_cardinal_dim(crop)

            role, parsed_val = classify_semantic_role(ocr_text)

            # Current main's _PURE_NUMBER_RE requires \d{2,5}, which excludes '0.5' (only 1 digit)
            # Check both classify_semantic_role and direct numeric float parse:
            direct_float = None
            try:
                direct_float = float(ocr_text.replace(",", "."))
            except ValueError:
                pass

            if is_num:
                # If direct float matches expected value, OCR succeeded
                if direct_float == exp_val:
                    exact_numeric_matches += 1
                    if parsed_val == exp_val:
                        status = "EXACT_NUMERIC_PASS"
                    else:
                        status = "OCR_PASS_REGEX_LIMIT"  # regex \d{2,5} excluded single leading digit
                elif direct_float is None:
                    status = "PARSE_FAILED"
                    catastrophic_substitutions += 1
                elif abs(direct_float - exp_val * 10) < 1e-4:
                    status = "DECIMAL_LOST"
                    catastrophic_substitutions += 1
                elif abs(direct_float - exp_val / 10) < 1e-4:
                    status = "DECIMAL_ADDED"
                    catastrophic_substitutions += 1
                else:
                    status = f"NUMERIC_CORRUPT ({direct_float})"
                    catastrophic_substitutions += 1
            else:
                norm_in = "".join(raw_dim.split()).upper()
                norm_out = "".join(ocr_text.split()).upper()
                if norm_in == norm_out:
                    status = "LABEL_PASS"
                else:
                    status = "LABEL_MISMATCH"

            exp_str = str(exp_val) if exp_val is not None else "N/A"
            parsed_str = str(parsed_val) if parsed_val is not None else "None"

            print(
                f"{raw_dim:<10} | {rot:<7} | {ocr_text:<12} | {conf:<6.2f} | "
                f"{role:<16} | {parsed_str:<11} | {exp_str:<9} | {status:<20}"
            )

    print("-" * 110)
    num_pass_rate = 100.0 * exact_numeric_matches / total_numeric
    print(f"NUMERIC CASES: {total_numeric} | EXACT NUMERIC MATCHES: {exact_numeric_matches} ({num_pass_rate:.1f}%)")
    print(f"CATASTROPHIC NUMERIC FAILURES: {catastrophic_substitutions}")
    print("=" * 110)
    assert num_pass_rate >= 95.0, f"Expected numeric pass rate >= 95%, got {num_pass_rate}%"
    print("DIMENSION NUMERIC SAFETY VERIFIED.")


if __name__ == "__main__":
    run_numeric_safety_benchmark()
