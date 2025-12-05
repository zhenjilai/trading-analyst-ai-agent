from langchain_anthropic import ChatAnthropic
from config.settings import settings

def get_claude_client(model="claude-4-sonnet-20250514"):
    """
    Initialize and return a Claude client using LangChain's ChatAnthropic.

    Args:
        model (str): The Claude model to use. Defaults to "claude-4-sonnet-20250514".

    Returns:
        ChatAnthropic: An instance of the ChatAnthropic client.
    """
    return ChatAnthropic(
        model=model,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=64000,
        temperature=1, 
        thinking={
            "type": "enabled",
            "budget_tokens": 20000
        }
    )