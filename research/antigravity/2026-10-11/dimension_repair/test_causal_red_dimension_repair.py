"""
test_causal_red_dimension_repair.py — Deterministic Public Causal RED for
Headless Linear Dimension & Associativity Repair in DXF Builder.

Proves 5 distinct failure modes on current production behavior (Strategy A):
- RED-1: Broken / deleted dimension entity handle in DXF
- RED-2: Tampered defpoint coordinates / measurement drift
- RED-3: Corrupted layer on DIMENSION entity
- RED-4: Broken line feature binding / out-of-sync dimension endpoints
- RED-5: Fail-safe skip on untracked / ambiguous validation ID
"""

from __future__ import annotations

import os
import tempfile
import pytest

from primitive_ir_lib.models import (
    Calibration, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
from dxf_builder_lib.reviewer import review_dxf

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from dimension_repair_engine import (
    repair_dimensions_strategy_a,
    repair_dimensions_strategy_d,
)


def _build_fixture(tmp_dir: str, length: float = 100.0, approved: float = 100.0):
    doc = PrimitiveIRDocument(
        source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=[
            Primitive(
                id="l1", type="line", source="geo", confidence=1.0,
                trace=Trace(bbox_px=(0, 0, 10, 10)),
                geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(length, 0)),
            )
        ],
    )
    dxf_path = os.path.join(tmp_dir, "test.dxf")
    spec = NativeLinearDimensionSpec(
        id="DIM-01",
        geometry_primitive_id="l1",
        approved_value_mm=approved,
        source_ref="TEST-REF",
    )
    built = build_dxf(doc, dxf_path, build_dimensions=True, dimension_specs=[spec])
    return built, "DIM-01", dxf_path


def test_causal_red_1_deleted_dimension_handle():
    """RED-1: Deleted DIMENSION entity handle in DXF.

    Strategy A (production repair_dxf) skips the mismatch; second review FAILS.
    Strategy D reconstructs the dimension entity; second review PASSES.
    """
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")

    with tempfile.TemporaryDirectory() as tmp:
        built, dim_id, dxf_path = _build_fixture(tmp)
        initial_review = review_dxf(built)
        assert initial_review.passed is True

        # Tamper: delete the DIMENSION entity from ModelSpace
        doc = ezdxf.readfile(dxf_path)
        handle = built.dimension_handle_by_cross_validation_id[dim_id]
        entity = doc.entitydb.get(handle)
        assert entity is not None
        doc.modelspace().delete_entity(entity)
        doc.saveas(dxf_path)

        tampered_review = review_dxf(built)
        assert tampered_review.passed is False
        assert any(dim_id in m for m in tampered_review.dimension_mismatches)

        # Strategy A: Fails to repair
        rep_a = repair_dimensions_strategy_a(built, tampered_review.dimension_mismatches)
        assert rep_a.repaired_count == 0
        assert rep_a.skipped_count == len(tampered_review.dimension_mismatches)
        review_after_a = review_dxf(built)
        assert review_after_a.passed is False

        # Strategy D: Successfully repairs
        rep_d = repair_dimensions_strategy_d(built, tampered_review.dimension_mismatches)
        assert rep_d.repaired_count == 1
        assert rep_d.skipped_count == 0
        assert dim_id in rep_d.repaired_validation_ids

        review_after_d = review_dxf(built)
        assert review_after_d.passed is True
        assert len(review_after_d.dimension_mismatches) == 0


def test_causal_red_2_measurement_and_defpoint_drift():
    """RED-2: Tampered defpoint coordinates causing measurement drift.

    Strategy A skips the mismatch; second review FAILS.
    Strategy D reconstructs the dimension entity; second review PASSES.
    """
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")

    with tempfile.TemporaryDirectory() as tmp:
        built, dim_id, dxf_path = _build_fixture(tmp, length=100.0, approved=100.0)

        # Tamper: alter defpoint3 coordinate in DXF
        doc = ezdxf.readfile(dxf_path)
        handle = built.dimension_handle_by_cross_validation_id[dim_id]
        entity = doc.entitydb.get(handle)
        entity.dxf.defpoint3 = (150.0, 0.0, 0.0)
        doc.saveas(dxf_path)

        tampered_review = review_dxf(built)
        assert tampered_review.passed is False
        assert any("expected measurement 100.0" in m or "approved measurement" in m
                   for m in tampered_review.dimension_mismatches)

        # Strategy A fails
        rep_a = repair_dimensions_strategy_a(built, tampered_review.dimension_mismatches)
        assert rep_a.repaired_count == 0
        review_after_a = review_dxf(built)
        assert review_after_a.passed is False

        # Strategy D succeeds
        rep_d = repair_dimensions_strategy_d(built, tampered_review.dimension_mismatches)
        assert rep_d.repaired_count == 1
        review_after_d = review_dxf(built)
        assert review_after_d.passed is True
        assert len(review_after_d.dimension_mismatches) == 0


