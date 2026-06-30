from datetime import UTC, datetime

from app.schemas.integration_analysis import (
    IntegrationAircraftRequest,
    IntegrationAirfieldRequest,
    IntegrationFlightRequest,
)
from app.services.analysis.analysis_context import build_flight_context_from_integration


def test_build_flight_context_from_integration_maps_request_fields() -> None:
    flight = IntegrationFlightRequest(
        departure_airfield=IntegrationAirfieldRequest(
            icao="YSSY",
            rwy="34L",
            iso_country="AU",
            length_ft=1299.0,
        ),
        arrival_airfield=IntegrationAirfieldRequest(icao="YPPH", rwy="03"),
        alternate_airfield_icao="YBLN",
        planned_dept_time=datetime(2026, 6, 6, 9, 8, tzinfo=UTC),
        planned_arr_time=datetime(2026, 6, 9, 11, 47, tzinfo=UTC),
        route="DCT",
        cruise_level="FL430",
        aircraft=IntegrationAircraftRequest(
            make="GULFSTREAM AEROSPACE",
            model="Gulfstream G700 (G-7)",
            rnav_equipped=True,
            icao_wtc="Medium",
            weight_class="Large",
            instrument_approach_category="C",
            aircraft_design_group="C",
        ),
    )

    context = build_flight_context_from_integration(flight)

    assert context.departure_airfield.icao == "YSSY"
    assert context.departure_airfield.length_ft == 1299.0
    assert context.arrival_airfield.icao == "YPPH"
    assert context.alternate_airfield_icao == "YBLN"
    assert context.cruise_level == "FL430"
    assert context.aircraft.make == "GULFSTREAM AEROSPACE"
    assert context.aircraft.instrument_approach_category == "C"
