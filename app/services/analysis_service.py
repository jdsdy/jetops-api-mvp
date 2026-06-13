from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.repositories.job_repository import (
    AWAITING_CONFIRMATION,
    PROCESSING_ANALYSIS,
    JobRepository,
)
from app.schemas.analysis_context import BeginAnalysisResponse
from app.schemas.job import BeginAnalysisRequest
from app.services.analysis_context import build_flight_context


class AnalysisService:
    def __init__(
        self,
        job_repository: JobRepository,
        context_repository: AnalysisContextRepository,
    ) -> None:
        self._job_repository = job_repository
        self._context_repository = context_repository

    def begin_analysis(self, request: BeginAnalysisRequest) -> BeginAnalysisResponse:
        job = self._job_repository.get_job(request.job_id)
        if not job:
            raise LookupError("Analysis job not found")
        _validate_job_request(job, request)
        if job["status"] != AWAITING_CONFIRMATION:
            raise ValueError("Job is not awaiting confirmation")

        build_flight_context(request.job_id, self._context_repository)
        self._job_repository.update_status(request.job_id, PROCESSING_ANALYSIS)
        return BeginAnalysisResponse()


def _validate_job_request(job: dict, request: BeginAnalysisRequest) -> None:
    if str(job["organisation_id"]) != str(request.organisation_id):
        raise ValueError("Job does not match organisation_id")
    if str(job["flight_plan_id"]) != str(request.flight_plan_id):
        raise ValueError("Job does not match flight_plan_id")
    flight_id = job["flight_plans"]["flight_id"]
    if str(flight_id) != str(request.flight_id):
        raise ValueError("Job does not match flight_id")
