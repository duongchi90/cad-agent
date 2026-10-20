"""tests/test_cleanroom_block_audit.py.

Batch S6 Test Suite: Block Tables, Spatial Dedup, Font Audit, Merge & Sync.
Validates cleanroom parity against physical C# source:
  - BlockInsertTableHandler (cadmind-block-insert-table)
  - BlockDedupHandler (cadmind-block-dedup)
  - FontAuditHandler (cadmind-font-audit)
  - DrawingMergeHandler (cadmind-drawing-merge)
  - BlockSyncHandler (cadmind-block-sync)
"""

import math
import os
import tempfile
import pytest

from cad_agent.cleanroom_block_audit import (
    BlockDedupArgs,
    BlockDedupHandler,
    BlockDefinition,
    BlockInsertRow,
    BlockInsertTableArgs,
    BlockInsertTableHandler,
    BlockReferenceInstance,
    BlockSyncArgs,
    BlockSyncHandler,
    CleanroomError,
    DegenerateGeometryError,
    DrawingMergeArgs,
    DrawingMergeHandler,
    FontAuditArgs,
    FontAuditHandler,
    MergeFileItem,
    SemanticCollisionError,
)
from cad_agent.cleanroom_mechanical import Point2D


# ============================================================================
# 1. BlockInsertTableHandler Tests
# ============================================================================


def test_block_insert_table_valid() -> None:
    handler = BlockInsertTableHandler()
    rows = [
        BlockInsertRow(x=10.0, y=20.0, rotation=0.0, scale=1.0),
        BlockInsertRow(x=30.0, y=40.0, rotation=90.0, scale=2.0),
    ]
    args = BlockInsertTableArgs(block="MY_BLOCK", rows=rows, layer="BLOCKS")
    res = handler.execute(args)

    assert res.status == "OK"
    assert res.insert_count == 2
    assert res.processed_count == 2
    assert res.block_name == "MY_BLOCK"


def test_block_insert_table_anonymous_rejected() -> None:
    handler = BlockInsertTableHandler()
    rows = [BlockInsertRow(x=0.0, y=0.0)]
    args = BlockInsertTableArgs(block="*Model_Space", rows=rows)
    res = handler.execute(args)

    assert res.status == "ERROR"
    assert "Reserved or anonymous block names are not permitted" in res.message


def test_block_insert_table_micro_scale_raises() -> None:
    with pytest.raises(DegenerateGeometryError):
        BlockInsertRow(x=0.0, y=0.0, scale=1e-7)

    with pytest.raises(DegenerateGeometryError):
        BlockInsertRow(x=math.nan, y=0.0, scale=1.0)



def test_block_insert_table_empty_rows_rejected() -> None:
    handler = BlockInsertTableHandler()
    args = BlockInsertTableArgs(block="VALID_BLOCK", rows=[])
    res = handler.execute(args)

    assert res.status == "ERROR"
    assert "requires at least one row" in res.message


# ============================================================================
# 2. BlockDedupHandler Tests
# ============================================================================


def test_block_dedup_spatial_clustering_dry_run_vs_apply() -> None:
    handler = BlockDedupHandler()
    instances = [
        BlockReferenceInstance("H1", "CHAIR", 100.0, 100.0, 0.0),
        BlockReferenceInstance("H2", "CHAIR", 100.005, 100.005, 0.0),  # within 0.01 tolerance
        BlockReferenceInstance("H3", "CHAIR", 100.0, 200.0, 0.0),      # far away
        BlockReferenceInstance("H4", "TABLE", 100.0, 100.0, 0.0),      # different name
    ]

    # Dry run
    res_dry = handler.execute(BlockDedupArgs(tolerance=0.01, apply=False), instances)
    assert res_dry.status == "OK"
    assert res_dry.total_inserts_scanned == 4
    assert res_dry.duplicate_groups_count == 1
    assert res_dry.duplicates_found == 1
    assert res_dry.duplicates_erased == 0
    assert res_dry.is_dry_run is True
    assert res_dry.duplicate_handles == ["H2"]

    # Apply
    res_apply = handler.execute(BlockDedupArgs(tolerance=0.01, apply=True), instances)
    assert res_apply.status == "OK"
    assert res_apply.duplicates_erased == 1
    assert res_apply.is_dry_run is False


