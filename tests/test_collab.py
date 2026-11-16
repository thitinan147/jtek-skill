"""Claim, lease, and per-task worktree behavior for a shared jt-queue."""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_flow import FLOW
import flow
from test_gate import GATE_PATH, board_text, card_body, commit_all, git, init_repo


def owner_env(name: str) -> dict[str, str]:
    env = os.environ.copy()
    env["JT_OWNER"] = name
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def gate(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def stamp_hours_ago(hours: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(hours=hours)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def plant(repo: Path, cards: str, files: dict[str, list[str]]) -> None:
    (repo / "jt-queue" / "tasks").mkdir(parents=True)
    (repo / "jt-queue" / "board.md").write_text(board_text(cards), encoding="utf-8")
    for task_id, names in files.items():
        folder = repo / "jt-queue" / "tasks" / task_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "task.md").write_text(card_body(names, title=task_id), encoding="utf-8")
    (repo / "README.md").write_text("queue\n", encoding="utf-8")
    commit_all(repo, "chore: board")


class ClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        plant(
            self.repo,
            "- [ ] **12** fresh (feat)\n- [ ] **13** other (feat)",
            {"12": ["src/a.py"], "13": ["src/b.py"]},
        )
        self.alice = owner_env("alice")
        self.bob = owner_env("bob")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_claim_records_owner_and_time(self) -> None:
        result = gate(self.repo, self.alice, "claim", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("claimed: new", result.stdout)
        self.assertIn("owner: alice", result.stdout)
        self.assertIn("commit: jt-queue/claims.md", result.stdout)
        text = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        self.assertIn("## 12", text)
        self.assertIn("owner: alice", text)
        self.assertRegex(text, r"claimed: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        self.assertIn("- src/a.py", text)
        commit_all(self.repo, "chore: claim 12")
        again = gate(self.repo, self.alice, "claim", "--id", "12")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("claimed: refresh", again.stdout)
        refreshed = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        self.assertEqual(refreshed.count("## 12"), 1)

    def test_other_owner_is_refused_until_a_human_releases(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        refused = gate(self.repo, self.bob, "claim", "--id", "12")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("refused: claimed", refused.stdout)
        self.assertIn("owner: alice", refused.stdout)
        self.assertIn("stale: no", refused.stdout)
        self.assertIn("task 12 is owned by alice", refused.stdout)
        self.assertIn("## 12", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))
        nxt = gate(self.repo, self.bob, "next")
        self.assertIn("action: do-task", nxt.stdout)
        self.assertIn("id: 13", nxt.stdout)
        self.assertIn("claimed-by: 12 owner: alice", nxt.stdout)
        self.assertNotIn("id: 12\n", nxt.stdout)
        released = gate(self.repo, self.alice, "release", "--id", "12")
        self.assertEqual(released.returncode, 0, released.stdout + released.stderr)
        self.assertIn("human-only: release", released.stdout)
        self.assertIn("released: 12", released.stdout)
        taken = gate(self.repo, self.bob, "claim", "--id", "12")
        self.assertEqual(taken.returncode, 0, taken.stdout + taken.stderr)
        self.assertIn("owner: bob", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))

    def test_stale_claim_is_shown_and_not_taken(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        old = stamp_hours_ago(25)
        text = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        for line in ("claimed:", "activity:"):
            text = "\n".join(
                f"{line} {old}" if row.startswith(line) else row for row in text.splitlines()
            )
        (self.repo / "jt-queue" / "claims.md").write_text(text + "\n", encoding="utf-8")
        refused = gate(self.repo, self.bob, "claim", "--id", "12")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("refused: claimed", refused.stdout)
        self.assertIn("stale: yes", refused.stdout)
        self.assertIn("owner: alice", refused.stdout)
        self.assertIn(old, refused.stdout)
        self.assertIn("owner: alice", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))
        solo = board_text("- [ ] **12** fresh (feat)")
        (self.repo / "jt-queue" / "board.md").write_text(solo, encoding="utf-8")
        nxt = gate(self.repo, self.bob, "next")
        self.assertIn("action: wait", nxt.stdout)
        self.assertIn("reason: claimed", nxt.stdout)
        self.assertIn("stale: yes", nxt.stdout)
        self.assertNotIn("action: do-task", nxt.stdout)

    def test_stale_window_comes_from_the_board(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        old = stamp_hours_ago(30)
        text = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        for line in ("claimed:", "activity:"):
            text = "\n".join(
                f"{line} {old}" if row.startswith(line) else row for row in text.splitlines()
            )
        (self.repo / "jt-queue" / "claims.md").write_text(text + "\n", encoding="utf-8")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        board = board.replace(
            "| `<STACK_LOCK>` | py · none · test · ban |\n",
            "| `<STACK_LOCK>` | py · none · test · ban |\n| `<CLAIM_STALE>` | 48 |\n",
        )
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        fresh = gate(self.repo, self.bob, "claim", "--id", "12")
        self.assertIn("stale: no", fresh.stdout)
        self.assertIn("refused: claimed", fresh.stdout)
        board = board.replace("| `<CLAIM_STALE>` | 48 |", "| `<CLAIM_STALE>` | 1 |")
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        stale = gate(self.repo, self.bob, "claim", "--id", "12")
        self.assertIn("stale: yes", stale.stdout)
        self.assertIn("refused: claimed", stale.stdout)
        self.assertIn("owner: alice", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))

    def test_only_claimed_tasks_wait_instead_of_clearing_the_queue(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "13").returncode, 0)
        nxt = gate(self.repo, self.bob, "next")
        self.assertIn("reason: claimed", nxt.stdout)
        self.assertIn("ids: 12, 13", nxt.stdout)
        self.assertNotIn("action: do-task", nxt.stdout)


class LeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        plant(
            self.repo,
            "- [ ] **12** login (feat)\n- [ ] **13** login form (feat)",
            {"12": ["src/app"], "13": ["src/app/utils.py"]},
        )
        self.alice = owner_env("alice")
        self.bob = owner_env("bob")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_overlap_refuses_with_the_other_task_and_owner(self) -> None:
        claimed = gate(self.repo, self.alice, "claim", "--id", "12")
        self.assertEqual(claimed.returncode, 0, claimed.stdout + claimed.stderr)
        refused = gate(self.repo, self.bob, "claim", "--id", "13")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("refused: lease", refused.stdout)
        self.assertIn("task: 12", refused.stdout)
        self.assertIn("owner: alice", refused.stdout)
        self.assertIn("path: src/app", refused.stdout)
        self.assertIn("src/app overlaps task 12 owned by alice", refused.stdout)
        text = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        self.assertNotIn("## 13", text)

    def test_distinct_paths_can_both_be_claimed(self) -> None:
        (self.repo / "jt-queue" / "tasks" / "13" / "task.md").write_text(
            card_body(["src/apple"]), encoding="utf-8"
        )
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        other = gate(self.repo, self.bob, "claim", "--id", "13")
        self.assertEqual(other.returncode, 0, other.stdout + other.stderr)
        self.assertIn("## 13", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))

    def test_release_drops_the_lease(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        released = gate(self.repo, self.alice, "release", "--id", "12")
        self.assertIn("released: 12", released.stdout)
        text = (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8")
        self.assertNotIn("## 12", text)
        taken = gate(self.repo, self.bob, "claim", "--id", "13")
        self.assertEqual(taken.returncode, 0, taken.stdout + taken.stderr)
        self.assertIn("owner: bob", taken.stdout)

    def test_merge_and_drop_release_closed_leases(self) -> None:
        self.assertEqual(gate(self.repo, self.alice, "claim", "--id", "12").returncode, 0)
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        board = board.replace(
            "- [ ] **12** login (feat)",
            "- [x] **12** login (feat) drop: done",
        )
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        closed = gate(self.repo, self.bob, "release", "--closed")
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)
        self.assertIn("released: 12", closed.stdout)
        self.assertNotIn("human-only: release", closed.stdout)
        self.assertNotIn("## 12", (self.repo / "jt-queue" / "claims.md").read_text(encoding="utf-8"))
        taken = gate(self.repo, self.bob, "claim", "--id", "13")
        self.assertEqual(taken.returncode, 0, taken.stdout + taken.stderr)


class WorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        plant(
            self.repo,
            "- [ ] **12** room search (feat)",
            {"12": ["src/rooms.py"]},
        )
        task = self.repo / "jt-queue" / "tasks" / "12" / "task.md"
        task.write_text(card_body(["src/rooms.py"], title="room search") + "ticket: BOOK-12\n", encoding="utf-8")
        commit_all(self.repo, "chore: ticket")
        self.alice = owner_env("alice")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def claim_and_commit(self) -> None:
        claimed = gate(self.repo, self.alice, "claim", "--id", "12")
        self.assertEqual(claimed.returncode, 0, claimed.stdout + claimed.stderr)
        commit_all(self.repo, "chore: claim 12")

    def test_create_is_idempotent_and_starts_at_queue_tip(self) -> None:
        self.claim_and_commit()
        tip = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        created = gate(self.repo, self.alice, "worktree", "--id", "12")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        self.assertIn("worktree: created", created.stdout)
        self.assertIn("base: main", created.stdout)
        self.assertIn("branch: feat/BOOK-12-room-search", created.stdout)
        path = Path(next(line.split(": ", 1)[1] for line in created.stdout.splitlines() if line.startswith("path: ")))
        self.assertTrue(path.is_dir(), path)
        self.assertEqual(git(path, "rev-parse", "HEAD").stdout.strip(), tip)
        self.assertIn("jt-queue/worktrees/12", path.as_posix())
        listed = git(self.repo, "worktree", "list", "--porcelain").stdout
        again = gate(self.repo, self.alice, "worktree", "--id", "12")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("worktree: reuse", again.stdout)
        self.assertIn(str(path), again.stdout)
        self.assertEqual(git(self.repo, "worktree", "list", "--porcelain").stdout, listed)
        reg = self.repo / ".git" / "jt-queue" / "worktrees.json"
        self.assertTrue(reg.is_file())
        self.assertNotIn("worktrees.json", git(self.repo, "status", "--porcelain").stdout)

    def test_uncommitted_claim_does_not_create_a_worktree(self) -> None:
        claimed = gate(self.repo, self.alice, "claim", "--id", "12")
        self.assertEqual(claimed.returncode, 0, claimed.stdout)
        refused = gate(self.repo, self.alice, "worktree", "--id", "12")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("refused: claims-uncommitted", refused.stdout)
        self.assertFalse((self.repo / ".git" / "jt-queue" / "worktrees" / "12").exists())

    def test_remove_after_drop_and_refuse_when_dirty(self) -> None:
        self.claim_and_commit()
        created = gate(self.repo, self.alice, "worktree", "--id", "12")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        path = Path(next(line.split(": ", 1)[1] for line in created.stdout.splitlines() if line.startswith("path: ")))
        open_tree = gate(self.repo, self.alice, "worktree-remove", "--id", "12")
        self.assertEqual(open_tree.returncode, 1, open_tree.stdout + open_tree.stderr)
        self.assertIn("refused: worktree-open", open_tree.stdout)
        self.assertTrue(path.is_dir())
        (path / "src-note.txt").write_text("local edit\n", encoding="utf-8")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        board = board.replace(
            "- [ ] **12** room search (feat)",
            "- [x] **12** room search (feat) drop: done",
        )
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        dirty = gate(self.repo, self.alice, "worktree-remove", "--id", "12")
        self.assertEqual(dirty.returncode, 1, dirty.stdout + dirty.stderr)
        self.assertIn("worktree: dirty", dirty.stdout)
        self.assertIn("refused: worktree-dirty", dirty.stdout)
        self.assertIn(str(path), dirty.stdout)
        self.assertTrue((path / "src-note.txt").is_file())
        (path / "src-note.txt").unlink()
        removed = gate(self.repo, self.alice, "worktree-remove", "--id", "12")
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertIn("worktree: removed", removed.stdout)
        self.assertFalse(path.exists())
        self.assertNotIn(str(path), git(self.repo, "worktree", "list").stdout)

    def test_merge_releases_the_lease_and_the_worktree(self) -> None:
        self.claim_and_commit()
        self.assertEqual(gate(self.repo, self.alice, "worktree", "--id", "12").returncode, 0)
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        board = board.replace(
            "- [ ] **12** room search (feat)",
            "- [x] **12** room search (feat) merge:",
        )
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        commit_all(self.repo, "chore: merge 12")
        released = gate(self.repo, self.alice, "release", "--closed")
        self.assertIn("released: 12", released.stdout)
        removed = gate(self.repo, self.alice, "worktree-remove", "--id", "12")
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertIn("worktree: removed", removed.stdout)


class BoardOwnerTests(unittest.TestCase):
    def test_flow_shows_owner_claimed_and_stale(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        init_repo(repo)
        plant(repo, "- [ ] **12** fresh (feat)", {"12": ["src/a.py"]})
        old = stamp_hours_ago(30)
        (repo / "jt-queue" / "claims.md").write_text(
            "\n".join(
                [
                    "# claims",
                    "",
                    "## 12",
                    "owner: alice",
                    f"claimed: {old}",
                    f"activity: {old}",
                    "paths:",
                    "- src/a.py",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        commit_all(repo, "chore: claim")
        text = flow.report(repo, now=datetime.now(timezone.utc))
        self.assertIn("  owner: alice", text)
        self.assertIn(f"  claimed: {old}", text)
        self.assertIn("  stale: yes", text)
        self.assertIn(f"  12 owner: alice claimed: {old} stale: yes", text)
        proc = subprocess.run(
            [sys.executable, "-I", str(FLOW), "--root", str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("owner: alice", proc.stdout)


if __name__ == "__main__":
    unittest.main()
