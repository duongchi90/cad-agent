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


def _validate_paper_space_visual_style_dataflow(source: str) -> None:
    """Validate authoritative dataflow from viewport/view VisualStyleId to observed camera state."""
    import re

    # 1. Negative: VSCURRENT system-variable query must be absent
    assert 'GetSystemVariable("VSCURRENT")' not in source, (
        "VSCURRENT system variable query must not be used in paper space"
    )

    # 2. Extract EnsureObservedCanonicalCameraState method body
    ensure_match = re.search(
        r'(private\s+static\s+ObservedCameraState\s+EnsureObservedCanonicalCameraState'
        r'\s*\([^)]*\)\s*\{)',
        source,
        re.DOTALL,
    )
    assert ensure_match is not None, (
        "EnsureObservedCanonicalCameraState method not found"
    )
    start_idx = ensure_match.end()
    depth = 1
    pos = start_idx
    while depth > 0 and pos < len(source):
        if source[pos] == '{':
            depth += 1
        elif source[pos] == '}':
            depth -= 1
        pos += 1
    ensure_body = source[ensure_match.start():pos]

    # 3. Counterfeit 1: dead/unrelated .VisualStyleId
    assert ".VisualStyleId" in ensure_body, (
        "Counterfeit-1 rejected: .VisualStyleId not found in EnsureObservedCanonicalCameraState"
    )

    # 4. Find the ObservedCameraState constructor call
    ocs_pattern = re.compile(
        r'new\s+ObservedCameraState\s*\('
        r'([^,]+),'   # arg 1 (ViewDirection)
        r'([^,]+),'   # arg 2 (Ucs)
        r'\s*([^)]+?)' # arg 3 (VisualStyle)
        r'\s*\)',
        re.DOTALL,
    )
    ocs_match = ocs_pattern.search(ensure_body)
    assert ocs_match is not None, (
        "ObservedCameraState constructor call not found in EnsureObservedCanonicalCameraState"
    )
    vs_arg = ocs_match.group(3).strip()

    # 5. Counterfeit 3: constant/literal in constructor
    assert not vs_arg.startswith('"'), (
        f"Counterfeit-3 rejected: ObservedCameraState.VisualStyle is a hard-coded literal {vs_arg!r}"
    )

    # 6. Counterfeit 2: request-derived in constructor argument
    assert "camera.VisualStyle" not in vs_arg, (
        f"Counterfeit-2 rejected: ObservedCameraState.VisualStyle references camera.VisualStyle ({vs_arg!r})"
    )

    # 7. Authoritative reaching-definition analysis:
    code_before_ocs = ensure_body[:ocs_match.start()]
    vs_var_name = vs_arg.split(".")[-1].split("(")[0].strip()

    assignment_pattern = re.compile(
        rf'(?:var\s+)?{re.escape(vs_var_name)}\s*=\s*([^;]+);',
        re.DOTALL,
    )
    assignments = assignment_pattern.findall(code_before_ocs)
    assert len(assignments) > 0, (
        f"Dataflow rejected: variable {vs_var_name!r} has no assignment before ObservedCameraState construction"
    )
    for a in assignments:
        rhs = a.strip()
        if '"' in rhs or "camera.VisualStyle" in rhs or ".VisualStyleId" not in rhs:
            raise AssertionError(
                f"Counterfeit-7 rejected: assignment to {vs_var_name!r} is not unconditionally derived from .VisualStyleId: {rhs!r}"
            )

    # 8. Mismatch check control-flow linkage:
    obs_inst_pattern = re.compile(
        rf'(?:var\s+)?([a-zA-Z0-9_]+)\s*=\s*{re.escape(ocs_match.group(0))}',
        re.DOTALL,
    )
    obs_inst_match = obs_inst_pattern.search(ensure_body)
    obs_var = obs_inst_match.group(1) if obs_inst_match else "observed"

    valid_targets = [vs_var_name, f"{obs_var}.VisualStyle", f"observed.VisualStyle"]

    # Match if-statement whose body directly throws NATIVE_RENDER_CAMERA_STATE_MISMATCH
    mismatch_block_pattern = re.compile(
        r'if\s*\((.*?)\)\s*\{[^{}]*throw\s+new\s+InvalidDataException\s*\(\s*"[^"]*NATIVE_RENDER_CAMERA_STATE_MISMATCH[^"]*"',
        re.DOTALL,
    )
    mismatch_match = mismatch_block_pattern.search(ensure_body)
    assert mismatch_match is not None, (
        "Counterfeit-4 rejected: no if-statement directly throwing NATIVE_RENDER_CAMERA_STATE_MISMATCH"
    )
    mismatch_cond = mismatch_match.group(1)

    cond_valid = False
    for vt in valid_targets:
        escaped_vt = re.escape(vt)
        p1 = rf'string\.Equals\s*\(\s*camera\.VisualStyle\s*,\s*{escaped_vt}\b'
        p2 = rf'string\.Equals\s*\(\s*{escaped_vt}\s*,\s*camera\.VisualStyle\b'
        p3 = rf'camera\.VisualStyle\s*!=\s*{escaped_vt}\b'
        p4 = rf'{escaped_vt}\s*!=\s*camera\.VisualStyle\b'
        if any(re.search(p, mismatch_cond) for p in (p1, p2, p3, p4)):
            cond_valid = True
            break

    assert cond_valid, (
        f"Counterfeit-8 rejected: throwing if-condition ({mismatch_cond.strip()!r}) does not compare camera.VisualStyle against the bound observed visual style ({vs_var_name!r} or {obs_var}.VisualStyle)"
    )


