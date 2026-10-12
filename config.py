import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------- LINE Messaging API ----------------
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

# ---------------- AI 模型後端 ----------------
# "gemini"（預設，原有行為）或 "openai"（OpenAI 相容 API，可接開源模型）
LLM_BACKEND = (os.getenv("LLM_BACKEND", "gemini").strip().lower() or "gemini")

# Google Gemini（from Google AI Studio: https://aistudio.google.com/）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODELS",
        "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash",
    ).split(",")
    if m.strip()
]

# OpenAI 相容 API（開源模型後端）
# 可用於：Ollama（本地端）、LM Studio、vLLM、llama.cpp server、OpenRouter、Groq 等
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen2.5:7b").strip()

# ---------------- Webhook 伺服器 ----------------
PORT = int(os.getenv("PORT", "5000"))

# ---------------- 安全白名單 ----------------
allowed_ids_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS = [uid.strip() for uid in allowed_ids_raw.split(",") if uid.strip()]


def is_user_allowed(user_id: str) -> bool:
    """Check if the user is authorized to interact or run commands."""
    if not ALLOWED_USER_IDS:
        return True  # If no restriction is configured, allow all
    return user_id in ALLOWED_USER_IDS


# ---------------- 對話紀錄持久化 ----------------
CHAT_HISTORY_DIR = os.getenv("CHAT_HISTORY_DIR", "chat_history").strip() or "chat_history"

# ---------------- 速率限制 ----------------
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "12"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
