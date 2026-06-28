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

    NOTAM_TOPIC_STRONG_SCORE: int = 15
    NOTAM_TOPIC_MODERATE_SCORE: int = 8
    NOTAM_TOPIC_WEAK_SCORE: int = 3
    NOTAM_TOPIC_SCORE_CUTOFF: int = 23

    NOTAM_CATEGORIZE_HAIKU_MODEL: str = "claude-haiku-4-5"
    NOTAM_CATEGORIZE_HAIKU_MAX_TOKENS: int = 8000
    NOTAM_CATEGORIZE_HAIKU_INPUT_COST_PER_M: float = 1.0
    NOTAM_CATEGORIZE_HAIKU_OUTPUT_COST_PER_M: float = 5.0

    NOTAM_SUMMARY_MODEL: str = "claude-haiku-4-5"
    NOTAM_SUMMARY_MAX_TOKENS: int = 8000
    NOTAM_SUMMARY_BATCH_SIZE: int = 20
    NOTAM_SUMMARY_RETRY_BATCH_SIZE: int = 10
    NOTAM_SUMMARY_INPUT_COST_PER_M: float = 1.0
    NOTAM_SUMMARY_OUTPUT_COST_PER_M: float = 5.0
    NOTAM_HEURISTIC_TOPIC_CONFIDENCE_MIN: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
