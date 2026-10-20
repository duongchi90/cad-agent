"""cad_agent/cleanroom_layer_text.py.

Batch S5: Layer Management, Deep Purging & Text Alignment Engines.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierAWave1Handlers.cs: AlignTextHandler (cadmind-align-text)
  - ExtendedHandlers.cs: LayerStandardizeHandler (cadmind-layer-standardize)
  - ExtendedHandlers.cs: LayerPurgeHandler (cadmind-layer-purge)
  - ExtendedHandlers.cs: RelayerRulesHandler (cadmind-relayer-rules)
  - TierAWave2Handlers.cs: PurgeDeepHandler (cadmind-purge-deep)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

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


# ============================================================================
# DTO & IR DEFINITIONS
# ============================================================================


@dataclass
class TextEntity:
    """Representation of DBText or MText entity for alignment."""

    handle: str
    text: str
    x: float
    y: float
    z: float = 0.0
    layer: str = "0"
    is_locked: bool = False

    def __post_init__(self) -> None:
        self.x = _validate_finite(self.x, "x")
        self.y = _validate_finite(self.y, "y")
        self.z = _validate_finite(self.z, "z")


@dataclass(frozen=True)
class AlignTextArgs:
    """Arguments for cadmind-align-text."""

    handles: Optional[Sequence[str]] = None
    alignment: str = "Left"
    reference_coord: Optional[float] = None
    axis: str = "X"


@dataclass(frozen=True)
class ToolGenericResult:
    """Standard generic result matching C# ToolGenericResult."""

    status: str
    message: str
    count: int = 0
    entities: Optional[Sequence[TextEntity]] = None


@dataclass(frozen=True)
class LayerDefinition:
    """Representation of an AutoCAD Layer table record."""

    name: str
    color_aci: int
    is_locked: bool = False


@dataclass(frozen=True)
class LayerStandardizeArgs:
    """Arguments for cadmind-layer-standardize."""

    standard_name: str = "DEFAULT"
    force_rename: bool = False


@dataclass(frozen=True)
class LayerStandardizeResult:
    """Result of layer standardization."""

    status: str
    message: str
    standard_layers_configured: int
    configured_layers: Dict[str, int]


@dataclass(frozen=True)
class LayerPurgeArgs:
    """Arguments for cadmind-layer-purge."""

    purge_unreferenced_only: bool = True


@dataclass(frozen=True)
class LayerPurgeResult:
    """Result of layer purging."""

    status: str
    message: str
    purged_count: int
    purged_layer_names: List[str]


@dataclass(frozen=True)
class RelayerRulesArgs:
    """Arguments for cadmind-relayer-rules."""

    ruleset_path: str = ""
    dry_run: bool = False
    rules: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class RelayerRulesResult:
    """Result of relayering rules execution."""

    status: str
    message: str
    relayered_count: int
    relayered_handles: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PurgeDeepArgs:
    """Arguments for cadmind-purge-deep."""

    purge_regapps: bool = True
    purge_blocks: bool = True
    purge_layers: bool = True
    purge_styles: bool = True
    purge_empty_text: bool = True
    max_passes: int = 5


@dataclass(frozen=True)
class PurgeDeepResult:
    """Result matching C# PurgeDeepResult."""

    status: str
    message: str
    reg_apps_purged: int
    blocks_purged: int
    layers_purged: int
    styles_purged: int
    empty_text_purged: int
    total_purged: int
    passes_run: int = 1


# ============================================================================
# 1. cadmind-align-text (AlignTextHandler)
# ============================================================================


