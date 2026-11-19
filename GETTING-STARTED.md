# Getting started

From nothing connected to your first ticket merged. Do the steps in order. Each one ends with what you should see.

> **Not walked end to end yet.** The script steps are tested. The steps that go through Notion and a real pull request have not been run by anyone. If a step does not behave as written, that is a bug in this guide: please open an issue.

Most steps are things you say to your agent. Text in a `text` block is a prompt. Text in a `bash` block is a command you run yourself.

## What you connect

| You connect | Why | Needed |
|---|---|---|
| A coding agent that loads skills (Claude Code, Cursor, Codex, ...) | It does the work | Yes |
| `git` 2.31 or later, and Python 3.10 or later | The script uses both | Yes |
| Notion, as a tool in the agent | The board lives there | Yes |
| GitHub, through the `gh` command, signed in | The agent opens pull requests with it, and the script reads their state and CI | With GitHub: yes |
| Your project's own commands for lint, types, and tests | They are the checks | At least one |
| A way to run your real app from the command line | So the agent can see a change work | Strongly advised |

jtek stores nothing outside your machine and your repository. There is no jtek account and no token.

## 1. Install the skills

```bash
npx skills add thitinan147/jtek-skill
```

Or in Claude Code, as two separate prompts:

```
/plugin marketplace add thitinan147/jtek-skill
```
```
/plugin install jtek@jtek-skill
```

**You should see:** eleven skills whose names start with `jt-`. In Claude Code, type `/jt-` and they are listed.

## 2. Connect GitHub

```bash
gh auth login
gh auth status
```

**You should see:** `Logged in to github.com`.

A repository with no remote at all needs none of this: its tickets end without a pull request, and you set Done by hand.

## 3. Connect Notion and create the board

