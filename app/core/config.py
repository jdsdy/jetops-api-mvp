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
    ANTHROPIC_API_KEY: str
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str
    BETA_SIGNUP_CODE: str

    NOTAM_ANALYSIS_MODEL: str = "claude-sonnet-4-6"
    NOTAM_ANALYSIS_MAX_TOKENS: int = 18000
    NOTAM_ANALYSIS_BATCH_SIZE: int = 10
    NOTAM_ANALYSIS_RETRY_BATCH_SIZE: int = 5
    NOTAM_ANALYSIS_MAX_CONCURRENCY: int = 4
    NOTAM_ANALYSIS_INPUT_COST_PER_M: float = 3.0
    NOTAM_ANALYSIS_OUTPUT_COST_PER_M: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
