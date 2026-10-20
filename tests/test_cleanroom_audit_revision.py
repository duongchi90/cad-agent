"""tests/test_cleanroom_audit_revision.py.

Cleanroom unit & parity tests for Batch S4:
Auditing, Standardization, Batch Stamps & Revision Diff Engines.
Verifies:
  - TagAuditHandler (cadmind-tag-audit)
  - StyleStandardizeHandler (cadmind-style-standardize)
  - StampBatchHandler (cadmind-stamp-batch)
  - DrawingAuditHandler (cadmind-drawing-audit)
  - CompareRevisionHandler (cadmind-compare-revision)

Strict 1:1 cleanroom fidelity with physical C# source:
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave13Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave14Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave16Handlers.cs
  - src/CadMind.Cleanroom.AutoCadPlugin/Handlers/TierBWave17Handlers.cs
"""

import pytest

from cad_agent.cleanroom_audit_revision import (
    CompareRevisionArgs,
    CompareRevisionHandler,
    DegenerateGeometryError,
    DrawingAuditArgs,
    DrawingAuditHandler,
    LayerAuditInfo,
    StampBatchArgs,
    StampBatchHandler,
    StyleStandardizeArgs,
    StyleStandardizeHandler,
    TagAuditArgs,
    TagAuditHandler,
    TagItemInput,
    TextStyleProperties,
)
from cad_agent.cleanroom_mechanical import Point2D


# ============================================================================
# 1. TAG AUDIT TESTS (cadmind-tag-audit)
# ============================================================================


