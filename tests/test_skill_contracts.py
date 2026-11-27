"""The skills stay small, self-contained, and consistent with the script."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
VERSION = "28.0.1"
STEPS = ["jt-babysit", "jt-build", "jt-cleanup", "jt-debug", "jt-harness", "jt-learn", "jt-review", "jt-ship", "jt-understand", "jt-verify", "jt-work"]
# Inner-loop skills run inside a ticket session and must never talk to the board (Notion/FLO).
INNER_LOOP_SKILLS = [
    "jt", "jt-babysit", "jt-build", "jt-cleanup", "jt-debug",
    "jt-review", "jt-ship", "jt-understand", "jt-verify", "jt-work",
]
# Modes sit above the router: the human types them, and they hand ticket work to jt-work.
MODES = ["jt", "jt-agents", "jt-init", "jt-me", "jt-status", "jt-ticket"]
# A mode that may start helpers, so it must pass the delegate rules on. jt-agents starts none.
STARTS_HELPERS = ["jt", "jt-me", "jt-ticket"]
ALL = sorted(STEPS + MODES)
# Other skill sets and their commands. jtek must work without any of them.
FOREIGN = [
    "superpowers", "pstack", "ponytail", "gstack", "poteto", "compound engineering",
    "executing-plans", "test-driven-development", "/no-comments", "/statechart",
]


class SkillContracts(unittest.TestCase):
    def test_frontmatter_values_are_plain_yaml_scalars(self):
        # An unquoted value with ": " in it is a YAML error, and the Agent Skills validator in CI rejects the skill.
        for name in ALL:
            front = (SKILLS / name / "SKILL.md").read_text().split("---", 2)[1]
            for line in front.strip().splitlines():
                key, _, value = line.partition(": ")
                if value and value[0] not in "'\"":
                    self.assertNotIn(": ", value, f"{name}: the `{key}` value has ': ' in it; quote it or reword")
                    self.assertFalse(value.rstrip().endswith(":"), f"{name}: the `{key}` value ends with ':'")

    def test_only_the_inner_loop_skills_ship(self):
        self.assertEqual(sorted(p.name for p in SKILLS.iterdir() if p.is_dir()), ALL)

    def test_every_step_in_the_router_names_a_shipped_skill(self):
        text = (SKILLS / "jt-work" / "SKILL.md").read_text()
        named = set(re.findall(r"`(jt-[a-z]+)`", text))
        self.assertEqual(sorted(named), STEPS, "jt-work must route to every step skill, and only to skills that ship")

    def test_only_the_router_knows_the_order(self):
        for name in STEPS:
            if name == "jt-work":
                continue
            body = (SKILLS / name / "SKILL.md").read_text().split("---", 2)[2]
            others = set(re.findall(r"jt-[a-z]+", body)) - {name, "jt-work"}
            self.assertEqual(others, set(), f"{name} names another step skill; the order belongs to jt-work")

    def test_playbooks_name_only_shipped_skills_and_end_with_ship(self):
        books = sorted((SKILLS / "jt-work" / "playbooks").glob("*.md"))
        self.assertEqual([b.stem for b in books], ["bug", "feature", "refactor"])
        for book in books:
            text = book.read_text()
            for other in set(re.findall(r"`(jt-[a-z]+)`", text)):
                self.assertIn(other, ALL, f"{book.name} names `{other}`")
            steps = re.findall(r"^\d+\. (.+)$", text, re.M)
            self.assertIn("`jt-ship`", steps[-1], book.name)
            for needed in ("jt-understand", "jt-build", "jtek.py check", "jt-verify", "jt-cleanup"):
                self.assertIn(needed, text, f"{book.name} skips {needed}")
        self.assertIn("n/a: <reason>", (SKILLS / "jt-work" / "SKILL.md").read_text())

    def test_a_mode_loads_only_when_typed_and_routes_tickets_to_the_router(self):
        for name in MODES:
            text = (SKILLS / name / "SKILL.md").read_text()
            self.assertIn("disable-model-invocation: true", text.split("---", 2)[1], name)
            if name in STARTS_HELPERS:
                self.assertIn("worker.md", text, f"{name} must pass the delegate rules on")
        self.assertIn("`jt-work`", (SKILLS / "jt" / "SKILL.md").read_text())

    def test_ci_scans_every_skill(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        listed = re.search(r"skill: \[(.+)\]", ci).group(1).split(", ")
        self.assertEqual(sorted(listed), ALL)

    def test_script_copies_are_identical(self):
        source = (SKILLS / "jt-work" / "scripts" / "jtek.py").read_bytes()
        self.assertEqual(source, (SKILLS / "jt-review" / "scripts" / "jtek.py").read_bytes())

    def test_no_other_skill_set_is_named(self):
        for path in list(SKILLS.rglob("*.md")) + list(SKILLS.rglob("*.py")):
            text = path.read_text().lower()
            for word in FOREIGN:
                self.assertNotIn(word, text, f"{path} names `{word}`")

    def test_skill_files_are_short_and_well_formed(self):
        for name in ALL:
            text = (SKILLS / name / "SKILL.md").read_text()
            self.assertLessEqual(len(text.splitlines()), 90, name)
            head = text.split("---")[1]
            self.assertIn(f"name: {name}", head)
            description = re.search(r"^description: (.+)$", head, re.M).group(1)
            self.assertIn("Use when", description)
            self.assertLessEqual(len(description), 1024)

    def test_links_in_skills_resolve(self):
        for path in SKILLS.rglob("*.md"):
            for target in re.findall(r"\]\(([^)#]+)\)", path.read_text()):
                if "://" not in target:
                    self.assertTrue((path.parent / target).exists(), f"{path}: {target}")

    def test_work_skill_never_merges_or_picks(self):
        text = (SKILLS / "jt-work" / "SKILL.md").read_text()
        self.assertIn("never merges", text)
        self.assertIn("never picks the next ticket", text)

    def test_only_the_outer_loop_talks_to_the_board(self):
        board_refs = ("notion.md", "flo.md")
        forbidden_instruction = re.compile(
            r"\b(?:notion|flo)\b|board's tool|write on the (?:ticket's )?page|or on the board|put on the board",
            re.I,
        )
        inner_docs = [SKILLS / name / "SKILL.md" for name in INNER_LOOP_SKILLS]
        inner_docs += sorted((SKILLS / "jt-work" / "playbooks").glob("*.md"))
        inner_docs.append(SKILLS / "jt-work" / "worker.md")
        for path in inner_docs:
            text = path.read_text()
            targets = re.findall(r"\]\(([^)#]+)\)", text)
            for ref in board_refs:
                self.assertFalse(
                    any(target.endswith(ref) for target in targets),
                    f"{path} links to {ref}; only the outer loop talks to the board",
                )
                self.assertNotIn(f"references/{ref}", text, f"{path} names references/{ref}")
            match = forbidden_instruction.search(text)
            self.assertIsNone(
                match,
                f"{path} tells the inner loop to use the board ({match.group(0) if match else ''!r})",
            )
        work_text = (SKILLS / "jt-work" / "SKILL.md").read_text()
        self.assertIn("references/starting-sessions.md", work_text)
        self.assertIn("references/files.md", work_text)
        starting = (SKILLS / "jt-work" / "references" / "starting-sessions.md").read_text()
        starting_targets = re.findall(r"\]\(([^)#]+)\)", starting)
        for ref in board_refs:
            self.assertTrue(
                any(target.endswith(ref) for target in starting_targets),
                f"starting-sessions.md must link to {ref} for the outer loop",
            )
            intro = "\n".join((SKILLS / "jt-work" / "references" / ref).read_text().splitlines()[:10]).lower()
            self.assertIn("outer loop", intro, f"{ref} intro must state it is for the outer loop")
        script_text = (SKILLS / "jt-work" / "scripts" / "jtek.py").read_text()
        self.assertNotIn("create the ticket there with the board's tool", script_text)
        self.assertNotIn("Otherwise read its page and", script_text)

    def test_statuses_match_the_script(self):
        script = (SKILLS / "jt-work" / "scripts" / "jtek.py").read_text()
        statuses = json.loads(re.search(r"^STATUSES = (\[.+\])$", script, re.M).group(1))
        for doc in (SKILLS / "jt-work" / "references" / "ticket.md", ROOT / "README.md"):
            rows = re.findall(r"^\| ([A-Z][A-Za-z ]+?) \|", doc.read_text(), re.M)
            self.assertEqual([r for r in rows if r in statuses], statuses, doc)

    def test_version_is_consistent(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(plugin["version"], VERSION)
        self.assertEqual(market["plugins"][0]["version"], VERSION)
        cursor = json.loads((ROOT / ".cursor-plugin" / "plugin.json").read_text())
        cursor_market = json.loads((ROOT / ".cursor-plugin" / "marketplace.json").read_text())
        self.assertEqual(cursor["version"], VERSION)
        self.assertEqual(cursor_market["metadata"]["version"], VERSION)
        self.assertIn(f"## {VERSION}", (ROOT / "CHANGELOG.md").read_text())


if __name__ == "__main__":
    unittest.main()
