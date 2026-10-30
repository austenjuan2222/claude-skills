#!/usr/bin/env python3
"""SessionStart hook: fast-forward every Git-managed skill root from its remote, then re-index.

Silent by design (hook stdout would be injected into the session). Never blocks the session:
offline, auth prompts, local edits or diverged branches just skip the pull for that repo.
Outcomes go to session_start.log (last 200 lines kept).
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_index as si  # noqa: E402

LOG = si.CONFIG_PATH.parent / "session_start.log"
PULL_TIMEOUT = 20  # seconds per repo


def git(root: str, *args: str, timeout: int = PULL_TIMEOUT) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env)


def pull(root: str) -> str:
    if not (Path(root) / ".git").exists():
        return "skip (not a git repo root)"
    try:
        if git(root, "remote").stdout.strip() == "":
            return "skip (no remote)"
        before = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
        r = git(root, "pull", "--ff-only", "--quiet")
        if r.returncode != 0:
            return f"skip (pull failed: {(r.stderr or r.stdout).strip().splitlines()[-1:] or ['?']})"
        after = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
        return f"updated {before}..{after}" if before != after else "up to date"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"skip ({type(e).__name__})"


def main():
    cfg = si.load_config()
    lines = [f"{root}: {pull(root)}" for root in cfg["roots"] if os.path.isdir(root)]
    try:
        res = si.sync(cfg, quiet=True)
        lines.append(f"sync: +{res['added']} ~{res['updated']} -{res['removed']} total={res['total']}")
    except Exception as e:  # index problems must not break session start
        lines.append(f"sync failed: {e}")
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    old = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []
    LOG.write_text("\n".join((old + [f"[{stamp}] " + l for l in lines])[-200:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
