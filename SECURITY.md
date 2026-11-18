# Security

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub: **Security tab → Report a vulnerability** on this repository. Do not open a public issue for an unfixed vulnerability.

## Trust model (read before installing)

`jtek-skill` is not a sandbox. `jtek.py check` runs commands on your machine, and so does `jtek.py start`, which runs the same checks once on the base before any edit.

- **Which commands:** only the checks and the `setup` command in `jtek.json` on the base branch of the repository. The script reads the file with `git show <base>:jtek.json`, so an edit in a ticket's worktree or branch has no effect until it is merged.
- **How they run:** each command is split into a program and arguments and run without a shell, in the ticket's worktree, with your full environment (including any tokens in it), except `NOTION_TOKEN`, which is removed. The time limit is 30 minutes per check.
- **What a ticket can do:** name checks that `jtek.json` already declares. A name that is not declared is refused. Ticket text is read from Notion and is never executed. Ticket fields come from the page's properties only, so text in the page body cannot waive the review or choose checks.
- **Treat `jtek.json` like CI config.** Review every change to it before you merge, including in pull requests from others.
- **The `verify` script is code too.** The `jt-harness` skill writes a script and the `.jtek/` folder. `jtek.json` names that script, but the script itself is read from the ticket's worktree, so a ticket can change it. Review changes to it, and to anything a check runs, as you review product code. The result's `attention:` line names such a file when a ticket changes it, along with `jtek.json`, `.jtek/`, CI config, lockfiles, and deleted tests. It is a pointer for the reviewer, not a block.

## What the script cannot enforce

- It cannot tell who ran a command. An agent that ignores its instructions could commit to the base branch, use the Notion token to set a page to Todo, or record a verdict on its own change. The skills forbid these. Do not put `jtek.py release` or `jtek.py verdict` on an always-allow list in the session that writes code.
- It does not prove the reviewer is a different session. `verdict --by` is a label.
- It does not check that the evidence is true. The evidence is the author's account, written for the human to read first. The checks and the reviewer's own runs are what test the change.

## What the skills do outside the repository

- **Worktrees:** `start` creates `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.
- **State:** a copy of each ticket, claims, check logs, review notes, and results are under `<git-common-dir>/jtek/` and are not committed. Check logs can contain secrets that a command printed.
- **Network:** the script calls the Notion API, and `gh pr view` (read-only) in `finish` and `list --sync`. Nothing else.
- **Push:** the `jt-ship` skill tells the agent to push the ticket branch and open a pull request. This sends your code to that remote on purpose.
- **Merge:** never. There is no command for it.
- **Notion:** the script reads the board with the token in `NOTION_TOKEN`, and writes Status, Waiting, PR, and one comment per result on a ticket's page. The comment holds the result block and the evidence text. Diffs and logs are not sent.
- **The token:** every session that runs `jtek.py` holds it, and an agent can read its own environment. Share only the board database with the integration, so the token reaches nothing else. `JTEK_NOTION_API` moves the requests to another address for tests, and the script refuses any address that is not this machine.
