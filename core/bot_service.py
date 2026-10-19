"""
core/bot_service.py — 跨平台共用 Bot 核心業務邏輯

整合：
1. 權限與白名單驗證
2. 系統指令處理 (command_handler)
3. 本地知識庫查詢 (knowledge_base，離線優先)
4. AI 模型對話 (agent / llm)
5. 雲端環境安全隔離
6. 圖片多模態辨識分析
"""

import os
import logging
from typing import Tuple, Optional
from core.schemas import BotRequest, BotResponse, BotPlatform
from config import (
    is_user_allowed,
    GEMINI_API_KEY,
    GEMINI_MODELS,
    LLM_BACKEND,
)
from agent import ask_antigravity, clear_session, get_model_info
from command_handler import handle_command
from knowledge_base import search_kb, format_entry
from llm import get_backend_name

logger = logging.getLogger("bot_service")

# 判斷是否運行於 Google Cloud Run 或雲端容器環境
RUNNING_ON_CLOUD = bool(
    os.getenv("K_SERVICE")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("RUNNING_ON_CLOUD", "").lower() in ("true", "1", "yes")
)


def handle_bot_request(req: BotRequest) -> BotResponse:
    """
    處理使用者訊息的核心調度函式（LINE Webhook 與網頁 API 皆調用此處）。
    """
    clean_text = (req.text or "").strip()
    user_id = req.user_id

    # 1. 空白訊息檢查
    if not clean_text:
        return BotResponse(
            text="⚠️ 收到空白訊息，請輸入內容後再試。",
            success=False,
            source="system",
        )

    # 2. LINE 專屬白名單權限檢查（若有配置 ALLOWED_USER_IDS）
    if req.platform == BotPlatform.LINE and not is_user_allowed(user_id):
        return BotResponse(
            text=(
                "⛔ Access restricted: Your LINE account is not whitelisted.\n"
                f"Your User ID is: {user_id}\n"
                "Please add this ID to ALLOWED_USER_IDS in the server's .env file."
            ),
            success=False,
            source="permission",
        )

    # 3. 清理對話記憶指令 (/clear, /reset)
    if clean_text.lower() in ("/clear", "!clear", "/reset", "!reset"):
        result_text = clear_session(user_id)
        return BotResponse(
            text=result_text,
            success=True,
            source="command",
        )

    # 4. 系統指令處理 (/cmd, /status, /model, /kb, /search, /help...)
    # 雲端安全防護：若在 Cloud Run 容器環境下嘗試執行 /cmd
    if RUNNING_ON_CLOUD and clean_text.lower().startswith(("/cmd", "!cmd", "/exec", "!exec")):
        return BotResponse(
            text=(
                "🛡️ 安全提示：系統目前運行於 Google Cloud Run 雲端容器環境。\n"
                "為確保雲端伺服器與主機安全，終端機指令（/cmd）僅限在本機電腦執行時啟用。"
            ),
            success=False,
            source="security",
        )

    is_cmd, cmd_output = handle_command(user_id, clean_text)
    if is_cmd:
        return BotResponse(
            text=cmd_output or "",
            success=True,
            source="command",
        )

    # 5. 本地知識庫查詢（離線優先、零延遲、高準確率，例如「陳文盛是誰」）
    kb_hits = search_kb(clean_text)
    if kb_hits and kb_hits[0]["score"] >= 3:
        kb_text = format_entry(kb_hits[0])
        return BotResponse(
            text=kb_text,
            success=True,
            source="kb",
        )

    # 6. AI 智慧對話（Gemini 或 OpenAI / Ollama 開源模型）
    try:
        current_backend = get_backend_name(user_id)
        ai_reply = ask_antigravity(user_id, clean_text)
        return BotResponse(
            text=ai_reply,
            success=True,
            source="ai",
            model_name=current_backend,
        )
    except Exception as e:
        logger.exception(f"AI 回覆過程發生例外錯誤 (user_id: {user_id}): {e}")
        return BotResponse(
            text=f"⚠️ 處理訊息時發生錯誤：\n{str(e)}",
            success=False,
            source="error",
        )


def analyze_image_bytes(image_bytes: bytes, prompt: str = "請用繁體中文描述這張圖片的內容。") -> str:
    """
    通用圖片分析函式：使用 Google Gemini Vision 進行圖片解讀。
    LINE 圖片訊息與網頁上傳圖片皆可共用此函式。
    """
    if not GEMINI_API_KEY:
        return "⚠️ 未設定 GEMINI_API_KEY，無法啟用圖片分析功能。"

    try:
        from google import genai
        from google.genai import types as gtypes

        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = GEMINI_MODELS[0] if GEMINI_MODELS else "gemini-3.8-flash"

        response = gemini_client.models.generate_content(
            model=model_name,
            contents=[
                gtypes.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",
                ),
                prompt,
            ],
        )
        return (response.text or "無法分析圖片內容。").strip()
    except Exception as e:
        logger.warning(f"圖片分析失敗: {e}")
        return f"🖼️ 圖片分析失敗，錯誤原因：{str(e)}"
