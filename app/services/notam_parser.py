from app.schemas.notam import RawNotam
from app.services.flight_format import detect_plan_format
from app.services.foreflight_notam_parser import parse_foreflight_notams
from app.services.naips_notam_parser import parse_naips_notams

PARSERS = {
    "foreflight": parse_foreflight_notams,
    "naips": parse_naips_notams,
}


def extract_notams(text: str) -> list[RawNotam]:
    return PARSERS[detect_plan_format(text)](text)
