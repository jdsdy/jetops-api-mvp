import json
from datetime import datetime
from uuid import UUID

from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.schemas.analysis_context import (
    AircraftContext,
    AirfieldContext,
    AnalysisContext,
    AnalysisNotam,
    FlightContext,
)
from app.schemas.notam_analysis import AnalysisNotamRow

# ---------------------------------------------------------------------------
# Runway matching
# ---------------------------------------------------------------------------


def _match_runway(runways: list[dict], rwy_ident: str | None) -> dict | None:
    if not rwy_ident:
        return None

    ident = rwy_ident.strip().upper()
    for runway in runways:
        le = runway.get("le_ident")
        he = runway.get("he_ident")
        if ident == (le or "").upper() or ident == (he or "").upper():
            return runway
    return None


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _build_airfield(
    icao: str | None,
    rwy: str | None,
    airport: dict | None,
) -> AirfieldContext:
    runway = None
    iso_country = None
    if airport:
        iso_country = airport.get("iso_country")
        runways = airport.get("airport_runways_reference") or []
        runway = _match_runway(runways, rwy)

    return AirfieldContext(
        icao=icao,
        rwy=rwy,
        iso_country=iso_country,
        length_ft=runway.get("length_ft") if runway else None,
        length_m=runway.get("length_m") if runway else None,
        width_ft=runway.get("width_ft") if runway else None,
        width_m=runway.get("width_m") if runway else None,
        surface_type=runway.get("surface_type") if runway else None,
        lighted=runway.get("lighted") if runway else None,
    )


def _parse_custom_data(value: object | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict) or not value:
        return None
    return value


def _specs_from_aircraft_reference(reference: dict) -> dict[str, object | None]:
    return {
        "icao_wtc": reference.get("icao_wtc"),
        "weight_class": reference.get("weight_class"),
        "wingspan_ft": reference.get("wingspan_ft"),
        "wingspan_m": reference.get("wingspan_m"),
        "length_ft": reference.get("length_ft"),
        "length_m": reference.get("length_m"),
        "instrument_approach_category": reference.get("aac"),
        "aircraft_design_group": reference.get("adc"),
    }


def _specs_from_custom_data(custom_data: dict) -> dict[str, object | None]:
    return {
        "icao_wtc": custom_data.get("icao_wtc"),
        "weight_class": custom_data.get("weight_class"),
        "wingspan_ft": custom_data.get("wingspan_ft"),
        "wingspan_m": custom_data.get("wingspan_m"),
        "length_ft": custom_data.get("length_ft"),
        "length_m": custom_data.get("length_m"),
        "instrument_approach_category": custom_data.get("aac"),
        "aircraft_design_group": custom_data.get("adg"),
    }


def _build_aircraft(fleet: dict | None) -> AircraftContext:
    if not fleet:
        return AircraftContext()

    reference = fleet.get("aircraft_reference")
    if reference:
        specs = _specs_from_aircraft_reference(reference)
        return AircraftContext(
            make=reference.get("manufacturer"),
            model=reference.get("model"),
            seats=fleet.get("seats"),
            rnav_equipped=fleet.get("rnav_equipped"),
            **specs,
        )

    custom_data = _parse_custom_data(fleet.get("custom_data"))
    specs = _specs_from_custom_data(custom_data) if custom_data else {}

    return AircraftContext(
        make=fleet.get("manufacturer"),
        model=fleet.get("model"),
        seats=fleet.get("seats"),
        rnav_equipped=fleet.get("rnav_equipped"),
        **specs,
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_notams(rows: list[dict]) -> list[AnalysisNotam]:
    return [AnalysisNotam.model_validate(row) for row in rows]


def build_notam_rows(rows: list[dict]) -> list[AnalysisNotamRow]:
    return [AnalysisNotamRow.model_validate(row) for row in rows]


def _flight_context_from_bundle(
    bundle: dict,
    repository: AnalysisContextRepository,
) -> FlightContext:
    flight_plan = bundle["flight_plans"]
    flight = flight_plan["flights"]
    fleet = flight.get("fleet_aircraft")

    departure_icao = flight.get("departure_icao")
    arrival_icao = flight.get("arrival_icao")

    return FlightContext(
        departure_airfield=_build_airfield(
            departure_icao,
            flight_plan.get("dept_rwy"),
            repository.fetch_airport_context(departure_icao),
        ),
        arrival_airfield=_build_airfield(
            arrival_icao,
            flight_plan.get("arr_rwy"),
            repository.fetch_airport_context(arrival_icao),
        ),
        alternate_airfield_icao=flight_plan.get("alt_icao"),
        planned_dept_time=_parse_timestamp(flight_plan.get("planned_dept_time")),
        planned_arr_time=_parse_timestamp(flight_plan.get("planned_arr_time")),
        route=flight_plan.get("route"),
        cruise_level=flight_plan.get("cruise_level"),
        aircraft=_build_aircraft(fleet),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_flight_context(
    job_id: UUID,
    repository: AnalysisContextRepository | None = None,
) -> FlightContext:
    if repository is None:
        from app.core.supabase import get_supabase_client

        repository = AnalysisContextRepository(get_supabase_client())

    bundle = repository.fetch_job_bundle(job_id)
    if not bundle:
        raise ValueError("Analysis job not found")

    return _flight_context_from_bundle(bundle, repository)


def build_analysis_context(
    job_id: UUID,
    repository: AnalysisContextRepository | None = None,
) -> AnalysisContext:
    if repository is None:
        from app.core.supabase import get_supabase_client

        repository = AnalysisContextRepository(get_supabase_client())

    bundle = repository.fetch_job_bundle(job_id)
    if not bundle:
        raise ValueError("Analysis job not found")

    return AnalysisContext(
        flight=_flight_context_from_bundle(bundle, repository),
        notams=_build_notams(repository.fetch_notams(job_id)),
    )
