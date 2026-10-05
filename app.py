import os
import sys

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
import threading
from flask import Flask, request, abort, jsonify

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    PORT,
    is_user_allowed
)
from command_handler import handle_command
from agent import ask_antigravity, clear_session

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


def process_user_message(reply_token: str, user_id: str, text: str):
    """
    Process incoming message asynchronously:
    1. Check for system/shell commands
    2. Check for session reset
    3. Forward conversation to Antigravity
    4. Send response back to LINE
    """
    response_text = ""
    clean_text = text.strip()

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
            # Check built-in commands (/cmd, /status, /help, etc.)
            is_cmd, cmd_output = handle_command(user_id, clean_text)
            if is_cmd:
                response_text = cmd_output
            else:
                # Chat with Antigravity / Gemini
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
        "endpoint": "/callback"
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

    # Spawn processing thread so webhook can return HTTP 200 immediately
    worker = threading.Thread(
        target=process_user_message,
        args=(reply_token, user_id, user_text),
        daemon=True
    )
    worker.start()


if __name__ == "__main__":
    print(f"🚀 Starting Antigravity LINE Bot server on port {PORT}...")
    print(f"🔗 Health check available at: http://localhost:{PORT}/")
    print(f"🔗 Webhook endpoint: http://localhost:{PORT}/callback")
    app.run(host="0.0.0.0", port=PORT, debug=False)
