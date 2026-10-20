"""tests/test_cleanroom_layer_text.py.

Batch S5 Test Suite: Layer Management, Deep Purging & Text Alignment.
Validates cleanroom parity against C# source:
  - AlignTextHandler (cadmind-align-text)
  - LayerStandardizeHandler (cadmind-layer-standardize)
  - LayerPurgeHandler (cadmind-layer-purge)
  - RelayerRulesHandler (cadmind-relayer-rules)
  - PurgeDeepHandler (cadmind-purge-deep)
"""

import json
import math
import os
import tempfile
import pytest

from cad_agent.cleanroom_layer_text import (
    AlignTextArgs,
    AlignTextHandler,
    DegenerateGeometryError,
    LayerPurgeArgs,
    LayerPurgeHandler,
    LayerStandardizeArgs,
    LayerStandardizeHandler,
    PurgeDeepArgs,
    PurgeDeepHandler,
    RelayerRulesArgs,
    RelayerRulesHandler,
    TextEntity,
)


# ============================================================================
# 1. AlignTextHandler Tests
# ============================================================================


def test_align_text_y_axis_default_reference() -> None:
    handler = AlignTextHandler()
    entities = [
        TextEntity("H1", "Line 1", 10.0, 50.0),
        TextEntity("H2", "Line 2", 15.0, 75.0),
        TextEntity("H3", "Line 3", 20.0, 100.0),
    ]
    args = AlignTextArgs(axis="Y")
    res = handler.execute(args, entities)

    assert res.status == "OK"
    assert res.count == 3
    assert res.entities is not None
    # Default reference coord should be first entity's Y (50.0)
    for ent in res.entities:
        assert ent.y == 50.0
    # X coordinates should remain unchanged
    assert res.entities[0].x == 10.0
    assert res.entities[1].x == 15.0
    assert res.entities[2].x == 20.0


def test_align_text_x_axis_explicit_reference() -> None:
    handler = AlignTextHandler()
    entities = [
        TextEntity("1A", "Col A", 10.0, 50.0),
        TextEntity("1B", "Col B", 25.0, 60.0),
    ]
    args = AlignTextArgs(axis="X", reference_coord=100.0)
    res = handler.execute(args, entities)

    assert res.status == "OK"
    assert res.count == 2
    assert res.entities is not None
    for ent in res.entities:
        assert ent.x == 100.0
    assert res.entities[0].y == 50.0
    assert res.entities[1].y == 60.0


def test_align_text_handles_filter() -> None:
    handler = AlignTextHandler()
    entities = [
        TextEntity("H1", "Target 1", 10.0, 20.0),
        TextEntity("H2", "Skip", 30.0, 40.0),
        TextEntity("H3", "Target 2", 50.0, 60.0),
    ]
    args = AlignTextArgs(handles=["H1", "H3"], axis="Y", reference_coord=0.0)
    res = handler.execute(args, entities)

    assert res.status == "OK"
    assert res.count == 2
    assert res.entities is not None
    assert [e.handle for e in res.entities] == ["H1", "H3"]
    assert res.entities[0].y == 0.0
    assert res.entities[1].y == 0.0


def test_align_text_locked_layer_abort() -> None:
    handler = AlignTextHandler()
    entities = [
        TextEntity("H1", "OK text", 10.0, 20.0, layer="TEXT"),
        TextEntity("H2", "Locked text", 30.0, 40.0, layer="LOCKED_LAYER"),
        TextEntity("H3", "Other text", 50.0, 60.0, layer="TEXT"),
    ]
    layer_locks = {"locked_layer": True, "text": False}
    args = AlignTextArgs(axis="Y")
    res = handler.execute(args, entities, layer_locks=layer_locks)

    assert res.status == "ERROR"
    assert "LOCKED_LAYER: Entity H2 is on locked layer 'LOCKED_LAYER'" in res.message
    assert res.count == 0
    assert res.entities is None


def test_align_text_empty_targets() -> None:
    handler = AlignTextHandler()
    res = handler.execute(AlignTextArgs(), [])
    assert res.status == "OK"
    assert res.count == 0
    assert "No text entities found" in res.message


def test_align_text_degenerate_non_finite_raises() -> None:
    with pytest.raises(DegenerateGeometryError):
        TextEntity("H1", "Bad coordinate", math.nan, 20.0)

    with pytest.raises(DegenerateGeometryError):
        handler = AlignTextHandler()
        entities = [TextEntity("H1", "T", 10.0, 20.0)]
        handler.execute(AlignTextArgs(reference_coord=math.inf), entities)



