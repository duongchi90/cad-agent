import math
import numpy as np
from dataclasses import dataclass
from typing import Sequence

# -----------------------------------------------------------------------------
# Core Numerical SVD Similarity Fitting (matches primitive_ir_lib.geometry_alignment)
# -----------------------------------------------------------------------------

def fit_similarity_unconstrained(cad_pts: np.ndarray, ref_pts: np.ndarray):
    """Fits 2D similarity transform without angle restrictions."""
    N = len(cad_pts)
    source_centroid = cad_pts.mean(axis=0)
    target_centroid = ref_pts.mean(axis=0)
    source_centered = cad_pts - source_centroid
    target_centered = ref_pts - target_centroid

    if N == 2:
        source_delta = source_centered[1] - source_centered[0]
        target_delta = target_centered[1] - target_centered[0]
        source_length = float(np.linalg.norm(source_delta))
        target_length = float(np.linalg.norm(target_delta))
        if source_length <= 1e-12 or target_length <= 1e-12:
            return None
        uniform_scale = target_length / source_length
        cosine = float(np.dot(source_delta, target_delta) / (source_length * target_length))
        sine = float((source_delta[0] * target_delta[1] - source_delta[1] * target_delta[0]) / (source_length * target_length))
        linear = uniform_scale * np.asarray([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    else:
        covariance = source_centered.T @ target_centered
        left, singular_values, right_transposed = np.linalg.svd(covariance)
        row_rotation = left @ right_transposed
        det = float(np.linalg.det(row_rotation))
        if det < 0.0:
            # Reflection is forbidden
            return None
        source_energy = float(np.sum(source_centered * source_centered))
        if source_energy <= 1e-12:
            return None
        uniform_scale = float(np.sum(singular_values) / source_energy)
        linear = uniform_scale * row_rotation.T

    translation = target_centroid - linear @ source_centroid
    projected = cad_pts @ linear.T + translation
    residuals = np.linalg.norm(projected - ref_pts, axis=1)
    residual_rms = float(np.sqrt(np.mean(residuals * residuals)))
    rotation_deg = math.degrees(math.atan2(float(linear[1, 0]), float(linear[0, 0])))
    
    return {
        "scale": uniform_scale,
        "rotation_deg": rotation_deg,
        "translation": (float(translation[0]), float(translation[1])),
        "residual_rms": residual_rms,
        "linear": linear,
    }

# -----------------------------------------------------------------------------
# Policy Evaluators
# -----------------------------------------------------------------------------

def evaluate_policy_a(rot_deg: float) -> bool:
    """POLICY_A: abs(theta) <= 5.0 deg"""
    return abs(rot_deg) <= 5.0

def evaluate_policy_b(rot_deg: float) -> bool:
    """POLICY_B: abs(theta) <= 180.0 deg (arbitrary planar rotation)"""
    return abs(rot_deg) <= 180.0

def evaluate_policy_c(rot_deg: float, skew_tolerance: float = 5.0) -> bool:
    """POLICY_C: nearest cardinal {0, 90, -90, 180} +/- skew_tolerance"""
    cardinals = [0.0, 90.0, -90.0, 180.0, -180.0]
    min_dist = min(abs(rot_deg - c) for c in cardinals)
    return min_dist <= skew_tolerance

def evaluate_policy_d(rot_deg: float, expected_envelope: tuple[list[float], float]) -> bool:
    """POLICY_D: caller declares allowed orientations and tolerance"""
    allowed_centers, tol = expected_envelope
    min_dist = min(abs(rot_deg - c) for c in allowed_centers)
    return min_dist <= tol

# -----------------------------------------------------------------------------
# Experiment 1: Positive Fixtures (Section 4)
# -----------------------------------------------------------------------------
def run_positive_fixtures():
    print("=" * 80)
    print("EXPERIMENT 1: POSITIVE FIXTURES (SECTION 4)")
    print("=" * 80)
    
    # 3 Non-collinear anchors in target mm
    # A1=(0, 0), A2=(100, 0), A3=(0, 80)
    target_pts = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 80.0]])
    test_angles = [0.0, 1.0, 5.0, 15.0, 30.0, 45.0, 89.0, 90.0, 91.0, 135.0, 179.0, 180.0, -90.0]
    
    # Policy D envelope configurations:
    # Env 1: Default upright sheet (0 +/- 5)
    # Env 2: Cardinal allowed [0, 90, -90, 180] +/- 5
    # Env 3: Explicit rotated sheet matching angle +/- 5
    
    header = f"{'True theta':>10} | {'Pol A (<=5deg)':>14} | {'Pol B (<=180deg)':>16} | {'Pol C (Card+-5)':>15} | {'Pol D (Env)':>14} | {'Scale Err':>10} | {'RMS Err':>10}"
    print(header)
    print("-" * len(header))
    
    for theta_deg in test_angles:
        rad = math.radians(theta_deg)
        R = np.array([[math.cos(rad), -math.sin(rad)], [math.sin(rad), math.cos(rad)]])
        t = np.array([250.0, 175.0])
        base_pts = (R @ target_pts.T).T + t
        
        fit = fit_similarity_unconstrained(target_pts, base_pts)
        assert fit is not None
        
        rot = fit["rotation_deg"]
        s = fit["scale"]
        rms = fit["residual_rms"]
        scale_err = abs(s - 1.0)
        
        pass_a = evaluate_policy_a(rot)
        pass_b = evaluate_policy_b(rot)
        pass_c = evaluate_policy_c(rot, 5.0)
        
        # Policy D with caller declaring expected orientation:
        pass_d = evaluate_policy_d(rot, ([theta_deg], 5.0))
        
        print(f"{theta_deg:>7.1f} deg | {str(pass_a):>14} | {str(pass_b):>16} | {str(pass_c):>15} | {str(pass_d):>14} | {scale_err:>10.2e} | {rms:>10.2e}")

