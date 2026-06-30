from datetime import datetime

import pytest

from app.core.errors import (
    IntegrationAnalysisTooManyNotamsError,
    IntegrationAnalysisValidationError,
)
from app.services.integration.analysis_submission import (
    validate_and_normalize_analysis_submission,
)


def minimal_valid_payload() -> dict:
    return {
        "flight": {
            "departure_airfield": {"icao": "YSSY"},
            "arrival_airfield": {"icao": "YPPH"},
            "planned_dept_time": "2026-06-06T09:08:00Z",
            "planned_arr_time": "2026-06-09T11:47:00Z",
            "cruise_level": "FL430",
            "aircraft": {
                "make": "GULFSTREAM AEROSPACE",
                "model": "Gulfstream G700 (G-7)",
                "rnav_equipped": True,
                "icao_wtc": "Medium",
                "weight_class": "Large",
                "instrument_approach_category": "C",
                "aircraft_design_group": "C",
            },
        },
        "notams": [
            {
                "id": "C1223/26 NOTAMN",
                "a": "YBBB",
                "b": "2606170200",
                "c": "2606171200",
                "e": "ARFF NOT AVAILABLE.",
            }
        ],
    }


def full_example_payload() -> dict:
    return {
        "flight": {
            "departure_airfield": {
                "icao": "YSSY",
                "rwy": "34L",
                "iso_country": "AU",
                "length_ft": 12999,
                "length_m": 3962.1,
                "width_ft": 148,
                "width_m": 45.1,
                "surface_type": "Asphalt",
                "lighted": True,
            },
            "arrival_airfield": {
                "icao": "YPPH",
                "rwy": "03",
                "iso_country": "AU",
                "length_ft": None,
                "length_m": None,
                "width_ft": None,
                "width_m": None,
                "surface_type": None,
                "lighted": None,
            },
            "alternate_airfield_icao": "YPTN",
            "planned_dept_time": "2026-06-06T09:08:00Z",
            "planned_arr_time": "2026-06-09T11:47:00Z",
            "route": "YSSY TESAT YPPH",
            "cruise_level": "FL430",
            "aircraft": {
                "make": "GULFSTREAM AEROSPACE",
                "model": "Gulfstream G700 (G-7)",
                "seats": 18,
                "rnav_equipped": True,
                "icao_wtc": "Medium",
                "weight_class": "Large",
                "wingspan_ft": 103,
                "wingspan_m": 31.4,
                "length_ft": 109.8,
                "length_m": 33.5,
                "instrument_approach_category": "C",
                "aircraft_design_group": "C",
            },
        },
        "notams": [
            {
                "a": "YBBB",
                "b": "2606170200",
                "c": "2606171200",
                "d": "DAILY 0200-1200",
                "e": "AERODROME RESCUE AND FIREFIGHTING SERVICES (ARFF) NOT AVAILABLE.",
                "f": None,
                "g": None,
                "q": "YBBB/QFFAU/IV/NBO/A/000/999/3450S13835E005",
                "id": "C1223/26 NOTAMN",
                "title": "AIRPORT SERVICE LIMITED",
            }
        ],
    }


def notam_payload(index: int) -> dict:
    return {
        "id": f"C{index:04d}/26 NOTAMN",
        "a": "YBBB",
        "b": "2606170200",
        "c": "2606171200",
        "e": f"NOTAM body {index}.",
    }


def test_validate_minimal_payload_normalizes_optional_fields_to_null() -> None:
    result = validate_and_normalize_analysis_submission(minimal_valid_payload())
    normalized = result.model_dump(mode="json")

    assert normalized["flight"]["departure_airfield"]["rwy"] is None
    assert normalized["flight"]["alternate_airfield_icao"] is None
    assert normalized["flight"]["route"] is None
    assert normalized["flight"]["aircraft"]["seats"] is None
    assert normalized["notams"][0]["q"] is None
    assert normalized["notams"][0]["title"] is None
    assert normalized["notams"][0]["d"] is None


def test_validate_full_example_payload() -> None:
    result = validate_and_normalize_analysis_submission(full_example_payload())

    assert result.flight.departure_airfield.icao == "YSSY"
    assert result.notams[0].id == "C1223/26 NOTAMN"
    assert result.notams[0].q is not None


def test_validate_rejects_missing_departure_icao() -> None:
    payload = minimal_valid_payload()
    del payload["flight"]["departure_airfield"]["icao"]

    with pytest.raises(IntegrationAnalysisValidationError):
        validate_and_normalize_analysis_submission(payload)


def test_validate_rejects_missing_aircraft_make() -> None:
    payload = minimal_valid_payload()
    del payload["flight"]["aircraft"]["make"]

    with pytest.raises(IntegrationAnalysisValidationError):
        validate_and_normalize_analysis_submission(payload)


def test_validate_rejects_missing_notam_id() -> None:
    payload = minimal_valid_payload()
    del payload["notams"][0]["id"]

    with pytest.raises(IntegrationAnalysisValidationError):
        validate_and_normalize_analysis_submission(payload)


def test_validate_rejects_missing_notam_e() -> None:
    payload = minimal_valid_payload()
    del payload["notams"][0]["e"]

    with pytest.raises(IntegrationAnalysisValidationError):
        validate_and_normalize_analysis_submission(payload)


def test_validate_allows_empty_notams_list() -> None:
    payload = minimal_valid_payload()
    payload["notams"] = []

    result = validate_and_normalize_analysis_submission(payload)

    assert result.notams == []


def test_validate_allows_800_notams() -> None:
    payload = minimal_valid_payload()
    payload["notams"] = [notam_payload(index) for index in range(800)]

    result = validate_and_normalize_analysis_submission(payload)

    assert len(result.notams) == 800


def test_validate_rejects_more_than_800_notams() -> None:
    payload = minimal_valid_payload()
    payload["notams"] = [notam_payload(index) for index in range(801)]

    with pytest.raises(IntegrationAnalysisTooManyNotamsError) as exc_info:
        validate_and_normalize_analysis_submission(payload)

    assert "800" in exc_info.value.message


def test_validate_parses_planned_times_as_datetime() -> None:
    result = validate_and_normalize_analysis_submission(minimal_valid_payload())

    assert isinstance(result.flight.planned_dept_time, datetime)
