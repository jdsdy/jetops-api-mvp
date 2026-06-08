import re

from app.schemas.flight import FlightData
from app.services.flight_utils import (
    build_foreflight_datetimes,
    normalize_cruise,
    parse_foreflight_date,
)

HEADER_ICAO_DATE = re.compile(
    r"^([A-Z]{4})\s*[—–-]\s*([A-Z]{4})\s*\(([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\)",
    re.MULTILINE,
)
ETD_ETA_LINE = re.compile(
    r"^([A-Z]{4})\s+.*?/\s*(\d{4})Z\s+([A-Z]{4})\s+.*?/\s*(\d{4})Z",
    re.MULTILINE,
)
CRUISE_LEVEL = re.compile(r"@\s*(FL\d+)", re.IGNORECASE)
ROUTE_REPORT_BLOCK = re.compile(
    r"Route Report\s+Departure Destination STD\s+.*?\nRoute\s+(.*?)\s+RESTRICTIONS",
    re.DOTALL,
)
PRIMARY_ALTERNATE = re.compile(
    r"PRIMARY ALTERNATE\s*\n(.*?)(?:\nCODED ICAO FLIGHT PLAN|\Z)",
    re.DOTALL,
)
ALTERNATE_ICAO = re.compile(r"^([A-Z]{4})\s+BURN:", re.MULTILINE)


def parse_foreflight(text: str) -> FlightData:
    header = HEADER_ICAO_DATE.search(text)
    if not header:
        raise ValueError("ForeFlight header line with ICAOs and date not found")

    departure_icao, arrival_icao, date_fragment = header.groups()
    flight_date = parse_foreflight_date(date_fragment)

    etd_eta = ETD_ETA_LINE.search(text)
    if not etd_eta:
        raise ValueError("ForeFlight ETD/ETA line not found")

    line_dep, dept_zulu, line_arr, arr_zulu = etd_eta.groups()
    if line_dep != departure_icao or line_arr != arrival_icao:
        raise ValueError("ForeFlight ETD/ETA ICAOs do not match header")

    planned_dept_time, planned_arr_time = build_foreflight_datetimes(
        flight_date,
        f"{dept_zulu}Z",
        f"{arr_zulu}Z",
    )

    cruise_match = CRUISE_LEVEL.search(text)
    if not cruise_match:
        raise ValueError("ForeFlight cruise level not found")
    cruise_level = normalize_cruise(cruise_match.group(1))

    route_match = ROUTE_REPORT_BLOCK.search(text)
    if not route_match:
        raise ValueError("ForeFlight Route Report section not found")

    route = _strip_route_endpoints(
        " ".join(route_match.group(1).split()),
        departure_icao,
        arrival_icao,
    )

    alt_icao = _parse_alternate(text)

    return FlightData(
        departure_icao=departure_icao,
        arrival_icao=arrival_icao,
        planned_dept_time=planned_dept_time,
        planned_arr_time=planned_arr_time,
        route=route,
        cruise_level=cruise_level,
        alt_icao=alt_icao,
        source_app="foreflight",
    )


def _strip_route_endpoints(
    route: str,
    departure_icao: str,
    arrival_icao: str,
) -> str:
    tokens = route.split()
    if tokens and tokens[0] == departure_icao:
        tokens = tokens[1:]
    if tokens and tokens[-1] == arrival_icao:
        tokens = tokens[:-1]
    return " ".join(tokens)


def _parse_alternate(text: str) -> str | None:
    section = PRIMARY_ALTERNATE.search(text)
    if not section:
        return None

    first_line = section.group(1).strip().splitlines()[0]
    match = ALTERNATE_ICAO.match(first_line)
    return match.group(1) if match else None
