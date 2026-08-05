from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from cad_agent.manifest import (
    ManifestError,
    SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION,
    bind_source_bundle,
    read_manifest,
    require_source_bundle_match,
    validate_source_bundle_reference,
    write_manifest,
)
from cad_agent.pdf import read_pdf_manifest
from cad_agent.source_bundle import source_bundle_sha256, validate_source_bundle


FIXTURE = Path(__file__).parent / "fixtures" / "source-bundle.json"
MANIFEST_MODULE = Path(__file__).parents[1] / "cad_agent" / "manifest.py"
PDF_MODULE = Path(__file__).parents[1] / "cad_agent" / "pdf.py"


def _bundle() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _reference() -> dict[str, object]:
    bundle = validate_source_bundle(_bundle())
    return {
        "schema_version": "source-bundle-reference-1.0",
        "bundle_id": bundle["bundle_id"],
        "run_id": bundle["run_id"],
        "source_bundle_sha256": source_bundle_sha256(bundle),
        "item_count": len(bundle["items"]),
    }


def _legacy_manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source": {"name": "input.png", "sha256": "a" * 64, "kind": "image"},
        "configuration": {"scale_mm_per_px": 1.0},
        "approvals": {"calibration": {"approved": True, "reference": "TEST"}},
        "stages": {
            name: {"state": "pending", "artifact": None, "sha256": None, "details": None}
            for name in ("primitive_ir", "semantic_ir", "dxf")
        },
        "release_profile": "DRAFT_REFERENCE",
        "authoritative_release_eligible": False,
        "drawing_setup_evidence": None,
    }


def _legacy_pdf_manifest() -> dict[str, object]:
    return {
        "schema_version": "pdf-run-1.0",
        "source": {"name": "input.pdf", "sha256": "a" * 64, "kind": "pdf"},
        "configuration": {"scale_mm_per_px": 1.0, "dpi": 144, "auto_ocr_roi": False},
        "approvals": {"calibration": {"approved": True, "reference": "TEST"}},
        "render": {"state": "pending", "artifact": "pdf/manifest.json", "sha256": None, "details": None},
        "pages": [],
        "release_profile": "DRAFT_REFERENCE",
        "authoritative_release_eligible": False,
        "drawing_setup_evidence": None,
    }


def test_source_bundle_reference_is_closed_and_valid() -> None:
    reference = _reference()
    normalized = validate_source_bundle_reference(reference)
    assert normalized == reference
    assert normalized is not reference
    assert SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION == "source-bundle-reference-1.0"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "source-bundle-reference-2.0"),
        ("bundle_id", "bad id"),
        ("run_id", "bad id"),
        ("source_bundle_sha256", "A" * 64),
        ("item_count", 0),
        ("item_count", 10_001),
        ("item_count", True),
        ("unexpected", True),
    ],
)
def test_source_bundle_reference_fails_closed(field: str, value: object) -> None:
    reference = _reference()
    reference[field] = value
    with pytest.raises(ManifestError):
        validate_source_bundle_reference(reference)


@pytest.mark.parametrize("field", ["schema_version", "bundle_id", "run_id", "source_bundle_sha256", "item_count"])
def test_source_bundle_reference_requires_every_field(field: str) -> None:
    reference = _reference()
    del reference[field]
    with pytest.raises(ManifestError, match=field):
        validate_source_bundle_reference(reference)


def test_source_bundle_reference_rejects_non_mapping() -> None:
    with pytest.raises(ManifestError, match="reference"):
        validate_source_bundle_reference([])


def test_bind_source_bundle_returns_copy_and_small_reference_only() -> None:
    manifest = _legacy_manifest()
    original_manifest = copy.deepcopy(manifest)
    bundle = _bundle()
    original_bundle = copy.deepcopy(bundle)

    bound = bind_source_bundle(manifest, bundle)

    assert manifest == original_manifest
    assert bundle == original_bundle
    assert bound is not manifest
    assert bound["source_bundle"] == _reference()
    assert set(bound["source_bundle"]) == {
        "schema_version",
        "bundle_id",
        "run_id",
        "source_bundle_sha256",
        "item_count",
    }
    assert "items" not in bound["source_bundle"]


def test_binding_is_idempotent_but_conflicting_rebind_is_refused() -> None:
    first = bind_source_bundle(_legacy_manifest(), _bundle())
    assert bind_source_bundle(first, _bundle()) == first

    changed = _bundle()
    changed["items"][0]["sha256"] = "d" * 64
    with pytest.raises(ManifestError, match="conflict"):
        bind_source_bundle(first, changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bundle_id", "OTHER-BUNDLE"),
        ("run_id", "RUN-OTHER"),
        ("source_bundle_sha256", "d" * 64),
        ("item_count", 4),
    ],
)
def test_require_source_bundle_match_checks_all_bound_values(field: str, value: object) -> None:
    bound = bind_source_bundle(_legacy_manifest(), _bundle())
    bound["source_bundle"][field] = value
    with pytest.raises(ManifestError, match="does not match"):
        require_source_bundle_match(bound, _bundle())


