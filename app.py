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

from flask import Flask, request, abort, jsonify, render_template, redirect, url_for, send_file

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
    GEMINI_MODELS,
    OPENAI_MODEL,
    PORT,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    is_user_allowed,
    is_api_key_valid
)
from core.schemas import BotRequest, BotResponse, BotPlatform
from core.bot_service import handle_bot_request, analyze_image_bytes
from llm import list_backends, get_history
from agent import clear_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("line_bot")

app = Flask(__name__)

# ---------------- 跨來源資源共享 (CORS) 支援 ----------------
# 確保 Google Apps Script、瀏覽器前端或第三方系統能順暢呼叫 API
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, Accept"
    return response

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
    Process incoming message asynchronously via shared bot core service:
    1. Wrap as BotRequest
    2. Forward to handle_bot_request
    3. Send response back to LINE
    """
    try:
        req = BotRequest(
            user_id=user_id,
            text=text,
            platform=BotPlatform.LINE,
            reply_token=reply_token,
        )
        resp = handle_bot_request(req)
        response_text = resp.text
    except Exception as e:
        logger.exception("Error while processing message in worker:")
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
def index():
    """根目錄：瀏覽器存取時提供網頁聊天介面，API 客戶端存取時回傳健康檢查 JSON。"""
    accept = request.headers.get("Accept", "")
    if "text/html" in accept and "application/json" not in accept:
        return render_template("chat.html")
    return health_check()


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint to test if server is running."""
    configured = bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN)
    return jsonify({
        "status": "online",
        "service": "Antigravity LINE Bot",
        "web_ui": "/chat",
        "line_configured": configured,
        "endpoint": "/callback",
        "ai_backend": LLM_BACKEND,
        "open_source_model": OPENAI_MODEL if LLM_BACKEND == "openai" else None,
        "backends": list_backends()
    })


@app.route("/chat", methods=["GET"])
def web_chat_page():
    """獨立網頁聊天頁面路由。"""
    return render_template("chat.html")


@app.route("/presentation", methods=["GET"])
def presentation_page():
    """工作執行成果簡報投影片頁面。"""
    return send_file("presentation.html")


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    """網頁聊天訊息 API（支援 CORS、Session 隔離與 API Key 防護）。"""
    if request.method == "OPTIONS":
        return "", 200

    data = request.get_json(silent=True) or {}
    api_key = request.headers.get("X-API-Key") or data.get("api_key", "")

    # API 金鑰驗證（若伺服器有設定 WEB_API_KEY）
    if not is_api_key_valid(api_key):
        return jsonify({"success": False, "error": "無效或缺少 API 金鑰 (Invalid or missing API Key)"}), 401

    session_id = str(data.get("session_id", "")).strip()
    message = str(data.get("message", "")).strip()

    # 若為外部客戶端（如自動化腳本）未附帶 session_id，自動給予預設標識
    if not session_id:
        client_ip = request.remote_addr or "client"
        session_id = f"auto_session_{abs(hash(client_ip)) % 100000}"

    if not message:
        return jsonify({"success": False, "error": "訊息內容不可為空白"}), 400

    # 頻率限制檢查
    if not _check_rate_limit(session_id):
        return jsonify({
            "success": False,
            "source": "security",
            "reply": "⏳ 訊息發送太過頻繁，請稍候再試！"
        }), 429

    # 封裝為統一請求並呼叫共用核心服務
    req = BotRequest(
        user_id=session_id,
        text=message,
        platform=BotPlatform.WEB,
        client_ip=request.remote_addr
    )
    resp = handle_bot_request(req)

    return jsonify({
        "success": resp.success,
        "reply": resp.text,
        "source": resp.source,
        "model": resp.model_name
    })


@app.route("/api/gas/chat", methods=["GET", "POST", "OPTIONS"])
def gas_chat():
    """
    專為 Google Apps Script (GAS) 及 Google Sheets / Docs 設計的輕量端點。
    支援 GET (查詢字串 ?message=...) 與 POST (JSON payload: { "message": "..." })。
    回傳超簡潔 JSON 結構，方便 UrlFetchApp 一行解析。
    """
    if request.method == "OPTIONS":
        return "", 200

    if request.method == "GET":
        message = request.args.get("message", "").strip()
        api_key = request.args.get("api_key", "") or request.headers.get("X-API-Key", "")
        session_id = request.args.get("session_id", "gas_default").strip()
    else:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()
        api_key = str(data.get("api_key", "")).strip() or request.headers.get("X-API-Key", "")
        session_id = str(data.get("session_id", "gas_default")).strip()

    # 驗證金鑰
    if not is_api_key_valid(api_key):
        return jsonify({"status": "error", "reply": "❌ API Key 驗證失敗"}), 401

    if not message:
        return jsonify({"status": "error", "reply": "⚠️ 請提供訊息內容 (message)"}), 400

    if not _check_rate_limit(session_id):
        return jsonify({"status": "error", "reply": "⏳ 請求頻率過高，請稍後再試"}), 429

    req = BotRequest(
        user_id=session_id,
        text=message,
        platform=BotPlatform.WEB,
        client_ip=request.remote_addr
    )
    resp = handle_bot_request(req)

    return jsonify({
        "status": "success" if resp.success else "fail",
        "reply": resp.text,
        "source": resp.source,
        "model": resp.model_name
    })


@app.route("/api/history", methods=["GET"])
def api_history():
    """取得特定 Session 的對話歷史。"""
    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        return jsonify({"success": False, "error": "缺少 session_id 參數"}), 400

    history = get_history(session_id)
    return jsonify({"success": True, "history": history})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """清空特定 Session 的對話歷史。"""
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return jsonify({"success": False, "error": "缺少 session_id 參數"}), 400

    msg = clear_session(session_id)
    return jsonify({"success": True, "message": msg})


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
        # 下載圖片 bytes（LINE SDK v3）
        with ApiClient(line_config) as api_client:
            blob_api = MessagingApiBlob(api_client)
            content = blob_api.get_message_content(message_id)  # 回傳 bytes

        reply = analyze_image_bytes(content)
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
