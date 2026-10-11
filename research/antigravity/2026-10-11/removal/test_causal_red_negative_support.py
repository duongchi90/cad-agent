import sys
sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")

import cad_agent.source_support_verifier as ssv

def test_public_causal_red_negative_support():
    print("=== EXECUTING PUBLIC CAUSAL RED: NEGATIVE SOURCE SUPPORT EVIDENCE ===")
    
    # Check if source_support_verifier currently exports any negative support or absence verification function
    exported_functions = dir(ssv)
    negative_functions = [f for f in exported_functions if "absence" in f.lower() or "negative" in f.lower()]
    
    print("Exported functions in cad_agent.source_support_verifier:")
    print(" ", ssv.__all__)
    print("Functions matching 'absence' or 'negative':", negative_functions)
    
    # Assert current main lacks negative support verification
    assert len(negative_functions) == 0
    assert "verify_native_line_source_absence_evidence" not in exported_functions
    print("\nSUCCESS: Current main LACKS negative source support evidence owner (REPRODUCED RED).")

if __name__ == "__main__":
    test_public_causal_red_negative_support()
