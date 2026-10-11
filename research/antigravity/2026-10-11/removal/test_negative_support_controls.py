"""Empirical measurement and threshold closure for negative source support across controls A-H."""

from __future__ import annotations

import hashlib
import io
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(r"C:\Users\duong\ZCodeProject\cad-agent")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def create_png_bytes(image: Image.Image) -> tuple[bytes, str]:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    b = stream.getvalue()
    return b, hashlib.sha256(b).hexdigest()


def bresenham_samples(start: tuple[int, int], end: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    x0, y0 = start
    x1, y1 = end
    count = max(abs(x1 - x0), abs(y1 - y0)) + 1
    xs = np.rint(np.linspace(x0, x1, count)).astype(np.int32)
    ys = np.rint(np.linspace(y0, y1, count)).astype(np.int32)
    return xs, ys


def evaluate_candidate_verifier(
    image: np.ndarray,
    roi: list[int],
    start_px: tuple[int, int],
    end_px: tuple[int, int],
    *,
    darkness_threshold: int = 220,
    max_ink_fraction: float = 0.02,
    min_mean_intensity: float = 245.0,
    dilation_tolerance_px: int = 2,
    max_dilated_ink_fraction: float = 0.05,
) -> dict[str, object]:
    """Pure pixel-domain candidate verifier for absence evidence."""
    height, width = image.shape
    x0_roi, y0_roi, x1_roi, y1_roi = roi

    xs, ys = bresenham_samples(start_px, end_px)
    sample_count = int(xs.size)

    # 1. ROI bounds check
    in_roi = not (
        np.any(xs < x0_roi)
        or np.any(xs > x1_roi)
        or np.any(ys < y0_roi)
        or np.any(ys > y1_roi)
        or np.any(xs < 0)
        or np.any(xs >= width)
        or np.any(ys < 0)
        or np.any(ys >= height)
    )
    if not in_roi:
        return {
            "status": "INSUFFICIENT",
            "reason": "PRIMITIVE_OUTSIDE_ROI_OR_RENDER",
            "sample_count": sample_count,
            "mean_intensity": None,
            "ink_fraction": None,
            "dilated_ink_fraction": None,
        }

    # 2. Extract corridor sample pixels
    corridor_pixels = image[ys, xs]
    mean_intensity = float(np.mean(corridor_pixels))
    ink_samples = corridor_pixels <= darkness_threshold
    ink_fraction = float(np.mean(ink_samples))

    # 3. Dilated ink check (tolerance = 2px)
    dark_mask = (image <= darkness_threshold).astype(np.uint8) * 255
    if dilation_tolerance_px > 0:
        kernel_size = dilation_tolerance_px * 2 + 1
        dilated_mask = np.asarray(
            Image.fromarray(dark_mask).filter(ImageFilter.MaxFilter(size=kernel_size)),
            dtype=np.uint8,
        )
    else:
        dilated_mask = dark_mask
    dilated_ink_fraction = float(np.mean(dilated_mask[ys, xs] > 0))

    # 4. Absence decision
    passed_ink = ink_fraction <= max_ink_fraction
    passed_mean = mean_intensity >= min_mean_intensity
    passed_dilation = dilated_ink_fraction <= max_dilated_ink_fraction

    if passed_ink and passed_mean and passed_dilation:
        status = "VERIFIED"
        reason = "OBSERVATIONAL_WHITESPACE_PROVEN"
    else:
        status = "INSUFFICIENT"
        failed_reasons = []
        if not passed_ink:
            failed_reasons.append(f"INK_FRACTION_EXCEEDED({ink_fraction:.4f}>{max_ink_fraction})")
        if not passed_mean:
            failed_reasons.append(f"MEAN_INTENSITY_LOW({mean_intensity:.1f}<{min_mean_intensity})")
        if not passed_dilation:
            failed_reasons.append(f"DILATED_INK_CONTAMINATION({dilated_ink_fraction:.4f}>{max_dilated_ink_fraction})")
        reason = "; ".join(failed_reasons)

    return {
        "status": status,
        "reason": reason,
        "sample_count": sample_count,
        "mean_intensity": round(mean_intensity, 2),
        "ink_fraction": round(ink_fraction, 4),
        "dilated_ink_fraction": round(dilated_ink_fraction, 4),
    }


def run_control_suite():
    print("=== EMPIRICAL CONTROL SUITE: CASES 0 & A-H ===")
    width, height = 100, 100
    start_px, end_px = (20, 50), (80, 50)
    roi = [10, 10, 90, 90]

    scenarios = {}

    # Case 0: Positive control - Genuine deletion (pure white)
    img0 = Image.new("L", (width, height), 255)
    scenarios["Case 0: Genuine Deletion"] = img0

    # Control A: Faint but physically present line (intensity 230, above darkness threshold 220)
    imgA = Image.new("L", (width, height), 255)
    ImageDraw.Draw(imgA).line([start_px, end_px], fill=230, width=1)
    scenarios["Control A: Faint Present Line (val=230)"] = imgA

    # Control B: Partially occluded line (50% solid dark ink)
    imgB = Image.new("L", (width, height), 255)
    ImageDraw.Draw(imgB).line([start_px, (50, 50)], fill=0, width=1)
    scenarios["Control B: Partially Occluded Line"] = imgB

    # Control C: ROI-clipped line (ROI ends at x=70, line ends at x=80)
    # We will test this with custom roi in the loop

    # Control D: Nearby parallel-line contamination (line at y=52, dist=2px)
    imgD = Image.new("L", (width, height), 255)
    ImageDraw.Draw(imgD).line([(20, 52), (80, 52)], fill=0, width=1)
    scenarios["Control D: Nearby Parallel Line (dist=2px)"] = imgD

    # Control E: Dashed / center line (5px dash, 5px gap)
    imgE = Image.new("L", (width, height), 255)
    drawE = ImageDraw.Draw(imgE)
    for x in range(20, 80, 10):
        drawE.line([(x, 50), (min(x + 5, 80), 50)], fill=0, width=1)
    scenarios["Control E: Dashed Line"] = imgE

    # Control F: Text-crossed line (glyph crosses at x=45..55)
    imgF = Image.new("L", (width, height), 255)
    drawF = ImageDraw.Draw(imgF)
    drawF.rectangle([48, 40, 52, 60], fill=0)  # vertical stroke of text crossing
    scenarios["Control F: Text-Crossed Line"] = imgF

    # Control G: Shifted line (original empty, new line at y=65)
    imgG = Image.new("L", (width, height), 255)
    ImageDraw.Draw(imgG).line([(20, 65), (80, 65)], fill=0, width=1)
    scenarios["Control G: Shifted Line (15px away)"] = imgG

    # Control H: Unknown occlusion (hatch/stain noise)
    imgH = Image.new("L", (width, height), 255)
    drawH = ImageDraw.Draw(imgH)
    for x in range(25, 75, 4):
        drawH.point((x, 50), fill=180)
    scenarios["Control H: Unparsed Texture / Hatch Noise"] = imgH

    results = []
    for name, img in scenarios.items():
        arr = np.array(img, dtype=np.uint8)
        res = evaluate_candidate_verifier(arr, roi, start_px, end_px)
        results.append((name, res))

    # Test Control C separately with clipped ROI
    arr0 = np.array(img0, dtype=np.uint8)
    resC = evaluate_candidate_verifier(arr0, [10, 10, 70, 90], start_px, end_px)  # ROI clips at x=70
    results.insert(3, ("Control C: ROI-Clipped Line (ROI x1=70)", resC))

    print(f"\n{'Scenario':<42} | {'Status':<12} | {'Mean':<6} | {'InkFrac':<8} | {'DilFrac':<8} | {'Reason'}")
    print("-" * 115)
    for name, r in results:
        mean_str = f"{r['mean_intensity']}" if r['mean_intensity'] is not None else "N/A"
        ink_str = f"{r['ink_fraction']}" if r['ink_fraction'] is not None else "N/A"
        dil_str = f"{r['dilated_ink_fraction']}" if r['dilated_ink_fraction'] is not None else "N/A"
        print(f"{name:<42} | {r['status']:<12} | {mean_str:<6} | {ink_str:<8} | {dil_str:<8} | {r['reason']}")


if __name__ == "__main__":
    run_control_suite()
