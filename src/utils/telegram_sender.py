import requests
import time
from typing import List
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    def send_analysis(self, chat_ids: List[int], title: str, content: str):
        """
        Send analysis to a list of users.
        Splits content into chunks to fit Telegram limits
        """
        formatted_message = f"*{title}*\n\n{content}"
        chunks = self._split_message(formatted_message)
        
        for chat_id in chat_ids:
            try:
                for i, chunk in enumerate(chunks):
                    # Add pagination context if multiple parts
                    if len(chunks) > 1:
                        final_chunk = f"{chunk}\n\n_(Part {i+1}/{len(chunks)})_"
                    else:
                        final_chunk = chunk
                    self._send_message(chat_id, final_chunk)
                    # time.sleep(0.5) # Prevent rate limiting
                logger.info(f"Sent analysis to chat_id {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send analysis to chat_id {chat_id}: {e}")
                
    def _split_message(self, text: str, limit=4000) -> List[str]:
        """Splits text into 4096-char chunks respecting markdown."""
        if len(text) <= limit:
            return [text]
        return [text[i:i+limit] for i in range(0, len(text), limit)]

    def _send_message(self, chat_id: int, text: str):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(f"{self.base_url}/sendMessage", json=payload)
        response.raise_for_status()