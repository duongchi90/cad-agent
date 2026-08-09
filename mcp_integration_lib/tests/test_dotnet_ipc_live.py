"""Opt-in disposable AutoCAD Mechanical smoke test for the .NET IPC path."""

import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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


def _normalized_live_ipc_root(value: str | None) -> str | None:
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


def _live_prerequisites_available() -> bool:
    file_ipc_root = _normalized_live_ipc_root(os.getenv("CAD_AGENT_FILE_IPC_DIR"))
    dotnet_ipc_root = _normalized_live_ipc_root(os.getenv("CAD_AGENT_DOTNET_IPC_DIR"))
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and file_ipc_root is not None
        and file_ipc_root == dotnet_ipc_root
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


def _s3b_live_prerequisites_available() -> bool:
    return _live_prerequisites_available() and all(
        bool(os.getenv(name))
        for name in (
            "CAD_AGENT_DOTNET_IPC_DIR",
            "CAD_AGENT_S3B_FIXTURE_JSON",
            "CAD_AGENT_S3B_CANDIDATE_DWG",
            "CAD_AGENT_S3B_DISPOSABLE_ROOT",
            "CAD_AGENT_S3B_ACCEPTED_DWG_PATH",
            "CAD_AGENT_S3B_ACCEPTED_DWG_SHA256",
            "CAD_AGENT_S3B_EXACT_BASE_SOURCE_PATH",
            "CAD_AGENT_S3B_EXACT_BASE_SOURCE_SHA256",
            "CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION",
        )
    )


