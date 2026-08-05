"""Check the mandatory Reuse Declaration on implementation pull requests."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_SECTIONS = (
    "Existing capability inspected:",
    "Existing API reused:",
    "Adapter required:",
    "New capability genuinely missing:",
    "Files allowed to change:",
    "Files forbidden to duplicate:",
    "Compatibility behavior:",
    "Migration and rollback path:",
)
IMPLEMENTATION_PREFIXES = (
    "cad_agent/",
    "primitive_ir_lib/",
    "semantic_ir_lib/",
    "agent_lib/",
    "dxf_builder_lib/",
    "mcp_integration_lib/",
    "autocad_plugin/",
    "contracts/",
    "scripts/",
    ".github/workflows/",
)
IMPLEMENTATION_ROOT_FILES = {
    "pyproject.toml",
    "requirements/windows-py311.lock",
}


def implementation_change(paths: list[str]) -> bool:
    """Return whether changed paths require a Reuse Declaration."""

    normalized_paths = (
        path.lstrip("\ufeff").strip().replace("\\", "/") for path in paths
    )
    return any(
        path in IMPLEMENTATION_ROOT_FILES
        or path.startswith(IMPLEMENTATION_PREFIXES)
        for path in normalized_paths
    )


def _section_value(line: str, section: str) -> str | None:
    candidate = line.strip()
    while candidate[:1] in {"-", "*", ">"}:
        candidate = candidate[1:].lstrip()
    if not candidate.startswith(section):
        return None
    return candidate[len(section) :].strip()


def missing_sections(body: str) -> tuple[str, ...]:
    """Return required declaration fields that are absent or empty."""

    missing: list[str] = []
    lines = body.splitlines()
    for section in REQUIRED_SECTIONS:
        values = [
            value
            for line in lines
            if (value := _section_value(line, section)) is not None
        ]
        if not values or not any(values):
            missing.append(section)
    return tuple(missing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_reuse_declaration")
    parser.add_argument("--body-file", type=Path, required=True)
    parser.add_argument("--changed-files", type=Path, required=True)
    args = parser.parse_args(argv)
    body = args.body_file.read_text(encoding="utf-8-sig")
    paths = [
        line
        for line in args.changed_files.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not implementation_change(paths):
        print("Reuse Declaration: docs/non-implementation exemption")
        return 0
    missing = missing_sections(body)
    if missing:
        print("Reuse Declaration missing or empty sections:")
        for section in missing:
            print(f"- {section}")
        return 2
    print("Reuse Declaration: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
