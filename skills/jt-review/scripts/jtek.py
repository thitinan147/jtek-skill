#!/usr/bin/env python3
"""jtek inner loop: one ticket, one session, one worktree.

The board is a Notion database or a FLO product, which only the outer loop reads and writes
with its own tool. Neither this script nor inner-loop sessions talk to the board: the outer loop
hands the ticket in as a file and writes back what the `board:` line says. Config and per-repository knowledge live on this machine,
under $HOME/.jtek (or JTEK_HOME). No file there means the defaults: an empty board, so tickets
are files. Nothing is read from jtek.json or .jtek/ inside the repository.
Claims, logs, and results live under the repository's common git directory, so every
worktree sees the same claims and no tracked file is shared between sessions.
Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import hmac
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no advisory locks, so writes go unlocked as before
    fcntl = None

STATUSES = ["Backlog", "Todo", "In Progress", "Review", "Done", "Cancelled"]
VERDICTS = ["PASS", "PASS+NOTES", "FAIL"]
WAITING = ["input", "approval"]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CONFIG = "jtek.json"
LOCAL_RE = re.compile(r"^LOCAL-([0-9]+)$")
TICKETS = "_tickets"  # the old folder beside the repository. Never a ticket id: an id starts with a letter or a digit
WORKTREE_COMMIT = " (of the worktree, not of that folder)"
MAX_FAILED_RUNS = 3
MAX_EVIDENCE_LINES = 40
DEFAULT_TIMEOUT = 1800
MAX_RUN_OUTPUT = 20000
CI_TRIES = 40  # how many times finish looks again while CI is still pending
CI_WAIT = 15.0  # seconds between those looks. JTEK_CI_TRIES and JTEK_CI_WAIT override them
CI_APPEAR_TRIES = 3  # how many times finish looks when the rollup is still empty
CI_APPEAR_WAIT = 2.0  # seconds between those looks. JTEK_CI_APPEAR_TRIES and JTEK_CI_APPEAR_WAIT override them
AUTHOR_CAP = 20  # later writers can be dropped; the original writer, stored first, is not
# The first name that is set identifies the session. The raw value is hashed and never printed.
# There is no parent-process fallback: a second shell would share that id and could record a pass.
SESSION_KEYS = ("JTEK_SESSION", "CURSOR_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")
# A missing id is refused. The same text in any of these names is the same session.
SESSION_MISSING = (
    "Set JTEK_SESSION (or CURSOR_SESSION_ID, CLAUDE_CODE_SESSION_ID, or CODEX_THREAD_ID) to an id that stays "
    "the same for this whole session. jtek does not use the parent process as a session. The same text in any "
    "of those names is the same session."
)
UNOBSERVABLE_WORD = re.compile(
    r"\b(?:fast(?:er|est)?|slow(?:er|est)?|eas(?:y|ier|iest)|delight(?:ful)?|better|nicer|smoother|snappy|"
    r"feel(?:s|ing|t)?|usable|user-friendly|convenient|intuitive|secure|works|quicker|pleasant|simple|simpler)\b",
    re.I,
)
# A digit, a version, or a unit-less number does not make a quality word checkable.
# Longer phrases first. ง่าย and เร็ว do not match inside ไม่ง่าย, ไม่เร็ว, or ความเร็ว.
# ความเร็ว is the noun for speed and is itself unobservable unless the item is measured.
THAI_UNOBSERVABLE = re.compile(
    r"(?<!ไม่)(?:รู้สึก|ใช้งานง่าย|ใช้งานดีขึ้น|น่าใช้|เร็วขึ้น|ง่ายขึ้น|ความเร็ว|เร็ว|ง่าย)"
)
MEASURE = re.compile(
    r"(?:\d+(?:\.\d+)?)\s*(?:ms|msec|milliseconds?|s|sec|secs|seconds?|min|mins|minutes?|%|px|mb|kb|gb|x)\b",
    re.I,
)
COMPARE = re.compile(r"\b(?:under|at least|at most|no more than|within|fewer than|less than)\b", re.I)
_DQ = '"'
_SQ = "'"
QUOTED = re.compile("`[^`]*`|" + _DQ + "[^" + _DQ + "]*" + _DQ + "|" + _SQ + "[^" + _SQ + "]*" + _SQ)
FULLWIDTH_DIGITS = str.maketrans("０１２３４５๖７８９", "0123456789")
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
# A check is lint-class when one of its name pieces is a lint, format, or type tool.
# Name a behaviour check test, verify, or behaviour-<name> (behaviour-eslint still counts).
LINT_TOKENS = frozenset({
    "lint", "eslint", "ruff", "flake8", "prettier", "tsc", "mypy", "pyright", "pylint",
    "black", "isort", "stylelint", "biome", "rubocop", "clippy", "phpcs", "golint",
    "syntax", "format", "fmt", "type", "types", "typecheck", "import", "imports", "style",
    "rustfmt", "gofmt", "shfmt",
    "bandit", "semgrep", "shellcheck", "hadolint", "markdownlint",
})
RUN_CITE = re.compile(r"\bruns? ([0-9]+(?:\s*(?:,\s*and|,|and)\s*[0-9]+)*)")


def read_run(work: Path, number: int) -> dict:
    """The header of a recorded run, or {} when there is none or it never finished being written."""
    path = work / "runs" / f"{number}.txt"
    text = path.read_text(errors="replace") if path.exists() else ""
    header, _, rest = text.partition("\n--- stdout ---\n")
    head = {}
    for line in header.splitlines():
        key, _, value = line.partition(": ")
        head[key] = value
    head["stdout"] = rest.partition("--- stderr ---\n")[0]
    return head if "exit" in head else {}


def cited_runs(text: str) -> list[int]:
    """Run numbers cited in brackets, such as `(run 3)`, `(runs 3 and 4)`, or `(run 7 stand-in, run 5 real service)`."""
    return [int(n) for group in re.findall(r"\(([^()]*)\)", text)
            for found in RUN_CITE.findall(group) for n in re.findall(r"[0-9]+", found)]
# Files a human should look at first when a ticket touches them.
SENSITIVE = [
    CONFIG, ".jtek/*", ".github/*", ".claude/*", ".gitlab-ci.yml", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "poetry.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
    # Files that commonly define what a check command runs.
    "Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "package.json", "pyproject.toml", "setup.cfg",
    "tox.ini", "noxfile.py", "pytest.ini", "conftest.py",
    # A new dependency or migration goes ahead inside the pull request, so the human must see it there.
    "requirements*.txt", "Pipfile", "Pipfile.lock", "go.mod", "Cargo.toml", "Gemfile", "bun.lock", "bun.lockb",
    "*migrations/*", "*migrate/*",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradle.lockfile",
    "libs.versions.toml", "build.sbt", "composer.json", "composer.lock", "*.csproj", "*.fsproj", "packages.lock.json",
    "Directory.Packages.props", "mix.exs", "mix.lock", "pubspec.yaml", "pubspec.lock", "Package.swift",
    "Package.resolved", "Podfile", "Podfile.lock", "deno.json", "deno.lock", "npm-shrinkwrap.json", "pdm.lock",
]

class Refuse(Exception):
    """A rule is not met. The message says what to do next."""


def redact(text: str) -> str:
    """Drop values that can be a token. The name of a variable, such as GH_TOKEN, stays."""
    text = re.sub(r"(?i)(?:(?:ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]+|(?:glpat-|gloas-|gldt-)[A-Za-z0-9_-]+)", "[redacted]", text)
    text = re.sub(r"(?i)\b(token|authorization|bearer)\b\s*[:=]\s*\S+", r"\1 [redacted]", text)
    text = re.sub(r"//[^/\s:@]+:[^@\s/]+@", "//", text)
    return text


def public_url(url: str) -> str:
    """A link safe to print. A token in the --pr argument is redacted the same way as gh stderr."""
    return redact(url or "")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def session_identity() -> str:
    """Who launched this command, as 16 hex characters, or "" when no session id is set.

    The hash is of the value only, so the same text in JTEK_SESSION or CURSOR_SESSION_ID is one session.
    The raw id is never stored or printed. The parent process is not a session."""
    for key in SESSION_KEYS:
        value = " ".join(os.environ.get(key, "").split())
        if value:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
    return ""


def author_key() -> bytes:
    """A key that stays on this machine, so a hand edit of meta.json cannot recompute the seal.

    Two starts can create the file at the same moment. The one that loses the exclusive create reads
    the key the other wrote, once those bytes are there."""
    key_file = state_dir() / "author.key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        try:
            data = key_file.read_bytes()
        except FileNotFoundError:
            data = b""
        if len(data) >= 32:
            return data
        try:
            handle = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            time.sleep(0.01)
            continue
        try:
            os.write(handle, os.urandom(32))
        finally:
            os.close(handle)
        return key_file.read_bytes()
    raise Refuse(f"could not read {key_file}")


def mac_of(payload: bytes, key: bytes | None = None) -> str:
    return hmac.new(key if key is not None else author_key(), payload, hashlib.sha256).hexdigest()


def origin_url(cwd: Path | None = None) -> str:
    """The configured origin URL, or "" when this repository has no origin.

    This is remote.origin.url, not git remote get-url. get-url expands url.*.insteadOf,
    so a rewrite would look like a different remote instead of a rewrite of this one."""
    if "origin" not in git("remote", cwd=cwd, check=False).split():
        return ""
    return git("config", "--get", "remote.origin.url", cwd=cwd, check=False)


def origin_seal(url: str) -> str:
    """The same HMAC as the authors list, over the origin URL and nothing else."""
    return mac_of(url.encode())


def origin_record_path() -> Path:
    return state_dir() / "origin-url.json"


def read_origin_record() -> dict:
    path = origin_record_path()
    if not path.is_file():
        return {}
    try:
        return read_json(path)
    except Refuse:
        return {}


def origin_intact(record: dict) -> bool:
    """False when the sealed origin URL was written or edited without the machine key."""
    url = record.get("url") if isinstance(record, dict) else None
    seal = record.get("seal") if isinstance(record, dict) else None
    if not isinstance(url, str) or not isinstance(seal, str) or not seal:
        return False
    return hmac.compare_digest(origin_seal(url), seal)


def origin_seal_due() -> bool:
    """True when a start has already recorded authors, so a missing seal file was removed.

    The start that writes the seal still has `starting` on disk until it finishes, and it has no
    author seal yet. A later start must not treat that missing file as the first sight of an origin."""
    work = state_dir() / "work"
    if not work.is_dir():
        return False
    for meta_path in work.glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and (
            meta.get("authors_seal") or meta.get("authors") or meta.get("author") or not meta.get("starting")
        ):
            return True
    return False


def remember_origin(cwd: Path | None = None) -> None:
    """Seal the origin URL the first time start can see one.

    An empty URL means there was no origin yet. A later start that sees one seals that URL, once.
    A sealed non-empty URL is never replaced here. A missing, empty, or damaged file is not written
    again: finish keeps refusing it. A hand edit that does not recompute the seal is ignored.
    A process that can rewrite both the key and this file can still forge it."""
    url = origin_url(cwd)
    path = origin_record_path()
    record = read_origin_record()
    if origin_intact(record):
        if record["url"] or not url:
            return
    elif path.is_file() or origin_seal_due():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"url": url, "seal": origin_seal(url)})


def repo_identity(url: str) -> tuple[str, str]:
    """Host (with non-default port) and path of a repository URL.

    `https://github.com/acme/widget.git` and the same path with a credential or default port
    are one repository. A non-default port is a different repository. Only URLs with a host
    strip a trailing `.git`; a local or `file://` path keeps its exact normalised path.
    The credential itself is not part of the result."""
    text = url.strip()
    host = ""
    port: int | None = None
    scheme = ""
    path = text
    if "://" in text:
        parsed = urllib.parse.urlparse(text)
        scheme = (parsed.scheme or "").lower()
        host = (parsed.hostname or "").lower()
        port = parsed.port
        path = urllib.parse.unquote(parsed.path or "")
    else:
        scp = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):(.+)", text)
        if scp and not text.startswith("/") and not text.startswith("."):
            host = scp.group(1).lower()
            path = scp.group(2)
    path = path.rstrip("/")
    if host:
        default = {"https": 443, "http": 80, "ssh": 22, "git": 9418}.get(scheme)
        if port and port != default:
            host = f"{host}:{port}"
        if path.endswith(".git"):
            path = path[:-4]
        path = path.lstrip("/")
    else:
        path = os.path.normpath(path)
    return host, path


def rewritten_origin(url: str, cwd: Path | None = None) -> str:
    """The URL git would ask after the longest matching url.*.insteadOf rule.

    The rule's key can hold a credential, so this string is compared and never printed."""
    raw = git("config", "--null", "--get-regexp", r"^url\..*\.insteadof$", cwd=cwd, check=False)
    best: tuple[int, str, str] | None = None
    for record in raw.split("\0"):
        if not record:
            continue
        key, sep, value = record.partition("\n")
        if not sep or not value:
            continue
        folded = key.lower()
        if not (folded.startswith("url.") and folded.endswith(".insteadof")):
            continue
        # Not named `base`: that name is the branch argument of the git commands below, and a
        # scanner treats one assignment as the source of every later use.
        replacement = key[len("url."):-len(".insteadof")]
        if url.startswith(value) and (best is None or len(value) > best[0]):
            best = (len(value), replacement, value)
    if best is None:
        return url
    return best[1] + url[len(best[2]):]


def insteadof_applies(url: str, cwd: Path | None = None) -> bool:
    """True when a url.*.insteadOf rule would send ls-remote and fetch to a different repository.

    A rewrite that keeps the same host and path, such as a credential on https://github.com/, does not.
    The rule is not printed: its key can hold a credential."""
    if not url:
        return False
    rewritten = rewritten_origin(url, cwd)
    if rewritten == url:
        return False
    return repo_identity(rewritten) != repo_identity(url)


def require_honest_origin(cwd: Path | None = None) -> None:
    """Refuse when finish --no-pr would ask a different repository than the one sealed at init or start."""
    url = origin_url(cwd)
    if insteadof_applies(url, cwd):
        raise Refuse(
            "a url.*.insteadOf rule rewrites the origin URL, so ls-remote and fetch would not ask the sealed origin. "
            "This change is not sent without a pull request."
        )
    record = read_origin_record()
    if not origin_intact(record):
        raise Refuse(
            "the origin URL sealed at init or start is missing or was edited. The seal does not match. "
            "This change is not sent without a pull request."
        )
    if record["url"] and url != record["url"]:
        try:
            remote_default(cwd)
        except Refuse as err:
            raise Refuse(
                "the origin URL changed from the one sealed at init or start, so this change is not sent without a pull request. "
                + str(err)
            ) from None
        raise Refuse(
            "the origin URL changed from the one sealed at init or start, so this change is not sent without a pull request."
        )


def authors_seal(authors: list) -> str:
    body = "\n".join(str(item) for item in authors).encode()
    return mac_of(body)


def broke_body(record: dict) -> bytes:
    """The bytes a broke proof is sealed over. The seal field itself is not part of them."""
    body = {"sha": record.get("sha", ""), "items": record.get("items", {})}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def attach_broke_seal(record: dict, key: bytes | None = None) -> dict:
    """Return the proof with a seal. A hand-written broke.json does not have this seal."""
    sealed = {"sha": record.get("sha", ""), "items": record.get("items", {})}
    sealed["seal"] = mac_of(broke_body(sealed), key)
    return sealed


def broke_intact(record: dict) -> bool:
    """False when broke.json was written or edited without the same key that seals the authors."""
    seal = record.get("seal") if isinstance(record, dict) else None
    if not isinstance(seal, str) or not seal:
        return False
    return hmac.compare_digest(mac_of(broke_body(record)), seal)


def authors_intact(meta: dict) -> bool:
    """False when the authors list was edited without the machine key that sealed it."""
    authors = meta.get("authors")
    seal = meta.get("authors_seal")
    if not isinstance(authors, list) or not isinstance(seal, str) or not seal:
        return False
    return hmac.compare_digest(authors_seal(authors), seal)


def note_author(meta: dict) -> None:
    """Remember this session as one that wrote the ticket. A later resume adds itself.

    The first id is the original writer and is never dropped. Later ids stop at AUTHOR_CAP.
    The list is sealed. A hand edit that does not recompute the seal with the machine key is refused.
    A process that can rewrite both the key and meta.json can still forge the list. The limit is that
    key, not a claim that the file is tamper-proof against the user who owns the machine."""
    ident = session_identity()
    if not ident:
        raise Refuse(SESSION_MISSING)
    if meta.get("authors") or meta.get("authors_seal"):
        if not authors_intact(meta):
            raise Refuse(
                "the authors recorded at start were changed in meta.json. The seal no longer matches. "
                "A hand edit of the authors does not make a verdict count."
            )
    authors = [a for a in meta.get("authors", []) if isinstance(a, str) and a]
    if not authors:
        authors = [ident]
    elif ident not in authors:
        authors.append(ident)
    while len(authors) > AUTHOR_CAP:
        del authors[1]  # index 0 is the original writer
    meta["authors"] = authors
    meta["author"] = ident
    meta["authors_seal"] = authors_seal(authors)


def fold_item(text: str) -> str:
    """Drop format characters and fold fullwidth and Thai digits, so a hidden letter cannot hide a word.

    Format characters are Unicode category Cf: zero-width spaces, word joiner (U+2060),
    left-to-right and right-to-left marks (U+200E, U+200F), soft hyphen (U+00AD), and the same class."""
    kept = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return kept.translate(FULLWIDTH_DIGITS).translate(THAI_DIGITS)


def quoted_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in QUOTED.finditer(text)]


