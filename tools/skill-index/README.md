# skill-index

這個工具用 SQLite + FTS5 為技能庫建立索引。Agent 先查索引拿到單一檔案的路徑，再只讀那一份，不需要逐一瀏覽技能目錄。
只用 Python 標準函式庫，不必另外安裝套件（需要 Python 3.10 以上）。

## 新電腦安裝

```bash
git clone https://github.com/austenjuan2222/claude-skills.git "$HOME/Documents/GitHub/claude-skills"
```

```bash
python "$HOME/Documents/GitHub/claude-skills/tools/skill-index/install.py"
```

裝完後開一個新的 Claude Code 工作階段就能用。重複執行 `install.py` 也安全，可以拿來修復設定或套用工具的新版本。
解除安裝：`python install.py --uninstall`

## 安裝後的檔案位置

| 位置 | 內容 |
|---|---|
| 這個資料夾（repo 內） | 程式碼。執行 `git pull` 就會更新，兩台電腦共用同一份 |
| `~/.claude/skill-index/` | 這台電腦專用：`config.json`、`skills.db`、`session_start.log` |
| `~/.claude/settings.json` | guard hook（PreToolUse）和 SessionStart hook（先 pull 再同步） |
| `~/.claude/CLAUDE.md` | Router 指引，放在 `skill-index:start` 和 `skill-index:end` 兩個標記之間，標記外的內容不會被動到 |
| MCP `skill-index`（使用者層級） | 提供 `skill_search`、`skill_get`、`skill_sql`、`skill_stats` |

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `skill_index.py` | 索引器與 CLI：`init`、`sync`、`search`、`get`、`sql`、`stats` |
| `mcp_server.py` | stdio MCP 伺服器，全部操作都是唯讀 |
| `guard_hook.py` | 禁止 Agent 改寫技能庫，也禁止 Agent 自己建立 Markdown 記憶檔 |
| `session_start.py` | 每個工作階段開始時，先對 Git 管理的根目錄執行 `pull --ff-only`，再做增量同步 |
| `ROUTER_PROMPT.md` | Agent 的路由規則，安裝時會寫進 `CLAUDE.md` |
| `install.py` | 一鍵安裝、修復、解除安裝 |

## 日常使用

- 新增或修改技能：人工編輯 → `git commit` → `git push`。另一台電腦開下一個工作階段時會自動拉下來並重建索引。
- 想立刻更新索引：`python session_start.py`；想完全重建：`python skill_index.py init`
- 查看最近一次 pull 和同步的結果：`~/.claude/skill-index/session_start.log`
