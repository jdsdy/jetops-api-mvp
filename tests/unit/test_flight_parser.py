from datetime import UTC, datetime

import pytest

from app.services.flight_parser import (
    _ozrunways_etd_info,
    detect_plan_format,
    parse_flight_data,
)
from tests.paths import EXAMPLE_PLANS_DIR


def load_txt(name: str) -> str:
    return (EXAMPLE_PLANS_DIR / name).read_text(encoding="utf-8")


# --- Format detection ---


@pytest.mark.parametrize(
    ("txt_name", "expected"),
    [
        ("Specific Pre-Flight Information Bulletin.txt", "naips"),
        ("Briefing: YSSY - YPPH (created Apr 14 01:22:14Z).txt", "foreflight"),
        ("2026-06-10 14-48AWST YPPH-YBRM OZ-NEW.txt", "ozrunways"),
    ],
)
def test_detect_plan_format(txt_name: str, expected: str) -> None:
    assert detect_plan_format(load_txt(txt_name)) == expected


# --- ForeFlight ---


def test_yssy_ypph_foreflight_fields() -> None:
    data = parse_flight_data(load_txt("Briefing: YSSY - YPPH (created Apr 14 01:22:14Z).txt"))

    assert data.departure_icao == "YSSY"
    assert data.arrival_icao == "YPPH"
    assert data.planned_dept_time == datetime(2026, 4, 15, 11, 35, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 15, 15, 42, tzinfo=UTC)
    assert data.cruise_level == "FL430"
    assert data.alt_icao == "YBLN"
    assert data.route == "TESAT A576 KADOM H44 BORLI Q32 NODEV Q10 MALUP Q158 PH"


def test_yssy_ybbn_foreflight_fields() -> None:
    data = parse_flight_data(load_txt("Briefing: YSSY - YBBN (created Apr 14 01:10:42Z).txt"))

    assert data.planned_dept_time == datetime(2026, 4, 25, 9, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 25, 10, 6, tzinfo=UTC)
    assert data.route == "DCT"
    assert data.alt_icao == "YBSU"


def test_ybbn_rjtt_foreflight_no_alternate() -> None:
    data = parse_flight_data(load_txt("Briefing: YBBN - RJTT (created Apr 19 07:02:56Z).txt"))

    assert data.planned_dept_time == datetime(2026, 4, 19, 7, 15, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 19, 15, 9, tzinfo=UTC)
    assert data.cruise_level == "FL470"
    assert data.alt_icao is None


# --- NAIPS ---


def test_naips_flight_fields() -> None:
    data = parse_flight_data(load_txt("Specific Pre-Flight Information Bulletin.txt"))

    assert data.departure_icao == "YSSY"
    assert data.arrival_icao == "YPDN"
    assert data.planned_dept_time is None
    assert data.planned_arr_time is None
    assert data.cruise_level == "FL430"
    assert data.alt_icao == "YPTN"
    assert (
        data.route
        == "YSSY TESAT YSRI MUDGI KABIX POTUM BAZZA OPAXA IVRAD DODRO NITUN MIGAX OPEKO YPTN VEGPU YPDN"
    )


# --- OzRunways ---


def test_ozrunways_flight_fields() -> None:
    data = parse_flight_data(load_txt("2026-06-10 14-48AWST YPPH-YBRM OZ-NEW.txt"))

    assert data.departure_icao == "YPPH"
    assert data.arrival_icao == "YBRM"
    assert data.planned_dept_time == datetime(2026, 6, 10, 6, 26, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 6, 10, 9, 55, tzinfo=UTC)
    assert data.route is None
    assert data.cruise_level is None
    assert data.alt_icao is None
    assert data.source_app == "ozrunways"


def test_ozrunways_etd_info_returns_flight_date_and_year() -> None:
    text = "YPPH-YBRM\nTotal: 903 NM, 3:29 ETD: 10 Jun 0626 UTC\n"
    flight_date, year = _ozrunways_etd_info(text)

    assert flight_date == datetime(2026, 6, 10, tzinfo=UTC).date()
    assert year == "26"
