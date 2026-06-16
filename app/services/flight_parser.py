import re
from datetime import UTC, date, datetime, timedelta

from app.schemas.flight import FlightData, PlanSource

# ---------------------------------------------------------------------------
# Format detection (also used by notam_parser)
# ---------------------------------------------------------------------------


_OZ_ICAO_PAIR = re.compile(r"^([A-Z]{4})-([A-Z]{4})$", re.MULTILINE)
_OZ_TOTAL_ETD = re.compile(
    r"Total:\s*[\d.]+\s*NM,\s*(\d+):(\d+)\s+ETD:\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+UTC",
    re.MULTILINE,
)


def _is_ozrunways(text: str) -> bool:
    return (
        _OZ_ICAO_PAIR.search(text) is not None
        and _OZ_TOTAL_ETD.search(text) is not None
    )


def detect_plan_format(text: str) -> PlanSource:
    if text.lstrip().startswith("Specific PreFlight Information Bulletin Number:"):
        return "naips"
    if _is_ozrunways(text):
        return "ozrunways"
    return "foreflight"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _parse_foreflight_date(value: str) -> date:
    match = re.search(r"([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})", value)
    if not match:
        raise ValueError(f"Could not parse ForeFlight date from: {value}")
    month_name, day, year = match.groups()
    return date(int(year), _MONTHS[month_name], int(day))


def _parse_zulu_hhmm(token: str) -> tuple[int, int]:
    cleaned = token.rstrip("Z")
    if len(cleaned) != 4 or not cleaned.isdigit():
        raise ValueError(f"Invalid zulu time token: {token}")
    return int(cleaned[:2]), int(cleaned[2:])


def _combine_zulu(flight_date: date, zulu_token: str) -> datetime:
    hour, minute = _parse_zulu_hhmm(zulu_token)
    return datetime(
        flight_date.year,
        flight_date.month,
        flight_date.day,
        hour,
        minute,
        tzinfo=UTC,
    )


def _build_foreflight_datetimes(
    flight_date: date,
    dept_zulu: str,
    arr_zulu: str,
) -> tuple[datetime, datetime]:
    dept_time = _combine_zulu(flight_date, dept_zulu)
    arr_date = flight_date
    if int(arr_zulu.rstrip("Z")) < int(dept_zulu.rstrip("Z")):
        arr_date = flight_date + timedelta(days=1)
    return dept_time, _combine_zulu(arr_date, arr_zulu)


def _normalize_cruise(level: str) -> str:
    if level.upper().startswith("FL"):
        return level.upper()
    return f"FL{level}"


# ---------------------------------------------------------------------------
# ForeFlight parser
# ---------------------------------------------------------------------------

_FF_HEADER_ICAO_DATE = re.compile(
    r"^([A-Z]{4})\s*[—–-]\s*([A-Z]{4})\s*\(([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\)",
    re.MULTILINE,
)
_FF_ETD_ETA_LINE = re.compile(
    r"^(.+?)/\s*(\d{4})Z\s+([A-Z]{4})\s+.*?/\s*(\d{4})Z",
    re.MULTILINE,
)
_ICAO_CODE = re.compile(r"^[A-Z]{4}$")
_FF_CRUISE_LEVEL = re.compile(r"@\s*(FL\d+)", re.IGNORECASE)
_FF_ROUTE_REPORT_BLOCK = re.compile(
    r"Route Report\s+Departure Destination STD\s+.*?\nRoute\s+(.*?)\s+RESTRICTIONS",
    re.DOTALL,
)
_FF_PRIMARY_ALTERNATE = re.compile(
    r"PRIMARY ALTERNATE\s*\n(.*?)(?:\nCODED ICAO FLIGHT PLAN|\Z)",
    re.DOTALL,
)
_FF_ALTERNATE_ICAO = re.compile(r"^([A-Z]{4})\s+BURN:", re.MULTILINE)


def _foreflight_departure_icao_from_prefix(prefix: str) -> str | None:
    words = prefix.split()
    if not words:
        return None
    if _ICAO_CODE.match(words[0]):
        return words[0]
    if len(words) >= 2 and _ICAO_CODE.match(words[1]):
        return words[1]
    return None


