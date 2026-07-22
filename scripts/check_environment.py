from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from lock_contract import requirement_blocks, validate_lock


PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)")
BOOTSTRAP_ALLOWLIST = {"pip", "setuptools", "wheel"}


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_versions(lock_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in requirement_blocks(lock_path.read_text(encoding="utf-8")):
        match = PIN_RE.match(block[0])
        if match is None:
            raise SystemExit(f"cannot parse locked requirement: {block[0]}")
        result[canonical_name(match.group(1))] = match.group(2)
    return result


def installed_versions() -> dict[str, str]:
    return {
        canonical_name(dist.metadata["Name"]): dist.version
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_environment.py LOCK_FILE")
    lock_path = Path(sys.argv[1]).resolve()
    validate_lock(lock_path)
    locked = locked_versions(lock_path)
    installed = installed_versions()

    missing = sorted(set(locked) - set(installed))
    extra = sorted(set(installed) - set(locked) - BOOTSTRAP_ALLOWLIST)
    mismatched = sorted(
        f"{name}: locked={locked[name]} installed={installed[name]}"
        for name in set(locked) & set(installed)
        if locked[name] != installed[name]
    )
    if missing or extra or mismatched:
        raise SystemExit(
            f"missing={missing}\nextra={extra}\nversion_mismatch={mismatched}"
        )

    completed = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stdout + completed.stderr)
    print(
        f"Environment contract PASS: {len(locked)} locked distributions; "
        f"bootstrap allowlist present={sorted(set(installed) & BOOTSTRAP_ALLOWLIST)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
