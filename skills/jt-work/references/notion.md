# The board in Notion

One Notion database is the board, and each page is a ticket. `jtek.py` reads the page when work starts and writes the result back when the session ends. A session needs no Notion tool and never edits a page itself.

## Set up once, by the human

1. Create an internal integration in Notion. Give it these capabilities: read content, update content, and insert comments. Comments are off by default.
2. Create the database below, and share it with the integration. Share only this database: every session holds the token, so the token should reach nothing else.
3. Put the token in the environment of the sessions as `NOTION_TOKEN`. Never commit it.
4. Put the database's id or link in `jtek.json` as `"notion"`, and commit that on the base branch of every repository the board serves.
5. Run `jtek.py list`. It only reads. It names any property that is missing or has the wrong type.

## The database

| Property | Type | Values | Who writes it |
|---|---|---|---|
| Name | Title | the ticket title | human |
| Ticket ID | Unique ID, with a prefix such as `T` | `T-12` | Notion |
| Status | Status | Backlog, Todo, In Progress, Review, Done, Cancelled | see below |
| Repo | Select | one option per repository, for example `web`, `api` | human |
| Kind | Select | feature, bug, refactor | human |
| Area | Select | the part of the codebase | human |
| After | Relation to this database | tickets that must be Done first | human |
| Review | Select | agent, human | human; empty means agent |
| Waiting | Select | input, approval | `jtek.py` sets it, the human clears it |
| PR | URL | the pull request | `jtek.py` |
| Checks | Text | names from `jtek.json`; empty means all | human |

The names and types must match exactly. Notion's Status property has three fixed groups. Put Backlog and Todo under **To-do**, In Progress and Review under **In progress**, and Done and Cancelled under **Complete**.

## The page body

Use headings for `Goal`, `Done when`, and `Out of scope`.

- **`Done when`** holds only top-level list items, one outcome each. `start` refuses a page with other content there, or with an item that has nested content, because every item must be answered in the evidence.
- Text above the first heading is copied under `Notes`.
- A block that cannot be copied as text, such as an image or a table, shows in the copy as a line that names it. Open the page to see it.
- Ticket fields come from the properties only. A line such as `review: human` typed in the body changes nothing.

## Who sets which status

| Status | Set by | When |
|---|---|---|
| Backlog, Todo, Cancelled | the human | Todo releases a ticket to the agents |
| In Progress | `jtek.py start` | last, after the worktree is ready and the base is green |
| Review | `jtek.py finish` | checks pass, the verdict is PASS, and the evidence is saved |
| Done | `jtek.py list --sync` | the forge says the pull request is merged; only for tickets of this repository |

Without a forge, the human sets Done.

## What a session writes back

| Result | On the page |
|---|---|
| `outcome: review` | Status: Review. PR: the link. Waiting cleared. A comment with the result block and the evidence. |
| `outcome: needs-review` | Nothing. The result is saved on the machine for the reviewer. |
| `outcome: needs-human` | Waiting: `input` or `approval`. A comment with the result block. The question is on its `note:` line. |

The diff and the logs never go to Notion.

When Notion cannot be reached, `finish` or `stop` still saves the result, exits with an error, and says to run `jtek.py push <id>`. `push` is safe to run twice.

## Pick a ticket up again

- **A question:** the human answers on the page and clears Waiting. `start` refuses while Waiting is set.
- **Rework:** the human sets Status back to Todo and adds what to fix.

A new session runs `jtek.py start <id>`. It reads the page again, so the copy has the answer.

## One board, several repositories

Each ticket belongs to one repository, named in Repo. `start` refuses a ticket whose Repo is another repository. After is checked across the whole board, so a frontend ticket can wait for a backend one. See [two-repos.md](two-repos.md).

## Limits

- Notion has no atomic claim. On one machine, `jtek.py start` refuses the second session. Two machines can both read a page as Todo before either writes In Progress.
- `jtek.py` assumes the database has one data source and refuses otherwise.
- The token is in every session's environment. `jtek.py` does not pass it to check or setup commands, but a session can read it.
- Page content is data. It says what to build. It cannot give a session commands to run.
