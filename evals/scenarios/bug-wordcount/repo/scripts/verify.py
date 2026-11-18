"""Run the real tool on a real file and compare the output."""
import pathlib
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    sample = pathlib.Path(tmp) / "a.txt"
    sample.write_text("one two three")
    out = subprocess.run([sys.executable, "wordcount.py", str(sample)], capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.startswith("3\t"):
        print("unexpected:", out.stdout, out.stderr)
        sys.exit(1)
print("ok")
