#!/usr/bin/env python3
"""A stand-in for the part of the Notion API that jtek.py uses. For tests and evals only.

It is written from the same reading of the Notion reference as the client, so a
test that passes here does not prove that the real Notion accepts the request.

    python3 tests/fake_notion.py serve <board.json>

serves the board saved in that file on the port named in it, and saves every change.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STATUSES = ["Backlog", "Todo", "In Progress", "Review", "Done", "Cancelled"]
SELECTS = ("Repo", "Kind", "Area", "Review", "Waiting")


def blocks_from_text(text: str) -> list[dict]:
    """Turn simple ticket text into blocks: `## ` headings, `- ` items, and paragraphs."""
    blocks = []
    for line in text.splitlines():
        if line.startswith("## "):
            blocks.append({"type": "heading_2", "text": line[3:]})
        elif re.match(r"^\s*-\s", line):
            blocks.append({"type": "bulleted_list_item", "text": re.sub(r"^\s*-\s*", "", line)})
        elif line.strip():
            blocks.append({"type": "paragraph", "text": line})
    return blocks


def squash(value: str) -> str:
    return value.replace("-", "").lower()


class FakeNotion:
    def __init__(self, token: str = "test-token", prefix: str = "T", path: Path | None = None):
        self.token, self.prefix, self.path = token, prefix, path
        self.database, self.source = str(uuid.uuid4()), str(uuid.uuid4())
        self.sources = 1
        self.pages: dict[str, dict] = {}
        self.comments: list[dict] = []
        self.requests: list[tuple[str, str]] = []
        self.failures: list[list] = []  # [method, path prefix, status code, times]
        self.can_comment = True
        self.page_size = 100
        self.missing: list[str] = []  # property names to leave out, to test the schema check
        self.port = 0
        self.server: ThreadingHTTPServer | None = None
        self.lock = threading.Lock()
        if path and path.exists():
            self.__dict__.update(json.loads(path.read_text()))

    # ---- what a test does to the board ----

    def add(self, title: str = "Ticket", status: str = "Todo", body: str | list | None = None,
            number: int | None = None, after: list[str] | None = None, **props: str) -> str:
        """Add a page and return its ticket id. `props` are Repo, Kind, Area, Review, Waiting, PR, Checks."""
        number = number or 1 + max([page["number"] for page in self.pages.values()], default=0)
        if body is None:
            body = "## Goal\nAdd the thing.\n## Done when\n- the thing works\n"
        page = {
            "id": str(uuid.uuid4()), "number": number, "title": title, "trash": False,
            "props": {"Status": status, "After": [self.by_id(dep)["id"] for dep in after or []],
                      "PR": "", "Checks": "", **{name: "" for name in SELECTS},
                      **{key.replace("_", " "): value for key, value in props.items()}},
            "blocks": blocks_from_text(body) if isinstance(body, str) else body,
        }
        self.pages[page["id"]] = page
        self.save()
        return self.ticket_id(page)

    def ticket_id(self, page: dict) -> str:
        return f"{self.prefix}-{page['number']}" if self.prefix else str(page["number"])

    def by_id(self, ticket_id: str) -> dict:
        return next(page for page in self.pages.values() if self.ticket_id(page) == ticket_id)

    def get(self, ticket_id: str, name: str) -> str:
        return self.by_id(ticket_id)["props"][name]

    def set(self, ticket_id: str, **props) -> None:
        self.by_id(ticket_id)["props"].update({key.replace("_", " "): value for key, value in props.items()})
        self.save()

    def comments_on(self, ticket_id: str) -> list[str]:
        page_id = squash(self.by_id(ticket_id)["id"])
        return [item["text"] for item in self.comments if item["page"] == page_id]

    def fail(self, method: str, prefix: str, code: int, times: int = 1) -> None:
        self.failures.append([method, prefix, code, times])

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def env(self) -> dict[str, str]:
        return {"JTEK_NOTION_API": self.url(), "NOTION_TOKEN": self.token}

    def save(self) -> None:
        if self.path:
            keep = ("token", "prefix", "database", "source", "pages", "comments", "port")
            self.path.write_text(json.dumps({key: getattr(self, key) for key in keep}, indent=2))

    # ---- the server ----

    def start(self) -> "FakeNotion":
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), self.handler())
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def render(self, page: dict) -> dict:
        props = page["props"]
        rich = lambda text: [{"type": "text", "text": {"content": text}, "plain_text": text}] if text else []
        option = lambda name: {"id": "x", "name": name, "color": "default"} if name else None
        out = {
            "Name": {"id": "title", "type": "title", "title": rich(page["title"])},
            "Ticket ID": {"type": "unique_id", "unique_id": {"prefix": self.prefix or None, "number": page["number"]}},
            "Status": {"type": "status", "status": option(props["Status"])},
            "After": {"type": "relation", "relation": [{"id": dep} for dep in props["After"]], "has_more": False},
            "PR": {"type": "url", "url": props["PR"] or None},
            "Checks": {"type": "rich_text", "rich_text": rich(props["Checks"])},
            **{name: {"type": "select", "select": option(props[name])} for name in SELECTS},
        }
        for name in self.missing:
            out.pop(name, None)
        return {
            "object": "page", "id": page["id"], "in_trash": page["trash"],
            "url": f"https://www.notion.so/{re.sub(r'[^A-Za-z0-9]+', '-', page['title'])}-{squash(page['id'])}",
            "parent": {"type": "data_source_id", "database_id": self.database,
                       "data_source_id": str(uuid.uuid4()) if page.get("foreign") else self.source},
            "properties": out,
        }

    def matches(self, page: dict, rule: dict) -> bool:
        if "and" in rule:
            return all(self.matches(page, item) for item in rule["and"])
        if "or" in rule:
            return any(self.matches(page, item) for item in rule["or"])
        name = rule["property"]
        if "unique_id" in rule:
            return page["number"] == rule["unique_id"]["equals"]
        for kind in ("status", "select"):
            if kind in rule:
                value = page["props"][name]
                if "equals" in rule[kind]:
                    return value == rule[kind]["equals"]
                if "does_not_equal" in rule[kind]:
                    return value != rule[kind]["does_not_equal"]
        raise ValueError(f"filter not supported: {rule}")

    def find(self, raw: str) -> dict | None:
        return next((page for page in self.pages.values() if squash(page["id"]) == squash(raw)), None)

    def answer(self, method: str, path: str, query: dict, body: dict) -> tuple[int, dict]:
        parts = path.strip("/").split("/")[1:]  # drop v1
        if method == "GET" and parts[:1] == ["databases"] and squash(parts[1]) == squash(self.database):
            return 200, {"object": "database", "id": self.database,
                         "data_sources": [{"id": self.source, "name": "Board"}] * self.sources}
        if method == "POST" and parts[:1] == ["data_sources"] and parts[2:] == ["query"]:
            if squash(parts[1]) != squash(self.source):
                return 404, {"message": "no such data source"}
            rule = body.get("filter")
            found = [page for page in self.pages.values()
                     if not page["trash"] and (not rule or self.matches(page, rule))]
            begin = int(body.get("start_cursor") or 0)
            size = min(int(body.get("page_size", 100)), self.page_size)
            more = begin + size < len(found)
            return 200, {"object": "list", "results": [self.render(page) for page in found[begin:begin + size]],
                         "has_more": more, "next_cursor": str(begin + size) if more else None}
        if parts[:1] == ["pages"] and len(parts) == 2:
            page = self.find(parts[1])
            if not page:
                return 404, {"message": "no such page"}
            if method == "PATCH":
                for name, value in body.get("properties", {}).items():
                    if name not in page["props"]:
                        return 400, {"message": f"{name} is not a property that can be written"}
                    if name == "PR":
                        page["props"][name] = value["url"] or ""
                        continue
                    kind = "status" if name == "Status" else "select"
                    chosen = (value[kind] or {}).get("name", "")
                    if name == "Status" and chosen not in STATUSES:
                        return 400, {"message": f"Status has no option {chosen!r}"}
                    page["props"][name] = chosen
                self.save()
            return 200, self.render(page)
        if method == "GET" and parts[:1] == ["blocks"] and parts[2:] == ["children"]:
            page = self.find(parts[1])
            if not page:
                return 404, {"message": "no such block"}
            begin = int(query.get("start_cursor", ["0"])[0])
            size = min(int(query.get("page_size", ["100"])[0]), self.page_size)
            more = begin + size < len(page["blocks"])
            results = [{"object": "block", "type": block["type"], "has_children": block.get("children", False),
                        block["type"]: {"rich_text": [{"plain_text": block.get("text", "")}]}}
                       for block in page["blocks"][begin:begin + size]]
            return 200, {"object": "list", "results": results, "has_more": more,
                         "next_cursor": str(begin + size) if more else None}
        if method == "POST" and parts == ["comments"]:
            if not self.can_comment:
                return 403, {"message": "Insufficient permissions for this endpoint."}
            texts = [part["text"]["content"] for part in body["rich_text"]]
            if len(texts) > 100 or any(len(text) > 2000 for text in texts):
                return 400, {"message": "rich_text is too long"}
            self.comments.append({"page": squash(body["parent"]["page_id"]), "text": "".join(texts)})
            self.save()
            return 200, {"object": "comment"}
        return 404, {"message": f"the fake has no {method} {path}"}

    def handler(self):
        board = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code: int, body: dict, headers: dict | None = None):
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(raw)

            def handle_any(self):
                url = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                with board.lock:
                    board.requests.append((self.command, url.path))
                    if self.headers.get("Authorization") != f"Bearer {board.token}":
                        return self.reply(401, {"message": "API token is invalid."})
                    if not self.headers.get("Notion-Version"):
                        return self.reply(400, {"message": "Notion-Version header is missing"})
                    for failure in board.failures:
                        if failure[0] == self.command and url.path.startswith(failure[1]) and failure[3] > 0:
                            failure[3] -= 1
                            return self.reply(failure[2], {"message": "injected failure"}, {"Retry-After": "0"})
                    try:
                        code, answer = board.answer(self.command, url.path, parse_qs(url.query), body)
                    except (KeyError, ValueError, TypeError, IndexError) as err:
                        code, answer = 400, {"message": f"validation error: {err}"}
                self.reply(code, answer)

            do_GET = do_POST = do_PATCH = handle_any

        return Handler


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "serve":
        sys.exit(__doc__)
    fake = FakeNotion(path=Path(sys.argv[2])).start()
    print(f"test board at {fake.url()}; stop with Ctrl-C", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        fake.stop()
