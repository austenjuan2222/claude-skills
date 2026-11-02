#!/usr/bin/env python3
"""每週 Skills 跨裝置同步與使用率分析（本機版）。
用法： python skill_sync.py            # 全自動（比對→同步→使用率→驗證）
      python skill_sync.py --dry-run  # 只比對與統計，不 commit/pull/push/寫檔
不讀取、輸出或儲存任何金鑰／token。
"""
import argparse, datetime as dt, fnmatch, glob, hashlib, json, os, re, socket
import sqlite3, subprocess, sys
from collections import defaultdict
from pathlib import Path

TZ = dt.timezone(dt.timedelta(hours=8))  # Asia/Taipei
HOME = Path.home()
REMOTE_RE = re.compile(r"github\.com[:/]+austenjuan2222/claude-skills(\.git)?/?$", re.I)
SECRET_PATTERNS = [".env", ".env.*", "*.pem", "*key*", "*token*", "*credential*", "*secret*", "id_rsa*"]
LOCAL_ONLY_DIRS = {"projects", "todos", "shell-snapshots", "statsig", "session-env", "file-history",
                   "skill-index", "ide", "plugins", "cache", "logs"}
PROTECTED = {  # 必須保留的修正；同步若改動相關路徑就停下回報
    "genjutsu-ui-ux-pro-max 名稱": re.compile(r"genjutsu-ui-ux-pro-max", re.I),
    "REA 外部參考路徑修正": re.compile(r"(^|/)rea[-_/]", re.I),
    "Design DNA sharp 0.35.5 修補": re.compile(r"design-dna", re.I),
}
LOG = []
CMD_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


QUIET = False


def log(msg=""):
    if not QUIET:
        print(msg)
    LOG.append(str(msg))


def scrub(text):  # 移除 URL 內的帳密/token
    return re.sub(r"(https?://)[^/@\s]+@", r"\1", text or "")


