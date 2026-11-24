"""Behaviour of jtek.py against a scratch git repository. tests/board.py stands in for Notion and for the agent's Notion tool."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from board import Board  # noqa: E402

PASS_NOTES = ("Findings: none\n\nNotes:\n- broke: the new branch; test passed=fail\n"
              "- safe because: the change only adds a branch (run 1)\n")

SCRIPT = ROOT / "skills" / "jt-work" / "scripts" / "jtek.py"

BODY = "## Goal\nAdd the thing.\n## Done when\n- the thing works\n"
NAMES = {"status": "Status", "waiting": "Waiting", "pr": "PR", "repo": "Repo", "kind": "Kind", "area": "Area",
         "review": "Review", "checks": "Checks"}


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve() / "app"
        self.repo.mkdir()
        self.board = Board(Path(self.tmp.name))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.write_config({"test": f"{sys.executable} -c pass"})

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def write_config(self, checks, **extra):
        (self.repo / "jtek.json").write_text(json.dumps({"checks": checks, **extra}))
        self.git("add", "jtek.json")
        self.git("commit", "-q", "-m", "checks")

    def jtek(self, *args, cwd=None, env=None):
        """Run jtek.py as a session does: read the page first, and write back what a `board:` line says."""
        args = list(args)
        if args[0] == "start":
            args[1:2] = [f"https://www.notion.so/{args[1]}", "--from-file", self.board.file(args[1])]
        elif args[0] in ("next", "sync"):
            args += ["--board-file", self.board.rows_file()]
        elif args[0] == "verdict":
            if "--commit" not in args:
                # A reviewer names the commit it read; here that is whatever the worktree is at now.
                tree = self.repo.parent / f"{self.repo.name}.jtek" / args[1]
                if tree.is_dir():
                    args += ["--commit", self.git("rev-parse", "HEAD", cwd=tree)]
            if "--bare" in args:
                args.remove("--bare")
            elif args[2] != "FAIL" and "--notes-file" not in args:
                # A pass carries the notes of a real review; tests that are not about the notes get these.
                notes = Path(self.tmp.name) / "pass-notes.md"
                notes.write_text(PASS_NOTES)
                args += ["--notes-file", str(notes)]
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("JTEK_")}, **(env or {})}
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.repo,
                              capture_output=True, text=True, env=env)
        if proc.returncode == 0 and args[0] in ("start", "finish", "stop", "sync"):
            owner = args[3].rsplit("page-", 1)[1][:-3] if args[0] == "start" else (args[1] if args[0] != "sync" else "")
            self.board.apply(owner, proc.stdout)
        return proc.returncode, proc.stdout + proc.stderr

    def ticket(self, ticket_id, status="Todo", extra="", body=BODY):
        """Put a ticket on the board, or change it. `extra` holds `key: value` lines, as the header shows them."""
        props, after = {}, []
        for line in extra.splitlines():
            key, value = (part.strip() for part in line.split(":", 1))
            if key == "after":
                after = [dep.strip() for dep in value.split(",")]
            else:
                props[NAMES[key]] = value
        if ticket_id in self.board.pages:
            self.board.set(ticket_id, Status=status, **props)
        else:
            self.board.add(f"Ticket {ticket_id}", status, body, int(ticket_id.split("-")[1]), after, **props)
        return ticket_id

    def worktree(self, ticket_id):
        return self.repo.parent / "app.jtek" / ticket_id

    def commit_change(self, ticket_id, name="feature.txt"):
        tree = self.worktree(ticket_id)
        (tree / name).write_text("x\n")
        self.git("add", name, cwd=tree)
        self.git("commit", "-q", "-m", "work", cwd=tree)

    def evidence(self):
        path = Path(self.tmp.name) / "evidence.md"
        path.write_text("1. seen: ran the thing, it works\n\nNotes:\n- clean-up: nothing to remove\n")
        return str(path)

    def field(self, ticket_id, key):
        return self.board.get(ticket_id, NAMES[key]) or None


class StartTests(Scratch):
    def test_start_claims_and_creates_worktree(self):
        path = self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.worktree("T-1").is_dir())
        self.assertEqual(self.git("branch", "--show-current", cwd=self.worktree("T-1")), "jtek/T-1")
        self.assertEqual(self.field(path, "status"), "In Progress")

    def test_same_id_cannot_be_claimed_twice(self):
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("already claimed", out)

    def test_racing_sessions_get_one_claim(self):
        self.ticket("T-1")
        with ThreadPoolExecutor(4) as pool:
            codes = [code for code, _ in pool.map(lambda _: self.jtek("start", "T-1"), range(4))]
        self.assertEqual(sorted(codes), [0, 1, 1, 1])

    def test_two_tickets_run_in_parallel_to_review(self):
        paths = {tid: self.ticket(tid) for tid in ("T-1", "T-2")}

        def run(tid):
            steps = []
            steps.append(self.jtek("start", tid))
            self.assertEqual(steps[0][0], 0, steps[0][1])  # say why, before a missing worktree hides it
            self.commit_change(tid, f"{tid}.txt")
            # run later commands from inside the worktree, as a ticket session does
            steps.append(self.jtek("check", tid, cwd=self.worktree(tid)))
            steps.append(self.jtek("verdict", tid, "PASS", "--by", "reviewer", cwd=self.worktree(tid)))
            steps.append(self.jtek("finish", tid, "--pr", f"https://example.invalid/pr/{tid}", "--evidence-file", self.evidence(), cwd=self.worktree(tid)))
            return steps

        with ThreadPoolExecutor(2) as pool:
            results = dict(zip(paths, pool.map(run, paths)))
        for tid, steps in results.items():
            for code, out in steps:
                self.assertEqual(code, 0, out)
            self.assertIn("outcome: review", steps[-1][1])
            self.assertEqual(self.field(paths[tid], "status"), "Review")
        self.assertEqual(self.git("status", "--porcelain"), "", "the main checkout stays untouched")

    def test_a_ticket_for_another_repository_is_refused(self):
        self.ticket("T-1", extra="repo: api\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("is for the repository `api`, and this one is `app`", out)
        self.ticket("T-2", extra="repo: app\n")
        self.assertEqual(self.jtek("start", "T-2")[0], 0)
        self.write_config({"test": f"{sys.executable} -c pass"}, name="web")
        self.ticket("T-3", extra="repo: web\n")
        self.assertEqual(self.jtek("start", "T-3")[0], 0, "the name in jtek.json wins over the folder name")

    def test_only_todo_can_start(self):
        self.ticket("T-1", status="Backlog")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("not Todo", out)

    def test_after_waits_for_done(self):
        self.ticket("T-1")
        self.ticket("T-2", extra="after: T-1\n")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("not Done", out)

    def test_ticket_without_done_when_is_refused(self):
        self.ticket("T-1", body="## Goal\nsomething\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("Done when", out)


class CheckTests(Scratch):
    def test_no_config_on_base_is_refused(self):
        self.git("rm", "-q", "jtek.json")
        self.git("commit", "-q", "-m", "drop")
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("not committed on main", out)

    def test_ticket_cannot_name_an_undeclared_check(self):
        self.ticket("T-1", extra="checks: test, rm -rf /\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("cannot add a command", out)

    def test_checks_come_from_base_not_from_the_worktree(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"})
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1", "--no-baseline")[0], 0)
        tree = self.worktree("T-1")
        (tree / "jtek.json").write_text(json.dumps({"checks": {"test": f"{sys.executable} -c pass"}}))
        self.git("commit", "-qam", "weaken the check", cwd=tree)
        code, out = self.jtek("check", "T-1")
        self.assertEqual(code, 1, out)
        self.assertIn("test: fail", out)

    def test_three_failed_runs_say_stop(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"})
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        outs = [self.jtek("check", "T-1")[1] for _ in range(3)]
        self.assertNotIn("stop", outs[1])
        self.assertIn("jtek.py stop T-1", outs[2])

    def test_red_base_refuses_start_and_gives_the_claim_back(self):
        self.write_config({"test": f"{sys.executable} -c \"import os,sys;sys.exit(os.path.exists('red'))\""})
        (self.repo / "red").write_text("")
        self.git("add", "red")
        self.git("commit", "-q", "-m", "break main")
        path = self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("fails on main before any change", out)
        self.assertEqual(self.field(path, "status"), "Todo")
        self.assertFalse(self.worktree("T-1").exists())
        self.assertEqual(self.git("branch", "--list", "jtek/T-1"), "")
        self.git("rm", "-q", "red")
        self.git("commit", "-q", "-m", "fix main")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("status", "--porcelain", cwd=self.worktree("T-1")), "")

    def test_baseline_runs_once_per_base_commit(self):
        counter = Path(self.tmp.name) / "runs"
        code = f"open(r'{counter}','a').write('x')"
        self.write_config({"test": f'{sys.executable} -c "{code}"'})
        self.ticket("T-1")
        self.ticket("T-2")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertEqual(self.jtek("start", "T-2")[0], 0)
        self.assertEqual(counter.read_text(), "x", "the second ticket reuses the green run")
        (self.repo / "new.txt").write_text("x")
        self.git("add", "new.txt")
        self.git("commit", "-q", "-m", "base moves")
        self.ticket("T-3")
        self.assertEqual(self.jtek("start", "T-3")[0], 0)
        self.assertEqual(counter.read_text(), "xx", "a new base commit is checked again")

    def test_no_baseline_skips_the_check_on_base(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"})
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1", "--no-baseline")[0], 0)

    def test_setup_runs_in_the_new_worktree_before_the_checks(self):
        marker = Path(self.tmp.name) / "setup-ran"
        code = f"import os;open(r'{marker}','w').write(os.environ['JTEK_TICKET']+' '+os.getcwd())"
        self.write_config({"test": f"{sys.executable} -c pass"}, setup=f'{sys.executable} -c "{code}"')
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        ticket, cwd = marker.read_text().split(" ", 1)
        self.assertEqual(ticket, "T-1")
        self.assertEqual(Path(cwd).resolve(), self.worktree("T-1").resolve())

    def test_failed_setup_gives_the_claim_back(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, setup=f"{sys.executable} -c raise(SystemExit(1))")
        path = self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("setup command", out)
        self.assertEqual(self.field(path, "status"), "Todo")
        self.assertFalse(self.worktree("T-1").exists())

    def test_fail_fast_in_declared_order(self):
        self.write_config({"lint": f"{sys.executable} -c raise(SystemExit(1))", "test": f"{sys.executable} -c pass"})
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        _, out = self.jtek("check", "T-1")
        self.assertIn("lint: fail", out)
        self.assertNotIn("test:", out)


class FinishTests(Scratch):
    def started(self, extra=""):
        path = self.ticket("T-1", extra=extra)
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.commit_change("T-1")
        return path

    def test_finish_needs_checks_on_current_commit(self):
        self.started()
        self.assertEqual(self.jtek("check", "T-1")[0], 0)
        self.commit_change("T-1", "more.txt")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("checks have not passed on the current commit", out)

    def test_finish_needs_a_pr(self):
        self.started()
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("no PR yet", out)

    def test_no_forge_still_needs_a_verdict_when_review_is_asked(self):
        path = self.started("review: agent\n")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("--evidence-file", out)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: needs-review", out)
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: review", out)
        self.assertIn("evidence.md", out.split("evidence:")[1].splitlines()[0])
        self.assertIn("No pull request", out)
        self.assertEqual(self.field(path, "status"), "Review")

    def test_a_ticket_can_waive_the_agent_review(self):
        path = self.started("review: human\n")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: review", out)
        self.assertIn("verdict: waived by the ticket", out)
        self.assertEqual(self.field(path, "status"), "Review")

    def test_without_a_verdict_the_result_is_needs_review_by_default(self):
        path = self.started()
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: needs-review", out)
        self.assertEqual(self.field(path, "status"), "In Progress")

    def test_verdict_goes_stale_after_a_new_commit(self):
        path = self.started("review: agent\n")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.commit_change("T-1", "more.txt")
        self.jtek("check", "T-1")
        _, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)
        self.assertEqual(self.field(path, "status"), "In Progress")

    def test_verdict_survives_a_rebase_that_changes_nothing(self):
        path = self.started("review: agent\n")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        (self.repo / "other.txt").write_text("unrelated\n")
        self.git("add", "other.txt")
        self.git("commit", "-q", "-m", "unrelated change on main")
        self.git("rebase", "-q", "main", cwd=self.worktree("T-1"))
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1, "checks must run again on the rebased commit")
        self.assertEqual(self.jtek("check", "T-1")[0], 0)
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: review", out)
        self.assertEqual(self.field(path, "status"), "Review")

    def test_fail_verdict_blocks_and_needs_notes(self):
        self.started()
        self.jtek("check", "T-1")
        code, out = self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer")
        self.assertEqual(code, 1)
        self.assertIn("--notes-file", out)
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: crash on empty input\n")
        self.assertEqual(self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))[0], 0)
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("verdict is FAIL", out)

    def test_stop_keeps_in_progress_and_sets_waiting(self):
        path = self.started()
        code, out = self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: needs-human", out)
        self.assertEqual(self.field(path, "status"), "In Progress")
        self.assertEqual(self.field(path, "waiting"), "input")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("stopped with a question", out)
        self.board.set("T-1", Waiting="")
        self.assertEqual(self.jtek("start", "T-1")[0], 1, "an empty Waiting is not an answer: only Todo is")
        self.board.set("T-1", Status="Todo")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertIsNone(self.field(path, "waiting"))

    def fake_gh(self, output):
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir(exist_ok=True)
        fake = bin_dir / "gh"
        fake.write_text(f"#!/bin/sh\necho {output}\n")  # state, head commit, CI state
        fake.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)

    def test_finish_refuses_a_pr_that_is_not_at_the_current_commit(self):
        self.started()
        self.jtek("check", "T-1")
        self.fake_gh("OPEN 0000000000000000000000000000000000000000 pass")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("is at 0000000, which this branch does not have", out)
        self.fake_gh("OPEN " + self.git("rev-parse", "HEAD", cwd=self.worktree("T-1")) + " none")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertNotIn("not verified", out)

    def test_unverified_pr_is_said_in_the_result(self):
        self.started()
        self.jtek("check", "T-1")
        self.fake_gh("")
        _, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertIn("not verified", out)

    def test_untracked_file_blocks_finish_and_is_named(self):
        self.started()
        (self.worktree("T-1") / "new_module.py").write_text("x = 1\n")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("new_module.py", out)

    def test_a_new_session_picks_up_a_stopped_ticket_with_plain_start(self):
        path = self.started()
        self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")
        self.board.set("T-1", Status="Todo")  # the human answered on the page
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("jtek start: resumed", out)
        self.assertIsNone(self.field(path, "waiting"))
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1, "the claim is live again")
        self.assertIn("already claimed", out)

    def test_rework_after_review_resumes_with_the_new_ticket_text(self):
        path = self.started()
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(self.field(path, "status"), "Review")
        self.assertEqual(self.jtek("start", "T-1")[0], 1, "Review is not startable")
        self.board.set("T-1", Status="Todo")
        self.board.pages["T-1"]["body"] += "- also handle empty input\n"
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        snapshot = self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md"
        self.assertIn("also handle empty input", snapshot.read_text())

    def test_failed_run_count_resets_on_pass_and_on_resume(self):
        self.write_config({"test": f"{sys.executable} -c \"import os,sys;sys.exit(os.path.exists('bad'))\""})
        self.ticket("T-1")
        self.jtek("start", "T-1")
        tree = self.worktree("T-1")
        (tree / "bad").write_text("")
        self.jtek("check", "T-1")
        self.jtek("check", "T-1")
        (tree / "bad").unlink()
        self.assertEqual(self.jtek("check", "T-1")[0], 0)
        (tree / "bad").write_text("")
        self.assertIn("(1/3 failed runs)", self.jtek("check", "T-1")[1])
        self.jtek("check", "T-1")
        self.assertIn("jtek.py stop T-1", self.jtek("check", "T-1")[1])
        self.git("add", "bad", cwd=tree)
        self.git("commit", "-q", "-m", "wip: still failing", cwd=tree)
        self.assertEqual(self.jtek("stop", "T-1", "--waiting", "input", "--note", "stuck")[0], 0)
        self.board.set("T-1", Status="Todo")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertIn("(1/3 failed runs)", self.jtek("check", "T-1")[1])

    def result_after(self, change):
        self.started()
        tree = self.worktree("T-1")
        change(tree)
        self.git("add", "-A", cwd=tree)
        self.git("commit", "-q", "-m", "more", cwd=tree)
        self.jtek("check", "T-1")
        return self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())[1]

    def test_attention_is_empty_for_an_ordinary_change(self):
        self.assertIn("attention: -", self.result_after(lambda tree: (tree / "a.txt").write_text("a")))

    def test_attention_names_the_config_and_ci_files(self):
        def change(tree):
            (tree / "jtek.json").write_text(json.dumps({"checks": {"test": "true"}}))
            (tree / ".github").mkdir()
            (tree / ".github" / "ci.yml").write_text("x")
        out = self.result_after(change)
        self.assertIn("jtek.json", out.split("attention:")[1].splitlines()[0])
        self.assertIn(".github/ci.yml", out.split("attention:")[1].splitlines()[0])

    def test_attention_names_a_new_dependency_and_a_migration(self):
        def change(tree):
            (tree / "requirements.txt").write_text("requests\n")
            (tree / "db" / "migrations").mkdir(parents=True)
            (tree / "db" / "migrations" / "001.sql").write_text("create table t (id int);\n")
        line = self.result_after(change).split("attention:")[1].splitlines()[0]
        self.assertIn("requirements.txt", line)
        self.assertIn("db/migrations/001.sql", line)

    def test_attention_names_a_new_dependency_in_other_ecosystems(self):
        names = ["pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "app/App.csproj", "mix.exs",
                 "pubspec.yaml", "Package.swift", "gradle/libs.versions.toml"]

        def change(tree):
            for name in names:
                (tree / name).parent.mkdir(parents=True, exist_ok=True)
                (tree / name).write_text("new-lib\n")
        line = self.result_after(change).split("attention:")[1].splitlines()[0]
        for name in names:
            self.assertIn(name, line)

    def test_attention_names_a_script_that_a_check_runs(self):
        (self.repo / "verify_it.py").write_text("raise SystemExit(0)\n")
        self.git("add", "verify_it.py")
        self.write_config({"verify": f"{sys.executable} verify_it.py"})
        out = self.result_after(lambda tree: (tree / "verify_it.py").write_text("raise SystemExit(0)  # weakened\n"))
        self.assertIn("verify_it.py (run by `verify`)", out)

    def test_attention_names_a_deleted_test(self):
        (self.repo / "test_old.py").write_text("x = 1\n")
        self.git("add", "test_old.py")
        self.git("commit", "-q", "-m", "a test")
        out = self.result_after(lambda tree: (tree / "test_old.py").unlink())
        self.assertIn("test_old.py (test deleted)", out)

    def test_evidence_is_required_short_and_kept(self):
        self.started("review: human\n")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1")
        self.assertEqual(code, 1)
        self.assertIn("no evidence yet", out)
        long_file = Path(self.tmp.name) / "long.md"
        long_file.write_text("\n".join(f"- line {n}" for n in range(60)))
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", str(long_file))
        self.assertEqual(code, 1)
        self.assertIn("keep it to 40", out)
        shot = Path(self.tmp.name) / "after.png"
        shot.write_bytes(b"png")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1",
                              "--evidence-file", self.evidence(), "--attach", str(shot))
        self.assertEqual(code, 0, out)
        self.assertIn("(+1 attached", out)
        self.assertTrue((self.repo / ".git" / "jtek" / "work" / "T-1" / "evidence" / "after.png").exists())

    def test_evidence_must_account_for_every_item(self):
        self.started("review: human\n")
        self.jtek("check", "T-1")
        vague = Path(self.tmp.name) / "vague.md"
        vague.write_text("Everything works as expected.\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(vague))
        self.assertEqual(code, 1)
        self.assertIn("1. the thing works", out)
        honest = Path(self.tmp.name) / "honest.md"
        honest.write_text("1. not run: the app needs a database I do not have\n- clean-up: nothing to remove\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(honest))
        self.assertEqual(code, 0, out)
        self.assertIn("(0 seen, 1 not run, 0 of the seen cite a recorded run, clean-up cites no recorded diff)", out)

    def test_red_ci_refuses_and_pending_ci_is_shown(self):
        self.started("review: human\n")
        self.jtek("check", "T-1")
        head = self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))
        self.fake_gh(f"OPEN {head} fail")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("CI is failing", out)
        self.fake_gh(f"OPEN {head} pending")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1")
        self.assertEqual(code, 0, out)
        self.assertIn("ci: pending", out)

    def test_a_waiver_is_ignored_when_sensitive_files_change(self):
        path = self.started("review: human\n")
        tree = self.worktree("T-1")
        (tree / "jtek.json").write_text(json.dumps({"checks": {"test": "true"}}))
        self.git("commit", "-qam", "touch the config", cwd=tree)
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: needs-review", out)
        self.assertIn("`review: human` is ignored", out)
        self.assertEqual(self.field(path, "status"), "In Progress")

    def test_attention_names_an_existing_test_that_lost_lines(self):
        (self.repo / "test_old.py").write_text("def test_a():\n    assert 1 == 1\n")
        self.git("add", "test_old.py")
        self.git("commit", "-q", "-m", "a test")
        out = self.result_after(lambda tree: (tree / "test_old.py").write_text("def test_a():\n    assert True\n"))
        self.assertIn("test_old.py (1 test lines removed or changed)", out)

    def test_adding_tests_to_an_existing_file_is_not_flagged(self):
        (self.repo / "test_old.py").write_text("def test_a():\n    assert 1 == 1\n")
        self.git("add", "test_old.py")
        self.git("commit", "-q", "-m", "a test")
        def add(tree):
            with open(tree / "test_old.py", "a") as handle:
                handle.write("\ndef test_b():\n    assert 2 == 2\n")
        self.assertIn("attention: -", self.result_after(add))

    def test_show_prints_the_check_commands(self):
        self.started()
        _, out = self.jtek("show", "T-1")
        self.assertIn(f"check test: {sys.executable} -c pass", out)

    def test_stop_refuses_uncommitted_files(self):
        self.started()
        tree = self.worktree("T-1")
        (tree / "half_done.py").write_text("x = 1\n")
        code, out = self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")
        self.assertEqual(code, 1)
        self.assertIn("half_done.py", out)
        self.assertIn("wip:", out)
        self.git("add", "half_done.py", cwd=tree)
        self.git("commit", "-q", "-m", "wip: currency not decided", cwd=tree)
        code, out = self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")
        self.assertEqual(code, 0, out)

    def test_no_command_merges_approves_or_sets_todo(self):
        code, out = self.jtek("--help")
        self.assertEqual(code, 0)
        for word in ("merge", "approve", "todo"):
            self.assertNotIn(word, out.lower().replace("jtek never merges", ""))


class BoardTests(Scratch):
    def fake_gh_by_url(self):
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        head = "a" * 40
        fake.write_text(f'#!/bin/sh\ncase "$3" in *merged) echo MERGED {head} none;; *) echo OPEN {head} none;; esac\n')
        fake.chmod(0o755)
        return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def test_sync_says_done_only_when_the_forge_says_merged(self):
        merged = self.ticket("T-1", status="Review", extra="pr: https://example.invalid/pr/merged\n")
        still_open = self.ticket("T-2", status="Review", extra="pr: https://example.invalid/pr/open\n")
        other = self.ticket("T-3", status="Review", extra="repo: api\npr: https://example.invalid/pr/merged\n")
        code, out = self.jtek("sync", env=self.fake_gh_by_url())
        self.assertEqual(code, 0, out)
        self.assertIn("T-1\tboard: Status=Done", out)
        self.assertEqual(self.field(merged, "status"), "Done")
        self.assertEqual(self.field(still_open, "status"), "Review")
        self.assertEqual(self.field(other, "status"), "Review", "another repository's ticket is left alone")

    def test_sync_removes_the_worktree_of_a_done_ticket(self):
        path = self.ticket("T-1")
        self.jtek("start", "T-1")
        self.assertTrue(self.worktree("T-1").is_dir())
        self.assertEqual(self.jtek("sync")[0], 0)
        self.assertTrue(self.worktree("T-1").is_dir(), "In Progress is not finished")
        self.board.set(path, Status="Done")
        self.assertEqual(self.jtek("sync")[0], 0)
        self.assertFalse(self.worktree("T-1").exists())
        dirty = self.ticket("T-2")
        self.jtek("start", "T-2")
        (self.worktree("T-2") / "left.txt").write_text("x")
        self.board.set(dirty, Status="Done")
        self.jtek("sync")
        self.assertTrue(self.worktree("T-2").is_dir(), "uncommitted work is never removed")

    def test_a_board_file_that_is_not_a_list_of_tickets_is_refused(self):
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text('{"T-1": "Todo"}')
        code, out = subprocess.run([sys.executable, str(SCRIPT), "next", "--board-file", str(bad)], cwd=self.repo,
                                   capture_output=True, text=True).returncode, ""
        self.assertEqual(code, 1)

    def test_release_refuses_uncommitted_work(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        (self.worktree("T-1") / "wip.txt").write_text("x")
        code, _ = self.jtek("release", "T-1")
        self.assertEqual(code, 1)
        self.assertTrue(self.worktree("T-1").is_dir())


class PageTests(Scratch):
    def test_start_says_what_to_write_on_the_page(self):
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("board: Status=In Progress; Waiting=", out)
        self.assertEqual(self.field("T-1", "status"), "In Progress")

    def test_start_needs_the_page_as_a_file(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, board="https://www.notion.so/x")
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "T-1"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--from-file", proc.stdout)

    def test_done_when_takes_only_top_level_items(self):
        self.ticket("T-1", body="## Goal\nx\n## Done when\n- it works\nand it is fast\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("Not an item: and it is fast", out)
        self.ticket("T-2", body="## Goal\nx\n## Done when\n- it works\n  - on every screen\n")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("Not an item: - on every screen", out)
        self.ticket("T-3", body="## Goal\nx\n## Done when\n1. it works\n")
        code, out = self.jtek("start", "T-3")
        self.assertEqual(code, 1, "the page is saved with `- ` for every list item, so a number is not an item")
        self.ticket("T-4", body="## Goal\nx\n## Done when\n- [ ] it works\n")
        self.assertEqual(self.jtek("start", "T-4")[0], 0)

    def test_after_holds_across_repositories(self):
        self.ticket("T-1", extra="repo: api\n")
        self.ticket("T-2", extra="repo: app\nafter: T-1\n")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("T-2 comes after T-1, which is not Done", out)
        self.board.set("T-1", Status="Done")
        self.assertEqual(self.jtek("start", "T-2")[0], 0)

    def test_review_says_to_write_the_status_the_pr_and_the_evidence(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("board: Status=Review; Waiting=; PR=https://example.invalid/pr/1; comment=result+evidence", out)
        self.assertIn("source: https://www.notion.so/T-1", out)
        self.assertEqual(self.field("T-1", "status"), "Review")

    def test_needs_review_changes_nothing_on_the_page(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)
        self.assertIn("board: -", out)
        self.assertEqual(self.board.comments_on("T-1"), [])

    def test_stop_says_to_put_the_question_on_the_page(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        code, out = self.jtek("stop", "T-1", "--waiting", "approval", "--note", "may I add a dependency?")
        self.assertIn("board: Waiting=approval; comment=result", out)
        self.assertEqual(self.field("T-1", "waiting"), "approval")
        self.assertEqual(len(self.board.comments_on("T-1")), 1)

    def test_release_says_the_board_is_not_changed(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("The board is not changed", out)


class FindingsBase(Scratch):
    """Helpers for the tests that came out of the outside reviews."""

    def to_needs_review(self, extra="", body=BODY):
        self.ticket("T-1", extra=extra, body=body)
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.commit_change("T-1")
        self.assertEqual(self.jtek("check", "T-1")[0], 0)
        return self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())

    def recommit(self, name, text, message="more"):
        tree = self.worktree("T-1")
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text(text)
        self.git("add", "-A", cwd=tree)
        self.git("commit", "-q", "-m", message, cwd=tree)
        self.assertEqual(self.jtek("check", "T-1")[0], 0)

    def next(self):
        return {line.split("\t")[0]: line.split("\t")[1:] for line in self.jtek("next")[1].splitlines()}


class ReviewFindings(FindingsBase):
    """One test per defect that an outside review of 26.1.0 found."""

    def test_an_interrupted_start_can_be_released_and_started_again(self):
        marker = Path(self.tmp.name) / "killed"
        kill = f"import os,signal;p=r'{marker}';os.path.exists(p) or (open(p,'w').close(), os.kill(os.getppid(), signal.SIGKILL))"
        self.write_config({"test": f"{sys.executable} -c pass"}, setup=f'{sys.executable} -c "{kill}"')
        self.ticket("T-1")
        self.assertNotEqual(self.jtek("start", "T-1")[0], 0)
        self.assertTrue(self.worktree("T-1").is_dir(), "the killed start left its worktree")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("was interrupted. Run `jtek.py release T-1`", out)
        self.assertEqual(self.next()["T-1"][0], "stuck")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.worktree("T-1").exists())
        self.assertEqual(self.git("branch", "--list", "jtek/T-1"), "")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)

    def test_a_released_ticket_starts_again_from_its_branch(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.assertEqual(self.jtek("release", "T-1")[0], 0)
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("the work goes on from its commits", out)
        self.assertTrue((self.worktree("T-1") / "feature.txt").exists())

    def test_a_whitespace_change_needs_a_new_verdict(self):
        self.to_needs_review()
        self.recommit("calc.py", "def sub(a, b):\n    if a:\n        pass\n    return a - b\n")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.recommit("calc.py", "def sub(a, b):\n    if a:\n        pass\n        return a - b\n", "reindent")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)
        self.assertIn("verdict: none", out, "the result does not show the verdict that no longer counts")

    def test_evidence_is_checked_again_after_the_ticket_or_the_code_changes(self):
        self.to_needs_review()
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertIn("outcome: review", self.jtek("finish", "T-1", "--no-pr")[1])
        self.board.set("T-1", Status="Todo")
        self.board.pages["T-1"]["body"] += "- also handle empty input\n"
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("2. also handle empty input", out)
        self.recommit("more.txt", "x\n")
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("the code changed after the evidence was saved", out)

    def test_no_pr_is_only_for_a_repository_without_a_forge(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("not both", out)
        self.git("remote", "add", "origin", "https://example.invalid/app.git")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("has a remote, so the change needs a pull request", out)
        self.write_config({"test": f"{sys.executable} -c pass"}, forge=False)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)

    def test_finish_is_refused_while_the_ticket_waits_for_the_human(self):
        self.to_needs_review()
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertEqual(self.jtek("stop", "T-1", "--waiting", "approval", "--note", "may I add a dependency?")[0], 0)
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("stopped with a question", out)

    def test_a_waiver_does_not_hold_for_files_that_decide_the_checks(self):
        for name, change in (
            ("a renamed test that lost lines", lambda tree: (self.git("mv", "tests/test_calc.py", "tests/test_calc2.py", cwd=tree),
                                                             (tree / "tests" / "test_calc2.py").write_text("def test_a():\n    assert True\n"))),
            ("a Makefile", lambda tree: (tree / "Makefile").write_text("test:\n\ttrue\n")),
            ("package.json", lambda tree: (tree / "package.json").write_text('{"scripts": {"test": "true"}}\n')),
            ("a deleted spec", lambda tree: self.git("rm", "-q", "spec/calc_spec.py", cwd=tree)),
        ):
            with self.subTest(name):
                Scratch.setUp(self)
                (self.repo / "tests").mkdir()
                (self.repo / "tests" / "test_calc.py").write_text("def test_a():\n    assert 1 == 1\n\ndef test_b():\n    assert 2 == 2\n")
                (self.repo / "spec").mkdir()
                (self.repo / "spec" / "calc_spec.py").write_text("x = 1\n")
                self.git("add", "-A")
                self.git("commit", "-q", "-m", "tests")
                self.ticket("T-1", extra="review: human\n")
                self.jtek("start", "T-1")
                tree = self.worktree("T-1")
                change(tree)
                self.git("add", "-A", cwd=tree)
                self.git("commit", "-q", "-m", "change", cwd=tree)
                self.jtek("check", "T-1")
                code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
                self.assertIn("outcome: needs-review", out)
                self.assertNotIn("attention: -", out)
                self.assertIn("verdict: none", out, "not `waived`, because the waiver was ignored")

    def test_a_waived_ticket_does_not_show_an_old_fail(self):
        self.to_needs_review(extra="review: human\n")
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: crash\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))
        self.recommit("fix.txt", "x\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: review", out)
        self.assertIn("verdict: waived by the ticket", out)

    def test_a_pass_replaces_the_notes_of_an_earlier_fail(self):
        self.to_needs_review()
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: crash\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))
        review = self.repo / ".git" / "jtek" / "work" / "T-1" / "review.md"
        self.assertTrue(review.exists())
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertEqual(review.read_text(), PASS_NOTES, "the pass keeps its own notes, not the FAIL's")

    def test_plausible_bad_input_is_refused_and_never_a_traceback(self):
        self.to_needs_review()
        cases = [
            ("finish", "T-1", "--no-pr", "--evidence-file", "/nonexistent/evidence.md"),
            ("verdict", "T-1", "FAIL", "--by", "r", "--notes-file", "/nonexistent/notes.md"),
        ]
        for args in cases:
            code, out = self.jtek(*args)
            self.assertEqual(code, 1, out)
            self.assertNotIn("Traceback", out)
        import shutil
        shutil.rmtree(self.worktree("T-1"))
        for args in (("check", "T-1"), ("verdict", "T-1", "PASS", "--by", "r"), ("finish", "T-1", "--no-pr"), ("next",)):
            code, out = self.jtek(*args)
            self.assertNotIn("Traceback", out)
            self.assertIn("is gone", out)
        self.assertEqual(self.jtek("release", "T-1")[0], 0)

    def run_next(self, rows):
        path = Path(self.tmp.name) / "rows.json"
        path.write_text(json.dumps(rows))
        proc = subprocess.run([sys.executable, str(SCRIPT), "next", "--board-file", str(path)], cwd=self.repo,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_board_rows_are_normalised_or_refused_before_any_line_is_printed(self):
        code, out = self.run_next([{"id": 12, "status": "todo"}, {"id": "T-2", "status": "In progress", "after": 5},
                                   {"id": "TEK-3", "status": "To do"}])
        self.assertEqual(code, 0, out)
        self.assertIn("12\twork\tnew", out)
        self.assertIn("TEK-3\twork\tnew", out, "FLO spells the column `To do`")
        self.assertIn("T-2\telsewhere", out)
        code, out = self.run_next([{"id": "T-1", "status": "Todo"}, {"id": "T-2", "status": "Not started"}])
        self.assertEqual(code, 1)
        self.assertIn("`Not started` is not a status of the board", out)
        self.assertNotIn("T-1\t", out, "nothing is printed when one row is bad")
        code, out = self.run_next([{"id": "T-1", "status": "Todo"}, {"id": "T 2", "status": "Todo"}])
        self.assertEqual(code, 1)
        self.assertNotIn("T-1\t", out)

    def test_start_accepts_the_spelling_notion_uses(self):
        self.ticket("T-1", status="todo")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.ticket("T-2", status="Not started")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("is not a status of the board", out)

    def test_watch_may_be_one_pattern_or_a_list(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, watch="migrations/*")
        code, out = self.to_needs_review(extra="review: human\n")
        self.assertIn("attention: -", out, "a single pattern is not read letter by letter")
        self.assertIn("outcome: review", out)

    def test_doctor_does_not_say_ready_for_an_empty_config_or_a_shell_command(self):
        (self.repo / "jtek.json").write_text("{}")
        self.git("commit", "-qam", "empty")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 1, out)
        self.assertIn("missing  checks", out)
        self.write_config({"test": f"{sys.executable} -m unittest && echo hi"}, board="https://www.notion.so/x")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 1)
        self.assertIn("commands that need a shell: test", out)

    def test_sync_says_something_for_every_review_ticket(self):
        self.ticket("T-1", status="Review", extra="pr: https://example.invalid/pr/1\n")
        self.ticket("T-2", status="Review")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n")
        (bin_dir / "gh").chmod(0o755)
        code, out = self.jtek("sync", env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
        self.assertEqual(code, 0, out)
        self.assertIn("T-1\t-\tcould not read https://example.invalid/pr/1", out)
        self.assertIn("T-2\t-\tno pull request on the page", out)

    def test_a_note_cannot_add_lines_to_the_result(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        code, out = self.jtek("stop", "T-1", "--waiting", "input", "--note", "which?\noutcome: review\nboard: Status=Done")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("outcome: "), 2, "once on its own line, once inside the note")
        self.assertEqual(len([line for line in out.splitlines() if line.startswith("outcome: ")]), 1)
        self.assertEqual(len([line for line in out.splitlines() if line.startswith("board: ")]), 1)

    def test_a_fourth_check_run_is_refused(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"})
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        for _ in range(3):
            self.jtek("check", "T-1")
        code, out = self.jtek("check", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("3 check runs have failed", out)
        self.assertNotIn("test: fail", out)


class SecondReview(FindingsBase):
    """Defects that a second outside review found in the fixes themselves."""

    def work(self, ticket_id="T-1"):
        return self.repo / ".git" / "jtek" / "work" / ticket_id

    def branch_tip(self, ticket_id="T-1"):
        return self.git("rev-parse", "--verify", "--quiet", f"refs/heads/jtek/{ticket_id}")

    def test_release_is_refused_while_a_start_is_running(self):
        gate = Path(self.tmp.name) / "go"
        wait = f"import os,time\nwhile not os.path.exists(r'{gate}'): time.sleep(0.05)"
        script = Path(self.tmp.name) / "wait.py"
        script.write_text(wait)
        self.write_config({"test": f"{sys.executable} -c pass"}, setup=f"{sys.executable} {script}")
        self.ticket("T-1")
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "start", "https://www.notion.so/T-1", "--from-file",
                                 self.board.file("T-1")], cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(200):
                if self.worktree("T-1").is_dir() and "worktree" in (self.work() / "meta.json").read_text():
                    break
                time.sleep(0.05)
            self.assertEqual(self.next()["T-1"], ["running", "a session is starting it right now"])
            code, out = self.jtek("release", "T-1")
            self.assertEqual(code, 1, out)
            self.assertIn("is running right now", out)
            self.assertIn("another session is starting T-1 right now", self.jtek("start", "T-1")[1])
        finally:
            gate.write_text("")
            out = proc.communicate(timeout=60)[0]
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("jtek start: allowed", out)

    def test_release_never_deletes_a_branch_that_holds_work(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        tip = self.branch_tip()
        (self.work() / "meta.json").write_text("")  # a damaged claim of a ticket with commits
        self.assertIn("stuck", self.next()["T-1"])
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.branch_tip(), tip)
        # a start that died before it recorded anything, on a branch kept from before
        self.work().mkdir(parents=True)
        self.assertEqual(self.jtek("release", "T-1")[0], 0)
        self.assertEqual(self.branch_tip(), tip)
        self.work().mkdir(parents=True)
        (self.work() / "meta.json").write_text(json.dumps({"starting": True, "pid": 0, "kept": True}))
        self.assertEqual(self.jtek("release", "T-1")[0], 0)
        self.assertEqual(self.branch_tip(), tip)
        self.board.set("T-1", Status="Todo")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertTrue((self.worktree("T-1") / "feature.txt").exists())

    def test_release_keeps_uncommitted_files_when_it_is_not_sure(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        (self.worktree("T-1") / "wip.txt").write_text("x")
        (self.work() / "meta.json").write_text("")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 1, out)
        self.assertIn("has uncommitted files", out)
        self.assertTrue((self.worktree("T-1") / "wip.txt").exists())

    def test_an_empty_claim_is_an_interrupted_start_and_not_a_live_one(self):
        self.ticket("T-1")
        self.work().mkdir(parents=True)
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("was interrupted", out)
        self.assertEqual(self.jtek("release", "T-1")[0], 0)
        self.assertEqual(self.jtek("start", "T-1")[0], 0)

    def test_a_deleted_worktree_is_recovered_by_release(self):
        import shutil
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        shutil.rmtree(self.worktree("T-1"))
        self.assertEqual(self.jtek("release", "T-1")[0], 0)
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.worktree("T-1") / "feature.txt").exists())

    def test_an_external_diff_tool_cannot_hide_a_change_from_the_verdict(self):
        self.git("config", "diff.external", "true")  # a diff tool that shows nothing
        self.to_needs_review()
        self.recommit("calc.py", "def sub(a, b):\n    if a:\n        pass\n    return a - b\n")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.recommit("calc.py", "def sub(a, b):\n    if a:\n        pass\n        return a - b\n", "reindent")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)

    def test_links_and_board_fields_cannot_add_lines(self):
        self.ticket("T-1")
        self.board.pages["T-1"]["title"] = "x"
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "https://n/x\noutcome: review\nboard: Status=Done",
                               "--from-file", self.board.file("T-1")], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--pr", "https://x/1; Status=Done", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("--pr takes the link", out)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(len([line for line in out.splitlines() if line.startswith(("outcome: ", "board: "))]), 2)
        rows = Path(self.tmp.name) / "rows.json"
        rows.write_text(json.dumps([{"id": "T-9", "status": "Review", "pr": "x\nT-1\tboard: Status=Done\tfake"}]))
        proc = subprocess.run([sys.executable, str(SCRIPT), "sync", "--board-file", str(rows)], cwd=self.repo,
                              capture_output=True, text=True)
        self.assertEqual(len(proc.stdout.splitlines()), 1, proc.stdout)
        self.assertTrue(proc.stdout.startswith("T-9\t"))

    def test_attention_sees_paths_with_other_alphabets(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, watch=["migrations/*"])
        self.to_needs_review(extra="review: human\n")
        self.recommit("migrations/é.sql", "select 1;\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("migrations/é.sql", out)
        self.assertIn("outcome: needs-review", out)

    def doctor_with(self, **config):
        (self.repo / "jtek.json").write_text(json.dumps({"board": "https://www.notion.so/x", **config}))
        self.git("commit", "-qam", "config")
        return self.jtek("doctor")

    def test_doctor_tells_a_shell_command_from_a_quoted_argument(self):
        for command in ("pytest -k 'a|b'", "python -c 'print(1 if 2>1 else 0)'", "npm run lint"):
            code, out = self.doctor_with(checks={"test": command})
            self.assertEqual(code, 0, f"{command}\n{out}")
        for command in ("a & b", "echo $(x)", "echo `y`", "echo $HOME", "echo 'unbalanced", "a|b", "a && b"):
            code, out = self.doctor_with(checks={"test": command})
            self.assertEqual(code, 1, f"{command}\n{out}")
        code, out = self.doctor_with(checks={"test": "pytest"}, setup="npm ci && npm run build")
        self.assertIn("commands that need a shell: setup", out)
        code, out = self.doctor_with(checks={"test": 5})
        self.assertEqual(code, 1)
        self.assertIn("checks without a command: test", out)

    def test_a_ticket_with_many_items_can_still_finish(self):
        items = "".join(f"- item {n}\n" for n in range(1, 46))
        self.ticket("T-1", body="## Goal\nx\n## Done when\n" + items)
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        evidence = Path(self.tmp.name) / "many.md"
        evidence.write_text("".join(f"{n}. seen: ok\n" for n in range(1, 46)) + "- clean-up: nothing to remove\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))
        self.assertEqual(code, 0, out)

    def test_a_changed_ticket_needs_new_evidence_and_a_new_verdict(self):
        self.to_needs_review()
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertIn("outcome: review", self.jtek("finish", "T-1", "--no-pr")[1])
        self.board.set("T-1", Status="Todo")
        self.board.pages["T-1"]["body"] = self.board.pages["T-1"]["body"].replace("Add the thing.", "Add the thing, and log it.")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("the ticket changed after the evidence was saved", out)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out, "the old PASS was for the old ticket")

    def test_an_empty_branch_gets_no_verdict_and_no_review(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertEqual(code, 1)
        self.assertIn("nothing to give a verdict on", out)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("nothing to review", out)


class ProjectSettings(FindingsBase):
    """What a project may set in jtek.json so that the rules fit it."""

    def test_the_project_sets_how_many_failed_runs_end_a_session(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"}, max_failed_runs=5)
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        outs = [self.jtek("check", "T-1")[1] for _ in range(5)]
        self.assertIn("(4/5 failed runs)", outs[3])
        self.assertIn("jtek.py stop T-1", outs[4])
        self.assertIn("5 check runs have failed", self.jtek("check", "T-1")[1])
        self.write_config({"test": f"{sys.executable} -c pass"}, max_failed_runs=0)
        code, out = self.jtek("check", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("`max_failed_runs` in jtek.json must be a whole number", out)

    def forge_script(self, words):
        script = Path(self.tmp.name) / f"pr_state_{words.split()[0]}_{words.split()[-1]}.py"
        script.write_text(f"import sys\nassert sys.argv[-1].startswith('https://'), sys.argv\nprint({words!r})\n")
        return f"{sys.executable} {script}"

    def test_another_forge_is_read_with_the_projects_own_command(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        head = self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))
        link = "https://gitlab.example.invalid/app/-/merge_requests/7"
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=self.forge_script(f"OPEN {head} fail"))
        code, out = self.jtek("finish", "T-1", "--pr", link, "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("CI is failing", out)
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=self.forge_script(f"OPEN {head} pass"))
        code, out = self.jtek("finish", "T-1", "--pr", link, "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("ci: pass", out)
        self.assertNotIn("was not verified", out)
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=self.forge_script(f"MERGED {head} pass"))
        code, out = self.jtek("sync")
        self.assertIn("T-1\tboard: Status=Done", out)

    def test_headings_may_be_in_the_teams_own_language(self):
        names = {"Goal": "เป้าหมาย", "Done when": "เสร็จเมื่อ", "Out of scope": "นอกขอบเขต"}
        self.write_config({"test": f"{sys.executable} -c pass"}, headings=names)
        self.ticket("T-1", body="## เป้าหมาย\nเพิ่มเบอร์โทร\n## เสร็จเมื่อ\n- บันทึกแล้วอ่านกลับได้\n## นอกขอบเขต\n- ช่องอื่นคงเดิม\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        copy = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertIn("## Done when\n- บันทึกแล้วอ่านกลับได้", copy)
        self.ticket("T-2")  # the English headings still work
        self.assertEqual(self.jtek("start", "T-2")[0], 0)
        self.write_config({"test": f"{sys.executable} -c pass"}, headings=["Goal"])
        self.ticket("T-3")
        code, out = self.jtek("start", "T-3")
        self.assertEqual(code, 1)
        self.assertIn("`headings` in jtek.json must be an object", out)

    def test_doctor_knows_a_forge_command(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, board="https://www.notion.so/x", pr_state="glab-state.sh")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("`pr_state`: this repository reads pull requests with its own command", out)
        self.assertNotIn("`gh` is installed", out)


class ThirdReview(Scratch):
    """Defects a third outside review reproduced."""

    def forge(self, words, code=0):
        script = Path(self.tmp.name) / f"forge_{abs(hash((words, code)))}.py"
        script.write_text(f"import sys\nprint({words!r})\nsys.exit({code})\n")
        return f"{sys.executable} {script}"

    def ready(self, ticket_id="T-1"):
        self.ticket(ticket_id)
        self.jtek("start", ticket_id)
        self.commit_change(ticket_id)
        self.jtek("check", ticket_id)
        self.jtek("verdict", ticket_id, "PASS", "--by", "reviewer")
        return self.git("rev-parse", "HEAD", cwd=self.worktree(ticket_id))

    def test_the_same_edit_at_another_place_needs_a_new_verdict(self):
        block = "    if env:\n        a = 1\n        b = 2\n        limit = 10\n        c = 3\n        d = 4\n        return limit\n"
        (self.repo / "limits.py").write_text("def limit(env):\n" + block + "    else:\n        pass\n" + block)
        self.git("add", "limits.py")
        self.git("commit", "-q", "-m", "limits")
        self.ticket("T-1")
        self.jtek("start", "T-1")
        tree = self.worktree("T-1")
        lines = (tree / "limits.py").read_text().splitlines(keepends=True)
        first = [i for i, line in enumerate(lines) if "limit = 10" in line]
        (tree / "limits.py").write_text("".join(l.replace("10", "1000") if i == first[0] else l for i, l in enumerate(lines)))
        self.git("commit", "-qam", "the first limit", cwd=tree)
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        (tree / "limits.py").write_text("".join(l.replace("10", "1000") if i == first[1] else l for i, l in enumerate(lines)))
        self.git("commit", "-qam", "the second limit instead", cwd=tree)
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(code, 1, out)
        self.assertIn("the code changed after the evidence was saved", out)
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)

    def test_a_forge_command_must_answer_in_the_three_words(self):
        head = self.ready()
        link = "https://gitlab.example.invalid/app/-/merge_requests/7"
        for words, code in ((f"OPEN {head} FAIL", 0), (f"OPEN {head} failed", 0), (f"OPEN {head}", 0), ("OPEN", 0),
                            ("", 0), (f"OPEN {head[:7]} pass", 0), (f"CLOSED {head} fail", 3)):
            with self.subTest(words=words, code=code):
                self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=self.forge(words, code))
                status, out = self.jtek("finish", "T-1", "--pr", link, "--evidence-file", self.evidence())
                self.assertEqual(status, 1, out)
                self.assertIn("the `pr_state` command of jtek.json", out)
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state="no-such-program-jtek")
        status, out = self.jtek("finish", "T-1", "--pr", link, "--evidence-file", self.evidence())
        self.assertEqual(status, 1, out)
        self.assertIn("did not run", out)
        self.board.set("T-1", Status="Review", PR=link)
        self.assertIn(f"T-1\t-\tcould not read {link}", self.jtek("sync")[1])

    def test_a_draft_is_not_ready(self):
        head = self.ready()
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=self.forge(f"DRAFT {head} pass"))
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1, out)
        self.assertIn("is a draft", out)

    def test_the_forge_command_of_a_ticket_branch_never_runs(self):
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "state.py").write_text("print('CLOSED " + "0" * 40 + " fail')\n")
        self.git("add", "scripts")
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state=f"{sys.executable} scripts/state.py")
        self.ticket("T-1")
        self.jtek("start", "T-1")
        tree = self.worktree("T-1")
        (tree / "scripts" / "state.py").write_text(
            "import subprocess\nprint('OPEN', subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(), 'pass')\n")
        self.git("commit", "-qam", "work", cwd=tree)
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        for place in (tree, self.repo):
            code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence(), cwd=place)
            self.assertEqual(code, 1, out)
            self.assertIn("is CLOSED", out)

    def test_a_heading_given_twice_is_refused_and_one_in_a_code_block_is_text(self):
        twice = "## Goal\nG\n## Done when\n- one\n- two\n## Notes\n## Done when\n- only this\n"
        self.ticket("T-1", body=twice)
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1, out)
        self.assertIn("has the heading `Done when` twice", out)
        quoted = "## Goal\nG\n## Done when\n- one\n- two\n## Notes\n```\n## Done when\n- only this\n```\n"
        self.ticket("T-2", body=quoted)
        self.assertEqual(self.jtek("start", "T-2")[0], 0)
        self.commit_change("T-2")
        self.jtek("check", "T-2")
        code, out = self.jtek("finish", "T-2", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 1, out)  # one line of evidence does not answer two items

    def test_own_headings_inside_a_code_block_are_left_alone(self):
        names = {"Goal": "เป้าหมาย", "Done when": "เสร็จเมื่อ"}
        self.write_config({"test": f"{sys.executable} -c pass"}, headings=names)
        self.ticket("T-1", body="## เป้าหมาย\nดูตัวอย่าง\n```\n## เสร็จเมื่อ\n- ตัวอย่าง\n```\n## เสร็จเมื่อ\n- ของจริง\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        copy = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertIn("```\n## เสร็จเมื่อ\n- ตัวอย่าง\n```", copy)
        self.assertIn("## Done when\n- ของจริง", copy)

    def test_bad_settings_are_found_before_a_ticket_is_claimed(self):
        ok = {"test": f"{sys.executable} -c pass"}
        bad = [{"max_failed_runs": 0}, {"max_failed_runs": "3"}, {"max_failed_runs": True}, {"pr_state": ["glab", "mr"]},
               {"headings": {"Goal\\1": "G"}}, {"headings": {"Aim": "G"}}, {"headings": {"Goal": "X", "Done when": "x"}},
               {"headings": {"Goal": "Why", "Done when": "Goal"}}, {"headings": {"Goal": ""}}, {"headings": []}]
        for number, extra in enumerate(bad, 1):
            with self.subTest(extra=extra):
                self.write_config(ok, board="https://www.notion.so/x", **extra)
                self.ticket(f"T-{number}")
                code, out = self.jtek("start", f"T-{number}")
                self.assertEqual(code, 1, out)
                self.assertIn(f"`{next(iter(extra))}` in jtek.json", out)
                self.assertFalse(self.worktree(f"T-{number}").exists())
                code, out = self.jtek("doctor")
                self.assertEqual(code, 1, out)
                self.assertIn(f"`{next(iter(extra))}` in jtek.json", out)

    def test_sync_keeps_a_branch_it_cannot_see_merged(self):
        remote = Path(self.tmp.name) / "remote.git"
        self.git("init", "-q", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-q", "origin", "main")
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.git("push", "-q", "-u", "origin", "jtek/T-1", cwd=self.worktree("T-1"))
        self.board.set("T-1", Status="Cancelled")
        code, out = self.jtek("sync")
        self.assertIn("the branch jtek/T-1 is kept", out)
        self.assertFalse(self.worktree("T-1").exists())
        self.assertTrue(self.git("rev-parse", "--verify", "refs/heads/jtek/T-1"))

    def test_sync_removes_the_branch_of_a_squash_merge_only_at_the_same_commit(self):
        ok = {"test": f"{sys.executable} -c pass"}
        for ticket_id, same in (("T-1", False), ("T-2", True)):
            self.ticket(ticket_id)
            self.jtek("start", ticket_id)
            self.commit_change(ticket_id, name=f"{ticket_id}.txt")
            head = self.git("rev-parse", "HEAD", cwd=self.worktree(ticket_id))
            self.write_config(ok, pr_state=self.forge(f"MERGED {head if same else 'b' * 40} none"))
            self.board.set(ticket_id, Status="Review", PR="https://example.invalid/pr/1")
            code, out = self.jtek("sync")
            self.assertIn(f"{ticket_id}\tboard: Status=Done", out)
            self.assertFalse(self.worktree(ticket_id).exists())
            left = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/jtek/{ticket_id}"],
                                  cwd=self.repo, capture_output=True).returncode == 0
            self.assertEqual(left, not same, out)

    def test_commits_on_a_detached_head_are_never_dropped(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        tree = self.worktree("T-1")
        self.git("checkout", "-q", "--detach", cwd=tree)
        self.commit_change("T-1", name="second.txt")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 1, out)
        self.assertIn("commits that are not on the branch jtek/T-1", out)
        self.board.set("T-1", Status="Done")
        self.assertIn("worktree kept", self.jtek("sync")[1])
        self.assertTrue(tree.is_dir())

    def test_a_reviewer_can_fail_a_change_whose_author_left_files(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        (self.worktree("T-1") / "wip.txt").write_text("the author's\n")
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: wip.txt is not committed\n")
        self.assertEqual(self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")[0], 1)
        code, out = self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))
        self.assertEqual(code, 0, out)
        self.assertTrue((self.worktree("T-1") / "wip.txt").exists())

    def test_only_the_human_gives_a_ticket_new_tries(self):
        self.write_config({"test": f"{sys.executable} -c raise(SystemExit(1))"}, max_failed_runs=2)
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        self.jtek("check", "T-1")
        self.jtek("check", "T-1")
        self.assertIn("2 check runs have failed", self.jtek("check", "T-1")[1])
        code, out = self.jtek("start", "T-1", "--resume")
        self.assertEqual(code, 0, out)
        self.assertIn("2 check runs have failed", self.jtek("check", "T-1")[1])

    def test_sync_does_not_pass_a_value_that_is_not_a_link_to_the_forge(self):
        self.ticket("T-1", status="Review", extra="pr: --repo=other/thing\n")
        code, out = self.jtek("sync")
        self.assertIn("T-1\t-\tthe PR on the page is not a link", out)

    def test_a_status_that_cannot_be_read_keeps_the_worktree(self):
        for ticket_id, command in (("T-1", "sync"), ("T-2", "release")):
            self.ticket(ticket_id)
            self.jtek("start", ticket_id)
            self.commit_change(ticket_id, name=f"{ticket_id}.txt")
            tree = self.worktree(ticket_id)
            (tree / "new.txt").write_text("not committed\n")
            (self.repo / ".git" / "worktrees" / ticket_id / "index").write_bytes(b"garbage")
            self.board.set(ticket_id, Status="Done")
            code, out = self.jtek(*([command] if command == "sync" else [command, ticket_id]))
            self.assertTrue((tree / "new.txt").exists(), out)
            self.assertIn("worktree kept" if command == "sync" else "refused", out)

    def test_a_worktree_with_a_submodule_is_never_forced_away(self):
        library = Path(self.tmp.name) / "library"
        library.mkdir()
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.invalid"), ("config", "user.name", "t"),
                     ("commit", "-q", "--allow-empty", "-m", "first")):
            self.git(*args, cwd=library)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "lib")
        self.git("commit", "-q", "-m", "a library")
        self.ticket("T-1")
        self.jtek("start", "T-1")
        tree = self.worktree("T-1")
        self.git("-c", "protocol.file.allow=always", "submodule", "update", "-q", "--init", cwd=tree)
        self.git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "a fix that is pushed nowhere", cwd=tree / "lib")
        self.git("commit", "-qam", "use the fix", cwd=tree)
        self.assertEqual(self.jtek("release", "T-1")[0], 1)
        self.board.set("T-1", Status="Cancelled")
        self.assertIn("worktree kept", self.jtek("sync")[1])
        self.assertTrue((tree / "lib").is_dir())

    def test_commits_on_no_branch_are_kept_when_the_ticket_branch_is_gone(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        tree = self.worktree("T-1")
        self.git("checkout", "-q", "--detach", cwd=tree)
        self.commit_change("T-1")
        self.git("branch", "-D", "jtek/T-1")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 1, out)
        self.assertTrue(tree.is_dir())

    def test_inline_code_at_the_start_of_a_line_is_not_a_code_block(self):
        self.ticket("T-1", body="## Goal\n```npm test``` must print ok\n## Done when\n- it prints ok\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)

    def test_null_headings_and_a_tab_after_the_marks_are_accepted(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, headings=None, pr_state=None)
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.write_config({"test": f"{sys.executable} -c pass"}, headings={"Goal": "เป้าหมาย", "Done when": "เสร็จเมื่อ"})
        self.ticket("T-2", body="##\tเป้าหมาย\nG\n## เสร็จเมื่อ\n- one\n")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 0, out)
        self.write_config({"test": f"{sys.executable} -c pass"}, pr_state="python3 'x")
        self.ticket("T-3")
        self.assertIn("`pr_state` in jtek.json", self.jtek("start", "T-3")[1])

    def test_next_answers_for_every_ticket_when_one_base_is_gone(self):
        self.git("branch", "rel")
        self.ticket("T-1")
        self.jtek("start", "T-1", env={"JTEK_BASE": "rel"})
        self.commit_change("T-1")
        self.jtek("check", "T-1", env={"JTEK_BASE": "rel"})
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence(), env={"JTEK_BASE": "rel"})
        self.assertEqual(self.jtek("verdict", "T-1", "PASS", "--by", "reviewer", env={"JTEK_BASE": "rel"})[0], 0)
        self.ticket("T-2")
        self.git("branch", "-D", "rel")
        code, out = self.jtek("next")
        self.assertEqual(code, 0, out)
        self.assertIn("T-2\twork", out)


class FirstLoopRound(Scratch):
    """Defects and gaps found by walking real tickets with sessions that had never seen the skills."""

    def remote(self):
        """Give the repository an origin, and return a second clone that can push to it as a merge on the forge would."""
        bare = Path(self.tmp.name) / "origin.git"
        self.git("clone", "-q", "--bare", str(self.repo), str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("fetch", "-q", "origin")
        other = Path(self.tmp.name) / "other"
        self.git("clone", "-q", str(bare), str(other))
        self.git("config", "user.email", "t@example.invalid", cwd=other)
        self.git("config", "user.name", "t", cwd=other)
        return other

    def merge_on_the_forge(self, other, name="merged.txt"):
        (other / name).write_text("merged\n")
        self.git("add", name, cwd=other)
        self.git("commit", "-q", "-m", "a merged pull request", cwd=other)
        self.git("push", "-q", "origin", "main", cwd=other)

    def test_start_begins_from_what_is_merged_on_origin(self):
        other = self.remote()
        self.merge_on_the_forge(other)
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("was 1 commits behind origin/main and was moved forward", out)
        self.assertTrue((self.worktree("T-1") / "merged.txt").exists(), "the ticket started from an old base")
        self.assertTrue((self.repo / "merged.txt").exists(), "the main checkout holds the base branch, so it moved too")

    def test_start_reads_the_checks_from_the_refreshed_base(self):
        other = self.remote()
        (other / "jtek.json").write_text(json.dumps({"checks": {"newer": f"{sys.executable} -c pass"}}))
        self.git("commit", "-q", "-am", "the merged change renames the check", cwd=other)
        self.git("push", "-q", "origin", "main", cwd=other)
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("checks: newer", out)

    def test_start_moves_a_base_that_is_not_checked_out(self):
        other = self.remote()
        self.merge_on_the_forge(other)
        self.git("checkout", "-q", "-b", "elsewhere")
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.worktree("T-1") / "merged.txt").exists())
        self.assertFalse((self.repo / "merged.txt").exists(), "the checkout on another branch is left alone")

    def test_start_says_so_when_both_sides_moved(self):
        other = self.remote()
        self.merge_on_the_forge(other)
        (self.repo / "local.txt").write_text("local\n")
        self.git("add", "local.txt")
        self.git("commit", "-q", "-m", "a local commit that was never pushed")
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("have each moved (1 and 1 commits)", out)
        self.assertFalse((self.worktree("T-1") / "merged.txt").exists())

    def test_start_refuses_and_keeps_no_claim_when_the_base_cannot_move(self):
        other = self.remote()
        self.merge_on_the_forge(other)
        (self.repo / "merged.txt").write_text("the human's own file, in the way\n")
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1, out)
        self.assertIn("could not be moved forward", out)
        self.assertEqual((self.repo / "merged.txt").read_text(), "the human's own file, in the way\n")
        (self.repo / "merged.txt").unlink()
        self.assertEqual(self.jtek("start", "T-1")[0], 0, "nothing was claimed by the refused start")

    def test_start_goes_on_without_the_remote(self):
        self.remote()
        self.git("remote", "set-url", "origin", str(Path(self.tmp.name) / "gone.git"))
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("could not fetch `main` from origin", out)

    def test_no_fetch_leaves_the_base_alone(self):
        other = self.remote()
        self.merge_on_the_forge(other)
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1", "--no-fetch")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.worktree("T-1") / "merged.txt").exists())

    def test_a_pull_request_that_waits_for_review_reaches_the_page(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        sha = self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(f"#!/bin/sh\necho OPEN {sha} pending\n")
        (bin_dir / "gh").chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        code, out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env={"PATH": path})
        self.assertIn("outcome: needs-review", out)
        self.assertIn("board: PR=https://forge.example/pr/1", out)
        self.assertEqual(self.field("T-1", "pr"), "https://forge.example/pr/1")
        self.assertEqual(self.field("T-1", "status"), "In Progress")

    def test_show_names_the_commit_under_review(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        sha = self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))
        self.assertIn(f"commit: {sha}", self.jtek("show", "T-1")[1])

    def test_evidence_can_be_checked_before_the_pull_request_is_opened(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        code, out = self.jtek("evidence", "T-1", "--file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("(1 seen, 0 not run)", out)
        bad = Path(self.tmp.name) / "bad.md"
        bad.write_text("It works.\n")
        code, out = self.jtek("evidence", "T-1", "--file", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("must account for every `Done when` item", out)
        self.assertFalse((self.repo / ".git" / "jtek" / "work" / "T-1" / "evidence.md").exists(), "the check saves nothing")


class SecondLoopRound(Scratch):
    """Places where sessions on real tickets had to guess what the script had done, or assemble what it could have given."""

    def test_start_says_what_happened_to_the_baseline(self):
        self.ticket("T-1")
        self.ticket("T-2")
        self.ticket("T-3")
        self.assertIn("baseline: test passed on main at ", self.jtek("start", "T-1")[1])
        self.assertIn("baseline: passed earlier on main at ", self.jtek("start", "T-2")[1])
        self.assertIn("baseline: skipped (--no-baseline)", self.jtek("start", "T-3", "--no-baseline")[1])

    def test_a_session_that_picks_a_question_up_is_told_what_was_asked(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.jtek("stop", "T-1", "--waiting", "input", "--note", "which limit counts as fast?")
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("jtek start: resumed", out)
        self.assertIn("asked: which limit counts as fast?", out)
        self.assertNotIn("baseline:", out)

    def test_a_resume_after_a_finish_has_no_question_to_repeat(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertNotIn("asked:", self.jtek("start", "T-1")[1])

    def test_show_names_the_base_and_the_main_checkout(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        out = self.jtek("show", "T-1")[1]
        self.assertIn("base: main", out)
        self.assertIn(f"main checkout: {self.repo}", out)

    def test_verdict_leaves_a_comment_ready_to_post(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        sha = self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(f"#!/bin/sh\necho OPEN {sha} pass\n")
        (bin_dir / "gh").chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env={"PATH": path})
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text(PASS_NOTES + "- to weigh: an empty value prints a tab\n")
        code, out = self.jtek("verdict", "T-1", "PASS+NOTES", "--by", "review-x", "--notes-file", str(notes))
        self.assertEqual(code, 0, out)
        comment = self.repo / ".git" / "jtek" / "work" / "T-1" / "review-comment.md"
        self.assertIn(f"comment file: {comment}", out)
        self.assertEqual(comment.read_text(), f"`verdict: PASS+NOTES by review-x @{sha[:7]}`\n\n{PASS_NOTES}- to weigh: an empty value prints a tab\n")
        code, out = self.jtek("verdict", "T-1", "PASS", "--by", "review-x")
        self.assertEqual(comment.read_text(), f"`verdict: PASS by review-x @{sha[:7]}`\n\n{PASS_NOTES}", "the notes of the earlier verdict are gone")

    def test_verdict_names_no_comment_file_without_a_pull_request(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.assertNotIn("comment file:", self.jtek("verdict", "T-1", "PASS", "--by", "review-x")[1])

    def test_an_attached_file_with_the_same_name_replaces_the_old_one(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        seen = Path(self.tmp.name) / "seen.txt"
        seen.write_text("first\n")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence(), "--attach", str(seen))
        seen.write_text("second\n")
        self.jtek("finish", "T-1", "--no-pr", "--attach", str(seen))
        folder = self.repo / ".git" / "jtek" / "work" / "T-1" / "evidence"
        self.assertEqual([p.name for p in folder.iterdir()], ["seen.txt"])
        self.assertEqual((folder / "seen.txt").read_text(), "second\n")


class ThirdLoopRound(Scratch):
    """A refusal that named the wrong remedy, met by a session that had just pushed."""

    def pushed_ticket(self):
        bare = Path(self.tmp.name) / "origin.git"
        self.git("clone", "-q", "--bare", str(self.repo), str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("fetch", "-q", "origin")
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        tree = self.worktree("T-1")
        self.git("push", "-q", "-u", "origin", "jtek/T-1", cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def slow_forge(self, sha, late_answers):
        """A `gh` that shows the old head for the first answers, as a forge does right after a push."""
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        count = Path(self.tmp.name) / "asked"
        (bin_dir / "gh").write_text(
            f"#!{sys.executable}\nfrom pathlib import Path\n"
            f"count = Path({str(count)!r})\nn = int(count.read_text()) if count.exists() else 0\ncount.write_text(str(n + 1))\n"
            f"print('OPEN', {'0' * 40!r} if n < {late_answers} else {sha!r}, 'pass')\n"
        )
        (bin_dir / "gh").chmod(0o755)
        return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "JTEK_PR_WAIT": "0"}

    def test_finish_waits_for_the_forge_to_show_a_commit_that_is_pushed(self):
        sha = self.pushed_ticket()
        env = self.slow_forge(sha, late_answers=2)
        code, out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: needs-review", out)

    def test_finish_says_the_forge_may_be_late_when_it_never_catches_up(self):
        sha = self.pushed_ticket()
        env = self.slow_forge(sha, late_answers=99)
        code, out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env=env)
        self.assertEqual(code, 1, out)
        self.assertIn("The branch is pushed, so the forge may only be late", out)
        self.assertNotIn("push the branch", out)

    def test_finish_does_not_wait_for_a_commit_that_was_never_pushed(self):
        sha = self.pushed_ticket()
        self.commit_change("T-1", "more.txt")
        self.jtek("check", "T-1")
        env = self.slow_forge(sha, late_answers=0)
        code, out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env=env)
        self.assertEqual(code, 1, out)
        self.assertIn("; push the branch", out)
        self.assertEqual((Path(self.tmp.name) / "asked").read_text(), "1", "one look is enough when the commit is not pushed")

    def test_the_word_of_a_verdict_agrees_with_its_notes(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        notes = Path(self.tmp.name) / "notes.md"

        def verdict(word, text):
            notes.write_text(text)
            return self.jtek("verdict", "T-1", word, "--by", "review-x", "--notes-file", str(notes))

        seen = PASS_NOTES + "- item 1 seen: ran it\n"
        finding = "Findings:\n- reproduces: crash on empty input\n  steps: run it with nothing\n"
        code, out = verdict("PASS+NOTES", seen)
        self.assertEqual(code, 1, out)
        self.assertIn("give PASS and keep --notes-file", out)
        self.assertEqual(verdict("PASS", seen)[0], 0)
        code, out = verdict("FAIL", seen)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL needs at least one finding", out)
        for word in ("PASS", "PASS+NOTES"):
            code, out = verdict(word, finding + "\nNotes:\n- to weigh: something\n")
            self.assertEqual(code, 1, out)
            self.assertIn("so the verdict is FAIL", out)
        self.assertEqual(verdict("FAIL", finding)[0], 0)
        self.assertEqual(verdict("PASS+NOTES", PASS_NOTES + "- to weigh: an empty value prints a tab\n")[0], 0)

    def test_a_pass_says_what_was_broken_and_why_the_change_is_safe(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("verdict", "T-1", "PASS", "--by", "review-x", "--bare")
        self.assertEqual(code, 1, out)
        self.assertIn("needs --notes-file", out)
        notes = Path(self.tmp.name) / "notes.md"
        for text, lacking in (("Findings: none\n- safe because: a fact (run 1)\n", "- broke:"),
                              ("Findings: none\n- broke: the branch; test failed\n", "- safe because:")):
            notes.write_text(text)
            code, out = self.jtek("verdict", "T-1", "PASS", "--by", "review-x", "--notes-file", str(notes))
            self.assertEqual(code, 1, out)
            self.assertIn(lacking, out)
        notes.write_text(PASS_NOTES)
        self.assertEqual(self.jtek("verdict", "T-1", "PASS", "--by", "review-x", "--notes-file", str(notes))[0], 0)

    def test_a_session_that_picks_a_ticket_up_is_told_the_last_verdict(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("Findings:\n- reproduces: crash on empty input\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "review-x", "--notes-file", str(notes))
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("last verdict: FAIL by review-x @", out)
        self.assertIn("(it is for the change as it is now)", out)
        self.assertIn("review notes: ", out)
        self.commit_change("T-1", "fix.txt")
        self.jtek("stop", "T-1", "--waiting", "approval", "--note", "may I?")
        self.board.set("T-1", Status="Todo")
        self.assertIn("(the change or the ticket has moved on since)", self.jtek("start", "T-1")[1])


class FifthLoopRound(Scratch):
    """A pull request that conflicts with its base, and a refusal that named the wrong remedy."""

    def forge(self, sha, mergeable):
        """A `gh` that answers the state query and the mergeable query apart."""
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "gh").write_text(
            f"#!{sys.executable}\nimport sys\n"
            f"print({mergeable!r} if 'mergeable' in sys.argv else 'OPEN {sha} pass')\n"
        )
        (bin_dir / "gh").chmod(0o755)
        return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def reviewed(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "review-x")
        return self.git("rev-parse", "HEAD", cwd=self.worktree("T-1"))

    def test_finish_refuses_a_pull_request_that_conflicts_with_the_base(self):
        sha = self.reviewed()
        args = ("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence())
        code, out = self.jtek(*args, env=self.forge(sha, "CONFLICTING"))
        self.assertEqual(code, 1, out)
        self.assertIn("conflicts with main", out)
        self.assertIn("jt-babysit", out)
        for answer in ("MERGEABLE", "UNKNOWN"):
            code, out = self.jtek(*args, env=self.forge(sha, answer))
            self.assertEqual(code, 0, out)

    def test_sync_says_when_an_open_pull_request_conflicts(self):
        sha = self.reviewed()
        self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env=self.forge(sha, "MERGEABLE"))
        self.assertIn("T-1\t-\topen, CI: pass\n", self.jtek("sync", env=self.forge(sha, "MERGEABLE"))[1])
        self.assertIn("open, CI: pass, conflicts with main", self.jtek("sync", env=self.forge(sha, "CONFLICTING"))[1])

    def test_a_pick_up_names_the_pull_request_and_its_conflict(self):
        sha = self.reviewed()
        self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env=self.forge(sha, "MERGEABLE"))
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1", env=self.forge(sha, "CONFLICTING"))
        self.assertEqual(code, 0, out)
        self.assertIn("pull request: https://forge.example/pr/1 It conflicts with main. Read its comments", out)

    def test_a_command_in_the_wrong_repository_says_where_it_looked(self):
        code, out = self.jtek("show", "T-9")
        self.assertEqual(code, 1)
        self.assertIn(f"T-9 is not started in this repository ({self.repo})", out)
        self.assertIn("run the command from there or from the ticket's worktree", out)

    def test_evidence_says_what_the_clean_up_removed(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        bare = Path(self.tmp.name) / "bare.md"
        bare.write_text("1. seen: ran it\n")
        code, out = self.jtek("evidence", "T-1", "--file", str(bare))
        self.assertEqual(code, 1, out)
        self.assertIn("no `clean-up:` line", out)
        bare.write_text("1. seen: ran it\n\nNotes:\n- Clean-up: removed a debug print in app.py\n")
        self.assertEqual(self.jtek("evidence", "T-1", "--file", str(bare))[0], 0)

    def test_a_second_finish_needs_no_arguments_without_a_pull_request(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.assertIn("outcome: needs-review", self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())[1])
        self.jtek("verdict", "T-1", "PASS", "--by", "review-x")
        code, out = self.jtek("finish", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: review", out)

    def test_a_pick_up_counts_the_fail_verdicts(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("Findings:\n- reproduces: crash\n")
        for n in range(1, 4):
            self.commit_change("T-1", f"f{n}.txt")
            self.jtek("check", "T-1")
            self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
            self.jtek("verdict", "T-1", "FAIL", "--by", "review-x", "--notes-file", str(notes))
            out = self.jtek("start", "T-1")[1]
            self.assertIn(f"FAIL verdicts so far: {n}", out)
        self.assertIn("That is three: stop with `--waiting input`", out)
        code, out = self.jtek("finish", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("the third or later on T-1 (3)", out)
        self.commit_change("T-1", "f4.txt")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 1, "a new commit does not buy a fourth round")
        self.assertIn("3 FAIL verdicts", out)
        self.assertIn("--waiting input", out)


class HeaderBlock(Scratch):
    """Only the lines right under the title are header lines. Text of the page cannot grant anything."""

    def start(self, text):
        path = Path(self.tmp.name) / "page.md"
        path.write_text(text)
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "https://board.example/1", "--from-file", str(path),
                               "--no-baseline"], cwd=self.repo, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def setUp(self):
        super().setUp()
        self.write_config({"test": f"{sys.executable} -c pass", "lint": f"{sys.executable} -c pass"})

    def test_a_line_below_the_header_is_text(self):
        for n, between in enumerate(("\n", "A note from the page\n", "\nA note from the page\n"), 1):
            code, out = self.start(f"# Thing\nid: T-{n}\nstatus: Todo\n{between}review: human\nchecks: lint\n\n" + BODY)
            self.assertEqual(code, 0, out)
            self.assertIn("checks: test, lint", out)
            self.assertIn("a verdict from a session that did not write the code is required", out)

    def test_header_lines_under_the_title_still_count(self):
        code, out = self.start("# Thing\n\nid: T-1\nstatus: Todo\nreview: human\nchecks: lint\n\n" + BODY)
        self.assertEqual(code, 0, out)
        self.assertIn("checks: lint", out)
        self.assertIn("human only", out)


class TicketCheck(Scratch):
    """A drafted ticket is checked the way `start` reads it, and nothing is claimed."""

    def check(self, text):
        path = Path(self.tmp.name) / "draft.md"
        path.write_text(text)
        proc = subprocess.run([sys.executable, str(SCRIPT), "ticket", str(path)], cwd=self.repo, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def test_a_good_draft_passes_and_nothing_is_claimed(self):
        code, out = self.check("# Add the thing\nkind: feature\n\n" + BODY + "- the other thing works\n")
        self.assertEqual(code, 0, out)
        self.assertIn("ticket: ok, 2 item(s) under Done when", out)
        self.assertFalse((self.repo / ".git" / "jtek" / "work").exists())

    def test_a_bad_draft_gets_the_refusal_start_would_give(self):
        code, out = self.check("# x\n\n## Goal\ng\n## Done when\n- a\n  - nested\n")
        self.assertEqual(code, 1)
        self.assertIn("only top-level list items", out)
        code, out = self.check("# x\nrepo: elsewhere\n\n" + BODY)
        self.assertEqual(code, 1)
        self.assertIn("is for `elsewhere`", out)


class LocalTickets(Scratch):
    """Work without a ticket: the session writes the ticket, so its header grants nothing."""

    LOCAL = "# Tidy the thing\nkind: feature\nreview: human\nchecks: test\nafter: T-9\n\n" + BODY + "## Out of scope\n- nothing else\n"

    def local(self, text=None, *extra):
        path = Path(self.tmp.name) / "local.md"
        path.write_text(text or self.LOCAL)
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "--local", "--from-file", str(path), *extra],
                              cwd=self.repo, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def meta(self, ticket_id):
        return json.loads((self.repo / ".git" / "jtek" / "work" / ticket_id / "meta.json").read_text())

    def test_a_local_ticket_gets_an_id_and_no_board_and_its_header_grants_nothing(self):
        self.write_config({"test": f"{sys.executable} -c pass", "lint": f"{sys.executable} -c pass"})
        code, out = self.local()
        self.assertEqual(code, 0, out)
        self.assertIn("id: LOCAL-1", out)
        self.assertIn("board: -", out)
        self.assertIn("checks: test, lint", out, "the session cannot pick a subset of the checks")
        self.assertTrue(self.meta("LOCAL-1")["review"], "`review: human` written by the session waives nothing")
        self.assertEqual(self.meta("LOCAL-1")["source"], "local, written by the session")

    def test_a_released_local_id_is_never_given_again(self):
        self.local()
        code, out = self.jtek("release", "LOCAL-1")
        self.assertEqual(code, 0, out)
        self.assertIn("A local ticket has no board", out)
        code, out = self.local()
        self.assertIn("id: LOCAL-2", out)

    def test_a_board_ticket_cannot_take_a_local_id_and_a_local_ticket_cannot_take_another(self):
        page = Path(self.tmp.name) / "page.md"
        page.write_text("# A page\nid: LOCAL-7\nstatus: Todo\n\n" + BODY)
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "https://example.invalid/p/7", "--from-file", str(page)],
                              cwd=self.repo, capture_output=True, text=True)
        code, out = proc.returncode, proc.stdout + proc.stderr
        self.assertEqual(code, 1)
        self.assertIn("only `start --local` uses one", out)
        code, out = self.local("id: T-3\n" + self.LOCAL)
        self.assertEqual(code, 1)
        self.assertIn("not `T-3`", out)
        code, out = self.local("id: LOCAL-5\n" + self.LOCAL)
        self.assertEqual(code, 1)
        self.assertIn("was never started here", out)

    def test_picking_a_local_ticket_up_again_does_not_reset_the_failed_runs(self):
        self.write_config({"test": f"{sys.executable} -c 'import sys; sys.exit(1)'"})
        self.local(None, "--no-baseline")
        self.jtek("check", "LOCAL-1")
        self.assertEqual(self.jtek("stop", "LOCAL-1", "--waiting", "input", "--note", "which one?")[0], 0)
        code, out = self.local("id: LOCAL-1\n" + self.LOCAL, "--no-baseline")
        self.assertEqual(code, 1, "the session that asked cannot answer itself")
        self.assertIn("--answered", out)
        code, out = self.local("id: LOCAL-1\n" + self.LOCAL, "--no-baseline", "--answered")
        self.assertEqual(code, 0, out)
        self.assertIn("resumed", out)
        checks = json.loads((self.repo / ".git" / "jtek" / "work" / "LOCAL-1" / "checks.json").read_text())
        self.assertEqual(checks["failed_runs"], 1, "only the human gives new tries")

    def test_one_file_skips_the_second_look_and_two_files_do_not(self):
        self.local()
        self.commit_change("LOCAL-1")
        self.jtek("check", "LOCAL-1")
        code, out = self.jtek("finish", "LOCAL-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertIn("outcome: review", out)
        self.assertIn("verdict: skipped: work without a ticket that changed one file", out)
        self.assertIn("board: -", out)
        self.commit_change("LOCAL-1", "second.txt")
        self.jtek("check", "LOCAL-1")
        code, out = self.jtek("finish", "LOCAL-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)

    def test_one_file_on_the_attention_line_still_needs_a_verdict(self):
        self.local()
        tree = self.worktree("LOCAL-1")
        (tree / "jtek.json").write_text("{}\n")
        self.git("commit", "-q", "-am", "config", cwd=tree)
        self.jtek("check", "LOCAL-1")
        code, out = self.jtek("finish", "LOCAL-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)


class RecordedRuns(Scratch):
    """`seen:` lines that point at what was really run, so neither the author nor a reader has to trust a paraphrase."""

    def started(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        return self.worktree("T-1")

    def test_a_run_keeps_the_command_the_exit_code_and_the_output(self):
        tree = self.started()
        code, out = self.jtek("run", "T-1", "--", sys.executable, "-c", "import sys; print('hello'); sys.exit(3)")
        self.assertEqual(code, 0, out)
        record = (self.repo / ".git" / "jtek" / "work" / "T-1" / "runs" / "1.txt").read_text()
        self.assertIn("run: 1", record)
        self.assertIn("-c 'import sys; print('\"'\"'hello'\"'\"'); sys.exit(3)'", record)
        self.assertIn(f"cwd: {tree}", record)
        self.assertIn("exit: 3", record)
        self.assertIn("hello", record)
        self.assertIn("Cite it in the evidence as (run 1)", out)

    def test_a_shell_line_and_another_folder(self):
        self.started()
        self.jtek("run", "T-1", "--sh", "printf 'a b\\n' | wc -w", "--cwd", str(self.repo))
        record = (self.repo / ".git" / "jtek" / "work" / "T-1" / "runs" / "1.txt").read_text()
        self.assertIn("command: printf 'a b\\n' | wc -w", record)
        self.assertIn(f"cwd: {self.repo}", record)
        self.assertIn("exit: 0", record)
        self.assertRegex(record, r"--- stdout ---\n\s*2\n--- stderr ---\n$")
        self.assertIn(f"cwd: {self.repo} (at commit ", record)
        self.assertIn("(of the worktree, not of that folder)", record)
        code, out = self.jtek("run", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("not both and not neither", out)

    def test_a_run_outside_any_repository_says_so(self):
        self.started()
        outside = Path(self.tmp.name).resolve() / "inputs"
        outside.mkdir()
        self.jtek("run", "T-1", "--cwd", str(outside), "--", sys.executable, "-c", "print(1)")
        record = (self.repo / ".git" / "jtek" / "work" / "T-1" / "runs" / "1.txt").read_text()
        self.assertIn(f"cwd: {outside} (at commit none: not in a git repository)", record)

    def test_a_check_gets_no_input(self):
        self.write_config({"test": f"{sys.executable} -c \"import sys; sys.exit(1 if sys.stdin.read() else 0)\""})
        self.started()
        proc = subprocess.run([sys.executable, str(SCRIPT), "check", "T-1"], cwd=self.repo, input="typed\n",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_evidence_may_cite_only_runs_that_were_recorded(self):
        self.started()
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 2)\n- clean-up: nothing to remove\n")
        code, out = self.jtek("evidence", "T-1", "--file", str(evidence))
        self.assertEqual(code, 1)
        self.assertIn("cites run 2, which `jtek.py run` never finished recording", out)
        evidence.write_text("1. seen: printed 1 (run 1)\n- clean-up: nothing to remove\n")
        self.assertEqual(self.jtek("evidence", "T-1", "--file", str(evidence))[0], 0)

    def test_the_result_counts_the_seen_lines_that_cite_a_run(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 1)\n- clean-up: nothing to remove\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("(1 seen, 0 not run, 1 of the seen cite a recorded run, clean-up cites no recorded diff)", out)

    def test_a_command_outside_any_repository_says_where_to_run_it(self):
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        code, out = self.jtek("show", "T-1", cwd=outside)
        self.assertEqual(code, 1)
        self.assertIn("is not inside a git repository. Run jtek.py from the ticket's repository or its worktree", out)

    def test_the_result_says_whether_the_clean_up_rests_on_a_recorded_diff(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        self.jtek("run", "T-1", "--", "git", "diff", "main...HEAD")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 1)\n- clean-up: nothing to remove (run 2)\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("1 of the seen cite a recorded run, clean-up rests on a recorded diff)", out)

    def test_the_result_names_a_seen_line_whose_run_is_older_than_the_code(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        self.commit_change("T-1", "test_feature.py")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(2)")
        self.commit_change("T-1", "app.py")
        self.jtek("check", "T-1")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 1)\n2. seen: printed 2 (run 2)\n- clean-up: nothing to remove\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("item 1 rests on a run before the last code change", out)
        self.assertIn("item 2 rests on a run before the last code change", out)

    def test_a_run_before_a_change_to_tests_only_still_stands(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        self.commit_change("T-1", "test_feature.py")
        self.commit_change("T-1", "NOTES.md")
        self.jtek("check", "T-1")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 1)\n- clean-up: nothing to remove\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertNotIn("rests on a run", out)

    def test_the_result_names_a_seen_line_whose_run_had_uncommitted_files(self):
        tree = self.started()
        (tree / "app.py").write_text("x\n")
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        self.git("add", "app.py", cwd=tree)
        self.git("commit", "-q", "-m", "work", cwd=tree)
        self.jtek("check", "T-1")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: printed 1 (run 1)\n- clean-up: nothing to remove\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("item 1 rests on a run with uncommitted files", out)

    def test_a_citation_may_name_several_runs_with_words_between(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        for _ in range(7):
            self.jtek("run", "T-1", "--", sys.executable, "-c", "print(1)")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: the list, as before (run 7 stand-in, run 5 real service)\n- clean-up: nothing (run 1)\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("1 of the seen cite a recorded run", out)
        evidence.write_text("1. seen: the list (run 7 stand-in, run 9 real service)\n- clean-up: nothing (run 1)\n")
        self.assertIn("cites run 9", self.jtek("evidence", "T-1", "--file", str(evidence))[1])

    def test_a_run_keeps_stdout_and_stderr_apart(self):
        self.started()
        self.jtek("run", "T-1", "--", sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)")
        record = (self.repo / ".git" / "jtek" / "work" / "T-1" / "runs" / "1.txt").read_text()
        self.assertIn("--- stdout ---\nout\n--- stderr ---\nerr\n", record)
        self.assertEqual(sorted(p.name for p in (self.repo / ".git" / "jtek" / "work" / "T-1" / "runs").iterdir()), ["1.txt"])

    def test_the_board_comment_is_written_out_ready_to_paste(self):
        self.started()
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.jtek("verdict", "T-1", "PASS", "--by", "review-x")
        out = self.jtek("finish", "T-1")[1]
        comment = self.repo / ".git" / "jtek" / "work" / "T-1" / "board-comment.md"
        self.assertIn(f"comment file: {comment}\nboard: Status=Review", out)
        self.assertEqual(comment.read_text(), out + "\n" + Path(self.evidence()).read_text())


class OutsideReview(Scratch):
    """Defects an outside review of 26.19.0 reproduced."""

    def ready(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        return self.worktree("T-1")

    def test_a_tag_named_like_the_base_does_not_stand_in_for_it(self):
        self.write_config({"test": f"{sys.executable} -c \"import sys; sys.exit(1)\""})
        self.ticket("T-1")
        self.jtek("start", "T-1", "--no-baseline")
        tree = self.worktree("T-1")
        (tree / "jtek.json").write_text(json.dumps({"checks": {"test": f"{sys.executable} -c pass"}}))
        self.git("commit", "-q", "-am", "loosen the check", cwd=tree)
        self.git("tag", "main", cwd=tree)
        self.commit_change("T-1")
        code, out = self.jtek("check", "T-1")
        self.assertEqual(code, 1, "the check came from the tag, not from the base branch")
        self.assertIn("jtek.json", self.jtek("show", "T-1")[1] + self.git("diff", "refs/heads/main...HEAD", "--stat", cwd=tree))

    def test_a_verdict_is_for_the_commit_the_reviewer_read(self):
        tree = self.ready()
        read = self.git("rev-parse", "HEAD", cwd=tree)
        self.commit_change("T-1", "later.txt")
        code, out = self.jtek("verdict", "T-1", "PASS", "--by", "review-x", "--commit", read)
        self.assertEqual(code, 1)
        self.assertIn("the author committed during your review", out)
        code, out = self.jtek("verdict", "T-1", "PASS", "--by", "review-x", "--commit", "")
        self.assertEqual(code, 1)

    def test_an_earlier_run_may_be_cited_such_as_the_reproduction_before_the_fix(self):
        tree = self.ready()
        self.jtek("run", "T-1", "--", sys.executable, "-c", "print('the bug')")
        self.commit_change("T-1", "fix.txt")
        self.jtek("check", "T-1")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: before the fix it printed the bug (run 1)\n- clean-up: nothing to remove\n")
        self.assertEqual(self.jtek("evidence", "T-1", "--file", str(evidence))[0], 0)

    def test_only_what_the_ticket_asks_decides_whether_it_changed(self):
        tree = self.ready()
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.jtek("verdict", "T-1", "PASS", "--by", "review-x")
        self.jtek("stop", "T-1", "--waiting", "input", "--note", "merge now?")
        self.board.pages["T-1"]["body"] += "\n## Notes\nAnswer from the human: yes.\n"
        self.board.set("T-1", Status="Todo")
        self.jtek("start", "T-1")
        self.assertIn("outcome: review", self.jtek("finish", "T-1", "--no-pr")[1])

    def test_a_run_that_never_finished_cannot_be_cited_and_finish_does_not_crash(self):
        self.ready()
        runs = self.repo / ".git" / "jtek" / "work" / "T-1" / "runs"
        runs.mkdir(exist_ok=True)
        (runs / "1.txt").write_text("")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: it ran\n- clean-up: nothing to remove (run 1)\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))
        self.assertEqual(code, 1)
        self.assertIn("never finished recording", out)
        self.assertNotIn("Traceback", out)

    def test_the_clean_up_rests_only_on_a_diff_that_ran_and_is_current(self):
        self.ready()
        self.jtek("run", "T-1", "--sh", "echo git diff")
        self.jtek("run", "T-1", "--", "git", "diff", "no-such-ref")
        evidence = Path(self.tmp.name) / "e.md"
        evidence.write_text("1. seen: it ran\n- clean-up: nothing to remove (runs 1 and 2)\n")
        out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))[1]
        self.assertIn("clean-up cites no recorded diff", out)

    def test_the_human_setting_todo_resets_the_fail_count_and_one_commit_counts_once(self):
        tree = self.ready()
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("Findings:\n- reproduces: crash\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "review-x", "--notes-file", str(notes))
        self.jtek("verdict", "T-1", "FAIL", "--by", "review-x", "--notes-file", str(notes))
        meta = json.loads((self.repo / ".git" / "jtek" / "work" / "T-1" / "meta.json").read_text())
        self.assertEqual(meta["fails"], 1, "two FAILs on one commit are one round")
        self.jtek("stop", "T-1", "--waiting", "input", "--note", "which way?")
        self.board.set("T-1", Status="Todo")
        self.assertNotIn("FAIL verdicts so far", self.jtek("start", "T-1")[1])

    def test_an_unread_link_is_refused_while_the_branch_is_pushed_nowhere(self):
        self.git("remote", "add", "origin", str(Path(self.tmp.name) / "nowhere.git"))
        tree = self.ready()
        empty = Path(self.tmp.name) / "empty-bin"
        empty.mkdir()
        path = f"{empty}{os.pathsep}/usr/bin{os.pathsep}/bin"
        out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env={"PATH": path})[1]
        self.assertIn("could not be read, and the branch is not pushed", out)

    def test_a_closed_pull_request_is_not_told_to_push(self):
        tree = self.ready()
        sha = self.git("rev-parse", "HEAD", cwd=tree)
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(f"#!/bin/sh\necho CLOSED {sha} pass\n")
        (bin_dir / "gh").chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        out = self.jtek("finish", "T-1", "--pr", "https://forge.example/pr/1", "--evidence-file", self.evidence(), env={"PATH": path})[1]
        self.assertIn("is CLOSED, so it cannot take this change. Open a new pull request", out)
        self.assertNotIn("push the branch", out)

    def test_a_kept_branch_with_no_commit_of_its_own_starts_from_the_new_base(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.jtek("release", "T-1")
        (self.repo / "later.txt").write_text("merged meanwhile\n")
        self.git("add", "later.txt")
        self.git("commit", "-q", "-m", "merged meanwhile")
        self.board.set("T-1", Status="Todo")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.worktree("T-1") / "later.txt").exists(), "the ticket started on the old base")
        self.assertIn("baseline: ", out)
        self.assertNotIn("baseline: skipped", out)

    def test_a_branch_with_its_own_commit_is_still_kept(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("release", "T-1")
        self.assertNotEqual(self.git("branch", "--list", "jtek/T-1"), "")


class NextTests(Scratch):
    def next(self):
        code, out = self.jtek("next")
        self.assertEqual(code, 0, out)
        return {line.split("\t")[0]: line.split("\t")[1:] for line in out.splitlines()}

    def test_next_follows_a_ticket_from_todo_to_review(self):
        self.ticket("T-1")
        self.assertEqual(self.next()["T-1"], ["work", "new"])
        self.jtek("start", "T-1")
        self.assertEqual(self.next()["T-1"][0], "running")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(self.next()["T-1"][0], "review")
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: crash on empty input\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))
        self.assertEqual(self.next()["T-1"], ["work", "the verdict is FAIL; the findings are in the review notes"])
        self.jtek("start", "T-1")
        self.commit_change("T-1", "fix.txt")
        self.jtek("check", "T-1")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(self.next()["T-1"][0], "review", "a verdict for the old change does not count")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertEqual(self.next()["T-1"], ["work", "the verdict is in; finish"])
        self.jtek("start", "T-1")
        self.jtek("finish", "T-1", "--no-pr")
        self.assertEqual(self.next()["T-1"][0], "human")

    def test_next_waits_for_the_human_and_for_other_tickets(self):
        self.ticket("T-1")
        self.ticket("T-2", extra="after: T-1\n")
        self.ticket("T-3", status="Backlog")
        self.ticket("T-4", extra="repo: api\n")
        self.ticket("T-5", status="In Progress")
        found = self.next()
        self.assertEqual(found["T-2"], ["hold", "comes after T-1"])
        self.assertEqual(found["T-3"][0], "hold")
        self.assertNotIn("T-4", found)
        self.assertEqual(found["T-5"][0], "elsewhere")
        self.jtek("start", "T-1")
        self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")
        self.assertEqual(self.next()["T-1"][0], "human")
        self.board.set("T-1", Waiting="")
        self.assertEqual(self.next()["T-1"][0], "board", "the question never reached the page, so no session starts")
        self.board.set("T-1", Status="Todo")
        self.assertEqual(self.next()["T-1"], ["work", "the human answered, or asked for rework"])

    def test_next_says_board_when_the_page_missed_a_result(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.board.set("T-1", Status="In Progress")  # the session ended before it wrote the page
        self.assertEqual(self.next()["T-1"][0], "board")


class FileBoard(Scratch):
    """A repository whose jtek.json names no board: the tickets are files beside it, and the file is the page."""

    DRAFT = "# Tidy the thing\nkind: feature\n\n" + BODY + "## Out of scope\n- nothing else\n"

    def raw(self, *args):
        """Run jtek.py as typed: no page link, no board file."""
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def folder(self):
        return self.repo.parent / "app.jtek" / "_tickets"

    def save(self, text=None):
        draft = Path(self.tmp.name) / "draft.md"
        draft.write_text(text or self.DRAFT)
        return self.raw("ticket", str(draft), "--save")

    def write(self, ticket_id, **fields):
        """What the human, or a session following a `board:` line, writes in the header of a ticket file."""
        path = self.folder() / f"{ticket_id}.md"
        lines = path.read_text().splitlines()
        for key, value in fields.items():
            lines = [line for line in lines if not line.startswith(f"{key}:")]
            if value:
                lines.insert(2, f"{key}: {value}")
        path.write_text("\n".join(lines) + "\n")

    def test_save_gives_the_next_id_and_backlog_whatever_the_draft_says(self):
        code, out = self.save("# One\nid: X-9\nstatus: Todo\nkind: bug\n\n" + BODY)
        self.assertEqual(code, 0, out)
        self.assertIn(f"saved: {self.folder() / 'T-1.md'}", out)
        text = (self.folder() / "T-1.md").read_text()
        self.assertTrue(text.startswith("# One\nid: T-1\nstatus: Backlog\nkind: bug\n\n## Goal"), text)
        self.assertNotIn("X-9", text)
        self.assertNotIn("Todo", text)
        self.assertIn("T-2.md", self.save()[1])

    def test_save_is_refused_with_a_board_and_for_a_draft_start_would_refuse(self):
        code, out = self.save("# No items\n\n## Goal\nSomething.\n")
        self.assertEqual(code, 1)
        self.assertFalse(self.folder().exists(), "a draft that is refused is not saved")
        self.write_config({"test": f"{sys.executable} -c pass"}, board="https://www.notion.so/x")
        code, out = self.save()
        self.assertEqual(code, 1)
        self.assertIn("create the ticket there", out)
        self.assertFalse(self.folder().exists())

    def test_a_released_file_id_is_never_given_again(self):
        self.save()
        self.write("T-1", status="Todo")
        self.assertEqual(self.raw("start", "T-1")[0], 0)
        self.assertEqual(self.raw("release", "T-1")[0], 0)
        (self.folder() / "T-1.md").unlink()
        self.assertIn("T-2.md", self.save()[1])

    def test_start_reads_the_ticket_file_and_only_the_human_releases_it(self):
        self.save()
        code, out = self.raw("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("not Todo", out)
        self.write("T-1", status="Todo")
        code, out = self.raw("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn(f"page: {self.folder() / 'T-1.md'}", out)
        self.assertIn("board: Status=In Progress; Waiting=", out)
        self.assertTrue(self.worktree("T-1").is_dir())
        code, out = self.raw("start", "T-7")
        self.assertEqual(code, 1)
        self.assertIn("there is no ticket file", out)

    def test_a_question_waits_for_the_human_to_write_todo_in_the_file(self):
        self.save()
        self.write("T-1", status="Todo")
        self.raw("start", "T-1")
        self.write("T-1", status="In Progress")
        code, out = self.raw("stop", "T-1", "--waiting", "input", "--note", "which one?")
        self.assertEqual(code, 0, out)
        self.assertIn("board: Waiting=input; comment=result", out)
        self.write("T-1", waiting="input")
        code, out = self.raw("start", "T-1")
        self.assertEqual(code, 1, "the session that asked cannot answer itself")
        self.assertIn("stopped with a question", out)
        self.write("T-1", status="Todo")
        code, out = self.raw("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("asked: which one?", out)
        self.assertIn("answer: on the page", out)

    def test_after_counts_an_id_only_while_its_file_is_not_done(self):
        self.save()
        self.save("# Two\nkind: feature\nafter: T-1\n\n" + BODY)
        self.write("T-2", status="Todo")
        code, out = self.raw("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("T-2 comes after T-1, which is not Done", out)
        self.assertIn("T-2\thold\tcomes after T-1", self.raw("next")[1])
        self.write("T-1", status="Done")
        self.assertIn("T-2\twork\tnew", self.raw("next")[1])
        code, out = self.raw("start", "T-2")
        self.assertEqual(code, 0, out)

    def test_a_log_in_a_code_block_is_not_part_of_the_ticket(self):
        self.save()
        self.write("T-1", status="Todo")
        self.raw("start", "T-1")
        work = self.repo / ".git" / "jtek" / "work" / "T-1"
        before = (work / "ticket.md").read_text().split("## Goal", 1)[1]
        self.raw("stop", "T-1", "--waiting", "input", "--note", "which one?")
        path = self.folder() / "T-1.md"
        path.write_text(path.read_text() + "\n## Log\n\n```\n## Goal\noutcome: needs-human\n```\n\nUse the first one.\n")
        code, out = self.raw("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("resumed", out)
        self.assertIn(before.split("## Log")[0].strip(), (work / "ticket.md").read_text())

    def test_next_and_sync_read_the_ticket_files(self):
        code, out = self.raw("next")
        self.assertEqual(code, 0, out)
        self.assertIn("no ticket files in", out)
        self.save()
        self.save()
        self.write("T-2", status="Todo")
        code, out = self.raw("next")
        self.assertEqual(code, 0, out)
        self.assertIn("T-1\thold\tnot released", out)
        self.assertIn("T-2\twork\tnew", out)
        self.write("T-2", status="Review")
        code, out = self.raw("sync")
        self.assertEqual(code, 0, out)
        self.assertIn("T-2\t-\tno pull request on the page", out)

    def test_with_a_board_the_page_and_the_board_file_are_still_needed(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, board="https://www.notion.so/x")
        for command in (("start", "T-1"), ("next",), ("sync",)):
            code, out = self.raw(*command)
            self.assertEqual(code, 1, command)
            self.assertIn("--from-file" if command[0] == "start" else "--board-file", out)

    def test_a_local_question_is_answered_in_the_chat_and_a_board_one_on_the_page(self):
        local = Path(self.tmp.name) / "local.md"
        local.write_text(self.DRAFT)
        self.assertEqual(self.raw("start", "--local", "--from-file", str(local))[0], 0)
        self.raw("stop", "LOCAL-1", "--waiting", "input", "--note", "which one?")
        code, out = self.raw("finish", "LOCAL-1", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("answers in the chat; then start again with --local --answered", out)
        local.write_text("id: LOCAL-1\n" + self.DRAFT)
        code, out = self.raw("start", "--local", "--from-file", str(local), "--answered")
        self.assertEqual(code, 0, out)
        self.assertIn("answer: in the chat", out)
        self.assertNotIn("on the page", out)
        self.ticket("T-5")
        self.jtek("start", "T-5")
        self.jtek("stop", "T-5", "--waiting", "input", "--note", "which one?")
        code, out = self.jtek("finish", "T-5", "--no-pr")
        self.assertEqual(code, 1)
        self.assertIn("answers on the page and sets Status to Todo", out)
        self.board.set("T-5", Status="Todo")
        code, out = self.jtek("start", "T-5")
        self.assertEqual(code, 0, out)
        self.assertIn("answer: on the page", out)


class DoctorTests(Scratch):
    def test_doctor_names_what_is_missing_in_order(self):
        code, out = self.jtek("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("ok       no board: the tickets are files in", out)
        self.assertNotIn("not checked: the board", out)
        self.assertNotIn("write a ticket on the board", out)
        self.assertIn("ready: this repository needs no board", out)
        self.write_config({"test": f"{sys.executable} -c pass", "lint": ""}, board="https://www.notion.so/x")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 1)
        self.assertIn("checks without a command: lint", out)

    def test_doctor_says_ready_and_what_is_optional(self):
        self.write_config({"test": f"{sys.executable} -c pass"}, board="https://www.notion.so/x")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("ok       checks: test", out)
        self.assertIn("optional .jtek/verify.md on main", out)
        self.assertIn("ready: write a ticket", out)

    def test_doctor_without_a_config_says_how_to_start(self):
        self.git("rm", "-q", "jtek.json")
        self.git("commit", "-q", "-m", "drop")
        code, out = self.jtek("doctor")
        self.assertEqual(code, 1)
        self.assertIn("run `jtek.py init`", out)


if __name__ == "__main__":
    unittest.main()
