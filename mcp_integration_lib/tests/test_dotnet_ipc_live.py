"""Opt-in disposable AutoCAD Mechanical smoke test for the .NET IPC path."""

import hashlib
import os
import shutil
import tempfile
import time
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import ezdxf
import pytest

from mcp_integration_lib.autocad_render_evidence import (
    REQUEST_SCHEMA_VERSION,
    build_render_evidence_request,
    validate_render_request,
)
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    DotNetIPCResultError,
    make_windows_dotnet_dispatch_trigger,
    normalize_windows_absolute_path,
    request_path,
    result_path,
)
from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    make_windows_dispatch_trigger,
    make_windows_lisp_trigger,
)


def _live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and bool(os.getenv("CAD_AGENT_AUTOCAD_HWND"))
        and bool(os.getenv("CAD_AGENT_AUTOCAD_LISP_PATH"))
    )


def _lean_setup_prerequisites_available() -> bool:
    return all(
        bool(os.getenv(name))
        for name in (
            "CAD_AGENT_LEAN_DISPOSABLE_DWG",
            "CAD_AGENT_AUTOCAD_HWND",
            "CAD_AGENT_DOTNET_IPC_DIR",
        )
    )


def _s2c_live_prerequisites_available() -> bool:
    return (
        os.getenv("CAD_AGENT_S2C_LIVE") == "1"
        and _live_prerequisites_available()
        and bool(os.getenv("CAD_AGENT_LEAN_DISPOSABLE_DWG"))
    )


def _s2c_refusal_probe_prerequisites_available(profile: str) -> bool:
    return _s2c_live_prerequisites_available() and (
        os.getenv("CAD_AGENT_S2C_NEGATIVE_PROFILE") == profile
    )


