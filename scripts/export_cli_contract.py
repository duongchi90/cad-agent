"""Export the current CLI parser as a deterministic compatibility contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cad_agent.cli import build_parser


def parser_contract(parser: argparse.ArgumentParser) -> dict[str, object]:
    """Return the sorted command and option surface of ``parser``."""

    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    commands: dict[str, Any] = {}
    for name, command_parser in sorted(subparsers.choices.items()):
        options: dict[str, object] = {}
        for action in command_parser._actions:
            if action.dest == "help":
                continue
            option_names = sorted(action.option_strings)
            key = option_names[0] if option_names else action.dest
            options[key] = {
                "dest": action.dest,
                "required": bool(getattr(action, "required", False)),
                "nargs": action.nargs,
            }
        commands[name] = {"options": options}
    return {"schema_version": "legacy-cli-baseline-1.0", "commands": commands}


def main() -> int:
    print(json.dumps(parser_contract(build_parser()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
