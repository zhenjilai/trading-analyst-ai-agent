import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.llm.openai_client import get_openai_client

def format_analysis_for_telegram(data: Dict[str, Any], title: str) -> str:
    """
    Formats analysis JSON into Telegram Markdown using OpenAI.
    Args:
        data: The dictionary containing the analysis.
        title: The dynamic title (e.g., "🇺🇸 FOMC Analysis").
    """
    try:
        llm = get_openai_client(model="o4-mini-2025-04-16")
        
        # 2. Serialize data safely
        if hasattr(data, 'model_dump'):
             content_str = json.dumps(data.model_dump(), indent=2, default=str)
        else:
             content_str = json.dumps(data, indent=2, default=str)

        system_prompt = f"""You are a formatter that converts any given text into **Telegram-optimized Markdown**.
Your output must be easy to read on mobile and should be encoded in Utf-8:

1. **Headings & Structure**
- Use `#`, `##` for main sections.

2. **Line Length & Spacing**
- Separate paragraphs with a blank line.

3. **Lists & Emphasis**
- Turn lists into `-` or `•` bullets.
- Use **bold** for key terms, _italic_ for emphasis.

4. **Links & Emojis**
- Use inline links: `[label](URL)`.
- Sprinkle in simple emojis (✅, 🔹, ⚠️) to highlight.
You should retain the key and value exactly the same. The title should be {title}."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=content_str)
        ]
        
        response = llm.invoke(messages)
        return response.content

    except Exception as e:
        return f"⚠️ **Error Formatting Analysis**\n{str(e)}"