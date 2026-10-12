"""
agent.py — AI Agent：系統提示詞、工具定義與對話入口

對話由 llm.py 的統一後端處理（gemini 或 openai 開源模型）。
"""

import logging
import os
import subprocess
from typing import Dict

from config import GEMINI_API_KEY, OPENAI_BASE_URL, is_user_allowed
from llm import (
    get_backend,
    get_backend_name,
    list_backends,
    reset_user,
    set_user_backend,
)

logger = logging.getLogger(__name__)

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
        content: The text content to write into the file.
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

# ----------------- Tool specs for OpenAI function calling -----------------

TOOL_SPECS = [
    {
        "name": "create_desktop_file",
        "description": "在使用者 Windows 桌面建立文字或程式檔案",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "檔案名稱，例如 note.txt"},
                "content": {"type": "string", "description": "要寫入的內容"},
            },
            "required": ["filename", "content"],
        },
        "handler": create_desktop_file,
    },
    {
        "name": "write_file",
        "description": "在指定路徑寫入或覆寫檔案",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "完整或相對路徑"},
                "content": {"type": "string", "description": "要寫入的內容"},
            },
            "required": ["filepath", "content"],
        },
        "handler": write_file,
    },
    {
        "name": "read_file",
        "description": "讀取電腦上指定檔案的內容",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "要讀取的檔案路徑"},
            },
            "required": ["filepath"],
        },
        "handler": read_file,
    },
    {
        "name": "execute_terminal_command",
        "description": "在電腦執行終端機指令並回傳輸出結果",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要執行的指令字串"},
            },
            "required": ["command"],
        },
        "handler": execute_terminal_command,
    },
]

# ----------------- Chat Management -----------------

def clear_session(user_id: str) -> str:
    """Clear conversation history for a specific user."""
    if reset_user(user_id):
        return "🧹 對話記憶已清空，隨時可以開始新的話題！"
    return "ℹ️ 目前沒有已存在的對話紀錄。"


def get_model_info(user_id: str) -> str:
    """回傳目前使用中的 AI 後端與可用後端清單。"""
    current = get_backend_name(user_id)
    lines = [f"🤖 目前 AI 後端：{current}", ""]
    for b in list_backends():
        status = "✅ 已設定" if b["configured"] else "⚠️ 尚未設定"
        detail = b.get("model") or ", ".join(b.get("models", []))
        lines.append(f"• {b['name']}：{detail}（{status}）")
    lines.append("")
    lines.append("切換方式：/model gemini 或 /model openai")
    return "\n".join(lines)


def switch_model(user_id: str, name: str) -> str:
    """切換使用者的 AI 後端。"""
    if set_user_backend(user_id, name.lower()):
        return f"✅ 已將 AI 後端切換為：{name.lower()}"
    return "⚠️ 未知的模型後端。目前支援：gemini、openai"


def ask_antigravity(user_id: str, prompt: str) -> str:
    """
    Sends message to the configured LLM backend with automatic tool calling
    and model fallback.
    """
    backend_name = get_backend_name(user_id)

    if backend_name == "gemini" and not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY is not configured in .env."
    if backend_name == "openai" and not OPENAI_BASE_URL:
        return (
            "⚠️ 尚未設定開源模型後端。請在 .env 設定 LLM_BACKEND=openai 與 "
            "OPENAI_BASE_URL，例如使用 Ollama：http://localhost:11434/v1"
        )

    backend = get_backend(user_id)

    # Only provide tools if user is authorized in whitelist
    tools = TOOL_SPECS if is_user_allowed(user_id) else []
    tool_map = {t["name"]: t["handler"] for t in tools}

    try:
        return backend.chat(user_id, prompt, SYSTEM_INSTRUCTION, tools, tool_map)

    except Exception as e:
        logger.exception("Error in ask_antigravity:")
        err_text = str(e)
        if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
            return "⏳ 觸發 API 免費版頻率限制（每分鐘 5 次請求），請稍等約 30 秒後再發送！"
        # 對話狀態可能已損壞，重置後讓使用者重試
        reset_user(user_id)
        return f"❌ 處理訊息時發生錯誤：\n{err_text}"
