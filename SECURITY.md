# Security

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub: **Security tab → Report a vulnerability** on this repository. Do not open a public issue for an unfixed vulnerability.

## Trust model (read before installing)

`jtek-skill` is not a sandbox. `jtek.py check` runs commands on your machine.

- **Which commands:** only the ones in `jtek.json` on the base branch of the repository. The script reads the file with `git show <base>:jtek.json`, so an edit in a ticket's worktree or branch has no effect until it is merged.
- **How they run:** each command is split into a program and arguments and run without a shell, in the ticket's worktree, with your full environment (including any tokens in it). The time limit is 30 minutes per check.
- **What a ticket can do:** name checks that `jtek.json` already declares. A name that is not declared is refused. Ticket text, including text fetched from Notion, is never executed.
- **Treat `jtek.json` like CI config.** Review every change to it before you merge, including in pull requests from others.

## What the script cannot enforce

- It cannot tell who ran a command. An agent that ignores its instructions could commit to the base branch, edit a ticket file to `status: Todo`, or record a verdict on its own change. The skills forbid these. Do not put `jtek.py release` or `jtek.py verdict` on an always-allow list in the session that writes code.
- It does not prove the reviewer is a different session. `verdict --by` is a label.

## What the skills do outside the repository

- **Worktrees:** `start` creates `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.
- **State:** tickets, claims, check logs, review notes, and results are under `<git-common-dir>/jtek/` and are not committed. Check logs can contain secrets that a command printed.
- **Network:** the script calls `gh pr view` (read-only) in `list --sync`. Nothing else.
- **Push:** the `jt-ship` skill tells the agent to push the ticket branch and open a pull request. This sends your code to that remote on purpose.
- **Merge:** never. There is no command for it.
- **Notion:** the agent reads the ticket page and writes its status and a result comment with whatever Notion connection it has. The script does not talk to Notion.
