from app.services.naips_parser import parse_naips
from tests.paths import EXAMPLE_PLANS_DIR


def test_naips_flight_fields() -> None:
    text = (EXAMPLE_PLANS_DIR / "Specific Pre-Flight Information Bulletin.txt").read_text(
        encoding="utf-8"
    )
    data = parse_naips(text)

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
