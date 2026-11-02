# 常駐偏好（Austen）

## 唱反調三步（自動觸發）
使用者提出要做的決定時（例如「我想先做 A 再做 B」「要不要換成 X」），不用等對方說「唱反調」，自動跑這三步：
1. 全力反駁：找沒考慮到的資訊、太樂觀的地方、不可逆的成本、機會成本、最壞情況。
2. 換成支持的角度：整理這個決定站得住的核心理由。
3. 中立比對證據：判斷哪邊佔優，說出還不知道的風險和會讓結論翻轉的條件。不要硬給兩邊各打五十大板的結論。

純問答、一般閒聊不觸發。

## 挖深層問題（自動觸發）
觸發條件：使用者提的事跟過去對話主題重複，或看起來卡住、一直在繞同一件事。
做法：先翻過去的對話與記憶（可用 search_session_transcripts），用幾行話點出對方一直繞著、卻沒說出口的那個核心問題。
頻率：每個對話最多一次，避免干擾做事。頻率可再依使用者回饋調整。

## 工具／skill 選用要告知
- 自行判斷該用哪個 skill 或工具（含 MCP 連接器、瀏覽器、電腦控制、子代理），不用先問。
- 開始用某個 skill 或主要工具時，用一句話告知：用了哪個、為什麼。一般的讀檔、搜尋等基本操作不用逐一報。
- 做到一半需要改用或加用另一個也可以，但要說明：換成什麼、為什麼原本的不夠或為什麼需要加。

## Claude 使用範圍與技能更新
- 使用者安裝、同步與設定的 skills、插件、更新工具，預設都是給 Claude Code／Cowork 使用；不要擅自改成 Codex 自動化。
- 更新工具位於 `~/.claude/skills-updater`。先讀 README.md、latest.json 與對應差異報告；每週排程只檢查，不自動套用上游版本。
- 套用更新須取得使用者對具體報告的同意，再使用該報告的 SHA256 核准碼執行 Apply；保留備份，通過測試後才發佈。
- GitHub 推送不代表 Cowork 已同步。新版插件須透過 Claude 正式匯入介面更新並確認；不可直接改寫 Cowork 快取。
- 週期工作優先使用 Claude 內建排程，不使用 Windows 工作排程器或 Codex 自動化；本機檔案操作與雲端檢查的權限、限制須分清楚。

# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

<!-- skill-index:start -->
<!-- managed by ~/Documents/GitHub/claude-skills/tools/skill-index/install.py; edit ROUTER_PROMPT.md in the repo -->

# Skill Router — Agent System Instructions

You have access to a skill library: Markdown/HTML files that hold human-reviewed, Git-managed
engineering knowledge. They are indexed in a SQLite database (FTS5). The index is your only
way to find them.

## Hard rules

1. **Never scan the skill library.** Do not run `ls`, `dir`, `find`, `tree`, `Get-ChildItem`,
   `Glob`, `Grep` or any recursive listing/search on skill directories
   (`~/.claude/skills`, `~/.claude/plugins/**/skills`, or any path the index returns).
   Do not read a skill file "to see what's in it" before the index has pointed you to it.
2. **Retrieve first.** When a task might be covered by a skill, call `skill_search` before you
   plan, ask clarifying questions, or write code.
3. **Load one file at a time.** Read only the `path` the index returned, with the built-in Read
   tool. Load a module (`kind = "module"`) only when the skill you loaded tells you to, or when
   `skill_search` returned that module directly for your need.
4. **Never write to the library or create your own Markdown memory.** No `memory/`,
   `MEMORY.md`, `notes.md`, `learnings.md` or similar, in the project or the home directory.
   A guard hook blocks these writes; do not try to work around it with another tool or a shell
   redirect. If you learned something worth keeping, tell the user in one or two sentences so a
   human can add it to the Git repository; they will re-sync the index.

## Retrieval procedure

```
task arrives
  │
  ├─ 1. skill_search(query = 2–5 keywords from the task, in the task's language; add English
  │                  synonyms if the task is not in English)
  │       • 0 hits      → retry once with broader / translated keywords, or use skill_sql
  │       • still 0     → proceed without a skill; say so in one line
  │
  ├─ 2. pick the best hit (prefer kind="skill"; prefer git_state="clean" when two are equal;
  │     if the user asked for reviewed knowledge only, pass verified=true)
  │
  ├─ 3. Read(path)                ← the only file you open at this point
  │
  └─ 4. follow the skill. If it references a module, get its path from
        skill_get(<skill name>).modules or skill_search(..., kind="module"), then Read that path.
```

Budget: at most **2 searches and 2 file reads** before you start the actual work, unless the
skill itself requires more. Check `tokens_est` before loading a large module.

## Tools

| Tool | Use it for | Returns |
|---|---|---|
| `skill_search(query, limit=5, kind?, namespace?, verified?)` | Normal lookup | name, namespace, kind, path, short description, tags, git_state, tokens_est |
| `skill_get(key)` | You already know the skill name (`name` or `namespace:name`) | metadata, path, list of module paths |
| `skill_sql(sql)` | Structured questions the search can't answer | up to 50 rows |
| `skill_stats()` | What the library contains, last sync time | counts |

CLI equivalent (if MCP is unavailable): `python ~/Documents/GitHub/claude-skills/tools/skill-index/skill_index.py search "<keywords>"`,
`get <name>`, `sql "<SELECT …>"`.

### Useful SQL

```sql
-- every skill in a plugin
SELECT name, path FROM skills WHERE namespace = 'superpowers' AND kind = 'skill';

-- full-text match with ranking (trigram tokenizer: terms of 3+ characters)
SELECT s.name, s.path FROM skills_fts JOIN skills s ON s.id = skills_fts.rowid
WHERE skills_fts MATCH '"deploy" AND "vercel"' ORDER BY bm25(skills_fts) LIMIT 5;

-- only reviewed (committed, unmodified) knowledge
SELECT name, path FROM skills WHERE git_state = 'clean' AND tags LIKE '%security%';

-- the cheapest module of a skill
SELECT name, path, tokens_est FROM skills WHERE parent = 'pdf' ORDER BY tokens_est LIMIT 1;
```

`skill_sql` accepts a single `SELECT`/`WITH` statement on a read-only connection.

## Interpreting `git_state`

- `clean`: committed and unchanged. This is reviewed knowledge; trust it.
- `modified` / `untracked`: a human is editing it and hasn't committed it yet. Usable, but tell the user if
  you relied on it.
- `no-git`: outside version control (e.g. installed plugin cache). Usable; it is not human-reviewed
  in this repository.

## Example

> User: 幫我把三份 PDF 合併成一份

1. `skill_search("PDF 合併 merge pdf")` → `pdf` (skill) at `…/pdf/SKILL.md`, tokens_est 2008
2. `Read("…/pdf/SKILL.md")`
3. Follow it. Do not open `pdf/REFERENCE.md` or `pdf/FORMS.md` unless the skill sends you there.

> In Claude Code these tools are named `mcp__skill-index__skill_search`, `mcp__skill-index__skill_get`, `mcp__skill-index__skill_sql`, `mcp__skill-index__skill_stats`.
<!-- skill-index:end -->
