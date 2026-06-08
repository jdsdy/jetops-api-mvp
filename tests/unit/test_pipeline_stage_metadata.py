from datetime import UTC, datetime

from app.schemas.flight import FlightData
from app.schemas.notam import RawNotam
from app.schemas.pipeline_stage import (
    build_flight_parse_metadata,
    build_notam_parse_metadata,
)


def test_build_flight_parse_metadata_splits_null_and_non_null_fields() -> None:
    flight_data = FlightData(
        departure_icao="YSSY",
        arrival_icao="YPDN",
        planned_dept_time=None,
        planned_arr_time=None,
        route="YSSY TESAT YPDN",
        cruise_level="FL430",
        alt_icao="YPTN",
        source_app="naips",
    )

    metadata = build_flight_parse_metadata(flight_data)

    assert metadata.source_type == "naips"
    assert metadata.fields_extracted == [
        "departure_icao",
        "arrival_icao",
        "route",
        "cruise_level",
        "alt_icao",
        "source_app",
    ]
    assert metadata.fields_missing == ["planned_dept_time", "planned_arr_time"]


def test_build_flight_parse_metadata_includes_all_fields_when_populated() -> None:
    flight_data = FlightData(
        departure_icao="YSSY",
        arrival_icao="YPPH",
        planned_dept_time=datetime(2026, 4, 15, 11, 35, tzinfo=UTC),
        planned_arr_time=datetime(2026, 4, 15, 15, 42, tzinfo=UTC),
        route="DCT",
        cruise_level="FL430",
        alt_icao="YBLN",
        source_app="foreflight",
    )

    metadata = build_flight_parse_metadata(flight_data)

    assert metadata.fields_missing == []
    assert set(metadata.fields_extracted) == set(flight_data.model_dump().keys())


def test_build_notam_parse_metadata_dedupes_aerodromes() -> None:
    notams = [
        RawNotam(notam_id="C0481/26 NOTAMN", a="YBBN", q="YBBB/..."),
        RawNotam(notam_id="C0478/26 NOTAMN", a="YBBN", q="YBBB/..."),
        RawNotam(notam_id="C0470/26 NOTAMN", a="YSSY", q="YMMM/..."),
    ]

    metadata = build_notam_parse_metadata(notams, "foreflight")

    assert metadata.notams_found == 3
    assert metadata.aerodromes_found == ["YBBN", "YSSY"]
    assert metadata.parse_failures == 0


def test_build_notam_parse_metadata_detects_multiformat_foreflight() -> None:
    notams = [
        RawNotam(notam_id="C0481/26 NOTAMN", q="YBBB/..."),
        RawNotam(notam_id="HNL 04/227"),
    ]

    metadata = build_notam_parse_metadata(notams, "foreflight")

    assert metadata.multiformat_notams is True


def test_build_notam_parse_metadata_not_multiformat_for_naips() -> None:
    notams = [RawNotam(notam_id="H4489/26", a="YSSY")]

    metadata = build_notam_parse_metadata(notams, "naips")

    assert metadata.multiformat_notams is False
