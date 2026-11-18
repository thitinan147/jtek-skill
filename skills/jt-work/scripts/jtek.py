#!/usr/bin/env python3
"""jtek inner loop: one ticket, one session, one worktree.

The board is a Notion database. Claims, logs, and results live under the
repository's common git directory, so every worktree sees the same claims and
no tracked file is shared between sessions.
Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STATUSES = ["Backlog", "Todo", "In Progress", "Review", "Done", "Cancelled"]
VERDICTS = ["PASS", "PASS+NOTES", "FAIL"]
WAITING = ["input", "approval"]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CONFIG = "jtek.json"
MAX_FAILED_RUNS = 3
MAX_EVIDENCE_LINES = 40
DEFAULT_TIMEOUT = 1800
# Files a human should look at first when a ticket touches them.
SENSITIVE = [
    CONFIG, ".jtek/*", ".github/*", ".gitlab-ci.yml", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "poetry.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
]

class Refuse(Exception):
    """A rule is not met. The message says what to do next."""


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise Refuse(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def common_dir() -> Path:
    out = git("rev-parse", "--git-common-dir")
    return (Path.cwd() / out).resolve()


def state_dir() -> Path:
    override = os.environ.get("JTEK_STATE")
    return Path(override).expanduser().resolve() if override else common_dir() / "jtek"


def main_root() -> Path:
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree "):])
    raise Refuse("no main worktree found")


def base_branch() -> str:
    override = os.environ.get("JTEK_BASE")
    if override:
        return override
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if head.startswith("origin/"):
        return head[len("origin/"):]
    for name in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False):
            return name
    raise Refuse("cannot find the base branch; set JTEK_BASE")


def load_config(base: str) -> dict:
    """The config comes from the base branch, never from the ticket or the worktree."""
    proc = subprocess.run(["git", "show", f"{base}:{CONFIG}"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise Refuse(f"{CONFIG} is not committed on {base}; run `jtek.py init`, fill it in, and have the human merge it")
    try:
        config = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise Refuse(f"{CONFIG} on {base} is not valid JSON: {err}") from err
    if not isinstance(config, dict):
        raise Refuse(f"{CONFIG} on {base} must be a JSON object")
    return config


def load_checks(base: str) -> dict[str, str]:
    checks = load_config(base).get("checks", {})
    if not isinstance(checks, dict) or not checks:
        raise Refuse(f"{CONFIG} on {base} declares no checks; a ticket needs at least one real check")
    for name, cmd in checks.items():
        if not isinstance(cmd, str) or not cmd.strip():
            raise Refuse(f"check `{name}` in {CONFIG} has no command")
    return checks


# ---- ticket text -----------------------------------------------------------

def parse_ticket(text: str) -> dict:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    title, current = "", None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            match = re.match(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$", line)
            if match:
                fields[match.group(1).strip().lower()] = match.group(2).strip()
    return {"title": title, "fields": fields, "sections": sections}


def validate_ticket(ticket: dict, checks: dict[str, str]) -> list[str]:
    sections = ticket["sections"]
    if not any(line.strip() for line in sections.get("goal", [])):
        raise Refuse("ticket has no `## Goal`")
    done = [line for line in sections.get("done when", []) if re.match(r"^\s*-\s*\S", line)]
    if not done:
        raise Refuse("ticket has no item under `## Done when`")
    wanted = [name.strip() for name in ticket["fields"].get("checks", "").split(",") if name.strip()]
    unknown = [name for name in wanted if name not in checks]
    if unknown:
        raise Refuse(
            f"ticket names checks that {CONFIG} does not declare: {', '.join(unknown)}. "
            "A ticket may only name a declared check; it cannot add a command"
        )
    return wanted or list(checks)


# ---- per-ticket state ------------------------------------------------------

def check_id(ticket_id: str) -> str:
    if not ID_RE.match(ticket_id or ""):
        raise Refuse(f"bad ticket id `{ticket_id}`; use letters, digits, `.`, `_`, `-`")
    return ticket_id


def work_dir(ticket_id: str) -> Path:
    return state_dir() / "work" / check_id(ticket_id)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_meta(ticket_id: str) -> dict:
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if not meta:
        raise Refuse(f"{ticket_id} is not started; run `jtek.py start {ticket_id}`")
    return meta


def head_state(worktree: Path) -> tuple[str, str]:
    """Return the commit and the uncommitted files. Untracked files count: a new file that was
    never added would pass the checks here and be missing from the pull request."""
    sha = git("rev-parse", "HEAD", cwd=worktree)
    return sha, git("status", "--porcelain", cwd=worktree)


CLAIMED = (
    "{id} is already claimed and its session has not ended with a result. "
    "Pick another ticket. If that session died, the human runs start with --resume"
)
def patch_id(worktree: Path, base: str) -> str:
    """Identify the change by its content, so a rebase that changes nothing keeps its verdict."""
    diff = subprocess.run(["git", "diff", f"{base}...HEAD"], cwd=worktree, capture_output=True, text=True)
    proc = subprocess.run(["git", "patch-id", "--stable"], input=diff.stdout, capture_output=True, text=True)
    return proc.stdout.split()[0] if proc.stdout.split() else ""


DIRTY_HINT = "commit them, or add build output to .gitignore"


def done_when_items(work: Path) -> list[str]:
    ticket = parse_ticket((work / "ticket.md").read_text())
    return [m.group(1).strip() for line in ticket["sections"].get("done when", [])
            if (m := re.match(r"^\s*-\s*(\S.*)$", line))]


def attention(meta: dict) -> str:
    """Name what the human should look at before the diff: files that decide whether checks pass."""
    worktree = Path(meta["worktree"])
    if not worktree.is_dir():
        return "-"
    span = f"{meta['base']}...HEAD"
    changed = git("diff", "--name-only", span, cwd=worktree, check=False).splitlines()
    deleted = git("diff", "--name-only", "--diff-filter=D", span, cwd=worktree, check=False).splitlines()
    try:
        config = load_config(meta["base"])
    except Refuse:
        config = {}
    commands = dict(config.get("checks", {})) if isinstance(config.get("checks"), dict) else {}
    if config.get("setup"):
        commands["setup"] = config["setup"]
    run_by: dict[str, str] = {}
    for name, command in commands.items():
        try:
            tokens = shlex.split(str(command))
        except ValueError:
            continue
        for token in tokens:
            run_by.setdefault(token.removeprefix("./"), name)
    watch = SENSITIVE + [w for w in config.get("watch", []) if isinstance(w, str)]
    removed: dict[str, int] = {}
    for line in git("diff", "--numstat", span, cwd=worktree, check=False).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit():
            removed[parts[2]] = int(parts[1])
    notes = []
    for path in changed:
        if path in run_by:
            notes.append(f"{path} (run by `{run_by[path]}`)")
        elif any(fnmatch.fnmatch(path, pattern) for pattern in watch):
            notes.append(path)
        elif path in deleted and "test" in path.lower():
            notes.append(f"{path} (test deleted)")
        elif "test" in path.lower() and removed.get(path):
            # Adding tests is normal. Removing or rewriting lines of an existing test is how a check gets weakened.
            notes.append(f"{path} ({removed[path]} test lines removed or changed)")
    return ", ".join(notes) or "-"


def write_result(ticket_id: str, outcome: str, status: str, note: str = "", waiting: str = "") -> str:
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    checks = read_json(work / "checks.json")
    verdict = read_json(work / "verdict.json")
    check_line = " ".join(f"{r['name']}={r['status']}" for r in checks.get("results", [])) or "not run"
    if checks.get("sha"):
        check_line += f" @{checks['sha'][:7]}"
    evidence = "-"
    if (work / "evidence.md").exists():
        text = (work / "evidence.md").read_text()
        seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
        not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
        evidence = f"{work / 'evidence.md'} ({seen} seen, {not_run} not run)"
    attached = sorted(p.name for p in (work / "evidence").glob("*")) if (work / "evidence").is_dir() else []
    if attached:
        evidence += f" (+{len(attached)} attached in {work / 'evidence'})"
    verdict_line = "none" if meta.get("review") else "waived by the ticket"
    if verdict:
        verdict_line = f"{verdict['verdict']} by {verdict['by']} @{verdict['sha'][:7]}"
    lines = [
        "jtek-result",
        f"id: {ticket_id}",
        f"status: {status}",
        f"outcome: {outcome}",
        f"waiting: {waiting or '-'}",
        f"checks: {check_line}",
        f"verdict: {verdict_line}",
        f"pr: {meta.get('pr') or '-'}",
        f"ci: {meta.get('ci') or '-'}",
        f"evidence: {evidence}",
        f"attention: {attention(meta)}",
        f"branch: {meta['branch']}",
        f"source: {meta['source']}",
        f"note: {note or '-'}",
    ]
    text = "\n".join(lines) + "\n"
    (work / "result.md").write_text(text)
    return text


# ---- the board (Notion) -----------------------------------------------------
# Every request to Notion is made in this section.

NOTION_API = "https://api.notion.com"
NOTION_VERSION = "2026-03-11"
TOKEN_ENV = "NOTION_TOKEN"
# field -> (property name on the board, property type)
PROPS = {
    "id": ("Ticket ID", "unique_id"), "status": ("Status", "status"), "repo": ("Repo", "select"),
    "kind": ("Kind", "select"), "area": ("Area", "select"), "after": ("After", "relation"),
    "review": ("Review", "select"), "waiting": ("Waiting", "select"), "pr": ("PR", "url"),
    "checks": ("Checks", "rich_text"),
}
LIST_BLOCKS = ("bulleted_list_item", "numbered_list_item", "to_do")
TEXT_BLOCKS = ("paragraph", "quote", "callout", "code")


def api_base() -> str:
    override = os.environ.get("JTEK_NOTION_API", "").rstrip("/")
    if not override:
        return NOTION_API
    parsed = urllib.parse.urlparse(override)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        # The token goes to this address, so it may only be a test board on this machine.
        raise Refuse("JTEK_NOTION_API is for tests and may only point at this machine; unset it")
    return override


def notion(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise Refuse(f"{TOKEN_ENV} is not set; the board is in Notion, and jtek.py needs an integration token to read it")
    base = api_base()
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}
    for attempt in range(4):
        request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        try:
            # The address is Notion's, or an http(s) address on this machine: api_base() refuses anything else.
            with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 3:
                wait = err.headers.get("Retry-After", "1")
                time.sleep(min(int(wait) if wait.isdigit() else 1, 30))
                continue
            try:
                message = json.loads(err.read()).get("message", "")
            except ValueError:
                message = ""
            hint = {
                401: f"Check {TOKEN_ENV}",
                403: "The integration lacks a capability: read content, update content, or insert comments",
                404: "Share the board database with the integration",
            }.get(err.code, "")
            raise Refuse(f"Notion refused {method} {path.split('?')[0]} ({err.code}): {message}"
                         + (f". {hint}" if hint else "")) from None
        except (OSError, ValueError) as err:
            raise Refuse(f"cannot reach Notion at {base}: {err}") from None
    raise Refuse("Notion kept answering 429; try again later")


def hex_id(ref: str) -> str:
    """The 32 hex digits of a Notion id, from a bare id or from a link. Empty when there is none."""
    tail = urllib.parse.urlparse(ref).path.rstrip("/").rsplit("/", 1)[-1] if "/" in ref else ref
    match = re.search(r"([0-9a-f]{32})$", tail.replace("-", "").lower())
    return match.group(1) if match else ""


def board(base: str) -> str:
    """Return the id of the board's one data source. The database is named in jtek.json on the base branch."""
    database = hex_id(str(load_config(base).get("notion") or ""))
    if not database:
        raise Refuse(f"{CONFIG} on {base} has no `notion`; set it to the id or the link of the board database")
    cache = state_dir() / "board.json"
    cached = read_json(cache)
    if cached.get("database") == database and cached.get("api") == api_base():
        return cached["source"]
    sources = notion("GET", f"/v1/databases/{database}").get("data_sources") or []
    if len(sources) != 1:
        raise Refuse(f"the board database must have exactly one data source, and it has {len(sources)}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    write_json(cache, {"database": database, "api": api_base(), "source": sources[0]["id"]})
    return sources[0]["id"]


def plain(rich: list | None) -> str:
    """Text of a rich-text value on one line, so that page text can never start a new header line."""
    return " ".join("".join(part.get("plain_text", "") for part in rich or []).split())


def prop(page: dict, key: str):
    name, kind = PROPS[key]
    value = page.get("properties", {}).get(name, {}).get(kind)
    if kind == "unique_id":
        value = value or {}
        number = value.get("number")
        return "" if number is None else (f"{value['prefix']}-{number}" if value.get("prefix") else str(number))
    if kind in ("status", "select"):
        return " ".join(str((value or {}).get("name", "")).split())
    if kind == "relation":
        return [item["id"] for item in value or []]
    if kind == "rich_text":
        return plain(value)
    return value or ""


def page_title(page: dict) -> str:
    for value in page.get("properties", {}).values():
        if value.get("type") == "title":
            return plain(value.get("title"))
    return ""


def check_schema(page: dict) -> None:
    properties = page.get("properties", {})
    missing = [f"`{name}` ({kind})" for name, kind in PROPS.values() if properties.get(name, {}).get("type") != kind]
    if missing:
        raise Refuse("the board is missing properties, or they have another type: " + ", ".join(missing)
                     + ". The layout is in references/notion.md of the jt-work skill")


def find_page(ref: str, source: str) -> dict:
    """Find a ticket by its id (`T-12`), by a page link, or by a page id. The page must be on the board."""
    known = read_json(work_dir(ref) / "meta.json").get("page", "") if ID_RE.match(ref) else ""
    page_id = known or hex_id(ref)
    if page_id:
        page = notion("GET", f"/v1/pages/{page_id}")
        if hex_id(str(page.get("parent", {}).get("data_source_id", ""))) != hex_id(source):
            raise Refuse(f"{ref} is not a page of the board database named in {CONFIG}")
    else:
        match = re.match(r"^(?:.+-)?(\d+)$", ref)
        if not match:
            raise Refuse(f"`{ref}` is not a ticket id such as T-12, and not a Notion page link")
        found = notion("POST", f"/v1/data_sources/{source}/query", {
            "filter": {"property": PROPS["id"][0], "unique_id": {"equals": int(match.group(1))}}, "page_size": 10,
        }).get("results", [])
        pages = [item for item in found if prop(item, "id") == ref]
        if not pages:
            raise Refuse(f"no ticket `{ref}` on the board")
        page = pages[0]
    if page.get("in_trash") or page.get("archived"):
        raise Refuse(f"{ref} is in the trash in Notion")
    return page


def page_body(page_id: str) -> list[str]:
    """The page body as ticket text. Anything under `Done when` that is not a plain list item is refused,
    because that list decides what the evidence must show."""
    lines: list[str] = []
    section, cursor = "", ""
    while True:
        query = f"/v1/blocks/{page_id}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        data = notion("GET", query)
        for block in data.get("results", []):
            kind = block.get("type", "")
            text = plain(block.get(kind, {}).get("rich_text"))
            if kind.startswith("heading_"):
                section = text.lower()
                lines += ["", f"## {text}", ""]
                if block.get("has_children"):
                    # A toggle heading keeps its content inside it, and that content is not read here.
                    if section == "done when":
                        raise Refuse("the `Done when` heading on the page is a toggle, so its items are hidden inside it. "
                                     "Make it a plain heading with the items below it")
                    lines.append("[this heading is a toggle, and what is inside it is not copied here; open the page to see it]")
                continue
            if kind == "divider" or (kind == "paragraph" and not text):
                lines.append("")
                continue
            if not section:
                # Text above the first heading goes in a section, so it cannot be read as a ticket field.
                section = "notes"
                lines += ["", "## Notes", ""]
            nested = bool(block.get("has_children"))
            if section == "done when" and (kind not in LIST_BLOCKS or nested):
                what = "an item with nested content" if kind in LIST_BLOCKS else f"a {kind} block"
                raise Refuse(f"`Done when` on the page has {what}. Make every outcome one top-level list item, "
                             "because each item must be answered in the evidence")
            if kind in LIST_BLOCKS:
                lines.append(f"- {text}")
            elif kind in TEXT_BLOCKS:
                lines.append(text)
            else:
                lines.append(f"[a {kind} block is not copied here; open the page to see it]")
            if nested:
                lines.append("  [nested content is not copied here; open the page to see it]")
        if not data.get("has_more"):
            return lines
        cursor = data.get("next_cursor") or ""


def waits_on(page: dict) -> list[tuple[str, str]]:
    """The tickets in After, as (id, status). They may belong to any repository on the board."""
    if page.get("properties", {}).get(PROPS["after"][0], {}).get("has_more"):
        raise Refuse("After lists more than 25 tickets; split the work")
    found = []
    for page_id in prop(page, "after"):
        other = notion("GET", f"/v1/pages/{hex_id(page_id)}")
        found.append((prop(other, "id") or page_id, prop(other, "status")))
    return found


def ticket_text(page: dict, after: list[tuple[str, str]]) -> str:
    """Header lines come from properties only. The body comes after the first heading."""
    head = [f"# {page_title(page)}", f"id: {prop(page, 'id')}", f"status: {prop(page, 'status')}"]
    head += [f"{key}: {prop(page, key)}" for key in ("repo", "kind", "area", "checks") if prop(page, key)]
    if prop(page, "review").lower() == "human":
        head.append("review: human")
    if after:
        head.append("after: " + ", ".join(ticket_id for ticket_id, _ in after))
    return "\n".join(head + page_body(hex_id(page["id"]))) + "\n"


def set_page(page_id: str, **fields: str | None) -> None:
    """Write Status, Waiting, or PR on a page. None clears Waiting or PR."""
    properties: dict = {}
    for key, value in fields.items():
        name, kind = PROPS[key]
        if kind == "url":
            properties[name] = {"url": value or None}
        else:
            properties[name] = {kind: {"name": value} if value else None}
    notion("PATCH", f"/v1/pages/{page_id}", {"properties": properties})


def add_comment(page_id: str, text: str) -> None:
    parts = [text[i:i + 2000] for i in range(0, len(text), 2000)][:100]
    notion("POST", "/v1/comments", {"parent": {"page_id": page_id},
                                    "rich_text": [{"text": {"content": part}} for part in parts]})


def board_pages(source: str, query_filter: dict | None = None) -> list[dict]:
    pages: list[dict] = []
    cursor = ""
    while True:
        body: dict = {"page_size": 100}
        if query_filter:
            body["filter"] = query_filter
        if cursor:
            body["start_cursor"] = cursor
        data = notion("POST", f"/v1/data_sources/{source}/query", body)
        pages += data.get("results", [])
        if not data.get("has_more"):
            return pages
        cursor = data.get("next_cursor") or ""


def push_result(ticket_id: str) -> None:
    """Put the saved result on the board. Safe to run again: the same result is commented once."""
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    text = (work / "result.md").read_text()
    lines = dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)
    outcome = lines.get("outcome", "")
    if outcome == "needs-review":
        return  # nothing changes for the human until the verdict is in
    if outcome == "review":
        status = prop(notion("GET", f"/v1/pages/{meta['page']}"), "status")
        if status not in ("In Progress", "Review"):
            # The human moved the ticket while the session worked. Their choice stays.
            raise Refuse(f"the page is `{status}`, not In Progress, so it was left as it is")
        set_page(meta["page"], status="Review", waiting=None, pr=meta.get("pr") or None)
        if (work / "evidence.md").exists():
            text += "\nevidence:\n" + (work / "evidence.md").read_text()
    else:
        set_page(meta["page"], waiting=lines.get("waiting", ""))
    digest = hashlib.sha256(text.encode()).hexdigest()
    marker = work / "pushed"
    if not marker.exists() or marker.read_text().strip() != digest:
        add_comment(meta["page"], text)
        marker.write_text(digest + "\n")


