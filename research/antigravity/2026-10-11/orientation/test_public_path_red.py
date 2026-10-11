import sys
import pytest
from pathlib import Path
import importlib

# Add cad-agent to sys.path
sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")

from primitive_ir_lib.geometry_alignment import AnchorPair
from primitive_ir_lib.models import Calibration
import tests.test_external_visual_primitive_ir_admission as test_helper

def test_compose_line_delta_90deg_rotation():
    print("=== TESTING PUBLIC PRODUCTION PATH RED (90 DEG ROTATION) ===")
    
    # 1. Create verified target document with 1 line
    target_case = test_helper._verified_target_case([("target-line-1", 10)])
    
    # In target_case with default calibration (scale=1.0, origin=(0, 64)):
    # Primitive start = (10.0, 54.0), end = (30.0, 54.0) in mm
    
    # 2. Define 90-degree CCW rotated base DWG frame:
    # WCS_X = -y_target + 100.0
    # WCS_Y =  x_target + 200.0
    # Target line transforms to:
    # start: (-54 + 100, 10 + 200) = (46.0, 210.0)
    # end:   (-54 + 100, 30 + 200) = (46.0, 230.0)
    
    # Base native line observation has modified end (shortened by 5mm):
    base_lines = [
        {
            "observation_id": "base-line-1",
            "start": [46.0, 210.0],
            "end": [46.0, 225.0],
        }
    ]
    
    # 3. Anchors (3 non-collinear points):
    # A1 target: (0.0, 0.0)   -> base: (100.0, 200.0)
    # A2 target: (50.0, 0.0)  -> base: (100.0, 250.0)
    # A3 target: (0.0, 40.0)  -> base: (60.0, 200.0)
    anchors_90deg = [
        AnchorPair("A1", reference_px=(100.0, 200.0), cad_px=(0.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A2", reference_px=(100.0, 250.0), cad_px=(50.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A3", reference_px=(60.0, 200.0), cad_px=(0.0, 40.0), authority="DATUM", confidence=1.0),
    ]
    
    # 4. Invoke compose_verified_native_line_delta
    try:
        result = test_helper._compose_line_delta(
            base_lines=base_lines,
            target_case=target_case,
            target_to_base_alignment_anchors=anchors_90deg,
            max_correspondence_residual=10.0,
            keep_tolerance=0.01,
        )
        print("RESULT SUCCESS:", result["correspondence_status"])
    except ValueError as e:
        print("CAUGHT EXPECTED CURRENT-MAIN RED FAILURE:", str(e))

def test_negative_control_symmetric_ambiguity():
    print("\n=== TESTING NEGATIVE CONTROL: SYMMETRIC / AMBIGUOUS ANCHOR CASE ===")
    target_case = test_helper._verified_target_case([("target-line-1", 10)])
    
    # Upright sheet, but anchors are square-symmetric and permuted by 90 deg:
    # Target square: (0,0), (50,0), (50,50), (0,50)
    # Ref square: permuted by 90 deg
    anchors_permuted = [
        AnchorPair("A1", reference_px=(50.0, 0.0), cad_px=(0.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A2", reference_px=(50.0, 50.0), cad_px=(50.0, 0.0), authority="DATUM", confidence=1.0),
        AnchorPair("A3", reference_px=(0.0, 50.0), cad_px=(50.0, 50.0), authority="DATUM", confidence=1.0),
        AnchorPair("A4", reference_px=(0.0, 0.0), cad_px=(0.0, 50.0), authority="DATUM", confidence=1.0),
    ]
    
    base_lines = [
        {
            "observation_id": "base-line-1",
            "start": [10.0, 54.0],
            "end": [30.0, 54.0],
        }
    ]
    
    try:
        result = test_helper._compose_line_delta(
            base_lines=base_lines,
            target_case=target_case,
            target_to_base_alignment_anchors=anchors_permuted,
            max_correspondence_residual=10.0,
            keep_tolerance=0.01,
        )
        print("PERMUTED ANCHOR RESULT:", result["correspondence_status"])
    except ValueError as e:
        print("PERMUTED ANCHOR FAILED CLOSED:", str(e))

if __name__ == "__main__":
    test_compose_line_delta_90deg_rotation()
    test_negative_control_symmetric_ambiguity()
