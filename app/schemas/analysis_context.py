from datetime import datetime

from pydantic import BaseModel


class AirfieldContext(BaseModel):
    icao: str | None = None
    rwy: str | None = None
    iso_country: str | None = None
    length_ft: float | None = None
    length_m: float | None = None
    width_ft: float | None = None
    width_m: float | None = None
    surface_type: str | None = None
    lighted: bool | None = None


class AircraftContext(BaseModel):
    make: str | None = None
    model: str | None = None
    seats: int | None = None
    rnav_equipped: bool | None = None
    icao_wtc: str | None = None
    weight_class: str | None = None
    wingspan_ft: float | None = None
    wingspan_m: float | None = None
    length_ft: float | None = None
    length_m: float | None = None
    instrument_approach_category: str | None = None
    aircraft_design_group: str | None = None


class FlightContext(BaseModel):
    departure_airfield: AirfieldContext
    arrival_airfield: AirfieldContext
    alternate_airfield_icao: str | None = None
    planned_dept_time: datetime | None = None
    planned_arr_time: datetime | None = None
    route: str | None = None
    cruise_level: str | None = None
    aircraft: AircraftContext


class AnalysisNotam(BaseModel):
    title: str | None = None
    notam_id: str
    q: str | None = None
    a: str | None = None
    b: str | None = None
    c: str | None = None
    d: str | None = None
    e: str | None = None
    f: str | None = None
    g: str | None = None


class AnalysisContext(BaseModel):
    flight: FlightContext
    notams: list[AnalysisNotam]


class BeginAnalysisResponse(BaseModel):
    response_begun: bool = True
