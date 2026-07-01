from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.repositories.analysis_context_repository import AnalysisContextRepository
from app.repositories.job_repository import (
    AWAITING_CONFIRMATION,
    PROCESSING_ANALYSIS,
    JobRepository,
)
from app.schemas.job import BeginAnalysisRequest
from app.services.analysis.analysis_service import AnalysisService
from tests.conftest import FLIGHT_ID, ORG_ID, PLAN_ID


def _analysis_request(job_id=None) -> BeginAnalysisRequest:
    return BeginAnalysisRequest(
        organisation_id=ORG_ID,
        flight_id=FLIGHT_ID,
        flight_plan_id=PLAN_ID,
        job_id=job_id or uuid4(),
    )


def test_begin_analysis_updates_status_and_returns_response_begun() -> None:
    request = _analysis_request()

    mock_job_repo = MagicMock(spec=JobRepository)
    mock_job_repo.get_job.return_value = {
        "id": str(request.job_id),
        "status": AWAITING_CONFIRMATION,
        "flight_plan_id": str(PLAN_ID),
        "organisation_id": str(ORG_ID),
        "flight_plans": {"flight_id": str(FLIGHT_ID)},
    }
    mock_context_repo = MagicMock(spec=AnalysisContextRepository)

    with patch(
        "app.services.analysis.analysis_service.build_flight_context",
    ) as mock_build:
        service = AnalysisService(mock_job_repo, mock_context_repo)
        result = service.begin_analysis(request)

    mock_job_repo.update_status.assert_called_once_with(
        request.job_id, PROCESSING_ANALYSIS
    )
    mock_build.assert_called_once_with(request.job_id, mock_context_repo)
    assert result.response_begun is True


def test_begin_analysis_rejects_wrong_status() -> None:
    request = _analysis_request()
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_job_repo.get_job.return_value = {
        "id": str(request.job_id),
        "status": PROCESSING_ANALYSIS,
        "flight_plan_id": str(PLAN_ID),
        "organisation_id": str(ORG_ID),
        "flight_plans": {"flight_id": str(FLIGHT_ID)},
    }

    service = AnalysisService(mock_job_repo, MagicMock(spec=AnalysisContextRepository))

    with pytest.raises(ValueError, match="not awaiting confirmation"):
        service.begin_analysis(request)


def test_begin_analysis_raises_when_job_missing() -> None:
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_job_repo.get_job.return_value = None

    service = AnalysisService(mock_job_repo, MagicMock(spec=AnalysisContextRepository))

    with pytest.raises(LookupError, match="Analysis job not found"):
        service.begin_analysis(_analysis_request())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("organisation_id", uuid4()),
        ("flight_id", uuid4()),
        ("flight_plan_id", uuid4()),
    ],
)
def test_begin_analysis_rejects_mismatched_request(field: str, value) -> None:
    request = _analysis_request()
    mismatched = request.model_copy(update={field: value})
    mock_job_repo = MagicMock(spec=JobRepository)
    mock_job_repo.get_job.return_value = {
        "id": str(request.job_id),
        "status": AWAITING_CONFIRMATION,
        "flight_plan_id": str(PLAN_ID),
        "organisation_id": str(ORG_ID),
        "flight_plans": {"flight_id": str(FLIGHT_ID)},
    }

    service = AnalysisService(mock_job_repo, MagicMock(spec=AnalysisContextRepository))

    with pytest.raises(ValueError, match=f"Job does not match {field}"):
        service.begin_analysis(mismatched)
