# Quickstart

From a blank machine to a ready repository, on one page. Do the four steps in order. Each step ends with what you should see.

Prerequisites: `git` 2.31 or later, Python 3.10 or later, and a coding agent that loads skills. jtek stores nothing outside your machine and your repository; there is no jtek account or token.

## Step 1. First install

**Claude Code**, as two separate prompts:

```text
/plugin marketplace add thitinan147/jtek-skill
```

```text
/plugin install jtek@jtek-skill
```

**Other agents** (Cursor, Antigravity, Codex, ...):

```bash
npx skills add thitinan147/jtek-skill
```

Install the whole set, not one skill at a time. The script lives in `jt-work` and `jt-review`, so a step skill installed alone cannot run it.

> **On this box:** `agy` and `grok` load jtek through a symlink to `/workspace/tools/jtek-skill` instead of installing through `/plugin` or `npx`. Other machines follow the commands above.

**You should see:** seventeen skills — `jt` and sixteen whose names start with `jt-` (for example, type `/jt-` in Claude Code to see the list).

## Step 2. Machine-wide init

There is **no single machine-level init command** today. These are the real machine-level pieces that exist:

- **Storage:** jtek stores machine and repository data under `~/.jtek`. There is no required `~/.jtek/config` file; when both `~/.jtek/config` and a per-repository file are absent, the defaults apply (empty board, tickets as files).
- **Reviewer list (optional):** `/jt-agents` runs `jtek.py doctor --agents` and proposes `~/.jtek/agents.json`. The owner must say yes before it is written. Skip until you want a second-vendor reviewer.
- **Style file (optional):** `/jt-me` proposes `~/.jtek/me.md`. The owner must say yes before it is written.
- **GitHub (when using GitHub remotes):** sign in and check status:

```bash
gh auth login
gh auth status
```

  To push CI workflow YAML under `.github/workflows/`, also add the `workflow` scope:

```bash
gh auth refresh -s workflow
```

  A repository with no remote needs none of this.
- **Migrating older machine files:** if `~/.config/jtek/agents.json` or `~/.config/jtek/me.md` already exist, `jtek.py migrate` moves them into `~/.jtek` and refuses to overwrite.

**You should see:** `gh auth status` prints `Logged in to github.com` (when using GitHub). Optional files (`~/.jtek/agents.json`, `~/.jtek/me.md`) appear only after you accept `/jt-agents` or `/jt-me`.

## Step 3. First repo

Open your agent inside the repository and type:

```text
/jt-init
```

It guesses checks from `package.json`, `Makefile`, `pyproject.toml`, and CI workflows, asks once (including the board question), writes `~/.jtek/repos/<repo id>/jtek.json`, runs the `jt-harness` skill, and then runs `jtek.py doctor`. Nothing is written into the repository.

If the repository still has an old `jtek.json` or `.jtek/`, `/jt-init` runs `jtek.py migrate` instead and tells you to commit the removal. If doctor says it cannot find the base branch, make the first commit first.

**You should see:** `jtek.py doctor` prints no `missing` line and ends with `ready:` (lines marked `optional` can wait). Running `/jt-status` shows `พร้อมใช้` on its first line, followed by the work table; if anything required is still missing, the first line starts with `ยังไม่พร้อม`, names what is missing, and names the command to fix it.

## Step 4. Board

You choose the board when `/jt-init` asks `board? none (tickets as files) / Notion database link / FLO product link`:

- **`none` (tickets as files):** records `"board": ""` and keeps tickets in `~/.jtek/repos/<repo id>/tickets/`. **You should see:** `no board: the tickets are files in ...` in `jtek.py doctor`. Format and rules: [files.md](skills/jt-work/references/files.md).
- **Notion:** connect the Notion tool in your outer-loop agent (worker sessions do not need it), give it access to your database, and paste the database link when `/jt-init` asks. **You should see:** `` `board`: the Notion database or FLO product link `` in `jtek.py doctor`, and your outer-loop agent can read the database against the schema in [notion.md](skills/jt-work/references/notion.md).
- **FLO:** connect the FLO tool in your outer-loop agent (worker sessions do not need it) and paste the FLO product link when `/jt-init` asks. **You should see:** `` `board`: the Notion database or FLO product link `` in `jtek.py doctor`, and your outer-loop agent can read the product against the schema in [flo.md](skills/jt-work/references/flo.md).

## Next

- **Day-to-day flow** (writing the first ticket, `/jt` and `/jt-work`, `/jt-review` in a fresh session, `/jt-status`, and merging yourself — jtek never merges): [README.md](README.md).
- **Ticket format:** [ticket-template.md](skills/jt-work/references/ticket-template.md).
- **Multi-repo features & outer-loop automation:** [two-repos.md](skills/jt-work/references/two-repos.md) and [starting-sessions.md](skills/jt-work/references/starting-sessions.md).