def test_require_source_bundle_match_accepts_same_bundle() -> None:
    bound = bind_source_bundle(_legacy_manifest(), _bundle())
    require_source_bundle_match(bound, _bundle())


def test_require_source_bundle_match_rejects_changed_source_bundle() -> None:
    bound = bind_source_bundle(_legacy_manifest(), _bundle())
    changed = _bundle()
    changed["items"][0]["sha256"] = "d" * 64
    with pytest.raises(ManifestError, match="does not match"):
        require_source_bundle_match(bound, changed)


def test_require_source_bundle_match_requires_binding() -> None:
    with pytest.raises(ManifestError, match="binding"):
        require_source_bundle_match(_legacy_manifest(), _bundle())


@pytest.mark.parametrize("manifest", [None, [], "manifest"])
def test_binding_and_match_require_mapping_manifest(manifest: object) -> None:
    with pytest.raises(ManifestError, match="Manifest"):
        bind_source_bundle(manifest, _bundle())
    with pytest.raises(ManifestError, match="Manifest"):
        require_source_bundle_match(manifest, _bundle())


def test_malformed_full_source_bundle_is_translated_to_manifest_error() -> None:
    invalid = _bundle()
    invalid["items"] = []
    with pytest.raises(ManifestError, match="SourceBundle"):
        bind_source_bundle(_legacy_manifest(), invalid)


def test_legacy_image_manifest_is_read_without_injected_reference(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    write_manifest(path, _legacy_manifest())

    loaded = read_manifest(path)

    assert "source_bundle" not in loaded
    assert loaded["release_profile"] == "DRAFT_REFERENCE"


def test_bound_image_manifest_round_trips_reference(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    write_manifest(path, bind_source_bundle(_legacy_manifest(), _bundle()))

    loaded = read_manifest(path)

    assert loaded["source_bundle"] == _reference()


def test_image_reader_rejects_malformed_optional_reference(tmp_path: Path) -> None:
    manifest = _legacy_manifest()
    manifest["source_bundle"] = {**_reference(), "unexpected": True}
    path = tmp_path / "run-manifest.json"
    write_manifest(path, manifest)

    with pytest.raises(ManifestError, match="unsupported"):
        read_manifest(path)


def test_legacy_pdf_manifest_is_read_without_injected_reference(tmp_path: Path) -> None:
    path = tmp_path / "pdf-run-manifest.json"
    write_manifest(path, _legacy_pdf_manifest())

    loaded = read_pdf_manifest(path)

    assert "source_bundle" not in loaded
    assert loaded["release_profile"] == "DRAFT_REFERENCE"


def test_bound_pdf_manifest_round_trips_reference(tmp_path: Path) -> None:
    path = tmp_path / "pdf-run-manifest.json"
    write_manifest(path, {**_legacy_pdf_manifest(), "source_bundle": _reference()})

    loaded = read_pdf_manifest(path)

    assert loaded["source_bundle"] == _reference()


def test_pdf_reader_rejects_malformed_optional_reference(tmp_path: Path) -> None:
    manifest = _legacy_pdf_manifest()
    manifest["source_bundle"] = {**_reference(), "source_bundle_sha256": "A" * 64}
    path = tmp_path / "pdf-run-manifest.json"
    write_manifest(path, manifest)

    with pytest.raises(ManifestError):
        read_pdf_manifest(path)


def _function_nodes(path: Path, names: set[str]) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]


def test_binding_adapter_functions_do_not_add_runtime_or_filesystem_calls() -> None:
    functions = _function_nodes(
        MANIFEST_MODULE,
        {"validate_source_bundle_reference", "bind_source_bundle", "require_source_bundle_match"},
    )
    assert {node.name for node in functions} == {
        "validate_source_bundle_reference",
        "bind_source_bundle",
        "require_source_bundle_match",
    }
    forbidden_modules = {
        "primitive_ir_lib",
        "semantic_ir_lib",
        "agent_lib",
        "dxf_builder_lib",
        "mcp_integration_lib",
        "autocad_plugin",
        "ctypes",
        "subprocess",
    }
    forbidden_calls = {"open", "read_text", "write_text", "add_parser", "set_defaults"}
    for function in functions:
        for node in ast.walk(function):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                assert not any(module == item or module.startswith(f"{item}.") for item in forbidden_modules)
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                assert name not in forbidden_calls


def test_manifest_owner_keeps_one_writer_and_pdf_adds_no_cli_commands() -> None:
    manifest_tree = ast.parse(MANIFEST_MODULE.read_text(encoding="utf-8"))
    pdf_tree = ast.parse(PDF_MODULE.read_text(encoding="utf-8"))
    manifest_writers = [
        node for node in manifest_tree.body if isinstance(node, ast.FunctionDef) and node.name == "write_manifest"
    ]
    pdf_writers = [
        node for node in pdf_tree.body if isinstance(node, ast.FunctionDef) and node.name == "write_manifest"
    ]
    assert len(manifest_writers) == 1
    assert not pdf_writers
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"add_parser", "set_defaults"}
        for node in ast.walk(pdf_tree)
    )
