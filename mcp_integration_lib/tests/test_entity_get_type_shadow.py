from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "mcp_integration_lib" / "mcp_dispatch.lsp"


def _extract_defun(source: str, name: str) -> str:
    marker = f"(defun {name} "
    start = source.index(marker)
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated AutoLISP defun: {name}")


def _local_bindings(defun_source: str, name: str) -> set[str]:
    match = re.search(
        rf"\(defun\s+{re.escape(name)}\s+\((?P<parameters>[^)]*)\)",
        defun_source,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"missing parameter list for {name}"
    parameters = match.group("parameters")
    if "/" not in parameters:
        return set()
    return set(parameters.split("/", 1)[1].split())


def test_entity_get_type_shadow_cannot_reach_handle_validation_or_projection() -> None:
    source = DISPATCHER.read_text(encoding="utf-8")
    entity_get = _extract_defun(source, "mcp-op-entity-get")
    entity_from_handle = _extract_defun(source, "mcp-entity-from-handle")
    valid_handle = _extract_defun(source, "mcp-valid-handle-p")

    # The failing live path starts before projection: the entity-get operation
    # validates the handle through a helper that calls AutoLISP's TYPE function.
    assert "(mcp-entity-from-handle" in entity_get
    assert "(mcp-valid-handle-p value)" in entity_from_handle
    assert "(type value)" in valid_handle

    # Keep representative LINE and CIRCLE projection coverage in the same
    # causal assertion instead of reducing the regression to a name grep.
    line_match = re.search(r'\(\(=\s+([A-Za-z][A-Za-z0-9_-]*)\s+"LINE"\)', entity_get)
    circle_match = re.search(r'\(\(=\s+([A-Za-z][A-Za-z0-9_-]*)\s+"CIRCLE"\)', entity_get)
    assert line_match is not None and circle_match is not None
    entity_type = line_match.group(1)
    assert circle_match.group(1) == entity_type
    assert entity_type in _local_bindings(entity_get, "mcp-op-entity-get")
    assert '(cons "start" (mcp-array' in entity_get
    assert '(cons "center" (mcp-array' in entity_get
    assert "(mcp-object pairs)" in entity_get

    # AutoLISP dynamically scopes local symbols. A local TYPE binding therefore
    # shadows the built-in called by mcp-valid-handle-p and must be forbidden.
    assert entity_type.casefold() != "type", (
        "mcp-op-entity-get must not dynamically shadow AutoLISP's built-in TYPE "
        "while validating handles and constructing LINE/CIRCLE projections"
    )
