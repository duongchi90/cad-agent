"""Controls Test Suite for Calibration Candidate Extraction Transfer Architecture.

Establishes positive and negative control baselines for Method C (Guarded Multi-Primitive Oracle):
- Positive Controls:
  1. Pure dual-line bridged consensus (X & Y axes, error <= 1%)
  2. Mixed primitive consensus (1 bridged line + 1 isolated borehole circle)
  3. Multi-circle independent borehole consensus (two distinct centers)
- Negative Controls:
  1. Concentric circle ambiguity refusal (concentric circles rejected from candidates)
  2. Non-dimension text exclusion (drawing notes, title blocks, revision text ignored)
  3. Excessive carrier distance rejection (> 3 * text.height)
  4. Angular misalignment rejection (rotation mismatch > 15 deg)
  5. Scale disparity consensus rejection (> 3% relative error between candidates)
  6. Single-witness insufficiency rejection (< 2 candidates cannot produce verified consensus)
"""

import pytest

from .calibration_candidate_transfer_engine import (
    TransferState,
    MethodC_GuardedMultiPrimitiveOracle,
    SimpleLine,
    SimpleText,
    SimpleCircle,
)


# ==============================================================================
# POSITIVE CONTROLS
# ==============================================================================

def test_pos_control_1_dual_line_bridged_consensus():
    """Positive Control 1: Two independent orthogonal dimension lines with text gaps.
    Line 1 (Horizontal): Span 1000px, Text '100' -> scale = 0.100 mm/px.
    Line 2 (Vertical): Span 500px, Text '50' -> scale = 0.100 mm/px.
    Result: 2 contributing candidates, relative error = 0.0%, status='needs_verification'."""
    t_h = SimpleText("th", "100", bbox=(480.0, 90.0, 520.0, 110.0), rotation_deg=0.0, parsed_value=100.0)
    lines_h = [
        SimpleLine("lh1", (0.0, 100.0), (450.0, 100.0)),
        SimpleLine("lh2", (550.0, 100.0), (1000.0, 100.0)),
    ]

    t_v = SimpleText("tv", "50", bbox=(90.0, 230.0, 110.0, 270.0), rotation_deg=90.0, parsed_value=50.0)
    lines_v = [
        SimpleLine("lv1", (100.0, 0.0), (100.0, 200.0)),
        SimpleLine("lv2", (100.0, 300.0), (100.0, 500.0)),
    ]

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_h, t_v],
        lines=lines_h + lines_v,
    )

    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res.contributing_candidates) == 2
    assert res.relative_error_pct <= 0.01
    assert res.is_reviewable is True


def test_pos_control_2_mixed_primitive_consensus():
    """Positive Control 2: 1 bridged line + 1 isolated borehole circle.
    Line: Span 600px, Text '60' -> scale = 0.100 mm/px.
    Circle: Radius 150px (Diameter 300px), Text 'Ø30' -> scale = 30 / 300 = 0.100 mm/px.
    Result: Successfully cross-validates across primitive types."""
    t_line = SimpleText("t_line", "60", bbox=(280.0, 40.0, 320.0, 60.0), rotation_deg=0.0, parsed_value=60.0)
    lines = [
        SimpleLine("l1", (0.0, 50.0), (250.0, 50.0)),
        SimpleLine("l2", (350.0, 50.0), (600.0, 50.0)),
    ]

    t_circle = SimpleText("t_circ", "Ø30", bbox=(780.0, 480.0, 820.0, 520.0), parsed_value=30.0)
    circle = SimpleCircle("c1", center=(800.0, 500.0), radius=150.0)

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t_line, t_circle],
        lines=lines,
        circles=[circle],
    )

    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res.contributing_candidates) == 2
    types = {c.primitive_type for c in res.contributing_candidates}
    assert "line_bridged" in types
    assert "circle_diameter" in types


