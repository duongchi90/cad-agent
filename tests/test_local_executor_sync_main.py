from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SYNC_ACTION = "SYNC_MAIN_STATE_CHECK"
CANONICAL_ORIGIN = "https://github.com/duongchi90/cad-agent"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "local-executor.ps1"
EXPECTED_BRANCH = "main"


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class LocalExecutorSyncMainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = (
            os.environ.get("CAD_AGENT_POWERSHELL")
            or shutil.which("pwsh")
            or shutil.which("powershell")
            or r"C:\Program Files\PowerShell\7\pwsh.exe"
        )
        if not Path(cls.powershell).exists() and shutil.which(cls.powershell) is None:
            raise AssertionError("PowerShell is required for sync-main executor tests")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="cad-agent-sync-main-")
        self.root = Path(self.temp_dir.name)
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        subprocess.run(
            ["git", "init", "-b", EXPECTED_BRANCH, str(self.seed)],
            check=True,
            capture_output=True,
        )
        git("config", "user.email", "tests@example.invalid", cwd=self.seed)
        git("config", "user.name", "Local Executor Tests", cwd=self.seed)
        (self.seed / "state.txt").write_text("base\n", encoding="utf-8")
        git("add", "state.txt", cwd=self.seed)
        git("commit", "-m", "base", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "origin", EXPECTED_BRANCH, cwd=self.seed)
        self.base_sha = git("rev-parse", "HEAD", cwd=self.seed)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def clone_managed_repo(self) -> Path:
        managed = self.root / "managed"
        git("clone", "--branch", EXPECTED_BRANCH, str(self.remote), str(managed), cwd=self.root)
        git("config", "user.email", "tests@example.invalid", cwd=managed)
        git("config", "user.name", "Local Executor Tests", cwd=managed)
        git("remote", "set-url", "origin", CANONICAL_ORIGIN, cwd=managed)
        git(
            "config",
            "url." + self.remote.as_uri() + ".insteadOf",
            CANONICAL_ORIGIN,
            cwd=managed,
        )
        return managed

    def advance_remote(self, content: str) -> str:
        (self.seed / "state.txt").write_text(content, encoding="utf-8")
        git("add", "state.txt", cwd=self.seed)
        git("commit", "-m", "advance", cwd=self.seed)
        git("push", "origin", EXPECTED_BRANCH, cwd=self.seed)
        return git("rev-parse", "HEAD", cwd=self.seed)

    def run_sync(self, managed: Path, expected_sha: str) -> subprocess.CompletedProcess[str]:
        artifacts = self.root / "artifacts" / managed.name
        artifacts.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-Action",
                SYNC_ACTION,
                "-RepoPath",
                str(managed),
                "-ExpectedBranch",
                EXPECTED_BRANCH,
                "-ExpectedSha",
                expected_sha,
                "-ArtifactsDir",
                str(artifacts),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def output(result: subprocess.CompletedProcess[str]) -> str:
        return result.stdout + result.stderr

    def test_ancestor_remote_main_fast_forwards_and_passes_state_check(self) -> None:
        managed = self.clone_managed_repo()
        expected_sha = self.advance_remote("remote\n")

        result = self.run_sync(managed, expected_sha)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(git("rev-parse", "HEAD", cwd=managed), expected_sha)
        self.assertIn("LOCAL_EXECUTOR_RESULT=PASS", self.output(result))

    def test_already_current_remote_main_is_a_noop(self) -> None:
        managed = self.clone_managed_repo()
        result = self.run_sync(managed, self.base_sha)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(git("rev-parse", "HEAD", cwd=managed), self.base_sha)
        self.assertIn("LOCAL_EXECUTOR_RESULT=PASS", self.output(result))

    def test_dirty_managed_repo_fails_closed(self) -> None:
        managed = self.clone_managed_repo()
        (managed / "untracked.txt").write_text("dirty\n", encoding="utf-8")

        result = self.run_sync(managed, self.base_sha)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("LOCAL_WORKTREE_DIRTY", self.output(result))

    def test_foreign_origin_fails_closed(self) -> None:
        managed = self.clone_managed_repo()
        git("remote", "set-url", "origin", str(self.root / "foreign.git"), cwd=managed)

        result = self.run_sync(managed, self.base_sha)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("ORIGIN_URL_MISMATCH", self.output(result))

    def test_ahead_managed_repo_fails_closed(self) -> None:
        managed = self.clone_managed_repo()
        (managed / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=managed)
        git("commit", "-m", "local ahead", cwd=managed)

        result = self.run_sync(managed, self.base_sha)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("LOCAL_HEAD_NOT_ANCESTOR_OF_REMOTE_MAIN", self.output(result))

    def test_diverged_managed_repo_fails_closed(self) -> None:
        managed = self.clone_managed_repo()
        (managed / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=managed)
        git("commit", "-m", "local diverged", cwd=managed)
        expected_sha = self.advance_remote("remote\n")

        result = self.run_sync(managed, expected_sha)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("LOCAL_HEAD_NOT_ANCESTOR_OF_REMOTE_MAIN", self.output(result))

    def test_fetched_remote_sha_must_match_expected_sha(self) -> None:
        managed = self.clone_managed_repo()
        actual_remote_sha = self.advance_remote("remote\n")
        self.assertNotEqual(actual_remote_sha, self.base_sha)

        result = self.run_sync(managed, self.base_sha)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("REMOTE_MAIN_SHA_MISMATCH", self.output(result))

    def test_sync_action_has_no_history_rewrite_or_force_operations(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("git reset", "git rebase", "git cherry-pick", "git push --force"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
