import subprocess
import os
import sys
import platform
import shutil
from typing import Optional, Tuple
from config import is_user_allowed

HELP_MESSAGE = """🤖 Antigravity LINE Bot Commands:

💬 Chatting:
Just type any message normally to chat with Antigravity AI!

⚡ Commands:
• /cmd <command> - Execute a shell command on host machine
• /status - Show bot & system status
• /id - Show your LINE User ID (for security whitelist)
• /clear - Clear your AI chat history
• /dir - List current workspace files
• /help - Display this command guide
"""

def execute_shell_command(command: str, cwd: Optional[str] = None) -> str:
    """Executes a shell command safely with timeout and returns output."""
    if not command.strip():
        return "⚠️ Empty command provided."
    
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
    
    if cmd in ("cmd", "run", "exec"):
        # Permission check
        if not is_user_allowed(user_id):
            return True, "⛔ Permission denied: You are not authorized to run commands on this host."
        
        if not arg:
            return True, "⚠️ Please specify a command to run.\nExample: /cmd dir or /cmd git status"
        
        return True, execute_shell_command(arg)
    
    # Unknown command indicator or let Antigravity handle it
    return False, None
