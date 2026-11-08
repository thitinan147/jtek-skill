import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-work-queue" / "scripts" / "gate.py"
LANDED_PATH = REPO / "skills" / "jt-review-work" / "scripts" / "landed.py"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


class LandedParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "card-loop" / "backlog").mkdir(parents=True)
        (self.repo / "card-loop" / "board.md").write_text(
            "# Board - app\n\nqueue: main\n\n## first\n\n- [ ] **12** item (feat) review: local\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "docs: init board")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "feat: work")
        git(self.repo, "checkout", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _env_with_gh(self, name: str, script: str | None = None) -> dict[str, str]:
        bin_dir = self.repo / "card-loop" / name
        bin_dir.mkdir(parents=True, exist_ok=True)
        real_git = shutil.which("git")
        assert real_git is not None
        git_link = bin_dir / "git"
        if not git_link.exists():
            git_link.symlink_to(real_git)
        if script is not None:
            gh = bin_dir / "gh"
            gh.write_text(script, encoding="utf-8")
            gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir)
        env["GIT_TERMINAL_PROMPT"] = "0"
        return env

    def _assert_parity(self, env: dict[str, str], card_id: str = "12") -> subprocess.CompletedProcess[str]:
        res_gate = subprocess.run(
            [sys.executable, str(GATE_PATH), "landed", "--root", str(self.repo), "--id", card_id],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
        )
        res_landed = subprocess.run(
            [sys.executable, str(LANDED_PATH), "--root", str(self.repo), "--id", card_id],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(res_landed.returncode, res_gate.returncode)
        self.assertEqual(res_landed.stdout, res_gate.stdout)
        return res_landed

    def test_not_landed_missing_and_open_parity(self) -> None:
        missing_env = self._env_with_gh("bin-missing")
        res_missing = self._assert_parity(missing_env)
        self.assertNotEqual(res_missing.returncode, 0)
        self.assertIn("refused: not-landed", res_missing.stdout)
        self.assertIn("detail: pr-missing", res_missing.stdout)

        open_env = self._env_with_gh(
            "bin-open",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"OPEN\",\"headRefName\":\"card-12\"}'\n",
        )
        res_open = self._assert_parity(open_env)
        self.assertNotEqual(res_open.returncode, 0)
        self.assertIn("refused: not-landed", res_open.stdout)
        self.assertIn("detail: pr-open", res_open.stdout)

    def test_squash_and_ancestor_parity(self) -> None:
        squash_env = self._env_with_gh(
            "bin-squash",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"MERGED\",\"headRefName\":\"card-12\"}'\n",
        )
        res_squash = self._assert_parity(squash_env)
        self.assertEqual(res_squash.returncode, 0)
        self.assertIn("landed: squash", res_squash.stdout)

        git(self.repo, "merge", "--no-ff", "card-12", "-m", "merge card-12")
        anc_env = self._env_with_gh("bin-anc")
        res_anc = self._assert_parity(anc_env)
        self.assertEqual(res_anc.returncode, 0)
        self.assertIn("landed: ancestor", res_anc.stdout)

    def test_standalone_review_skill_without_work_queue_runs_landed(self) -> None:
        git(self.repo, "merge", "--no-ff", "card-12", "-m", "merge card-12")
        with tempfile.TemporaryDirectory() as isolated:
            dest = Path(isolated) / "skills" / "jt-review-work"
            shutil.copytree(REPO / "skills" / "jt-review-work", dest)
            res = subprocess.run(
                [sys.executable, str(dest / "scripts" / "landed.py"), "--root", str(self.repo), "--id", "12"],
                cwd=self.repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertIn("landed: ancestor", res.stdout)


if __name__ == "__main__":
    unittest.main()
