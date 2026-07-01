from datetime import UTC, datetime

import pytest

from app.services.extraction.flight_parser import (
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


def test_ypph_ybtl_foreflight_with_recall_number() -> None:
    data = parse_flight_data(load_txt("ypph-ybtl 17jun26.txt"))

    assert data.departure_icao == "YPPH"
    assert data.arrival_icao == "YBTL"
    assert data.planned_dept_time == datetime(2026, 6, 17, 5, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 6, 17, 8, 37, tzinfo=UTC)
    assert data.source_app == "foreflight"


def test_foreflight_etd_eta_line_without_recall_prefix() -> None:
    text = (
        "YSSY — YBBN (Apr 25, 2026) in N70HN\n"
        "Recall # DEP ETD DEST ETA\n"
        "YSSY 19:10 AEST / 0910Z YBBN 20:06 AEST / 1006Z\n"
        "@ FL450\n"
        "Route Report\nDeparture Destination STD\n"
        "YSSY YBBN\n"
        "Route DCT RESTRICTIONS\n"
    )
    data = parse_flight_data(text)

    assert data.departure_icao == "YSSY"
    assert data.arrival_icao == "YBBN"
    assert data.planned_dept_time == datetime(2026, 4, 25, 9, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 25, 10, 6, tzinfo=UTC)


def test_foreflight_etd_eta_line_with_recall_prefix() -> None:
    text = (
        "Recall # DEP ETD DEST ETA\n"
        "F0100 YPPH 13:10 AWST / 0510Z YBTL 18:37 AEST / 0837Z\n"
        "YPPH — YBTL (Jun 17, 2026) in N70HN\n"
        "@ FL450\n"
        "Route Report\nDeparture Destination STD\n"
        "YPPH YBTL\n"
        "Route DCT RESTRICTIONS\n"
    )
    data = parse_flight_data(text)

    assert data.departure_icao == "YPPH"
    assert data.arrival_icao == "YBTL"
    assert data.planned_dept_time == datetime(2026, 6, 17, 5, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 6, 17, 8, 37, tzinfo=UTC)


def test_foreflight_etd_eta_line_raises_when_departure_not_icao() -> None:
    text = (
        "YSSY — YBBN (Apr 25, 2026) in N70HN\n"
        "RECALL 1234 19:10 AEST / 0910Z YBBN 20:06 AEST / 1006Z\n"
        "@ FL450\n"
        "Route Report\nDeparture Destination STD\n"
        "YSSY YBBN\n"
        "Route DCT RESTRICTIONS\n"
    )

    with pytest.raises(ValueError, match="ForeFlight ETD/ETA line not found"):
        parse_flight_data(text)


def test_yssy_ypph_standard_foreflight_fields() -> None:
    data = parse_flight_data(load_txt("618f85e5-2377-9370-804b-9d46b916c212.txt"))

    assert data.departure_icao == "YSSY"
    assert data.arrival_icao == "YPPH"
    assert data.planned_dept_time == datetime(2026, 6, 24, 11, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 6, 24, 15, 30, tzinfo=UTC)
    assert data.route == "N0473F400 DCT"
    assert data.cruise_level == "FL400"
    assert data.alt_icao == "YBLN"
    assert data.source_app == "foreflight"


def test_foreflight_standard_etd_eta_line_without_recall_prefix() -> None:
    text = (
        "YSSY — YPPH (Jun 24, 2026) in N254HN (BCS1 - A220-100) IFR Created Jun 24 2026 1100Z\n"
        "250/290 KIAS/M0.76 - Max Cruise Speed @ FL400 - M0.78/275/250 KIAS\n"
        "ETE Distance Avg Wind ETD ETA TOW ELW\n"
        "4h20m 1773NM 49kt head (271°/049) 21:10 AEST / 1110Z 23:30 AWST / 1530Z 100623 lbs 84050 lbs\n"
        "ALTERNATE #1 YBLN / ROUTE: DCT\n"
        "Overflight Report YSSY — YPPH (Jun 24, 2026Z) in N254HN (BCS1) IFR Created Jun 24 2026 1100Z\n"
        "Departure Destination ETD MTOW\n"
        "YSSY YPPH 2026-06-24 11:10Z 63730 kilograms\n"
        "Route\n"
        "N0473F400 DCT\n"
        "COUNTRY FIR OVERFLIGHTS COSTS\n"
    )
    data = parse_flight_data(text)

    assert data.planned_dept_time == datetime(2026, 6, 24, 11, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 6, 24, 15, 30, tzinfo=UTC)
    assert data.route == "N0473F400 DCT"
    assert data.alt_icao == "YBLN"


def test_foreflight_overflight_route_spans_multiple_lines() -> None:
    text = (
        "YSSY — YPPH (Jun 24, 2026) in N254HN IFR Created Jun 24 2026 1100Z\n"
        "ETE Distance Avg Wind ETD ETA TOW ELW\n"
        "4h20m 1773NM 49kt head 21:10 AEST / 1110Z 23:30 AWST / 1530Z 100623 lbs 84050 lbs\n"
        "@ FL400\n"
        "Overflight Report YSSY — YPPH (Jun 24, 2026Z) in N254HN IFR Created Jun 24 2026 1100Z\n"
        "Departure Destination ETD MTOW\n"
        "YSSY YPPH 2026-06-24 11:10Z 63730 kilograms\n"
        "Route\n"
        "N0504F430 BIXAD2 BIXAD Q67 GUDSO\n"
        "OMLET/N0496F470 B586 XAC XACN\n"
        "COUNTRY FIR OVERFLIGHTS COSTS\n"
    )
    data = parse_flight_data(text)

    assert (
        data.route
        == "N0504F430 BIXAD2 BIXAD Q67 GUDSO OMLET/N0496F470 B586 XAC XACN"
    )


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