class LiveIPCRootPrerequisiteTests(unittest.TestCase):
    def _available(
        self,
        *,
        enable: str = "1",
        file_ipc_dir: str | None = r"C:\cad-agent\session\ipc",
        dotnet_ipc_dir: str | None = r"C:\cad-agent\session\ipc",
    ) -> bool:
        environment = {
            "CAD_AGENT_FILE_IPC": enable,
            "CAD_AGENT_AUTOCAD_HWND": "1001",
            "CAD_AGENT_AUTOCAD_LISP_PATH": r"C:\cad-agent\mcp_dispatch.lsp",
        }
        if file_ipc_dir is not None:
            environment["CAD_AGENT_FILE_IPC_DIR"] = file_ipc_dir
        if dotnet_ipc_dir is not None:
            environment["CAD_AGENT_DOTNET_IPC_DIR"] = dotnet_ipc_dir
        with patch.dict(os.environ, environment, clear=True):
            return _live_prerequisites_available()

    def test_file_ipc_enable_flag_remains_boolean_and_requires_explicit_dir(self) -> None:
        self.assertTrue(self._available())
        self.assertFalse(self._available(file_ipc_dir=None))
        self.assertFalse(self._available(enable=r"C:\cad-agent\session\ipc"))

    def test_file_and_dotnet_ipc_roots_must_match_after_normalization(self) -> None:
        self.assertTrue(
            self._available(
                file_ipc_dir=r"C:/cad-agent/session/ipc",
                dotnet_ipc_dir=r"C:\cad-agent\session\ipc",
            )
        )
        self.assertFalse(
            self._available(dotnet_ipc_dir=r"C:\cad-agent\other-session\ipc")
        )

    def test_ambiguous_nonlocal_or_alias_file_ipc_roots_fail_prerequisites(self) -> None:
        for invalid in (
            "",
            r"relative\ipc",
            r"C:drive-relative\ipc",
            r"\\server\share\ipc",
            r"C:\cad-agent\session\..\escape",
        ):
            with self.subTest(root=invalid):
                self.assertFalse(self._available(file_ipc_dir=invalid))


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
    "requires CAD_AGENT_FILE_IPC=1, CAD_AGENT_FILE_IPC_DIR, CAD_AGENT_DOTNET_IPC_DIR, "
    "CAD_AGENT_AUTOCAD_HWND, and CAD_AGENT_AUTOCAD_LISP_PATH",
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
                ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
                trigger=make_windows_dispatch_trigger(hwnd),
                raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
                bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
            )
            dotnet_client = DotNetIPCClient(
                ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
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
    "requires CAD_AGENT_S2C_LIVE=1, CAD_AGENT_FILE_IPC=1, CAD_AGENT_FILE_IPC_DIR, "
    "AutoCAD HWND, LISP path, CAD_AGENT_DOTNET_IPC_DIR, and CAD_AGENT_LEAN_DISPOSABLE_DWG",
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
            ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
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
            ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
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


@unittest.skipUnless(
    _s3b_live_prerequisites_available(),
    "requires AutoCAD File IPC, CAD_AGENT_FILE_IPC_DIR, CAD_AGENT_DOTNET_IPC_DIR, "
    "an approved S3B fixture, a disposable candidate DWG, and server-owned S3B configuration",
)
@pytest.mark.autocad_mechanical
class ExactBaseXrefS3BLiveTests(unittest.TestCase):
    def test_s3b_live_extraction_is_fresh_read_only_preflight_and_candidate_only(self) -> None:
        fixture_path = Path(os.environ["CAD_AGENT_S3B_FIXTURE_JSON"]).resolve()
        if not fixture_path.is_file():
            self.skipTest(f"Missing approved S3B fixture: {fixture_path}")

        try:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.skipTest(f"S3B fixture is unavailable or invalid: {exc}")
        if not isinstance(fixture, dict):
            self.skipTest("S3B fixture must be a JSON object")

        inspection = fixture.get("inspection")
        extraction_plan = fixture.get("plan")
        if not isinstance(inspection, dict) or not isinstance(extraction_plan, dict):
            self.skipTest("S3B fixture must contain inspection and plan objects")

        approval = extraction_plan.get("approval")
        if not isinstance(approval, dict) or approval.get("status") != "APPROVED":
            self.skipTest("S3B live extraction requires an operator-approved plan fixture")

        root = Path(os.environ["CAD_AGENT_S3B_DISPOSABLE_ROOT"]).resolve()
        source = Path(os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_PATH"]).resolve()
        accepted = Path(os.environ["CAD_AGENT_S3B_ACCEPTED_DWG_PATH"]).resolve()
        candidate = Path(os.environ["CAD_AGENT_S3B_CANDIDATE_DWG"]).resolve()
        for label, path in (
            ("disposable root", root),
            ("exact-base source", source),
            ("accepted DWG", accepted),
            ("candidate DWG", candidate),
        ):
            if label == "disposable root":
                available = path.is_dir()
            else:
                available = path.is_file()
            if not available:
                self.skipTest(f"Missing S3B {label}: {path}")

        if not candidate.is_relative_to(root):
            self.skipTest("S3B candidate DWG must be under the server-owned disposable root")

        configured_source_hash = os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_SHA256"]
        configured_accepted_hash = os.environ["CAD_AGENT_S3B_ACCEPTED_DWG_SHA256"]
        source_hash_before = _sha256(source)
        accepted_hash_before = _sha256(accepted)
        candidate_hash_before = _sha256(candidate)
        self.assertEqual(configured_source_hash, source_hash_before)
        self.assertEqual(configured_accepted_hash, accepted_hash_before)

        plan_source = extraction_plan.get("base_source")
        plan_target_hash = extraction_plan.get("target_drawing_sha256")
        inspection_target_hash = inspection.get("target_drawing_sha256")
        if not isinstance(plan_source, dict):
            self.skipTest("S3B plan fixture has no base_source binding")
        if plan_source.get("sha256") != configured_source_hash:
            self.skipTest("S3B plan source hash is not bound to server configuration")
        if plan_target_hash != candidate_hash_before:
            self.skipTest("S3B plan target hash is not bound to the disposable candidate")
        if inspection_target_hash != accepted_hash_before:
            self.skipTest("S3B inspection target hash is not bound to the accepted DWG")

        request_id = f"s3b-live-{time.time_ns()}"
        candidate_output = root / f"cadagent-s3b-output-{request_id}.dwg"
        self.assertFalse(candidate_output.exists())

        hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
        legacy_client = FileIPCLiveMCPClient(
            ipc_dir=os.environ["CAD_AGENT_FILE_IPC_DIR"],
            trigger=make_windows_dispatch_trigger(hwnd),
            raw_lisp_trigger=make_windows_lisp_trigger(hwnd),
            bootstrap_lisp_path=os.environ["CAD_AGENT_AUTOCAD_LISP_PATH"],
        )
        dotnet_client = DotNetIPCClient(
            ipc_dir=os.environ["CAD_AGENT_DOTNET_IPC_DIR"],
            trigger=make_windows_dotnet_dispatch_trigger(hwnd),
            timeout_s=45.0,
        )
        accepted_full_path = normalize_windows_absolute_path(str(accepted))
        candidate_full_path = normalize_windows_absolute_path(str(candidate))
        candidate_output_hash: str | None = None
        accepted_open = False

        try:
            legacy_client.drawing_open(str(accepted))
            accepted_open = True
            accepted_state_before = legacy_client.drawing_get_variables(
                ["DBMOD", "CTAB", "CVPORT", "UCSNAME"]
            )
            inspection_result = dotnet_client.exact_base_xref_inspection(
                accepted_full_path,
                drawing_sha256=accepted_hash_before,
                source_full_path=str(source),
                inspection=inspection,
                source_revision=os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION"],
                request_id=f"{request_id}-inspection",
            )
            inspection_payload = inspection_result["payload"]
            self.assertTrue(inspection_result["success"])
            self.assertFalse(inspection_result["changed"])
            self.assertEqual([], inspection_result["entity_handles"])
            self.assertEqual(accepted_full_path, inspection_result["drawing_full_path"])
            self.assertEqual("exact-base-xref-inspection-1.0", inspection_payload["schema_version"])
            self.assertEqual(inspection_result["request_id"], inspection_payload["request_id"])
            self.assertEqual(inspection["run_id"], inspection_payload["run_id"])
            self.assertEqual(accepted_hash_before, inspection_payload["target_drawing_sha256"])
            self.assertEqual(configured_source_hash, inspection_payload["base_source"]["sha256"])
            self.assertEqual(accepted_hash_before, inspection_payload["target_drawing_sha256"])
            self.assertEqual(inspection_payload["base_source"]["sha256"], _sha256(source))
            self.assertFalse(inspection_payload["changed"])
            self.assertEqual(inspection_payload["dbmod_before"], inspection_payload["dbmod_after"])
            self.assertTrue(inspection_payload["eligible"])
            self.assertTrue(inspection_payload["xref"]["read_only"])
            self.assertEqual("INSPECTED", inspection_payload["xref"]["status"])
            self.assertTrue(all(item["status"] == "PASS" for item in inspection_payload["identity_observations"]))
            self.assertTrue(all(item["status"] == "PASS" for item in inspection_payload["critical_dimensions"]))
            self.assertTrue(all(item["component_type"] == "BLOCK" for item in inspection_payload["components"]))
            self.assertTrue(all(item["provenance"] == "REUSED_FROM_BASE_CAD" for item in inspection_payload["components"]))
            accepted_state_after = legacy_client.drawing_get_variables(
                ["DBMOD", "CTAB", "CVPORT", "UCSNAME"]
            )
            self.assertEqual(accepted_state_before, accepted_state_after)
            self.assertEqual(source_hash_before, _sha256(source))
            self.assertEqual(accepted_hash_before, _sha256(accepted))

            with _disposable_drawing_cleanup(dotnet_client, str(candidate)) as mark_closed:
                legacy_client.drawing_open(str(candidate))
                state_before = legacy_client.drawing_get_variables(
                    ["DBMOD", "CTAB", "CVPORT", "UCSNAME"]
                )
                result = dotnet_client.exact_base_xref_extraction(
                    candidate_full_path,
                    drawing_sha256=candidate_hash_before,
                    source_full_path=str(source),
                    inspection=inspection,
                    extraction_plan=extraction_plan,
                    candidate_output_path=str(candidate_output),
                    approval=approval,
                    source_revision=os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION"],
                    request_id=request_id,
                )
                state_after = legacy_client.drawing_get_variables(
                    ["DBMOD", "CTAB", "CVPORT", "UCSNAME"]
                )
                payload = result["payload"]
                self.assertTrue(result["success"])
                self.assertTrue(result["changed"])
                self.assertEqual(candidate_full_path, result["drawing_full_path"])
                self.assertEqual(sorted(result["entity_handles"]), result["entity_handles"])
                self.assertEqual(
                    len(result["entity_handles"]),
                    len(set(result["entity_handles"])),
                )
                self.assertTrue(payload["accepted_target_overwrite"] is False)
                self.assertTrue(payload["candidate_changed_during_operation"])
                self.assertTrue(payload["save_performed"])
                self.assertFalse(payload["source_mutated"])
                self.assertFalse(payload["source_saved"])
                self.assertEqual(candidate_full_path, payload["candidate_input_path"])
                self.assertEqual(candidate_hash_before, payload["candidate_input_sha256"])
                self.assertEqual(configured_source_hash, payload["source_sha256_before"])
                self.assertEqual(configured_source_hash, payload["source_sha256_after"])
                self.assertEqual(
                    os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION"],
                    payload["source_revision"],
                )
                self.assertEqual(state_before, state_after)
                self.assertEqual(source_hash_before, _sha256(source))
                self.assertEqual(accepted_hash_before, _sha256(accepted))
                self.assertEqual(candidate_hash_before, _sha256(candidate))

                live_preflight = payload["live_preflight"]
                self.assertTrue(live_preflight["eligible"])
                self.assertEqual(
                    live_preflight["dbmod_before"],
                    live_preflight["dbmod_after"],
                )
                self.assertEqual(candidate_hash_before, live_preflight["target_drawing_sha256"])
                self.assertEqual(configured_source_hash, live_preflight["source_sha256"])
                self.assertTrue(live_preflight["xref"]["read_only"])
                self.assertEqual("INSPECTED", live_preflight["xref"]["status"])

                expected_components = {
                    component["source_handle"]: component
                    for component in extraction_plan["components"]
                }
                actual_components = {
                    component["source_handle"]: component
                    for component in payload["components"]
                }
                self.assertEqual(set(expected_components), set(actual_components))
                for source_handle, expected in expected_components.items():
                    actual = actual_components[source_handle]
                    self.assertEqual(expected["source_block"], actual["source_block"])
                    self.assertEqual(expected["source_layer"], actual["source_layer"])
                    self.assertEqual(expected["provenance"], actual["provenance"])
                    self.assertEqual(
                        os.environ["CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION"],
                        actual["source_revision"],
                    )
                    self.assertEqual(configured_source_hash, actual["source_sha256"])

                mapping = payload["source_handle_to_candidate_handle"]
                self.assertEqual(
                    set(expected_components),
                    {item["source_handle"] for item in mapping},
                )
                candidate_output_hash = payload["candidate_output_sha256"]
                self.assertTrue(candidate_output.is_file())
                self.assertEqual(candidate_output_hash, _sha256(candidate_output))

                close = dotnet_client.close_disposable(
                    candidate_full_path,
                    disposable=True,
                    save_changes=False,
                    request_id=f"{request_id}-close",
                )
                self.assertTrue(close["success"])
                self.assertFalse(close["changed"])
                self.assertTrue(close["payload"]["closed_without_saving"])
                mark_closed()
        finally:
            if accepted_open:
                legacy_client.drawing_close(save_changes=False)
            if candidate_output_hash is not None and candidate_output.is_file():
                self.assertEqual(candidate_output_hash, _sha256(candidate_output))
                candidate_output.unlink()
            self.assertFalse(candidate_output.exists())