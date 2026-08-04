from __future__ import annotations

import pytest

from cad_agent.visual_contracts import VisualContractError, require_dimension_gate_ready
from tests.visual_supervisor_fixtures import valid_dimension_register


def test_dimension_gate_rejects_incomplete_cluster_disposition() -> None:
    payload = valid_dimension_register()
    payload["coverage"]["clusters_detected"] = 2
    with pytest.raises(VisualContractError, match="clusters"):
        require_dimension_gate_ready(payload)


def test_dimension_gate_accepts_complete_confirmed_register() -> None:
    require_dimension_gate_ready(valid_dimension_register())
