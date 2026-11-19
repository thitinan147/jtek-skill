#!/usr/bin/env python3
"""Read a GitLab merge request for jtek: print `STATE HEAD CI`.

Copy this file into your repository, for example to `scripts/pr-state-gitlab.py`, commit it on the base
branch, and name it in jtek.json:

    "pr_state": "python3 scripts/pr-state-gitlab.py"

jtek adds the merge request's link as the last argument. The script needs `glab`, GitLab's command-line
tool, signed in (`glab auth login`). It only reads.

Not run against a real GitLab yet. It is tested against a stand-in for `glab` that returns the fields
GitLab documents for a merge request.
"""
import json
import subprocess
import sys
from urllib.parse import quote, urlparse

STATES = {"opened": "OPEN", "locked": "OPEN", "merged": "MERGED", "closed": "CLOSED"}
CI = {"success": "pass", "failed": "fail", "canceled": "fail", "skipped": "none"}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pr-state-gitlab.py <merge request link>", file=sys.stderr)
        return 2
    link = urlparse(sys.argv[-1])
    project, mark, number = link.path.strip("/").partition("/-/merge_requests/")
    number = number.split("/")[0]
    if not link.hostname or not project or not mark or not number.isdigit():
        print(f"not a merge request link: {sys.argv[-1]}", file=sys.stderr)
        return 2
    path = f"projects/{quote(project, safe='')}/merge_requests/{number}"
    proc = subprocess.run(["glab", "api", "--hostname", link.hostname, path], capture_output=True, text=True, timeout=45)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "glab failed", file=sys.stderr)
        return 1
    request = json.loads(proc.stdout)
    state = STATES.get(str(request.get("state")))
    if state == "OPEN" and (request.get("draft") or request.get("work_in_progress")):
        state = "DRAFT"
    head = str(request.get("sha") or "")
    if not state or not head:
        print("the answer has no state or no head commit", file=sys.stderr)
        return 1
    pipeline = request.get("head_pipeline") or {}
    if not pipeline:
        ci = "none"
    elif pipeline.get("sha") not in (None, head):
        ci = "pending"  # the pipeline shown is for an older commit
    else:
        ci = CI.get(str(pipeline.get("status")), "pending")
    print(state, head, ci)
    return 0


if __name__ == "__main__":
    sys.exit(main())
