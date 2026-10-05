import asyncio
import logging
from typing import Dict, List, Optional
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Maintain in-memory chat session history per LINE user_id
# Structure: {user_id: [{"role": "user"|"model", "content": "..."}]}
_user_sessions: Dict[str, List[Dict[str, str]]] = {}

SYSTEM_INSTRUCTION = (
    "You are Antigravity, an intelligent AI assistant connected directly to the user's "
    "development environment and LINE messaging bot. You can help with programming, "
    "debugging, brainstorming, system commands, and general questions. "
    "Keep answers concise, helpful, and properly formatted for mobile chat."
)

def clear_session(user_id: str) -> str:
    """Clear conversation history for a specific user."""
    if user_id in _user_sessions:
        _user_sessions[user_id] = []
        return "🧹 Your chat history has been reset."
    return "ℹ️ No existing chat history to clear."

async def _chat_with_antigravity_sdk(prompt: str) -> Optional[str]:
    """Attempt chat using google-antigravity SDK."""
    try:
        from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
        config = LocalAgentConfig(
            system_instructions=SYSTEM_INSTRUCTION,
            capabilities=CapabilitiesConfig()
        )
        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            tokens = []
            async for token in response:
                tokens.append(token)
            full_response = "".join(tokens).strip()
            if full_response:
                return full_response
    except Exception as e:
        logger.debug(f"Antigravity SDK chat fallback: {e}")
    return None

def _chat_with_gemini(user_id: str, prompt: str) -> str:
    """Chat using google-genai or google-generativeai."""
    api_key = GEMINI_API_KEY
    if not api_key:
        return (
            "⚠️ GEMINI_API_KEY is not configured in .env.\n"
            "Please obtain an API key from https://aistudio.google.com/ and add it to your .env file."
        )

    # Maintain history
    history = _user_sessions.setdefault(user_id, [])
    
    try:
        # Try google.genai (the modern SDK)
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        
        # Build contents with history (keep last 10 messages)
        recent_history = history[-10:]
        contents = []
        for msg in recent_history:
            contents.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )
        )
        
        reply = response.text or "I processed your request, but received an empty response."
        
        # Save to history
        history.append({"role": "user", "content": prompt})
        history.append({"role": "model", "content": reply})
        if len(history) > 20:
            _user_sessions[user_id] = history[-20:]
            
        return reply

    except Exception as e:
        # Fallback to older google.generativeai if available
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SYSTEM_INSTRUCTION
            )
            chat = model.start_chat(history=[])
            response = chat.send_message(prompt)
            return response.text
        except Exception as inner_e:
            return f"❌ AI Generation Error:\n{str(e)}"

def ask_antigravity(user_id: str, prompt: str) -> str:
    """Synchronous interface to ask Antigravity / Gemini."""
    # Attempt SDK first if event loop allows, else Gemini API
    try:
        sdk_result = asyncio.run(_chat_with_antigravity_sdk(prompt))
        if sdk_result:
            return sdk_result
    except Exception:
        pass
    
    return _chat_with_gemini(user_id, prompt)
