import pytest

from app.core.config import Settings
from app.schemas.notam_analysis import AnalysisNotamRow
from app.services.analysis.notam_heuristic_category import (
    HEURISTIC_CATEGORY_3_TOPICS,
    heuristic_category,
    is_heuristic_category_candidate,
)


def _row(*, topic: str | None = None, topic_confidence: int | None = None) -> AnalysisNotamRow:
    return AnalysisNotamRow(
        id=1,
        notam_id="C0481/26 NOTAMN",
        topic=topic,
        topic_confidence=topic_confidence,
    )


@pytest.mark.parametrize("topic", sorted(HEURISTIC_CATEGORY_3_TOPICS))
def test_is_heuristic_category_candidate_accepts_allowed_topics(topic: str) -> None:
    assert is_heuristic_category_candidate(_row(topic=topic, topic_confidence=41)) is True


def test_is_heuristic_category_candidate_rejects_confidence_at_threshold() -> None:
    assert (
        is_heuristic_category_candidate(_row(topic="OBSTACLE", topic_confidence=40))
        is False
    )


def test_is_heuristic_category_candidate_accepts_confidence_above_threshold() -> None:
    assert (
        is_heuristic_category_candidate(_row(topic="OBSTACLE", topic_confidence=41))
        is True
    )


def test_is_heuristic_category_candidate_rejects_disallowed_topic() -> None:
    assert (
        is_heuristic_category_candidate(_row(topic="RUNWAY", topic_confidence=100))
        is False
    )


def test_heuristic_category_returns_three() -> None:
    assert heuristic_category(_row(topic="OBSTACLE", topic_confidence=100)) == 3


def test_is_heuristic_category_candidate_uses_settings_threshold() -> None:
    settings = Settings(
        API_KEY="k",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="s",
        ANTHROPIC_API_KEY="a",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="token",
        BETA_SIGNUP_CODE="test-signup-code",
        NOTAM_HEURISTIC_TOPIC_CONFIDENCE_MIN=50,
    )

    assert (
        is_heuristic_category_candidate(
            _row(topic="COMMS", topic_confidence=50),
            settings=settings,
        )
        is False
    )
    assert (
        is_heuristic_category_candidate(
            _row(topic="COMMS", topic_confidence=51),
            settings=settings,
        )
        is True
    )
