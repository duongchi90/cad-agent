from __future__ import annotations

from copy import deepcopy
import importlib

import pytest

from cad_agent import candidate_revision as candidate_revision_module
from cad_agent import drawing_artifact_reference as dara


MODULE_NAME = "cad_agent.standalone_dwg_extraction"
SHA = "a" * 64


def _module():
    return importlib.import_module(MODULE_NAME)


def _inspection_request() -> dict[str, object]:
    return {
        "schema_version": "standalone-dwg-component-inspection-1.0",
        "request_id": "standalone-inspection-request-001",
        "run_id": "standalone-run-001",
        "source_drawing_path": r"C:\synthetic\source\standalone-source.dwg",
        "source_drawing_sha256": SHA,
        "source_setup_audit_sha256": "b" * 64,
        "selection_groups": [
            {
                "group_id": "group-001",
                "logical_component_id": "component-001",
                "source_handles": ["A1B2"],
                "expected_entity_types": ["INSERT"],
                "source_layer_expectations": ["BODY"],
            }
        ],
        "expected_dbmod": 0,
        "approval": None,
    }


def _inspection_result() -> dict[str, object]:
    return {
        "schema_version": "standalone-dwg-component-inspection-result-1.0",
        "inspection_id": "standalone-inspection-001",
        "request_id": "standalone-inspection-request-001",
        "source_identity": {
            "path": r"C:\synthetic\source\standalone-source.dwg",
            "sha256": SHA,
            "dbmod": 0,
        },
        "source_sha256_before": SHA,
        "source_sha256_after": SHA,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "read_only": True,
        "groups": [
            {
                "group_id": "group-001",
                "logical_component_id": "component-001",
                "source_handles": ["A1B2"],
                "entity_types": ["INSERT"],
                "layers": ["BODY"],
                "signature_sha256": "c" * 64,
            }
        ],
        "warnings": [],
        "conflicts": [],
        "changed": False,
        "eligible": True,
        "inspection_sha256": "d" * 64,
    }


def _extraction_plan() -> dict[str, object]:
    return {
        "plan_id": "standalone-plan-001",
        "request_id": "standalone-extraction-request-001",
        "run_id": "standalone-run-001",
        "inspection_id": "standalone-inspection-001",
        "inspection_sha256": "d" * 64,
        "source_drawing_sha256": SHA,
        "candidate_output_path": r"C:\temp\standalone-candidate-001.dwg",
        "candidate_base_model": "EMPTY_NEW_DATABASE",
        "components": [
            {
                "group_id": "group-001",
                "logical_component_id": "component-001",
                "source_handles": ["A1B2"],
                "transform": {
                    "rotation_degrees": 0.0,
                    "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "uniform_scale": 1.0,
                },
            }
        ],
        "transform_policy": "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        "approval": {"reference": "approval-standalone-001", "status": "APPROVED"},
    }


def _extraction_result() -> dict[str, object]:
    return {
        "schema_version": "standalone-dwg-component-extraction-result-1.0",
        "request_id": "standalone-extraction-request-001",
        "run_id": "standalone-run-001",
        "source_drawing_sha256": SHA,
        "candidate_base_model": "EMPTY_NEW_DATABASE",
        "candidate_output_sha256": "e" * 64,
        "candidate_output_identity": {
            "path": r"C:\temp\standalone-candidate-001.dwg",
            "file_id": "synthetic-file-id-001",
        },
        "source_mutated": False,
        "source_dbmod_before": 0,
        "source_dbmod_after": 0,
        "save_performed": True,
        "components": [
            {
                "group_id": "group-001",
                "logical_component_id": "component-001",
                "source_handles": ["A1B2"],
                "candidate_handles": ["F001"],
            }
        ],
        "source_handle_to_candidate_handle": [
            {"source_handle": "A1B2", "candidate_handle": "F001"}
        ],
        "result_sha256": "f" * 64,
    }


