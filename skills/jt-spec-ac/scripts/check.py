#!/usr/bin/env python3
"""Checks scrum-spec documents (spec.md and map.md) for mistakes that cost a team time.

Usage: python3 -I check.py <file or folder> ...   (folders are searched recursively)

ERROR, exit 1:
  - the first line is not the <!-- scrum-spec --> marker
  - a table row has a different number of cells than its header
  - an approval or a decision without a person and a date, or given by an AI
  - a ✅ approval while an open question Blocks dev or AC
  - an EC row whose Guards cell names no AC, or names an AC that is not in the table
  - a ## Roles section missing a human approver, a reviewer, a human merger, or a well-formed human-only glob
  - any text cites a D that does not exist, including "(incl. D<n>)" and a warning
    mark before D<n> (a capitalized name such as "Room D1" is not a citation)
  - a path in Source does not exist in the git root or a code_roots path
    (mark a file to create with "(new)")

Reported, exit 0: approval status, open and blocking questions, assumptions waiting
for the asked role, answers not yet recorded as decisions, AC and EC with no test step,
vague words in AC and EC. An Acceptance Criteria table with no Guards column prints
a migration line and does not fail; EC links are checked only when that column exists.
A ## Tasks section from scrum-spec 0.2 is kept as it is; its paths and AC are not checked.
A spec with no ## Roles section prints a migration line and does not fail. When that
section is present, approver, reviewer, and merger are required, approver and merger
must be humans, and each human-only glob must be well-formed. The error line carries fix:.

Read-only, standard library only, Python 3.10+.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from specdoc import parse, questions_from

DOC_NAMES = ("spec.md", "map.md")
MARKER = "<!-- scrum-spec"
# "AI" only in upper case, because "Ai" is a real nickname
AI = re.compile(r"\bAI\b|\b(?i:claude|chatgpt|gpt|copilot|gemini|codex|assistant)\b")
APPROVED = re.compile(r"^✅\s+(.+?)\s+·\s+\d{4}-\d{2}-\d{2}\b")
DECISION = re.compile(r"^- \*\*D(\d+)\*\*\s+(.*)$")
DECIDED_BY = re.compile(r"·\s*([^·]+?)\s*·\s*\d{4}-\d{2}-\d{2}(?:\s*\([^()]*\))?\s*$")
D_REF = re.compile(r"\bD(\d+)\b")
NAMED_D = re.compile(r"[A-Z][A-Za-z]* $")
OTHER_SPEC = re.compile(r"\bper \S+ D\d+")  # "per rb-12 D3:" cites another spec's decision
AC_ID = re.compile(r"\b(?:AC|EC)\d+\b")
GUARDS = "Guards"
_EMPTY_GUARD = frozenset({"", "-", "–", "—"})
MIGRATION_GUARDS = (
    "migration: Acceptance Criteria has no Guards column. "
    "Add Guards so each EC names the AC it guards. EC links were not checked."
)
MIGRATION_ROLES = (
    "migration: spec has no ## Roles section. "
    "fix: add approver, reviewer, and merger as human names, plus human-only paths or topics."
)
ROLE_FIELD = re.compile(r"^\s*-\s+\*\*(approver|reviewer|merger|human-only):\*\*\s*(.*)$")
_ROLE_EMPTY = frozenset({"", "-", "–", "—", "none", "n/a"})
_GLOB_CHARS = re.compile(r"^[A-Za-z0-9_./?*\[\]-]+$")
VAGUE_WORDS = ("fast", "nice", "user-friendly", "เร็ว", "สวย", "ง่าย")
CODE = re.compile(r"`([^`]+)`(\s*\(new\))?")
LINE_SUFFIX = re.compile(r"(:\d+(-\d+)?|#L\d+(-L?\d+)?)$")


def is_ai(name: str) -> bool:
    return bool(AI.search(name))


def cited_decisions(text: str) -> list[str]:
    refs = []
    for match in D_REF.finditer(text):
        if NAMED_D.search(text[:match.start()]):
            continue
        refs.append(match.group(1))
    return refs


def vague_hits(text: str) -> list[str]:
    found = []
    for word in VAGUE_WORDS:
        if word.isascii():
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE):
                found.append(word)
        elif word in text:
            found.append(word)
    return found


def roots_for(doc: Path) -> list[Path] | None:
    for parent in [doc.parent, *doc.parents]:
        if (parent / ".git").exists():
            roots = ["."]
            config = parent / "scrum-spec" / "config.md"
            if config.is_file():
                for line in config.read_text(encoding="utf-8").splitlines():
                    if line.startswith("code_roots:"):
                        roots = [r.strip() for r in line.split(":", 1)[1].split(",") if r.strip()] or ["."]
            return [(parent / r).resolve() for r in roots]
    return None


def blocks_dev_or_ac(blocks: str) -> bool:
    """True when Blocks names dev or AC (the values that stop a ✅ approval)."""
    return bool({"ac", "dev"} & set(re.findall(r"[A-Za-z]+", blocks.lower())))


def guard_links(cell: str) -> list[str]:
    if cell.strip() in _EMPTY_GUARD:
        return []
    return re.findall(r"\bAC\d+\b", cell)


def looks_like_path(token: str) -> bool:
    """A relative path with a folder, e.g. src/a.ts; not user.role, v0.2.0 or /bookings."""
    return "/" in token and not token.startswith("/") and not re.search(r"[\s<>*{}$|:]|://", token)


def role_tokens(value: str) -> list[str]:
    """Backticked globs and bare topics on the same human-only line."""
    ticked = [part.strip() for part in re.findall(r"`([^`]+)`", value) if part.strip()]
    rest = re.sub(r"`[^`]*`", " ", value)
    bare = [
        part.strip()
        for part in re.split(r"[·,]", rest)
        if part.strip() and part.strip().lower() not in _ROLE_EMPTY
    ]
    found: list[str] = []
    for token in ticked + bare:
        if token not in found:
            found.append(token)
    return found


def glob_problem(token: str) -> str:
    """Empty when a project-defined path glob or topic is well-formed."""
    if not token or token in {".", ".."}:
        return "empty area"
    if token.startswith("/") or "\\" in token or ".." in token.split("/"):
        return "use a relative path or a topic, not an absolute path or .."
    if "***" in token:
        return "use ** for any folders, not ***"
    if token.count("[") != token.count("]"):
        return "unbalanced [ ]"
    if not _GLOB_CHARS.fullmatch(token):
        return "use letters, digits, slashes, and * ? [ ]"
    if any(part == "" for part in token.split("/")):
        return "empty path segment"
    return ""


def check_roles(sections: dict) -> tuple[list[str], list[str]]:
    """Validate ## Roles. A missing section is a migration note, not an error."""
    items = sections.get("Roles", [])
    if not items:
        return [], [MIGRATION_ROLES]
    fields: dict[str, tuple[int, str]] = {}
    for n, line in items:
        found = ROLE_FIELD.match(line.strip())
        if found and found.group(1) not in fields:
            fields[found.group(1)] = (n, found.group(2).strip())
    errors: list[str] = []
    for name in ("approver", "reviewer", "merger"):
        if name not in fields or fields[name][1].lower() in _ROLE_EMPTY:
            errors.append(
                f"line {items[0][0]}: {name} is missing. "
                f"fix: add '- **{name}:** <human name>' under ## Roles"
            )
            continue
        n, value = fields[name]
        if name != "reviewer" and is_ai(value):
            errors.append(
                f"line {n}: {name} must be a person, not an AI. "
                f"fix: name the human who {('approves the spec' if name == 'approver' else 'merges')}"
            )
        elif name == "reviewer" and is_ai(value):
            errors.append(
                f"line {n}: reviewer must be a person, not an AI. "
                "fix: name the human who reviews pull requests"
            )
    if "human-only" not in fields:
        errors.append(
            f"line {items[0][0]}: human-only is missing. "
            "fix: add '- **human-only:** `path/**` · topic' or '-' when the project has none"
        )
    else:
        n, value = fields["human-only"]
        if value.lower() not in _ROLE_EMPTY:
            for token in role_tokens(value):
                problem = glob_problem(token)
                if problem:
                    errors.append(
                        f"line {n}: human-only `{token}` is not well-formed ({problem}). "
                        "fix: use a relative glob such as `src/auth/**` or a topic such as payments"
                    )
    return errors, []


