import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "skills"
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith(" "):
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data


class SkillContractTests(unittest.TestCase):
    def test_expected_skill_directories_exist(self) -> None:
        dirs = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
        self.assertEqual(
            dirs,
            [
                "jt-add-task",
                "jt-board",
                "jt-help",
                "jt-review",
                "jt-setup",
                "jt-spec-ac",
                "jt-spec-handoff",
                "jt-spec-split",
                "jt-work",
            ],
        )

    def test_no_pycache_or_bytecode_in_skills(self) -> None:
        bad = [
            str(p.relative_to(REPO))
            for p in SKILLS_DIR.rglob("*")
            if p.name == "__pycache__" or p.suffix in {".pyc", ".pyo"}
        ]
        self.assertEqual(bad, [], f"Bytecode or __pycache__ found in skills/: {bad}")

    def test_agentskills_frontmatter_constraints(self) -> None:
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            self.assertTrue(skill_md.is_file(), str(skill_md))
            fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            self.assertEqual(fm.get("name"), skill_dir.name)
            self.assertTrue(1 <= len(fm.get("name", "")) <= 64)
            self.assertRegex(fm.get("name", ""), r"^[a-z0-9-]+$")
            self.assertTrue(1 <= len(fm.get("description", "")) <= 1024)

    def test_line_budgets_and_single_level_references(self) -> None:
        budgets = {
            SKILLS_DIR / "jt-setup" / "SKILL.md": 50,
            SKILLS_DIR / "jt-add-task" / "SKILL.md": 50,
            SKILLS_DIR / "jt-work" / "SKILL.md": 90,
            SKILLS_DIR / "jt-review" / "SKILL.md": 60,
            SKILLS_DIR / "jt-help" / "SKILL.md": 80,
            SKILLS_DIR / "jt-work" / "references" / "contract.md": 100,
        }
        queue_cap = {
            SKILLS_DIR / "jt-setup" / "SKILL.md",
            SKILLS_DIR / "jt-add-task" / "SKILL.md",
            SKILLS_DIR / "jt-work" / "SKILL.md",
            SKILLS_DIR / "jt-review" / "SKILL.md",
            SKILLS_DIR / "jt-work" / "references" / "contract.md",
        }
        total_lines = 0
        for path, limit in budgets.items():
            self.assertTrue(path.is_file(), str(path))
            count = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, limit, f"{path}: {count} > {limit}")
            if path in queue_cap:
                total_lines += count
        # Splitting the queue skill must not grow these files past the old 300-line cap.
        self.assertLessEqual(total_lines, 300)

        # Reference files must not chain to further markdown references (depth <= 1)
        for ref_file in SKILLS_DIR.rglob("references/*.md"):
            links = LINK_RE.findall(ref_file.read_text(encoding="utf-8"))
            self.assertEqual(links, [], f"nested reference links in {ref_file}")

    def test_all_markdown_links_in_skills_resolve_within_skill_folder(self) -> None:
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_root = skill_dir.resolve()
            for md_file in skill_dir.rglob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                for target in LINK_RE.findall(content):
                    if target.startswith(("http://", "https://", "#")):
                        continue
                    clean = target.split("#", 1)[0]
                    logical = md_file.parent / clean
                    lexical = Path(os.path.normpath(logical))
                    self.assertTrue(logical.exists(), f"{md_file} -> {target}")
                    # The link as written stays inside the skill. Shared modules
                    # are real copies, so an installed skill does not depend
                    # on a file that lives in another skill.
                    self.assertTrue(
                        lexical.is_relative_to(skill_root),
                        f"cross-skill link {md_file} -> {target}",
                    )
                    self.assertTrue(
                        logical.resolve().is_relative_to(REPO.resolve()),
                        f"link leaves the repo: {md_file} -> {target}",
                    )
            # Ensure no skill references the other skill's scripts directory
            other_names = {
                other.name
                for other in SKILLS_DIR.iterdir()
                if other.is_dir() and other.name != skill_dir.name
            }
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            for other in other_names:
                self.assertFalse(
                    f"{other}/scripts/" in skill_text,
                    f"{skill_dir.name} references {other}/scripts/",
                )

    def test_human_only_skill_has_three_layer_protection(self) -> None:
        human_only = (
            "jt-review",
            "jt-spec-split",
            "jt-spec-ac",
            "jt-spec-handoff",
            "jt-board",
        )
        for name in human_only:
            review_dir = SKILLS_DIR / name
            skill_text = (review_dir / "SKILL.md").read_text(encoding="utf-8")
            fm = parse_frontmatter(skill_text)
            # Layer 1: Claude Code frontmatter flag
            self.assertEqual(fm.get("disable-model-invocation"), "true", name)
            # Layer 2: Codex agents/openai.yaml policy
            openai_yaml = review_dir / "agents" / "openai.yaml"
            self.assertTrue(openai_yaml.is_file(), name)
            yaml_text = openai_yaml.read_text(encoding="utf-8")
            self.assertIsNotNone(
                re.search(r"allow_implicit_invocation:\s*false", yaml_text),
                name,
            )
            # Layer 3: Description prefix for Cursor / Antigravity
            self.assertTrue(
                fm.get("description", "").startswith("HUMAN-ONLY COMMAND."),
                name,
            )

    def test_versions_match_across_plugin_and_skills(self) -> None:
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        versions = {"plugin.json": plugin["version"]}
        for entry in market["plugins"]:
            if entry["name"] == plugin["name"]:
                versions["marketplace.json"] = entry["version"]
        for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            match = re.search(r'^\s+version:\s*"([^"]+)"', text, re.MULTILINE)
            self.assertIsNotNone(match, f"{skill_dir.name}: metadata.version missing")
            versions[skill_dir.name] = match.group(1)
        self.assertIn("marketplace.json", versions, "plugin missing from marketplace.json")
        self.assertEqual(len(set(versions.values())), 1, f"versions differ: {versions}")
        changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {plugin['version']}", changelog)
        self.assertEqual(plugin["version"], "24.0.0")

    def test_second_lesson_must_name_what_enforces_it(self) -> None:
        template = (SKILLS_DIR / "jt-work" / "assets" / "lessons.template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("| symptom | cause | prevention | enforced by |", template)
        skill = (SKILLS_DIR / "jt-work" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("enforced by", skill)
        self.assertIn("second time", skill)
        self.assertIn("chore", skill)
        self.assertIn("lint rule", skill)

    def test_readme_links_and_skill_paths_exist(self) -> None:
        readme_path = REPO / "README.md"
        self.assertTrue(readme_path.is_file())
        readme = readme_path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(readme):
            if target.startswith(("http://", "https://", "#")):
                continue
            clean = target.split("#", 1)[0]
            resolved = (REPO / clean).resolve()
            self.assertTrue(resolved.exists(), f"README link missing: {target}")
        for match in re.findall(r"\bskills/([a-z0-9-]+(?:/[a-zA-Z0-9._-]+)*)", readme):
            candidate = REPO / "skills" / match
            self.assertTrue(candidate.exists(), f"README path missing: skills/{match}")

    def test_shared_modules_are_byte_identical_copies(self) -> None:
        """The skills CLI skips a symlink that points outside the skill, so each skill ships a real copy."""
        links = [p for p in SKILLS_DIR.rglob("*") if p.is_symlink()]
        self.assertEqual(links, [])
        gate = SKILLS_DIR / "jt-work" / "scripts" / "gate.py"
        contract = SKILLS_DIR / "jt-work" / "references" / "contract.md"
        parser = SKILLS_DIR / "jt-spec-ac" / "scripts" / "specdoc.py"
        checker = SKILLS_DIR / "jt-spec-ac" / "scripts" / "check.py"
        rules = SKILLS_DIR / "jt-spec-ac" / "references" / "rules.md"
        notes = SKILLS_DIR / "jt-spec-ac" / "references" / "input.md"
        for name in ("jt-setup", "jt-add-task"):
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "scripts" / "gate.py", gate, shallow=False), name)
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "references" / "contract.md", contract, shallow=False), name)
        for name in ("jt-spec-split", "jt-spec-handoff"):
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "scripts" / "specdoc.py", parser, shallow=False), name)
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "scripts" / "check.py", checker, shallow=False), name)
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "references" / "rules.md", rules, shallow=False), name)
            self.assertTrue(filecmp.cmp(SKILLS_DIR / name / "references" / "input.md", notes, shallow=False), name)
        self.assertTrue(filecmp.cmp(SKILLS_DIR / "jt-board" / "scripts" / "specdoc.py", parser, shallow=False))

    def test_names_and_single_work_command(self) -> None:
        work = (SKILLS_DIR / "jt-work" / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        contract = (SKILLS_DIR / "jt-work" / "references" / "contract.md").read_text(encoding="utf-8")
        for text in (work, readme, contract):
            self.assertIn("feat(booking): add room search API (BOOK-12)", text)
            self.assertIn("feat/BOOK-12-room-search", text)
            self.assertNotIn("S-001", text)
            self.assertNotIn("T-012", text)
        self.assertIn("no `--loop` flag", work)
        self.assertIn("task-<id>-<slug>", work)
        self.assertIn("do not check its shape", work)

    def test_each_skill_directory_installs_alone(self) -> None:
        """Each skill folder is complete: no symlink for the installer to skip."""
        for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
            for path in skill_dir.rglob("*"):
                self.assertFalse(path.is_symlink(), f"{skill_dir.name} contains symlink {path.name}")
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / skill_dir.name
                shutil.copytree(skill_dir, dest, symlinks=False)
                for path in dest.rglob("*"):
                    self.assertFalse(path.is_symlink(), f"{skill_dir.name} left a symlink at {path.name}")
                scripts = dest / "scripts"
                if not scripts.is_dir():
                    continue
                for script in scripts.glob("*.py"):
                    compiled = subprocess.run(
                        [sys.executable, "-I", "-m", "py_compile", str(script)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(compiled.returncode, 0, f"{script}: {compiled.stderr}")
                if (scripts / "check.py").is_file():
                    help_run = subprocess.run(
                        [sys.executable, "-I", str(scripts / "check.py"), "--help"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(help_run.returncode, 0, help_run.stderr)
                    self.assertIn("Usage:", help_run.stdout)
                if (scripts / "board.py").is_file():
                    help_run = subprocess.run(
                        [sys.executable, "-I", str(scripts / "board.py"), "--help"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(help_run.returncode, 0, help_run.stderr)


if __name__ == "__main__":
    unittest.main()
