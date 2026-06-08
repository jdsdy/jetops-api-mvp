import re
from datetime import UTC, date, datetime, timedelta

MONTHS = {
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


def parse_foreflight_date(value: str) -> date:
    match = re.search(r"([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})", value)
    if not match:
        raise ValueError(f"Could not parse ForeFlight date from: {value}")
    month_name, day, year = match.groups()
    return date(int(year), MONTHS[month_name], int(day))


def parse_zulu_hhmm(token: str) -> tuple[int, int]:
    cleaned = token.rstrip("Z")
    if len(cleaned) != 4 or not cleaned.isdigit():
        raise ValueError(f"Invalid zulu time token: {token}")
    return int(cleaned[:2]), int(cleaned[2:])


def combine_zulu(flight_date: date, zulu_token: str) -> datetime:
    hour, minute = parse_zulu_hhmm(zulu_token)
    return datetime(
        flight_date.year,
        flight_date.month,
        flight_date.day,
        hour,
        minute,
        tzinfo=UTC,
    )


def build_foreflight_datetimes(
    flight_date: date,
    dept_zulu: str,
    arr_zulu: str,
) -> tuple[datetime, datetime]:
    dept_time = combine_zulu(flight_date, dept_zulu)
    arr_date = flight_date
    if int(arr_zulu.rstrip("Z")) < int(dept_zulu.rstrip("Z")):
        arr_date = flight_date + timedelta(days=1)
    return dept_time, combine_zulu(arr_date, arr_zulu)


def normalize_cruise(level: str) -> str:
    if level.upper().startswith("FL"):
        return level.upper()
    return f"FL{level}"
