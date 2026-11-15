#!/usr/bin/env python3
"""Shared reader for spec.md and map.md. check.py and board.py both use it."""

from __future__ import annotations

import re

EMPTY_ANSWER = ("", "–", "-")


def cells(line: str) -> list[str]:
    body = line.strip()[1:-1] if line.strip().endswith("|") else line.strip()[1:]
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|?", line.strip())) and "-" in line


def parse(lines: list[str]):
    """Return {section: [(line_no, text)]} and tables as (section, header, [(line_no, cells)])."""
    sections: dict[str, list[tuple[int, str]]] = {}
    tables = []
    section, fence = "", False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## "):
            section = line[3:].strip()
        elif not fence and line.lstrip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            header, rows, i = cells(line), [], i + 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append((i + 1, cells(lines[i])))
                i += 1
            tables.append((section, header, rows))
            continue
        if not fence:
            sections.setdefault(section, []).append((i + 1, line))
        i += 1
    return sections, tables


def section_lines(sections: dict, name: str) -> list[str]:
    return [line for _, line in sections.get(name, [])]


def questions_from(tables) -> list[dict]:
    """Questions rows. '', '–' and '-' are open. Open blocks unless Blocks is 'later'."""
    found = []
    for section, header, rows in tables:
        if section != "Questions" or "Answer" not in header:
            continue
        answer_at = header.index("Answer")
        blocks_at = header.index("Blocks") if "Blocks" in header else None
        ask_at = header.index("Ask") if "Ask" in header else None
        question_at = header.index("Question") if "Question" in header else None
        for _, row in rows:
            answer = row[answer_at] if answer_at < len(row) else ""
            blocks = row[blocks_at] if blocks_at is not None and blocks_at < len(row) else ""
            ask = row[ask_at] if ask_at is not None and ask_at < len(row) else "?"
            question = row[question_at] if question_at is not None and question_at < len(row) else ""
            open_ = answer in EMPTY_ANSWER
            assumed = not open_ and answer.startswith("⚠")
            found.append({
                "id": row[0] if row else "",
                "question": question,
                "ask": ask,
                "blocks": blocks,
                "answer": answer,
                "open": open_,
                "blocking": open_ and blocks.lower() != "later",
                "assumed": assumed,
                "unrecorded": not open_ and not assumed and not answer.startswith("✅"),
            })
    return found
