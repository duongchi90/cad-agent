"""Bounded, non-authenticating probe for the official Codex Python SDK."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_lib.codex_sdk_compat import (
    inspect_codex_sdk,
    render_probe_json,
    run_disposable_probe,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_codex_sdk_windows")
    parser.add_argument(
        "--mode",
        choices=("inspect", "start"),
        default="inspect",
        help="inspect metadata only, or start and close the disposable runtime",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="bounded runtime-start timeout (maximum 30 seconds)",
    )
    args = parser.parse_args(argv)

    if args.mode == "inspect":
        inspection = inspect_codex_sdk()
        payload: dict[str, object] = {"inspection": inspection, "mode": "inspect"}
        exit_code = 0 if inspection["status"] == "compatible" else 2
    else:
        try:
            payload = run_disposable_probe(timeout_seconds=args.timeout_seconds)
            runtime_start = payload.get("runtime_start")
            exit_code = 0 if isinstance(runtime_start, dict) and runtime_start.get("success") else 2
        except ValueError:
            payload = {
                "mode": "start",
                "runtime_start": {
                    "status": "invalid_timeout",
                    "success": False,
                },
            }
            exit_code = 2

    sys.stdout.buffer.write(render_probe_json(payload).encode("utf-8"))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
