import re
from typing import Literal

from pydantic import BaseModel

from app.schemas.analysis_context import AircraftContext, AirfieldContext, FlightContext
from app.schemas.flight import FlightData, PlanSource
from app.schemas.notam import RawNotam
from app.schemas.notam_analysis import BatchAnalysisResult

StageName = Literal[
    "pdf_extraction",
    "flight_data_parse",
    "notam_parse",
    "build_context_object",
    "notam_analysis",
]

_CONDENSED_NOTAM_ID = re.compile(r"^[A-Z]{2,4} \d{1,2}/\d{2,4}\b")


class PdfExtractionMetadata(BaseModel):
    page_count: int
    file_size_bytes: int
    download_url: str


class FlightDataParseMetadata(BaseModel):
    fields_extracted: list[str]
    fields_missing: list[str]
    source_type: PlanSource


class NotamParseMetadata(BaseModel):
    notams_found: int
    aerodromes_found: list[str]
    multiformat_notams: bool
    parse_failures: int
    source_type: PlanSource


class BuildContextObjectMetadata(BaseModel):
    departure_airfield_full_data_found: bool
    arrival_airfield_full_data_found: bool
    aircraft_full_data_found: bool


class NotamAnalysisMetadata(BaseModel):
    batches: int
    notams_analysed: int
    model: str
    batch_sizes: list[int]
    token_limit_hit: bool
    slowest_batch_ms: int
    input_tokens: int
    output_tokens: int
    est_cost: float


def _airfield_full_data_found(airfield: AirfieldContext) -> bool:
    return airfield.iso_country is not None and airfield.length_ft is not None


def _aircraft_full_data_found(aircraft: AircraftContext) -> bool:
    return aircraft.icao_wtc is not None


def build_context_object_metadata(flight: FlightContext) -> BuildContextObjectMetadata:
    return BuildContextObjectMetadata(
        departure_airfield_full_data_found=_airfield_full_data_found(
            flight.departure_airfield
        ),
        arrival_airfield_full_data_found=_airfield_full_data_found(
            flight.arrival_airfield
        ),
        aircraft_full_data_found=_aircraft_full_data_found(flight.aircraft),
    )


def build_notam_analysis_metadata(
    batch_result: BatchAnalysisResult,
    *,
    input_cost_per_m: float,
    output_cost_per_m: float,
) -> NotamAnalysisMetadata:
    input_tokens = batch_result.input_tokens
    output_tokens = batch_result.output_tokens
    est_cost = (
        input_tokens * input_cost_per_m / 1_000_000
        + output_tokens * output_cost_per_m / 1_000_000
    )
    return NotamAnalysisMetadata(
        batches=batch_result.batches,
        notams_analysed=batch_result.notams_analysed,
        model=batch_result.model,
        batch_sizes=batch_result.batch_sizes,
        token_limit_hit=batch_result.token_limit_hit,
        slowest_batch_ms=batch_result.slowest_batch_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        est_cost=est_cost,
    )


def build_flight_parse_metadata(flight_data: FlightData) -> FlightDataParseMetadata:
    extracted: list[str] = []
    missing: list[str] = []
    for name, value in flight_data.model_dump().items():
        if value is None:
            missing.append(name)
        else:
            extracted.append(name)
    return FlightDataParseMetadata(
        fields_extracted=extracted,
        fields_missing=missing,
        source_type=flight_data.source_app,
    )


def build_notam_parse_metadata(
    notams: list[RawNotam],
    source_type: PlanSource,
) -> NotamParseMetadata:
    has_standard = any(notam.q for notam in notams)
    has_condensed = any(
        notam.q is None and _CONDENSED_NOTAM_ID.match(notam.notam_id) for notam in notams
    )
    return NotamParseMetadata(
        notams_found=len(notams),
        aerodromes_found=sorted({notam.a for notam in notams if notam.a}),
        multiformat_notams=source_type == "foreflight" and has_standard and has_condensed,
        parse_failures=0,
        source_type=source_type,
    )
