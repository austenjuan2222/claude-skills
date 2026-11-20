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

### 全自動同步（筆電、桌機）

```bash
python "$HOME/Documents/GitHub/claude-skills/tools/skill-index/install.py" --auto-sync
```

加上 `--auto-sync` 後，每次開 Claude Code 都會自動：commit 本機改動 → `pull --rebase` → `push` → 把 `~/.claude/skills` 裡的每個 repo skill 換成連到 repo 的連結（Windows 用 junction）→ 更新索引。
所以三個地方（筆電、桌機、雲端）用的都是 GitHub 上同一份 skill。

- 原本 `~/.claude/skills` 裡的複本不會被刪：一律先移到 `~/.claude/skills-backup/<時間>/`，內容和 repo 不同的會在對話中提醒。
- 不在 repo 的 skill（例如 Anthropic 內建的 `docx`、`pdf` 複本）完全不動。
- 保護規則、機密檔檢查、禁止 `--force` 都照舊；遇到衝突會停下來告訴你，不會亂合。
- 沒有東西要同步時不會輸出任何訊息。

只想看會做什麼：`python tools/skill_links.py --dry-run`

## 安裝後的檔案位置

| 位置 | 內容 |
|---|---|
| 這個資料夾（repo 內） | 程式碼。執行 `git pull` 就會更新，兩台電腦共用同一份 |
| `~/.claude/skill-index/` | 這台電腦專用：`config.json`、`skills.db`、`session_start.log` |
| `~/.claude/settings.json` | guard hook（PreToolUse）和 SessionStart hook（只 fetch、有新版就提醒，再同步本機索引） |
| `~/.claude/CLAUDE.md` | Router 指引，放在 `skill-index:start` 和 `skill-index:end` 兩個標記之間，標記外的內容不會被動到 |
| MCP `skill-index`（使用者層級） | 提供 `skill_search`、`skill_get`、`skill_sql`、`skill_stats` |

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `skill_index.py` | 索引器與 CLI：`init`、`sync`、`search`、`get`、`sql`、`stats` |
| `mcp_server.py` | stdio MCP 伺服器，全部操作都是唯讀 |
| `guard_hook.py` | 禁止 Agent 改寫技能庫，也禁止 Agent 自己建立 Markdown 記憶檔 |
| `session_start.py` | 每個工作階段開始時，對 Git 管理的根目錄只執行 `fetch`；有新版時在對話中提醒（不自動 pull，經使用者同意才 `pull --ff-only`），再做增量同步 |
| `ROUTER_PROMPT.md` | Agent 的路由規則，安裝時會寫進 `CLAUDE.md` |
| `install.py` | 一鍵安裝、修復、解除安裝；`--auto-sync` 開啟全自動同步 |
| `../skill_links.py` | 把 `~/.claude/skills` 的 repo skill 換成連到 repo 的連結（只備份、不刪除） |
| `../tests/` | 單元測試：`python -m unittest discover -s tools/tests` |

## 日常使用

- 新增或修改技能：人工編輯 → `git commit` → `git push`。另一台電腦開下一個工作階段時會自動拉下來並重建索引。
- 想立刻更新索引：`python session_start.py`；想完全重建：`python skill_index.py init`
- 查看最近一次 fetch 檢查和同步的結果：`~/.claude/skill-index/session_start.log`
