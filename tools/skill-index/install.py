#!/usr/bin/env python3
"""One-click setup of the skill index on this PC (safe to re-run; also used to update/migrate).

  python tools/skill-index/install.py              install / repair
  python tools/skill-index/install.py --uninstall  remove MCP server, hooks and CLAUDE.md block

What it does:
  1. ~/.claude/skill-index/config.json  machine-local config (scan roots incl. this repo)
  2. ~/.claude/skill-index/skills.db    builds the SQLite + FTS5 index
  3. MCP server `skill-index` registered at user scope (runs from this repo, so `git pull` updates it)
  4. ~/.claude/settings.json            guard hook (PreToolUse) + pull-and-sync hook (SessionStart)
  5. ~/.claude/CLAUDE.md                Router prompt inside a marked block; other content is kept
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO = TOOL_DIR.parents[1]
HOME = Path.home()
CLAUDE = HOME / ".claude"
STATE = CLAUDE / "skill-index"
SETTINGS = CLAUDE / "settings.json"
CLAUDE_MD = CLAUDE / "CLAUDE.md"
START, END = "<!-- skill-index:start -->", "<!-- skill-index:end -->"
LEGACY_HEADER = "<!-- skill-index router:"
# code files from the first, pre-repo install that lived in the state dir
LEGACY_CODE = ["skill_index.py", "mcp_server.py", "guard_hook.py", "session_start.py", "sync.ps1", "sync.sh",
               "README.md", "ROUTER_PROMPT.md", "git-hooks", "__pycache__"]


def tilde(p: Path) -> str:
    """~/... form when under the home dir, so the config reads the same on every PC."""
    try:
        return "~/" + p.resolve().relative_to(HOME.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def py() -> str:
    return Path(sys.executable).as_posix()


def step(msg: str):
    print(f"• {msg}")


# ---------------------------------------------------------------- 1. config

def write_config():
    STATE.mkdir(parents=True, exist_ok=True)
    path, repo = STATE / "config.json", tilde(REPO)
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "db_path": "skills.db",
        "roots": ["~/.claude/skills", "~/.claude/plugins/cache", "~/.claude/plugins/synced"],
        "latest_version_only": ["~/.claude/plugins/cache"],
        "include_ext": [".md", ".html", ".htm"],
        "exclude_dirs": [".git", "node_modules", "__pycache__", ".venv", "dist", "build"],
        "exclude_files": ["CHANGELOG.md", "LICENSE.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md"],
        "guard": {
            "readonly_roots": ["~/.claude/skills", "~/.claude/plugins/cache", "~/.claude/plugins/synced"],
            "memory_name_patterns": [
                "(^|[\\\\/])memor(y|ies)[\\\\/]",
                "(^|[\\\\/])MEMORY\\.md$",
                "(^|[\\\\/])(notes?|learnings?|knowledge|lessons?|journal|scratch[-_]?notes?)[^\\\\/]*\\.md$",
                "(^|[\\\\/])(notes?|learnings?|knowledge|lessons?)[\\\\/][^\\\\/]+\\.md$",
            ],
            "allow_paths": ["~/.claude/projects"],
        },
    }
    for key in (cfg["roots"], cfg["guard"]["readonly_roots"]):
        if repo not in key:
            key.insert(0, repo)
    cfg.setdefault("latest_version_only", ["~/.claude/plugins/cache"])
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    step(f"config: {path}  (repo root: {repo})")


def remove_legacy_code():
    if STATE.resolve() == TOOL_DIR:
        return
    gone = []
    for name in LEGACY_CODE:
        p = STATE / name
        if p.is_dir():
            shutil.rmtree(p); gone.append(name)
        elif p.exists():
            p.unlink(); gone.append(name)
    if gone:
        step(f"removed old copies from {STATE}: {', '.join(gone)}")


# ---------------------------------------------------------------- 2. index

def build_index():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(a, tokenize='trigram')")
    except sqlite3.OperationalError:
        sys.exit("This Python's SQLite lacks FTS5 trigram support (needs SQLite >= 3.34). Install Python 3.10+.")
    subprocess.run([sys.executable, str(TOOL_DIR / "skill_index.py"), "init"], check=True)


# ---------------------------------------------------------------- 3. MCP

def register_mcp(remove_only=False):
    claude = shutil.which("claude")
    cmd = [py(), (TOOL_DIR / "mcp_server.py").as_posix()]
    if not claude:
        step("claude CLI not found. Register the MCP server manually:\n    claude mcp add skill-index -s user -- "
             + " ".join(f'"{c}"' for c in cmd))
        return
    subprocess.run([claude, "mcp", "remove", "skill-index", "-s", "user"], capture_output=True)
    if remove_only:
        step("MCP server removed")
        return
    r = subprocess.run([claude, "mcp", "add", "skill-index", "-s", "user", "--", *cmd],
                       capture_output=True, text=True)
    step("MCP server registered" if r.returncode == 0 else f"MCP registration failed: {r.stderr.strip()}")


# ---------------------------------------------------------------- 4. hooks

def ours(entry: dict) -> bool:
    return any(("skill-index" in h.get("command", "") or "skill_index" in h.get("command", ""))
               for h in entry.get("hooks", []))


def write_hooks(remove_only=False):
    s = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_name("settings.json.bak-skill-index"))
    hooks = s.setdefault("hooks", {})
    for event in ("PreToolUse", "SessionStart"):
        hooks[event] = [e for e in hooks.get(event, []) if not ours(e)]
    if not remove_only:
        hooks["PreToolUse"].append({
            "matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell",
            "hooks": [{"type": "command", "command": f'"{py()}" "{(TOOL_DIR / "guard_hook.py").as_posix()}"'}]})
        hooks["SessionStart"].append({
            "hooks": [{"type": "command", "timeout": 90,
                       "command": f'"{py()}" "{(TOOL_DIR / "session_start.py").as_posix()}"'}]})
    for event in ("PreToolUse", "SessionStart"):
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        del s["hooks"]
    SETTINGS.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    step(f"hooks {'removed from' if remove_only else 'written to'} {SETTINGS} (backup: settings.json.bak-skill-index)")


# ---------------------------------------------------------------- 5. CLAUDE.md

def write_router(remove_only=False):
    text = CLAUDE_MD.read_text(encoding="utf-8") if CLAUDE_MD.exists() else ""
    if START in text and END in text:
        head, rest = text.split(START, 1)
        text = head.rstrip() + "\n\n" + rest.split(END, 1)[1].lstrip()
    elif text.startswith(LEGACY_HEADER):
        text = ""  # first install wrote the whole file; nothing else in it to keep
    text = text.strip()
    if not remove_only:
        router = (TOOL_DIR / "ROUTER_PROMPT.md").read_text(encoding="utf-8").replace("{{TOOL_DIR}}", tilde(TOOL_DIR))
        block = (f"{START}\n<!-- managed by {tilde(TOOL_DIR)}/install.py; edit ROUTER_PROMPT.md in the repo -->\n\n"
                 f"{router.strip()}\n\n> In Claude Code these tools are named `mcp__skill-index__skill_search`, "
                 f"`mcp__skill-index__skill_get`, `mcp__skill-index__skill_sql`, `mcp__skill-index__skill_stats`.\n{END}")
        text = (text + "\n\n" + block) if text else block
    CLAUDE_MD.write_text(text + "\n" if text else "", encoding="utf-8")
    step(f"router prompt {'removed from' if remove_only else 'written to'} {CLAUDE_MD}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--uninstall" in sys.argv:
        register_mcp(remove_only=True)
        write_hooks(remove_only=True)
        write_router(remove_only=True)
        print(f"Uninstalled. Index data kept in {STATE}; delete that folder to remove it.")
        return
    write_config()
    remove_legacy_code()
    build_index()
    register_mcp()
    write_hooks()
    write_router()
    print("Done. Open a new Claude Code session to start using it.")


if __name__ == "__main__":
    main()
