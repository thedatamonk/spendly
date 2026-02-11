from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    telegram_bot_token: str = ""
    db_path: str = "memory_ledger.json"
    llm_model: str = "google/gemini-2.0-flash-exp"


@lru_cache
def get_settings() -> Settings:
    return Settings()
