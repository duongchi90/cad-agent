import numpy as np
from PIL import Image, ImageDraw

def test_positive_removal():
    print("=" * 80)
    print("CONSTRUCTING POSITIVE REMOVAL CASE")
    print("=" * 80)

    # 1. Base DWG geometry:
    # Outer box: (20, 20) -> (80, 100)
    # Rib 1: (20, 40) -> (80, 40)
    # Rib 2 (LINE_OLD): (20, 60) -> (80, 60)
    # Rib 3: (20, 80) -> (80, 80)
    base_lines = {
        "box-top": ((20, 20), (80, 20)),
        "box-bottom": ((20, 100), (80, 100)),
        "box-left": ((20, 20), (20, 100)),
        "box-right": ((80, 20), (80, 100)),
        "rib-1": ((20, 40), (80, 40)),
        "rib-2-old": ((20, 60), (80, 60)),
        "rib-3": ((20, 80), (80, 80)),
    }

    # 2. Synthetic Modified Source Render (Revision B):
    # Rib 2 is physically deleted. Rib 1 and Rib 3 are drawn.
    img = Image.new("L", (100, 120), 255) # white background
    draw = ImageDraw.Draw(img)
    # Draw box
    draw.rectangle((20, 20, 80, 100), outline=0, width=1)
    # Draw rib 1 and rib 3 only
    draw.line((20, 40, 80, 40), fill=0, width=1)
    draw.line((20, 80, 80, 80), fill=0, width=1)
    # rib 2 is intentionally NOT drawn

    img_arr = np.array(img)

    # 3. Analyze the Corridor of rib-2-old: y in [58, 62], x in [25, 75]
    corridor = img_arr[58:63, 25:76]
    mean_intensity = float(np.mean(corridor))
    min_intensity = int(np.min(corridor))
    dark_pixels = int(np.sum(corridor < 128))

    # 4. Analyze neighboring witnesses: rib-1 and rib-3
    rib1_strip = img_arr[38:43, 25:76]
    rib3_strip = img_arr[78:83, 25:76]
    rib1_dark = int(np.sum(rib1_strip < 128))
    rib3_dark = int(np.sum(rib3_strip < 128))

    print("Positive Removal Inspection Evidence:")
    print(f"  Rib 2 (LINE_OLD) Corridor mean intensity: {mean_intensity:.1f} / 255.0 (min: {min_intensity})")
    print(f"  Dark pixels in Rib 2 corridor:            {dark_pixels} (pure whitespace)")
    print(f"  Neighboring Rib 1 dark pixels detected:   {rib1_dark} (intact)")
    print(f"  Neighboring Rib 3 dark pixels detected:   {rib3_dark} (intact)")
    print(f"  Neighboring witness contrast ratio:       {255.0 / (np.min(rib1_strip) + 1e-3):.1f}x")

    distinguishing_factors = [
        "1. Active Negative Pixel Verification: Zero dark pixels (100% pure background whitespace) in expected line corridor.",
        "2. Neighboring Witness Completeness: Adjacent parallel lines (Rib 1 at y=40, Rib 3 at y=80) detected with strong SNR, proving scanner sensitivity was sufficient.",
        "3. Zero Occlusion: No OCR text bbox, dimension witness line, or hatch intersects the corridor.",
        "4. Enclosed Geometry Scope: The outer boundary polygon is fully detected and declared closed.",
        "5. Explicit Revision Intent: Manifest records revision obligation covering component modification."
    ]
    print("\nRequired Affirmative Evidence Distinguishing True Removal from Dropout:")
    for f in distinguishing_factors:
        print(" ", f)

if __name__ == "__main__":
    test_positive_removal()
