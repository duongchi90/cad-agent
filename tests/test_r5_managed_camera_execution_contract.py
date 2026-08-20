from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Drawing/NativeRenderModels.cs"
READER = ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadNativeRenderReader.cs"
VALIDATOR = ROOT / "autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_managed_native_render_parses_optional_closed_camera_contract() -> None:
    source = _text(MODELS)
    assert "record NativeRenderCamera(" in source
    assert "NativeRenderCamera? Camera" in source
    assert 'GetOptionalObject(renderOptions, "camera")' in source
    assert '"canonical-camera-render-1.0"' in source


def test_managed_camera_render_emits_artifact_bound_visual_capture_receipt() -> None:
    source = _text(MODELS)
    assert "record NativeRenderCameraReceipt(" in source
    assert "NativeRenderCameraReceipt? VisualCaptureReceipt" in source
    assert 'payload["visual_capture_receipt"]' in source
    assert '"visual-capture-receipt-1.0"' in source
    assert "TransientStateRestored" in source


def test_ipc_validator_accepts_camera_only_as_closed_native_render_extension() -> None:
    source = _text(VALIDATOR)
    assert 'ValidateNativeRenderCamera(' in source
    assert '"camera"' in source
    assert '"visual_capture_receipt"' in source
    assert 'canonical camera native render must be PNG' in source


def test_managed_reader_uses_deterministic_plot_window_not_zoom_command_text() -> None:
    source = _text(READER)
    assert "SetPlotWindowArea(" in source
    assert "PlotType.Window" in source
    assert "BuildCanonicalCameraWindow(" in source
    assert "CreateCameraReceipt(" in source
    assert 'SendStringToExecute("ZOOM' not in source
    assert "ZoomExtents" not in source


def test_managed_reader_transforms_wcs_camera_window_to_dcs_before_plotting() -> None:
    source = _text(READER)
    assert "Editor.GetCurrentView()" in source
    assert "Matrix3d.PlaneToWorld(" in source
    assert "Matrix3d.Displacement(" in source
    assert "Matrix3d.Rotation(" in source
    assert ".ViewTwist" in source
    assert ".Inverse()" in source
    assert "TransformBy(" in source
    assert "SetPlotWindowArea(" in source


def test_managed_camera_fails_closed_unless_requested_layout_is_current() -> None:
    source = _text(READER)
    assert 'GetSystemVariable("CTAB")' in source
    assert "request.Layout.Name" in source
    assert "NATIVE_RENDER_CAMERA_LAYOUT_NOT_ACTIVE" in source


def test_managed_camera_attests_observed_top_world_wireframe_state() -> None:
    source = _text(READER)
    for system_variable in ("WORLDUCS", "VIEWDIR", "VIEWTWIST"):
        assert f'GetSystemVariable("{system_variable}")' in source
    assert "NATIVE_RENDER_CAMERA_STATE_MISMATCH" in source
    assert "ObservedViewDirection" in source
    assert "ObservedUcs" in source
    assert "ObservedVisualStyle" in source
    assert "cameraWindow.ObservedViewDirection" in source
    assert "cameraWindow.ObservedUcs" in source
    assert "cameraWindow.ObservedVisualStyle" in source


def test_managed_camera_paper_space_visual_style_does_not_use_vscurrent_system_variable() -> None:
    """Causal RED for terminal 5349900479: VSCURRENT throws eInvalidInput in
    paper-space root viewport (CVPORT=1).  Visual style must be acquired from
    the actual active viewport/view object, not the VSCURRENT system variable."""
    source = _text(READER)
    # Negative: VSCURRENT system-variable query must be absent.
    assert 'GetSystemVariable("VSCURRENT")' not in source

    # Positive structural binding — the production code must:
    # 1. Acquire visual style from actual viewport/view object property
    #    (Viewport.VisualStyleId / AbstractViewTableRecord.VisualStyleId),
    #    not from a string system-variable or a request/literal substitute.
    assert ".VisualStyleId" in source  # object property access, not bare token

    # 2. The observed visual style must flow into ObservedCameraState
    #    construction from the acquired viewport/view value — not from a
    #    hard-coded literal like "2D_WIREFRAME" or "2D Wireframe".
    #    Find the ObservedCameraState constructor call and verify the
    #    VisualStyle argument references a variable, not a string literal.
    import re
    ocs_pattern = re.compile(
        r'new\s+ObservedCameraState\s*\('
        r'[^)]*'           # ViewDirection arg
        r','
        r'[^)]*'           # Ucs arg
        r','
        r'\s*([^)]+?)\s*'  # VisualStyle arg (capture group 1)
        r'\)',
        re.DOTALL,
    )
    match = ocs_pattern.search(source)
    assert match is not None, (
        "ObservedCameraState constructor call not found in reader source"
    )
    visual_style_arg = match.group(1).strip()
    # Must NOT be a string literal (hard-coded value).
    assert not visual_style_arg.startswith('"'), (
        f"ObservedCameraState.VisualStyle is a hard-coded literal: "
        f"{visual_style_arg!r}; it must reference the acquired viewport "
        f"visual style"
    )


def test_managed_reader_preserves_legacy_layout_plot_path_without_camera() -> None:
    source = _text(READER)
    assert "request.RenderOptions.Camera is null" in source
    assert "PlotType.Layout" in source
    assert "ScaleToFit" in source
