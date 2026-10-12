import os
import sys
import time
import threading
from collections import defaultdict, deque

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging

from flask import Flask, request, abort, jsonify

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    StickerMessageContent,
    ImageMessageContent,
)

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    LLM_BACKEND,
    GEMINI_API_KEY,
    OPENAI_MODEL,
    PORT,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    is_user_allowed
)
from command_handler import handle_command
from agent import ask_antigravity, clear_session
from knowledge_base import format_entry, search_kb
from llm import list_backends

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("line_bot")

app = Flask(__name__)

# Validate credentials
if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
    logger.warning("⚠️ LINE_CHANNEL_SECRET or LINE_CHANNEL_ACCESS_TOKEN is missing in .env!")

handler = WebhookHandler(LINE_CHANNEL_SECRET or "dummy_secret")
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN or "dummy_token")

# ---------------- 速率限制 ----------------
_rate_limit_window: dict = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _check_rate_limit(user_id: str) -> bool:
    """簡易滑動視窗速率限制，避免濫用與 API 配額耗盡。"""
    now = time.time()
    with _rate_limit_lock:
        queue = _rate_limit_window[user_id]
        while queue and queue[0] <= now - RATE_LIMIT_WINDOW:
            queue.popleft()
        if len(queue) >= RATE_LIMIT_REQUESTS:
            return False
        queue.append(now)
        return True


def process_user_message(reply_token: str, user_id: str, text: str):
    """
    Process incoming message asynchronously:
    1. Check for system/shell commands
    2. Check for session reset
    3. Check local knowledge base (offline-first)
    4. Forward conversation to the configured LLM backend
    5. Send response back to LINE
    """
    response_text = ""
    clean_text = text.strip()

    if not clean_text:
        send_line_message(reply_token, user_id, "⚠️ 收到空白訊息，請輸入內容後再試。")
        return

    try:
        # Check authorization
        if not is_user_allowed(user_id):
            response_text = (
                "⛔ Access restricted: Your LINE account is not whitelisted.\n"
                f"Your User ID is: {user_id}\n"
                "Please add this ID to ALLOWED_USER_IDS in the server's .env file."
            )
        elif clean_text.lower() in ("/clear", "!clear", "/reset", "!reset"):
            response_text = clear_session(user_id)
        else:
            # Check built-in commands (/cmd, /status, /model, /kb, /search...)
            is_cmd, cmd_output = handle_command(user_id, clean_text)
            if is_cmd:
                response_text = cmd_output
            else:
                # 先查本地知識庫：離線、快速、答案準確（例如「陳文盛是誰」）
                kb_hits = search_kb(clean_text)
                if kb_hits and kb_hits[0]["score"] >= 3:
                    response_text = format_entry(kb_hits[0])
                else:
                    # Chat with the configured LLM backend (Gemini 或開源模型)
                    response_text = ask_antigravity(user_id, clean_text)

    except Exception as e:
        logger.exception("Error while processing message:")
        response_text = f"⚠️ An error occurred while processing your message:\n{str(e)}"

    # Send response back to LINE
    send_line_message(reply_token, user_id, response_text)


def send_line_message(reply_token: str, user_id: str, text: str):
    """Send message via reply token, falling back to push message if reply token expired."""
    # Ensure text is not empty and within LINE's 5000 character limit
    if not text:
        text = "(No response generated)"
    if len(text) > 4900:
        text = text[:4900] + "\n...[truncated]"

    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
            logger.info(f"Replied to user {user_id} successfully.")
        except Exception as e:
            logger.warning(f"Reply failed ({e}), falling back to push_message...")
            try:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=text)]
                    )
                )
                logger.info(f"Pushed message to user {user_id} successfully.")
            except Exception as push_err:
                logger.error(f"Failed to push message: {push_err}")


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint to test if server is running."""
    configured = bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN)
    return jsonify({
        "status": "online",
        "service": "Antigravity LINE Bot",
        "line_configured": configured,
        "endpoint": "/callback",
        "ai_backend": LLM_BACKEND,
        "open_source_model": OPENAI_MODEL if LLM_BACKEND == "openai" else None,
        "backends": list_backends()
    })


@app.route("/callback", methods=["POST"])
def callback():
    """LINE webhook callback endpoint."""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid LINE webhook signature received.")
        abort(400)
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        abort(500)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    """Handle incoming text messages from LINE."""
    user_id = event.source.user_id
    user_text = event.message.text
    reply_token = event.reply_token

    logger.info(f"Received message from {user_id}: {user_text[:50]}...")

    # 速率限制檢查
    if not _check_rate_limit(user_id):
        logger.warning(f"Rate limit exceeded for user {user_id}")
        send_line_message(reply_token, user_id, "⏳ 訊息太頻繁了，請稍等一下再發送！")
        return

    # Spawn processing thread so webhook can return HTTP 200 immediately
    worker = threading.Thread(
        target=process_user_message,
        args=(reply_token, user_id, user_text),
        daemon=True
    )
    worker.start()


@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker_message(event: MessageEvent):
    """Handle sticker messages: politely inform that only text is supported."""
    user_id = event.source.user_id
    logger.info(f"Received sticker from {user_id}")
    send_line_message(
        event.reply_token,
        user_id,
        "⚠️ 目前只支援文字訊息哦，請用文字跟我說話：)"
    )


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event: MessageEvent):
    """Handle image messages: download and analyse with Gemini vision."""
    user_id = event.source.user_id
    message_id = event.message.id
    logger.info(f"Received image from {user_id}, message_id={message_id}")

    try:
        import base64
        from google import genai
        from google.genai import types as gtypes

        # 下載圖片 bytes（LINE SDK v3）
        with ApiClient(line_config) as api_client:
            blob_api = MessagingApiBlob(api_client)
            content = blob_api.get_message_content(message_id)  # 回傳 bytes
            img_b64 = base64.b64encode(content).decode("utf-8")

        # 使用 Gemini 分析圖片
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                gtypes.Part.from_bytes(
                    data=base64.b64decode(img_b64),
                    mime_type="image/jpeg"
                ),
                "請用繁體中文描述這張圖片的內容。",
            ],
        )
        reply = (response.text or "無法分析圖片。").strip()
    except Exception as e:
        logger.warning(f"圖片分析失敗: {e}")
        reply = "🖼️ 圖片已收到！AI 正在分析中，但目前無法取得結果，請稍後再試。"

    send_line_message(event.reply_token, user_id, reply)


if __name__ == "__main__":
    print(f"🚀 Starting Antigravity LINE Bot server on port {PORT}...")
    print(f"🧠 AI backend: {LLM_BACKEND}")
    print(f"🔗 Health check available at: http://localhost:{PORT}/")
    print(f"🔗 Webhook endpoint: http://localhost:{PORT}/callback")
    app.run(host="0.0.0.0", port=PORT, debug=False)
