import sys
from src.utils.logger import setup_logging
from config.settings import settings
from src.fomc.fomc_workflow import FOMCAnalysisWorkflow
from src.fomc.fomc_database import create_database_schema
from src.handlers.user_handler import UserHandler
from src.utils.telegram_sender import TelegramSender
from src.utils.telegram_formatter import format_analysis_for_telegram

# Setup Logging
logger = setup_logging()

def main():
    logger.info("Starting FOMC Analysis Job...")
    
    # 1. Database Setup
    create_database_schema(settings.db_connection_params)
    
    # 2. Run Workflow
    workflow = FOMCAnalysisWorkflow()
    
    # Check for force date argument
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    try:
        result = workflow.run(force_date=target_date)
        
        if result.get("status") == "success" and result.get("data"):
            logger.info("Analysis success. Formatting for Telegram...")
        
            # 1. Get Data
            analysis_data = result['data']
            
            # 2. Format with Specific Title
            # You can now change this string for other analysis types!
            markdown_report = format_analysis_for_telegram(
                data=analysis_data, 
                title="🇺🇸 FOMC Meeting Analysis"
            )
            
            # 4. Fetch Users
            user_handler = UserHandler()
            chat_ids = user_handler.get_all_users()
            
            # 5. Broadcast
            if chat_ids:
                sender = TelegramSender()
                sender.send_message(chat_ids, markdown_report)
                logger.info(f"Broadcast complete to {len(chat_ids)} users.")
            else:
                logger.warning("No users found to broadcast to.")
                
        else:
            logger.info(f"Job finished without analysis: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"Critical Job Failure: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()