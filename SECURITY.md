# Security

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub: **Security tab → Report a vulnerability** on this repository. Do not open a public issue for an unfixed vulnerability.

## Trust model (read before installing)

`jtek-skill` is not a sandbox. `jtek.py check` runs commands on your machine, and so does `jtek.py start`, which runs the same checks once on the base before any edit.

- **Which commands:** only the checks, the `setup` command, and the `pr_state` command in `jtek.json` on the base branch of the repository. The script reads the file with `git show <base>:jtek.json`, so an edit in a ticket's worktree or branch has no effect until it is merged.
- **How they run:** each command is split into a program and arguments and run without a shell, in the ticket's worktree, with your full environment (including any tokens in it). The time limit is 30 minutes per check.
- **What a ticket can do:** name checks that `jtek.json` already declares. A name that is not declared is refused. Ticket text is read from Notion by the agent and is never executed. The agent is told to take ticket fields from the page's properties only. The script cannot check that, so a session that copies a line such as `review: human` from the page body into the header would waive the review.
- **Treat `jtek.json` like CI config.** Review every change to it before you merge, including in pull requests from others.
- **The `verify` script is code too.** The `jt-harness` skill writes a script and the `.jtek/` folder. `jtek.json` names that script, but the script itself is read from the ticket's worktree, so a ticket can change it. Review changes to it, and to anything a check runs, as you review product code. The result's `attention:` line names such a file when a ticket changes it, along with `jtek.json`, `.jtek/`, CI config, lockfiles, files such as `Makefile` and `package.json`, and deleted or shortened tests. It works from a list of known names plus your `watch` patterns, so a file the list does not know is not named. It is a pointer for the reviewer, and it only blocks the `review: human` waiver.

## What the script cannot enforce

- It cannot tell who ran a command. An agent that ignores its instructions could commit to the base branch, set a page to Todo with its Notion tool, or record a verdict on its own change. The skills forbid these. Do not put `jtek.py release` or `jtek.py verdict` on an always-allow list in the session that writes code.
- It trusts what the session passes in: the header lines of the ticket file, `--resume`, `--no-baseline`, and the `JTEK_BASE` and `JTEK_STATE` variables. Its state is plain files under the git directory, and it reads the local base branch, not the remote one.
- It does not prove the reviewer is a different session. `verdict --by` is a label.
- It does not check that the evidence is true. The evidence is the author's account, written for the human to read first. The checks and the reviewer's own runs are what test the change.

## What the skills do outside the repository

- **Worktrees:** `start` creates `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.
- **State:** a copy of each ticket, claims, check logs, review notes, and results are under `<git-common-dir>/jtek/` and are not committed. Check logs can contain secrets that a command printed.
- **Network:** the script calls `gh pr view` (read-only) in `finish` and `sync`, or the `pr_state` command when the project set one. Nothing else.
- **Push:** the `jt-ship` skill tells the agent to push the ticket branch and open a pull request. This sends your code to that remote on purpose.
- **Merge:** never. There is no command for it.
- **Notion:** the script does not talk to Notion. The agent reads the ticket page with its Notion tool, and writes Status, Waiting, PR, and one comment per result, as the script's `board:` line says. The comment holds the result block and the evidence text. Diffs and logs are not sent.
