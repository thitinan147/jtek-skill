# Changelog

## 26.42.0 - the remote, not a local ref, says whether there is a forge

A re-review of 26.41.0 moved `refs/remotes/origin/HEAD` onto an unpushed commit with `"forge": false`, and `finish --no-pr` shipped. The other gates from that review held. This reads the remote.

- `finish --no-pr` asks the remote for its default branch (`git ls-remote --symref origin HEAD`), fetches that exact tip, and reads `jtek.json` there. A local `origin/HEAD` does not count. If the remote cannot be read, or the fetched tip does not match, `--no-pr` is refused.
- A backtick or a quote exempts a quality word only when that word is inside it. `feels faster `x`` is refused. `the label reads `faster`` is allowed. A verb such as `prints` does not exempt the other words on the line.
- ความเร็ว is the unobservable noun for speed. The short word เร็ว does not also match inside it. ไม่ง่าย stays allowed.
- Format characters (Unicode category Cf) are stripped before the Done when check: word joiner U+2060, direction marks U+200E and U+200F, soft hyphen U+00AD, and the zero-width characters already stripped.
- A check is lint-class by the pieces of its name, not only the exact name `lint`: `eslint`, `ruff`, `ruff-format`, `prettier`, `tsc`, `mypy`, and the same family. A behaviour check is any other name. Prefix `behaviour-` to mark one whose command is a linter (`behaviour-eslint`).
- `broke.json` is sealed with the same key as the authors list. A hand-written proof does not count.
- `refs/tags/jtek/<id>` reserves that id.
- `--at` on a fast-forward uses the reflog or the remote-tracking base. With both gone, the review is refused instead of showing only the last commit.
- `doctor` warns when a setup script it can read creates a virtualenv, not only when the setup string itself says `venv`.

## 26.41.0 - a green light has to be a real one

A review of 26.40.0 found ways through the new gates. Each one is closed in the script.

