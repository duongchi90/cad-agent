"""Exercise the staged native-review CLI's exact dimension acceptance seam."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent import cli
from cad_agent.live import write_build_evidence
from dxf_builder_lib.tests.dxf_test_support import build_native_dimension_consumer_fixture
from dxf_builder_lib.reviewer import review_dxf
from mcp_integration_lib.mcp_client import FakeMCPClient, MCPTimeoutError, MCPToolError


@pytest.mark.parametrize(
    "length,approved,display,want_exit",
    [
        (80.0, 79.0, "79", 1),
        (80.0, 79.0, "", 1),
        (1_000_000_000.0, 999_999_999.5, "", 1),
        (79.0, 79.0, "", 0),
        (80.0, None, "79", 0),
    ],
    ids=["wrong-exact-hidden-by-display", "wrong-exact", "large-exact", "correct-exact", "display-only"],
)
def test_mechanical_review_consumes_exact_dimension_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    length: float,
    approved: float | None,
    display: str,
    want_exit: int,
) -> None:
    built, records, actual_measurement = build_native_dimension_consumer_fixture(
        tmp_path, length, approved, display,
    )
    candidate = Path(built.output_path)
    assert actual_measurement == length
    assert review_dxf(built).passed == (want_exit == 0)

    evidence = tmp_path / "build-evidence.json"
    write_build_evidence(evidence, built)
    before = candidate.read_bytes(), evidence.read_bytes()
    client = FakeMCPClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    # Only the external native transport is replaced; acceptance is real code.
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    report_path = tmp_path / "review.json"
    exit_code = cli.main([
        "mechanical-review", "--dxf", str(candidate),
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "transport.lsp"),
        "--report", str(report_path),
    ])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == want_exit
    assert report["review"]["passed"] == (want_exit == 0)
    assert report["review"]["dimension_checked"] == 1
    assert not report["review"]["geometry_degraded"]
    if want_exit:
        assert any("approved" in message for message in report["review"]["mismatches"])
    assert (candidate.read_bytes(), evidence.read_bytes()) == before


@pytest.mark.parametrize("error_type", [MCPTimeoutError, MCPToolError])
@pytest.mark.parametrize("approved", [79.0, None], ids=["exact", "reference"])
def test_mechanical_review_does_not_accept_unreadable_exact_dimension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    approved: float | None,
) -> None:
    built, records, _ = build_native_dimension_consumer_fixture(
        tmp_path, 80.0, approved, "79",
    )
    dimension_handle = next(iter(built.dimension_handle_by_cross_validation_id.values()))

    class DimensionReadFailureClient(FakeMCPClient):
        def entity_get(self, handle: str):
            if handle == dimension_handle:
                raise error_type("native DIMENSION measurement unavailable")
            return super().entity_get(handle)

    client = DimensionReadFailureClient(fail_entity_get=False)
    for handle, entity_type, layer, geometry in records:
        client.preload_entity(handle, entity_type, layer, geometry)
    monkeypatch.setattr(cli, "_live_client", lambda *_args: client)
    evidence = tmp_path / "build-evidence.json"
    write_build_evidence(evidence, built)
    candidate = Path(built.output_path)
    before = candidate.read_bytes(), evidence.read_bytes()
    report_path = tmp_path / "review.json"
    exit_code = cli.main([
        "mechanical-review", "--dxf", str(candidate),
        "--build-evidence", str(evidence), "--hwnd", "1",
        "--dispatcher", str(tmp_path / "transport.lsp"),
        "--report", str(report_path),
    ])
    review = json.loads(report_path.read_text(encoding="utf-8"))["review"]
    assert review["geometry_checked"] == len(built.handle_by_primitive_id)
    assert review["dimension_checked"] == 1
    assert review["geometry_degraded"]
    assert exit_code == (1 if approved is not None else 0)
    assert review["passed"] == (approved is None)
    if approved is not None:
        assert any("approved_value_mm" in message for message in review["mismatches"])
    assert (candidate.read_bytes(), evidence.read_bytes()) == before