def test_inspection_rejects_unknown_or_missing_fields() -> None:
    module = _module()
    unknown = _inspection_request()
    unknown["unexpected"] = True
    with pytest.raises(module.StandaloneDwgExtractionError, match="REQUEST_SCHEMA_INVALID"):
        module.validate_standalone_inspection_request(unknown)

    missing = _inspection_request()
    del missing["source_setup_audit_sha256"]
    with pytest.raises(module.StandaloneDwgExtractionError, match="REQUEST_SCHEMA_INVALID"):
        module.validate_standalone_inspection_request(missing)


def test_inspection_rejects_duplicate_handles_and_empty_groups() -> None:
    module = _module()
    duplicate = _inspection_request()
    duplicate["selection_groups"] = [
        deepcopy(duplicate["selection_groups"][0]),
        deepcopy(duplicate["selection_groups"][0]),
    ]
    with pytest.raises(module.StandaloneDwgExtractionError, match="DUPLICATE_HANDLE"):
        module.validate_standalone_inspection_request(duplicate)

    empty = _inspection_request()
    empty["selection_groups"] = []
    with pytest.raises(module.StandaloneDwgExtractionError, match="EMPTY_GROUP"):
        module.validate_standalone_inspection_request(empty)


def test_inspection_rejects_non_hash_bound_or_non_hex_handles() -> None:
    module = _module()
    bad_hash = _inspection_request()
    bad_hash["source_drawing_sha256"] = "not-a-sha256"
    with pytest.raises(module.StandaloneDwgExtractionError, match="HASH_INVALID"):
        module.validate_standalone_inspection_request(bad_hash)

    bad_handle = _inspection_request()
    bad_handle["selection_groups"][0]["source_handles"] = ["GG"]
    with pytest.raises(module.StandaloneDwgExtractionError, match="HANDLE_INVALID"):
        module.validate_standalone_inspection_request(bad_handle)


def test_layer_names_allow_autocad_safe_text_but_reject_controls() -> None:
    module = _module()

    request = _inspection_request()
    request["selection_groups"][0]["source_layer_expectations"] = ["Duong manh"]
    normalized_request = module.validate_standalone_inspection_request(request)
    assert normalized_request["selection_groups"][0]["source_layer_expectations"] == [
        "Duong manh"
    ]

    result = _inspection_result()
    result["groups"][0]["layers"] = ["Duong manh"]
    result["inspection_sha256"] = module.standalone_inspection_result_sha256(result)
    normalized_result = module.validate_standalone_inspection_result(result)
    assert normalized_result["groups"][0]["layers"] == ["Duong manh"]

    for field in ("source_layer_expectations",):
        invalid = _inspection_request()
        invalid["selection_groups"][0][field] = ["Duong\nmanh"]
        with pytest.raises(
            module.StandaloneDwgExtractionError, match="REQUEST_SCHEMA_INVALID"
        ):
            module.validate_standalone_inspection_request(invalid)

    invalid_result = _inspection_result()
    invalid_result["groups"][0]["layers"] = ["Duong\nmanh"]
    invalid_result["inspection_sha256"] = module.standalone_inspection_result_sha256(
        invalid_result
    )
    with pytest.raises(
        module.StandaloneDwgExtractionError, match="RESULT_SCHEMA_INVALID"
    ):
        module.validate_standalone_inspection_result(invalid_result)


def test_extraction_plan_requires_empty_new_database_and_no_candidate_input() -> None:
    module = _module()
    plan = _extraction_plan()
    assert module.build_standalone_extraction_plan(plan)["candidate_base_model"] == (
        "EMPTY_NEW_DATABASE"
    )

    candidate_input = deepcopy(plan)
    candidate_input["candidate_input_sha256"] = "b" * 64
    with pytest.raises(module.StandaloneDwgExtractionError, match="CANDIDATE_INPUT_FORBIDDEN"):
        module.build_standalone_extraction_plan(candidate_input)


