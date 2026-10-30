#!/usr/bin/env python3
"""Minimal stdio MCP server exposing the skill index (stdlib only, no `mcp` SDK needed).

Tools (all read-only; none returns file bodies — the agent loads the chosen path itself):
  skill_search  free-text / keyword search over name, tags, description, headings
  skill_get     metadata, path and module list for one skill
  skill_sql     a single read-only SELECT against the `skills` table
  skill_stats   counts by namespace, kind and git state

Register with Claude Code:
  claude mcp add skill-index -s user -- python <abs path>/mcp_server.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_index as si  # noqa: E402

PROTOCOL = "2025-06-18"

TOOLS = [
    {
        "name": "skill_search",
        "description": ("Find the skill or module file that fits a task. Returns name, namespace, kind, "
                        "path and a short description, ranked by BM25. Call this BEFORE reading any skill "
                        "file; then Read only the returned path. Never list or glob skill directories."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords in any language, e.g. 'merge pdf' or '保單 部署'"},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "kind": {"type": "string", "enum": ["skill", "module"]},
                "namespace": {"type": "string", "description": "Plugin/collection, e.g. 'superpowers'"},
                "verified": {"type": "boolean", "default": False,
                             "description": "Only files that are committed and unmodified in Git (human-reviewed)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "skill_get",
        "description": "Metadata and path for one skill (by id, name, or namespace:name), plus its module files.",
        "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    {
        "name": "skill_sql",
        "description": ("Run ONE read-only SELECT on table skills(id, name, namespace, kind, parent, path, "
                        "description, tags, headings, git_root, git_state, sha256, size, tokens_est, indexed_at) "
                        "or FTS5 table skills_fts(name, description, tags, headings). Max 50 rows."),
        "inputSchema": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
    },
    {
        "name": "skill_stats",
        "description": "Index size by kind, namespace and git state, plus last sync time.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(name: str, args: dict):
    cfg = si.load_config()
    if not os.path.exists(cfg["db_path"]):
        raise RuntimeError("Skill index not built. A human must run: python skill_index.py init")
    conn = si.connect(cfg, readonly=True)
    try:
        if name == "skill_search":
            return si.search(conn, args["query"], int(args.get("limit", 5)), args.get("kind"),
                             args.get("namespace"), bool(args.get("verified", False)))
        if name == "skill_get":
            return si.get(conn, str(args["key"])) or {"error": f"no skill named {args['key']!r}"}
        if name == "skill_sql":
            return si.run_sql(conn, args["sql"])
        if name == "skill_stats":
            return si.stats(conn)
        raise ValueError(f"unknown tool {name}")
    finally:
        conn.close()


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # notification (e.g. notifications/initialized)
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "skill-index", "version": "1.0.0"},
                  "instructions": ("Skill library router. Use skill_search to get a file path, then Read only "
                                   "that file. Do not enumerate skill directories.")}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg.get("params", {})
        try:
            data = call_tool(p.get("name"), p.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=1)}]}
        except Exception as e:  # tool errors are returned to the model, not raised as protocol errors
            result = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    stdin = open(sys.stdin.fileno(), encoding="utf-8", newline="\n")
    stdout = open(sys.stdout.fileno(), "w", encoding="utf-8", newline="\n")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
