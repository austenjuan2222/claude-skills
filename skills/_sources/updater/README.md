# Claude skills 更新管理

這些工具供 Claude Code / Cowork 使用；依使用者偏好，週期工作使用 Claude 內建排程，不使用 Windows 工作排程器或 Codex 自動化。

## 更新政策

- 預定每週一 09:00（Asia/Taipei）由 Claude 內建排程檢查；是否已建立須以 Claude 的排程頁確認，不能以本機檔案存在推斷。
- 本機檢查追蹤 11 個上游來源、64 個主要 skills 與 17 個 Genjutsu 內部模組；另 17 個主要技能未指定上游，維持原樣。
- 檢查只下載候選變更並產生差異報告，不執行新下載的程式，不自動覆蓋技能。
- 保留內部模組名稱 `genjutsu-ui-ux-pro-max`、REA 外部參考路徑修正，以及 Design DNA 的 `sharp 0.35.5` 修補版。
- 只有新的待審查變更、完成、錯誤或需要使用者處理的情況才提醒；相同結果不重複通知。
- 確認具體報告後才能套用。程式核對報告 SHA256、本機檔案及候選檔案，建立逐檔備份；驗證失敗時還原檔案。
- GitHub 發佈需要明確的 `-Publish`。GitHub 推送不代表 Cowork 帳號已更新，必須另外匯入新版插件並確認。

## 在 Claude 中使用

檢查：

> 幫我檢查 Claude skills 更新，讀取 ~/.claude/skills-updater/latest.json 和對應的 report.md、changes.diff。先解釋變更，不要直接套用。

審閱完後：

> 我同意套用這份更新報告。請使用該報告的完整 SHA256 核准碼套用，執行必要測試，成功後推送 GitHub，並協助更新 Cowork 插件。失敗時回報並保留還原資訊。

Claude Code 可在有本機工具的工作階段執行下列指令。Cowork 的雲端排程無法直接讀取桌機 `.claude` 時，應依附帶排程提示詞檢查公開上游並報告限制；不要宣稱已更新本機、修改快取或另建 Windows 排程。

## 手動檢查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills-updater\update-skills.ps1" -Mode Check
```

最新結果：`~/.claude/skills-updater/latest.json`；完整差異位於該檔指向的 report.md 及 changes.diff。

## 明確核准後套用

先讀取並審閱報告，再執行：

```powershell
$latest = Get-Content "$env:USERPROFILE\.claude\skills-updater\latest.json" -Raw | ConvertFrom-Json
# 僅在審閱並同意後執行下一行：
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills-updater\update-skills.ps1" -Mode Apply -Report $latest.report -Approval $latest.approval -Publish
```

如果審閱後本機或候選檔案又改了，程式會拒絕套用，請重新檢查並審閱。

## 還原

```powershell
$last = Get-Content "$env:USERPROFILE\.claude\skills-updater\last-apply.json" -Raw | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills-updater\update-skills.ps1" -Mode Rollback -Backup $last.backup
```

這會還原本機及 Git 工作副本的檔案，不重寫 Git 歷史，也不撤回 Cowork 帳號版本。相依套件若有變更，以還原後 lockfile 執行 `npm ci --ignore-scripts`。撤回已推送版本時，檢查還原結果並建立回復提交，再重建及匯入插件。

## 筆電安裝

從私人倉庫取得 skills，執行 `skills/_sources/updater/install-updater.ps1`，它會備份舊更新程式並產生筆電的 config.json，不建立任何 Windows 排程。Claude 的內建排程隨帳號管理；本機工具仍需在各機器安裝。

node_modules、憑證及機器設定不放進 GitHub 或 Cowork 插件。紀錄與備份保存在 `.claude/skills-updater`。
