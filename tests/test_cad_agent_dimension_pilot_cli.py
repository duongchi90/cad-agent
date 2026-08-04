from __future__ import annotations

import json
from pathlib import Path

from cad_agent.cli import main
from dimension_pilot_fixtures import (
    dimension_pilot_cli_args,
    write_dimension_pilot_inputs,
)


ROOT = Path(__file__).resolve().parents[1]


def test_dimension_pilot_cli_writes_dxf_and_not_run_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)

    assert main(dimension_pilot_cli_args(inputs)) == 0

    evidence = json.loads(inputs.output_evidence.read_text(encoding="utf-8"))
    assert evidence["offline_passed"] is True
    assert evidence["acceptance"] == "NOT_RUN"
    assert inputs.output_dxf.is_file()
    assert "OFFLINE PASS" in capsys.readouterr().out


def test_dimension_pilot_cli_refuses_overwrite_and_bad_suffix(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.output_evidence.write_text("keep", encoding="utf-8")

    assert main(dimension_pilot_cli_args(inputs)) == 2
    assert inputs.output_evidence.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err

    inputs = write_dimension_pilot_inputs(tmp_path / "bad")
    inputs.output_dxf = inputs.output_dxf.with_suffix(".dwg")
    assert main(dimension_pilot_cli_args(inputs)) == 2
    assert "must be a .dxf" in capsys.readouterr().err


def test_dimension_pilot_cli_records_blockers_without_dxf(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path, disconnected=True)

    assert main(dimension_pilot_cli_args(inputs)) == 1

    evidence = json.loads(inputs.output_evidence.read_text(encoding="utf-8"))
    assert evidence["offline_passed"] is False
    assert evidence["acceptance"] == "NOT_RUN"
    assert "underconstrained" in {
        item["code"] for item in evidence["blockers"]
    }
    assert not inputs.output_dxf.exists()
    assert "underconstrained" in capsys.readouterr().err


def test_dimension_pilot_cli_requires_private_outputs_outside_repository(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.output_dxf = ROOT / "must-not-create-private-pilot.dxf"

    assert main(dimension_pilot_cli_args(inputs)) == 2

    assert not inputs.output_dxf.exists()
    assert "outside the repository" in capsys.readouterr().err


def test_dimension_pilot_cli_rejects_missing_input_and_bad_evidence_suffix(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.semantic_ir.unlink()

    assert main(dimension_pilot_cli_args(inputs)) == 2
    assert "existing file" in capsys.readouterr().err

    inputs = write_dimension_pilot_inputs(tmp_path / "bad-evidence")
    inputs.output_evidence = inputs.output_evidence.with_suffix(".txt")
    assert main(dimension_pilot_cli_args(inputs)) == 2
    assert "must be a .json" in capsys.readouterr().err


def test_dimension_pilot_cli_reads_setup_evidence_strictly(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = write_dimension_pilot_inputs(tmp_path)
    inputs.setup_evidence_path.write_text("{}", encoding="utf-8")

    assert main(dimension_pilot_cli_args(inputs)) == 2
    assert "drawing_setup_evidence" in capsys.readouterr().err
