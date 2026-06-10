from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.schemas.analysis_context import AnalysisContext
from app.services.analysis_context import (
    _build_aircraft,
    _build_airfield,
    _match_runway,
    build_analysis_context,
)


# --- Runway matching ---


def test_match_runway_matches_le_ident_case_insensitive() -> None:
    runways = [{"le_ident": "16L", "he_ident": "34R", "length_ft": 8000.0}]
    assert _match_runway(runways, "16l") == runways[0]


def test_match_runway_matches_he_ident() -> None:
    runways = [{"le_ident": "07", "he_ident": "25", "length_ft": 6000.0}]
    assert _match_runway(runways, "25") == runways[0]


def test_match_runway_returns_none_when_no_match() -> None:
    runways = [{"le_ident": "07", "he_ident": "25"}]
    assert _match_runway(runways, "16") is None


def test_match_runway_returns_none_for_empty_ident() -> None:
    assert _match_runway([{"le_ident": "07"}], None) is None


# --- Mapping helpers ---


def test_build_airfield_populates_runway_fields_from_match() -> None:
    airport = {
        "iso_country": "AU",
        "airport_runways_reference": [
            {
                "le_ident": "34L",
                "he_ident": "16R",
                "length_ft": 1299.0,
                "length_m": 396.0,
                "width_ft": 148.0,
                "width_m": 45.0,
                "surface_type": "ASP",
                "lighted": True,
            }
        ],
    }
    airfield = _build_airfield("YSSY", "34L", airport)
    assert airfield.icao == "YSSY"
    assert airfield.rwy == "34L"
    assert airfield.iso_country == "AU"
    assert airfield.length_ft == 1299.0
    assert airfield.surface_type == "ASP"
    assert airfield.lighted is True


def test_build_airfield_keeps_icao_rwy_when_airport_missing() -> None:
    airfield = _build_airfield("YSSY", "34L", None)
    assert airfield.icao == "YSSY"
    assert airfield.rwy == "34L"
    assert airfield.iso_country is None
    assert airfield.length_ft is None


def test_build_aircraft_uses_reference_when_present() -> None:
    fleet = {
        "manufacturer": "Fleet Mfr",
        "model": "Fleet Model",
        "seats": 8,
        "rnav_equipped": True,
        "aircraft_reference": {
            "manufacturer": "Ref Mfr",
            "model": "Ref Model",
            "wingspan_ft": 94.0,
            "wingspan_m": 28.7,
            "length_ft": 66.0,
            "length_m": 20.1,
            "icao_wtc": "L",
            "weight_class": "Small",
            "adc": "III",
            "aac": "C",
        },
    }
    aircraft = _build_aircraft(fleet)
    assert aircraft.make == "Ref Mfr"
    assert aircraft.model == "Ref Model"
    assert aircraft.seats == 8
    assert aircraft.instrument_approach_category == "C"
    assert aircraft.aircraft_design_group == "III"


def test_build_aircraft_falls_back_to_fleet_without_reference() -> None:
    fleet = {
        "manufacturer": "Fleet Mfr",
        "model": "Fleet Model",
        "seats": 6,
        "rnav_equipped": False,
        "aircraft_reference": None,
    }
    aircraft = _build_aircraft(fleet)
    assert aircraft.make == "Fleet Mfr"
    assert aircraft.model == "Fleet Model"
    assert aircraft.seats == 6
    assert aircraft.wingspan_ft is None
    assert aircraft.icao_wtc is None


def test_build_aircraft_all_null_when_no_fleet() -> None:
    aircraft = _build_aircraft(None)
    assert aircraft.make is None
    assert aircraft.seats is None


# --- build_analysis_context ---


JOB_BUNDLE = {
    "id": str(uuid4()),
    "flight_plan_id": str(uuid4()),
    "flight_plans": {
        "route": "DCT",
        "cruise_level": "FL430",
        "dept_rwy": "34L",
        "arr_rwy": "03",
        "alt_icao": "YBLN",
        "planned_dept_time": "2026-04-15T11:35:00+00:00",
        "planned_arr_time": "2026-04-15T15:42:00+00:00",
        "flights": {
            "departure_icao": "YSSY",
            "arrival_icao": "YPPH",
            "fleet_aircraft": {
                "manufacturer": "Bombardier",
                "model": "Global 6000",
                "seats": 14,
                "rnav_equipped": True,
                "aircraft_reference": {
                    "manufacturer": "Bombardier",
                    "model": "Global 6000",
                    "wingspan_ft": 94.0,
                    "wingspan_m": 28.7,
                    "length_ft": 99.0,
                    "length_m": 30.2,
                    "icao_wtc": "M",
                    "weight_class": "Medium",
                    "adc": "C",
                    "aac": "D",
                },
            },
        },
    },
}

DEP_AIRPORT = {
    "icao_code": "YSSY",
    "iso_country": "AU",
    "airport_runways_reference": [
        {
            "le_ident": "34L",
            "he_ident": "16R",
            "length_ft": 1299.0,
            "length_m": 396.0,
            "width_ft": 148.0,
            "width_m": 45.0,
            "surface_type": "ASP",
            "lighted": True,
        }
    ],
}

ARR_AIRPORT = {
    "icao_code": "YPPH",
    "iso_country": "AU",
    "airport_runways_reference": [
        {
            "le_ident": "03",
            "he_ident": "21",
            "length_ft": 3444.0,
            "length_m": 1050.0,
            "width_ft": 148.0,
            "width_m": 45.0,
            "surface_type": "ASP",
            "lighted": True,
        }
    ],
}

NOTAM_ROWS = [
    {
        "title": "TAXIWAY CLOSED",
        "notam_id": "C0481/26 NOTAMN",
        "q": "YBBB/QMXLC/IV/BO/A/000/999/2723S15307E005",
        "a": "YBBN",
        "b": "2604191200",
        "c": "2604191900",
        "d": "HJ",
        "e": "TWY B2 CLSD",
        "f": None,
        "g": None,
    }
]


def test_build_analysis_context_assembles_flight_and_notams() -> None:
    job_id = uuid4()
    mock_repo = MagicMock(spec=AnalysisContextRepository)
    mock_repo.fetch_job_bundle.return_value = JOB_BUNDLE
    mock_repo.fetch_airport_context.side_effect = lambda icao: {
        "YSSY": DEP_AIRPORT,
        "YPPH": ARR_AIRPORT,
    }.get(icao)
    mock_repo.fetch_notams.return_value = NOTAM_ROWS

    context = build_analysis_context(job_id, mock_repo)

    assert isinstance(context, AnalysisContext)
    assert context.flight.route == "DCT"
    assert context.flight.alternate_airfield_icao == "YBLN"
    assert context.flight.planned_dept_time == datetime(
        2026, 4, 15, 11, 35, tzinfo=UTC
    )
    assert context.flight.departure_airfield.length_ft == 1299.0
    assert context.flight.arrival_airfield.rwy == "03"
    assert context.flight.aircraft.make == "Bombardier"
    assert len(context.notams) == 1
    assert context.notams[0].notam_id == "C0481/26 NOTAMN"


def test_build_analysis_context_raises_when_job_missing() -> None:
    mock_repo = MagicMock(spec=AnalysisContextRepository)
    mock_repo.fetch_job_bundle.return_value = None

    with pytest.raises(ValueError, match="Analysis job not found"):
        build_analysis_context(uuid4(), mock_repo)
