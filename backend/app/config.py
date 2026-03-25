from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    redis_url: str = "redis://localhost:6379/0"
    model_store_path: str = "./ml_models"
    environment: str = "development"
    frontend_url: Optional[str] = None  # e.g. https://wasteiq.vercel.app

    class Config:
        env_file = ".env"


settings = Settings()