def test_pos_control_3_multi_circle_independent_consensus():
    """Positive Control 3: Two separate, non-concentric boreholes with diameter callouts.
    Hole 1 at (200, 200): Radius 50px (D=100px), Text 'Ø10' -> scale = 0.100 mm/px.
    Hole 2 at (800, 800): Radius 100px (D=200px), Text 'Ø20' -> scale = 0.100 mm/px.
    Result: 2 independent circle witnesses satisfy AGENTS.md consensus."""
    t1 = SimpleText("t1", "Ø10", bbox=(180.0, 180.0, 220.0, 220.0), parsed_value=10.0)
    c1 = SimpleCircle("c1", center=(200.0, 200.0), radius=50.0)

    t2 = SimpleText("t2", "Ø20", bbox=(780.0, 780.0, 820.0, 820.0), parsed_value=20.0)
    c2 = SimpleCircle("c2", center=(800.0, 800.0), radius=100.0)

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t1, t2],
        lines=[],
        circles=[c1, c2],
    )

    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res.contributing_candidates) == 2


# ==============================================================================
# NEGATIVE CONTROLS
# ==============================================================================

def test_neg_control_1_concentric_ambiguity_refused():
    """Negative Control 1: Concentric circles (e.g. counterbore c1=50px, c2=100px sharing center)
    without leader association must be refused. They cannot be used to guess a candidate scale."""
    t = SimpleText("t1", "Ø10", bbox=(180.0, 180.0, 220.0, 220.0), parsed_value=10.0)
    c_inner = SimpleCircle("c_in", center=(200.0, 200.0), radius=50.0)
    c_outer = SimpleCircle("c_out", center=(200.0, 200.0), radius=100.0)

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[t],
        lines=[],
        circles=[c_inner, c_outer],
    )

    # Must refuse to pick between concentric candidates:
    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None
    assert len(res.contributing_candidates) == 0


def test_neg_control_2_non_dimension_text_excluded():
    """Negative Control 2: Drawing notes, title block text, revision numbers, etc.
    must be ignored even if they contain numbers or are close to lines."""
    texts = [
        SimpleText("t_rev", "REV 2", bbox=(10.0, 10.0, 50.0, 30.0), parsed_value=2.0, semantic_role="title_block"),
        SimpleText("t_mat", "AL 6061", bbox=(60.0, 10.0, 120.0, 30.0), parsed_value=6061.0, semantic_role="drawing_note"),
        SimpleText("t_sec", "SECTION A-A", bbox=(200.0, 10.0, 300.0, 30.0), parsed_value=None, semantic_role="section_label"),
    ]
    lines = [
        SimpleLine("l1", (0.0, 20.0), (100.0, 20.0)),
        SimpleLine("l2", (200.0, 20.0), (300.0, 20.0)),
    ]

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=texts, lines=lines)

    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None
    assert len(res.contributing_candidates) == 0


def test_neg_control_3_excessive_carrier_distance_rejected():
    """Negative Control 3: A dimension text placed far away (> 3 * text.height) from a line
    carrier must NOT be snapped to it."""
    # Text height = 20px -> Corridor limit = max(30, 3 * 20) = 60px.
    # Line at y=200, text at y=100 (dist = 100px > 60px).
    t = SimpleText("t1", "50", bbox=(100.0, 90.0, 140.0, 110.0), parsed_value=50.0)
    line = SimpleLine("l1", (0.0, 200.0), (500.0, 200.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[t], lines=[line])

    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None


def test_neg_control_4_misaligned_orientation_rejected():
    """Negative Control 4: Text orientation must match carrier line within 15 deg.
    Horizontal text (0 deg) cannot associate with a 45 deg or 90 deg line."""
    t = SimpleText("t1", "50", bbox=(90.0, 90.0, 110.0, 110.0), rotation_deg=0.0, parsed_value=50.0)
    line_diag = SimpleLine("l_diag", (50.0, 50.0), (150.0, 150.0))  # 45 deg

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[t], lines=[line_diag])

    assert res.status == TransferState.NO_CANDIDATE_SUPPORTED
    assert res.estimated_scale is None


