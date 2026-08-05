"""Validate the closed repository reuse-inventory contract."""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


CLASSIFICATIONS = frozenset(
    {
        "REUSE_AS_IS",
        "EXTEND_WITH_ADAPTER",
        "EXTEND_WITH_TEST",
        "REFACTOR_BEHIND_COMPATIBILITY_LAYER",
        "NEW_MISSING_CAPABILITY",
        "DEPRECATED_AFTER_MIGRATION",
    }
)
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ROOT_FIELDS = {
    "schema_version",
    "repository",
    "base_sha",
    "generated_at_utc",
    "capabilities",
}
_CAPABILITY_FIELDS = {
    "capability_id",
    "capability",
    "current_owner",
    "current_paths",
    "current_apis",
    "current_consumers",
    "classification",
    "adapter",
    "tests",
    "acceptance_gate",
    "migration",
    "rollback",
    "inspected_paths",
    "gap_reason",
}


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _string_list(value: object, path: str, *, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        raise ValueError(f"{path} must be a string list with at least {min_items} items")
    result = [_non_empty_string(item, f"{path}[]") for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{path} contains duplicates")
    return result


def _utc_datetime(value: object) -> str:
    text = _non_empty_string(value, "generated_at_utc")
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("generated_at_utc must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("generated_at_utc must use UTC")
    return text


def validate_inventory(payload: Mapping[str, object]) -> dict[str, Any]:
    """Validate and deep-copy one closed reuse inventory payload."""

    if not isinstance(payload, Mapping):
        raise ValueError("reuse inventory must be a JSON object")
    fields = set(payload)
    if fields != _ROOT_FIELDS:
        raise ValueError(
            f"unexpected root fields: missing={sorted(_ROOT_FIELDS - fields)} "
            f"extra={sorted(fields - _ROOT_FIELDS)}"
        )
    if payload["schema_version"] != "reuse-inventory-1.0":
        raise ValueError("unsupported reuse inventory schema_version")
    if payload["repository"] != "duongchi90/cad-agent":
        raise ValueError("reuse inventory repository is invalid")
    base_sha = payload["base_sha"]
    if not isinstance(base_sha, str) or _SHA1.fullmatch(base_sha) is None:
        raise ValueError("base_sha must be a lowercase 40-character Git SHA")
    _utc_datetime(payload["generated_at_utc"])
    capabilities = payload["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("capabilities must be a non-empty array")

    seen: set[str] = set()
    for index, raw in enumerate(capabilities):
        if not isinstance(raw, Mapping):
            raise ValueError(f"capabilities[{index}] must be an object")
        fields = set(raw)
        if fields != _CAPABILITY_FIELDS:
            raise ValueError(
                f"capabilities[{index}] fields are not closed: "
                f"missing={sorted(_CAPABILITY_FIELDS - fields)} "
                f"extra={sorted(fields - _CAPABILITY_FIELDS)}"
            )
        capability_id = _non_empty_string(
            raw["capability_id"], f"capabilities[{index}].capability_id"
        )
        if _CAPABILITY_ID.fullmatch(capability_id) is None:
            raise ValueError(
                f"capabilities[{index}].capability_id must be a lowercase identifier"
            )
        if capability_id in seen:
            raise ValueError(f"duplicate capability_id: {capability_id}")
        seen.add(capability_id)
        _non_empty_string(raw["capability"], f"capabilities[{index}].capability")
        _non_empty_string(raw["current_owner"], f"capabilities[{index}].current_owner")
        _string_list(raw["current_paths"], f"capabilities[{index}].current_paths")
        _string_list(raw["current_apis"], f"capabilities[{index}].current_apis")
        _string_list(raw["current_consumers"], f"capabilities[{index}].current_consumers")
        classification = raw["classification"]
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"capabilities[{index}].classification is invalid")
        if raw["adapter"] is not None:
            _non_empty_string(raw["adapter"], f"capabilities[{index}].adapter")
        _string_list(raw["tests"], f"capabilities[{index}].tests", min_items=1)
        _non_empty_string(raw["acceptance_gate"], f"capabilities[{index}].acceptance_gate")
        _non_empty_string(raw["migration"], f"capabilities[{index}].migration")
        _non_empty_string(raw["rollback"], f"capabilities[{index}].rollback")
        inspected = _string_list(raw["inspected_paths"], f"capabilities[{index}].inspected_paths")
        gap_reason = raw["gap_reason"]
        if classification == "NEW_MISSING_CAPABILITY":
            if not inspected or not isinstance(gap_reason, str) or not gap_reason.strip():
                raise ValueError(
                    "NEW_MISSING_CAPABILITY requires inspected_paths and gap_reason"
                )
        elif gap_reason is not None:
            raise ValueError("gap_reason is only valid for NEW_MISSING_CAPABILITY")
    return copy.deepcopy(dict(payload))


def read_inventory(path: Path) -> dict[str, Any]:
    """Read and validate a UTF-8 JSON reuse inventory."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read reuse inventory: {path}") from exc
    return validate_inventory(payload)


def validate_against_repository(inventory: Mapping[str, object], repo_root: Path) -> None:
    """Ensure all repository-relative inventory paths exist inside ``repo_root``."""

    validated = validate_inventory(inventory)
    root = repo_root.resolve()
    for item in validated["capabilities"]:
        for field in ("current_paths", "inspected_paths", "tests"):
            for relative in item[field]:
                if relative.startswith("external:"):
                    continue
                relative_path = Path(relative)
                if relative_path.is_absolute():
                    raise ValueError(f"inventory path must be repository-relative: {relative}")
                candidate = (root / relative_path).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"inventory path escapes repository: {relative}") from exc
                if not candidate.exists():
                    raise ValueError(f"inventory path does not exist: {relative}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reuse_inventory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("inventory", type=Path)
    check.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    inventory = read_inventory(args.inventory)
    validate_against_repository(inventory, args.repo_root)
    print(args.inventory.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
