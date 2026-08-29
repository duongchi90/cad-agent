"""M1 Golden Path Web preflight through the existing live-review seam.

This is acceptance-only lookahead. It composes accepted owners and stops at the
real AutoCAD/FileIPC boundary; it must not introduce a second execution path.
"""

from __future__ import annotations

import json
from pathlib import Path

import cad_agent.cli as cad_cli
from cad_agent.live import load_build_evidence
from cad_agent.manifest import sha256_file
from tests.test_cad_agent_cli import _drawing as _write_synthetic_drawing
from tests.test_cad_agent_live import FakeMCPClient


_DXF_TYPE = {
    "line": "LINE",
    "circle": "CIRCLE",
    "arc": "ARC",
    "text": "TEXT",
}


class _ReadOnlyMechanicalClient(FakeMCPClient):
    def __init__(self) -> None:
        super().__init__(fail_entity_get=False)
        self.save_calls = 0
        self.mutation_calls = 0

    def drawing_save(self, path: str | None = None) -> None:
        self.save_calls += 1

    def drawing_save_as_dxf(self, path: str) -> None:
        self.save_calls += 1

    def entity_create_line(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.mutation_calls += 1
        return super().entity_create_line(*args, **kwargs)

    def entity_create_circle(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.mutation_calls += 1
        return super().entity_create_circle(*args, **kwargs)

    def entity_create_arc(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.mutation_calls += 1
        return super().entity_create_arc(*args, **kwargs)

    def annotation_create_text(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.mutation_calls += 1
        return super().annotation_create_text(*args, **kwargs)

    def entity_erase(self, entity_id: str) -> None:
        self.mutation_calls += 1
        super().entity_erase(entity_id)


def _preload_exact_build(client: FakeMCPClient, build: object) -> None:
    for primitive_id, handle in build.handle_by_primitive_id.items():
        written = build.written_geometry_by_primitive_id[primitive_id]
        kind = written["type"]
        geometry = {key: value for key, value in written.items() if key != "type"}
        client.preload_entity(
            str(handle),
            _DXF_TYPE[kind],
            build.layer_by_primitive_id.get(primitive_id, "0"),
            geometry,
        )

    for validation_id, handle in build.dimension_handle_by_cross_validation_id.items():
        expected = build.written_dimension_by_cross_validation_id[validation_id]
        client.preload_entity(
            str(handle),
            "DIMENSION",
            expected["layer"],
            {"measurement": expected["measurement"]},
        )


def test_m1_existing_owners_reach_mechanical_review_boundary_without_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "approved-synthetic.png"
    output = tmp_path / "run"
    report_path = tmp_path / "mechanical-review.json"
    dispatcher = tmp_path / "mcp_dispatch.lsp"
    _write_synthetic_drawing(source)
    dispatcher.write_text("; synthetic preflight only\n", encoding="utf-8")

    assert cad_cli.main(
        [
            "run",
            "--input",
            str(source),
            "--output-dir",
            str(output),
            "--scale-mm-per-px",
            "0.5",
            "--calibration-approval",
            "m1-lookahead-synthetic-approval",
        ]
    ) == 0

    manifest_path = output / "run-manifest.json"
    dxf = output / "staged.dxf"
    evidence = output / "build-evidence.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None
    assert all(record["state"] == "completed" for record in manifest["stages"].values())

    build = load_build_evidence(evidence, dxf)
    client = _ReadOnlyMechanicalClient()
    _preload_exact_build(client, build)
    before_sha = sha256_file(dxf)

    monkeypatch.setattr(cad_cli, "_live_client", lambda *_args, **_kwargs: client)

    assert cad_cli.main(
        [
            "mechanical-review",
            "--dxf",
            str(dxf),
            "--build-evidence",
            str(evidence),
            "--hwnd",
            "42",
            "--dispatcher",
            str(dispatcher),
            "--report",
            str(report_path),
            "--timeout-s",
            "10",
        ]
    ) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["operation"] == "mechanical-review"
    assert report["dxf_sha256"] == before_sha == sha256_file(dxf)
    assert report["review"]["passed"] is True
    assert report["review"]["structural_checked"] == len(build.handle_by_primitive_id)
    assert report["review"]["dimension_checked"] == len(
        build.dimension_handle_by_cross_validation_id
    )
    assert client.opened_path == str(dxf)
    assert client.save_calls == 0
    assert client.mutation_calls == 0
    assert "save_state" not in report
    assert "repair" not in report
