from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://bfs_bot:bfs_bot@localhost:5432/bfs_bot"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "free-tier-model"
    seed_customer_count: int = 200
    session_secret: str = "bfs-bot-local-dev-session-secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