# -----------------------------------------------------------------------------
# Experiment 2: Wrong-Anchor Safety Matrix (Section 5)
# -----------------------------------------------------------------------------
def run_wrong_anchor_matrix():
    print("\n" + "=" * 80)
    print("EXPERIMENT 2: WRONG-ANCHOR SAFETY MATRIX (SECTION 5)")
    print("=" * 80)
    
    scenarios = []
    
    # A. Repeated parallel lines:
    # 3 lines at y = 0, y = 20, y = 40.
    # Anchors on line 1: (0, 0), (100, 0); on line 2: (0, 20), (100, 20); on line 3: (0, 40), (100, 40)
    # Mispairing line 1 to line 2 (pure translation shift dy = +20)
    pts_cad_A = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 40.0], [100.0, 40.0]])
    pts_ref_A = pts_cad_A + np.array([0.0, 20.0]) # dy shift
    scenarios.append(("A. Repeated Parallel Lines (dy shift)", pts_cad_A, pts_ref_A, "Translation shift"))
    
    # B1. Square symmetry (4-fold, 90 deg rotation):
    # Corners: (0,0), (100,0), (100,100), (0,100)
    # Target is upright (0 deg). Mispairing permutes corners by 90 deg:
    # cad: [0, 1, 2, 3] -> ref: [1, 2, 3, 0]
    sq_corners = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    sq_perm_90 = np.array([[100.0, 0.0], [100.0, 100.0], [0.0, 100.0], [0.0, 0.0]])
    scenarios.append(("B1. Square Symmetry (90 deg corner permutation)", sq_corners, sq_perm_90, "Rotated 90 deg"))
    
    # B2. Rectangle symmetry (2-fold, 180 deg rotation):
    # Corners: (0,0), (200,0), (200,100), (0,100)
    # Permuting by 180 deg: [0,1,2,3] -> [2,3,0,1]
    rect_corners = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]])
    rect_perm_180 = np.array([[200.0, 100.0], [0.0, 100.0], [0.0, 0.0], [200.0, 0.0]])
    scenarios.append(("B2. Rectangle Symmetry (180 deg corner permutation)", rect_corners, rect_perm_180, "Rotated 180 deg"))

    # C. Repeated hole pattern (8-hole bolt circle, 45 deg step):
    # Radius = 100 mm. Holes at 0 deg, 45 deg, 90 deg, 135 deg.
    # Mispairing by 1 hole step (45 deg):
    angles = np.array([0.0, 45.0, 90.0, 135.0])
    holes_cad = np.column_stack([100.0 * np.cos(np.radians(angles)), 100.0 * np.sin(np.radians(angles))])
    holes_ref = np.column_stack([100.0 * np.cos(np.radians(angles + 45.0)), 100.0 * np.sin(np.radians(angles + 45.0))])
    scenarios.append(("C. Circular Bolt Pattern (45 deg mispairing)", holes_cad, holes_ref, "Rotated 45 deg"))
    
    # D. Two identical features (e.g. 2 mounting bosses at (-50, 0) and (+50, 0)):
    # With a 3rd datum anchor that is swapped or 2 anchors swapped (180 deg flip)
    bosses_cad = np.array([[-50.0, 0.0], [50.0, 0.0], [0.0, 80.0]])
    # Swapping the two bosses but keeping 3rd point gives large residual:
    bosses_ref = np.array([[50.0, 0.0], [-50.0, 0.0], [0.0, 80.0]])
    scenarios.append(("D. Two Identical Bosses Swapped (3rd anchor fixed)", bosses_cad, bosses_ref, "Inconsistent"))

    # E. Mirrored-looking but non-reflected layout (asymmetric notch):
    # (0,0), (100,0), (100, 50), (20, 50)
    # Mirrored ref would have negative det, but rotating 180 deg gives best positive-det fit:
    pts_cad_E = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 50.0], [20.0, 50.0]])
    # 180 deg rotated:
    pts_ref_E = -pts_cad_E + np.array([100.0, 50.0])
    scenarios.append(("E. 180 deg Inverted Layout Match", pts_cad_E, pts_ref_E, "Rotated 180 deg"))

    # F. Rotated repeated subassemblies (60 deg triangular/hexagonal pitch):
    # Feature triad at 0, 60, 120 mispaired to 60, 120, 180:
    tri_cad = np.array([[0.0, 0.0], [100.0, 0.0], [50.0, 86.60254]])
    rad60 = math.radians(60.0)
    R60 = np.array([[math.cos(rad60), -math.sin(rad60)], [math.sin(rad60), math.cos(rad60)]])
    tri_ref = (R60 @ tri_cad.T).T
    scenarios.append(("F. Rotated Subassembly (60 deg pitch mispair)", tri_cad, tri_ref, "Rotated 60 deg"))

    # G. One wrong high-authority anchor (outlier):
    # 3 DATUM anchors: (0,0), (100,0), (0,100).
    # Anchor 3 is shifted by 15 mm in x (wrong correspondence):
    pts_cad_G = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 100.0]])
    pts_ref_G = np.array([[0.0, 0.0], [100.0, 0.0], [15.0, 100.0]])
    scenarios.append(("G. 1 Outlier Anchor (15mm shift in 1/3 anchors)", pts_cad_G, pts_ref_G, "Outlier pull"))

    for name, cad, ref, desc in scenarios:
        fit = fit_similarity_unconstrained(cad, ref)
        print(f"\n--- {name} ---")
        if fit is None:
            print("  Fit: REJECTED by SVD / reflection check")
            continue
        rot = fit["rotation_deg"]
        s = fit["scale"]
        rms = fit["residual_rms"]
        print(f"  Fitted theta: {rot:.2f} deg, Scale: {s:.4f}, RMS: {rms:.4f} mm")
        
        pass_a = evaluate_policy_a(rot)
        pass_b = evaluate_policy_b(rot)
        pass_c = evaluate_policy_c(rot, 5.0)
        # Policy D assuming caller expected upright sheet (0 +/- 5 deg)
        pass_d_upright = evaluate_policy_d(rot, ([0.0], 5.0))
        # Policy D if caller declared cardinal [0, 90, -90, 180]
        pass_d_cardinal = evaluate_policy_d(rot, ([0.0, 90.0, -90.0, 180.0, -180.0], 5.0))
        
        print(f"  Policy A (<=5deg):      {'ACCEPTED (FALSE PASS!)' if pass_a and rms < 3.0 and abs(s-1.0)<1e-4 else 'REJECTED (SAFE)'}")
        print(f"  Policy B (<=180deg):    {'ACCEPTED (FALSE PASS!)' if pass_b and rms < 3.0 and abs(s-1.0)<1e-4 else 'REJECTED (SAFE)'}")
        print(f"  Policy C (Card+-5):     {'ACCEPTED (FALSE PASS!)' if pass_c and rms < 3.0 and abs(s-1.0)<1e-4 else 'REJECTED (SAFE)'}")
        print(f"  Policy D (Exp=0+-5):    {'ACCEPTED (FALSE PASS!)' if pass_d_upright and rms < 3.0 and abs(s-1.0)<1e-4 else 'REJECTED (SAFE)'}")
        print(f"  Policy D (Card+-5):     {'ACCEPTED (FALSE PASS!)' if pass_d_cardinal and rms < 3.0 and abs(s-1.0)<1e-4 else 'REJECTED (SAFE)'}")

