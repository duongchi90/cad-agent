"""Behavioral Causal RED: Proving current main lacks raster absence evidence capability.

Fixture requirements satisfied:
- Exact source render bytes
- Exact bound source-render hash
- Valid ROI
- Known projected pixel LINE
- Genuine empty source corridor

Demonstrates that current main has no public observational path that can return a structured
VERIFIED absence result for that projected line while preserving negative safety controls.
Does NOT rely on AttributeError, ImportError, or missing symbol checks.
"""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO_ROOT = Path(r"C:\Users\duong\ZCodeProject\cad-agent")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cad_agent.source_support_verifier import verify_external_visual_proposal_source_support
from cad_agent.source_fusion_proposal import compile_external_visual_object_proposal


def create_png_fixture(width: int, height: int, draw_fn=None) -> tuple[bytes, str]:
    img = Image.new("L", (width, height), 255)
    if draw_fn:
        draw_fn(ImageDraw.Draw(img))
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    content = stream.getvalue()
    return content, hashlib.sha256(content).hexdigest()


def test_public_behavioral_causal_red_absence():
    print("=== EXECUTING BEHAVIORAL CAUSAL RED: NEGATIVE SOURCE SUPPORT ===")
    width, height = 100, 100
    start_px, end_px = [20, 50], [80, 50]
    roi_bbox = [10, 10, 90, 90]

    # Fixture 1: Genuine empty white corridor (absence true positive)
    empty_bytes, empty_sha = create_png_fixture(width, height)

    binding = {
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": empty_sha,
        "roi_bbox_px": roi_bbox,
    }
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "line_empty_corridor", "type": "LINE", "start_px": start_px, "end_px": end_px}
        ],
        "object_groups": [
            {
                "group_id": "g0",
                "proposed_label": "PART",
                "primitive_hypothesis_ids": ["line_empty_corridor"],
            }
        ],
        "excluded_memberships": [],
    }
    request = compile_external_visual_object_proposal(proposal=proposal, expected_binding=binding)

    # 1. Behavioral Failure: Current public entry point raises unhandled ValueError on empty corridor
    # instead of returning a structured absence verification result.
    observed_exception = None
    try:
        verify_external_visual_proposal_source_support(
            verification_request=request,
            source_render_bytes=empty_bytes,
        )
    except ValueError as e:
        observed_exception = str(e)

    print(f"1. Empty corridor public result: ValueError('{observed_exception}')")
    assert observed_exception == "PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:line_empty_corridor", (
        f"Unexpected exception: {observed_exception}"
    )

    # 2. Causal Consequence: Trapping ValueError('PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT')
    # to infer absence causes catastrophic false deletion on faint lines (Control A).
    def draw_faint(draw: ImageDraw.ImageDraw):
        draw.line([tuple(start_px), tuple(end_px)], fill=230, width=1)

    faint_bytes, faint_sha = create_png_fixture(width, height, draw_faint)
    faint_binding = dict(binding, source_render_sha256=faint_sha)
    faint_proposal = dict(proposal, **faint_binding)
    faint_proposal["primitive_hypotheses"] = [
        {"id": "line_faint_present", "type": "LINE", "start_px": start_px, "end_px": end_px}
    ]
    faint_proposal["object_groups"][0]["primitive_hypothesis_ids"] = ["line_faint_present"]
    faint_request = compile_external_visual_object_proposal(
        proposal=faint_proposal, expected_binding=faint_binding
    )

    faint_exception = None
    try:
        verify_external_visual_proposal_source_support(
            verification_request=faint_request,
            source_render_bytes=faint_bytes,
        )
    except ValueError as e:
        faint_exception = str(e)

    print(f"2. Faint present line public result: ValueError('{faint_exception}')")
    assert faint_exception == "PRIMITIVE_SOURCE_SUPPORT_INSUFFICIENT:line_faint_present", (
        f"Unexpected exception: {faint_exception}"
    )

    # 3. Behavioral Proof:
    # Both an empty corridor AND a faint present line produce the exact same failure code.
    # Current main has no mechanism to distinguish whitespace from faint ink.
    assert observed_exception.split(":")[0] == faint_exception.split(":")[0]
    print("\nSUCCESS: Behavioral Causal RED established.")
    print("Current main cannot observe absence without conflating genuine deletion with faint lines.")


if __name__ == "__main__":
    test_public_behavioral_causal_red_absence()
