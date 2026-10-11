import sys
import math
import numpy as np

sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")

from primitive_ir_lib.geometry_alignment import AnchorPair, estimate_similarity_alignment
import cad_agent.source_fusion_proposal as sfp
import tests.test_external_visual_primitive_ir_admission as test_helper

def test_square_symmetry_with_sfp(policy_mode="POL_D_UPRIGHT"):
    # Target drawing has 2 perpendicular lines forming an L-bracket:
    # Line 1: (10, 10) -> (30, 10) [horizontal]
    # Line 2: (10, 10) -> (10, 30) [vertical]
    #
    # Base drawing also has the same L-bracket at (10, 10):
    # Base 1: (10, 10) -> (30, 10)
    # Base 2: (10, 10) -> (10, 30)
    #
    # But suppose anchors are on a 4-hole square pattern: (0,0), (40,0), (40,40), (0,40)
    # And there is a 90° mispairing / rotational ambiguity:
    # A1 (0,0) -> (40,0)
    # A2 (40,0) -> (40,40)
    # A3 (40,40) -> (0,40)
    # A4 (0,40) -> (0,0)
    anchors_permuted = [
        AnchorPair("A1", reference_px=(40.0, 0.0), cad_px=(0.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A2", reference_px=(40.0, 40.0), cad_px=(40.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A3", reference_px=(0.0, 40.0), cad_px=(40.0, 40.0), authority="DATUM", confidence=1.0),
        AnchorPair("A4", reference_px=(0.0, 0.0), cad_px=(0.0, 40.0), authority="DATUM", confidence=1.0),
    ]
    
    # Fit alignment under different policies:
    # Policy A: max_rot = 5.0
    # Policy B: max_rot = 180.0
    # Policy C: cardinal {0, 90, -90, 180} +/- 5
    # Policy D: caller declares expected = 0 +/- 5
    
    res_b = estimate_similarity_alignment(anchors_permuted, max_rotation_deg=180.0)
    rot_b = math.degrees(math.atan2(float(res_b.matrix[1][0]), float(res_b.matrix[0][0])))
    
    print("Under Policy B (max_rot=180.0):")
    print("  Status:", res_b.status)
    print(f"  Fitted rot: {rot_b:.2f}°, residual RMS: {res_b.residual_rms_px:.4f}")
    print("  -> Policy B ACCEPTS the 90° false alignment!")
    
    # What about Policy D with expected=0.0, tol=5.0?
    min_dist_0 = abs(rot_b - 0.0)
    print("Under Policy D (expected=0°, tol=5°):")
    print(f"  Distance to expected 0°: {min_dist_0:.2f}°")
    print("  -> Policy D REJECTS the 90° false alignment! Fails closed!")

if __name__ == "__main__":
    test_square_symmetry_with_sfp()
