from __future__ import annotations

import json
from pathlib import Path

IPC_ROOT = Path(__file__).parents[1] / "contracts/autocad-ipc"


def test_native_render_success_example_is_closed_and_read_only() -> None:
    result = json.loads(
        (IPC_ROOT / "examples/native-render-evidence-result.json").read_text(encoding="utf-8")
    )

    assert result["success"] is True
    assert result["changed"] is False
    assert result["entity_handles"] == []
    assert result["errors"] == []
    assert result["payload"]["renderer"] == "AUTOCAD_NATIVE"
    assert result["payload"]["artifact"]["relative_path"] == (
        "native-render/render-request-001/artifact.png"
    )
    assert result["payload"]["changed"] is False
    assert result["payload"]["dbmod_before"] == result["payload"]["dbmod_after"]
    assert not any(
        forbidden in result["payload"]
        for forbidden in ("verdict", "approval", "repair", "publication")
    )
