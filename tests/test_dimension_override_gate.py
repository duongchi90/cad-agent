from __future__ import annotations

import pytest

from cad_agent.dimension_override_gate import (
    DimensionInput,
    build_dimension_register,
    evaluate_dimension_gate,
    is_reference_dimension_text,
    parse_dimension_numeric_value,
)
from cad_agent.visual_contracts import (
    VisualContractError,
    require_dimension_gate_ready,
    validate_visual_contract,
)

SOURCE_SHA = "1" * 64


def _ref_from(tag: str) -> dict[str, str]:
    return {"type": "DATUM", "id": f"DATUM_{tag}"}


def _dim(
    dimension_id: str,
    raw_text: str,
    measured_geometry_value: float | None,
    center_xy: tuple[float, float],
    *,
    orientation_deg: float | None = 0.0,
    critical: bool = True,
    with_refs: bool = True,
) -> DimensionInput:
    return DimensionInput(
        dimension_id=dimension_id,
        raw_text=raw_text,
        measured_geometry_value=measured_geometry_value,
        center_xy=center_xy,
        orientation_deg=orientation_deg,
        critical=critical,
        from_ref=_ref_from(f"{dimension_id}_A") if with_refs else None,
        to_ref=_ref_from(f"{dimension_id}_B") if with_refs else None,
    )


def test_parse_dimension_numeric_and_reference_detection() -> None:
    assert parse_dimension_numeric_value("4500") == pytest.approx(4500.0)
    assert parse_dimension_numeric_value("1,250.5 mm") == pytest.approx(1250.5)
    assert parse_dimension_numeric_value("(1200)") == pytest.approx(1200.0)
    assert parse_dimension_numeric_value("<>") is None
    assert parse_dimension_numeric_value("") is None

    assert is_reference_dimension_text("(1200)") is True
    assert is_reference_dimension_text("REF 4500") is True
    assert is_reference_dimension_text("4500 (THAM KHẢO)") is True
    assert is_reference_dimension_text("~4500") is True
    assert is_reference_dimension_text("4500") is False


