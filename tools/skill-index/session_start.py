#!/usr/bin/env python3
"""SessionStart hook: fetch every Git-managed skill root, report pending updates, then re-index local files.

Never pulls by itself, unless config.json sets "auto_sync": true: then skill_sync.py --auto runs first
(commit, pull --rebase, push, link ~/.claude/skills to the repo) with all of its safety checks. Prints to stdout (which is injected
into the session) only when a repo is behind its remote. Never blocks the session: offline or auth
prompts just skip that repo. Outcomes go to session_start.log (last 200 lines kept).
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
FETCH_TIMEOUT = 20  # seconds per repo
AUTO_TIMEOUT = 90  # seconds for skill_sync.py --auto


def git(root: str, *args: str, timeout: int = FETCH_TIMEOUT) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env)


def check(root: str) -> tuple[str, int]:
    """Fetch only; never touches the working tree. Returns (log status, commits behind upstream)."""
    if not (Path(root) / ".git").exists():
        return "skip (not a git repo root)", 0
    try:
        if git(root, "remote").stdout.strip() == "":
            return "skip (no remote)", 0
        r = git(root, "fetch", "--quiet")
        if r.returncode != 0:
            return f"skip (fetch failed: {(r.stderr or r.stdout).strip().splitlines()[-1:] or ['?']})", 0
        r = git(root, "rev-list", "--count", "HEAD..@{u}")
        if r.returncode != 0:
            return "skip (no upstream branch)", 0
        behind = int(r.stdout.strip() or 0)
        return (f"{behind} new commit(s) on remote, not applied" if behind else "up to date"), behind
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        return f"skip ({type(e).__name__})", 0


def auto_sync(lines: list[str]):
    """config.json 有 "auto_sync": true 時，先跑 skill_sync.py --auto（commit、pull、push、連結 skills）。"""
    tool = Path(__file__).resolve().parents[1] / "skill_sync.py"
    if not tool.exists():
        lines.append("auto-sync: skill_sync.py not found")
        return
    try:
        r = subprocess.run([sys.executable, str(tool), "--auto"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=AUTO_TIMEOUT,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never",
                                "PYTHONIOENCODING": "utf-8"})
        out = r.stdout.strip()
        if out:
            print(out)  # 注入對話，讓 Claude 告訴使用者這次同步了什麼
        lines.append(f"auto-sync: exit {r.returncode} {out[:300]}")
    except (OSError, subprocess.TimeoutExpired) as e:
        lines.append(f"auto-sync: skip ({type(e).__name__})")


def main():
    cfg = si.load_config()
    lines, notices = [], []
    if cfg.get("auto_sync"):
        auto_sync(lines)
    for root in cfg["roots"]:
        if not os.path.isdir(root):
            continue
        status, behind = check(root)
        lines.append(f"{root}: {status}")
        if behind:
            notices.append(f"- {root}: {behind} new commit(s) on GitHub (log: git -C \"{root}\" log --oneline HEAD..@{{u}})")
    if notices:
        # stdout is injected into the session, so this is how Claude learns to remind the user
        print("[skill-index] Skill repo updates are available but NOT applied:\n" + "\n".join(notices)
              + "\nTell the user, show what changed, and only run `git pull --ff-only` there after they approve.")
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
