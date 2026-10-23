from __future__ import annotations

from pathlib import Path

import pytest

import cad_agent.run_dimension_observer as observer_cli


def test_cli_forwards_explicit_anchor_coordinate_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def run(**kwargs: object) -> Path:
        captured.update(kwargs)
        return tmp_path / "run" / "dimension-register.json"

    monkeypatch.setattr(observer_cli, "run_dimension_observer", run)
    result = observer_cli.main([
        "--run-id", "RUN-CLI-ANCHOR-MODE",
        "--source", str(tmp_path / "source.png"),
        "--page-id", "PAGE-001",
        "--view-id", "SIDE",
        "--output", str(tmp_path / "run"),
        "--anchor-coordinate-mode", "page",
    ])

    assert result == 0
    assert captured["anchor_coordinate_mode"] == "page"


def test_cli_rejects_unknown_anchor_coordinate_mode() -> None:
    with pytest.raises(SystemExit):
        observer_cli.build_parser().parse_args([
            "--run-id", "RUN-CLI-INVALID",
            "--source", "source.png",
            "--page-id", "PAGE-001",
            "--view-id", "SIDE",
            "--output", "out",
            "--anchor-coordinate-mode", "view",
        ])
