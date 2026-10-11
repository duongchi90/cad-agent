import io
import sys
import hashlib
from PIL import Image, ImageDraw

sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")

from primitive_ir_lib.models import Calibration
from primitive_ir_lib.geometry_alignment import AnchorPair
from cad_agent.source_fusion_proposal import (
    compile_external_visual_object_proposal,
    compose_verified_native_line_delta,
)
from cad_agent.source_support_verifier import (
    verify_external_visual_proposal_source_support,
)
from cad_agent.source_verified_geometry import (
    materialize_verified_external_visual_lines,
)

def make_calibration():
    # 1 pixel = 1 mm, origin at (0, 64)
    # CAD_x = px_x * 1.0
    # CAD_y = (64 - px_y) * 1.0
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 64.0),
        method="manual_override",
        status="verified",
        source_sha256="1" * 64,
    )

def make_target_case(lines: list[tuple[str, tuple[int, int], tuple[int, int]]]):
    """lines: list of (primitive_id, (x1, y1), (x2, y2)) in pixels"""
    calibration = make_calibration()
    image = Image.new("L", (128, 128), 255)
    draw = ImageDraw.Draw(image)
    for _id, (x1, y1), (x2, y2) in lines:
        draw.line((x1, y1, x2, y2), fill=0, width=1)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    render_bytes = stream.getvalue()
    binding = {
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": hashlib.sha256(render_bytes).hexdigest(),
        "roi_bbox_px": [0, 0, 127, 127],
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "SIDE",
        "primitive_hypotheses": [
            {"id": pid, "type": "LINE", "start_px": [p1[0], p1[1]], "end_px": [p2[0], p2[1]]}
            for pid, p1, p2 in lines
        ],
        "object_groups": [
            {
                "group_id": "group-1",
                "proposed_label": "UNKNOWN_BOUNDARY",
                "primitive_hypothesis_ids": [pid for pid, _p1, _p2 in lines],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(
        proposal=proposal,
        expected_binding=binding,
        expected_calibration_binding=calibration.to_dict(),
    )
    support = verify_external_visual_proposal_source_support(
        verification_request=request,
        source_render_bytes=render_bytes,
    )
    doc = materialize_verified_external_visual_lines(
        verification_request=request,
        verification_result=support,
        source_render_bytes=render_bytes,
        calibration=calibration,
        source_file_name="synthetic-source.png",
        image_width_px=128,
        image_height_px=128,
    )
    return {
        "document": doc,
        "request": request,
        "result": support,
        "render_bytes": render_bytes,
        "calibration": calibration,
    }

def run_compose(base_lines, target_case, max_res=10.0, keep_tol=0.01):
    anchors = [
        AnchorPair("A1", (0.0, 0.0), (0.0, 0.0), "DATUM", 1.0),
        AnchorPair("A2", (50.0, 0.0), (50.0, 0.0), "DATUM", 1.0),
    ]
    return compose_verified_native_line_delta(
        base_native_line_observations=base_lines,
        verified_target_document=target_case["document"],
        verification_request=target_case["request"],
        verification_result=target_case["result"],
        source_render_bytes=target_case["render_bytes"],
        calibration=target_case["calibration"],
        base_coordinate_unit="mm",
        max_correspondence_residual=max_res,
        keep_tolerance=keep_tol,
        target_to_base_alignment_anchors=anchors,
        max_alignment_residual=0.001,
    )

def test_cases():
    print("=" * 80)
    print("RUNNING CAUSAL MATRIX EXPERIMENTS (CASES A - L)")
    print("=" * 80)
    
    # In calibration (scale=1, origin=(0, 64)):
    # px (10, 14) -> (30, 14) maps to CAD (10.0, 50.0) -> (30.0, 50.0)
    # px (10, 34) -> (30, 34) maps to CAD (10.0, 30.0) -> (30.0, 30.0)
    
    # -------------------------------------------------------------
    # CASE A: KEEP (identical base and target)
    target_A = make_target_case([("target-a", (10, 14), (30, 14))])
    base_A = [{"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_A = run_compose(base_A, target_A)
    print("CASE A (KEEP):")
    print(f"  status: {res_A['correspondence_status']}, corr: {len(res_A['base_target_correspondence'])}, deltas: {len(res_A['bounded_native_line_deltas'])}")
    if res_A['base_target_correspondence']:
        print(f"  disposition: {res_A['base_target_correspondence'][0]['disposition']}")

    # -------------------------------------------------------------
    # CASE B: CHANGE (base (10, 50)->(30, 50), target end shifted by +4mm)
    # px (10, 14) -> (34, 14) maps to CAD (10.0, 50.0) -> (34.0, 50.0)
    target_B = make_target_case([("target-b", (10, 14), (34, 14))])
    base_B = [{"observation_id": "base-b", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_B = run_compose(base_B, target_B)
    print("\nCASE B (CHANGE):")
    print(f"  status: {res_B['correspondence_status']}, corr: {len(res_B['base_target_correspondence'])}, deltas: {len(res_B['bounded_native_line_deltas'])}")
    if res_B['base_target_correspondence']:
        print(f"  disposition: {res_B['base_target_correspondence'][0]['disposition']}, residual: {res_B['base_target_correspondence'][0]['residual']}")

    # -------------------------------------------------------------
    # CASE C: TARGET_ONLY (Base has LINE_A; Target has LINE_A and LINE_NEW)
    target_C = make_target_case([
        ("target-a", (10, 14), (30, 14)), # (10, 50)->(30, 50)
        ("target-new", (10, 34), (30, 34)), # (10, 30)->(30, 30)
    ])
    base_C = [{"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_C = run_compose(base_C, target_C)
    print("\nCASE C (TARGET_ONLY / ADD Candidate):")
    print(f"  status: {res_C['correspondence_status']}, corr: {len(res_C['base_target_correspondence'])}, deltas: {len(res_C['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE D: BASE_ONLY (Base has LINE_A and LINE_OLD; Target has LINE_A only)
    target_D = make_target_case([("target-a", (10, 14), (30, 14))])
    base_D = [
        {"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]},
        {"observation_id": "base-old", "start": [10.0, 30.0], "end": [30.0, 30.0]},
    ]
    res_D = run_compose(base_D, target_D)
    print("\nCASE D (BASE_ONLY / REMOVE Candidate):")
    print(f"  status: {res_D['correspondence_status']}, corr: {len(res_D['base_target_correspondence'])}, deltas: {len(res_D['bounded_native_line_deltas'])}")
    corr_ids = [c["base_observation_id"] for c in res_D["base_target_correspondence"]]
    print(f"  base lines accounted for in correspondence: {corr_ids}")

    # -------------------------------------------------------------
    # CASE E: CHANGE + ADD (Base has A; Target has changed A + new line B)
    target_E = make_target_case([
        ("target-a-shifted", (10, 14), (34, 14)),
        ("target-new-b", (10, 34), (30, 34)),
    ])
    base_E = [{"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_E = run_compose(base_E, target_E)
    print("\nCASE E (CHANGE + ADD):")
    print(f"  status: {res_E['correspondence_status']}, corr: {len(res_E['base_target_correspondence'])}, deltas: {len(res_E['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE F: CHANGE + REMOVE (Base has A and OLD; Target has changed A)
    target_F = make_target_case([("target-a-shifted", (10, 14), (34, 14))])
    base_F = [
        {"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]},
        {"observation_id": "base-old", "start": [10.0, 30.0], "end": [30.0, 30.0]},
    ]
    res_F = run_compose(base_F, target_F)
    print("\nCASE F (CHANGE + REMOVE):")
    print(f"  status: {res_F['correspondence_status']}, corr: {len(res_F['base_target_correspondence'])}, deltas: {len(res_F['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE G: ADD + REMOVE (Base has A; Target has completely different B)
    target_G = make_target_case([("target-b", (10, 34), (30, 34))]) # y = 30
    base_G = [{"observation_id": "base-a", "start": [10.0, 50.0], "end": [30.0, 50.0]}] # y = 50, diff=20mm > max_res=10
    res_G = run_compose(base_G, target_G, max_res=10.0)
    print("\nCASE G (ADD + REMOVE):")
    print(f"  status: {res_G['correspondence_status']}, corr: {len(res_G['base_target_correspondence'])}, deltas: {len(res_G['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE H: Reversed endpoint orientation
    # Base: (10, 50) -> (30, 50); Target drawn (30, 50) -> (10, 50)
    # px: (30, 14) -> (10, 14)
    target_H = make_target_case([("target-rev", (30, 14), (10, 14))])
    base_H = [{"observation_id": "base-h", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_H = run_compose(base_H, target_H)
    print("\nCASE H (Reversed endpoint orientation):")
    print(f"  status: {res_H['correspondence_status']}, corr: {len(res_H['base_target_correspondence'])}, deltas: {len(res_H['bounded_native_line_deltas'])}")
    if res_H['base_target_correspondence']:
        print(f"  disposition: {res_H['base_target_correspondence'][0]['disposition']}, residual: {res_H['base_target_correspondence'][0]['residual']}")

    # -------------------------------------------------------------
    # CASE I: Two geometrically identical base lines
    target_I = make_target_case([("target-i", (10, 14), (30, 14))])
    base_I = [
        {"observation_id": "base-dup-1", "start": [10.0, 50.0], "end": [30.0, 50.0]},
        {"observation_id": "base-dup-2", "start": [10.0, 50.0], "end": [30.0, 50.0]},
    ]
    res_I = run_compose(base_I, target_I)
    print("\nCASE I (Two geometrically identical base lines):")
    print(f"  status: {res_I['correspondence_status']}, corr: {len(res_I['base_target_correspondence'])}, deltas: {len(res_I['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE J: Two geometrically identical target lines
    target_J = make_target_case([
        ("target-dup-1", (10, 14), (30, 14)),
        ("target-dup-2", (10, 14), (30, 14)),
    ])
    base_J = [{"observation_id": "base-j", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_J = run_compose(base_J, target_J)
    print("\nCASE J (Two geometrically identical target lines):")
    print(f"  status: {res_J['correspondence_status']}, corr: {len(res_J['base_target_correspondence'])}, deltas: {len(res_J['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE K: Target equidistant between two base lines
    # Base 1 at y = 52.0, Base 2 at y = 48.0; Target at y = 50.0
    # Both residuals = 2.0 mm
    target_K = make_target_case([("target-mid", (10, 14), (30, 14))]) # y = 50
    base_K = [
        {"observation_id": "base-top", "start": [10.0, 52.0], "end": [30.0, 52.0]},
        {"observation_id": "base-bot", "start": [10.0, 48.0], "end": [30.0, 48.0]},
    ]
    res_K = run_compose(base_K, target_K)
    print("\nCASE K (Target equidistant between two base lines):")
    print(f"  status: {res_K['correspondence_status']}, corr: {len(res_K['base_target_correspondence'])}, deltas: {len(res_K['bounded_native_line_deltas'])}")

    # -------------------------------------------------------------
    # CASE L: Crossing but geometrically distinct lines
    # Base horizontal: (10, 50) -> (30, 50)
    # Target vertical: (20, 40) -> (20, 60)
    # px: (20, 24) -> (20, 4) maps to CAD (20, 40) -> (20, 60)
    target_L = make_target_case([("target-vert", (20, 24), (20, 4))])
    base_L = [{"observation_id": "base-horiz", "start": [10.0, 50.0], "end": [30.0, 50.0]}]
    res_L = run_compose(base_L, target_L, max_res=5.0)
    print("\nCASE L (Crossing lines, residual > max_res):")
    print(f"  status: {res_L['correspondence_status']}, corr: {len(res_L['base_target_correspondence'])}, deltas: {len(res_L['bounded_native_line_deltas'])}")

if __name__ == "__main__":
    test_cases()
