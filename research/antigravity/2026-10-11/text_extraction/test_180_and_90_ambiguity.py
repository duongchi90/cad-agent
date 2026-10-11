"""test_180_and_90_ambiguity.py - Empirical Ambiguity Handling for Cardinal Text.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Sections:
  1. 0 deg vs 180 deg Rotational Ambiguity:
     Strings: '808', '180', 'MOM', 'NO', 'ON', 'S', 'Z', '6', '9', '69', '96'
     Tests whether confidence and glyph symmetry create ambiguous orientation candidates.
     Verifies bounded status: TEXT_CONTENT_ACCEPTED, ROTATION_UNRESOLVED.
  2. 90 deg vs 270 deg Separation:
     Strings: '1700', 'M20', 'R10', '@40' (Ø40), '12', '100'
     Measures confidence delta and semantic validity separation between quarter-turn candidates.
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


def evaluate_180_degree_ambiguity():
    test_cases = ["808", "180", "MOM", "NO", "ON", "S", "Z", "6", "9", "69", "96"]
    print("=" * 105)
    print("PART 1: 0 DEG VS 180 DEG AMBIGUITY EVALUATION")
    print("=" * 105)
    print(f"{'String':<8} | {'0 deg Text':<12} | {'0 Conf':<7} | {'180 deg Text':<12} | {'180 Conf':<8} | {'Delta Conf':<10} | {'Classification':<25}")
    print("-" * 105)

    ambiguous_count = 0
    total = len(test_cases)

    for s in test_cases:
        crop = render_crop(s, source_angle=0)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # k=0 (0 deg)
        d0 = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config="--psm 7")
        t0 = " ".join(w.strip() for w in d0["text"] if w.strip())
        c0_list = [float(c) for w, c in zip(d0["text"], d0["conf"]) if w.strip() and c not in ("-1", "")]
        conf0 = sum(c0_list) / len(c0_list) if c0_list else 0.0

        # k=2 (180 deg)
        d180 = pytesseract.image_to_data(np.rot90(gray, 2), output_type=pytesseract.Output.DICT, config="--psm 7")
        t180 = " ".join(w.strip() for w in d180["text"] if w.strip())
        c180_list = [float(c) for w, c in zip(d180["text"], d180["conf"]) if w.strip() and c not in ("-1", "")]
        conf180 = sum(c180_list) / len(c180_list) if c180_list else 0.0

        delta = abs(conf0 - conf180)
        # Symmetrical / ambiguous if delta <= 6.0 and both produce non-empty strings
        is_ambiguous = (delta <= 6.0) and (bool(t0) and bool(t180))
        if is_ambiguous:
            ambiguous_count += 1
            classification = "ROTATION_AMBIGUOUS"
        else:
            classification = "RESOLVED_BY_CONFIDENCE"

        print(f"{s:<8} | {t0:<12} | {conf0:<7.1f} | {t180:<12} | {conf180:<8.1f} | {delta:<10.1f} | {classification:<25}")

    print("-" * 105)
    print(f"Ambiguous strings detected: {ambiguous_count}/{total} ({100.0*ambiguous_count/total:.1f}%)")
    print("Contract: When ROTATION_AMBIGUOUS occurs, content is accepted with ROTATION_UNRESOLVED.")
    print("=" * 105)


def evaluate_90_vs_270_separation():
    test_cases = ["1700", "M20", "R10", "@40", "12", "100"]
    print("\n" + "=" * 105)
    print("PART 2: 90 DEG VS 270 DEG SEPARATION EVALUATION (SOURCE ROTATION = 90 DEG)")
    print("=" * 105)
    print(f"{'String':<8} | {'Correct 90 Text':<15} | {'90 Conf':<8} | {'Opposite 270 Text':<18} | {'270 Conf':<8} | {'Delta':<8} | {'Separated?':<12}")
    print("-" * 105)

    separated_count = 0
    total = len(test_cases)

    for s in test_cases:
        crop = render_crop(s, source_angle=90)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # Candidate 90 deg (norm=270 CCW, k=3)
        d90 = pytesseract.image_to_data(np.rot90(gray, 3), output_type=pytesseract.Output.DICT, config="--psm 7")
        t90 = " ".join(w.strip() for w in d90["text"] if w.strip())
        c90_list = [float(c) for w, c in zip(d90["text"], d90["conf"]) if w.strip() and c not in ("-1", "")]
        conf90 = sum(c90_list) / len(c90_list) if c90_list else 0.0

        # Candidate 270 deg (norm=90 CCW, k=1)
        d270 = pytesseract.image_to_data(np.rot90(gray, 1), output_type=pytesseract.Output.DICT, config="--psm 7")
        t270 = " ".join(w.strip() for w in d270["text"] if w.strip())
        c270_list = [float(c) for w, c in zip(d270["text"], d270["conf"]) if w.strip() and c not in ("-1", "")]
        conf270 = sum(c270_list) / len(c270_list) if c270_list else 0.0

        delta = conf90 - conf270
        is_separated = (delta >= 15.0) or (t90 == s and t270 != s)
        if is_separated:
            separated_count += 1
            status = "YES (CLEAN)"
        else:
            status = "UNCERTAIN"

        print(f"{s:<8} | {t90:<15} | {conf90:<8.1f} | {t270:<18} | {conf270:<8.1f} | {delta:<8.1f} | {status:<12}")

    print("-" * 105)
    print(f"Separation rate: {separated_count}/{total} ({100.0*separated_count/total:.1f}%)")
    print("=" * 105)


if __name__ == "__main__":
    evaluate_180_degree_ambiguity()
    evaluate_90_vs_270_separation()
