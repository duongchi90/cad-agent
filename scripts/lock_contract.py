from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path


INPUT_NAMES = ("runtime.in", "vision.in", "solver.in", "dev.in")
STAMP_PREFIX = "# input-sha256: "
PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+==[^\s;\\]+(?:\s*;.*)?$")
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}\b")


def compute_input_digest(lock_path: Path) -> str:
    digest = hashlib.sha256()
    for name in INPUT_NAMES:
        input_path = lock_path.parent / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        normalized = input_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        normalized = normalized.replace("\r", "\n")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def requirement_blocks(lock_text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in lock_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current:
                current.append(line)
            continue
        if line.startswith("--"):
            continue
        if current:
            blocks.append(current)
        current = [line]
    if current:
        blocks.append(current)
    return blocks


def validate_lock(lock_path: Path) -> None:
    text = lock_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    expected_stamp = STAMP_PREFIX + compute_input_digest(lock_path)
    errors: list[str] = []
    if not lines or lines[0] != expected_stamp:
        errors.append("input digest is missing or stale; regenerate and stamp the lock")

    blocks = requirement_blocks(text)
    if not blocks:
        errors.append("lock contains no requirement blocks")
    for block in blocks:
        pin = block[0].removesuffix("\\").rstrip()
        if not PIN_RE.fullmatch(pin):
            errors.append(f"requirement is not an exact == pin: {pin}")
        if not HASH_RE.search(" ".join(block)):
            errors.append(f"requirement has no sha256 hash: {pin}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Lock contract PASS: {len(blocks)} pinned, hashed distributions")


def stamp_lock(lock_path: Path) -> None:
    text = lock_path.read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.startswith(STAMP_PREFIX)
    )
    stamped = f"{STAMP_PREFIX}{compute_input_digest(lock_path)}\n{body.rstrip()}\n"
    lock_path.write_text(stamped, encoding="utf-8")


def compile_lock(lock_path: Path) -> None:
    repo_root = lock_path.parent.parent
    generated_path = lock_path.with_name(lock_path.name + ".generated")
    generated_relative = generated_path.relative_to(repo_root)
    input_relative = (lock_path.parent / "dev.in").relative_to(repo_root)
    command = [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--resolver=backtracking",
        "--generate-hashes",
        "--allow-unsafe",
        "--strip-extras",
        "--output-file",
        str(generated_relative),
        str(input_relative),
    ]
    try:
        completed = subprocess.run(command, cwd=repo_root, check=False)
        if completed.returncode != 0:
            raise SystemExit(f"pip-compile failed with exit code {completed.returncode}")
        stamp_lock(generated_path)
        validate_lock(generated_path)
        generated_path.replace(lock_path)
    finally:
        if generated_path.exists():
            generated_path.unlink()
    validate_lock(lock_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("compile", "check"))
    parser.add_argument("lock", type=Path)
    args = parser.parse_args()
    lock_path = args.lock.resolve()
    if args.command == "compile":
        compile_lock(lock_path)
    validate_lock(lock_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
