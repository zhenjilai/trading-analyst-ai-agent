import psycopg2
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class UserHandler:
    def __init__(self):
        self.db_params = settings.db_connection_params
        
    def register_user(self, user_data: dict):
        """Upsert user details on /start"""
        query = """
        INSERT INTO users.users (chat_id, first_name, last_name, username, is_bot, register_date)
        VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
        ON CONFLICT (chat_id) DO UPDATE 
        SET first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            username = EXCLUDED.username;
        """
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (
                        user_data['id'],
                        user_data.get('first_name'),
                        user_data.get('last_name'),
                        user_data.get('username'),
                        user_data.get('is_bot', False)
                    ))
            logger.info(f"Registered user {user_data['id']}")
        except Exception as e:
            logger.error(f"DB Error registering user: {e}")

    def get_all_users(self) -> list[int]:
        """Get list of all chat_ids for broadcasting"""
        query = "SELECT chat_id FROM users.users WHERE is_bot = False;"
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"DB Error fetching users: {e}")
            return []