- `finish` ships a pull request only when every required check is SUCCESS, or when the project's `pr_state` command prints `none` because the repository has no checks. SKIPPED, NEUTRAL, and a mix of those with SUCCESS stay pending. A null, missing, or empty rollup is `absent`, not `none`: `finish` waits `JTEK_CI_APPEAR_TRIES` (3) looks and `JTEK_CI_APPEAR_WAIT` (2) seconds for the first check, then refuses.
- `broke` runs every declared check and keeps a log per item. A lint, syntax, format, or import failure does not prove the item. The stored text has to match the current Done when line, so rewriting that line drops the proof.
- `ticket --save` keeps `kind`, `area`, and `repo` across a blank line, and refuses a saved file whose `repo` was dropped.
- The next ticket id treats `refs/remotes/*/jtek/<id>` and an id named in commit history as taken.
- `show` and `verdict --pr` do not trust a local `refs/pull/<n>/head` or `refs/jtek/pull/<n>/head` until a fetch updates it or `gh` reports the same commit. `--at` on a fast-forward of several commits reviews the whole range.
- `start` and `verdict` require `JTEK_SESSION` (or `CURSOR_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, or `CODEX_THREAD_ID`). The hash is of that text only, so the variable name does not make a second id. The parent process is not a session. The authors list is sealed; a hand edit that does not recompute the seal is refused. The original writer is never dropped when the list is capped at 20. A process that can rewrite both the seal key and `meta.json` can still forge the list.
- A Done when item needs a measurable comparison or an observable action. A digit anywhere, including a version, a Thai digit, or a fullwidth digit, does not turn off the check. `secure`, `works`, and `quicker` are included. Ordinary Thai such as ไม่ง่าย is not refused.
- `finish --no-pr` with a remote is allowed only when the published base says `"forge": false`. An unmerged `JTEK_BASE` that sets the flag does not skip the pull request.
- `comment` treats `addComment` on stdout the same as on stderr, so the `gh api` fallback still runs. A token in a `--pr` link is redacted before it is printed. `doctor` warns when `setup` would create a virtualenv and `ensurepip` is missing.

## 26.40.0 - finish tells the truth about the pull request, and a check has to be able to fail

A pilot of 26.39.0 shipped work the script could not see, took a verdict from the session that wrote the code, and kept tickets where a fresh machine could not find them. Each hole is closed in the script.

- `finish` refuses when it cannot read the pull request. A missing `gh`, a token that cannot read checks, a draft it cannot see, and a link that is not a pull request used to print `needs-review` with `ci: unknown`. The refusal names the link and the GH_TOKEN scope. Token-like text in the forge's error is not printed.
- `finish` waits while CI is `pending`, then refuses if it is still pending. The bound is `JTEK_CI_TRIES` (40) looks and `JTEK_CI_WAIT` (15) seconds between them. `pass` and `none` ship. `fail` still refuses.
- `start` records the session, and `verdict` refuses that same session, including one that resumed the ticket later. Set `JTEK_SESSION` to an id that stays the same for the writing session. Otherwise the script uses `CURSOR_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`, or the process that launched it. Only a hash is stored, and it is never printed.
- `ticket` and `start` refuse a `Done when` item that is a quality with no number (fast, easy, feels, น่าใช้, เร็วขึ้น, and the same kind of word). A number keeps the item. Nothing is claimed.
- Ticket files are written in `.jtek/tickets`, inside the repository, so a clone has them. Commit that folder on the base branch. The old folder beside the repository, `<name>.jtek/_tickets`, is still read, and its ids are not reused.
- After three FAIL verdicts, `start` refuses, including `start --answered`. The only reset is a board ticket the human set back to Todo after a question. A local ticket has no reset.
- `show` and `verdict` run after a squash, when the worktree and the branch are gone. `--pr <link>` reviews `refs/pull/<n>/head`, fetched when it is not local. `--at <commit>` reviews that commit's parent range, which is the diff a squash commit does not show against the base. An empty ticket branch does not use that parent range.
- `jtek.py comment <id>` posts the verdict. It tries `gh pr comment`, then `gh api` as an issue comment when the token cannot add a comment, then writes `unposted-comment.md` and exits with a refusal. It does not report a comment as posted when it was not.
- `jtek.py broke <id> --item <n>` runs the declared checks while one `Done when` item is broken and records the check that failed. `finish` refuses until every item has that record on the current commit. A check that still passes is not a record.
- A prose apostrophe in a refusal is worded so the script can be read in full, and `gh` is started from one argument list. The skill scan stays at the same caution level as 26.39.0.

## 26.39.0 - the owner's list of reviewers, and a survey of the agents on the machine

Until now the skills said "prefer a reviewer from another vendor" in `/jt` only, and left the agent to guess which programs the machine has. Now the script looks, and the owner keeps the order.

- `jtek.py doctor --agents` prints each coding agent it finds on PATH (`claude`, `codex`, `cursor-agent`, `agy`, `gemini`), how a session is started with it, and the models of a program that can list them, which today is `cursor-agent`. It says what it did not check: whether a program is signed in, an agent it does not know, and a shell alias. It needs no repository.
- `~/.config/jtek/agents.json` is the owner's ordered list of reviewers: a `command`, a `vendor`, and a `model` per entry. It holds only models the owner trusts to review. The script follows the order and does not rank models.
- `jtek.py reviewer --vendor <the author's vendor>` prints the command of the first installed entry of another vendor. Without one it prints the first installed entry of the author's own vendor, and with no list or nothing installed it says to start a fresh session of the author's own model. It never says that no review is needed, and it never runs the command it prints. A damaged list is refused with its path.
- `/jt-agents`, a new mode typed by hand, runs the survey, asks the owner which models they trust and in what order, and writes the list only after a yes.
- `/jt`, `jt-work`, and `starting-sessions.md` now point at `jtek.py reviewer`, so the ticket route has the same preference as work without a ticket.
- README: "Who gives the second look" says the preference for another vendor is a reason and not a measurement; no eval compares the two yet.
- The contract test asks only a mode that may start helpers to name `worker.md`. `/jt-agents` starts none.

Thirteen new tests cover both commands with a scratch home and a scratch PATH. The evals were not run for the changed skill text.

## 26.38.0 - every skill works in a repository with no board

A repository no longer needs Notion or FLO. Leave `board` empty in `jtek.json`, and the tickets are files. `/jt <what to do>` already worked without a ticket; now nothing around it asks for a board.

- **Tickets as files.** With no board, each ticket is `<repository>.jtek/_tickets/<id>.md`, beside the repository and outside git, and that file is the page: the session writes there what a `board:` line says. The new `references/files.md` says where each part lives, as `notion.md` and `flo.md` do for their boards. A file keeps no history of who changed it, so a team that needs that record uses a board.
- `jtek.py ticket <file> --save` keeps a checked draft as a ticket file. The script gives the next free `T-<n>` and writes Backlog, whatever the draft says. `/jt-ticket` uses it when the repository has no board.
- `jtek.py start <id>` needs no `--from-file` when there is no board: it reads the ticket file itself and prints it as `page:`. With a board, `--from-file` is required as before.
- An `after:` line of a ticket file counts an id only while that id's file is not Done. A board hands over only the open ones; a file keeps the line as written, so the script looks each one up.
- `jtek.py next` and `jtek.py sync` need no `--board-file` when there is no board: they read the ticket files.
- `doctor` no longer calls an empty `board` missing. It prints the folder of the ticket files and how to start there.
- A local ticket that stopped with a question now says the answer is in the chat, in `start` and in `finish`, not on a page it does not have.
- `jt-work` says that `/jt` does work that has no ticket, and still never starts such work itself. `/jt` says how to set up a repository that has no `jtek.json` yet: the checks still come from the base branch, and the human still merges that file.

Ten new tests cover the file route, and it was walked on a scratch repository with no board, from `init` to `finish`. A walk by a fresh session through the skills is still to do.

## 26.37.0 - four holes a review found, closed in the script

A review of 26.35.0 and 26.36.0 reproduced four ways past a rule. Each has a test that failed first.

- `attention:` names the dependency manifests of more ecosystems: Maven, Gradle, sbt, Composer, .NET, Elixir, Dart, Swift, CocoaPods, Deno, and PDM. Since 26.36.0 a new dependency goes ahead inside the pull request, and before this a ticket with `review: human` that added one to `pom.xml` reached Review with no verdict and `attention: -`.
- Header lines are read only right under the title. The first blank line after one, or the first line of other text, ends them. Before, a line such as `review: human` or `checks: lint` anywhere above the first heading counted, so text of a FLO description could waive the review. `flo.md` now says where that text goes.
- `finish` refuses a new commit after three FAIL verdicts, as `check` refuses after three failed runs. Before, the refusal held only while the last verdict was for the current commit, so a new commit went to a fourth review. The human setting Todo after a question starts the count again, as before.
- A local ticket that stopped with a question is picked up with `start --local --answered`, after the human answered in the chat. Before, the script wrote `status: Todo` for it, so the session that asked could go on at once.

## 26.36.0 - the agent decides inside the pull request; the script checks more of the result

Agents and models keep getting better. The text that tells an agent how to work holds a strong one back; the script that checks the result costs it almost nothing, and it is what lets the human trust the agent with more. So this release loosens the first and adds to the second.

- P16 now stops only before something that acts outside the pull request: a deploy, deleting or changing real or shared data, a migration run against a shared database, a message to someone outside the run. A new dependency, a migration file, or a change to CI or `jtek.json` goes ahead, is said in the evidence, and is named on the `attention:` line, which also cancels a `review: human` waiver. `worker.md`, `jt-build`, `/jt`, and `jt-verify` follow.
- `attention:` also names dependency manifests (`requirements*.txt`, `go.mod`, `Cargo.toml`, `Gemfile`, `Pipfile`, `bun.lock`) and migration folders.
- `jt-work`: the playbook's order is a default. An agent may combine or reorder steps; what must hold is what the script and the reviewer check.
- `/jt`: subagents may write code too. No session that wrote any part of the change reviews it.
- `jt-understand`: a plan file is allowed, outside the repository and its worktrees.
- `verdict`: a pass needs notes with at least one `broke:` line and a `safe because:` line, the two steps a quick review skips.
- The result's `evidence:` field names a `seen:` line whose every run predates the last code change, or ran with uncommitted files. It reports and does not refuse, because a run before a change to tests or documents still stands.
- Evals: `build --lean` gives the agent a short router and the reviewer, without step skills or playbooks, to measure whether the step text still helps a model. A new scenario, `refactor-config`, has two loops that look like copies and are not.
- README: fourteen skills, `jt-me` in the table, and credit to pstack, whose mode shape `/jt` follows.

## 26.35.0 - tickets small enough to review

`/jt-ticket` was walked on a two-repository ask (tags on notes). Its questions were numbered with a recommendation each, it found in advance the contract check, `verify`, and stand-in changes the work would need, it carried a changed answer into every item, and it refused to create tickets on an approval that came from another agent instead of the owner. `/jt` then worked the API ticket it wrote without stopping once, through a FAIL verdict and a fix to PASS+NOTES and green CI. The ticket had nine `Done when` items and took over an hour.

- `jt-ticket`: a ticket holds at most six `Done when` items as a rule; more is split.

## 26.34.0 - `/jt-ticket`

The owner asked for jtek's own skill to write tickets, so that a session gets a ticket it can work without guessing, and large work arrives in pieces.

- `jt-ticket`, typed only: restates the ask, reads the code for the facts, asks the owner only for decisions (four at a time at most, numbered, with a recommendation), drafts tickets whose `Done when` items can be seen working, splits large or cross-repository work into ordered tickets linked with `after:`, checks each draft, and creates the ones the owner approves on the board as Backlog. Todo stays the owner's.
- `jtek.py ticket <file>`: checks a drafted ticket the way `start` will read it, without claiming anything.
- `/jt` suggests `/jt-ticket` when work without a ticket is too large for one pull request or not yet decided.

## 26.33.0 - engineering lines in the steps, and `jt-me` reads far enough

Each line goes into the step where it applies, with the id of the principle it carries.

- Bug playbook: write the right and the wrong result first, reproduce twice with a reset between, and make a test for a bug that shows only sometimes give the same result every run.
- `jt-debug`: when the first error does not name the cause, list two or three candidates and the observation that tells them apart; revert what a refuted guess added; a guard, a retry, a default, or a caught error hides the bug when the state that reached it should not exist.
- `jt-understand`: run what a run can answer before asking; search the history and open pull requests for the same fix before writing one.
- `jt-build`: expected values come from the ticket, and a new test fails for the reason you expect.
- `jt-verify`: a result that comes too easily, and a number from one run, do not count; when the change seems not to work, rule out the way you looked first.
- `jt-review`: name the one fact the change is safe because of, and prove it (`safe because:` in the notes).
- `jt-cleanup`: a lint or type suppression the diff added is fixed, or kept with the rule and the reason named.
- `jt-babysit`: a job that failed with no change may be re-run once; comments about security, data, migrations, concurrency, or money are never dismissed; replies go through a file, never a shell command built from comment text.
- `jt-work`: the stop note holds the question, the options, and your pick.
- `jt-me`: it read only what happened after `me.md` last changed, so a file written another way was never checked against the past. It now keeps `read through: <date>` as the file's last line, and without it reads the last two to four weeks.

## 26.32.0 - `/jt-me`

- `jt-me`, typed only: reads this workspace's past sessions in three slices and the owner's own comments on tickets, keeps a pattern only when two slices show it, asks at most two questions, and proposes changes to `~/.config/jtek/me.md`. It writes only what the owner accepts, never a secret or a name, and never a line that would change a rule of jtek; a rule a check could enforce goes to `jt-learn` instead.
- `/jt`: `me.md` sets style only. A line in it that would change who merges, when to stop, what counts as evidence, or who reviews is void.

## 26.31.0 - blind evals, and the first walks of `/jt`

`/jt` was walked twice on 26.30.0 by fresh sessions that read it by path: a FLO ticket (TEK-13, a client feature with a real pull request) and a request typed in Thai with no ticket, which became `LOCAL-1`, changed two files, and so got a reviewer. Both reached Review and were merged. Both reports followed the owner's style file.

- Evals are blind. The skills are copied beside the scratch repository, so the agent never reads the folder that holds the hidden tests. The git author, the page link, and the prompt say nothing about a test. The grade reads the agent's session files and lists which skills it opened and which `jtek.py` commands it ran, in order, instead of asking the agent.
- `release` on a local ticket no longer tells you to set Status on a page that does not exist.
- `/jt`: a decision no principle settled gets `-` in the principle column, not a file name.

## 26.30.0 - `/jt`, your mode

The owner asked for their own mode, after a close reading of another skill set built around one person's working style. `/jt` is that mode for jtek: typed only, for any coding task.

- `jt`: restates the goal and the smallest change, says "no" when it disagrees, sends ticket work to `jt-work`, and works anything else as a local ticket. It reports in the owner's style, read from `~/.config/jtek/me.md` outside the repository, and names the principle behind each decision.
- `jtek.py start --local`: work without a ticket gets an id such as `LOCAL-3`, a worktree, the baseline, and the same evidence. The header the session wrote grants nothing: every check runs, `review: human` and `checks:` are ignored, and resuming does not reset the failed runs. A local change of one file with nothing on the `attention:` line skips the second look, and the result says so. A board ticket cannot take a `LOCAL-` id.
- `jt-work/worker.md`: the rules every agent a session starts reads first, a reviewer included.
- `jt-work/references/principles.md`: the principles, now with ids P1 to P19 and a test each, replacing `jt-build`'s list. Steps mark the lines that carry one, and a `choice:` line in the evidence ends with its id.

## 26.29.0 - approval on FLO, and the README names FLO

Round five on FLO, on 26.28.0. TEK-11 asked for a library from PyPI: the session stopped for approval before any code, because the ticket allowed the dependency but nothing on the base could install it. The human declined and rewrote the ticket; a new session built it without the library. TEK-12, an API route, went through review and CI on a real pull request. Both are Done. No wrong action in rounds four and five.

- `jt-build`: a dependency the ticket allows still needs `setup` on the base to install it; until then, stop for approval.
- `jt-verify`: a commit that changes only documents no program reads does not void earlier runs.
- `ticket.md`: `ci: none` right after a push usually means the forge has not started the run.
- README: the board may be Notion or FLO, and what was walked on FLO.

## 26.28.0 - a bug and a refactor on FLO

Round four on FLO, on 26.27.0: a Bug item (tally counted a Windows line end as one character) went through the bug playbook, tests first; a Feature item tagged `refactor` went through the refactor playbook with a real pull request. Both passed review and are Done. No wrong action; the notes were about the documents.

- The bug playbook records the reproduction with `jtek.py run`, before any edit: it is the base run the evidence cites.
- A run made in another folder says that its `commit:` line is the worktree's. Three sessions read it as the folder's.
- `evidence.md`: an item about the code itself may be `seen:` in a recorded read of the code, and the line says it is a read.
- `flo.md`: the tag `refactor` wins over the item's type.

## 26.27.0 - the consumer half of a two-repository pair on FLO

TEK-8, the client half of TEK-7, started once TEK-7 was Done, moved the pin to the provider's new commit, and passed review and CI on a real pull request.

- `flo.md`: an item is on the board's product when its link and the board link name the same product number. No product lookup is needed.
- `two-repos.md`: when `.jtek/verify.md` names a variable for the provider that is not set, clone the remote it names.

## 26.26.0 - a question, a refusal, and a two-repository pair on FLO

Round three on FLO, on 26.25.0. TEK-6 had two `Done when` items that could not both hold: the session stopped before any code with one question and the `Open questions` tag; the human answered in a comment and set To do; a new session read the answer, cleared the tag, and passed review. TEK-8 was blocked by TEK-7 in FLO, and `start` refused it until TEK-7 was Done. TEK-7, an API change, passed review and CI on a real pull request.

- `jt-understand`: two `Done when` items that cannot both hold are a reason to stop and ask, never to pick one.
- `jt-work`: a refusal that says nothing to do ends the session with the refusal as its result.
- `flo.md`: `get_product` gives a product's link, `list_products` does not; a `blocks` item is not on the `after:` line; a waiting tag is written into the ticket file also when the item is back in To do; an item that is someone else's is the one FLO refuses to move.

## 26.25.0 - rework and a pull request on FLO

TEK-5, a client feature, went through a real pull request with green CI, a late verdict, and a second `finish`. TEK-4 was sent back by the human with a comment and To do, and a new session picked it up, fixed it, and passed review. Both are Done. Their notes:

- A check gets no input. One run of `check` hung until the session gave it none.
- A run whose `--cwd` is outside any git repository says so, instead of showing only the worktree's commit.
- `flo.md`: the product's prefix is found from the link with `list_products`; header lines may come in any order; a comment that holds only the pull request's link is a fenced result block, so the next session reads it as a session's; the result block is the lines up to the first blank line, in a plain fence; FLO turns a bare link into a Markdown link and may add blank lines; the human's answer or fix is in the comments after the last result, and goes under `## Notes`.

## 26.24.0 - the second walk on FLO

TEK-4, a tally feature, was worked on 26.23.0 and passed with notes. The human sent it back with a comment on the item and moved it to To do, to walk the rework path on FLO. The session's notes became these fixes to `flo.md`:

- The exact spelling of FLO's columns, and that the type is `type.name`.
- What an empty answer of `get_agent_instructions` looks like.
- A missing Review column is said at once and again in the last message, since a subagent's first message reaches no one.
- An item with no sprint still shows in its column.
- After a dropped connection, a read may be sent again; a write is sent again only after reading the item.

## 26.23.0 - the first walk on FLO

TEK-3, a tally feature, was worked on 26.22.0 from a FLO item by a fresh Claude session and passed its review. The board had no Review column, so the item stayed In progress, as `flo.md` said it would. The session's notes became these fixes to `flo.md`:

- Agent instructions are read with `get_agent_instructions`: `get_item` may leave them out.
- The session looks at the board when it reads the item, and says at once when the Review column is missing.
- Header lines go in the order of `ticket.md`; `Waiting=` writes nothing when neither tag is there; the comment keeps every line of the block, local paths included.
- A session never sets a sprint, or starts or closes one.

## 26.22.0 - FLO as the board

The board may now be a FLO product instead of a Notion database. `references/flo.md` says where each part of a ticket lives in FLO (column, type, tags, `blocked by`, comments), what to write for each `board:` line, and what the human sets up once: a Review column on the board. It was worked out by trying each write against a real FLO product first.

- `jt-work` reads `notion.md` or `flo.md`, by the board's link.
- Status names are read whatever their spacing, so FLO's `To do` is `Todo`.
- `doctor`, `setup.md`, `ticket.md`, and the session guide name both boards.

## 26.21.0 - the fifteenth round of real walks

Round fifteen on 26.20.0, the first after the outside review: a tally feature on Claude Code that went through a FAIL and a fix, and a two-repository client ticket on Cursor through a real pull request. Both reached Review on their own; the reviewers passed `--commit`, and evidence cited runs from before a commit that changed only tests. Two reviewers each saw a wrong result from a stale Python cache after undoing a break.

- `jt-review` and `jt-build`: run without a build cache when you break and restore code, because a cache written in the same second can hide the break.
- A skill's frontmatter is checked to stay valid YAML.

## 26.20.0 - an outside review of 26.19.0

Two outside reviewers read 26.19.0: one ran the scripts against scratch repositories and reproduced eleven defects, the other read every skill document as an agent that must follow it. A third reviewer then read the fixes before release, found that two of them did harm, and those were redone. The script defects have tests.

- `verdict` takes `--commit`, the commit `show` printed when the review began, and refuses when the author has committed since. A verdict could be recorded for a commit nobody reviewed.
- A cited run must have ended: a run killed half way could be cited, and on the clean-up line it crashed `finish`. An earlier run may still be cited, because the base run, a reproduction before the fix, and the diff read before clean-up are meant to be earlier.
- The clean-up rests on a diff only when the cited run is a `git diff` (also `git -C <path> diff`) that exited 0 and printed something.
- The base is read as `refs/heads/<base>` in `start`, `check`, `show`, and the diff, so a tag of the same name cannot stand in for it.
- Only `Goal`, `Done when`, and `Out of scope` decide whether the ticket changed, with whitespace evened out. An answer added under Notes no longer voids a verdict. Upgrading: a ticket in Review keeps its verdict only if it is finished on the old version; otherwise it needs new evidence and a new verdict.
- The FAIL count counts commits, not verdicts (a count from before is kept), is written under a lock so a concurrent `finish` cannot undo it, and starts again when the human answers a question and sets Todo.
- `finish` names the right fix for a closed or merged pull request, for a history rewritten here (push with `--force-with-lease`), for commits only the forge has, and for a link it could not read while the branch is pushed nowhere. A branch pushed to any remote counts as pushed.
- `start` brings a kept branch that has no commit of its own up to the base, so a ticket released and started again takes the new base and runs the baseline. `release` itself is unchanged.
- The script loads on systems without `fcntl`, as before.
- Documents: the bug playbook's step 4 reads in order again; `jt-review` runs the check commands directly during its breaks, never `jtek.py check`, keeps the commit for `verdict`, and may read the evidence once it has its own view; `jt-harness` and `jt-review` say in their descriptions when not to load them; the evidence forms show `(run <n>)`; a long-running service is not started through `run`; README, GETTING-STARTED, and the Notion and session guides no longer speak as if only Claude Code exists, and README's unproven list says what is still unproven.

## 26.19.0 - the fourteenth round of real walks

Round fourteen on 26.18.0: Cursor and Antigravity worked a ticket each at the same time, Cursor's through a real pull request with CI on two Node versions. Both reached Review on their own and cited a recorded run on every `seen:` line. Cursor's service, started in the background as the demo's guide said, died when its shell call ended.

- The `jt-harness` template says to start a service in a session of its own, because a background process can die with the agent's shell call.

## 26.18.0 - other agents

Round thirteen on 26.17.0: one ticket on Sonnet with a reviewer on the strongest model, and one ticket each on Cursor's command-line agent and on Antigravity's, both handed the ticket as a file because neither had a Notion tool. All three reached Review on their own, cited a recorded run on every `seen:` line, rested the clean-up on a recorded diff, and started their own reviewer. Cursor and Antigravity each listed the board lines they could not write.

- The bug playbook says where a test goes for an item that already holds on the base: with the failing test, as a pin, seen failing by breaking the fix once.
- `jt-verify`: inputs and drafts stay in the session's temporary folder, not beside the worktrees.
- README: which agents the walks used.

## 26.17.0 - the twelfth round of real walks

Round twelve on 26.16.0: a client feature on Sonnet, with CI now on Node 20 and 22, and a tally feature on the strongest model. Both cited a run on every `seen:` line, and the clean-up rested on a recorded diff. CI stayed green: in twenty-two tickets, a pull request never went red on its own.

- A run keeps stdout and stderr apart. A session could not show that an error went to stderr.
- A run in another folder names that folder's commit, so a run of the base shows the base. `jt-verify` says to run the base with `--cwd`.
- A citation may name several runs with words between them, such as `(run 7 stand-in, run 5 real service)`. The result counted such a line as citing nothing.
- `finish` and `stop` write the board comment to a file and name it on a `comment file:` line, ready to paste. Sessions on Sonnet shortened the comment three times when they had to put it together.

## 26.16.0 - the eleventh round of real walks

Round eleven on 26.15.0: one ticket on Sonnet and one on the strongest model, both using `jtek.py run`. Every `seen:` line cited a run, and the human could check each line against its run file in a minute. That found one soft spot on Sonnet (a claim about the base that rested on a run of the branch) and none on the other. Sonnet still read only part of its diff at Clean-up.

- The result says whether the `clean-up:` line rests on a recorded `git diff` run. `jt-cleanup` runs the diff through `jtek.py run` and cites it.
- A command run from outside any repository says to run it from the ticket's repository or worktree, not only git's own message.
- `jt-build`: a change that needs approval may go ahead when the ticket, written by the human, allows it in so many words, quoted in the evidence. `jt-ship`: an item that can only be seen once the pull request exists. `jt-work`: wait for a reviewer without opening the state folder.
- `jt-verify`: let `run` record the exit code; a `seen:` line may name a command briefly because the run holds it; record the inputs too. `notion.md`: the result comment is not shortened.

## 26.15.0 - recorded runs

Round ten on 26.14.0 tried what the earlier rounds had not: Linux, a smaller model, and a rework with no pull request. The script's tests pass on Linux, and the demo service runs on Python 3.10 there. Sonnet and Haiku each took a ticket to Done with correct code, but each wrote a `seen:` line that said more than it had run and skipped part of a step. Asked plainly, a session on the strongest model said its own `seen:` lines paraphrased the commands, and that one claim came from a different command. A rule in prose had not stopped any of this.

- `jtek.py run <id> -- <command>` (or `--sh "<pipeline>"`, and `--cwd` for the base) runs a command and keeps exactly what ran, where, at which commit, the exit code, and the output. Evidence ends each `seen:` line with the runs it rests on, `(run 3)`; `finish` refuses a number that was never recorded, and the result counts the `seen:` lines that cite a run. A reviewer reads the run files.
- README: which model to use, from what the walks showed.
- `jt-work`: a rework with no pull request. `jt-babysit`: stopping at one commit during a rebase without an editor.

## 26.14.0 - the ninth round of real walks

Round nine on 26.13.0: a client feature that shows times in the machine's zone (worked once, sent back by a FAIL, fixed with a test) and an API filter, each taken to Done. Both had a real chance to pass locally and fail in CI, which runs in another time zone; neither did, because both tested under two zones. One reviewer wrote a claim about the base as if it had run the base, when it had read it in the diff. The claim was true.

- `jt-review`: a claim about the base comes from a run on the base, or the note says it was read from the diff. The `to weigh:` line is for a behaviour the human may not want that the ticket does not settle.
- `jt-build`: `git stash` is not a forbidden copy, and adding new lines to a check's script is not changing it.

## 26.13.0 - the eighth round of real walks

Round eight on 26.12.0: an API feature with a new route and a tally refactor, each taken from Todo to Done by one session that started its own reviewer. The refactor got a FAIL and was fixed with a test. No session did a wrong thing, and no refusal named a wrong remedy. With round seven, that is two such rounds in a row.

- The refusal of `finish` after a FAIL says how many FAIL verdicts the ticket has had, and after the third it says to stop. A session that got the FAIL while still running never ran `start`, so it never saw the count that 26.12.0 added there.
- `jt-cleanup`: the `clean-up:` line covers a change as well as a removal.
- `jt-verify`: running the base in the main checkout writes no cache there either.
- `jt-verify`: a script that a check runs is not a test file for the rule on earlier output; a slower check the repository describes outside `jtek.json` is run when it covers the change.

## 26.12.0 - the FAIL count

Round seven on 26.10.0 and 26.11.0: a tally feature from Todo to Done, and the `jt-learn` ticket reworked after a FAIL and passed on its next review. No session did a wrong thing, and no refusal named a wrong remedy.

- `verdict` counts FAIL verdicts, and `start` on a pick-up prints the count. `jt-work` says to stop after the third FAIL, but a session had no way to know how many there had been.
- `jt-work`: a finding that is only a missing test is fixed when the new test fails on the reviewer's break.
- `jt-verify`: when a check copies the worktree while it runs, break a copy made with `git archive`.
- `notion.md`: the property names in a `board:` line take no prefix.

## 26.11.0 - the seventh round of real walks

- A second `finish` remembers that the first had no pull request, so `finish <id>` alone works after the verdict, as `jt-work` says. A session was refused there and had to add `--no-pr` again.
- `jt-work` no longer asks for a written step list. Four sessions in a row skipped it, and nothing failed when they did; the steps that matter are held by the script. Skipping a step is still not allowed.

## 26.10.0 - the sixth round of real walks

Walked on 26.9.0: a consumer ticket that moved its pin, taken from Todo to Review by one session, and a bug in a check's own script, the ticket `jt-learn` had proposed. The second session skipped the Clean-up step and edited a saved output instead of running it again; it said so itself. Three reviewers in a row died when the machine went to sleep, and each time the ticket's state stayed whole: no verdict, a clean worktree, and `next` naming the next step.

- `finish` and `evidence` refuse evidence without a `clean-up:` line. The step that reads the diff once more is the easiest to skip at the end of a long session, so the script now asks for its result.
- `jt-build`: when the code and its test are both new, commit them before breaking the code to see the test fail. The advice of 26.9.0, to restore with git, brought back the old file when the new one was not committed.
- `jt-verify`: never edit a saved output; run it again or say what it lacks.
- The bug playbook: when the fault is in a check's own script, that check failing on the old code is the failing test, and a reproduction that needs a broken file is restored with git, with no copy kept.
- `jt-work`: a session that must end before its reviewer reports ends with `needs-review` and says a reviewer is running. `starting-sessions.md`: run `next` before starting another reviewer.
- `jt-review`: only checks declared in `jtek.json` count as noticing a break, and breaks are made one at a time, after the previous runs end.
- The evidence form: an item seen only in part, and the `clean-up:` line. `notion.md`: the 2000-character limit on one piece of a comment, and where to keep temporary files.

## 26.9.0 - the fifth round of real walks

Walked on 26.8.0: two tickets started in the same moment on the same file, each taken from Todo to Review by one session; the second pull request then conflicted with the base and a new session rebased it with `jt-babysit`; and `jt-learn` turned a correction that had come up twice into a check that fails on both past mistakes. No session removed or stopped anything it had not made. One refusal named the wrong remedy.

- A command run from another repository said the ticket was not started and to run `start`. It now says which repository it looked in, and to run from the ticket's repository or worktree.
- A pull request that conflicts with its base: `finish` refuses to call it ready, `sync` says so on its line, and `start` on a pick-up names the pull request, says when it conflicts, and says to read its comments. A ticket had come back with the reason written only on the pull request.
- `jt-babysit`: where the count of rebases is, and that a rebase which brings changes to the same files means seeing the change work again.
- `jt-build`: restore a deliberate break with git, and keep no copy of the file.
- `jt-ship`: which branch a pull request goes into, and where the ticket id goes when earlier titles differ.
- `jt-verify`: in the bug playbook the reproduction is the base run; after a rebase every evidence line is run again.
- `notion.md`: the page link without its query part, what a comments tool answers for a page with no comments, and a limit on one piece of a comment.
- `jt-work`: how to wait for a reviewer that runs in the background.
- `jt-learn`: where to build the trial of a new check, which commit it must fail on, where the proposed ticket and the rule row go, and what to do when the mistaken work is already merged.

## 26.8.0 - the fourth round of real walks

Walked on 26.7.0: a ticket picked up after the human's answer and taken to Review by one session through three reviews (FAIL, FAIL, PASS+NOTES), and a harness repaired with `jt-harness`. All six demo tickets are Done.

- A session that repaired a harness deleted temporary folders by a pattern, in a folder other sessions were using. No skill said how to clean up. `jt-verify`, `jt-review`, and `jt-harness` now say it: remove only what you made, by its exact path, and stop only a process you started.
- `start` prints the last verdict when a ticket is picked up. A session had opened the state folder to learn that the verdict was FAIL.
- `jt-work`: fixes after a FAIL follow `jt-build`; after the third FAIL on one ticket the session stops and asks; a verdict posted on the pull request is not a review comment; a fix that needs permission stops for approval; push before `stop` when a pull request is open; the second `finish` takes no other argument.
- `jt-ship`: what to do when the ticket already has a pull request.
- `jt-harness`: a sixth question about what the app needs from elsewhere; a repair for a fault the check cannot see; where to make the break; and, in the template, that a command must stand alone because an agent's shell keeps nothing between commands.
- `notion.md`: the status is copied as the page shows it; how to tell the human's comment from a session's; a long comment is sent in parts.
- `jt-understand`, `jt-verify`, and the evidence form: an answer whose effect it says it does not want, saved output after commits that changed only tests, and a line for the `Out of scope` comparison.

## 26.7.0 - the third round of real walks

Walked on 26.6.0: a refactor from start to Review by one session that started its own reviewer, a pull request sent back with a new item and a comment, and a second review that gave FAIL where the first had passed, followed by the rework.

- `verdict` refuses a word that disagrees with its notes: `FAIL` needs a `- reproduces:` line, a `- reproduces:` line makes it `FAIL`, and `PASS+NOTES` needs a `- to weigh:` line. Reviewers had to guess where `PASS` ends and `PASS+NOTES` begins.
- `jt-review`: the rule of 26.6.0 for a break that no check notices now also stands in the list of what counts as a finding and in what `PASS` means. A reviewer found the three places disagreed. The step also covers an outcome that lives in code the change did not touch.
- `finish` waits a moment for the forge to show a commit that is already pushed. A session that pushed and finished in the same second was told to push the branch.
- `start` tries three times to create the worktree. One CI run of 26.6.0 failed when two tickets started in the same moment; it passed when run again and was not reproduced, so this guards the likely cause and is not a proven fix.
- `jt-work`: when a ticket comes back with a changed item and a comment on the pull request, the playbook leads and `jt-babysit` only answers on the pull request.
- `jt-babysit`: put the new evidence in the pull request's body again, and answer a comment that has no thread with a new comment.
- `notion.md`: a backslash before punctuation is the tool's escape. The notes form of `jt-review` has a line for each kind of note.

## 26.6.0 - the second round of real walks

Three more tickets were walked on 26.5.0 by sessions that had never seen the skills: a consumer ticket that moves a contract pin, a bug, and a ticket whose only item could not be measured, which stopped, was answered, and was picked up by a new session. No session was refused without knowing why. This release is where they had to guess.

- `jt-review` had two rules for a break that no check catches: one called it a finding, the other a note. A reviewer chose the note and said the other reading would have been a FAIL. There is now one rule: a finding when `Done when` names the behaviour, a note otherwise.
- `jt-review`: when the base handled a case and the change handles it worse, that is a finding, also when the ticket never mentions the case. A reviewer had passed a change that printed `undefined` where the base printed nothing.
- `start` prints a `baseline:` line (passed now, passed earlier, or skipped), and on a pick-up an `asked:` line with the question the earlier session put to the human. A session had opened the state folder to find out.
- `show` prints the base branch and the main checkout. `verdict` writes the verdict line and the notes to one file, ready to post on the pull request, and prints its path.
- `jt-work`: a subagent that starts with none of the conversation counts as a fresh session; a ticket session does not run `jt-harness`; `stop` with nothing changed needs no commit.
- `jt-understand`: what to do when the base already does what an item asks.
- `jt-build`: how to see a test of new code fail, the form of a commit message, and that a script the ticket asks for is not a check.
- `jt-verify`: where to run the base branch, where to keep output files, and that the `attention:` line asks the human to look and does not forbid an edit under `.jtek/`.
- `notion.md`: read the comments on a pick-up, an empty After, the form of a comment, and which link to pass.
- `two-repos.md`: read the provider's newest commit from its remote, not from a folder that happens to be on the machine.

## 26.5.0 - what the first real walks found

Three tickets were walked on demo repositories with the board in Notion. Two were worked and reviewed by sessions that had never seen the skills, and each was asked afterwards what was unclear. This release is what they found.

- `start` fetches the base branch from `origin` and moves the local one forward when it is only behind. Before, a ticket that started after a pull request was merged on the forge began from the old local branch, without the merged change. `--no-fetch` skips it.
- `jtek.py evidence <id> --file <file>` checks the form of an evidence file and saves nothing. `jt-ship` runs it before the pull request is opened, so a refused file is never a pull request body.
- A first `finish` that has a pull request prints `board: PR=<link>`, so the page shows the pull request while it waits for its review.
- `show` prints the commit under review.
- `notion.md`: how to find a page by its id (Notion stores only the number), what to do with `<code>` tags a Notion tool returns, that an agent can create the board, and that the id prefix needs two letters or more.
- `jt-build` says when an existing test or a check's script may change, and how.
- `jt-review` gives the command that posts the verdict on a pull request, says what `--by` takes, names the files a reviewer must not open, asks for one break per behaviour, and says how to undo a break.
- `jt-ship` says that attached files stay on the machine, and what `ci: pending` means.
- `jt-verify` says what to write when the code that reads a changed response is in another repository.

## 26.4.1 - fixes to the fixes

A second look at the fixes of 26.4.0 found that they added defects. Each fix has a test.

- `sync` and `release` no longer force a worktree away. In 26.4.0 they did, which deleted submodule commits that were pushed nowhere, and deleted uncommitted files when `git status` itself failed. A worktree with submodules is now kept, and you remove it by hand.
- A worktree whose commits are on no branch is kept also when the ticket's branch is gone, and after an interrupted start.
- A line that starts with inline code, such as three backticks around a command, is not read as the start of a code block. In 26.4.0 it hid every heading after it.
- `next` answers for every ticket when the base branch of one is gone.
- A changed file whose name is not UTF-8 no longer stops `verdict`.
- `"headings": null` is accepted again, and so is a tab after the `##` of an own-language heading.
- A `pr_state` with an unclosed quote is found by `doctor` and `start`.
- A closed draft on GitHub is read as closed, not as a draft.
- The GitLab example counts a failed pipeline as failed also when it ran on a merged-result commit.

## 26.4.0 - the project sets the numbers and the names

- `max_failed_runs` in `jtek.json` sets how many failed `check` runs end a session. It was fixed at 3, which stopped a model that would have found the cause on the next try.
- `pr_state` in `jtek.json` names a command that reads a pull request, so GitLab, Bitbucket, and other forges work. It gets the link and prints the state, the head commit, and the CI state. Without it, `gh` is used as before.
- `headings` in `jtek.json` lets tickets use a team's own words for `Goal`, `Done when`, and `Out of scope`.
- `examples/pr-state-gitlab.py` is a `pr_state` command for GitLab to copy. It is tested against a stand-in for `glab`, not a real GitLab.
- A third outside review found defects, and each fix has a test:
  - A verdict and the evidence no longer survive the same edit moved to another place in a file. The identity of a change now includes the content of every file it leaves behind. A verdict recorded by an earlier version must be given again, and a rebase drops the verdict when the base changed a file the change also touches.
  - The `pr_state` command runs in the main checkout, so a ticket's branch cannot change the program that runs. When it fails or prints anything but the three words, `finish` refuses. Before, any other spelling of a red CI passed.
  - A draft pull request is refused, as the docs already said.
  - A heading given twice is refused, and a heading inside a code block is text. Before, the later one silently replaced the real `Done when` items.
  - `sync` deletes a branch only when its commits are on the base, or the forge says the pull request merged at the branch's last commit. Before, a pushed branch of a cancelled ticket could be deleted unmerged.
  - `release` and `sync` keep a worktree whose commits are not on its branch, such as commits on a detached HEAD.
  - A reviewer can record FAIL when the author left uncommitted files.
  - A bad `max_failed_runs`, `pr_state`, or `headings` is found by `doctor` and `start`, not by the first `check`. `headings` takes only the three names.
  - Only the human setting Todo gives a ticket new check runs. A session that resumes does not.
- The README says what a project can change, what jtek does not decide, what still assumes today's agents, and where it does not fit yet.

## 26.3.0 - templates, and a picture of the whole factory

- Templates, each with a blank form, a filled example, and its rules: the ticket page, the evidence, the review notes, `.jtek/verify.md` with a feature file, and `.jtek/rules.md`. `setup.md` has `jtek.json` examples for Node, Python, and Go. The README lists them.
- The README has a picture of the whole factory: human in the loop, outer loop, and inner loop.

## 26.2.0 - fixes from two outside reviews

An independent review of 26.1.0 found ways to reach Review without meeting the rules, and claims that could not be recovered. A second review checked the fixes and found defects in them. Each fix has a test.

**Reaching Review**

- A verdict counts whitespace, and it is bound to the ticket text as well as to the change. Re-indenting a line after a PASS needs a new verdict. So does a change the human makes to the ticket. An external diff tool or a text conversion in the git config cannot hide a change from it.
- `finish` checks the saved evidence against the ticket's current `Done when` items every time. It refuses evidence that was saved before the code or the ticket last changed.
- `finish` and `verdict` refuse a branch that has no change.
- `--no-pr` is refused in a repository that has a remote, unless `jtek.json` says `"forge": false`. `--pr` and `--no-pr` together are refused, and `--pr` takes only a link.
- `finish` is refused while the ticket waits for the human.
- `attention:` sees a renamed test that lost lines, a deleted spec file, paths with non-ASCII characters, and the usual files that define a check command, such as `Makefile` and `package.json`. `watch` may be one pattern or a list.
- The result shows only a verdict that counts now, and says `none`, not `waived`, when a waiver was ignored.
- A fourth `check` after three failed runs is refused.
- The `--note` of `stop`, the reviewer name, the page link, and the fields of a board file are each kept on one line, so none can add a line to the result or to the output of `next` and `sync`.

**Claims**

- A `start` that was killed half way leaves a claim that says so. `release` cleans it up, and the next `start` works.
- `release` never loses work. It refuses while a `start` for that ticket is running and while the worktree has uncommitted files. It deletes a branch only when an interrupted start made it and it holds no commit. It also recovers a ticket whose worktree folder or `meta.json` was deleted or damaged.
- A `start` after `release` goes on from the kept branch.
- Two sessions cannot both pick up one parked ticket.

**Input**

- A missing worktree, a missing evidence or notes file, a damaged state file, and unexpected values in a board file give `refused:` and not a traceback. State files are written whole or not at all.
- Status names are matched without regard to case, so Notion's `In progress` works. A status the board does not have is refused. Board rows are all checked before any line is printed.
- `sync` prints a line for every ticket in Review, Done, or Cancelled, so silence never means success.
- A ticket with more than 30 `Done when` items gets room for one evidence line per item.
- `doctor` no longer says `ready:` for an empty `jtek.json` or for a check without a command, and it names commands that need a shell.

**Layout and docs**

- `init`, `doctor`, `next`, `sync`, and `release` moved to `launcher.py` beside the script. They run from the `jt-work` skill only.
- Fixed the places where two files disagreed about who runs `next`, `sync`, `release`, and `--resume`, and removed leftovers from v25.

**Known, and not changed**

- The script trusts the session's git access. A session that removes the remote, or passes a link that `gh` cannot read, is not stopped. See SECURITY.md.
- `attention:` works from a list of known file names. A file that decides a check and is not on the list, such as `jest.config.js`, is not named unless you add it to `watch`.

## 26.1.0 - a guided first run

- `GETTING-STARTED.md` walks from nothing connected to the first merged ticket: what to connect, each step with what you should see, a first ticket to copy, and what each refusal means. The steps through Notion and a real pull request have not been walked yet, and the guide says so.
- `jtek.py doctor` lists what is set up in a repository and what is missing, in the order to fix it. It only reads. It cannot see Notion.

## 26.0.0 - inner loop only

This version is a rewrite. It does not read the `jt-queue/` files of earlier versions.

- Eleven skills, one per step: `jt-work` (start, check, stop, and the order of the steps, in playbooks for a feature, a bug, and a refactor), `jt-understand`, `jt-build`, `jt-debug`, `jt-verify`, `jt-cleanup`, `jt-ship`, `jt-review` (the non-author verdict), `jt-babysit` (conflicts, failing CI, and review comments on an open pull request), `jt-learn`, and `jt-harness` (builds a repository's verify guide, feature map, and `verify` check). The spec skills, `jt-board`, `jt-add-task`, `jt-setup`, `jt-help`, `gate.py`, and the `jt-queue/` files are removed.
- jtek no longer names or calls any other skill set.
- `jtek.py` replaces the gate. `start` claims a ticket and creates its worktree, `check` runs the declared checks, `verdict` records the reviewer's result, `finish` moves the ticket to Review, and `stop` waits for the human.
- A session may work several tickets in a row when the last one ended cleanly, the next one is in code it already read, and the session is still short. Each ticket keeps its own worktree, evidence, pull request, and result.
- Several tickets can run at once, each in its own session and worktree. A claim is an atomic directory under the git common directory, so the same ticket cannot be taken twice.
- Checks are declared in `jtek.json` and read from the base branch. A ticket can name a check and cannot add a command. `jtek.json` and the `.jtek/` folder are all that is added to a repository.
- The board is a Notion database, and nothing else. The agent reads a ticket's page with its Notion tool, such as the Notion MCP connector, saves it as a ticket file, and runs `start <page link> --from-file <file>`. `start`, `finish`, and `stop` print a `board:` line that says exactly what to write on the page, and the script never talks to Notion. `After` may point at a ticket of any repository. `jtek.json` names the board as `board`, and a ticket that stopped with a question starts again only after the human sets Todo. `references/notion.md` gives the database layout and the rules. Local ticket files and `jtek.py add` are removed.
- `jtek.py next --board-file` tells whoever starts sessions what each open ticket needs: `work`, `review`, `board`, or nothing. `jtek.py sync --board-file` says which Review tickets are merged. A human, a Claude Code session, or a bot follows the same contract, in `references/starting-sessions.md`.
- A feature that spans two repositories is one ticket per repository, joined by a contract file and checks that read it. `references/two-repos.md` gives the setup and what each check catches.
- Statuses are Backlog, Todo, In Progress, Review, Done, and Cancelled. `waiting: input | approval` is a field on an In Progress ticket.
- Review requires passing checks on the current commit, a `PASS` or `PASS+NOTES` verdict from a session that did not write the change, saved evidence, and a pull request. The human merges. A ticket with `review: human` waives the verdict. A change to the code makes the verdict stale. A rebase that changes nothing keeps it, and the checks run again.
- `jtek.json` may declare `setup`, a command that installs dependencies in each new worktree, and `watch`, a list of file patterns.
- The result has an `attention:` line. It names `jtek.json`, `.jtek/`, CI config, lockfiles, a file that a check runs, a deleted test, and `watch` matches when the ticket changes them.
- The evidence must account for every `Done when` item as `seen:` or `not run:`, and the result counts both.
- The `attention:` line also names an existing test file that lost or changed lines. A ticket that touches an attention file cannot waive the review.
- `finish` reads the pull request's CI state with `gh`, shows it as `ci:`, and refuses while it is failing.
- The `jtek.json` template offers `secrets` and `audit` checks. `show` prints the check commands for the reviewer.
- Declared commands run with `JTEK_TICKET` and `JTEK_WORKTREE` set.
- `finish --evidence-file` saves what was run and seen, in at most 40 lines. It is required, and it is also the pull request body. `--attach` keeps screenshots and output with it. The result has an `evidence:` line.
- A green run on the base is remembered per base commit, so parallel tickets do not repeat it.
- `sync` removes the worktree of each Done ticket, unless it has uncommitted files.
- `jt-work` gives the path of each step skill, for agents that cannot load a skill by name.
- `start` runs the ticket's checks on the base before any edit. If one fails, the ticket is not started and stays Todo. `--no-baseline` skips this.
- `stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first.
- A ticket may name its repository with `repo:`. `start` refuses one that is for another repository, so one board can serve a frontend and a backend.
- Every session ends with the same `jtek-result` block.
- The skills never choose the next ticket and never merge.
- `evals/` has two scenarios with hidden acceptance tests, a builder, and a grader that reads the repository an agent leaves behind.
- Skill and plugin metadata are `26.0.0`.

Entries below 26.0.0 describe files that the rewrite removed. They are in the git history at commit `4c9d0f1`.

## 25.0.0 - the queue can plan a batch and still stop for a human

- Specs keep `## Roles`. The approver, reviewer, and merger are people. `human-only` paths and topics are project-defined. A diff there is `refused: human-only` until the task has the spec approver's `human-sign-off`. `/jt-board` and `/jt-review` stay human-only. The agent does not merge.
- `/jt-work` composes pstack `/no-comments` before the draft PR. `/jt-spec-ac` composes pstack `/statechart` when the story has states.
- `blocked-by:` skips a task until those ids are `merge:` or `drop:`. `<MAX_PARALLEL>` and `<MAX_REVIEW>` wait instead of starting. `<QUOTA>` is the budget for one run (`gate.py run-start` resets it).
- `/jt-setup` proposes a CODEOWNERS lock for approved tests. A human commits it.
- `allowed` prints `risk:` (`low`, `medium`, `high`). High suggests `/ponytail-review`. A diff over `<DIFF_LIMIT>` is `refused: diff-limit` with `fix:`.
- `gate.py resume` prints the handoff Next line as data. `gate.py merge-queue` prints the human merge order and does not merge. `gate.py flags` describes an optional self-hosted Unleash revert and does not call the server.
- `## repos` remains the multi-repo queue. `evals/queue.json` is the deterministic eval for risk. `gate.py title` checks `type(scope): summary`. release-please and commitlint are templates, not a CI gate.
- Docs follow a Diátaxis layout (`docs/index.md`). Architecture decisions use `docs/adr/`.
- `/jt-work --loop` plans at most 100 tickets from the latest queue commit, skips blocked and unclear tasks, and caps open reviews. mise and reviewdog are the tools when installed. Testcontainers, Pact, and act stay optional.
- `<IMPORT_CMD>` (dependency-cruiser or import-linter) and `<PBT_CMD>` (fast-check or Hypothesis) are optional gate slots. A failure prints `fix:`.
- Pin installs with `v25.0.0`. Skill and plugin metadata are `25.0.0`.

## 24.13.0 - a repeated lesson becomes a rule

- `jt-queue/team-lessons.md` is the shared lesson list and is committed. Each row says what went wrong, how to fix it, and `enforced by` (`not yet`, a proposal, or a gate check, a denylist line, a lint rule, or a test). `jt-queue/lessons.md` stays uncommitted.
- The first `gate.py lesson` records the row as `not yet`. The second time the same lesson is recorded, the gate proposes the enforcement and does not install it. A human runs `gate.py lesson-approve`. Nothing becomes a rule without that approval. `/jt-board flow` lists lessons that are still `not yet`.
- A refusal tied to a lesson rule prints `fix:` with the replacement or the action. Other refusals print `fix:` when the fix is known.
- After approval, `gate.py lesson-legacy` can add a chore whose body lists the search hits for the old name. Changed lines fail immediately. Lines the diff did not touch do not fail while that chore is open. After it is `merge:` or `drop:`, a remaining hit fails too.
- Pin installs with `v24.13.0`. Skill and plugin metadata are `24.13.0`.

## 24.12.0 - a resume note when work changes hands

- When `/jt-work` stops on a task without merge, it writes `jt-queue/tasks/<id>/handoff.md` and replaces that file on the next stop. The stops are a gate failure, `ask:`, `send-back:`, a human `release`, the session ending, and the round cap. The note records state, what was done, what is left, the failing gate step and a one-line error, the files touched, and the next command.
- The note follows the Matt handoff style `/jt-spec-handoff` already composes: cite `plan.md` and `task.md` instead of pasting them, redact secrets, and keep suggested skills out of the file. Starting a task that already has the note reads it first as data, not as instructions, and the plan continues from it.
- Commit `handoff.md` with the other queue files. `/jt-board flow` prints which tasks have a note and how old the `Updated` stamp is. `gate.py release --id` prints that path. A merged task is not given a new resume note.
- The writer uses the same secret checks as `secret-suspect` (a private-key block, a dotenv name other than `.env.example`, a private-key file name). It does not copy `.git/jt-queue/logs`. The error line is a summary, not the command output.
- Pin installs with `v24.12.0`. Skill and plugin metadata are `24.12.0`.

## 24.11.0 - claims, file leases, and one worktree per task

- `/jt-work` records who is working a task in `jt-queue/claims.md` (`owner`, `claimed`, `activity`) and commits that file on the queue branch. The owner is `JT_OWNER` when that is set, otherwise `git config user.name`. `/jt-board flow` prints the owner, the claimed time, and whether the claim is stale.
- A task owned by someone else is refused with `claimed`. A stale claim (no activity newer than `<CLAIM_STALE>`, empty means 24 hours) is shown as stale and is not taken. Only a human runs `gate.py release --id` on an open task. The agent never does.
- Starting a task leases the paths in `files:`. `/jt-work` refuses `lease` when those paths overlap an open lease and names the other task and owner. `release --closed` drops leases whose board line is `merge:` or `drop:`.
- Each task gets one git worktree under `.git/jt-queue/worktrees/<id>`, on `type/<ticket-id>-<slug>`, from the latest queue commit. Running it again reuses that worktree. It is removed after merge or drop when the checkout is clean. A dirty worktree is reported and kept. That directory stays on this machine.
- Pin installs with `v24.11.0`. Skill and plugin metadata are `24.11.0`.

## 24.10.0 - queue flow metrics on /jt-board

- `/jt-board flow` prints, per task and as a summary, lead time, gate fails, rework, and review time for a window (default the last 30 days). Each value names its source. A missing source prints `unknown` and the reason. The script does not guess.
- Lead time is the first git commit of `task.md` to the merge (`gh` `mergedAt` when exactly one merged PR matches, otherwise the commit that wrote `merge:`). Review time is the first `review:` commit, or the local gate-pass row, to that same merge. Rework is `plan.md` `round:` minus one, checked against how many times the board line entered `send-back:`. When those counts differ, rework is `unknown`.
- Gate fails count failed `reach-review` runs recorded in `.git/jt-queue/gate-runs.jsonl`. `reach-review` appends one row per pass or gate failure (id, time, result, reason). It does not store command output. The file stays on this machine, with `attempts.json`. Older tasks have no rows, so their gate fails stay `unknown`.
- Escaped defects list merged tasks that a later git revert names, and tasks linked from a PR or issue labelled `bug` opened after the merge. `gh` is used only when it is installed. If it is missing, `bug-label` is `unknown` rather than zero.
- The spec `board.html` command is unchanged. The gate checks, who may merge, and which queue files are committed are unchanged.
- Pin installs with `v24.10.0`. Skill and plugin metadata are `24.10.0`.

## 24.9.0 - AGENTS.md is the repo's agent instructions

- `/jt-setup` writes `AGENTS.md` at the repo root. It lists `TEST_CMD`, `LINT_CMD`, `TYPECHECK_CMD`, `SECURITY_CMD`, `VERIFY_CMD`, and `AFFECTED_TEST_CMD`, the flow spec -> tasks -> work -> gate -> human merge, the house rules, and where `jt-queue/` files live.
- `CLAUDE.md`, when created or already present, is an `@AGENTS.md` import. It does not repeat that file.
- An existing `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, or board is not replaced. `gate.py agents` shows a diff, keeps the current text, and adds only a `::: jtek:start` section. The same files produce no new diff on the next run. `unparsed` means the file is left untouched.
- `gate.py detect` proposes those slots from `package.json` scripts, `pyproject.toml`, `Makefile`, `justfile`, `go.mod`, `Cargo.toml`, and `.github/workflows` run lines. A slot with no source stays empty.
- Pin installs with `v24.9.0`. Skill and plugin metadata are `24.9.0`.

## 24.8.0 - screen evidence a human can review

- On a screen task, `/jt-work` drives the app with Microsoft's Playwright CLI (`playwright-cli -s=<ticket-id>`, one session per worktree), not Playwright MCP. It reads console and network errors. An uncaught error or a console error on a touched screen is `finding:` in `plan.md` `## evidence`, next to a screenshot path for that AC id. A short video or trace path is optional.
- The gate still decides with `<VERIFY_CMD>` (`npx playwright test`, including `toHaveScreenshot`). `reach-review` refuses `snapshot-update` instead of running `--update-snapshots`, `-u`, or a Playwright config that would write baselines. `updateSnapshots` must be `none`. A baseline change is a separate step a human reviews. This task does not accept new snapshots.
- A `screen: yes` pass line that names an AC or EC id must quote that id in `## evidence` and name a screenshot path. Missing either is `evidence-missing`. A console or network error in that section that is not marked `finding:` is `console-error`.
- `/jt-setup` proposes `<VERIFY_CMD>` `npx playwright test` and a minimal `playwright.config.ts` when `gate.py detect` sees a web app. `--write` creates the file only when none exists. When pstack `create-verification-skill` is installed, `feature-map:` says so and the agent follows that map.
- Install docs name `npm install -g @playwright/cli@latest`, `playwright-cli install --skills`, and the official Playwright CLI and skills pages. The board slot is `VERIFY_CMD`.
- SkillSpector treats `npx playwright test` as that verify command, not an unpinned MCP server (`.skillspector-baseline.yaml`).
- Fail-fast order, size tiers, `## ai-review`, and pre-commit hooks are unchanged.
- Pin installs with `v24.8.0`. Skill and plugin metadata are `24.8.0`.

## 24.7.0 - pre-commit hooks as an early warning

- `/jt-setup` runs `gate.py hooks` and shows a `.pre-commit-config.yaml` with the source of each hook. It waits for confirmation. `--write` merges into an existing file. Existing repos, revs, and hook ids stay.
- The proposal pins typos, plus actionlint and zizmor when `.github/workflows` exists. It adds the board's `LINT_CMD` or secret scan only when that command is a cheap local tool, and a commit-msg hook (commitlint when that config exists, otherwise conventional-pre-commit).
- `reach-review` does not run pre-commit and does not fail when it is missing. When the `pre-commit` program is installed, `allowed` prints `hooks: ok` or `hooks: missing`.
- Size tiers, the fail-fast order, and `## ai-review` are unchanged.
- This repo checks typos, actionlint, and zizmor on commit.
- Pin installs with `v24.7.0`. Skill and plugin metadata are `24.7.0`.

## 24.6.0 - one fresh-context review before the human

- After the fail-fast checks pass, `/jt-work` invokes one reviewer in a fresh context that cannot read the implementer's chat. It receives only the spec acceptance criteria and edge cases, `task.md`, and the diff.
- The one reviewer is pstack `/interrogate` when that skill is installed, otherwise Matt `/pr`, otherwise `/ponytail-review` when the effective size is `large`. No second reviewer. If none of those skills is installed, `plan.md` records `fallback: no reviewer skill installed`.
- Findings go in `## ai-review` as `accepted:` or `rejected:` plus a reason. Accepted findings are fixed and the gate runs again. The reviewer does not approve or merge. `/jt-review` stays human-only.
- The gate requires that section on Standard `medium` and `large` (`refused: ai-review`). `small` and Quick print `ai-review: skip`. Size tiers and the fail-fast order are unchanged. `large` still prints `size-hooks:`; `worktree-rounds` is still only recorded.
- Pin installs with `v24.6.0`. Skill and plugin metadata are `24.6.0`.

## 24.5.0 - fail fast, cheapest check first

- `reach-review` stops at the first failure and prints `step:` and `skipped:` (the next step). Order: secret scan, deprecated-name denylist, `<TYPECHECK_CMD>`, `<LINT_CMD>`, tests, `<VERIFY_CMD>`.
- Secret scan runs `<SECURITY_CMD>` when that program is installed (the TruffleHog slot). Otherwise it keeps the v23 `secret-suspect` check. The output names the file and never the value, and the scan's own output is not printed.
- `<DENYLIST>`, or `jt-queue/denylist.txt` when the cell is empty, lists `old -> replacement` (for example `dmedasset -> dmecasset`). A hit in the diff fails with `deprecated-name` and names the replacement. An empty list skips the step.
- On Standard, typecheck runs before lint, and both run before tests. Quick still skips typecheck and lint. `<VERIFY_CMD>` runs after tests on every tier when the cell is set. Empty cells stay `skip`.
- Non-empty `<SECURITY_CMD>` and `<VERIFY_CMD>` join the `approve-commands` hash (home table and each `## repos` block). Empty cells stay out, so an existing approval still matches. `<DENYLIST>` is not a shell command and is not part of the hash.
- Size tiers and `<AFFECTED_TEST_CMD>` are unchanged. `allowed` prints `gates:` as `secret`, `denylist`, `typecheck`, `lint`, `tests`, `verify`, `screen`, `review-diff`, `test-weakening`.
- Pin installs with `v24.5.0`. Skill and plugin metadata are `24.5.0`.

## 24.4.0 - one spec approval, traced to the task

- `check.py` fails a `✅` approval while an open question Blocks `dev` or `AC`. A question that Blocks `later` does not. A spec still waiting for the PO does not fail for that reason.
- Acceptance Criteria gains a `Guards` column. Each EC names the AC it guards. An empty link, or a link to an AC that is not in the table, is an error. A table without that column prints `migration:` and still checks.
- A task with `spec:` must copy each `pass:` line from that row (`- <id>: <Then>`). The gate refuses `pass-ac` when the id or the Then does not match, and `spec-unapproved` when the spec is not approved. Tasks with no `spec:` line are unchanged. Size tiers are unchanged.
- One spec approval covers the tasks derived from it. `/jt-add-task` does not ask again for those tasks. `/jt-work` does not ask the human to approve each of them or their pass lines. `/jt-review` stays human-only. Shell commands still need the one-time `approve-commands` on each machine.
- Commit the queue files a teammate needs: `jt-queue/board.md`, `brief.md`, `tasks/<id>/task.md`, and `plan.md` (including `## decisions`). Leave local files uncommitted: `lessons.md` (notes for this agent, not the task); `.git/jt-queue/approved-commands.json` (permission to run shell commands; it must not travel in a commit); `.git/jt-queue/logs/` (command output can hold secrets); `.git/jt-queue/attempts.json` (this machine's round counter); `.env` files and private keys.
- Pin installs with `v24.4.0`. Skill and plugin metadata are `24.4.0`.

## 24.3.0 - compose external method skills

- `/jt-work` invokes obra/superpowers **executing-plans** and **test-driven-development** for Standard work; playbooks.md is a short gate-habits fallback instead of inlined TDD and per-kind method text.
- Spec skills invoke Matt Pocock **grill-me** and superpowers **brainstorming** for questioning (outcomes unchanged: `check.py`, blocking questions, `(Recommended)` options). `/jt-spec-handoff` follows Matt Pocock **handoff** style; the `spec.md` template and checker rules stay.
- README and `skills/jt-help/references/install-before-use.md` move superpowers (`executing-plans`, `test-driven-development`, `brainstorming`) and **grill-me** to **Required**; official install links only in the reference file.
- Pin installs with `v24.3.0`. Skill and plugin metadata are `24.3.0`.

## 24.2.1 - install before use

- README and `/jt-help` document a fixed **Install before use** checklist: required tools, recommended skills, and optional tools with copy-paste install commands, the jtek step each plugs into, and board slots (`TEST_CMD`, `AFFECTED_TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, `VERIFY_CMD`). The list lives in `skills/jt-help/references/install-before-use.md` with official install URLs (no markdown links in references).
- Vitest, Jest, and pytest-testmon rows point at `<AFFECTED_TEST_CMD>` for `small` tasks, on top of v24.2.0 size tiers.
- Pin installs with `v24.2.1`. Skill and plugin metadata are `24.2.1`.

## 24.2.0 - size the process to the work

- A task has `size:` `small`, `medium`, or `large`, set when the task or the spec is created. A `size:` token on the board line overrides it. Unset stays `medium`, so an existing board still runs the full gate.
- `small` runs the full `<TEST_CMD>` unless the board sets `<AFFECTED_TEST_CMD>` or `<TEST_CMD>` contains `{files}`. The name-stem heuristic fills `{files}`. The cell can also be a command that selects its own tests (`npx vitest --changed`, `npx jest --findRelatedTests {files}`, `pytest --testmon`). When no affected test can be named, `small` still runs the full suite and prints `affected: none -> full suite`. `medium` and `large` run `<TEST_CMD>` unchanged. `small` needs no spec (`/jt-add-task`). `medium` is a short spec. `large` is a full spec.
- The gate raises that size, and never lowers it, when the diff touches auth or a migration or `.sql` file, or is larger than `<DIFF_LIMIT>` lines (empty means 400). `allowed` then prints `size-from:` and `escalate:` (`auth`, `migrations`, or `diff`).
- `large` prints `size-hooks: worktree-rounds, fresh-context-review, high-risk`. Those three are recorded only; this version does not run them.
- An empty `<AFFECTED_TEST_CMD>` is not part of the command approval. Setting it is `commands-changed` until a human approves it.

## 24.1.0 - conventional task branches

- `gate.py` and `landed.py` find the task branch as `type/<ticket-id>-<slug>` (for example `feat/BOOK-12-room-search`), using `ticket:` from `task.md` and the task kind. Legacy `task-<id>` / `task-<id>-<slug>` still work; `reach-review` prints `branch-deprecated:` when it uses one.
- `/jt-work` skill text, `contract.md`, README **Names**, and the usage docs describe the conventional branch as the default. Worktree temp dirs use the `jt-work-` prefix.
- Pin installs with `v24.1.0`. Skill and plugin metadata are `24.1.0`.

## 24.0.0 - commands that say what they do

- **Breaking:** `/jt-work-queue` is three commands. `/jt-setup` writes the board. `/jt-add-task` agrees the brief and drafts tasks (the gate's `brief` and `add-task` actions both print this command). `/jt-work` implements the next ready task. `/jt-review-work` is `/jt-review`. Plugin names follow the skill names (`/jtek:jt-work`, `/jtek:jt-review`, and the rest).
- **Breaking install:** each skill is a folder you can install alone, `npx skills add thitinan147/jtek-skill --skill <name>` with a space before the name. The Claude Code plugin still installs the whole set.
- The spec workflow from [scrum-spec](https://github.com/thitinan147/scrum-spec) 0.5.0 (`81d88ea`) is here as `/jt-spec-split`, `/jt-spec-ac`, `/jt-spec-handoff`, and `/jt-board`. `/jt-help` lists every command, the order, and which are human-only. Command names do not use the word scrum.
- `gate.py` checks the same things as v23. `next` prints the new command for the action. The refusal tokens, the approval hash, the `gates:` line, and the secret and test-weakening reports are unchanged.
- `check.py` is unchanged, including a human name and date on approvals and D lines, and a failure when an AI signed one. `check.py` and `board.py` still share one `specdoc.py`. The marker `<!-- scrum-spec -->` and `scrum-spec/config.md` stay, because the checker reads them. Existing spec files and `jt-queue/` boards need no rewrite.
- Names the skills write: a commit and a draft PR title are `type(scope): summary (<ticket-id>)`, using the id the ticket already has (`BOOK-12`, `#45`, a Notion id). The skills require an id and do not check its shape. `/jt-work` is one command with no `--loop` flag. It works ready tasks in board order and skips blocked ones, or only the ticket id it was given. The branch `gate.py` finds is still `task-<id>-<slug>`. The conventional branch `type/<ticket-id>-short-slug` is documented and not enforced.
- See MIGRATING.md.

## 23.0.0 - the gate runs the checks it already named

- **Breaking:** a Standard task with no diff outside `jt-queue/` no longer passes `reach-review`. A `(feat)` branch with zero commits used to answer `allowed` and `repo-review: skip` with no plan and no evidence. It is now `review-diff` / `no diff outside jt-queue/ to review`.
- **Breaking:** on Standard, a non-empty `<LINT_CMD>` or `<TYPECHECK_CMD>` runs in the task worktree after `<TEST_CMD>` and must exit 0 (`lint-failed`, `typecheck-failed`, and the matching timeouts; each counts as a round). An empty cell is `skip` and is not run. Quick tier does not run them. The same commands run per repo when a task lists `repos:`.
- **Breaking for boards that already set those cells:** `LINT_CMD` and `TYPECHECK_CMD` are now part of the `approve-commands` hash (home table and each `## repos` block) when the cell is not empty. Setting or changing one is `commands-changed` until a human approves it again. Empty cells stay out of the hash, so a v22 approval still matches. See MIGRATING.md.
- `allowed` prints one `gates:` line in a fixed order: `tests`, `lint`, `typecheck`, `screen`, `review-diff`, `security`, `test-weakening`.
- `reach-review` refuses with `secret-suspect` and `next: ask` when the diff adds a file whose name starts with `.env` (`.env.example` is allowed), a private-key file (`*.pem`, `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`; not `*.pub`), or a `PRIVATE KEY` block. The output names the file or `file:line` and never the value.
- A deleted test file, or an added `.skip` / `.only` / `xit` / `@skip` / `xfail` marker, is reported as `test-weakening` on `allowed`. It does not refuse: the same diff can be a rename or a skip the task asked for, and the human judges it the way they already judge `outside-files:`.
- `assets/lessons.template.md` has an `enforced by` column. The second time the same lesson appears, add a `chore` task whose `pass:` is a lint rule, a test, or a gate check, and cite that check in the column.

## 22.2.0 - task branches say what they hold

- Task branches can be named `task-<id>-<slug>`, for example `task-12-login-rate-limit`. The slug is ASCII `a-z0-9` words joined by `-`; any other name is not seen as the task branch. The gate and `landed.py` find the branch by its `task-<id>` prefix, so nothing is stored on the board, and renaming the task later does not lose the branch. A plain `task-<id>` still works, so existing branches and open PRs need no change.
- One branch per task: when `task-<id>` and `task-<id>-<slug>` (or two slugs) both exist, `reach-review` refuses with `task-branch-missing`, and `detail:` names the branches to choose from.
- `landed` still finds a squash-merged slug branch after the branch was deleted from your clone, by matching the merged PR's head against `task-<id>-<slug>`.
- Fix: the documented draft PR command now passes `--title '<id>: <name>'` (single-quoted, since the name is board text) and `--body`. Without them `gh pr create` refuses when an agent runs it, because it cannot prompt. The body leaves out `do:` and `pass:` so task text stays in your gitignored `jt-queue/`.
- `getting-started.md` uses slug branches in the walkthrough; `plan.template.md` shows `Branch: task-<id>-<slug>`.
- CHANGELOG: the 22.0.0 and 22.1.0 entries are one list each again.

## 22.1.0 - one board for frontend and backend

- New, opt-in: a `## repos` section on the board declares sibling repos (one `### <name>` block each with `path:`, `queue:`, and the usual command table). Without it nothing changes, and existing command approvals still match.
- `next` stops with `repo-invalid`, `not-ready` (for example `be.TEST_CMD`), or `repo-missing` when a repo block is wrong or the repo is not at its path.
- A task can list `repos: fe, be`. `reach-review` then needs `task-<id>` in every listed repo, runs each repo's `TEST_CMD` in its own worktree, needs a `<repo>: <sha>` line per repo in `## review-diff`, reports `outside-files:` per repo, and refuses code in an unlisted repo (`repo-undeclared`). `--write` records one PR link per repo.
- `start:` can list `- <repo>: <command>` lines: the screen check starts every repo from its task branch and waits for all ports before `click:`.
- `landed.py` and `gate.py landed` answer `landed: all` only when every repo has landed, in `land:` order, with `order-warning:` when a repo landed out of order.
- `approve-commands` covers each repo's `path:`, `queue:`, `TEST_CMD`, `SETUP_CMD`, and a task's `start:` list with its `repos:`. Once a board has `## repos`, it always needs approval, even when every repo is `no-suite`, and `screen-check` checks it too.
- A repo cannot be named after a status word (`merge`, `review`, `ask`, `drop`, `send-back`).
- Removed `<REPO_SKILLS>` from the board template, `jt-work-queue` SKILL.md, and `contract.md`. The gate never read it; the agent reviews a Standard task's diff itself and records it in `## review-diff`, as before. Boards that still have the row keep working.
- README and CHANGELOG show the plugin marketplace pinned with `#v22.1.0`. `getting-started.md` marks the task 2 block as an excerpt.

## 22.0.1 - easier to start

- Claude Code plugin: `/plugin marketplace add thitinan147/jtek-skill#v22.0.1`, then `/plugin install jtek@jtek-skill`. The skills are also available as `/jtek:jt-work-queue` and `/jtek:jt-review-work`.
- New Getting started guide: the words the skill uses, and one real round from setup to merge with the gate's actual output.
- README rewritten for new users. The full walkthrough moved to `docs/usage.md`, and the v20/v21 upgrade notes to `MIGRATING.md`. Added `CONTRIBUTING.md`, issue templates, and a platform table (Windows is not supported yet; use WSL).
- Fix: when `## evidence` in `plan.md` misses a `pass:` line, the `hint:` no longer tells the agent to add a `## review-diff` section it already has.
- `jt-work-queue` SKILL.md: the tier table lists only the two gate tiers. Diff review and asking instead of guessing are separate rules, with the same content as before.
- A test keeps the version in `plugin.json`, `marketplace.json`, and both SKILL.md files the same.

## 22.0.0 - evidence the gate can check (breaking)

- **Breaking:** a `Standard` task now needs more in `plan.md` before `review:`. `## review-diff` must contain `verdict: pass` and at least one `checked:` line besides the commit SHA (a `verdict: fix-needed` refuses), and every `pass:` line of `task.md` must be quoted in the first cell of a filled `| pass line | command | result |` row of `## evidence`. Copy the new `assets/plan.template.md`; plans written for v21 are refused with `detail:` naming what is missing.
- **Breaking:** the gate counts failed rounds. Every failed `reach-review` (test, timeout, or setup) prints `round <n> of 3`, even when the commit did not change; the third answers `next: ask`. `gate.py ask` resets the count, and `next` forgets the count of a task once it is closed on the board. The count lives in `.git/jt-queue/attempts.json` and is written under a lock.
- Every refusal now prints a one-line `hint:`. `start-down` and `click-mismatch` keep the command output in a log (`log:`), and `related`, `review-diff`, `one-off-checker`, and `browser-empty` say what to fix in `detail:`.
- `gate.py detect --root .` prints the suggested `TEST_CMD` and `SETUP_CMD` with the file each came from. It writes nothing.
- `task.md` has an optional `needs:` list for work in another repo. It is text only: `reach-review` prints it, `/jt-review-work` shows it and asks the human to confirm each item has landed before `merge:`; the gate never refuses because of it.
- Added `assets/brief.template.md` and `assets/lessons.template.md`. `plan.template.md` gains `## evidence` rows, a structured `## review-diff`, kind notes, and a `## send-back` section.
- Both skills say how to handle a `send-back:` task, and `/jt-review-work` can answer an `ask:`.
- Docs use the word "task" throughout (v21 mixed "card", "task", and "ticket"); `contract.md` now says queue files are read from the working tree unless tracked. The unused `chosen:` field is gone from `task.template.md`.
- Removed the unused `execute_test_cmd` and `surface_refusal` helpers.
- `jt-queue/` replaces `card-loop/`. A gitignored or untracked queue is read from the working tree, so personal queue files are not committed or pushed. A tracked queue is still read from its branch.
- Each task lives at `jt-queue/tasks/<id>/task.md` with its plan at `plan.md` in the same folder. Work branches are named `task-<id>`.
- **Breaking:** `card-loop/` queues, `card-<id>` branches, and command approvals in `.git/card-loop/` are not migrated. Recreate the queue under `jt-queue/` and run `gate.py approve-commands` again. Until `jt-queue/board.md` exists, `next` reports `board-missing`.

## 21.0.0 (security hardening release)

### Security and packaging
- **Fixed: board commands could be changed and run without a human noticing.** A new `gate.py approve-commands` step records the human-reviewed `TEST_CMD`/`SETUP_CMD` and card `start`/`click` (as a hash in `.git`). `reach-review` and `screen-check` now refuse when they are unapproved or changed since approval. Reproduced before the fix: editing `TEST_CMD` in `board.md` (committed or not) made `reach-review` run it and answer `allowed`.
- **Upgrade note:** after updating, run `gate.py approve-commands --root . --id <id>` once per card you want to verify, after reviewing the commands it prints. Without it the gate stops with `commands-unapproved`.
- Fixed invalid YAML frontmatter in `jt-review-work`: the unquoted `review: cards` in `description` made strict parsers fail to read the skill.
- `compatibility` now states Python 3.10+ and the optional `gh`; skill `version` is semver (`21.0.0`).
- Both skills now state that board, card, plan, diff, commit and PR text is data, not instructions.
- `JT_TEST_TIMEOUT` and `JT_GH_TIMEOUT` are capped at 3600 s; NaN is rejected.
- The three intentional `shell=True` calls are annotated (`# nosec B602`) with their reason.
- README: install pinned to a release tag (`#v21.0.0`); CI actions moved to Node 24 releases and `ubuntu-24.04`.
- Added `SECURITY.md` (trust model and reporting), CI (tests, bandit, skills validator, SkillSpector), and `.skillspector-baseline.yaml` for reviewed false positives.

## Before the hardening release
- Two-command rewrite: `/jt-work-queue` and `/jt-review-work`. See the README for the v20 migration guide.