def run(cmd, cwd=None, check=False, show=True, input_text=None):
    p = subprocess.run(cmd, cwd=cwd, input=input_text, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = scrub((p.stdout or "") + (p.stderr or "")).rstrip()
    if show:
        log(f"$ {' '.join(cmd)}  (exit {p.returncode})")
        if out:
            log("\n".join("  " + l for l in out.splitlines()[:60]))
    if check and p.returncode:
        raise RuntimeError(f"指令失敗：{' '.join(cmd)}")
    return p.returncode, out


def git(repo, *args, **kw):
    return run(["git", *args], cwd=repo, **kw)


# ---------- 1. 來源 ----------
def find_repos():
    cands = [HOME / ".claude", HOME / ".claude" / "skills", HOME / "Documents" / "GitHub" / "claude-skills"]
    found = {}
    for c in cands:
        if not c.exists():
            continue
        rc, top = run(["git", "rev-parse", "--show-toplevel"], cwd=c, show=False)
        if rc:
            continue
        rc, url = run(["git", "config", "--get", "remote.origin.url"], cwd=top, show=False)
        if rc == 0 and REMOTE_RE.search(url.strip()):
            found[os.path.normcase(os.path.realpath(top))] = Path(top)
    return list(found.values())


def skills_link_kind():
    p = HOME / ".claude" / "skills"
    if not p.exists():
        return "不存在", None
    real = Path(os.path.realpath(p))
    is_junc = getattr(p, "is_junction", lambda: False)()
    if p.is_symlink():
        return "symlink", real
    if is_junc or os.path.normcase(str(real)) != os.path.normcase(str(p.absolute())):
        return "junction", real
    return "實體資料夾（複本或 repo 本身）", real


def default_branch(repo):
    rc, out = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", show=False)
    if rc == 0 and out.strip():
        return out.strip().split("/", 1)[1]
    for b in ("main", "master"):
        if git(repo, "rev-parse", "--verify", f"origin/{b}", show=False)[0] == 0:
            return b
    return "main"


# ---------- 2. 比對 ----------
def blob_hash(path):
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # 同 git hash-object


def local_skills(repo):
    base = repo / "skills" if (repo / "skills").is_dir() else repo
    res = {}
    files = [f for f in base.rglob("SKILL.md") if ".git" not in f.parts]
    # 用 git hash-object 套用 autocrlf 等轉換，避免 CRLF 造成假差異
    rc, out = run(["git", "hash-object", "--stdin-paths"], cwd=repo, show=False,
                  input_text="\n".join(str(f) for f in files))
    hashes = out.split() if rc == 0 and len(out.split()) == len(files) else [blob_hash(f) for f in files]
    for f, h in zip(files, hashes):
        res[f.parent.relative_to(base).as_posix()] = h
    return res, base


def origin_skills(repo, branch, base_rel):
    prefix = (base_rel + "/") if base_rel else ""
    rc, out = git(repo, "ls-tree", "-r", f"origin/{branch}", "--", base_rel or ".", show=False)
    res = {}
    if rc:
        return res
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        if path.endswith("/SKILL.md") or path == "SKILL.md":
            name = path[len(prefix):-len("/SKILL.md")] if path.startswith(prefix) else path[:-9]
            res[name] = meta.split()[2]
    return res


def db_skills():
    db = HOME / ".claude" / "skill-index" / "skills.db"
    if not db.exists():
        return None, "找不到 skills.db"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "skills" not in tables:
            return None, f"沒有 skills 資料表（現有：{tables}）"
        cols = [r[1] for r in con.execute("PRAGMA table_info(skills)")]
        want = [c for c in ("name", "path", "namespace", "kind") if c in cols]
        rows = [dict(zip(want, r)) for r in con.execute(f"SELECT {', '.join(want)} FROM skills")]
        total = len(rows)
        sk = [r for r in rows if Path(str(r.get("path") or "")).name.lower() == "skill.md"]
        rows = sk or [r for r in rows if str(r.get("kind", "")).lower() == "skill"] or rows
        return rows, f"DB 共 {total} 筆，其中 SKILL.md {len(rows)} 筆"
    finally:
        con.close()


def db_name_set(rows, base):
    names = set()
    for r in rows or []:
        p = r.get("path")
        if p:
            p = Path(p)
            p = p.parent if p.name.lower() == "skill.md" else p
            try:
                names.add(Path(os.path.realpath(p)).relative_to(os.path.realpath(base)).as_posix())
                continue
            except ValueError:
                pass
        if r.get("name"):
            names.add(r["name"])
    return names


def compare(repo, branch, label):
    log(f"\n## 比對（{label}）— {repo}")
    _, st = git(repo, "status", "--porcelain")
    _, cnt = git(repo, "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}")
    git(repo, "diff", "--stat")
    nums = [int(x) for x in cnt.split() if x.isdigit()]
    ahead, behind = (nums + [0, 0])[:2]
    loc, base = local_skills(repo)
    base_rel = base.relative_to(repo).as_posix() if base != repo else ""
    org = origin_skills(repo, branch, base_rel)
    rows, dbinfo = db_skills()
    if rows is not None:  # 只比 repo 或 ~/.claude/skills 底下的項目，外掛 skill 不算
        roots = [os.path.normcase(os.path.realpath(x)) for x in (base, HOME / ".claude" / "skills")]
        in_scope = [r for r in rows if r.get("path") and any(
            os.path.normcase(os.path.realpath(r["path"])).startswith(rt) for rt in roots)]
        if len(in_scope) != len(rows):
            log(f"（DB 另有 {len(rows) - len(in_scope)} 筆外掛／其他來源 skill，不列入比對）")
        rows = in_scope
    dbn = db_name_set(rows, base) if rows is not None else None
    leaf = lambda s: {x.split("/")[-1] for x in s}
    info = {}
    diff = {
        "local_only_vs_origin": sorted(set(loc) - set(org)),
        "origin_only": sorted(set(org) - set(loc)),
        "hash_diff": sorted(k for k in set(loc) & set(org) if loc[k] != org[k]),
    }
    if dbn is not None:
        ln, dn = leaf(loc), leaf(dbn)
        diff["local_not_in_db"] = sorted(ln - dn)
        copy_dir = HOME / ".claude" / "skills"
        copy_names = {f.parent.name for f in copy_dir.rglob("SKILL.md")} if copy_dir.is_dir() else set()
        extra = dn - ln
        diff["db_not_in_local"] = sorted(extra - copy_names)
        info["copy_only_skills"] = sorted(extra & copy_names)
    log(f"本機 {len(loc)} 個、origin {len(org)} 個、DB skill {len(rows) if rows is not None else 'N/A'} 筆（{dbinfo}）")
    if info.get("copy_only_skills"):
        log(f"- ~/.claude/skills 複本有、repo 沒有（{len(info['copy_only_skills'])}）：{info['copy_only_skills']}")
    for k, v in diff.items():
        if v:
            log(f"- {k}: {v[:30]}{' …' if len(v) > 30 else ''}")
    dirty = [l for l in st.splitlines() if l.strip()]
    consistent = not dirty and ahead == 0 and behind == 0 and not any(diff.values())
    return dict(copy_only=info.get("copy_only_skills", []), dirty=dirty, ahead=ahead, behind=behind, local=loc, diff=diff, consistent=consistent,
                db_count=len(rows) if rows is not None else None, base=base)


def touches_protected(paths):
    hits = []
    for p in paths:
        for label, rx in PROTECTED.items():
            if rx.search(p.replace("\\", "/")):
                hits.append(f"{label}: {p}")
    return hits


# ---------- 4. 使用率 ----------
def iter_tool_uses(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name") == "Skill":
            yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from iter_tool_uses(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_tool_uses(v)


def parse_ts(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(TZ)
    except Exception:
        return None


def collect_usage(since):
    calls = []
    files = glob.glob(str(HOME / ".claude" / "projects" / "**" / "*.jsonl"), recursive=True)
    cowork_files = []
    appdata = os.environ.get("APPDATA")
    if appdata and Path(appdata, "Claude").is_dir():
        cowork_files = glob.glob(str(Path(appdata, "Claude") / "**" / "*.jsonl"), recursive=True)
    for src, flist in (("code", files), ("cowork", cowork_files)):
        for f in flist:
            try:
                if dt.datetime.fromtimestamp(os.path.getmtime(f), TZ) < since:
                    continue
                with open(f, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if '"Skill"' not in line and "<command-name>" not in line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            continue
                        ts = parse_ts(rec.get("timestamp"))
                        if not ts or ts < since:
                            continue
                        sess = rec.get("sessionId") or Path(f).stem
                        for tu in iter_tool_uses(rec):
                            inp = tu.get("input") or {}
                            sk = inp.get("skill") or inp.get("command")
                            if sk:
                                calls.append((str(sk).lstrip("/"), ts.date().isoformat(), sess, src))
                        if rec.get("type") == "user":
                            for m in CMD_RE.findall(line):
                                calls.append((m.lstrip("/"), ts.date().isoformat(), sess, src))
            except OSError:
                continue
    return calls, len(files), len(cowork_files)


def week_id(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def usage_report(repo, host, skill_names, now):
    since = now - dt.timedelta(days=7)
    calls, n_code, n_cowork = collect_usage(since)
    by = defaultdict(lambda: {"calls": 0, "days": set(), "sessions": set()})
    for sk, day, sess, _ in calls:
        key = sk.split(":")[-1]
        by[key]["calls"] += 1
        by[key]["days"].add(day)
        by[key]["sessions"].add(sess)
    leaf_names = {n.split("/")[-1] for n in skill_names}
    used = {k for k in by if k in leaf_names}
    stats = {k: {"calls": v["calls"], "days": len(v["days"]), "sessions": len(v["sessions"])} for k, v in by.items()}
    top = sorted(stats.items(), key=lambda kv: (-kv[1]["calls"], kv[0]))
    total = len(leaf_names)
    wid = week_id(now.date())
    rep = {
        "week": wid, "host": host, "generated_at": now.isoformat(), "window_start": since.isoformat(),
        "total_skills": total, "used_skills": len(used),
        "usage_rate": round(len(used) / total, 4) if total else 0,
        "skills": dict(sorted(stats.items())),
        "top10": [{"skill": k, **v} for k, v in top[:10]],
        "zero_use": sorted(leaf_names - used),
        "not_in_skill_list": sorted(set(by) - leaf_names),
        "sources": {"code_jsonl_files": n_code, "cowork_jsonl_files": n_cowork,
                    "note": "" if n_cowork else "未含 Cowork 紀錄"},
    }
    udir = repo / "reports" / "usage"
    prev_w = week_id((now - dt.timedelta(days=7)).date())
    prev = udir / f"{prev_w}-{host}.json"
    if prev.exists():
        p = json.loads(prev.read_text(encoding="utf-8"))
        rep["vs_last_week"] = {"usage_rate_delta": round(rep["usage_rate"] - p.get("usage_rate", 0), 4),
                               "used_delta": rep["used_skills"] - p.get("used_skills", 0)}
    else:
        rep["vs_last_week"] = f"找不到上週報告 {prev.name}"
    # 連續 4 週未用
    hist = [rep]
    for i in (1, 2, 3):
        f = udir / f"{week_id((now - dt.timedelta(days=7 * i)).date())}-{host}.json"
        if f.exists():
            hist.append(json.loads(f.read_text(encoding="utf-8")))
    if len(hist) >= 4:
        rep["consider_disable"] = sorted(set.intersection(*(set(h.get("zero_use", [])) for h in hist)))
    else:
        rep["consider_disable"] = f"歷史不足 4 週（目前 {len(hist)} 週），暫不判斷"
    # 另一台同週檔案 → 合併摘要
    others = [f for f in udir.glob(f"{wid}-*.json") if f.name != f"{wid}-{host}.json"
              and not f.name.startswith(f"{wid}-merged")] if udir.exists() else []
    merged = None
    if others:
        o = json.loads(others[0].read_text(encoding="utf-8"))
        comb = defaultdict(int)
        for src in (rep, o):
            for k, v in src.get("skills", {}).items():
                comb[k] += v["calls"]
        used_all = {k for k in comb if k in leaf_names}
        merged = {"week": wid, "hosts": [host, o.get("host")], "total_skills": total,
                  "used_skills": len(used_all), "usage_rate": round(len(used_all) / total, 4) if total else 0,
                  "top10": sorted(comb.items(), key=lambda kv: -kv[1])[:10]}
    return rep, merged


# ---------- 3. 同步 ----------
def sync(repo, branch, host, today, dry):
    problems, commits = [], []
    _, st = git(repo, "status", "--porcelain", show=False)
    changed = [l[3:].strip().strip('"') for l in st.splitlines() if l.strip()]
    hits = touches_protected(changed)
    if hits:
        problems.append("本機修改涉及必須保留項目，停止同步：" + "; ".join(hits))
        return problems, commits
    for rf in (repo / "reports" / "usage").glob(f"*{host}.json") if not dry else []:
        rel = rf.relative_to(repo).as_posix()
        if git(repo, "check-ignore", "-q", rel, show=False)[0] == 0:
            log(f"{rel} 被 .gitignore 排除，強制加入")
            git(repo, "add", "-f", rel)
            changed.append(rel)
        elif rel not in changed and git(repo, "status", "--porcelain", "--", rel, show=False)[1].strip():
            changed.append(rel)
    if changed and not dry:
        git(repo, "add", "-A")
        _, staged = git(repo, "diff", "--cached", "--name-only", show=False)
        staged_l = staged.splitlines()
        bad = [f for f in staged_l
               if any(fnmatch.fnmatch(Path(f).name.lower(), p) for p in SECRET_PATTERNS)]
        local_state = [f for f in staged_l if f not in bad and
                       (f.split("/")[0] in LOCAL_ONLY_DIRS or f.endswith(".jsonl") or f.endswith(".db"))]
        for f in bad + local_state:
            git(repo, "reset", "-q", "--", f, show=False)
        if bad:
            problems.append(f"疑似機密檔未 commit：{bad}")
        if local_state:
            problems.append(f"本機狀態檔（對話紀錄/DB 等）未 commit，建議加入 .gitignore：{local_state[:10]}")
        if git(repo, "diff", "--cached", "--quiet", show=False)[0]:
            rc, _ = git(repo, "commit", "-m", f"chore(skills): auto-sync from {host} {today}")
            if rc:
                problems.append("commit 失敗（可能被 hook 擋下），未繞過")
                return problems, commits
            commits.append(git(repo, "rev-parse", "--short", "HEAD", show=False)[1].strip())
    _, cnt = git(repo, "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}", show=False)
    ahead, behind = (int(x) for x in cnt.split())
    if behind:
        _, incoming = git(repo, "diff", "--name-only", f"HEAD...origin/{branch}", show=False)
        hits = touches_protected(incoming.splitlines())
        if hits:
            problems.append("遠端更新會改動必須保留項目，停止 pull：" + "; ".join(hits))
            return problems, commits
        if not dry:
            rc, out = git(repo, "pull", "--rebase", "origin", branch)
            if rc:
                _, conf = git(repo, "diff", "--name-only", "--diff-filter=U", show=False)
                in_rebase = (repo / ".git" / "rebase-merge").exists() or (repo / ".git" / "rebase-apply").exists()
                if in_rebase:
                    git(repo, "rebase", "--abort")
                if conf.split() or "CONFLICT" in out:
                    problems.append(f"rebase 衝突，已 abort：{conf.split()}")
                else:
                    problems.append("pull 失敗（非衝突，見輸出：網路或權限）")
                return problems, commits
    _, cnt = git(repo, "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}", show=False)
    ahead = int(cnt.split()[0])
    if ahead and not dry:
        rc, _ = git(repo, "push", "origin", branch)  # 禁止 --force
        if rc:
            problems.append("push 失敗（權限或 hook 擋下），未繞過")
        else:
            commits.append("pushed:" + git(repo, "rev-parse", "--short", "HEAD", show=False)[1].strip())
    return problems, commits


def reindex(repo, dry):
    if dry:
        return
    tool = repo / "tools" / "skill-index"
    if (tool / "session_start.py").exists():
        run([sys.executable, str(tool / "session_start.py")], cwd=repo)
    else:
        log("找不到 tools/skill-index/session_start.py")


def install_hook():
    settings = HOME / ".claude" / "settings.json"
    cmd = f'python "{Path(__file__).resolve()}" --weekly'
    data = {}
    if settings.exists():
        raw = settings.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        bak = settings.with_name(f"settings.json.bak-{dt.datetime.now(TZ):%Y%m%d%H%M%S}")
        bak.write_text(raw, "utf-8")
        print(f"已備份：{bak}")
    groups = data.setdefault("hooks", {}).setdefault("SessionStart", [])
    if any("skill_sync.py" in h.get("command", "") for g in groups for h in g.get("hooks", [])):
        print("hook 已存在，未重複加入")
        return 0
    groups.append({"matcher": "startup", "hooks": [{"type": "command", "command": cmd, "timeout": 300}]})
    settings.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(f"已加入 SessionStart hook：{cmd}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--weekly", action="store_true", help="距上次成功執行未滿 7 天就跳過；只輸出摘要")
    ap.add_argument("--install-hook", action="store_true", help="在 Claude Code 啟動時自動執行 --weekly")
    a = ap.parse_args()
    if a.install_hook:
        return install_hook()
    stamp = HOME / ".claude" / "skill-sync-last.txt"
    if a.weekly:
        global QUIET
        QUIET = True
        try:
            last = dt.datetime.fromisoformat(stamp.read_text(encoding="utf-8").strip())
            if dt.datetime.now(TZ) - last < dt.timedelta(days=7):
                return 0
        except (OSError, ValueError):
            pass
    now = dt.datetime.now(TZ)
    today = now.date().isoformat()
    host = socket.gethostname()
    kind = "桌機" if host.lower() == "desktop-1a862i4" else "筆電"
    log(f"# Skills 同步報告 — {host}（{kind}）{now:%Y-%m-%d %H:%M}{'  [dry-run]' if a.dry_run else ''}")

    if not (HOME / ".claude").is_dir():
        log("本機無法存取：找不到 ~/.claude，停止。")
        return 2
    repos = find_repos()
    if not repos:
        log("本機無法存取：找不到 origin 為 austenjuan2222/claude-skills 的 repo，停止。")
        return 2
    lk, real = skills_link_kind()
    log(f"找到 repo：{[str(r) for r in repos]}")
    log(f"~/.claude/skills 類型：{lk} → {real}")
    primary = next((r for r in repos if real and str(real).lower().startswith(str(r).lower())), repos[0])

    results = {}
    offline = False
    for repo in repos:
        rc, out = git(repo, "fetch", "origin")
        if rc:
            offline = True
            log("⚠ fetch 失敗（網路/DNS/權限），本次不 pull/push，origin 狀態以本機快取為準")
        br = default_branch(repo)
        results[repo] = (br, compare(repo, br, "同步前"))
        _, last = git(repo, "log", "-5", f"origin/{br}", "--format=%h %an %ad %s", "--date=iso", show=False)
        log("origin 最近 commit（推斷另一台狀態）：\n" + "\n".join("  " + l for l in last.splitlines()))
    br, before = results[primary]

    rep, merged = usage_report(primary, host, list(before["local"]), now)
    if not a.dry_run:
        udir = primary / "reports" / "usage"
        udir.mkdir(parents=True, exist_ok=True)
        (udir / f"{rep['week']}-{host}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), "utf-8")
        if merged:
            (udir / f"{rep['week']}-merged.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")

    log("\n## 同步")
    if offline:
        problems, commits = ["連不到 GitHub（fetch 失敗），未同步；請確認網路後重跑"], []
    else:
        problems, commits = sync(primary, br, host, today, a.dry_run)
    reindex(primary, a.dry_run)
    git(primary, "fetch", "origin", show=False)
    after = compare(primary, br, "同步後")
    if not a.dry_run and (after["diff"].get("local_not_in_db") or after["diff"].get("db_not_in_local")):
        tool = primary / "tools" / "skill-index" / "skill_index.py"
        if tool.exists():
            run([sys.executable, str(tool), "init"], cwd=primary)
            after = compare(primary, br, "重建索引後")
    for other in repos:
        if other != primary:
            log(f"\n注意：另有 repo {other}（未自動同步，僅比對）")

    log("\n## 摘要")
    log(f"裝置：{host}（{kind}）")
    log(f"同步前→後：dirty {len(before['dirty'])}→{len(after['dirty'])}、ahead {before['ahead']}→{after['ahead']}、"
        f"behind {before['behind']}→{after['behind']}、一致 {before['consistent']}→{after['consistent']}")
    log(f"commit：{commits or '無'}")
    if after.get("copy_only"):
        problems.append(f"~/.claude/skills 有 {len(after['copy_only'])} 個 skill 不在 repo（未自動加入，請決定是否納管）")
    log(f"問題：{problems or '無'}")
    top5 = ", ".join(f"{t['skill']}({t['calls']})" for t in rep["top10"][:5]) or "無"
    log(f"使用率：{rep['usage_rate']:.1%}（{rep['used_skills']}/{rep['total_skills']}）；前5：{top5}；"
        f"零使用 {len(rep['zero_use'])}；vs上週：{rep['vs_last_week']}；{rep['sources']['note']}")
    log(f"可考慮停用：{rep['consider_disable']}")
    if merged:
        log(f"兩台合併使用率：{merged['usage_rate']:.1%}")
    logf = HOME / f"skill-sync-{today}-{host}.log"
    logf.write_text("\n".join(LOG), "utf-8")
    if not offline and not a.dry_run:
        stamp.write_text(now.isoformat(), "utf-8")
    if QUIET:
        i = max(i for i, l in enumerate(LOG) if "## 摘要" in l)
        print("[每週 skills 同步] " + " | ".join(LOG[i + 1:]))
    print(f"\n完整紀錄：{logf}")
    return 0 if QUIET else (1 if problems else 0)  # hook 模式不回傳錯誤碼，避免干擾啟動


if __name__ == "__main__":
    sys.exit(main())