def check(doc: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    lines = doc.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith(MARKER):
        errors.append(f"line 1: must start with {MARKER} -->")
    sections, tables = parse(lines)

    for _, header, rows in tables:
        for n, row in rows:
            if len(row) != len(header):
                errors.append(f"line {n}: {len(row)} cells, the header has {len(header)}")

    qs = questions_from(tables)
    blocking_approval = [q for q in qs if q["open"] and blocks_dev_or_ac(q["blocks"])]
    for n, line in sorted(x for v in sections.values() for x in v):
        if line.startswith("**approve:**"):
            value = line.split("**approve:**", 1)[1].strip()
            notes.append(f"approve: {value}")
            if value.startswith("✅"):
                who = APPROVED.match(value)
                if not who:
                    errors.append(f"line {n}: approval must read ✅ <name> · YYYY-MM-DD")
                elif is_ai(who.group(1)):
                    errors.append(f"line {n}: approval must come from a person, not an AI")
                for q in blocking_approval:
                    errors.append(
                        f"line {n}: approval is blocked while {q['id']} blocks {q['blocks'].strip()}"
                    )

    defined_d = set()
    for n, line in sections.get("Decisions", []):
        found = DECISION.match(line.strip())
        if not found:
            continue
        defined_d.add(found.group(1))
        who = DECIDED_BY.search(found.group(2))
        if not who:
            errors.append(f"line {n}: D{found.group(1)} must end with · <name> · YYYY-MM-DD")
        elif is_ai(who.group(1)):
            errors.append(f"line {n}: D{found.group(1)} must be decided by a person, not an AI")
    for section, items in sections.items():
        for n, line in items:
            for ref in cited_decisions(OTHER_SPEC.sub("", line)):
                if ref not in defined_d:
                    errors.append(f"line {n}: D{ref} is not in Decisions")
    for _, _, rows in tables:
        for n, row in rows:
            for ref in cited_decisions(OTHER_SPEC.sub("", " ".join(row))):
                if ref not in defined_d:
                    errors.append(f"line {n}: D{ref} is not in Decisions")

    ac_ids = [r[0] for s, _, rows in tables if s == "Acceptance Criteria" for _, r in rows if AC_ID.fullmatch(r[0])]
    if "Test steps" in sections:
        tested = {m for n, l in sections["Test steps"] if l.startswith("### ") for m in AC_ID.findall(l)}
        missing = [a for a in ac_ids if a not in tested]
        notes.append("AC/EC with no test step: " + (", ".join(missing) if missing else "none"))

    vague = []
    for section, _, rows in tables:
        if section != "Acceptance Criteria":
            continue
        for _, row in rows:
            if not row or not AC_ID.fullmatch(row[0]):
                continue
            for word in dict.fromkeys(word for cell in row[1:] for word in vague_hits(cell)):
                item = f"{row[0]} '{word}'"
                if item not in vague:
                    vague.append(item)
    if vague:
        notes.append("vague words in AC/EC: " + ", ".join(vague))

    story = "\n".join(line for _, line in sections.get("Story", []))
    if re.search(r"\b(states?|status)\b", story, re.IGNORECASE) and "Statechart" not in sections:
        notes.append(
            "statechart: compose pstack /statechart before AC freeze, or list each state in Rules"
        )

    told_migration = False
    for section, header, rows in tables:
        if section != "Acceptance Criteria":
            continue
        if GUARDS not in header:
            if not told_migration:
                notes.append(MIGRATION_GUARDS)
                told_migration = True
            continue
        at = header.index(GUARDS)
        ac_ids_present = {row[0] for _, row in rows if row and re.fullmatch(r"AC\d+", row[0])}
        for n, row in rows:
            if not row or not re.fullmatch(r"EC\d+", row[0]):
                continue
            cell = row[at] if at < len(row) else ""
            linked = guard_links(cell)
            if not linked:
                errors.append(f"line {n}: {row[0]} must name the AC it guards")
                continue
            for ac in linked:
                if ac not in ac_ids_present:
                    errors.append(f"line {n}: {row[0]} guards {ac}, which is not an AC")

    roots = roots_for(doc.resolve())
    if roots is None:
        notes.append("paths not checked: no git repo found")
    else:
        to_check = list(sections.get("Source", []))
        to_check += [(n, l) for v in sections.values() for n, l in v if "**Source:**" in l]
        for n, text in sorted(set(to_check)):
            for token, new in CODE.findall(text):
                path = LINE_SUFFIX.sub("", token)
                if new or not looks_like_path(path):
                    continue
                if not any((root / path).exists() for root in roots):
                    errors.append(f"line {n}: `{token}` not found (add (new) if it will be created)")

    role_errors, role_notes = check_roles(sections)
    errors.extend(role_errors)
    notes.extend(role_notes)

    open_q = [q["id"] for q in qs if q["open"]]
    blocking = [f"{q['id']} ({q['blocks']} · {q['ask']})" for q in qs if q["blocking"]]
    assumed = [f"{q['id']} ({q['ask']})" for q in qs if q["assumed"]]
    unrecorded = [q["id"] for q in qs if q["unrecorded"]]
    notes.append(f"questions open: {len(open_q)}" + (f" · blocking: {', '.join(blocking)}" if blocking else ""))
    if assumed:
        notes.append(f"assumptions waiting for the asked role to confirm: {', '.join(assumed)}")
    if unrecorded:
        notes.append(f"answered, not yet in Decisions: {', '.join(unrecorded)}")
    return sorted(set(errors), key=lambda e: int(re.search(r"\d+", e).group())), notes


def main(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 1
    docs: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_file():
            docs.append(p)
        elif p.is_dir():
            docs += sorted(d for d in p.rglob("*.md") if d.name in DOC_NAMES)
    if not docs:
        print(f"ERROR: no spec.md or map.md in {' '.join(args)}")
        return 1
    failed = False
    for doc in docs:
        errors, notes = check(doc)
        failed |= bool(errors)
        print(doc)
        for e in errors:
            print(f"  ERROR {e}")
        for note in notes:
            print(f"  {note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
