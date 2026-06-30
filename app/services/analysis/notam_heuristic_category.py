from app.core.config import Settings, get_settings
from app.schemas.notam_analysis import AnalysisNotamRow

HEURISTIC_CATEGORY_3_TOPICS = frozenset({
    "OBSTACLE",
    "GROUND_MOVEMENT",
    "LIGHTING",
    "COMMS",
    "NAVAID",
})


def is_heuristic_category_candidate(
    row: AnalysisNotamRow,
    *,
    settings: Settings | None = None,
) -> bool:
    if settings is None:
        settings = get_settings()

    return (
        row.topic in HEURISTIC_CATEGORY_3_TOPICS
        and (row.topic_confidence or 0) > settings.NOTAM_HEURISTIC_TOPIC_CONFIDENCE_MIN
    )


def heuristic_category(row: AnalysisNotamRow) -> int:
    return 3
