"""Run the real tool on the example files and compare the output."""
import subprocess
import sys

expected = {
    "server": '{"host": "0.0.0.0", "port": 9000}',
    "client": '{"timeout": 5.0, "url": "http://example.com/api"}',
}
for kind, want in expected.items():
    out = subprocess.run([sys.executable, "config.py", kind, f"examples/{kind}.conf"], capture_output=True, text=True)
    if out.returncode != 0 or out.stdout.strip() != want:
        print("unexpected:", kind, out.stdout, out.stderr)
        sys.exit(1)
print("ok")
