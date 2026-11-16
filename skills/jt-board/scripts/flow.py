#!/usr/bin/env python3
"""Print queue flow metrics from data that is already recorded.

Read-only. A missing source is `unknown` with a reason. This script does not
guess a duration, does not merge, and does not write queue files.

  python3 -I flow.py --root <repo> [--days 30] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--id <id>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True

CARD_RE = re.compile(r"^- \[([ xX])\] \*\*(.+?)\*\*\s*(.*)$")
ID_RE = re.compile(r"^\d+(?:\.\d+)*$")
KIND_RE = re.compile(r"\(([a-z]+)\)\s*(.*)$")
STATUS_RE = re.compile(r"(?<!\S)([^\s:]+):")
ROUND_RE = re.compile(r"^[ \t*-]*round:[ \t]*(\d+)[ \t]*$")
TICKET_RE = re.compile(r"^ticket:[ \t]*(.*)$")
STATUSES = frozenset({"ask:", "review:", "send-back:", "merge:", "drop:"})
SECTIONS = frozenset({"closed", "first", "main", "later"})
REASON_RE = re.compile(r"^[a-z0-9-]{1,40}$")
REVERT_SHA_RE = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)
GH_LIMIT = 200
GIT_TIMEOUT = 30
GH_TIMEOUT = 15

# Passed to git and gh. GIT_DIR is omitted so the child inspects --root.
# Token files are not read. gh uses its own config under HOME.
_ENV_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "GH_CONFIG_DIR",
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "no_proxy",
    "ALL_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "CURL_CA_BUNDLE",
)


def child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in _ENV_KEYS if os.environ.get(key)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_time(text: str) -> datetime | None:
    raw = text.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return as_utc(datetime.fromisoformat(raw))
    except ValueError:
        return None


def parse_bound(text: str, *, end: bool) -> datetime:
    raw = text.strip()
    if not raw:
        raise ValueError("empty")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        day = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        if end:
            return day + timedelta(days=1) - timedelta(seconds=1)
        return day
    found = parse_time(raw)
    if found is None:
        raise ValueError(raw)
    return found


def duration(seconds: int) -> str:
    remaining = max(0, seconds)
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, secs = divmod(remaining, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return "".join(parts)


def one_line(text: str, limit: int = 80) -> str:
    clean = " ".join("".join(ch for ch in text if ch.isprintable()).split())
    if len(clean) <= limit:
        return clean
    return clean[:limit] + " (truncated)"


def ticket_ok(ticket: str) -> bool:
    if not ticket or len(ticket) > 80 or any(ch.isspace() for ch in ticket):
        return False
    return any(ch.isalpha() or ch in "#-" for ch in ticket)


def token_in(text: str, token: str) -> bool:
    if not ticket_ok(token):
        return False
    return re.search(rf"(?<![\w]){re.escape(token)}(?![\w])", text) is not None


def task_mentioned(text: str, task_id: str) -> bool:
    if re.search(rf"(?:^|/)tasks/{re.escape(task_id)}(?![\d.])", text):
        return True
    if re.search(rf"(?<![\w-])task-{re.escape(task_id)}(?![\d.])", text):
        return True
    return f"Task {task_id} from jt-queue" in text


def valid_id(task_id: str) -> bool:
    return bool(ID_RE.fullmatch(task_id))


def id_key(task_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in task_id.split("."))


def short_sha(sha: str) -> str:
    return sha[:12]


def status_of(suffix: str) -> str | None:
    for found in STATUS_RE.finditer(suffix):
        token = f"{found.group(1)}:"
        if token == "size:":
            continue
        if token in STATUSES:
            return token
        return None
    return None


def split_card(rest: str) -> tuple[str, str | None]:
    match = KIND_RE.search(rest)
    if match:
        name = rest[: match.start()].strip()
        suffix = match.group(2)
    else:
        name = rest.strip()
        suffix = rest
    return one_line(name), status_of(suffix)


@dataclass
class Card:
    task_id: str
    name: str
    status: str | None


@dataclass
class Stamp:
    at: datetime | None = None
    source: str = ""
    reason: str = ""


@dataclass
class Hist:
    review: tuple[str, datetime] | None = None
    merge: tuple[str, datetime] | None = None
    sendbacks: int = 0
    prev: str | None = None


@dataclass
class Task:
    card: Card
    created: Stamp = field(default_factory=Stamp)
    merge: Stamp = field(default_factory=Stamp)
    review_start: Stamp = field(default_factory=Stamp)
    lead: Stamp = field(default_factory=Stamp)
    lead_seconds: int | None = None
    gate: Stamp = field(default_factory=Stamp)
    gate_count: int | None = None
    rework: Stamp = field(default_factory=Stamp)
    rework_count: int | None = None
    review: Stamp = field(default_factory=Stamp)
    review_seconds: int | None = None
    ticket: str = ""
    in_window: str = "no"
    window_reason: str = ""


class GitRepo:
    def __init__(self, root: Path):
        self.root = root
        self.env = child_env()
        self.ok = False
        self.failed = False
        probe = self.run(["rev-parse", "--is-inside-work-tree"])
        if probe is not None and probe.returncode == 0 and probe.stdout.strip() == "true":
            self.ok = True

    def run(self, args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
                env=self.env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            self.failed = True
            return None

    def lines(self, args: list[str]) -> tuple[str, list[str]]:
        proc = self.run(args)
        if proc is None:
            return "failed", []
        if proc.returncode != 0:
            err = proc.stderr or ""
            if "does not have any commits yet" in err:
                return "ok", []
            self.failed = True
            return "failed", []
        return "ok", [line for line in proc.stdout.splitlines() if line.strip()]

    def common_dir(self) -> Path | None:
        proc = self.run(["rev-parse", "--git-common-dir"])
        if proc is None or proc.returncode != 0 or not proc.stdout.strip():
            return None
        raw = Path(proc.stdout.strip())
        if not raw.is_absolute():
            raw = self.root / raw
        return raw.resolve()


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def parse_board(text: str) -> tuple[list[Card], set[str]]:
    section = ""
    found: dict[str, Card] = {}
    dupes: set[str] = set()
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().casefold()
            continue
        if section not in SECTIONS:
            continue
        match = CARD_RE.match(line)
        if not match:
            continue
        task_id = match.group(2).strip()
        if not valid_id(task_id):
            continue
        if task_id in found:
            dupes.add(task_id)
            continue
        name, status = split_card(match.group(3))
        found[task_id] = Card(task_id, name, status)
    cards = [found[key] for key in sorted(found, key=id_key)]
    return cards, dupes


def board_history(repo: GitRepo) -> tuple[str, list[tuple[str, datetime, str]]]:
    state, rows = repo.lines(["log", "--reverse", "--format=%H%x09%cI", "--", "jt-queue/board.md"])
    if state != "ok":
        return state, []
    history: list[tuple[str, datetime, str]] = []
    for row in rows:
        sha, _, when_text = row.partition("\t")
        when = parse_time(when_text)
        if not sha or when is None:
            continue
        shown = repo.run(["show", f"{sha}:jt-queue/board.md"])
        if shown is None or shown.returncode != 0:
            continue
        history.append((sha, when, shown.stdout))
    return "ok", history


def apply_history(history: list[tuple[str, datetime, str]]) -> dict[str, Hist]:
    tracks: dict[str, Hist] = {}
    for sha, when, text in history:
        cards, _dupes = parse_board(text)
        for card in cards:
            hist = tracks.setdefault(card.task_id, Hist())
            status = card.status
            if status == "review:" and hist.prev != "review:" and hist.review is None:
                hist.review = (sha, when)
            if status == "merge:" and hist.prev != "merge:" and hist.merge is None:
                hist.merge = (sha, when)
            if status == "send-back:" and hist.prev != "send-back:":
                hist.sendbacks += 1
            hist.prev = status
    return tracks


def load_ticket(repo: GitRepo, task_id: str) -> str:
    path = repo.root / "jt-queue" / "tasks" / task_id / "task.md"
    text = read_text(path)
    if text is None and repo.ok:
        shown = repo.run(["show", f"HEAD:jt-queue/tasks/{task_id}/task.md"])
        if shown is not None and shown.returncode == 0:
            text = shown.stdout
    if not text:
        return ""
    for line in text.splitlines():
        match = TICKET_RE.match(line.strip())
        if not match:
            continue
        raw = match.group(1).strip().strip("\"'")
        raw = raw.split(" #", 1)[0].strip()
        return raw if ticket_ok(raw) else ""
    return ""


def load_plan_round(repo: GitRepo, task_id: str) -> tuple[str, int | None]:
    """Return ('ok', n), ('missing', None), ('many', None), or ('failed', None)."""
    path = repo.root / "jt-queue" / "tasks" / task_id / "plan.md"
    text = read_text(path)
    if text is None and repo.ok:
        state, rows = repo.lines(
            ["log", "-1", "--format=%H", "--", f"jt-queue/tasks/{task_id}/plan.md"]
        )
        if state == "failed":
            return "failed", None
        if rows:
            shown = repo.run(["show", f"{rows[0]}:jt-queue/tasks/{task_id}/plan.md"])
            if shown is None:
                return "failed", None
            if shown.returncode == 0:
                text = shown.stdout
    if not text:
        return "missing", None
    numbers = [int(match.group(1)) for match in (ROUND_RE.match(line) for line in text.splitlines()) if match]
    if not numbers:
        return "missing", None
    if len(numbers) > 1:
        return "many", None
    return "ok", numbers[0]


def created_stamp(repo: GitRepo, task_id: str) -> Stamp:
    if not repo.ok:
        return Stamp(reason="not a git repository")
    state, rows = repo.lines(
        [
            "log",
            "--diff-filter=A",
            "--format=%H%x09%cI",
            "--",
            f"jt-queue/tasks/{task_id}/task.md",
        ]
    )
    if state == "failed":
        return Stamp(reason="git log failed for task.md")
    parsed: list[tuple[str, datetime]] = []
    for row in rows:
        sha, _, when_text = row.partition("\t")
        when = parse_time(when_text)
        if sha and when is not None:
            parsed.append((sha, when))
    if not parsed:
        return Stamp(reason="task.md is not in git history")
    sha, when = min(parsed, key=lambda item: item[1])
    return Stamp(at=when, source=f"git {short_sha(sha)} task.md")


def gate_log(repo: GitRepo, task_id: str) -> tuple[str, list[tuple[datetime, str]]]:
    """Return ('ok', rows), ('missing', []), or ('failed', []). Rows are (time, result)."""
    if not repo.ok:
        return "failed", []
    common = repo.common_dir()
    if common is None:
        return "failed", []
    path = common / "jt-queue" / "gate-runs.jsonl"
    if not path.is_file():
        return "missing", []
    text = read_text(path)
    if text is None:
        return "failed", []
    rows: list[tuple[datetime, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("id") != task_id:
            continue
        result = item.get("result")
        if result not in {"fail", "pass"}:
            continue
        when = parse_time(str(item.get("at", "")))
        if when is None:
            continue
        reason = item.get("reason", "")
        if result == "fail" and (not isinstance(reason, str) or not REASON_RE.fullmatch(reason)):
            continue
        rows.append((when, result))
    return "ok", rows


def gate_metric(repo: GitRepo, task_id: str) -> tuple[Stamp, int | None]:
    state, rows = gate_log(repo, task_id)
    source = ".git/jt-queue/gate-runs.jsonl"
    if state == "missing":
        return Stamp(reason=f"no gate-run log ({source})"), None
    if state == "failed":
        return Stamp(reason="gate-run log could not be read"), None
    if not rows:
        return Stamp(reason="no gate-run record for this task"), None
    fails = sum(1 for _when, result in rows if result == "fail")
    passed = any(result == "pass" for _when, result in rows)
    note = source if passed else f"{source} (no pass recorded)"
    return Stamp(at=datetime.now(timezone.utc), source=note), fails


def rework_metric(
    repo: GitRepo, task_id: str, hist: Hist | None, board_state: str
) -> tuple[Stamp, int | None]:
    plan_state, plan_round = load_plan_round(repo, task_id)
    if plan_state == "failed":
        return Stamp(reason="plan.md could not be read"), None
    if plan_state == "many":
        return Stamp(reason="plan.md has more than one round:"), None
    plan_rework = None
    if plan_state == "ok" and plan_round is not None:
        if plan_round < 1:
            return Stamp(reason="plan.md round is 0"), None
        plan_rework = plan_round - 1
    # A line that never appears in board history is not an observed zero.
    git_rework = hist.sendbacks if board_state == "ok" and hist is not None else None
    if plan_rework is not None and git_rework is not None and plan_rework != git_rework:
        return (
            Stamp(
                reason=(
                    f"plan.md round {plan_round} (rework {plan_rework}) "
                    f"disagrees with git send-back count {git_rework}"
                )
            ),
            None,
        )
    if plan_rework is not None and git_rework is not None:
        return Stamp(source=f"plan.md round: {plan_round}; git send-back {git_rework}"), plan_rework
    if plan_rework is not None:
        return Stamp(source=f"plan.md round: {plan_round}"), plan_rework
    if git_rework is not None:
        return Stamp(source=f"git send-back {git_rework}"), git_rework
    if board_state == "failed":
        return Stamp(reason="git log failed for board.md and plan.md has no round:"), None
    if not repo.ok:
        return Stamp(reason="not a git repository and plan.md has no round:"), None
    return Stamp(reason="plan.md has no round: and board.md has no send-back history"), None


class Gh:
    def __init__(self, root: Path, env: dict[str, str]):
        self.root = root
        self.env = env
        self.state = "missing"
        self.note = "gh is not installed"
        self.merged: list[dict] = []
        self.bugs: list[tuple[str, dict]] = []
        self.merged_truncated = False
        self.bug_truncated = False
        binary = shutil.which("gh", path=env.get("PATH"))
        if binary is None:
            return
        self.state = "ok"
        self.note = ""
        merged, merged_note, truncated = self._list(
            [
                "pr", "list", "--state", "merged", "--limit", str(GH_LIMIT),
                "--json", "number,title,body,mergedAt,headRefName",
            ]
        )
        if merged is None:
            self.state = "failed"
            self.note = merged_note
            return
        self.merged = merged
        self.merged_truncated = truncated
        issues, issue_note, issue_cut = self._list(
            [
                "issue", "list", "--state", "all", "--label", "bug",
                "--limit", str(GH_LIMIT), "--json", "number,title,body,createdAt",
            ]
        )
        prs, pr_note, pr_cut = self._list(
            [
                "pr", "list", "--state", "all", "--label", "bug",
                "--limit", str(GH_LIMIT), "--json", "number,title,body,createdAt",
            ]
        )
        if issues is None or prs is None:
            self.state = "failed"
            self.note = issue_note if issues is None else pr_note
            return
        self.bugs = [("issue", item) for item in issues] + [("pr", item) for item in prs]
        self.bug_truncated = issue_cut or pr_cut

    @classmethod
    def unavailable(cls, note: str) -> Gh:
        gh = cls.__new__(cls)
        gh.state = "failed"
        gh.note = note
        gh.merged = []
        gh.bugs = []
        gh.merged_truncated = False
        gh.bug_truncated = False
        gh.root = Path(".")
        gh.env = {}
        return gh

    def _list(self, args: list[str]) -> tuple[list[dict] | None, str, bool]:
        try:
            proc = subprocess.run(
                ["gh", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=GH_TIMEOUT,
                env=self.env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, "gh timed out", False
        except OSError:
            return None, "gh could not be started", False
        if proc.returncode != 0:
            return None, f"gh exited {proc.returncode}", False
        try:
            data = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            return None, "gh returned data that is not JSON", False
        if not isinstance(data, list):
            return None, "gh returned data that is not a list", False
        rows = [item for item in data if isinstance(item, dict)]
        return rows, "", len(rows) >= GH_LIMIT


def pr_matches(item: dict, task_id: str, ticket: str) -> bool:
    title = str(item.get("title") or "")
    body = str(item.get("body") or "")
    text = f"{title}\n{body}"
    if f"Task {task_id} from jt-queue" in text or task_mentioned(text, task_id):
        return True
    if ticket and token_in(text, ticket):
        return True
    head = str(item.get("headRefName") or "")
    if ticket and token_in(head.replace("/", " "), ticket):
        return True
    return False


def merge_from_gh(gh: Gh, task_id: str, ticket: str) -> Stamp | None:
    if gh.state != "ok":
        return None
    matched = [item for item in gh.merged if pr_matches(item, task_id, ticket)]
    if len(matched) != 1:
        return None
    item = matched[0]
    when = parse_time(str(item.get("mergedAt") or ""))
    number = item.get("number")
    if when is None or not isinstance(number, int):
        return None
    return Stamp(at=when, source=f"gh pr {number} mergedAt")


def merge_stamp(repo: GitRepo, gh: Gh, task: Card, hist: Hist | None, ticket: str) -> Stamp:
    gh_stamp = merge_from_gh(gh, task.task_id, ticket)
    if gh_stamp is not None:
        return gh_stamp
    if hist is not None and hist.merge is not None:
        sha, when = hist.merge
        return Stamp(at=when, source=f"git {short_sha(sha)} board merge:")
    if not repo.ok:
        return Stamp(reason="not a git repository")
    if gh.state == "failed" and (hist is None or hist.merge is None):
        if task.status == "merge:":
            return Stamp(reason=f"{gh.note} and no merge commit in git history")
        return Stamp(reason="task is not merged")
    if gh.state == "ok":
        matched = [item for item in gh.merged if pr_matches(item, task.task_id, ticket)]
        if len(matched) > 1:
            return Stamp(reason=f"gh returned {len(matched)} merged PRs for this task")
        if gh.merged_truncated and task.status == "merge:":
            return Stamp(
                reason=f"gh returned {GH_LIMIT} merged PRs; the list may be truncated"
            )
    if task.status == "drop:":
        return Stamp(reason="task was dropped, not merged")
    if task.status == "merge:":
        return Stamp(reason="board says merge: but that line is not in git history and gh has no merged PR")
    return Stamp(reason="task is not merged")


def review_start(repo: GitRepo, task_id: str, hist: Hist | None) -> Stamp:
    if hist is not None and hist.review is not None:
        sha, when = hist.review
        return Stamp(at=when, source=f"git {short_sha(sha)} board review:")
    state, rows = gate_log(repo, task_id)
    if state == "ok":
        passes = [when for when, result in rows if result == "pass"]
        if passes:
            return Stamp(at=min(passes), source="gate-runs pass")
    if not repo.ok:
        return Stamp(reason="not a git repository")
    return Stamp(reason="no review: commit and no gate-pass record")


def span(start: Stamp, end: Stamp, order_reason: str) -> tuple[Stamp, int | None]:
    if start.at is None:
        return Stamp(reason=start.reason), None
    if end.at is None:
        return Stamp(reason=end.reason), None
    seconds = int((end.at - start.at).total_seconds())
    if seconds < 0:
        return Stamp(reason=order_reason), None
    return Stamp(source=f"{start.source} -> {end.source}"), seconds


def task_commits(repo: GitRepo, task_id: str, ticket: str) -> set[str]:
    shas: set[str] = set()
    _state, rows = repo.lines(["log", "--format=%H", "--", f"jt-queue/tasks/{task_id}/"])
    shas.update(rows)
    if not ticket_ok(ticket):
        return shas
    _state, subjects = repo.lines(["log", "--fixed-strings", f"--grep={ticket}", "--format=%H%x09%s"])
    for row in subjects:
        sha, _, subject = row.partition("\t")
        if sha and token_in(subject, ticket):
            shas.add(sha)
    return shas


def sha_in(short: str, shas: set[str]) -> bool:
    low = short.lower()
    return any(item.lower().startswith(low) for item in shas)


def revert_defects(repo: GitRepo, tasks: dict[str, Task]) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (status, rows of (task_id, kind, text)). kind is 'hit' or 'unknown'."""
    if not repo.ok:
        return "not a git repository", []
    state, rows = repo.lines(["log", "--format=%H", "--grep=^Revert ", "--grep=This reverts commit"])
    if state == "failed":
        return "git log failed", []
    by_id = {task.card.task_id: task for task in tasks.values()}
    commits = {task_id: task_commits(repo, task_id, task.ticket) for task_id, task in by_id.items()}
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for sha in rows:
        shown = repo.run(["show", "-s", "--format=%cI%n%B", sha])
        if shown is None or shown.returncode != 0:
            continue
        when_text, _, message = shown.stdout.partition("\n")
        when = parse_time(when_text)
        if when is None:
            continue
        reverted = {match.group(1).lower() for match in REVERT_SHA_RE.finditer(message)}
        for task_id, task in by_id.items():
            referenced = task_mentioned(message, task_id) or token_in(message, task.ticket)
            if not referenced:
                referenced = any(sha_in(item, commits[task_id]) for item in reverted)
            if not referenced:
                continue
            key = (task_id, short_sha(sha))
            if key in seen:
                continue
            seen.add(key)
            label = f"git revert {short_sha(sha)}"
            if task.ticket and token_in(message, task.ticket):
                label += f" ticket {task.ticket}"
            elif task_mentioned(message, task_id):
                label += f" task {task_id}"
            else:
                label += " reverts a commit that names this task"
            if task.merge.at is None:
                found.append((task_id, "unknown", f"{label} references it but merge time is missing"))
                continue
            if when <= task.merge.at:
                continue
            found.append((task_id, "hit", label))
    return "ok", found