def test_neg_control_5_scale_disparity_consensus_rejected():
    """Negative Control 5: When candidate scales disagree by > 3%, consensus must fail
    closed (status='consensus_failed', estimated_scale=None)."""
    # Cand 1: 100 mm / 1000 px = 0.100 mm/px
    t1 = SimpleText("t1", "100", bbox=(480.0, 90.0, 520.0, 110.0), parsed_value=100.0)
    l1 = SimpleLine("l1", (0.0, 100.0), (1000.0, 100.0))

    # Cand 2: 50 mm / 400 px = 0.125 mm/px (+25% difference)
    t2 = SimpleText("t2", "50", bbox=(180.0, 290.0, 220.0, 310.0), parsed_value=50.0)
    l2 = SimpleLine("l2", (0.0, 300.0), (400.0, 300.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[t1, t2], lines=[l1, l2])

    assert res.status == TransferState.CONSENSUS_FAILED
    assert res.estimated_scale is None
    assert res.relative_error_pct > 3.0
    assert res.is_reviewable is False


def test_neg_control_6_single_witness_insufficiency():
    """Negative Control 6: A single candidate cannot achieve multi-candidate consensus.
    While extracted as a reviewable hypothesis (needs_verification), it is explicitly
    annotated as a single witness and cannot satisfy the AGENTS.md gate of >= 2 candidates."""
    t = SimpleText("t1", "100", bbox=(480.0, 90.0, 520.0, 110.0), parsed_value=100.0)
    l = SimpleLine("l1", (0.0, 100.0), (1000.0, 100.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[t], lines=[l])

    assert res.status == TransferState.CANDIDATE_NEEDS_VERIFICATION
    assert res.estimated_scale == pytest.approx(0.100, rel=1e-3)
    assert len(res.contributing_candidates) == 1
    assert any("Single candidate only" in note for note in res.notes)
    # AGENTS.md requires >= 2 independent candidates for automated release:
    assert len(res.contributing_candidates) < 2


def test_neg_control_7_correlated_evidence_rejected():
    """Negative Control 7: Correlated Evidence Hazard.
    Two text annotations snapping to the SAME carrier line (e.g. duplicate labels or
    sub-segments of the same entity) cannot be counted as 2 independent witnesses.
    Consensus must fail closed because geometric independence is violated."""
    t1 = SimpleText("t1", "100", bbox=(200.0, 90.0, 240.0, 110.0), parsed_value=100.0)
    t2 = SimpleText("t2", "100", bbox=(700.0, 90.0, 740.0, 110.0), parsed_value=100.0)
    # Both associate to single line l1
    l1 = SimpleLine("l1", (0.0, 100.0), (1000.0, 100.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(texts=[t1, t2], lines=[l1])

    assert res.status == TransferState.CONSENSUS_FAILED
    assert res.estimated_scale is None
    assert any("geometrically correlated" in n for n in res.notes)


def test_control_8_conflicting_mixed_view_scales_refused():
    """Negative Control 8: Mixed-Scale Views Conflict Hazard.
    On an unpartitioned sheet with equal dimensions across mixed-scale views (Main 1:1 vs Detail 5:1):
    - Main view has 2 dimensions: 100mm/1000px and 50mm/500px -> scale 0.100 mm/px.
    - Detail view has 2 dimensions: 10mm/500px and 5mm/250px -> scale 0.020 mm/px.
    Without semantic view partitioning, assigning a single global scale would corrupt one or both views.
    Method C refuses to synthesize a compromise scale and fails closed (status='consensus_failed')."""
    # Main view (0.100 mm/px)
    tm1 = SimpleText("tm1", "100", bbox=(480.0, 90.0, 520.0, 110.0), parsed_value=100.0)
    lm1 = SimpleLine("lm1", (0.0, 100.0), (1000.0, 100.0))
    tm2 = SimpleText("tm2", "50", bbox=(230.0, 290.0, 270.0, 310.0), parsed_value=50.0)
    lm2 = SimpleLine("lm2", (0.0, 300.0), (500.0, 300.0))

    # Detail view (0.020 mm/px)
    td1 = SimpleText("td1", "10", bbox=(1230.0, 90.0, 1270.0, 110.0), parsed_value=10.0)
    ld1 = SimpleLine("ld1", (1000.0, 100.0), (1500.0, 100.0))
    td2 = SimpleText("td2", "5", bbox=(1110.0, 290.0, 1150.0, 310.0), parsed_value=5.0)
    ld2 = SimpleLine("ld2", (1000.0, 300.0), (1250.0, 300.0))

    res = MethodC_GuardedMultiPrimitiveOracle.extract_candidate(
        texts=[tm1, tm2, td1, td2],
        lines=[lm1, lm2, ld1, ld2],
    )

    assert res.status == TransferState.CONSENSUS_FAILED
    assert res.estimated_scale is None
    assert res.is_reviewable is False
    assert res.relative_error_pct > 10.0