def test_managed_camera_paper_space_visual_style_does_not_use_vscurrent_system_variable() -> None:
    """Causal RED for terminal 5349900479: VSCURRENT throws eInvalidInput in
    paper-space root viewport (CVPORT=1).  Visual style must be acquired from
    the actual active viewport/view object, not the VSCURRENT system variable."""
    source = _text(READER)
    _validate_paper_space_visual_style_dataflow(source)


def test_paper_space_visual_style_discriminator_rejects_counterfeits() -> None:
    """Self-test demonstrating that the discriminator rejects all counterfeit families."""
    import pytest

    # Counterfeit 1: dead/unrelated .VisualStyleId in another method
    c1 = '''
    private void OtherMethod() { var x = viewport.VisualStyleId; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-1 rejected"):
        _validate_paper_space_visual_style_dataflow(c1)

    # Counterfeit 2: request-derived camera.VisualStyle passed as observed
    c2 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var dummy = currentView.VisualStyleId;
        var observed = new ObservedCameraState("TOP", "WORLD", camera.VisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-2 rejected"):
        _validate_paper_space_visual_style_dataflow(c2)

    # Counterfeit 3: constant/literal-derived variable in constructor
    c3 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var dummy = currentView.VisualStyleId;
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-3 rejected"):
        _validate_paper_space_visual_style_dataflow(c3)

    # Counterfeit 4: unconditional/pass-through (no mismatch check against camera.VisualStyle)
    c4 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-4 rejected"):
        _validate_paper_space_visual_style_dataflow(c4)

    # Counterfeit 5: .VisualStyleId assigned but overwritten with literal before constructor
    c5 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        observedVisualStyle = "2D_WIREFRAME";
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-7 rejected"):
        _validate_paper_space_visual_style_dataflow(c5)

    # Counterfeit 6: correct viewport constructor value, but mismatch check compares against unrelated literal
    c6 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        if (!string.Equals(camera.VisualStyle, "2D_WIREFRAME")) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c6)

    # Counterfeit 7: constant-dominant conditional / dead .VisualStyleId branch
    c7 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = false ? Resolve(currentView.VisualStyleId) : "2D_WIREFRAME";
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-7 rejected"):
        _validate_paper_space_visual_style_dataflow(c7)

    # Counterfeit 8: unused correct comparison + unrelated throwing predicate
    c8 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        var unusedComparison = string.Equals(camera.VisualStyle, observed.VisualStyle);
        if (dummyFlag) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c8)

    # Valid synthetic implementation passes
    valid = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var observedVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", observedVisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    _validate_paper_space_visual_style_dataflow(valid)


def test_managed_reader_preserves_legacy_layout_plot_path_without_camera() -> None:
    source = _text(READER)
    assert "request.RenderOptions.Camera is null" in source
    assert "PlotType.Layout" in source
    assert "ScaleToFit" in source
