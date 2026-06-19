from typing import Literal

from pydantic import BaseModel

MISC_TOPIC = "MISC"

NotamTopic = Literal[
    "OBSTACLE",
    "AIRSPACE_ORGANISATION",
    "PROCEDURE_GENERAL",
    "AERODROME_GENERAL",
    "COMMS",
    "LIGHTING",
    "GROUND_MOVEMENT",
    "AIRSPACE",
    "NAVAID",
    "APPROACH_PROCEDURE",
    "RUNWAY",
    MISC_TOPIC,
]

SPECIALIST_TOPICS: tuple[str, ...] = (
    "OBSTACLE",
    "AIRSPACE_ORGANISATION",
    "PROCEDURE_GENERAL",
    "AERODROME_GENERAL",
    "COMMS",
    "LIGHTING",
    "GROUND_MOVEMENT",
    "AIRSPACE",
    "NAVAID",
    "APPROACH_PROCEDURE",
    "RUNWAY",
)


class ClassificationResult(BaseModel):
    topic: str
    confidence: int
