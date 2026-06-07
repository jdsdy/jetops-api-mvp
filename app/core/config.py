from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
    )

    API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
