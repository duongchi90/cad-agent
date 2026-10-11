"""test_cardinal_rotation_benchmark.py - Benchmark of Cardinal Rotation Strategies A, B, C, D.

ROLE=ANTIGRAVITY_RESEARCH
MODE=CARDINAL_ROTATED_TEXT_EXTRACTION_EMPIRICAL
TARGET_EPIC=CARDINAL_ROTATED_TEXT_EXTRACTION_V1

Compares:
  - STRATEGY_A_CURRENT: Single upright OCR (0 deg only)
  - STRATEGY_B_BRUTE_CARDINAL: 4-way rotation with composite evidence scoring
  - STRATEGY_C_OSD: Tesseract Orientation & Script Detection (--psm 0), then OCR
  - STRATEGY_D_GEOMETRY_ASSISTED: Aspect ratio pruning (2 orientations if AR > 1.75 or AR < 0.57, else 4)

Measures:
  - Exact match accuracy (%) across 0, 90, 180, 270 deg
  - Correct source rotation determination (%)
  - Execution runtime (ms per ROI)
  - Failure modes per strategy
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
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

    # Semantic pattern bonuses
    if re.match(r"^\d+([.,]\d+)?$", t):
        score += 25.0
    elif re.match(r"^[A-Z]{1,4}[-_][A-Z0-9]+([-_/][A-Z0-9]+)*$", t):
        score += 25.0
    elif re.match(r"^[RMØ@]\d+([.,]\d+)?$", t, re.IGNORECASE):
        score += 25.0
    elif len(t.split()) >= 2:
        score += 15.0

    return round(score, 2)


def run_strategy_a(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    """Strategy A: Single upright OCR (current main)."""
    data = pytesseract.image_to_data(crop_bgr, output_type=pytesseract.Output.DICT, config="--psm 7")
    words = [w.strip() for w in data["text"] if w.strip()]
    confs = [float(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and c not in ("-1", "")]
    text = " ".join(words)
    mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return text, mean_conf, 0.0


def run_strategy_b(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    """Strategy B: Brute cardinal 4-way with composite scoring."""
    best_text = ""
    best_conf = 0.0
    best_source_rot = 0.0
    best_score = -999.0

    for k in range(4):
        norm_rot_ccw = k * 90
        cand_source_rot = float((360 - norm_rot_ccw) % 360)
        rot_img = np.rot90(crop_bgr, k=k)

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


def run_strategy_c(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    """Strategy C: OSD orientation detection, then OCR."""
    # Attempt OSD
    try:
        osd = pytesseract.image_to_osd(crop_bgr)
        match = re.search(r"Orientation in degrees:\s*(\d+)", osd)
        osd_angle = int(match.group(1)) if match else 0
        # OSD reports degrees of clockwise rotation needed, or script angle
        k = (osd_angle // 90) % 4
        # Normalize and OCR
        rot_img = np.rot90(crop_bgr, k=k)
        data = pytesseract.image_to_data(rot_img, output_type=pytesseract.Output.DICT, config="--psm 7")
        words = [w.strip() for w in data["text"] if w.strip()]
        confs = [float(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and c not in ("-1", "")]
        text = " ".join(words)
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        source_rot = float((360 - k * 90) % 360)
        return text, round(mean_conf, 3), source_rot
    except Exception:
        # OSD failure fallback: upright OCR
        return run_strategy_a(crop_bgr)


def run_strategy_d(crop_bgr: np.ndarray) -> Tuple[str, float, float]:
    """Strategy D: Geometry-assisted aspect ratio pruning."""
    h, w = crop_bgr.shape[:2]
    ar = w / max(h, 1)

    if ar >= 1.75:
        # Elongated horizontally: only test 0 and 180 deg (k=0 and k=2)
        candidate_ks = [0, 2]
    elif ar <= 0.57:
        # Elongated vertically: only test 90 and 270 deg (k=3 and k=1)
        candidate_ks = [3, 1]
    else:
        # Near square: test all 4
        candidate_ks = [0, 1, 2, 3]

    best_text = ""
    best_conf = 0.0
    best_source_rot = 0.0
    best_score = -999.0

    for k in candidate_ks:
        norm_rot_ccw = k * 90
        cand_source_rot = float((360 - norm_rot_ccw) % 360)
        rot_img = np.rot90(crop_bgr, k=k)

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


def run_benchmark():
    test_cases = [
        "1700",
        "12.5",
        "TP-TL-A001/07/26",
        "R12",
        "M20",
        "TYP 4 PLACES",
    ]
    rotations = [0, 90, 180, 270]

    strategies = {
        "Strategy A (Current Upright)": run_strategy_a,
        "Strategy B (Brute 4-Way)": run_strategy_b,
        "Strategy C (OSD Mode)": run_strategy_c,
        "Strategy D (Geometry-Assisted)": run_strategy_d,
    }

    print("=" * 105)
    print("CARDINAL ROTATION STRATEGIES BENCHMARK: ACCURACY & SPEED COMPARISON")
    print("=" * 105)

    stats = {name: {"exact": 0, "rot_correct": 0, "total": 0, "time_ms": 0.0} for name in strategies}

    for text in test_cases:
        for rot in rotations:
            crop = render_crop(text, source_angle=rot)
            for strat_name, strat_fn in strategies.items():
                stats[strat_name]["total"] += 1
                t0 = time.perf_counter()
                out_text, out_conf, out_rot = strat_fn(crop)
                t1 = time.perf_counter()
                stats[strat_name]["time_ms"] += (t1 - t0) * 1000.0

                is_exact = (out_text == text)
                is_rot = (out_rot == float(rot))
                if is_exact:
                    stats[strat_name]["exact"] += 1
                if is_rot:
                    stats[strat_name]["rot_correct"] += 1

    print(f"{'Strategy':<32} | {'Exact Rate':<14} | {'Rot Accuracy':<14} | {'Total Time (ms)':<16} | {'Mean ms/ROI':<12}")
    print("-" * 105)
    for name, s in stats.items():
        exact_pct = 100.0 * s["exact"] / s["total"]
        rot_pct = 100.0 * s["rot_correct"] / s["total"]
        mean_time = s["time_ms"] / s["total"]
        print(f"{name:<32} | {s['exact']}/{s['total']} ({exact_pct:5.1f}%) | {s['rot_correct']}/{s['total']} ({rot_pct:5.1f}%) | {s['time_ms']:10.1f} ms     | {mean_time:6.1f} ms")
    print("=" * 105)


if __name__ == "__main__":
    run_benchmark()