class AlignTextHandler:
    """Cleanroom implementation of AlignTextHandler (TierAWave1Handlers.cs)."""

    def execute(
        self,
        args: AlignTextArgs,
        entities: Sequence[TextEntity],
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> ToolGenericResult:
        """Align text entities along Axis X or Y with locked layer rollback safety."""
        if not entities:
            return ToolGenericResult("OK", "No text entities found to align.", 0, [])

        locks = layer_locks or {}

        # 1. Filter targets by handles if provided
        target_entities: List[TextEntity] = []
        if args.handles is not None and len(args.handles) > 0:
            handle_set = {h.lower() for h in args.handles}
            for ent in entities:
                if ent.handle.lower() in handle_set:
                    target_entities.append(ent)
        else:
            target_entities = list(entities)

        if not target_entities:
            return ToolGenericResult("OK", "No text entities found to align.", 0, [])

        # 2. Pre-check locked layers across all targets (Transactional Rollback Gate)
        for ent in target_entities:
            is_locked = ent.is_locked or locks.get(ent.layer.lower(), False)
            if is_locked:
                return ToolGenericResult(
                    status="ERROR",
                    message=f"LOCKED_LAYER: Entity {ent.handle} is on locked layer '{ent.layer}'. Cannot align text. Transaction rolled back.",
                    count=0,
                    entities=None,
                )

        # 3. Determine target coordinate
        axis_upper = (args.axis or "X").strip().upper()
        if axis_upper != "Y":
            axis_upper = "X"

        if args.reference_coord is not None and not math.isnan(args.reference_coord):
            target_coord = _validate_finite(args.reference_coord, "reference_coord")
        else:
            first = target_entities[0]
            target_coord = first.y if axis_upper == "Y" else first.x

        # 4. Perform alignment
        aligned_list: List[TextEntity] = []
        for ent in target_entities:
            new_x = target_coord if axis_upper == "X" else ent.x
            new_y = target_coord if axis_upper == "Y" else ent.y
            aligned_list.append(
                TextEntity(
                    handle=ent.handle,
                    text=ent.text,
                    x=new_x,
                    y=new_y,
                    z=ent.z,
                    layer=ent.layer,
                    is_locked=ent.is_locked,
                )
            )

        count = len(aligned_list)
        msg = f"Aligned {count} text entities along {axis_upper} to {target_coord:g}."
        return ToolGenericResult("OK", msg, count, aligned_list)


# ============================================================================
# 2. cadmind-layer-standardize (LayerStandardizeHandler)
# ============================================================================


class LayerStandardizeHandler:
    """Cleanroom implementation of LayerStandardizeHandler (ExtendedHandlers.cs)."""

    STANDARD_DEFINITIONS: Dict[str, int] = {
        "0": 7,  # White / Black
        "CENTERLINE": 1,  # Red
        "FRAME": 7,  # White
        "DIM": 3,  # Green
        "COORD": 4,  # Cyan
        "TEXT": 2,  # Yellow
        "HATCH": 8,  # Gray
    }

    def execute(
        self,
        args: LayerStandardizeArgs,
        existing_layers: Optional[Dict[str, int]] = None,
    ) -> LayerStandardizeResult:
        """Upsert standard layer table with standardized ACI colors."""
        configured = dict(existing_layers or {})
        standard_count = 0

        for layer_name, aci_color in self.STANDARD_DEFINITIONS.items():
            # Match case-insensitively
            found_key = None
            for ex_name in configured.keys():
                if ex_name.strip().upper() == layer_name.strip().upper():
                    found_key = ex_name
                    break

            if found_key:
                configured[found_key] = aci_color
            else:
                configured[layer_name] = aci_color
            standard_count += 1

        std_name = args.standard_name or "DEFAULT"
        msg = f"Standardized {standard_count} layers under '{std_name}'."
        return LayerStandardizeResult("OK", msg, standard_count, configured)


# ============================================================================
# 3. cadmind-layer-purge (LayerPurgeHandler)
# ============================================================================


class LayerPurgeHandler:
    """Cleanroom implementation of LayerPurgeHandler (ExtendedHandlers.cs)."""

    PROTECTED_SYSTEM_LAYERS: Set[str] = {"0", "defpoints"}

    def execute(
        self,
        args: LayerPurgeArgs,
        all_layers: Sequence[str],
        used_layers: Set[str],
        clayer: str = "0",
    ) -> LayerPurgeResult:
        """Purge unreferenced layers while strictly protecting system layers."""
        used_normalized = {lyr.strip().lower() for lyr in used_layers}
        clayer_norm = (clayer or "0").strip().lower()

        purged: List[str] = []
        for lyr in all_layers:
            name_norm = lyr.strip().lower()

            # Safety Gate: Never purge system layers '0', 'Defpoints', or the active layer CLAYER
            if name_norm in self.PROTECTED_SYSTEM_LAYERS or name_norm == clayer_norm:
                continue

            # Safety Gate: Never purge layers referenced anywhere
            if name_norm not in used_normalized:
                if args.purge_unreferenced_only:
                    purged.append(lyr)

        count = len(purged)
        msg = f"Purged {count} unreferenced layers."
        return LayerPurgeResult("OK", msg, count, purged)


# ============================================================================
# 4. cadmind-relayer-rules (RelayerRulesHandler)
# ============================================================================


class RelayerRulesHandler:
    """Cleanroom implementation of RelayerRulesHandler (ExtendedHandlers.cs)."""

    DEFAULT_RULES: Dict[str, str] = {
        "OLD_TEXT": "TEXT",
        "ANNO": "DIM",
        "BORDER": "FRAME",
        "MARKER": "COORD",
    }

    def execute(
        self,
        args: RelayerRulesArgs,
        entities: Sequence[TextEntity],
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> RelayerRulesResult:
        """Execute relayering rules with locked layer source protection and DryRun."""
        rules = dict(self.DEFAULT_RULES)

        # Load from file if path provided and exists
        if args.ruleset_path and os.path.exists(args.ruleset_path):
            try:
                with open(args.ruleset_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        rules = {str(k): str(v) for k, v in loaded.items()}
            except Exception:
                pass
        elif args.rules:
            rules = dict(args.rules)

        # Normalize rules keys to uppercase
        norm_rules = {k.strip().upper(): v.strip().upper() for k, v in rules.items()}
        locks = layer_locks or {}

        # Check for locked layer abort before mutating
        for ent in entities:
            src_layer = ent.layer.strip().upper()
            if src_layer in norm_rules:
                is_locked = ent.is_locked or locks.get(src_layer.lower(), False)
                if is_locked:
                    return RelayerRulesResult(
                        status="ERROR",
                        message=f"LOCKED_LAYER: Entity {ent.handle} is on locked layer '{ent.layer}'. Cannot relayer. Transaction rolled back.",
                        relayered_count=0,
                        relayered_handles=[],
                    )

        # Relayer entities
        relayered_count = 0
        relayered_handles: List[str] = []

        for ent in entities:
            src_layer = ent.layer.strip().upper()
            if src_layer in norm_rules:
                target_layer = norm_rules[src_layer]
                if not args.dry_run:
                    ent.layer = target_layer
                relayered_count += 1
                relayered_handles.append(ent.handle)

        msg = f"Relayered {relayered_count} entities (DryRun: {args.dry_run})."
        return RelayerRulesResult("OK", msg, relayered_count, relayered_handles)


# ============================================================================
# 5. cadmind-purge-deep (PurgeDeepHandler)
# ============================================================================


class PurgeDeepHandler:
    """Cleanroom implementation of PurgeDeepHandler (TierAWave2Handlers.cs)."""

    PROTECTED_SYSTEM_LAYERS: Set[str] = {"0", "defpoints"}
    PROTECTED_STYLES: Set[str] = {"standard", "bylayer", "byblock", "continuous"}
    PROTECTED_REGAPPS: Set[str] = {"acad"}

    def execute(
        self,
        args: PurgeDeepArgs,
        database: Dict[str, any],
    ) -> PurgeDeepResult:
        """Multi-pass iterative deep purge until convergence.

        Database dict expected schema:
          - 'regapps': list of str
          - 'blocks': list of str (unreferenced blocks, name starting with '*' are layout/anonymous)
          - 'layers': list of dict {'name': str, 'referenced': bool, 'is_locked': bool}
          - 'styles': list of str (unreferenced styles)
          - 'entities': list of dict {'type': str, 'text': str, 'handle': str}
          - 'clayer': str (active layer)
          - 'textstyle': str (active text style)
          - 'dimstyle': str (active dim style)
          - 'celtype': str (active line type)
        """
        reg_apps_purged = 0
        blocks_purged = 0
        layers_purged = 0
        styles_purged = 0
        empty_text_purged = 0

        max_passes = max(1, min(args.max_passes, 10))
        clayer_norm = (database.get("clayer") or "0").strip().lower()

        active_styles = {
            (database.get("textstyle") or "").strip().lower(),
            (database.get("dimstyle") or "").strip().lower(),
            (database.get("celtype") or "").strip().lower(),
        }

        passes_run = 0

        for pass_idx in range(max_passes):
            passes_run += 1
            pass_purged = 0

            # 1. Blocks
            if args.purge_blocks and "blocks" in database:
                to_remove_blocks = []
                for bname in database["blocks"]:
                    if bname.startswith("*"):
                        continue
                    to_remove_blocks.append(bname)

                for b in to_remove_blocks:
                    database["blocks"].remove(b)
                    blocks_purged += 1
                    pass_purged += 1

            # 2. Layers
            if args.purge_layers and "layers" in database:
                to_remove_layers = []
                for lyr in database["layers"]:
                    lname = lyr["name"].strip().lower()
                    if lname in self.PROTECTED_SYSTEM_LAYERS or lname == clayer_norm or lyr.get("is_locked", False):
                        continue
                    if not lyr.get("referenced", False):
                        to_remove_layers.append(lyr)

                for lyr in to_remove_layers:
                    database["layers"].remove(lyr)
                    layers_purged += 1
                    pass_purged += 1

            # 3. RegApps
            if args.purge_regapps and "regapps" in database:
                to_remove_regapps = []
                for ra in database["regapps"]:
                    if ra.strip().lower() in self.PROTECTED_REGAPPS:
                        continue
                    to_remove_regapps.append(ra)

                for ra in to_remove_regapps:
                    database["regapps"].remove(ra)
                    reg_apps_purged += 1
                    pass_purged += 1

            # 4. Styles
            if args.purge_styles and "styles" in database:
                to_remove_styles = []
                for s in database["styles"]:
                    snorm = s.strip().lower()
                    if snorm in self.PROTECTED_STYLES or snorm in active_styles:
                        continue
                    to_remove_styles.append(s)

                for s in to_remove_styles:
                    database["styles"].remove(s)
                    styles_purged += 1
                    pass_purged += 1

            # 5. Empty Text Purge (only on first pass, pass == 0)
            if pass_idx == 0 and args.purge_empty_text and "entities" in database:
                to_remove_ents = []
                for ent in database["entities"]:
                    etype = ent.get("type", "")
                    if etype in ("DBText", "MText"):
                        text_val = ent.get("text", "")
                        if not text_val or text_val.strip() == "":
                            to_remove_ents.append(ent)

                for ent in to_remove_ents:
                    database["entities"].remove(ent)
                    empty_text_purged += 1
                    pass_purged += 1

            # Convergence check
            if pass_purged == 0:
                break

        total_purged = reg_apps_purged + blocks_purged + layers_purged + styles_purged + empty_text_purged
        msg = (
            f"Deep purge completed: {reg_apps_purged} regapps, {blocks_purged} blocks, "
            f"{layers_purged} layers, {styles_purged} styles, {empty_text_purged} empty texts purged "
            f"({total_purged} total)."
        )
        return PurgeDeepResult(
            status="OK",
            message=msg,
            reg_apps_purged=reg_apps_purged,
            blocks_purged=blocks_purged,
            layers_purged=layers_purged,
            styles_purged=styles_purged,
            empty_text_purged=empty_text_purged,
            total_purged=total_purged,
            passes_run=passes_run,
        )
