import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY")
    
    # DB Params
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    
    @property
    def db_connection_params(self):
        return {
            "host": self.POSTGRES_HOST,
            "port": self.POSTGRES_PORT,
            "database": self.POSTGRES_DB,
            "user": self.POSTGRES_USER,
            "password": self.POSTGRES_PASSWORD,
        }
        
settings = Settings()
    
    