"""Deterministic multi-oracle cross-view consistency verifier for ship lines plans.

Pure Python (stdlib-only) consumer contract: inspects pre-extracted lines, curves,
texts, view regions, and optional dimension/grid records across Sheer, Half-Breadth,
and Body Plan views. Fails closed on unitless (``$INSUNITS=0``) or zero-curve plans
so uncalibrated drawings or zero-pair comparisons never emit ``PASS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Sequence
import unicodedata


_SUPPORTED_METRIC_INSUNITS = frozenset({4, 5, 6})  # 4=mm, 5=cm, 6=m

_INLINE_DIM_RE = re.compile(
    r"\b(lpp|loa|lmax|ltk|l|bmax|b|d_mld|d|t)\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\b"
)
_FRAME_A_RE = re.compile(r"\ba\s*=\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)\b")
_SCALE_RE = re.compile(r"\b(?:t[iy]\s*le|scale)\s*[:=]?\s*1\s*:\s*([0-9]+)\b")
_QCVN_RE = re.compile(r"(qcvn\s*\d+(?:\s*:\s*\d+)?(?:/bgtvt)?)", re.IGNORECASE)
_GRADE_RE = re.compile(r"\b(vr-[a-z0-9-]+)\b", re.IGNORECASE)
_TABULAR_VAL_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?")
_BASE_LABEL_RE = re.compile(r"\b(?:base|d\.?\s*chuan|dcb|wl\s*0|dn\s*0)\b")
_DATUM_LABEL_RE = re.compile(
    r"\b(?:wl|dn|st|sn|cd|bt|cl|mpdx|base|b\.?\s*line|d\.?\s*chuan|dcb|dntk|suon|duong\s*nuoc|doc\s*doc)\s*\d*\b",
    re.IGNORECASE,
)


def _fold_text(text: str) -> str:
    stripped = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", stripped)
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_only.lower()).strip()


def _bbox_from_points(points: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _dist_to_bbox(px: float, py: float, bbox: tuple[float, float, float, float]) -> float:
    dx = max(bbox[0] - px, 0.0, px - bbox[2])
    dy = max(bbox[1] - py, 0.0, py - bbox[3])
    return math.hypot(dx, dy)


@dataclass(frozen=True)
class LinesViewRegion:
    """View bounding box (typically ``sheer``, ``half_breadth``, or ``body_plan``)."""

    view_type: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class LinesLine:
    """Straight line segment extracted from a CAD or IR view."""

    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = "0"
    is_dashed: bool = False

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (
            min(float(self.start[0]), float(self.end[0])),
            min(float(self.start[1]), float(self.end[1])),
            max(float(self.start[0]), float(self.end[0])),
            max(float(self.start[1]), float(self.end[1])),
        )

    def center(self) -> tuple[float, float]:
        return (
            0.5 * (float(self.start[0]) + float(self.end[0])),
            0.5 * (float(self.start[1]) + float(self.end[1])),
        )

    def width(self) -> float:
        return abs(float(self.end[0]) - float(self.start[0]))

    def height(self) -> float:
        return abs(float(self.end[1]) - float(self.start[1]))


@dataclass(frozen=True)
class LinesCurve:
    """Discretized curve or hull polyline inside a lines-plan view."""

    points: tuple[tuple[float, float], ...]
    layer: str = "0"
    is_dashed: bool = False

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return _bbox_from_points(self.points)

    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return (0.5 * (x0 + x1), 0.5 * (y0 + y1))

    def width(self) -> float:
        x0, _, x1, _ = self.bbox
        return max(0.0, x1 - x0)

    def height(self) -> float:
        _, y0, _, y1 = self.bbox
        return max(0.0, y1 - y0)


@dataclass(frozen=True)
class LinesText:
    """Text annotation or particular entry positioned on the lines plan."""

    text: str
    position: tuple[float, float]
    bbox: tuple[float, float, float, float] | None = None
    height: float = 0.0
    layer: str = "0"

    def center(self) -> tuple[float, float]:
        if self.bbox is not None:
            return (0.5 * (self.bbox[0] + self.bbox[2]), 0.5 * (self.bbox[1] + self.bbox[3]))
        return (float(self.position[0]), float(self.position[1]))


@dataclass(frozen=True)
class GridWaterlineLabel:
    """Waterline datum label anchored to a spatial point or bbox."""

    canonical_label: str
    bbox: tuple[float, float, float, float]


@dataclass
class CrossViewCheckResult:
    """Fail-closed result emitted by the marine lines-plan cross-view oracle."""

    status: str
    principal_dims_mm: dict[str, Any] = field(default_factory=dict)
    max_delta_mm: float | None = None
    discrepancies: list[str] = field(default_factory=list)


def _in_padded_bbox(
    center: tuple[float, float],
    bbox: tuple[float, float, float, float],
    pad_y: float = 0.0,
    pad_x: float | None = None,
) -> bool:
    px = pad_y if pad_x is None else pad_x
    cx, cy = center
    return (bbox[0] - px) <= cx <= (bbox[2] + px) and (bbox[1] - pad_y) <= cy <= (bbox[3] + pad_y)


def extract_declared_particulars(texts: Sequence[LinesText]) -> dict[str, Any]:
    """Parse explicit Principal Particulars (Lmax, Lpp, B, D, d/T, a, scale, QCVN, grade)."""
    parsed: dict[str, float] = {}
    meta: dict[str, Any] = {}
    key_tokens: list[tuple[str, LinesText]] = []

    for tp in texts:
        raw = tp.text.strip()
        if not raw:
            continue
        folded = _fold_text(raw)

        m_sc = _SCALE_RE.search(folded)
        if m_sc:
            meta["drawing_scale"] = float(m_sc.group(1))
        m_q = _QCVN_RE.search(raw)
        if m_q:
            meta["classification_standard"] = re.sub(r"\s+", " ", m_q.group(1).upper()).replace(" :", ":")
        m_g = _GRADE_RE.search(raw)
        if m_g:
            meta["ship_grade"] = m_g.group(1).upper()
        m_fa = _FRAME_A_RE.search(folded)
        if m_fa:
            val = float(m_fa.group(1).replace(",", "."))
            parsed["frame_spacing_a"] = val * 1000.0 if m_fa.group(2) == "m" else val

        for m in _INLINE_DIM_RE.finditer(folded):
            key = m.group(1).upper()
            val = float(m.group(2).replace(",", "."))
            unit = m.group(3) or ("m" if val < 400.0 else "mm")
            mm_val = val * 1000.0 if unit == "m" else val
            norm_key = {
                "LPP": "Lpp",
                "LOA": "Loa",
                "LMAX": "Lmax",
                "LTK": "L",
                "L": "L",
                "BMAX": "Bmax",
                "B": "B",
                "D_MLD": "D",
                "D": "D",
                "T": "T",
            }.get(key, key)
            if (
                key == "D"
                and re.search(r"(?<![A-Za-z])d\s*[:=]", raw)
                and not re.search(r"(?<![A-Za-z])D\s*[:=]", raw)
            ):
                norm_key = "d"
            parsed[norm_key] = mm_val

        if raw in ("Lmax", "L", "Lpp", "Loa", "Bmax", "B", "D", "d", "T"):
            key_tokens.append((raw, tp))

    # Tabular row-aligned Key -> Value fallback common in CAD title/spec blocks
    for key_name, ktp in key_tokens:
        kx, ky = float(ktp.position[0]), float(ktp.position[1])
        kh = max(float(ktp.height), 200.0)
        row_tol = max(kh * 0.9, 150.0) if kh > 20.0 else max(kh * 1.2, 8.0)
        candidates: list[tuple[float, float]] = []
        for vtp in texts:
            if vtp is ktp:
                continue
            vx, vy = float(vtp.position[0]), float(vtp.position[1])
            if vx <= kx or abs(vy - ky) > row_tol:
                continue
            m_val = _TABULAR_VAL_RE.fullmatch(_fold_text(vtp.text))
            if m_val:
                val = float(m_val.group(1).replace(",", "."))
                unit = m_val.group(2) or ("m" if val < 400.0 else "mm")
                candidates.append((vx - kx, val * 1000.0 if unit == "m" else val))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            if candidates[0][0] <= max(kh * 25.0, 12000.0):
                parsed.setdefault(key_name, candidates[0][1])

    out: dict[str, Any] = dict(parsed)
    out.update(meta)
    return out


def check_grid_label_cross_view_consistency(
    grid_labels: Sequence[GridWaterlineLabel],
    view_regions: Sequence[LinesViewRegion],
    *,
    proximity_tol: float = 30.0,
) -> CrossViewCheckResult | None:
    """Detect numeric waterline grid label mismatches across distinct views (e.g., 4500 vs 4575)."""
    if len(view_regions) < 2 or not grid_labels:
        return None
    region_sets: dict[int, set[int]] = {i: set() for i in range(len(view_regions))}

    for lbl in grid_labels:
        m = re.search(r"(\d{3,5})", lbl.canonical_label)
        if not m:
            continue
        val = int(m.group(1))
        if val <= 0:
            continue
        ecx = 0.5 * (lbl.bbox[0] + lbl.bbox[2])
        ecy = 0.5 * (lbl.bbox[1] + lbl.bbox[3])
        best_i: int | None = None
        best_d = 1e9
        for i, vr in enumerate(view_regions):
            d = _dist_to_bbox(ecx, ecy, vr.bbox)
            if d < best_d and d <= proximity_tol:
                best_d = d
                best_i = i
        if best_i is not None:
            region_sets[best_i].add(val)

    view_wl_nums: dict[str, list[int]] = {}
    for i, vr in enumerate(view_regions):
        if len(region_sets[i]) >= 2:
            view_wl_nums[vr.view_type] = sorted(region_sets[i])

    if len(view_wl_nums) >= 2:
        views = list(view_wl_nums)
        base_set = view_wl_nums[views[0]]
        for other in views[1:]:
            other_set = view_wl_nums[other]
            if len(base_set) == len(other_set):
                diffs = [abs(a - b) for a, b in zip(base_set, other_set)]
                significant = [d for d in diffs if d >= 15]
                if significant:
                    return CrossViewCheckResult(
                        status="CONFLICT_DETECTED",
                        max_delta_mm=float(max(significant)),
                        discrepancies=[
                            f"{views[0]} waterlines {base_set} != {other} waterlines {other_set} (max_delta={max(significant)}mm)"
                        ],
                    )
    return None


def _sample_hb_half_breadths(
    hb_curves: Sequence[LinesCurve],
    hb_cl_y: float,
    x_min: float,
    x_max: float,
) -> tuple[list[float], list[float], float]:
    """Measure Half-Breadth half-widths at midship and across parallel-middle-body split curves."""
    span = max(1.0, x_max - x_min)
    sample_fracs = (0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85)
    sample_xs = [x_min + f * span for f in sample_fracs]

    mid_lo = x_min + 0.28 * span
    mid_hi = x_min + 0.72 * span
    core_curves = [c for c in hb_curves if c.bbox[0] <= mid_hi and c.bbox[2] >= mid_lo]
    active_curves = core_curves if len(core_curves) >= 4 else hb_curves

    all_max_ys: list[float] = []
    at_x: dict[float, list[float]] = {sx: [] for sx in sample_xs}
    for c in active_curves:
        pts = sorted(c.points, key=lambda pt: pt[0])
        ys_off = [abs(pt[1] - hb_cl_y) for pt in pts]
        if ys_off:
            all_max_ys.append(max(ys_off))
        for sx in sample_xs:
            for i in range(len(pts) - 1):
                if pts[i][0] <= sx <= pts[i + 1][0]:
                    t = (sx - pts[i][0]) / max(1e-9, pts[i + 1][0] - pts[i][0])
                    y_val = pts[i][1] + t * (pts[i + 1][1] - pts[i][1])
                    at_x[sx].append(abs(y_val - hb_cl_y))
                    break

    mid_vals = sorted(at_x[sample_xs[3]])
    if len(mid_vals) < 4:
        sorted_max = sorted(y for y in all_max_ys if y > 1e-3)
        deduped: list[float] = []
        tol = max(0.05, 0.008 * (sorted_max[-1] if sorted_max else 1.0))
        for val in sorted_max:
            if not deduped or abs(val - deduped[-1]) > tol:
                deduped.append(val)
        return deduped, mid_vals, (max(sorted_max) if sorted_max else 0.0)
    return mid_vals, mid_vals, (max(all_max_ys) if all_max_ys else 0.0)


def _has_calibrated_datum_labels(texts: Sequence[LinesText]) -> bool:
    return any(_DATUM_LABEL_RE.search(_fold_text(t.text)) for t in texts)


def _unit_multiplier(insunits: int, max_raw_dim: float) -> float:
    if insunits == 4:
        return 1.0
    if insunits == 5:
        return 10.0 if (0.0 < max_raw_dim < 40000.0) else 1.0
    return 1000.0 if (0.0 < max_raw_dim < 400.0) else 1.0


def verify_lines_plan_cross_view(
    view_regions: Sequence[LinesViewRegion],
    lines: Sequence[LinesLine],
    curves: Sequence[LinesCurve],
    texts: Sequence[LinesText],
    *,
    insunits: int = 0,
    dim_records: Sequence[dict[str, Any]] | None = None,
    grid_labels: Sequence[GridWaterlineLabel] | None = None,
) -> CrossViewCheckResult:
    """Verify multi-view lines-plan consistency across Sheer, Half-Breadth, and Body Plan views."""
    hb_region = next((r for r in view_regions if r.view_type == "half_breadth"), None)
    bp_region = next((r for r in view_regions if r.view_type == "body_plan"), None)
    sh_region = next((r for r in view_regions if r.view_type == "sheer"), None)

    declared = extract_declared_particulars(texts)
    discrepancies: list[str] = []
    principal: dict[str, Any] = {}
    if declared.get("Lpp"):
        principal["Declared_Lpp"] = round(float(declared["Lpp"]), 1)
    if declared.get("B"):
        principal["Declared_B"] = round(float(declared["B"]), 1)
    if declared.get("D"):
        principal["Declared_D"] = round(float(declared["D"]), 1)

    if dim_records:
        for dr in dim_records:
            meas = dr.get("measurement")
            dtxt = str(dr.get("dim_text") or "").strip()
            if meas and dtxt:
                try:
                    d_num = float(dtxt.replace(",", "."))
                except ValueError:
                    continue
                if d_num > 0.0 and float(meas) > 0.0:
                    r_scale = float(meas) / d_num
                    if 0.5 <= r_scale <= 1.5 and abs(r_scale - 1.0) >= 0.025:
                        principal["Dim_Scale_Discrepancy_Ratio"] = round(r_scale, 5)
                        break

    grid_conflict = check_grid_label_cross_view_consistency(grid_labels or (), view_regions)

    if not (hb_region and bp_region):
        if grid_conflict is not None:
            return grid_conflict
        if sh_region and hb_region:
            sh_pad = max(2.0, 0.08 * (sh_region.bbox[3] - sh_region.bbox[1]))
            hb_pad = max(2.0, 0.08 * (hb_region.bbox[3] - hb_region.bbox[1]))
            sh_c = [c for c in curves if _in_padded_bbox(c.center(), sh_region.bbox, pad_y=sh_pad)]
            hb_c = [c for c in curves if _in_padded_bbox(c.center(), hb_region.bbox, pad_y=hb_pad)]
            if sh_c and hb_c:
                sh_xs = [pt[0] for c in sh_c for pt in c.points]
                hb_xs = [pt[0] for c in hb_c for pt in c.points]
                sh_span = max(sh_xs) - min(sh_xs)
                hb_span = max(hb_xs) - min(hb_xs)
                u_mult = _unit_multiplier(insunits, max(sh_span, hb_span))
                l_delta = abs(sh_span - hb_span) * u_mult
                principal["Sheer_Lpp_mm"] = round(sh_span * u_mult, 1)
                principal["HB_Lpp_mm"] = round(hb_span * u_mult, 1)
                if l_delta > max(50.0, 0.03 * max(sh_span, hb_span) * u_mult):
                    return CrossViewCheckResult(
                        status="CONFLICT_DETECTED",
                        principal_dims_mm=principal,
                        max_delta_mm=round(l_delta, 2),
                        discrepancies=[
                            f"LPP_CROSS_VIEW_MISMATCH: Sheer Lpp={sh_span * u_mult:.1f}mm vs Half-Breadth Lpp={hb_span * u_mult:.1f}mm (delta={l_delta:.1f}mm)"
                        ],
                    )
        return CrossViewCheckResult(
            status="NOT_APPLICABLE" if len(view_regions) <= 1 else "NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
        )

    hb_h = max(1e-6, hb_region.bbox[3] - hb_region.bbox[1])
    hb_w = max(1e-6, hb_region.bbox[2] - hb_region.bbox[0])
    bp_h = max(1e-6, bp_region.bbox[3] - bp_region.bbox[1])
    bp_w = max(1e-6, bp_region.bbox[2] - bp_region.bbox[0])

    hb_lines = [ln for ln in lines if _in_padded_bbox(ln.center(), hb_region.bbox, pad_y=max(2.0, 0.08 * hb_h))]
    bp_lines = [ln for ln in lines if _in_padded_bbox(ln.center(), bp_region.bbox, pad_y=max(2.0, 0.08 * bp_h))]
    sh_lines = (
        [
            ln
            for ln in lines
            if _in_padded_bbox(
                ln.center(),
                sh_region.bbox,
                pad_y=max(2.0, 0.08 * (sh_region.bbox[3] - sh_region.bbox[1])),
            )
        ]
        if sh_region
        else []
    )

    hb_curves = [
        c
        for c in curves
        if _in_padded_bbox(c.center(), hb_region.bbox, pad_y=max(2.0, 0.08 * hb_h))
        and c.width() > 0.12 * hb_w
        and len(c.points) >= 4
    ]
    bp_curves = [
        c
        for c in curves
        if _in_padded_bbox(c.center(), bp_region.bbox, pad_y=max(2.0, 0.08 * bp_h))
        and len(c.points) >= 3
    ]
    if not hb_curves or not bp_curves:
        if grid_conflict is not None:
            return grid_conflict
        return CrossViewCheckResult(
            status="INSUFFICIENT_GEOMETRY",
            principal_dims_mm=principal,
            max_delta_mm=None,
            discrepancies=["NO_CURVED_HULL_GEOMETRY_ZERO_PAIRS_COMPARED"],
        )

    hb_pad = max(10.0, 0.28 * hb_h)
    bp_pad = max(10.0, 0.28 * bp_h)
    hb_texts = [
        tp
        for tp in texts
        if _in_padded_bbox(tp.center(), hb_region.bbox, pad_y=hb_pad, pad_x=max(hb_pad, 0.05 * hb_w))
    ]
    bp_texts = [
        tp
        for tp in texts
        if _in_padded_bbox(tp.center(), bp_region.bbox, pad_y=bp_pad, pad_x=max(bp_pad, 0.05 * bp_w))
    ]
    if not hb_texts or not bp_texts:
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            discrepancies=["MISSING_CALIBRATED_VIEW_LABELS"],
        )

    # Half-Breadth centerline & longitudinal station extent
    hb_cl_lines = [
        ln
        for ln in hb_lines
        if abs(ln.bbox[3] - ln.bbox[1]) < 0.01 * hb_h and ("cl" in _fold_text(ln.layer) or ln.is_dashed)
    ]
    hb_cl_y = min(ln.bbox[1] for ln in hb_cl_lines) if hb_cl_lines else hb_region.bbox[1]
    hb_stations = sorted(
        {
            round(ln.bbox[0], 3)
            for ln in hb_lines
            if abs(ln.bbox[2] - ln.bbox[0]) < 0.01 * hb_w and ln.height() > 0.20 * hb_h
        }
    )
    x_lo, x_hi = (hb_stations[0], hb_stations[-1]) if len(hb_stations) >= 2 else (hb_region.bbox[0], hb_region.bbox[2])
    lpp_raw = x_hi - x_lo

    # Body Plan centerline & waterline datum heights
    bp_curve_xs = [pt[0] for c in bp_curves for pt in c.points]
    bp_curve_mid_x = 0.5 * (min(bp_curve_xs) + max(bp_curve_xs))
    bp_vert_lines = [
        ln
        for ln in bp_lines
        if abs(ln.bbox[2] - ln.bbox[0]) < 0.01 * bp_w and ln.height() > 0.45 * bp_h
    ]
    bp_cl_priority = [ln for ln in bp_vert_lines if "cl" in _fold_text(ln.layer) or ln.is_dashed]
    pool_cl = bp_cl_priority or bp_vert_lines
    bp_cl_x = (
        min(pool_cl, key=lambda ln: (abs(ln.center()[0] - bp_curve_mid_x), -ln.height())).center()[0]
        if pool_cl
        else bp_curve_mid_x
    )

    bp_wl_ys = sorted(
        {
            round(ln.bbox[1], 3)
            for ln in bp_lines
            if abs(ln.bbox[3] - ln.bbox[1]) < 0.01 * bp_h and ln.width() > 0.25 * bp_w
        }
    )
    if len(bp_wl_ys) < 2:
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            discrepancies=["INSUFFICIENT_BODY_PLAN_WATERLINES"],
        )

    hb_widths, mid_direct, max_all_hb = _sample_hb_half_breadths(hb_curves, hb_cl_y, x_lo, x_hi)
    hb_max = max(max_all_hb, max(hb_widths) if hb_widths else 0.0)

    bp_wl_max_ys: list[float] = []
    for wz in bp_wl_ys[1:]:
        xs_at_wz: list[float] = []
        for c in bp_curves:
            for i in range(len(c.points) - 1):
                y0, y1 = c.points[i][1], c.points[i + 1][1]
                if (y0 <= wz <= y1) or (y1 <= wz <= y0):
                    x_at = (
                        c.points[i][0]
                        if abs(y1 - y0) < 1e-9
                        else c.points[i][0] + ((wz - y0) / (y1 - y0)) * (c.points[i + 1][0] - c.points[i][0])
                    )
                    xs_at_wz.append(abs(x_at - bp_cl_x))
        if xs_at_wz:
            bp_wl_max_ys.append(max(xs_at_wz))
    bp_max = max(bp_wl_max_ys) if bp_wl_max_ys else 0.0

    if hb_max > 0.0 and bp_max > 0.0:
        ratio = max(hb_max, bp_max) / max(1e-6, min(hb_max, bp_max))
        if ratio >= 100.0:
            discrepancies.append(
                f"UNIT_MISMATCH_1000X: Half-Breadth max={hb_max:.3f} vs Body Plan max={bp_max:.3f} (ratio={ratio:.1f}x)"
            )

    unit_mult = _unit_multiplier(insunits, max(lpp_raw, bp_max, hb_max))
    if declared.get("B") and bp_max > 0.0:
        decl_half_b = 0.5 * float(declared["B"])
        if 500.0 <= decl_half_b / max(1e-6, bp_max) <= 2000.0:
            discrepancies.append(
                f"UNIT_MISMATCH_1000X: Declared B/2={decl_half_b:.1f}mm vs drawing half-breadth={bp_max:.3f}"
            )

    lpp_mm = lpp_raw * unit_mult
    hb_max_mm = hb_max * unit_mult
    bp_max_mm = bp_max * unit_mult
    draft_mm = (max(bp_wl_ys) - min(bp_wl_ys)) * unit_mult
    principal.update(
        {
            "Lpp": round(lpp_mm, 1),
            "HalfBreadthMax": round(max(hb_max_mm, bp_max_mm), 1),
            "Draft_DNTK": round(draft_mm, 1),
        }
    )

    hb_mm_list = sorted(v * unit_mult for v in hb_widths)
    bp_mm_list = [v * unit_mult for v in bp_wl_max_ys]
    n_pairs = min(len(hb_mm_list), len(bp_mm_list))
    if n_pairs < 2:
        if discrepancies:
            return CrossViewCheckResult(
                status="CONFLICT_DETECTED",
                principal_dims_mm=principal,
                max_delta_mm=round(abs(hb_max_mm - bp_max_mm), 2),
                discrepancies=discrepancies,
            )
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            discrepancies=["INSUFFICIENT_MATCHED_WATERLINE_PAIRS"],
        )

    max_delta = 0.0
    tol_mm = max(5.0, 0.015 * max(hb_max_mm, bp_max_mm))
    is_parallel_split_hull = len(mid_direct) < 4
    if not is_parallel_split_hull:
        pair_indices = (
            list(zip(hb_mm_list, bp_mm_list))
            if len(hb_mm_list) == len(bp_mm_list)
            else list(zip(hb_mm_list[-min(5, n_pairs) :], bp_mm_list[-min(5, n_pairs) :]))
        )
        for idx, (vhb, vbp) in enumerate(pair_indices):
            d = abs(vhb - vbp)
            max_delta = max(max_delta, d)
            if d > tol_mm:
                discrepancies.append(
                    f"WL_pair_{idx + 1}: Half-Breadth={vhb:.1f}mm vs Body Plan={vbp:.1f}mm (delta={d:.1f}mm)"
                )
    else:
        pair_indices = [(vhb, min(bp_mm_list, key=lambda vbp: abs(vbp - vhb))) for vhb in hb_mm_list[-5:]]
        for idx, (vhb, vbp) in enumerate(pair_indices):
            d = abs(vhb - vbp)
            max_delta = max(max_delta, d)
            if d > max(tol_mm, 0.03 * max(hb_max_mm, 1.0)):
                discrepancies.append(
                    f"Split_WL_{idx + 1}: Half-Breadth={vhb:.1f}mm vs nearest Body Plan WL={vbp:.1f}mm (delta={d:.1f}mm)"
                )

    env_delta = abs(hb_max_mm - bp_max_mm)
    max_delta = max(max_delta, env_delta)
    if env_delta > tol_mm:
        discrepancies.append(
            f"Max_HalfBreadth: Half-Breadth={hb_max_mm:.1f}mm vs Body Plan={bp_max_mm:.1f}mm (delta={env_delta:.1f}mm)"
        )

    if declared.get("B") and max(hb_max_mm, bp_max_mm) > 0.0 and not any("UNIT_MISMATCH" in d for d in discrepancies):
        decl_half_b = 0.5 * float(declared["B"])
        beam_err = abs(max(hb_max_mm, bp_max_mm) - decl_half_b)
        max_delta = max(max_delta, beam_err)
        if beam_err > max(30.0, 0.025 * decl_half_b):
            discrepancies.append(
                f"BEAM_BOUND_MISMATCH: Measured max half-breadth={max(hb_max_mm, bp_max_mm):.1f}mm disagrees with declared B/2={decl_half_b:.1f}mm (delta={beam_err:.1f}mm)"
            )

    decl_l_val = declared.get("Lpp") or (
        (declared.get("L") or declared.get("Lmax") or declared.get("Loa")) if declared.get("drawing_scale") else None
    )
    if decl_l_val and lpp_mm > 0.0 and not any("UNIT_MISMATCH" in d for d in discrepancies):
        decl_l = float(decl_l_val)
        lpp_err = abs(lpp_mm - decl_l)
        max_delta = max(max_delta, lpp_err)
        scale_val = float(declared.get("drawing_scale") or 0.0)
        if scale_val > 1.0 and abs((decl_l / max(1e-6, lpp_mm)) - scale_val) <= 0.15 * scale_val:
            discrepancies.append(
                f"TITLE_BLOCK_SCALE_DISCREPANCY: Modelspan Lpp={lpp_mm:.1f}mm appears scaled 1:{int(scale_val)} vs declared L={decl_l:.1f}mm"
            )
        elif lpp_err > max(50.0, 0.03 * decl_l):
            discrepancies.append(
                f"LPP_BOUND_MISMATCH: Measured Lpp={lpp_mm:.1f}mm disagrees with declared L={decl_l:.1f}mm (delta={lpp_err:.1f}mm)"
            )

    bp_curve_min_y = min(pt[1] for c in bp_curves for pt in c.points)
    bp_base_labels = [tp for tp in bp_texts if _BASE_LABEL_RE.search(_fold_text(tp.text))]
    bp_base_line_y = bp_wl_ys[0]
    if bp_base_labels:
        lbl_y = bp_base_labels[0].center()[1]
        bp_base_line_y = min(bp_wl_ys, key=lambda y: abs(y - lbl_y))
    keel_shift_mm = abs(bp_curve_min_y - bp_base_line_y) * unit_mult
    if keel_shift_mm > max(40.0, 0.03 * max(1.0, draft_mm)):
        max_delta = max(max_delta, keel_shift_mm)
        discrepancies.append(f"BASELINE_MISMATCH: Body Plan keel offset {keel_shift_mm:.1f}mm from BASE line")

    if sh_lines and sh_region is not None:
        sh_w = max(1e-6, sh_region.bbox[2] - sh_region.bbox[0])
        sh_h = max(1.0, sh_region.bbox[3] - sh_region.bbox[1])
        sh_wl_ys = sorted(
            {
                round(ln.bbox[1], 3)
                for ln in sh_lines
                if abs(ln.bbox[3] - ln.bbox[1]) < 0.01 * sh_h and ln.width() > 0.25 * sh_w
            }
        )
        if sh_wl_ys and len(bp_wl_ys) >= 2 and abs(bp_region.bbox[1] - sh_region.bbox[1]) < 0.4 * max(bp_h, sh_h):
            base_diff_mm = abs(bp_base_line_y - sh_wl_ys[0]) * unit_mult
            if base_diff_mm > max(40.0, 0.03 * max(1.0, draft_mm)):
                max_delta = max(max_delta, base_diff_mm)
                discrepancies.append(
                    f"BASELINE_MISMATCH: Body Plan BASE Y={bp_base_line_y:.1f} vs Sheer BASE Y={sh_wl_ys[0]:.1f} (delta={base_diff_mm:.1f}mm)"
                )

    if grid_conflict is not None:
        max_delta = max(max_delta, float(grid_conflict.max_delta_mm or 0.0))
        discrepancies.extend(grid_conflict.discrepancies)

    principal["Pairs_Compared"] = len(pair_indices)
    if discrepancies:
        return CrossViewCheckResult(
            status="CONFLICT_DETECTED",
            principal_dims_mm=principal,
            max_delta_mm=round(max_delta, 2),
            discrepancies=discrepancies,
        )
    if insunits == 0:
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            max_delta_mm=round(max_delta, 2),
            discrepancies=["UNITLESS_CAD_INSUNITS_0"],
        )
    if insunits not in _SUPPORTED_METRIC_INSUNITS:
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            max_delta_mm=round(max_delta, 2),
            discrepancies=[f"UNSUPPORTED_CAD_INSUNITS_{insunits}"],
        )
    if not (_has_calibrated_datum_labels(hb_texts) and _has_calibrated_datum_labels(bp_texts)):
        return CrossViewCheckResult(
            status="NOT_MEASURABLE_NO_SCALE",
            principal_dims_mm=principal,
            max_delta_mm=round(max_delta, 2),
            discrepancies=["MISSING_CALIBRATED_DATUM_LABELS"],
        )
    return CrossViewCheckResult(
        status="PASS",
        principal_dims_mm=principal,
        max_delta_mm=round(max_delta, 2),
        discrepancies=[],
    )
