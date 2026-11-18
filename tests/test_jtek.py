"""Behaviour of jtek.py against a scratch git repository and a stand-in for the Notion board."""
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
from fake_notion import FakeNotion  # noqa: E402

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
        self.board = FakeNotion().start()
        self.addCleanup(self.board.stop)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.write_config({"test": f"{sys.executable} -c pass"})

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def write_config(self, checks, **extra):
        (self.repo / "jtek.json").write_text(json.dumps({"notion": self.board.database, "checks": checks, **extra}))
        self.git("add", "jtek.json")
        self.git("commit", "-q", "-m", "checks")

    def jtek(self, *args, cwd=None, env=None):
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("JTEK_")}, **self.board.env(), **(env or {})}
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.repo,
                              capture_output=True, text=True, env=env)
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
        number = int(ticket_id.split("-")[1])
        if any(page["number"] == number for page in self.board.pages.values()):
            self.board.set(ticket_id, Status=status, **props)
        else:
            self.board.add(f"Ticket {ticket_id}", status, body, number, after, **props)
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
        self.assertIn("still waiting for input", out)
        self.board.set("T-1", Waiting="")
        self.assertEqual(self.jtek("start", "T-1", "--resume")[0], 0)
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
        self.board.set("T-1", Waiting="")  # the human answered on the page
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
        self.board.by_id("T-1")["blocks"].append({"type": "bulleted_list_item", "text": "also handle empty input"})
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
        self.board.set("T-1", Waiting="")
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

    def test_there_is_no_command_that_releases_or_merges(self):
        code, out = self.jtek("--help")
        self.assertEqual(code, 0)
        for word in ("merge", "approve", "todo"):
            self.assertNotIn(word, out.lower().replace("jtek never merges", ""))


