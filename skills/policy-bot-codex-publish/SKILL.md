---
name: "policy-bot-codex-publish"
description: "在桌面版一般對話中，用電腦控制操作 Codex App 把保單客服網站（policy-demo）發布到 chatgpt.site 並驗收線上版。使用者說「發布保單網站」或要用 Codex 發布時使用。"
---

# 用 Codex App 發布保單客服網站

回覆用繁體中文、簡潔。沒實際驗證的項目不可說通過。

## 前提
- 只能在**桌面版一般對話**執行（專案對話／Remote Control 沒有電腦控制工具）。若沒有 `mcp__remote-devices__computer_*` 工具，告訴使用者到桌面版開一般對話，然後停止。
- 桌機的 Claude 桌面版要開著、電腦醒著。

## 固定資訊
- 專案資料夾：`C:\Users\TESTER\Documents\ChatGPT\保單\policy-demo`
- 發布指令檔：`policy-demo\site\給Codex的發布指令.txt`
- 公開站：https://policy-assistant-three-products-1018.fuzzyanole33.chatgpt.site/
- Codex App 在電腦控制中顯示為「ChatGPT」（bundleId `OpenAI.Codex_2p2nqsd0c76g0!App`），用 "Codex" 解析會找不到。

## 步驟
1. **讀發布指令**：`device_request_folder_access` 申請 policy-demo 資料夾 → `device_stage_files` 取得發布指令檔 → Read 全文。
2. **取得 App 權限**：用 ToolSearch 查詢 `computer`（max_results 40）載入工具 → `computer_resolve_access(apps=["ChatGPT"], clipboardWrite=true)` → `computer_request_access`，回傳的 entries 原封不動傳入。
3. **開新任務**：`computer_open_application("ChatGPT")` → 截圖 → 點左上「新對話」→ 確認專案是「保單」（只有這個專案，policy-demo 在它底下）。
4. **貼上送出**：`computer_write_clipboard` 寫入「（工作資料夾：專案「保單」底下的 policy-demo\site）」加上發布指令全文 → 點輸入框 → ctrl+v → 截圖確認 → 點送出鈕。
5. **等待**：每次 `computer_batch`（wait 50 秒＋0.6 倍截圖）輪詢，總等待時間不可超過 50 秒；需要時用 zoom 讀文字。通常 2–5 分鐘完成。
6. **已知錯誤：`"npm" is not recognized`**：這是 PATH 問題，程式沒有錯。回覆 Codex：找出 node/npm 的實際位置（where node、Get-Command npm、npm.cmd 或完整路徑，或把 Node 加入這次 shell 的 PATH），重跑 build 後發布到同一網站；規則不變，不改程式碼與 knowledge.json，build 失敗就不發布。
   其他錯誤：照實回報給使用者，不自行修改程式碼。
7. **記下 Codex 回報**：版本號、發布時間、測試／tsc／build 結果、/api/status。完成後呼叫 `computer_release_lock`。
8. **自己驗收線上版**（用內建瀏覽器 `mcp__remote-devices__Claude_Browser__*`，先讀 built-in-browser skill）：
   - navigate 到公開站首頁。
   - javascript_tool：fetch `/api/status`（cache:no-store），確認 `configured:true`，記下 provider／model。
   - 列出文字含「問／查證／安心」的 `a` 元素與其 href（預期 `/chat`、`/chat?tab=library`、`/chat?tab=rates`），並 fetch 這些路徑確認回 200。
   - 確認首頁有 `/chat?...q=` 的問題卡連結。
   - 檢查首頁 HTML 不含 `sk-ant`、`x-api-key`、`api.anthropic.com`、`AIza`。
   - 實際點一個步驟連結（用 find 找 ref），確認網址有跳轉。

## 回報格式
- 發布：第 N 版、時間、網址不變；過程中處理過的問題（一句話）。
- 驗收：逐項列出實測結果（可點、200、configured、無金鑰外洩）。
- 沒測到的項目寫「未驗證」並說明原因。