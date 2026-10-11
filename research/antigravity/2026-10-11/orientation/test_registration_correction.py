import math
import numpy as np

# -----------------------------------------------------------------------------
# Part 1: Double-Scale Corruption vs Option A Physical Invariant
# -----------------------------------------------------------------------------
def test_double_scale_semantics():
    # Ground truth part dimension
    L_true_mm = 100.0  # e.g., 100 mm bolt pitch
    
    # Layer A: Pixel to Physical Calibration
    # Sheet scanned at 254 DPI -> 0.1 mm/px
    scale_px_to_mm = 0.1
    L_px = L_true_mm / scale_px_to_mm  # 1000 px
    
    # Primitive IR assemble() applies calibration:
    L_target_calibrated_mm = L_px * scale_px_to_mm  # 100.0 mm
    
    # Base DWG native line:
    L_base_mm = 100.0
    
    # Option A: Layer B Target-to-Base Alignment enforces scale approx 1.0
    s_align_optA = 1.0
    L_wcs_optA = L_target_calibrated_mm * s_align_optA
    err_optA = abs(L_wcs_optA - L_base_mm)
    
    # Flawed Contract: Arbitrary scale in Layer B (e.g. s = 2.0)
    s_align_flawed = 2.0
    L_wcs_flawed = L_target_calibrated_mm * s_align_flawed
    err_flawed = abs(L_wcs_flawed - L_base_mm)
    
    print("=== PART 1: PHYSICAL SCALE INVARIANT & DOUBLE-SCALE RISK ===")
    print(f"Ground truth dimension:        {L_true_mm:.4f} mm")
    print(f"Layer A calibrated target:     {L_target_calibrated_mm:.4f} mm")
    print(f"Option A WCS result (s=1.0):   {L_wcs_optA:.4f} mm (Error: {err_optA:.4f} mm)")
    print(f"Flawed WCS result (s=2.0):     {L_wcs_flawed:.4f} mm (Error: {err_flawed:.4f} mm)")
    print(f"Corruption factor:             {L_wcs_flawed / L_true_mm:.2f}x\n")

# -----------------------------------------------------------------------------
# Part 2: Collinear Anchor Numerical Evaluation (Cases A - E)
# -----------------------------------------------------------------------------
def rank_check(points: np.ndarray) -> int:
    centered = points - points.mean(axis=0)
    return int(np.linalg.matrix_rank(centered, tol=1e-10))

