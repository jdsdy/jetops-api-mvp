from datetime import UTC, datetime

from app.services.foreflight_parser import parse_foreflight
from tests.paths import EXAMPLE_PLANS_DIR


def load_txt(name: str) -> str:
    return (EXAMPLE_PLANS_DIR / name).read_text(encoding="utf-8")


def test_yssy_ypph_foreflight_fields() -> None:
    data = parse_foreflight(load_txt("Briefing: YSSY - YPPH (created Apr 14 01:22:14Z).txt"))

    assert data.departure_icao == "YSSY"
    assert data.arrival_icao == "YPPH"
    assert data.planned_dept_time == datetime(2026, 4, 15, 11, 35, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 15, 15, 42, tzinfo=UTC)
    assert data.cruise_level == "FL430"
    assert data.alt_icao == "YBLN"
    assert data.route == "TESAT A576 KADOM H44 BORLI Q32 NODEV Q10 MALUP Q158 PH"


def test_yssy_ybbn_foreflight_fields() -> None:
    data = parse_foreflight(load_txt("Briefing: YSSY - YBBN (created Apr 14 01:10:42Z).txt"))

    assert data.planned_dept_time == datetime(2026, 4, 25, 9, 10, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 25, 10, 6, tzinfo=UTC)
    assert data.route == "DCT"
    assert data.alt_icao == "YBSU"


def test_ybbn_rjtt_foreflight_no_alternate() -> None:
    data = parse_foreflight(load_txt("Briefing: YBBN - RJTT (created Apr 19 07:02:56Z).txt"))

    assert data.planned_dept_time == datetime(2026, 4, 19, 7, 15, tzinfo=UTC)
    assert data.planned_arr_time == datetime(2026, 4, 19, 15, 9, tzinfo=UTC)
    assert data.cruise_level == "FL470"
    assert data.alt_icao is None
