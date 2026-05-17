"""
Application configuration — loaded from .env via pydantic-settings.

All runtime parameters (Ollama endpoint, model names, DB path, SMTP) are
read from environment variables or the .env file in the backend directory.
Defaults are set so the app runs out-of-the-box with a standard local
Ollama installation and SQLite.  Never hardcode secrets — use .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised settings object for the GEMMA backend.

    Loaded once at import time and imported as `settings` throughout the app.
    pydantic-settings automatically reads from .env and validates types.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    GEMMA_MODEL: str = "gemma4:e4b"
    MEDGEMMA_MODEL: str = "medgemma:4b"
    DATABASE_URL: str = "sqlite+aiosqlite:///./gemma.db"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000


settings = Settings()
