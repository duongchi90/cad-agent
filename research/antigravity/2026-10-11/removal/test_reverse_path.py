import math
import numpy as np

def test_reverse_coordinate_path():
    print("=" * 80)
    print("TESTING REVERSE COORDINATE PATH & ROUND-TRIP PRECISION")
    print("=" * 80)

    # Calibration parameters: scale = 0.0917 mm/px, origin_px = (0.0, 1000.0)
    scale = 0.0917
    ox, oy = 0.0, 1000.0

    def pixel_to_cad(px_x, px_y):
        cad_x = (px_x - ox) * scale
        cad_y = (oy - px_y) * scale
        return cad_x, cad_y

    def cad_to_pixel(cad_x, cad_y):
        px_x = cad_x / scale + ox
        px_y = oy - cad_y / scale
        return px_x, px_y

    def forward_transform(target_x, target_y, matrix):
        wcs_x = matrix[0][0] * target_x + matrix[0][1] * target_y + matrix[0][2]
        wcs_y = matrix[1][0] * target_x + matrix[1][1] * target_y + matrix[1][2]
        return wcs_x, wcs_y

    def inverse_transform(wcs_x, wcs_y, matrix):
        # M is 2x3: [R | t]. R is pure 2D rotation matrix (orthogonal, det=1).
        r00, r01, tx = matrix[0][0], matrix[0][1], matrix[0][2]
        r10, r11, ty = matrix[1][0], matrix[1][1], matrix[1][2]
        dx = wcs_x - tx
        dy = wcs_y - ty
        # R^T * d:
        target_x = r00 * dx + r10 * dy
        target_y = r01 * dx + r11 * dy
        return target_x, target_y

    # Test cases: (name, initial_px, theta_deg, translation)
    test_cases = [
        ("Case 1: 0° alignment, translation (500, 400)", (250.0, 350.0), 0.0, (500.0, 400.0)),
        ("Case 2: 90° CCW rotation + translation", (150.25, 780.75), 90.0, (1200.0, -350.0)),
        ("Case 3: 180° rotation + translation", (600.5, 450.5), 180.0, (-800.0, 600.0)),
        ("Case 4: Negative coordinates in WCS", (50.123, 950.456), 45.0, (-2000.0, -1500.0)),
        ("Case 5: Non-integer subpixel float", (123.456789, 876.54321), 27.5, (333.333, 777.777)),
        ("Case 6: Endpoint near ROI boundary (0, 0)", (0.001, 999.999), 90.0, (100.0, 100.0)),
    ]

    header = f"{'Scenario':<42} | {'Original Px':<20} | {'WCS (mm)':<26} | {'Recovered Px':<20} | {'Error (px)':<12}"
    print(header)
    print("-" * len(header))

    max_err = 0.0
    for name, (px_x, px_y), theta_deg, (tx, ty) in test_cases:
        rad = math.radians(theta_deg)
        c, s = math.cos(rad), math.sin(rad)
        matrix = [[c, -s, tx], [s, c, ty]]

        # 1. px -> target mm
        t_x, t_y = pixel_to_cad(px_x, px_y)

        # 2. target mm -> base WCS mm
        wcs_x, wcs_y = forward_transform(t_x, t_y, matrix)

        # 3. base WCS mm -> target mm (inverse)
        rec_tx, rec_ty = inverse_transform(wcs_x, wcs_y, matrix)

        # 4. target mm -> source px (inverse)
        rec_px, rec_py = cad_to_pixel(rec_tx, rec_ty)

        err = math.hypot(rec_px - px_x, rec_py - px_y)
        max_err = max(max_err, err)

        orig_str = f"({px_x:.3f}, {px_y:.3f})"
        wcs_str = f"({wcs_x:.2f}, {wcs_y:.2f})"
        rec_str = f"({rec_px:.3f}, {rec_py:.3f})"
        print(f"{name:<42} | {orig_str:<20} | {wcs_str:<26} | {rec_str:<20} | {err:<12.2e}")

    print(f"\nROUNDTRIP_MAX_ERROR_PX: {max_err:.2e} px (Machine precision ~ 10^-14)")

if __name__ == "__main__":
    test_reverse_coordinate_path()
