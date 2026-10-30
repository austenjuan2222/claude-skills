#!/usr/bin/env python3
"""Claude Code PreToolUse hook: stops agents from fragmenting knowledge into ad-hoc Markdown.

Blocks (exit code 2, reason sent back to the model):
  1. Any Write/Edit/MultiEdit/NotebookEdit inside the skill library roots. The library is
     human-reviewed and Git-managed; agents read it, they do not write it.
  2. Creating a memory-style Markdown file anywhere (memory/, MEMORY.md, notes*.md,
     learnings*.md, knowledge/*.md …), e.g. in the project tree or the home directory.
  3. Bash commands that redirect/tee/copy into such paths.

Patterns and roots live in config.json → "guard". Paths in "allow_paths" are always allowed.

settings.json:
  "hooks": {"PreToolUse": [{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
             "hooks": [{"type": "command", "command": "python <abs path>/guard_hook.py"}]}]}
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get("SKILL_INDEX_CONFIG", os.path.expanduser("~/.claude/skill-index/config.json")))

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
BASH_WRITE_RE = re.compile(r"(?:>>?|\btee\b(?:\s+-a)?|\b(?:cp|mv|Out-File|Set-Content|Add-Content|New-Item)\b[^|;&]*?)"
                           r"\s*[\"']?([^\s\"'|;&>]+\.(?:md|markdown))", re.I)


def norm(p: str) -> str:
    return os.path.normcase(str(Path(os.path.expanduser(p)).resolve()))


def verdict(path: str, guard: dict) -> str | None:
    target = norm(path)
    if any(target == norm(a) or target.startswith(norm(a) + os.sep) for a in guard.get("allow_paths", [])):
        return None
    for root in guard.get("readonly_roots", []):
        r = norm(root)
        if target == r or target.startswith(r + os.sep):
            return (f"BLOCKED: {path} is inside the Git-managed skill library ({root}). "
                    "Agents must not edit skills. Describe the change you propose to the user; a human edits "
                    "the file, commits it, and runs sync.")
    if target.endswith((".md", ".markdown")):
        for pat in guard.get("memory_name_patterns", []):
            if re.search(pat, path, re.I) or re.search(pat, target, re.I):
                return (f"BLOCKED: {path} looks like an agent-made memory/notes Markdown file. Ad-hoc Markdown "
                        "memory fragments the knowledge base. Use skill_search to recall reviewed knowledge; "
                        "if something new should be remembered, tell the user so they can add it to the Git "
                        "repository and re-sync the index.")
    return None


def main():
    try:
        event = json.load(sys.stdin)
        guard = json.loads(CONFIG.read_text(encoding="utf-8")).get("guard", {})
    except Exception:
        sys.exit(0)  # never break the session because the guard itself is misconfigured
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()

    paths: list[str] = []
    if tool in WRITE_TOOLS:
        p = inp.get("file_path") or inp.get("notebook_path")
        if p:
            paths.append(p)
    elif tool in ("Bash", "PowerShell"):
        paths += BASH_WRITE_RE.findall(inp.get("command", ""))

    for p in paths:
        full = p if os.path.isabs(os.path.expanduser(p)) else os.path.join(cwd, p)
        reason = verdict(full, guard)
        if reason:
            print(reason, file=sys.stderr)
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
