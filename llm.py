"""
llm.py — 統一大型語言模型 (LLM) 後端介面

支援兩種後端：
1. gemini — Google Gemini（google-genai SDK，保留原有工具呼叫能力）
2. openai — 任何 OpenAI 相容 API，可接「開源模型」：
   Ollama、LM Studio、vLLM、llama.cpp server、OpenRouter、Groq 等

後端由 config.LLM_BACKEND 決定，使用者也可在 LINE 透過 /model 即時切換。
"""

import json
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional

from config import (
    CHAT_HISTORY_DIR,
    GEMINI_API_KEY,
    GEMINI_MODELS,
    LLM_BACKEND,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6      # 工具呼叫最大輪數，避免無限迴圈
MAX_HISTORY_TURNS = 40   # 每個使用者保留的最大對話輪數


# ================= 對話紀錄管理（記憶體 + 磁碟持久化） =================

_sessions: Dict[str, List[Dict[str, str]]] = {}
_sessions_lock = threading.Lock()


def _history_path(user_id: str) -> Optional[str]:
    try:
        os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in user_id)
        return os.path.join(CHAT_HISTORY_DIR, f"{safe_name}.json")
    except Exception:
        return None


def load_history(user_id: str) -> List[Dict[str, str]]:
    """從磁碟載入對話紀錄（伺服器重啟後仍保留）。"""
    path = _history_path(user_id)
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [
                    m
                    for m in data
                    if isinstance(m, dict) and "role" in m and "content" in m
                ]
        except Exception as e:
            logger.warning(f"無法讀取對話紀錄 {path}: {e}")
    return []


def save_history(user_id: str) -> None:
    path = _history_path(user_id)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(get_history(user_id), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"無法儲存對話紀錄 {path}: {e}")


def get_history(user_id: str) -> List[Dict[str, str]]:
    with _sessions_lock:
        if user_id not in _sessions:
            _sessions[user_id] = load_history(user_id)
        return _sessions[user_id]


def get_history_length(user_id: str) -> int:
    return len(get_history(user_id))


def append_history(user_id: str, role: str, content: str) -> None:
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY_TURNS * 2:
        del history[: len(history) - MAX_HISTORY_TURNS * 2]
    save_history(user_id)


def clear_history(user_id: str) -> bool:
    with _sessions_lock:
        existed = _sessions.pop(user_id, None)
    if existed is not None:
        path = _history_path(user_id)
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    return existed is not None


# ================= 後端實作 =================

class LLMBackend:
    """所有 LLM 後端的基底類別。"""

    name = "base"

    def chat(
        self,
        user_id: str,
        prompt: str,
        system_prompt: str,
        tools: Optional[List[dict]] = None,
        tool_map: Optional[Dict[str, Callable]] = None,
    ) -> str:
        raise NotImplementedError

    def reset_session(self, user_id: str) -> None:
        """清空該使用者的後端會話狀態。"""


class GeminiBackend(LLMBackend):
    """Google Gemini 後端（保留原有工具呼叫與模型容錯能力）。"""

    name = "gemini"

    def __init__(self):
        self._client = None
        self._chats: Dict[str, Any] = {}

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=GEMINI_API_KEY)
        return self._client

    def reset_session(self, user_id: str) -> None:
        self._chats.pop(user_id, None)

    def chat(
        self,
        user_id: str,
        prompt: str,
        system_prompt: str,
        tools: Optional[List[dict]] = None,
        tool_map: Optional[Dict[str, Callable]] = None,
    ) -> str:
        from google.genai import types
        from google.genai import types as gtypes

        client = self._get_client()
        user_tools = tools or []
        last_error: Optional[Exception] = None

        # 將 OpenAI 格式的工具 dict 轉換為 google-genai 的 Tool 格式
        gemini_tools = None
        if user_tools:
            fn_decls = []
            for t in user_tools:
                props = {}
                for prop_name, prop_info in t['parameters'].get('properties', {}).items():
                    props[prop_name] = gtypes.Schema(
                        type=gtypes.Type.STRING,
                        description=prop_info.get('description', '')
                    )
                fn_decls.append(gtypes.FunctionDeclaration(
                    name=t['name'],
                    description=t['description'],
                    parameters=gtypes.Schema(type=gtypes.Type.OBJECT, properties=props)
                ))
            gemini_tools = [gtypes.Tool(function_declarations=fn_decls)]

        # 依序嘗試候選模型，失敗自動切換
        for model_name in GEMINI_MODELS:
            try:
                chat = self._chats.get(user_id)
                if chat is None:
                    config = types.GenerateContentConfig(
                        tools=gemini_tools or [],
                        system_instruction=system_prompt,
                        temperature=0.7,
                    )
                    chat = client.chats.create(model=model_name, config=config)
                    self._chats[user_id] = chat

                # 工具呼叫循環
                current_msg = prompt
                for _round in range(MAX_TOOL_ROUNDS):
                    response = chat.send_message(current_msg)
                    # 檢查是否有工具呼叫
                    fn_call = None
                    if response.candidates:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                fn_call = part.function_call
                                break
                    if fn_call and tool_map:
                        func = tool_map.get(fn_call.name)
                        if func:
                            try:
                                result = str(func(**dict(fn_call.args)))
                            except Exception as e:
                                result = f'工具執行錯誤：{e}'
                        else:
                            result = f'未知工具：{fn_call.name}'
                        # 傳回工具結果給模型
                        current_msg = gtypes.Part(
                            function_response=gtypes.FunctionResponse(
                                name=fn_call.name,
                                response={'result': result}
                            )
                        )
                        continue
                    # 正常文字回覆
                    reply = (response.text or '').strip()
                    append_history(user_id, 'user', prompt)
                    append_history(user_id, 'assistant', reply)
                    return reply or '✅ 任務已執行完畢。'
                return '⚠️ 工具呼叫次數超過上限。'

            except Exception as e:
                last_error = e
                err_text = str(e)
                if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
                    # 頻率限制：交給上層回覆友善提示
                    raise
                logger.warning(f"Gemini 模型 {model_name} 發生錯誤，切換下一個: {e}")
                self._chats.pop(user_id, None)

        assert last_error is not None
        raise last_error


