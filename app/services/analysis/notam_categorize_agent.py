from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings

ThinkingType = Literal["adaptive", "disabled"]

HAIKU_CATEGORIZE_TOPICS = frozenset(
    {
        "OBSTACLE",
        "NAVAID",
        "LIGHTING",
        "GROUND_MOVEMENT",
        "COMMS",
    }
)

NO_THINKING_CATEGORIZE_TOPICS = HAIKU_CATEGORIZE_TOPICS | frozenset({"AIRSPACE_ORGANISATION"})


@dataclass(frozen=True)
class CategorizeAgentConfig:
    model: str
    max_tokens: int
    thinking_type: ThinkingType
    input_cost_per_m: float
    output_cost_per_m: float
    include_effort: bool

    @property
    def thinking(self) -> dict[str, str]:
        return {"type": self.thinking_type}

    def category_output_config(self, schema: dict) -> dict:
        config: dict = {
            "format": {
                "type": "json_schema",
                "schema": schema,
            },
        }
        if self.include_effort:
            config["effort"] = "low"
        return config


def get_categorize_agent_config(topic: str, settings: Settings) -> CategorizeAgentConfig:
    if topic in HAIKU_CATEGORIZE_TOPICS:
        return CategorizeAgentConfig(
            model=settings.NOTAM_CATEGORIZE_HAIKU_MODEL,
            max_tokens=settings.NOTAM_CATEGORIZE_HAIKU_MAX_TOKENS,
            thinking_type="disabled",
            input_cost_per_m=settings.NOTAM_CATEGORIZE_HAIKU_INPUT_COST_PER_M,
            output_cost_per_m=settings.NOTAM_CATEGORIZE_HAIKU_OUTPUT_COST_PER_M,
            include_effort=False,
        )

    if topic in NO_THINKING_CATEGORIZE_TOPICS:
        return CategorizeAgentConfig(
            model=settings.NOTAM_ANALYSIS_MODEL,
            max_tokens=settings.NOTAM_ANALYSIS_MAX_TOKENS,
            thinking_type="disabled",
            input_cost_per_m=settings.NOTAM_ANALYSIS_INPUT_COST_PER_M,
            output_cost_per_m=settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M,
            include_effort=True,
        )

    return CategorizeAgentConfig(
        model=settings.NOTAM_ANALYSIS_MODEL,
        max_tokens=settings.NOTAM_ANALYSIS_MAX_TOKENS,
        thinking_type="adaptive",
        input_cost_per_m=settings.NOTAM_ANALYSIS_INPUT_COST_PER_M,
        output_cost_per_m=settings.NOTAM_ANALYSIS_OUTPUT_COST_PER_M,
        include_effort=True,
    )
