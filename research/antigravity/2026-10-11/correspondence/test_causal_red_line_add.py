import os
import sys
sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")
sys.path.insert(0, os.path.dirname(__file__))

from test_causal_matrix import make_target_case, run_compose

def test_causal_red_line_add():
    print("=== EXECUTING PUBLIC CAUSAL RED: SOURCE LINE ADD PROPOSAL ===")
    
    # Base DWG has 1 line:
    base = [{"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    
    # Modified source drawing has 2 lines:
    # 1. target-kept: matches base-a at (10, 50) -> (30, 50)
    # 2. target-new: newly drawn rib at (10, 30) -> (30, 30)
    target = make_target_case([
        ("target-kept", (10, 14), (30, 14)), # maps to (10, 50) -> (30, 50)
        ("target-new", (10, 34), (30, 34)),  # maps to (10, 30) -> (30, 30)
    ])
    
    result = run_compose(base, target, max_res=10.0, keep_tol=0.01)
    
    print("Current Main Result:")
    print("  status:                ", result.get("status"))
    print("  correspondence_status: ", result.get("correspondence_status"))
    print("  correspondence:        ", result.get("base_target_correspondence"))
    print("  deltas:                ", result.get("bounded_native_line_deltas"))
    
    # Assert current main failure
    assert result["correspondence_status"] == "NO_SUPPORTED_DELTA"
    assert result["base_target_correspondence"] == []
    assert result["bounded_native_line_deltas"] == []
    print("\nSUCCESS: Current main FAILS as expected (emits NO_SUPPORTED_DELTA and 0 deltas).")

if __name__ == "__main__":
    test_causal_red_line_add()
