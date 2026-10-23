---
name: "policy-bot-rules"
description: "三商品保單客服機器人（policy-demo，RAC／RAE2／SCB）的開發規則。只要提到保單機器人、policy-demo、安新100、享安心、安心加倍防癌，或要修改、測試、部署這個網站，就使用這個 skill。"
---

# 保單客服機器人開發規則

## 專案背景
- 三商品：安新100（RAC）、享安心（RAE2）、安心加倍防癌（SCB），資料來源是第一金人壽的範例文件。
- 本機資料夾：`C:\Users\TESTER\Documents\ChatGPT\保單\policy-demo\site`
- 公開站：policy-assistant-three-products-1018.fuzzyanole33.chatgpt.site
- 保留現有網站與三商品資料。修改時以小幅更動為主，不要整站重寫，因為使用者已經投入時間，也已經上線。

## API 金鑰（最重要）
- 回答由 Claude 提供，模型使用 Haiku 等級，以節省費用。
- 金鑰只能放在伺服器端環境變數（例如 `ANTHROPIC_API_KEY`），前端只能呼叫自己的後端端點。寫進前端 JS 的金鑰，任何訪客打開開發者工具就能看到並盜用。
- 不要請使用者把金鑰貼在聊天中，請他們自己在託管平台的環境變數設定頁貼上。
- 每次修改後，搜尋前端檔案中是否出現 `sk-ant`、`x-api-key`、`api.anthropic.com`。只要前端直接呼叫 Anthropic，就視為漏洞。

## 誠實回報
- 沒有實際執行過的測試，不可以說通過。請寫明「未執行」與原因。
- 無法執行程式或部署時，直接說明，並改提供 patch 檔或完整修改後的檔案。
- 宣稱完成前，先依照 superpowers:verification-before-completion 實際驗證。

## 目前優先順序
1. 確認 Claude 真的接上了（不是前一版的 Gemini 提示）。
2. 修正公開站的文字，避免仍寫著「私人／private」或「Gemini」。
3. 費率顯示正確：數字要和原始文件一致，並標示單位與條件。
4. 引用可靠：每個回答都要附上依據的商品與條款或段落，找不到依據就說不知道，不要猜。

## 系統提示詞
修改機器人的系統提示時，先讀 prompt-engineering-patterns skill，重點放在：限定只用三商品資料回答、強制引用、超出範圍時拒答並建議洽詢業務員。

## 暫緩事項
簡報與專家審核的測試問答集都先不做，除非使用者主動提起。