def test_unitless_insunits_zero_without_verified_calibration_fails_closed() -> None:
    dims = [_dim("DIM-001", "4500", 4500.0, (100.0, 100.0))]
    evaluated = evaluate_dimension_gate(dims, insunits=0, verified_scale_to_mm=None)
    assert len(evaluated) == 1
    assert evaluated[0].role == "AMBIGUOUS"
    assert evaluated[0].status == "UNRESOLVED"
    assert evaluated[0].reason_code == "UNITLESS_UNCALIBRATED"
    assert evaluated[0].unit is None

    register = build_dimension_register(
        evaluated,
        dims,
        run_id="RUN-GATE-001",
        source_sha256=SOURCE_SHA,
        page_id="PAGE-001",
        view_id="PLAN",
    )
    validated = validate_visual_contract(register, contract="dimension_register")
    assert validated["summary"] == {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    with pytest.raises(VisualContractError, match="blocks"):
        require_dimension_gate_ready(validated)


def test_unitless_with_verified_calibration_and_driving_dims_passes_gate() -> None:
    dims = [
        _dim("DIM-LOA", "64500", 64500.0, (5000.0, 0.0)),
        _dim("DIM-LOA-DUP", "64500", 64500.0, (5200.0, 400.0)),
        _dim("DIM-REF-BREADTH", "(12600)", 13000.0, (0.0, 200.0), with_refs=False),
    ]
    evaluated = evaluate_dimension_gate(dims, insunits=0, verified_scale_to_mm=1.0)
    by_id = {item.dimension_id: item for item in evaluated}

    assert by_id["DIM-LOA"].role == "DRIVING"
    assert by_id["DIM-LOA"].status == "CONFIRMED"
    assert by_id["DIM-LOA-DUP"].role == "DERIVED"
    assert by_id["DIM-LOA-DUP"].status == "CONFIRMED"
    assert by_id["DIM-LOA-DUP"].redundant_of == "DIM-LOA"
    assert by_id["DIM-REF-BREADTH"].role == "REFERENCE"
    assert by_id["DIM-REF-BREADTH"].status == "CONFIRMED"

    register = build_dimension_register(
        evaluated,
        dims,
        run_id="RUN-GATE-002",
        source_sha256=SOURCE_SHA,
        page_id="PAGE-001",
        view_id="PROFILE",
    )
    validated = validate_visual_contract(register, contract="dimension_register")
    assert validated["summary"] == {"confirmed": 3, "unresolved": 0, "conflicts": 0}
    require_dimension_gate_ready(validated)


def test_override_mismatch_emits_conflict_and_blocks_gate() -> None:
    dims = [_dim("DIM-BEAM", "14000", 12600.0, (200.0, 300.0))]
    evaluated = evaluate_dimension_gate(dims, insunits=4)
    assert evaluated[0].role == "CONFLICT"
    assert evaluated[0].status == "CONFLICT"
    assert evaluated[0].reason_code == "DIMENSION_OVERRIDE_CONFLICT"
    assert evaluated[0].override_diff_mm == pytest.approx(1400.0)

    register = build_dimension_register(
        evaluated,
        dims,
        run_id="RUN-GATE-003",
        source_sha256=SOURCE_SHA,
        page_id="PAGE-001",
        view_id="SECTION",
    )
    with pytest.raises(VisualContractError, match="blocks"):
        require_dimension_gate_ready(register)


def test_colocated_conflicting_dimensions_are_flagged_when_same_orientation() -> None:
    dims = [
        _dim("DIM-SPAN-1", "12600", 12600.0, (1000.0, 500.0), orientation_deg=90.0),
        _dim("DIM-SPAN-2", "13400", 13400.0, (1250.0, 520.0), orientation_deg=90.0),
        _dim("DIM-ORTHO", "4200", 4200.0, (1100.0, 510.0), orientation_deg=0.0),
    ]
    evaluated = evaluate_dimension_gate(dims, insunits=4)
    by_id = {item.dimension_id: item for item in evaluated}

    assert by_id["DIM-SPAN-1"].role == "CONFLICT"
    assert by_id["DIM-SPAN-1"].status == "CONFLICT"
    assert by_id["DIM-SPAN-1"].reason_code == "COLOCATED_DIMENSION_CONFLICT"
    assert by_id["DIM-SPAN-2"].role == "CONFLICT"
    assert "DIM-SPAN-1" in by_id["DIM-SPAN-2"].conflicting_with
    assert by_id["DIM-ORTHO"].role == "DRIVING"
    assert by_id["DIM-ORTHO"].status == "CONFIRMED"

    register = build_dimension_register(
        evaluated,
        dims,
        run_id="RUN-GATE-004",
        source_sha256=SOURCE_SHA,
        page_id="PAGE-001",
        view_id="PLAN",
    )
    assert register["summary"] == {"confirmed": 1, "unresolved": 0, "conflicts": 2}
    with pytest.raises(VisualContractError, match="blocks"):
        require_dimension_gate_ready(register)


def test_missing_attachment_refs_for_driving_dim_fails_closed() -> None:
    dims = [_dim("DIM-NO-REFS", "4500", 4500.0, (0.0, 0.0), with_refs=False)]
    evaluated = evaluate_dimension_gate(dims, insunits=4)
    assert evaluated[0].role == "AMBIGUOUS"
    assert evaluated[0].status == "UNRESOLVED"
    assert evaluated[0].reason_code == "MISSING_ATTACHMENT_REFS"

    register = build_dimension_register(
        evaluated,
        dims,
        run_id="RUN-GATE-005",
        source_sha256=SOURCE_SHA,
        page_id="PAGE-001",
        view_id="SIDE",
    )
    validate_visual_contract(register, contract="dimension_register")
    with pytest.raises(VisualContractError, match="blocks"):
        require_dimension_gate_ready(register)
