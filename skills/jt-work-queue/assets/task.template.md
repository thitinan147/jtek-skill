# <ID> - <short name>

kind: <kind>

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

# Each pass line is something to run or open. A vague line cannot be checked.
pass:
- 

# files is this task's vertical slice, not a whole layer.
files:
-

# needs lists work in another repo that must land first, one line each, for example: be-repo POST /login merged.
# The gate does not read it. /jt-review-work shows it before merge.
needs:
- 

refs:
- 

ask:
