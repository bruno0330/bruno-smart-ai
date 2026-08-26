# Bruno Smart AI Ltd. — 專案脈絡

使用者的個人專案，把自己定位成「一人公司」，用組織架構（處／部）對應已完成、規劃中、未來可規劃的數位工具。核心判準：工具是否真的做出來、真的省到使用者的時間——不是空談組織圖。

正式上線：`https://bruno0330.github.io/bruno-smart-ai/`（GitHub Pages，repo `bruno0330/bruno-smart-ai`）。這裡就是正式運作位置，改網站/工具功能直接在這裡改。

## 這個資料夾 vs. OneDrive 的「Bruno Claude files」

- **這裡（`~/Projects/bruno-smart-ai/`）**——正式 git repo，正式上線內容都在這。
- **OneDrive `Bruno Claude files/`**——使用者個人 OneDrive，放交接文件、歷史檔案，**不是**開發位置，不要去改那邊的舊複製檔。
- 使用者的開發習慣：實際寫程式主要在 Claude App（桌面版）進行；找 Claude Code（這裡）是為了**回顧進度、規劃下一步、審核並 push**。

## 開新 session 想接續進度時，怎麼抓現況

不用等使用者交接，先自己看：
1. `git log --oneline -20` 看最近做了什麼
2. `git status` / `git diff --stat` 看有沒有未 commit 的異動
3. 需要更完整脈絡再讀 `~/.claude/skills/bsa-coordinator/SKILL.md`（統籌／審核 push 的 SOP）

## 組織架構現況（6 處 14 部，2 部已上線）

產品研發處（市場調查部、輿情分析部）／智能內容處（**智能策展部**＝遠見線上讀，已上線／內容生成部）／會員經營處（會員數據分析部、會員關懷部、**數位行銷部**已上線、**訂單處理部**規劃中）／社群經營處（LINE OA智能貼文部）／圖文設計處（視覺設計部）／秘書處（CEO秘書部、客戶關懷部、CEO健康管理部——僅部門名稱定案）。

## 硬性規則（不是風格偏好，是產品正確性要求）

1. **零捏造資訊**——牽涉文章/期數/連結/資料時，100% 用真實來源，不確定就標註提示、問使用者，不要用猜的填。這是所有工具的核心要求，`bsa-coordinator` skill 的審核流程也把它列為 non-negotiable。
2. **零外部 API 呼叫（前端）**——這是公開靜態網站，前端藏不住 API 金鑰，任何會被 push 到這個 repo、部署上線的程式碼都不能內嵌憑證或呼叫外部 API。本機 Claude Code session 用環境變數/本機設定是另一回事，但進 git 歷史或部署內容的不行。
3. **手機寬度必測**——任何觸及按鈕/標頭排版的改動，push 前要在真手機寬度（375px）測過，不能只看桌機寬度。2026-08-21 曾因此出過手機版跑版的問題，只有使用者截圖才抓到。

## 技術基礎設施

- GitHub 帳號 `bruno0330`，單一 monorepo，不為每部門開獨立 repo。
- 資料夾結構：`index.html`（入口頁）、`assets/`（品牌 Logo）、`data/`（共用資料庫，`gvm_index_full.json` 29,583 篇遠見文章索引）、`smart-curation/`、`digital-marketing/`、`scripts/`、`.github/workflows/`。
- **雙機器已設定**：兩台 Mac 都能 push 到同一個 repo，SSH 金鑰與 git 身份各自獨立設定（金鑰不可跨機器複製）。兩邊都有未 push 的 commit 時，push 前留意先 pull/rebase 避免衝突。
- 每月文章自動化：`scripts/monthly_scrape.py` + GitHub Actions（每月 5 號跑，開 PR 給人工審核，不直接推 main）。

## 已上線工具速覽

- **智能策展部（遠見線上讀）** `smart-curation/`——關鍵字→真實文章庫→策展頁面，選文邏輯全在瀏覽器端 JS 跑（零 API）。
- **數位行銷部 UTM 產生器** `digital-marketing/`——取代手動 Excel 貼公式；命名規則來自使用者提供的公司內部 Excel，逐筆核對過，不要自行更改命名邏輯。

## 更完整的歷史脈絡

`~/Library/CloudStorage/OneDrive-個人/Bruno Claude files/bruno_smart_ai_handoff_2026-08-25.md` 有 2026-08-25 當時更完整的敘述（規劃中項目細節、待辦總覽等）。但那份文件會隨時間過時——`git log` 和這份 CLAUDE.md 才是活的來源，衝突時以這裡和 git 紀錄為準。
