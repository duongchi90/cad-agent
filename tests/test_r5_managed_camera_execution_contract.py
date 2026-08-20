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
    """Validate authoritative dataflow from currentView.VisualStyleId to observed camera state."""
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

    # 3. Exact actual-view provenance: EnsureObservedCanonicalCameraState must acquire from exact member currentView.VisualStyleId
    assert re.search(r'\bcurrentView\.VisualStyleId\b', ensure_body) is not None, (
        "Counterfeit-14 rejected: acquisition must be rooted in exact member currentView.VisualStyleId"
    )

    # 4. Reaching assignment to raw style variable deriving from currentView.VisualStyleId:
    raw_assignment_pattern = re.compile(
        r'(?:var\s+|string\s+)?(?<![\.\w])\b([A-Za-z_][A-Za-z0-9_]*)\b\s*=\s*([^;]+);',
        re.DOTALL,
    )
    raw_assignments = [
        (var_name, rhs.strip())
        for var_name, rhs in raw_assignment_pattern.findall(ensure_body)
        if re.search(r'\bcurrentView\.VisualStyleId\b', rhs)
    ]
    assert len(raw_assignments) == 1, (
        f"Counterfeit-15 rejected: expected exactly 1 bare reaching assignment deriving from currentView.VisualStyleId, found {len(raw_assignments)}"
    )
    raw_var, rhs = raw_assignments[0]

    assert '"' not in rhs, (
        f"Counterfeit-7 rejected: raw visual style assignment contains string literal: {rhs!r}"
    )
    assert "camera.VisualStyle" not in rhs, (
        f"Counterfeit-7 rejected: raw visual style assignment contains camera.VisualStyle: {rhs!r}"
    )
    assert '?' not in rhs, (
        f"Counterfeit-7 rejected: raw visual style assignment contains ternary or nullable operator: {rhs!r}"
    )
    assert ".ToString()" not in rhs, (
        f"Counterfeit-19 rejected: raw visual style assignment uses ToString() on ObjectId instead of resolving visual style name"
    )

    # 5. Helper provenance & SDK-real read-only acquisition resolving exact overload with ObjectId parameter:
    helper_call_match = re.search(r'([A-Za-z0-9_]+)\s*\(([^)]*\bcurrentView\.VisualStyleId\b[^)]*)\)', rhs)
    assert helper_call_match is not None, (
        f"Counterfeit-25 rejected: unsupported direct RHS expression {rhs!r}; must resolve via approved DBVisualStyle helper"
    )
    helper_name = helper_call_match.group(1)
    args_str = helper_call_match.group(2)
    call_args = [a.strip() for a in args_str.split(',')]
    call_arity = len(call_args)
    arg_idx = None
    for i, a in enumerate(call_args):
        if re.search(r'\bcurrentView\.VisualStyleId\b', a):
            arg_idx = i
            break
    assert arg_idx is not None

    helper_defs = list(re.finditer(
        r'(?:private|public|internal|protected)\s+(?:static\s+)?[A-Za-z0-9_<>?]+\s+'
        + re.escape(helper_name)
        + r'\s*\(([^)]*)\)\s*\{',
        source,
        re.DOTALL,
    ))
    matched_helper_def = None
    for h_match in helper_defs:
        p_str = h_match.group(1).strip()
        params = [p.strip() for p in p_str.split(',') if p.strip()]
        if len(params) == call_arity:
            target_p = params[arg_idx]
            if re.match(r'^(?:(?:Autodesk\.AutoCAD\.DatabaseServices\.)?ObjectId)\s+([A-Za-z0-9_]+)$', target_p):
                p_var = target_p.split()[-1]
                matched_helper_def = (h_match, p_var)
                break

    assert matched_helper_def is not None, (
        f"Counterfeit-16 rejected: helper method {helper_name!r} with arity {call_arity} and ObjectId parameter at index {arg_idx} is missing from source"
    )
    helper_def_match, target_param = matched_helper_def

    h_start = helper_def_match.end()
    h_depth = 1
    h_pos = h_start
    while h_depth > 0 and h_pos < len(source):
        if source[h_pos] == '{':
            h_depth += 1
        elif source[h_pos] == '}':
            h_depth -= 1
        h_pos += 1
    helper_body = source[h_start:h_pos-1]

    # Strip comments to prevent comment-only tokens
    helper_clean = re.sub(r'//.*', '', helper_body)
    helper_clean = re.sub(r'/\*.*?\*/', '', helper_clean, flags=re.DOTALL)

    assert re.search(r'\bDBVisualStyle\b', helper_clean) is not None, (
        f"Counterfeit-21 rejected: helper {helper_name!r} must resolve visual style via SDK-real DBVisualStyle"
    )
    assert "ForWrite" not in helper_clean, (
        f"Counterfeit-24 rejected: DBVisualStyle opened ForWrite; read-only observation requires OpenMode.ForRead"
    )
    assert re.search(r'\b(?:OpenMode\.)?ForRead\b', helper_clean) is not None, (
        f"Helper {helper_name!r} must open DBVisualStyle with OpenMode.ForRead"
    )
    assert '?' not in helper_clean, (
        f"Counterfeit-17 rejected: helper {helper_name!r} contains ternary/null-coalescing conditional logic"
    )
    return_match = re.search(r'return\s+([^;]+);', helper_clean)
    assert return_match is not None, (
        f"Helper method {helper_name!r} has no return statement"
    )
    return_expr = return_match.group(1).strip()
    assert not return_expr.startswith('"'), (
        f"Counterfeit-13 rejected: helper method {helper_name!r} returns a constant literal: {return_expr!r}"
    )
    assert return_expr.endswith(".Name") or return_expr == "Name", (
        f"Counterfeit-17 rejected: helper return must access .Name of DBVisualStyle record, found {return_expr!r}"
    )

    ret_var = return_expr.split('.')[0].strip()
    ret_var_assignments = re.findall(
        rf'(?:var\s+|[A-Za-z0-9_<>?]+\s+)?(?<![\.\w])\b{re.escape(ret_var)}\b\s*=\s*([^;]+);',
        helper_clean,
    )
    assert len(ret_var_assignments) == 1, (
        f"Counterfeit-26 rejected: helper {helper_name!r} overwrites or has multiple assignments to return record {ret_var!r}"
    )
    r_rhs = ret_var_assignments[0].strip()

    assert re.search(rf'GetObject\s*\(\s*{re.escape(target_param)}\b', r_rhs) is not None, (
        f"Counterfeit-17 rejected: bound parameter {target_param!r} (at index {arg_idx}) is not opened in helper {helper_name!r}"
    )

    # Exact type-bearing DBVisualStyle acquisition:
    exact_dbvs_cast = (
        re.search(rf'\(\s*(?:Autodesk\.AutoCAD\.DatabaseServices\.)?DBVisualStyle\s*\)\s*[A-Za-z0-9_.]*GetObject\s*\(\s*{re.escape(target_param)}\s*,\s*(?:OpenMode\.)?ForRead\b', r_rhs)
        or re.search(rf'GetObject\s*\(\s*{re.escape(target_param)}\s*,\s*(?:OpenMode\.)?ForRead\b[^;]*\bas\s+(?:Autodesk\.AutoCAD\.DatabaseServices\.)?DBVisualStyle\b', r_rhs)
    )
    assert exact_dbvs_cast is not None, (
        f"Counterfeit-21 rejected: helper {helper_name!r} must resolve visual style via SDK-real DBVisualStyle cast from bound parameter {target_param!r} opened ForRead"
    )

    # 6. ObservedCameraState constructor call & canonical token verification:
    ocs_pattern = re.compile(
        r'new\s+ObservedCameraState\s*\('
        r'\s*([^,]+)\s*,'   # arg 1 (ViewDirection)
        r'\s*([^,]+)\s*,'   # arg 2 (Ucs)
        r'\s*([^)]+?)\s*'   # arg 3 (VisualStyle)
        r'\)',
        re.DOTALL,
    )
    ocs_match = ocs_pattern.search(ensure_body)
    assert ocs_match is not None, (
        "ObservedCameraState constructor call not found in EnsureObservedCanonicalCameraState"
    )
    vs_arg = ocs_match.group(3).strip()

    assert vs_arg == '"2D_WIREFRAME"', (
        f"Counterfeit-3 rejected: ObservedCameraState.VisualStyle must be exact literal \"2D_WIREFRAME\", found {vs_arg!r}"
    )

    # 7. Raw name attestation fail-closed check preceding constructor call:
    code_before_ocs = ensure_body[:ocs_match.start()]
    raw_attestation_block = re.search(
        r'if\s*\(\s*!\s*string\.Equals\s*\(\s*'
        + re.escape(raw_var)
        + r'\s*,\s*"2D Wireframe"\s*,\s*StringComparison\.OrdinalIgnoreCase\s*\)\s*\)\s*(?:\{[^{}]*)?throw\s+new\s+InvalidDataException\s*\(\s*"[^"]*NATIVE_RENDER_CAMERA_STATE_MISMATCH[^"]*"',
        code_before_ocs,
        re.DOTALL,
    )
    assert raw_attestation_block is not None, (
        f"Counterfeit-28 rejected: raw visual style {raw_var!r} must be attested in a direct throwing if-guard before ObservedCameraState construction"
    )

    # 8. Closed Mismatch Predicate against exact constructed observed instance field:
    obs_inst_pattern = re.compile(
        rf'(?:var\s+|ObservedCameraState\s+)?(?<![\.\w])\b([A-Za-z0-9_]+)\b\s*=\s*{re.escape(ocs_match.group(0))}',
        re.DOTALL,
    )
    obs_inst_match = obs_inst_pattern.search(ensure_body)
    assert obs_inst_match is not None, (
        "Constructed ObservedCameraState must be assigned to an observed instance variable"
    )
    obs_var = obs_inst_match.group(1).strip()

    mismatch_block_pattern = re.compile(
        r'if\s*\((.*?)\)\s*\{[^{}]*throw\s+new\s+InvalidDataException\s*\(\s*"[^"]*NATIVE_RENDER_CAMERA_STATE_MISMATCH[^"]*"',
        re.DOTALL,
    )
    mismatch_blocks = mismatch_block_pattern.findall(ensure_body)
    assert len(mismatch_blocks) > 0, (
        "Counterfeit-4 rejected: no if-statement directly throwing NATIVE_RENDER_CAMERA_STATE_MISMATCH"
    )

    def _is_approved_camera_inequality_clause(cl: str, obs_var_name: str) -> tuple[bool, bool]:
        while cl.startswith('(') and cl.endswith(')'):
            inner = cl[1:-1].strip()
            d = 0
            balanced = True
            for ch in inner:
                if ch == '(':
                    d += 1
                elif ch == ')':
                    d -= 1
                    if d < 0:
                        balanced = False
                        break
            if balanced and d == 0:
                cl = inner
            else:
                break

        if "== false" in cl or "== true" in cl or "!= true" in cl or "!= false" in cl:
            return (False, False)
        if re.search(r'(&&\s*false|\bfalse\s*&&)', cl):
            return (False, False)
        if cl in ("true", "!false", "1 == 1", "0 == 0", "null == null") or re.match(r'^\s*([0-9]+)\s*==\s*\1\s*$', cl):
            return (False, False)

        # EXACT VisualStyle comparison: must compare camera.VisualStyle against exact obs_var_name.VisualStyle
        p_vs1 = rf'^!\s*string\.Equals\s*\(\s*camera\.VisualStyle\s*,\s*{re.escape(obs_var_name)}\.VisualStyle(?:\s*,\s*[^)]+)?\s*\)$'
        p_vs2 = rf'^!\s*string\.Equals\s*\(\s*{re.escape(obs_var_name)}\.VisualStyle\s*,\s*camera\.VisualStyle(?:\s*,\s*[^)]+)?\s*\)$'
        p_vs3 = rf'^camera\.VisualStyle\s*!=\s*{re.escape(obs_var_name)}\.VisualStyle$'
        p_vs4 = rf'^{re.escape(obs_var_name)}\.VisualStyle\s*!=\s*camera\.VisualStyle$'
        if any(re.search(p, cl) for p in (p_vs1, p_vs2, p_vs3, p_vs4)):
            return (True, True)

        # EXACT ViewDirection and Ucs paired comparisons:
        p_vd1 = rf'^!\s*string\.Equals\s*\(\s*camera\.ViewDirection\s*,\s*{re.escape(obs_var_name)}\.ViewDirection(?:\s*,\s*[^)]+)?\s*\)$'
        p_vd2 = rf'^camera\.ViewDirection\s*!=\s*{re.escape(obs_var_name)}\.ViewDirection$'
        p_ucs1 = rf'^!\s*string\.Equals\s*\(\s*camera\.Ucs\s*,\s*{re.escape(obs_var_name)}\.Ucs(?:\s*,\s*[^)]+)?\s*\)$'
        p_ucs2 = rf'^camera\.Ucs\s*!=\s*{re.escape(obs_var_name)}\.Ucs$'
        if any(re.search(p, cl) for p in (p_vd1, p_vd2, p_ucs1, p_ucs2)):
            return (True, False)

        return (False, False)

    cond_valid = False
    for cond in mismatch_blocks:
        clauses = [c.strip() for c in cond.split('||')]
        all_clauses_approved = True
        has_vs_pair = False
        for clause in clauses:
            approved, is_vs = _is_approved_camera_inequality_clause(clause.strip(), obs_var)
            if not approved:
                all_clauses_approved = False
                break
            if is_vs:
                has_vs_pair = True
        if all_clauses_approved and has_vs_pair:
            cond_valid = True
            break

    assert cond_valid, (
        f"Counterfeit-8 rejected: no throwing if-condition has closed, approved inequality comparison clauses against {obs_var}.VisualStyle"
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
    with pytest.raises(AssertionError, match="Counterfeit-14 rejected"):
        _validate_paper_space_visual_style_dataflow(c1)

    # Counterfeit 2: request-derived camera.VisualStyle passed as observed
    c2 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", camera.VisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-3 rejected"):
        _validate_paper_space_visual_style_dataflow(c2)

    # Counterfeit 3: non-canonical literal in constructor
    c3 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "INVALID_LITERAL");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-3 rejected"):
        _validate_paper_space_visual_style_dataflow(c3)

    # Counterfeit 4: unconditional/pass-through (no mismatch check against camera.VisualStyle)
    c4 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-4 rejected"):
        _validate_paper_space_visual_style_dataflow(c4)

    # Counterfeit 5: multiple assignments / overwritten before constructor
    c5 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var secondAssign = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-15 rejected"):
        _validate_paper_space_visual_style_dataflow(c5)

    # Counterfeit 6: mismatch check compares against unrelated literal
    c6 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, "2D_WIREFRAME_OTHER")) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c6)

    # Counterfeit 7: unquoted variable fallback / dead .VisualStyleId ternary branch
    c7 = '''
    private static string Resolve(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var fallback = "2D";
        var rawVisualStyle = false ? Resolve(currentView.VisualStyleId) : fallback;
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
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
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        var unusedComparison = string.Equals(camera.VisualStyle, observed.VisualStyle);
        if (dummyFlag) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c8)

    # Counterfeit 9: positive-equality throw (throws when EQUAL instead of NOT equal)
    c9 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c9)

    # Counterfeit 10: wrong uncaptured alias (mismatch checks unlinked variable name)
    c10 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var state = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, unlinkedOtherState.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return state;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c10)

    # Counterfeit 11: negated comparison modified by `== false`
    c11 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle) == false) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c11)

    # Counterfeit 12: negated comparison neutralized by `&& false`
    c12 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle) && false) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c12)

    # Counterfeit 13: dead helper that returns a constant literal string
    c13 = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        return "2D_WIREFRAME";
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-21 rejected"):
        _validate_paper_space_visual_style_dataflow(c13)

    # Counterfeit 14: otherView.VisualStyleId instead of currentView.VisualStyleId
    c14 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(otherView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-14 rejected"):
        _validate_paper_space_visual_style_dataflow(c14)

    # Counterfeit 15: member-qualified suffix assignment holder.rawVisualStyle
    c15 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        holder.rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-15 rejected"):
        _validate_paper_space_visual_style_dataflow(c15)

    # Counterfeit 16: missing helper definition
    c16 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = MissingHelperFunction(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-16 rejected"):
        _validate_paper_space_visual_style_dataflow(c16)

    # Counterfeit 17: helper taking (ObjectId a, ObjectId b) where currentView.VisualStyleId is b but helper uses a
    c17 = '''
    private static string ResolveVisualStyle(ObjectId a, ObjectId b) {
        var record = (DBVisualStyle)transaction.GetObject(a, OpenMode.ForRead);
        return record.Name;
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(dummyId, currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-17 rejected"):
        _validate_paper_space_visual_style_dataflow(c17)

    # Counterfeit 18: tautological mismatch condition `1 == 1 || !string.Equals(...)`
    c18 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (1 == 1 || !string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c18)

    # Counterfeit 19: ToString() on ObjectId instead of name resolution
    c19 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = currentView.VisualStyleId.ToString();
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-19 rejected"):
        _validate_paper_space_visual_style_dataflow(c19)

    # Counterfeit 20: lookalike member currentView.VisualStyleIdFake
    c20 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleIdFake);
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-14 rejected"):
        _validate_paper_space_visual_style_dataflow(c20)

    # Counterfeit 21: helper using non-canonical VisualStyleTableRecord instead of DBVisualStyle
    c21 = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        var record = (VisualStyleTableRecord)transaction.GetObject(vsId, OpenMode.ForRead);
        return record.Name;
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-21 rejected"):
        _validate_paper_space_visual_style_dataflow(c21)

    # Counterfeit 22: parenthesized tautological mismatch condition `!string.Equals(...) || (true)`
    c22 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle) || (true)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c22)

    # Counterfeit 23 (Probe a): raw DBVisualStyle.Name passed directly into ObservedCameraState / camera comparison
    c23 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", rawVisualStyle);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-3 rejected"):
        _validate_paper_space_visual_style_dataflow(c23)

    # Counterfeit 24 (Probe b): DBVisualStyle opened OpenMode.ForWrite
    c24 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForWrite); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-24 rejected"):
        _validate_paper_space_visual_style_dataflow(c24)

    # Counterfeit 25 (Probe c): unsupported direct-expression bypass currentView.VisualStyleId.GetType().Name
    c25 = '''
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = currentView.VisualStyleId.GetType().Name;
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-25 rejected"):
        _validate_paper_space_visual_style_dataflow(c25)

    # Counterfeit 26 (Probe d): helper gets correct bound ObjectId ForRead, then overwrites record before .Name return
    c26 = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        var record = (DBVisualStyle)transaction.GetObject(vsId, OpenMode.ForRead);
        record = (DBVisualStyle)transaction.GetObject(otherId, OpenMode.ForRead);
        return record.Name;
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-26 rejected"):
        _validate_paper_space_visual_style_dataflow(c26)

    # Counterfeit 27 (Probe e): correct VisualStyle pair OR'ed with unrelated literal comparison
    c27 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle) || camera.ViewDirection != "TOP") {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c27)

    # Counterfeit 28: dead raw visual style attestation (no throwing if-branch for !string.Equals(raw, "2D Wireframe", ...))
    c28 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var is2D = string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase);
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.ViewDirection, observed.ViewDirection, StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, observed.Ucs, StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, observed.VisualStyle, StringComparison.Ordinal)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: Visual style mismatch");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-28 rejected"):
        _validate_paper_space_visual_style_dataflow(c28)

    # Counterfeit 29: literal canonical mismatch shortcut (!string.Equals(camera.VisualStyle, "2D_WIREFRAME"))
    c29 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active visual style is not 2D Wireframe.");
        }
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.ViewDirection, observed.ViewDirection, StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, observed.Ucs, StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, "2D_WIREFRAME", StringComparison.Ordinal)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: Visual style mismatch");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-8 rejected"):
        _validate_paper_space_visual_style_dataflow(c29)

    # Counterfeit 30: same-name different-arity overload decoy (safe 1-arg overload exists, but call site uses 2-arg unsafe overload)
    c30 = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        var record = (DBVisualStyle)transaction.GetObject(vsId, OpenMode.ForRead);
        return record.Name;
    }
    private static string ResolveVisualStyle(ObjectId vsId, ObjectId decoy) {
        return "2D_WIREFRAME";
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId, decoyId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active visual style is not 2D Wireframe.");
        }
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.ViewDirection, observed.ViewDirection, StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, observed.Ucs, StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, observed.VisualStyle, StringComparison.Ordinal)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: Visual style mismatch");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-21 rejected"):
        _validate_paper_space_visual_style_dataflow(c30)

    # Counterfeit 31: local variable alias passed into ObservedCameraState constructor
    c31 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var canonicalVs = "2D_WIREFRAME";
        var observed = new ObservedCameraState("TOP", "WORLD", canonicalVs);
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-3 rejected"):
        _validate_paper_space_visual_style_dataflow(c31)

    # Counterfeit 32: comment-only DBVisualStyle token / DBVisualStyleFake
    c32 = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        // DBVisualStyle
        var record = (DBVisualStyleFake)transaction.GetObject(vsId, OpenMode.ForRead);
        return record.Name;
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-21 rejected"):
        _validate_paper_space_visual_style_dataflow(c32)

    # Counterfeit 33: post-hoc raw visual style attestation guard placed after constructor call
    c33 = '''
    private static string ResolveVisualStyle(ObjectId vsId) { var record = (DBVisualStyle)t.GetObject(vsId, OpenMode.ForRead); return record.Name; }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-28 rejected"):
        _validate_paper_space_visual_style_dataflow(c33)

    # Counterfeit 34: same-name same-arity overload decoy (safe non-ObjectId overload vs unsafe ObjectId overload)
    c34 = '''
    private static string ResolveVisualStyle(int dummy) {
        var record = (DBVisualStyle)transaction.GetObject(dummyId, OpenMode.ForRead);
        return record.Name;
    }
    private static string ResolveVisualStyle(ObjectId vsId) {
        return "2D_WIREFRAME";
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.VisualStyle, observed.VisualStyle)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH");
        }
        return observed;
    }
    '''
    with pytest.raises(AssertionError, match="Counterfeit-21 rejected"):
        _validate_paper_space_visual_style_dataflow(c34)

    # Valid synthetic with pre-existing earlier WORLD/TOP mismatch checks and SDK-real DBVisualStyle helper passes
    valid_with_earlier_checks = '''
    private static string ResolveVisualStyle(ObjectId vsId) {
        var record = (DBVisualStyle)transaction.GetObject(vsId, OpenMode.ForRead);
        return record.Name;
    }
    private static ObservedCameraState EnsureObservedCanonicalCameraState(NativeRenderRequest request, NativeRenderCamera camera, ViewTableRecord currentView) {
        if (worldUcs != 1) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: UCS mismatch");
        }
        if (!IsTopDirection(currentView.ViewDirection)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: View direction mismatch");
        }
        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active visual style is not 2D Wireframe.");
        }
        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.ViewDirection, observed.ViewDirection, StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, observed.Ucs, StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, observed.VisualStyle, StringComparison.Ordinal)) {
            throw new InvalidDataException("NATIVE_RENDER_CAMERA_STATE_MISMATCH: Visual style mismatch");
        }
        return observed;
    }
    '''
    _validate_paper_space_visual_style_dataflow(valid_with_earlier_checks)


def test_managed_reader_preserves_legacy_layout_plot_path_without_camera() -> None:
    source = _text(READER)
    assert "request.RenderOptions.Camera is null" in source
    assert "PlotType.Layout" in source
    assert "ScaleToFit" in source
