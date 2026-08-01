from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dotnet_ipc.paths import (
    DEFAULT_IPC_DIR,
    REQUEST_PREFIX,
    RESULT_PREFIX,
    cleanup_request_files,
    get_ipc_dir,
    normalize_request_id,
    normalize_windows_absolute_path,
    request_filename,
    request_path,
    result_filename,
    result_path,
)


class PathUtilityTests(unittest.TestCase):
    def test_request_and_result_names_use_the_new_prefix(self) -> None:
        request_id = "health-20260801-001"

        self.assertEqual(
            f"{REQUEST_PREFIX}{request_id}.json",
            request_filename(request_id),
        )
        self.assertEqual(
            f"{RESULT_PREFIX}{request_id}.json",
            result_filename(request_id),
        )

    def test_request_ids_are_safe_for_file_names(self) -> None:
        self.assertEqual("abc-123_X", normalize_request_id("abc-123_X"))

        for invalid in ("", " ", "../escape", "bad.id", "a\\b", "a" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_request_id(invalid)

    def test_paths_are_scoped_to_the_ipc_directory(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request = request_path(ipc_dir, "one")
            result = result_path(ipc_dir, "one")

            self.assertEqual(ipc_dir / "cadagent_dotnet_request_one.json", request)
            self.assertEqual(ipc_dir / "cadagent_dotnet_result_one.json", result)

    def test_normalizes_absolute_windows_paths_and_rejects_relative_paths(self) -> None:
        self.assertEqual(
            r"C:\drawings\sample.dwg",
            normalize_windows_absolute_path(r"C:/drawings/parts/../sample.dwg"),
        )
        self.assertEqual(
            r"\\server\share\sample.dwg",
            normalize_windows_absolute_path(r"\\server\share\folder\..\sample.dwg"),
        )

        for invalid in ("sample.dwg", r"C:sample.dwg", "", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_windows_absolute_path(invalid)

    def test_ipc_directory_env_override_is_resolved(self) -> None:
        with TemporaryDirectory() as temporary:
            previous = os.environ.get("CAD_AGENT_DOTNET_IPC_DIR")
            try:
                os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = temporary
                self.assertEqual(Path(temporary).resolve(), get_ipc_dir())
            finally:
                if previous is None:
                    os.environ.pop("CAD_AGENT_DOTNET_IPC_DIR", None)
                else:
                    os.environ["CAD_AGENT_DOTNET_IPC_DIR"] = previous

        self.assertEqual(Path(DEFAULT_IPC_DIR), Path(r"C:\temp"))

    def test_cleanup_removes_only_the_requested_pair(self) -> None:
        with TemporaryDirectory() as temporary:
            ipc_dir = Path(temporary)
            request_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            result_path(ipc_dir, "one").write_text("one", encoding="utf-8")
            request_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            result_path(ipc_dir, "two").write_text("two", encoding="utf-8")
            old_dispatcher = ipc_dir / "autocad_mcp_result_legacy.json"
            old_dispatcher.write_text("legacy", encoding="utf-8")

            cleanup_request_files(ipc_dir, "one")

            self.assertFalse(request_path(ipc_dir, "one").exists())
            self.assertFalse(result_path(ipc_dir, "one").exists())
            self.assertTrue(request_path(ipc_dir, "two").exists())
            self.assertTrue(result_path(ipc_dir, "two").exists())
            self.assertTrue(old_dispatcher.exists())


if __name__ == "__main__":
    unittest.main()
