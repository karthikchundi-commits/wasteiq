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
    frontend_url: Optional[str] = None

    # Oracle Fusion integration (optional — leave blank to disable)
    oracle_host: Optional[str] = None        # e.g. your-instance.oraclecloud.com
    oracle_client_id: Optional[str] = None
    oracle_client_secret: Optional[str] = None
    oracle_token_url: Optional[str] = None   # OAuth2 token endpoint
    oracle_bu_id: Optional[str] = None       # Business Unit ID for PO creation

    class Config:
        env_file = ".env"


settings = Settings()
