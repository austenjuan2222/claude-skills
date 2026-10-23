每週一上午 09:00（Asia/Taipei）檢查我供 Claude Code／Cowork 使用的 skills 上游更新，只檢查、準備差異報告，絕不自行套用、安裝新依賴、推送 GitHub 或更換 Cowork 插件。不要建立 Windows 排程或 Codex 自動化。

優先使用已安裝且經測試的更新工具。若此工作階段具有桌機的本機檔案與終端機權限：讀取 C:\Users\TESTER\.claude\skills-updater\README.md，執行 powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\TESTER\.claude\skills-updater\update-skills.ps1 -Mode Check，再讀取 latest.json 指向的 report.md、changes.diff、report.json。check 不執行新下載腳本，不覆蓋技能。只在新的有意義變更或錯誤、需要我處理時通知；latest.json 的 notify 為 false 且沒有新問題時保持安靜。

若是雲端工作階段，不能讀取桌機 .claude，請不要假裝讀到或另建本機排程。改為檢查下列公開上游倉庫，只比較列出的技能路徑：使用本任務保留的最近一次上游快照作基準；首次沒有快照時使用下列 commit。把新快照與變更報告保存到這個 Claude 任務的檔案，供後續執行比對。若無法存取前次快照，明確說明無法排除重複，不宣稱已確認本機狀態。

重要：上游整個倉庫有新提交不等於技能有更新；必須比較對應路徑的檔案樹、內容或歷史。只在技能路徑有新的實際變更、檢查失敗或需要使用者操作時提醒，沒有變更時不發例行通知。回報更新的 skill、變更摘要、相容性及測試需求、來源連結；不得讀取或儲存金鑰。保留 genjutsu-ui-ux-pro-max 名稱、REA 外部參考路徑修正及 Design DNA sharp 0.35.5 修補版，不能自動降版。

私人版本來源是 https://github.com/austenjuan2222/claude-skills；若連接器有權限，可讀 skills/_sources/updater/sources.json、upstream-baseline.json 與 shared-skills-manifest.json。沒有權限時使用下面的公開上游基準。雲端檢查不代表本機或 Cowork 插件已更新。

上游路徑與首次基準：
- CloudAI-X/threejs-skills；commit 0e181866f095b5f06d005133876e926515390d95；路徑：skills/threejs-animation, skills/threejs-asset-pipeline, skills/threejs-fundamentals, skills/threejs-geometry, skills/threejs-interaction, skills/threejs-lighting, skills/threejs-loaders, skills/threejs-materials, skills/threejs-performance, skills/threejs-postprocessing, skills/threejs-react-three-fiber, skills/threejs-shaders, skills/threejs-textures
- greensock/gsap-skills；commit aed9cfd3277740755f6bfc1155c7aa645403b760；路徑：skills/gsap-core, skills/gsap-frameworks, skills/gsap-performance, skills/gsap-plugins, skills/gsap-react, skills/gsap-scrolltrigger, skills/gsap-timeline, skills/gsap-utils
- lottiefiles/motion-design-skill；commit f9a8a041b85185ee4881b3471d3415e939aac772；路徑：skills/motion-design
- AThevon/genjutsu；commit 1f518a71378b15d423389e546e767cffc86e14c3；路徑：skills/_jutsu, skills/bunshin, skills/cast, skills/paint
- zanwei/design-dna；commit 593e39bc9e3652734653bd75544a333d7d43615e；路徑：SKILL.md, LICENSE, references/, scripts/
- WenyuChiou/awesome-agentic-ai-zh；commit 3c5356d0ba345a57e54a13965c60261173d47c4b；路徑：examples/stage-5/tool-calling-tutor
- harry0703/MoneyPrinterTurbo；commit f063a2b95e0f71f60891ac1c7b53add684bc6a46；路徑：docs/skill
- heygen-com/hyperframes；commit 2ed882ccf22fdf070e21442e0437b3ae57253405；路徑：skills/figma, skills/hyperframes, skills/hyperframes-cli, skills/hyperframes-registry, skills/media-use, skills/remotion-to-hyperframes, skills/slideshow, .claude/skills/captions-overlay, .claude/skills/changelog-video, .claude/skills/cut-the-curve, .claude/skills/motion-doctrine, .claude/skills/oversized-cursor, .claude/skills/seam-craft, registry/blocks/canopy-part-title, registry/blocks/code-slice-hero, registry/blocks/cuboid-carousel, registry/blocks/frost-sequence-camera-orbit, registry/blocks/glass-shard-title, registry/blocks/orbit-card, registry/blocks/wireframe-portal-title
- latent-spaces/brag；commit 069432cac935ed1895859df201c31436c07fb74e；路徑：skills/brag, skills/brag-slim
- morluto/rea；commit 5f702dd6ccd9e8e505e224854b91678439c3b41f；路徑：.agents/skills/rea-analysis-optimization, .agents/skills/rea-changelog-update, .agents/skills/rea-ci-tests-audit, .agents/skills/rea-tool-design, .agents/skills/reverse-engineer-anything
- usestrix/strix；commit 594398876f9cd465f00cce626d0cb98bfa5e1662；路徑：skills/api-security-testing, skills/application-security-testing, skills/ci-security-scanning-with-strix, skills/find-security-vulnerabilities-in-code, skills/fix-security-vulnerabilities-with-strix, skills/managed-pentesting-with-strix, skills/owasp-top-10-testing, skills/penetration-testing-with-strix, skills/web-app-penetration-testing
