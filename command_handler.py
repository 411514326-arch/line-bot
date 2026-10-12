import subprocess
import os
import sys
import platform
import shutil
from typing import Optional, Tuple
from config import is_user_allowed
from agent import get_model_info, switch_model
from knowledge_base import format_entry, search_kb
from websearch import format_results, web_search
from llm import get_history_length

HELP_MESSAGE = """🤖 Antigravity LINE Bot 指令清單 v2：

💬 對話：
直接輸入任何文字即可與 AI 對話（支援多輪記憶）
問「陳文盛是誰」等問題會先查本地知識庫（離線可用）

🔍 搜尋：
• /kb <關鍵字> - 搜尋本地知識庫
• /search <關鍵字> - 搜尋網頁（DuckDuckGo）

🤖 AI 後端：
• /model - 查詢目前 AI 後端
• /model gemini - 切換到 Google Gemini
• /model openai - 切換到開源模型（需設定 Ollama）

⚡ 系統指令（需白名單權限）：
• /cmd <command> - 執行主機終端指令
• /status - 顯示機器人與系統狀態
• /dir - 列出工作目錄檔案

📊 其他：
• /history - 顯示目前對話記錄長度
• /id - 顯示你的 LINE User ID
• /clear - 清空 AI 對話記憶
• /help - 顯示本說明

⚠️ 速率限制：每分鐘最多 12 則訊息
"""

# 危險指令黑名單：防止誤刪或破壞系統
DANGEROUS_PATTERNS = [
    "rm -rf",
    "mkfs",
    "format c:",
    "del /f /s",
    "shutdown",
    "dd if=",
    ":(){",
]


def _check_dangerous(command: str) -> Optional[str]:
    """檢查指令是否包含危險模式，回傳命中的模式或 None。"""
    lowered = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lowered:
            return pattern
    return None


def execute_shell_command(command: str, cwd: Optional[str] = None) -> str:
    """Executes a shell command safely with timeout and returns output."""
    if not command.strip():
        return "⚠️ Empty command provided."

    # 危險指令防護
    danger = _check_dangerous(command)
    if danger:
        return (
            f"⛔ 為保護你的電腦安全，已封鎖包含「{danger}」的危險指令。\n"
            "如有必要，請直接在本機終端機執行。"
        )

    target_cwd = cwd or os.getcwd()

    try:
        # Run command with 30s timeout
        result = subprocess.run(
            command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        output = result.stdout or ""
        if result.stderr:
            output += ("\n[STDERR]\n" if output else "") + result.stderr

        if not output.strip():
            output = f"✅ Command completed with return code {result.returncode} (No output)."

        # LINE has a 5000 character limit per text message
        if len(output) > 4000:
            output = output[:4000] + "\n... [Output truncated due to LINE message limit]"

        return f"💻 $ {command}\n\n{output}"
    except subprocess.TimeoutExpired:
        return f"⏱️ Command timed out after 30 seconds: `{command}`"
    except Exception as e:
        return f"❌ Command execution error: {str(e)}"

def get_system_status() -> str:
    """Returns runtime and system status information."""
    cwd = os.getcwd()
    py_ver = sys.version.split()[0]
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    disk = shutil.disk_usage(cwd)
    free_gb = disk.free / (1024 ** 3)

    return (
        f"🖥️ System Status:\n"
        f"• OS: {os_info}\n"
        f"• Python: {py_ver}\n"
        f"• Workspace: {cwd}\n"
        f"• Free Disk: {free_gb:.1f} GB\n"
        f"• Bot: Active & Connected"
    )

def list_workspace_files() -> str:
    """Lists files in the current workspace directory."""
    cwd = os.getcwd()
    try:
        items = os.listdir(cwd)
        if not items:
            return f"📂 Directory {cwd} is empty."
        lines = [f"📂 Workspace files ({cwd}):"]
        for item in sorted(items):
            full_path = os.path.join(cwd, item)
            tag = "📁" if os.path.isdir(full_path) else "📄"
            lines.append(f"{tag} {item}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list files: {str(e)}"

def handle_command(user_id: str, text: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if message is a command.
    Returns (is_command, response_text).
    """
    clean_text = text.strip()

    # Check for commands starting with / or !
    if not (clean_text.startswith("/") or clean_text.startswith("!")):
        return False, None

    parts = clean_text[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("help", "h"):
        return True, HELP_MESSAGE

    if cmd == "id":
        return True, f"🆔 Your LINE User ID:\n{user_id}\n\n(Add this to ALLOWED_USER_IDS in .env to restrict access)"

    if cmd == "status":
        return True, get_system_status()

    if cmd in ("dir", "ls"):
        return True, list_workspace_files()

    if cmd == "model":
        if not arg:
            return True, get_model_info(user_id)
        return True, switch_model(user_id, arg)

    if cmd == "kb":
        if not arg:
            return True, "⚠️ 請輸入要查詢的關鍵字。\n範例：/kb 陳文盛"
        results = search_kb(arg)
        if not results:
            return True, f"🔍 知識庫中找不到「{arg}」相關條目，可改用 /search {arg} 搜尋網頁。"
        return True, "\n\n".join(format_entry(e) for e in results)

    if cmd in ("search", "google"):
        if not arg:
            return True, "⚠️ 請輸入要搜尋的關鍵字。\n範例：/search 國立東華大學 陳文盛"
        return True, format_results(arg, web_search(arg))

    if cmd == "history":
        count = get_history_length(user_id)
        return True, f"🗂️ 目前對話記錄：{count} 則訊息"

    if cmd in ("cmd", "run", "exec"):
        # Permission check
        if not is_user_allowed(user_id):
            return True, "⛔ Permission denied: You are not authorized to run commands on this host."

        if not arg:
            return True, "⚠️ Please specify a command to run.\nExample: /cmd dir or /cmd git status"

        return True, execute_shell_command(arg)

    # Unknown command indicator or let Antigravity handle it
    return False, None