def test_page1_delta_group_is_rejected_by_extraction_plan() -> None:
    """A page-1-only delta cannot enter the standalone reuse plan uninspected."""

    module = _module()
    request = _inspection_request()
    inspection = _inspection_result()
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    plan = _extraction_plan()
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    page1_delta = deepcopy(plan)
    page1_delta["components"][0]["group_id"] = "cargo-side-frame"
    page1_delta["components"][0]["logical_component_id"] = "cargo-side-frame"

    with pytest.raises(
        module.StandaloneDwgExtractionError, match="PLAN_INSPECTION_MISMATCH"
    ):
        module.build_standalone_extraction_plan(
            page1_delta,
            inspection_result=inspection,
            inspection_request=request,
        )


def test_extraction_rejects_invalid_transform_or_fabricated_approval() -> None:
    module = _module()
    invalid_transform = _extraction_plan()
    invalid_transform["components"][0]["transform"]["uniform_scale"] = 0.0
    with pytest.raises(module.StandaloneDwgExtractionError, match="TRANSFORM_INVALID"):
        module.build_standalone_extraction_plan(invalid_transform)

    fabricated_approval = _extraction_plan()
    fabricated_approval["approval"] = None
    with pytest.raises(module.StandaloneDwgExtractionError, match="APPROVAL_INVALID"):
        module.build_standalone_extraction_plan(fabricated_approval)


def test_result_rejects_source_mutation_or_false_save() -> None:
    module = _module()
    mutated = _extraction_result()
    mutated["source_mutated"] = True
    with pytest.raises(module.StandaloneDwgExtractionError, match="SOURCE_MUTATED"):
        module.validate_standalone_extraction_result(mutated)

    unsaved = _extraction_result()
    unsaved["save_performed"] = False
    with pytest.raises(module.StandaloneDwgExtractionError, match="SAVE_NOT_PERFORMED"):
        module.validate_standalone_extraction_result(unsaved)


def test_result_hash_and_mapping_are_deterministic() -> None:
    module = _module()
    first_payload = _extraction_result()
    first_payload["result_sha256"] = module.standalone_extraction_result_sha256(
        first_payload
    )
    second_payload = _extraction_result()
    second_payload["result_sha256"] = module.standalone_extraction_result_sha256(
        second_payload
    )
    first = module.validate_standalone_extraction_result(first_payload)
    second = module.validate_standalone_extraction_result(second_payload)
    assert first == second
    assert first["result_sha256"] == module.standalone_extraction_result_sha256(first)


def test_inspection_checksum_mismatch_fails_closed() -> None:
    module = _module()
    payload = _inspection_result()
    payload["inspection_sha256"] = module.standalone_inspection_result_sha256(payload)
    assert module.validate_standalone_inspection_result(payload)["inspection_sha256"] == (
        payload["inspection_sha256"]
    )

    forged = deepcopy(payload)
    forged["inspection_sha256"] = "0" * 64
    with pytest.raises(module.StandaloneDwgExtractionError, match="CHECKSUM_MISMATCH"):
        module.validate_standalone_inspection_result(forged)


def test_extraction_checksum_mismatch_fails_closed() -> None:
    module = _module()
    payload = _extraction_result()
    payload["result_sha256"] = module.standalone_extraction_result_sha256(payload)
    assert module.validate_standalone_extraction_result(payload)["result_sha256"] == (
        payload["result_sha256"]
    )

    forged = deepcopy(payload)
    forged["result_sha256"] = "0" * 64
    with pytest.raises(module.StandaloneDwgExtractionError, match="CHECKSUM_MISMATCH"):
        module.validate_standalone_extraction_result(forged)