# -----------------------------------------------------------------------------
# Experiment 3: Cardinal-Plus-Skew Tests (Section 6)
# -----------------------------------------------------------------------------
def run_cardinal_skew_tests():
    print("\n" + "=" * 80)
    print("EXPERIMENT 3: CARDINAL-PLUS-SKEW HYPOTHESIS (SECTION 6)")
    print("=" * 80)
    
    target_pts = np.array([[0.0, 0.0], [100.0, 0.0], [0.0, 80.0]])
    cases = [
        ("Case 1: 90 deg sheet rotation + 2 deg scan skew (92 deg)", 92.0),
        ("Case 2: 180 deg sheet rotation - 3 deg scan skew (177 deg)", 177.0),
        ("Case 3: 0 deg sheet rotation + 4 deg scan skew (4 deg)", 4.0),
        ("Case 4: 45 deg legitimate local detail (45 deg)", 45.0),
    ]
    
    for name, theta in cases:
        rad = math.radians(theta)
        R = np.array([[math.cos(rad), -math.sin(rad)], [math.sin(rad), math.cos(rad)]])
        base_pts = (R @ target_pts.T).T
        fit = fit_similarity_unconstrained(target_pts, base_pts)
        assert fit is not None
        rot = fit["rotation_deg"]
        
        pass_a = evaluate_policy_a(rot)
        pass_b = evaluate_policy_b(rot)
        pass_c = evaluate_policy_c(rot, 5.0)
        pass_d_cardinal = evaluate_policy_d(rot, ([0.0, 90.0, -90.0, 180.0, -180.0], 5.0))
        pass_d_explicit = evaluate_policy_d(rot, ([theta], 5.0))
        
        print(f"--- {name} ---")
        print(f"  Fitted theta: {rot:.2f} deg")
        print(f"  Policy A (<=5deg):   {pass_a}")
        print(f"  Policy B (<=180deg): {pass_b}")
        print(f"  Policy C (Card+-5):  {pass_c}")
        print(f"  Policy D (Card+-5):  {pass_d_cardinal}")
        print(f"  Policy D (Exact+-5): {pass_d_explicit}")

if __name__ == "__main__":
    run_positive_fixtures()
    run_wrong_anchor_matrix()
    run_cardinal_skew_tests()
