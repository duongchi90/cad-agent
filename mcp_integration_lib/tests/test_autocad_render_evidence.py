from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from mcp_integration_lib import autocad_render_evidence as contract


FIXTURE = Path(__file__).with_name("fixtures") / "autocad-render-evidence.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _request() -> dict[str, object]:
    return copy.deepcopy(_fixture()["request"])


def _png_result() -> dict[str, object]:
    return copy.deepcopy(_fixture()["png"])


def _pdf_result() -> dict[str, object]:
    return copy.deepcopy(_fixture()["pdf"])


def _assert_rejected(payload: object, request: object | None = None) -> None:
    with pytest.raises(contract.AutoCADRenderEvidenceError):
        contract.validate_render_evidence(payload, request=request)


def test_fixture_round_trip_validates_png_and_pdf_evidence() -> None:
    fixture = _fixture()
    request = contract.validate_render_request(fixture["request"])
    pdf_request = {**request, "artifact_kind": "PDF"}

    assert contract.validate_render_evidence(fixture["png"], request=request)["artifact_kind"] == "PNG"
    assert contract.validate_render_evidence(fixture["pdf"], request=pdf_request)["artifact_kind"] == "PDF"


def test_request_builder_is_deterministic_and_matches_fixture() -> None:
    expected = _request()
    built = contract.build_render_evidence_request(
        request_id="render-request-001",
        run_id="run-001",
        drawing_sha256="a" * 64,
        latest_mutation_sha256="b" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"identity": "layout-001", "name": "Layout1"},
        artifact_kind="PNG",
        render_options={
            "background": "white",
            "dpi": 300,
            "fit_to_paper": True,
            "paper_size": "A4",
            "plot_style": "monochrome.ctb",
        },
        requested_at="2026-08-05T08:00:00Z",
    )

    assert built == expected
    assert built == contract.build_render_evidence_request(
        request_id="render-request-001",
        run_id="run-001",
        drawing_sha256="a" * 64,
        latest_mutation_sha256="b" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"name": "Layout1", "identity": "layout-001"},
        artifact_kind="PNG",
        render_options={
            "plot_style": "monochrome.ctb",
            "fit_to_paper": True,
            "paper_size": "A4",
            "dpi": 300,
            "background": "white",
        },
        requested_at="2026-08-05T08:00:00Z",
    )


@pytest.mark.parametrize("location", ["root", "layout", "render_options", "artifact"])
def test_unknown_fields_are_rejected_at_every_contract_level(location: str) -> None:
    payload = _png_result()
    target = payload if location == "root" else payload[location]
    target["unexpected"] = "reject-me"
    _assert_rejected(payload, _request())


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("request_id", "other-request"),
        ("run_id", "other-run"),
        ("drawing_sha256", "f" * 64),
        ("latest_mutation_sha256", "f" * 64),
        ("visual_run_manifest_sha256", "f" * 64),
        ("layout", {"identity": "other-layout", "name": "Layout1"}),
        ("artifact_kind", "PDF"),
        ("render_options", {"background": "black", "dpi": 300, "fit_to_paper": True, "paper_size": "A4", "plot_style": "monochrome.ctb"}),
    ],
)
def test_request_result_identity_mismatch_is_rejected(field: str, replacement: object) -> None:
    payload = _png_result()
    payload[field] = replacement
    _assert_rejected(payload, _request())


@pytest.mark.parametrize(
    "mutation",
    [
        {"changed": True},
        {"dbmod_after": 1},
        {"dbmod_before": 1, "dbmod_after": 0},
    ],
)
def test_mutation_or_changed_result_is_rejected(mutation: dict[str, object]) -> None:
    payload = _png_result()
    payload.update(mutation)
    _assert_rejected(payload, _request())


@pytest.mark.parametrize(
    "relative_path",
    ["C:/temp/evidence.png", "/tmp/evidence.png", "\\\\server\\share\\evidence.png", "evidence/../evidence.png", "../evidence.png", "evidence\\file.png"],
)
def test_absolute_or_traversal_artifact_paths_are_rejected(relative_path: str) -> None:
    payload = _png_result()
    payload["artifact"]["relative_path"] = relative_path
    _assert_rejected(payload, _request())


@pytest.mark.parametrize("field", ["drawing_sha256", "latest_mutation_sha256", "visual_run_manifest_sha256"])
@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "a" * 65, "not-a-hash"])
def test_identity_hashes_must_be_lowercase_sha256(field: str, value: str) -> None:
    payload = _request()
    payload[field] = value
    with pytest.raises(contract.AutoCADRenderEvidenceError):
        contract.validate_render_request(payload)


@pytest.mark.parametrize("artifact_kind", ["JPG", "SVG", "png", "pdf"])
def test_unsupported_artifact_kind_is_rejected(artifact_kind: str) -> None:
    payload = _request()
    payload["artifact_kind"] = artifact_kind
    with pytest.raises(contract.AutoCADRenderEvidenceError):
        contract.validate_render_request(payload)


def test_unsupported_renderer_is_rejected() -> None:
    payload = _png_result()
    payload["renderer"] = "PYTHON"
    _assert_rejected(payload, _request())


@pytest.mark.parametrize("field", ["verdict", "pass", "approval", "repair", "publication"])
def test_verdict_approval_repair_and_publication_fields_are_rejected(field: str) -> None:
    payload = _png_result()
    payload[field] = "forbidden"
    _assert_rejected(payload, _request())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requested_at", "2026-08-05T08:00:00+01:00"),
        ("requested_at", "2026-08-05 08:00:00Z"),
        ("capture_timestamp", "not-a-timestamp"),
    ],
)
def test_timestamps_must_be_explicit_utc_iso8601(field: str, value: str) -> None:
    payload = _request() if field == "requested_at" else _png_result()
    payload[field] = value
    with pytest.raises(contract.AutoCADRenderEvidenceError):
        if field == "requested_at":
            contract.validate_render_request(payload)
        else:
            contract.validate_render_evidence(payload, request=_request())


@pytest.mark.parametrize(
    ("field", "value"),
    [("width", 0), ("height", -1), ("width", True), ("height", 100_001)],
)
def test_png_dimensions_must_be_positive_bounded_integers(field: str, value: object) -> None:
    payload = _png_result()
    payload["artifact"][field] = value
    _assert_rejected(payload, _request())


@pytest.mark.parametrize("page_count", [0, -1, True, 100_001])
def test_pdf_page_count_must_be_positive_bounded_integer(page_count: object) -> None:
    payload = _pdf_result()
    payload["artifact"]["page_count"] = page_count
    _assert_rejected(payload, {**_request(), "artifact_kind": "PDF"})


def test_dbmod_values_are_required_and_equal() -> None:
    payload = _png_result()
    del payload["dbmod_before"]
    _assert_rejected(payload, _request())


def test_contract_module_has_no_autoCAD_or_transport_imports() -> None:
    tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported.isdisjoint({"ctypes", "dotnet_ipc", "subprocess"})
