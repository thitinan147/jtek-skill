"""Behaviour of jtek.py against a scratch git repository. tests/board.py stands in for Notion and for the agent's Notion tool."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from board import Board  # noqa: E402

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
        path.write_text("1. seen: ran the thing, it works\n")
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
        self.fake_gh("OPEN 0000000000000000000000000000000000000000")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 1)
        self.assertIn("push the branch", out)
        self.fake_gh("OPEN " + self.git("rev-parse", "HEAD", cwd=self.worktree("T-1")))
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
        honest.write_text("1. not run: the app needs a database I do not have\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(honest))
        self.assertEqual(code, 0, out)
        self.assertIn("(0 seen, 1 not run)", out)

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
        fake.write_text('#!/bin/sh\ncase "$3" in *merged) echo MERGED abc;; *) echo OPEN abc;; esac\n')
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
        proc = subprocess.run([sys.executable, str(SCRIPT), "start", "T-1"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--from-file", proc.stderr)

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


class ReviewFindings(Scratch):
    """One test per defect that an outside review of 26.1.0 found."""

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

    def next(self):
        return {line.split("\t")[0]: line.split("\t")[1:] for line in self.jtek("next")[1].splitlines()}

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

    def test_a_pass_removes_the_notes_of_an_earlier_fail(self):
        self.to_needs_review()
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("- reproduces: crash\n")
        self.jtek("verdict", "T-1", "FAIL", "--by", "reviewer", "--notes-file", str(notes))
        review = self.repo / ".git" / "jtek" / "work" / "T-1" / "review.md"
        self.assertTrue(review.exists())
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.assertFalse(review.exists())

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
        code, out = self.run_next([{"id": 12, "status": "todo"}, {"id": "T-2", "status": "In progress", "after": 5}])
        self.assertEqual(code, 0, out)
        self.assertIn("12\twork\tnew", out)
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
        self.assertIn("checks that use shell operators: test", out)

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


class DoctorTests(Scratch):
    def test_doctor_names_what_is_missing_in_order(self):
        code, out = self.jtek("doctor")
        self.assertEqual(code, 1, out)
        self.assertIn("missing  `board`: the Notion database link", out)
        self.assertIn("not checked: Notion", out)
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
