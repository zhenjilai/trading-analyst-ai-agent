from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

# Add the project root to the Python path so imports work
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import your workflow and utilities
from src.fomc.fomc_workflow import FOMCAnalysisWorkflow
from src.handlers.user_handler import UserHandler
from src.utils.telegram_formatter import TelegramFormatter
from src.utils.telegram_sender import TelegramSender
import requests

class handler(BaseHTTPRequestHandler):
    
    # --- CRON JOB TRIGGER (Runs Daily) ---
    def do_GET(self):
        """
        This endpoint is triggered by Vercel Cron.
        It runs the FOMC Analysis Workflow and sends results to Telegram.
        """
        try:
            print("🕒 Cron Trigger received. Initializing FOMC Workflow...")

            # 1. Initialize the Workflow
            # We pass credentials from Vercel Environment Variables
            workflow = FOMCAnalysisWorkflow(
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                db_connection_params={
                    "url": os.environ.get("SUPABASE_URL"),
                    "key": os.environ.get("SUPABASE_KEY")
                },
                langsmith_api_key=os.environ.get("LANGSMITH_API_KEY")
            )

            # 2. Run the Analysis
            # result structure matches what you defined in 'node_save_results'
            result = workflow.run() 
            
            # 3. Check Outcome & Send Telegram Alerts
            if result.get("status") == "success":
                print("✅ Analysis successful. Preparing Telegram notification...")
                
                # Format the raw JSON into a readable message
                formatter = TelegramFormatter()
                formatted_message = formatter.format_analysis_for_telegram(result.get("data"), 'FOMC Analysis')
                
                # Send to all subscribed users
                # We initialize UserHandler to get the list of users
                user_handler = UserHandler()
                telegram_sender = TelegramSender(token=os.environ.get("TELEGRAM_BOT_TOKEN"))
                
                # Fetch all users (assuming get_all_users or similar exists, otherwise use your specific method)
                # If UserHandler doesn't have a bulk fetch, we might need to adjust this part
                subscribers = user_handler.get_subscribed_users() 
                
                for user_id in subscribers:
                    telegram_sender.send_message(user_id, formatted_message)
                
                self.send_response(200)
                self.wfile.write(f"Success: Sent to {len(subscribers)} users.".encode('utf-8'))
            
            elif result.get("status") == "skipped":
                print("ℹ️ Analysis skipped (No new data).")
                self.send_response(200)
                self.wfile.write(b"Skipped: Database is up to date.")
                
            else:
                print(f"⚠️ Workflow error: {result.get('message')}")
                self.send_response(500)
                self.wfile.write(f"Error: {result.get('message')}".encode('utf-8'))

        except Exception as e:
            print(f"🔥 Critical Error in Webhook: {str(e)}")
            self.send_response(500)
            self.wfile.write(str(e).encode('utf-8'))

    # --- TELEGRAM USER INTERACTION ---
    def do_POST(self):
        """
        Handles incoming messages from Telegram users (e.g., /start)
        """
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data.decode('utf-8'))

            if "message" in update and "text" in update["message"]:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"]["text"]
                user_data = update["message"]["from"]
                
                # Handle /start command
                if text == "/start":
                    user_handler = UserHandler()
                    user_handler.register_user(user_data)
                    self._send_simple_reply(chat_id, "✅ You are registered for Daily FOMC Analysis.")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            
        except Exception as e:
            print(f"Error in do_POST: {e}")
            self.send_response(500)
            self.wfile.write(b"Error")

    def _send_simple_reply(self, chat_id, text):
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text})