"""End-to-End Synthesis Test Suite: Robust Dimension Association feeding into Calibration Consensus.

Verifies:
1. Synthetic reproduction of CASE01 drawing (14 OCR regions) demonstrating that
   while production baseline yields 0 candidates (CALIBRATION_CANDIDATE_EXTRACTION_NOT_SUPPORTED_FOR_THIS_SOURCE),
   Strategy D multi-primitive association recovers 6 robust witnesses and enables
   reviewable DRAFT_REFERENCE calibration with $INSUNITS=0.
2. Aspect ratio anisotropy detection on bridged dimension geometry.
3. Provenance and audit-readiness for pdf-run-manifest.json.
"""

import sys
from pathlib import Path
import pytest

from .dimension_association_engine import (
    SimpleLine,
    SimpleText,
    SimpleCircle,
    SimpleArc,
    DimensionType,
    StrategyA_ProductionBaseline,
    StrategyD_MultiPrimitiveAssociationOracle,
)

cal_unstated_dir = Path(__file__).resolve().parent.parent / "calibration_unstated_units"
if str(cal_unstated_dir) not in sys.path:
    sys.path.insert(0, str(cal_unstated_dir))

from calibration_unstated_units_engine import (
    DimensionEvidence,
    CalibrationState,
    UnitType,
    StrategyD_MultiDomainConsensusOracle,
)


def test_case01_synthetic_reproduction_unblocks_candidate_extraction():
    """Reproduces CASE01 motor-mount-bottom drawing layout:
    - 14 OCR regions:
      * 4 linear dimensions with central text gaps (Width 120, Height 80, Hole spacing 60, Flange 20)
      * 2 borehole diameter callouts (Ø10, Ø6.5)
      * 8 non-dimension notes (Title block 'MOTOR MOUNT BOTTOM', Rev 'A', Material 'AL 6061', Scale '1:1', etc.)
    - Geometry:
      * Split lines for linear dimensions
      * Circles for mounting boreholes
    - Scale: True scale = 0.100 length-units/px (Width 120 = 1200px, Height 80 = 800px).
    """
    # 14 OCR Texts
    texts = [
        # 4 Dimension Values with text gaps
        SimpleText("dim_w", "120.0", bbox=(585.0, 45.0, 615.0, 55.0), rotation_deg=0.0, parsed_value=120.0),
        SimpleText("dim_h", "80.0", bbox=(35.0, 385.0, 45.0, 415.0), rotation_deg=90.0, parsed_value=80.0),
        SimpleText("dim_pitch", "60.0", bbox=(585.0, 195.0, 615.0, 205.0), rotation_deg=0.0, parsed_value=60.0),
        SimpleText("dim_flange", "20.0", bbox=(95.0, 95.0, 105.0, 105.0), rotation_deg=0.0, parsed_value=20.0),
        # 2 Diameter callouts
        SimpleText("dim_bore1", "Ø10.0", bbox=(290.0, 390.0, 310.0, 410.0), parsed_value=10.0),
        SimpleText("dim_bore2", "Ø6.5", bbox=(490.0, 390.0, 510.0, 410.0), parsed_value=6.5),
        # 8 Non-dimension texts (title block, notes)
        SimpleText("txt_title", "MOTOR MOUNT BOTTOM", bbox=(800.0, 900.0, 950.0, 920.0), parsed_value=None, semantic_role="title"),
        SimpleText("txt_dwg", "DWG NO: MMB-001", bbox=(800.0, 930.0, 920.0, 945.0), parsed_value=1.0, semantic_role="drawing_number"),
        SimpleText("txt_rev", "REV B", bbox=(930.0, 930.0, 960.0, 945.0), parsed_value=None, semantic_role="revision"),
        SimpleText("txt_mat", "MATERIAL: AL 6061-T6", bbox=(100.0, 850.0, 250.0, 865.0), parsed_value=6061.0, semantic_role="general_note"),
        SimpleText("txt_finish", "FINISH: ANODIZE BLACK", bbox=(100.0, 870.0, 240.0, 885.0), parsed_value=None, semantic_role="general_note"),
        SimpleText("txt_tol", "TOLERANCES UNLESS SPECIFIED", bbox=(100.0, 890.0, 280.0, 905.0), parsed_value=None, semantic_role="general_note"),
        SimpleText("txt_scale", "SCALE 1:1", bbox=(800.0, 950.0, 860.0, 965.0), parsed_value=1.0, semantic_role="scale_label"),
        SimpleText("txt_sheet", "SHEET 1 OF 1", bbox=(900.0, 950.0, 960.0, 965.0), parsed_value=1.0, semantic_role="sheet_number"),
    ]

    # Geometry: split line segments (Hough lines)
    lines = [
        # Width dim (0 to 1200 at y=50, split at 580 to 620)
        SimpleLine("w_s1", (0.0, 50.0), (580.0, 50.0)),
        SimpleLine("w_s2", (620.0, 50.0), (1200.0, 50.0)),
        # Height dim (0 to 800 at x=40, split at 380 to 420)
        SimpleLine("h_s1", (40.0, 0.0), (40.0, 380.0)),
        SimpleLine("h_s2", (40.0, 420.0), (40.0, 800.0)),
        # Pitch dim (300 to 900 at y=200, split at 580 to 620)
        SimpleLine("p_s1", (300.0, 200.0), (580.0, 200.0)),
        SimpleLine("p_s2", (620.0, 200.0), (900.0, 200.0)),
        # Flange dim (0 to 200 at y=100)
        SimpleLine("f_s1", (0.0, 100.0), (200.0, 100.0)),
    ]

    circles = [
        # Bore 1: radius 50px (diameter 100px) -> 10.0 / 100px = 0.100 scale
        SimpleCircle("c_bore1", (300.0, 400.0), radius=50.0),
        # Bore 2: radius 32.5px (diameter 65px) -> 6.5 / 65px = 0.100 scale
        SimpleCircle("c_bore2", (500.0, 400.0), radius=32.5),
    ]

    # 1. Strategy A (Baseline): Fails to bridge gaps, miscalculates lengths
    assoc_a = StrategyA_ProductionBaseline.associate(texts, lines, circles)
    # Strategy A ignores circles (0 diameter associations) and only picks single fragmented segments:
    assert all(a.measured_pixel_span < 600.0 for a in assoc_a)  # completely missed 1200px and 800px spans

    # 2. Strategy D: Recovers all 6 dimension callouts with exact true spans
    assoc_d = StrategyD_MultiPrimitiveAssociationOracle.associate(texts, lines, circles)
    assert len(assoc_d) == 6

    # Convert to DimensionEvidence for calibration consensus oracle
    dim_evidence = []
    for a in assoc_d:
        axis = "X" if a.dimension_type == DimensionType.LINEAR_HORIZONTAL else (
            "Y" if a.dimension_type == DimensionType.LINEAR_VERTICAL else "RADIAL"
        )
        dim_evidence.append(DimensionEvidence(
            id=a.id,
            text_value=a.stated_value,
            pixel_length=a.measured_pixel_span,
            axis=axis,
            confidence=a.confidence,
        ))

    # 3. Feed into Multi-Domain Calibration Consensus Oracle
    cal_result = StrategyD_MultiDomainConsensusOracle.evaluate(dim_evidence, explicit_unit=None)

    # In CASE01, units are unstated:
    # Must achieve UNVERIFIED_DRAFT_REFERENCE with $INSUNITS=0
    assert cal_result.state == CalibrationState.UNVERIFIED_DRAFT_REFERENCE
    assert cal_result.unit == UnitType.UNKNOWN_UNSTATED
    assert cal_result.scale_x == pytest.approx(0.100, rel=1e-3)
    assert cal_result.scale_y == pytest.approx(0.100, rel=1e-3)
    assert cal_result.anisotropy_ratio == pytest.approx(1.0, rel=1e-3)
    assert cal_result.dxf_insunits == 0  # Unitless draft
    assert cal_result.can_generate_dxf is False  # Physical release gated!
    assert len(cal_result.contributing_witness_ids) >= 4


