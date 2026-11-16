# <ID> - <short name>

kind: <kind>

# size: small, medium, or large. The gate may raise it. A size: token on the board line overrides it.
size: medium

# ticket: the id this work already has. Copy it (BOOK-12, #45, a Notion id).
# The gate does not read this line. Do not invent an id.
ticket:

layer:

screen: no
# For `screen: yes` a human approves start and click with gate.py approve-commands.
# start runs the app, port is what it listens on (space or comma list), wait is seconds to wait,
# click is the command that opens the screen and checks what pass names.
start:
port:
wait:
click:

do:
- 

out:
- 

# spec: path of spec.md when this task comes from an approved spec. Empty when there is no spec.
# pass: lines are then "- <AC id>: <Then>" copied from that row. A vague line cannot be checked.
spec:

# Each pass line is something to run or open. A vague line cannot be checked.
pass:
- 

# files is this task's vertical slice, not a whole layer.
files:
-

# repos names the repos this task changes when board.md has '## repos' (for example: fe, be).
# Leave it empty for a task in this repo only. Prefix files: with <repo>: and give start: one
# '- <repo>: <command>' line per repo (all start before click). 'click: <repo>: <command>' runs
# in that repo, otherwise in the first one. land is the order the repos must land in.
repos:
land:

# needs lists work in another repo that must land first, one line each, for example: be-repo POST /login merged.
# The gate does not read it. /jt-review shows it before merge.
needs:
- 

refs:
- 

ask:
