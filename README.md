# Antigravity LINE Bot 🤖⚡

Connect your **LINE** app directly to **Antigravity AI** on your local machine to chat and execute terminal commands on the fly!

---

## ✨ Features

- 💬 **Antigravity & Gemini Chatting**: Natural conversation with AI directly from your LINE messenger. Context history is remembered per user.
- 💻 **Remote Command Execution**: Execute shell commands on your host system with `/cmd <command>` and receive stdout/stderr output in real-time.
- ⚡ **Asynchronous Webhook Processing**: Immediate HTTP 200 acknowledgment to avoid LINE webhook timeouts, with reply token and push fallback.
- 🛡️ **Security Whitelist**: Restrict command execution and access to your specific LINE User ID.
- 🛠️ **Utility Commands**: Check host status (`/status`), list workspace files (`/dir`), view your LINE User ID (`/id`), reset chat memory (`/clear`), and more.

---

## 📋 Prerequisites

- **Python 3.10+** (Tested on Python 3.12)
- A **LINE Developers Account** (free: [https://developers.line.biz/](https://developers.line.biz/))
- A **Google Gemini API Key** (free tier: [https://aistudio.google.com/](https://aistudio.google.com/))
- **ngrok** (or cloudflared) for exposing your local server to LINE Webhooks.

---

## 🚀 Setup & Installation

### Step 1: Install Python Dependencies

Open PowerShell in this directory (`c:\Users\LEE68\OneDrive\line bot`) and install:

```powershell
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Open the `.env` file in this directory and fill in your credentials:

```ini
# LINE Bot Credentials (from LINE Developers Console)
LINE_CHANNEL_SECRET=your_line_channel_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here

# Google Gemini / Antigravity API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Whitelist your LINE user ID to restrict commands (optional, recommended)
ALLOWED_USER_IDS=

# Local Server Port
PORT=5000
```

---

## 📱 LINE Developers Console Setup

1. Go to [LINE Developers Console](https://developers.line.biz/) and log in.
2. Create a **Provider** (or select an existing one).
3. Create a **Messaging API** channel:
   - Fill in Channel Name, Description, and Category.
4. In the **Basic settings** tab:
   - Copy the **Channel secret** and paste it into `LINE_CHANNEL_SECRET` in `.env`.
5. In the **Messaging API** tab:
   - Issue a **Channel access token (long-lived)** and paste it into `LINE_CHANNEL_ACCESS_TOKEN` in `.env`.
   - Set **Webhook URL** to:
     ```
     https://<your-ngrok-domain>.ngrok-free.app/callback
     ```
   - Toggle **Use webhook** to **Enabled**.
   - Under **LINE Official Account features**, click **Auto-reply messages** -> disable "Auto-reply" and enable "Webhooks".
6. Scan the QR code in the Messaging API tab to add your bot as a friend on LINE.

---

## 🌐 Exposing Localhost with ngrok

Because LINE requires a public HTTPS URL for webhooks, run ngrok in a separate terminal:

```powershell
# Install ngrok if not already installed (winget install ngrok or download from ngrok.com)
ngrok http 5000
```

Copy the forwarding HTTPS address (e.g. `https://xxxx-xx-xx.ngrok-free.app`) and append `/callback`, then paste it as the **Webhook URL** in the LINE Developers Console. Click **Verify** to test connection.

---

## 🏃 Starting the Bot

Start the server:

```powershell
python app.py
```

You should see:
```
🚀 Starting Antigravity LINE Bot server on port 5000...
🔗 Health check available at: http://localhost:5000/
🔗 Webhook endpoint: http://localhost:5000/callback
```

---

## 💬 Usage & Command Reference

| Action / Command | Example | Description |
| :--- | :--- | :--- |
| **Normal Chat** | `How do I write an async worker in Python?` | Chats with Antigravity AI. Session memory is preserved. |
| `/cmd <command>` | `/cmd dir` or `/cmd git status` | Runs a shell command on your local PC and returns output. |
| `/status` | `/status` | Displays OS info, Python version, workspace path, and disk space. |
| `/dir` | `/dir` | Lists files in the current workspace directory. |
| `/id` | `/id` | Shows your unique LINE User ID (to put into `ALLOWED_USER_IDS`). |
| `/clear` | `/clear` | Clears conversation context and resets chat memory. |
| `/help` | `/help` | Displays the help menu and commands list. |

---

## 🛡️ Security Best Practice

By default, anyone who adds your bot could theoretically run `/cmd` commands. To prevent unauthorized command execution:
1. Message `/id` to your bot in LINE to get your personal User ID (starts with `U...`).
2. Add your ID to `.env`:
   ```ini
   ALLOWED_USER_IDS=U1234567890abcdef...
   ```
3. Restart `python app.py`. Now only your account can run shell commands!
