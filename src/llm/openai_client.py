# src/llm/openai_client.py
from langchain_openai import ChatOpenAI
from config.settings import settings

def get_openai_client(model="gpt-4o-mini"):
    """
    Returns a configured ChatOpenAI instance.
    Matches the n8n workflow's preference for OpenAI.
    """
    return ChatOpenAI(
        model=model,
        api_key=settings.OPENAI_API_KEY,
        max_tokens=100000,
        temperature=1, 
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    )