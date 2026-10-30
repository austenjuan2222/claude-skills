#!/usr/bin/env python3
"""Skill index: SQLite + FTS5 catalog of Markdown/HTML skill files.

Agents query this index instead of walking skill directories, then load the
single file they need by path.

  python skill_index.py init              # create schema and do a full scan
  python skill_index.py sync              # incremental re-index (changed files only)
  python skill_index.py search "pdf merge" [--limit 5] [--kind skill] [--verified]
  python skill_index.py get <name-or-id>  # metadata + path, never file body
  python skill_index.py sql "SELECT name, path FROM skills WHERE namespace='superpowers'"
  python skill_index.py stats

No third-party dependencies (stdlib only).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
# machine-local state (config, db, log) lives outside the repo so each PC keeps its own paths
STATE_DIR = Path(os.path.expanduser("~/.claude/skill-index"))
CONFIG_PATH = Path(os.environ.get("SKILL_INDEX_CONFIG", STATE_DIR / "config.json"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,          -- skill name (frontmatter `name` or folder name)
    namespace   TEXT NOT NULL,          -- plugin / collection the file belongs to
    kind        TEXT NOT NULL,          -- 'skill' (SKILL.md) or 'module' (any other doc inside a skill)
    parent      TEXT,                   -- for modules: name of the owning skill
    path        TEXT NOT NULL UNIQUE,   -- absolute path to load with the Read tool
    description TEXT,                   -- frontmatter description or auto summary
    tags        TEXT,                   -- space-separated keyword tags
    headings    TEXT,                   -- section headings, improves recall without indexing bodies
    git_root    TEXT,
    git_state   TEXT,                   -- 'clean' | 'modified' | 'untracked' | 'no-git'
    sha256      TEXT NOT NULL,
    size        INTEGER,
    tokens_est  INTEGER,                -- rough token cost of loading the file
    indexed_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_ns   ON skills(namespace, kind);

-- External-content FTS5 table: stores only the inverted index, rows live in `skills`.
-- trigram tokenizer gives substring matching for CJK text as well as English.
CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
    name, description, tags, headings,
    content='skills', content_rowid='id', tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS skills_ai AFTER INSERT ON skills BEGIN
    INSERT INTO skills_fts(rowid, name, description, tags, headings)
    VALUES (new.id, new.name, new.description, new.tags, new.headings);
END;
CREATE TRIGGER IF NOT EXISTS skills_ad AFTER DELETE ON skills BEGIN
    INSERT INTO skills_fts(skills_fts, rowid, name, description, tags, headings)
    VALUES ('delete', old.id, old.name, old.description, old.tags, old.headings);
END;
CREATE TRIGGER IF NOT EXISTS skills_au AFTER UPDATE ON skills BEGIN
    INSERT INTO skills_fts(skills_fts, rowid, name, description, tags, headings)
    VALUES ('delete', old.id, old.name, old.description, old.tags, old.headings);
    INSERT INTO skills_fts(rowid, name, description, tags, headings)
    VALUES (new.id, new.name, new.description, new.tags, new.headings);
END;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

STOPWORDS = set("""
a an the and or but if then else when while for to of in on at by with from into onto
is are was were be been being this that these those it its as not no use used using
you your we our they their can will should must may might do does did done any all
each every some more most other such only also just than so very per via about over
skill skills file files user users claude agent when-to whenever before after
""".split())

FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.S)
HEADING_RE = re.compile(r"^#{1,4}\s+(.+?)\s*#*\s*$", re.M)


# ---------------------------------------------------------------- config / db

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["roots"] = [str(Path(os.path.expanduser(r)).resolve()) for r in cfg["roots"]]
    db = Path(os.path.expanduser(cfg.get("db_path", "skills.db")))
    cfg["db_path"] = str(db if db.is_absolute() else (CONFIG_PATH.parent / db).resolve())
    return cfg


def connect(cfg: dict, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{cfg['db_path']}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(cfg["db_path"])
        conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- parsing

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end():]
    try:
        import yaml  # optional; handles multi-line values properly
        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return data, body
    except Exception:
        pass
    data, key = {}, None
    for line in raw.splitlines():
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            data[key] = val.strip("\"'") if val not in ("|", ">", "|-", ">-") else ""
        elif key and line.startswith((" ", "\t")):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, body


def html_to_text(text: str) -> tuple[str, list[str]]:
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    heads = [re.sub(r"<[^>]+>", "", h) for h in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", text, re.S | re.I)]
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    if title:
        heads.insert(0, html.unescape(title.group(1)))
    return re.sub(r"\s+", " ", text), [html.unescape(h).strip() for h in heads if h.strip()]


def auto_summary(body: str, limit: int = 300) -> str:
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith(("#", "```", "|", "<!--", "---", "![", "<")):
            continue
        p = re.sub(r"[*_`>\[\]]", "", re.sub(r"\s+", " ", p))
        return p[:limit] + ("…" if len(p) > limit else "")
    return ""


def auto_tags(name: str, namespace: str, description: str, headings: list[str], explicit) -> list[str]:
    tags: list[str] = []
    if isinstance(explicit, str):
        explicit = re.split(r"[,\s]+", explicit)
    for t in explicit or []:
        tags.append(str(t).strip().lower())
    tags += [p for p in re.split(r"[-_:/\s]+", f"{namespace} {name}".lower()) if len(p) > 1]
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", f"{description} {' '.join(headings)}".lower())
    tags += [w for w, _ in Counter(w.strip(".-") for w in words if w not in STOPWORDS).most_common(10)]
    # quoted trigger phrases in descriptions ("make a deck") are strong retrieval keys
    tags += [q.lower() for q in re.findall(r"[\"“']([^\"”']{3,40})[\"”']", description)][:8]
    seen, out = set(), []
    for t in tags:
        t = t.strip()
        if t and t not in seen and t not in STOPWORDS:
            seen.add(t)
            out.append(t.replace(" ", "_"))
    return out[:30]


# ---------------------------------------------------------------- git

class GitInfo:
    """Caches `git status` per repository so each file costs O(1) to classify."""

    def __init__(self):
        self.roots: dict[str, str | None] = {}
        self.dirty: dict[str, dict[str, str]] = {}

    def root_of(self, d: Path) -> str | None:
        # filesystem walk for a `.git` entry instead of spawning `git rev-parse` per directory
        key = str(d)
        if key not in self.roots:
            if (d / ".git").exists():
                self.roots[key] = key
            elif d.parent == d:
                self.roots[key] = None
            else:
                self.roots[key] = self.root_of(d.parent)
        return self.roots[key]

    def state(self, path: Path) -> tuple[str | None, str]:
        root = self.root_of(path.parent)
        if not root:
            return None, "no-git"
        if root not in self.dirty:
            try:
                out = subprocess.run(["git", "-C", root, "status", "--porcelain", "-z", "--untracked-files=all"],
                                     capture_output=True, text=True, encoding="utf-8", timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                out = None  # git not installed or hung: review state unknown
            if out is None or out.returncode != 0:
                self.dirty[root] = None
            else:
                states = {}
                for entry in out.stdout.split("\0"):
                    if len(entry) > 3:
                        code = entry[:2]
                        states[str((Path(root) / entry[3:]).resolve())] = "untracked" if code == "??" else "modified"
                self.dirty[root] = states
        if self.dirty[root] is None:
            return root, "no-git"
        return root, self.dirty[root].get(str(path), "clean")


# ---------------------------------------------------------------- scanning

def iter_files(cfg: dict):
    exts = {e.lower() for e in cfg["include_ext"]}
    skip_dirs, skip_files = set(cfg["exclude_dirs"]), set(cfg["exclude_files"])
    versioned = [os.path.normcase(str(Path(os.path.expanduser(r)).resolve())) for r in cfg.get("latest_version_only", [])]
    for root in cfg["roots"]:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            if any(os.path.normcase(dirpath).startswith(v) for v in versioned):
                dirnames[:] = latest_versions(dirnames)
            for fn in filenames:
                if fn in skip_files or os.path.splitext(fn)[1].lower() not in exts:
                    continue
                yield root, Path(dirpath, fn).resolve()


VERSION_RE = re.compile(r"^v?\d+(\.\d+)*([-+.][0-9A-Za-z.-]+)?$")


def latest_versions(dirnames: list[str]) -> list[str]:
    """Plugin caches keep one folder per version (superpowers/7.0.0, 7.1.0 ...).
    When every child is a version folder, keep only the newest so stale copies drop out of the index."""
    if len(dirnames) < 2 or not all(VERSION_RE.match(d) for d in dirnames):
        return dirnames
    key = lambda d: [int(x) if x.isdigit() else -1 for x in re.split(r"[.+-]", d.lstrip("v"))]
    return [max(dirnames, key=key)]


def find_skill_dir(path: Path, root: str) -> Path | None:
    """Nearest ancestor (within root) that contains a SKILL.md."""
    for d in [path.parent, *path.parent.parents]:
        if (d / "SKILL.md").exists():
            return d
        if str(d) == root:
            return None
    return None


def namespace_for(skill_dir: Path, root: str) -> str:
    """Plugin name from .claude-plugin/plugin.json or the folder above `skills/`."""
    for d in [skill_dir, *skill_dir.parents]:
        pj = d / ".claude-plugin" / "plugin.json"
        if pj.exists():
            try:
                return json.loads(pj.read_text(encoding="utf-8")).get("name") or d.name
            except (OSError, ValueError):
                return d.name
        if str(d) == root:
            break
    parts = skill_dir.parts
    if "skills" in parts[:-1]:
        i = len(parts) - 1 - parts[::-1].index("skills", 1)
        if i > 0 and parts[i - 1] not in (".claude",):
            return parts[i - 1]
    return Path(root).name


def build_row(root: str, path: Path, git: GitInfo) -> dict | None:
    skill_dir = find_skill_dir(path, root)
    if skill_dir is None:
        return None  # stray markdown outside any skill: not part of the library
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    is_html = path.suffix.lower() in (".html", ".htm")
    if is_html:
        body, headings = html_to_text(text)
        fm = {}
    else:
        fm, body = parse_frontmatter(text)
        headings = [h.strip() for h in HEADING_RE.findall(body)]

    is_skill = path.name == "SKILL.md"
    skill_fm = fm if is_skill else parse_frontmatter((skill_dir / "SKILL.md").read_text("utf-8", "replace"))[0]
    skill_name = str(skill_fm.get("name") or skill_dir.name)
    namespace = namespace_for(skill_dir, root)
    name = skill_name if is_skill else f"{skill_name}/{path.relative_to(skill_dir).as_posix()}"
    description = str(fm.get("description") or "").strip() or auto_summary(body)
    if is_html and not description:
        description = body[:300]
    tags = auto_tags(name.split("/")[-1].rsplit(".", 1)[0], namespace, description, headings,
                     fm.get("tags") or fm.get("keywords"))
    git_root, git_state = git.state(path)
    return {
        "name": name, "namespace": namespace, "kind": "skill" if is_skill else "module",
        "parent": None if is_skill else skill_name, "path": str(path),
        "description": description, "tags": " ".join(tags), "headings": " | ".join(headings[:40]),
        "git_root": git_root, "git_state": git_state,
        "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
        "tokens_est": max(1, len(text) // 4),
    }


def sync(cfg: dict, full: bool = False, quiet: bool = False) -> dict:
    conn = connect(cfg)
    git = GitInfo()
    if full:
        conn.execute("DELETE FROM skills")
    known = {r["path"]: (r["id"], r["sha256"], r["git_state"])
             for r in conn.execute("SELECT id, path, sha256, git_state FROM skills")}
    seen, added, updated, unchanged = set(), 0, 0, 0
    cols = ["name", "namespace", "kind", "parent", "path", "description", "tags", "headings",
            "git_root", "git_state", "sha256", "size", "tokens_est"]
    with conn:
        for root, path in iter_files(cfg):
            sp = str(path)
            if sp in seen:
                continue
            seen.add(sp)
            prev = known.get(sp)
            if prev:
                # cheap check first: same bytes and same git state → skip re-parse
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest == prev[1] and git.state(path)[1] == prev[2]:
                    unchanged += 1
                    continue
            row = build_row(root, path, git)
            if row is None:
                continue
            if prev:
                conn.execute(f"UPDATE skills SET {', '.join(c + '=?' for c in cols)}, indexed_at=datetime('now') "
                             "WHERE id=?", [row[c] for c in cols] + [prev[0]])
                updated += 1
            else:
                conn.execute(f"INSERT INTO skills ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             [row[c] for c in cols])
                added += 1
        removed = [known[p][0] for p in known if p not in seen]
        conn.executemany("DELETE FROM skills WHERE id=?", [(i,) for i in removed])
        conn.execute("INSERT INTO skills_fts(skills_fts) VALUES ('optimize')")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('last_sync', datetime('now'))")
    result = {"added": added, "updated": updated, "removed": len(removed), "unchanged": unchanged,
              "total": conn.execute("SELECT count(*) FROM skills").fetchone()[0], "db": cfg["db_path"]}
    conn.close()
    if not quiet:
        print(json.dumps(result, ensure_ascii=False))
    return result


# ---------------------------------------------------------------- queries

FIELDS = "s.id, s.name, s.namespace, s.kind, s.parent, s.path, s.description, s.tags, s.git_state, s.tokens_est"


def _fts_query(q: str) -> str | None:
    """Turn free text into an FTS5 OR-query of quoted terms (trigram needs >= 3 chars)."""
    terms = [t for t in re.findall(r"[^\s\"'(),;:]+", q) if len(t) >= 3]
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms) or None


def search(conn, query: str, limit: int = 5, kind: str | None = None,
           namespace: str | None = None, verified: bool = False) -> list[dict]:
    where, args = [], []
    if kind:
        where.append("s.kind = ?"); args.append(kind)
    if namespace:
        where.append("s.namespace = ?"); args.append(namespace)
    if verified:
        where.append("s.git_state = 'clean'")
    extra = (" AND " + " AND ".join(where)) if where else ""
    fq = _fts_query(query)
    rows = []
    if fq:
        # bm25 column weights: name > tags > description > headings. bm25 is negative (lower = better),
        # so multiplying skills by 2 ranks a skill above its own modules for the same terms.
        rows = conn.execute(
            f"SELECT {FIELDS}, bm25(skills_fts, 10.0, 5.0, 2.0, 1.0) "
            f"* (CASE s.kind WHEN 'skill' THEN 2.0 ELSE 1.0 END) AS score "
            f"FROM skills_fts JOIN skills s ON s.id = skills_fts.rowid "
            f"WHERE skills_fts MATCH ?{extra} ORDER BY score LIMIT ?",
            [fq, *args, limit * 3]).fetchall()
    if not rows:
        # short terms (e.g. 2-char CJK words) fall back to an indexed-prefix + LIKE scan
        like = [t for t in query.split() if t] or [query]
        cond = " OR ".join("(s.name LIKE ? OR s.tags LIKE ? OR s.description LIKE ?)" for _ in like)
        largs = [a for t in like for a in (f"%{t}%",) * 3]
        rows = conn.execute(f"SELECT {FIELDS}, 0 AS score FROM skills s WHERE ({cond}){extra} "
                            f"ORDER BY s.kind DESC, length(s.name) LIMIT ?", [*largs, *args, limit * 3]).fetchall()
    # the same skill can exist in several roots (Git repo, plugin cache, synced copy): show it once,
    # at the rank of its best copy, but point at the Git-reviewed copy when one exists
    rank = {"clean": 0, "modified": 1, "untracked": 2, "no-git": 3}
    best: dict[str, sqlite3.Row] = {}
    order: list[str] = []
    for r in rows:
        key = r["name"]
        if key not in best:
            order.append(key)
            best[key] = r
        elif rank.get(r["git_state"], 9) < rank.get(best[key]["git_state"], 9):
            best[key] = r
    return [_compact(best[k]) for k in order[:limit]]


def _compact(r: sqlite3.Row, desc_len: int = 240) -> dict:
    d = dict(r)
    if d.get("description") and len(d["description"]) > desc_len:
        d["description"] = d["description"][:desc_len] + "…"
    d.pop("score", None)
    return d


def get(conn, key: str) -> dict | None:
    if key.isdigit():
        r = conn.execute(f"SELECT {FIELDS} FROM skills s WHERE id=?", (int(key),)).fetchone()
    else:
        ns, _, nm = key.rpartition(":")
        r = conn.execute(f"SELECT {FIELDS} FROM skills s WHERE name=? AND (?='' OR namespace=?) "
                         f"ORDER BY kind DESC LIMIT 1", (nm, ns, ns)).fetchone()
    if not r:
        return None
    out = dict(r)
    if out["kind"] == "skill":
        # modules of this exact copy: files under the SKILL.md's own directory
        skill_dir = str(Path(out["path"]).parent) + os.sep
        out["modules"] = [dict(m) for m in conn.execute(
            "SELECT name, path, tokens_est FROM skills WHERE kind='module' AND substr(path, 1, ?) = ? ORDER BY name",
            (len(skill_dir), skill_dir))]
    return out


READONLY_SQL = re.compile(r"^\s*(SELECT|WITH)\b", re.I)


def run_sql(conn, sql: str, max_rows: int = 50) -> list[dict]:
    """Read-only SQL. The connection is opened mode=ro as well, so this is defence in depth."""
    if not READONLY_SQL.match(sql) or ";" in sql.strip().rstrip(";"):
        raise ValueError("Only a single SELECT/WITH statement is allowed.")
    cur = conn.execute(sql)
    return [dict(r) for r in cur.fetchmany(max_rows)]


def stats(conn) -> dict:
    q = lambda s: [dict(r) for r in conn.execute(s)]
    return {
        "by_kind": q("SELECT kind, count(*) n, sum(tokens_est) tokens FROM skills GROUP BY kind"),
        "by_namespace": q("SELECT namespace, count(*) n FROM skills WHERE kind='skill' GROUP BY namespace ORDER BY n DESC"),
        "by_git_state": q("SELECT git_state, count(*) n FROM skills GROUP BY git_state"),
        "last_sync": (conn.execute("SELECT value FROM meta WHERE key='last_sync'").fetchone() or [None])[0],
    }


# ---------------------------------------------------------------- cli

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_ in (("init", "create schema and fully (re)build the index"),
                        ("sync", "incremental re-index of changed/added/removed files")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--quiet", action="store_true", help="print nothing (for SessionStart hooks)")
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--limit", type=int, default=5)
    s.add_argument("--kind", choices=["skill", "module"]); s.add_argument("--namespace")
    s.add_argument("--verified", action="store_true", help="only git-clean (reviewed & committed) files")
    g = sub.add_parser("get"); g.add_argument("key", help="id, name, or namespace:name")
    q = sub.add_parser("sql"); q.add_argument("query")
    sub.add_parser("stats")
    a = p.parse_args(argv)
    cfg = load_config()

    if a.cmd in ("init", "sync"):
        sync(cfg, full=a.cmd == "init", quiet=a.quiet)
        return
    if not os.path.exists(cfg["db_path"]):
        sys.exit("Index not built yet. Run: python skill_index.py init")
    conn = connect(cfg, readonly=True)
    if a.cmd == "search":
        out = search(conn, a.query, a.limit, a.kind, a.namespace, a.verified)
    elif a.cmd == "get":
        out = get(conn, a.key)
    elif a.cmd == "sql":
        out = run_sql(conn, a.query)
    else:
        out = stats(conn)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