def bug_text(item: dict) -> str:
    return f"{item.get('title') or ''}\n{item.get('body') or ''}"


def bug_defects(gh: Gh, tasks: dict[str, Task]) -> tuple[str, list[tuple[str, str, str]]]:
    if gh.state == "missing":
        return gh.note, []
    if gh.state == "failed":
        return gh.note, []
    found: list[tuple[str, str, str]] = []
    for kind, item in gh.bugs:
        number = item.get("number")
        if not isinstance(number, int):
            continue
        text = bug_text(item)
        when = parse_time(str(item.get("createdAt") or ""))
        for task_id, task in tasks.items():
            if not (task_mentioned(text, task_id) or token_in(text, task.ticket)):
                continue
            label = f"gh {kind} {number} label bug"
            if when is None:
                found.append((task_id, "unknown", f"{label} references it but createdAt is missing"))
                continue
            if task.merge.at is None:
                found.append((task_id, "unknown", f"{label} references it but merge time is missing"))
                continue
            if when <= task.merge.at:
                continue
            found.append((task_id, "hit", label))
    note = "ok"
    if gh.bug_truncated:
        note = f"gh returned {GH_LIMIT} bug items; the list may be truncated"
    return note, found


def metric_line(name: str, stamp: Stamp, value: int | None, *, seconds: bool) -> str:
    if value is None:
        return f"  {name}: unknown ({stamp.reason})"
    if seconds:
        return f"  {name}: {value}s ({duration(value)}) source: {stamp.source}"
    return f"  {name}: {value} source: {stamp.source}"


