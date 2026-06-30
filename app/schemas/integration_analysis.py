from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_INTEGRATION_NOTAMS = 800
DEFAULT_INTEGRATION_LIST_LIMIT = 20
MAX_INTEGRATION_LIST_LIMIT = 100


class IntegrationAnalysisStatus(StrEnum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class IntegrationAnalysisStage(StrEnum):
    TOPIC_IDENTIFICATION = "topic_identification"
    CLASSIFICATION = "classification"
    RETRY = "retry"
    COMPLETE = "complete"


class IntegrationErrorCode(StrEnum):
    INVALID_REQUEST_FORMAT = "invalid_request_format"
    UNSUPPORTED_ICAO = "unsupported_icao"
    INTERNAL_ERROR = "internal_error"
    ANALYSIS_ERROR = "analysis_error"
    TIMEOUT = "timeout"


class IntegrationAirfieldRequest(BaseModel):
    icao: str
    rwy: str | None = None
    iso_country: str | None = None
    length_ft: float | None = None
    length_m: float | None = None
    width_ft: float | None = None
    width_m: float | None = None
    surface_type: str | None = None
    lighted: bool | None = None


class IntegrationAircraftRequest(BaseModel):
    make: str
    model: str
    seats: int | None = None
    rnav_equipped: bool
    icao_wtc: str
    weight_class: str
    wingspan_ft: float | None = None
    wingspan_m: float | None = None
    length_ft: float | None = None
    length_m: float | None = None
    instrument_approach_category: str
    aircraft_design_group: str


class IntegrationFlightRequest(BaseModel):
    departure_airfield: IntegrationAirfieldRequest
    arrival_airfield: IntegrationAirfieldRequest
    alternate_airfield_icao: str | None = None
    planned_dept_time: datetime
    planned_arr_time: datetime
    route: str | None = None
    cruise_level: str
    aircraft: IntegrationAircraftRequest


class IntegrationNotamRequest(BaseModel):
    id: str
    title: str | None = None
    q: str | None = None
    a: str
    b: str
    c: str
    d: str | None = None
    e: str
    f: str | None = None
    g: str | None = None


class IntegrationAnalysisRequest(BaseModel):
    flight: IntegrationFlightRequest
    notams: list[IntegrationNotamRequest]


class IntegrationAnalysisError(BaseModel):
    code: IntegrationErrorCode
    message: str


class IntegrationAnalysisSubmitErrorResponse(BaseModel):
    error: IntegrationAnalysisError


class IntegrationAnalysisSubmitResponse(BaseModel):
    job_id: UUID
    status: IntegrationAnalysisStatus
    poll_url: str
    started_at: datetime


class IntegrationAnalysisNotamResult(BaseModel):
    notam_id: str
    category: int
    summary: str


class IntegrationAnalysisResultSummary(BaseModel):
    total_notams: int
    priority_1: int
    priority_2: int
    priority_3: int


class IntegrationAnalysisResult(BaseModel):
    summary: IntegrationAnalysisResultSummary
    notams: list[IntegrationAnalysisNotamResult]


class IntegrationAnalysisPollResponse(BaseModel):
    job_id: UUID
    status: IntegrationAnalysisStatus
    started_at: datetime
    stage: IntegrationAnalysisStage | None = None
    completed_at: datetime | None = None
    result: IntegrationAnalysisResult | None = None
    error: IntegrationAnalysisError | None = None


class IntegrationAnalysisListParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    limit: int = Field(default=DEFAULT_INTEGRATION_LIST_LIMIT, ge=1, le=MAX_INTEGRATION_LIST_LIMIT)
    offset: int = Field(default=0, ge=0)
    status: IntegrationAnalysisStatus | None = None
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None


class IntegrationAnalysisListJobFlight(BaseModel):
    departure_icao: str
    arrival_icao: str


class IntegrationAnalysisListJobSummary(BaseModel):
    total_notams: int
    category_1: int
    category_2: int
    category_3: int


class IntegrationAnalysisListJobItem(BaseModel):
    job_id: UUID
    status: IntegrationAnalysisStatus
    submitted_at: datetime
    completed_at: datetime | None = None
    flight: IntegrationAnalysisListJobFlight
    summary: IntegrationAnalysisListJobSummary | None = None


class IntegrationAnalysisListPagination(BaseModel):
    total: int
    limit: int
    offset: int


class IntegrationAnalysisListResponse(BaseModel):
    jobs: list[IntegrationAnalysisListJobItem]
    pagination: IntegrationAnalysisListPagination
