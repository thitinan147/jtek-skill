"""AGENTS.md from /jt-setup: fresh repo, merge, idempotent re-run, slot detection."""

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "skills" / "jt-setup" / "scripts" / "gate.py"

FLOW = "spec -> tasks -> work -> gate -> human merge"


def run_gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args, "--root", str(root)],
        cwd=root,
        capture_output=True,
        text=True,
    )


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AgentsFileTests(unittest.TestCase):
    def test_fresh_repo_proposes_then_writes_agents_and_claude_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = run_gate(root, "agents")
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertIn("AGENTS.md: create", preview.stdout)
            self.assertIn("CLAUDE.md: create", preview.stdout)
            self.assertIn("cursor-rules: skip", preview.stdout)
            self.assertIn("board: skip", preview.stdout)
            self.assertIn("wrote: no", preview.stdout)
            self.assertIn(FLOW, preview.stdout)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertFalse((root / ".cursor").exists())
            self.assertFalse((root / "jt-queue").exists())

            written = run_gate(root, "agents", "--write")
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            self.assertIn("wrote: AGENTS.md CLAUDE.md", written.stdout)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertEqual(claude, "@AGENTS.md\n")
            self.assertNotIn(FLOW, claude)
            self.assertNotIn("## Commands", claude)
            self.assertNotIn("## Queue files", claude)
            self.assertIn(FLOW, agents)
            self.assertIn("jt-queue/board.md", agents)
            self.assertIn("jt-queue/brief.md", agents)
            self.assertIn("jt-queue/tasks/<id>/task.md", agents)
            self.assertIn("jt-queue/tasks/<id>/plan.md", agents)
            self.assertIn("jt-queue/ at the repo root", agents)
            self.assertIn("Do not run approve-commands", agents)
            self.assertIn("/jt-review is human-only", agents)
            self.assertIn("::: jtek:start", agents)
            self.assertIn("::: jtek:end", agents)
            self.assertIn("| TEST_CMD | no-suite |", agents)
            self.assertIn("none found; left empty", agents)
            for invented in ("eslint", "pytest", "ruff check", "tsc ", "golangci-lint"):
                self.assertNotIn(invented, agents)

    def test_existing_agents_md_keeps_user_text_and_adds_one_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = "# Team\n\nKeep this sentence.\n"
            write(root, "AGENTS.md", original)
            result = run_gate(root, "agents", "--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("AGENTS.md: merge", result.stdout)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith(original))
            self.assertEqual(text.count("Keep this sentence."), 1)
            self.assertEqual(text.count("::: jtek:start"), 1)
            self.assertIn(FLOW, text)
            self.assertIn("--- diff AGENTS.md", result.stdout)
            self.assertNotIn("\n-Keep this sentence.", "\n" + result.stdout)

    def test_claude_md_only_imports_agents_without_copying_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "CLAUDE.md", "# Team rules\nPrefer small diffs.\n")
            result = run_gate(root, "agents", "--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("AGENTS.md: create", result.stdout)
            self.assertIn("CLAUDE.md: merge", result.stdout)
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Prefer small diffs.", claude)
            self.assertIn("@AGENTS.md", claude)
            self.assertNotIn(FLOW, claude)
            self.assertNotIn("## Commands", claude)
            self.assertNotIn("| TEST_CMD |", claude)
            self.assertIn(FLOW, agents)
            self.assertTrue(claude.startswith("# Team rules\nPrefer small diffs.\n"))

    def test_rerun_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "package.json",
                '{"scripts": {"test": "vitest run", "lint": "eslint ."}}\n',
            )
            first = run_gate(root, "agents", "--write")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            snapshot = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            second = run_gate(root, "agents", "--write")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("AGENTS.md: unchanged", second.stdout)
            self.assertIn("CLAUDE.md: unchanged", second.stdout)
            self.assertIn("diff: none", second.stdout)
            self.assertNotIn("--- diff", second.stdout)
            self.assertIn("wrote: no", second.stdout)
            again = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(snapshot, again)

    def test_node_and_python_slots_come_from_the_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "package.json",
                textwrap.dedent(
                    """\
                    {
                      "scripts": {
                        "test": "vitest run",
                        "lint": "eslint .",
                        "typecheck": "tsc --noEmit"
                      }
                    }
                    """
                ),
            )
            detected = run_gate(root, "detect")
            self.assertEqual(detected.returncode, 0, detected.stdout + detected.stderr)
            self.assertIn("TEST_CMD = vitest run  [source: package.json scripts.test]", detected.stdout)
            self.assertIn("LINT_CMD = eslint .  [source: package.json scripts.lint]", detected.stdout)
            self.assertIn(
                "TYPECHECK_CMD = tsc --noEmit  [source: package.json scripts.typecheck]",
                detected.stdout,
            )
            self.assertIn("SECURITY_CMD = (empty)  [source: none found; left empty]", detected.stdout)
            self.assertIn(
                "AFFECTED_TEST_CMD = (empty)  [source: none found; left empty]",
                detected.stdout,
            )
            self.assertIn("VERIFY_CMD = (empty)  [source: not a web app]", detected.stdout)
            self.assertNotIn("trufflehog", detected.stdout)
            written = run_gate(root, "agents", "--write")
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("| TEST_CMD | vitest run | package.json scripts.test |", agents)
            self.assertIn("| LINT_CMD | eslint . | package.json scripts.lint |", agents)
            self.assertIn("| TYPECHECK_CMD | tsc --noEmit | package.json scripts.typecheck |", agents)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pyproject.toml",
                textwrap.dedent(
                    """\
                    [tool.pytest.ini_options]
                    addopts = "--testmon"

                    [tool.ruff]
                    line-length = 100

                    [tool.mypy]
                    python_version = "3.12"
                    """
                ),
            )
            detected = run_gate(root, "detect")
            self.assertEqual(detected.returncode, 0, detected.stdout + detected.stderr)
            self.assertIn("TEST_CMD = pytest  [source: pyproject.toml]", detected.stdout)
            self.assertIn("LINT_CMD = ruff check  [source: pyproject.toml [tool.ruff]]", detected.stdout)
            self.assertIn("TYPECHECK_CMD = mypy  [source: pyproject.toml [tool.mypy]]", detected.stdout)
            self.assertIn(
                "AFFECTED_TEST_CMD = pytest --testmon  [source: pyproject.toml]",
                detected.stdout,
            )
            self.assertIn("SECURITY_CMD = (empty)  [source: none found; left empty]", detected.stdout)
            self.assertNotIn("eslint", detected.stdout)
            self.assertNotIn("tsc", detected.stdout)

    def test_makefile_justfile_and_ci_commands_are_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\tpython -m unittest\n")
            write(root, "justfile", "typecheck:\n    mypy src\n")
            detected = run_gate(root, "detect")
            self.assertIn("TEST_CMD = make test  [source: Makefile target test]", detected.stdout)
            self.assertIn(
                "TYPECHECK_CMD = just typecheck  [source: justfile recipe typecheck]",
                detected.stdout,
            )
            self.assertNotIn("TEST_CMD = python -m unittest", detected.stdout)
            self.assertNotIn("TYPECHECK_CMD = mypy src", detected.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                ".github/workflows/ci.yml",
                textwrap.dedent(
                    """\
                    name: ci
                    on: push
                    jobs:
                      test:
                        runs-on: ubuntu-latest
                        steps:
                          - run: |
                              cargo test --all
                              cargo clippy -- -D warnings
                    """
                ),
            )
            detected = run_gate(root, "detect")
            self.assertEqual(detected.returncode, 0, detected.stdout + detected.stderr)
            self.assertIn(
                "TEST_CMD = cargo test --all  [source: .github/workflows/ci.yml]",
                detected.stdout,
            )
            self.assertIn(
                "LINT_CMD = cargo clippy -- -D warnings  [source: .github/workflows/ci.yml]",
                detected.stdout,
            )
            self.assertIn("TYPECHECK_CMD = (empty)  [source: none found; left empty]", detected.stdout)
            self.assertNotIn("TEST_CMD = cargo test  [source: Cargo.toml]", detected.stdout)

    def test_existing_rules_and_board_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", '{"scripts": {"test": "vitest run", "lint": "eslint ."}}\n')
            write(root, ".cursor/rules/existing.mdc", "User rule.\n")
            write(
                root,
                "jt-queue/board.md",
                textwrap.dedent(
                    """\
                    # Board

                    | Value | In this repo |
                    | --- | --- |
                    | `<TEST_CMD>` | pytest -q |
                    | `<LINT_CMD>` | |
                    | `<TYPECHECK_CMD>` | |
                    | `<SECURITY_CMD>` | |
                    | `<VERIFY_CMD>` | |
                    | `<AFFECTED_TEST_CMD>` | |

                    ## main

                    no items
                    """
                ),
            )
            user_rule = (root / ".cursor/rules/existing.mdc").read_bytes()
            result = run_gate(root, "agents", "--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("cursor-rules: create", result.stdout)
            self.assertIn("board: merge", result.stdout)
            self.assertEqual((root / ".cursor/rules/existing.mdc").read_bytes(), user_rule)
            pointer = (root / ".cursor/rules/jtek.mdc").read_text(encoding="utf-8")
            self.assertIn("Follow AGENTS.md at the repo root.", pointer)
            self.assertNotIn(FLOW, pointer)
            self.assertNotIn("| TEST_CMD |", pointer)
            board = (root / "jt-queue/board.md").read_text(encoding="utf-8")
            self.assertIn("| `<TEST_CMD>` | pytest -q |", board)
            self.assertEqual(board.count("::: jtek:start"), 1)
            self.assertIn("This board keeps the command table above.", board)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("| TEST_CMD | pytest -q | jt-queue/board.md |", agents)
            self.assertIn("| LINT_CMD | eslint . | package.json scripts.lint |", agents)
            again = run_gate(root, "agents", "--write")
            self.assertIn("diff: none", again.stdout)
            self.assertIn("board: unchanged", again.stdout)
            self.assertIn("cursor-rules: unchanged", again.stdout)
            self.assertEqual((root / "jt-queue/board.md").read_text(encoding="utf-8"), board)
            self.assertEqual((root / ".cursor/rules/jtek.mdc").read_text(encoding="utf-8"), pointer)

    def test_cursor_rules_file_keeps_user_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".cursor/rules", "Keep this rule.\n")
            result = run_gate(root, "agents", "--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (root / ".cursor/rules").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("Keep this rule.\n"))
            self.assertIn("Follow AGENTS.md at the repo root.", text)
            self.assertNotIn(FLOW, text)
            self.assertFalse((root / ".cursor" / "rules" / "jtek.mdc").exists())
            again = run_gate(root, "agents", "--write")
            self.assertIn("cursor-rules: unchanged", again.stdout)
            self.assertIn("diff: none", again.stdout)
            self.assertEqual((root / ".cursor" / "rules").read_text(encoding="utf-8"), text)

    def test_board_template_uses_the_same_pointer(self) -> None:
        template = (REPO / "skills" / "jt-setup" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        pointer = (
            "Agent instructions live in AGENTS.md at the repo root. "
            "CLAUDE.md imports that file. This board keeps the command table above."
        )
        self.assertIn("::: jtek:start\n" + pointer + "\n::: jtek:end\n", template)

    def test_broken_markers_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = "Keep\n::: jtek:start\nno end\n"
            write(root, "AGENTS.md", original)
            preview = run_gate(root, "agents")
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertIn("AGENTS.md: unparsed", preview.stdout)
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), original)
            written = run_gate(root, "agents", "--write")
            self.assertEqual(written.returncode, 2, written.stdout + written.stderr)
            self.assertIn("wrote: no", written.stdout)
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
