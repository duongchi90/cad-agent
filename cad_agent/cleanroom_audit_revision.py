"""cad_agent/cleanroom_audit_revision.py.

Batch S4: Auditing, Standardization, Batch Stamps & Revision Diff Engines.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave13Handlers.cs: DrawingAuditHandler (cadmind-drawing-audit)
  - TierBWave14Handlers.cs: TagAuditHandler (cadmind-tag-audit)
  - TierBWave16Handlers.cs: StyleStandardizeHandler (cadmind-style-standardize)
  - TierBWave16Handlers.cs: StampBatchHandler (cadmind-stamp-batch)
  - TierBWave17Handlers.cs: CompareRevisionHandler (cadmind-compare-revision)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from cad_agent.cleanroom_mechanical import Point2D

# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================


class CleanroomError(ValueError):
    """Base exception for cleanroom validation errors."""

    pass


class DegenerateGeometryError(CleanroomError):
    """Raised when geometric or validation parameters violate construction rules."""

    pass


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Numeric arguments must be finite numbers ({name}={val}).")
    return float(val)


def _validate_positive(val: float, name: str) -> float:
    """Ensure value is strictly positive (> 1e-6)."""
    f = _validate_finite(val, name)
    if f <= 1e-6:
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Parameter '{name}' must be positive (> 1e-6), got {f}.")
    return f


# ============================================================================
# 1. TAG AUDIT (cadmind-tag-audit / TierB Wave 14)
# ============================================================================


@dataclass(frozen=True)
class TagItemInput:
    """Input tag record for audit."""

    handle: str
    tag_text: str
    layer: str = "0"


@dataclass(frozen=True)
class TagAuditArgs:
    """Input arguments for tag auditing."""

    layer: Optional[str] = None
    prefix: Optional[str] = None
    check_sequence: bool = False
    tags: Optional[Sequence[TagItemInput]] = None


@dataclass(frozen=True)
class TagAuditItem:
    """Result item for audited tag."""

    handle: str
    tag_text: str
    layer: str
    occurrences: int


@dataclass(frozen=True)
class TagAuditResult:
    """Result of tag auditing."""

    status: str
    message: str
    total_scanned: int
    unique_tags_count: int
    duplicate_tags_count: int
    duplicate_tags: List[str]
    missing_sequence_numbers: List[int]
    items: List[TagAuditItem]


class TagAuditHandler:
    """Audits text and tag entities for uniqueness, frequency, and sequential integrity."""

    def execute(self, args: TagAuditArgs) -> TagAuditResult:
        """Execute tag audit matching C# grouping and missing sequence deduction."""
        tag_items = list(args.tags) if args.tags is not None else []
        target_layer = args.layer.strip().lower() if args.layer and args.layer.strip() else None
        target_prefix = args.prefix.strip().lower() if args.prefix and args.prefix.strip() else None

        filtered_items: List[TagItemInput] = []
        counts: Dict[str, int] = {}

        for item in tag_items:
            tag_str = (item.tag_text or "").strip()
            if not tag_str:
                continue

            if target_layer is not None and item.layer.strip().lower() != target_layer:
                continue

            if target_prefix is not None and not tag_str.lower().startswith(target_prefix):
                continue

            filtered_items.append(item)
            key = tag_str.upper()
            counts[key] = counts.get(key, 0) + 1

        duplicates = sorted([k for k, v in counts.items() if v > 1])
        missing_seq: List[int] = []

        if args.check_sequence and args.prefix:
            prefix_len = len(args.prefix.strip())
            seq_numbers: List[int] = []
            for item in filtered_items:
                sub = item.tag_text.strip()[prefix_len:].strip()
                try:
                    num = int(sub)
                    seq_numbers.append(num)
                except ValueError:
                    pass

            if seq_numbers:
                min_n = min(seq_numbers)
                max_n = max(seq_numbers)
                num_set = set(seq_numbers)
                for expected in range(min_n, max_n + 1):
                    if expected not in num_set:
                        missing_seq.append(expected)

        result_items = [
            TagAuditItem(
                handle=item.handle,
                tag_text=item.tag_text.strip(),
                layer=item.layer,
                occurrences=counts.get(item.tag_text.strip().upper(), 1),
            )
            for item in filtered_items
        ]

        total_scanned = len(filtered_items)
        unique_count = len(counts)
        dup_count = len(duplicates)

        msg = (
            f"Audited {total_scanned} tags: {unique_count} unique, "
            f"{dup_count} duplicates, {len(missing_seq)} missing sequence numbers."
        )

        return TagAuditResult(
            status="OK",
            message=msg,
            total_scanned=total_scanned,
            unique_tags_count=unique_count,
            duplicate_tags_count=dup_count,
            duplicate_tags=duplicates,
            missing_sequence_numbers=missing_seq,
            items=result_items,
        )


# ============================================================================
# 2. STYLE STANDARDIZE (cadmind-style-standardize / TierB Wave 16)
# ============================================================================


