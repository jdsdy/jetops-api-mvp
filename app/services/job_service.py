from uuid import UUID

from storage3.exceptions import StorageApiError
from supabase_auth.types import User

from app.core.errors import JobStepError, extract_error_message
from app.repositories.job_repository import JobRepository
from app.schemas.job import CreateJobRequest
from app.services.storage_path import validate_storage_path

PROCESSING_EXTRACTION = "processing_extraction"


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def create_job(self, request: CreateJobRequest, user: User) -> UUID:
        validate_storage_path(
            request.storage_path,
            request.organisation_id,
            request.flight_id,
            request.flight_plan_id,
        )

        job_id = self._repository.create_job(
            flight_plan_id=request.flight_plan_id,
            organisation_id=request.organisation_id,
            triggered_by=user.id,
            status=PROCESSING_EXTRACTION,
        )

        try:
            self._repository.verify_flight_plan_pdf(request.storage_path)
        except Exception as error:
            error_message = extract_error_message(error)
            self._repository.mark_failed(job_id, error_message)
            status_code = 404 if _is_not_found_error(error) else 500
            raise JobStepError(job_id, status_code, error_message) from error

        return job_id


def _is_not_found_error(error: Exception) -> bool:
    if isinstance(error, FileNotFoundError):
        return True

    if isinstance(error, StorageApiError):
        status = getattr(error, "status", None)
        if status in (404, "404"):
            return True

    message = extract_error_message(error).lower()
    return "not found" in message or "404" in message