def test_provenance_context_requires_verified_inspection_and_result_checksums() -> None:
    module = _module()
    source_bytes = b"standalone-source"
    candidate_bytes = b"standalone-candidate"
    import hashlib

    source_sha = hashlib.sha256(source_bytes).hexdigest()
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    inspection = _inspection_result()
    inspection["source_identity"]["sha256"] = source_sha
    inspection["source_sha256_before"] = source_sha
    inspection["source_sha256_after"] = source_sha
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    extraction = _extraction_result()
    extraction["source_drawing_sha256"] = source_sha
    extraction["candidate_output_sha256"] = candidate_sha
    extraction["result_sha256"] = module.standalone_extraction_result_sha256(
        extraction
    )
    plan = _extraction_plan()
    plan["inspection_id"] = inspection["inspection_id"]
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    plan["source_drawing_sha256"] = source_sha

    context = module.build_standalone_provenance_context(
        source_artifact_bytes=source_bytes,
        run_id="standalone-run-001",
        project_id="project-001",
        drawing_id="drawing-001",
        source_upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-evidence-001",
            "evidence_sha256": "1" * 64,
        },
        observation_evidence_sha256="2" * 64,
        plan=plan,
        inspection_result=inspection,
        extraction_result=extraction,
    )
    assert context["provenance_mode"] == "STANDALONE_DWG_COMPONENTS"
    assert "candidate_reference" not in context

    forged = deepcopy(inspection)
    forged["inspection_sha256"] = "f" * 64
    with pytest.raises(module.StandaloneDwgExtractionError, match="CHECKSUM_MISMATCH"):
        module.build_standalone_provenance_context(
            source_artifact_bytes=source_bytes,
            run_id="standalone-run-001",
            project_id="project-001",
            drawing_id="drawing-001",
            source_upstream_evidence={
                "evidence_kind": "BASELINE_CUSTODY",
                "evidence_id": "baseline-evidence-001",
                "evidence_sha256": "1" * 64,
            },
            observation_evidence_sha256="2" * 64,
            plan=plan,
            inspection_result=forged,
            extraction_result=extraction,
        )