def solve_2pt(cad: np.ndarray, ref: np.ndarray):
    # Same as geometry_alignment.py for N=2
    source_centroid = cad.mean(axis=0)
    target_centroid = ref.mean(axis=0)
    source_centered = cad - source_centroid
    target_centered = ref - target_centroid
    
    source_delta = source_centered[1] - source_centered[0]
    target_delta = target_centered[1] - target_centered[0]
    source_length = float(np.linalg.norm(source_delta))
    target_length = float(np.linalg.norm(target_delta))
    if source_length <= 1e-12 or target_length <= 1e-12:
        return None, "coincident"
    uniform_scale = target_length / source_length
    cosine = float(np.dot(source_delta, target_delta) / (source_length * target_length))
    sine = float(
        (source_delta[0] * target_delta[1] - source_delta[1] * target_delta[0])
        / (source_length * target_length)
    )
    linear = uniform_scale * np.asarray([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    translation = target_centroid - linear @ source_centroid
    return linear, translation

def solve_svd(cad: np.ndarray, ref: np.ndarray):
    source_centroid = cad.mean(axis=0)
    target_centroid = ref.mean(axis=0)
    source_centered = cad - source_centroid
    target_centered = ref - target_centroid
    
    covariance = source_centered.T @ target_centered
    left, singular_values, right_transposed = np.linalg.svd(covariance)
    row_rotation = left @ right_transposed
    det = float(np.linalg.det(row_rotation))
    source_energy = float(np.sum(source_centered * source_centered))
    if source_energy <= 1e-12:
        return None, "no_energy"
    uniform_scale = float(np.sum(singular_values) / source_energy)
    linear = uniform_scale * row_rotation.T
    translation = target_centroid - linear @ source_centroid
    return linear, translation, det

def evaluate_collinear():
    print("=== PART 2: COLLINEAR ANCHOR BEHAVIORAL MATRIX ===")
    # Base line: along y = 2x + 10 in target space
    # Let's define a rigid transform to WCS: Rot = 30 deg, Trans = (100, 200), Scale = 1.0
    theta = math.radians(30.0)
    R_gt = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    t_gt = np.array([100.0, 200.0])
    
    # Points along line y = 0.5 * x:
    # x = 10, 20, 30, 40, 50
    x_coords = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    cad_pts_all = np.column_stack([x_coords, 0.5 * x_coords])
    
    # Ground truth WCS reference points
    ref_pts_all = (R_gt @ cad_pts_all.T).T + t_gt
    
    cases = [
        ("Case A: N=2 distinct collinear points", cad_pts_all[:2], ref_pts_all[:2]),
        ("Case B: N=3 collinear points (perfect)", cad_pts_all[:3], ref_pts_all[:3]),
        ("Case C: N=5 collinear points (perfect)", cad_pts_all, ref_pts_all),
        ("Case D: N=5 collinear with transverse jitter (0.5px)", 
         cad_pts_all + np.array([[0, 0.5], [0, -0.4], [0, 0.3], [0, -0.5], [0, 0.2]]),
         ref_pts_all),
        ("Case E: N=5 collinear with 1 gross outlier",
         cad_pts_all,
         np.vstack([ref_pts_all[:4], ref_pts_all[4] + np.array([50.0, -80.0])]))
    ]
    
    for name, cad, ref in cases:
        N = len(cad)
        rk_cad = rank_check(cad)
        rk_ref = rank_check(ref)
        policy_fail_closed = (N >= 3 and (rk_cad < 2 or rk_ref < 2))
        
        # Test 2-point solve
        res_2pt = solve_2pt(cad[:2], ref[:2])
        if res_2pt[0] is not None:
            lin_2pt, tr_2pt = res_2pt
            s_2pt = math.hypot(lin_2pt[0, 0], lin_2pt[1, 0])
            rot_2pt = math.degrees(math.atan2(lin_2pt[1, 0], lin_2pt[0, 0]))
            err_2pt = np.max(np.linalg.norm((lin_2pt @ cad[:2].T).T + tr_2pt - ref[:2], axis=1))
        else:
            s_2pt, rot_2pt, err_2pt = None, None, None
            
        # Test SVD solve
        res_svd = solve_svd(cad, ref)
        if res_svd[0] is not None:
            lin_svd, tr_svd, det_svd = res_svd
            s_svd = math.hypot(lin_svd[0, 0], lin_svd[1, 0])
            rot_svd = math.degrees(math.atan2(lin_svd[1, 0], lin_svd[0, 0]))
            err_svd = np.max(np.linalg.norm((lin_svd @ cad.T).T + tr_svd - ref, axis=1))
        else:
            s_svd, rot_svd, det_svd, err_svd = None, None, None, None
            
        print(f"--- {name} ---")
        print(f"  N: {N}, Rank(cad): {rk_cad}, Rank(ref): {rk_ref}")
        print(f"  Current Policy Guard (N>=3 & rank<2): {'REJECTED (FAIL-CLOSED)' if policy_fail_closed else 'ACCEPTED'}")
        print(f"  2-Point solver: s={s_2pt:.4f}, rot={rot_2pt:.2f}°, max_res={err_2pt:.4f}")
        if s_svd is not None:
            print(f"  SVD solver:     s={s_svd:.4f}, rot={rot_svd:.2f}°, det={det_svd:.2f}, max_res={err_svd:.4f}")
        print()

if __name__ == "__main__":
    test_double_scale_semantics()
    evaluate_collinear()
