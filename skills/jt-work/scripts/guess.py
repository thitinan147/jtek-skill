#!/usr/bin/env python3
"""`jtek.py guess`: propose check commands for this repository. Read-only.

It looks at the root package.json script names, Makefile target names, pyproject.toml
tool sections, and the `run:` lines of .github/workflows. It never opens a dotenv file,
and it prints a command only when that command matches a fixed shape. `j` is the jtek module.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


ASK = "board? none (tickets as files) / Notion database link / FLO product link"
ORDER = ("setup", "secrets", "lint", "types", "test", "audit", "verify")
MAX_BYTES = 1_000_000
DOTENV = "." + "env"

# A command is printed only when it matches one of these. The first matching kind wins.
SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("setup", re.compile(r"^npm ci$")),
    ("setup", re.compile(r"^pnpm install --frozen-lockfile$")),
    ("setup", re.compile(r"^yarn install --frozen-lockfile$")),
    ("setup", re.compile(r"^bun install --frozen-lockfile$")),
    ("setup", re.compile(r"^uv sync$")),
    ("setup", re.compile(r"^go mod download$")),
    ("setup", re.compile(r"^cargo fetch$")),
    ("setup", re.compile(r"^pip install -r requirements\.txt$")),
    ("secrets", re.compile(r"^gitleaks detect(?: --source \.)?$")),
    ("secrets", re.compile(r"^(?:npm|pnpm|bun) run (?:secrets|gitleaks|secretlint)$")),
    ("secrets", re.compile(r"^yarn (?:secrets|gitleaks|secretlint)$")),
    ("secrets", re.compile(r"^make gitleaks$")),
    ("audit", re.compile(r"^(?:npm|pnpm|yarn|bun) audit$")),
    ("audit", re.compile(r"^(?:npm|pnpm|bun) run audit$")),
    ("audit", re.compile(r"^yarn audit$")),
    ("audit", re.compile(r"^make audit$")),
    ("types", re.compile(r"^(?:npm|pnpm|bun) run (?:typecheck|type-check|types|tsc|mypy|pyright)$")),
    ("types", re.compile(r"^yarn (?:typecheck|type-check|types|tsc|mypy|pyright)$")),
    ("types", re.compile(r"^uv run mypy \.$")),
    ("types", re.compile(r"^mypy \.$")),
    ("types", re.compile(r"^make (?:typecheck|types|mypy)$")),
    ("verify", re.compile(r"^(?:npm|pnpm|bun) run (?:verify|e2e|acceptance)$")),
    ("verify", re.compile(r"^yarn (?:verify|e2e|acceptance)$")),
    ("verify", re.compile(r"^make (?:verify|e2e)$")),
    ("verify", re.compile(r"^node scripts/[A-Za-z0-9_./-]{1,80}$")),
    ("test", re.compile(r"^(?:npm|pnpm|yarn) test$")),
    ("test", re.compile(r"^(?:npm|pnpm|bun) run tests?$")),
    ("test", re.compile(r"^bun run test$")),
    ("test", re.compile(r"^uv run pytest -q$")),
    ("test", re.compile(r"^pytest -q$")),
    ("test", re.compile(r"^go test \./\.\.\.$")),
    ("test", re.compile(r"^cargo test$")),
    ("test", re.compile(r"^make test$")),
    ("lint", re.compile(r"^(?:npm|pnpm|bun) run (?:lint|eslint|stylelint)$")),
    ("lint", re.compile(r"^yarn (?:lint|eslint|stylelint)$")),
    ("lint", re.compile(r"^uv run ruff check \.$")),
    ("lint", re.compile(r"^ruff check \.$")),
    ("lint", re.compile(r"^go vet \./\.\.\.$")),
    ("lint", re.compile(r"^cargo clippy$")),
    ("lint", re.compile(r"^make (?:lint|eslint)$")),
)

SCRIPT_KEYS = {
    "secrets": ("secrets", "gitleaks", "secretlint"),
    "lint": ("lint", "eslint", "stylelint"),
    "types": ("typecheck", "type-check", "types", "tsc", "mypy", "pyright"),
    "test": ("test", "tests"),
    "audit": ("audit",),
    "verify": ("verify", "e2e", "acceptance"),
}
MAKE_KEYS = {
    "lint": "lint", "eslint": "lint",
    "typecheck": "types", "types": "types", "mypy": "types",
    "test": "test", "verify": "verify", "e2e": "verify",
    "audit": "audit", "gitleaks": "secrets",
}


def skipped_name(name: str) -> bool:
    """True for a dotenv file or a name that holds credentials. Those files are not opened."""
    low = name.lower()
    return low == DOTENV or low.startswith(DOTENV) or "secret" in low or "credential" in low or low.endswith(".pem")


def open_text(root: Path, path: Path) -> str | None:
    if skipped_name(path.name) or path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if skipped_name(resolved.name):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def classify(command: str) -> tuple[str, str] | None:
    text = " ".join(command.split())
    if not text or "$" in text or "`" in text or DOTENV in text.lower():
        return None
    for kind, shape in SHAPES:
        if shape.fullmatch(text):
            return kind, text
    return None


def pieces(command: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*(?:&&|\|\||[|;])\s*", command) if part.strip()]


def add(found: dict[str, tuple[str, str]], kind: str, command: str, source: str) -> None:
    hit = classify(command)
    if hit is None or hit[0] != kind or kind in found:
        return
    found[kind] = (hit[1], source)


def plain_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def package_manager(root: Path) -> str:
    if plain_file(root / "pnpm-lock.yaml"):
        return "pnpm"
    if plain_file(root / "yarn.lock"):
        return "yarn"
    if plain_file(root / "bun.lock") or plain_file(root / "bun.lockb"):
        return "bun"
    return "npm"


def pm_command(pm: str, script: str) -> str:
    if pm == "bun":
        return f"bun run {script}"
    if script == "test" and pm in {"npm", "pnpm", "yarn"}:
        return f"{pm} test"
    if pm == "yarn":
        return f"yarn {script}"
    return f"{pm} run {script}"


def from_package(root: Path, found: dict[str, tuple[str, str]]) -> None:
    path = root / "package.json"
    text = open_text(root, path)
    if text is None:
        return
    try:
        data = json.loads(text)
    except ValueError:
        return
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return
    names = {str(key) for key, value in scripts.items() if isinstance(key, str) and isinstance(value, str) and value.strip()}
    pm = package_manager(root)
    source = "package.json"
    for kind, keys in SCRIPT_KEYS.items():
        for key in keys:
            if key in names:
                add(found, kind, pm_command(pm, key), source)
                break


def from_make(root: Path, found: dict[str, tuple[str, str]]) -> None:
    path = next((root / name for name in ("Makefile", "makefile", "GNUmakefile") if (root / name).is_file()), None)
    if path is None:
        return
    text = open_text(root, path)
    if text is None:
        return
    source = path.name
    for line in text.splitlines():
        if not line or line[0] in " \t#":
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_.-]*)\s*:", line)
        if not match:
            continue
        kind = MAKE_KEYS.get(match.group(1))
        if kind:
            add(found, kind, f"make {match.group(1)}", source)


def from_pyproject(root: Path, found: dict[str, tuple[str, str]]) -> None:
    path = root / "pyproject.toml"
    text = open_text(root, path)
    if text is None:
        return
    sections = set(re.findall(r"(?m)^\[([A-Za-z0-9_.-]+)\]", text))
    prefix = "uv run " if (root / "uv.lock").is_file() or "tool.uv" in sections else ""
    source = "pyproject.toml"
    if "tool.ruff" in sections or any(name.startswith("tool.ruff.") for name in sections):
        add(found, "lint", f"{prefix}ruff check .", source)
    if "tool.mypy" in sections:
        add(found, "types", f"{prefix}mypy .", source)
    if "tool.pytest" in sections or "tool.pytest.ini_options" in sections:
        add(found, "test", f"{prefix}pytest -q", source)


def run_commands(text: str) -> list[str]:
    """The scalar values of `run:` keys. Other lines, including env values, are ignored."""
    commands: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*?)\s*$", lines[index])
        if not match:
            index += 1
            continue
        rest = match.group(2).strip()
        if rest in {"|", ">", "|-", ">-", "|+", ">+"}:
            base = len(match.group(1))
            index += 1
            block: list[str] = []
            while index < len(lines):
                line = lines[index]
                if line.strip() == "":
                    index += 1
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if indent <= base:
                    break
                block.append(line.strip())
                index += 1
            if block:
                commands.append(" ".join(block))
            continue
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
            rest = rest[1:-1]
        if rest:
            commands.append(rest)
        index += 1
    return commands


def from_workflows(root: Path, found: dict[str, tuple[str, str]]) -> None:
    folder = root / ".github" / "workflows"
    if not folder.is_dir() or folder.is_symlink():
        return
    for path in sorted(folder.iterdir()):
        if path.suffix not in {".yml", ".yaml"}:
            continue
        text = open_text(root, path)
        if text is None:
            continue
        source = path.relative_to(root).as_posix()
        for command in run_commands(text):
            for piece in pieces(command):
                hit = classify(piece)
                if hit is not None and hit[0] not in found:
                    found[hit[0]] = (hit[1], source)


def setup_from_files(root: Path) -> tuple[str, str] | None:
    pm = package_manager(root)
    if plain_file(root / "package.json") and pm == "npm" and plain_file(root / "package-lock.json"):
        return "npm ci", "package-lock.json"
    if plain_file(root / "pnpm-lock.yaml"):
        return "pnpm install --frozen-lockfile", "pnpm-lock.yaml"
    if plain_file(root / "yarn.lock"):
        return "yarn install --frozen-lockfile", "yarn.lock"
    if plain_file(root / "bun.lock") or plain_file(root / "bun.lockb"):
        return "bun install --frozen-lockfile", "bun.lock"
    if plain_file(root / "uv.lock"):
        return "uv sync", "uv.lock"
    if plain_file(root / "go.mod") and not plain_file(root / "package.json"):
        return "go mod download", "go.mod"
    if plain_file(root / "Cargo.lock"):
        return "cargo fetch", "Cargo.lock"
    if plain_file(root / "requirements.txt") and not plain_file(root / "pyproject.toml"):
        return "pip install -r requirements.txt", "requirements.txt"
    return None


def collect(root: Path) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    setup = setup_from_files(root)
    if setup is not None:
        add(found, "setup", setup[0], setup[1])
    from_package(root, found)
    from_make(root, found)
    from_pyproject(root, found)
    from_workflows(root, found)
    return found


def run(j, args) -> None:
    del args
    root = j.main_root()
    found = collect(root)
    if not any(kind in found for kind in ORDER):
        print("guess\t-\t-\tnothing to guess")
    else:
        for kind in ORDER:
            if kind in found:
                command, source = found[kind]
                print(f"guess\t{kind}\t{command}\t{source}")
    print(f"ask\t{ASK}")