def conclude(ticket_id: str, text: str) -> None:
    """Print the result, then put it on the board. The result file is already saved."""
    print(text, end="")
    try:
        push_result(ticket_id)
    except Refuse as err:
        raise Refuse(f"the result is saved, but the board was not updated: {err}\n"
                     f"Run `jtek.py push {ticket_id}` when Notion can be reached") from None


# ---- commands --------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    path = Path(git("rev-parse", "--show-toplevel")) / CONFIG
    if path.exists():
        raise Refuse(f"{path} already exists")
    write_json(path, {"notion": "", "setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}})
    print(f"wrote {path}")
    print("`notion` is the id or the link of the board database.")
    print("`setup` installs dependencies in a new worktree, for example `npm ci`. Leave it empty when nothing is needed.")
    print("Fill in one command per check (no shell operators; put a pipeline in a script).")
    print("`secrets` is a secret scanner and `audit` a dependency audit, when the project has them.")
    print("Delete a check the project does not have. The human commits this file on the base branch.")


def cmd_start(args: argparse.Namespace) -> None:
    base = base_branch()
    declared = load_checks(base)
    page = find_page(args.ref, board(base))
    check_schema(page)
    page_id = hex_id(page["id"])
    ticket_id = check_id(prop(page, "id"))
    after = waits_on(page)
    text = ticket_text(page, after)
    ticket = parse_ticket(text)
    selected = validate_ticket(ticket, declared)
    wanted_repo = prop(page, "repo")
    this_repo = str(load_config(base).get("name") or main_root().name)
    if wanted_repo and wanted_repo != this_repo:
        raise Refuse(
            f"{ticket_id} is for the repository `{wanted_repo}`, and this one is `{this_repo}`. "
            "Start the session in that repository"
        )
    status = prop(page, "status")
    waiting = prop(page, "waiting")
    work = work_dir(ticket_id)
    # A claim is parked once its session ended with a result. A parked claim can be picked up again.
    parked = (work / "result.md").exists()

    if args.resume or parked:
        meta = load_meta(ticket_id)
        if not Path(meta["worktree"]).is_dir():
            raise Refuse(f"worktree for {ticket_id} is gone; nothing to resume")
        if status not in ("Todo", "In Progress"):
            raise Refuse(f"{ticket_id} is `{status}`; only a ticket in Todo or In Progress can resume")
        if waiting and status != "Todo":
            raise Refuse(f"{ticket_id} is still waiting for {waiting}. The human answers on the page and clears Waiting")
        set_page(page_id, status="In Progress", waiting=None)
        (work / "result.md").unlink(missing_ok=True)
        (work / "pushed").unlink(missing_ok=True)
        checks_path = work / "checks.json"
        if checks_path.exists():
            write_json(checks_path, {**read_json(checks_path), "failed_runs": 0})
        resumed = True
    else:
        resumed = False
        if work.exists():
            raise Refuse(CLAIMED.format(id=ticket_id))
        if status != "Todo":
            raise Refuse(f"{ticket_id} is `{status or 'unset'}`, not Todo; the human releases a ticket by setting Status to Todo")
        for dep, dep_status in after:
            if dep_status != "Done":
                raise Refuse(f"{ticket_id} comes after {dep}, which is `{dep_status or 'unset'}`, not Done")
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            work.mkdir()  # atomic claim: the second session to try loses
        except FileExistsError:
            raise Refuse(CLAIMED.format(id=ticket_id)) from None
        root = main_root()
        worktree = root.parent / f"{root.name}.jtek" / ticket_id
        branch = f"jtek/{ticket_id}"
        try:
            worktree.parent.mkdir(parents=True, exist_ok=True)
            git("worktree", "add", "-b", branch, str(worktree), base)
        except Refuse:
            work.rmdir()
            raise
        logs = state_dir() / "baseline" / ticket_id

        def undo() -> None:
            git("worktree", "remove", "--force", str(worktree))
            git("branch", "-D", branch)
            work.rmdir()

        def give_back(reason: str, log: Path) -> Refuse:
            undo()
            return Refuse(f"{reason}, so {ticket_id} was not started and is still Todo.\nlog: {log}\n{log_tail(log)}")

        setup = load_config(base).get("setup", "")
        if isinstance(setup, str) and setup.strip():
            # A new worktree has no installed dependencies. Install them before anything runs.
            if not run_command(setup, worktree, logs / "setup.log"):
                raise give_back(f"the setup command from {CONFIG} failed in the new worktree", logs / "setup.log")
        if not args.no_baseline:
            # A check that is already red on the base is not this ticket's to fix. Find out before any edit.
            # One green run per base commit and command set is enough, so parallel tickets do not repeat it.
            base_sha = git("rev-parse", base)
            key = hashlib.sha256(json.dumps([base_sha, [(n, declared[n]) for n in selected]]).encode()).hexdigest()
            green = state_dir() / "baseline" / "green" / key
            if not green.exists():
                _, failed = run_checks(worktree, selected, declared, logs)
                if failed:
                    raise give_back(
                        f"check `{failed}` fails on {base} before any change (fix {base} first, or pass --no-baseline)",
                        logs / f"{failed}.log",
                    )
                green.parent.mkdir(parents=True, exist_ok=True)
                green.write_text(base_sha + "\n")
        try:
            # Last, so that the board says In Progress only when the worktree is ready.
            set_page(page_id, status="In Progress", waiting=None)
        except Refuse:
            undo()
            raise
        source = page.get("url") or page_id
        if api_base() != NOTION_API:
            source += f" (test board at {api_base()})"
        meta = {
            "id": ticket_id, "page": page_id, "source": source,
            "base": base, "worktree": str(worktree), "branch": branch, "pr": "",
        }

    meta["checks"] = selected
    # Every change needs a verdict from a session that did not write it. The human may waive that per ticket.
    meta["review"] = ticket["fields"].get("review", "").lower() != "human"
    write_json(work / "meta.json", meta)
    (work / "ticket.md").write_text(text)
    print("jtek start: resumed" if resumed else "jtek start: allowed")
    print(f"id: {ticket_id}")
    print(f"worktree: {meta['worktree']}")
    print(f"branch: {meta['branch']}")
    print(f"base: {meta['base']}")
    print(f"ticket: {work / 'ticket.md'}  (a copy taken now; read this file)")
    print(f"checks: {', '.join(selected)}")
    print(f"review: {'a verdict from a session that did not write the code is required' if meta['review'] else 'human only (the ticket says `review: human`)'}")
    if resumed and (work / "review.md").exists():
        print(f"review notes: {work / 'review.md'}")
    kind = ticket["fields"].get("kind", "") or "not set; decide from the Goal"
    print(f"kind: {kind}")
    print("next: follow the playbook for this kind, step by step. Work only inside the worktree")


def run_command(command: str, worktree: Path, log: Path) -> bool:
    """Run one declared command without a shell. The ticket id is in the environment so that
    a command can pick its own port or data folder when several worktrees run at once."""
    env = {**os.environ, "JTEK_TICKET": worktree.name, "JTEK_WORKTREE": str(worktree)}
    env.pop(TOKEN_ENV, None)  # a check runs code from the worktree, and that code has no use for the board
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "w") as handle:
            proc = subprocess.run(shlex.split(command), cwd=worktree, stdout=handle,
                                  stderr=subprocess.STDOUT, timeout=DEFAULT_TIMEOUT, env=env)
        return proc.returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        with open(log, "a") as handle:
            handle.write(f"\njtek: {err}\n")
        return False


def run_checks(worktree: Path, names: list[str], declared: dict[str, str], logs: Path) -> tuple[list[dict], str | None]:
    """Run checks in order and stop at the first failure. Return the results and the failed name."""
    results: list[dict] = []
    for name in names:
        started = time.time()
        ok = run_command(declared[name], worktree, logs / f"{name}.log")
        results.append({"name": name, "status": "pass" if ok else "fail", "seconds": round(time.time() - started, 1)})
        if not ok:
            return results, name
    return results, None


def log_tail(log: Path) -> str:
    return "\n".join(log.read_text(errors="replace").splitlines()[-20:])


def cmd_check(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    declared = load_checks(meta["base"])
    missing = [name for name in meta["checks"] if name not in declared]
    if missing:
        raise Refuse(f"{CONFIG} on {meta['base']} no longer declares: {', '.join(missing)}")
    sha, dirty = head_state(worktree)
    previous = read_json(work / "checks.json")
    logs = work / "logs"
    results, failed = run_checks(worktree, meta["checks"], declared, logs)
    failed_runs = previous.get("failed_runs", 0) + 1 if failed else 0
    write_json(work / "checks.json", {"sha": sha, "dirty": bool(dirty), "results": results, "failed_runs": failed_runs})
    for result in results:
        print(f"{result['name']}: {result['status']} ({result['seconds']}s)")
    if failed:
        log = logs / f"{failed}.log"
        print(f"log: {log}")
        print(log_tail(log))
        if failed_runs >= MAX_FAILED_RUNS:
            print(f"next: {failed_runs} failed runs; stop with `jtek.py stop {args.id} --waiting input --note ...`")
        else:
            print(f"next: fix the cause, commit, run check again ({failed_runs}/{MAX_FAILED_RUNS} failed runs)")
        sys.exit(1)
    if dirty:
        print(f"next: all checks pass, but these files are not committed; {DIRTY_HINT} and run check again")
        print(dirty)
    else:
        print(f"next: all checks pass at {sha[:7]}; go on with the next step of your playbook. "
              "Run check again after any new commit")


def cmd_verdict(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    sha, dirty = head_state(Path(meta["worktree"]))
    if dirty:
        raise Refuse(f"a verdict is for a commit, and these files are not committed; {DIRTY_HINT}\n{dirty}")
    if args.verdict != "PASS" and not args.notes_file:
        raise Refuse(f"{args.verdict} needs --notes-file with the findings")
    if args.notes_file:
        (work / "review.md").write_text(Path(args.notes_file).read_text())
    write_json(work / "verdict.json", {
        "verdict": args.verdict, "by": args.by, "sha": sha,
        "patch": patch_id(Path(meta["worktree"]), meta["base"]),
    })
    print(f"verdict: {args.verdict} by {args.by} @{sha[:7]}")


def cmd_finish(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if args.pr:
        meta["pr"] = args.pr
        write_json(work / "meta.json", meta)
    sha, dirty = head_state(Path(meta["worktree"]))
    checks = read_json(work / "checks.json")
    passed = checks.get("results") and all(r["status"] == "pass" for r in checks["results"])
    ran_all = [r["name"] for r in checks.get("results", [])] == meta["checks"]
    if dirty:
        raise Refuse(f"these files are not committed; {DIRTY_HINT} and run `jtek.py check {args.id}`\n{dirty}")
    if checks.get("dirty") or checks.get("sha") != sha or not passed or not ran_all:
        raise Refuse(f"checks have not passed on the current commit {sha[:7]}; run `jtek.py check {args.id}`")
    if args.evidence_file:
        text = Path(args.evidence_file).read_text()
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise Refuse("the evidence file is empty")
        if len(lines) > MAX_EVIDENCE_LINES:
            raise Refuse(
                f"the evidence has {len(lines)} lines; the human reads it before the diff, so keep it to "
                f"{MAX_EVIDENCE_LINES}. Say what you ran and saw for each `Done when` item, and cut the rest"
            )
        items = done_when_items(work)
        missing = [
            f"{n}. {item}" for n, item in enumerate(items, 1)
            if not re.search(rf"^\s*{n}\.\s*(seen|not run):", text, re.M)
        ]
        if missing:
            raise Refuse(
                "the evidence must account for every `Done when` item. Start one line per item with its number and "
                "`seen:` (the command or steps, and the result) or `not run:` (the reason). Missing:\n" + "\n".join(missing)
            )
        (work / "evidence.md").write_text(text)
    for item in args.attach or []:
        source = Path(item)
        if not source.is_file():
            raise Refuse(f"cannot attach {item}: not a file")
        (work / "evidence").mkdir(exist_ok=True)
        (work / "evidence" / source.name).write_bytes(source.read_bytes())
    if not (work / "evidence.md").exists():
        raise Refuse(
            "no evidence yet; the human reviews the evidence before the diff. Write what you ran and saw for each "
            "`Done when` item to a file and pass --evidence-file <file>. Use the same text as the pull request body"
        )
    if args.no_pr:
        pr_note = f" No pull request: the branch {meta['branch']} is local."
    elif not meta["pr"]:
        raise Refuse(
            "no PR yet; open it (ready, not draft) and pass --pr <url>. "
            "Only when this repository has no forge to open one on, pass --no-pr"
        )
    else:
        state, head, ci = pr_info(meta["pr"])
        if state != "unknown" and (state != "OPEN" or head != sha):
            raise Refuse(f"{meta['pr']} is {state} at {head[:7]}, not open at the current commit {sha[:7]}; push the branch")
        if ci == "fail":
            raise Refuse(f"CI is failing on {meta['pr']}; a pull request with red CI is not ready for the human. Fix it first")
        meta["ci"] = ci
        write_json(work / "meta.json", meta)
        pr_note = "" if state == "OPEN" else " The PR link was not verified because gh could not read it."
    verdict = read_json(work / "verdict.json")
    if verdict.get("patch") != patch_id(Path(meta["worktree"]), meta["base"]):
        verdict = {}  # a verdict belongs to one change; new content needs a new verdict
    needs_verdict = meta.get("review")
    if not needs_verdict and attention(meta) != "-":
        # The human waived the review for a small ticket, but this one touches files that decide whether checks pass.
        needs_verdict = True
        pr_note += " `review: human` is ignored because the change touches the files on the attention line."
    if needs_verdict and not verdict:
        conclude(args.id, write_result(args.id, "needs-review", "In Progress",
                                       note="start a session that did not write this code and run jt-review for this id." + pr_note))
        return
    if verdict.get("verdict") == "FAIL":
        raise Refuse(f"verdict is FAIL; read {work / 'review.md'}, fix what reproduces, commit, check, and get a new verdict")
    conclude(args.id, write_result(args.id, "review", "Review",
                                   note="the human reviews and merges; jtek never merges." + pr_note))


def cmd_stop(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    worktree = Path(meta["worktree"])
    if worktree.is_dir():
        _, dirty = head_state(worktree)
        if dirty:
            raise Refuse(
                "these files are not committed, and the next session would not know what they are. "
                f"Commit them as `wip: <what is unfinished>`, or add build output to .gitignore\n{dirty}"
            )
    conclude(args.id, write_result(args.id, "needs-human", "In Progress", note=args.note, waiting=args.waiting))


def cmd_result(args: argparse.Namespace) -> None:
    path = work_dir(args.id) / "result.md"
    if not path.exists():
        raise Refuse(f"{args.id} has no result yet")
    print(path.read_text(), end="")


def cmd_show(args: argparse.Namespace) -> None:
    """Everything a reviewer needs, without the author's chat."""
    meta = load_meta(args.id)
    print(f"ticket: {work_dir(args.id) / 'ticket.md'}")
    print(f"worktree: {meta['worktree']}")
    print(f"diff: git -C {shlex.quote(meta['worktree'])} diff {meta['base']}...HEAD")
    try:
        declared = load_checks(meta["base"])
    except Refuse:
        declared = {}
    for name in meta["checks"]:
        print(f"check {name}: {declared.get(name, '(no longer declared)')}")
    print(f"pr: {meta.get('pr') or '-'}")


CI_QUERY = (
    '.state + " " + .headRefOid + " " + ([.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] '
    '| if length == 0 then "none" '
    'elif any(.[]; . == "FAILURE" or . == "ERROR" or . == "TIMED_OUT" or . == "CANCELLED" or . == "ACTION_REQUIRED") then "fail" '
    'elif all(.[]; . == "SUCCESS" or . == "NEUTRAL" or . == "SKIPPED") then "pass" else "pending" end)'
)


def pr_info(url: str) -> tuple[str, str, str]:
    """Return (state, head commit, CI state) from the forge, or ("unknown", "", "unknown") when gh cannot answer.
    CI state is pass, fail, pending, or none."""
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", url, "--json", "state,headRefOid,statusCheckRollup", "-q", CI_QUERY],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", "", "unknown"
    parts = proc.stdout.split()
    if proc.returncode != 0 or len(parts) < 2:
        return "unknown", "", "unknown"
    return parts[0], parts[1], parts[2] if len(parts) > 2 else "unknown"


def tidy_done(ticket_id: str) -> None:
    """Remove the worktree of a finished ticket. Git refuses when it has uncommitted files, and then it stays."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if meta and Path(meta["worktree"]).is_dir():
        if subprocess.run(["git", "worktree", "remove", meta["worktree"]], capture_output=True).returncode == 0:
            # -d deletes only a merged branch, so unmerged work is never lost here
            subprocess.run(["git", "branch", "-d", meta["branch"]], capture_output=True)


def cmd_push(args: argparse.Namespace) -> None:
    if not (work_dir(args.id) / "result.md").exists():
        raise Refuse(f"{args.id} has no result yet")
    push_result(args.id)
    print(f"the board has the result of {args.id}")


def cmd_list(args: argparse.Namespace) -> None:
    base = base_branch()
    this_repo = str(load_config(base).get("name") or main_root().name)
    name = PROPS["status"][0]
    pages = board_pages(board(base), {"and": [
        {"property": name, "status": {"does_not_equal": "Done"}},
        {"property": name, "status": {"does_not_equal": "Cancelled"}},
    ]})
    if pages:
        check_schema(pages[0])
    ids = {hex_id(page["id"]): prop(page, "id") for page in pages}
    rows: dict[str, list[str]] = {status: [] for status in STATUSES if status not in ("Done", "Cancelled")}
    done: list[str] = []
    for page in sorted(pages, key=lambda item: prop(item, "id")):
        ticket_id, status = prop(page, "id"), prop(page, "status") or "Backlog"
        fields = {key: prop(page, key) for key in ("repo", "area", "kind", "waiting", "pr")}
        fields["after"] = ", ".join(ids[hex_id(dep)] for dep in prop(page, "after") if hex_id(dep) in ids)
        mine = fields["repo"] in ("", this_repo)
        if args.sync and mine and status == "Review" and fields["pr"]:
            state, _, ci = pr_info(fields["pr"])  # Done is read back from the forge, never assumed
            if state == "OPEN" and ci in ("fail", "pending"):
                fields["note"] = f"CI: {ci}"
            if state == "MERGED":
                set_page(hex_id(page["id"]), status="Done")
                done.append(ticket_id)
                continue
            if state not in ("OPEN", "unknown"):
                fields["note"] = f"PR state: {state}"
        extra = "".join(f"  [{key}: {fields[key]}]" for key in ("repo", "area", "kind", "waiting", "after", "pr", "note")
                        if fields.get(key))
        rows.setdefault(status, []).append(f"  {ticket_id}  {page_title(page)}{extra}")
    for status, items in rows.items():
        print(f"{status} ({len(items)})")
        print("\n".join(items) if items else "  -")
    if done:
        print("set to Done, pull request merged: " + ", ".join(done))
    print("Done and Cancelled tickets are not listed.")
    if args.sync:
        # Remove the worktree of a ticket this machine worked, only when its page says Done or Cancelled.
        # A page that is merely absent from the list above proves nothing.
        folder = state_dir() / "work"
        for work in sorted(folder.iterdir()) if folder.is_dir() else []:
            page_id = read_json(work / "meta.json").get("page")
            if not page_id:
                continue
            try:
                finished = prop(notion("GET", f"/v1/pages/{page_id}"), "status") in ("Done", "Cancelled")
            except Refuse:
                finished = False
            if finished:
                tidy_done(work.name)


def cmd_release(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if Path(meta["worktree"]).is_dir():
        git("worktree", "remove", meta["worktree"])  # git refuses when it has uncommitted changes
    for path in sorted(work.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    work.rmdir()
    print(f"released {args.id}; branch {meta['branch']} is kept. The board is not changed: set Status on the page yourself")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jtek.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a jtek.json template").set_defaults(func=cmd_init)

    start = sub.add_parser("start", help="claim a ticket and create its worktree")
    start.add_argument("ref", help="a ticket id on the board, such as T-12, or the link of its Notion page")
    start.add_argument("--resume", action="store_true")
    start.add_argument("--no-baseline", action="store_true", help="do not run the checks on the base first")
    start.set_defaults(func=cmd_start)

    check = sub.add_parser("check", help="run the declared checks in the worktree")
    check.add_argument("id")
    check.set_defaults(func=cmd_check)

    verdict = sub.add_parser("verdict", help="record a non-author verdict for the current commit")
    verdict.add_argument("id")
    verdict.add_argument("verdict", choices=VERDICTS)
    verdict.add_argument("--by", required=True)
    verdict.add_argument("--notes-file")
    verdict.set_defaults(func=cmd_verdict)

    finish = sub.add_parser("finish", help="move to Review when checks and verdict hold on the current commit")
    finish.add_argument("id")
    finish.add_argument("--pr")
    finish.add_argument("--no-pr", action="store_true", help="the repository has no forge; the branch stays local")
    finish.add_argument("--evidence-file", help="what was run and seen for each `Done when` item; required once")
    finish.add_argument("--attach", action="append", help="a screenshot, recording, or output file to keep with the evidence")
    finish.set_defaults(func=cmd_finish)

    stop = sub.add_parser("stop", help="stop and wait for the human")
    stop.add_argument("id")
    stop.add_argument("--waiting", required=True, choices=WAITING)
    stop.add_argument("--note", required=True)
    stop.set_defaults(func=cmd_stop)

    for name, func, text in (("result", cmd_result, "print the last result"),
                             ("show", cmd_show, "print what a reviewer needs"),
                             ("push", cmd_push, "put the saved result on the board again, after Notion could not be reached"),
                             ("release", cmd_release, "human only: drop the claim and the worktree")):
        item = sub.add_parser(name, help=text)
        item.add_argument("id")
        item.set_defaults(func=func)

    listing = sub.add_parser("list", help="print the open tickets of the board")
    listing.add_argument("--sync", action="store_true",
                         help="set Review tickets to Done when their PR is merged, and remove the worktrees of Done tickets")
    listing.set_defaults(func=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Refuse as err:
        print(f"refused: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
