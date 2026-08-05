"""Check the repository's reuse-first architecture boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "architecture-boundaries-1.0"
RESERVED_COMBINATIONS = (
    ("ocr", "engine"),
    ("dimension", "recognizer"),
    ("semantic", "solver"),
    ("dxf", "builder"),
    ("autocad", "transport"),
    ("repair", "executor"),
    ("manifest", "store"),
    ("checkpoint", "store"),
    ("revision", "store"),
    ("verified", "publisher"),
)
APPROVED_OWNER_ROOTS = frozenset(
    {
        "primitive_ir_lib",
        "semantic_ir_lib",
        "dxf_builder_lib",
        "mcp_integration_lib",
        "cad_agent",
        "agent_lib",
        "autocad_plugin",
    }
)
APPROVED_AUTOCAD_TRANSPORT_PREFIXES = (
    "mcp_integration_lib/",
    "autocad_plugin/",
    "contracts/autocad-ipc/",
)
_TRUTH_STORE_COMBINATIONS = frozenset(
    {
        ("manifest", "store"),
        ("checkpoint", "store"),
        ("revision", "store"),
        ("verified", "publisher"),
    }
)
_ROOT_FIELDS = frozenset(
    {"schema_version", "base_sha", "accepted_existing_violations"}
)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TOKEN = re.compile(r"[a-z0-9]+")
_VIOLATION = re.compile(r"^[A-Z0-9_]+:[^:]+:.+$")


def _normalise_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _under(path: str, prefixes: tuple[str, ...] | frozenset[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _tracked_source_files(repo_root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", "*.py", "*.cs"],
        capture_output=True,
        check=True,
        text=True,
    )
    paths = {_normalise_path(line) for line in result.stdout.splitlines() if line.strip()}
    return tuple(sorted(paths))


def _tokens(name: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(name.lower()))


def reserved_duplicate_name(name: str) -> bool:
    """Return whether a package or module name combines reserved architecture terms."""

    if name.lower() in APPROVED_OWNER_ROOTS:
        return False
    tokens = set(_tokens(name))
    return any(left in tokens and right in tokens for left, right in RESERVED_COMBINATIONS)


def _name_violations(path: str) -> set[str]:
    violations: set[str] = set()
    for component in path.split("/"):
        name = component.rsplit(".", 1)[0]
        if not reserved_duplicate_name(name):
            continue
        tokens = set(_tokens(name))
        truth_store = any(
            left in tokens and right in tokens
            for left, right in _TRUTH_STORE_COMBINATIONS
        )
        rule = "SECOND_TRUTH_STORE_NAME" if truth_store else "DUPLICATE_PACKAGE_NAME"
        violations.add(f"{rule}:{path}:{name}")
    return violations


def _python_imports(source: str, path: str) -> set[str]:
    tree = ast.parse(source, filename=path)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _source_violations(repo_root: Path, path: str) -> set[str]:
    source_path = repo_root / Path(path)
    source = source_path.read_text(encoding="utf-8-sig")
    violations = _name_violations(path)

    if path.endswith(".cs"):
        if "Autodesk.AutoCAD" in source and not _under(path, ("autocad_plugin/",)):
            violations.add(f"AUTOCAD_API_OUTSIDE_PLUGIN:{path}:Autodesk.AutoCAD")
        return violations

    for module in _python_imports(source, path):
        root = module.split(".", 1)[0]
        if root in {"cv2", "pytesseract"} and not _under(
            path, ("primitive_ir_lib/",)
        ):
            violations.add(f"DIRECT_OCR_IMPORT_OUTSIDE_PRIMITIVE_OWNER:{path}:{module}")
        if root == "ezdxf" and not _under(path, ("dxf_builder_lib/",)):
            violations.add(f"DIRECT_DXF_WRITE_OUTSIDE_DXF_BUILDER:{path}:{module}")
        if root == "mcp_integration_lib" and not _under(
            path, APPROVED_AUTOCAD_TRANSPORT_PREFIXES
        ):
            violations.add(
                f"AUTOCAD_TRANSPORT_OUTSIDE_APPROVED_BOUNDARY:{path}:{module}"
            )
    return violations


def collect_violations(repo_root: Path) -> tuple[str, ...]:
    """Collect stable architecture violations from tracked Python and C# files."""

    root = Path(repo_root).resolve()
    violations: set[str] = set()
    for path in _tracked_source_files(root):
        violations.update(_source_violations(root, path))
    return tuple(sorted(violations))


def read_baseline(path: Path) -> dict[str, Any]:
    """Read and validate the closed architecture exception baseline."""

    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("architecture baseline must be a JSON object")
    fields = set(payload)
    if fields != _ROOT_FIELDS:
        raise ValueError(
            "unexpected baseline fields: "
            f"missing={sorted(_ROOT_FIELDS - fields)} "
            f"extra={sorted(fields - _ROOT_FIELDS)}"
        )
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported architecture baseline schema_version")
    base_sha = payload["base_sha"]
    if not isinstance(base_sha, str) or _SHA.fullmatch(base_sha) is None:
        raise ValueError("base_sha must be a lowercase 40-character Git SHA")
    accepted = payload["accepted_existing_violations"]
    if not isinstance(accepted, list) or any(
        not isinstance(item, str) or _VIOLATION.fullmatch(item) is None
        for item in accepted
    ):
        raise ValueError("accepted_existing_violations must contain valid violation strings")
    if accepted != sorted(set(accepted)):
        raise ValueError("accepted_existing_violations must be sorted and unique")
    return dict(payload)


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _snapshot(repo_root: Path, output: Path) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "base_sha": _git_head(repo_root),
        "accepted_existing_violations": list(collect_violations(repo_root)),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Architecture baseline snapshot: {output}")
    print(f"Accepted existing violations: {len(payload['accepted_existing_violations'])}")
    return 0


def _check(repo_root: Path, baseline_path: Path) -> int:
    baseline = read_baseline(baseline_path)
    current = set(collect_violations(repo_root))
    accepted = set(baseline["accepted_existing_violations"])
    removed = sorted(accepted - current)
    new = sorted(current - accepted)
    if removed:
        print("Removed baseline exceptions (informational):")
        for item in removed:
            print(f"- {item}")
    if new:
        print("New architecture boundary violations (blockers):")
        for item in new:
            print(f"- {item}")
        return 2
    print("Architecture boundaries: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_architecture_boundaries")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--repo-root", type=Path, required=True)
    snapshot.add_argument("--output", type=Path, required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--repo-root", type=Path, required=True)
    check.add_argument("--baseline", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return _snapshot(args.repo_root, args.output)
    return _check(args.repo_root, args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())
