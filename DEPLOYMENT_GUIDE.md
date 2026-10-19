# Google Cloud Run 完整部署與維運手冊 🚀

本手冊提供逐步、清晰且可直接執行的指令，引導您將 **Antigravity LINE Bot 與網頁化系統** 部署至 **Google Cloud Run**。

---

## 📌 為什麼選擇 Google Cloud Run？

1. **免費額度充足**：Google Cloud 提供每月 200 萬次請求的免費額度，個人或中小型專案幾乎不用花費。
2. **自備 HTTPS 憑證**：自動簽發正式 SSL 憑證，完全符合 LINE Webhook 與瀏覽器的安全要求。
3. **自動縮放至零 (Scale to Zero)**：沒有人聊天時自動休眠，不浪費運算資源；收到訊息時數秒內自動喚醒。
4. **免安裝 Docker**：使用 Google Cloud Build，雲端直接根據 `Dockerfile` 自動建置並部署。

---

## 🛠️ 部署前準備：取得必備金鑰

請確認您已備妥以下 3 項必要金鑰（可在本機的 `.env` 檔案中找到）：

| 環境變數名稱 | 取得來源 | 範例格式 |
| :--- | :--- | :--- |
| `LINE_CHANNEL_SECRET` | [LINE Developers Console](https://developers.line.biz/) ➔ Basic settings | `7bf997c7...` |
| `LINE_CHANNEL_ACCESS_TOKEN` | [LINE Developers Console](https://developers.line.biz/) ➔ Messaging API ➔ Channel access token | `5Kr2fzS...` |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) ➔ Get API key | `AQ.Ab8RN...` |
| `WEB_API_KEY` *(選用)* | 您自訂的安全密碼（保護網頁 API 與 Google Apps Script） | `my_secret_token_2026` |

---

## 🌐 方法一：最推薦！使用 Google Cloud Shell（免安裝任何軟體）

> **💡 優點**：不用在自己電腦安裝 Docker 或 gcloud，直接在 Google Chrome 瀏覽器內 5 分鐘完成部署！

### 步驟 1：開啟 Google Cloud 主控台
1. 前往 [Google Cloud Console](https://console.cloud.google.com/) 並登入您的 Google 帳號。
2. 點擊頂部專案選單，點選「**新增專案**」（例如專案名稱設為 `my-linebot-web`），並確定該專案已連結帳單帳戶（新用戶有 $300 美元免費試用金）。

### 步驟 2：打開 Cloud Shell 終端機
點擊右上角的「**啟用 Cloud Shell**」按鈕（圖示為 `>_`），網頁底部會彈出專屬的 Linux 雲端終端機。

### 步驟 3：設定專案 ID
在 Cloud Shell 終端機中執行（請替換為您的專案 ID）：
```bash
gcloud config set project YOUR_PROJECT_ID
```

### 步驟 4：啟用必要雲端 API
```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com
```

### 步驟 5：上傳專案程式碼至 Cloud Shell
有以下兩種方式（二擇一）：
- **方式 A (推薦)**：若您的專案已推送到 GitHub：
  ```bash
  git clone https://github.com/411514326-arch/line-bot.git
  cd line-bot
  ```
- **方式 B**：在 Cloud Shell 介面上點擊右上角「**⋮**」➔「**Upload**」，將本專案目錄打包為 zip 上傳後解壓縮：
  ```bash
  unzip line-bot.zip
  cd line-bot
  ```

### 步驟 6：一鍵建置並部署至 Cloud Run
直接在 Cloud Shell 執行以下指令（將金鑰替換為您的真實數值）：
```bash
gcloud run deploy line-bot-web \
    --source . \
    --region asia-east1 \
    --allow-unauthenticated \
    --set-env-vars="LINE_CHANNEL_SECRET=您的Secret,LINE_CHANNEL_ACCESS_TOKEN=您的Token,GEMINI_API_KEY=您的GeminiKey,LLM_BACKEND=gemini,PORT=8080"
```

> **參數說明**：
> - `--source .`：由 Google 雲端自動讀取 `Dockerfile` 並建置容器。
> - `--region asia-east1`：部署至**台灣彰化機房**，連線速度最快、延遲最低！
> - `--allow-unauthenticated`：允許公開存取（LINE Webhook 與網頁瀏覽器必要設定）。

### 步驟 7：取得您的專屬 HTTPS 服務網址
部署完成後，終端機會顯示產生的服務網址：
```text
Service [line-bot-web] has been deployed and is available at:
https://line-bot-web-xxxxxxxx-de.a.run.app
```
請記下這串以 `https://` 開頭的網址！

---

## 💻 方法二：使用本機 gcloud CLI 部署

若您已在電腦中安裝 [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)：

1. 開啟 PowerShell 或命令提示字元，登入 Google 帳號：
   ```powershell
   gcloud auth login
   ```
2. 切換至本專案目錄：
   ```powershell
   cd "c:\Users\LEE68\OneDrive\line bot"
   ```
3. 設定目前專案 ID：
   ```powershell
   gcloud config set project YOUR_PROJECT_ID
   ```
4. 執行部署指令：
   ```powershell
   gcloud run deploy line-bot-web `
       --source . `
       --region asia-east1 `
       --allow-unauthenticated `
       --set-env-vars="LINE_CHANNEL_SECRET=您的Secret,LINE_CHANNEL_ACCESS_TOKEN=您的Token,GEMINI_API_KEY=您的GeminiKey,LLM_BACKEND=gemini,PORT=8080"
   ```

---

## 📱 階段八：更新 LINE Developers Webhook 設定

取得 Cloud Run 網址後，請前往 LINE 官方後台完成雙向連結：

1. 開啟 [LINE Developers Console](https://developers.line.biz/)。
2. 進入您的 **Provider** ➔ 點選您的 **Messaging API 頻道**。
3. 切換至 **Messaging API** 分頁。
4. 找到 **Webhook settings**：
   - 將 **Webhook URL** 填入：
     `https://您的Cloud-Run網址/callback`
     （例如：`https://line-bot-web-xxxxxxxx-de.a.run.app/callback`）
   - 點擊「**Verify**」驗證按鈕 ➔ 必須顯示綠色 **Success**！
   - 將 **Use webhook** 開關切換為 **開啟 (Enabled)**。
5. 在同一分頁下方，將 **Auto-reply messages (自動回應訊息)** 設為 **Disabled (關閉)**，避免 LINE 預設機器人干擾。

---

## 🌐 網頁端與 Google Apps Script 驗證方式

### 1. 瀏覽器網頁直接聊天
在 Google Chrome、Edge 或手機瀏覽器打開：
`https://您的Cloud-Run網址/chat`
- 即刻開啟網頁聊天視窗！
- 測試傳送「你好」、「請問陳文盛老師是誰？」或輸入 `/status`。

### 2. Google Apps Script / Google Sheets 試算表連線
1. 開啟任意 Google Sheets 試算表。
2. 點選「**擴充功能**」➔「**Apps Script**」。
3. 將專案中的 `gas_integration.js` 貼入編輯器中。
4. 將第 9 行的 `BOT_SERVER_URL` 改為您的 Cloud Run 網址：
   ```javascript
   var BOT_SERVER_URL = "https://您的Cloud-Run網址";
   ```
5. 儲存後，在 Google 試算表格子中輸入公式：
   ```text
   =ASK_BOT("陳文盛老師是誰？")
   ```
   按下 Enter，格子內將直接顯示機器人的完整解答！

---

## 🔍 維護與常見問題排除 (Troubleshooting)

### 1. 如何查看 Cloud Run 即時日誌 (Logs)？
- **網頁版**：前往 Google Cloud Console ➔ 搜尋「Cloud Run」➔ 點選 `line-bot-web` ➔ 切換至「**日誌 (LOGS)**」分頁。
- **終端機**：
  ```bash
  gcloud run services logs tail line-bot-web --region asia-east1
  ```

### 2. 如何修改程式並重新部署？
修改本機程式碼後，重新執行相同的 `gcloud run deploy` 指令即可。Cloud Run 會自動執行無中斷滾動更新（Zero-downtime rolling update）。

### 3. 如何回復到上一個正常版本（Rollback）？
若新部署的版本有問題，不用重新打包：
1. 進入 Cloud Run ➔ 點選 `line-bot-web` ➔ 切換至「**修訂版本 (REVISIONS)**」分頁。
2. 選擇之前正常運作的修訂版本 ➔ 點擊「**管理流量**」➔ 將 100% 流量切換回該版本，1 秒內即可完成回復！
