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
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            "# Board - app\n\nqueue: main\n\n## first\n\n- [ ] **12** item (feat) review: local\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "docs: init board")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "feat: work")
        git(self.repo, "checkout", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _env_with_gh(self, name: str, script: str | None = None) -> dict[str, str]:
        bin_dir = self.repo / "jt-queue" / name
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
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"OPEN\",\"headRefName\":\"task-12\"}'\n",
        )
        res_open = self._assert_parity(open_env)
        self.assertNotEqual(res_open.returncode, 0)
        self.assertIn("refused: not-landed", res_open.stdout)
        self.assertIn("detail: pr-open", res_open.stdout)

    def test_squash_and_ancestor_parity(self) -> None:
        squash_env = self._env_with_gh(
            "bin-squash",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"MERGED\",\"headRefName\":\"task-12\"}'\n",
        )
        res_squash = self._assert_parity(squash_env)
        self.assertEqual(res_squash.returncode, 0)
        self.assertIn("landed: squash", res_squash.stdout)

        git(self.repo, "merge", "--no-ff", "task-12", "-m", "merge task-12")
        anc_env = self._env_with_gh("bin-anc")
        res_anc = self._assert_parity(anc_env)
        self.assertEqual(res_anc.returncode, 0)
        self.assertIn("landed: ancestor", res_anc.stdout)

    def test_standalone_review_skill_without_work_queue_runs_landed(self) -> None:
        git(self.repo, "merge", "--no-ff", "task-12", "-m", "merge task-12")
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


class MultiRepoLandedTests(unittest.TestCase):
    """A task across repos is landed only when every repo has landed; order is a warning."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fe = base / "fe"
        self.be = base / "be"
        for repo in (self.fe, self.be):
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("x\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "docs: init")
            git(repo, "checkout", "-b", "task-12")
            (repo / "work.txt").write_text("y\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "feat: work")
            git(repo, "checkout", "main")
        (self.fe / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.fe / "jt-queue" / "board.md").write_text(
            "# Board - app\n\nqueue: main\n\n## repos\n\n### fe\npath: .\n\n"
            "### be\npath: ../be\nqueue: main\n\n## first\n\n"
            "- [ ] **12** login (feat) review: fe:local be:local\n",
            encoding="utf-8",
        )
        (self.fe / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            "# 12 - login\n\nkind: feat\n\nrepos: fe, be\nland: be, fe\n", encoding="utf-8"
        )
        bin_dir = base / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        assert real_git is not None
        (bin_dir / "git").symlink_to(real_git)
        self.env = os.environ.copy()
        self.env["PATH"] = str(bin_dir)
        self.env["GIT_TERMINAL_PROMPT"] = "0"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def merge(self, repo: Path, when: str) -> None:
        env = os.environ.copy()
        env["GIT_COMMITTER_DATE"] = when
        env["GIT_AUTHOR_DATE"] = when
        subprocess.run(
            ["git", "merge", "--no-ff", "task-12", "-m", "merge task-12"],
            cwd=repo, check=True, capture_output=True, text=True, env=env,
        )

    def both(self) -> subprocess.CompletedProcess[str]:
        gate = subprocess.run(
            [sys.executable, str(GATE_PATH), "landed", "--root", str(self.fe), "--id", "12"],
            cwd=self.fe, capture_output=True, text=True, env=self.env,
        )
        landed = subprocess.run(
            [sys.executable, str(LANDED_PATH), "--root", str(self.fe), "--id", "12"],
            cwd=self.fe, capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(landed.stdout, gate.stdout)
        self.assertEqual(landed.returncode, gate.returncode)
        return landed

    def test_nothing_landed_lists_each_repo_in_land_order(self) -> None:
        res = self.both()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("refused: not-landed", res.stdout)
        self.assertIn("detail: be: pr-missing; fe: pr-missing", res.stdout)
        self.assertIn("land-order: be, fe", res.stdout)

    def test_one_repo_landed_is_not_landed(self) -> None:
        self.merge(self.be, "2026-01-01T10:00:00")
        res = self.both()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("detail: fe: pr-missing", res.stdout)
        self.assertIn("landed-be: ancestor", res.stdout)

    def test_all_landed_in_order_has_no_warning(self) -> None:
        self.merge(self.be, "2026-01-01T10:00:00")
        self.merge(self.fe, "2026-01-01T11:00:00")
        res = self.both()
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("landed: all", res.stdout)
        self.assertNotIn("order-warning", res.stdout)

    def test_wrong_order_still_lands_with_a_warning(self) -> None:
        self.merge(self.fe, "2026-01-01T10:00:00")
        self.merge(self.be, "2026-01-01T11:00:00")
        res = self.both()
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("landed: all", res.stdout)
        self.assertIn("order-warning: fe landed before be", res.stdout)

    def test_next_waits_for_every_repo_before_landed_waiting(self) -> None:
        def next_out() -> str:
            return subprocess.run(
                [sys.executable, str(GATE_PATH), "next", "--root", str(self.fe)],
                cwd=self.fe, capture_output=True, text=True, env=self.env,
            ).stdout
        self.merge(self.fe, "2026-01-01T10:00:00")
        self.assertNotIn("landed-waiting", next_out())
        self.merge(self.be, "2026-01-01T11:00:00")
        self.assertIn("landed-waiting: 12", next_out())


if __name__ == "__main__":
    unittest.main()
