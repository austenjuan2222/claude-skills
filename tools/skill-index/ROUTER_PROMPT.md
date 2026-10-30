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

CLI equivalent (if MCP is unavailable): `python {{TOOL_DIR}}/skill_index.py search "<keywords>"`,
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
