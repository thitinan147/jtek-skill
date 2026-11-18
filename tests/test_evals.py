"""The eval builder and grader work on a scripted, known-good run."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "evals" / "run.py"
JTEK = ROOT / "skills" / "jt-work" / "scripts" / "jtek.py"


def run(*args, cwd=None):
    proc = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name).resolve() / "run"

    def test_every_scenario_builds_and_an_untouched_one_fails_the_grade(self):
        for scenario in sorted(p.name for p in (ROOT / "evals" / "scenarios").iterdir()):
            dest = self.dest / scenario
            code, out = run(RUN, "build", scenario, dest)
            self.assertEqual(code, 0, out)
            self.assertIn("prompt for a fresh agent session", out)
            code, out = run(RUN, "grade", scenario, dest)
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL  result outcome", out)

    def test_a_correct_bug_fix_gets_full_marks(self):
        self.assertEqual(run(RUN, "build", "bug-wordcount", self.dest)[0], 0)
        repo = self.dest / "app"
        self.assertEqual(run(JTEK, "start", "B-1", cwd=repo)[0], 0)
        tree = self.dest / "app.jtek" / "B-1"
        test = tree / "test_wordcount.py"
        test.write_text(test.read_text().replace(
            "if __name__", "class More(unittest.TestCase):\n    def test_tabs(self):\n"
            "        self.assertEqual(count_words(\"a\\tb\"), 2)\n\n\nif __name__"))
        git("commit", "-qam", "test: failing test for tabs", cwd=tree)
        code = tree / "wordcount.py"
        code.write_text(code.read_text().replace('text.split(" ")', "text.split()"))
        git("commit", "-qam", "fix: split on any whitespace", cwd=tree)
        self.assertEqual(run(JTEK, "check", "B-1", cwd=tree)[0], 0)
        evidence = self.dest / "evidence.md"
        evidence.write_text("- ran wordcount on a mixed file, saw 4\n")
        self.assertEqual(run(JTEK, "verdict", "B-1", "PASS", "--by", "reviewer", cwd=tree)[0], 0)
        code, out = run(JTEK, "finish", "B-1", "--no-pr", "--evidence-file", evidence, cwd=tree)
        self.assertIn("outcome: review", out)
        code, out = run(RUN, "grade", "bug-wordcount", self.dest)
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def test_a_fix_without_the_test_first_loses_that_mark(self):
        self.assertEqual(run(RUN, "build", "bug-wordcount", self.dest)[0], 0)
        repo = self.dest / "app"
        run(JTEK, "start", "B-1", cwd=repo)
        tree = self.dest / "app.jtek" / "B-1"
        code = tree / "wordcount.py"
        code.write_text(code.read_text().replace('text.split(" ")', "text.split()"))
        git("commit", "-qam", "fix", cwd=tree)
        run(JTEK, "check", "B-1", cwd=tree)
        code, out = run(RUN, "grade", "bug-wordcount", self.dest)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  the first commit holds only the failing test", out)
        self.assertIn("PASS  hidden acceptance tests pass", out)


if __name__ == "__main__":
    unittest.main()
