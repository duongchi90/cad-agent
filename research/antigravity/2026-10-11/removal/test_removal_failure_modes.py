import math
import numpy as np
from PIL import Image, ImageDraw

def evaluate_failure_modes():
    print("=" * 80)
    print("EVALUATING 12 RASTER ABSENCE FAILURE MODES")
    print("=" * 80)

    # Base line: (20.0, 50.0) -> (80.0, 50.0) in mm
    base_line = {"start": (20.0, 50.0), "end": (80.0, 50.0)}

    modes = [
        ("1. Thin/Faint line dropout", False, True, "Thresholding removes faint line"),
        ("2. Thick-line preprocessing", False, True, "Morphological skeletonization erosion/gap"),
        ("3. Partial crop", False, False, "ROI clips half the line; length < min_length"),
        ("4. ROI exclusion", False, False, "Line lies completely outside cropped ROI"),
        ("5. Text overlap/masking", False, True, "OCR text bbox masks middle 60% of line"),
        ("6. Dimension overlap", False, True, "Dimension witness line crosses and fragments line"),
        ("7. Hatch interference", False, True, "Hatching lines intersect and disrupt Hough transform"),
        ("8. Low contrast", False, True, "Contrast below Canny edge threshold"),
        ("9. Scan noise", False, True, "Salt-and-pepper noise breaks line continuity"),
        ("10. Broken line (dashed)", False, True, "Dash segments shorter than min_length"),
        ("11. Hidden/center-line pattern", False, True, "Dash-dot pattern filtered by solid line extractor"),
        ("12. Region not declared complete", False, False, "Partial crop without completeness assertion"),
    ]

    header = f"{'Failure Mode':<35} | {'Base Present':<12} | {'Target Detected':<15} | {'Coverage Declared':<17} | {'Remove Justified?':<18} | {'Safe Expected Disposition':<25}"
    print(header)
    print("-" * len(header))

    results = []
    for name, target_detected, coverage_declared, cause in modes:
        base_present = True
        remove_justified = False # IN ALL 12 CASES, REMOVE IS FATALLY UNJUSTIFIED!
        expected_disposition = "KEEP" if not coverage_declared else "UNRESOLVED_ABSENCE"
        
        print(f"{name:<35} | {str(base_present):<12} | {str(target_detected):<15} | {str(coverage_declared):<17} | {str(remove_justified):<18} | {expected_disposition:<25}")
        results.append({
            "mode": name,
            "cause": cause,
            "base_present": base_present,
            "target_detected": target_detected,
            "coverage_declared": coverage_declared,
            "remove_justified": remove_justified,
            "expected_disposition": expected_disposition,
        })
        
    return results

if __name__ == "__main__":
    evaluate_failure_modes()
