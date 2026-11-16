---
name: jt-board
description: "HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Writes a FigJam-style board.html from spec.md and map.md and does not edit those files. Use when the human explicitly invokes /jt-board."
disable-model-invocation: true
license: MIT
compatibility: Claude Code, Codex, Cursor and other Agent Skills clients. Needs git and Python 3.10+ (standard library only).
metadata:
  author: Thitinan
  version: "24.6.0"
  short-description: Open a FigJam-style board of the specs
argument-hint: "[<flow or folder>]"
---

# jt-board

**HUMAN-ONLY COMMAND.** This command only draws the board. It does not edit `spec.md` or `map.md`, and it does not commit, push, delete, or move files.

```bash
python3 -I <this-skill-dir>/scripts/board.py <folder> --open
```

`<folder>` is the flow or docs directory the user named, otherwise `<docs_root>` from `scrum-spec/config.md`, otherwise `scrum-spec`. The script writes `<folder>/board.html` (or `-o <path>`). `--open` opens it in the browser.

The page loads Google Fonts when someone opens it. Say that when you hand back the path.

Reply with the path, how many stories and maps were written, and which specs are blocked. Do not paste the HTML. A question is blocking on the board when the checker would report it as blocking. `scripts/board.py` and the checker share `scripts/specdoc.py`.