1. In Notion, create one database. Give it the eleven properties in [notion.md](skills/jt-work/references/notion.md#the-database). The names and types must match exactly.
2. Connect the Notion tool in your agent, and give it access to that database. In Claude Code: `/mcp`, then Notion.
3. Copy the database's link. You need it in step 4.
4. Ask the agent to check your work:

```text
Read the Notion database at <link>. Compare its properties with the table in
the notion.md reference of the jt-work skill. List every property that is
missing, misnamed, or has another type, and every Status option that is missing
or spelled differently. Change nothing.
```

**You should see:** an empty list. Fix what it names and ask again.

## 4. Set up the repository

Do this in each repository the board serves.

```text
Run jtek.py init in this repository. Then read the package scripts and the CI
config, and propose one command per check for jtek.json. Set "board" to <link>
and "name" to <the name tickets will use for this repository>.
Show me the file. Do not commit it.
```

Read the file. A command is one program with arguments: a pipeline goes into a script. Delete the checks your project does not have. Then commit `jtek.json` on your base branch yourself.

```text
Run jtek.py doctor.
```

**You should see:** no `missing` line, and `ready:` at the end. The `optional` lines about `verify` and `.jtek/verify.md` are step 5.

If it says it cannot find the base branch, the repository has no commit yet: make the first commit.

## 5. Build the harness

```text
Follow the jt-harness skill for this repository.
```

It writes `.jtek/verify.md`, a feature map, and one script, and it proposes a `verify` check. It must show you the check passing on the working app and failing when a feature is broken on purpose.

Read what it wrote, add `verify` to `jtek.json`, and commit both on the base branch.

**You should see:** `jtek.py doctor` with no `optional` line for `verify`.

You can skip this step for a first try. Then a passing check only means the code compiles and the tests pass, and nothing has run the real app.

## 6. Write the first ticket

Pick something small and safe. Create a page on the board:

- **Name:** `Add a --version flag to the command-line tool`
- **Kind:** `feature`
- **Repo:** the `name` in this repository's `jtek.json`
- **Body:**

```markdown
## Goal
Running the tool with --version prints its version, so a user can report it in a bug.

## Done when
- `mytool --version` prints the version from the package file and exits with 0
- `mytool --help` lists the flag

## Out of scope
- the output of every other flag stays exactly as it is now
```

The three headings must be named exactly like this. `Done when` holds only top-level list items, one outcome each. Each one must be something that can be seen working.

Notion gives the page an id, such as `T-1`. If you made other pages while testing, yours has another number: use that one below.

Set **Status** to **Todo**. Nothing happens until you start a session.

## 7. Work it

Open a session in the repository:

```text
/jt-work T-1
```

**You should see, in this order:**

1. The agent reads the page and runs `jtek.py start`. The page changes to **In Progress**.
2. It works in a new folder beside your repository, `<repo>.jtek/T-1`. Your own checkout is not touched.
3. It runs `jtek.py check` until every check passes.
4. It opens a pull request, and ends with a `jtek-result` block that says `outcome: needs-review`.

That outcome is correct. A change needs a verdict from a session that did not write it.

An agent that can start a separate session by itself may do steps 8 and 9 on its own, and end with `outcome: review`. Then go to step 10.

## 8. Get the verdict

Open a **new** session in the repository. It must not be the one from step 7.

```text
/jt-review T-1
```

**You should see:** `verdict: PASS by ...`, or `FAIL` with findings. On `FAIL`, run `/jt-work T-1` again: the agent reproduces each finding, fixes what reproduces, and you repeat this step.

## 9. Finish

```text
/jt-work T-1
```

**You should see:** `outcome: review`. The page is now **Review**, with the pull request link and a comment that holds the result and the evidence.

## 10. Review and merge

1. Read the evidence comment. It has one line per `Done when` item: what was run, and what was seen.
2. Read the `attention:` line of the result. It names the files that decide whether checks pass.
3. Read the diff, and merge the pull request yourself. jtek never merges.

Then set the page to **Done**, or ask an agent:

```text
Read the board and run jtek.py sync, as the starting-sessions.md reference of the jt-work skill says.
```

**You should see:** the page is **Done**, and the folder `<repo>.jtek/T-1` is gone.

That is the whole flow.

## When a session stops with a question

The result says `outcome: needs-human`, and the page has **Waiting** set and a comment with the question.

1. Answer on the page.
2. Set **Status** to **Todo**. This is the only signal that restarts the ticket.
3. Run `/jt-work T-1` again.

The same three steps ask for a fix on a ticket that is in Review.

## When the script refuses

`jtek.py` prints `refused:` and what to do. The agent must do that, and must not work around it.

| It says | What it means | What you do |
|---|---|---|
| `jtek.json is not committed on <base>` | The checks are read from the base branch | Commit `jtek.json` there |
| `is ..., not Todo` | Only a Todo ticket can start | Set Status to Todo |
| `comes after ..., which is not Done` | A ticket in After is not merged yet | Merge that one first |
| `is for the repository ...` | The ticket's Repo is another repository | Start the session there |
| `fails on <base> before any change` | Your base branch is red | Fix the base branch first |
| `` `Done when` may hold only top-level list items `` | The page has other text or nested items there | Fix the page |
| `is already claimed` | Another session has the ticket | Wait for it, or tell a new session that the earlier one died |
| `an earlier start ... was interrupted` | A `start` was killed half way | Ask the agent to run `jtek.py release <id>`, then start again |
| `the worktree ... is gone` | The ticket's folder was deleted | The same: `jtek.py release <id>`, set the page to Todo, and start again. The commits are on the branch |
| `the ticket changed after the evidence was saved` | You edited the ticket | The agent reads it again, does what it now asks, and passes new evidence. A new verdict is needed too |
| `has no change against` | The branch is empty | Nothing to review. If the ticket needs no change, the agent stops and says so |
| `has a remote, so the change needs a pull request` | `--no-pr` is only for a repository without a forge | The agent opens a pull request |
| `the code changed after the evidence was saved` | The evidence describes an older change | The agent sees it work again and passes new evidence |
| `check runs have failed` | Three runs failed | The agent stops and asks you |
| `checks have not passed on the current commit` | A commit came after the last check | The agent runs `check` again |
| `CI is failing` | The pull request is red on the forge | The agent fixes it before it reaches you |
| `stopped with a question` | The ticket waits for you | Answer, then set Todo |

## Next

- **Several repositories, one feature:** [two-repos.md](skills/jt-work/references/two-repos.md)
- **Let something else start the sessions:** [starting-sessions.md](skills/jt-work/references/starting-sessions.md). Work three tickets by hand first.
- **A mistake that happened twice:** the `jt-learn` skill turns it into a check, so it cannot happen a third time.
