import json
from datetime import datetime

import pytest

from app.schemas.flight import FlightData
from app.services.flight_parser import parse_flight_data
from app.services.pdf_extractor import extract_pdf_text
from tests.paths import EXAMPLE_PLANS_DIR, FLIGHT_DATA_FIXTURES


def load_expected_cases() -> list[dict]:
    return json.loads(FLIGHT_DATA_FIXTURES.read_text(encoding="utf-8"))


def assert_flight_data_matches_case(data: FlightData, case: dict) -> None:
    assert data.departure_icao == case["departure_icao"]
    assert data.arrival_icao == case["arrival_icao"]
    assert data.route == case["route"]
    assert data.cruise_level == case["cruise_level"]
    assert data.alt_icao == case["alt_icao"]
    assert data.source_app == case["source_app"]

    if case["planned_dept_time"] is None:
        assert data.planned_dept_time is None
    else:
        assert data.planned_dept_time == datetime.fromisoformat(case["planned_dept_time"])

    if case["planned_arr_time"] is None:
        assert data.planned_arr_time is None
    else:
        assert data.planned_arr_time == datetime.fromisoformat(case["planned_arr_time"])


@pytest.mark.parametrize("case", load_expected_cases(), ids=lambda c: c["pdf"])
def test_parse_flight_data_from_txt(case: dict) -> None:
    txt_name = case["pdf"].replace(".pdf", ".txt")
    text = (EXAMPLE_PLANS_DIR / txt_name).read_text(encoding="utf-8")
    assert_flight_data_matches_case(parse_flight_data(text), case)


@pytest.mark.parametrize("case", load_expected_cases(), ids=lambda c: c["pdf"])
def test_parse_flight_data_from_pdf(case: dict) -> None:
    text = extract_pdf_text(EXAMPLE_PLANS_DIR / case["pdf"])
    assert_flight_data_matches_case(parse_flight_data(text), case)
