import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEK_SKILLS = """## `<TEK_SKILLS>` makes the work sharper

`/jt-do-work` may open one name from this row per moment, and only when that skill's `description` matches the moment.

| Moment | Words in that skill's description |
|---|---|
| The card still has two outcomes before you write `ask:` | grill, interview |
| A `fix` whose cause is still unclear, before a red test | diagnose, debug |
| Editing production code | YAGNI, stdlib, delete |

If no name in the row matches the moment, continue without opening a skill. Do not open this group during the repo diff review.
"""


class RepoSkillRuleTests(unittest.TestCase):
    def test_missing_repo_skill_must_review_the_diff_itself(self) -> None:
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        do_card = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(TEK_SKILLS.strip(), skills)
        start = skills.index("## `<TEK_SKILLS>`")
        end = skills.index("## `<REPO_SKILLS>`")
        self.assertEqual(skills[start:end].strip(), TEK_SKILLS.strip())
        for text in (skills, do_card):
            self.assertNotIn("note it in the plan and continue along loop.md", text)
            self.assertNotIn("note it in the plan and continue", text)
        self.assertIn("review this card's diff yourself", skills)
        self.assertIn("Do not skip", skills)
        self.assertIn("cannot review the diff", skills)
        self.assertIn("A note in the plan is not that review", skills)
        self.assertIn("review this card's diff yourself", do_card)
        self.assertIn("Do not skip that review", do_card)
        self.assertIn("cannot review the diff", do_card)
        self.assertIn("A note in the plan is not that review", do_card)
        self.assertIn("Do not set `review:`", skills)
        self.assertIn("Do not set `review:`", do_card)

    def test_tek_skills_row_on_the_board_template_is_unchanged(self) -> None:
        template = (REPO / "skills" / "jt-card-gate" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "`<TEK_SKILLS>` names skills that make the work sharper. "
            "`/jt-do-work` opens a name from this row when the card still has two paths, "
            "when it is finding the bug cause before a test, and when it is editing production code. "
            "An empty cell opens nothing.",
            template,
        )

    def test_name_check_is_not_in_ci_and_the_test_limit_is_not_a_loop_paragraph(self) -> None:
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(encoding="utf-8")
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("reach-review", loop)
        self.assertIn("/jt-next-step", loop)
        self.assertIn("version 20", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("start:", loop)
        self.assertNotIn("port:", loop)
        self.assertNotIn("click:", loop)
        self.assertNotIn("browser-empty", loop)
        self.assertIn("The gate refuses", loop)
        self.assertIn("`docs` does not open", skills)
        self.assertNotIn("one-off-checker", loop)
        self.assertNotIn("repeat-patch", loop)
        self.assertNotIn("reach-review", loop)


COMMANDS = [
    "/jt-new-board",
    "/jt-ask-brief",
    "/jt-new-card",
    "/jt-read-board",
    "/jt-find-skills",
    "/jt-do-work",
    "/jt-open-work",
    "/jt-send-back",
    "/jt-merge",
    "/jt-drop-card",
    "/jt-move-card",
    "/jt-next-step",
]

OLD_NAMES = [
    "/jt-gate",
    "/jt-setup-board",
    "/jt-brief",
    "/jt-add-card",
    "/jt-do-card",
    "/jt-open-review",
    "/jt-scan-skills",
    "/jt-mark-merge",
    "/jt-mark-close",
]

OLD_SCREEN = (
    "One round is one full attempt. The evidence is that the relevant tests are green, "
    "and for screen work of every kind, not only `fix`, "
    "the same steps on the same screen do not show the bug. "
    "Screen work that cannot be clicked is not this round. Follow **Write ask**."
)


class RenamedCommandTests(unittest.TestCase):
    def test_only_the_new_command_names_and_the_four_behavior_changes(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        rule = (REPO / "skills" / "jt-card-gate" / "SKILL.md").read_text(encoding="utf-8")
        find = (REPO / "skills" / "jt-find-skills" / "SKILL.md").read_text(encoding="utf-8")
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        drop = (REPO / "skills" / "jt-drop-card" / "SKILL.md").read_text(encoding="utf-8")
        move = (REPO / "skills" / "jt-move-card" / "SKILL.md").read_text(encoding="utf-8")
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `(/jt-[^`]+)`", readme, re.M)
        self.assertEqual(rows, COMMANDS)
        self.assertEqual(re.findall(r"^\| `(/jt-[^`]+)`", loop, re.M), COMMANDS)
        self.assertEqual(readme.count("\n## "), 4)
        self.assertIn("not a catalog of dozens of skills", readme)
        self.assertIn("npx skills add thitinan147/jtek-skill -g", readme)
        self.assertIn("name: jt-card-gate", rule)
        for text in (readme, loop, rule, find, merge, drop, move, work):
            for old in OLD_NAMES:
                self.assertNotIn(old, text)
        self.assertIn("`<REPO_SKILLS>` for the open repo", find)
        self.assertIn("`<TEK_SKILLS>` for the moments the loop already uses", find)
        self.assertIn("Do not write `card-loop/board.md` until the human accepts", find)
        self.assertIn("Do not run an install command", find)
        self.assertNotIn("only the folder of the agent that is running", find)
        self.assertIn("every folder in home whose name starts with `.`", find)
        self.assertIn("Follow each symlink to the real file", find)
        self.assertIn("The same real path counts as one skill", find)
        self.assertIn("`on this machine`", find)
        self.assertIn("`install this`", find)
        self.assertIn("skills.sh/api/search", find)
        self.assertNotIn("-a <running-agent>", find)
        board = (REPO / "skills" / "jt-new-board" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("the status table from **Search**", board)
        self.assertIn("install this", board)
        self.assertIn("a `playwright` command is on PATH", board)
        self.assertIn("Do not put a session or MCP browser name", board)
        self.assertNotIn(
            "If `playwright` is in `package.json`, write `playwright`. If not and `cypress` is present, write `cypress`. Otherwise leave the cell empty.",
            board,
        )
        self.assertIn("does not run git merge", merge)
        self.assertIn("changes only the mark on that line", merge)
        self.assertIn("Change `- [ ]` on that line to `- [x]`", drop)
        self.assertIn("drop:", drop)
        self.assertIn("Do not delete other lines", drop)
        self.assertIn("Do not change the status on that line", move)
        self.assertIn("Do not touch code", move)
        self.assertIn("Do not merge", move)
        self.assertIn("The agent does not call those three commands", loop)
        self.assertIn("`/jt-send-back` `/jt-merge` `/jt-drop-card`", loop)
        self.assertIn("The human merges", loop)
        self.assertIn("does not run git merge", loop)
        self.assertNotIn(OLD_SCREEN, work)
        self.assertIn("**Three rounds**", work)
        self.assertIn(
            "One round is one full attempt. The evidence is that the relevant tests are green, "
            "and for screen work of every kind, not only `fix`, "
            "the same steps on the same screen do not show the bug. "
            "Screen work that cannot be clicked does not count as this round. Write `ask:`.",
            loop,
        )
        self.assertIn("disable-model-invocation: true", merge)
        self.assertIn("disable-model-invocation: true", drop)
        send = (REPO / "skills" / "jt-send-back" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", send)
        dirs = sorted(path.name for path in (REPO / "skills").iterdir() if path.is_dir())
        self.assertEqual(dirs, sorted([name[1:] for name in COMMANDS] + ["jt-card-gate"]))


class PairedRepoRuleTests(unittest.TestCase):
    def test_pair_rules_live_in_the_skills_and_the_gate(self) -> None:
        new_board = (REPO / "skills" / "jt-new-board" / "SKILL.md").read_text(encoding="utf-8")
        new_card = (REPO / "skills" / "jt-new-card" / "SKILL.md").read_text(encoding="utf-8")
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        gate = (REPO / "skills" / "jt-next-step" / "gate.py").read_text(encoding="utf-8")
        template = (REPO / "skills" / "jt-card-gate" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("Ask once", new_board)
        self.assertIn("`none`", new_board)
        self.assertIn("Do not invent a repo name", new_board)
        self.assertIn("Do not ask again", new_board)
        self.assertIn("card-loop/paired.md", new_board)
        self.assertIn("Do not ask where the paired repo is", new_card)
        self.assertIn("is one card", new_card)
        self.assertIn("does not include that name", new_card)
        self.assertIn("Do not create it because the board has the name", new_card)
        self.assertIn("Do not set status in the paired repo", work)
        self.assertIn("Do not create `card-loop/board.md`", work)
        self.assertIn("Do not move the whole queue off the primary repo", work)
        self.assertIn("card-loop/paired.md", work)
        self.assertIn("point back", work)
        self.assertIn("Do not create this file only because the board recorded the name", work)
        self.assertIn("The human merges both repos", work)
        self.assertNotIn(OLD_SCREEN, work)
        self.assertIn("**Three rounds**", work)
        self.assertIn("pair-not-passed", gate)
        self.assertNotIn("jtekth", gate)
        self.assertNotIn("git merge", gate)
        self.assertIn("pair-not-passed", work)
        self.assertIn("Ask once", loop)
        self.assertIn("Do not move the whole queue off the primary repo", loop)
        self.assertIn("Do not create this file only because the board recorded the name", loop)
        self.assertIn("The human merges both repos", loop)
        self.assertIn("does not run git merge", loop)
        self.assertIn("The agent does not call those three commands", loop)
        self.assertIn("`/jt-send-back` `/jt-merge` `/jt-drop-card`", loop)
        self.assertIn("does not run git merge", merge)
        self.assertIn("The human merges both repos", merge)
        self.assertEqual(template.count("\npair:"), 1)
        self.assertEqual(readme.count("\n## "), 4)
        self.assertIn("/jt-new-board", readme)
        self.assertFalse(list(REPO.glob("*playbook*")))
        self.assertFalse(list((REPO / "skills").glob("**/*playbook*")))


class RepeatRuleTests(unittest.TestCase):
    def test_the_three_rules_agree_across_the_skills_and_the_readme(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        nxt = (REPO / "skills" / "jt-next-step" / "SKILL.md").read_text(encoding="utf-8")
        new_card = (REPO / "skills" / "jt-new-card" / "SKILL.md").read_text(encoding="utf-8")
        reading = (REPO / "skills" / "jt-read-board" / "SKILL.md").read_text(encoding="utf-8")
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        plan = (REPO / "skills" / "jt-card-gate" / "assets" / "plan.template.md").read_text(
            encoding="utf-8"
        )
        card = (REPO / "skills" / "jt-card-gate" / "assets" / "card.template.md").read_text(
            encoding="utf-8"
        )
        gate = (REPO / "skills" / "jt-next-step" / "gate.py").read_text(encoding="utf-8")
        self.assertIn("existing check commands", loop)
        self.assertIn("new check script", loop)
        for text in (readme, work):
            self.assertIn("existing check commands", text)
            self.assertIn("new check script", text)
        for text in (readme, loop, work):
            self.assertIn("update-rule", text)
            self.assertIn("layer", text)
        self.assertIn("Do not split into parallel agents", readme)
        self.assertIn("Do not split into parallel agents without a link", loop)
        self.assertIn("refused: one-off-checker", work)
        self.assertIn("refused: repeat-patch", work)
        self.assertIn("refused: related", work)
        self.assertIn("`reason` is `related`", nxt)
        self.assertIn("refused: one-off-checker", nxt)
        self.assertIn("refused: repeat-patch", nxt)
        self.assertIn("step: ask", nxt)
        self.assertIn("Do not split into parallel agents", new_card)
        self.assertIn("Do not report them as parallel work", reading)
        self.assertIn("does not replace the check commands on the board", skills)
        self.assertIn("This row may be empty", skills)
        self.assertIn("update-rule", plan)
        self.assertIn("layer:", card)
        self.assertIn("one-off-checker", gate)
        self.assertIn("repeat-patch", gate)
        self.assertIn("update-rule", gate)
        self.assertFalse(list(REPO.glob("*playbook*")))
        self.assertFalse(list((REPO / "skills").glob("**/*playbook*")))
        self.assertEqual(readme.count("\n## "), 4)


class DraftPrSkillTests(unittest.TestCase):
    def test_the_loop_opens_a_draft_pr_before_review_and_merge_only_marks(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        nxt = (REPO / "skills" / "jt-next-step" / "SKILL.md").read_text(encoding="utf-8")
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        command = "gh pr create --draft --base <queue> --head card-<id>"
        for text in (readme, loop, work, nxt):
            self.assertIn(command, text)
        self.assertIn("The line must not be `review:`", loop)
        for text in (readme, work, nxt):
            self.assertIn("The line must not be `review:`", text)
        for text in (work, nxt):
            self.assertIn("refused: pr-missing", text)
            self.assertIn("step: ask", text)
        self.assertIn("Do not open a duplicate", work)
        self.assertIn("skip `gh pr create`", nxt)
        self.assertIn("does not open a PR", merge)
        self.assertIn("does not merge a PR", merge)
        self.assertIn("does not run git merge", merge)
        self.assertIn("git merge-base --is-ancestor", merge)
        self.assertIn("including a merge through a pull request", readme)
        self.assertIn("does not open a PR, does not merge a PR, and does not run git merge", loop)
        self.assertNotIn("reach-review", loop)


if __name__ == "__main__":
    unittest.main()
