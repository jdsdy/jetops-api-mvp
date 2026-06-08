from app.schemas.flight import PlanSource


def detect_plan_format(text: str) -> PlanSource:
    if text.lstrip().startswith("Specific PreFlight Information Bulletin Number:"):
        return "naips"
    return "foreflight"
