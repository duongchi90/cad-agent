from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile
import uuid
import xml.etree.ElementTree as ET

import pytest


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
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_autocad2027_bundle_autoloads_existing_cadagent_assembly() -> None:
    if not PLUGIN_DLL.is_file():
        pytest.skip(
            "SKIP: bundle assembly is produced by the AutoCAD .NET build gate"
        )
    assert BUNDLE_MANIFEST.is_file(), (
        "Issue #409 RED: repository-owned CadAgent ApplicationPlugins manifest is absent"
    )

    root = ET.parse(BUNDLE_MANIFEST).getroot()
    assert root.tag == "ApplicationPackage"
    assert root.attrib["AutodeskProduct"] == "AutoCAD"
    product_code = root.attrib.get("ProductCode", "")
    assert product_code, (
        "Issue #409 RED: ApplicationPackage ProductCode is required for local deployment"
    )
    uuid.UUID(product_code)

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
    assert entry.attrib["LoadOnCommandInvocation"] == "True", (
        "Issue #409 RED: CadAgent dispatch must use command-demand loading"
    )
    assert entry.attrib["LoadOnAutoCADStartup"] == "False", (
        "Issue #409 RED: command-demand loading must not depend on startup timing"
    )
    commands = entry.findall("./Commands/Command")
    assert len(commands) == 1
    assert commands[0].attrib == {
        "Global": "CADAGENT_DISPATCH",
        "Local": "CADAGENT_DISPATCH",
    }

    bundle_root = BUNDLE_MANIFEST.parent.resolve()
    module_path = (BUNDLE_MANIFEST.parent / entry.attrib["ModuleName"]).resolve()
    assert module_path.is_relative_to(bundle_root), (
        "Issue #409 RED: ComponentEntry ModuleName escapes CadAgent.bundle"
    )

    assert PLUGIN_DLL.is_file()
    approved_sha256 = _sha256(PLUGIN_DLL)

    with tempfile.TemporaryDirectory(prefix="cadagent-bundle-stage-") as staging:
        staged_bundle = Path(staging) / "CadAgent.bundle"
        shutil.copytree(BUNDLE_MANIFEST.parent, staged_bundle)
        staged_module = staged_bundle / "Contents" / "Windows" / "CadAgent.AutoCAD2027.dll"
        staged_module.parent.mkdir(parents=True)
        shutil.copy2(PLUGIN_DLL, staged_module)

        staged_manifest = staged_bundle / "PackageContents.xml"
        staged_root = ET.parse(staged_manifest).getroot()
        staged_entry = staged_root.findall("./Components/ComponentEntry")[0]
        staged_module_path = (staged_manifest.parent / staged_entry.attrib["ModuleName"]).resolve()

        assert staged_module_path.is_relative_to(staged_bundle.resolve())
        assert staged_module_path == staged_module.resolve()
        assert _sha256(staged_module_path) == approved_sha256
