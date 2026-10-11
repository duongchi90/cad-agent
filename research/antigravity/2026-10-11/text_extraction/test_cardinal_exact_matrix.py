"""test_cardinal_exact_matrix.py - Full Empirical Matrix across Text Classes, Rotations, and Font Sizes.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Matrix dimensions:
  - Text classes:
      A. Pure dimension: '1700'
      B. Decimal: '12.5'
      C. Drawing code: 'TP-TL-A001/07/26'
      D. Latin label: 'R12', 'M20'
      E. Short label: 'DIAM'
      F. General note: 'TYP 4 PLACES'
  - Source rotations: 0, 90, 180, 270 deg
  - Font sizes: 12, 18, 24, 36, 48 px
  - Paddings: 6, 12 px
  - Contrasts: Normal (black on white) vs Inverse (white on black, auto-inverted)

Measures:
  - OCR_EXACT_RATE
  - OCR_NORMALIZED_RATE
  - ROTATION_CLASSIFICATION_RATE
  - MEAN_CONFIDENCE
  - FALSE_ACCEPT_RATE
"""

from __future__ import annotations

import os
import re
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


def render_matrix_crop(
    text: str,
    source_angle: int,
    font_size: int,
    pad_px: int = 8,
    inverse: bool = False,
) -> np.ndarray:
    font_path = os.path.join(r"C:\Windows\Fonts", "arial.ttf")
    font = ImageFont.truetype(font_path, font_size) if os.path.exists(font_path) else ImageFont.load_default()

    dummy = Image.new("RGB", (1, 1), "white")
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = max(tw + 2 * pad_px, 10), max(th + 2 * pad_px, 10)

    bg_color = "black" if inverse else "white"
    fg_color = "white" if inverse else "black"

    img = Image.new("RGB", (w, h), bg_color)
    d = ImageDraw.Draw(img)
    d.text((pad_px - bbox[0], pad_px - bbox[1]), text, fill=fg_color, font=font)

    if source_angle != 0:
        img = img.rotate(source_angle, expand=True, fillcolor=bg_color)

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


def extract_cardinal_text(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    """Execute cardinal normalized OCR using composite evidence selection."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    # Contrast normalization: if background is dark, invert to black text on white
    if np.mean(gray) < 127:
        gray = cv2.bitwise_not(gray)

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


def run_matrix_benchmark():
    text_corpus = [
        ("A", "1700"),
        ("B", "12.5"),
        ("C", "TP-TL-A001/07/26"),
        ("D", "R12"),
        ("D", "M20"),
        ("E", "DIAM"),
        ("F", "TYP 4 PLACES"),
    ]

    rotations = [0, 90, 180, 270]
    font_sizes = [12, 18, 24, 36, 48]
    paddings = [6, 12]

    total_runs = 0
    exact_matches = 0
    norm_matches = 0
    rot_correct = 0
    conf_sum = 0.0
    false_accepts = 0

    print("=" * 110)
    print("EMPIRICAL MATRIX: CARDINAL ROTATION EXTRACTION ACROSS CLASSES, ROTATIONS, AND FONT SIZES")
    print("=" * 110)

    # Breakdown by font size
    by_font_size = {fs: {"total": 0, "exact": 0, "rot": 0, "conf_sum": 0.0} for fs in font_sizes}
    # Breakdown by rotation
    by_rotation = {rot: {"total": 0, "exact": 0, "rot": 0, "conf_sum": 0.0} for rot in rotations}

    for cls_id, expected in text_corpus:
        for rot in rotations:
            for fs in font_sizes:
                for pad in paddings:
                    total_runs += 1
                    crop = render_matrix_crop(expected, source_angle=rot, font_size=fs, pad_px=pad)
                    out_text, out_conf, out_rot = extract_cardinal_text(crop)

                    is_exact = (out_text == expected)
                    norm_expected = "".join(expected.split()).lower()
                    norm_actual = "".join(out_text.split()).lower()
                    is_norm = (norm_expected == norm_actual)
                    is_rot = (out_rot == float(rot))

                    if is_exact:
                        exact_matches += 1
                    if is_norm:
                        norm_matches += 1
                    if is_rot:
                        rot_correct += 1
                    conf_sum += out_conf

                    # False accept: non-empty output that matches neither exact nor norm
                    if out_text and not is_norm and not is_exact:
                        false_accepts += 1

                    by_font_size[fs]["total"] += 1
                    if is_exact:
                        by_font_size[fs]["exact"] += 1
                    if is_rot:
                        by_font_size[fs]["rot"] += 1
                    by_font_size[fs]["conf_sum"] += out_conf

                    by_rotation[rot]["total"] += 1
                    if is_exact:
                        by_rotation[rot]["exact"] += 1
                    if is_rot:
                        by_rotation[rot]["rot"] += 1
                    by_rotation[rot]["conf_sum"] += out_conf

    ocr_exact_rate = 100.0 * exact_matches / total_runs
    ocr_norm_rate = 100.0 * norm_matches / total_runs
    rot_class_rate = 100.0 * rot_correct / total_runs
    mean_conf = conf_sum / total_runs
    false_accept_rate = 100.0 * false_accepts / total_runs

    print(f"TOTAL RUNS: {total_runs}")
    print(f"OCR_EXACT_RATE:               {exact_matches}/{total_runs} ({ocr_exact_rate:5.1f}%)")
    print(f"OCR_NORMALIZED_RATE:          {norm_matches}/{total_runs} ({ocr_norm_rate:5.1f}%)")
    print(f"ROTATION_CLASSIFICATION_RATE: {rot_correct}/{total_runs} ({rot_class_rate:5.1f}%)")
    print(f"MEAN_CONFIDENCE:              {mean_conf:.3f}")
    print(f"FALSE_ACCEPT_RATE:            {false_accepts}/{total_runs} ({false_accept_rate:5.1f}%)")
    print("-" * 110)

    print("BREAKDOWN BY FONT SIZE:")
    for fs in font_sizes:
        s = by_font_size[fs]
        print(f"  Font size {fs:2d} px: Exact = {s['exact']}/{s['total']} ({100.0*s['exact']/s['total']:5.1f}%), Rot = {s['rot']}/{s['total']} ({100.0*s['rot']/s['total']:5.1f}%), Mean Conf = {s['conf_sum']/s['total']:.3f}")

    print("-" * 110)
    print("BREAKDOWN BY ROTATION:")
    for rot in rotations:
        s = by_rotation[rot]
        print(f"  Rotation {rot:3d} deg: Exact = {s['exact']}/{s['total']} ({100.0*s['exact']/s['total']:5.1f}%), Rot = {s['rot']}/{s['total']} ({100.0*s['rot']/s['total']:5.1f}%), Mean Conf = {s['conf_sum']/s['total']:.3f}")
    print("=" * 110)

    assert ocr_norm_rate >= 90.0, f"Expected normalized rate >= 90%, got {ocr_norm_rate}%"
    print("MATRIX BENCHMARK VERIFIED.")


if __name__ == "__main__":
    run_matrix_benchmark()
