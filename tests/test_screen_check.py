import importlib.util
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-next-step" / "gate.py"
CLI = REPO / "scripts" / "jt-screen-check"


def load_gate():
    spec = importlib.util.spec_from_file_location("tek_screen_gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tek_screen_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = load_gate()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def write_exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class ResolveBrowserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = "/usr/bin:/bin"

    def tearDown(self) -> None:
        os.environ["PATH"] = self.old_path

    def test_local_playwright_bin_beats_a_declared_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"devDependencies":{"cypress":"1.0.0","@playwright/test":"1.0.0"}}\n',
                encoding="utf-8",
            )
            write_exe(root / "node_modules" / ".bin" / "playwright", "#!/bin/sh\nexit 0\n")
            argv = gate.resolve_browser_argv(root, "")
            self.assertEqual(argv, [str(root / "node_modules" / ".bin" / "playwright"), "test"])

    def test_path_cypress_when_playwright_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = Path(tmp) / "bin"
            write_exe(bindir / "cypress", "#!/bin/sh\nexit 0\n")
            os.environ["PATH"] = str(bindir)
            argv = gate.resolve_browser_argv(root, "")
            self.assertEqual(argv, ["cypress", "run"])

    def test_named_tool_does_not_fall_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = Path(tmp) / "bin"
            write_exe(bindir / "cypress", "#!/bin/sh\nexit 0\n")
            os.environ["PATH"] = str(bindir)
            argv = gate.resolve_browser_argv(root, "playwright")
            self.assertIsNone(argv)

    def test_declared_package_uses_npx_without_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"devDependencies":{"@playwright/test":"1.0.0"}}\n',
                encoding="utf-8",
            )
            self.assertEqual(
                gate.resolve_browser_argv(root, "playwright"),
                ["npx", "--no-install", "playwright", "test"],
            )

    def test_unknown_tool_name_is_not_a_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(gate.resolve_browser_argv(Path(tmp), "selenium"))


class ScreenCheckCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bindir = self.root / "bin"
        self.old_path = os.environ.get("PATH", "")

    def tearDown(self) -> None:
        os.environ["PATH"] = self.old_path
        self.tmp.cleanup()

    def _playwright(self, body: str) -> None:
        write_exe(self.bindir / "playwright", body)
        os.environ["PATH"] = f"{self.bindir}:{self.old_path}"

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    def test_help_names_jtek_and_exits_zero(self) -> None:
        result = self._run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("JTek", result.stdout)

    def test_missing_browser_exits_nonzero(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        result = self._run("--root", str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("screen-check: browser-missing", result.stdout)
        self.assertNotIn("รอรีวิว", result.stdout)

    def test_browser_failure_exits_nonzero(self) -> None:
        self._playwright("#!/bin/sh\nexit 3\n")
        result = self._run("--root", str(self.root), "--no-start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("screen-check: browser-failed", result.stdout)

    def test_no_start_does_not_launch_the_app(self) -> None:
        self._playwright("#!/bin/sh\nexit 0\n")
        result = self._run(
            "--root",
            str(self.root),
            "--no-start",
            "--start",
            "python3 -c 'import sys; sys.exit(1)'",
            "--port",
            "9",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("screen-check: ok", result.stdout)

    def test_start_failure_exits_nonzero(self) -> None:
        self._playwright("#!/bin/sh\nexit 0\n")
        result = self._run(
            "--root",
            str(self.root),
            "--start",
            "python3 -c 'import sys; sys.exit(1)'",
            "--port",
            str(free_port()),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("screen-check: start-down", result.stdout)

    def test_start_then_browser_tool_and_the_port_closes(self) -> None:
        port = free_port()
        marker = self.root / "hit"
        self._playwright(
            "#!/bin/sh\n"
            f"python3 -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:{port}/\")'\n"
            f"touch {marker}\n"
        )
        result = self._run(
            "--root",
            str(self.root),
            "--start",
            f"python3 -m http.server {port}",
            "--port",
            str(port),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("screen-check: ok", result.stdout)
        self.assertTrue(marker.is_file())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))

    def test_id_reads_the_card_and_the_board_tool(self) -> None:
        port = free_port()
        card_dir = self.root / "card-loop" / "backlog"
        card_dir.mkdir(parents=True)
        (self.root / "card-loop" / "board.md").write_text(
            "| `<BROWSER_TOOL>` | playwright |\n",
            encoding="utf-8",
        )
        (card_dir / "12.md").write_text(
            f"เห็นจอ: ใช่\nเริ่ม: python3 -m http.server {port}\nพอร์ต: {port}\nรอ: 5\nคลิก:\n",
            encoding="utf-8",
        )
        self._playwright(
            "#!/bin/sh\n"
            f"python3 -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:{port}/\")'\n"
        )
        result = self._run("--root", str(self.root), "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("screen-check: ok", result.stdout)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))


class ScreenCheckDocTests(unittest.TestCase):
    def test_skills_prefer_the_fixed_cli_and_still_refuse_one_off_checkers(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        rule = (REPO / "skills" / "jt-card-gate" / "SKILL.md").read_text(encoding="utf-8")
        nxt = (REPO / "skills" / "jt-next-step" / "SKILL.md").read_text(encoding="utf-8")
        for text in (readme, work, loop, rule, nxt):
            self.assertIn("scripts/jt-screen-check", text)
            self.assertIn("JTek", text)
            self.assertIn("คำสั่งตรวจที่มีอยู่", text)
        self.assertIn("refused: one-off-checker", work)
        self.assertIn("refused: one-off-checker", nxt)
        self.assertIn("one-off-checker", GATE_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("เริ่ม:", loop)
        self.assertNotIn("พอร์ต:", loop)
        self.assertNotIn("คลิก:", loop)
        self.assertNotIn("one-off-checker", loop)
        self.assertEqual(readme.count("\n## "), 4)
        self.assertTrue(os.access(CLI, os.X_OK))