def _add_mechanical_bom_fixture(drawing_document) -> None:
    modelspace = drawing_document.modelspace()
    modelspace.add_line((0, 0), (10, 0))
    frame_block = drawing_document.blocks.new("COMP_FRAME")
    frame_block.add_attdef("PART_ID", (0, 0), text="", height=1.0)
    modelspace.add_blockref("COMP_FRAME", (0, 0)).add_auto_attribs(
        {"PART_ID": "FRAME-001"}
    )
    empty_block = drawing_document.blocks.new("COMP_EMPTY")
    empty_block.add_line((0, 0), (5, 0))
    nested_block = drawing_document.blocks.new("COMP_NESTED")
    nested_block.add_line((0, 0), (1, 0))
    empty_block.add_blockref("COMP_NESTED", (0, 0))
    modelspace.add_blockref("COMP_EMPTY", (20, 0))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _s2c_request(
    _drawing_full_path: str,
    drawing_sha256: str,
    request_id: str,
    *,
    artifact_kind: str = "PNG",
    layout_name: str = "Layout1",
    render_options: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_render_evidence_request(
        request_id=request_id,
        run_id="s2c-live-run",
        drawing_sha256=drawing_sha256,
        latest_mutation_sha256="b" * 64,
        visual_run_manifest_sha256="c" * 64,
        layout={"identity": "s2c-layout-001", "name": layout_name},
        artifact_kind=artifact_kind,
        render_options=render_options
        or {
            "background": "white",
            "dpi": 300,
            "fit_to_paper": True,
            "paper_size": "A4",
            "plot_style": "monochrome.ctb",
        },
        requested_at=(
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
    )


class NativeRenderRequestShapeTests(unittest.TestCase):
    def test_s2c_request_is_a_valid_closed_native_render_payload(self) -> None:
        request = _s2c_request(
            r"C:\\temp\\s2c-shape-regression.dwg",
            "a" * 64,
            "s2c-offline-shape",
        )
        expected_keys = {
            "schema_version",
            "request_id",
            "run_id",
            "drawing_sha256",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
            "requested_at",
        }

        self.assertEqual(expected_keys, set(request))
        self.assertEqual(REQUEST_SCHEMA_VERSION, request["schema_version"])
        self.assertEqual(request, validate_render_request(request))
        for forbidden_field in (
            "approval",
            "operation",
            "drawing_full_path",
            "parameters",
            "verdict",
            "repair",
            "publication",
        ):
            self.assertNotIn(forbidden_field, request)


def _cleanup_disposable_fixture_directory(
    test_directory: Path,
    drawing_path: Path,
    *,
    original_sha256: str,
) -> None:
    try:
        _wait_for_disposable_drawing_release(drawing_path)
        if original_sha256:
            if not drawing_path.is_file():
                raise AssertionError(f"Disposable drawing was removed: {drawing_path}")
            if original_sha256 != _sha256(drawing_path):
                raise AssertionError(f"Disposable drawing changed: {drawing_path}")
    finally:
        shutil.rmtree(test_directory)


class MechanicalBomFixtureTests(unittest.TestCase):
    def test_mechanical_bom_fixture_uses_direct_attributed_insert(self) -> None:
        drawing_document = ezdxf.new("R2010")
        _add_mechanical_bom_fixture(drawing_document)

        modelspace_inserts = [
            entity for entity in drawing_document.modelspace() if entity.dxftype() == "INSERT"
        ]
        self.assertEqual(
            ["COMP_FRAME", "COMP_EMPTY"],
            [insert.dxf.name for insert in modelspace_inserts],
        )
        frame_insert = next(
            insert for insert in modelspace_inserts if insert.dxf.name == "COMP_FRAME"
        )
        self.assertEqual(
            [("PART_ID", "FRAME-001")],
            [(attribute.dxf.tag, attribute.dxf.text) for attribute in frame_insert.attribs],
        )
        self.assertNotIn(
            "COMP_NESTED",
            [insert.dxf.name for insert in modelspace_inserts],
        )


def _wait_for_disposable_drawing_release(
    drawing_path: Path,
    *,
    timeout_s: float = 20.0,
    poll_interval_s: float = 0.1,
    replace: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] = os.replace,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Wait until AutoCAD releases a disposable drawing before directory removal."""

    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if poll_interval_s < 0:
        raise ValueError("poll_interval_s must not be negative")
    if not drawing_path.exists():
        return

    probe_path = drawing_path.with_name(f"{drawing_path.name}.release-probe")
    deadline = monotonic() + timeout_s
    while True:
        moved_to_probe = False
        try:
            replace(drawing_path, probe_path)
            moved_to_probe = True
            replace(probe_path, drawing_path)
            return
        except FileNotFoundError:
            if moved_to_probe:
                replace(probe_path, drawing_path)
            return
        except PermissionError as exc:
            if moved_to_probe:
                replace(probe_path, drawing_path)
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for disposable drawing release: {drawing_path}"
                ) from exc
            sleep(min(poll_interval_s, remaining))


@contextmanager
def _disposable_drawing_cleanup(
    dotnet_client: DotNetIPCClient,
    drawing_path: str,
) -> Iterator[Callable[[], None]]:
    cleanup_needed = True

    def mark_closed() -> None:
        nonlocal cleanup_needed
        cleanup_needed = False

    try:
        yield mark_closed
    finally:
        if cleanup_needed:
            dotnet_client.close_disposable(
                drawing_path,
                disposable=True,
                save_changes=False,
                request_id="dotnet-live-finally-close",
            )


class _CloseRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, bool, str]] = []

    def close_disposable(
        self,
        drawing_path: str,
        *,
        disposable: bool,
        save_changes: bool,
        request_id: str,
    ) -> None:
        self.calls.append((drawing_path, disposable, save_changes, request_id))


class _OpenThenRaise:
    def __init__(self) -> None:
        self.opened_paths: list[str] = []

    def drawing_open(self, drawing_path: str) -> None:
        self.opened_paths.append(drawing_path)
        raise RuntimeError("open raised after opening")


class DisposableCleanupTests(unittest.TestCase):
    def test_waits_until_disposable_drawing_is_released(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            drawing_path = Path(temporary_directory) / "dotnet_live.dxf"
            drawing_path.write_text("disposable", encoding="utf-8")
            attempts = 0

            def replace_with_transient_lock(source: str, destination: str) -> None:
                nonlocal attempts
                if os.fspath(source) == os.fspath(drawing_path):
                    attempts += 1
                    if attempts < 3:
                        raise PermissionError("drawing is still locked")
                os.replace(source, destination)

            _wait_for_disposable_drawing_release(
                drawing_path,
                timeout_s=1.0,
                poll_interval_s=0.0,
                replace=replace_with_transient_lock,
                sleep=lambda _seconds: None,
            )

            self.assertEqual(3, attempts)
            self.assertTrue(drawing_path.is_file())

    def test_closes_when_opening_raises_after_opening(self) -> None:
        drawing_path = r"C:\temp\disposable\dotnet_live.dxf"
        recorder = _CloseRecorder()
        legacy_client = _OpenThenRaise()

        with self.assertRaisesRegex(RuntimeError, "after opening"):
            with _disposable_drawing_cleanup(recorder, drawing_path):
                legacy_client.drawing_open(drawing_path)

        self.assertEqual([drawing_path], legacy_client.opened_paths)
        self.assertEqual(
            [(drawing_path, True, False, "dotnet-live-finally-close")],
            recorder.calls,
        )

    def test_verified_close_disarms_fallback_cleanup(self) -> None:
        drawing_path = r"C:\temp\disposable\dotnet_live.dxf"
        recorder = _CloseRecorder()

        with _disposable_drawing_cleanup(recorder, drawing_path) as mark_closed:
            recorder.close_disposable(
                drawing_path,
                disposable=True,
                save_changes=False,
                request_id="dotnet-live-close",
            )
            mark_closed()

        self.assertEqual(
            [(drawing_path, True, False, "dotnet-live-close")],
            recorder.calls,
        )

    def test_fixture_directory_is_removed_when_integrity_assertion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as parent_directory:
            test_directory = Path(parent_directory) / "fixture"
            test_directory.mkdir()
            drawing_path = test_directory / "dotnet_live.dxf"
            drawing_path.write_text("disposable", encoding="utf-8")

            with self.assertRaises(AssertionError):
                _cleanup_disposable_fixture_directory(
                    test_directory,
                    drawing_path,
                    original_sha256="sha-does-not-match",
                )

            self.assertFalse(test_directory.exists())


@unittest.skipUnless(
    _lean_setup_prerequisites_available(),
    "requires CAD_AGENT_LEAN_DISPOSABLE_DWG, CAD_AGENT_AUTOCAD_HWND, "
    "and CAD_AGENT_DOTNET_IPC_DIR",
)
@pytest.mark.autocad_mechanical
class PersonalSetupLiveTests(unittest.TestCase):
    def test_live_personal_setup_audit_is_read_only(self) -> None:
        drawing = Path(os.environ["CAD_AGENT_LEAN_DISPOSABLE_DWG"]).resolve()
        self.assertTrue(drawing.is_file(), f"Missing disposable drawing: {drawing}")
        self.assertIn(drawing.suffix.lower(), {".dwg", ".dxf"})
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        before = _sha256(drawing)
        drawing_full_path = normalize_windows_absolute_path(str(drawing))
        request_id = "lean-setup-live-001"
        client = DotNetIPCClient(
            ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
            trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            timeout_s=30.0,
        )

        result = client.drawing_setup_audit(
            drawing_full_path,
            drawing_sha256=before,
            request_id=request_id,
        )

        self.assertTrue(result["success"])
        self.assertEqual(drawing_full_path, result["drawing_full_path"])
        self.assertFalse(result["changed"])
        self.assertEqual([], result["entity_handles"])
        self.assertEqual([], result["errors"])
        self.assertFalse(result["payload"]["changed"])
        self.assertEqual(
            result["payload"]["dbmod_before"],
            result["payload"]["dbmod_after"],
        )
        self.assertEqual(before, _sha256(drawing))
        self.assertFalse(request_path(client.ipc_dir, request_id).exists())
        self.assertFalse(result_path(client.ipc_dir, request_id).exists())


@unittest.skipUnless(
    _live_prerequisites_available(),
    "requires CAD_AGENT_FILE_IPC=1, CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_AUTOCAD_LISP_PATH",
)
@pytest.mark.autocad_mechanical
class DotNetIPCLiveSmokeTests(unittest.TestCase):
    def test_disposable_dxf_uses_dotnet_mechanical_bom_health_review_and_close(self) -> None:
        test_directory = Path(tempfile.mkdtemp(prefix="cad_agent_dotnet_live_", dir=r"C:\temp"))
        drawing_path = test_directory / "dotnet_live.dxf"
        original_sha256 = ""

        try:
            drawing_document = ezdxf.new("R2010")
            _add_mechanical_bom_fixture(drawing_document)
            drawing_document.saveas(drawing_path)
            original_sha256 = _sha256(drawing_path)

            expected_full_path = normalize_windows_absolute_path(str(drawing_path))
            hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
            legacy_client = FileIPCLiveMCPClient(
                trigger=make_windows_dispatch_trigger(hwnd),
                raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            )
            dotnet_client = DotNetIPCClient(
                ipc_dir=r"C:\temp",
                trigger=make_windows_dotnet_dispatch_trigger(hwnd),
                timeout_s=20.0,
            )

            with _disposable_drawing_cleanup(dotnet_client, str(drawing_path)) as mark_closed:
                legacy_client.drawing_open(str(drawing_path))
                entities = legacy_client.entity_list()
                self.assertTrue(entities)
                handle = str(entities[0]["handle"])

                health_request_id = "dotnet-live-health"
                health = dotnet_client.health(
                    expected_full_path,
                    request_id=health_request_id,
                )
                self.assertTrue(health["success"])
                self.assertEqual("1.0.0", health["payload"]["plugin_version"])
                self.assertEqual(expected_full_path, health["drawing_full_path"])
                self.assertFalse(health["changed"])
                self.assertFalse(request_path(dotnet_client.ipc_dir, health_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, health_request_id).exists())

                review_request_id = "dotnet-live-review"
                review = dotnet_client.review(
                    expected_full_path,
                    [handle],
                    request_id=review_request_id,
                )
                self.assertTrue(review["success"])
                self.assertEqual(expected_full_path, review["drawing_full_path"])
                self.assertFalse(review["changed"])
                self.assertEqual([], review["errors"])
                self.assertFalse(request_path(dotnet_client.ipc_dir, review_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, review_request_id).exists())

                dbmod_before_values = legacy_client.drawing_get_variables(["DBMOD"])
                self.assertIn("DBMOD", dbmod_before_values)
                dbmod_before = dbmod_before_values["DBMOD"]
                bom_request_id = "dotnet-live-mechanical-bom"
                bom = dotnet_client.mechanical_bom(
                    expected_full_path,
                    request_id=bom_request_id,
                )
                dbmod_after_values = legacy_client.drawing_get_variables(["DBMOD"])
                self.assertIn("DBMOD", dbmod_after_values)
                dbmod_after = dbmod_after_values["DBMOD"]
                self.assertTrue(bom["success"])
                self.assertEqual(dbmod_before, dbmod_after)
                self.assertEqual(expected_full_path, bom["drawing_full_path"])
                self.assertFalse(bom["changed"])
                self.assertEqual([], bom["errors"])
                self.assertEqual(2, bom["payload"]["component_count"])
                components = bom["payload"]["components"]
                self.assertEqual(
                    ["COMP_EMPTY", "COMP_FRAME"],
                    sorted(component["block_name"] for component in components),
                )
                self.assertNotIn(
                    "COMP_NESTED",
                    [component["block_name"] for component in components],
                )
                frame_component = next(
                    component for component in components if component["block_name"] == "COMP_FRAME"
                )
                self.assertEqual(
                    [{"tag": "PART_ID", "value": "FRAME-001"}],
                    frame_component["attributes"],
                )
                empty_component = next(
                    component for component in components if component["block_name"] == "COMP_EMPTY"
                )
                self.assertEqual([], empty_component["attributes"])
                self.assertEqual(
                    [component["handle"] for component in components],
                    bom["entity_handles"],
                )
                self.assertFalse(request_path(dotnet_client.ipc_dir, bom_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, bom_request_id).exists())

                close_request_id = "dotnet-live-close"
                close = dotnet_client.close_disposable(
                    expected_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=close_request_id,
                )
                self.assertTrue(close["success"])
                self.assertEqual(expected_full_path, close["drawing_full_path"])
                self.assertFalse(close["changed"])
                self.assertTrue(close["payload"]["closed_without_saving"])
                mark_closed()
                self.assertFalse(request_path(dotnet_client.ipc_dir, close_request_id).exists())
                self.assertFalse(result_path(dotnet_client.ipc_dir, close_request_id).exists())
        finally:
            _cleanup_disposable_fixture_directory(
                test_directory,
                drawing_path,
                original_sha256=original_sha256,
            )


@unittest.skipUnless(
    _s2c_live_prerequisites_available(),
    "requires CAD_AGENT_S2C_LIVE=1, CAD_AGENT_FILE_IPC=1, AutoCAD HWND, "
    "LISP path, CAD_AGENT_DOTNET_IPC_DIR, and CAD_AGENT_LEAN_DISPOSABLE_DWG",
)
@pytest.mark.autocad_mechanical
class NativeRenderS2CLiveTests(unittest.TestCase):
    def _run_refusal_probe(self, profile: str) -> None:
        """Run against an operator-prepared isolated AutoCAD profile.

        missing-device must hide the approved PNG PC3 from the profile.
        missing-media must expose that PC3 without the approved 2480x3508
        pixel media. The test never changes shared AutoCAD configuration.
        """

        drawing = Path(os.environ["CAD_AGENT_LEAN_DISPOSABLE_DWG"]).resolve()
        self.assertTrue(drawing.is_file(), f"Missing disposable drawing: {drawing}")
        original_sha256 = _sha256(drawing)
        expected_full_path = normalize_windows_absolute_path(str(drawing))
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        legacy_client = FileIPCLiveMCPClient(
            trigger=make_windows_dispatch_trigger(hwnd),
            raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
            bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
        )
        dotnet_client = DotNetIPCClient(
            ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
            trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            timeout_s=30.0,
        )
        request_id = f"s2c-live-{profile}-{time.time_ns()}"
        request_directory = dotnet_client.ipc_dir / "native-render" / request_id
        expected_error_code = {
            "missing-device": "NATIVE_RENDER_DEVICE_UNAVAILABLE",
            "missing-media": "NATIVE_RENDER_MEDIA_UNAVAILABLE",
        }[profile]

        try:
            with _disposable_drawing_cleanup(dotnet_client, str(drawing)) as mark_closed:
                legacy_client.drawing_open(str(drawing))
                state_before = legacy_client.drawing_get_variables(
                    ["DBMOD", "CTAB", "BACKGROUNDPLOT"]
                )
                with self.assertRaises(DotNetIPCResultError) as refusal_error:
                    dotnet_client.native_render_evidence(
                        expected_full_path,
                        _s2c_request(
                            expected_full_path,
                            original_sha256,
                            request_id,
                            artifact_kind="PNG",
                        ),
                    )
                result = refusal_error.exception.result
                self.assertIsNotNone(result)
                assert result is not None
                self.assertFalse(result["success"])
                self.assertFalse(result["changed"])
                self.assertEqual([], result["entity_handles"])
                self.assertEqual({}, result["payload"])
                self.assertTrue(result["errors"])
                self.assertTrue(
                    any(expected_error_code in error for error in result["errors"]),
                    result["errors"],
                )
                self.assertEqual(
                    state_before,
                    legacy_client.drawing_get_variables(
                        ["DBMOD", "CTAB", "BACKGROUNDPLOT"]
                    ),
                )
                self.assertEqual(original_sha256, _sha256(drawing))
                self.assertTrue(request_directory.is_dir())
                self.assertFalse((request_directory / "artifact.png").exists())

                close = dotnet_client.close_disposable(
                    expected_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=f"s2c-live-{profile}-close-{time.time_ns()}",
                )
                self.assertTrue(close["success"])
                self.assertFalse(close["changed"])
                mark_closed()
        finally:
            shutil.rmtree(request_directory, ignore_errors=True)
            self.assertEqual(original_sha256, _sha256(drawing))

    @unittest.skipUnless(
        _s2c_refusal_probe_prerequisites_available("missing-device"),
        "requires an isolated AutoCAD profile with the approved PNG device absent "
        "and CAD_AGENT_S2C_NEGATIVE_PROFILE=missing-device",
    )
    def test_s2c_missing_device_refuses_without_artifact(self) -> None:
        self._run_refusal_probe("missing-device")

    @unittest.skipUnless(
        _s2c_refusal_probe_prerequisites_available("missing-media"),
        "requires an isolated AutoCAD profile with no approved PNG pixel media "
        "and CAD_AGENT_S2C_NEGATIVE_PROFILE=missing-media",
    )
    def test_s2c_missing_media_refuses_without_artifact(self) -> None:
        self._run_refusal_probe("missing-media")

    def test_s2c_png_pdf_and_fail_closed_probes_are_read_only(self) -> None:
        from PIL import Image
        from pypdf import PdfReader

        drawing = Path(os.environ["CAD_AGENT_LEAN_DISPOSABLE_DWG"]).resolve()
        self.assertTrue(drawing.is_file(), f"Missing disposable drawing: {drawing}")
        original_sha256 = _sha256(drawing)
        expected_full_path = normalize_windows_absolute_path(str(drawing))
        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        legacy_client = FileIPCLiveMCPClient(
            trigger=make_windows_dispatch_trigger(hwnd),
            raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
            bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
        )
        dotnet_client = DotNetIPCClient(
            ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
            trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            timeout_s=30.0,
        )

        def session_state() -> dict[str, object]:
            values = legacy_client.drawing_get_variables(
                ["DBMOD", "CTAB", "BACKGROUNDPLOT"]
            )
            return {name: values.get(name) for name in ("DBMOD", "CTAB", "BACKGROUNDPLOT")}

        def artifact_path(relative_path: str) -> Path:
            return dotnet_client.ipc_dir.joinpath(*relative_path.split("/"))

        def assert_failed(
            result_error: DotNetIPCResultError,
            *,
            request_id: str,
            expected_error_code: str,
            state_before: dict[str, object],
            drawing_hash_before: str,
            artifact_kind: str = "PNG",
            artifact_must_exist: bool = False,
        ) -> None:
            self.assertIsNotNone(result_error.result)
            result = result_error.result
            assert result is not None
            self.assertFalse(result["success"])
            self.assertFalse(result["changed"])
            self.assertEqual([], result["entity_handles"])
            self.assertEqual({}, result["payload"])
            self.assertTrue(result["errors"])
            self.assertTrue(
                any(expected_error_code in error for error in result["errors"]),
                result["errors"],
            )
            self.assertEqual(state_before, session_state())
            self.assertEqual(drawing_hash_before, _sha256(drawing))
            final_path = (
                dotnet_client.ipc_dir
                / "native-render"
                / request_id
                / f"artifact.{artifact_kind.lower()}"
            )
            self.assertEqual(artifact_must_exist, final_path.is_file())

        try:
            with _disposable_drawing_cleanup(dotnet_client, str(drawing)) as mark_closed:
                legacy_client.drawing_open(str(drawing))

                for artifact_kind in ("PNG", "PDF"):
                    request_id = f"s2c-live-{artifact_kind.lower()}-{time.time_ns()}"
                    request = _s2c_request(
                        expected_full_path,
                        original_sha256,
                        request_id,
                        artifact_kind=artifact_kind,
                    )
                    state_before = session_state()
                    result = dotnet_client.native_render_evidence(
                        expected_full_path,
                        request,
                    )
                    state_after = session_state()

                    self.assertTrue(result["success"])
                    self.assertFalse(result["changed"])
                    self.assertEqual([], result["entity_handles"])
                    self.assertEqual([], result["errors"])
                    self.assertNotIn("NATIVE_RENDER_NOT_IMPLEMENTED", result["errors"])
                    self.assertEqual(expected_full_path, result["drawing_full_path"])
                    self.assertEqual(state_before, state_after)
                    self.assertEqual(original_sha256, _sha256(drawing))
                    self.assertEqual(
                        state_before["DBMOD"],
                        result["payload"]["dbmod_before"],
                    )
                    self.assertEqual(
                        state_before["DBMOD"],
                        result["payload"]["dbmod_after"],
                    )

                    artifact = result["payload"]["artifact"]
                    expected_suffix = artifact_kind.lower()
                    self.assertEqual(
                        f"native-render/{request_id}/artifact.{expected_suffix}",
                        artifact["relative_path"],
                    )
                    final_path = artifact_path(artifact["relative_path"])
                    self.assertTrue(final_path.is_file())
                    final_bytes = final_path.read_bytes()
                    self.assertEqual(
                        hashlib.sha256(final_bytes).hexdigest(),
                        artifact["sha256"],
                    )
                    self.assertGreater(len(final_bytes), 0)

                    if artifact_kind == "PNG":
                        with Image.open(final_path) as image:
                            self.assertIn(
                                (image.width, image.height),
                                {(2480, 3508), (3508, 2480)},
                            )
                            self.assertEqual(image.width, artifact["width"])
                            self.assertEqual(image.height, artifact["height"])
                            image.verify()
                        with Image.open(final_path) as image:
                            image.load()
                            self.assertIn(
                                (image.width, image.height),
                                {(2480, 3508), (3508, 2480)},
                            )
                    else:
                        self.assertEqual(1, artifact["page_count"])
                        self.assertEqual(1, len(PdfReader(str(final_path)).pages))

                    with self.assertRaises(DotNetIPCResultError) as duplicate_error:
                        duplicate_state_before = session_state()
                        duplicate_hash_before = _sha256(drawing)
                        dotnet_client.native_render_evidence(
                            expected_full_path,
                            request,
                        )
                    assert_failed(
                        duplicate_error.exception,
                        request_id=request_id,
                        expected_error_code="NATIVE_RENDER_DUPLICATE_REQUEST",
                        state_before=duplicate_state_before,
                        drawing_hash_before=duplicate_hash_before,
                        artifact_kind=artifact_kind,
                        artifact_must_exist=True,
                    )
                    shutil.rmtree(final_path.parent)

                missing_layout_id = f"s2c-live-missing-layout-{time.time_ns()}"
                missing_layout_request = _s2c_request(
                    expected_full_path,
                    original_sha256,
                    missing_layout_id,
                    layout_name="S2C_LAYOUT_DOES_NOT_EXIST",
                )
                missing_layout_state_before = session_state()
                missing_layout_hash_before = _sha256(drawing)
                with self.assertRaises(DotNetIPCResultError) as missing_layout_error:
                    dotnet_client.native_render_evidence(
                        expected_full_path,
                        missing_layout_request,
                    )
                assert_failed(
                    missing_layout_error.exception,
                    request_id=missing_layout_id,
                    expected_error_code="NATIVE_RENDER_LAYOUT_NOT_FOUND",
                    state_before=missing_layout_state_before,
                    drawing_hash_before=missing_layout_hash_before,
                )
                shutil.rmtree(
                    dotnet_client.ipc_dir / "native-render" / missing_layout_id,
                    ignore_errors=True,
                )

                unsupported_id = f"s2c-live-unsupported-profile-{time.time_ns()}"
                unsupported_request = _s2c_request(
                    expected_full_path,
                    original_sha256,
                    unsupported_id,
                    render_options={
                        "background": "white",
                        "dpi": 600,
                        "fit_to_paper": True,
                        "paper_size": "A4",
                        "plot_style": "monochrome.ctb",
                    },
                )
                unsupported_state_before = session_state()
                unsupported_hash_before = _sha256(drawing)
                with self.assertRaises(DotNetIPCResultError) as unsupported_error:
                    dotnet_client.native_render_evidence(
                        expected_full_path,
                        unsupported_request,
                    )
                assert_failed(
                    unsupported_error.exception,
                    request_id=unsupported_id,
                    expected_error_code="NATIVE_RENDER_UNSUPPORTED_PROFILE",
                    state_before=unsupported_state_before,
                    drawing_hash_before=unsupported_hash_before,
                )
                shutil.rmtree(
                    dotnet_client.ipc_dir / "native-render" / unsupported_id,
                    ignore_errors=True,
                )

                close = dotnet_client.close_disposable(
                    expected_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=f"s2c-live-close-{time.time_ns()}",
                )
                self.assertTrue(close["success"])
                self.assertFalse(close["changed"])
                self.assertTrue(close["payload"]["closed_without_saving"])
                mark_closed()
        finally:
            self.assertEqual(original_sha256, _sha256(drawing))
