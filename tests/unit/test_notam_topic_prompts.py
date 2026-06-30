from app.schemas.notam_topic import MISC_TOPIC, SPECIALIST_TOPICS
from app.services.analysis.notam_prompts import GENERIC
from app.services.analysis.notam_topic_prompts import get_system_prompt


def test_get_system_prompt_returns_non_empty_for_all_specialist_topics() -> None:
    for topic in SPECIALIST_TOPICS:
        prompt = get_system_prompt(topic)
        assert prompt.strip(), f"Expected non-empty prompt for topic {topic!r}"


def test_get_system_prompt_returns_general_prompt_for_misc() -> None:
    assert get_system_prompt(MISC_TOPIC) == GENERIC
