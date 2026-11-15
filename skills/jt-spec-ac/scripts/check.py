#!/usr/bin/env python3
"""Checks scrum-spec documents (spec.md and map.md) for mistakes that cost a team time.

Usage: python3 -I check.py <file or folder> ...   (folders are searched recursively)

ERROR, exit 1:
  - the first line is not the <!-- scrum-spec --> marker
  - a table row has a different number of cells than its header
  - an approval or a decision without a person and a date, or given by an AI
  - any text cites a D that does not exist, including "(incl. D<n>)" and a warning
    mark before D<n> (a capitalized name such as "Room D1" is not a citation)
  - a path in Source does not exist in the git root or a code_roots path
    (mark a file to create with "(new)")

Reported, exit 0: approval status, open and blocking questions, assumptions waiting
for the asked role, answers not yet recorded as decisions, AC and EC with no test step,
vague words in AC and EC.
A ## Tasks section from scrum-spec 0.2 is kept as it is; its paths and AC are not checked.

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


def looks_like_path(token: str) -> bool:
    """A relative path with a folder, e.g. src/a.ts; not user.role, v0.2.0 or /bookings."""
    return "/" in token and not token.startswith("/") and not re.search(r"[\s<>*{}$|:]|://", token)


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

    qs = questions_from(tables)
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
