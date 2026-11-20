#!/usr/bin/env python3
"""讓 ~/.claude/skills 直接使用 repo 的 skills：每個 repo skill 在 ~/.claude/skills 底下建一個連結
（Windows 用 junction，其他系統用 symlink），Claude Code 讀到的就是 repo 那一份，不會再有過期的複本。

安全規則：
- 只處理 repo `skills/` 底下的資料夾（`_sources` 除外）；不在 repo 的 skill（例如 Anthropic 內建的複本）完全不動。
- 既有的實體資料夾一律「移到備份」，從不刪除；內容和 repo 不同的會在報告中列出。
- 只移除「指向 repo 但 repo 已刪掉該 skill」的連結本身，從不刪除連結指向的內容。

  python skill_links.py            # 建立／修復連結
  python skill_links.py --dry-run  # 只列出會做什麼
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKIP = {"_sources"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv"}


def is_link(p: Path) -> bool:
    """symlink 或 Windows junction（Python 3.11 也要認得）。"""
    if os.path.islink(p):
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction:
        return bool(isjunction(p))
    try:  # Python 3.11 以前：Windows junction 是帶 reparse-point 屬性的資料夾
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & 0x400)
    except OSError:
        return False


def make_link(link: Path, target: Path):
    if os.name == "nt":  # junction 不需要系統管理員或開發人員模式
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, text=True, errors="replace")
        if r.returncode:
            raise OSError(f"mklink 失敗：{(r.stdout + r.stderr).strip()}")
    else:
        os.symlink(target, link, target_is_directory=True)


def remove_link(link: Path):
    """只移除連結本身，不碰它指向的資料夾。"""
    if not is_link(link):
        raise ValueError(f"不是連結，拒絕刪除：{link}")
    try:
        os.unlink(link)
    except (IsADirectoryError, PermissionError, OSError):
        os.rmdir(link)  # Windows junction


def same_target(link: Path, target: Path) -> bool:
    return os.path.normcase(os.path.realpath(link)) == os.path.normcase(os.path.realpath(target))


def tree_digest(root: Path) -> str:
    """忽略換行差異（CRLF/LF）的資料夾內容摘要。"""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in sorted(filenames):
            p = Path(dirpath, fn)
            h.update(p.relative_to(root).as_posix().encode())
            h.update(b"\0")
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
            h.update(b"\0")
    return h.hexdigest()


def link_skills(repo_skills: Path, home_skills: Path, backup_root: Path, dry: bool = False,
                stamp: str | None = None) -> dict:
    stamp = stamp or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    rep = {k: [] for k in ("ok", "linked", "relinked", "replaced_identical", "replaced_different",
                           "removed_stale", "not_in_repo", "errors")}
    rep["whole_dir_linked"] = False
    rep["backup_dir"] = None
    if os.path.lexists(home_skills) and same_target(home_skills, repo_skills):
        rep["whole_dir_linked"] = True  # 整個 ~/.claude/skills 已經就是 repo 的 skills
        return rep
    names = sorted(d.name for d in repo_skills.iterdir()
                   if d.is_dir() and d.name not in SKIP and not d.name.startswith("."))
    if not dry:
        home_skills.mkdir(parents=True, exist_ok=True)
    backup = backup_root / stamp
    for name in names:
        target, link = repo_skills / name, home_skills / name
        try:
            if is_link(link):
                if same_target(link, target):
                    rep["ok"].append(name)
                    continue
                rep["relinked"].append(name)
                if not dry:
                    remove_link(link)
                    make_link(link, target)
            elif link.exists():
                key = "replaced_identical" if tree_digest(link) == tree_digest(target) else "replaced_different"
                rep[key].append(name)
                if not dry:
                    backup.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(link), str(backup / name))
                    rep["backup_dir"] = str(backup)
                    make_link(link, target)
            else:
                rep["linked"].append(name)
                if not dry:
                    make_link(link, target)
        except Exception as e:  # 單一 skill 失敗不影響其他
            rep["errors"].append(f"{name}: {e}")
    if home_skills.is_dir():
        for entry in sorted(home_skills.iterdir()):
            if entry.name in names:
                continue
            if is_link(entry):
                dest = os.path.realpath(entry)
                inside_repo = os.path.normcase(dest).startswith(os.path.normcase(os.path.realpath(repo_skills)))
                if inside_repo and not os.path.exists(dest):
                    rep["removed_stale"].append(entry.name)
                    if not dry:
                        remove_link(entry)
                    continue
            if (entry / "SKILL.md").exists():
                rep["not_in_repo"].append(entry.name)
    return rep


def summary(rep: dict) -> str:
    if rep["whole_dir_linked"]:
        return "~/.claude/skills 整個資料夾已連到 repo"
    parts = [f"一致 {len(rep['ok'])}"]
    for key, label in (("linked", "新連結"), ("relinked", "重連"), ("replaced_identical", "複本換成連結"),
                       ("replaced_different", "內容不同已備份"), ("removed_stale", "移除失效連結"),
                       ("errors", "失敗")):
        if rep[key]:
            parts.append(f"{label} {len(rep[key])}：{rep[key][:10]}")
    if rep["backup_dir"]:
        parts.append(f"備份：{rep['backup_dir']}")
    return "；".join(parts)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    home = Path.home() / ".claude"
    rep = link_skills(repo / "skills", home / "skills", home / "skills-backup", dry=a.dry_run)
    print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else summary(rep))
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