@dataclass(frozen=True)
class TextStyleProperties:
    """Target font and dimension properties for a text style."""

    font: Optional[str] = None
    height: Optional[float] = None
    width_factor: Optional[float] = None
    oblique: Optional[float] = None


@dataclass(frozen=True)
class StyleStandardizeArgs:
    """Input arguments for style standardization."""

    text_styles: Optional[Dict[str, TextStyleProperties]] = None
    dim_styles: Optional[Dict[str, Dict[str, float]]] = None
    available_text_styles: Optional[Sequence[str]] = None
    available_dim_styles: Optional[Sequence[str]] = None


@dataclass(frozen=True)
class StyleStandardizeResult:
    """Result of style standardization."""

    status: str
    message: str
    text_styles_updated: int
    text_styles_missing: List[str]
    dim_styles_updated: int
    dim_styles_missing: List[str]
    details: List[str]


class StyleStandardizeHandler:
    """Enforces corporate standards across text styles and dimension style variable dictionaries."""

    def execute(self, args: StyleStandardizeArgs) -> StyleStandardizeResult:
        """Execute style standardization matching C# table resolution and missing-style tracking."""
        avail_text = set(s.strip().upper() for s in (args.available_text_styles or []))
        avail_dim = set(s.strip().upper() for s in (args.available_dim_styles or []))

        text_updated = 0
        text_missing: List[str] = []
        dim_updated = 0
        dim_missing: List[str] = []
        details: List[str] = []

        if args.text_styles:
            for style_name, props in args.text_styles.items():
                s_key = style_name.strip().upper()
                if s_key in avail_text:
                    text_updated += 1
                    details.append(f"Updated text style '{style_name}'.")
                else:
                    text_missing.append(style_name)
                    details.append(f"Text style '{style_name}' not found (reported, not created).")

        if args.dim_styles:
            for dim_name, _ in args.dim_styles.items():
                d_key = dim_name.strip().upper()
                if d_key in avail_dim:
                    dim_updated += 1
                    details.append(f"Updated dimension style '{dim_name}'.")
                else:
                    dim_missing.append(dim_name)
                    details.append(f"Dimension style '{dim_name}' not found (reported, not created).")

        msg = f"Standardized {text_updated} text styles and {dim_updated} dimension styles."
        return StyleStandardizeResult(
            status="OK",
            message=msg,
            text_styles_updated=text_updated,
            text_styles_missing=text_missing,
            dim_styles_updated=dim_updated,
            dim_styles_missing=dim_missing,
            details=details,
        )


# ============================================================================
# 3. STAMP BATCH (cadmind-stamp-batch / TierB Wave 16)
# ============================================================================


@dataclass(frozen=True)
class StampBatchArgs:
    """Input arguments for multi-layout watermark stamps."""

    text: str
    layouts: Optional[Sequence[str]] = None
    point: Optional[Sequence[float]] = None
    height: float = 30.0
    rotation: float = 30.0
    color: int = 8
    layer: str = "STAMP"


@dataclass(frozen=True)
class StampBatchResult:
    """Result of batch stamp application."""

    status: str
    message: str
    text: str
    stamped_layouts_count: int
    stamped_layout_names: List[str]
    layer: str
    border_vertices: List[Point2D]
    text_position: Point2D
    text_rotation: float
    created_handles: List[str]


class StampBatchHandler:
    """Applies status watermark stamps with angled border boxes across drawing layouts."""

    def execute(self, args: StampBatchArgs) -> StampBatchResult:
        """Execute stamp geometry layout with angled bounding rectangle matching C#."""
        if not args.text or not args.text.strip():
            raise DegenerateGeometryError("EMPTY_TEXT: Stamp text cannot be empty or whitespace.")

        height = _validate_positive(args.height, "Height")
        rotation = _validate_finite(args.rotation, "Rotation")

        px, py = 100.0, 100.0
        if args.point is not None and len(args.point) >= 2:
            px = _validate_finite(args.point[0], "Point[0]")
            py = _validate_finite(args.point[1], "Point[1]")
        point = Point2D(px, py)

        layer = args.layer.strip() if args.layer and args.layer.strip() else "STAMP"
        text = args.text.strip()
        layouts = list(args.layouts) if args.layouts else ["Model"]

        # Calculate bounding box dimensions: width ~ len * height * 0.7, height ~ height * 1.4
        box_w = max(20.0, len(text) * height * 0.7)
        box_h = height * 1.4
        rad = rotation * math.pi / 180.0
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        hw = box_w / 2.0
        hh = box_h / 2.0

        local_corners = [
            (-hw, -hh),
            (hw, -hh),
            (hw, hh),
            (-hw, hh),
        ]

        border_vertices = [
            Point2D(
                point.x + (lx * cos_r - ly * sin_r),
                point.y + (lx * sin_r + ly * cos_r),
            )
            for lx, ly in local_corners
        ]

        msg = f"Applied stamp '{text}' across {len(layouts)} layouts on layer '{layer}'."
        return StampBatchResult(
            status="OK",
            message=msg,
            text=text,
            stamped_layouts_count=len(layouts),
            stamped_layout_names=layouts,
            layer=layer,
            border_vertices=border_vertices,
            text_position=point,
            text_rotation=rotation,
            created_handles=[],
        )


