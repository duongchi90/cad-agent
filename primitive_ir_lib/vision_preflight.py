"""Non-billing readiness check for optional Claude Vision integration."""
from __future__ import annotations
import importlib.util
import os


def check_vision_readiness() -> dict:
    return {
        "sdk_installed": importlib.util.find_spec("anthropic") is not None,
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ready_for_live_calls": importlib.util.find_spec("anthropic") is not None and bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


def main() -> int:
    result = check_vision_readiness()
    print(result)
    return 0 if result["ready_for_live_calls"] else 1


if __name__ == "__main__":
    raise SystemExit(main())