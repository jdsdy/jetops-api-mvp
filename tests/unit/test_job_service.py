from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from storage3.exceptions import StorageApiError

from app.core.errors import JobStepError
from app.repositories.job_repository import JobRepository
from app.schemas.job import CreateJobRequest
from app.services.jobs.job_service import JobService
from tests.conftest import (
    FLIGHT_ID,
    ORG_ID,
    PLAN_ID,
    STORAGE_PATH,
)


@pytest.fixture
def mock_repository() -> MagicMock:
    return MagicMock(spec=JobRepository)


@pytest.fixture
def job_service(mock_repository: MagicMock) -> JobService:
    return JobService(mock_repository)


@pytest.fixture
def create_request() -> CreateJobRequest:
    return CreateJobRequest(
        organisation_id=ORG_ID,
        flight_id=FLIGHT_ID,
        flight_plan_id=PLAN_ID,
        storage_path=STORAGE_PATH,
    )


def test_storage_download_failure_marks_job_failed(
    job_service: JobService,
    mock_repository: MagicMock,
    create_request: CreateJobRequest,
    mock_user,
) -> None:
    job_id = uuid4()
    mock_repository.create_job.return_value = job_id
    mock_repository.verify_flight_plan_pdf.side_effect = StorageApiError(
        "Object not found",
        "404",
        404,
    )

    with pytest.raises(JobStepError) as exc_info:
        job_service.create_job(create_request, mock_user)

    assert exc_info.value.job_id == job_id
    assert exc_info.value.status_code == 404
    mock_repository.mark_failed.assert_called_once_with(job_id, "Object not found")


def test_unexpected_error_marks_job_failed(
    job_service: JobService,
    mock_repository: MagicMock,
    create_request: CreateJobRequest,
    mock_user,
) -> None:
    job_id = uuid4()
    mock_repository.create_job.return_value = job_id
    mock_repository.verify_flight_plan_pdf.side_effect = RuntimeError(
        "unexpected failure"
    )

    with pytest.raises(JobStepError) as exc_info:
        job_service.create_job(create_request, mock_user)

    assert exc_info.value.status_code == 500
    mock_repository.mark_failed.assert_called_once_with(
        job_id,
        "unexpected failure",
    )


def test_successful_flow_returns_job_id(
    job_service: JobService,
    mock_repository: MagicMock,
    create_request: CreateJobRequest,
    mock_user,
) -> None:
    job_id = uuid4()
    mock_repository.create_job.return_value = job_id

    result = job_service.create_job(create_request, mock_user)

    assert result == job_id
    mock_repository.verify_flight_plan_pdf.assert_called_once_with(STORAGE_PATH)
    mock_repository.mark_failed.assert_not_called()