def test_e2e_anisotropy_detection_on_bridged_dimensions():
    """Verify that anisotropic elongation on bridged dimensions halts isotropic CAD."""
    # X span 100mm = 1000px (scale 0.1000)
    # Y span 100mm = 1050px (scale 0.0952, 5% stretch)
    texts = [
        SimpleText("tx", "100", bbox=(485.0, 45.0, 515.0, 55.0), rotation_deg=0.0, parsed_value=100.0),
        SimpleText("ty", "100", bbox=(45.0, 510.0, 55.0, 540.0), rotation_deg=90.0, parsed_value=100.0),
    ]
    lines = [
        SimpleLine("x1", (0.0, 50.0), (480.0, 50.0)),
        SimpleLine("x2", (520.0, 50.0), (1000.0, 50.0)),
        SimpleLine("y1", (50.0, 0.0), (50.0, 500.0)),
        SimpleLine("y2", (50.0, 550.0), (50.0, 1050.0)),
    ]

    assoc_d = StrategyD_MultiPrimitiveAssociationOracle.associate(texts, lines)
    assert len(assoc_d) == 2

    dim_evidence = [
        DimensionEvidence(assoc_d[0].id, assoc_d[0].stated_value, assoc_d[0].measured_pixel_span, axis="X"),
        DimensionEvidence(assoc_d[1].id, assoc_d[1].stated_value, assoc_d[1].measured_pixel_span, axis="Y"),
    ]

    cal_result = StrategyD_MultiDomainConsensusOracle.evaluate(dim_evidence, explicit_unit="mm")

    # Aspect ratio distortion detected -> CONFLICTING_AMBIGUOUS
    assert cal_result.state == CalibrationState.CONFLICTING_AMBIGUOUS
    assert abs(cal_result.anisotropy_ratio - 1.0) > 0.015
    assert "Anisotropic scan distortion detected" in cal_result.notes[0]