class BoardTests(Scratch):
    def test_list_groups_by_status(self):
        self.ticket("T-1", extra="area: billing\n")
        self.ticket("T-2", status="Backlog")
        _, out = self.jtek("list")
        self.assertIn("[area: billing]", out)
        self.assertIn("Todo (1)", out)
        self.assertIn("Backlog (1)", out)
        self.assertNotIn("Done (", out)
        self.assertIn("Done and Cancelled tickets are not listed", out)

    def test_sync_sets_done_only_when_the_forge_says_merged(self):
        merged = self.ticket("T-1", status="Review", extra="pr: https://example.invalid/pr/merged\n")
        still_open = self.ticket("T-2", status="Review", extra="pr: https://example.invalid/pr/open\n")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text('#!/bin/sh\ncase "$3" in *merged) echo MERGED abc;; *) echo OPEN abc;; esac\n')
        fake.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        self.assertEqual(self.jtek("list")[0], 0)
        self.assertEqual(self.field(merged, "status"), "Review", "list without --sync changes nothing")
        self.assertEqual(self.jtek("list", "--sync")[0], 0)
        self.assertEqual(self.field(merged, "status"), "Done")
        self.assertEqual(self.field(still_open, "status"), "Review")

    def test_sync_removes_the_worktree_of_a_done_ticket(self):
        path = self.ticket("T-1")
        self.jtek("start", "T-1")
        self.assertTrue(self.worktree("T-1").is_dir())
        self.board.set(path, Status="Done")
        self.assertEqual(self.jtek("list", "--sync")[0], 0)
        self.assertFalse(self.worktree("T-1").exists())
        dirty = self.ticket("T-2")
        self.jtek("start", "T-2")
        (self.worktree("T-2") / "left.txt").write_text("x")
        self.board.set(dirty, Status="Done")
        self.jtek("list", "--sync")
        self.assertTrue(self.worktree("T-2").is_dir(), "uncommitted work is never removed")

    def test_release_refuses_uncommitted_work(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        (self.worktree("T-1") / "wip.txt").write_text("x")
        code, _ = self.jtek("release", "T-1")
        self.assertEqual(code, 1)
        self.assertTrue(self.worktree("T-1").is_dir())


class NotionTests(Scratch):
    def to_review(self, ticket_id="T-1"):
        self.commit_change(ticket_id)
        self.jtek("check", ticket_id)
        self.jtek("verdict", ticket_id, "PASS", "--by", "reviewer")
        return self.jtek("finish", ticket_id, "--no-pr", "--evidence-file", self.evidence())

    def test_start_by_page_link_and_the_source_names_the_test_board(self):
        self.ticket("T-1")
        link = self.board.render(self.board.by_id("T-1"))["url"]
        code, out = self.jtek("start", link)
        self.assertEqual(code, 0, out)
        self.assertIn("id: T-1", out)
        _, out = self.to_review()
        self.assertIn(f"source: {link} (test board at {self.board.url()})", out)

    def test_no_token_is_refused_before_any_request(self):
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1", env={"NOTION_TOKEN": ""})
        self.assertEqual(code, 1)
        self.assertIn("NOTION_TOKEN is not set", out)
        self.assertEqual(self.board.requests, [])

    def test_the_token_only_goes_to_notion_or_to_this_machine(self):
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1", env={"JTEK_NOTION_API": "https://example.invalid"})
        self.assertEqual(code, 1)
        self.assertIn("may only point at this machine", out)

    def test_checks_and_setup_do_not_get_the_token(self):
        seen = Path(self.tmp.name) / "seen"
        code = f"import os;open(r'{seen}','a').write(os.environ.get('NOTION_TOKEN','none')+' ')"
        self.write_config({"test": f'{sys.executable} -c "{code}"'}, setup=f'{sys.executable} -c "{code}"')
        self.ticket("T-1")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.jtek("check", "T-1")
        self.assertEqual(seen.read_text().split(), ["none", "none", "none"])

    def test_page_text_cannot_set_a_ticket_field(self):
        self.ticket("T-1", body="review: human\nchecks: nothing\n## Goal\nreview: human\n## Done when\n- it works\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("a verdict from a session that did not write the code is required", out)
        self.assertIn("checks: test", out)
        snapshot = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertLess(snapshot.index("## Notes"), snapshot.index("review: human"))

    def test_done_when_takes_only_plain_list_items(self):
        self.ticket("T-1", body="## Goal\nx\n## Done when\n- it works\nand it is fast\n")
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("`Done when` on the page has a paragraph block", out)
        self.ticket("T-2", body=[{"type": "heading_2", "text": "Goal"}, {"type": "paragraph", "text": "x"},
                                 {"type": "heading_2", "text": "Done when"},
                                 {"type": "bulleted_list_item", "text": "it works", "children": True}])
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("an item with nested content", out)
        self.assertEqual(self.field("T-2", "status"), "Todo")

    def test_a_block_that_is_not_copied_is_named_in_the_ticket(self):
        self.ticket("T-1", body=[{"type": "heading_2", "text": "Goal"}, {"type": "image"},
                                 {"type": "heading_2", "text": "Done when"},
                                 {"type": "to_do", "text": "it works"}])
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        snapshot = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertIn("[a image block is not copied here", snapshot)
        self.assertIn("- it works", snapshot)

    def test_a_long_page_body_is_read_in_full(self):
        self.board.page_size = 2
        self.ticket("T-1", body="## Goal\na\nb\nc\n## Done when\n- one\n- two\n- three\n")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        snapshot = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertIn("- three", snapshot)

    def test_a_board_without_a_property_is_refused_by_name(self):
        self.ticket("T-1")
        self.board.missing = ["Waiting", "PR"]
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("`Waiting` (select), `PR` (url)", out)

    def test_a_page_outside_the_board_is_refused(self):
        self.ticket("T-1")
        page = self.board.by_id("T-1")
        page["foreign"] = True
        code, out = self.jtek("start", page["id"])
        self.assertEqual(code, 1)
        self.assertIn("is not a page of the board database", out)

    def test_a_database_with_two_data_sources_is_refused(self):
        self.ticket("T-1")
        self.board.sources = 2
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("exactly one data source", out)

    def test_after_holds_across_repositories(self):
        self.ticket("T-1", extra="repo: api\n")
        self.ticket("T-2", extra="repo: app\nafter: T-1\n")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("T-2 comes after T-1, which is `Todo`, not Done", out)
        self.board.set("T-1", Status="Done")
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 0, out)

    def test_a_failed_write_at_start_gives_the_claim_back(self):
        self.ticket("T-1")
        self.board.fail("PATCH", "/v1/pages", 500)
        code, out = self.jtek("start", "T-1")
        self.assertEqual(code, 1)
        self.assertIn("Notion refused PATCH", out)
        self.assertFalse(self.worktree("T-1").exists())
        self.assertEqual(self.field("T-1", "status"), "Todo")
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertEqual(self.field("T-1", "status"), "In Progress")

    def test_a_rate_limit_is_waited_out(self):
        self.ticket("T-1")
        self.board.fail("GET", "/v1/blocks", 429, times=2)
        self.assertEqual(self.jtek("start", "T-1")[0], 0)

    def test_review_puts_the_result_and_the_evidence_on_the_page(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        code, out = self.jtek("finish", "T-1", "--pr", "https://example.invalid/pr/1", "--evidence-file", self.evidence())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.field("T-1", "status"), "Review")
        self.assertEqual(self.field("T-1", "pr"), "https://example.invalid/pr/1")
        (comment,) = self.board.comments_on("T-1")
        self.assertIn("outcome: review", comment)
        self.assertIn("1. seen: ran the thing, it works", comment)

    def test_needs_review_changes_nothing_on_the_board(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertIn("outcome: needs-review", out)
        self.assertEqual(self.field("T-1", "status"), "In Progress")
        self.assertEqual(self.board.comments_on("T-1"), [])

    def test_stop_puts_the_question_on_the_page(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.jtek("stop", "T-1", "--waiting", "approval", "--note", "may I add a dependency?")
        self.assertEqual(self.field("T-1", "waiting"), "approval")
        (comment,) = self.board.comments_on("T-1")
        self.assertIn("note: may I add a dependency?", comment)

    def test_a_result_that_did_not_reach_the_board_can_be_pushed_again(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.board.can_comment = False
        code, out = self.to_review()
        self.assertEqual(code, 1)
        self.assertIn("outcome: review", out)
        self.assertIn("the board was not updated", out)
        self.assertIn("insert comments", out)
        self.assertIn("jtek.py push T-1", out)
        self.assertEqual(self.jtek("result", "T-1")[0], 0, "the result is saved all the same")
        self.board.can_comment = True
        self.assertEqual(self.jtek("push", "T-1")[0], 0)
        self.assertEqual(self.jtek("push", "T-1")[0], 0)
        self.assertEqual(len(self.board.comments_on("T-1")), 1, "the same result is commented once")
        self.assertEqual(self.field("T-1", "status"), "Review")

    def test_a_long_result_is_split_for_the_comment(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        evidence = Path(self.tmp.name) / "long.md"
        evidence.write_text("1. seen: " + "x" * 5000 + "\n")
        code, out = self.jtek("finish", "T-1", "--no-pr", "--evidence-file", str(evidence))
        self.assertEqual(code, 0, out)
        self.assertIn("x" * 5000, self.board.comments_on("T-1")[0])

    def test_list_reads_every_page_and_shows_open_dependencies(self):
        self.board.page_size = 2
        self.ticket("T-1", status="Done")
        self.ticket("T-2", extra="repo: api\n")
        self.ticket("T-3", extra="after: T-1, T-2\n")
        self.ticket("T-4", status="Backlog")
        self.ticket("T-5", status="Cancelled")
        code, out = self.jtek("list")
        self.assertEqual(code, 0, out)
        self.assertIn("Todo (2)", out)
        self.assertIn("T-3  Ticket T-3  [after: T-2]", out)
        self.assertIn("[repo: api]", out)
        self.assertNotIn("T-1 ", out)
        self.assertNotIn("T-5", out)

    def test_sync_leaves_the_tickets_of_another_repository(self):
        self.ticket("T-1", status="Review", extra="repo: api\npr: https://example.invalid/pr/merged\n")
        self.ticket("T-2", status="Review", extra="repo: app\npr: https://example.invalid/pr/merged\n")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text("#!/bin/sh\necho MERGED abc pass\n")
        (bin_dir / "gh").chmod(0o755)
        code, out = self.jtek("list", "--sync", env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
        self.assertEqual(code, 0, out)
        self.assertEqual(self.field("T-1", "status"), "Review")
        self.assertEqual(self.field("T-2", "status"), "Done")
        self.assertIn("set to Done, pull request merged: T-2", out)

    def test_sync_keeps_a_worktree_when_the_page_is_only_missing_from_the_list(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.board.by_id("T-1")["hidden"] = True  # the query does not return it, but the page says In Progress
        self.assertEqual(self.jtek("list", "--sync")[0], 0)
        self.assertTrue(self.worktree("T-1").is_dir())
        self.board.fail("GET", "/v1/pages", 500, times=5)
        self.jtek("list", "--sync")
        self.assertTrue(self.worktree("T-1").is_dir(), "a page that cannot be read is not finished")

    def test_a_toggle_heading_is_named_and_refused_for_done_when(self):
        body = [{"type": "heading_2", "text": "Goal"}, {"type": "paragraph", "text": "x"},
                {"type": "heading_2", "text": "Done when"}, {"type": "bulleted_list_item", "text": "it works"},
                {"type": "heading_2", "text": "Out of scope", "children": True}]
        self.ticket("T-1", body=body)
        self.assertEqual(self.jtek("start", "T-1")[0], 0)
        snapshot = (self.repo / ".git" / "jtek" / "work" / "T-1" / "ticket.md").read_text()
        self.assertIn("this heading is a toggle", snapshot)
        body[2]["children"] = True
        self.ticket("T-2", body=body)
        code, out = self.jtek("start", "T-2")
        self.assertEqual(code, 1)
        self.assertIn("`Done when` heading on the page is a toggle", out)

    def test_finish_does_not_overwrite_a_status_the_human_set(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.board.set("T-1", Status="Cancelled")
        code, out = self.to_review()
        self.assertEqual(code, 1)
        self.assertIn("the page is `Cancelled`, not In Progress", out)
        self.assertEqual(self.field("T-1", "status"), "Cancelled")
        self.assertEqual(self.board.comments_on("T-1"), [])

    def test_the_test_address_must_be_http(self):
        self.ticket("T-1")
        code, out = self.jtek("start", "T-1", env={"JTEK_NOTION_API": "ftp://127.0.0.1/x"})
        self.assertEqual(code, 1)
        self.assertIn("may only point at this machine", out)

    def test_the_same_question_asked_again_is_commented_again(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        for _ in range(2):
            self.assertEqual(self.jtek("stop", "T-1", "--waiting", "input", "--note", "which currency?")[0], 0)
            self.board.set("T-1", Waiting="")
            self.assertEqual(self.jtek("start", "T-1")[0], 0)
        self.assertEqual(len(self.board.comments_on("T-1")), 2)

    def test_release_says_the_board_is_not_changed(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        code, out = self.jtek("release", "T-1")
        self.assertEqual(code, 0, out)
        self.assertIn("The board is not changed", out)
        self.assertEqual(self.field("T-1", "status"), "In Progress")


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
        self.assertEqual(self.next()["T-1"], ["work", "the human answered"])

    def test_next_says_push_when_the_board_missed_a_result(self):
        self.ticket("T-1")
        self.jtek("start", "T-1")
        self.commit_change("T-1")
        self.jtek("check", "T-1")
        self.jtek("verdict", "T-1", "PASS", "--by", "reviewer")
        self.board.can_comment = False
        self.jtek("finish", "T-1", "--no-pr", "--evidence-file", self.evidence())
        self.assertEqual(self.next()["T-1"][0], "push")


if __name__ == "__main__":
    unittest.main()