def summary_line(name: str, values: list[int], unknown: int, *, seconds: bool) -> str:
    known = len(values)
    if not values:
        return f"  {name}: median unknown known {known} unknown {unknown}"
    mid = sorted(values)[(known - 1) // 2]
    if seconds:
        return f"  {name}: median {mid}s ({duration(mid)}) known {known} unknown {unknown}"
    return f"  {name}: median {mid} known {known} unknown {unknown}"


def build_task(
    repo: GitRepo, gh: Gh, card: Card, hist: Hist | None, board_state: str, dupe: bool
) -> Task:
    task = Task(card=card)
    if dupe:
        reason = "board has more than one line for this id"
        task.lead = Stamp(reason=reason)
        task.gate = Stamp(reason=reason)
        task.rework = Stamp(reason=reason)
        task.review = Stamp(reason=reason)
        return task
    task.ticket = load_ticket(repo, card.task_id)
    task.created = created_stamp(repo, card.task_id)
    task.merge = merge_stamp(repo, gh, card, hist, task.ticket)
    task.review_start = review_start(repo, card.task_id, hist)
    task.lead, task.lead_seconds = span(
        task.created, task.merge, "merge time is before task.md was added"
    )
    task.gate, task.gate_count = gate_metric(repo, card.task_id)
    task.rework, task.rework_count = rework_metric(repo, card.task_id, hist, board_state)
    task.review, task.review_seconds = span(
        task.review_start, task.merge, "merge time is before the review start"
    )
    return task


def window_of(task: Task, since: datetime, until: datetime) -> None:
    if task.merge.at is not None:
        anchor = task.merge.at
    elif task.card.status != "merge:" and task.created.at is not None:
        anchor = task.created.at
    else:
        anchor = None
    if anchor is None:
        task.in_window = "unknown"
        task.window_reason = "no created time and no merge time"
        return
    if since <= anchor <= until:
        task.in_window = "yes"
        return
    task.in_window = "no"


@dataclass
class ClaimRow:
    owner: str
    claimed: str
    activity: str


def stale_hours(board: str) -> int:
    for line in board.splitlines():
        match = re.match(r"^\|\s*`<CLAIM_STALE>`\s*\|\s*(.*?)\s*\|\s*$", line)
        if match is None:
            continue
        raw = match.group(1).strip().lower()
        if raw.endswith("h"):
            raw = raw[:-1]
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
    return 24


def parse_claim_file(text: str) -> dict[str, ClaimRow] | None:
    """Claims keyed by task id. None means the file is not a claim list."""
    if not text.strip():
        return {}
    claims: dict[str, ClaimRow] = {}
    current: str | None = None
    owner = ""
    claimed = ""
    activity = ""

    def finish() -> bool:
        nonlocal current, owner, claimed, activity
        if current is None:
            return True
        if current in claims or not owner or parse_time(claimed) is None or parse_time(activity) is None:
            return False
        if any(ch.isspace() and ch != " " for ch in owner):
            return False
        claims[current] = ClaimRow(owner, claimed, activity)
        current = None
        owner = claimed = activity = ""
        return True

    for line in text.splitlines():
        if line.startswith("# ") or line.strip() == "#":
            continue
        if line.startswith("## "):
            if not finish():
                return None
            task_id = line[3:].strip()
            if not valid_id(task_id):
                return None
            current = task_id
            continue
        if current is None:
            if line.strip():
                return None
            continue
        if line.startswith("owner:"):
            owner = line.split(":", 1)[1].strip()
            continue
        if line.startswith("claimed:"):
            claimed = line.split(":", 1)[1].strip()
            continue
        if line.startswith("activity:"):
            activity = line.split(":", 1)[1].strip()
            continue
        if line.strip() == "paths:" or line.strip() == "-" or line.startswith("- "):
            continue
        if line.strip():
            return None
    if not finish():
        return None
    return claims


def load_claim_text(root: Path, repo: GitRepo) -> str | None:
    text = read_text(root / "jt-queue" / "claims.md")
    if text is not None:
        return text
    if not repo.ok:
        return None
    shown = repo.run(["show", "HEAD:jt-queue/claims.md"])
    if shown is not None and shown.returncode == 0:
        return shown.stdout
    return None


def _branch_matches(name: str, task_id: str, ticket: str) -> bool:
    bare = f"task-{task_id}"
    if name == bare or (name.startswith(bare + "-") and name[len(bare) + 1 :]):
        return True
    if not ticket or "/" not in name or any(ch.isspace() for ch in ticket):
        return False
    _kind, rest = name.split("/", 1)
    return rest == ticket or rest.startswith(ticket + "-")


def branch_activity(repo: GitRepo, task_id: str, ticket: str) -> datetime | None:
    if not repo.ok:
        return None
    state, names = repo.lines(["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    if state != "ok":
        return None
    matched = [name for name in names if _branch_matches(name, task_id, ticket)]
    if len(matched) != 1:
        return None
    proc = repo.run(["log", "-1", "--format=%cI", matched[0]])
    if proc is None or proc.returncode != 0:
        return None
    return parse_time(proc.stdout.strip())


def worktree_dirty(repo: GitRepo, task_id: str) -> bool:
    common = repo.common_dir()
    if common is None:
        return False
    reg = common / "jt-queue" / "worktrees.json"
    try:
        loaded = json.loads(reg.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(loaded, dict):
        return False
    entry = loaded.get(task_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        return False
    path = Path(entry["path"])
    if not path.is_dir():
        return False
    proc = repo.run(["-C", str(path), "status", "--porcelain"])
    if proc is None or proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def claim_view(
    repo: GitRepo,
    task: Task,
    claims: dict[str, ClaimRow] | None,
    hours: int,
    now: datetime,
) -> tuple[str, str]:
    """(owner line body, stale yes/no/unknown). Owner body is `none` or the name."""
    if claims is None:
        return "unknown (jt-queue/claims.md could not be read)", "unknown"
    claim = claims.get(task.card.task_id)
    if claim is None:
        return "none", "no"
    if worktree_dirty(repo, task.card.task_id):
        return claim.owner, "no"
    moments = [parse_time(claim.activity), parse_time(claim.claimed)]
    tip = branch_activity(repo, task.card.task_id, task.ticket)
    if tip is not None:
        moments.append(tip)
    latest = max((item for item in moments if item is not None), default=None)
    if latest is None:
        return claim.owner, "unknown"
    stale = "yes" if now - latest > timedelta(hours=hours) else "no"
    return claim.owner, stale


def owner_block(owner: str, claimed: str, activity: str, stale: str) -> list[str]:
    lines = [f"  owner: {owner}"]
    if owner == "none" or owner.startswith("unknown"):
        lines.append("  claimed: none" if owner == "none" else "  claimed: unknown")
        lines.append(f"  stale: {stale}")
        return lines
    lines.append(f"  claimed: {claimed}")
    lines.append(f"  activity: {activity}")
    lines.append(f"  stale: {stale}")
    return lines


_UPDATED_STAMP = re.compile(
    r"^- \*\*Updated:\*\*\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$",
    re.M,
)


def _note_head(path: Path) -> str | None:
    """First bytes of a regular file. A symlink is not followed."""
    if path.is_symlink():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return handle.read(4096)
    except (OSError, UnicodeError):
        return None


def age_label(stamp: datetime, now: datetime) -> str:
    seconds = (as_utc(now) - as_utc(stamp)).total_seconds()
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    if hours < 48:
        return f"{hours}h"
    return f"{hours // 24}d"


def handoff_line(root: Path, repo: GitRepo, task_id: str, now: datetime) -> str:
    """Whether tasks/<id>/handoff.md exists, and how old its Updated stamp is.

    The note body is not printed. A symlink is not read.
    """
    if not valid_id(task_id):
        return "no"
    rel = f"jt-queue/tasks/{task_id}/handoff.md"
    path = root / "jt-queue" / "tasks" / task_id / "handoff.md"
    if path.is_symlink():
        return f"yes age: unknown (handoff.md is not a regular file) path: {rel}"
    text = _note_head(path) if path.is_file() else None
    if text is None and repo.ok:
        shown = repo.run(["show", f"HEAD:{rel}"])
        if shown is not None and shown.returncode == 0:
            text = shown.stdout[:4096]
    if text is None:
        return "no"
    match = _UPDATED_STAMP.search(text)
    stamp = parse_time(match.group(1)) if match else None
    if stamp is None:
        return f"yes age: unknown (no updated stamp) path: {rel}"
    return f"yes age: {age_label(stamp, now)} path: {rel}"


def render_task(
    task: Task, owners: list[str] | None = None, handoff: str = ""
) -> list[str]:
    name = f" {task.card.name}" if task.card.name else ""
    lines = [f"task: {task.card.task_id}{name}"]
    if owners:
        lines.extend(owners)
    if handoff:
        lines.append(f"  handoff: {handoff}")
    if task.in_window == "unknown":
        lines.append(f"  in-window: unknown ({task.window_reason})")
    else:
        lines.append(f"  in-window: {task.in_window}")
    lines.append(metric_line("lead-time", task.lead, task.lead_seconds, seconds=True))
    lines.append(metric_line("gate-fails", task.gate, task.gate_count, seconds=False))
    lines.append(metric_line("rework", task.rework, task.rework_count, seconds=False))
    lines.append(metric_line("review-time", task.review, task.review_seconds, seconds=True))
    return lines


def lesson_report(root: Path) -> list[str]:
    """Lessons whose enforced-by cell is still `not yet`. The file is data."""
    path = root / "jt-queue" / "team-lessons.md"
    if not path.exists():
        return ["lessons:", "  not-yet: none (jt-queue/team-lessons.md is absent)"]
    text = read_text(path)
    if text is None or not path.is_file():
        return ["lessons:", "  not-yet: unknown (jt-queue/team-lessons.md could not be read)"]
    header: list[str] | None = None
    pending: list[str] = []
    proposed: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        folded = [cell.casefold() for cell in cells]
        if header is None:
            if "id" in folded and "enforced by" in folded and "wrong" in folded:
                header = folded
            continue
        if cells and all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        if len(cells) < len(header):
            continue
        data = {header[index]: cells[index] for index in range(len(header))}
        ident = one_line(data.get("id", ""), 40)
        wrong = one_line(data.get("wrong", ""), 80)
        enforced = " ".join(data.get("enforced by", "").split())
        if not ident:
            continue
        if enforced == "not yet":
            pending.append(f"  not-yet: {ident} wrong: {wrong}")
        elif enforced.startswith("proposed:"):
            proposal = one_line(enforced[len("proposed:") :], 80)
            proposed.append(f"  proposed: {ident} {proposal}")
    lines = ["lessons:"]
    lines.extend(pending or ["  not-yet: none"])
    lines.extend(proposed)
    return lines


def report(
    root: Path,
    *,
    days: int = 30,
    since: str = "",
    until: str = "",
    only_id: str = "",
    now: datetime | None = None,
) -> str:
    if only_id and not valid_id(only_id):
        raise ValueError("id")
    if days < 1:
        raise ValueError("days")
    moment = as_utc(now or datetime.now(timezone.utc))
    try:
        end = parse_bound(until, end=True) if until else moment
        start = parse_bound(since, end=False) if since else end - timedelta(days=days)
    except ValueError as err:
        raise ValueError(f"date {err}") from err
    if start > end:
        raise ValueError("since is after until")

    root = root.resolve()
    repo = GitRepo(root)
    board_path = root / "jt-queue" / "board.md"
    text = read_text(board_path)
    board_from = "worktree"
    if text is None and repo.ok:
        shown = repo.run(["show", "HEAD:jt-queue/board.md"])
        if shown is not None and shown.returncode == 0:
            text = shown.stdout
            board_from = "HEAD"
    lines: list[str] = [
        f"window: {start.strftime('%Y-%m-%dT%H:%M:%SZ')} .. {end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    ]
    if text is None:
        lines.append("board: unknown (jt-queue/board.md is missing)")
        lines.append("summary:")
        lines.append("  tasks: 0")
        lines.append("  undated: 0")
        lines.append("  outside-window: 0")
        lines.append("escaped-defects: 0")
        lines.append("revert: unknown (jt-queue/board.md is missing)")
        lines.append("bug-label: unknown (jt-queue/board.md is missing)")
        lines.extend(lesson_report(root))
        return "\n".join(lines) + "\n"

    cards, dupes = parse_board(text)
    if only_id:
        cards = [card for card in cards if card.task_id == only_id]
        if not cards:
            lines.append(f"task: {only_id}")
            lines.append("  in-window: unknown (no board line for this id)")
            lines.append("summary:")
            lines.append("  tasks: 0")
            lines.append("  undated: 0")
            lines.append("  outside-window: 0")
            lines.append("escaped-defects: 0")
            lines.append("revert: ok")
            lines.append("bug-label: unknown (no board line for this id)")
            lines.extend(lesson_report(root))
            return "\n".join(lines) + "\n"

    hist_state, history = board_history(repo) if repo.ok else ("skipped", [])
    tracks = apply_history(history) if hist_state == "ok" else {}
    gh = Gh(root, repo.env) if repo.ok else Gh.unavailable("not a git repository")

    tasks = [
        build_task(
            repo, gh, card, tracks.get(card.task_id), hist_state, card.task_id in dupes
        )
        for card in cards
    ]
    for task in tasks:
        window_of(task, start, end)
        if only_id and task.in_window == "no":
            task.in_window = "no"

    shown = [task for task in tasks if task.in_window != "no" or task.card.task_id == only_id]
    outside = [task for task in tasks if task.in_window == "no" and task.card.task_id != only_id]
    in_window = [task for task in shown if task.in_window == "yes"]
    undated = [task for task in shown if task.in_window == "unknown"]

    claim_text = load_claim_text(root, repo)
    claims = parse_claim_file(claim_text) if claim_text is not None else {}
    hours = stale_hours(text)
    by_id = {task.card.task_id: task for task in tasks}

    def owner_lines(task: Task) -> list[str]:
        owner, stale = claim_view(repo, task, claims, hours, moment)
        claim = claims.get(task.card.task_id) if claims is not None else None
        claimed = claim.claimed if claim is not None else ""
        activity = claim.activity if claim is not None else ""
        return owner_block(owner, claimed, activity, stale)

    for task in shown:
        lines.extend(
            render_task(
                task,
                owner_lines(task),
                handoff_line(root, repo, task.card.task_id, moment),
            )
        )

    lines.append("claims:")
    if claims is None:
        lines.append("  claims: unknown (jt-queue/claims.md could not be read)")
    else:
        for card in cards:
            task = by_id.get(card.task_id)
            if task is None:
                continue
            owner, stale = claim_view(repo, task, claims, hours, moment)
            claim = claims.get(card.task_id)
            claimed = claim.claimed if claim is not None else "none"
            lines.append(f"  {card.task_id} owner: {owner} claimed: {claimed} stale: {stale}")

    lines.append("handoffs:")
    for card in cards:
        lines.append(
            f"  {card.task_id} handoff: {handoff_line(root, repo, card.task_id, moment)}"
        )

    lines.append("summary:")
    lines.append(f"  tasks: {len(in_window)}")
    lines.append(f"  undated: {len(undated)}")
    lines.append(f"  outside-window: {len(outside)}")
    for name, values, unknown, seconds in (
        (
            "lead-time",
            [task.lead_seconds for task in in_window if task.lead_seconds is not None],
            sum(1 for task in in_window if task.lead_seconds is None),
            True,
        ),
        (
            "gate-fails",
            [task.gate_count for task in in_window if task.gate_count is not None],
            sum(1 for task in in_window if task.gate_count is None),
            False,
        ),
        (
            "rework",
            [task.rework_count for task in in_window if task.rework_count is not None],
            sum(1 for task in in_window if task.rework_count is None),
            False,
        ),
        (
            "review-time",
            [task.review_seconds for task in in_window if task.review_seconds is not None],
            sum(1 for task in in_window if task.review_seconds is None),
            True,
        ),
    ):
        lines.append(summary_line(name, values, unknown, seconds=seconds))

    considered = {task.card.task_id: task for task in shown}
    revert_state, revert_rows = revert_defects(repo, considered)
    bug_state, bug_rows = bug_defects(gh, considered)
    hits = [(task_id, text) for task_id, kind, text in revert_rows + bug_rows if kind == "hit"]
    unknowns = [(task_id, text) for task_id, kind, text in revert_rows + bug_rows if kind == "unknown"]
    hit_ids = sorted({task_id for task_id, _text in hits}, key=id_key)
    lines.append(f"escaped-defects: {len(hit_ids)}")
    for task_id, text in sorted(hits, key=lambda item: (id_key(item[0]), item[1])):
        lines.append(f"  task: {task_id} source: {text}")
    for task_id, text in sorted(unknowns, key=lambda item: (id_key(item[0]), item[1])):
        lines.append(f"  task: {task_id} unknown ({text})")
    if revert_state == "ok":
        lines.append("revert: ok")
    else:
        lines.append(f"revert: unknown ({revert_state})")
    if bug_state == "ok":
        lines.append("bug-label: ok")
    else:
        lines.append(f"bug-label: unknown ({bug_state})")
    if board_from == "HEAD":
        lines.append("board-from: HEAD (jt-queue/board.md is not in the worktree)")
    lines.extend(lesson_report(root))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print jt-queue flow metrics. Read-only.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--since", default="")
    parser.add_argument("--until", default="")
    parser.add_argument("--id", default="")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        sys.stderr.write("root is not a directory\n")
        return 2
    try:
        sys.stdout.write(
            report(
                root,
                days=args.days,
                since=args.since,
                until=args.until,
                only_id=args.id,
            )
        )
    except ValueError as err:
        sys.stderr.write(f"invalid argument: {err}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
