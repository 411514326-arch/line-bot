"""
core/schemas.py — 跨平台統一訊息結構定義

此模組定義 LINE 與網頁端訊息轉換後的統一內部格式。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict


class BotPlatform(str, Enum):
    """訊息來源平台"""
    LINE = "line"
    WEB = "web"
    SYSTEM = "system"


@dataclass
class BotRequest:
    """
    跨平台統一訊息請求結構
    """
    user_id: str                      # LINE 為使用者 ID (例如 Uxxx)；網頁端為 Session UUID
    text: str                         # 使用者輸入的文字訊息
    platform: BotPlatform = BotPlatform.WEB  # 來源平台
    reply_token: Optional[str] = None # LINE 專屬回覆 token (網頁端為 None)
    image_bytes: Optional[bytes] = None  # 圖片位元組陣列 (選填)
    client_ip: Optional[str] = None      # 網頁端客戶端 IP (用於防刷)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BotResponse:
    """
    跨平台統一訊息回應結構
    """
    text: str                         # 主要文字回覆內容
    success: bool = True              # 是否執行成功
    source: str = "ai"                # 回覆來源：ai / kb / command / error / system
    model_name: Optional[str] = None  # 使用的 AI 模型名稱 (例: gemini-3.8-flash)
    truncated: bool = False           # 是否因平台限制而被截斷
