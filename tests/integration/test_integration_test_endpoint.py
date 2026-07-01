from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.integration_dependencies import get_api_key_repository
from app.core.config import Settings, get_settings
from app.main import app

from tests.conftest import (
    auth_headers,
    integration_auth_headers,
    valid_job_payload,
)

API_KEY_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
API_CLIENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
ORG_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def integration_client(test_settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _valid_key_row() -> dict:
    return {
        "id": str(API_KEY_ID),
        "api_client_id": str(API_CLIENT_ID),
        "is_active": True,
        "revoked_at": None,
        "expires_at": None,
        "api_clients": {
            "is_active": True,
            "organisation_id": str(ORG_ID),
        },
    }


def test_integration_test_endpoint_returns_401_without_authorization(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/v1/test")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_integration_test_endpoint_returns_401_for_invalid_key(
    integration_client: TestClient,
) -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.return_value = None
    app.dependency_overrides[get_api_key_repository] = lambda: mock_repository

    response = integration_client.get(
        "/v1/test",
        headers=integration_auth_headers("jops_dev_sk_invalid"),
    )

    app.dependency_overrides.pop(get_api_key_repository, None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_integration_test_endpoint_returns_401_when_lookup_raises(
    integration_client: TestClient,
) -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.side_effect = AttributeError(
        "'NoneType' object has no attribute 'data'"
    )
    app.dependency_overrides[get_api_key_repository] = lambda: mock_repository

    response = integration_client.get(
        "/v1/test",
        headers=integration_auth_headers("not-a-valid-key-shape"),
    )

    app.dependency_overrides.pop(get_api_key_repository, None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_integration_test_endpoint_returns_ok_for_valid_key(
    integration_client: TestClient,
) -> None:
    mock_repository = MagicMock()
    mock_repository.lookup_by_hash.return_value = _valid_key_row()
    app.dependency_overrides[get_api_key_repository] = lambda: mock_repository

    response = integration_client.get(
        "/v1/test",
        headers=integration_auth_headers(),
    )

    app.dependency_overrides.pop(get_api_key_repository, None)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_repository.lookup_by_hash.assert_called_once()


def test_app_routes_do_not_require_integration_bearer_token(
    client: TestClient,
    mock_job_service: MagicMock,
) -> None:
    job_id = uuid4()
    mock_job_service.create_job.return_value = job_id

    response = client.post(
        "/v1/app/jobs",
        json=valid_job_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 201
    assert response.json() == {"id": str(job_id)}
