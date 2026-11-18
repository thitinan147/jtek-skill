"""A stand-in for the Notion board and for the agent that reads and writes it. For tests only.

jtek.py never talks to Notion. In a real run the agent reads a page with its Notion tool, saves it as a
ticket file, and writes back what a `board:` line says. This class does those three things from memory.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SELECTS = ("Repo", "Kind", "Area", "Review", "Waiting")
HEADER = (("repo", "Repo"), ("kind", "Kind"), ("area", "Area"), ("checks", "Checks"), ("waiting", "Waiting"), ("pr", "PR"))


class Board:
    def __init__(self, folder: Path, prefix: str = "T"):
        self.folder, self.prefix = folder, prefix
        self.pages: dict[str, dict] = {}
        self.comments: list[tuple[str, str]] = []

    def add(self, title: str = "Ticket", status: str = "Todo", body: str = "", number: int | None = None,
            after: list[str] | None = None, **props: str) -> str:
        number = number or 1 + max([page["number"] for page in self.pages.values()], default=0)
        ticket_id = f"{self.prefix}-{number}"
        self.pages[ticket_id] = {
            "number": number, "title": title, "body": body,
            "props": {"Status": status, "After": list(after or []), "PR": "", "Checks": "",
                      **{name: "" for name in SELECTS}, **props},
        }
        return ticket_id

    def set(self, ticket_id: str, **props) -> None:
        self.pages[ticket_id]["props"].update(props)

    def get(self, ticket_id: str, name: str) -> str:
        return self.pages[ticket_id]["props"][name]

    def comments_on(self, ticket_id: str) -> list[str]:
        return [text for owner, text in self.comments if owner == ticket_id]

    def open_after(self, ticket_id: str) -> list[str]:
        return [dep for dep in self.get(ticket_id, "After") if self.get(dep, "Status") != "Done"]

    def file(self, ticket_id: str) -> str:
        """The page, saved in the ticket format as the agent saves it."""
        page, props = self.pages[ticket_id], self.pages[ticket_id]["props"]
        head = [f"# {page['title']}", f"id: {ticket_id}", f"status: {props['Status']}"]
        head += [f"{key}: {props[name]}" for key, name in HEADER if props[name]]
        if props["Review"]:
            head.append(f"review: {props['Review']}")
        if self.open_after(ticket_id):
            head.append("after: " + ", ".join(self.open_after(ticket_id)))
        path = self.folder / f"page-{ticket_id}.md"
        path.write_text("\n".join(head) + "\n\n" + page["body"])
        return str(path)

    def rows_file(self) -> str:
        rows = [{"id": ticket_id, "title": page["title"], "status": page["props"]["Status"],
                 "repo": page["props"]["Repo"], "waiting": page["props"]["Waiting"], "pr": page["props"]["PR"],
                 "after": self.open_after(ticket_id)} for ticket_id, page in self.pages.items()]
        path = self.folder / "board.json"
        path.write_text(json.dumps(rows))
        return str(path)

    def apply(self, ticket_id: str, output: str) -> None:
        """Write what each `board:` line in the output says, as the agent does with its Notion tool."""
        for line in output.splitlines():
            found = re.search(r"\bboard: (.+)$", line)
            if not found or found.group(1).strip() == "-":
                continue
            owner = line.split("\t")[0] if "\t" in line else ticket_id
            for part in found.group(1).split("\t")[0].split(";"):
                key, _, value = part.strip().partition("=")
                if key == "comment":
                    self.comments.append((owner, output))
                elif key:
                    self.set(owner, **{key: value})
