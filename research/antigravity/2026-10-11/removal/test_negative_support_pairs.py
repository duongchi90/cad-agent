import io
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def create_raster_pair_benchmark():
    print("=" * 80)
    print("BENCHMARKING NEGATIVE-SUPPORT DISCRIMINATION ACROSS PAIRS A - H")
    print("=" * 80)

    # Base line geometry in pixels: (20, 50) -> (80, 50) (length = 60 px)
    start_px = (20, 50)
    end_px = (80, 50)
    width, height = 120, 100
    roi = (10, 10, 110, 90) # [x0, y0, x1, y1]

    # Positive verifier approved parameters
    tolerance_px = 2
    darkness_threshold = 220 # pixels <= 220 are dark

    def measure_metrics(img_arr, start, end, roi_bbox):
        x0, y0, x1, y1 = roi_bbox
        # ROI check
        xs = np.rint(np.linspace(start[0], end[0], max(abs(end[0] - start[0]), abs(end[1] - start[1])) + 1)).astype(np.int32)
        ys = np.rint(np.linspace(start[1], end[1], max(abs(end[0] - start[0]), abs(end[1] - start[1])) + 1)).astype(np.int32)
        
        in_roi = not (np.any(xs < x0) or np.any(xs > x1) or np.any(ys < y0) or np.any(ys > y1))
        
        # Binary mask of dark pixels in ROI
        dark = np.zeros_like(img_arr, dtype=np.uint8)
        roi_pixels = img_arr[y0 : y1 + 1, x0 : x1 + 1]
        dark[y0 : y1 + 1, x0 : x1 + 1] = np.where(roi_pixels <= darkness_threshold, 255, 0).astype(np.uint8)
        
        # MaxFilter with size = 2 * tolerance + 1 = 5
        dilated_dark = np.asarray(Image.fromarray(dark).filter(ImageFilter.MaxFilter(size=5)), dtype=np.uint8)
        
        # Positive ink metric: fraction of samples seeing dark ink within 2px
        # Clip indices to valid range for safety if outside
        valid_idx = (xs >= 0) & (xs < img_arr.shape[1]) & (ys >= 0) & (ys < img_arr.shape[0])
        if not np.all(valid_idx):
            return 0.0, 0.0, False, "CLIPPED"
            
        positive_ink_fraction = float(np.mean(dilated_dark[ys, xs] > 0))
        
        # Undilated corridor mean intensity along the exact centerline samples
        centerline_intensities = img_arr[ys, xs]
        # Negative support metric: fraction of centerline samples that are strictly clean background (> 220)
        clean_background_fraction = float(np.mean(centerline_intensities > darkness_threshold))
        mean_intensity = float(np.mean(centerline_intensities))
        min_intensity = int(np.min(centerline_intensities))

        return positive_ink_fraction, clean_background_fraction, in_roi, mean_intensity, min_intensity

    cases = []

    # PAIR A: Genuine deletion (source corridor genuinely empty, pure white background 255)
    img_A = Image.new("L", (width, height), 255)
    cases.append(("PAIR A — Genuine deletion", img_A, "NONE", "CONFIRMED_ABSENT", roi))

    # PAIR B: Faint unchanged line (intensity = 230, so > darkness_threshold 220, but visibly gray line)
    img_B = Image.new("L", (width, height), 255)
    draw_B = ImageDraw.Draw(img_B)
    draw_B.line((20, 50, 80, 50), fill=230, width=1) # Faint gray line
    cases.append(("PAIR B — Faint unchanged line", img_B, "NONE", "UNRESOLVED (RETAIN)", roi))

    # PAIR C: Partially occluded unchanged line (left 30px occluded by smudge/artifact, right 30px intact)
    img_C = Image.new("L", (width, height), 255)
    draw_C = ImageDraw.Draw(img_C)
    draw_C.line((50, 50, 80, 50), fill=0, width=1) # Only half line visible
    cases.append(("PAIR C — Partially occluded line", img_C, "OCCLUSION", "UNRESOLVED (RETAIN)", roi))

    # PAIR D: Dashed / centerline (5px on, 5px off; dark=0, gap=255)
    img_D = Image.new("L", (width, height), 255)
    draw_D = ImageDraw.Draw(img_D)
    for x in range(20, 80, 10):
        draw_D.line((x, 50, x + 5, 50), fill=0, width=1)
    cases.append(("PAIR D — Dashed / center line", img_D, "NONE", "UNRESOLVED (RETAIN)", roi))

    # PAIR E: Crop clips part of line (ROI is x0=40, clipping line from 20 to 40)
    img_E = Image.new("L", (width, height), 255)
    draw_E = ImageDraw.Draw(img_E)
    draw_E.line((20, 50, 80, 50), fill=0, width=1)
    roi_clipped = (40, 10, 110, 90) # ROI clips start of line
    cases.append(("PAIR E — Crop clips part of line", img_E, "CLIPPED_BY_ROI", "UNRESOLVED (RETAIN)", roi_clipped))

    # PAIR F: Text crosses line (text block at x in [45, 55], y in [40, 60])
    img_F = Image.new("L", (width, height), 255)
    draw_F = ImageDraw.Draw(img_F)
    draw_F.line((20, 50, 80, 50), fill=0, width=1)
    draw_F.rectangle((45, 40, 55, 60), fill=0) # Text character mask
    cases.append(("PAIR F — Text crosses line", img_F, "TEXT_OCCLUSION", "UNRESOLVED (RETAIN)", roi))

    # PAIR G: Neighboring parallel line (line at y=52, 2px away from y=50!)
    img_G = Image.new("L", (width, height), 255)
    draw_G = ImageDraw.Draw(img_G)
    draw_G.line((20, 52, 80, 52), fill=0, width=1) # Parallel line at y=52
    cases.append(("PAIR G — Nearby parallel line (2px away)", img_G, "CONTAMINATION", "UNRESOLVED (RETAIN)", roi))

    # PAIR H: Source line shifted (moved from y=50 to y=55; represents CHANGE, not REMOVE)
    img_H = Image.new("L", (width, height), 255)
    draw_H = ImageDraw.Draw(img_H)
    draw_H.line((20, 55, 80, 55), fill=0, width=1) # Shifted line at y=55
    cases.append(("PAIR H — Shifted line (CHANGE not REMOVE)", img_H, "NONE", "CHANGE_OR_UNRESOLVED", roi))

    header = f"{'Case':<38} | {'Pos Ink Frac':<12} | {'Clean Bg Frac':<13} | {'Mean Int':<8} | {'ROI Status':<14} | {'Expected':<22} | {'Naive <0.15 Inversion':<22}"
    print(header)
    print("-" * len(header))

    for name, img, occlusion, expected, r_box in cases:
        arr = np.array(img)
        pos_ink, clean_bg, in_roi, mean_int, min_int = measure_metrics(arr, start_px, end_px, r_box)
        
        # Test naive inversion: "support_fraction < 0.15 implies REMOVE"
        naive_remove = (pos_ink < 0.15 and in_roi)

        naive_verdict = "FALSE REMOVE (!!)" if naive_remove and expected != "CONFIRMED_ABSENT" else ("CONFIRMED_ABSENT" if naive_remove else "RETAIN")

        print(f"{name:<38} | {pos_ink:<12.3f} | {clean_bg:<13.3f} | {mean_int:<8.1f} | {str(in_roi):<14} | {expected:<22} | {naive_verdict:<22}")

if __name__ == "__main__":
    create_raster_pair_benchmark()
