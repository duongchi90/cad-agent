from __future__ import annotations

import ast
import copy
import inspect
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


# -------------------------------------------------------- Task 8 RED ---


def _task8_manifest_module() -> object:
    import cad_agent.manifest as manifest

    return manifest


def _task8_hash(seed: str) -> str:
    return seed * 64


def _task8_custody_reference() -> dict[str, object]:
    return {
        "schema_version": "source-custody-reference-1.0",
        "bundle_id": "BUNDLE-001",
        "run_id": "RUN-001",
        "approved_root_id": "ROOT-001",
        "approved_root_revision": "ROOT-REV-001",
        "approved_root_configuration_sha256": _task8_hash("a"),
        "identity_scheme": "HMAC-SHA-256",
        "identity_scheme_version": "r1c-file-identity-v1",
        "identity_key_revision": "KEY-REV-001",
        "numeric_policy_version": "r1c-numeric-v1",
        "source_bundle_sha256": _task8_hash("b"),
        "source_custody_sha256": _task8_hash("c"),
        "status": "READY",
        "item_count": 2,
        "eligible_count": 2,
        "blocking_count": 0,
    }


def _task8_fusion_reference() -> dict[str, object]:
    return {
        "schema_version": "source-fusion-reference-1.0",
        "source_bundle_sha256": _task8_hash("b"),
        "source_custody_sha256": _task8_hash("c"),
        "approved_root_id": "ROOT-001",
        "approved_root_revision": "ROOT-REV-001",
        "approved_root_configuration_sha256": _task8_hash("a"),
        "numeric_policy_version": "r1c-numeric-v1",
        "tolerance_policy_version": "r1c-tolerance-v1",
        "fusion_input_sha256": _task8_hash("d"),
        "source_fusion_sha256": _task8_hash("e"),
        "status": "READY",
        "conflict_count": 0,
        "unresolved_count": 0,
    }


def _task8_evaluation_reference() -> dict[str, object]:
    return {
        "schema_version": "source-fusion-evaluation-reference-1.0",
        "source_fusion_sha256": _task8_hash("e"),
        "fusion_input_sha256": _task8_hash("d"),
        "evaluation_time_source": "SERVER-CLOCK-EVIDENCE-1",
        "evaluation_time_evidence_sha256": _task8_hash("f"),
        "expiry_policy_version": "r1c-expiry-v1",
        "status": "REUSABLE",
        "blocking_count": 0,
    }


def _task8_public(name: str) -> object:
    value = getattr(_task8_manifest_module(), name, None)
    assert callable(value), f"Task8 public API is missing: {name}"
    return value


def test_task8_freezes_constants_and_existing_owner_api_pattern() -> None:
    manifest = _task8_manifest_module()
    assert manifest.SOURCE_CUSTODY_REFERENCE_SCHEMA_VERSION == (
        "source-custody-reference-1.0"
    )
    assert manifest.SOURCE_FUSION_REFERENCE_SCHEMA_VERSION == (
        "source-fusion-reference-1.0"
    )
    assert manifest.SOURCE_FUSION_EVALUATION_REFERENCE_SCHEMA_VERSION == (
        "source-fusion-evaluation-reference-1.0"
    )
    expected = {
        "validate_source_custody_reference",
        "bind_source_custody",
        "require_source_custody_match",
        "validate_source_fusion_reference",
        "bind_source_fusion",
        "require_source_fusion_match",
        "validate_source_fusion_evaluation_reference",
        "bind_source_fusion_evaluation",
        "require_source_fusion_evaluation_match",
    }
    expected_parameters = {
        "validate_source_custody_reference": ["value"],
        "validate_source_fusion_reference": ["value"],
        "validate_source_fusion_evaluation_reference": ["value"],
        "bind_source_custody": ["manifest", "custody"],
        "require_source_custody_match": ["manifest", "custody"],
        "bind_source_fusion": ["manifest", "fusion"],
        "require_source_fusion_match": ["manifest", "fusion"],
        "bind_source_fusion_evaluation": ["manifest", "evaluation"],
        "require_source_fusion_evaluation_match": [
            "manifest",
            "evaluation",
        ],
    }
    for name in expected:
        function = _task8_public(name)
        assert list(inspect.signature(function).parameters) == expected_parameters[name]


@pytest.mark.parametrize(
    ("validator_name", "reference_factory"),
    [
        ("validate_source_custody_reference", _task8_custody_reference),
        ("validate_source_fusion_reference", _task8_fusion_reference),
        (
            "validate_source_fusion_evaluation_reference",
            _task8_evaluation_reference,
        ),
    ],
)
def test_task8_closed_references_validate_and_deep_copy(
    validator_name: str,
    reference_factory: object,
) -> None:
    reference = reference_factory()
    original = copy.deepcopy(reference)
    normalized = _task8_public(validator_name)(reference)
    assert normalized == reference
    assert normalized is not reference
    assert reference == original