def test_composes_staged_standalone_r3_and_root_r4_binding() -> None:
    module = _module()
    source_bytes = b"standalone-source"
    candidate_bytes = b"standalone-candidate"
    import hashlib

    source_sha = hashlib.sha256(source_bytes).hexdigest()
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    inspection = _inspection_result()
    inspection["source_identity"]["sha256"] = source_sha
    inspection["source_sha256_before"] = source_sha
    inspection["source_sha256_after"] = source_sha
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    extraction = _extraction_result()
    extraction["source_drawing_sha256"] = source_sha
    extraction["candidate_output_sha256"] = candidate_sha
    extraction["result_sha256"] = module.standalone_extraction_result_sha256(
        extraction
    )
    plan = _extraction_plan()
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    plan["source_drawing_sha256"] = source_sha
    provenance = module.build_standalone_provenance_context(
        source_artifact_bytes=source_bytes,
        run_id="standalone-run-001",
        project_id="project-001",
        drawing_id="drawing-001",
        source_upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-evidence-001",
            "evidence_sha256": "1" * 64,
        },
        observation_evidence_sha256="2" * 64,
        plan=plan,
        inspection_result=inspection,
        extraction_result=extraction,
    )

    composed = module.compose_standalone_candidate_binding(
        provenance_context=provenance,
        candidate_id="standalone-candidate-001",
        source_artifact_bytes=source_bytes,
        candidate_artifact_bytes=candidate_bytes,
        candidate_upstream_evidence={
            "evidence_kind": "R3_CANDIDATE_CUSTODY",
            "evidence_id": "r3-candidate-evidence-001",
            "evidence_sha256": "3" * 64,
        },
        candidate_observation_evidence_sha256="4" * 64,
    )
    assert composed["registry"]["schema_version"] == (
        "component-view-registry-standalone-dwg-1.0"
    )
    assert composed["candidate_revision"]["upstream_bindings"]["source_sha256"] == source_sha
    assert composed["candidate_revision"]["upstream_bindings"][
        "candidate_drawing_sha256"
    ] == candidate_sha
    assert composed["candidate_revision"]["upstream_bindings"][
        "extraction_result_sha256"
    ] == extraction["result_sha256"]
    assert composed["candidate_revision"]["change_scope"][
        "registry_snapshot_sha256"
    ] == composed["registry"]["registry_snapshot_sha256"]

    foreign_source_bytes = b"standalone-source-foreign"
    foreign_reference = dara.issue_drawing_artifact_reference(
        run_id="standalone-run-001",
        project_id="project-001",
        drawing_id="drawing-001",
        artifact_role="BASELINE",
        artifact_bytes=foreign_source_bytes,
        upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-evidence-foreign-001",
            "evidence_sha256": "5" * 64,
        },
    )
    foreign_observation = dara.observe_drawing_artifact_currentness(
        reference=foreign_reference,
        artifact_bytes=foreign_source_bytes,
        observation_evidence_sha256="6" * 64,
    )
    with pytest.raises(
        candidate_revision_module.CandidateRevisionError,
        match="STANDALONE_SOURCE_MISMATCH",
    ):
        candidate_revision_module.build_candidate_revision(
            registry=composed["registry"],
            base_cad_handoff=None,
            baseline_context={
                "reference": foreign_reference,
                "observation": foreign_observation,
                "artifact_bytes": foreign_source_bytes,
            },
            parent_candidate=None,
            change_impact=composed["change_impact"],
            mutation_evidence=composed["mutation_evidence"],
            schema_version=candidate_revision_module.CANDIDATE_REVISION_V11_SCHEMA_VERSION,
            candidate_kind=candidate_revision_module.CANDIDATE_REVISION_ROOT_KIND,
        )

    unapproved = deepcopy(extraction)
    unapproved["components"][0]["group_id"] = "unapproved-group"
    unapproved["result_sha256"] = module.standalone_extraction_result_sha256(
        unapproved
    )
    with pytest.raises(
        module.StandaloneDwgExtractionError, match="PLAN_SELECTION_MISMATCH"
    ):
        module.build_standalone_provenance_context(
            source_artifact_bytes=source_bytes,
            run_id="standalone-run-001",
            project_id="project-001",
            drawing_id="drawing-001",
            source_upstream_evidence={
                "evidence_kind": "BASELINE_CUSTODY",
                "evidence_id": "baseline-evidence-001",
                "evidence_sha256": "1" * 64,
            },
            observation_evidence_sha256="2" * 64,
            plan=plan,
            inspection_result=inspection,
            extraction_result=unapproved,
        )


