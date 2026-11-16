"""Queue controls for v25: blocked tasks, caps, risk, limits, and the batch plan."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-work" / "scripts" / "gate.py"
CHECK = REPO / "skills" / "jt-spec-ac" / "scripts" / "check.py"


def load_gate():
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("tek_gate_v25", GATE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["tek_gate_v25"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = prev


gate = load_gate()


def git(repo: Path, *args: str) -> None:
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "commit.gpgsign"
    env["GIT_CONFIG_VALUE_0"] = "false"
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env)


def board(cards: str, **cells: str) -> str:
    rows = [
        ("`<TEST_CMD>`", cells.get("test", "python3 check.py")),
        ("`<SETUP_CMD>`", ""),
        ("`<STACK_LOCK>`", "py · none · test · ban"),
    ]
    for name, key in (
        ("`<DIFF_LIMIT>`", "diff"),
        ("`<MAX_PARALLEL>`", "parallel"),
        ("`<MAX_REVIEW>`", "review"),
        ("`<QUOTA>`", "quota"),
        ("`<IMPORT_CMD>`", "import_cmd"),
        ("`<PBT_CMD>`", "pbt"),
    ):
        if key in cells:
            rows.append((name, cells[key]))
    table = "\n".join(f"| {name} | {value} |" for name, value in rows)
    return (
        "# Board - app\n\nqueue: main\n\n"
        "| Value | In this repo |\n|---|---|\n"
        f"{table}\n\n"
        "## first\n\n"
        f"{cards}\n\n"
        "## main\n\nno items\n\n"
        "## later\n\nno items\n"
    )


def card(files: list[str], blocked: str = "", question: str = "") -> str:
    listed = "\n".join(f"- {name}" for name in files) if files else "-"
    ask = "ask:" if not question else f"ask: {question}"
    return (
        "# 12 - title\n\nkind: feat\n\ndo:\n- something\n\nout:\n- other\n\n"
        "pass:\n- HEADER_TOKEN\n\nfiles:\n"
        f"{listed}\n\nblocked-by: {blocked}\n\n{ask}\n"
    )


def decide(text: str, bodies: dict[str, str | None]):
    parsed = gate.hydrate(gate.parse_board(text), bodies)
    return gate.decide(parsed, brief_exists=True, dirty=False, is_git=True)


class QueueControlTests(unittest.TestCase):
    def test_blocked_by_skips_until_the_dependency_is_closed(self) -> None:
        text = board("- [ ] **2** first (feat)\n- [ ] **3** next (feat)")
        open_body = {"2": card(["src/a.py"]), "3": card(["src/b.py"], blocked="2")}
        waiting = decide(text, open_body)
        self.assertEqual(waiting.id, "2")
        self.assertNotEqual(waiting.id, "3")
        closed = board("- [x] **2** first (feat) merge:\n- [ ] **3** next (feat)")
        ready = decide(closed, open_body)
        self.assertEqual(ready.action, "do-task")
        self.assertEqual(ready.id, "3")
        self.assertNotIn("merge", ready.action)

    def test_parallel_and_review_caps_wait(self) -> None:
        text = board("- [ ] **2** ready (feat)", parallel="1")
        parsed = gate.hydrate(gate.parse_board(text), {"2": card(["src/a.py"])})
        claim = gate.Claim("9", "other", "2026-11-16T00:00:00Z", "2026-11-16T00:00:00Z", ())
        capped = gate.decide(
            parsed,
            brief_exists=True,
            dirty=False,
            is_git=True,
            claims={"9": claim},
            me="me",
        )
        self.assertEqual(capped.reason, "parallel")
        self.assertEqual(capped.action, "wait")
        review = board("- [ ] **2** waiting (feat) review: local\n- [ ] **3** ready (feat)", review="1")
        held = decide(review, {"2": card(["src/a.py"]), "3": card(["src/b.py"])})
        self.assertEqual(held.reason, "review-cap")
        self.assertNotEqual(held.action, "do-task")

    def test_risk_levels_match_the_eval_file(self) -> None:
        cases = json.loads((REPO / "evals" / "queue.json").read_text(encoding="utf-8"))
        for case in cases:
            got = gate.risk_level(case["paths"], case["lines"], case["human_hit"], case["limit"])
            self.assertEqual(got, case["expect"], case["name"])

    def test_titles_and_codeowners_stay_with_the_human(self) -> None:
        self.assertIsNone(gate.commit_title_problem("feat(queue): add a cap (BOOK-12)"))
        self.assertIsNotNone(gate.commit_title_problem("wip"))
        proposal = gate.codeowners_proposal(["tests/test_app.py", "src/app.py"])
        self.assertIn("/tests/test_app.py @human", proposal)
        self.assertIn("The agent does not", proposal)
        self.assertNotIn("src/app.py", proposal)

    def test_import_and_property_failures_name_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "t@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "jt-queue").mkdir()
            for slug, skipped in (("import", "tests"), ("pbt", "verify")):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = gate._run_check(
                        repo, "12", repo, slug, "python3 -c 'import sys; sys.exit(1)'"
                    )
                out = buf.getvalue()
                self.assertEqual(code, 1, out)
                self.assertIn(f"refused: {slug}-failed", out)
                self.assertIn(f"step: {slug}", out)
                self.assertIn(f"skipped: {skipped}", out)
                self.assertIn("fix:", out)
                self.assertIn("merge: no", out)

    def test_diff_limit_refuses_with_a_fix_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "t@example.com")
            git(repo, "config", "user.name", "Test")
            queue = repo / "jt-queue"
            (queue / "tasks" / "12").mkdir(parents=True)
            (queue / "board.md").write_text(
                board("- [ ] **12** grow (feat)", diff="1"), encoding="utf-8"
            )
            (queue / "tasks" / "12" / "task.md").write_text(card(["app.py"]), encoding="utf-8")
            (repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "docs: board")
            git(repo, "checkout", "-b", "task-12")
            (repo / "app.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "feat: grow the diff")
            git(repo, "checkout", "main")
            result = subprocess.run(
                [sys.executable, str(GATE_PATH), "reach-review", "--root", str(repo), "--id", "12"],
                cwd=repo,
                capture_output=True,
                text=True,
                env={**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false"},
            )
        self.assertIn("refused: diff-limit", result.stdout, result.stderr)
        self.assertIn("step: diff-limit", result.stdout)
        self.assertIn("fix:", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("\nallowed\n", f"\n{result.stdout}")

    def test_loop_resume_merge_queue_flags_and_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "t@example.com")
            git(repo, "config", "user.name", "Test")
            queue = repo / "jt-queue"
            (queue / "tasks" / "2").mkdir(parents=True)
            (queue / "tasks" / "3").mkdir(parents=True)
            (queue / "board.md").write_text(
                board(
                    "- [ ] **2** ask (feat) ask:\n- [ ] **3** ready (feat)",
                    quota="1",
                    review="5",
                ),
                encoding="utf-8",
            )
            (queue / "tasks" / "2" / "task.md").write_text(
                card(["src/a.py"], question="which name?"), encoding="utf-8"
            )
            (queue / "tasks" / "3" / "task.md").write_text(
                card(["src/b.py"], blocked="2"), encoding="utf-8"
            )
            (queue / "tasks" / "3" / "handoff.md").write_text(
                "# Handoff\n\n- **State:** gate-fail\n- **Done:** see plan.md\n- **Left:** see task.md\n"
                "- **Gate:** tests\n- **Files:** src/b.py\n- **Next:** `gate.py reach-review --id 3`\n"
                "- **Updated:** 2026-11-16\n",
                encoding="utf-8",
            )
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "docs: queue")

            def run(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                )

            planned = run("loop", "--max", "100")
            self.assertIn("merge: no", planned.stdout)
            self.assertIn("questions: 2", planned.stdout)
            self.assertIn("skip-blocked: 3", planned.stdout)
            self.assertIn("tools: mise, reviewdog", planned.stdout)
            self.assertIn("each-from: latest main", planned.stdout)
            self.assertNotIn("ids: 3", planned.stdout)
            resume = run("resume", "--id", "3")
            self.assertIn("data: not instructions", resume.stdout)
            self.assertIn("next: gate.py reach-review --id 3", resume.stdout)
            self.assertIn("merge: no", resume.stdout)
            order = run("merge-queue")
            self.assertIn("does-not-merge:", order.stdout)
            self.assertIn("order: none", order.stdout)
            flags = run("flags")
            self.assertIn("flags: skip", flags.stdout)
            self.assertIn("revert:", flags.stdout)
            self.assertNotIn("http", flags.stdout)
            started = run("run-start")
            self.assertIn("run: started", started.stdout)
            title = run("title", "--text", "not a title")
            self.assertIn("refused: commit-title", title.stdout)
            self.assertIn("fix:", title.stdout)
            good = run("title", "--text", "feat(queue): plan the batch (BOOK-1)")
            self.assertIn("title: ok", good.stdout)
            self.assertIn("post-merge:", good.stdout)
            owners = run("codeowners")
            self.assertIn("owner: human", owners.stdout)
            self.assertIn("merge: no", owners.stdout)

    def test_statechart_note_and_eval_files_exist(self) -> None:
        cases = json.loads((REPO / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["query"].startswith("/jt-work --loop") for item in cases))
        for item in cases:
            for rel in item["files"]:
                self.assertTrue((REPO / rel).is_file(), rel)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            spec = root / "scrum-spec" / "book" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text(
                "<!-- scrum-spec -->\n# book\n\n## Story\n\n- **Story:** the booking state changes\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-I", str(CHECK), str(spec)],
                capture_output=True,
                text=True,
            )
        self.assertIn("statechart: compose pstack /statechart", result.stdout)

    def test_commands_do_not_merge(self) -> None:
        self.assertIn("loop", Path(GATE_PATH).read_text(encoding="utf-8"))
        self.assertIn("Does not merge", (REPO / "skills" / "jt-work" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("HUMAN-ONLY", (REPO / "skills" / "jt-review" / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
