"""The GitLab example for `pr_state`, run against a stand-in for `glab`."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "pr-state-gitlab.py"
LINK = "https://gitlab.example.com/team/sub/app/-/merge_requests/7"


class GitLabExample(unittest.TestCase):
    def run_with(self, answer, link=LINK, code=0):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "glab"
            fake.write_text(
                f"#!{sys.executable}\nimport sys\n"
                f"open({str(Path(tmp) / 'args')!r}, 'w').write(' '.join(sys.argv[1:]))\n"
                f"sys.stdout.write({json.dumps(answer)!r})\nsys.exit({code})\n"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}"}
            proc = subprocess.run([sys.executable, str(EXAMPLE), link], capture_output=True, text=True, env=env)
            args = (Path(tmp) / "args").read_text() if (Path(tmp) / "args").exists() else ""
        return proc, args

    def test_open_request_with_a_green_pipeline(self):
        proc, args = self.run_with({"state": "opened", "sha": "abc", "head_pipeline": {"status": "success", "sha": "abc"}})
        self.assertEqual(proc.stdout.split(), ["OPEN", "abc", "pass"])
        self.assertEqual(args, "api --hostname gitlab.example.com projects/team%2Fsub%2Fapp/merge_requests/7")

    def test_states_and_pipelines(self):
        cases = [
            ({"state": "merged", "sha": "abc", "head_pipeline": {"status": "failed"}}, "MERGED abc fail"),
            ({"state": "closed", "sha": "abc", "head_pipeline": None}, "CLOSED abc none"),
            ({"state": "opened", "draft": True, "sha": "abc", "head_pipeline": None}, "DRAFT abc none"),
            ({"state": "opened", "sha": "abc", "head_pipeline": {"status": "running", "sha": "abc"}}, "OPEN abc pending"),
            ({"state": "opened", "sha": "abc", "head_pipeline": {"status": "success", "sha": "old"}}, "OPEN abc pending"),
            ({"state": "opened", "sha": "abc", "head_pipeline": {"status": "failed", "sha": "merged-result"}}, "OPEN abc fail"),
            ({"state": "opened", "sha": "abc", "head_pipeline": {"status": "manual", "sha": "abc"}}, "OPEN abc pending"),
        ]
        for answer, words in cases:
            with self.subTest(words=words):
                self.assertEqual(self.run_with(answer)[0].stdout.strip(), words)

    def test_it_fails_and_prints_nothing_when_it_cannot_tell(self):
        for proc in (
            self.run_with({}, link="https://github.com/a/b/pull/1")[0],
            self.run_with({"state": "opened"})[0],
            self.run_with({"message": "404"}, code=1)[0],
        ):
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
