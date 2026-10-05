import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PORT = int(os.getenv("PORT", "5000"))

# Parse allowed user IDs if provided
allowed_ids_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS = [uid.strip() for uid in allowed_ids_raw.split(",") if uid.strip()]

def is_user_allowed(user_id: str) -> bool:
    """Check if the user is authorized to interact or run commands."""
    if not ALLOWED_USER_IDS:
        return True  # If no restriction is configured, allow all
    return user_id in ALLOWED_USER_IDS