def inside_quotes(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(left <= start and end <= right for left, right in spans)


def unobservable_word(line: str) -> str:
    """A quality word with nothing a person can measure or watch, or "" when the item can be checked.

    A digit anywhere does not by itself make the item checkable. A comparison with a unit does.
    A backtick or a quote exempts a quality word only when that word sits inside it.
    A verb such as prints does not exempt the other words on the line. A backtick after feels faster does not count."""
    text = fold_item(re.sub(r"^-\s*", "", line.strip()))
    if MEASURE.search(text) or (COMPARE.search(text) and re.search(r"\d", text)):
        return ""
    spans = quoted_spans(text)
    found = UNOBSERVABLE_WORD.search(text)
    if found and not inside_quotes(*found.span(), spans):
        return found.group(0)
    thai = THAI_UNOBSERVABLE.search(text)
    if thai and not inside_quotes(*thai.span(), spans):
        return thai.group(0)
    return ""


def is_behaviour_check(name: str) -> bool:
    """True when this declared check can prove a Done when item.

    Lint, format, and type tools cannot, whatever the exact name: eslint, ruff-format, prettier, tsc,
    bandit, semgrep, shellcheck, hadolint, stylelint, markdownlint.
    A behaviour check is any other name. Prefix behaviour- to force one, as in behaviour-eslint."""
    folded = name.strip().lower()
    if not folded:
        return False
    if folded.startswith("behaviour-") or folded.startswith("behavior-"):
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", folded) if part]
    return not any(part in LINT_TOKENS or part.startswith("lint") for part in parts)


def git(*args: str, cwd: Path | None = None, check: bool = True, code: bool = False, timeout: float | None = None,
        replace: bool = True):
    """Run git. Returns its output, or with `code` its exit code (for questions such as `merge-base --is-ancestor`)."""
    # replace=False reads the stored objects. git --no-replace-objects is the switch for GIT_NO_REPLACE_OBJECTS.
    argv = ["git", *args] if replace else ["git", "--no-replace-objects", *args]
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as err:
        raise Refuse(f"git {' '.join(argv[1:])}: timed out") from err
    if code:
        return proc.returncode
    if check and proc.returncode != 0:
        raise Refuse(f"git {' '.join(argv[1:])}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def common_dir() -> Path:
    try:
        out = git("rev-parse", "--git-common-dir")
    except Refuse:
        raise Refuse(f"{Path.cwd()} is not inside a git repository. Run jtek.py from the ticket's repository "
                     "or its worktree; `start` printed the worktree's path") from None
    return (Path.cwd() / out).resolve()


def state_dir() -> Path:
    override = os.environ.get("JTEK_STATE")
    return Path(override).expanduser().resolve() if override else common_dir() / "jtek"


def main_root(cwd: Path | None = None) -> Path:
    for line in git("worktree", "list", "--porcelain", cwd=cwd).splitlines():
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


def base_ref(base: str) -> str:
    """The base as a full ref when it is a local branch, so a tag with the same name cannot stand in for it."""
    full = f"refs/heads/{base}"
    return full if git("rev-parse", "--verify", "--quiet", full, check=False) else base


def load_config(base: str, cwd: Path | None = None) -> dict:
    """Config from this machine, never from the worktree or from a commit.

    No per-repository file and no $HOME/.jtek/config means the defaults: an empty board and no checks.
    `base` is unused. Callers still pass the branch they are on.
    """
    del base
    path = find_config(cwd)
    if path is None:
        return {"board": "", "setup": "", "checks": {}}
    try:
        config = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise Refuse(f"{path} is not valid JSON: {err}") from err
    if not isinstance(config, dict):
        raise Refuse(f"{path} must be a JSON object")
    return config


def load_checks(base: str) -> dict[str, str]:
    checks = load_config(base).get("checks", {})
    if not isinstance(checks, dict) or not checks:
        if find_config() is None:
            raise Refuse("no jtek config for this repository; run `jtek.py init` or `/jt-init`, fill it in, and give at least one check "
                         "a command. With no config file the board is empty and tickets are files on this machine")
        raise Refuse(f"{config_name()} declares no checks; a ticket needs at least one real check")
    for name, cmd in checks.items():
        if not isinstance(cmd, str) or not cmd.strip():
            raise Refuse(f"check `{name}` in {config_name()} has no command")
    return checks


HEADINGS = ["Goal", "Done when", "Out of scope", "Done check", "Proof", "Context", "Constraints"]


def load_settings(base: str = "", cwd: Path | None = None) -> dict:
    """The optional settings, checked in one place so `doctor` and `start` find a bad value,
    and not the first `check` after the ticket is claimed."""
    config = load_config(base, cwd)
    name = config_name(cwd)
    limit = config.get("max_failed_runs", MAX_FAILED_RUNS)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise Refuse(f"`max_failed_runs` in {name} must be a whole number of at least 1")
    pr_state = config.get("pr_state") or ""
    try:
        shlex.split(pr_state)
    except (ValueError, AttributeError):
        raise Refuse(f'`pr_state` in {name} must be one command as text, such as "python3 scripts/pr-state.py"') from None
    forge_val = config.get("forge")
    if forge_val is None or isinstance(forge_val, bool):
        forge_name = ""
    elif isinstance(forge_val, str) and forge_val.strip().lower() in FORGES:
        forge_name = forge_val.strip().lower()
    else:
        raise Refuse(f'`forge` in {name} must be "gh", "glab", true, or false')
    names = {} if config.get("headings") is None else config["headings"]
    form = '{"Goal": "...", "Done check": "...", "Proof": "...", "Context": "...", "Constraints": "..."}'
    if not isinstance(names, dict) or any(not isinstance(v, str) or not v.strip() for v in names.values()):
        raise Refuse(f"`headings` in {name} must be an object such as {form}")
    unknown = [key for key in names if key not in HEADINGS]
    if unknown:
        raise Refuse(f"`headings` in {name} has the name `{unknown[0]}`. Its names are exactly: {', '.join(HEADINGS)}")
    own = {key: " ".join(value.split()).lower() for key, value in names.items()}
    if len(set(own.values())) != len(own):
        raise Refuse(f"`headings` in {name} gives two headings the same words")
    clash = [key for key, value in own.items() if any(value == other.lower() and other != key for other in HEADINGS)]
    if clash:
        raise Refuse(f"`headings` in {name} names `{clash[0]}` with the English name of another heading")
    return {"max_failed_runs": limit, "pr_state": pr_state.strip(), "forge": forge_name, "headings": own}


# ---- ticket text -----------------------------------------------------------

def fenced(lines: list[str]):
    """Yield (line, inside a code fence). A heading quoted in a fence is text, not a heading."""
    fence = ""
    for line in lines:
        # As in CommonMark: a line such as ```npm test``` is inline code, not the start of a block.
        mark = re.match(r"^ {0,3}(`{3,})[^`]*$|^ {0,3}(~{3,})", line)
        if fence:
            yield line, True
            run = (mark.group(1) or mark.group(2)) if mark else ""
            if run[:1] == fence[0] and len(run) >= len(fence) and not line.strip().strip(fence[0]):
                fence = ""
        elif mark:
            fence = mark.group(1) or mark.group(2)
            yield line, True
        else:
            yield line, False


def parse_ticket(text: str) -> dict:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    repeated: list[str] = []
    title, current = "", None
    # Header lines sit right under the title. The first blank line after one, or the first line of other text,
    # ends them, so a line such as `review: human` in the page's own text grants nothing.
    header = True
    for line, inside in fenced(text.splitlines()):
        if line.startswith("## ") and not inside:
            current = line[3:].strip().lower()
            if current in sections:
                repeated.append(line[3:].strip())
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
        elif inside:
            continue
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            match = re.match(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$", line)
            if match and header:
                fields[match.group(1).strip().lower()] = match.group(2).strip()
            elif line.strip() or fields:
                header = False
    return {"title": title, "fields": fields, "sections": sections, "repeated": repeated}


def squash(text: str) -> str:
    return "".join(text.split()).lower()


def canon_status(value: str) -> str:
    """Notion's own spelling is `In progress`. Accept any case, and refuse a status this board does not have."""
    # FLO's column is `To do`, so spaces are ignored too.
    found = next((s for s in STATUSES if squash(s) == squash(value)), None)
    if value and not found:
        raise Refuse(f"`{value}` is not a status of the board; it has: {', '.join(STATUSES)}")
    return found or ""


def outcome_lines(sections: dict) -> tuple[str, list[str]]:
    """The outcomes live under Done check on a draft card, or under Done when on a page already written that way."""
    present = [name for name in ("done when", "done check") if name in sections]
    if len(present) > 1:
        raise Refuse(
            "the ticket has both `## Done when` and `## Done check`. "
            "A draft puts the outcomes under `## Done check` only"
        )
    name = present[0] if present else "done when"
    label = "Done check" if name == "done check" else "Done when"
    return label, sections.get(name, [])


CARD_SLOTS = ("Goal", "Done check", "Proof", "Context", "Constraints")
SKILL_STEP = re.compile(
    r"(?i)\bjt-[a-z]+\b"
    r"|\b(?:follow|run|use|execute|complete|finish|apply|check|read)\s+(?:the\s+|this\s+|our\s+|a\s+)?(?:skill\s+)?playbook\b"
    r"|\bplaybook\s+steps?\b"
)
GUESSED_LINE = re.compile(r"(?i)^(the )?(cause|fix) is\b|^caused by\b|^fix:")


def guessed_line(line: str) -> bool:
    """A guessed cause or fix. List markers, checkboxes, and emphasis in front of the sentence do not hide it."""
    text = line.strip()
    while True:
        updated = re.sub(r"^(?:[-*+]\s+|\[\s*[xX ]?\s*\]\s*|>\s*|[`*_~]+(?=\S))", "", text)
        if updated == text:
            break
        text = updated.lstrip()
    return bool(GUESSED_LINE.match(text))


def require_card(ticket: dict) -> None:
    """A draft is five slots and nothing else. start still reads a page that uses Done when."""
    sections = ticket["sections"]
    missing = [label for label in CARD_SLOTS if not any(line.strip() for line in sections.get(label.lower(), []))]
    extra = [" ".join(word.capitalize() for word in name.split())
             for name in sections if name not in {label.lower() for label in CARD_SLOTS}]
    if missing or extra:
        raise Refuse(
            "a draft has exactly five slots: Goal, Done check, Proof, Context, Constraints. "
            f"Missing or empty: {', '.join(missing) or '-'}. "
            f"Not a slot: {', '.join(extra) or '-'}. "
            "Outcomes go under Done check. Behaviour that must stay goes under Constraints. "
            "Leave out a guessed cause, a guessed fix, and any step the skills already run."
        )
    for line in sections.get("done check", []):
        if re.match(r"^-\s*\S", line) and SKILL_STEP.search(line):
            raise Refuse(
                "a Done check item is an outcome someone can see, not a step the skills already run: "
                f"{line.strip()[:80]}"
            )
    for lines in sections.values():
        for line in lines:
            if guessed_line(line):
                raise Refuse(
                    "leave the guessed cause or fix out of the draft. Say the goal and the check, not where the bug lives. "
                    f"Not a slot line: {line.strip()[:80]}"
                )


def validate_ticket(ticket: dict, checks: dict[str, str]) -> list[str]:
    sections = ticket["sections"]
    if ticket.get("repeated"):
        raise Refuse(f"the ticket has the heading `{ticket['repeated'][0]}` twice, so it is not clear which one counts. "
                     "The human gives each heading once; an example of a heading goes inside a code block")
    if not any(line.strip() for line in sections.get("goal", [])):
        raise Refuse("ticket has no `## Goal`")
    done_label, done_lines = outcome_lines(sections)
    done = [line for line in done_lines if re.match(r"^-\s*\S", line)]
    if not done:
        raise Refuse(f"ticket has no item under `## {done_label}`")
    other = [line for line in done_lines if line.strip() and not re.match(r"^-\s*\S", line)]
    if other:
        raise Refuse(f"`{done_label}` may hold only top-level list items, one outcome each, because every item must be "
                     f"answered in the evidence. Not an item: {other[0].strip()[:80]}")
    vague = [f"{n}. {line.strip()[1:].strip()[:80]} (`{word}`)"
             for n, line in enumerate(done, 1) if (word := unobservable_word(line))]
    if vague:
        raise Refuse(
            f"`{done_label}` must name something a person can see from outside. These items are a quality with no number, "
            "so they cannot be checked, and `ticket` refuses them before `start`:\n" + "\n".join(vague) + "\n"
            "Name a command, a request, or a screen, with a concrete input and result. A word such as fast, easy, "
            "better, or feels needs a number."
        )
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
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        raise Refuse(f"{path} is damaged; a write was probably interrupted. If it is a ticket's meta.json, run "
                     "`jtek.py release <id>` and start again: the commits stay on the branch. "
                     "Any other file: delete it and run the command that wrote it") from None
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    """Write beside the file and rename, so a killed run never leaves half a file."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


@contextlib.contextmanager
def meta_lock(work: Path):
    """One writer of a ticket's meta.json at a time, so a verdict and a finish never undo each other's write."""
    if fcntl is None:
        yield
        return
    folder = os.open(work, os.O_RDONLY)  # the claim folder itself is the lock: nothing extra to write or clean up
    try:
        fcntl.flock(folder, fcntl.LOCK_EX)
        yield
    finally:
        os.close(folder)


def update_meta(work: Path, **changes) -> dict:
    """Write some keys of meta.json, reading the rest fresh under the lock."""
    with meta_lock(work):
        meta = {**read_json(work / "meta.json"), **changes}
        write_json(work / "meta.json", meta)
    return meta


def load_meta(ticket_id: str, tree: bool = False) -> dict:
    """With `tree`, the worktree must still be there."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if not meta or meta.get("starting"):
        if work_dir(ticket_id).exists():
            raise Refuse(claimed(ticket_id))
        raise Refuse(f"{ticket_id} is not started in this repository ({main_root()}). If the ticket belongs to another "
                     "repository, run the command from there or from the ticket's worktree. Otherwise run `jtek.py start` "
                     "(with the ticket file and page link from the outer loop when this repository has a board)")
    if tree and not Path(meta["worktree"]).is_dir():
        raise Refuse(f"the worktree of {ticket_id} is gone: {meta['worktree']}. Run `jtek.py release {ticket_id}`; "
                     f"the commits are on the branch {meta['branch']}")
    return meta


def head_state(worktree: Path) -> tuple[str, str]:
    """Return the commit and the uncommitted files. Untracked files count: a new file that was
    never added would pass the checks here and be missing from the pull request."""
    sha = git("rev-parse", "HEAD", cwd=worktree)
    return sha, git("status", "--porcelain", cwd=worktree)


CLAIMED = (
    "{id} is already claimed and its session has not ended with a result. Pick another ticket. "
    "If that session died, the human tells a new session to take it over, and that session adds --resume"
)


def starting_now(meta: dict) -> bool:
    """True while the `start` that wrote this claim is still running."""
    try:
        pid = int(meta.get("pid") or 0)
        if not meta.get("starting") or pid <= 0:
            return False
        os.kill(pid, 0)  # signal 0 only asks whether that process is alive
        return True
    except (OSError, ValueError, TypeError):
        return False


def claimed(ticket_id: str) -> str:
    """Why a ticket that has a claim cannot be started now."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if meta.get("worktree") and not meta.get("starting"):
        return CLAIMED.format(id=ticket_id)
    if starting_now(meta):
        return f"another session is starting {ticket_id} right now. Pick another ticket"
    return f"an earlier start of {ticket_id} was interrupted. Run `jtek.py release {ticket_id}`, then start again"


def diff_spec(repo: Path, base: str, head: str, landed: bool = False) -> str:
    """The diff that shows `head`. `base...head` is that change.

    It is empty when `head` is already on the base, which is a squash commit on the base branch.
    Only a commit the caller named as the one that landed (`--at`) then uses that commit's parent
    range. A ticket branch that has not moved is also empty against the base, and its parent range
    would be the base's previous commit, which is not this ticket."""
    spec = f"{base_ref(base)}...{head}"
    if git("diff", "--quiet", spec, cwd=repo, code=True) == 1:
        return spec
    if not landed:
        return ""
    tip = git("rev-parse", "--verify", "--quiet", base_ref(base), cwd=repo, check=False)
    if tip == head:
        # The parent of the tip is only the last commit of a fast-forward. Use that parent only when
        # the reflog, the fork point, or the remote base says the landed range is a single commit.
        return landed_span(repo, base, head)
    return parent_span(repo, head)


def parent_span(repo: Path, head: str, replace: bool = True) -> str:
    if not git("rev-parse", "--verify", "--quiet", f"{head}^", cwd=repo, check=False, replace=replace):
        return ""
    spec = f"{head}^..{head}"
    if git("diff", "--quiet", spec, cwd=repo, code=True, replace=replace) == 1:
        return spec
    return ""


def commit_span(repo: Path, older: str, head: str, replace: bool = True) -> tuple[str, int]:
    """Return the range and how many commits it holds. Empty when older is not an ancestor or the diff is empty."""
    if not older or git("merge-base", "--is-ancestor", older, head, cwd=repo, code=True, replace=replace) != 0:
        return "", 0
    spec = f"{older}..{head}"
    count = git("rev-list", "--count", spec, cwd=repo, check=False, replace=replace)
    if not count.isdigit() or int(count) < 1:
        return "", 0
    if git("diff", "--quiet", spec, cwd=repo, code=True, replace=replace) != 1:
        return "", 0
    return spec, int(count)


def remote_tip(repo: Path, base: str) -> str:
    """The sha ls-remote reports for refs/heads/<base>, or "" when the remote cannot be read.

    refs/remotes/origin/<base> is a local ref. Moving it does not change this sha."""
    try:
        text = git("ls-remote", "origin", f"refs/heads/{base}", cwd=repo, check=False, timeout=60, replace=False)
    except Refuse:
        return ""
    wanted = f"refs/heads/{base}"
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == wanted and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", parts[0]):
            return parts[0]
    return ""


def landed_span(repo: Path, base: str, head: str) -> str:
    """The commits that landed on the current base tip, or "" when that range cannot be named.

    A fast-forward of several commits is not reviewed as only the last commit. The reflog and the
    fork point name the range, including a landing of one commit. With both gone, the sha the remote
    reports is used only when it covers more than the last commit. A remote tip one commit behind is
    the same shape as a one-commit landing and as a longer landing whose remote was moved to HEAD^,
    so the review is refused. A local refs/remotes/origin/<base> is not a source. The walk ignores
    replace refs."""
    ref = base_ref(base)
    local: list[str] = []
    prev = git("rev-parse", "--verify", "--quiet", f"{ref}@{{1}}", cwd=repo, check=False, replace=False)
    if prev:
        local.append(prev)
    fork = git("merge-base", "--fork-point", ref, head, cwd=repo, check=False, replace=False)
    if fork and fork not in local:
        local.append(fork)
    remote = remote_tip(repo, base)
    candidates = list(local)
    if remote and remote not in candidates:
        candidates.append(remote)
    local_one = False
    for candidate in candidates:
        spec, count = commit_span(repo, candidate, head, replace=False)
        if count > 1:
            return spec
        if count == 1 and candidate in local:
            local_one = True
    if local_one:
        return parent_span(repo, head, replace=False)
    return ""


def patch_from(repo: Path, spec: str) -> str:
    """Identify a diff by its content. Hunk positions are left out, so the same edit moved within a file
    still matches, and `--raw` keeps the id of each file's content before and after."""
    diff = subprocess.run(["git", "diff", "--raw", "--patch", "--no-abbrev", "--no-ext-diff", "--no-textconv", "--binary",
                           "--no-renames", spec], cwd=repo, capture_output=True)
    kept = [re.sub(rb"^@@ .*? @@", b"@@", line) for line in diff.stdout.split(b"\n") if not line.startswith(b"index ")]
    return hashlib.sha256(b"\n".join(kept)).hexdigest() if diff.stdout.strip() else ""


def patch_id(worktree: Path, base: str) -> str:
    """Identify the change by its content: the diff, and the content of every file it changes, before and after.
    A rebase keeps the verdict unless the base changed a file this change also touches.
    Whitespace counts: in Python or YAML, an indent is a change of behaviour."""
    if not worktree.is_dir():
        return ""
    spec = diff_spec(worktree, base, "HEAD")
    return patch_from(worktree, spec) if spec else ""


def pull_number(url: str) -> str:
    match = re.search(r"/pull/(\d+)\b", url) or re.fullmatch(r"\s*(\d+)\s*", url)
    return match.group(1) if match else ""


def parse_github_pull(url: str) -> tuple[str, str, str] | None:
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+)/pull/(\d+)\b", url)
    if not match:
        return None
    repo = match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return match.group(1), repo, match.group(3)


def gh_pull_head(url: str) -> str:
    """The head commit `gh` reports for this pull request, or "" when gh cannot say."""
    if not url:
        return ""
    try:
        proc = run_argv(["gh", "pr", "view", url, "--json", "headRefOid", "-q", ".headRefOid"],
                        cwd=main_root(), timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    sha = proc.stdout.strip() if proc.returncode == 0 else ""
    return sha if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) else ""


def resolve_pull_head(repo: Path, number: str, url: str = "") -> str:
    """The commit of pull request `number`, confirmed by a fetch or by gh.

    A local refs/pull/<n>/head or refs/jtek/pull/<n>/head is not the review by itself. Someone can point
    that ref at any commit. A fetch that updates refs/jtek/pull/<n>/head is trusted. Otherwise gh must
    report the same commit as the local ref."""
    stored = f"refs/jtek/pull/{number}/head"
    fetched = False
    try:
        git("fetch", "--quiet", "origin", f"pull/{number}/head:{stored}", cwd=repo, timeout=60)
        fetched = True
    except (Refuse, OSError):
        fetched = False
    fetched_sha = git("rev-parse", "--verify", "--quiet", stored, cwd=repo, check=False) if fetched else ""
    if fetched and fetched_sha:
        return fetched_sha
    local = ""
    for ref in (f"refs/pull/{number}/head", f"refs/remotes/origin/pull/{number}/head", stored):
        sha = git("rev-parse", "--verify", "--quiet", ref, cwd=repo, check=False)
        if sha:
            local = sha
            break
    confirmed = gh_pull_head(url)
    if confirmed and local and confirmed == local:
        return confirmed
    raise Refuse(
        f"refs/pull/{number}/head is not confirmed. A local ref is not the review until "
        f"`git fetch origin pull/{number}/head` succeeds, or `gh` reports the same commit as that ref. "
        "Fetch it, or pass --at <the commit that landed on the base>."
    )


def review_target(meta: dict, pr: str = "", at: str = "") -> tuple[Path, str, str, str]:
    """Where a review reads the change when the worktree is gone, or when the caller names a pull request
    or the commit that landed. Returns (repo, full commit, diff spec, a short note for the session)."""
    worktree = Path(meta["worktree"])
    repo = worktree if worktree.is_dir() else main_root()
    if at:
        head = git("rev-parse", "--verify", "--quiet", at, cwd=repo, check=False)
        if not head:
            raise Refuse(f"--at `{at}` is not a commit in this repository")
        spec = diff_spec(repo, meta["base"], head, landed=True)
        if not spec:
            raise Refuse(
                f"{head[:7]} has no diff against {meta['base']} and no parent range. "
                "A fast-forward of several commits is not reviewed as only the last commit. "
                "The reflog, or the sha the remote reports for " + meta["base"] + ", has to name the whole range. "
                "A local origin/" + meta["base"] + " does not. There is nothing to review at that commit."
            )
        return repo, head, spec, f"parent range of {head[:7]}"
    number = pull_number(pr or meta.get("pr") or "")
    if not number:
        gone = meta["worktree"]
        raise Refuse(
            f"the worktree of {meta.get('id', 'this ticket')} is gone: {gone}. "
            "Pass --pr <pull request link> to review refs/pull/<n>/head, or --at <the commit that landed> "
            "to review that commit's parent range. A squash commit compared with the base is an empty diff; "
            "the parent range is the change."
        )
    head = resolve_pull_head(repo, number, pr or meta.get("pr") or "")
    spec = diff_spec(repo, meta["base"], head)
    if not spec:
        raise Refuse(
            f"refs/pull/{number}/head ({head[:7]}) has an empty diff against {meta['base']}, "
            "which happens when those commits are already on the base. "
            f"Pass --at <the commit that landed> to review its parent range."
        )
    return repo, head, spec, f"refs/pull/{number}/head"


def ticket_id_of_text(work: Path) -> str:
    """Identify what the ticket asks for, so that a ticket the human changed needs new evidence and a new verdict."""
    sections = parse_ticket((work / "ticket.md").read_text())["sections"]
    # Only what the ticket asks for counts: an answer added under Notes, or a blank line, is not a new ticket.
    asked = {name: [" ".join(line.split()) for line in sections.get(name, []) if line.strip()]
             for name in ("goal", "done when", "done check", "out of scope", "proof", "context", "constraints")}
    return hashlib.sha256(json.dumps(asked, sort_keys=True).encode()).hexdigest()


def current_verdict(ticket_id: str, meta: dict) -> dict:
    """The verdict, when it is for the change and the ticket as they are now."""
    work = work_dir(ticket_id)
    verdict = read_json(work / "verdict.json")
    worktree = Path(meta["worktree"])
    if (not verdict.get("verdict") or not worktree.is_dir() or verdict.get("patch") != patch_id(worktree, meta["base"])
            or verdict.get("ticket") != ticket_id_of_text(work)):
        return {}
    return verdict


def needs_verdict(meta: dict) -> bool:
    """The human may waive the review for a small ticket, but not for one that touches files that decide whether checks pass."""
    if attention(meta) != "-":
        return True
    return not local_one_file(meta) and bool(meta.get("review"))


def local_one_file(meta: dict) -> bool:
    """Work without a ticket that changed one file, none of which decides a check, needs no second session."""
    if not meta.get("local") or not Path(meta["worktree"]).is_dir():
        return False
    changed = git("diff", "--name-only", f"{base_ref(meta['base'])}...HEAD", cwd=Path(meta["worktree"]), check=False)
    return len(changed.splitlines()) == 1


DIRTY_HINT = "commit them, or add build output to .gitignore"


def bullet_items(lines: list[str]) -> list[str]:
    return [m.group(1).strip() for line in lines if (m := re.match(r"^-\s*(\S.*)$", line))]


def done_when_items(work: Path) -> list[str]:
    """Outcomes under Done when, and under Done check when that list has items too.

    A blank `## Done when` is not a list. It must not hide the Done check items, or finish
    would accept evidence with no `seen:` line and no broke proof."""
    sections = parse_ticket((work / "ticket.md").read_text())["sections"]
    items: list[str] = []
    for name in ("done when", "done check"):
        found = bullet_items(sections.get(name, []))
        if found:
            items.extend(found)
    return items


TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "__tests__", "__specs__"})
TEST_TOKENS = frozenset({"test", "tests", "spec", "specs"})


