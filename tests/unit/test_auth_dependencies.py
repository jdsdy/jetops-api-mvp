from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

from tests.conftest import TEST_API_KEY, auth_headers, valid_job_payload


@pytest.fixture
def auth_client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_missing_api_key_returns_401(auth_client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-jwt"}
    response = auth_client.post("/v1/app/jobs", json=valid_job_payload(), headers=headers)
    assert response.status_code == 401


def test_wrong_api_key_returns_401(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/v1/app/jobs",
        json=valid_job_payload(),
        headers=auth_headers(api_key="wrong-key"),
    )
    assert response.status_code == 401


def test_missing_bearer_token_returns_401(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/v1/app/jobs",
        json=valid_job_payload(),
        headers={"x-api-key": TEST_API_KEY},
    )
    assert response.status_code == 401


def test_invalid_bearer_token_returns_401(auth_client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.auth.get_user.side_effect = Exception("invalid jwt")

    with patch("app.api.dependencies.get_supabase_client", return_value=mock_client):
        response = auth_client.post(
            "/v1/app/jobs",
            json=valid_job_payload(),
            headers=auth_headers(),
        )

    assert response.status_code == 401