# ============================================================================
# 2. LayerStandardizeHandler Tests
# ============================================================================


def test_layer_standardize_palette() -> None:
    handler = LayerStandardizeHandler()
    existing = {"DIM": 5, "CUSTOM": 12}
    args = LayerStandardizeArgs(standard_name="ISO_MECH")
    res = handler.execute(args, existing)

    assert res.status == "OK"
    assert res.standard_layers_configured == 7
    # All 7 standard layers present
    expected_colors = {
        "0": 7,
        "CENTERLINE": 1,
        "FRAME": 7,
        "DIM": 3,
        "COORD": 4,
        "TEXT": 2,
        "HATCH": 8,
    }
    for lyr, col in expected_colors.items():
        assert lyr in res.configured_layers
        assert res.configured_layers[lyr] == col
    # Custom pre-existing layer preserved
    assert res.configured_layers["CUSTOM"] == 12


# ============================================================================
# 3. LayerPurgeHandler Tests
# ============================================================================


def test_layer_purge_system_and_active_protection() -> None:
    handler = LayerPurgeHandler()
    all_layers = ["0", "Defpoints", "ACTIVE_LAYER", "USED_WALL", "UNREFERENCED_1", "UNREFERENCED_2"]
    used_layers = {"USED_WALL"}
    clayer = "ACTIVE_LAYER"

    res = handler.execute(LayerPurgeArgs(), all_layers, used_layers, clayer=clayer)

    assert res.status == "OK"
    assert res.purged_count == 2
    assert sorted(res.purged_layer_names) == ["UNREFERENCED_1", "UNREFERENCED_2"]
    # 0, Defpoints, ACTIVE_LAYER, USED_WALL must never be in purged list
    assert "0" not in res.purged_layer_names
    assert "Defpoints" not in res.purged_layer_names
    assert "ACTIVE_LAYER" not in res.purged_layer_names
    assert "USED_WALL" not in res.purged_layer_names


def test_layer_purge_case_insensitivity() -> None:
    handler = LayerPurgeHandler()
    all_layers = ["0", "DEFPOINTS", "clayer_test", "used_beam", "unused_temp"]
    used_layers = {"USED_BEAM"}
    clayer = "CLAYER_TEST"

    res = handler.execute(LayerPurgeArgs(), all_layers, used_layers, clayer=clayer)
    assert res.status == "OK"
    assert res.purged_count == 1
    assert res.purged_layer_names == ["unused_temp"]


# ============================================================================
# 4. RelayerRulesHandler Tests
# ============================================================================


def test_relayer_rules_default_translation() -> None:
    handler = RelayerRulesHandler()
    entities = [
        TextEntity("H1", "T1", 0.0, 0.0, layer="OLD_TEXT"),
        TextEntity("H2", "T2", 0.0, 0.0, layer="ANNO"),
        TextEntity("H3", "T3", 0.0, 0.0, layer="BORDER"),
        TextEntity("H4", "T4", 0.0, 0.0, layer="MARKER"),
        TextEntity("H5", "T5", 0.0, 0.0, layer="UNCHANGED"),
    ]
    res = handler.execute(RelayerRulesArgs(dry_run=False), entities)

    assert res.status == "OK"
    assert res.relayered_count == 4
    assert entities[0].layer == "TEXT"
    assert entities[1].layer == "DIM"
    assert entities[2].layer == "FRAME"
    assert entities[3].layer == "COORD"
    assert entities[4].layer == "UNCHANGED"


def test_relayer_rules_dry_run() -> None:
    handler = RelayerRulesHandler()
    entities = [
        TextEntity("H1", "T1", 0.0, 0.0, layer="OLD_TEXT"),
    ]
    res = handler.execute(RelayerRulesArgs(dry_run=True), entities)

    assert res.status == "OK"
    assert res.relayered_count == 1
    # Dry run should NOT change entity layer
    assert entities[0].layer == "OLD_TEXT"


def test_relayer_rules_locked_layer_abort() -> None:
    handler = RelayerRulesHandler()
    entities = [
        TextEntity("H1", "T1", 0.0, 0.0, layer="OLD_TEXT", is_locked=True),
    ]
    res = handler.execute(RelayerRulesArgs(dry_run=False), entities)

    assert res.status == "ERROR"
    assert "LOCKED_LAYER: Entity H1 is on locked layer 'OLD_TEXT'" in res.message
    assert res.relayered_count == 0
    assert entities[0].layer == "OLD_TEXT"


