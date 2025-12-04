import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.llm.openai_client import get_openai_client

def format_analysis_for_telegram(data: Dict[str, Any], title: str) -> str:
    """
    Uses OpenAI (gpt-4o-mini) to format the analysis into Telegram Markdown.
    Replicates the 'Prompt For Output Processing' node from n8n.
    """
    
    llm = get_openai_client(model="o4-mini-2025-04-16")
    json_content = json.dumps(data, indent=2)

    system_prompt = """You are a formatter that converts any given text into **Telegram-optimized Markdown**.
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

    # 4. Invoke the LLM
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json_content)
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"⚠️ Error formatting message with AI: {str(e)}"