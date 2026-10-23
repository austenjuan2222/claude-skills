# Claude Code / Cowork 共用技能

共同的自訂清單：73 個原本的 Code skills + 8 個既有帳號個人 skills，共 81 個主要 skills；另有 17 個 Genjutsu 內部模組。

- `shared-skills-manifest.json` 列出兩組名稱與安裝包資訊。
- `austen-shared-skills` 帳號插件打包 73 個主要 skills 與 17 個內部模組，保留腳本、參考文件和素材。
- 8 個既有帳號個人 skills 仍留在原位，這裡保存相同版本，避免在帳號中再安裝一份。
- 內部模組 `_jutsu/ui-ux-pro-max` 的識別名稱改為 `genjutsu-ui-ux-pro-max`，避免匯入時與獨立 skill 衝突；目錄不變。
- 內建與第三方插件保留各自原版本，不併入自訂數量。

## 更新

在此倉庫更新 skill 並推送後，執行：

```powershell
python skills/_sources/build_shared_plugin.py --output austen-shared-skills.zip
```

到 Claude 的「自訂 → 外掛程式」上傳同名插件更新。GitHub push 本身不會自動更新 Claude 帳號。

Claude Code 需以同一個 Claude 帳號登入，版本至少 2.1.273，並保持 `syncClaudeAiSkills: true`，才能使用官方帳號同步。若只用本機檔案，將倉庫的 skills 複製到自己的 `.claude/skills`；已有同名檔案時先備份，避免覆蓋未提交的修改。

本次安裝電腦保留了本機完整副本。帳號同步成功後，若 `/skills` 出現本機與帳號插件兩種來源，核對內容一致再把本機副本移到備份位置；不要在尚未登入時移除。

## 使用條件

同步技能檔案不會同步金鑰、Docker、瀏覽器、FFmpeg、REA MCP 或其他執行環境。首次使用相關功能時，在執行端檢查相依工具。平台專屬流程不代表另一平台也具備相同工具。

官方說明：https://support.claude.com/en/articles/12512180-use-skills-in-claude
