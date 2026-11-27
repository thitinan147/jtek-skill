"""The eval builder and grader work on a scripted, known-good run."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "evals" / "run.py"
JTEK = ROOT / "skills" / "jt-work" / "scripts" / "jtek.py"


def run(*args, cwd=None):
    env = os.environ.copy()
    # The scripted run is two sessions: the author, then a reviewer. finish does not wait on CI here.
    if args and str(args[0]).endswith("jtek.py"):
        command = args[1] if len(args) > 1 else ""
        env["JTEK_SESSION"] = "reviewer-session" if command == "verdict" else "author-session"
        env.setdefault("JTEK_CI_TRIES", "0")
        env.setdefault("JTEK_CI_WAIT", "0")
        env.setdefault("JTEK_CI_APPEAR_TRIES", "0")
        env.setdefault("JTEK_CI_APPEAR_WAIT", "0")
    proc = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def load_runner():
    spec = importlib.util.spec_from_file_location("runner", RUN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name).resolve() / "run"
        self._old_home = os.environ.get("JTEK_HOME")
        os.environ["JTEK_HOME"] = str(Path(self.tmp.name).resolve() / "jtek-home")
        self.addCleanup(self._restore_home)

    def _restore_home(self):
        if self._old_home is None:
            os.environ.pop("JTEK_HOME", None)
        else:
            os.environ["JTEK_HOME"] = self._old_home

    def start(self):
        return run(JTEK, "start", "--from-file", self.dest / "ticket.md", cwd=self.dest / "app")

    def test_every_scenario_builds_and_an_untouched_one_fails_the_grade(self):
        for scenario in sorted(p.name for p in (ROOT / "evals" / "scenarios").iterdir()):
            dest = self.dest / scenario
            code, out = run(RUN, "build", scenario, dest)
            self.assertEqual(code, 0, out)
            self.assertIn("prompt for a fresh agent session", out)
            self.assertFalse((dest / "app" / "jtek.json").exists(), scenario)
            self.assertFalse((dest / "app" / ".jtek").exists(), scenario)
            code, out = run(RUN, "grade", scenario, dest)
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL  result outcome", out)

    def test_a_correct_bug_fix_gets_full_marks(self):
        self.assertEqual(run(RUN, "build", "bug-wordcount", self.dest)[0], 0)
        repo = self.dest / "app"
        self.assertEqual(self.start()[0], 0)
        tree = self.dest / "app" / ".claude" / "worktrees" / "B-1"
        test = tree / "test_wordcount.py"
        test.write_text(test.read_text().replace(
            "if __name__", "class More(unittest.TestCase):\n    def test_tabs(self):\n"
            "        self.assertEqual(count_words(\"a\\tb\"), 2)\n\n\nif __name__"))
        git("commit", "-qam", "test: failing test for tabs", cwd=tree)
        code = tree / "wordcount.py"
        code.write_text(code.read_text().replace('text.split(" ")', "text.split()"))
        git("commit", "-qam", "fix: split on any whitespace", cwd=tree)
        self.assertEqual(run(JTEK, "check", "B-1", cwd=tree)[0], 0)
        # Break the fix, show a declared check fails for each Done when item, then restore it.
        code.write_text(code.read_text().replace("text.split()", 'text.split(" ")'))
        for item in ("1", "2", "3"):
            code_b, out_b = run(JTEK, "broke", "B-1", "--item", item, cwd=tree)
            self.assertEqual(code_b, 0, out_b)
        git("checkout", "--", "wordcount.py", cwd=tree)
        evidence = self.dest / "evidence.md"
        evidence.write_text("1. seen: mixed file counts 4\n2. seen: empty file counts 0\n3. seen: single spaces count 3\n- clean-up: nothing to remove\n")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tree, capture_output=True, text=True).stdout.strip()
        notes = Path(self.tmp.name) / "notes.md"
        notes.write_text("Findings: none\n- broke: the tab split; the test check failed\n- safe because: only the split changed (run 1)\n")
        self.assertEqual(run(JTEK, "verdict", "B-1", "PASS", "--by", "reviewer", "--commit", head,
                             "--notes-file", notes, cwd=tree)[0], 0)
        code, out = run(JTEK, "finish", "B-1", "--no-pr", "--evidence-file", evidence, cwd=tree)
        self.assertIn("outcome: review", out)
        self.assertIn("status: Review", (self.dest / "ticket.md").read_text())
        code, out = run(RUN, "grade", "bug-wordcount", self.dest)
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def test_a_fix_without_the_test_first_loses_that_mark(self):
        self.assertEqual(run(RUN, "build", "bug-wordcount", self.dest)[0], 0)
        repo = self.dest / "app"
        self.start()
        tree = self.dest / "app" / ".claude" / "worktrees" / "B-1"
        code = tree / "wordcount.py"
        code.write_text(code.read_text().replace('text.split(" ")', "text.split()"))
        git("commit", "-qam", "fix", cwd=tree)
        run(JTEK, "check", "B-1", cwd=tree)
        code, out = run(RUN, "grade", "bug-wordcount", self.dest)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  the first commit holds only the failing test", out)
        self.assertIn("PASS  hidden acceptance tests pass", out)


    def test_nothing_the_agent_sees_says_it_is_measured(self):
        code, out = run(RUN, "build", "bug-wordcount", self.dest)
        self.assertEqual(code, 0, out)
        prompt = out.split("prompt for a fresh agent session:")[1].split("then:")[0]
        for word in ("eval", "judge", "hidden", "score", "grade"):
            self.assertNotIn(word, prompt.lower())
        self.assertIn(str(self.dest / "tools" / "skills" / "jt-work" / "SKILL.md"), prompt)
        seen = [p for p in self.dest.rglob("*") if "hidden" in p.name or p.name == "scenario.json"]
        self.assertEqual(seen, [], "the hidden tests stay out of the folder the agent works in")
        log = subprocess.run(["git", "log", "--format=%an %ae"], cwd=self.dest / "app", capture_output=True, text=True).stdout
        self.assertNotIn("eval", log)

    def test_a_lean_build_gives_the_short_router_and_the_reviewer_only(self):
        code, out = run(RUN, "build", "--lean", "feature-slug", self.dest)
        self.assertEqual(code, 0, out)
        skills = self.dest / "tools" / "skills"
        self.assertEqual(sorted(p.name for p in skills.iterdir()), ["jt-review", "jt-work"])
        self.assertEqual((skills / "jt-work" / "SKILL.md").read_text(), (ROOT / "evals" / "lean" / "jt-work.md").read_text())
        self.assertFalse((skills / "jt-work" / "playbooks").exists())
        self.assertTrue((skills / "jt-work" / "scripts" / "jtek.py").exists())
        self.assertEqual((self.dest / "variant.txt").read_text(), "lean\n")
        self.assertIn("variant: lean", run(RUN, "grade", "feature-slug", self.dest)[1])
        for target in re.findall(r"\]\(([^)#]+)\)", (skills / "jt-work" / "SKILL.md").read_text()):
            self.assertTrue((skills / "jt-work" / target).exists(), target)

    def test_the_grade_reads_what_the_agent_opened_from_its_transcript(self):
        runner = load_runner()
        home = Path(self.tmp.name) / "home"
        folder = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.dest / "app"))
        folder.mkdir(parents=True)
        calls = [{"type": "tool_use", "name": "Read", "input": {"file_path": str(self.dest / "tools/skills/jt-work/SKILL.md")}},
                 {"type": "tool_use", "name": "Bash", "input": {"command": "python3 x/jtek.py start a; python3 x/jtek.py check B-1"}},
                 {"type": "tool_use", "name": "Read", "input": {"file_path": str(self.dest / "tools/skills/jt-build/SKILL.md")}}]
        (folder / "s.jsonl").write_text("\n".join(json.dumps({"message": {"content": [c]}}) for c in calls) + "\nnot json\n")
        self.assertEqual(runner.transcript(self.dest, home), (["jt-work", "jt-build"], ["start", "check"]))
        self.assertIsNone(runner.transcript(self.dest / "elsewhere", home))


if __name__ == "__main__":
    unittest.main()