def test_relayer_rules_from_file() -> None:
    handler = RelayerRulesHandler()
    custom_rules = {"OLD_A": "NEW_A", "OLD_B": "NEW_B"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(custom_rules, f)
        rule_path = f.name

    try:
        entities = [TextEntity("HA", "A", 0, 0, layer="OLD_A")]
        res = handler.execute(RelayerRulesArgs(ruleset_path=rule_path), entities)
        assert res.status == "OK"
        assert res.relayered_count == 1
        assert entities[0].layer == "NEW_A"
    finally:
        os.remove(rule_path)


def test_layer_purge_immutable_sequence() -> None:
    handler = LayerPurgeHandler()
    all_layers_tuple = ("0", "Defpoints", "ACTIVE_LAYER", "USED_WALL", "UNREFERENCED_1")
    used_layers = {"USED_WALL"}
    res = handler.execute(LayerPurgeArgs(), all_layers_tuple, used_layers, clayer="ACTIVE_LAYER")

    assert res.status == "OK"
    assert res.purged_count == 0  # 0 purged because input is immutable sequence
    assert "[OFFLINE_AUDIT]" in res.message
    assert "UNREFERENCED_1" in res.purged_layer_names


def test_layer_purge_offline_stub() -> None:
    handler = LayerPurgeHandler()
    res = handler.execute(LayerPurgeArgs())

    assert res.status == "OK"
    assert res.purged_count == 0
    assert "[OFFLINE_STUB]" in res.message


# ============================================================================
# 5. PurgeDeepHandler Tests
# ============================================================================


def test_purge_deep_offline_stub() -> None:
    handler = PurgeDeepHandler()
    res = handler.execute(PurgeDeepArgs(), database=None)

    assert res.status == "OK"
    assert "[OFFLINE_STUB]" in res.message
    assert res.total_purged == 0
    assert res.passes_run == 0


def test_purge_deep_convergence_and_counters() -> None:
    handler = PurgeDeepHandler()
    db = {
        "regapps": ["ACAD", "APP1", "APP2"],
        "blocks": ["*Model_Space", "*Paper_Space", "VALID_BLOCK", "UNUSED_B1"],
        "layers": [
            {"name": "0", "referenced": False, "is_locked": False},
            {"name": "Defpoints", "referenced": False, "is_locked": False},
            {"name": "ACTIVE", "referenced": False, "is_locked": False},
            {"name": "LOCKED_UNUSED", "referenced": False, "is_locked": True},
            {"name": "REFERENCED_L", "referenced": True, "is_locked": False},
            {"name": "UNUSED_L1", "referenced": False, "is_locked": False},
        ],
        "styles": ["Standard", "ByLayer", "ByBlock", "Continuous", "ACTIVE_STYLE", "UNUSED_STYLE"],
        "entities": [
            {"type": "DBText", "text": "   ", "handle": "T1"},
            {"type": "MText", "text": "", "handle": "T2"},
            {"type": "DBText", "text": "Valid Text", "handle": "T3"},
        ],
        "clayer": "ACTIVE",
        "textstyle": "ACTIVE_STYLE",
        "dimstyle": "Standard",
        "celtype": "ByLayer",
    }

    res = handler.execute(PurgeDeepArgs(), db)

    assert res.status == "OK"
    assert res.reg_apps_purged == 2  # APP1, APP2 (ACAD preserved)
    assert res.blocks_purged == 2    # VALID_BLOCK, UNUSED_B1 (* preserved)
    assert res.layers_purged == 1    # UNUSED_L1 (0, Defpoints, ACTIVE, LOCKED, REFERENCED preserved)
    assert res.styles_purged == 1    # UNUSED_STYLE (Standard, ByLayer, ByBlock, Continuous, ACTIVE preserved)
    assert res.empty_text_purged == 2 # T1, T2 (T3 preserved)
    assert res.total_purged == 8
    assert res.passes_run >= 1


def test_purge_deep_max_passes_clamp() -> None:
    handler = PurgeDeepHandler()
    db = {"regapps": [], "blocks": [], "layers": [], "styles": [], "entities": []}
    res = handler.execute(PurgeDeepArgs(max_passes=25), db)
    # Empty db should terminate at pass 1
    assert res.status == "OK"
    assert res.passes_run == 1
    assert res.total_purged == 0
