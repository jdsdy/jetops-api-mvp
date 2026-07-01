import pytest

from app.core.config import Settings
from app.services.analysis.notam_categorize_agent import (
    HAIKU_CATEGORIZE_TOPICS,
    NO_THINKING_CATEGORIZE_TOPICS,
    get_categorize_agent_config,
)


def _settings(**overrides) -> Settings:
    defaults = {
        "API_KEY": "k",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SECRET_KEY": "s",
        "ANTHROPIC_API_KEY": "a",
        "UPSTASH_REDIS_REST_URL": "https://example.upstash.io",
        "UPSTASH_REDIS_REST_TOKEN": "token",
        "BETA_SIGNUP_CODE": "test-signup-code",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.parametrize(
    "topic",
    sorted(HAIKU_CATEGORIZE_TOPICS),
)
def test_haiku_topics_use_haiku_model_with_thinking_disabled(topic: str) -> None:
    settings = _settings()

    config = get_categorize_agent_config(topic, settings)

    assert config.model == settings.NOTAM_CATEGORIZE_HAIKU_MODEL
    assert config.thinking == {"type": "disabled"}
    assert config.max_tokens == settings.NOTAM_CATEGORIZE_HAIKU_MAX_TOKENS
    assert config.include_effort is False


def test_airspace_organisation_uses_sonnet_with_thinking_disabled() -> None:
    settings = _settings()

    config = get_categorize_agent_config("AIRSPACE_ORGANISATION", settings)

    assert config.model == settings.NOTAM_ANALYSIS_MODEL
    assert config.thinking == {"type": "disabled"}
    assert config.max_tokens == settings.NOTAM_ANALYSIS_MAX_TOKENS
    assert config.include_effort is True


@pytest.mark.parametrize(
    "topic",
    ["RUNWAY", "AIRSPACE", "APPROACH_PROCEDURE", "PROCEDURE_GENERAL", "AERODROME_GENERAL", "MISC"],
)
def test_complex_topics_use_sonnet_with_adaptive_thinking(topic: str) -> None:
    settings = _settings()

    config = get_categorize_agent_config(topic, settings)

    assert config.model == settings.NOTAM_ANALYSIS_MODEL
    assert config.thinking == {"type": "adaptive"}
    assert config.max_tokens == settings.NOTAM_ANALYSIS_MAX_TOKENS
    assert config.include_effort is True


def test_no_thinking_topics_cover_requested_specialists() -> None:
    assert NO_THINKING_CATEGORIZE_TOPICS == {
        "OBSTACLE",
        "NAVAID",
        "LIGHTING",
        "GROUND_MOVEMENT",
        "COMMS",
        "AIRSPACE_ORGANISATION",
    }
