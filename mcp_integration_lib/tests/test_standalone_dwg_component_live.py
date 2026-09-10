"""Opt-in live gate for standalone BVTL component extraction.

The gate consumes an operator-prepared JSON fixture and never invents a live
result.  The source DWG and all evidence referenced by the fixture remain
outside the repository.  When AutoCAD/File IPC is not prepared, the live test
reports the exact missing prerequisites and skips.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path

import pytest

from cad_agent.candidate_revision import build_candidate_revision_state
from cad_agent.drawing_query import observe_drawing, query_entities, validate_entity_query
from cad_agent.standalone_dwg_extraction import (
    build_standalone_extraction_plan,
    build_standalone_provenance_context,
    compose_standalone_candidate_binding,
    validate_standalone_inspection_request,
)
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    make_windows_dotnet_dispatch_trigger,
    normalize_windows_absolute_path,
    request_path,
    result_path,
)
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    make_windows_dispatch_trigger,
    make_windows_command_trigger,
    make_windows_lisp_trigger,
    make_windows_start_tab_no_document_probe,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_DLL_PATH = (
    _REPO_ROOT
    / "autocad_plugin"
    / "CadAgent.AutoCAD2027"
    / "bin"
    / "x64"
    / "Release"
    / "net10.0-windows"
    / "CadAgent.AutoCAD2027.dll"
)
_FIXTURE_FIELDS = frozenset(
    {
        "project_id",
        "drawing_id",
        "inspection_request",
        "extraction_plan",
        "source_upstream_evidence",
        "observation_evidence_sha256",
        "candidate_id",
        "candidate_upstream_evidence",
        "candidate_observation_evidence_sha256",
        "query",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _normalized_local_path(value: str | None) -> str | None:
    if not value:
        return None
    try:
        normalized = normalize_windows_absolute_path(value)
    except ValueError:
        return None
    if normalized.startswith("\\\\"):
        return None
    if value.replace("/", "\\") != normalized:
        return None
    return normalized.casefold()


def _path_key(value: str | Path) -> str:
    return normalize_windows_absolute_path(str(value)).casefold()


def _missing_prerequisites(
    environment: Mapping[str, str] | None = None,
    *,
    plugin_path: Path = _PLUGIN_DLL_PATH,
) -> list[str]:
    env = os.environ if environment is None else environment
    missing: list[str] = []

    if env.get("CAD_AGENT_FILE_IPC") != "1":
        missing.append("CAD_AGENT_FILE_IPC=1")
    file_root = _normalized_local_path(env.get("CAD_AGENT_FILE_IPC_DIR"))
    dotnet_root = _normalized_local_path(env.get("CAD_AGENT_DOTNET_IPC_DIR"))
    if file_root is None:
        missing.append("CAD_AGENT_FILE_IPC_DIR (local absolute path)")
    elif not Path(env["CAD_AGENT_FILE_IPC_DIR"]).is_dir():
        missing.append("CAD_AGENT_FILE_IPC_DIR (directory missing)")
    if dotnet_root is None:
        missing.append("CAD_AGENT_DOTNET_IPC_DIR (local absolute path)")
    elif not Path(env["CAD_AGENT_DOTNET_IPC_DIR"]).is_dir():
        missing.append("CAD_AGENT_DOTNET_IPC_DIR (directory missing)")
    if file_root is not None and dotnet_root is not None and file_root != dotnet_root:
        missing.append("CAD_AGENT_FILE_IPC_DIR == CAD_AGENT_DOTNET_IPC_DIR")

    try:
        if int(env.get("CAD_AGENT_AUTOCAD_HWND", "")) <= 0:
            raise ValueError
    except ValueError:
        missing.append("CAD_AGENT_AUTOCAD_HWND (positive window handle)")

    lisp_path = env.get("CAD_AGENT_AUTOCAD_LISP_PATH")
    if not lisp_path:
        missing.append("CAD_AGENT_AUTOCAD_LISP_PATH")
    elif not Path(lisp_path).is_file():
        missing.append("CAD_AGENT_AUTOCAD_LISP_PATH (file missing)")

    fixture_path = env.get("CAD_AGENT_STANDALONE_DWG_FIXTURE_JSON")
    if not fixture_path:
        missing.append("CAD_AGENT_STANDALONE_DWG_FIXTURE_JSON")
    elif not Path(fixture_path).is_file():
        missing.append("CAD_AGENT_STANDALONE_DWG_FIXTURE_JSON (file missing)")

    source_path = env.get("CAD_AGENT_STANDALONE_DWG_SOURCE_PATH")
    if not source_path:
        missing.append("CAD_AGENT_STANDALONE_DWG_SOURCE_PATH (approved BVTL.dwg file)")
    else:
        source = Path(source_path)
        if source.name.casefold() != "bvtl.dwg":
            missing.append("CAD_AGENT_STANDALONE_DWG_SOURCE_PATH (approved BVTL.dwg basename)")
        elif not source.is_file():
            missing.append("CAD_AGENT_STANDALONE_DWG_SOURCE_PATH (file missing)")

    if not _is_sha256(env.get("CAD_AGENT_STANDALONE_DWG_SOURCE_SHA256")):
        missing.append("CAD_AGENT_STANDALONE_DWG_SOURCE_SHA256")
    if not _is_sha256(env.get("CAD_AGENT_STANDALONE_DWG_SOURCE_SETUP_AUDIT_SHA256")):
        missing.append("CAD_AGENT_STANDALONE_DWG_SOURCE_SETUP_AUDIT_SHA256")

    disposable_root = env.get("CAD_AGENT_STANDALONE_DWG_DISPOSABLE_ROOT")
    if not disposable_root:
        missing.append("CAD_AGENT_STANDALONE_DWG_DISPOSABLE_ROOT")
    elif not Path(disposable_root).is_dir():
        missing.append("CAD_AGENT_STANDALONE_DWG_DISPOSABLE_ROOT (directory missing)")

    if not plugin_path.is_file():
        missing.append("approved CadAgent.AutoCAD2027 Release plugin binary")
    return missing


def _load_fixture(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or set(payload) != _FIXTURE_FIELDS:
        raise AssertionError(
            "standalone live fixture must contain exactly the documented evidence fields"
        )
    return dict(payload)


def _assert_ipc_files_are_consumed(client: DotNetIPCClient, request_id: str) -> None:
    assert not request_path(client.ipc_dir, request_id).exists()
    assert not result_path(client.ipc_dir, request_id).exists()


def test_missing_prerequisites_are_reported_without_fabricating_live_evidence(
    tmp_path: Path,
) -> None:
    assert _missing_prerequisites({}, plugin_path=tmp_path / "missing.dll") == [
        "CAD_AGENT_FILE_IPC=1",
        "CAD_AGENT_FILE_IPC_DIR (local absolute path)",
        "CAD_AGENT_DOTNET_IPC_DIR (local absolute path)",
        "CAD_AGENT_AUTOCAD_HWND (positive window handle)",
        "CAD_AGENT_AUTOCAD_LISP_PATH",
        "CAD_AGENT_STANDALONE_DWG_FIXTURE_JSON",
        "CAD_AGENT_STANDALONE_DWG_SOURCE_PATH (approved BVTL.dwg file)",
        "CAD_AGENT_STANDALONE_DWG_SOURCE_SHA256",
        "CAD_AGENT_STANDALONE_DWG_SOURCE_SETUP_AUDIT_SHA256",
        "CAD_AGENT_STANDALONE_DWG_DISPOSABLE_ROOT",
        "approved CadAgent.AutoCAD2027 Release plugin binary",
    ]


@pytest.mark.autocad_mechanical
def test_standalone_bvtl_live_gate_binds_source_candidate_and_query() -> None:
    missing = _missing_prerequisites()
    if missing:
        pytest.skip("SKIP: missing prerequisites: " + "; ".join(missing))

    environment = os.environ
    fixture = _load_fixture(Path(environment["CAD_AGENT_STANDALONE_DWG_FIXTURE_JSON"]))
    source_path = Path(environment["CAD_AGENT_STANDALONE_DWG_SOURCE_PATH"]).resolve()
    expected_source_path = normalize_windows_absolute_path(str(source_path))
    source_hash = environment["CAD_AGENT_STANDALONE_DWG_SOURCE_SHA256"]
    setup_audit_hash = environment[
        "CAD_AGENT_STANDALONE_DWG_SOURCE_SETUP_AUDIT_SHA256"
    ]

    inspection_request = validate_standalone_inspection_request(
        fixture["inspection_request"]
    )
    assert inspection_request["source_drawing_path"] == expected_source_path
    assert inspection_request["source_drawing_sha256"] == source_hash
    assert inspection_request["source_setup_audit_sha256"] == setup_audit_hash
    assert _sha256(source_path) == source_hash

    disposable_root = Path(
        environment["CAD_AGENT_STANDALONE_DWG_DISPOSABLE_ROOT"]
    ).resolve()
    extraction_plan = fixture["extraction_plan"]
    candidate_output_path = Path(str(extraction_plan["candidate_output_path"])).resolve()
    assert _path_key(candidate_output_path) != _path_key(source_path)
    assert candidate_output_path.is_relative_to(disposable_root)
    assert not candidate_output_path.exists()

    plan = build_standalone_extraction_plan(
        extraction_plan,
        inspection_request=inspection_request,
    )
    assert plan["candidate_base_model"] == "EMPTY_NEW_DATABASE"
    assert _path_key(plan["candidate_output_path"]) == _path_key(candidate_output_path)

    hwnd = int(environment["CAD_AGENT_AUTOCAD_HWND"])
    legacy_client = FileIPCLiveMCPClient(
        ipc_dir=environment["CAD_AGENT_FILE_IPC_DIR"],
        trigger=make_windows_dispatch_trigger(hwnd),
        raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
        bootstrap_lisp_path=environment["CAD_AGENT_AUTOCAD_LISP_PATH"],
        command_trigger=make_windows_command_trigger(hwnd),
        start_tab_no_document_probe=make_windows_start_tab_no_document_probe(hwnd),
        bootstrap_start_tab=True,
    )
    dotnet_client = DotNetIPCClient(
        ipc_dir=environment["CAD_AGENT_DOTNET_IPC_DIR"],
        trigger=make_windows_dotnet_dispatch_trigger(hwnd),
        timeout_s=30.0,
    )

    active_path: str | None = None
    candidate_opened = False
    candidate_created = False
    candidate_hash: str | None = None

    try:
        legacy_client.drawing_open(str(source_path), read_only=True)
        active_path = expected_source_path
        source_variables = legacy_client.drawing_get_variables(["DBMOD"])
        assert type(source_variables.get("DBMOD")) is int
        expected_dbmod = int(inspection_request["expected_dbmod"])
        assert source_variables["DBMOD"] == expected_dbmod

        health_id = "standalone-live-health"
        health = dotnet_client.health(expected_source_path, request_id=health_id)
        assert health["success"] is True
        assert health["drawing_full_path"] == expected_source_path
        assert health["changed"] is False
        assert health["payload"]["host"] == "AutoCAD Mechanical 2027"
        assert health["payload"]["read_only"] is True
        assert health["payload"]["plugin_version"] == "1.0.0"
        assert _path_key(health["payload"]["plugin_binary_path"]) == _path_key(
            _PLUGIN_DLL_PATH.resolve()
        )
        assert health["payload"]["plugin_binary_sha256"] == _sha256(_PLUGIN_DLL_PATH)
        _assert_ipc_files_are_consumed(dotnet_client, health_id)

        setup_id = "standalone-live-setup-audit"
        setup = dotnet_client.drawing_setup_audit(
            expected_source_path,
            drawing_sha256=source_hash,
            request_id=setup_id,
        )
        assert setup["success"] is True
        assert setup["changed"] is False
        assert setup["payload"]["changed"] is False
        assert setup["payload"]["dbmod_before"] == expected_dbmod
        assert setup["payload"]["dbmod_after"] == expected_dbmod
        _assert_ipc_files_are_consumed(dotnet_client, setup_id)

        inspection_id = str(inspection_request["request_id"])
        inspection = dotnet_client.standalone_dwg_component_inspection(
            expected_source_path,
            inspection_request=inspection_request,
            request_id=inspection_id,
        )
        assert inspection["success"] is True
        assert inspection["changed"] is False
        assert inspection["entity_handles"] == []
        assert inspection["warnings"] == []
        assert inspection["errors"] == []
        inspection_payload = inspection["payload"]
        assert inspection_payload["source_identity"]["path"] == expected_source_path
        assert inspection_payload["source_identity"]["sha256"] == source_hash
        assert inspection_payload["source_identity"]["xref_count"] == 0
        assert inspection_payload["source_identity"]["dbmod"] == expected_dbmod
        assert inspection_payload["source_sha256_before"] == source_hash
        assert inspection_payload["source_sha256_after"] == source_hash
        assert inspection_payload["dbmod_before"] == expected_dbmod
        assert inspection_payload["dbmod_after"] == expected_dbmod
        assert inspection_payload["read_only"] is True
        assert inspection_payload["changed"] is False
        assert inspection_payload["eligible"] is True
        assert [group["group_id"] for group in inspection_payload["groups"]] == [
            group["group_id"] for group in inspection_request["selection_groups"]
        ]
        assert _sha256(source_path) == source_hash
        assert legacy_client.drawing_get_variables(["DBMOD"])["DBMOD"] == expected_dbmod
        _assert_ipc_files_are_consumed(dotnet_client, inspection_id)

        plan = build_standalone_extraction_plan(
            extraction_plan,
            inspection_result=inspection_payload,
            inspection_request=inspection_request,
        )
        assert not candidate_output_path.exists()

        extraction_id = str(plan["request_id"])
        extraction = dotnet_client.standalone_dwg_component_extraction(
            expected_source_path,
            extraction_plan=plan,
            inspection_result=inspection_payload,
            inspection_request=inspection_request,
            request_id=extraction_id,
        )
        assert extraction["success"] is True
        assert extraction["changed"] is True
        assert extraction["drawing_full_path"] == expected_source_path
        extraction_payload = extraction["payload"]
        assert extraction_payload["candidate_base_model"] == "EMPTY_NEW_DATABASE"
        assert extraction_payload["source_drawing_sha256"] == source_hash
        assert extraction_payload["source_mutated"] is False
        assert extraction_payload["source_dbmod_before"] == expected_dbmod
        assert extraction_payload["source_dbmod_after"] == expected_dbmod
        assert extraction_payload["save_performed"] is True
        assert extraction_payload["candidate_output_identity"]["path"] == str(
            plan["candidate_output_path"]
        )
        assert candidate_output_path.is_file()
        candidate_hash = _sha256(candidate_output_path)
        assert candidate_hash == extraction_payload["candidate_output_sha256"]
        candidate_created = True
        assert _sha256(source_path) == source_hash
        assert legacy_client.drawing_get_variables(["DBMOD"])["DBMOD"] == expected_dbmod
        _assert_ipc_files_are_consumed(dotnet_client, extraction_id)

        legacy_client.drawing_open(str(candidate_output_path))
        active_path = normalize_windows_absolute_path(str(candidate_output_path))
        candidate_opened = True
        assert _sha256(candidate_output_path) == candidate_hash

        provenance = build_standalone_provenance_context(
            source_artifact_bytes=source_path.read_bytes(),
            run_id=str(plan["run_id"]),
            project_id=str(fixture["project_id"]),
            drawing_id=str(fixture["drawing_id"]),
            source_upstream_evidence=fixture["source_upstream_evidence"],
            observation_evidence_sha256=str(fixture["observation_evidence_sha256"]),
            plan=plan,
            inspection_result=inspection_payload,
            extraction_result=extraction_payload,
        )
        composed = compose_standalone_candidate_binding(
            provenance_context=provenance,
            candidate_id=str(fixture["candidate_id"]),
            source_artifact_bytes=source_path.read_bytes(),
            candidate_artifact_bytes=candidate_output_path.read_bytes(),
            candidate_upstream_evidence=fixture["candidate_upstream_evidence"],
            candidate_observation_evidence_sha256=str(
                fixture["candidate_observation_evidence_sha256"]
            ),
        )
        candidate_reference = composed["candidate_reference"]
        assert candidate_reference["artifact_role"] == "R3_CANDIDATE"
        assert candidate_reference["artifact_sha256"] == candidate_hash
        assert composed["candidate_revision"]["upstream_bindings"][
            "candidate_drawing_sha256"
        ] == candidate_hash
        candidate_state = build_candidate_revision_state(
            candidate_revisions=[composed["candidate_revision"]],
            current_candidate_revision_sha256=composed["candidate_revision"][
                "candidate_revision_sha256"
            ],
        )

        query = validate_entity_query(fixture["query"])
        source_handles = {
            handle
            for group in inspection_request["selection_groups"]
            for handle in group["source_handles"]
        }
        candidate_handles = {
            handle
            for component in extraction_payload["components"]
            for handle in component["candidate_handles"]
        }
        assert query["handles"] or query["component_ids"] or query["view_ids"]
        query_handles = {handle.casefold() for handle in query["handles"]}
        assert query_handles.issubset(
            {handle.casefold() for handle in candidate_handles}
        )
        assert not query_handles.intersection(
            handle.casefold() for handle in source_handles
        )

        observation = observe_drawing(
            client=legacy_client,
            reference=candidate_reference,
            current_observation=composed["candidate_observation"],
            artifact_bytes=candidate_output_path.read_bytes(),
            parent_reference=None,
            accepted_transition_evidence_sha256=None,
            registry=composed["registry"],
            registry_upstream_context=composed["upstream_context"],
            candidate_state=candidate_state,
            expected_active_document_path=active_path,
        )
        query_result = query_entities(
            client=legacy_client,
            reference=candidate_reference,
            current_observation=composed["candidate_observation"],
            artifact_bytes=candidate_output_path.read_bytes(),
            parent_reference=None,
            accepted_transition_evidence_sha256=None,
            registry=composed["registry"],
            registry_upstream_context=composed["upstream_context"],
            candidate_state=candidate_state,
            expected_active_document_path=active_path,
            query=query,
        )
        assert query_result["binding"] == observation["binding"]
        assert query_result["entities"]
        assert all(
            item["handle"].casefold() in {handle.casefold() for handle in candidate_handles}
            for item in query_result["entities"]
        )

        close_id = "standalone-live-candidate-close"
        close = dotnet_client.close_disposable(
            active_path,
            disposable=True,
            save_changes=False,
            request_id=close_id,
        )
        assert close["success"] is True
        assert close["changed"] is False
        assert close["payload"]["closed_without_saving"] is True
        _assert_ipc_files_are_consumed(dotnet_client, close_id)
        candidate_opened = False
        active_path = None

        assert candidate_output_path.is_file()
        assert _sha256(candidate_output_path) == candidate_hash
        candidate_output_path.unlink()
        assert not candidate_output_path.exists()

        legacy_client.drawing_open(str(source_path))
        active_path = expected_source_path
        assert _sha256(source_path) == source_hash
        assert legacy_client.drawing_get_variables(["DBMOD"])["DBMOD"] == expected_dbmod
        legacy_client.drawing_close(save_changes=False)
        active_path = None
        legacy_client.close_start_tab_bootstrap()
    finally:
        if (
            candidate_opened
            and active_path is not None
            and _path_key(active_path) == _path_key(candidate_output_path)
        ):
            try:
                dotnet_client.close_disposable(
                    active_path,
                    disposable=True,
                    save_changes=False,
                    request_id="standalone-live-finally-candidate-close",
                )
            except Exception:
                pass
        if (
            active_path is not None
            and _path_key(active_path) != _path_key(candidate_output_path)
        ):
            try:
                legacy_client.drawing_close(save_changes=False)
            except Exception:
                pass
        if candidate_created and candidate_output_path.is_file() and candidate_hash:
            try:
                if _sha256(candidate_output_path) == candidate_hash:
                    candidate_output_path.unlink()
            except OSError:
                pass
        try:
            legacy_client.close_start_tab_bootstrap()
        except Exception:
            pass
