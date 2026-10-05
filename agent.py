import os
import sys
import logging
import subprocess
from typing import Dict, Any, Optional
from config import GEMINI_API_KEY, is_user_allowed

logger = logging.getLogger(__name__)

# Maintain in-memory chat sessions per LINE user_id
_user_chats: Dict[str, Any] = {}

SYSTEM_INSTRUCTION = (
    "You are Antigravity, an intelligent AI assistant and autonomous agent connected directly to "
    "the user's Windows computer and LINE messenger bot.\n"
    "You have access to tools that can directly operate on the user's computer:\n"
    "1. `create_desktop_file`: Create text or code files on the user's Desktop.\n"
    "2. `execute_terminal_command`: Run PowerShell/shell commands on the computer.\n"
    "3. `write_file`: Write or overwrite files at any specified path.\n"
    "4. `read_file`: Read the content of files on the system.\n\n"
    "When the user asks you in natural language to perform an action on their computer (like creating a file, "
    "checking files, running a command), use the appropriate tool to perform the action, and then inform them "
    "clearly and concisely what was done.\n"
    "Format answers cleanly for mobile chat reading in Traditional Chinese or the user's language."
)

# ----------------- Tools for the Agent -----------------

def create_desktop_file(filename: str, content: str) -> str:
    """
    Creates a text or code file on the user's Windows Desktop with the specified content.
    Args:
        filename: The name of the file to create (e.g. 'notes.txt', 'reminder.md').
        content: The text content to write into the file.
    """
    try:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        # Ensure Desktop directory exists
        os.makedirs(desktop_dir, exist_ok=True)
        filepath = os.path.join(desktop_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File successfully created on Desktop: {filepath}"
    except Exception as e:
        return f"Error creating desktop file: {str(e)}"

def write_file(filepath: str, content: str) -> str:
    """
    Writes or overwrites a file with the given content at any specified file path.
    Args:
        filepath: Full or relative path to the file.
        content: The text content to write.
    """
    try:
        # Expand user path like ~
        expanded_path = os.path.expanduser(filepath)
        os.makedirs(os.path.dirname(os.path.abspath(expanded_path)), exist_ok=True)
        with open(expanded_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File saved successfully at {expanded_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def read_file(filepath: str) -> str:
    """
    Reads and returns the contents of a file on the computer.
    Args:
        filepath: The path to the file to read.
    """
    try:
        expanded_path = os.path.expanduser(filepath)
        if not os.path.exists(expanded_path):
            return f"File does not exist: {expanded_path}"
        with open(expanded_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 3000:
            content = content[:3000] + "\n...[truncated]"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

def execute_terminal_command(command: str) -> str:
    """
    Executes a shell or PowerShell command on the computer and returns stdout/stderr.
    Args:
        command: The command line string to run (e.g. 'dir', 'git status', 'python test.py').
    """
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or "") + (("\n[STDERR]\n" + res.stderr) if res.stderr else "")
        if not out.strip():
            out = f"Command finished with exit code {res.returncode}."
        if len(out) > 3000:
            out = out[:3000] + "\n...[truncated]"
        return out
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Execution error: {str(e)}"

ALL_TOOLS = [create_desktop_file, write_file, read_file, execute_terminal_command]

# ----------------- Chat Management -----------------

def clear_session(user_id: str) -> str:
    """Clear conversation history for a specific user."""
    if user_id in _user_chats:
        del _user_chats[user_id]
        return "🧹 對話記憶已清空，隨時可以開始新的話題！"
    return "ℹ️ 目前沒有已存在的對話紀錄。"

def _get_or_create_chat(client: Any, user_id: str, model_name: str) -> Any:
    """Retrieve existing chat or initialize a new chat session with tools."""
    from google.genai import types

    # Only provide tools if user is authorized in whitelist
    user_tools = ALL_TOOLS if is_user_allowed(user_id) else []

    config = types.GenerateContentConfig(
        tools=user_tools,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )
    return client.chats.create(model=model_name, config=config)

_global_client = None

def get_client():
    global _global_client
    if _global_client is None:
        from google import genai
        _global_client = genai.Client(api_key=GEMINI_API_KEY)
    return _global_client

def ask_antigravity(user_id: str, prompt: str) -> str:
    """
    Sends message to Gemini Agent with automatic tool calling and model fallback.
    """
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY is not configured in .env."

    from google.genai.errors import ServerError, ClientError

    client = get_client()
    candidate_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.7-flash"]

    for model_name in candidate_models:
        try:
            # Check or create chat session
            chat = _user_chats.get(user_id)
            if chat is None:
                chat = _get_or_create_chat(client, user_id, model_name)
                _user_chats[user_id] = chat

            response = chat.send_message(prompt)
            reply = (response.text or "").strip()
            if reply:
                return reply
            return "✅ 任務已執行完畢。"

        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning(f"Rate limit 429 on {model_name}: {e}")
                return "⏳ 觸發 Google API 免費版頻率限制（每分鐘 5 次請求），請稍等約 30 秒後再發送！"
            logger.error(f"ClientError with {model_name}: {e}")
            if user_id in _user_chats:
                del _user_chats[user_id]
            return f"❌ 處理訊息時發生錯誤：\n{str(e)}"

        except Exception as e:
            logger.error(f"Error in ask_antigravity with {model_name}: {e}")
            # Reset chat session on error
            if user_id in _user_chats:
                del _user_chats[user_id]
            return f"❌ 處理訊息時發生錯誤：\n{str(e)}"

    return "⚠️ 伺服器目前流量較高，請稍候片刻再試一次。"
