import re
from typing import Literal

from pydantic import BaseModel

from app.schemas.analysis_context import AircraftContext, AirfieldContext, FlightContext
from app.schemas.flight import FlightData, PlanSource
from app.schemas.notam import RawNotam
from app.schemas.notam_analysis import AnalysisJobResult, BatchAnalysisResult

StageName = Literal[
    "pdf_extraction",
    "flight_data_parse",
    "notam_parse",
    "notam_topic_classification",
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


class NotamTopicClassificationMetadata(BaseModel):
    notams_classified: int
    topic_counts: dict[str, int]
    misc_count: int
    classification_errors: int


class BuildContextObjectMetadata(BaseModel):
    departure_airfield_full_data_found: bool
    arrival_airfield_full_data_found: bool
    aircraft_full_data_found: bool


class NotamAnalysisMetadata(BaseModel):
    total_notams: int
    heuristically_classified_notams: int
    summarisation_batches: int
    categorisation_batches: int
    summarisation_batch_sizes: list[int]
    categorisation_batch_sizes: list[int]
    token_limit_hit: bool
    slowest_batch_ms: int
    summarize_input_tokens: int
    categorize_input_tokens: int
    summarize_output_tokens: int
    categorize_output_tokens: int
    est_cost: float
    retried_summary_notam_ids: list[str] = []
    retried_category_notam_ids: list[str] = []


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
    job_result: AnalysisJobResult,
    *,
    categorize_input_cost_per_m: float,
    categorize_output_cost_per_m: float,
    summarize_input_cost_per_m: float,
    summarize_output_cost_per_m: float,
    retried_category_notam_ids: list[str] | None = None,
    retried_summary_notam_ids: list[str] | None = None,
) -> NotamAnalysisMetadata:
    category_result = job_result.category_result
    summary_result = job_result.summary_result
    categorize_input_tokens = category_result.input_tokens
    categorize_output_tokens = category_result.output_tokens
    summarize_input_tokens = summary_result.input_tokens
    summarize_output_tokens = summary_result.output_tokens
    est_cost = (
        categorize_input_tokens * categorize_input_cost_per_m / 1_000_000
        + categorize_output_tokens * categorize_output_cost_per_m / 1_000_000
        + summarize_input_tokens * summarize_input_cost_per_m / 1_000_000
        + summarize_output_tokens * summarize_output_cost_per_m / 1_000_000
    )
    slowest_batch_ms = max(
        category_result.slowest_batch_ms,
        summary_result.slowest_batch_ms,
    )
    return NotamAnalysisMetadata(
        total_notams=len(job_result.results),
        heuristically_classified_notams=job_result.heuristic_category_count,
        summarisation_batches=summary_result.batches,
        categorisation_batches=category_result.batches,
        summarisation_batch_sizes=summary_result.batch_sizes,
        categorisation_batch_sizes=category_result.batch_sizes,
        token_limit_hit=job_result.token_limit_hit,
        slowest_batch_ms=slowest_batch_ms,
        categorize_input_tokens=categorize_input_tokens,
        categorize_output_tokens=categorize_output_tokens,
        summarize_input_tokens=summarize_input_tokens,
        summarize_output_tokens=summarize_output_tokens,
        est_cost=est_cost,
        retried_category_notam_ids=retried_category_notam_ids or [],
        retried_summary_notam_ids=retried_summary_notam_ids or [],
    )


def build_notam_analysis_metadata_from_batch(
    batch_result: BatchAnalysisResult,
    *,
    input_cost_per_m: float,
    output_cost_per_m: float,
    retried_notam_ids: list[str] | None = None,
) -> NotamAnalysisMetadata:
    """Backward-compatible helper for tests that only exercise categorization."""
    input_tokens = batch_result.input_tokens
    output_tokens = batch_result.output_tokens
    est_cost = (
        input_tokens * input_cost_per_m / 1_000_000
        + output_tokens * output_cost_per_m / 1_000_000
    )
    return NotamAnalysisMetadata(
        total_notams=batch_result.notams_analysed,
        heuristically_classified_notams=0,
        summarisation_batches=0,
        categorisation_batches=batch_result.batches,
        summarisation_batch_sizes=[],
        categorisation_batch_sizes=batch_result.batch_sizes,
        token_limit_hit=batch_result.token_limit_hit,
        slowest_batch_ms=batch_result.slowest_batch_ms,
        categorize_input_tokens=input_tokens,
        categorize_output_tokens=output_tokens,
        summarize_input_tokens=0,
        summarize_output_tokens=0,
        est_cost=est_cost,
        retried_category_notam_ids=retried_notam_ids or [],
        retried_summary_notam_ids=[],
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


def build_notam_topic_classification_metadata(
    results: list[tuple[int, str, int]],
    *,
    classification_errors: int = 0,
) -> NotamTopicClassificationMetadata:
    topic_counts: dict[str, int] = {}
    misc_count = 0
    for _row_id, topic, _confidence in results:
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if topic == "MISC":
            misc_count += 1
    return NotamTopicClassificationMetadata(
        notams_classified=len(results),
        topic_counts=topic_counts,
        misc_count=misc_count,
        classification_errors=classification_errors,
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
