---
name: "policy-bot-vercel-deploy"
description: "部署或更新三商品保單客服機器人（policy-demo）到 Vercel 時使用：取得檔案、檢查金鑰、建 /api 函式、部署、驗證。"
---

# 保單機器人 Vercel 部署流程

先讀 policy-bot-rules，遵守其中的金鑰與誠實回報規則。

## 1. 取得網站檔案
- 優先：對話已連結桌面 App 時，從 `C:\Users\TESTER\Documents\ChatGPT\保單\policy-demo\site` 讀取。
- 否則請使用者上傳 zip。不要憑記憶重建檔案。

## 2. 金鑰檢查（部署前必做）
- 搜尋前端檔案：`sk-ant`、`x-api-key`、`api.anthropic.com`、`gemini`、`generativelanguage`。
- 任何前端直接呼叫模型 API 的地方，都改成呼叫 `/api/chat`。

## 3. 後端函式
- 建立 `api/chat.js`（Vercel Serverless Function），從 `process.env.ANTHROPIC_API_KEY` 讀金鑰，模型用 Haiku 等級。
- 系統提示：只用三商品資料回答、必附商品與條款出處、找不到依據就說不知道並建議洽業務員。
- 加基本防護：限制輸入長度、只接受 POST。

## 4. 文字修正
- 移除「私人／private」「Gemini」字樣。
- 確認費率數字與原始文件一致，並標示單位與條件。

## 5. 部署
- 用 Vercel 連接器建立或更新專案並部署。
- 提醒使用者自己到 Vercel 專案 Settings → Environment Variables 加 `ANTHROPIC_API_KEY`，不要在聊天中貼金鑰；加完需重新部署。

## 6. 驗證（未執行就寫「未執行」）
- 用 Vercel 工具查 runtime logs／errors。
- 實測三題：各商品一題，確認有回答且附出處。
- 再搜一次部署後的前端檔案，確認沒有金鑰。
- 回報：網址、改了哪些檔、哪些驗證有跑、哪些沒跑。