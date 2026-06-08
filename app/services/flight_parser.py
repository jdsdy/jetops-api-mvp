from datetime import datetime

from app.schemas.flight import FlightData
from app.services.flight_format import detect_plan_format
from app.services.foreflight_parser import parse_foreflight
from app.services.naips_parser import parse_naips

PARSERS = {
    "foreflight": parse_foreflight,
    "naips": parse_naips,
}


def parse_flight_data(text: str) -> FlightData:
    return PARSERS[detect_plan_format(text)](text)
