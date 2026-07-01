from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.integration_dependencies import get_api_key_repository
from app.api.rate_limit import rate_limit_integration_poll
from app.api.v1.integration.endpoints.analysis import get_integration_analysis_service
from app.core.config import Settings, get_settings
from app.main import app
from app.repositories.job_repository import ACCEPTED
from app.schemas.integration_analysis import (
    IntegrationAnalysisListResponse,
    IntegrationAnalysisPollResponse,
    IntegrationAnalysisStatus,
    IntegrationAnalysisSubmitResponse,
    IntegrationErrorCode,
)
from app.services.integration.integration_analysis_service import (
    IntegrationAnalysisService,
    build_poll_url,
)

from tests.conftest import auth_headers, integration_auth_headers, valid_job_payload
from tests.unit.test_integration_analysis_submission import (
    minimal_valid_payload,
    notam_payload,
)

API_CLIENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
STARTED_AT = datetime(2025, 1, 15, 10, 30, tzinfo=UTC)


@pytest.fixture
def mock_analysis_service() -> MagicMock:
    return MagicMock(spec=IntegrationAnalysisService)


@pytest.fixture
def integration_client(
    test_settings: Settings,
    mock_analysis_service: MagicMock,
) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_integration_analysis_service] = (
        lambda: mock_analysis_service
    )
    mock_api_key_repository = MagicMock()
    mock_api_key_repository.lookup_by_hash.return_value = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "api_client_id": str(API_CLIENT_ID),
        "is_active": True,
        "revoked_at": None,
        "expires_at": None,
        "api_clients": {
            "is_active": True,
            "organisation_id": None,
        },
    }
    app.dependency_overrides[get_api_key_repository] = lambda: mock_api_key_repository
    app.dependency_overrides[rate_limit_integration_poll] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_submit_analysis_returns_401_without_authorization() -> None:
    settings = Settings(
        API_KEY="test-api-key",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="test-secret-key",
        ANTHROPIC_API_KEY="test-anthropic-key",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="test-upstash-token",
        BETA_SIGNUP_CODE="test-signup-code",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        response = client.post("/v1/analysis", json=minimal_valid_payload())

    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_submit_analysis_returns_400_for_malformed_json(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/v1/analysis",
        content=b'{"flight": {"departure_airfield": {"icao": "YSSY",},}}',
        headers={
            **integration_auth_headers(),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": IntegrationErrorCode.INVALID_REQUEST_FORMAT,
            "message": "Malformed JSON body",
        }
    }


def test_submit_analysis_returns_400_for_invalid_body(
    integration_client: TestClient,
) -> None:
    payload = minimal_valid_payload()
    del payload["flight"]["cruise_level"]

    response = integration_client.post(
        "/v1/analysis",
        json=payload,
        headers=integration_auth_headers(),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == IntegrationErrorCode.INVALID_REQUEST_FORMAT
    assert "cruise_level" in body["error"]["message"]


def test_submit_analysis_returns_413_when_notam_limit_exceeded(
    integration_client: TestClient,
) -> None:
    payload = minimal_valid_payload()
    payload["notams"] = [notam_payload(index) for index in range(801)]

    response = integration_client.post(
        "/v1/analysis",
        json=payload,
        headers=integration_auth_headers(),
    )

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == IntegrationErrorCode.INVALID_REQUEST_FORMAT
    assert "800" in body["error"]["message"]


def test_submit_analysis_returns_job_response_and_schedules_background_task(
    integration_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    job_id = uuid4()
    mock_analysis_service.submit_analysis.return_value = (
        IntegrationAnalysisSubmitResponse(
            job_id=job_id,
            status=IntegrationAnalysisStatus.ACCEPTED,
            poll_url=build_poll_url(job_id),
            started_at=STARTED_AT,
        )
    )

    with patch(
        "app.api.v1.integration.endpoints.analysis.run_integration_analysis"
    ) as mock_task:
        response = integration_client.post(
            "/v1/analysis",
            json=minimal_valid_payload(),
            headers=integration_auth_headers(),
        )

    assert response.status_code == 201
    assert response.json() == {
        "job_id": str(job_id),
        "status": ACCEPTED,
        "poll_url": f"/v1/analysis/{job_id}",
        "started_at": STARTED_AT.isoformat().replace("+00:00", "Z"),
    }
    mock_analysis_service.submit_analysis.assert_called_once()
    mock_task.assert_called_once()


def test_get_analysis_returns_job_status(
    integration_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    job_id = uuid4()
    mock_analysis_service.get_job_status.return_value = IntegrationAnalysisPollResponse(
        job_id=job_id,
        status=IntegrationAnalysisStatus.ACCEPTED,
        started_at=STARTED_AT,
    )

    response = integration_client.get(
        f"/v1/analysis/{job_id}",
        headers=integration_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(job_id),
        "status": ACCEPTED,
        "started_at": STARTED_AT.isoformat().replace("+00:00", "Z"),
        "stage": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }


def test_get_analysis_returns_404_when_job_missing(
    integration_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    mock_analysis_service.get_job_status.return_value = None

    response = integration_client.get(
        f"/v1/analysis/{uuid4()}",
        headers=integration_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis job not found"}


def test_list_analyses_returns_paginated_jobs(
    integration_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    job_id = uuid4()
    mock_analysis_service.list_analyses.return_value = IntegrationAnalysisListResponse(
        jobs=[],
        pagination={"total": 0, "limit": 20, "offset": 0},
    )

    response = integration_client.get(
        "/v1/analysis",
        params={"limit": 20, "offset": 0, "status": "complete"},
        headers=integration_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [],
        "pagination": {"total": 0, "limit": 20, "offset": 0},
    }
    mock_analysis_service.list_analyses.assert_called_once()


def test_list_analyses_returns_400_for_invalid_date_range(
    integration_client: TestClient,
    mock_analysis_service: MagicMock,
) -> None:
    mock_analysis_service.list_analyses.side_effect = ValueError(
        "from must be before or equal to to"
    )

    response = integration_client.get(
        "/v1/analysis",
        params={
            "from": "2025-02-01T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
        },
        headers=integration_auth_headers(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == IntegrationErrorCode.INVALID_REQUEST_FORMAT


def test_app_routes_do_not_require_integration_bearer_for_jobs(
    test_settings: Settings,
    mock_user,
    mock_job_service: MagicMock,
) -> None:
    from app.api.dependencies import get_authenticated_user, verify_api_key
    from app.api.rate_limit import rate_limit_begin_analysis, rate_limit_create_job
    from app.api.v1.app.endpoints.jobs import get_job_service

    job_id = uuid4()
    mock_job_service.create_job.return_value = job_id

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user
    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    app.dependency_overrides[rate_limit_create_job] = lambda: None
    app.dependency_overrides[rate_limit_begin_analysis] = lambda: None

    with (
        patch("app.api.v1.app.endpoints.jobs.run_extraction"),
        TestClient(app) as client,
    ):
        response = client.post(
            "/v1/app/jobs",
            json=valid_job_payload(),
            headers=auth_headers(),
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
