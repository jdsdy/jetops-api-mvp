from app.schemas.notam_topic import MISC_TOPIC
from app.services.notam_prompts import (
    AERODROME_GENERAL,
    AIRSPACE,
    AIRSPACE_ORGANISATION,
    APPROACH_PROCEDURE,
    COMMS,
    GENERIC,
    GROUND_MOVEMENT,
    LIGHTING,
    NAVAID,
    OBSTACLE,
    PROCEDURE_GENERAL,
    RUNWAY,
)

TOPIC_SYSTEM_PROMPTS: dict[str, str] = {
    MISC_TOPIC: GENERIC,
    "OBSTACLE": OBSTACLE,
    "AIRSPACE_ORGANISATION": AIRSPACE_ORGANISATION,
    "PROCEDURE_GENERAL": PROCEDURE_GENERAL,
    "AERODROME_GENERAL": AERODROME_GENERAL,
    "COMMS": COMMS,
    "LIGHTING": LIGHTING,
    "GROUND_MOVEMENT": GROUND_MOVEMENT,
    "AIRSPACE": AIRSPACE,
    "NAVAID": NAVAID,
    "APPROACH_PROCEDURE": APPROACH_PROCEDURE,
    "RUNWAY": RUNWAY,
}


def get_system_prompt(topic: str) -> str:
    if topic == MISC_TOPIC:
        return GENERIC

    prompt = TOPIC_SYSTEM_PROMPTS.get(topic, "")
    if not prompt:
        raise ValueError(
            f"No system prompt configured for NOTAM topic '{topic}'. "
            f"Add a prompt in app/services/notam_prompts/."
        )
    return prompt