class TestTagAuditHandler:
    def setup_method(self):
        self.handler = TagAuditHandler()

    def test_tag_audit_duplicates_and_missing_sequence(self):
        items = [
            TagItemInput("H1", "TAG-01", "A-ANNO-TAG"),
            TagItemInput("H2", "TAG-02", "A-ANNO-TAG"),
            TagItemInput("H3", "TAG-01", "A-ANNO-TAG"),  # Duplicate
            TagItemInput("H4", "TAG-04", "A-ANNO-TAG"),  # Missing TAG-03!
            TagItemInput("H5", "TAG-05", "A-ANNO-TAG"),
        ]
        args = TagAuditArgs(
            prefix="TAG-",
            check_sequence=True,
            tags=items,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.total_scanned == 5
        assert res.unique_tags_count == 4
        assert res.duplicate_tags_count == 1
        assert res.duplicate_tags == ["TAG-01"]
        # Sequence 1, 2, 4, 5 -> missing 3
        assert res.missing_sequence_numbers == [3]

    def test_tag_audit_layer_filtering(self):
        items = [
            TagItemInput("H1", "EQ-101", "M-EQUIP"),
            TagItemInput("H2", "EQ-102", "E-EQUIP"),  # Different layer
            TagItemInput("H3", "EQ-103", "M-EQUIP"),
        ]
        args = TagAuditArgs(
            layer="M-EQUIP",
            tags=items,
        )
        res = self.handler.execute(args)
        assert res.total_scanned == 2
        assert res.unique_tags_count == 2
        assert len(res.items) == 2

    def test_tag_audit_empty_and_non_numeric_suffixes(self):
        # Empty tags list
        res_empty = self.handler.execute(TagAuditArgs(tags=[]))
        assert res_empty.total_scanned == 0
        assert res_empty.unique_tags_count == 0

        # Non-numeric suffixes ignored for sequence check
        items = [
            TagItemInput("H1", "TAG-A", "0"),
            TagItemInput("H2", "TAG-B", "0"),
        ]
        res_alpha = self.handler.execute(TagAuditArgs(prefix="TAG-", check_sequence=True, tags=items))
        assert res_alpha.total_scanned == 2
        assert len(res_alpha.missing_sequence_numbers) == 0


# ============================================================================
# 2. STYLE STANDARDIZE TESTS (cadmind-style-standardize)
# ============================================================================


class TestStyleStandardizeHandler:
    def setup_method(self):
        self.handler = StyleStandardizeHandler()

    def test_style_standardize_resolution_and_missing(self):
        text_rules = {
            "Standard": TextStyleProperties(font="arial.ttf", height=2.5),
            "NonExistentStyle": TextStyleProperties(font="isocp.shx", height=3.5),
        }
        dim_rules = {
            "ISO-25": {"DIMTXT": 2.5, "DIMASZ": 2.5},
            "OldDimStyle": {"DIMTXT": 3.0},
        }
        args = StyleStandardizeArgs(
            text_styles=text_rules,
            dim_styles=dim_rules,
            available_text_styles=["STANDARD", "ROMANS"],
            available_dim_styles=["ISO-25", "ARCHITECTURAL"],
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.text_styles_updated == 1
        assert res.text_styles_missing == ["NonExistentStyle"]
        assert res.dim_styles_updated == 1
        assert res.dim_styles_missing == ["OldDimStyle"]
        assert len(res.details) == 4

    def test_style_standardize_empty_inputs(self):
        res = self.handler.execute(StyleStandardizeArgs())
        assert res.status == "OK"
        assert res.text_styles_updated == 0
        assert res.dim_styles_updated == 0


# ============================================================================
# 3. STAMP BATCH TESTS (cadmind-stamp-batch)
# ============================================================================


class TestStampBatchHandler:
    def setup_method(self):
        self.handler = StampBatchHandler()

    def test_stamp_batch_geometry_and_layouts(self):
        args = StampBatchArgs(
            text="FOR REVIEW ONLY",
            layouts=["Model", "A1-Plan", "A1-Sections"],
            point=[200.0, 150.0],
            height=20.0,
            rotation=45.0,
            layer="WATERMARK",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.text == "FOR REVIEW ONLY"
        assert res.stamped_layouts_count == 3
        assert res.stamped_layout_names == ["Model", "A1-Plan", "A1-Sections"]
        assert res.layer == "WATERMARK"
        assert res.text_position == Point2D(200.0, 150.0)
        assert res.text_rotation == 45.0
        # 4 rotated bounding box vertices
        assert len(res.border_vertices) == 4

    def test_stamp_batch_rejections(self):
        with pytest.raises(DegenerateGeometryError, match="EMPTY_TEXT"):
            self.handler.execute(StampBatchArgs(text=""))

        with pytest.raises(DegenerateGeometryError, match="Height"):
            self.handler.execute(StampBatchArgs(text="APPROVED", height=0.0))

    def test_stamp_batch_rotation_ortho_and_custom_origin(self):
        # 0 rotation
        res0 = self.handler.execute(StampBatchArgs(text="CONFIDENTIAL", point=[0.0, 0.0], rotation=0.0))
        assert res0.text_rotation == 0.0
        # 90 rotation
        res90 = self.handler.execute(StampBatchArgs(text="VOID", point=[50.0, 50.0], rotation=90.0))
        assert res90.text_rotation == 90.0


# ============================================================================
# 4. DRAWING AUDIT TESTS (cadmind-drawing-audit)
# ============================================================================


class TestDrawingAuditHandler:
    def setup_method(self):
        self.handler = DrawingAuditHandler()

    def test_drawing_audit_empty_and_frozen_layers(self):
        layers = [
            LayerAuditInfo("0", is_empty=False, is_off=False, is_frozen=False),
            LayerAuditInfo("DEFPOINTS", is_empty=False, is_off=False, is_frozen=False),
            LayerAuditInfo("UNUSED_LAYER_1", is_empty=True, is_off=False, is_frozen=False),
            LayerAuditInfo("UNUSED_LAYER_2", is_empty=True, is_off=False, is_frozen=False),
            LayerAuditInfo("HIDDEN_LAYER", is_empty=False, is_off=True, is_frozen=False),
            LayerAuditInfo("FROZEN_LAYER", is_empty=False, is_off=False, is_frozen=True),
        ]
        args = DrawingAuditArgs(
            layers=layers,
            entities_on_layer_0=15,
            total_model_space_entities=1240,
            block_count=28,
            text_style_count=4,
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.total_layers == 6
        assert res.empty_layers_count == 2
        assert res.empty_layers == ["UNUSED_LAYER_1", "UNUSED_LAYER_2"]
        assert res.off_or_frozen_layers_count == 2
        assert res.off_or_frozen_layers == ["HIDDEN_LAYER", "FROZEN_LAYER"]
        assert res.entities_on_layer_0 == 15
        assert res.total_model_space_entities == 1240
        assert res.block_count == 28


# ============================================================================
# 5. COMPARE REVISION TESTS (cadmind-compare-revision)
# ============================================================================


class TestCompareRevisionHandler:
    def setup_method(self):
        self.handler = CompareRevisionHandler()

    def test_compare_revision_entity_differences(self):
        current = {
            ("WALLS", "LINE"): 120,
            ("DOORS", "INSERT"): 15,
            ("COLUMNS", "LWPOLYLINE"): 24,
        }
        other = {
            ("WALLS", "LINE"): 100,      # Current has +20
            ("DOORS", "INSERT"): 18,     # Current has -3
            ("COLUMNS", "LWPOLYLINE"): 24, # Equal
            ("BEAMS", "LINE"): 30,       # Current has -30 (0 - 30)
        }
        args = CompareRevisionArgs(
            current_entities=current,
            other_entities=other,
            compared_file="RevA_Final.dwg",
        )
        res = self.handler.execute(args)

        assert res.status == "OK"
        assert res.compared_file == "RevA_Final.dwg"
        assert res.current_entities_total == 120 + 15 + 24
        assert res.other_entities_total == 100 + 18 + 24 + 30
        # Total diffs = |20| + |-3| + |-30| = 53
        assert res.total_differences == 53
        # 3 categories differ (WALLS/LINE, DOORS/INSERT, BEAMS/LINE)
        assert len(res.differences) == 3

        diff_dict = {(d.layer, d.entity_type): d.difference for d in res.differences}
        assert diff_dict[("WALLS", "LINE")] == 20
        assert diff_dict[("DOORS", "INSERT")] == -3
        assert diff_dict[("BEAMS", "LINE")] == -30

    def test_compare_revision_identical_drawings(self):
        ents = {("LAYER1", "LINE"): 50}
        res = self.handler.execute(CompareRevisionArgs(current_entities=ents, other_entities=ents))
        assert res.status == "OK"
        assert res.total_differences == 0
        assert len(res.differences) == 0

    def test_compare_revision_empty_inputs(self):
        res = self.handler.execute(CompareRevisionArgs())
        assert res.status == "OK"
        assert res.total_differences == 0
        assert res.current_entities_total == 0
        assert res.other_entities_total == 0
