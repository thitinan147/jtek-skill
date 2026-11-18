"""Run the real tool and compare the output."""
import subprocess
import sys

out = subprocess.run([sys.executable, "slug.py", "Hello", "World"], capture_output=True, text=True)
if out.returncode != 0 or out.stdout.strip() != "hello-world":
    print("unexpected:", out.stdout, out.stderr)
    sys.exit(1)
print("ok")