def is_test_path(path: str) -> bool:
    parts = [p for p in re.split(r"[/\\]+", path.strip()) if p]
    if not parts:
        return False
    if any(part.lower() in TEST_DIRS for part in parts[:-1]):
        return True
    name = parts[-1]
    tokens = [tok for tok in re.split(r"[._-]+", name.lower()) if tok]
    if any(tok in TEST_TOKENS for tok in tokens):
        return True
    stem = name.split(".", 1)[0]
    return bool(re.search(r"(?:^Test[A-Z]|[a-z0-9](?:Tests?|Specs?)$)", stem))


def stale_seen(work: Path, worktree: Path, text: str) -> list[str]:
    """`seen:` lines whose every run predates the code as it is now, or ran over uncommitted files.
    Only reported: a run before a change to tests or documents still stands."""
    found = []
    changed_since: dict[str, bool] = {}

    def code_changed(sha: str) -> bool:
        if sha not in changed_since:
            names = git("diff", "--name-only", sha, "HEAD", cwd=worktree, check=False).splitlines()
            changed_since[sha] = any(
                not is_test_path(name) and not name.lower().endswith((".md", ".rst"))
                and not (name.lower().endswith(".txt") and "requirements" not in name.lower())
                for name in names)
        return changed_since[sha]

    for item, line in re.findall(r"^\s*([0-9]+)\.\s*(seen:.*)$", text, re.M):
        runs = [run for run in (read_run(work, n) for n in cited_runs(line)) if run]
        # A run somewhere else, such as the base, is not a run of this change.
        here = [run for run in runs if WORKTREE_COMMIT not in run.get("commit", "") and run.get("commit")]
        if not here:
            continue
        if all("(with uncommitted files)" in run["commit"] for run in here):
            found.append(f"item {item} rests on a run with uncommitted files")
        elif all(code_changed(run["commit"].split()[0]) for run in here):
            found.append(f"item {item} rests on a run before the last code change")
    return found


def attention(meta: dict) -> str:
    """Name what the human should look at before the diff: files that decide whether checks pass."""
    worktree = Path(meta["worktree"])
    if not worktree.is_dir():
        return "-"
    span = f"{base_ref(meta['base'])}...HEAD"
    # A rename is shown as a deletion and an addition, so a renamed test that lost lines is still seen.
    changed = git("-c", "core.quotePath=false", "diff", "--no-renames", "--name-only", span, cwd=worktree, check=False).splitlines()
    deleted = git("-c", "core.quotePath=false", "diff", "--no-renames", "--name-only", "--diff-filter=D", span, cwd=worktree, check=False).splitlines()
    try:
        config = load_config(meta["base"])
    except Refuse:
        config = {}
    commands = dict(config.get("checks", {})) if isinstance(config.get("checks"), dict) else {}
    for key in ("setup", "pr_state"):
        if config.get(key):
            commands[key] = config[key]
    run_by: dict[str, str] = {}
    for name, command in commands.items():
        try:
            tokens = shlex.split(str(command))
        except ValueError:
            continue
        for token in tokens:
            run_by.setdefault(token.removeprefix("./"), name)
    extra = config.get("watch") or []
    watch = SENSITIVE + [w for w in ([extra] if isinstance(extra, str) else extra if isinstance(extra, list) else [])
                         if isinstance(w, str)]
    removed: dict[str, int] = {}
    for line in git("-c", "core.quotePath=false", "diff", "--no-renames", "--numstat", span, cwd=worktree, check=False).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit():
            removed[parts[2]] = int(parts[1])
    notes = []
    for path in changed:
        is_test = is_test_path(path)
        if path in run_by:
            notes.append(f"{path} (run by `{run_by[path]}`)")
        elif any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern) for pattern in watch):
            notes.append(path)
        elif path in deleted and is_test:
            notes.append(f"{path} (test deleted)")
        elif is_test and removed.get(path):
            # Adding tests is normal. Removing or rewriting lines of an existing test is how a check gets weakened.
            notes.append(f"{path} ({removed[path]} test lines removed or changed)")
    return ", ".join(notes) or "-"


def board_line(outcome: str, waiting: str = "", pr: str = "") -> str:
    """What the outer loop must write on the ticket's page (or the session in a local file with no board). `-` means nothing."""
    if outcome == "review":
        return "Status=Review; Waiting=; " + (f"PR={public_url(pr)}; " if pr else "") + "comment=result+evidence"
    if outcome == "needs-human":
        return f"Waiting={waiting}; comment=result"
    # A pull request that waits for its second look is still worth a link on the page.
    return f"PR={public_url(pr)}" if pr else "-"


def write_result(ticket_id: str, outcome: str, status: str, note: str = "", waiting: str = "") -> str:
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    checks = read_json(work / "checks.json")
    verdict = current_verdict(ticket_id, meta)
    check_line = " ".join(f"{r['name']}={r['status']}" for r in checks.get("results", [])) or "not run"
    if checks.get("sha"):
        check_line += f" @{checks['sha'][:7]}"
    evidence = "-"
    if (work / "evidence.md").exists():
        text = (work / "evidence.md").read_text()
        seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
        not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
        backed = len([line for line in re.findall(r"^\s*\d+\.\s*seen:.*$", text, re.M) if cited_runs(line)])
        evidence = f"{work / 'evidence.md'} ({seen} seen, {not_run} not run, {backed} of the seen cite a recorded run"
        cleanup = re.search(r"^\s*(-\s*)?clean-up:.*$", text, re.M | re.I)
        diff_runs = cited_runs(cleanup.group(0)) if cleanup else []
        read_diff = any(re.match(r"^git( -C \S+)? diff \S", run.get("command", "")) and run.get("exit") == "0"
                        and run.get("stdout", "").strip()
                        for run in (read_run(work, n) for n in diff_runs))
        evidence += ", clean-up rests on a recorded diff" if read_diff else ", clean-up cites no recorded diff"
        if Path(meta["worktree"]).is_dir():
            evidence += "".join(f", {stale}" for stale in stale_seen(work, Path(meta["worktree"]), text))
        evidence += ")"
    attached = sorted(p.name for p in (work / "evidence").glob("*")) if (work / "evidence").is_dir() else []
    if attached:
        evidence += f" (+{len(attached)} attached in {work / 'evidence'})"
    verdict_line = "none" if needs_verdict(meta) else "skipped: work without a ticket that changed one file" \
        if local_one_file(meta) else "waived by the ticket"
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
        f"pr: {public_url(str(meta.get('pr') or '-'))}",
        f"ci: {meta.get('ci') or '-'}",
        f"evidence: {evidence}",
        f"attention: {attention(meta)}",
        f"branch: {meta['branch']}",
        f"source: {meta['source']}",
        f"note: {' '.join(note.split()) or '-'}",
        f"board: {'-' if meta.get('local') else board_line(outcome, waiting, meta.get('pr', ''))}",
    ]
    if "comment=" in lines[-1]:
        # The comment the board line asks for, ready to paste as it is, so nobody has to put it together or cut it.
        lines.insert(-1, f"comment file: {work / 'board-comment.md'}")
    text = "\n".join(lines) + "\n"
    (work / "result.md").write_text(text)
    if "comment=" in lines[-1]:
        evidence_text = (work / "evidence.md").read_text() if (work / "evidence.md").exists() else ""
        (work / "board-comment.md").write_text(text + ("\n" + evidence_text if "comment=result+evidence" in lines[-1] else ""))
    return text


WORKTREES_EXCLUDE = ".claude/worktrees/"


def ticket_paths(ticket_id: str) -> tuple[Path, str]:
    root = main_root()
    return root / ".claude" / "worktrees" / ticket_id, f"jtek/{ticket_id}"


def exclude_worktrees() -> None:
    """Add .claude/worktrees/ to .git/info/exclude once, without editing any tracked file."""
    root = main_root()
    # Not named `raw`: `env_int` assigns `raw` from os.environ.get, and the scanner joins names across functions.
    git_exclude = git("rev-parse", "--git-path", "info/exclude", cwd=root)
    if not git_exclude:
        raise Refuse("git did not name an info/exclude path for this repository")
    exclude_file = root / git_exclude
    try:
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        with meta_lock(exclude_file.parent):
            text = exclude_file.read_text(errors="replace") if exclude_file.exists() else ""
            if any(line.strip() in (WORKTREES_EXCLUDE, WORKTREES_EXCLUDE.rstrip("/")) for line in text.splitlines()):
                return
            prefix = "\n" if text and not text.endswith("\n") else ""
            with open(exclude_file, "a", encoding="utf-8") as handle:
                handle.write(f"{prefix}{WORKTREES_EXCLUDE}\n")
    except OSError as err:
        raise Refuse(f"cannot write {exclude_file} to exclude {WORKTREES_EXCLUDE}: {err}") from None


