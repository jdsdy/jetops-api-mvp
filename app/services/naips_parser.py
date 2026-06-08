import re

from app.schemas.flight import FlightData
from app.services.flight_utils import normalize_cruise

STAGE_LINE = re.compile(
    r"STAGE\s+\d+:([A-Z]{4})\s+TO\s+([A-Z]{4})\s+ETD\s+\d{4}\s+RTE\s+\S+\s+(FL\d+)",
    re.IGNORECASE,
)
ALTN_LINE = re.compile(r"^ALTN\s+([A-Z]{4})\b", re.MULTILINE)
ROUTE_SECTION = re.compile(
    r"ROUTE WIND CROSS-SECTION \(DERIVED FROM GRIB UPPER WINDS DATA\)\s*-+\s*(.*)",
    re.DOTALL | re.IGNORECASE,
)
SEGMENT_LINE = re.compile(
    r"^([A-Z0-9]{4,5})\s+([A-Z0-9]{4,5})\s+\d{3}\s+\d{4}\s",
    re.MULTILINE,
)
PAGE_FOOTER = re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE)


def parse_naips(text: str) -> FlightData:
    stage = STAGE_LINE.search(text)
    if not stage:
        raise ValueError("NAIPS STAGE flight details line not found")

    departure_icao, arrival_icao, cruise_level = stage.groups()
    cruise_level = normalize_cruise(cruise_level)

    alt_match = ALTN_LINE.search(text)
    alt_icao = alt_match.group(1) if alt_match else None

    route = _parse_route(text, departure_icao, arrival_icao)

    return FlightData(
        departure_icao=departure_icao,
        arrival_icao=arrival_icao,
        planned_dept_time=None,
        planned_arr_time=None,
        route=route,
        cruise_level=cruise_level,
        alt_icao=alt_icao,
        source_app="naips",
    )


def _parse_route(text: str, departure_icao: str, arrival_icao: str) -> str:
    section_match = ROUTE_SECTION.search(text)
    if not section_match:
        raise ValueError("NAIPS route wind cross-section section not found")

    section = PAGE_FOOTER.sub("", section_match.group(1))
    waypoints = [departure_icao]

    for match in SEGMENT_LINE.finditer(section):
        to_waypoint = match.group(2)
        waypoints.append(to_waypoint)
        if to_waypoint == arrival_icao:
            break

    if waypoints[-1] != arrival_icao:
        raise ValueError("NAIPS route did not reach arrival ICAO")

    return " ".join(waypoints)