@pytest.mark.parametrize(
    ("validator_name", "reference_factory", "field", "value"),
    [
        (
            "validate_source_custody_reference",
            _task8_custody_reference,
            "schema_version",
            "source-custody-reference-2.0",
        ),
        (
            "validate_source_custody_reference",
            _task8_custody_reference,
            "source_custody_sha256",
            "A" * 64,
        ),
        (
            "validate_source_custody_reference",
            _task8_custody_reference,
            "eligible_count",
            True,
        ),
        (
            "validate_source_fusion_reference",
            _task8_fusion_reference,
            "status",
            "BLOCKED_UNRESOLVED",
        ),
        (
            "validate_source_fusion_reference",
            _task8_fusion_reference,
            "conflict_count",
            -1,
        ),
        (
            "validate_source_fusion_evaluation_reference",
            _task8_evaluation_reference,
            "evaluation_time_evidence_sha256",
            "Z" * 64,
        ),
        (
            "validate_source_fusion_evaluation_reference",
            _task8_evaluation_reference,
            "blocking_count",
            1,
        ),
    ],
)
def test_task8_references_reject_malformed_version_hash_status_or_count(
    validator_name: str,
    reference_factory: object,
    field: str,
    value: object,
) -> None:
    reference = reference_factory()
    reference[field] = value
    with pytest.raises(ManifestError):
        _task8_public(validator_name)(reference)


@pytest.mark.parametrize(
    ("validator_name", "reference_factory", "extra"),
    [
        (
            "validate_source_custody_reference",
            _task8_custody_reference,
            "items",
        ),
        (
            "validate_source_fusion_reference",
            _task8_fusion_reference,
            "resolution_references",
        ),
        (
            "validate_source_fusion_evaluation_reference",
            _task8_evaluation_reference,
            "evaluation_time_utc",
        ),
    ],
)
def test_task8_references_reject_full_evidence_or_authority_fields(
    validator_name: str,
    reference_factory: object,
    extra: str,
) -> None:
    reference = reference_factory()
    reference[extra] = []
    with pytest.raises(ManifestError):
        _task8_public(validator_name)(reference)


@pytest.mark.parametrize(
    ("bind_name", "match_name", "reference_factory", "key"),
    [
        (
            "bind_source_custody",
            "require_source_custody_match",
            _task8_custody_reference,
            "source_custody",
        ),
        (
            "bind_source_fusion",
            "require_source_fusion_match",
            _task8_fusion_reference,
            "source_fusion",
        ),
        (
            "bind_source_fusion_evaluation",
            "require_source_fusion_evaluation_match",
            _task8_evaluation_reference,
            "source_fusion_evaluation",
        ),
    ],
)
def test_task8_equal_bind_is_idempotent_unequal_rebind_fails_and_match_is_exact(
    bind_name: str,
    match_name: str,
    reference_factory: object,
    key: str,
) -> None:
    manifest = _legacy_manifest()
    reference = reference_factory()
    original = copy.deepcopy(manifest)
    bind = _task8_public(bind_name)
    match = _task8_public(match_name)
    bound = bind(manifest, reference)
    assert manifest == original
    assert bound is not manifest
    assert bound[key] == reference
    assert bind(bound, copy.deepcopy(reference)) == bound
    match(bound, reference)

    changed = copy.deepcopy(reference)
    hash_field = next(field for field in changed if field.endswith("sha256"))
    changed[hash_field] = _task8_hash("9")
    with pytest.raises(ManifestError):
        bind(bound, changed)
    with pytest.raises(ManifestError):
        match(bound, changed)


@pytest.mark.parametrize("key", ["source_custody", "source_fusion", "source_fusion_evaluation"])
def test_task8_legacy_manifest_and_pdf_readers_preserve_absent_optional_reference(
    tmp_path: Path,
    key: str,
) -> None:
    image_path = tmp_path / f"{key}-run-manifest.json"
    write_manifest(image_path, _legacy_manifest())
    loaded_image = read_manifest(image_path)
    assert key not in loaded_image

    pdf_path = tmp_path / f"{key}-pdf-run-manifest.json"
    write_manifest(pdf_path, _legacy_pdf_manifest())
    loaded_pdf = read_pdf_manifest(pdf_path)
    assert key not in loaded_pdf


@pytest.mark.parametrize(
    ("key", "reference_factory"),
    [
        ("source_custody", _task8_custody_reference),
        ("source_fusion", _task8_fusion_reference),
        ("source_fusion_evaluation", _task8_evaluation_reference),
    ],
)
def test_task8_pdf_reader_validates_each_present_optional_reference(
    tmp_path: Path,
    key: str,
    reference_factory: object,
) -> None:
    manifest = _legacy_pdf_manifest()
    manifest[key] = reference_factory()
    path = tmp_path / f"{key}-pdf-run-manifest.json"
    write_manifest(path, manifest)
    loaded = read_pdf_manifest(path)
    assert loaded[key] == manifest[key]

    manifest[key]["unexpected"] = True
    write_manifest(path, manifest)
    with pytest.raises(ManifestError):
        read_pdf_manifest(path)


def test_task8_manifest_and_pdf_keep_one_writer_and_no_evidence_persistence() -> None:
    manifest_tree = ast.parse(MANIFEST_MODULE.read_text(encoding="utf-8"))
    pdf_tree = ast.parse(PDF_MODULE.read_text(encoding="utf-8"))
    assert sum(
        isinstance(node, ast.FunctionDef) and node.name == "write_manifest"
        for node in manifest_tree.body
    ) == 1
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "write_manifest"
        for node in pdf_tree.body
    )
    forbidden = {
        "items",
        "alias_groups",
        "page_locators",
        "region_locators",
        "render_provenance",
        "primitive_observations",
        "semantic_observations",
        "evaluation_time_utc",
        "blocking_codes",
        "path",
        "file_object_identity_token",
    }
    for factory in (
        _task8_custody_reference,
        _task8_fusion_reference,
        _task8_evaluation_reference,
    ):
        assert not forbidden.intersection(factory())
