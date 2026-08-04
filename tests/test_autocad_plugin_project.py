from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "autocad_plugin/CadAgent.AutoCAD2027.sln"
PLUGIN_PROJECT = ROOT / "autocad_plugin/CadAgent.AutoCAD2027/CadAgent.AutoCAD2027.csproj"
VERIFY_SCRIPT = ROOT / "scripts/verify.ps1"
IPC_CONTRACTS = ROOT / "contracts/autocad-ipc"


def _property(project: ET.Element, name: str) -> str | None:
    for element in project.iter():
        if element.tag.rsplit("}", 1)[-1] == name:
            return element.text
    return None


def test_solution_uses_the_exact_release_x64_projects() -> None:
    solution = SOLUTION.read_text(encoding="utf-8")
    assert '"CadAgent.AutoCAD2027", "CadAgent.AutoCAD2027\\CadAgent.AutoCAD2027.csproj"' in solution
    assert '"CadAgent.AutoCAD2027.Tests", "CadAgent.AutoCAD2027.Tests\\CadAgent.AutoCAD2027.Tests.csproj"' in solution
    assert "Release|x64" in solution


def test_plugin_project_targets_the_approved_autocad_boundary() -> None:
    project = ET.parse(PLUGIN_PROJECT).getroot()
    assert _property(project, "TargetFramework") == "net10.0-windows"
    assert _property(project, "PlatformTarget") == "x64"
    assert _property(project, "OutputType") == "Library"
    assert _property(project, "Nullable") == "enable"
    assert _property(project, "ImplicitUsings") == "enable"
    assert _property(project, "AutoCADProductBoundary") == "$(AutoCADProduct) $(AutoCADProductVersion)"


def test_plugin_references_only_non_copying_autodesk_managed_dlls() -> None:
    project = ET.parse(PLUGIN_PROJECT).getroot()
    references = {
        element.attrib["Include"]: element
        for element in project.iter()
        if element.tag.rsplit("}", 1)[-1] == "Reference"
    }
    assert set(references) == {"AcCoreMgd", "AcDbMgd", "AcMgd"}
    for name, reference in references.items():
        hint_path = next(
            child.text
            for child in reference
            if child.tag.rsplit("}", 1)[-1] == "HintPath"
        )
        private = next(
            child.text
            for child in reference
            if child.tag.rsplit("}", 1)[-1] == "Private"
        )
        assert hint_path == f"$(AutodeskReferenceDir)\\{name}.dll"
        assert private == "false"


def test_verifier_checks_build_outputs_for_autodesk_dll_copying() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    for name in ("AcCoreMgd.dll", "AcDbMgd.dll", "AcMgd.dll"):
        assert name in script
    assert "Get-ChildItem" in script
    assert "no Autodesk Managed DLLs copied" in script


def test_drawing_setup_audit_ipc_contract_is_versioned_and_read_only() -> None:
    request_schema = json.loads((IPC_CONTRACTS / "request.schema.json").read_text(encoding="utf-8"))
    result_schema = json.loads((IPC_CONTRACTS / "result.schema.json").read_text(encoding="utf-8"))
    operation_schema = json.loads(
        (IPC_CONTRACTS / "operations/drawing-setup-audit.schema.json").read_text(
            encoding="utf-8"
        )
    )
    request_example = json.loads(
        (IPC_CONTRACTS / "examples/drawing-setup-audit-request.json").read_text(encoding="utf-8")
    )
    result_example = json.loads(
        (IPC_CONTRACTS / "examples/drawing-setup-audit-result.json").read_text(encoding="utf-8")
    )

    assert "drawing_setup_audit" in request_schema["properties"]["operation"]["enum"]
    assert "drawing_setup_audit" in result_schema["properties"]["operation"]["enum"]
    branch = next(
        item
        for item in request_schema["allOf"]
        if item["if"]["properties"]["operation"].get("const") == "drawing_setup_audit"
    )
    assert branch["then"]["properties"]["parameters"]["$ref"] == (
        "operations/drawing-setup-audit.schema.json"
    )
    result_branch = next(
        item
        for item in result_schema["allOf"]
        if item["if"]["properties"]["operation"].get("const") == "drawing_setup_audit"
    )
    result_properties = result_branch["then"]["properties"]
    assert result_properties["changed"]["const"] is False
    assert result_properties["entity_handles"]["maxItems"] == 0
    assert operation_schema["type"] == "object"
    assert operation_schema["additionalProperties"] is False
    assert operation_schema["maxProperties"] == 0
    assert request_example["operation"] == "drawing_setup_audit"
    assert request_example["parameters"] == {}
    assert result_example["operation"] == "drawing_setup_audit"
    assert result_example["changed"] is False
    assert result_example["entity_handles"] == []

    contract_models = (
        ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs"
    ).read_text(encoding="utf-8")
    dispatcher = (
        ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs"
    ).read_text(encoding="utf-8")
    assert '"drawing_setup_audit"' in contract_models
    assert "drawing_setup_audit parameters must be an empty object" in validator
    assert "drawing_setup_audit results must be read-only" in validator
    assert '"drawing_setup_audit" => DispatchDrawingSetupAudit' in dispatcher
    assert "DrawingSetupPayload.Create(snapshot)" in dispatcher
