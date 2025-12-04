from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.handlers.user_handler import UserHandler
from config.settings import settings
import requests

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data.decode('utf-8'))

        # Check if it's a message and contains text
        if "message" in update and "text" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"]
            
            # Handle /start command
            if text == "/start":
                user_data = update["message"]["from"]
                
                # Use your existing UserHandler logic
                user_handler = UserHandler()
                user_handler.register_user(user_data)
                
                # Send confirmation back to Telegram
                self._send_telegram_message(chat_id, "✅ You are registered for Daily FOMC Analysis.")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def _send_telegram_message(self, chat_id, text):
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text})