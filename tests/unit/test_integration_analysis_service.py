from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.repositories.job_repository import ACCEPTED, JobRepository
from app.schemas.integration_analysis import (
    IntegrationAnalysisListParams,
    IntegrationAnalysisRequest,
    IntegrationAnalysisStatus,
)
from app.services.integration.integration_analysis_service import (
    IntegrationAnalysisService,
    build_poll_url,
)
from tests.unit.test_integration_analysis_submission import minimal_valid_payload

API_CLIENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
STARTED_AT = datetime(2025, 1, 15, 10, 30, tzinfo=UTC)


def test_build_poll_url() -> None:
    job_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert build_poll_url(job_id) == f"/v1/analysis/{job_id}"


def test_submit_analysis_creates_job_and_returns_response() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.create_integration_job.return_value = (job_id, STARTED_AT)
    service = IntegrationAnalysisService(mock_repository)
    request = IntegrationAnalysisRequest.model_validate(minimal_valid_payload())

    response = service.submit_analysis(request, API_CLIENT_ID)

    mock_repository.create_integration_job.assert_called_once_with(
        api_client_id=API_CLIENT_ID,
        status=ACCEPTED,
        departure_icao="YSSY",
        arrival_icao="YPPH",
    )
    assert response.job_id == job_id
    assert response.status == IntegrationAnalysisStatus.ACCEPTED
    assert response.poll_url == build_poll_url(job_id)
    assert response.started_at == STARTED_AT


def test_get_job_status_returns_none_when_missing() -> None:
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.get_integration_job.return_value = None
    service = IntegrationAnalysisService(mock_repository)

    assert service.get_job_status(uuid4(), API_CLIENT_ID) is None


def test_get_job_status_returns_none_for_other_api_client() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.get_integration_job.return_value = {
        "id": str(job_id),
        "status": ACCEPTED,
        "api_client_id": str(uuid4()),
        "started_at": STARTED_AT.isoformat(),
    }
    service = IntegrationAnalysisService(mock_repository)

    assert service.get_job_status(job_id, API_CLIENT_ID) is None


def test_get_job_status_returns_accepted_response() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.get_integration_job.return_value = {
        "id": str(job_id),
        "status": ACCEPTED,
        "api_client_id": str(API_CLIENT_ID),
        "started_at": STARTED_AT.isoformat(),
    }
    service = IntegrationAnalysisService(mock_repository)

    response = service.get_job_status(job_id, API_CLIENT_ID)

    assert response is not None
    assert response.job_id == job_id
    assert response.status == IntegrationAnalysisStatus.ACCEPTED
    assert response.started_at == STARTED_AT


def test_get_job_status_returns_processing_response_with_stage() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.get_integration_job.return_value = {
        "id": str(job_id),
        "status": "processing",
        "stage": "classification",
        "api_client_id": str(API_CLIENT_ID),
        "started_at": STARTED_AT.isoformat(),
    }
    service = IntegrationAnalysisService(mock_repository)

    response = service.get_job_status(job_id, API_CLIENT_ID)

    assert response is not None
    assert response.status == IntegrationAnalysisStatus.PROCESSING
    assert response.stage is not None
    assert response.stage.value == "classification"


def test_get_job_status_returns_complete_response_with_results() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_analysed_repository = MagicMock()
    mock_repository.get_integration_job.return_value = {
        "id": str(job_id),
        "status": "complete",
        "stage": "complete",
        "api_client_id": str(API_CLIENT_ID),
        "started_at": STARTED_AT.isoformat(),
        "completed_at": "2025-01-15T10:31:45+00:00",
    }
    mock_analysed_repository.fetch_integration_results.return_value = [
        {"notam_id": "A1234/25", "category": 1, "summary": "Runway closed"},
        {"notam_id": "B1234/25", "category": 2, "summary": "Taxiway work"},
    ]
    service = IntegrationAnalysisService(mock_repository, mock_analysed_repository)

    response = service.get_job_status(job_id, API_CLIENT_ID)

    assert response is not None
    assert response.status == IntegrationAnalysisStatus.COMPLETE
    assert response.stage is not None
    assert response.stage.value == "complete"
    assert response.result is not None
    assert response.result.summary.total_notams == 2
    assert response.result.summary.category_1 == 1
    assert response.result.summary.category_2 == 1
    assert len(response.result.notams) == 2


def test_get_job_status_returns_failed_response_with_error() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.get_integration_job.return_value = {
        "id": str(job_id),
        "status": "failed",
        "api_client_id": str(API_CLIENT_ID),
        "started_at": STARTED_AT.isoformat(),
        "completed_at": "2025-01-15T10:31:12+00:00",
        "error_code": "internal_error",
        "error_message": "Something broke",
    }
    service = IntegrationAnalysisService(mock_repository)

    response = service.get_job_status(job_id, API_CLIENT_ID)

    assert response is not None
    assert response.status == IntegrationAnalysisStatus.FAILED
    assert response.error is not None
    assert response.error.code.value == "internal_error"
    assert response.error.message == "Something broke"


def test_list_analyses_returns_paginated_jobs() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.list_integration_jobs.return_value = (
        [
            {
                "id": str(job_id),
                "status": "complete",
                "started_at": STARTED_AT.isoformat(),
                "completed_at": "2025-01-15T10:31:45+00:00",
                "departure_icao": "YPPH",
                "arrival_icao": "YMML",
                "total_notams": 47,
                "cat1_notams": 3,
                "cat2_notams": 12,
                "cat3_notams": 32,
            }
        ],
        134,
    )
    service = IntegrationAnalysisService(mock_repository)

    response = service.list_analyses(
        IntegrationAnalysisListParams(limit=20, offset=0),
        API_CLIENT_ID,
    )

    assert len(response.jobs) == 1
    job = response.jobs[0]
    assert job.job_id == job_id
    assert job.status == IntegrationAnalysisStatus.COMPLETE
    assert job.flight.departure_icao == "YPPH"
    assert job.summary is not None
    assert job.summary.total_notams == 47
    assert job.summary.category_1 == 3
    assert job.summary.category_2 == 12
    assert job.summary.category_3 == 32
    assert response.pagination.total == 134
    assert response.pagination.limit == 20
    assert response.pagination.offset == 0


def test_list_analyses_omits_summary_for_failed_jobs() -> None:
    job_id = uuid4()
    mock_repository = MagicMock(spec=JobRepository)
    mock_repository.list_integration_jobs.return_value = (
        [
            {
                "id": str(job_id),
                "status": "failed",
                "started_at": STARTED_AT.isoformat(),
                "completed_at": None,
                "departure_icao": "YSSY",
                "arrival_icao": "YBBN",
                "total_notams": None,
                "cat1_notams": None,
            }
        ],
        1,
    )
    service = IntegrationAnalysisService(mock_repository)

    response = service.list_analyses(
        IntegrationAnalysisListParams(),
        API_CLIENT_ID,
    )

    assert response.jobs[0].summary is None
    assert response.jobs[0].completed_at is None


def test_list_analyses_rejects_invalid_date_range() -> None:
    service = IntegrationAnalysisService(MagicMock(spec=JobRepository))

    with pytest.raises(ValueError, match="from must be before"):
        service.list_analyses(
            IntegrationAnalysisListParams(
                from_=datetime(2025, 2, 1, tzinfo=UTC),
                to=datetime(2025, 1, 1, tzinfo=UTC),
            ),
            API_CLIENT_ID,
        )
