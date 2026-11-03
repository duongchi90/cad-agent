from dxf_builder_lib.builder import BuildResult, DimensionLineExpectation
from cad_agent.live import _build_result_dict, _build_result_from_dict


def test_ephemeral_expectations_are_excluded_from_existing_build_evidence():
    build = BuildResult(
        output_path="candidate.dxf",
        dimension_count=1,
        dimension_line_expectations=(DimensionLineExpectation(
            "DIM-1", "AB", "*D1", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),),
        ),),
    )

    payload = _build_result_dict(build)
    assert "dimension_line_expectations" not in payload
    reconstructed = _build_result_from_dict(payload)
    assert reconstructed.dimension_line_expectations is None