def cmd_other(args: argparse.Namespace) -> None:
    """Commands for the human and the launcher live in launcher.py and doctor.py beside this file.
    The copy of this file in the jt-review skill does not have them."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import launcher
    except ImportError:
        raise Refuse(f"`{args.command}` is in launcher.py, in the scripts folder of the jt-work skill; run jtek.py from there") from None
    launcher.COMMANDS[args.command](sys.modules[__name__], args)


# ---- commands --------------------------------------------------------------

def refresh_base(base: str) -> str:
    """Bring the local base branch up to what the remote has, so a ticket starts from what is merged.
    Returns a note for the session, or "". Never rewrites history: only a fast-forward, and only when it is safe."""
    if not git("rev-parse", "--verify", "--quiet", f"refs/heads/{base}", check=False):
        return ""  # the base is not a local branch (JTEK_BASE names something else)
    if "origin" not in git("remote", check=False).split():
        return ""
    try:
        fetched = subprocess.run(["git", "fetch", "--quiet", "origin", base], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        fetched = None
    if fetched is None or fetched.returncode != 0:
        return f"note: could not fetch `{base}` from origin, so the ticket starts from the local `{base}`, which may be old"
    remote = f"refs/remotes/origin/{base}"
    if not git("rev-parse", "--verify", "--quiet", remote, check=False):
        return ""
    behind = int(git("rev-list", "--count", f"refs/heads/{base}..{remote}", check=False) or 0)
    ahead = int(git("rev-list", "--count", f"{remote}..refs/heads/{base}", check=False) or 0)
    if not behind:
        return ""
    if ahead:
        return (f"note: the local `{base}` and origin/{base} have each moved ({ahead} and {behind} commits), "
                f"so the ticket starts from the local `{base}`. The human brings them together")
    # Where is the base checked out? A branch that is checked out moves only by a merge in that worktree.
    holder, path = None, None
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{base}":
            holder = path
    if holder is None:
        moved = subprocess.run(["git", "update-ref", f"refs/heads/{base}", remote], capture_output=True, text=True)
    else:
        moved = subprocess.run(["git", "merge", "--quiet", "--ff-only", remote], cwd=holder, capture_output=True, text=True)
    if moved.returncode != 0:
        raise Refuse(
            f"`{base}` is {behind} commits behind origin/{base}, and it could not be moved forward"
            + (f" in {holder}" if holder else "") + f": {' '.join((moved.stderr or moved.stdout).split())}. "
            f"The human updates `{base}` (`git pull --ff-only`); a ticket must start from what is merged"
        )
    return f"note: `{base}` was {behind} commits behind origin/{base} and was moved forward before the ticket started"


def ticket_folders() -> list[Path]:
    """Every place a ticket file may be, later entries winning on the same id.

    New files go to the last folder: the origin id when this clone has an origin, otherwise the
    checkout's path id. A folder from before the origin was added is still read. So is the old
    folder beside the repository, `<name>.jtek/_tickets`.
    """
    folders = [legacy_tickets_dir()]
    homes = candidate_homes()
    # Prefer the write folder last so it wins. candidate_homes already lists the origin id first.
    for home in reversed(homes):
        folders.append(home / "tickets")
    return folders


def tickets_dir() -> Path:
    """Where new ticket files are written, when the config names no board.

    On this machine, at $HOME/.jtek/repos/<repo id>/tickets. The repository is not touched.
    A second checkout of the same origin on this machine sees the same files. A new machine does not,
    until someone copies that folder or runs `jtek.py migrate` there.
    """
    return repo_home() / "tickets"


def legacy_tickets_dir() -> Path:
    """The old place, beside the repository. Still read, so a ticket saved before the move is not lost."""
    root = main_root()
    return root.parent / f"{root.name}.jtek" / TICKETS


def ticket_file(ticket_id: str) -> Path:
    """The file for this id. The write folder wins, then any earlier folder, then the old folder beside the repo."""
    found = tickets_dir() / f"{ticket_id}.md"
    for folder in reversed(ticket_folders()):
        path = folder / f"{ticket_id}.md"
        if path.is_file():
            return path
    return found


def iter_ticket_files() -> list[Path]:
    """Every ticket file. The write folder wins when two folders have the same id."""
    found: dict[str, Path] = {}
    for folder in ticket_folders():
        if not folder.is_dir():
            continue
        for path in folder.glob("*.md"):
            found[path.stem] = path
    return [found[key] for key in sorted(found)]


def has_board(base: str) -> bool:
    return bool(str(load_config(base).get("board") or "").strip())


def file_status(ticket_id: str) -> str:
    """The status a ticket file shows, or an empty string when there is no such file or it cannot be read."""
    if not ID_RE.match(ticket_id):
        return ""
    try:
        path = ticket_file(ticket_id)
        if not path.is_file():
            return ""
        return canon_status(parse_ticket(path.read_text())["fields"].get("status", ""))
    except (OSError, ValueError, Refuse):
        return ""


def open_after(value: str) -> list[str]:
    """The ids of an `after:` line that are not Done. A board hands over only those; a ticket file keeps the line
    as it was written, so each id is looked up."""
    return [dep for dep in (part.strip() for part in value.split(",")) if dep and file_status(dep) != "Done"]


def next_free(prefix: str) -> str:
    """The next free id with this prefix. A released ticket keeps its branch, so its number is never given out again.

    A remote-tracking ref refs/remotes/*/jtek/<id>, a tag refs/tags/jtek/<id>, and an id named in any
    commit subject or body are taken too. Deleting the local branch does not make that id free."""
    taken = [p.name for p in (state_dir() / "work").glob(f"{prefix}-*")]
    for folder in ticket_folders():
        if folder.is_dir():
            taken += [p.stem for p in folder.glob(f"{prefix}-*.md")]
    refs = git("for-each-ref", "--format=%(refname)", "refs/heads/jtek/", "refs/remotes", "refs/tags", check=False)
    for ref in refs.split():
        if "/jtek/" in ref:
            taken.append(ref.rsplit("/", 1)[-1])
    taken += re.findall(rf"\b{prefix}-\d+\b", git("log", "--all", "--format=%s%n%b", check=False))
    numbers = [int(m.group(1)) for m in (re.match(rf"^{prefix}-([0-9]+)$", name) for name in taken) if m]
    return f"{prefix}-{max(numbers, default=0) + 1}"


def next_local_id() -> str:
    return next_free("LOCAL")


def save_ticket(text: str) -> Path:
    """Keep a checked draft as a ticket file. The id is the script's and the status is Backlog, whatever the draft
    says: only the human releases a ticket, by writing `status: Todo` in the file.

    Header fields are kept across a blank line in the draft. A saved file whose repo was dropped is deleted
    and refused, so a later start cannot run in the wrong repository."""
    lines = text.splitlines()
    title_at = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if title_at is None:
        raise Refuse("the ticket has no `# <title>` line")
    body_at = next((i for i in range(title_at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    fields: dict[str, str] = {}
    extra: list[str] = []
    for line in lines[title_at + 1:body_at]:
        match = re.match(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$", line)
        key = match.group(1).strip().lower() if match else ""
        if key in ("id", "status"):
            continue  # the script writes these; a draft cannot choose them
        if match:
            fields[key] = match.group(2).strip()
        elif line.strip() and not line.startswith("#"):
            extra.append(line)
    draft_repo = fields.get("repo", "")
    saved_lines = [lines[title_at], "id: {id}", "status: Backlog"]
    for key in ("kind", "area", "repo"):
        if fields.get(key):
            saved_lines.append(f"{key}: {fields[key]}")
    for key, value in fields.items():
        if key not in ("kind", "area", "repo", "id", "status") and value:
            saved_lines.append(f"{key}: {value}")
    if extra:
        saved_lines += ["", *extra]
    body = lines[body_at:]
    if body:
        if saved_lines[-1] != "":
            saved_lines.append("")
        saved_lines += body
    folder = tickets_dir()
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        ticket_id = next_free("T")
        path = folder / f"{ticket_id}.md"
        written = "\n".join(saved_lines).replace("{id}", ticket_id, 1) + "\n"
        try:
            with open(path, "x") as handle:  # two sessions that save at once cannot both get this id
                handle.write(written)
        except FileExistsError:
            continue
        saved_repo = parse_ticket(written)["fields"].get("repo", "")
        if draft_repo and saved_repo != draft_repo:
            path.unlink(missing_ok=True)
            raise Refuse(
                f"the saved ticket dropped repo `{draft_repo}`. A blank line must not split the header. "
                "The file was not kept."
            )
        return path


def local_ticket(text: str) -> str:
    """A ticket the session wrote for work without one. Its header grants nothing: no waived review, no subset of
    checks, no order after another ticket. Only the id it was given before, for picking it up again, is kept."""
    ticket = parse_ticket(text)
    given = ticket["fields"].get("id", "")
    if given and not LOCAL_RE.match(given):
        raise Refuse(f"a local ticket has no id of its own, or the `LOCAL-<n>` id `start --local` gave it; not `{given}`")
    if given and not work_dir(given).exists():
        raise Refuse(f"{given} was never started here; leave `id:` out, and `start --local` gives the ticket a new one")
    header = [f"id: {given or next_local_id()}", "status: Todo", f"kind: {ticket['fields'].get('kind', '')}"]
    first = re.search(r"^## ", text, re.M)
    body = text[first.start():] if first else ""
    return f"# {ticket['title'] or 'Local work'}\n" + "\n".join(header) + "\n\n" + body


def existing_test_file(token: str) -> bool:
    """True when `token` is a test or spec file inside this repository."""
    if not token or "://" in token or token.startswith("~"):
        return False
    root = main_root().resolve()
    try:
        path = (root / token).resolve()
    except OSError:
        return False
    if path != root and root not in path.parents:
        return False
    if not path.is_file():
        return False
    return is_test_path(path.relative_to(root).as_posix())


def lesson_kind(enforced_by: str) -> str:
    """architecture, type, lint (only when the text says what to use instead), test, or prose.

    A repeat is one of these shapes, and nothing looser:
    `architecture: <target>`, `type: <target>`, `lint <rule>: use <replacement>`,
    or `test: <path>` / `check: <path>` where the path is an existing test file.
    """
    text = " ".join(enforced_by.lower().split())
    if not text or text in {"prose", "not yet", "warning", "reminder", "note", "written", "docs"}:
        return "prose"

    def target_of(prefix: str) -> str:
        if text.startswith(prefix + ":"):
            return text[len(prefix) + 1:].strip()
        if text.startswith(prefix + " "):
            return text[len(prefix) + 1:].strip()
        return ""

    if target_of("architecture"):
        return "architecture"
    target = target_of("type")
    if target and re.match(r"[a-z_][a-z0-9_.]*\b", target):
        return "type"
    if text.startswith("lint:") or text.startswith("lint "):
        if any(mark in text for mark in ("use ", "instead", "error:", "fix:", "says ")):
            return "lint"
        return "lint-silent"
    if text.startswith("test:") or text.startswith("test ") or text.startswith("check:") or text.startswith("check "):
        rest = re.sub(r"^(?:test|check)\s*:?\s*", "", text, count=1)
        token = rest.split()[0] if rest.split() else ""
        if existing_test_file(token):
            return "test"
    return "prose"


def cmd_lesson(args: argparse.Namespace) -> None:
    """The first record of a mistake may be prose. The same mistake again must name a structural rule."""
    mistake = " ".join(args.mistake.split())
    if not mistake:
        raise Refuse("lesson needs --mistake: one sentence, what was done and what should have been done")
    key = mistake.lower()
    kind = lesson_kind(args.enforced_by or "")
    if kind == "lint-silent":
        raise Refuse(
            "a lint rule has to say how to fix the mistake, and the error says how to fix it. "
            "Pass --enforced-by with the replacement, such as `lint no-float-money: use Cents instead`"
        )
    path = state_dir() / "lessons.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json(path)
    lessons = data.get("lessons")
    if not isinstance(lessons, list):
        lessons = []
    prior = [row for row in lessons if isinstance(row, dict) and row.get("key") == key]
    if prior and kind == "prose":
        raise Refuse(
            "this mistake was already recorded, so a prose lesson is refused. "
            "A repeat needs a structural rule, strongest first: architecture (make the wrong shape impossible), "
            "then a type, then a lint rule whose error says what to use instead, then a test. "
            f"Pass --enforced-by with that rule. The earlier record was: {prior[-1].get('enforced_by', 'prose')}"
        )
    row = {"key": key, "mistake": mistake, "enforced_by": " ".join((args.enforced_by or "prose").split()),
           "kind": kind, "times": len(prior) + 1}
    lessons.append(row)
    write_json(path, {"lessons": lessons})
    if prior:
        print(f"lesson: structural ({kind}), time {row['times']}. "
              f"Put this enforcer on the row in {repo_home() / 'rules.md'}, in the ticket that adds it.")
    else:
        print(f"lesson: recorded ({kind}). The same mistake again needs a structural rule, not prose.")


def cmd_ticket(args: argparse.Namespace) -> None:
    """Check a drafted ticket the way start will, without claiming anything."""
    try:
        ticket = parse_ticket(Path(args.file).read_text())
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the ticket file as text: {err}") from None
    base = base_branch()
    validate_ticket(ticket, load_checks(base))
    repo = ticket["fields"].get("repo", "")
    here = str(load_config(base).get("name") or main_root().name)
    if repo and repo != here:
        raise Refuse(f"the ticket is for `{repo}`; check it in that repository, this one is `{here}`")
    require_card(ticket)
    label, lines = outcome_lines(ticket["sections"])
    items = sum(1 for line in lines if re.match(r"^-\s*\S", line))
    if args.save and has_board(base):
        raise Refuse(f"this repository has a board (`board` in {CONFIG}); leave the draft file for the outer loop to create the ticket there")
    print(f"ticket: ok, {items} item(s) under {label}, as start will read it")
    if args.save:
        path = save_ticket(Path(args.file).read_text())
        print(f"saved: {path}  (Backlog, on this machine in {tickets_dir()}. "
              "The human releases it by writing `status: Todo` in that file)")


def read_ticket_file(path: str) -> str:
    try:
        return Path(path).read_text()
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the ticket file as text: {err}") from None


def cmd_start(args: argparse.Namespace) -> None:
    if not session_identity():
        raise Refuse(SESSION_MISSING)
    text = read_ticket_file(args.from_file) if args.from_file else ""
    if args.local:
        if not args.from_file:
            raise Refuse("--local needs --from-file: the ticket file the session wrote")
        text = local_ticket(text)
    elif not args.ref:
        raise Refuse("name the ticket's page link, or pass --local for work that has no ticket")
    base = base_branch()
    # Before anything is read from the base: the checks and the settings come from it too.
    base_note = "" if args.no_fetch else refresh_base(base)
    page = None
    if not args.from_file:
        # Without a board the tickets are files, and the id alone names one.
        if has_board(base):
            raise Refuse("pass --from-file: the ticket file the outer loop read from the board and saved in the ticket format")
        page = ticket_file(check_id(args.ref))
        if not page.is_file():
            raise Refuse(f"there is no ticket file {page}. This repository has no board, so its tickets are files in "
                         f"{tickets_dir()} (older ones are still read from {legacy_tickets_dir()}). "
                         "For work that has no ticket, pass --local")
        text = read_ticket_file(str(page))
    english = {own: name for name, own in load_settings(base)["headings"].items()}
    if english:
        # The copy the session works from always has the three English headings, whatever the page calls them.
        lines = [f"## {english[' '.join(line[2:].split()).lower()]}"
                 if re.match(r"^##[ \t]", line) and not inside and " ".join(line[2:].split()).lower() in english else line
                 for line, inside in fenced(text.splitlines())]
        text = "\n".join(lines) + "\n"
    ticket = parse_ticket(text)
    fields = ticket["fields"]
    ticket_id = check_id(fields.get("id", ""))
    if page and ticket_id != args.ref:
        raise Refuse(f"{page} says `id: {ticket_id}`, not `{args.ref}`; the file's name and its id must be the same")
    if LOCAL_RE.match(ticket_id) and not args.local:
        raise Refuse(f"`{ticket_id}` is a local id; only `start --local` uses one")
    declared = load_checks(base)
    # A local ticket runs every declared check: the session that wrote it cannot pick a subset.
    selected = list(declared) if args.local else validate_ticket(ticket, declared)
    wanted_repo = fields.get("repo", "")
    this_repo = str(load_config(base).get("name") or main_root().name)
    if wanted_repo and wanted_repo != this_repo:
        raise Refuse(
            f"{ticket_id} is for the repository `{wanted_repo}`, and this one is `{this_repo}`. "
            "Start the session in that repository"
        )
    status = canon_status(fields.get("status", ""))
    waiting = fields.get("waiting", "")
    work = work_dir(ticket_id)
    # A claim is parked once its session ended with a result. A parked claim can be picked up again.
    parked = (work / "result.md").exists()

    baseline = asked = ""
    known_red_lines: list[str] = []
    followup_id = followup_path = followup_board = ""
    if args.resume or parked:
        meta = load_meta(ticket_id, tree=True)
        if status not in ("Todo", "In Progress"):
            raise Refuse(f"{ticket_id} is `{status}`; only a ticket in Todo or In Progress can resume")
        try:
            asked = parked and "outcome: needs-human" in (work / "result.md").read_text()
        except FileNotFoundError:  # another session picked it up between the two lines
            raise Refuse(CLAIMED.format(id=ticket_id)) from None
        if args.local and asked and not args.answered:
            # A local ticket has no board, so its `status: Todo` is the script's own and says nothing about the human.
            raise Refuse(f"{ticket_id} stopped with a question. When the human has answered it in the chat, start again "
                         "with --answered. A session never adds it on its own")
        if (asked or waiting) and status != "Todo":
            # Only the human sets Todo, so a ticket that stopped with a question cannot be restarted by a session.
            raise Refuse(f"{ticket_id} stopped with a question. The human answers on the page and sets Status to Todo")
        fails_now = int(meta.get("fails") or 0)
        # A question the human released, on a board, is the only thing that starts the FAIL count again.
        # `--answered` does not: it only says the human replied in the chat, and it must not open a fourth round.
        if fails_now >= 3 and not (status == "Todo" and asked and not args.local):
            raise Refuse(
                f"{ticket_id} has had {fails_now} FAIL verdicts. Stop with `jtek.py stop {ticket_id} --waiting input`: "
                "the ticket or the reviewer's standard needs the human. `--answered` does not start another round. "
                "On a board, the human answers on the page and sets Status to Todo; that is the only reset. "
                "A local ticket has no reset: start a new one."
            )
        if parked:
            try:
                # A rename happens once, so two sessions cannot both pick up the same parked ticket.
                (work / "result.md").rename(work / "last-result.md")
            except FileNotFoundError:
                raise Refuse(CLAIMED.format(id=ticket_id)) from None
            last = (work / "last-result.md").read_text()
            if "outcome: needs-human" in last:
                # The session that picks the ticket up must not have to open the state folder to learn what was asked.
                asked = next((line[6:].strip() for line in last.splitlines() if line.startswith("note: ")), "")
        checks_path = work / "checks.json"
        if checks_path.exists() and status == "Todo" and not args.local:
            # Only the human sets Todo, so only the human gives a ticket new tries.
            write_json(checks_path, {**read_json(checks_path), "failed_runs": 0})
        if status == "Todo" and asked and not args.local:
            # The human answered a question and released the ticket again: the FAIL rounds start over.
            meta = {**meta, "fails": 0, "failed_commits": [], "ci_fail_shas": []}
        resumed = True
    else:
        resumed = False
        if work.exists():
            raise Refuse(claimed(ticket_id))
        if status != "Todo":
            raise Refuse(f"{ticket_id} is `{status or 'unset'}`, not Todo; the human releases a ticket by setting Status to Todo")
        after = ", ".join(open_after(fields.get("after", ""))) if page else fields.get("after")
        if after:
            raise Refuse(f"{ticket_id} comes after {after}, which is not Done")
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            work.mkdir()  # atomic claim: the second session to try loses
        except FileExistsError:
            raise Refuse(claimed(ticket_id)) from None
        try:
            exclude_worktrees()
        except BaseException:
            work.rmdir()
            raise
        worktree, branch = ticket_paths(ticket_id)
        # A branch left by `release` holds earlier work on this ticket. Go on from it, and never delete it.
        kept = bool(git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False))
        if kept and git("rev-list", "--count", f"{base_ref(base)}..refs/heads/{branch}", check=False) == "0" and \
                git("merge-base", "--is-ancestor", f"refs/heads/{branch}", base_ref(base), code=True) == 0:
            # A kept branch with no commit of its own holds no work: bring it to the base, so the ticket
            # starts from what is merged, and treat it as new. Nothing is lost: its commit is in the base.
            git("update-ref", f"refs/heads/{branch}", git("rev-parse", base_ref(base)))
            kept = False
        # From here on a killed run leaves a claim that says so, and `release` can remove what it made.
        write_json(work / "meta.json", {"starting": True, "pid": os.getpid(), "kept": kept, "base": base})
        worktree.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                git("worktree", "prune")  # forget a worktree whose folder was deleted by hand
                # A failed try may have left the branch behind, so look again each time.
                exists = bool(git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False))
                git("worktree", "add", *([str(worktree), branch] if exists else ["-b", branch, str(worktree), base_ref(base)]))
                break
            except Refuse:
                # Two tickets that start in the same moment can trip over each other inside git. Try again before giving up.
                if attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                if not kept:
                    git("branch", "-D", branch, check=False)
                (work / "meta.json").unlink()
                work.rmdir()
                raise
        source = "local, written by the session" if args.local else str(page) if page else " ".join(args.ref.split())
        meta = {"id": ticket_id, "source": source, "local": bool(args.local), "base": base, "worktree": str(worktree), "branch": branch, "pr": ""}
        write_json(work / "meta.json", {**meta, "starting": True, "pid": os.getpid(), "kept": kept})
        logs = state_dir() / "baseline" / ticket_id

        def undo() -> None:
            git("worktree", "remove", "--force", str(worktree), check=False)
            if not kept:
                git("branch", "-D", branch, check=False)
            for path in sorted(work.rglob("*"), reverse=True):
                path.rmdir() if path.is_dir() else path.unlink()
            work.rmdir()

        def give_back(reason: str, log: Path) -> Refuse:
            undo()
            return Refuse(f"{reason}, so {ticket_id} was not started and is still Todo.\nlog: {log}\n{log_tail(log)}")

        setup = load_config(base).get("setup", "")
        if isinstance(setup, str) and setup.strip():
            # A new worktree has no installed dependencies. Install them before anything runs.
            if not run_command(setup, worktree, logs / "setup.log", ticket_id=ticket_id, use_verify_override=False):
                raise give_back(f"the setup command from {CONFIG} failed in the new worktree", logs / "setup.log")
        baseline = "skipped, because the work goes on from an existing branch" if kept else "skipped (--no-baseline)"
        if not args.no_baseline and not kept:
            # A check that is already red on the base is not this ticket's to fix. Find out before any edit.
            # One green run per base commit and command set is enough, so parallel tickets do not repeat it.
            base_sha = git("rev-parse", base_ref(base))
            key = hashlib.sha256(json.dumps([base_sha, [(n, declared[n]) for n in selected]]).encode()).hexdigest()
            green = state_dir() / "baseline" / "green" / key
            baseline = f"passed earlier on {base} at {base_sha[:7]} with the same commands; not run again"
            if not green.exists():
                base_results, failed = run_checks(worktree, selected, declared, logs, all_of=True,
                                                  ticket_id=ticket_id, use_verify_override=False)
                if failed:
                    red_checks = [row["name"] for row in base_results if row["status"] == "fail"]
                    meta["known_red"] = red_checks
                    meta["known_red_base"] = base_sha
                    followup_id, followup_path, followup_board = record_known_red_followup(
                        work, base, base_sha, red_checks, ticket_id, logs, this_repo
                    )
                    if followup_id:
                        meta["known_red_followup"] = followup_id
                    suffix = f" (follow-up: {followup_id})" if followup_id else ""
                    known_red_lines = [
                        f"known-red: {name} on {base} at {base_sha[:7]} (log: {logs / f'{name}.log'}){suffix}"
                        for name in red_checks
                    ]
                    (work / "known-red.md").write_text("\n".join(known_red_lines) + "\n")
                    baseline = f"known-red on {base} at {base_sha[:7]}: {', '.join(red_checks)}"
                else:
                    green.parent.mkdir(parents=True, exist_ok=True)
                    green.write_text(base_sha + "\n")
                    baseline = f"{', '.join(selected)} passed on {base} at {base_sha[:7]} before any change"

    known_red_file = work / "known-red.md"
    if resumed and active_known_red(meta, Path(meta["worktree"])) and known_red_file.is_file():
        known_red_lines = [line.strip() for line in known_red_file.read_text().splitlines() if line.strip()]
    meta["checks"] = selected
    # Every change needs a verdict from a session that did not write it. The human may waive that per ticket.
    meta["review"] = args.local or ticket["fields"].get("review", "").lower() != "human"
    note_author(meta)
    remember_origin()
    write_json(work / "meta.json", meta)
    (work / "ticket.md").write_text(text)
    print("jtek start: resumed" if resumed else "jtek start: allowed")
    if base_note:
        print(base_note)
    if not resumed and kept:
        print(f"note: the branch {branch} already existed, so the work goes on from its commits")
    print("board: -" if args.local else "board: Status=In Progress; Waiting=")
    print(f"id: {ticket_id}")
    if page:
        print(f"page: {page}  (the ticket file; write there what a `board:` line says)")
    print(f"worktree: {meta['worktree']}")
    print(f"branch: {meta['branch']}")
    print(f"base: {meta['base']}")
    print(f"ticket: {work / 'ticket.md'}  (a copy taken now; read this file)")
    print(f"checks: {', '.join(selected)}")
    if baseline:
        print(f"baseline: {baseline}")
    for line in known_red_lines:
        print(line)
    if known_red_lines and not resumed:
        print(f"known-red file: {work / 'known-red.md'}  (included in evidence automatically, or copy into your evidence)")
        if followup_id:
            print(f"follow-up: {followup_id} ({followup_path}, Backlog)")
        elif followup_path:
            print(f"follow-up draft: {followup_path}")
            print(f"board: {followup_board}")
    if asked:
        print(f"asked: {asked}")
        print("answer: in the chat" if args.local else "answer: on the page, so in the ticket file above")
    print(f"review: {'a verdict from a session that did not write the code is required' if meta['review'] else 'human only (the ticket says `review: human`)'}")
    if resumed and meta.get("pr"):
        # The human may have said why the ticket is back on the pull request, and nowhere else.
        clash = f" It conflicts with {base}." if pr_conflicts(meta["pr"], base) else ""
        print(f"pull request: {meta['pr']}{clash} Read its comments: the reason the ticket is back may be there")
    if resumed and (work / "verdict.json").exists():
        # A session that picks the ticket up learns here what the reviewer said, not from the state folder.
        last = read_json(work / "verdict.json")
        still = "it is for the change as it is now" if current_verdict(ticket_id, meta) else "the change or the ticket has moved on since"
        print(f"last verdict: {last.get('verdict')} by {last.get('by')} @{str(last.get('sha', ''))[:7]} ({still})")
        fails = int(meta.get("fails", 0))
        if fails:
            print(f"FAIL verdicts so far: {fails}" + (". That is three: stop with `--waiting input`, because the ticket or the "
                                                      "reviewer's standard needs the human" if fails >= 3 else ""))
    if resumed and (work / "review.md").exists():
        print(f"review notes: {work / 'review.md'}")
    kind = ticket["fields"].get("kind", "") or "not set; decide from the Goal"
    print(f"kind: {kind}")
    print("next: follow the playbook for this kind; its order is the default. Work only inside the worktree")


def active_known_red(meta: dict, worktree: Path) -> list[str]:
    """Checks recorded red on the base, still waived only while the base is at that same commit and they have not passed."""
    passed = {str(name) for name in (meta.get("known_red_passed") or []) if isinstance(name, str) and name}
    red = [str(name) for name in (meta.get("known_red") or []) if isinstance(name, str) and name and name not in passed]
    recorded_base = str(meta.get("known_red_base") or "")
    if not red or not recorded_base:
        return []
    base = meta["base"]
    local = base_ref(base)
    now_base = git("rev-parse", local, cwd=worktree, check=False)
    if now_base != recorded_base:
        return []
    common = git("merge-base", local, "HEAD", cwd=worktree, check=False)
    if common != recorded_base:
        return []
    remote = f"refs/remotes/origin/{base}"
    if git("rev-parse", "--verify", "--quiet", remote, cwd=worktree, check=False):
        remote_common = git("merge-base", remote, "HEAD", cwd=worktree, check=False)
        if remote_common != recorded_base:
            return []
    return red


def known_red_draft(base: str, base_sha: str, red_checks: list[str], source_id: str,
                    logs: Path, repo_name: str = "") -> str:
    """Draft one Backlog ticket to make every failing baseline check green on the base."""
    checks_csv = ", ".join(red_checks)
    header = [f"# Fix failing base checks on {base} ({checks_csv})", "kind: bug"]
    if repo_name:
        header.append(f"repo: {' '.join(repo_name.split())}")
    done_lines = [f"- running declared check `{name}` on `{base}` exits 0" for name in red_checks]
    log_lines = [f"- `{name}` log: `{logs / f'{name}.log'}`" for name in red_checks]
    sections = [
        "## Goal",
        f"Make the declared base checks ({checks_csv}) exit 0 on `{base}` (seen red at `{base_sha[:7]}` when starting `{source_id}`).",
        "",
        "## Done check",
        *done_lines,
        "",
        "## Proof",
        f"- recorded check output showing exit 0 for {checks_csv} on `{base}`",
        "",
        "## Context",
        f"- source ticket: `{source_id}`",
        f"- base: `{base}` at `{base_sha}`",
        *log_lines,
        "",
        "## Constraints",
        "- do not weaken or skip the declared checks",
    ]
    return "\n".join(header) + "\n\n" + "\n".join(sections) + "\n"


def record_known_red_followup(work: Path, base: str, base_sha: str, red_checks: list[str], source_id: str,
                              logs: Path, repo_name: str) -> tuple[str, str, str]:
    """Open one Backlog ticket for a red base (saved file without a board, or draft path with a board)."""
    draft = known_red_draft(base, base_sha, red_checks, source_id, logs, repo_name)
    if has_board(base):
        draft_path = work / "known-red-followup.md"
        try:
            draft_path.write_text(draft)
        except OSError:
            return "", "", ""
        return "", str(draft_path), f"create Backlog follow-up card from {draft_path}"
    try:
        saved_path = save_ticket(draft)
    except (OSError, Refuse):
        return "", "", ""
    return saved_path.stem, str(saved_path), ""


def ticket_env(ticket_id: str, worktree: Path, *, use_verify_override: bool = True) -> dict:
    """The session's own environment, plus the ticket id, the worktree, and JTEK_VERIFY_DIR when a ticket
    override exists. Nothing is read from it here."""
    env = {**os.environ, "JTEK_TICKET": ticket_id, "JTEK_WORKTREE": str(worktree)}
    env.pop("JTEK_VERIFY_DIR", None)
    if use_verify_override and ticket_id and ID_RE.match(ticket_id):
        override = active_verify_dir(ticket_id, cwd=worktree)
        if override is not None:
            env["JTEK_VERIFY_DIR"] = str(override)
    return env


def run_logged(argv: list[str], cwd: Path, env: dict, out_path: Path, stdin=None, err_log: Path | None = None) -> int | str:
    """Run one program with its arguments, no shell of jtek's own, with stdout in `log` and stderr there too,
    or in `err_log` when one is given. Returns the exit code, or the reason it did not run."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out_path, "w") as out, open(err_log or os.devnull, "w") as err:
            return subprocess.run(argv, cwd=cwd, stdout=out, stderr=err if err_log else subprocess.STDOUT,
                                  stdin=stdin, timeout=DEFAULT_TIMEOUT, env=env).returncode
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        with open(out_path, "a") as out:
            out.write(f"\njtek: {err}\n")
        return f"did not run: {err}"


def run_command(command: str, worktree: Path, log: Path, *, ticket_id: str = "",
                use_verify_override: bool = True) -> bool:
    """Run one declared command."""
    try:
        argv = shlex.split(command)
    except ValueError as err:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"jtek: {err}\n")
        return False
    # A check gets no input, so one that reads it cannot wait on the session's terminal.
    tid = ticket_id or worktree.name
    return run_logged(argv, worktree, ticket_env(tid, worktree, use_verify_override=use_verify_override),
                      log, stdin=subprocess.DEVNULL) == 0


def run_checks(worktree: Path, names: list[str], declared: dict[str, str], logs: Path, *,
               all_of: bool = False, ticket_id: str = "", use_verify_override: bool = True,
               known_red: set[str] | frozenset[str] = frozenset()) -> tuple[list[dict], str | None]:
    """Run checks in order. Stop at the first non-waived failure unless `all_of`, which is how `broke` runs them.

    Return the results and the first non-waived failed name."""
    results: list[dict] = []
    failed: str | None = None
    for name in names:
        started = time.time()
        ok = run_command(declared[name], worktree, logs / f"{name}.log",
                         ticket_id=ticket_id, use_verify_override=use_verify_override)
        status = "pass" if ok else ("known-red" if name in known_red else "fail")
        results.append({"name": name, "status": status, "seconds": round(time.time() - started, 1)})
        if status == "fail" and failed is None:
            failed = name
        if status == "fail" and not all_of:
            return results, name
    return results, failed


def log_tail(log: Path) -> str:
    return "\n".join(log.read_text(errors="replace").splitlines()[-20:])


def cmd_check(args: argparse.Namespace) -> None:
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    declared = load_checks(meta["base"])
    missing = [name for name in meta["checks"] if name not in declared]
    if missing:
        raise Refuse(f"{CONFIG} on {meta['base']} no longer declares: {', '.join(missing)}")
    sha, dirty = head_state(worktree)
    previous = read_json(work / "checks.json")
    limit = load_settings(meta["base"])["max_failed_runs"]
    if previous.get("failed_runs", 0) >= limit:
        raise Refuse(f"{limit} check runs have failed. One more guess usually means the design is wrong, not "
                     f"the line. Stop: `jtek.py stop {args.id} --waiting input --note \"<the cause you suspect>\"`")
    logs = work / "logs"
    waived = set(active_known_red(meta, worktree))
    results, failed = run_checks(worktree, meta["checks"], declared, logs,
                                 ticket_id=args.id, use_verify_override=True, known_red=waived)
    failed_runs = previous.get("failed_runs", 0) + 1 if failed else 0
    record: dict = {"sha": sha, "dirty": bool(dirty), "results": results, "failed_runs": failed_runs}
    if waived:
        record["known_red_base"] = meta["known_red_base"]
    write_json(work / "checks.json", record)
    recorded_red = [str(name) for name in (meta.get("known_red") or []) if isinstance(name, str) and name]
    recorded_red_set = set(recorded_red)
    passed_known_red = [row["name"] for row in results if row["name"] in recorded_red_set and row["status"] == "pass"]
    prior_passed = {str(name) for name in (meta.get("known_red_passed") or []) if isinstance(name, str) and name}
    if recorded_red and passed_known_red:
        all_passed = [name for name in recorded_red if name in prior_passed or name in passed_known_red]
        if all_passed != list(meta.get("known_red_passed") or []):
            meta = update_meta(work, known_red_passed=all_passed)
    for result in results:
        print(f"{result['name']}: {result['status']} ({result['seconds']}s)")
    still_red = [row["name"] for row in results if row["status"] == "known-red"]
    for name in still_red:
        print(f"known-red: {name} (still red on {meta['base']} @{meta['known_red_base'][:7]}; log: {logs / f'{name}.log'})")
    if passed_known_red:
        print(f"known-red passed: {', '.join(passed_known_red)}")
    if failed:
        log = logs / f"{failed}.log"
        print(f"log: {log}")
        print(log_tail(log))
        if failed_runs >= limit:
            print(f"next: {failed_runs} failed runs; stop with `jtek.py stop {args.id} --waiting input --note ...`")
        else:
            print(f"next: fix the cause, commit, run check again ({failed_runs}/{limit} failed runs)")
        sys.exit(1)
    if dirty:
        print(f"next: all checks pass, but these files are not committed; {DIRTY_HINT} and run check again")
        print(dirty)
    elif still_red:
        print(f"next: checks pass at {sha[:7]} (known-red waived: {', '.join(still_red)}); "
              "go on with the next step of your playbook. Run check again after any new commit")
    else:
        print(f"next: all checks pass at {sha[:7]}; go on with the next step of your playbook. "
              "Run check again after any new commit")


def read_file(path: str, what: str) -> str:
    try:
        return Path(path).read_text()
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the {what} file: {err}") from None


def uncommitted_test_files(worktree: Path) -> list[str]:
    """Test files with uncommitted changes (tracked or untracked) in the worktree."""
    tracked = git("diff", "--name-only", "HEAD", cwd=worktree, check=False).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=worktree, check=False).splitlines()
    paths = [p.strip() for p in tracked + untracked if p.strip()]
    return sorted({p for p in paths if is_test_path(p) or Path(p).name.lower() == "conftest.py"})


def cmd_broke(args: argparse.Namespace) -> None:
    """Record that breaking one Done when item made a declared check fail. The edit stays uncommitted;
    the author restores it afterwards. finish refuses until every item has such a record for this commit."""
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    items = done_when_items(work)
    try:
        number = int(str(args.item).strip())
    except ValueError:
        number = 0
    if not 1 <= number <= len(items):
        raise Refuse(f"--item is a Done when item from 1 to {len(items) or 0}")
    sha, dirty = head_state(worktree)
    if not dirty:
        raise Refuse(
            "nothing is broken in the worktree. Change the behaviour this item names, leave the change uncommitted, "
            f"and run `jtek.py broke {args.id} --item {number}` again. Then restore the file (`git checkout -- <file>`)."
        )
    uncommitted_tests = uncommitted_test_files(worktree)
    if uncommitted_tests:
        raise Refuse(
            "a broke proof must fail against already-committed tests, not uncommitted test files: "
            + ", ".join(uncommitted_tests)
            + ". Commit the tests first, then leave only the behaviour break uncommitted and run broke again."
        )
    diff_text = git("diff", "HEAD", cwd=worktree, check=False)
    untracked = [line[3:] for line in dirty.splitlines() if line.startswith("??")]
    shown = diff_text
    if untracked:
        shown += ("\n" if shown else "") + "untracked:\n" + "\n".join(untracked)
    if not shown.strip():
        raise Refuse("the worktree is dirty, but there is no diff to record. Break a tracked file, or add a file a check reads.")
    declared = load_checks(meta["base"])
    waived = set(active_known_red(meta, worktree))
    # One directory per item, so item 2 does not truncate the log of item 1.
    results, _failed = run_checks(worktree, meta["checks"], declared, work / "logs" / "broke" / f"item-{number}",
                                  all_of=True, ticket_id=args.id, use_verify_override=True, known_red=waived)
    behaviour = [row["name"] for row in results if row["status"] == "fail" and is_behaviour_check(row["name"])]
    if not behaviour:
        known_red_behaviour = [
            row["name"] for row in results if row["status"] == "known-red" and is_behaviour_check(row["name"])
        ]
        if known_red_behaviour:
            names = ", ".join(known_red_behaviour)
            raise Refuse(
                f"only known-red behaviour check(s) failed while item {number} was broken (`{items[number - 1][:80]}`): {names}. "
                f"A check that was already red on {meta['base']} is not proof that this edit broke the item. "
                "A non-waived behaviour check has to fail. "
                "The break is still in the worktree."
            )
        if not any(row["status"] == "fail" for row in results):
            raise Refuse(
                f"every check still passed while item {number} was broken (`{items[number - 1][:80]}`). "
                "No declared check covers that behaviour. A proof needs one of them to fail. "
                "The break is still in the worktree."
            )
        raise Refuse(
            f"item {number} (`{items[number - 1][:80]}`) has no failed behaviour check. "
            "A lint, syntax, format, or import failure does not prove the item. "
            "Every declared check was run. The declared behaviour check has to fail. "
            "The break is still in the worktree."
        )
    record = read_json(work / "broke.json")
    got = record.get("items") if record.get("sha") == sha and isinstance(record.get("items"), dict) else {}
    got[str(number)] = {"item": items[number - 1], "check": behaviour[0], "fails": behaviour,
                        "diff": shown[:4000], "sha": sha}
    write_json(work / "broke.json", attach_broke_seal({"sha": sha, "items": got}))
    print(f"broke: item {number} made `{behaviour[0]}` fail at {sha[:7]}")
    print(f"next: restore the break (`git checkout -- <file>`), then record the next item. "
          f"{len(got)} of {len(items)} recorded")


def require_broke(work: Path, sha: str) -> None:
    """finish refuses without a recorded break for every Done when item, on this commit."""
    items = done_when_items(work)
    record = read_json(work / "broke.json")
    if record.get("items") and not broke_intact(record):
        raise Refuse(
            "the broke proof was changed after it was recorded. The seal does not match. "
            "The same key that seals the authors seals this file. Run broke again for each Done when item."
        )
    got = record.get("items") if record.get("sha") == sha and isinstance(record.get("items"), dict) else {}
    missing = []
    for n, item in enumerate(items, 1):
        entry = got.get(str(n)) if isinstance(got, dict) else None
        # The stored text is the Done when line as it was. Rewriting that line invalidates the proof.
        same = isinstance(entry, dict) and entry.get("item") == item and entry.get("sha") == sha
        proved = same and is_behaviour_check(str(entry.get("check") or "")) and str(entry.get("diff") or "").strip()
        if not proved:
            missing.append(f"{n}. {item}")
    if missing:
        raise Refuse(
            "finish needs a broke proof for every `Done when` item. Break that behaviour in the worktree, leave the "
            "edit uncommitted, and run `jtek.py broke <id> --item <n>` so a declared check fails. Then restore the "
            "file (`git checkout -- <file>`). A check that still passes does not prove the item. Missing:\n"
            + "\n".join(missing)
        )


def author_sessions(meta: dict) -> list[str]:
    authors = [a for a in meta.get("authors", []) if isinstance(a, str) and a]
    if isinstance(meta.get("author"), str) and meta["author"] and meta["author"] not in authors:
        authors.append(meta["author"])
    return authors


NIT_WORD = re.compile(
    r"\b(nit|nits|nitpick|style|rename|typo|wording|preference|formatting|whitespace|comment)\b", re.I)
STRICT_NIT_WORD = re.compile(
    r"\b(nit|nits|nitpick|typo|wording|preference|formatting|whitespace|for\s+style|code\s+style|style\s+only)\b", re.I)
BUG_WORD = re.compile(
    r"\b(crash|fail|fails|failed|error|wrong|regression|bug|exception|broken|incorrect|loses|drops|rejects|"
    r"500|404|timeout|corrupt|uncommitted)\b", re.I)


def review_regions(text: str) -> str:
    """The notes that count. A Dropped or Nits list is optional and never a verdict."""
    kept: list[str] = []
    dropping = False
    for line in text.splitlines():
        head = line.strip().lower().rstrip(":")
        if head in {"dropped", "## dropped", "nits", "## nits"}:
            dropping = True
            continue
        if head in {"findings", "## findings", "notes", "## notes"}:
            dropping = False
        if not dropping:
            kept.append(line)
    return "\n".join(kept)


def review_findings(text: str) -> tuple[list[str], list[str]]:
    """Real findings, and the problems in the rest (nit, thin). Dropped lines are ignored."""
    counted = review_regions(text)
    blocks: list[list[str]] = []
    outside_lines: list[str] = []
    open_block = False
    for line in counted.splitlines():
        if re.match(r"^\s*[-*]\s*reproduces:", line):
            blocks.append([line])
            open_block = True
        elif open_block and (line.startswith((" ", "\t")) or not line.strip()):
            blocks[-1].append(line)
        else:
            open_block = False
            outside_lines.append(line)
    real: list[str] = []
    problems: list[str] = []
    for block in blocks:
        if not block:
            continue
        body = "\n".join(block)
        repro = re.search(r"reproduces:\s*(.*)", body, re.I)
        shown = repro.group(1) if repro else ""
        has_steps = re.search(r"(?im)^\s*(steps|scenario):\s*\S", body)
        has_expected = re.search(r"(?im)^\s*expected:\s*\S", body)
        if not BUG_WORD.search(body):
            if NIT_WORD.search(shown) and not (has_steps and has_expected):
                problems.append("nit")
                continue
            if STRICT_NIT_WORD.search(shown):
                problems.append("nit")
                continue
        if has_steps and has_expected:
            real.append(body)
        else:
            problems.append("thin")
    # A nit anywhere outside real findings in the notes that count blocks a pass.
    # Dropped and Nits were removed above, and a nit that only appeared on a reproduces line is already recorded.
    outside = "\n".join(outside_lines)
    if "nit" not in problems and re.search(r"(?i)\bnit(?:s|pick)?\b", outside):
        problems.append("nit")
    return real, problems


def check_reviewer_by(raw_by: str) -> str:
    """Normalize `--by` and check it against the owner's agents.json when that file exists."""
    by = " ".join((raw_by or "").split())
    if not by:
        raise Refuse("pass --by with the name of the model that reviewed")
    path, notice = owner_file("agents.json")
    if notice:
        print(notice)
    reviewers = load_reviewers(path)
    if reviewers is None:
        return by
    accepted: set[str] = set()
    shown: list[str] = []
    seen: set[str] = set()
    for entry in reviewers:
        prog_name = Path(entry["program"]).name
        for name in (entry["model"], entry["command"], entry["program"], prog_name):
            accepted.add(name.lower())
        for name in (entry["model"], entry["program"], prog_name):
            low = name.lower()
            if low not in seen:
                seen.add(low)
                shown.append(name)
    if by.lower() in accepted:
        return by
    if not shown:
        raise Refuse(
            f"`--by {by}` is not in {path} (the reviewers list is empty). "
            "Use the name `jtek.py reviewer` printed, add a reviewer with `/jt-agents`, or remove that file"
        )
    raise Refuse(
        f"`--by {by}` is not in {path}. Accepted names: {', '.join(shown)}. "
        "Use the name `jtek.py reviewer` printed"
    )


def cmd_verdict(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if not session_identity():
        raise Refuse(SESSION_MISSING)
    if not authors_intact(meta):
        raise Refuse(
            "the authors recorded at start were changed in meta.json, or this claim has no author seal. "
            "A hand edit of the authors does not make a verdict count. The seal uses a key in the state directory. "
            "A process that can rewrite both that key and meta.json can still forge the list."
        )
    authors = author_sessions(meta)
    if not authors:
        raise Refuse(
            "this claim recorded no session at start, so a verdict cannot be told apart from the writing session. "
            "Run start again in the session that writes the code, then verdict in a different session. "
            "Set JTEK_SESSION to an id that stays the same for the whole writing session, and to a different id "
            "in the session that reviews."
        )
    if session_identity() in authors:
        raise Refuse(
            "this session is one that wrote the code, so its verdict does not count. "
            "Start a session that did not write the change and run verdict there. "
            "`jtek.py reviewer` prints a command when the owner keeps a list. "
            "A session is the value of JTEK_SESSION, CURSOR_SESSION_ID, CLAUDE_CODE_SESSION_ID, or CODEX_THREAD_ID. "
            "The same text in any of those names is the same session. The parent process is not a session. "
            "The writing session must keep the same value the whole time."
        )
    by = check_reviewer_by(args.by)
    worktree = Path(meta["worktree"])
    if args.pr or args.at or not worktree.is_dir():
        repo, sha, spec, _note = review_target(meta, args.pr or "", args.at or "")
        dirty = ""
        if worktree.is_dir() and sha == git("rev-parse", "HEAD", cwd=worktree, check=False):
            sha, dirty = head_state(worktree)
        patch = patch_from(repo, spec)
    else:
        sha, dirty = head_state(worktree)
        patch = patch_id(worktree, meta["base"])
    reviewed = (args.commit or "").strip().lower()
    if len(reviewed) < 7 or not re.fullmatch(r"[0-9a-f]+", reviewed):
        raise Refuse("pass --commit with the commit id `jtek.py show` printed when you began, at least 7 characters")
    if not sha.startswith(reviewed):
        raise Refuse(f"the worktree is at {sha[:7]}, and --commit says you reviewed {reviewed or 'nothing'}. Pass the "
                     "`commit:` that `jtek.py show` printed when you began. If they differ, the author committed during "
                     "your review: review the new commit")
    if dirty and args.verdict != "FAIL":
        # FAIL opens nothing, so it is allowed here: a reviewer must not have to delete the author's files to say so.
        raise Refuse("a pass is for a commit, and these files are not committed. If your review made them, remove "
                     f"them. If the author left them, give FAIL and say so in the notes\n{dirty}")
    if not patch:
        raise Refuse(
            f"the branch has no change against {meta['base']}, so there is nothing to give a verdict on. "
            "When the worktree is gone after a squash, pass --pr <link> to review refs/pull/<n>/head, "
            "or --at <the commit that landed> to review that commit's parent range."
        )
    if not args.notes_file:
        raise Refuse(f"{args.verdict} needs --notes-file with your notes, in the form of the review notes")
    notes_text = read_file(args.notes_file, "notes")
    counted_notes = review_regions(notes_text)
    real, problems = review_findings(notes_text)
    weigh = re.search(r"^\s*[-*]\s*to weigh:", counted_notes, re.M)
    # The word of the verdict and the notes must say the same thing, because the human reads the word first.
    if "nit" in problems:
        raise Refuse(
            "a nit is not a finding and not a FAIL. Put it under `Dropped:` or leave it out. "
            "FAIL is only for a bug or a regression."
        )
    if "thin" in problems:
        raise Refuse(
            "a finding needs a reproduction (`steps:`) or a concrete failing scenario (`scenario:`), and `expected:`. "
            "A line that only says `- reproduces:` is not a finding. A nit goes under `Dropped:`."
        )
    if args.verdict == "FAIL" and not real:
        raise Refuse(
            "FAIL is only for a bug or a regression you can show: `- reproduces:` with `steps:` or `scenario:`, "
            "and `expected:`. A nit under `Dropped:` is not a FAIL. Without a finding, the verdict is PASS or PASS+NOTES"
        )
    if args.verdict != "FAIL" and real:
        raise Refuse(f"the notes hold a finding (`- reproduces:`), so the verdict is FAIL, not {args.verdict}. "
                     "If it does not count as a finding, write it as a note or under `Dropped:`")
    if args.verdict != "FAIL":
        # The two steps a quick review skips: testing the tests, and naming why the change is safe.
        lacking = [form for form, key in (("- broke: <the line you broke, and which checks failed or still passed>", "broke"),
                                          ("- safe because: <the one fact the change is safe because of> (run <n>)", "safe because"))
                   if not re.search(rf"^\s*[-*]\s*{key}:", counted_notes, re.M)]
        if lacking:
            raise Refuse("the notes of a pass say what you broke to test the tests, and why the change is safe, "
                         "as the `jt-review` skill says. Add:\n" + "\n".join(lacking))
    if args.verdict == "PASS+NOTES" and not weigh:
        raise Refuse("PASS+NOTES is for something the human should decide before merging: a line `- to weigh: <what>`. "
                     "Notes that only say what you saw are a PASS; give PASS and keep --notes-file")
    (work / "review.md").write_text(notes_text)
    if args.verdict == "FAIL":
        # `jt-work` stops after the third FAIL on one ticket, so the count has to live where a session can read it.
        # A second FAIL on the same commit is a corrected note, not a new round.
        with meta_lock(work):
            fresh = read_json(work / "meta.json")
            failed = sorted(set(fresh.get("failed_commits", [])) | {sha})
            earlier = 0 if "failed_commits" in fresh else int(fresh.get("fails", 0))  # counted before commits were kept
            meta = {**fresh, "failed_commits": failed, "fails": earlier + len(failed)}
            write_json(work / "meta.json", meta)
    write_json(work / "verdict.json", {
        "verdict": args.verdict, "by": by, "sha": sha,
        "patch": patch, "ticket": ticket_id_of_text(work),
    })
    line = f"verdict: {args.verdict} by {by} @{sha[:7]}"
    (work / "review-comment.md").write_text(f"`{line}`\n\n{notes_text}".rstrip() + "\n")
    print(line)
    if meta.get("pr"):
        print(f"comment file: {work / 'review-comment.md'}  (the verdict line and the notes, ready to post on {meta['pr']})")


def merge_known_red_evidence(work: Path, text: str) -> str:
    """Append recorded known-red lines to saved evidence when the author did not include them."""
    kr_file = work / "known-red.md"
    if not kr_file.is_file() or re.search(r"^\s*(-\s*)?known-red:", text, re.M | re.I):
        return text
    kr_lines = [line.strip() for line in kr_file.read_text().splitlines() if line.strip()]
    if not kr_lines:
        return text
    extra = "\n".join(f"- {line}" for line in kr_lines)
    base_text = text if text.endswith("\n") else text + "\n"
    return base_text + extra + "\n"


def check_evidence(work: Path, text: str) -> None:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise Refuse("the evidence file is empty")
    items = done_when_items(work)
    kr_file = work / "known-red.md"
    kr_extra = len([line for line in kr_file.read_text().splitlines() if line.strip()]) if kr_file.is_file() else 0
    limit = max(MAX_EVIDENCE_LINES, len(items) + 10) + kr_extra
    if len(lines) > limit:
        raise Refuse(
            f"the evidence has {len(lines)} lines; the human reads it before the diff, so keep it to "
            f"{limit}. Say what you ran and saw for each `Done when` item, and cut the rest"
        )
    missing = [
        f"{n}. {item}" for n, item in enumerate(items, 1)
        if not re.search(rf"^\s*{n}\.\s*(seen|not run):", text, re.M)
    ]
    if missing:
        raise Refuse(
            "the evidence must account for every `Done when` item. Start one line per item with its number and "
            "`seen:` (the command or steps, and the result) or `not run:` (the reason). Missing:\n" + "\n".join(missing)
        )
    cited = sorted(set(cited_runs(text)))
    missing_runs = [n for n in cited if not read_run(work, n)]
    if missing_runs:
        raise Refuse(
            "the evidence cites " + ", ".join(f"run {n}" for n in missing_runs) + ", which `jtek.py run` never finished "
            "recording for this ticket. Cite only the run numbers it printed, from runs that ended"
        )

    if not re.search(r"^\s*(-\s*)?clean-up:", text, re.M | re.I):
        # The step that reads the diff once more is the easiest to skip at the end of a long session.
        raise Refuse(
            "the evidence has no `clean-up:` line. Read the diff as the `jt-cleanup` skill says, then add one line "
            "under Notes: `- clean-up: <what you removed>`, or `- clean-up: nothing to clean up`"
        )


def cmd_run(args: argparse.Namespace) -> None:
    """Run a command the way a user would, and keep exactly what was run and what came back.
    The evidence then cites `(run <n>)`, so a reader can see the run behind each `seen:` line."""
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    command = list(args.command)
    # argparse hands everything after the id to the command, so options given there are read here.
    while command[:1] in (["--sh"], ["--cwd"]) and len(command) > 1:
        setattr(args, command[0][2:], command[1])
        command = command[2:]
    if command[:1] == ["--"]:
        command = command[1:]
    if bool(args.sh) == bool(command):
        raise Refuse("give one command after `--`, or one shell line with --sh \"<pipeline>\", not both and not neither")
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else worktree
    if not cwd.is_dir():
        raise Refuse(f"--cwd is not a folder: {cwd}")
    sha, dirty = head_state(worktree)
    runs = work / "runs"
    runs.mkdir(exist_ok=True)
    number = len(list(runs.glob("*.txt"))) + 1
    while True:
        try:
            (runs / f"{number}.txt").touch(exist_ok=False)  # exclusive, so two runs at once never share a number
            break
        except FileExistsError:
            number += 1
    shown = args.sh or shlex.join(command)
    # A shell line is what the session could type into its own shell; recording it adds no reach.
    argv = ["/bin/sh", "-c", args.sh] if args.sh else command
    out_file, err_file = runs / f"{number}.out", runs / f"{number}.err"
    started = time.monotonic()
    code = run_logged(argv, cwd, ticket_env(args.id, worktree), out_file, stdin=subprocess.DEVNULL, err_log=err_file)
    seconds = time.monotonic() - started

    def kept(path: Path) -> str:
        text = path.read_text(errors="replace")
        path.unlink()
        return text if len(text) <= MAX_RUN_OUTPUT else text[:MAX_RUN_OUTPUT] + f"\n... ({len(text) - MAX_RUN_OUTPUT} more characters not kept)\n"

    stdout, stderr = kept(out_file), kept(err_file)
    # When it ran somewhere else, say which commit that place was at, so a run of the base names the base.
    there = git("rev-parse", "HEAD", cwd=cwd, check=False) if cwd != worktree else ""
    if cwd != worktree and not there:
        there = "none: not in a git repository"
    record = (f"run: {number}\ncommand: {shown}\ncwd: {cwd}" + (f" (at commit {there})" if there else "")
              + f"\ncommit: {sha}" + (WORKTREE_COMMIT if cwd != worktree else "")
              + (" (with uncommitted files)" if dirty else "")
              + f"\nexit: {code}\nseconds: {seconds:.2f}\n--- stdout ---\n{stdout}--- stderr ---\n{stderr}")
    (runs / f"{number}.txt").write_text(record)
    print(record if len(record) <= 4000 else record[:4000] + "\n... (the rest is in the run file)")
    print(f"recorded: run {number} in {runs / f'{number}.txt'}. Cite it in the evidence as (run {number})")


def cmd_evidence(args: argparse.Namespace) -> None:
    """Check an evidence file before it becomes the body of a pull request. Saves nothing."""
    load_meta(args.id)
    text = read_file(args.file, "evidence")
    check_evidence(work_dir(args.id), text)
    seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
    not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
    print(f"evidence: the form is accepted ({seen} seen, {not_run} not run). Nothing was saved; pass the file to `finish`")


PR_HEAD_TRIES = 5
PR_HEAD_WAIT = float(os.environ.get("JTEK_PR_WAIT", "3"))


def pushed(worktree: Path, branch: str, sha: str) -> bool:
    """Whether the remote-tracking branch already holds this commit, so a pull request behind it is only late."""
    refs = git("for-each-ref", "--format=%(refname)", f"--points-at={sha}", "refs/remotes", cwd=worktree, check=False)
    return any(ref.endswith(f"/{branch}") for ref in refs.splitlines())


def remote_default(cwd: Path | None = None) -> tuple[str, str]:
    """Default branch name and tip sha from the remote. Empty when there is no remote."""
    if not git("remote", cwd=cwd, check=False).strip():
        return "", ""
    try:
        text = git("ls-remote", "--symref", "origin", "HEAD", cwd=cwd, timeout=60)
    except Refuse as err:
        raise Refuse("the remote could not be read, so this change is not sent without a pull request. " + str(err)) from None
    branch = ""
    sha = ""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "ref:" and parts[1].startswith("refs/heads/"):
            branch = parts[1].split("/", 2)[-1]
        elif parts and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", parts[0]):
            sha = parts[0]
    if not sha or not branch:
        raise Refuse("the remote did not name a default branch tip, so this change is not sent without a pull request.")
    return branch, sha


def remote_forge_off(cwd: Path | None = None) -> bool:
    """Whether this machine's config for the repository says there is no forge.

    The flag used to be `"forge": false` in jtek.json on the remote tip. A commit cannot set it:
    not on the published base, not on an unmerged branch, and not through a replace ref or a
    rewritten origin. The caller has already refused a rewritten or unsealed origin.
    `cwd` is accepted so the call site stays the same; the config is this repository's.
    """
    del cwd
    try:
        config = load_config("")
    except Refuse:
        return False
    return isinstance(config, dict) and config.get("forge") is False


def no_pr_allowed(worktree: Path) -> bool:
    """Whether a result may be recorded with no pull request."""
    if not git("remote", cwd=worktree, check=False).strip():
        return True
    require_honest_origin(worktree)
    return remote_forge_off(worktree)


def cmd_finish(args: argparse.Namespace) -> None:
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    last = work / "result.md"
    if last.exists() and "outcome: needs-human" in last.read_text():
        if meta.get("local"):
            raise Refuse(f"{args.id} stopped with a question. The human answers in the chat; then start again with --local --answered")
        raise Refuse(f"{args.id} stopped with a question. The human answers on the page and sets Status to Todo; then start again")
    if args.pr and args.no_pr:
        raise Refuse("pass --pr <url> or --no-pr, not both")
    if not args.pr and not args.no_pr and meta.get("no_pr"):
        args.no_pr = True  # an earlier finish already said there is no pull request, so `finish <id>` alone works again
    if args.pr and not re.match(r"^https?://[^\s;]+$", args.pr):
        raise Refuse("--pr takes the link of the pull request, as the forge gave it")
    if args.no_pr and not no_pr_allowed(worktree):
        raise Refuse("this repository has a remote, so the change needs a pull request: push the branch, open it, and pass "
                     "--pr <url>. finish --no-pr is allowed only when there is no remote, or when this machine config sets forge to false. "
                     "A commit cannot set that flag.")
    sha, dirty = head_state(worktree)
    checks = read_json(work / "checks.json")
    waived = set(active_known_red(meta, worktree))
    same_base = bool(waived) and checks.get("known_red_base") == meta.get("known_red_base")
    passed = bool(checks.get("results")) and all(
        r["status"] == "pass" or (same_base and r["status"] == "known-red" and r["name"] in waived)
        for r in checks["results"]
    )
    ran_all = [r["name"] for r in checks.get("results", [])] == meta["checks"]
    if dirty:
        raise Refuse(f"these files are not committed; {DIRTY_HINT} and run `jtek.py check {args.id}`\n{dirty}")
    if checks.get("dirty") or checks.get("sha") != sha or not passed or not ran_all:
        raise Refuse(f"checks have not passed on the current commit {sha[:7]}; run `jtek.py check {args.id}`")
    patch = patch_id(worktree, meta["base"])
    if not patch:
        raise Refuse(f"the branch has no change against {meta['base']}, so there is nothing to review. If the ticket "
                     f"needs no change, stop and say so: `jtek.py stop {args.id} --waiting input --note \"...\"`")
    about = ticket_id_of_text(work)
    saved = work / "evidence.md"
    if args.evidence_file:
        text = read_file(args.evidence_file, "evidence")
        check_evidence(work, text)
        saved.write_text(merge_known_red_evidence(work, text))
        meta = update_meta(work, evidence_patch=patch, evidence_ticket=about)  # kept even when a later rule refuses
    elif not saved.exists():
        raise Refuse(
            "no evidence yet; the human reviews the evidence before the diff. Write what you ran and saw for each "
            "`Done when` item to a file and pass --evidence-file <file>. Use the same text as the pull request body"
        )
    elif meta.get("evidence_patch") != patch:
        raise Refuse("the code changed after the evidence was saved, so the evidence describes an older change. "
                     "See each `Done when` item work again, and pass --evidence-file <file>")
    elif meta.get("evidence_ticket") != about:
        check_evidence(work, saved.read_text())
        raise Refuse("the ticket changed after the evidence was saved. Read the ticket file again, do what it now asks, "
                     "and pass --evidence-file <file>")
    else:
        check_evidence(work, saved.read_text())  # the ticket may have gained an item since
    require_broke(work, sha)
    for item in args.attach or []:
        source = Path(item)
        if not source.is_file():
            raise Refuse(f"cannot attach {item}: not a file")
        (work / "evidence").mkdir(exist_ok=True)
        (work / "evidence" / source.name).write_bytes(source.read_bytes())
    pr = args.pr or meta.get("pr", "")
    ci = ""
    pr_status = ""
    if args.no_pr:
        pr = ""
        pr_note = f" No pull request: the branch {meta['branch']} is local."
    elif not pr:
        raise Refuse(
            "no PR yet; open a draft pull request and pass --pr <url>. "
            "Only when this repository has no forge to open one on, pass --no-pr"
        )
    else:
        pr_status, head, ci, problem = pr_info(pr, meta["base"])
        for _ in range(PR_HEAD_TRIES):
            # A forge needs a moment after a push before the pull request shows the new commit.
            if pr_status not in ACTIVE_PR_STATES or head == sha or not pushed(worktree, meta["branch"], sha):
                break
            time.sleep(PR_HEAD_WAIT)
            pr_status, head, ci, problem = pr_info(pr, meta["base"])

        def refuse_unread() -> None:
            extra = ""
            if git("remote", cwd=worktree, check=False) and not pushed(worktree, meta["branch"], sha):
                extra = (f" The pull request could not be read, and the branch is not pushed at {sha[:7]}: "
                         "push the branch, check that the link is the pull request for it, and finish again.")
            chosen = select_forge(meta["base"])
            if chosen == "glab":
                hint = ("Check the link, then make `glab` able to read the merge request and its pipeline "
                        "(run `glab auth status`) and run finish again.")
            else:
                hint = ("Check the link, then make `gh` able to read the pull request and its checks "
                        "(the GH_TOKEN needs access to pull requests and checks, such as the repo scope) and run finish again.")
            raise Refuse(
                f"cannot read {public_url(pr)}, so this change is not sent for review. {problem}{extra} {hint}"
            )

        if pr_status == "unknown" or ci == "unknown":
            refuse_unread()
        link = public_url(pr)
        appeared = 0
        if pr_status in ACTIVE_PR_STATES and head == sha and ci == "absent":
            # An empty rollup is not "no checks". Wait a short bound for the first check, then refuse.
            looks = max(0, env_int("JTEK_CI_APPEAR_TRIES", CI_APPEAR_TRIES))
            pause = max(0.0, env_float("JTEK_CI_APPEAR_WAIT", CI_APPEAR_WAIT))
            while ci == "absent" and pr_status in ACTIVE_PR_STATES and head == sha and appeared < looks:
                time.sleep(pause)
                pr_status, head, ci, problem = pr_info(pr, meta["base"])
                appeared += 1
            if pr_status == "unknown" or ci == "unknown":
                refuse_unread()
        waited = 0
        if pr_status in ACTIVE_PR_STATES and head == sha and ci == "pending":
            # Pending is not a result. Look again, with a bound, and refuse when it is still pending.
            looks = max(0, env_int("JTEK_CI_TRIES", CI_TRIES))
            pause = max(0.0, env_float("JTEK_CI_WAIT", CI_WAIT))
            waited = 0
            while ci == "pending" and pr_status in ACTIVE_PR_STATES and waited < looks:
                time.sleep(pause)
                pr_status, head, ci, problem = pr_info(pr, meta["base"])
                waited += 1
            if pr_status == "unknown" or ci == "unknown":
                refuse_unread()
        if pr_status in ("CLOSED", "MERGED"):
            raise Refuse(f"{link} is {pr_status}, so it cannot take this change. Open a new pull request for the branch, or "
                         "reopen this one, and pass its link")
        if pr_status in ACTIVE_PR_STATES and head != sha:
            if pushed(worktree, meta["branch"], sha):
                raise Refuse(f"{link} is at {head[:7]}, not at the current commit {sha[:7]}. The branch is pushed, so the "
                             "forge may only be late: run `finish` again in a moment")
            ancestry = git("merge-base", "--is-ancestor", head, sha, cwd=worktree, code=True) if head else 0
            if ancestry == 1:
                raise Refuse(f"{link} is at {head[:7]}, which this branch has rewritten (a rebase or an amend). Push it "
                             "with `--force-with-lease`, as the `jt-babysit` skill says, and finish again")
            if ancestry != 0:
                raise Refuse(f"{link} is at {head[:7]}, which this branch does not have: someone added commits on the forge. "
                             f"Bring them in (`git pull --ff-only` or a rebase), check again, push, and finish again")
            raise Refuse(f"{link} is at {head[:7]}, not at the current commit {sha[:7]}; push the branch")
        if ci == "fail":
            with meta_lock(work):
                fresh = read_json(work / "meta.json")
                prior = [s for s in fresh.get("ci_fail_shas", []) if isinstance(s, str) and s]
                if sha not in prior:
                    prior.append(sha)
                write_json(work / "meta.json", {**fresh, "ci_fail_shas": prior})
            if len(prior) >= 2:
                raise Refuse(
                    f"CI is failing again on {link} after a fix round ({sha[:7]}); do not keep looping. "
                    f"Run `jtek.py stop {args.id} --waiting input --note \"CI still fails\"` and hand it to the human"
                )
            raise Refuse(
                f"CI is failing on {link}; a pull request with red CI is not ready for the human. "
                "Fix it once, push, and run finish again"
            )
        if ci == "pending":
            raise Refuse(
                f"CI is still pending on {link} after {waited if pr_status in ACTIVE_PR_STATES else 0} look(s). "
                "A pull request whose checks have not finished does not ship. "
                "SKIPPED and NEUTRAL are not a pass. Wait until every required check is SUCCESS, "
                "or until the command prints none because this repository has no checks, then finish again. "
                f"The bound is JTEK_CI_TRIES={max(0, env_int('JTEK_CI_TRIES', CI_TRIES))} and "
                f"JTEK_CI_WAIT={max(0.0, env_float('JTEK_CI_WAIT', CI_WAIT)):g} seconds between looks."
            )
        if ci == "absent":
            raise Refuse(
                f"no checks have appeared on {link} after {appeared} look(s). "
                "An empty rollup is not an explicit no-checks result, so this change does not ship. "
                "Wait for the first check, or set pr_state to a command that prints none when this repository "
                "really has no checks. "
                f"The bound is JTEK_CI_APPEAR_TRIES={max(0, env_int('JTEK_CI_APPEAR_TRIES', CI_APPEAR_TRIES))} and "
                f"JTEK_CI_APPEAR_WAIT={max(0.0, env_float('JTEK_CI_APPEAR_WAIT', CI_APPEAR_WAIT)):g} seconds between looks."
            )
        if ci not in ("pass", "none"):
            raise Refuse(f"CI on {link} is `{ci or 'unknown'}`, not pass or none, so this change is not sent for review.")
        if pr_status in ACTIVE_PR_STATES and pr_conflicts(pr, meta["base"]):
            raise Refuse(f"{link} conflicts with {meta['base']}; a pull request that cannot merge is not ready for the human. "
                         "Bring the branch up to date as the `jt-babysit` skill says, then check and finish again")
        pr_note = ""
    meta = update_meta(work, pr=pr, ci=ci, no_pr=bool(args.no_pr), ci_fail_shas=[])
    verdict = current_verdict(args.id, meta)
    if not meta.get("review") and needs_verdict(meta):
        pr_note += " `review: human` is ignored because the change touches the files on the attention line."
    if needs_verdict(meta) and not verdict and int(meta.get("fails", 0)) >= 3:
        # Checks stop after three failed runs; reviews stop after three too. A new commit does not buy a fourth round.
        raise Refuse(f"{args.id} has had {meta['fails']} FAIL verdicts, so a new commit does not go to another review. "
                     f"Stop with `jtek.py stop {args.id} --waiting input`, because the ticket or the reviewer's standard "
                     "needs the human")
    if needs_verdict(meta) and not verdict:
        print(write_result(args.id, "needs-review", "In Progress",
                           note="start a session that did not write this code and run jt-review for this id." + pr_note), end="")
        return
    if verdict.get("verdict") == "FAIL":
        fails = int(meta.get("fails", 0))
        if fails >= 3:
            raise Refuse(f"verdict is FAIL, the third or later on {args.id} ({fails}); stop with `jtek.py stop {args.id} "
                         "--waiting input`, because the ticket or the reviewer's standard needs the human")
        raise Refuse(f"verdict is FAIL ({fails} so far on this ticket); read {work / 'review.md'}, fix what reproduces, "
                     "commit, check, and get a new verdict")
    if pr and pr_status == "DRAFT" and verdict.get("verdict") in ("PASS", "PASS+NOTES") and ci in ("pass", "none"):
        ready_ok, ready_detail = mark_ready(pr, base=meta["base"])
        if not ready_ok:
            raise Refuse(f"could not mark {public_url(pr)} ready for review. {ready_detail} "
                         "Fix the forge error and run finish again.")
    print(write_result(args.id, "review", "Review",
                       note="the human reviews and merges; jtek never merges." + pr_note), end="")


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
    print(write_result(args.id, "needs-human", "In Progress", note=args.note, waiting=args.waiting), end="")


def cmd_result(args: argparse.Namespace) -> None:
    path = work_dir(args.id) / "result.md"
    if not path.exists():
        raise Refuse(f"{args.id} has no result yet")
    print(path.read_text(), end="")


def cmd_show(args: argparse.Namespace) -> None:
    """Everything a reviewer needs, without the author's chat.

    After a squash the worktree and the branch are gone, and a diff of the landed commit against the
    base is empty. `--pr` reviews `refs/pull/<n>/head`. `--at` reviews that commit's parent range.
    """
    meta = load_meta(args.id)
    worktree = Path(meta["worktree"])
    note = ""
    if worktree.is_dir() and not (args.pr or args.at):
        repo_path = meta["worktree"]
        head = git("rev-parse", "HEAD", cwd=worktree, check=False) or "unknown"
        spec = diff_spec(worktree, meta["base"], "HEAD") or f"{base_ref(meta['base'])}...HEAD"
    else:
        _repo, head, spec, note = review_target(meta, args.pr or "", args.at or "")
        repo_path = meta["worktree"] if worktree.is_dir() else str(_repo)
    print(f"ticket: {work_dir(args.id) / 'ticket.md'}")
    print(f"worktree: {meta['worktree']}" if worktree.is_dir() else "worktree: gone")
    print(f"commit: {head}")
    print(f"base: {meta['base']}")
    print(f"main checkout: {main_root()}")
    print(f"diff: git -C {shlex.quote(repo_path)} diff {spec}")
    if note:
        print(f"reviewing: {note}")
    if not worktree.is_dir():
        print(f"checkout: git worktree add --detach <a folder outside the repository> {head}")
    try:
        declared = load_checks(meta["base"])
    except Refuse:
        declared = {}
    for name in meta["checks"]:
        print(f"check {name}: {declared.get(name, '(no longer declared)')}")
    override = active_verify_dir(args.id)
    if override is not None:
        files = verify_override_files(override)
        print(f"verify override: {override}" + (f" ({', '.join(files)})" if files else ""))
    print(f"pr: {public_url(str(meta.get('pr') or '-'))}")


# pass only when every check conclusion is exactly SUCCESS.
# SKIPPED, NEUTRAL, and an empty, null, or missing rollup are not a pass and not "no checks".
# absent is the empty rollup. none is only what a pr_state command prints when the repository has no checks.
CI_QUERY = (
    '(if .state == "OPEN" and .isDraft then "DRAFT" else .state end) + " " + .headRefOid + " " + '
    '((.statusCheckRollup | if type == "array" then . else null end) as $roll | '
    'if $roll == null or ($roll | length) == 0 then "absent" '
    'elif any($roll[]; ((.conclusion // .state // "PENDING") as $c | '
    '$c == "FAILURE" or $c == "ERROR" or $c == "TIMED_OUT" or $c == "CANCELLED" or $c == "ACTION_REQUIRED" or $c == "STARTUP_FAILURE")) then "fail" '
    'elif all($roll[]; (.conclusion // .state // "PENDING") == "SUCCESS") then "pass" '
    'else "pending" end)'
)


PR_STATES = ["OPEN", "DRAFT", "MERGED", "CLOSED"]
CI_STATES = ["pass", "fail", "pending", "none", "absent"]
ACTIVE_PR_STATES = ("OPEN", "DRAFT")
FORGES = ("gh", "glab")
GITLAB_STATES = {"opened": "OPEN", "locked": "OPEN", "merged": "MERGED", "closed": "CLOSED"}
GITLAB_CI = {"success": "pass", "failed": "fail", "canceled": "fail", "skipped": "none"}


def run_argv(argv: list[str], *, cwd: Path | None = None, input_bytes: bytes | None = None, timeout: float = 60):
    """Run one program from an argument list. There is no shell, so the arguments are not a command line."""
    return subprocess.run(argv, cwd=cwd, capture_output=True, input=input_bytes, text=input_bytes is None, timeout=timeout)


def origin_host(cwd: Path | None = None) -> str:
    """Hostname of remote.origin.url (lowercased, without port), or "" when there is no remote host."""
    url = origin_url(cwd)
    if not url:
        return ""
    host, _ = repo_identity(url)
    if not host:
        return ""
    if host.startswith("["):
        return host.partition("]")[0].lstrip("[")
    return host.split(":", 1)[0]


def select_forge(base: str = "", cwd: Path | None = None) -> str:
    """Choose the forge CLI (`gh` or `glab`) from machine config, else origin host and PATH."""
    configured = load_settings(base, cwd)["forge"]
    if configured in FORGES:
        return configured
    host = origin_host(cwd)
    if host and host != "github.com" and shutil.which("glab"):
        return "glab"
    return "gh"


def parse_gitlab_mr(url: str) -> tuple[str, str, str] | None:
    """Return (hostname, project path, merge request number) for a GitLab link, or None."""
    link = urllib.parse.urlparse(url)
    project, mark, number = link.path.strip("/").partition("/-/merge_requests/")
    number = number.split("/", 1)[0]
    if link.scheme not in ("http", "https") or not link.hostname or link.hostname.startswith("-"):
        return None
    if not project or not mark or not number.isdigit():
        return None
    return link.hostname, project, number


def forge_cwd(cwd: Path | None = None) -> Path | None:
    if cwd is not None:
        return cwd
    try:
        return main_root()
    except Refuse:
        return None


def comment_permission_denied(text: str) -> bool:
    """True when `gh pr comment` failed because the token cannot add a comment."""
    folded = re.sub(r"\s+", "", text).lower()
    return "addcomment" in folded or "resourcenotaccessible" in folded


def proc_text(proc: subprocess.CompletedProcess) -> str:
    heard = []
    for chunk in (proc.stderr, proc.stdout):
        if isinstance(chunk, bytes):
            heard.append(chunk.decode(errors="replace"))
        elif chunk:
            heard.append(chunk)
    return "\n".join(heard)


def open_draft(base: str, title: str, body_path: Path, *, head: str = "", forge: str = "",
               cwd: Path | None = None) -> tuple[bool, str]:
    """Open a draft pull or merge request on the chosen forge. Returns (ok, url or error)."""
    chosen = forge or select_forge(base, cwd)
    run_dir = forge_cwd(cwd)
    if chosen == "glab":
        try:
            body_text = body_path.read_text()
        except (OSError, ValueError) as err:
            return False, f"cannot read {body_path}: {err}."
        argv = ["glab", "mr", "create", "--draft", "--target-branch", base, "--title", title,
                "--description", body_text, "--yes"]
        if head:
            argv += ["--source-branch", head]
        label = "glab mr create --draft"
    else:
        argv = ["gh", "pr", "create", "--draft", "--base", base, "--title", title, "--body-file", str(body_path)]
        if head:
            argv += ["--head", head]
        label = "gh pr create --draft"
    try:
        proc = run_argv(argv, cwd=run_dir, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, f"`{label}` did not run ({err})."
    if proc.returncode != 0:
        err = redact(" ".join(proc_text(proc).split())[:300])
        return False, f"`{label}` failed: {err or f'ended with {proc.returncode}'}."
    links = re.findall(r"https?://\S+", proc.stdout or "")
    if not links:
        return False, f"`{label}` printed no link."
    return True, links[-1]


def mark_ready(url: str, *, base: str = "", forge: str = "", cwd: Path | None = None) -> tuple[bool, str]:
    """Mark a draft pull or merge request ready for review. Returns (ok, command or error)."""
    chosen = forge or select_forge(base, cwd)
    run_dir = forge_cwd(cwd)
    if chosen == "glab":
        parsed = parse_gitlab_mr(url)
        if not parsed:
            return False, f"not a GitLab merge request link: {public_url(url)}."
        host, project, number = parsed
        argv = ["glab", "mr", "update", number, "--ready", "-R", f"{host}/{project}"]
        label = "glab mr update --ready"
    else:
        argv = ["gh", "pr", "ready", url]
        label = "gh pr ready"
    try:
        proc = run_argv(argv, cwd=run_dir, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, f"`{label}` did not run ({err})."
    if proc.returncode == 0:
        return True, label
    err = redact(" ".join(proc_text(proc).split())[:300])
    return False, f"`{label}` failed: {err or f'ended with {proc.returncode}'}."


def comment(url: str, body_path: Path, text: str, *, base: str = "", forge: str = "",
            cwd: Path | None = None) -> tuple[bool, str]:
    """Post a review comment on the pull or merge request. Returns (posted, how or why).

    On GitHub, tries `gh pr comment` first and falls back to an issue comment via `gh api` when
    addComment or Resource not accessible is returned. On GitLab, uses `glab mr note`.
    """
    chosen = forge or select_forge(base, cwd)
    if chosen == "glab":
        parsed = parse_gitlab_mr(url)
        if not parsed:
            return False, f"not a GitLab merge request link: {public_url(url)}."
        host, project, number = parsed
        try:
            proc = run_argv(["glab", "mr", "note", number, "-R", f"{host}/{project}", "-m", text],
                            cwd=forge_cwd(cwd), timeout=60)
        except (OSError, subprocess.TimeoutExpired) as err:
            return False, f"`glab mr note` did not run ({err})."
        if proc.returncode == 0:
            return True, "glab mr note"
        err = redact(" ".join(proc_text(proc).split())[:300])
        return False, f"`glab mr note` failed: {err or f'ended with {proc.returncode}'}."
    try:
        proc = run_argv(["gh", "pr", "comment", url, "--body-file", str(body_path)], timeout=60)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, f"`gh pr comment` did not run ({err})."
    if proc.returncode == 0:
        return True, "gh pr comment"
    blob = proc_text(proc)
    err = redact(" ".join(blob.split())[:300])
    # addComment on stdout is the same denial as on stderr. Other errors still do not call gh api.
    if not comment_permission_denied(blob):
        return False, f"`gh pr comment` failed: {err}."
    parsed = parse_github_pull(url)
    if not parsed:
        return False, (f"`gh pr comment` failed: {err}. The link is not a github.com pull request, "
                       "so an issue comment cannot be posted with `gh api`.")
    owner, repo, number = parsed
    payload = json.dumps({"body": text}).encode()
    try:
        api = run_argv(
            ["gh", "api", "--method", "POST", "--input", "-", f"repos/{owner}/{repo}/issues/{number}/comments"],
            input_bytes=payload, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as err_api:
        return False, f"`gh pr comment` failed: {err}. `gh api` did not run ({err_api})."
    if api.returncode == 0:
        return True, "gh api repos/.../issues/.../comments"
    api_err = redact(" ".join(api.stderr.decode(errors="replace").split())[:300])
    return False, f"`gh pr comment` failed ({err}). `gh api` issue comment failed: {api_err}."


def state(url: str, *, base: str = "", forge: str = "", cwd: Path | None = None) -> tuple[str, str, str, str]:
    """Read (state, head commit, CI state, problem) from the built-in forge (`gh` or `glab`)."""
    chosen = forge or select_forge(base, cwd)
    run_dir = forge_cwd(cwd)
    if chosen == "glab":
        parsed = parse_gitlab_mr(url)
        if not parsed:
            return ("unknown", "", "unknown", redact(f"not a GitLab merge request link: {url}"))
        host, project, number = parsed
        try:
            proc = run_argv(["glab", "mr", "view", number, "-R", f"{host}/{project}", "--output", "json"],
                            cwd=run_dir, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as err:
            return ("unknown", "", "unknown", redact(f"did not run: {type(err).__name__}: {err}"))
        if proc.returncode != 0:
            problem = f"ended with {proc.returncode}: {' '.join(proc.stderr.split())[:200]}"
            return ("unknown", "", "unknown", redact(problem))
        try:
            mr_data = json.loads(proc.stdout)
        except ValueError as err:
            return ("unknown", "", "unknown", redact(f"printed invalid JSON: {err}"))
        if not isinstance(mr_data, dict):
            return ("unknown", "", "unknown", "the GitLab answer is not a JSON object")
        mr_state = GITLAB_STATES.get(str(mr_data.get("state") or ""))
        if mr_state == "OPEN" and (mr_data.get("draft") or mr_data.get("work_in_progress")):
            mr_state = "DRAFT"
        head = str(mr_data.get("sha") or "")
        if not head and isinstance(mr_data.get("diff_refs"), dict):
            head = str(mr_data["diff_refs"].get("head_sha") or "")
        if not mr_state or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
            return ("unknown", "", "unknown", "the GitLab answer has no state or full head commit")
        pipeline = mr_data.get("head_pipeline")
        if not isinstance(pipeline, dict) or not pipeline:
            ci = "none"
        else:
            ci = GITLAB_CI.get(str(pipeline.get("status") or ""), "pending")
            if ci == "pass" and pipeline.get("sha") not in (None, head):
                ci = "pending"  # green for another commit proves nothing; red still counts
        return (mr_state, head, ci, "")
    command = ["gh", "pr", "view", url, "--json", "state,isDraft,headRefOid,statusCheckRollup", "-q", CI_QUERY]
    problem = ""
    parts: list[str] = []
    try:
        proc = run_argv(command, cwd=run_dir, timeout=60)
        parts = proc.stdout.split()
        if proc.returncode != 0:
            problem = f"ended with {proc.returncode}: {' '.join(proc.stderr.split())[:200]}"
        elif (len(parts) != 3 or parts[0] not in PR_STATES or parts[2] not in CI_STATES
              or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", parts[1])):
            problem = (f"printed `{' '.join(parts)[:120]}`. It must print three words: {', '.join(PR_STATES[:-1])} or "
                       f"{PR_STATES[-1]}; the full head commit; and {', '.join(CI_STATES[:-1])} or {CI_STATES[-1]}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        problem = f"did not run: {type(err).__name__}: {err}"
    if problem:
        return ("unknown", "", "unknown", redact(problem))
    return (parts[0], parts[1], parts[2], "")


def pr_info(url: str, base: str = "") -> tuple[str, str, str, str]:
    """Return (state, head commit, CI state, problem) of a pull request.
    State is OPEN, DRAFT, MERGED, or CLOSED. CI state is pass, fail, pending, none, or absent.
    Uses built-in `gh` or `glab` via `state`, unless `pr_state` in the machine config overrides it.
    A project that names its own `pr_state` command gets a refusal, and not "unknown", when that command does not answer."""
    custom = load_settings(base or base_branch())["pr_state"]
    if not custom:
        return state(url, base=base)
    problem = ""
    parts: list[str] = []
    try:
        command = shlex.split(custom) + [url]
        proc = run_argv(command, cwd=main_root(), timeout=60)
        parts = proc.stdout.split()
        if proc.returncode != 0:
            problem = f"ended with {proc.returncode}: {' '.join(proc.stderr.split())[:200]}"
        elif (len(parts) != 3 or parts[0] not in PR_STATES or parts[2] not in CI_STATES
              or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", parts[1])):
            problem = (f"printed `{' '.join(parts)[:120]}`. It must print three words: {', '.join(PR_STATES[:-1])} or "
                       f"{PR_STATES[-1]}; the full head commit; and {', '.join(CI_STATES[:-1])} or {CI_STATES[-1]}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        problem = f"did not run: {type(err).__name__}: {err}"
    if problem:
        raise Refuse(f"the `pr_state` command of {config_name()} {problem}")
    return (parts[0], parts[1], parts[2], "")


def pr_conflicts(url: str, base: str = "") -> bool:
    """Whether the forge says the pull request cannot merge into its base as it is. Unknown counts as no."""
    if load_settings(base or base_branch())["pr_state"]:
        return False
    if select_forge(base) == "glab":
        parsed = parse_gitlab_mr(url)
        if not parsed:
            return False
        host, project, number = parsed
        try:
            proc = run_argv(["glab", "mr", "view", number, "-R", f"{host}/{project}", "--output", "json"],
                            cwd=main_root(), timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if proc.returncode != 0:
            return False
        try:
            mr_data = json.loads(proc.stdout)
        except ValueError:
            return False
        return isinstance(mr_data, dict) and bool(mr_data.get("has_conflicts"))
    try:
        proc = run_argv(["gh", "pr", "view", url, "--json", "mergeable", "-q", ".mergeable"], cwd=main_root(), timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "CONFLICTING"


def post_review_comment(url: str, body_path: Path, text: str, base: str = "") -> tuple[bool, str]:
    """Post `text` on a pull or merge request using the selected forge."""
    return comment(url, body_path, text, base=base)


def cmd_comment(args: argparse.Namespace) -> None:
    """Post the verdict comment. A failure names the file that holds it and does not exit 0."""
    meta = load_meta(args.id)
    work = work_dir(args.id)
    pr = " ".join((args.pr or meta.get("pr") or "").split())
    if not pr:
        raise Refuse("no pull request on this ticket. Pass --pr <link>, the one `show` printed.")
    body_path = work / "review-comment.md"
    if not body_path.is_file():
        raise Refuse(f"no comment to post. Run verdict first; it writes {body_path}")
    text = body_path.read_text()
    posted, detail = post_review_comment(pr, body_path, text, meta.get("base", ""))
    if posted:
        print(f"posted: {public_url(pr)} ({detail})")
        return
    fallback = work / "unposted-comment.md"
    fallback.write_text(text)
    raise Refuse(
        f"the comment was not posted on {public_url(pr)}. {detail} "
        f"The comment is in {fallback}. Post that file on the pull request; nothing was posted."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jtek.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a jtek.json template on this machine, not in the repository").set_defaults(func=cmd_other)
    sub.add_parser("migrate", help="move jtek.json and .jtek/ out of this repository into $HOME/.jtek, and move the owner files").set_defaults(func=cmd_other)
    sub.add_parser("guess", help="print guessed check commands for this repository; reads only").set_defaults(func=cmd_other)
    status = sub.add_parser("status", help="read-only readiness line and table of claims, reviews, choices to confirm, and the one next action")
    status.add_argument("--board-file", help="the open tickets, read from the board and saved as JSON; not needed when the tickets are files")
    status.set_defaults(func=cmd_other)
    doctor = sub.add_parser("doctor", help="say what is set up in this repository and what is missing")
    doctor.add_argument("--agents", action="store_true", help="instead: the coding agents on this machine, their models, and the owner's list of reviewers")
    doctor.set_defaults(func=cmd_other)
    reviewer = sub.add_parser("reviewer", help="print the command that starts the reviewer, from the owner's list of reviewers")
    reviewer.add_argument("--vendor", required=True, help="the vendor of the model you run on; an entry of that vendor is used only when no other is installed")
    reviewer.set_defaults(func=cmd_other)

    lesson = sub.add_parser("lesson", help="record a mistake; the second time must name a structural rule")
    lesson.add_argument("--mistake", required=True, help="what was done, and what should have been done")
    lesson.add_argument("--enforced-by", default="", help="prose the first time; then architecture, a type, a lint rule that says what to use instead, or a test")
    lesson.set_defaults(func=cmd_lesson)

    ticket = sub.add_parser("ticket", help="check a drafted ticket file the way start will, without claiming it")
    ticket.add_argument("file")
    ticket.add_argument("--save", action="store_true", help="only without a board: keep the checked draft as a ticket file, with the next id and Status Backlog")
    ticket.set_defaults(func=cmd_ticket)

    start = sub.add_parser("start", help="claim a ticket and create its worktree")
    start.add_argument("ref", nargs="?", default="", help="the link of the ticket's page on the board; it becomes the `source:` of the result. Without a board: the ticket's id")
    start.add_argument("--local", action="store_true", help="work with no ticket: the file has no id, and the script gives it a LOCAL-<n> one")
    start.add_argument("--from-file", help="the ticket file the outer loop read from the board and saved in the ticket format; not needed when the tickets are files")
    start.add_argument("--resume", action="store_true", help="take over a claim whose session died without a result")
    start.add_argument("--answered", action="store_true", help="only with --local: the human answered the question the ticket stopped with")
    start.add_argument("--no-baseline", action="store_true", help="do not run the checks on the base first")
    start.add_argument("--no-fetch", action="store_true", help="do not fetch the base branch from origin first")
    start.set_defaults(func=cmd_start)

    check = sub.add_parser("check", help="run the declared checks in the worktree")
    check.add_argument("id")
    check.set_defaults(func=cmd_check)

    verdict = sub.add_parser("verdict", help="record a non-author verdict for the current commit")
    verdict.add_argument("id")
    verdict.add_argument("verdict", choices=VERDICTS)
    verdict.add_argument("--by", required=True)
    verdict.add_argument("--commit", help="the `commit:` that `show` printed when the review began (required)")
    verdict.add_argument("--notes-file")
    verdict.add_argument("--pr", help="review refs/pull/<n>/head when the worktree is gone")
    verdict.add_argument("--at", help="the commit that landed on the base, reviewed by its parent range")
    verdict.set_defaults(func=cmd_verdict)

    broke = sub.add_parser("broke", help="record that breaking one Done when item made a declared check fail")
    broke.add_argument("id")
    broke.add_argument("--item", required=True, help="the Done when item number, starting at 1")
    broke.set_defaults(func=cmd_broke)

    comment = sub.add_parser("comment", help="post the verdict comment on the pull request")
    comment.add_argument("id")
    comment.add_argument("--pr", help="the pull request link, when the claim has none")
    comment.set_defaults(func=cmd_comment)

    finish = sub.add_parser("finish", help="move to Review when checks and verdict hold on the current commit")
    finish.add_argument("id")
    finish.add_argument("--pr")
    finish.add_argument("--no-pr", action="store_true", help="only for a repository with no remote, or with `\"forge\": false` in this machine's config")
    finish.add_argument("--evidence-file", help="what was run and seen for each `Done when` item; needed again whenever the code changed")
    finish.add_argument("--attach", action="append", help="a screenshot, recording, or output file to keep with the evidence")
    finish.set_defaults(func=cmd_finish)

    run = sub.add_parser("run", help="run a command in the ticket's worktree and record exactly what ran and what came back")
    run.add_argument("id")
    run.add_argument("--sh", help="one shell line, for a pipe or a redirect")
    run.add_argument("--cwd", help="run somewhere else, such as the main checkout for the base")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)

    evidence = sub.add_parser("evidence", help="check the form of an evidence file before it becomes a pull request body")
    evidence.add_argument("id")
    evidence.add_argument("--file", required=True)
    evidence.set_defaults(func=cmd_evidence)

    stop = sub.add_parser("stop", help="stop and wait for the human")
    stop.add_argument("id")
    stop.add_argument("--waiting", required=True, choices=WAITING)
    stop.add_argument("--note", required=True)
    stop.set_defaults(func=cmd_stop)

    show = sub.add_parser("show", help="print what a reviewer needs")
    show.add_argument("id")
    show.add_argument("--pr", help="review refs/pull/<n>/head when the worktree is gone")
    show.add_argument("--at", help="the commit that landed on the base, reviewed by its parent range")
    show.set_defaults(func=cmd_show)

    for name, func, text in (("result", cmd_result, "print the last result"),
                             ("release", cmd_other, "only when the human asks: drop the claim and the worktree")):
        item = sub.add_parser(name, help=text)
        item.add_argument("id")
        item.set_defaults(func=func)

    for name, func, text in (
        ("next", cmd_other, "for whoever starts sessions: what each open ticket of this repository needs now"),
        ("sync", cmd_other, "read the pull request of each Review ticket from the forge, and remove the worktrees of finished tickets"),
    ):
        item = sub.add_parser(name, help=text)
        item.add_argument("--board-file", help="the open tickets, read from the board and saved as JSON; not needed when the tickets are files")
        item.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Refuse as err:
        print(f"refused: {err}")
        return 1
    except KeyboardInterrupt:
        print("refused: interrupted. If this was `start`, run `jtek.py release <id>` before you start the ticket again")
        return 130
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as err:
        # Not a rule, but a file or a value this script did not expect. Say it plainly instead of a traceback.
        if os.environ.get("JTEK_DEBUG"):
            raise
        print(f"refused: unexpected {type(err).__name__}: {err}. A file under {state_dir()} or an input file may be "
              "damaged or edited by hand. Set JTEK_DEBUG=1 to see where")
        return 2
    return 0


def machine_root() -> Path:
    """Where this machine keeps jtek config. JTEK_HOME overrides $HOME/.jtek. No file there means the defaults."""
    override = os.environ.get("JTEK_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".jtek").resolve()


def machine_config_path() -> Path:
    """Machine-wide defaults. Absent, and with no per-repository file either, the board is empty."""
    return machine_root() / "config"


def owner_file(name: str) -> tuple[Path, str]:
    """The machine file, or the old ~/.config/jtek path when that is the one that exists.

    The notice is one line when the old path is in use, and empty otherwise. A missing file returns the new path.
    """
    new = machine_root() / name
    old = Path.home() / ".config" / "jtek" / name
    if new.is_file() and not new.is_symlink():
        return new, ""
    if old.is_file() and not old.is_symlink():
        return old, f"notice: reading {old}. Run `jtek.py migrate` to move it to {new}."
    return new, ""


def load_reviewers(path: Path) -> list[dict] | None:
    """The owner's list, in the owner's order, or None when there is no file. Every entry is checked before any is used."""
    if not path.is_file():
        return None
    form = ('{"reviewers": [{"command": "codex exec -m <model>", "vendor": "openai", "model": "<model>"}]}')
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read {path}: {err}. Its form is {form}") from None
    entries = data.get("reviewers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise Refuse(f"{path} must hold a `reviewers` list. Its form is {form}")
    reviewers = []
    for number, entry in enumerate(entries, 1):
        values = {key: " ".join(str(entry.get(key) or "").split())
                  if isinstance(entry, dict) and isinstance(entry.get(key), str) else ""
                  for key in ("command", "vendor", "model")}
        lacking = [key for key, value in values.items() if not value]
        if lacking:
            raise Refuse(f"entry {number} of {path} needs " + ", ".join(f"`{key}`" for key in lacking)
                         + f", each a line of text. Its form is {form}")
        try:
            values["program"] = shlex.split(values["command"])[0]
        except (ValueError, IndexError):
            raise Refuse(f"entry {number} of {path}: the command `{values['command']}` has an unbalanced quote") from None
        reviewers.append(values)
    return reviewers


def same_content(src: Path, dest: Path) -> bool:
    """True when src and dest are both regular files with identical bytes, or both directories with identical trees.
    Symlinks are never considered equal."""
    if src.is_symlink() or dest.is_symlink():
        return False
    if src.is_file() and dest.is_file():
        try:
            return src.read_bytes() == dest.read_bytes()
        except OSError:
            return False
    if src.is_dir() and dest.is_dir():
        try:
            src_entries = {p.name: p for p in src.iterdir()}
            dest_entries = {p.name: p for p in dest.iterdir()}
        except OSError:
            return False
        if set(src_entries) != set(dest_entries):
            return False
        return all(same_content(src_entries[name], dest_entries[name]) for name in src_entries)
    return False


def repo_storage_id(url: str, base: Path | None = None) -> str:
    """A repository id safe to use as directories under $HOME/.jtek/repos.

    An origin URL contributes its host, a non-default port, and its path. Userinfo is left out.
    https://github.com/acme/widget.git, ssh://git@github.com/acme/widget.git, and
    git@github.com:acme/widget.git are github.com/acme/widget.
    ssh://git@gitlab.example:2222/acme/widget.git is gitlab.example:2222/acme/widget.
    https://git.example:8443/acme/widget keeps port 8443. The default ports 443, 80, 22, and 9418
    are left out. A trailing slash is left out; a trailing .git is left out only for URLs with a host.
    A local path, and a repository with no origin, is path plus that absolute path, such as
    path/tmp/app (or path/tmp/app.git). A relative local path is resolved against `base` (the checkout) when given.
    .. in host or path is refused so the id cannot step out of $HOME/.jtek/repos.
    """
    text = url.strip()
    host = ""
    port: int | None = None
    scheme = ""
    path = text
    if "://" in text:
        parsed = urllib.parse.urlparse(text)
        scheme = (parsed.scheme or "").lower()
        host = (parsed.hostname or "").lower()
        port = parsed.port
        path = urllib.parse.unquote(parsed.path or "")
    else:
        scp = re.fullmatch(r"(?:[^@/\s]+@)?([^:/\s]+):(.+)", text)
        if scp and not text.startswith("/") and not text.startswith("."):
            host = scp.group(1).lower()
            path = scp.group(2)
    path = path.rstrip("/")
    if host:
        if host in (".", "..") or "/" in host or "\\" in host:
            raise Refuse(f"the repository id for {url} is not usable: host {host!r} is not safe")
        if path.endswith(".git"):
            path = path[:-4]
        path = path.lstrip("/")
    else:
        if base is not None and not os.path.isabs(path):
            anchor = base if base.is_absolute() else base.resolve()
            path = os.path.join(anchor.as_posix(), path)
        path = os.path.normpath(path or ".")
    if "\\" in path:
        raise Refuse(f"the repository id for {url} is not usable: it contains a backslash")
    parts = [part for part in path.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise Refuse(f"the repository id for {url} is not usable: it contains '..'")
    path = "/".join(parts)
    if host:
        default = {"https": 443, "http": 80, "ssh": 22, "git": 9418}.get(scheme)
        if port and port != default:
            host = f"{host}:{port}"
        result = f"{host}/{path}" if path else host
    elif path.startswith("/"):
        result = "path" + path
    else:
        result = "path/" + path
    anchor_repos = Path("/repos")
    resolved = (anchor_repos / result).resolve()
    try:
        resolved.relative_to(anchor_repos)
    except ValueError:
        raise Refuse(f"the repository id for {url} is not usable: it steps outside repos/") from None
    if resolved == anchor_repos:
        raise Refuse(f"the repository id for {url} is not usable: it is empty")
    return result


def _legacy_local_home(home: Path) -> Path | None:
    """For a local/file:// storage home ending in `.git`, return the pre-27.3 stripped folder if it exists."""
    repos_path = machine_root() / "repos" / "path"
    try:
        home.relative_to(repos_path)
    except ValueError:
        return None
    if home.name.endswith(".git") and len(home.name) > 4:
        legacy = home.with_name(home.name[:-4])
        if legacy.exists():
            return legacy
    return None


def candidate_homes(cwd: Path | None = None) -> list[Path]:
    """Per-repository folders, the origin id first and the checkout path second.

    A config written before this clone had an origin still lives under the path id.
    A pre-existing folder under the legacy stripped local id (without `.git`) is also
    checked as a fallback when the new unstripped id does not have the file yet.
    The origin id wins when both have a file of the same kind.
    """
    homes: list[Path] = []
    root = main_root(cwd)
    url = origin_url(cwd)
    if url:
        origin_home = machine_root() / "repos" / repo_storage_id(url, base=root)
        homes.append(origin_home)
        legacy = _legacy_local_home(origin_home)
        if legacy is not None and legacy not in homes:
            homes.append(legacy)
    path_home = machine_root() / "repos" / repo_storage_id(root.as_posix())
    if path_home not in homes:
        homes.append(path_home)
    legacy_path = _legacy_local_home(path_home)
    if legacy_path is not None and legacy_path not in homes:
        homes.append(legacy_path)
    return homes


def repo_home(cwd: Path | None = None) -> Path:
    """Where new files for this repository are written. The origin id when there is an origin."""
    return candidate_homes(cwd)[0]


def find_config(cwd: Path | None = None) -> Path | None:
    """The config file in force: per-repository jtek.json, else $HOME/.jtek/config, else none."""
    for home in candidate_homes(cwd):
        path = home / CONFIG
        if path.is_file():
            return path
    if machine_config_path().is_file():
        return machine_config_path()
    return None


def config_name(cwd: Path | None = None) -> str:
    """The name error text uses. A per-repository file is still called jtek.json."""
    path = find_config(cwd)
    if path is None or path.name == CONFIG:
        return CONFIG
    return str(path)


VERIFY_OVERRIDE_DIR = "verify.d"


def verify_override_dir(ticket_id: str, cwd: Path | None = None) -> Path:
    """Where a ticket keeps whole-file verify overrides under this repository's machine home."""
    return repo_home(cwd) / VERIFY_OVERRIDE_DIR / check_id(ticket_id)


def active_verify_dir(ticket_id: str, cwd: Path | None = None) -> Path | None:
    """The existing per-ticket verify override directory, or None when the ticket has none."""
    tid = check_id(ticket_id)
    for home in candidate_homes(cwd):
        folder = home / VERIFY_OVERRIDE_DIR / tid
        if folder.is_dir() and not folder.is_symlink():
            return folder
    return None


def verify_override_files(folder: Path) -> list[str]:
    """Relative POSIX paths of known knowledge files under one verify.d/<ticket>/ directory."""
    if not folder.is_dir() or folder.is_symlink():
        return []
    found: list[str] = []
    for name in ("verify.md", "rules.md"):
        path = folder / name
        if path.is_file() and not path.is_symlink():
            found.append(name)
    features = folder / "features"
    if features.is_dir() and not features.is_symlink():
        for root_dir, dirnames, filenames in os.walk(features, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not (Path(root_dir) / d).is_symlink())
            for filename in sorted(filenames):
                file_path = Path(root_dir) / filename
                if file_path.is_file() and not file_path.is_symlink():
                    found.append(file_path.relative_to(folder).as_posix())
    return sorted(found)


def knowledge_path(name: str, cwd: Path | None = None, ticket_id: str | None = None) -> Path | None:
    """An existing verify guide, feature directory or file, rules file, or tickets directory.

    When `ticket_id` is given, a matching entry under `verify.d/<ticket_id>/` wins over the main home.
    """
    if ticket_id:
        override = active_verify_dir(ticket_id, cwd)
        if override is not None:
            base_dir = override.resolve()
            candidate = override / name
            try:
                resolved = candidate.resolve()
                resolved.relative_to(base_dir)
            except (OSError, ValueError):
                resolved = None
            if resolved is not None and candidate.exists() and not candidate.is_symlink():
                return candidate
    for home in candidate_homes(cwd):
        path = home / name
        if path.exists():
            return path
    return None


if __name__ == "__main__":
    sys.exit(main())