def test_composition_uses_only_the_approved_subset_of_inspected_groups() -> None:
    module = _module()
    source_bytes = b"standalone-source"
    candidate_bytes = b"standalone-candidate"
    import hashlib

    source_sha = hashlib.sha256(source_bytes).hexdigest()
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    inspection = _inspection_result()
    inspection["source_identity"]["sha256"] = source_sha
    inspection["source_sha256_before"] = source_sha
    inspection["source_sha256_after"] = source_sha
    inspection["groups"].append(
        {
            "group_id": "group-002",
            "logical_component_id": "component-002",
            "source_handles": ["C3D4"],
            "entity_types": ["INSERT"],
            "layers": ["BODY"],
            "signature_sha256": "f" * 64,
        }
    )
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    extraction = _extraction_result()
    extraction["source_drawing_sha256"] = source_sha
    extraction["candidate_output_sha256"] = candidate_sha
    extraction["result_sha256"] = module.standalone_extraction_result_sha256(
        extraction
    )
    plan = _extraction_plan()
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    plan["source_drawing_sha256"] = source_sha
    provenance = module.build_standalone_provenance_context(
        source_artifact_bytes=source_bytes,
        run_id="standalone-run-001",
        project_id="project-001",
        drawing_id="drawing-001",
        source_upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-evidence-subset-001",
            "evidence_sha256": "7" * 64,
        },
        observation_evidence_sha256="8" * 64,
        plan=plan,
        inspection_result=inspection,
        extraction_result=extraction,
    )
    composed = module.compose_standalone_candidate_binding(
        provenance_context=provenance,
        candidate_id="standalone-candidate-001",
        source_artifact_bytes=source_bytes,
        candidate_artifact_bytes=candidate_bytes,
        candidate_upstream_evidence={
            "evidence_kind": "R3_CANDIDATE_CUSTODY",
            "evidence_id": "r3-candidate-subset-001",
            "evidence_sha256": "9" * 64,
        },
        candidate_observation_evidence_sha256="a" * 64,
    )
    assert [group["group_id"] for group in provenance["selected_groups"]] == [
        "group-001"
    ]
    assert len(composed["registry"]["components"]) == 1

    drifted = deepcopy(extraction)
    drifted["source_dbmod_before"] = 1
    drifted["source_dbmod_after"] = 1
    drifted["result_sha256"] = module.standalone_extraction_result_sha256(drifted)
    with pytest.raises(module.StandaloneDwgExtractionError, match="DBMOD_MISMATCH"):
        module.build_standalone_provenance_context(
            source_artifact_bytes=source_bytes,
            run_id="standalone-run-001",
            project_id="project-001",
            drawing_id="drawing-001",
            source_upstream_evidence={
                "evidence_kind": "BASELINE_CUSTODY",
                "evidence_id": "baseline-evidence-001",
                "evidence_sha256": "1" * 64,
            },
            observation_evidence_sha256="2" * 64,
            plan=plan,
            inspection_result=inspection,
            extraction_result=drifted,
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda result: result["components"][0].__setitem__(
            "group_id", "unapproved-group"
        ),
        lambda result: result["components"][0].__setitem__(
            "logical_component_id", "unapproved-component"
        ),
        lambda result: result["components"][0]["source_handles"].__setitem__(
            0, "B2C3"
        ),
    ],
    ids=["group", "logical-component", "source-handle"],
)
def test_result_plan_binding_rejects_unapproved_selection(mutator) -> None:
    module = _module()
    plan = _extraction_plan()
    result = _extraction_result()
    mutator(result)
    result["result_sha256"] = module.standalone_extraction_result_sha256(result)
    with pytest.raises(module.StandaloneDwgExtractionError, match="PLAN_SELECTION_MISMATCH"):
        module.validate_standalone_extraction_result(result, plan=plan)


def test_result_inspection_binding_rejects_source_dbmod_drift() -> None:
    module = _module()
    plan = _extraction_plan()
    inspection = _inspection_result()
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    result = _extraction_result()
    result["source_dbmod_before"] = 1
    result["source_dbmod_after"] = 1
    result["result_sha256"] = module.standalone_extraction_result_sha256(result)
    with pytest.raises(module.StandaloneDwgExtractionError, match="DBMOD_MISMATCH"):
        module.validate_standalone_extraction_result(
            result, plan=plan, inspection_result=inspection
        )


def test_plan_rejects_present_destination_at_planning_time(tmp_path) -> None:
    module = _module()
    output = tmp_path / "candidate.dwg"
    output.write_bytes(b"existing")
    plan = _extraction_plan()
    plan["candidate_output_path"] = str(output)
    with pytest.raises(
        module.StandaloneDwgExtractionError, match="CANDIDATE_OUTPUT_NOT_ABSENT"
    ):
        module.build_standalone_extraction_plan(plan)


def test_result_validation_reuses_approved_plan_after_output_creation(tmp_path) -> None:
    module = _module()
    output = tmp_path / "candidate.dwg"
    output.write_bytes(b"serialized-candidate")
    plan = _extraction_plan()
    plan["candidate_output_path"] = str(output)
    result = _extraction_result()
    result["candidate_output_identity"]["path"] = str(output)
    result["result_sha256"] = module.standalone_extraction_result_sha256(result)

    validated = module.validate_standalone_extraction_result(result, plan=plan)
    assert validated["candidate_output_identity"]["path"] == str(output)

    wrong_path = deepcopy(result)
    wrong_path["candidate_output_identity"]["path"] = str(
        tmp_path / "different-candidate.dwg"
    )
    wrong_path["result_sha256"] = module.standalone_extraction_result_sha256(
        wrong_path
    )
    with pytest.raises(module.StandaloneDwgExtractionError, match="RESULT_PLAN_MISMATCH"):
        module.validate_standalone_extraction_result(wrong_path, plan=plan)