def _parse_foreflight(text: str) -> FlightData:
    header = _FF_HEADER_ICAO_DATE.search(text)
    if not header:
        raise ValueError("ForeFlight header line with ICAOs and date not found")

    departure_icao, arrival_icao, date_fragment = header.groups()
    flight_date = _parse_foreflight_date(date_fragment)

    etd_eta = _FF_ETD_ETA_LINE.search(text)
    if not etd_eta:
        raise ValueError("ForeFlight ETD/ETA line not found")

    prefix, dept_zulu, line_arr, arr_zulu = etd_eta.groups()
    line_dep = _foreflight_departure_icao_from_prefix(prefix.strip())
    if line_dep is None:
        raise ValueError("ForeFlight ETD/ETA line not found")
    if line_dep != departure_icao or line_arr != arrival_icao:
        raise ValueError("ForeFlight ETD/ETA ICAOs do not match header")

    planned_dept_time, planned_arr_time = _build_foreflight_datetimes(
        flight_date,
        f"{dept_zulu}Z",
        f"{arr_zulu}Z",
    )

    cruise_match = _FF_CRUISE_LEVEL.search(text)
    if not cruise_match:
        raise ValueError("ForeFlight cruise level not found")
    cruise_level = _normalize_cruise(cruise_match.group(1))

    route_match = _FF_ROUTE_REPORT_BLOCK.search(text)
    if not route_match:
        raise ValueError("ForeFlight Route Report section not found")

    route = _strip_route_endpoints(
        " ".join(route_match.group(1).split()),
        departure_icao,
        arrival_icao,
    )

    return FlightData(
        departure_icao=departure_icao,
        arrival_icao=arrival_icao,
        planned_dept_time=planned_dept_time,
        planned_arr_time=planned_arr_time,
        route=route,
        cruise_level=cruise_level,
        alt_icao=_parse_foreflight_alternate(text),
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


def _parse_foreflight_alternate(text: str) -> str | None:
    section = _FF_PRIMARY_ALTERNATE.search(text)
    if not section:
        return None

    first_line = section.group(1).strip().splitlines()[0]
    match = _FF_ALTERNATE_ICAO.match(first_line)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# NAIPS parser
# ---------------------------------------------------------------------------

_NAIPS_STAGE_LINE = re.compile(
    r"STAGE\s+\d+:([A-Z]{4})\s+TO\s+([A-Z]{4})\s+ETD\s+\d{4}\s+RTE\s+\S+\s+(FL\d+)",
    re.IGNORECASE,
)
_NAIPS_ALTN_LINE = re.compile(r"^ALTN\s+([A-Z]{4})\b", re.MULTILINE)
_NAIPS_ROUTE_SECTION = re.compile(
    r"ROUTE WIND CROSS-SECTION \(DERIVED FROM GRIB UPPER WINDS DATA\)\s*-+\s*(.*)",
    re.DOTALL | re.IGNORECASE,
)
_NAIPS_SEGMENT_LINE = re.compile(
    r"^([A-Z0-9]{4,5})\s+([A-Z0-9]{4,5})\s+\d{3}\s+\d{4}\s",
    re.MULTILINE,
)
_NAIPS_PAGE_FOOTER = re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE)


def _parse_naips(text: str) -> FlightData:
    stage = _NAIPS_STAGE_LINE.search(text)
    if not stage:
        raise ValueError("NAIPS STAGE flight details line not found")

    departure_icao, arrival_icao, cruise_level = stage.groups()
    cruise_level = _normalize_cruise(cruise_level)

    alt_match = _NAIPS_ALTN_LINE.search(text)
    alt_icao = alt_match.group(1) if alt_match else None

    return FlightData(
        departure_icao=departure_icao,
        arrival_icao=arrival_icao,
        planned_dept_time=None,
        planned_arr_time=None,
        route=_parse_naips_route(text, departure_icao, arrival_icao),
        cruise_level=cruise_level,
        alt_icao=alt_icao,
        source_app="naips",
    )


def _parse_naips_route(text: str, departure_icao: str, arrival_icao: str) -> str:
    section_match = _NAIPS_ROUTE_SECTION.search(text)
    if not section_match:
        raise ValueError("NAIPS route wind cross-section section not found")

    section = _NAIPS_PAGE_FOOTER.sub("", section_match.group(1))
    waypoints = [departure_icao]

    for match in _NAIPS_SEGMENT_LINE.finditer(section):
        to_waypoint = match.group(2)
        waypoints.append(to_waypoint)
        if to_waypoint == arrival_icao:
            break

    if waypoints[-1] != arrival_icao:
        raise ValueError("NAIPS route did not reach arrival ICAO")

    return " ".join(waypoints)


# ---------------------------------------------------------------------------
# OzRunways parser
# ---------------------------------------------------------------------------


def ozrunways_document_year(text: str) -> str:
    return _ozrunways_etd_info(text)[1]


def _ozrunways_etd_info(text: str) -> tuple[date, str]:
    match = _OZ_TOTAL_ETD.search(text)
    if not match:
        raise ValueError("OzRunways Total/ETD line not found")

    duration_hours, duration_minutes, day, month_name, hhmm = match.groups()
    year = datetime.now(UTC).year
    month = _MONTHS[month_name]
    flight_date = date(year, month, int(day))
    hour, minute = _parse_zulu_hhmm(hhmm)
    return flight_date, f"{year % 100:02d}"


def _parse_ozrunways(text: str) -> FlightData:
    icao_match = _OZ_ICAO_PAIR.search(text)
    if not icao_match:
        raise ValueError("OzRunways ICAO pair line not found")

    flight_date, _ = _ozrunways_etd_info(text)
    etd_match = _OZ_TOTAL_ETD.search(text)
    assert etd_match is not None
    duration_hours, duration_minutes, _, _, hhmm = etd_match.groups()
    hour, minute = _parse_zulu_hhmm(hhmm)
    planned_dept_time = datetime(
        flight_date.year,
        flight_date.month,
        flight_date.day,
        hour,
        minute,
        tzinfo=UTC,
    )
    planned_arr_time = planned_dept_time + timedelta(
        hours=int(duration_hours),
        minutes=int(duration_minutes),
    )

    departure_icao, arrival_icao = icao_match.groups()
    return FlightData(
        departure_icao=departure_icao,
        arrival_icao=arrival_icao,
        planned_dept_time=planned_dept_time,
        planned_arr_time=planned_arr_time,
        route=None,
        cruise_level=None,
        alt_icao=None,
        source_app="ozrunways",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PARSERS = {
    "foreflight": _parse_foreflight,
    "naips": _parse_naips,
    "ozrunways": _parse_ozrunways,
}


def parse_flight_data(text: str) -> FlightData:
    return _PARSERS[detect_plan_format(text)](text)