def test_causal_red_3_corrupted_layer():
    """RED-3: Corrupted layer on DIMENSION entity.

    Strategy A skips the mismatch; second review FAILS.
    Strategy D repairs the layer and re-renders; second review PASSES.
    """
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")

    with tempfile.TemporaryDirectory() as tmp:
        built, dim_id, dxf_path = _build_fixture(tmp)

        # Tamper: change layer to CORRUPTED_LAYER
        doc = ezdxf.readfile(dxf_path)
        handle = built.dimension_handle_by_cross_validation_id[dim_id]
        entity = doc.entitydb.get(handle)
        entity.dxf.layer = "CORRUPTED_LAYER"
        doc.saveas(dxf_path)

        tampered_review = review_dxf(built)
        assert tampered_review.passed is False
        assert any("expected layer 'DIMENSIONS', actual 'CORRUPTED_LAYER'" in m
                   for m in tampered_review.dimension_mismatches)

        # Strategy A fails
        rep_a = repair_dimensions_strategy_a(built, tampered_review.dimension_mismatches)
        assert rep_a.repaired_count == 0
        review_after_a = review_dxf(built)
        assert review_after_a.passed is False

        # Strategy D succeeds
        rep_d = repair_dimensions_strategy_d(built, tampered_review.dimension_mismatches)
        assert rep_d.repaired_count == 1
        review_after_d = review_dxf(built)
        assert review_after_d.passed is True
        assert len(review_after_d.dimension_mismatches) == 0


def test_causal_red_4_broken_feature_binding():
    """RED-4: Broken line feature binding / out-of-sync dimension endpoints.

    Strategy A skips the mismatch; second review FAILS.
    Strategy D reconstructs dimension from ground truth; second review PASSES.
    """
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")

    with tempfile.TemporaryDirectory() as tmp:
        built, dim_id, dxf_path = _build_fixture(tmp)

        # Tamper: shift defpoint2 away from line start
        doc = ezdxf.readfile(dxf_path)
        handle = built.dimension_handle_by_cross_validation_id[dim_id]
        entity = doc.entitydb.get(handle)
        entity.dxf.defpoint2 = (10.0, 10.0, 0.0)
        doc.saveas(dxf_path)

        tampered_review = review_dxf(built)
        assert tampered_review.passed is False
        assert any("DIMENSION feature binding unavailable" in m
                   for m in tampered_review.dimension_mismatches)

        # Strategy A fails
        rep_a = repair_dimensions_strategy_a(built, tampered_review.dimension_mismatches)
        assert rep_a.repaired_count == 0
        review_after_a = review_dxf(built)
        assert review_after_a.passed is False

        # Strategy D succeeds
        rep_d = repair_dimensions_strategy_d(built, tampered_review.dimension_mismatches)
        assert rep_d.repaired_count == 1
        review_after_d = review_dxf(built)
        assert review_after_d.passed is True
        assert len(review_after_d.dimension_mismatches) == 0


def test_causal_red_5_untracked_validation_id_failsafe():
    """RED-5: Untracked or ambiguous validation ID fail-safe handling.

    When an unknown validation ID is passed, Strategy D safely skips it without crash
    and does not corrupt existing valid dimensions.
    """
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")

    with tempfile.TemporaryDirectory() as tmp:
        built, dim_id, dxf_path = _build_fixture(tmp)

        # Synthetic mismatch with non-existent validation ID
        fake_mismatches = ["UNKNOWN-DIM-999: missing written dimension evidence"]

        rep_d = repair_dimensions_strategy_d(built, fake_mismatches)
        assert rep_d.repaired_count == 0
        assert rep_d.skipped_count == 1
        assert "UNKNOWN-DIM-999" in rep_d.skipped_validation_ids

        # Existing valid dimension is untouched and passes review
        review = review_dxf(built)
        assert review.passed is True
