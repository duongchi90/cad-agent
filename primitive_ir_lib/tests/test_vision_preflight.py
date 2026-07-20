from primitive_ir_lib.vision_preflight import check_vision_readiness

def test_preflight_reports_boolean_fields():
    report = check_vision_readiness()
    assert set(report) == {"sdk_installed", "api_key_configured", "ready_for_live_calls"}
    assert report["ready_for_live_calls"] == (report["sdk_installed"] and report["api_key_configured"])