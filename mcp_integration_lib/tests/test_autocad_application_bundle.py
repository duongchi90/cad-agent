from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_MANIFEST = REPO_ROOT / "autocad_plugin" / "CadAgent.bundle" / "PackageContents.xml"
PLUGIN_DLL = (
    REPO_ROOT
    / "autocad_plugin"
    / "CadAgent.AutoCAD2027"
    / "bin"
    / "x64"
    / "Release"
    / "net10.0-windows"
    / "CadAgent.AutoCAD2027.dll"
)


def test_autocad2027_bundle_autoloads_existing_cadagent_assembly() -> None:
    assert BUNDLE_MANIFEST.is_file(), (
        "Issue #409 RED: repository-owned CadAgent ApplicationPlugins manifest is absent"
    )

    root = ET.parse(BUNDLE_MANIFEST).getroot()
    assert root.tag == "ApplicationPackage"
    assert root.attrib["AutodeskProduct"] == "AutoCAD"

    runtime = root.find("RuntimeRequirements")
    assert runtime is not None
    assert runtime.attrib["OS"] == "Win64"
    assert runtime.attrib["Platform"] == "AutoCAD*"
    assert runtime.attrib["SeriesMin"] == "R26.0"
    assert runtime.attrib["SeriesMax"] == "R26.0"

    entries = root.findall("./Components/ComponentEntry")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.attrib["AppName"] == "CadAgent.AutoCAD2027"
    assert entry.attrib["LoadOnAutoCADStartup"] == "True"

    module_path = (BUNDLE_MANIFEST.parent / entry.attrib["ModuleName"]).resolve()
    assert module_path == PLUGIN_DLL.resolve()
    assert module_path.is_file()
