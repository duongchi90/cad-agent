"""R2 Gate-0 RED contract; production adapter is intentionally absent."""

from __future__ import annotations

import ast
from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256


_OFFLINE_EXECUTION = {
    "autocad_dotnet": "NOT RUN",
    "file_ipc": "NOT RUN",
    "live_cad": "NOT RUN",
    "private_cad": "SKIP",
}


def _adapter_module():
    """Turn the intentionally missing production owner into attributable RED."""
    try:
        return importlib.import_module("cad_agent.base_cad_adapter")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "R2 RED: cad_agent.base_cad_adapter is not implemented; "
            "Gate-0 production write is not authorized yet"
        )
        raise AssertionError from exc


def _world_frame() -> dict[str, object]:
    return {
        "name": "WORLD",
        "origin": [0.0, 0.0, 0.0],
        "x_axis": [1.0, 0.0, 0.0],
        "y_axis": [0.0, 1.0, 0.0],
    }


@pytest.fixture
def expected_exact_base():
    return {
        "source_sha256": "source-sha",
        "source_revision": "rev-7",
        "xref_sha256": "xref-sha",
        "units": "mm",
        "ucs": _world_frame(),
        "wcs": _world_frame(),
    }


@pytest.fixture
def exact_base_packet():
    return {
        "source_sha256": "source-sha",
        "source_revision": "rev-7",
        "xref_sha256": "xref-sha",
        "units": "mm",
        "ucs": _world_frame(),
        "wcs": _world_frame(),
        "entities": [
            {
                "logical_id": "component-A",
                "handle": "A",
                "layer": "0",
                "block": "*Model_Space",
                "transform": "I",
            },
            {
                "logical_id": "component-B",
                "handle": "B",
                "layer": "FRAME",
                "block": "*Model_Space",
                "transform": "I",
            },
        ],
    }


def _prepare(adapter, *, packet, expected_exact_base):
    return adapter.prepare_exact_base(
        packet=packet,
        expected_exact_base=expected_exact_base,
    )


def test_gate0_execution_scope_is_literal_offline_only():
    assert _OFFLINE_EXECUTION == {
        "autocad_dotnet": "NOT RUN",
        "file_ipc": "NOT RUN",
        "live_cad": "NOT RUN",
        "private_cad": "SKIP",
    }


def test_exact_base_provenance_is_immutable(exact_base_packet, expected_exact_base):
    adapter = _adapter_module()
    result = _prepare(
        adapter,
        packet=exact_base_packet,
        expected_exact_base=expected_exact_base,
    )
    exact_base_packet["source_revision"] = "rev-8"
    exact_base_packet["entities"][0]["handle"] = "MUTATED"
    expected_exact_base["source_revision"] = "rev-mutated"

    assert result.provenance.source_revision == "rev-7"
    assert result.provenance.source_sha256 == "source-sha"
    assert result.provenance.xref_sha256 == "xref-sha"
    assert result.evidence["entities"][0]["handle"] == "A"


@pytest.mark.parametrize(
    ("field", "stale_value"),
    [
        ("source_sha256", "different-source"),
        ("source_revision", "rev-8"),
    ],
)
def test_stale_source_fails_against_distinct_expected_baseline(
    exact_base_packet,
    expected_exact_base,
    field,
    stale_value,
):
    adapter = _adapter_module()
    stale = deepcopy(exact_base_packet)
    stale[field] = stale_value

    with pytest.raises(adapter.BaseCadAdapterError, match="STALE_EXACT_BASE"):
        _prepare(adapter, packet=stale, expected_exact_base=expected_exact_base)


def test_stale_xref_fails_against_distinct_expected_baseline(
    exact_base_packet,
    expected_exact_base,
):
    adapter = _adapter_module()
    stale = deepcopy(exact_base_packet)
    stale["xref_sha256"] = "different-xref"

    with pytest.raises(adapter.BaseCadAdapterError, match="STALE_EXACT_BASE"):
        _prepare(adapter, packet=stale, expected_exact_base=expected_exact_base)


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (lambda packet: packet.__setitem__("units", None), "UNITS_AMBIGUITY"),
        (lambda packet: packet.__setitem__("units", "in"), "UNITS_CONFLICT"),
        (lambda packet: packet["ucs"].pop("y_axis"), "UCS_AMBIGUITY"),
        (lambda packet: packet["wcs"].pop("x_axis"), "WCS_AMBIGUITY"),
        (
            lambda packet: packet["ucs"].__setitem__("name", "LOCAL"),
            "FRAME_CONFLICT",
        ),
    ],
)
def test_units_ucs_wcs_ambiguity_is_independently_observable(
    exact_base_packet,
    expected_exact_base,
    mutate,
    error_code,
):
    adapter = _adapter_module()
    ambiguous = deepcopy(exact_base_packet)
    mutate(ambiguous)

    with pytest.raises(adapter.BaseCadAdapterError, match=error_code):
        _prepare(adapter, packet=ambiguous, expected_exact_base=expected_exact_base)


def test_duplicate_handles_fail_closed(exact_base_packet, expected_exact_base):
    adapter = _adapter_module()
    duplicate = deepcopy(exact_base_packet)
    duplicate["entities"][1]["handle"] = "A"

    with pytest.raises(adapter.BaseCadAdapterError, match="DUPLICATE_HANDLE"):
        _prepare(adapter, packet=duplicate, expected_exact_base=expected_exact_base)


def test_duplicate_logical_ids_fail_separately_from_handles(
    exact_base_packet,
    expected_exact_base,
):
    adapter = _adapter_module()
    duplicate = deepcopy(exact_base_packet)
    duplicate["entities"][1]["logical_id"] = "component-A"
    assert duplicate["entities"][0]["handle"] != duplicate["entities"][1]["handle"]

    with pytest.raises(adapter.BaseCadAdapterError, match="DUPLICATE_LOGICAL_ID"):
        _prepare(adapter, packet=duplicate, expected_exact_base=expected_exact_base)


def test_five_replays_and_entity_permutations_have_one_canonical_identity(
    exact_base_packet,
    expected_exact_base,
):
    adapter = _adapter_module()
    results = []
    for replay in range(5):
        packet = deepcopy(exact_base_packet)
        if replay % 2:
            packet["entities"] = list(reversed(packet["entities"]))
        results.append(
            _prepare(
                adapter,
                packet=packet,
                expected_exact_base=deepcopy(expected_exact_base),
            )
        )

    assert all(result.identity == results[0].identity for result in results)
    assert all(result.evidence == results[0].evidence for result in results)
    assert results[0].identity == canonical_json_sha256(results[0].evidence)


def test_adapter_imports_only_existing_hash_owner_and_no_second_authority():
    adapter = _adapter_module()
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    imported_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            imported_names.update(alias.name for alias in node.names)

    assert "cad_agent.drawing_contracts" in imported_modules
    assert "canonical_json_sha256" in imported_names
    assert "hashlib" not in imported_modules
    assert "json.dumps" not in source

    forbidden_import_tokens = {
        "autocad",
        "cad_parser",
        "dwg",
        "dxf",
        "ezdxf",
        "extraction",
        "file_ipc",
        "fitz",
        "manifest",
        "mcp_integration_lib",
        "pillow",
        "pil",
        "primitive_ir",
        "pypdf",
        "registry",
        "renderer",
        "revision",
        "socket",
        "store",
        "subprocess",
        "transport",
        "visual_evidence",
    }
    lowered_imports = {module.lower() for module in imported_modules}
    for token in forbidden_import_tokens:
        assert all(token not in module for module in lowered_imports)
