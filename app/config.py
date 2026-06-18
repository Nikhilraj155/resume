import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    log_level: str = "INFO"
    port: int = 8000
    max_upload_size_mb: int = 10
    rate_limit_per_minute: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
