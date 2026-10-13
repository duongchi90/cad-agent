"""Reference engine for unstated units and scale calibration in CAD Agent Reconstruction Mode.

Implements Strategies A-D for handling raster/PDF drawings where units and/or drawing
scales are unstated, ambiguous, or multi-view.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set


class EvidenceFamily(enum.Enum):
    EXPLICIT_UNIT_DECLARATION = "explicit_unit_declaration"
    EXPLICIT_SCALE_LABEL = "explicit_scale_label"
    DIMENSION_GEOMETRY_PAIR = "dimension_geometry_pair"
    MULTI_DIMENSION_CONSENSUS = "multi_dimension_consensus"
    CIRCLE_DIAMETER_WITNESS = "circle_diameter_witness"
    PDF_PAGE_DPI_CONTAINER = "pdf_page_dpi_container"
    VECTOR_PDF_METADATA = "vector_pdf_metadata"
    PER_VIEW_SCALE = "per_view_scale"
    ANISOTROPIC_SCAN_DISTORTION = "anisotropic_scan_distortion"
    OCR_UNCERTAINTY = "ocr_uncertainty"
    DO_NOT_SCALE_CONSTRAINT = "do_not_scale_constraint"
    UNIT_AMBIGUITY_INCH_MM = "unit_ambiguity_inch_mm"
    AUDIT_PROVENANCE = "audit_provenance"
    SAFE_UNRESOLVED_REFUSAL = "safe_unresolved_refusal"


class UnitType(enum.Enum):
    MILLIMETER = "mm"
    INCH = "in"
    METER = "m"
    FOOT = "ft"
    UNKNOWN_UNSTATED = "unknown_unstated"


class CalibrationState(enum.Enum):
    UNKNOWN_UNSTATED = "unknown_unstated"
    HYPOTHESIS_FORMULATED = "hypothesis_formulated"
    CONSENSUS_ACHIEVED = "consensus_achieved"
    CONFLICTING_AMBIGUOUS = "conflicting_ambiguous"
    DO_NOT_SCALE_RESTRICTED = "do_not_scale_restricted"
    UNVERIFIED_DRAFT_REFERENCE = "unverified_draft_reference"
    VERIFIED_PHYSICAL = "verified_physical"


@dataclass(frozen=True)
class DimensionEvidence:
    id: str
    text_value: float
    pixel_length: float
    axis: str  # 'X', 'Y', 'ALIGNED', 'DIAMETER'
    view_id: str = "main_view"
    confidence: float = 1.0
    is_radius_or_diameter: bool = False
    source_bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    @property
    def scale_candidate(self) -> float:
        if self.pixel_length <= 0:
            return 0.0
        return self.text_value / self.pixel_length


@dataclass
class CalibrationHypothesis:
    unit: UnitType
    unit_confidence: float
    scale_x: float
    scale_y: float
    anisotropy_ratio: float  # scale_y / scale_x
    state: CalibrationState
    contributing_witness_ids: List[str] = field(default_factory=list)
    outlier_witness_ids: List[str] = field(default_factory=list)
    relative_error_pct: float = 0.0
    notes: List[str] = field(default_factory=list)
    view_scales: Dict[str, float] = field(default_factory=dict)
    can_generate_dxf: bool = False
    dxf_insunits: int = 0  # 0=Unitless, 1=Inches, 4=Millimeters


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


class StrategyA_ProductionBaseline:
    """Emulates current production calibration.py behavior:
    - Defaults unit to 'mm' silently without evidence.
    - Uses first candidate or permissive 10% consensus.
    - Blind to anisotropic scan stretching.
    - If 1 candidate exists under require_consensus=True, still returns calibration.
    """

    @staticmethod
    def evaluate(
        dimensions: List[DimensionEvidence],
        explicit_unit: Optional[str] = None,
        scale_label: Optional[float] = None,
        has_do_not_scale: bool = False,
    ) -> CalibrationHypothesis:
        # Defaults unit to mm
        unit = UnitType.MILLIMETER if explicit_unit is None else UnitType(explicit_unit)
        if not dimensions:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=0.1,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                notes=["No dimension candidates found"],
                can_generate_dxf=False,
                dxf_insunits=4,
            )

        # Baseline picks first or 10% median
        scales = [d.scale_candidate for d in dimensions if d.scale_candidate > 0]
        if not scales:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=0.1,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                can_generate_dxf=False,
                dxf_insunits=4,
            )

        med = _median(scales)
        # Permissive 10% tolerance
        agreeing = [d for d in dimensions if abs(d.scale_candidate - med) / med <= 0.10]
        chosen_scale = agreeing[0].scale_candidate if agreeing else scales[0]

        return CalibrationHypothesis(
            unit=unit,
            unit_confidence=0.5,
            scale_x=chosen_scale,
            scale_y=chosen_scale,  # Isotropic assumption
            anisotropy_ratio=1.0,
            state=CalibrationState.UNVERIFIED_DRAFT_REFERENCE,
            contributing_witness_ids=[d.id for d in agreeing],
            relative_error_pct=5.0,
            notes=["Baseline heuristic calibration accepted"],
            can_generate_dxf=True,  # Baseline attempts DXF staging
            dxf_insunits=4,  # Hardcoded mm
        )


class StrategyB_StrictClosedWorld:
    """Strict manual gate:
    - Fails closed if manual verified scale or explicit approval is missing.
    - Produces zero reviewable candidates for unseen uncalibrated drawings.
    """

    @staticmethod
    def evaluate(
        dimensions: List[DimensionEvidence],
        manual_verified_scale: Optional[float] = None,
        calibration_approval: Optional[str] = None,
        explicit_unit: Optional[str] = None,
    ) -> CalibrationHypothesis:
        if manual_verified_scale is None or not calibration_approval:
            return CalibrationHypothesis(
                unit=UnitType.UNKNOWN_UNSTATED,
                unit_confidence=0.0,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                notes=["Refused: manual verified scale and approval required"],
                can_generate_dxf=False,
                dxf_insunits=0,
            )

        unit = UnitType.MILLIMETER if explicit_unit == "mm" else (
            UnitType.INCH if explicit_unit == "in" else UnitType.UNKNOWN_UNSTATED
        )
        return CalibrationHypothesis(
            unit=unit,
            unit_confidence=1.0 if explicit_unit else 0.5,
            scale_x=manual_verified_scale,
            scale_y=manual_verified_scale,
            anisotropy_ratio=1.0,
            state=CalibrationState.VERIFIED_PHYSICAL,
            notes=[f"Verified scale provided with approval: {calibration_approval}"],
            can_generate_dxf=True,
            dxf_insunits=4 if unit == UnitType.MILLIMETER else (1 if unit == UnitType.INCH else 0),
        )


class StrategyC_TwoPhaseDiscovery:
    """Two-phase discovery:
    - Extracts candidates into needs_verification registry.
    - Stops before Semantic IR/DXF if unverified.
    - Still uses single isotropic scale and does not isolate per-view scales.
    """

    @staticmethod
    def evaluate(
        dimensions: List[DimensionEvidence],
        explicit_unit: Optional[str] = None,
        has_do_not_scale: bool = False,
    ) -> CalibrationHypothesis:
        unit = UnitType(explicit_unit) if explicit_unit in ("mm", "in") else UnitType.UNKNOWN_UNSTATED
        if not dimensions:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=0.0,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                can_generate_dxf=False,
                dxf_insunits=0,
            )

        scales = [d.scale_candidate for d in dimensions if d.scale_candidate > 0]
        med = _median(scales)
        agreeing = [d for d in dimensions if abs(d.scale_candidate - med) / med <= 0.05]

        if len(agreeing) < 2:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=0.3,
                scale_x=med,
                scale_y=med,
                anisotropy_ratio=1.0,
                state=CalibrationState.CONFLICTING_AMBIGUOUS,
                notes=["Fewer than 2 agreeing candidates"],
                can_generate_dxf=False,
                dxf_insunits=0,
            )

        return CalibrationHypothesis(
            unit=unit,
            unit_confidence=0.6 if unit != UnitType.UNKNOWN_UNSTATED else 0.2,
            scale_x=med,
            scale_y=med,
            anisotropy_ratio=1.0,
            state=CalibrationState.UNVERIFIED_DRAFT_REFERENCE,
            contributing_witness_ids=[d.id for d in agreeing],
            notes=["Reviewable draft candidate produced; physical DXF gated"],
            can_generate_dxf=False,
            dxf_insunits=0,
        )


class StrategyD_MultiDomainConsensusOracle:
    """Comprehensive adversarial multi-domain calibration consensus oracle:
    1. Strict AGENTS.md consensus invariant: >= 2 independent witnesses with <= 3.0% median relative error.
    2. Unit isolation: never infers physical unit (mm vs in) without explicit declaration or verified BOM/title evidence.
    3. Anisotropy detection: verifies horizontal (X) and vertical (Y) scale agreement. If |s_x - s_y| / mean > 1.5%, flags distortion.
    4. Per-view scale isolation: groups witnesses by view_id; refuses to apply detail view scale to main sheet.
    5. 'DO NOT SCALE' compliance: enforces hard constraint, preventing graphic scale promotion.
    6. Refusal semantics: stops cleanly at UNVERIFIED_DRAFT_REFERENCE or CONFLICTING_AMBIGUOUS, never releasing physical CAD.
    """

    MAX_CONSENSUS_REL_ERROR = 0.030  # 3.0% per AGENTS.md
    MIN_INDEPENDENT_WITNESSES = 2
    MAX_ANISOTROPY_TOLERANCE = 0.015  # 1.5% max elongation difference

    @classmethod
    def evaluate(
        cls,
        dimensions: List[DimensionEvidence],
        explicit_unit: Optional[str] = None,
        scale_label_denominator: Optional[int] = None,
        page_dpi: Optional[int] = None,
        has_do_not_scale: bool = False,
        view_regions: Optional[Dict[str, Tuple[float, float, float, float]]] = None,
    ) -> CalibrationHypothesis:
        notes: List[str] = []

        # 1. Constraint Check: DO NOT SCALE
        if has_do_not_scale:
            return CalibrationHypothesis(
                unit=UnitType.UNKNOWN_UNSTATED if not explicit_unit else UnitType(explicit_unit),
                unit_confidence=1.0 if explicit_unit else 0.0,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.DO_NOT_SCALE_RESTRICTED,
                notes=["Source explicitly specifies DO NOT SCALE; graphic measurement prohibited"],
                can_generate_dxf=False,
                dxf_insunits=0,
            )

        # 2. Unit Deduction & Isolation
        unit = UnitType.UNKNOWN_UNSTATED
        unit_confidence = 0.0
        if explicit_unit in ("mm", "millimeter", "millimeters"):
            unit = UnitType.MILLIMETER
            unit_confidence = 1.0
            notes.append("Explicit unit declaration: mm")
        elif explicit_unit in ("in", "inch", "inches"):
            unit = UnitType.INCH
            unit_confidence = 1.0
            notes.append("Explicit unit declaration: inch")
        else:
            notes.append("Physical unit unstated; unit remains UNKNOWN_UNSTATED")

        if not dimensions:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=unit_confidence,
                scale_x=0.0,
                scale_y=0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                notes=["No geometric dimension witnesses available"],
                can_generate_dxf=False,
                dxf_insunits=0,
            )

        # 3. Per-View Isolation: Partition by view
        views: Dict[str, List[DimensionEvidence]] = {}
        for d in dimensions:
            views.setdefault(d.view_id, []).append(d)

        main_view_id = "main_view" if "main_view" in views else next(iter(views.keys()))
        main_dims = views[main_view_id]

        # Calculate per-view scale medians
        view_medians: Dict[str, float] = {}
        for v_id, v_dims in views.items():
            v_scales = [d.scale_candidate for d in v_dims if d.scale_candidate > 0]
            if len(v_scales) >= cls.MIN_INDEPENDENT_WITNESSES:
                view_medians[v_id] = _median(v_scales)

        # 4. Multi-Witness Consensus on Primary View
        scales = [d.scale_candidate for d in main_dims if d.scale_candidate > 0]
        if len(scales) < cls.MIN_INDEPENDENT_WITNESSES:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=unit_confidence,
                scale_x=_median(scales) if scales else 0.0,
                scale_y=_median(scales) if scales else 0.0,
                anisotropy_ratio=1.0,
                state=CalibrationState.UNKNOWN_UNSTATED,
                notes=[f"Fewer than {cls.MIN_INDEPENDENT_WITNESSES} witnesses on primary view; fails consensus gate"],
                can_generate_dxf=False,
                dxf_insunits=0,
                view_scales=view_medians,
            )

        # Check per-axis consensus and anisotropy
        x_dims = [d for d in main_dims if d.axis == "X" and d.scale_candidate > 0]
        y_dims = [d for d in main_dims if d.axis == "Y" and d.scale_candidate > 0]

        x_scales = [d.scale_candidate for d in x_dims]
        y_scales = [d.scale_candidate for d in y_dims]

        if x_scales and y_scales:
            med_x = _median(x_scales)
            med_y = _median(y_scales)
            anisotropy = med_y / med_x if med_x > 0 else 1.0
            if abs(anisotropy - 1.0) > cls.MAX_ANISOTROPY_TOLERANCE:
                agreeing_x = [d for d in x_dims if abs(d.scale_candidate - med_x) / med_x <= cls.MAX_CONSENSUS_REL_ERROR]
                agreeing_y = [d for d in y_dims if abs(d.scale_candidate - med_y) / med_y <= cls.MAX_CONSENSUS_REL_ERROR]
                agreeing = agreeing_x + agreeing_y
                agreeing_ids = {d.id for d in agreeing}
                outliers = [d for d in main_dims if d.id not in agreeing_ids]
                return CalibrationHypothesis(
                    unit=unit,
                    unit_confidence=unit_confidence,
                    scale_x=med_x,
                    scale_y=med_y,
                    anisotropy_ratio=anisotropy,
                    state=CalibrationState.CONFLICTING_AMBIGUOUS,
                    contributing_witness_ids=[d.id for d in agreeing],
                    outlier_witness_ids=[d.id for d in outliers],
                    notes=[f"Anisotropic scan distortion detected: X={med_x:.5f}, Y={med_y:.5f} (ratio {anisotropy:.3f} > {cls.MAX_ANISOTROPY_TOLERANCE*100:.1f}%)"],
                    can_generate_dxf=False,
                    dxf_insunits=0,
                    view_scales=view_medians,
                )

        med = _median(scales)
        agreeing = [
            d for d in main_dims
            if abs(d.scale_candidate - med) / med <= cls.MAX_CONSENSUS_REL_ERROR
        ]
        agreeing_ids = {d.id for d in agreeing}
        outliers = [d for d in main_dims if d.id not in agreeing_ids]

        if len(agreeing) < cls.MIN_INDEPENDENT_WITNESSES:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=unit_confidence,
                scale_x=med,
                scale_y=med,
                anisotropy_ratio=1.0,
                state=CalibrationState.CONFLICTING_AMBIGUOUS,
                contributing_witness_ids=[d.id for d in agreeing],
                outlier_witness_ids=[d.id for d in outliers],
                notes=[f"Witness consensus failed: only {len(agreeing)}/{len(main_dims)} within {cls.MAX_CONSENSUS_REL_ERROR*100:.1f}%"],
                can_generate_dxf=False,
                dxf_insunits=0,
                view_scales=view_medians,
            )

        # 5. Anisotropy Check (Horizontal vs Vertical)
        x_scales_agr = [d.scale_candidate for d in agreeing if d.axis == "X"]
        y_scales_agr = [d.scale_candidate for d in agreeing if d.axis == "Y"]

        scale_x = _median(x_scales_agr) if x_scales_agr else med
        scale_y = _median(y_scales_agr) if y_scales_agr else med
        anisotropy = scale_y / scale_x if scale_x > 0 else 1.0

        if x_scales_agr and y_scales_agr and abs(anisotropy - 1.0) > cls.MAX_ANISOTROPY_TOLERANCE:
            return CalibrationHypothesis(
                unit=unit,
                unit_confidence=unit_confidence,
                scale_x=scale_x,
                scale_y=scale_y,
                anisotropy_ratio=anisotropy,
                state=CalibrationState.CONFLICTING_AMBIGUOUS,
                contributing_witness_ids=[d.id for d in agreeing],
                outlier_witness_ids=[d.id for d in outliers],
                notes=[f"Anisotropic scan distortion detected: X={scale_x:.5f}, Y={scale_y:.5f} (ratio {anisotropy:.3f} > {cls.MAX_ANISOTROPY_TOLERANCE*100:.1f}%)"],
                can_generate_dxf=False,
                dxf_insunits=0,
                view_scales=view_medians,
            )

        # 6. Final State Evaluation
        max_rel_error = max(abs(d.scale_candidate - med) / med for d in agreeing) * 100.0

        # Can we promote to VERIFIED_PHYSICAL?
        # Requires BOTH:
        # 1. Stated or independently verified unit
        # 2. Explicit scale agreement OR paper container corroboration
        is_fully_verified = False
        if unit != UnitType.UNKNOWN_UNSTATED and scale_label_denominator and page_dpi:
            expected_paper_scale = scale_label_denominator * 25.4 / page_dpi
            if abs(med - expected_paper_scale) / expected_paper_scale <= cls.MAX_CONSENSUS_REL_ERROR:
                is_fully_verified = True
                notes.append("Independent paper-scale and dimension-geometry corroboration verified")

        final_state = CalibrationState.VERIFIED_PHYSICAL if is_fully_verified else CalibrationState.UNVERIFIED_DRAFT_REFERENCE

        return CalibrationHypothesis(
            unit=unit,
            unit_confidence=unit_confidence,
            scale_x=scale_x,
            scale_y=scale_y,
            anisotropy_ratio=anisotropy,
            state=final_state,
            contributing_witness_ids=[d.id for d in agreeing],
            outlier_witness_ids=[d.id for d in outliers],
            relative_error_pct=round(max_rel_error, 3),
            notes=notes,
            view_scales=view_medians,
            can_generate_dxf=is_fully_verified,
            dxf_insunits=4 if unit == UnitType.MILLIMETER else (1 if unit == UnitType.INCH else 0),
        )