class OpenAICompatibleBackend(LLMBackend):
    """
    OpenAI 相容 API 後端：用於開源模型。

    可接 Ollama（本地端免費）、LM Studio、vLLM、llama.cpp server，
    或 OpenRouter / Groq 等雲端開源模型服務。
    """

    name = "openai"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            if not OPENAI_BASE_URL:
                raise RuntimeError(
                    "尚未設定開源模型後端。請在 .env 設定 LLM_BACKEND=openai 與 "
                    "OPENAI_BASE_URL，例如使用 Ollama：http://localhost:11434/v1"
                )
            self._client = OpenAI(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY or "ollama",
            )
        return self._client

    def chat(
        self,
        user_id: str,
        prompt: str,
        system_prompt: str,
        tools: Optional[List[dict]] = None,
        tool_map: Optional[Dict[str, Callable]] = None,
    ) -> str:
        client = self._get_client()

        messages = [{"role": "system", "content": system_prompt}]
        messages += [dict(m) for m in get_history(user_id)]
        messages.append({"role": "user", "content": prompt})

        openai_tools = None
        if tools:
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        for _round in range(MAX_TOOL_ROUNDS):
            kwargs = {"model": OPENAI_MODEL, "messages": messages}
            if openai_tools:
                kwargs["tools"] = openai_tools

            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as e:
                # 部分開源模型不支援工具呼叫 → 改用純文字模式重試
                if openai_tools and _is_tool_unsupported_error(e):
                    logger.warning(f"模型不支援工具呼叫，切換為純文字模式: {e}")
                    openai_tools = None
                    continue
                raise

            message = response.choices[0].message

            if message.tool_calls:
                messages.append(_assistant_message_with_tools(message))
                for tc in message.tool_calls:
                    result = _execute_tool(tc, tool_map)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(result),
                        }
                    )
                continue

            # 最終文字回覆：存入持久化對話紀錄
            text = (message.content or "").strip()
            append_history(user_id, "user", prompt)
            append_history(user_id, "assistant", text)
            return text or "✅ 任務已執行完畢。"

        return "⚠️ 模型工具呼叫次數超過上限，請精簡你的需求後再試。"


def _is_tool_unsupported_error(e: Exception) -> bool:
    text = str(e).lower()
    if "tool" not in text and "function" not in text:
        return False
    return any(
        k in text
        for k in ("not supported", "unsupported", "does not support", "invalid", "unknown")
    )


def _assistant_message_with_tools(message: Any) -> dict:
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in message.tool_calls
        ],
    }


def _execute_tool(tc: Any, tool_map: Optional[Dict[str, Callable]]) -> str:
    name = tc.function.name
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    func = (tool_map or {}).get(name)
    if func is None:
        return f"未知工具：{name}"
    try:
        if isinstance(args, dict):
            return str(func(**args))
        return str(func(args))
    except Exception as e:
        return f"工具執行錯誤：{e}"


# ================= 後端管理 =================

_backends: Dict[str, LLMBackend] = {}
_user_backend: Dict[str, str] = {}
_default_backend = LLM_BACKEND if LLM_BACKEND in ("gemini", "openai") else "gemini"


def _create_backend(name: str) -> LLMBackend:
    if name == "openai":
        return OpenAICompatibleBackend()
    return GeminiBackend()


def get_backend(user_id: Optional[str] = None) -> LLMBackend:
    """取得使用者目前使用的後端（依個人偏好或全域預設）。"""
    name = _user_backend.get(user_id, _default_backend) if user_id else _default_backend
    if name not in _backends:
        _backends[name] = _create_backend(name)
    return _backends[name]


def get_backend_name(user_id: Optional[str] = None) -> str:
    if user_id:
        return _user_backend.get(user_id, _default_backend)
    return _default_backend


def set_user_backend(user_id: str, name: str) -> bool:
    """切換使用者的 AI 後端（gemini / openai）。"""
    if name not in ("gemini", "openai"):
        return False
    _user_backend[user_id] = name
    return True


def list_backends() -> List[Dict[str, Any]]:
    """列出所有後端及其設定狀態（供 /model 與健康檢查使用）。"""
    return [
        {
            "name": "gemini",
            "models": GEMINI_MODELS,
            "configured": bool(GEMINI_API_KEY),
        },
        {
            "name": "openai",
            "model": OPENAI_MODEL,
            "base_url": OPENAI_BASE_URL,
            "configured": bool(OPENAI_BASE_URL),
        },
    ]


def reset_user(user_id: str) -> bool:
    """清空使用者的對話紀錄與所有後端會話狀態。"""
    cleared = clear_history(user_id)
    for backend in _backends.values():
        backend.reset_session(user_id)
    _user_backend.pop(user_id, None)
    return cleared
