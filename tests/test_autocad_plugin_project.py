from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "autocad_plugin/CadAgent.AutoCAD2027.sln"
PLUGIN_PROJECT = ROOT / "autocad_plugin/CadAgent.AutoCAD2027/CadAgent.AutoCAD2027.csproj"
VERIFY_SCRIPT = ROOT / "scripts/verify.ps1"


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
