"""Helper functions for LLM outputs, specifically cleaning code blocks."""

import re

def clean_llm_json_output(content: str) -> str:
    """
    Strips markdown code blocks (```json ... ```) from LLM response 
    to return pure JSON string.
    """
    
    if not content:
        return ""
    
    # Remove ```json ... ``` code blocks
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, content)
    
    if match:
        return match.group(1).strip()
    
    return content.strip()

def estimate_token_count(text: str) -> int:
    """Rough estimation of tokens (1 tokens ~= 4 chars)"""
    return len(text) // 4
    