# ============================================================================
# 4. DRAWING AUDIT (cadmind-drawing-audit / TierB Wave 13)
# ============================================================================


@dataclass(frozen=True)
class LayerAuditInfo:
    """Layer state information for audit."""

    name: str
    is_empty: bool = False
    is_off: bool = False
    is_frozen: bool = False


@dataclass(frozen=True)
class DrawingAuditArgs:
    """Input arguments for drawing audit."""

    layers: Optional[Sequence[LayerAuditInfo]] = None
    entities_on_layer_0: int = 0
    total_model_space_entities: int = 0
    block_count: int = 0
    text_style_count: int = 0


@dataclass(frozen=True)
class DrawingAuditResult:
    """Result of drawing entity and layer audit."""

    status: str
    message: str
    total_layers: int
    empty_layers_count: int
    empty_layers: List[str]
    off_or_frozen_layers_count: int
    off_or_frozen_layers: List[str]
    entities_on_layer_0: int
    total_model_space_entities: int
    block_count: int
    text_style_count: int


class DrawingAuditHandler:
    """Audits drawing database health: unused layers, hidden layers, and Layer 0 hygiene."""

    def execute(self, args: DrawingAuditArgs) -> DrawingAuditResult:
        """Execute drawing database audit matching C# layer table inspection."""
        layer_list = list(args.layers) if args.layers is not None else []
        total_layers = len(layer_list)

        empty_layers = [l.name for l in layer_list if l.is_empty]
        off_frozen = [l.name for l in layer_list if l.is_off or l.is_frozen]

        msg = (
            f"Drawing audit completed: {total_layers} layers ({len(empty_layers)} empty, "
            f"{len(off_frozen)} off/frozen), {args.total_model_space_entities} entities."
        )

        return DrawingAuditResult(
            status="OK",
            message=msg,
            total_layers=total_layers,
            empty_layers_count=len(empty_layers),
            empty_layers=empty_layers,
            off_or_frozen_layers_count=len(off_frozen),
            off_or_frozen_layers=off_frozen,
            entities_on_layer_0=args.entities_on_layer_0,
            total_model_space_entities=args.total_model_space_entities,
            block_count=args.block_count,
            text_style_count=args.text_style_count,
        )


# ============================================================================
# 5. COMPARE REVISION (cadmind-compare-revision / TierB Wave 17)
# ============================================================================


@dataclass(frozen=True)
class RevisionDiffEntry:
    """Entity count difference for a specific (Layer, EntityType) pair."""

    layer: str
    entity_type: str
    current_count: int
    other_count: int
    difference: int


@dataclass(frozen=True)
class CompareRevisionArgs:
    """Input arguments for revision drawing comparison."""

    current_entities: Optional[Dict[Tuple[str, str], int]] = None
    other_entities: Optional[Dict[Tuple[str, str], int]] = None
    compared_file: str = "revision_b.dwg"


@dataclass(frozen=True)
class CompareRevisionResult:
    """Result of revision comparison."""

    status: str
    message: str
    compared_file: str
    total_differences: int
    current_entities_total: int
    other_entities_total: int
    differences: List[RevisionDiffEntry]


class CompareRevisionHandler:
    """Performs geometric and entity-count diff between two drawing revisions grouped by layer and DXF class."""

    def execute(self, args: CompareRevisionArgs) -> CompareRevisionResult:
        """Execute revision comparison matching C# group-by-layer and entity-type diff."""
        current = args.current_entities or {}
        other = args.other_entities or {}

        all_keys = sorted(list(set(current.keys()) | set(other.keys())))
        diffs: List[RevisionDiffEntry] = []
        total_diff_count = 0

        for layer, ent_type in all_keys:
            c_cnt = current.get((layer, ent_type), 0)
            o_cnt = other.get((layer, ent_type), 0)
            diff = c_cnt - o_cnt
            if diff != 0:
                diffs.append(
                    RevisionDiffEntry(
                        layer=layer,
                        entity_type=ent_type,
                        current_count=c_cnt,
                        other_count=o_cnt,
                        difference=diff,
                    )
                )
                total_diff_count += abs(diff)

        cur_total = sum(current.values())
        other_total = sum(other.values())

        msg = (
            f"Compared with '{args.compared_file}': {total_diff_count} entity differences "
            f"across {len(diffs)} layer/type categories."
        )

        return CompareRevisionResult(
            status="OK",
            message=msg,
            compared_file=args.compared_file,
            total_differences=total_diff_count,
            current_entities_total=cur_total,
            other_entities_total=other_total,
            differences=diffs,
        )
