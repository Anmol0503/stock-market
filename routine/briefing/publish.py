"""Commit + push ONLY dashboard/briefing/. Anything else staged aborts the publish (the cloud owns the news
data; the Mac owns the code; never `git add -A`)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from . import config

PREFIX = "dashboard/briefing/"


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    base = ["git"]
    # On the Mac, push through the gh credential helper (the keychain holds a different account).
    if not os.environ.get("CLAUDE_CODE_REMOTE") and shutil.which("gh"):
        base += ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
    return subprocess.run(base + list(args), cwd=config.ROOT, capture_output=True, text=True, check=check)


def publish(date: str, *, branch: str | None = None, dry_run: bool = False) -> str:
    ed = {}
    try:
        ed = json.loads((config.PUB / f"{date}.json").read_text())
    except (OSError, ValueError):
        pass
    _git("add", "--", PREFIX)
    staged = [p for p in _git("diff", "--cached", "--name-only").stdout.split("\n") if p]
    outside = [p for p in staged if not p.startswith(PREFIX)]
    if outside:
        _git("reset", "-q", "--", *outside, check=False)
        return f"ABORTED: files outside {PREFIX} were staged: {', '.join(outside[:5])}"
    if not staged:
        return "nothing to publish"
    label = ed.get("edition") or "quality report only"
    msg = f"briefing: {date} {label} ({ed.get('status', 'failed')})"
    if dry_run:
        _git("reset", "-q", "--", PREFIX, check=False)
        return f"DRY RUN: would commit {len(staged)} files: {msg}"
    _git("commit", "-q", "-m", msg)
    sha = _git("rev-parse", "--short", "HEAD").stdout.strip()
    if branch:
        r = _git("push", "-q", "-f", "origin", f"HEAD:refs/heads/{branch}", check=False)
        return f"{sha} pushed to {branch}" if r.returncode == 0 else f"{sha} push to {branch} FAILED: {r.stderr[-300:]}"
    err = ""
    for attempt in range(3):
        _git("pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)
        r = _git("push", "-q", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            return f"{_git('rev-parse', '--short', 'HEAD').stdout.strip()} push OK"
        err = r.stderr[-300:]
        time.sleep(5 * (attempt + 1))
    return f"{sha} push FAILED: {err}"
