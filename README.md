# Antigravity LINE Bot 🤖⚡

Connect your **LINE** app directly to AI on your local machine to chat and execute terminal commands on the fly!

**v2 升級：新增開源模型後端（Ollama / OpenRouter）、本地知識庫、網頁搜尋、對話紀錄持久化與速率限制。**

---

## ✨ Features

- 🧠 **雙 AI 後端隨時切換**：
  - `gemini` — Google Gemini（預設，保留原有工具呼叫能力）
  - `openai` — **開源模型**：Ollama（本地免費）、LM Studio、vLLM、llama.cpp、OpenRouter、Groq 等
- 💬 **智慧對話**：多輪上下文記憶，對話紀錄持久化到磁碟（伺服器重啟不消失）
- 📚 **本地知識庫**：內建常見問題答案（例如國立東華大學陳文盛教授資料），離線也能答
- 🔍 **網頁搜尋**：`/search` 指令使用 DuckDuckGo，免 API 金鑰
- 💻 **遠端指令執行**：`/cmd <command>` 即時執行並回傳輸出
- 🤖 **自主工具呼叫**：自然語言即可建立桌面檔案、讀寫檔案、執行指令（Function Calling）
- ⚡ **非同步 Webhook**：立即回應 HTTP 200，避免 LINE 逾時
- 🛡️ **安全機制**：白名單控管、危險指令封鎖（rm -rf 等）、訊息速率限制
- 🛠️ **實用指令**：`/status`、`/dir`、`/id`、`/model`、`/kb`、`/history`、`/clear`、`/help`

---

## 📋 Prerequisites

- **Python 3.10+**（已測試 Python 3.12）
- **LINE Developers Account**（免費：https://developers.line.biz/）
- AI 後端擇一：
  - **Google Gemini API Key**（免費額度：https://aistudio.google.com/）
  - **開源模型**（推薦 Ollama：https://ollama.com/ ，安裝後 `ollama pull qwen2.5:7b`）
- **ngrok** 或 **cloudflared**（將本機伺服器暴露給 LINE Webhook）

---

## 🚀 Setup & Installation

### Step 1: Install Python Dependencies

```
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

複製 `.env.example` 為 `.env` 並填入憑證：

```
# LINE Bot Credentials
LINE_CHANNEL_SECRET=your_line_channel_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here

# 預設後端：gemini 或 openai
LLM_BACKEND=gemini
GEMINI_API_KEY=your_gemini_api_key_here

# 開源模型後端（LLM_BACKEND=openai 時需設定）
# Ollama 本地端範例：
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=
OPENAI_MODEL=qwen2.5:7b

# 安全白名單（強烈建議設定）
ALLOWED_USER_IDS=

PORT=5000
```

---

## 🌐 使用開源模型（Ollama）

1. 安裝 Ollama：https://ollama.com/
2. 下載開源模型：
   ```
   ollama pull qwen2.5:7b
   ```
3. 設定 `.env`：
   ```
   LLM_BACKEND=openai
   OPENAI_BASE_URL=http://localhost:11434/v1
   OPENAI_MODEL=qwen2.5:7b
   ```
4. 在 LINE 對話中也可隨時用 `/model openai` 或 `/model gemini` 切換。

其他支援的開源模型服務：LM Studio、vLLM、llama.cpp server、OpenRouter、Groq（皆為 OpenAI 相容 API）。

---

## 📱 LINE Developers Console Setup

1. Go to [LINE Developers Console](https://developers.line.biz/) and log in.
2. Create a **Provider** (or select an existing one).
3. Create a **Messaging API** channel.
4. In **Basic settings**：複製 **Channel secret** 貼到 `.env`。
5. In **Messaging API**：發行 **Channel access token (long-lived)** 貼到 `.env`；Webhook URL 設為 `https://<ngrok-domain>/callback`，開啟 **Use webhook**，並關閉自動回應。
6. 掃描 QR code 將機器人加入好友。

---

## 🏃 Starting the Bot

```
python app.py
```

You should see:

```
🚀 Starting Antigravity LINE Bot server on port 5000...
🧠 AI backend: gemini
🔗 Health check available at: http://localhost:5000/
🔗 Webhook endpoint: http://localhost:5000/callback
```

Expose to internet（LINE 需要公開 HTTPS）：

```
ngrok http 5000
```

---

## 💬 Usage & Command Reference

| Action / Command | Example | Description |
| --- | --- | --- |
| **Normal Chat** | `陳文盛是誰？` | 優先查本地知識庫，否則交給 AI 後端 |
| `/cmd <command>` | `/cmd dir` | 執行終端指令（需白名單） |
| `/model [名稱]` | `/model openai` | 查詢或切換 AI 後端 |
| `/kb <關鍵字>` | `/kb 陳文盛` | 搜尋本地知識庫（離線可用） |
| `/search <關鍵字>` | `/search 國立東華大學 陳文盛` | 搜尋網頁（DuckDuckGo） |
| `/status` | `/status` | 系統與機器人狀態 |
| `/dir` | `/dir` | 列出工作目錄檔案 |
| `/history` | `/history` | 目前對話記錄長度 |
| `/id` | `/id` | 顯示你的 LINE User ID |
| `/clear` | `/clear` | 清空對話記憶 |
| `/help` | `/help` | 指令說明 |

---

## 🛡️ Security Best Practice

1. Message `/id` to your bot to get your User ID（`U...` 開頭）。
2. 將 ID 加入 `.env` 的 `ALLOWED_USER_IDS`。
3. 重啟 `python app.py`，之後只有你的帳號能執行指令。
4. `/cmd` 內建危險指令封鎖（`rm -rf`、`shutdown` 等），雙重保護。

---

## 📂 Project Structure

```
line bot/
├── app.py               # Flask Webhook 伺服器、速率限制、事件處理
├── agent.py             # AI Agent：系統提示詞、工具定義、對話入口
├── llm.py               # 統一 LLM 後端（Gemini + OpenAI 相容開源模型）
├── command_handler.py   # 指令解析與系統工具
├── knowledge_base.py    # 本地知識庫（離線可查）
├── websearch.py         # DuckDuckGo 網頁搜尋
├── config.py            # 環境變數與設定
├── chat_history/        # 對話紀錄持久化（自動建立）
├── index.html           # 專案執行紀錄網頁
└── requirements.txt
```

---

## 🔗 Links

- GitHub: https://github.com/411514326-arch/line-bot
- 執行紀錄網頁: `index.html`