def test_extraction_request_identity_is_independent_from_inspection_request(
    tmp_path,
) -> None:
    module = _module()
    inspection_request = _inspection_request()
    inspection = _inspection_result()
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    output = tmp_path / "candidate.dwg"
    plan = _extraction_plan()
    plan["candidate_output_path"] = str(output)
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    approved_plan = module.build_standalone_extraction_plan(
        plan,
        inspection_result=inspection,
        inspection_request=inspection_request,
    )

    result = _extraction_result()
    result["candidate_output_identity"]["path"] = str(output)
    result["result_sha256"] = module.standalone_extraction_result_sha256(result)
    validated = module.validate_standalone_extraction_result(
        result,
        plan=approved_plan,
        inspection_result=inspection,
    )

    assert validated["request_id"] == "standalone-extraction-request-001"
    assert validated["request_id"] != inspection["request_id"]

    wrong_request = deepcopy(result)
    wrong_request["request_id"] = "another-extraction-request-001"
    wrong_request["result_sha256"] = module.standalone_extraction_result_sha256(
        wrong_request
    )
    with pytest.raises(module.StandaloneDwgExtractionError, match="RESULT_PLAN_MISMATCH"):
        module.validate_standalone_extraction_result(
            wrong_request,
            plan=approved_plan,
            inspection_result=inspection,
        )


def test_provenance_rejects_source_dara_from_different_run() -> None:
    module = _module()
    source_bytes = b"standalone-source"
    candidate_bytes = b"standalone-candidate"
    import hashlib

    source_sha = hashlib.sha256(source_bytes).hexdigest()
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    inspection = _inspection_result()
    inspection["source_identity"]["sha256"] = source_sha
    inspection["source_sha256_before"] = source_sha
    inspection["source_sha256_after"] = source_sha
    inspection["inspection_sha256"] = module.standalone_inspection_result_sha256(
        inspection
    )
    extraction = _extraction_result()
    extraction["source_drawing_sha256"] = source_sha
    extraction["candidate_output_sha256"] = candidate_sha
    extraction["result_sha256"] = module.standalone_extraction_result_sha256(
        extraction
    )
    plan = _extraction_plan()
    plan["inspection_id"] = inspection["inspection_id"]
    plan["inspection_sha256"] = inspection["inspection_sha256"]
    plan["source_drawing_sha256"] = source_sha

    from cad_agent.drawing_artifact_reference import (
        issue_drawing_artifact_reference,
        observe_drawing_artifact_currentness,
    )

    source_reference = issue_drawing_artifact_reference(
        run_id="foreign-run-001",
        project_id="project-001",
        drawing_id="drawing-001",
        artifact_role="BASELINE",
        artifact_bytes=source_bytes,
        upstream_evidence={
            "evidence_kind": "BASELINE_CUSTODY",
            "evidence_id": "baseline-evidence-foreign-run",
            "evidence_sha256": "1" * 64,
        },
    )
    source_observation = observe_drawing_artifact_currentness(
        reference=source_reference,
        artifact_bytes=source_bytes,
        observation_evidence_sha256="2" * 64,
    )

    with pytest.raises(
        module.StandaloneDwgExtractionError, match="PROVENANCE_SCOPE_MISMATCH"
    ):
        module.build_standalone_provenance_context(
            source_reference=source_reference,
            source_current_observation=source_observation,
            plan=plan,
            inspection_result=inspection,
            extraction_result=extraction,
        )
