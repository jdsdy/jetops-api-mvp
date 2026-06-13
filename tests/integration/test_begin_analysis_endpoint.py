from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_authenticated_user, verify_api_key
from app.api.rate_limit import rate_limit_begin_analysis
from app.api.v1.endpoints.jobs import get_analysis_service
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.analysis_context import BeginAnalysisResponse
from app.schemas.job import BeginAnalysisRequest
from app.services.analysis_service import AnalysisService
from tests.conftest import FLIGHT_ID, ORG_ID, PLAN_ID, auth_headers


def valid_begin_analysis_payload(job_id=None) -> dict[str, str]:
    return {
        "organisation_id": str(ORG_ID),
        "flight_id": str(FLIGHT_ID),
        "flight_plan_id": str(PLAN_ID),
        "job_id": str(job_id or uuid4()),
    }


@pytest.fixture
def mock_analysis_service() -> MagicMock:
    return MagicMock(spec=AnalysisService)


@pytest.fixture
def analysis_client(
    test_settings: Settings,
    mock_user,
    mock_analysis_service: MagicMock,
) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user
    app.dependency_overrides[get_analysis_service] = lambda: mock_analysis_service
    app.dependency_overrides[rate_limit_begin_analysis] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_begin_analysis_returns_response_begun_and_schedules_background_task(
    analysis_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    job_id = uuid4()
    mock_analysis_service.begin_analysis.return_value = BeginAnalysisResponse()

    with patch("app.api.v1.endpoints.jobs.run_analysis_task") as mock_task:
        response = analysis_client.post(
            "/v1/jobs/analysis",
            json=valid_begin_analysis_payload(job_id),
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"response_begun": True}
    mock_analysis_service.begin_analysis.assert_called_once()
    call_request = mock_analysis_service.begin_analysis.call_args.args[0]
    assert isinstance(call_request, BeginAnalysisRequest)
    assert call_request.job_id == job_id
    mock_task.assert_called_once_with(job_id, PLAN_ID)


def test_begin_analysis_wrong_status_returns_400(
    analysis_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    mock_analysis_service.begin_analysis.side_effect = ValueError(
        "Job is not awaiting confirmation"
    )

    response = analysis_client.post(
        "/v1/jobs/analysis",
        json=valid_begin_analysis_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Job is not awaiting confirmation"


def test_begin_analysis_missing_job_returns_404(
    analysis_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    mock_analysis_service.begin_analysis.side_effect = LookupError("Analysis job not found")

    response = analysis_client.post(
        "/v1/jobs/analysis",
        json=valid_begin_analysis_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 404


def test_begin_analysis_invalid_body_returns_422(analysis_client: TestClient) -> None:
    payload = valid_begin_analysis_payload()
    del payload["job_id"]

    response = analysis_client.post(
        "/v1/jobs/analysis",
        json=payload,
        headers=auth_headers(),
    )

    assert response.status_code == 422
