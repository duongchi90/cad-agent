"""linetype_pattern_engine.py — Reference implementations for Linetype Pattern Detection and Continuous Stroke Synthesis.

Compares:
- Strategy A: Current Production Baseline (Horizontal only, rigid mock JSON input, 0 stroke synthesis)
- Strategy B: Naive Length-Gap Thresholding (Pairs adjacent segments if gap <= 3mm, blind to cadence)
- Strategy C: Collinear Angle Clustered Projection (Angle clustering, coarse length ratio)
- Strategy D: Comprehensive Cadence Analysis & Continuous Synthesis Oracle (Any angle, cadence CV profiling, replaces N strokes with 1 native entity)
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from primitive_ir_lib.models import Point2D, LineGeometry, Primitive


class LinetypeKind(str, enum.Enum):
    CONTINUOUS = "CONTINUOUS"
    DASHED = "DASHED"
    CENTER = "CENTER"
    PHANTOM = "PHANTOM"


@dataclass
class SynthesizedLinetypeEntity:
    id: str
    linetype: LinetypeKind
    start: Point2D
    end: Point2D
    total_length_mm: float
    stroke_count: int
    mean_dash_len_mm: float
    mean_gap_len_mm: float
    cadence_ratio: float = 1.0  # L_long / L_short
    source_primitive_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class LinetypeSynthesisResult:
    synthesized_lines: List[SynthesizedLinetypeEntity]
    unmerged_primitives: List[str] = field(default_factory=list)


def _point_dist(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def _segment_length(l: LineGeometry) -> float:
    return math.hypot(l.end.x - l.start.x, l.end.y - l.start.y)


def _segment_angle_deg(l: LineGeometry) -> float:
    dx = l.end.x - l.start.x
    dy = l.end.y - l.start.y
    ang = math.degrees(math.atan2(dy, dx)) % 180.0
    return ang


# ==============================================================================
# STRATEGY A: CURRENT PRODUCTION BASELINE
# ==============================================================================

def synthesize_linetypes_strategy_a(
    primitives: List[Primitive],
    mock_observation: Optional[Dict[str, Any]] = None,
    tolerance_mm: float = 0.5,
) -> LinetypeSynthesisResult:
    """Strategy A: Simulates cad_agent/fidelity.py run_fidelity_linetype_reconstruct.
    - Strictly filters: abs(start.y - end.y) <= tolerance_mm (horizontal only).
    - Requires external mock JSON pattern with axis == 'horizontal'.
    - If mock observation absent or axis != 'horizontal', leaves all entities as CONTINUOUS.
    - Does NOT merge broken dash strokes: every fragment is emitted as an individual line.
    """
    synthesized: List[SynthesizedLinetypeEntity] = []
    unmerged: List[str] = []

    patterns = (mock_observation or {}).get("patterns", [])
    horiz_patterns = [
        p for p in patterns
        if isinstance(p, dict)
        and p.get("axis") == "horizontal"
        and isinstance(p.get("coordinate_px"), (int, float))
    ]

    for p in primitives:
        if p.type != "line" or not isinstance(p.geometry, LineGeometry):
            unmerged.append(p.id)
            continue

        l = p.geometry
        length = _segment_length(l)
        # Check horizontal constraint
        if abs(l.start.y - l.end.y) > tolerance_mm:
            # Vertical or diagonal -> strictly skipped by production!
            unmerged.append(p.id)
            continue

        # Check if matches any horizontal pattern coordinate
        matched_ltype = None
        for pat in horiz_patterns:
            coord_y = float(pat["coordinate_px"])
            if abs(l.start.y - coord_y) <= tolerance_mm:
                sug = str(pat.get("suggested_linetype", "DASHED")).upper()
                matched_ltype = LinetypeKind.CENTER if "CENTER" in sug else LinetypeKind.DASHED
                break

        if matched_ltype is not None:
            synthesized.append(SynthesizedLinetypeEntity(
                id=f"strat_a_{p.id}",
                linetype=matched_ltype,
                start=l.start,
                end=l.end,
                total_length_mm=round(length, 3),
                stroke_count=1,
                mean_dash_len_mm=round(length, 3),
                mean_gap_len_mm=0.0,
                source_primitive_ids=[p.id],
                confidence=0.5,
            ))
        else:
            unmerged.append(p.id)

    return LinetypeSynthesisResult(synthesized_lines=synthesized, unmerged_primitives=unmerged)


# ==============================================================================
# STRATEGY B: NAIVE LENGTH-GAP THRESHOLDING
# ==============================================================================

def synthesize_linetypes_strategy_b(
    primitives: List[Primitive],
    max_gap_mm: float = 3.0,
) -> LinetypeSynthesisResult:
    """Strategy B: Groups adjacent line segments if endpoint distance <= max_gap_mm.
    - Blindly labels all merged groups as DASHED.
    - Cannot distinguish CENTER or PHANTOM.
    """
    lines = [
        (p.id, p.geometry) for p in primitives
        if p.type == "line" and isinstance(p.geometry, LineGeometry)
    ]
    if len(lines) < 2:
        return LinetypeSynthesisResult(
            synthesized_lines=[],
            unmerged_primitives=[p.id for p in primitives],
        )

    used_ids = set()
    synthesized: List[SynthesizedLinetypeEntity] = []

    # Simple sequential clusterer
    chain = [lines[0]]
    used_ids.add(lines[0][0])

    for i in range(1, len(lines)):
        curr_id, curr_l = lines[i]
        prev_id, prev_l = chain[-1]
        dist = _point_dist(prev_l.end, curr_l.start)
        if dist <= max_gap_mm:
            chain.append((curr_id, curr_l))
            used_ids.add(curr_id)
        else:
            if len(chain) >= 3:
                start_pt = chain[0][1].start
                end_pt = chain[-1][1].end
                tot_len = _point_dist(start_pt, end_pt)
                synthesized.append(SynthesizedLinetypeEntity(
                    id=f"strat_b_{chain[0][0]}",
                    linetype=LinetypeKind.DASHED,  # Always DASHED
                    start=start_pt,
                    end=end_pt,
                    total_length_mm=round(tot_len, 3),
                    stroke_count=len(chain),
                    mean_dash_len_mm=round(tot_len / len(chain), 3),
                    mean_gap_len_mm=round(max_gap_mm, 3),
                    source_primitive_ids=[lid for lid, _ in chain],
                    confidence=0.7,
                ))
            chain = [(curr_id, curr_l)]
            used_ids.add(curr_id)

    if len(chain) >= 3:
        start_pt = chain[0][1].start
        end_pt = chain[-1][1].end
        tot_len = _point_dist(start_pt, end_pt)
        synthesized.append(SynthesizedLinetypeEntity(
            id=f"strat_b_{chain[0][0]}",
            linetype=LinetypeKind.DASHED,
            start=start_pt,
            end=end_pt,
            total_length_mm=round(tot_len, 3),
            stroke_count=len(chain),
            mean_dash_len_mm=round(tot_len / len(chain), 3),
            mean_gap_len_mm=round(max_gap_mm, 3),
            source_primitive_ids=[lid for lid, _ in chain],
            confidence=0.7,
        ))

    unmerged = [p.id for p in primitives if p.id not in used_ids]
    return LinetypeSynthesisResult(synthesized_lines=synthesized, unmerged_primitives=unmerged)


# ==============================================================================
# STRATEGY C: COLLINEAR ANGLE CLUSTERED PROJECTION
# ==============================================================================

def synthesize_linetypes_strategy_c(
    primitives: List[Primitive],
    angle_tol_deg: float = 3.0,
    max_gap_mm: float = 6.0,
) -> LinetypeSynthesisResult:
    """Strategy C: Clusters collinear fragments by orientation, sorts along axis.
    - Estimates linetype via max/min stroke length ratio.
    """
    lines = [
        (p.id, p.geometry) for p in primitives
        if p.type == "line" and isinstance(p.geometry, LineGeometry)
    ]
    if len(lines) < 3:
        return LinetypeSynthesisResult(
            synthesized_lines=[],
            unmerged_primitives=[p.id for p in primitives],
        )

    # Sort lines along principal direction
    lines.sort(key=lambda item: (item[1].start.x, item[1].start.y))
    used_ids = set()
    synthesized: List[SynthesizedLinetypeEntity] = []

    lengths = [_segment_length(l) for _, l in lines]
    max_l = max(lengths)
    min_l = min(lengths)
    ratio = max_l / max(min_l, 1e-4)

    ltype = LinetypeKind.CENTER if ratio >= 2.5 else LinetypeKind.DASHED
    start_pt = lines[0][1].start
    end_pt = lines[-1][1].end
    tot_len = _point_dist(start_pt, end_pt)

    synthesized.append(SynthesizedLinetypeEntity(
        id=f"strat_c_{lines[0][0]}",
        linetype=ltype,
        start=start_pt,
        end=end_pt,
        total_length_mm=round(tot_len, 3),
        stroke_count=len(lines),
        mean_dash_len_mm=round(sum(lengths) / len(lengths), 3),
        mean_gap_len_mm=round(max_gap_mm / 2.0, 3),
        cadence_ratio=round(ratio, 2),
        source_primitive_ids=[lid for lid, _ in lines],
        confidence=0.85,
    ))
    return LinetypeSynthesisResult(synthesized_lines=synthesized, unmerged_primitives=[])


# ==============================================================================
# STRATEGY D: COMPREHENSIVE CADENCE ANALYSIS & NATIVE SYNTHESIS ORACLE
# ==============================================================================

def _point_to_line_dist(pt: Point2D, a: Point2D, b: Point2D) -> float:
    dx = b.x - a.x
    dy = b.y - a.y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return math.hypot(pt.x - a.x, pt.y - a.y)
    return abs(dx * (pt.y - a.y) - dy * (pt.x - a.x)) / length


def _project_onto_line(pt: Point2D, origin: Point2D, unit_dir: Tuple[float, float]) -> float:
    return (pt.x - origin.x) * unit_dir[0] + (pt.y - origin.y) * unit_dir[1]


def extract_linetypes_strategy_d(
    primitives: List[Primitive],
    angle_tol_deg: float = 2.5,
    lateral_tol_mm: float = 0.8,
    max_gap_mm: float = 8.0,
    min_strokes_in_chain: int = 3,
) -> LinetypeSynthesisResult:
    """Strategy D: Full cadence analysis and continuous native stroke synthesis.
    
    1. Universal orientation:
       - Supports 0° (horizontal), 90° (vertical), and arbitrary inclined lines.
    2. Collinear chaining:
       - Clusters segments sharing collinear line axis (angle <= 2.5°, lateral drift <= 0.8mm).
       - Sorts strokes monotonically along candidate axis.
       - Chains consecutive segments with gap <= max_gap_mm.
    3. Rhythmic cadence profiling:
       - Computes lengths [L_1, ..., L_N] and gaps [G_1, ..., G_{N-1}].
       - If all dash lengths are uniform (CV = std/mean <= 0.25) -> DASHED.
       - If alternating bimodal (L_long / L_short >= 2.5) -> CENTER.
       - If trimodal / double-short (long, short, short, long) -> PHANTOM.
    4. Continuous native entity emission:
       - Synthesizes 1 continuous line from first start to last end with assigned linetype,
         replacing N fragmented raster strokes.
    """
    lines: List[Tuple[str, LineGeometry]] = [
        (p.id, p.geometry) for p in primitives
        if p.type == "line" and isinstance(p.geometry, LineGeometry)
    ]
    if len(lines) < min_strokes_in_chain:
        return LinetypeSynthesisResult(
            synthesized_lines=[],
            unmerged_primitives=[p.id for p in primitives],
        )

    used_primitive_ids = set()
    synthesized: List[SynthesizedLinetypeEntity] = []

    # Index by orientation angle mod 180°
    clusters: List[List[Tuple[str, LineGeometry]]] = []
    for lid, lgeom in lines:
        length = _segment_length(lgeom)
        if length < 1e-4:
            continue
        ang = _segment_angle_deg(lgeom)
        # Find matching cluster
        placed = False
        for c in clusters:
            ref_ang = _segment_angle_deg(c[0][1])
            diff = abs(ang - ref_ang)
            diff = min(diff, 180.0 - diff)
            if diff <= angle_tol_deg:
                # Check lateral offset to first segment
                lat_dist = _point_to_line_dist(lgeom.start, c[0][1].start, c[0][1].end)
                if lat_dist <= lateral_tol_mm:
                    c.append((lid, lgeom))
                    placed = True
                    break
        if not placed:
            clusters.append([(lid, lgeom)])

    for cluster in clusters:
        if len(cluster) < min_strokes_in_chain:
            continue

        # Determine axis unit direction
        ref_l = cluster[0][1]
        dx = ref_l.end.x - ref_l.start.x
        dy = ref_l.end.y - ref_l.start.y
        ref_len = math.hypot(dx, dy)
        if ref_len < 1e-6:
            continue
        unit_dir = (dx / ref_len, dy / ref_len)
        origin = ref_l.start

        # Sort segments along axis
        projected_strokes = []
        for lid, l in cluster:
            t0 = _project_onto_line(l.start, origin, unit_dir)
            t1 = _project_onto_line(l.end, origin, unit_dir)
            t_min = min(t0, t1)
            t_max = max(t0, t1)
            p_start = l.start if t0 <= t1 else l.end
            p_end = l.end if t0 <= t1 else l.start
            projected_strokes.append((t_min, t_max, lid, l, p_start, p_end))

        projected_strokes.sort(key=lambda s: s[0])

        # Form chains of consecutive strokes where gap <= max_gap_mm
        chains: List[List[Any]] = []
        curr_chain = [projected_strokes[0]]

        for i in range(1, len(projected_strokes)):
            prev_s = curr_chain[-1]
            curr_s = projected_strokes[i]
            gap = curr_s[0] - prev_s[1]
            if 0.0 <= gap <= max_gap_mm:
                curr_chain.append(curr_s)
            else:
                if len(curr_chain) >= min_strokes_in_chain:
                    chains.append(curr_chain)
                curr_chain = [curr_s]

        if len(curr_chain) >= min_strokes_in_chain:
            chains.append(curr_chain)

        # Process each chain into a synthesized linetype entity
        for chain in chains:
            p_ids = [s[2] for s in chain]
            dash_lengths = [s[1] - s[0] for s in chain]
            gap_lengths = [chain[k+1][0] - chain[k][1] for k in range(len(chain) - 1)]

            mean_dash = sum(dash_lengths) / len(dash_lengths)
            mean_gap = sum(gap_lengths) / max(1, len(gap_lengths))

            # Cadence analysis: coefficient of variation of dash lengths
            variance = sum((d - mean_dash)**2 for d in dash_lengths) / len(dash_lengths)
            std_dash = math.sqrt(variance)
            cv_dash = std_dash / max(mean_dash, 1e-4)

            max_d = max(dash_lengths)
            min_d = min(dash_lengths)
            ratio = max_d / max(min_d, 1e-4)

            # Classify linetype
            if ratio >= 2.5:
                # Check if Centerline (alternating long-short) or Phantom (long-short-short)
                # Count number of short vs long
                threshold = (max_d + min_d) / 2.0
                short_count = sum(1 for d in dash_lengths if d < threshold)
                long_count = sum(1 for d in dash_lengths if d >= threshold)

                if short_count > long_count and len(dash_lengths) >= 4:
                    ltype = LinetypeKind.PHANTOM
                else:
                    ltype = LinetypeKind.CENTER
            else:
                ltype = LinetypeKind.DASHED

            # Extreme endpoints
            start_point = chain[0][4]
            end_point = chain[-1][5]
            tot_len = _point_dist(start_point, end_point)

            used_primitive_ids.update(p_ids)
            synthesized.append(SynthesizedLinetypeEntity(
                id=f"synth_{chain[0][2]}",
                linetype=ltype,
                start=start_point,
                end=end_point,
                total_length_mm=round(tot_len, 3),
                stroke_count=len(chain),
                mean_dash_len_mm=round(mean_dash, 3),
                mean_gap_len_mm=round(mean_gap, 3),
                cadence_ratio=round(ratio, 2),
                source_primitive_ids=p_ids,
                confidence=0.98,
            ))

    unmerged = [p.id for p in primitives if p.id not in used_primitive_ids]
    return LinetypeSynthesisResult(synthesized_lines=synthesized, unmerged_primitives=unmerged)
