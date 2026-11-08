import re
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
        self.assertEqual(dirs, ["jt-review-work", "jt-work-queue"])

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
            SKILLS_DIR / "jt-work-queue" / "SKILL.md": 90,
            SKILLS_DIR / "jt-work-queue" / "references" / "contract.md": 100,
            SKILLS_DIR / "jt-review-work" / "SKILL.md": 60,
        }
        total_lines = 0
        for path, limit in budgets.items():
            self.assertTrue(path.is_file(), str(path))
            count = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, limit, f"{path.name}: {count} > {limit}")
            total_lines += count
        self.assertLessEqual(total_lines, 300)

        # Reference files must not chain to further markdown references (depth <= 1)
        ref_dir = SKILLS_DIR / "jt-work-queue" / "references"
        for ref_file in ref_dir.glob("*.md"):
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
                    resolved = (md_file.parent / clean).resolve()
                    self.assertTrue(resolved.exists(), f"{md_file} -> {target}")
                    self.assertTrue(
                        resolved.is_relative_to(skill_root),
                        f"cross-skill link {md_file} -> {target}",
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
        review_dir = SKILLS_DIR / "jt-review-work"
        skill_text = (review_dir / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(skill_text)
        # Layer 1: Claude Code frontmatter flag
        self.assertEqual(fm.get("disable-model-invocation"), "true")
        # Layer 2: Codex agents/openai.yaml policy
        openai_yaml = review_dir / "agents" / "openai.yaml"
        self.assertTrue(openai_yaml.is_file())
        yaml_text = openai_yaml.read_text(encoding="utf-8")
        self.assertIsNotNone(
            re.search(r"allow_implicit_invocation:\s*false", yaml_text)
        )
        # Layer 3: Description prefix for Cursor / Antigravity
        self.assertTrue(
            fm.get("description", "").startswith("HUMAN-ONLY COMMAND.")
        )

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


if __name__ == "__main__":
    unittest.main()