def test_block_dedup_negative_tolerance_raises() -> None:
    handler = BlockDedupHandler()
    with pytest.raises(CleanroomError, match="INVALID_TOLERANCE"):
        handler.execute(BlockDedupArgs(tolerance=-0.5), [])


# ============================================================================
# 3. FontAuditHandler Tests
# ============================================================================


def test_font_audit_standard_shx_and_missing() -> None:
    handler = FontAuditHandler()
    styles = [
        ("Standard", "simplex.shx", "", False),
        ("Notes", "txt.shx", "", False),
        ("CustomMissing", "unregistered_font.shx", "", False),
        ("Unassigned", "", "", False),
        ("TrueTypeArial", "", "Arial", False),
    ]
    res = handler.execute(FontAuditArgs(), styles)

    assert res.status == "OK"
    assert res.total_styles_checked == 5
    assert res.valid_styles_count == 3  # Standard, Notes, TrueTypeArial
    assert res.missing_font_styles_count == 2
    assert "CustomMissing" in res.missing_font_styles
    assert "Unassigned" in res.missing_font_styles


# ============================================================================
# 4. DrawingMergeHandler Tests
# ============================================================================


def test_drawing_merge_file_not_found() -> None:
    handler = DrawingMergeHandler()
    args = DrawingMergeArgs(files=[MergeFileItem(path="C:/non_existent_path.dwg")])
    res = handler.execute(args)

    assert res.status == "ERROR"
    assert "FILE_NOT_FOUND" in res.message


def test_drawing_merge_valid_files() -> None:
    handler = DrawingMergeHandler()
    with tempfile.NamedTemporaryFile("w", suffix=".dwg", delete=False) as f:
        f.write("DUMMY_DWG")
        p = f.name

    try:
        args = DrawingMergeArgs(files=[MergeFileItem(path=p, insertion_point=Point2D(10.0, 20.0))])
        res = handler.execute(args)
        assert res.status == "OK"
        assert res.merged_count == 1
    finally:
        os.remove(p)


# ============================================================================
# 5. BlockSyncHandler Tests
# ============================================================================


def test_block_sync_policies_and_fail_closed() -> None:
    handler = BlockSyncHandler()

    with tempfile.NamedTemporaryFile("w", suffix=".dwg", delete=False) as f:
        f.write("DUMMY_SOURCE")
        src_path = f.name

    try:
        # Source blocks
        src_blocks = [
            BlockDefinition("PUMP_A", 10, "SIG_100"),
            BlockDefinition("VALVE_B", 5, "SIG_200", nested_blocks=["INTERNAL_SEAL"]),
            BlockDefinition("INTERNAL_SEAL", 2, "SIG_SEAL_V1"),
        ]

        # Scenario 1: Clean sync with collision policy Ignore
        dest_1 = {"PUMP_A": BlockDefinition("PUMP_A", 10, "SIG_100")}
        res_ignore = handler.execute(
            BlockSyncArgs(source_path=src_path, collision_policy="Ignore"),
            src_blocks,
            dest_1,
        )
        assert res_ignore.status == "OK"
        # PUMP_A ignored, VALVE_B and INTERNAL_SEAL imported
        assert "VALVE_B" in res_ignore.synced_block_names
        assert "PUMP_A" not in res_ignore.synced_block_names

        # Scenario 2: Collision policy Replace
        dest_2 = {"PUMP_A": BlockDefinition("PUMP_A", 8, "SIG_OLD")}
        res_replace = handler.execute(
            BlockSyncArgs(source_path=src_path, collision_policy="Replace"),
            src_blocks,
            dest_2,
        )
        assert res_replace.status == "OK"
        assert "PUMP_A" in res_replace.synced_block_names
        assert dest_2["PUMP_A"].geometry_signature == "SIG_100"

        # Scenario 3: FAIL-CLOSED GATE on Nested Semantic Collision
        # dest has INTERNAL_SEAL with DIFFERENT geometry signature!
        dest_conflict = {
            "INTERNAL_SEAL": BlockDefinition("INTERNAL_SEAL", 2, "SIG_SEAL_DIFFERENT_V2"),
        }
        with pytest.raises(SemanticCollisionError, match="FAIL_CLOSED: NESTED_SEMANTIC_COLLISION"):
            handler.execute(
                BlockSyncArgs(source_path=src_path, collision_policy="Ignore"),
                src_blocks,
                dest_conflict,
            )
    finally:
        os.remove(src_path)
