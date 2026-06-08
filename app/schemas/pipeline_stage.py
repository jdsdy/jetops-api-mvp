import re
from typing import Literal

from pydantic import BaseModel

from app.schemas.flight import FlightData, PlanSource
from app.schemas.notam import RawNotam

StageName = Literal["pdf_extraction", "flight_data_parse", "notam_parse"]

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
